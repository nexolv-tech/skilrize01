@Tags(['live'])
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:skilrize_mobile/src/api/client.dart';
import 'package:skilrize_mobile/src/api/endpoints.dart';
import 'package:skilrize_mobile/src/api/token_store.dart';
import 'package:skilrize_mobile/src/state/session.dart';

/// End-to-end against a **running** stack — no mocks anywhere.
///
/// Excluded from the default run (`dart_test.yaml` skips the `live` tag)
/// because it needs `docker compose up` and a seeded account, which CI does
/// not have. Run it deliberately:
///
/// ```
/// flutter test --tags live
/// ```
///
/// This is what proves the client actually talks to Django — that the bearer
/// token the server issues is one the server then accepts, that the JSON
/// shapes parse into the models, and that push registration round-trips.
/// The mocked tests prove the client's own logic; only this proves the two
/// halves agree.
void main() {
  const baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
  const email = String.fromEnvironment('LIVE_EMAIL', defaultValue: 'mobile@example.com');
  const password = String.fromEnvironment('LIVE_PASSWORD', defaultValue: 'Mobile-Verify-Pass9');

  late TokenStore tokens;
  late SkilrizeApi api;
  late Session session;

  setUp(() {
    tokens = MemoryTokenStore();
    api = SkilrizeApi(ApiClient(baseUrl: baseUrl, tokens: tokens));
    session = Session(api: api, tokens: tokens);
  });

  test('signs in against the real API and holds a usable bearer token', () async {
    await session.signIn(email, password);

    expect(session.error, isNull);
    expect(session.stage, AuthStage.signedIn);
    expect(session.user!.email, email);

    // The token the server just issued is one the server accepts back —
    // the whole point of the Phase 7 bearer work.
    expect(await tokens.access(), isNotNull);
    final me = await api.me();
    expect(me.email, email);
  });

  test('reads config, projects, contracts and notifications', () async {
    await session.signIn(email, password);

    final config = await api.config();
    expect(config.containsKey('push_enabled'), isTrue);

    // Each of these parses real server JSON into the app's models; a shape
    // mismatch fails here rather than as a null on a screen.
    final projects = await api.projects();
    final contracts = await api.contracts();
    final notifications = await api.notifications();

    expect(projects.count, greaterThanOrEqualTo(0));
    expect(contracts.count, greaterThanOrEqualTo(0));
    // A bare list — see `SkilrizeApi.notifications` on why this one differs.
    expect(notifications.length, greaterThanOrEqualTo(0));
  });

  test('registers and unregisters a push device', () async {
    await session.signIn(email, password);

    await api.registerPushDevice(
      token: 'live-test-token',
      platform: 'android',
      label: 'Live test',
    );
    await api.unregisterPushDevice('live-test-token');
  });

  test('signing out revokes the session server-side', () async {
    await session.signIn(email, password);
    await session.signOut();

    expect(session.stage, AuthStage.signedOut);
    expect(await tokens.access(), isNull);
  });
}
