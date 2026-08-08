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
