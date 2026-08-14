# SkilRize — mobile client

Flutter client for the SkilRize API. Phase 7; see `DECISIONS.md` D38 for scope.

## What it does

Full parity with the web app's signed-in surface, not a slice of it: sign in
(including both second-factor paths and student email verification with a
real ID-card photo upload), browse and propose on projects, order and
manage gigs, fund/release/deliver/review contracts (money actions, gated the
same way the API gates them), message, browse communities, search, run the
professional layer (CRM, subscriptions, retainers, agencies, workspaces),
enter proof-of-work challenges, connect integrations and see contract
meetings/activity, use the role-gated admin console, manage account settings
and 2FA, and read the activity feed and showcase. Push device registration is
wired to the Phase 7 backend and gated on whether the deployment can
actually deliver a push.

Five bottom-nav destinations (Home / Work / Messages / Contracts / More)
rather than the web's ~35 routes — a phone nav bar cannot hold that many, so
everything outside the everyday loop lives one tap deeper under "More"
(`lib/src/screens/more_screen.dart`) and "Work" (`work_hub_screen.dart`). See
D38 and D40.

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

**The student ID card upload needs a browser hop for OAuth-style
integrations, not for itself.** `image_picker` reads a real photo/file from
the device and uploads it via multipart to `/auth/student/id-card/` — no
`TODO` there. The integrations "Connect" button is the one screen that does
carry a `TODO`: completing a provider's OAuth redirect needs a web view or
`url_launcher` external-browser hop, which is unwired until a provider has
real credentials to test the redirect against.

**Money-moving and plan-entitlement refusals share one banner, not two.**
`CanTransact`/`CanMoveMoney` (403) and the professional layer's
`upgrade_required` (402) read as the same shape of failure to a user — "you
can't do that yet" — so `MoneyGateBanner` branches on the error code once
rather than every money-adjacent screen reimplementing that branch.
