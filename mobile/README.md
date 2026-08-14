# SkilRize — mobile client

Flutter client for the SkilRize API. Phase 7; see `DECISIONS.md` D38 for scope.

## What it does

Sign in (including both second-factor paths), see your verification status,
browse and search projects, read contracts and their milestones, and read the
notification centre. Push device registration is wired to the Phase 7 backend
and gated on whether the deployment can actually deliver a push.

**This is a foundation, not parity with the web app.** The web client is ~35
routes across every phase built; this is the slice that makes a phone useful.
Gigs, communities, messaging, the CRM, the admin console, and the money
actions are deliberately not here — see D38.

## Running it

```bash
flutter pub get
```

Against the local Docker stack (`docker compose up` from the repo root):

```bash
flutter run -d chrome --web-port 3100
```

Port 3100 matters: it is the origin in the API's `CORS_ALLOWED_ORIGINS`.
On the Android emulator the host is reachable as `10.0.2.2`, and a physical
device needs the machine's LAN address:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

## Tests

```bash
flutter analyze
flutter test
```

There is a second suite that runs against a **real** running API rather than
mocks — it is what proves the client and Django actually agree on tokens and
JSON shapes. It needs `docker compose up` and a seeded account, so it is
tagged and skipped by default:

```bash
flutter test --tags live --run-skipped
```

Override the account it uses with
`--dart-define=LIVE_EMAIL=... --dart-define=LIVE_PASSWORD=...`.

## Notes worth knowing

**Auth is bearer, not cookies.** `accounts/auth.py` documents the split —
"Web sends cookies; mobile sends `Authorization: Bearer`" — and this client
takes the bearer path, so it needs no CSRF token and no cookie jar. The
tokens are handed over because the client identifies itself with
`X-Skilrize-Client: native`; see `ApiClient.nativeClientHeader`.

**The web build does not persist a session.** There is no browser equivalent
of the Android Keystore, and `localStorage` is readable by injected script —
which is the exact thing the web app's HttpOnly cookies exist to avoid. The
web build therefore keeps tokens in memory and signs out on reload. It exists
so the app can be run and verified without an emulator, not as a shipping
web client. See `MemoryTokenStore`.

**Push has no token source yet.** Registration, gating, and unregistration
are real and tested; obtaining the FCM token itself needs a Firebase project
(`google-services.json` / an APNs key) that does not exist for this
environment. One `TODO` in `push_settings.dart` marks the single call.
