import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skilrize_mobile/src/api/api_error.dart';
import 'package:skilrize_mobile/src/api/client.dart';
import 'package:skilrize_mobile/src/api/token_store.dart';

void main() {
  group('ApiError', () {
    test('flattens a DRF serializer rejection into per-field messages', () {
      final error = ApiError.fromResponse(400, {
        'email': ['This field is required.'],
        'password': ['Too short.'],
      });

      expect(error.fields['email'], 'This field is required.');
      expect(error.fields['password'], 'Too short.');
      // With no `detail`, the first field message stands in so a caller
      // always has something to show.
      expect(error.message, 'This field is required.');
    });

    test('keeps the machine-readable code callers branch on', () {
      final error = ApiError.fromResponse(403, {
        'detail': 'Two-factor authentication is required.',
        'code': 'two_factor_required',
      });

      expect(error.code, 'two_factor_required');
      expect(error.message, 'Two-factor authentication is required.');
    });
  });

  group('ApiClient', () {
    test('refreshes once on a 401 and replays the original request', () async {
      final tokens = MemoryTokenStore();
      await tokens.save(access: 'stale', refresh: 'refresh-1');

      var refreshCalls = 0;
      var meCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh/')) {
          refreshCalls++;
          // The endpoint returns the rotated pair in the body precisely
          // because the caller supplied one there — the native path.
          expect(jsonDecode(request.body)['refresh'], 'refresh-1');
          return http.Response(
            jsonEncode({'access': 'fresh', 'refresh': 'refresh-2'}),
            200,
          );
        }
        meCalls++;
        if (request.headers['Authorization'] == 'Bearer stale') {
          return http.Response(jsonEncode({'detail': 'expired'}), 401);
        }
        return http.Response(jsonEncode({'email': 'member@example.com'}), 200);
      });

      final client = ApiClient(
        baseUrl: 'http://test.local',
        tokens: tokens,
        httpClient: mock,
      );
      final result = await client.get('/auth/me/');

      expect(refreshCalls, 1);
      // Once with the stale token, once replayed with the fresh one.
      expect(meCalls, 2);
      expect((result as Map)['email'], 'member@example.com');
      expect(await tokens.access(), 'fresh');
      expect(await tokens.refresh(), 'refresh-2');
    });

    test('gives up rather than looping when the refresh itself fails', () async {
      final tokens = MemoryTokenStore();
      await tokens.save(access: 'stale', refresh: 'dead');

      var refreshCalls = 0;
      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh/')) {
          refreshCalls++;
          return http.Response(jsonEncode({'code': 'token_reuse'}), 401);
        }
        return http.Response(jsonEncode({'detail': 'expired'}), 401);
      });

      final client = ApiClient(
        baseUrl: 'http://test.local',
        tokens: tokens,
        httpClient: mock,
      );

      await expectLater(client.get('/auth/me/'), throwsA(isA<ApiError>()));
      expect(refreshCalls, 1);
      // A refusal clears local state rather than leaving a token that will
      // never work again sitting in the keystore.
      expect(await tokens.access(), isNull);
    });

    test('sends the surface header only when it is not the global one', () async {
      final captured = <String, String?>{};
      final mock = MockClient((request) async {
        captured[request.url.path] = request.headers['X-Skilrize-Surface'];
        return http.Response(jsonEncode({'ok': true}), 200);
      });

      final client = ApiClient(
        baseUrl: 'http://test.local',
        tokens: MemoryTokenStore(),
        httpClient: mock,
      );

      await client.get('/projects/');
      expect(captured['/api/v1/projects/'], isNull);

      client.surface = 'university';
      await client.get('/contracts/');
      expect(captured['/api/v1/contracts/'], 'university');
    });

    test('a 204 answers with null rather than trying to decode an empty body', () async {
      final mock = MockClient((request) async => http.Response('', 204));
      final client = ApiClient(
        baseUrl: 'http://test.local',
        tokens: MemoryTokenStore(),
        httpClient: mock,
      );

      expect(await client.delete('/integrations/zoom/disconnect/'), isNull);
    });
  });
}
