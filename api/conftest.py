"""
Shared pytest configuration.

The production Argon2id cost factors (accounts.hashers) are deliberately
expensive — roughly a quarter of a second per hash. That is the correct number
for a login endpoint and the wrong one for a test suite that creates several
hundred users, where it is pure dead time and buys no coverage: no test asserts
on the hash format, only on whether authentication succeeds.

Overriding the hasher here keeps the suite fast without touching the
configuration that actually ships. Anything that needs the real hasher can ask
for it explicitly with `@pytest.mark.django_db` plus `settings.PASSWORD_HASHERS`.
"""

import pytest


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _no_device_verification(settings):
    """Skip the emailed new-device code for the suite by default.

    Every test client is an unrecognised device, so leaving this on would put
    an email round-trip in front of every single sign-in and rewrite a hundred
    tests that have nothing to do with it. The control is covered directly in
    `accounts/tests.py`, by tests that switch it back on.
    """
    settings.REQUIRE_NEW_DEVICE_VERIFICATION = False


@pytest.fixture(autouse=True)
def _no_device_cooloff(settings):
    """Neutralise the new-device hold for the suite by default.

    Every test client is by definition an unrecognised device, so leaving the
    cool-off on would gate every transactional test behind a two-hour wait and
    turn one security control into a hundred unrelated failures. The control
    itself is covered directly in `accounts/tests.py`, by tests that turn it
    back on.
    """
    settings.DEVICE_COOLOFF_SECONDS = 0


@pytest.fixture(autouse=True)
def _no_scanner_required(settings):
    """Run the suite against the built-in EICAR fallback.

    CI sets DEBUG=False, which would otherwise make the upload pipeline fail
    closed against a ClamAV instance no test environment has. The fail-closed
    behaviour itself is covered explicitly in `core/tests.py`, by a test that
    turns this back on.
    """
    settings.REQUIRE_FILE_SCANNER = False


@pytest.fixture(autouse=True)
def _payments_open(settings):
    """Give the suite a Swich merchant account to pay through (D55).

    Every payment refuses outright on a server with Swich off, and no test
    environment has real keys. Tests pay by playing Swich's part with these
    keys (`payments.testing.swich_pays`); the refusal itself is covered in
    `payments/tests.py`, by tests that switch Swich off again.
    """
    settings.SWICH_ENABLED = True
    settings.SWICH_ENV = "sandbox"
    settings.SWICH_CLIENT_ID = "test-client"
    settings.SWICH_SECRET_KEY = "test-secret-key"  # noqa: S105 — a test fixture, not a credential


@pytest.fixture(autouse=True)
def _http_test_client(settings):
    """Undo the two production settings the test client cannot satisfy.

    CI runs with `DEBUG=False`, which is correct — it is the configuration that
    ships. But Django's test client speaks plain http and has no TLS to offer,
    so `SECURE_SSL_REDIRECT` turns every single request into a 301 to
    `https://testserver/`, and `COOKIE_SECURE` means no session cookie is ever
    stored. The suite then fails everywhere at once for one reason that has
    nothing to do with what any of it is testing.

    Neither is relaxed in the shipped configuration: `settings.py` forces both
    on whenever `DEBUG` is off, and `manage.py check --deploy` is what proves
    it. This only tells the harness to stop redirecting itself.
    """
    settings.SECURE_SSL_REDIRECT = False
    settings.COOKIE_SECURE = False


@pytest.fixture(autouse=True)
def _tasks_run_inline(settings):
    """Run Celery tasks in-process.

    Notifications and confirmation emails are deliberately queued rather than
    sent inline with the request, so with a real broker the assertions that
    follow a sign-up would race a worker that CI does not run. Eager execution
    is how the test observes the outcome at all; `CELERY_TASK_ALWAYS_EAGER`
    otherwise defaults to `DEBUG`, which is on locally and off in CI — the same
    suite passing in one place and failing in the other.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(autouse=True)
def _generous_scoped_throttles():
    """Widen the named-scope rate limits (`login`, `otp`, `signup`,
    `password_reset`) for the suite, without touching what actually ships.

    `core.throttling.scoped_throttle` (Phase 11, D37) fixed a real bug where
    these rates were silently never enforced — `ScopedRateThrottle` keys a
    request by IP once the caller is authenticated, and every test client
    that plays two roles in one test (award a contract as the client,
    deliver as the freelancer, review as the client again) does several
    `sign_in()` round trips from the same `127.0.0.1` in well under a
    minute. A real user re-authenticating that fast from one address would
    be unusual; a test suite exercising the same fixture-built contract from
    both sides in sequence is not.

    Deliberately not the `settings` fixture (`settings.REST_FRAMEWORK =
    ...`) — DRF's `SimpleRateThrottle.THROTTLE_RATES` is bound, once, at
    import time, to the *same dict object* `settings.REST_FRAMEWORK[
    "DEFAULT_THROTTLE_RATES"]` pointed to then (`rest_framework/
    throttling.py`). Reassigning `settings.REST_FRAMEWORK` to a new dict —
    which is what `settings.REST_FRAMEWORK = {...}` does, and what the
    `settings` fixture's own restore-on-teardown needs to work — breaks that
    aliasing silently: the throttle class keeps reading the *old* dict
    forever, so the "override" has no effect on actual throttling, while
    still looking correct to anything that reads `settings.REST_FRAMEWORK`
    directly. Mutating `SimpleRateThrottle.THROTTLE_RATES` in place, and
    restoring the exact same values on teardown, is the only way to
    actually reach what the throttle reads. `DEFAULT_THROTTLE_RATES` in
    `settings.py` is unchanged — this widens only what the suite sees, the
    same way `_tasks_run_inline` and `_no_device_cooloff` above adapt the
    test environment without touching production configuration. The
    mechanism itself is proven directly, at the real production rate, by
    `test_signup_is_throttled_at_the_named_scope_rate`
    (`accounts/tests.py`), which sets it back down explicitly.
    """
    from rest_framework.throttling import SimpleRateThrottle

    original = dict(SimpleRateThrottle.THROTTLE_RATES)
    SimpleRateThrottle.THROTTLE_RATES.update(
        {
            "login": "1000/minute",
            "otp": "1000/minute",
            "signup": "1000/minute",
            "password_reset": "1000/minute",
            "integration_connect": "1000/minute",
            "meeting_schedule": "1000/minute",
            "activity_sync": "1000/minute",
            "push_device": "1000/minute",
            "data_export": "1000/minute",
            "account_delete": "1000/minute",
        }
    )
    yield
    SimpleRateThrottle.THROTTLE_RATES.clear()
    SimpleRateThrottle.THROTTLE_RATES.update(original)


@pytest.fixture(autouse=True)
def _isolated_cache():
    """Give every test a clean cache.

    The login lockout counts failures in the cache, so without this a test that
    exhausts the attempt budget would leak a locked account into whatever ran
    next — an order-dependent failure, which is the worst kind to debug.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
