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
