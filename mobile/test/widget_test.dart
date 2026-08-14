import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skilrize_mobile/main.dart';
import 'package:skilrize_mobile/src/api/client.dart';
import 'package:skilrize_mobile/src/api/endpoints.dart';
import 'package:skilrize_mobile/src/api/token_store.dart';
import 'package:skilrize_mobile/src/state/session.dart';

/// A signed-in user payload shaped like `UserSerializer`'s real output.
const _user = {
  'id': 1,
  'email': 'member@example.com',
  'handle': 'member',
  'display_name': 'Member',
  'can_transact': false,
  'profile_complete': false,
  'missing_requirements': ['email', 'phone', 'identity'],
  'has_two_factor': false,
  'profile_strength': 10,
  'admin_role': '',
  'headline': '',
};

Session _session(MockClient mock, {TokenStore? store}) {
  final tokens = store ?? MemoryTokenStore();
  return Session(
    api: SkilrizeApi(
      ApiClient(baseUrl: 'http://test.local', tokens: tokens, httpClient: mock),
    ),
    tokens: tokens,
  );
}

void main() {
  group('sign-in', () {
    testWidgets('a plain password sign-in lands on the signed-in shell',
        (tester) async {
      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/login/')) {
          return http.Response(
            jsonEncode({'user': _user, 'access': 'a', 'refresh': 'r'}),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        if (request.url.path.endsWith('/config/')) {
          return http.Response(jsonEncode({'push_enabled': false}), 200);
        }
        // `/notifications/` answers with a bare list; every other list
        // endpoint uses the paginated envelope. Mirrored here so the mocks
        // cannot drift from what the server actually sends.
        if (request.url.path.endsWith('/notifications/')) {
          return http.Response(jsonEncode([]), 200);
        }
        return http.Response(jsonEncode({'count': 0, 'results': []}), 200);
      });

      final session = _session(mock);
      await tester.pumpWidget(SkilrizeApp(session: session));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('email')), 'member@example.com');
      await tester.enterText(find.byKey(const Key('password')), 'hunter2');
      await tester.tap(find.byKey(const Key('signIn')));
      await tester.pumpAndSettle();

      expect(session.isSignedIn, isTrue);
      expect(find.text('Overview'), findsOneWidget);
    });

    testWidgets('an account with an authenticator is asked for a code, not signed in',
        (tester) async {
      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/login/')) {
          return http.Response(
            jsonEncode({'two_factor_required': true, 'challenge': 'ch-1'}),
            200,
          );
        }
        return http.Response(jsonEncode({'push_enabled': false}), 200);
      });

      final session = _session(mock);
      await tester.pumpWidget(SkilrizeApp(session: session));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('email')), 'member@example.com');
      await tester.enterText(find.byKey(const Key('password')), 'hunter2');
      await tester.tap(find.byKey(const Key('signIn')));
      await tester.pumpAndSettle();

      expect(session.stage, AuthStage.twoFactorRequired);
      expect(session.isSignedIn, isFalse);
      expect(find.text('Enter your code'), findsOneWidget);
    });

    testWidgets('an unrecognised device is offered the emailed-code path instead',
        (tester) async {
      // Responses are built as raw UTF-8 bytes with no charset in the header,
      // which is exactly what DRF sends. Reading such a body through
      // `response.body` would decode it as latin-1 and mangle the `•` in the
      // masked address — a real bug this test caught in `ApiClient`.
      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/login/')) {
          return http.Response.bytes(
            utf8.encode(jsonEncode({
              'device_verification_required': true,
              'challenge': 'ch-2',
              'sent_to': 'm•••r@example.com',
            })),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response(jsonEncode({'push_enabled': false}), 200);
      });

      final session = _session(mock);
      await tester.pumpWidget(SkilrizeApp(session: session));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('email')), 'member@example.com');
      await tester.enterText(find.byKey(const Key('password')), 'hunter2');
      await tester.tap(find.byKey(const Key('signIn')));
      await tester.pumpAndSettle();

      expect(session.stage, AuthStage.deviceVerificationRequired);
      expect(find.text("Confirm it's you"), findsOneWidget);
      // The masked hint is shown so the right person is reassured and nobody
      // else learns the address.
      expect(find.textContaining('m•••r@example.com'), findsOneWidget);
    });

    testWidgets('a wrong password surfaces the server message and stays put',
        (tester) async {
      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/login/')) {
          return http.Response(
            jsonEncode({
              'detail': 'Email or password is incorrect.',
              'code': 'invalid_credentials',
            }),
            401,
          );
        }
        return http.Response(jsonEncode({'push_enabled': false}), 200);
      });

      final session = _session(mock);
      await tester.pumpWidget(SkilrizeApp(session: session));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('email')), 'member@example.com');
      await tester.enterText(find.byKey(const Key('password')), 'wrong');
      await tester.tap(find.byKey(const Key('signIn')));
      await tester.pumpAndSettle();

      expect(session.isSignedIn, isFalse);
      expect(find.text('Email or password is incorrect.'), findsOneWidget);
    });
  });

  group('push gating', () {
    testWidgets('the register button is disabled when the server says push is off',
        (tester) async {
      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/config/')) {
          return http.Response(jsonEncode({'push_enabled': false}), 200);
        }
        if (request.url.path.endsWith('/auth/login/')) {
          return http.Response(
            jsonEncode({'user': _user, 'access': 'a', 'refresh': 'r'}),
            200,
          );
        }
        // `/notifications/` answers with a bare list; every other list
        // endpoint uses the paginated envelope. Mirrored here so the mocks
        // cannot drift from what the server actually sends.
        if (request.url.path.endsWith('/notifications/')) {
          return http.Response(jsonEncode([]), 200);
        }
        return http.Response(jsonEncode({'count': 0, 'results': []}), 200);
      });

      final session = _session(mock);
      await tester.pumpWidget(SkilrizeApp(session: session));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('email')), 'member@example.com');
      await tester.enterText(find.byKey(const Key('password')), 'hunter2');
      await tester.tap(find.byKey(const Key('signIn')));
      await tester.pumpAndSettle();

      expect(session.pushEnabled, isFalse);
      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Register this device'),
      );
      // Disabled, so the OS permission prompt — which the platform grants
      // exactly once — is never spent on a deployment that cannot deliver.
      expect(button.onPressed, isNull);
    });
  });
}
