"""
Tests for the foundations.

The scope tests matter most: they are the seed of the cross-tenant leakage
suite that Section 4.4 makes a release gate. A build that cannot keep one
university's rows away from another does not ship, so the enforcement is proved
against real rows in a real table rather than asserted about in the abstract.
"""

from __future__ import annotations

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, models

from core import crypto
from core import files as filestore
from core.models import (
    AuditLog,
    Channel,
    NotificationCategory,
    NotificationPreference,
    ScopedModel,
)
from core.scope import (
    GLOBAL_SCOPE,
    UNRESTRICTED_SCOPE,
    Scope,
    ScopeDenied,
    ScopeNotSet,
    SurfaceKind,
    Visibility,
    resolve_for,
    use_scope,
)

User = get_user_model()


# --- Scope: the cross-tenant leakage suite ---------------------------------


class ScopedWidget(ScopedModel):
    """A concrete stand-in for the scopeable models later phases will add.

    Gigs, projects, communities, posts and message threads all inherit the same
    base, so proving the guarantee once here proves it for every one of them.
    The table is built inside the test transaction and vanishes on rollback,
    which is why it never appears in a migration.
    """

    name = models.CharField(max_length=50)

    class Meta:
        app_label = "core"


@pytest.fixture
def widgets(db):
    with connection.schema_editor() as editor:
        editor.create_model(ScopedWidget)
    return ScopedWidget


@pytest.fixture
def universities(db):
    from accounts.models import University

    return (
        University.objects.create(name="COMSATS", short_code="CUI"),
        University.objects.create(name="FAST", short_code="FAST"),
    )


def test_scoped_query_without_context_raises(widgets):
    """A scopeable model queried with no scope must raise, not return rows."""
    with pytest.raises(ScopeNotSet):
        list(widgets.objects.all())


def test_university_scope_never_sees_another_university(widgets, universities):
    """The central guarantee: X sees zero rows belonging to Y."""
    cui, fast = universities

    widgets.objects.unscoped().create(name="global", visibility=Visibility.GLOBAL)
    widgets.objects.unscoped().create(name="cui", visibility=Visibility.UNIVERSITY, university=cui)
    widgets.objects.unscoped().create(
        name="fast", visibility=Visibility.UNIVERSITY, university=fast
    )

    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=cui.pk)):
        assert {w.name for w in widgets.objects.all()} == {"cui"}

    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=fast.pk)):
        assert {w.name for w in widgets.objects.all()} == {"fast"}

    # The global surface sees only global content — portal content never leaks
    # into the public marketplace.
    with use_scope(GLOBAL_SCOPE):
        assert {w.name for w in widgets.objects.all()} == {"global"}

    # Guessing an id must not bypass scoping either.
    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=cui.pk)):
        assert not widgets.objects.filter(name="fast").exists()

    with use_scope(UNRESTRICTED_SCOPE):
        assert widgets.objects.count() == 3
    # The escape hatch is explicit and needs no context at all.
    assert widgets.objects.unscoped().count() == 3


def test_scope_is_a_pre_filter_not_a_post_filter(widgets, universities):
    """A count must not leak the existence of another university's rows."""
    cui, fast = universities
    widgets.objects.unscoped().create(
        name="shared", visibility=Visibility.UNIVERSITY, university=cui
    )
    widgets.objects.unscoped().create(
        name="shared", visibility=Visibility.UNIVERSITY, university=fast
    )

    with use_scope(Scope(SurfaceKind.UNIVERSITY, university_id=cui.pk)):
        assert widgets.objects.filter(name="shared").count() == 1


def test_university_content_requires_a_university(widgets, universities):
    """The two scope fields cannot contradict each other."""
    from django.core.exceptions import ValidationError as DjangoValidationError

    cui, _ = universities

    with pytest.raises(DjangoValidationError):
        widgets(name="orphan", visibility=Visibility.UNIVERSITY).clean()
    with pytest.raises(DjangoValidationError):
        widgets(name="confused", visibility=Visibility.GLOBAL, university=cui).clean()


@pytest.mark.django_db
def test_resolve_for_rejects_unentitled_university(universities):
    """A surface the user is not verified for is refused, not silently emptied."""
    cui, _ = universities
    outsider = User.objects.create_user("outsider@example.com", "correct-horse-battery")

    with pytest.raises(ScopeDenied):
        resolve_for(outsider, "university")

    student = User.objects.create_user("student@cui.edu.pk", "correct-horse-battery")
    student.university = cui
    student.student_verification_status = "verified"
    student.save()

    scope = resolve_for(student, "university")
    assert scope.kind is SurfaceKind.UNIVERSITY
    assert scope.university_id == cui.pk

    # Asking for a different university than the one they belong to.
    with pytest.raises(ScopeDenied):
        resolve_for(student, "university", university_id=cui.pk + 999)


def test_unknown_surface_is_rejected():
    with pytest.raises(ScopeDenied):
        resolve_for(None, "some-other-university")


def test_university_scope_requires_an_id():
    with pytest.raises(ValueError):
        Scope(SurfaceKind.UNIVERSITY)


# --- Files -----------------------------------------------------------------


def _png_bytes(size: tuple[int, int] = (8, 8)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (90, 76, 232)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(name: str, data: bytes):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


def test_type_is_decided_by_magic_bytes_not_extension():
    assert filestore.sniff(_png_bytes()[:32]) == "image/png"
    assert filestore.sniff(b"%PDF-1.7 ...") == "application/pdf"
    assert filestore.sniff(b"MZ\x90\x00 this is an executable") is None


def test_executable_renamed_as_an_image_is_rejected():
    """The attack this whole pipeline exists to stop."""
    with pytest.raises(ValidationError):
        filestore.prepare_upload(_upload("photo.png", b"MZ\x90\x00" + b"payload" * 40), "avatar")


def test_pdf_is_rejected_where_only_images_are_allowed():
    with pytest.raises(ValidationError):
        filestore.prepare_upload(_upload("scan.pdf", b"%PDF-1.7 " + b"x" * 100), "avatar")


def test_image_is_reencoded_and_metadata_is_stripped():
    from PIL import Image

    original = Image.new("RGB", (12, 12), (255, 0, 0))
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "SkilRizeTestCamera"  # Make
    exif[0x010E] = "taken at a private address"  # ImageDescription
    original.save(buffer, format="JPEG", exif=exif)
    raw = buffer.getvalue()
    assert b"SkilRizeTestCamera" in raw

    prepared = filestore.prepare_upload(_upload("photo.jpg", raw), "avatar")

    # Re-encoding is what actually removes it: none of the original metadata
    # survives, which is how EXIF GPS stops leaking a seller's home address.
    assert b"SkilRizeTestCamera" not in prepared.data
    assert b"private address" not in prepared.data
    assert prepared.content_type == "image/jpeg"


def test_oversize_upload_is_rejected():
    with pytest.raises(ValidationError):
        filestore.prepare_upload(_upload("big.png", _png_bytes()), "avatar", max_bytes=10)


def test_empty_upload_is_rejected():
    with pytest.raises(ValidationError):
        filestore.prepare_upload(_upload("nothing.png", b""), "avatar")


def test_signed_url_round_trip_and_tamper_resistance():
    token = filestore.sign("avatar/1/abc")
    assert filestore.verify(token) == "avatar/1/abc"

    with pytest.raises(ValidationError):
        filestore.verify(token[:-2] + "xy")
    with pytest.raises(ValidationError):
        filestore.verify("not-a-token")


def test_signed_url_survives_a_dot_byte_inside_the_signature():
    """A signature containing 0x2E must still verify.

    This was a real failure: `verify` split the token on the last ``.`` byte,
    and a raw SHA-256 signature contains one about an eighth of the time, so
    roughly one signed URL in eight was rejected as malformed. Picking the key
    by search rather than trusting a random draw is what makes it a regression
    test instead of a coin flip that passes seven times out of eight.
    """
    import base64
    import hashlib

    digest_size = hashlib.sha256().digest_size

    for index in range(500):
        key = f"avatar/1/probe{index}"
        token = filestore.sign(key)
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        # Everything after the separator is the signature; look for a dot in it.
        if b"." in raw[-digest_size:]:
            assert filestore.verify(token) == key
            return

    pytest.fail("No signature containing a dot byte was found in 500 attempts.")


def test_expired_signed_url_is_refused():
    with pytest.raises(ValidationError):
        filestore.verify(filestore.sign("avatar/1/abc", ttl=-1))


def test_storage_key_cannot_escape_the_root(tmp_path):
    storage = filestore.LocalPrivateStorage(tmp_path)
    storage.write("ok/file.bin", b"data")
    assert storage.read("ok/file.bin") == b"data"

    with pytest.raises(ValidationError):
        storage.write("../../escaped.bin", b"data")


def test_scanner_recognises_a_known_signature():
    """The scanner verdict itself, checked in memory.

    The EICAR string is assembled at runtime and never written to disk: it is
    the industry-standard antivirus test file, so a real endpoint scanner on
    the developer's machine will quarantine it the moment it is written and the
    test would fail for reasons that have nothing to do with our code.
    """
    from core.models import StoredFile
    from core.tasks import _scan_bytes

    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

    assert _scan_bytes(eicar) == StoredFile.ScanStatus.INFECTED
    assert _scan_bytes(b"an ordinary harmless file") == StoredFile.ScanStatus.CLEAN


def test_uploads_fail_closed_when_no_scanner_is_configured(settings):
    """The property that matters more than any signature match.

    If the scanner is unreachable the pipeline must refuse to call anything
    clean. A misconfiguration should cost downloads, not containment.
    """
    from core.models import StoredFile
    from core.tasks import _scan_bytes

    settings.REQUIRE_FILE_SCANNER = True
    settings.CLAMAV_HOST = ""

    assert _scan_bytes(b"an ordinary harmless file") == StoredFile.ScanStatus.FAILED


def test_an_unusable_scanner_verdict_is_never_treated_as_clean(settings):
    from core.tasks import _scan_with_clamav

    settings.CLAMAV_TIMEOUT = 1

    # Nothing is listening on this port, so the connection is refused. The
    # adapter must surface that rather than returning a verdict.
    with pytest.raises(Exception):  # noqa: B017 — socket errors vary by platform
        _scan_with_clamav(b"payload", "127.0.0.1", 1)


@pytest.mark.django_db
def test_a_file_is_not_downloadable_until_the_scan_clears_it():
    from core.models import StoredFile
    from core.tasks import scan_file

    user = User.objects.create_user("uploader@example.com", "correct-horse-battery")
    record = StoredFile.objects.create(
        owner=user,
        purpose=StoredFile.Purpose.ATTACHMENT,
        key="t/clean.png",
        original_name="clean.png",
        content_type="image/png",
        size_bytes=10,
        checksum="x" * 64,
    )
    # Pending on creation: nothing is released before it has been scanned.
    assert not record.is_downloadable

    filestore.get_storage().write(record.key, _png_bytes())
    assert scan_file(record.pk) == StoredFile.ScanStatus.CLEAN

    record.refresh_from_db()
    assert record.is_downloadable

    # And a file the scanner rejected stays sealed.
    record.scan_status = StoredFile.ScanStatus.INFECTED
    assert not record.is_downloadable


# --- Audit log -------------------------------------------------------------


@pytest.mark.django_db
def test_audit_log_is_append_only():
    user = User.objects.create_user("auditor@example.com", "correct-horse-battery")
    entry = AuditLog.record(actor=user, action=AuditLog.Action.LOGIN, target=user)

    entry.justification = "rewritten"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()

    entry.refresh_from_db()
    assert entry.justification == ""


# --- Notifications ---------------------------------------------------------


@pytest.mark.django_db
def test_security_notifications_cannot_be_silenced():
    user = User.objects.create_user("quiet@example.com", "correct-horse-battery")
    preference = NotificationPreference.objects.create(
        user=user,
        overrides={
            NotificationCategory.SECURITY: {Channel.EMAIL: False},
            NotificationCategory.ANNOUNCEMENT: {Channel.EMAIL: False},
        },
    )

    # Marketing can be turned off; a security notice cannot.
    assert preference.allows(NotificationCategory.ANNOUNCEMENT, Channel.EMAIL) is False
    assert preference.allows(NotificationCategory.SECURITY, Channel.EMAIL) is True


@pytest.mark.django_db
def test_sms_is_reserved_for_security_and_payment():
    user = User.objects.create_user("sms@example.com", "correct-horse-battery")
    preference = NotificationPreference.objects.create(
        user=user, overrides={NotificationCategory.MESSAGE: {Channel.SMS: True}}
    )

    assert preference.allows(NotificationCategory.MESSAGE, Channel.SMS) is False
    assert preference.allows(NotificationCategory.SECURITY, Channel.SMS) is True


@pytest.mark.django_db
def test_dispatch_writes_in_app_notification():
    from core.notify import dispatch

    user = User.objects.create_user("notify@example.com", "correct-horse-battery")
    notification = dispatch(user, NotificationCategory.VERIFICATION, "Hello", "Body")

    assert user.notifications.count() == 1
    assert not notification.is_read


# --- Field encryption ------------------------------------------------------


def test_encrypted_values_round_trip_and_differ_each_time():
    secret = "JBSWY3DPEHPK3PXP"
    first, second = crypto.encrypt(secret), crypto.encrypt(secret)

    assert first != second  # A fresh nonce per write.
    assert secret not in first
    assert crypto.decrypt(first) == crypto.decrypt(second) == secret


@pytest.mark.django_db
def test_totp_secret_is_not_stored_in_the_clear():
    from accounts.models import TwoFactorDevice

    user = User.objects.create_user("totp@example.com", "correct-horse-battery")
    device = TwoFactorDevice.objects.create(user=user, secret="JBSWY3DPEHPK3PXP")

    with connection.cursor() as cursor:
        cursor.execute("SELECT secret FROM accounts_twofactordevice WHERE id = %s", [device.pk])
        stored = cursor.fetchone()[0]

    assert "JBSWY3DPEHPK3PXP" not in stored
    device.refresh_from_db()
    assert device.secret == "JBSWY3DPEHPK3PXP"


# --- Beat schedule -----------------------------------------------------------


@pytest.mark.django_db
def test_every_previously_unscheduled_task_now_has_a_periodic_task_row():
    """Migration 0004 is the only place these six rows ever get created — a
    regression here means beat silently stopped running one of them."""
    from django_celery_beat.models import PeriodicTask

    expected = {
        "sweep-promotions": "core.tasks.sweep_promotions",
        "assess-review-integrity": "core.tasks.assess_review_integrity",
        "sweep-challenge-deadlines": "core.tasks.sweep_challenge_deadlines",
        "refresh-reputation": "core.tasks.refresh_reputation",
        "sweep-activity-sources": "integrations.tasks.sweep_activity_sources",
        "reindex-search": "core.tasks.reindex_search",
    }
    rows = {p.name: p.task for p in PeriodicTask.objects.filter(name__in=expected)}
    assert rows == expected
    assert all(p.enabled for p in PeriodicTask.objects.filter(name__in=expected))


# --- Security headers ---------------------------------------------------------


@pytest.mark.django_db
def test_hsts_is_sent_on_a_secure_request_when_debug_is_off(client, settings):
    """`SECURE_HSTS_SECONDS` etc. (Phase 11, D37) only apply under
    `DEBUG=False` in `settings.py`, and Django's `SecurityMiddleware` itself
    only ever adds the header when it believes the request came in over
    TLS — so this has to both flip `DEBUG` off and simulate a secure
    request to actually exercise the code path CI and production run."""
    settings.DEBUG = False
    settings.ALLOWED_HOSTS = ["testserver"]
    settings.SECURE_SSL_REDIRECT = False  # exercised separately; not this test's concern
    settings.SECURE_HSTS_SECONDS = 31536000
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    settings.SECURE_HSTS_PRELOAD = True

    response = client.get("/healthz", secure=True)

    header = response.headers["Strict-Transport-Security"]
    assert "max-age=31536000" in header
    assert "includeSubDomains" in header
    assert "preload" in header


# --- Error tracking ------------------------------------------------------------


def _sentry_client_is_active(*, dsn: str) -> bool:
    """Import `config.settings` fresh in a subprocess with `SENTRY_DSN` set
    (or not) in the environment. `sentry_sdk.init()` runs once, at import
    time, inside the settings module itself — the only way to observe
    whether it ran with a *different* `SENTRY_DSN` is a fresh interpreter,
    not a `settings` fixture override on an already-imported process."""
    import json
    import os
    import subprocess
    import sys

    from django.conf import settings

    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings", "SENTRY_DSN": dsn}
    result = subprocess.run(  # noqa: S603 — argv is a fixed list; only env vars are test-controlled
        [
            sys.executable,
            "-c",
            "import django; django.setup(); import sentry_sdk, json; "
            "print(json.dumps(sentry_sdk.get_client().is_active()))",
        ],
        cwd=str(settings.BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_sentry_is_inert_with_no_dsn_configured():
    assert _sentry_client_is_active(dsn="") is False


def test_sentry_actually_initialises_when_a_dsn_is_configured():
    assert _sentry_client_is_active(dsn="https://public@o0.ingest.sentry.io/1") is True
