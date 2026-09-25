"""
Upload pipeline.

Section 7.2 is blunt about why this file exists: uploads are the most common
path to remote code execution in a marketplace, because the entire product
depends on users sending files to each other. Every rule from that section is
implemented here.

  * Type validation by magic-byte inspection, never by extension or the
    client-supplied content type.
  * Size limits enforced before the bytes are written anywhere.
  * Images re-encoded server-side, which strips EXIF (including GPS) and
    destroys any polyglot payload.
  * Antivirus scanning before a file is ever released for download.
  * Private storage, reached only through short-lived signed URLs.
  * Downloads forced with Content-Disposition: attachment and nosniff.

Magic-byte sniffing is implemented directly rather than via libmagic: the
allowlist a marketplace needs is small and explicit, and a native dependency
that behaves differently across developer machines and CI is a poor trade for
a table this size.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

# --- Type detection --------------------------------------------------------

#: (offset, signature, content type). Order matters only in that the first
#: match wins; the signatures are distinct enough that it does not in practice.
_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"%PDF-", "application/pdf"),
    (4, b"ftyp", "video/mp4"),
    # Office formats and any other zip container. Narrowed by the per-purpose
    # allowlist rather than by inspecting the archive, which we deliberately do
    # not walk.
    (0, b"PK\x03\x04", "application/zip"),
)

#: WEBP needs two probes: "RIFF" at 0 and "WEBP" at 8.
_RIFF, _WEBP = b"RIFF", b"WEBP"

IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

#: What each purpose is allowed to accept. Anything not listed is rejected.
ALLOWED_TYPES: dict[str, frozenset[str]] = {
    "avatar": frozenset({"image/jpeg", "image/png", "image/webp"}),
    "identity": frozenset({"image/jpeg", "image/png", "image/webp", "application/pdf"}),
    "portfolio": IMAGE_TYPES | {"application/pdf", "video/mp4"},
    "deliverable": IMAGE_TYPES | {"application/pdf", "video/mp4", "application/zip"},
    "attachment": IMAGE_TYPES | {"application/pdf", "application/zip"},
    # A service's pictures and its one optional video. GIF is left out: it
    # is re-encoded to a still PNG, so an animation would silently freeze.
    "gig_image": frozenset({"image/jpeg", "image/png", "image/webp"}),
    "gig_video": frozenset({"video/mp4"}),
}


def sniff(head: bytes) -> str | None:
    """Return the content type proven by the leading bytes, or None."""
    if head[0:4] == _RIFF and head[8:12] == _WEBP:
        return "image/webp"
    for offset, signature, content_type in _SIGNATURES:
        if head[offset : offset + len(signature)] == signature:
            return content_type
    return None


# --- Validation and normalisation ------------------------------------------


@dataclass(frozen=True, slots=True)
class PreparedUpload:
    """A file that has passed validation and been normalised, ready to store."""

    data: bytes
    content_type: str
    original_name: str
    checksum: str

    @property
    def size(self) -> int:
        return len(self.data)


#: A single frame this large is already far past anything a profile photo or
#: portfolio image needs, and refusing it early is what stops a decompression
#: bomb from exhausting memory during re-encode.
MAX_IMAGE_PIXELS = 50_000_000


def prepare_upload(uploaded, purpose: str, *, max_bytes: int | None = None) -> PreparedUpload:
    """Validate and normalise an uploaded file.

    Raises ``ValidationError`` with a message safe to show the user. The
    returned bytes are what should be persisted — for images that is a freshly
    re-encoded file, not the original.
    """
    limit = max_bytes or settings.MAX_UPLOAD_BYTES
    if uploaded.size > limit:
        raise ValidationError(f"File is larger than the {limit // (1024 * 1024)} MB limit.")
    if uploaded.size == 0:
        raise ValidationError("File is empty.")

    allowed = ALLOWED_TYPES.get(purpose)
    if allowed is None:
        raise ValidationError(f"Unknown upload purpose '{purpose}'.")

    data = uploaded.read()
    if len(data) > limit:  # A lying `size` attribute must not get past the limit.
        raise ValidationError(f"File is larger than the {limit // (1024 * 1024)} MB limit.")

    content_type = sniff(data[:32])
    if content_type is None:
        raise ValidationError("File type could not be identified.")
    if content_type not in allowed:
        readable = ", ".join(sorted(t.split("/")[-1] for t in allowed))
        raise ValidationError(f"That file type is not accepted here. Allowed: {readable}.")

    if content_type in IMAGE_TYPES:
        data, content_type = _reencode_image(data)

    return PreparedUpload(
        data=data,
        content_type=content_type,
        original_name=_safe_name(uploaded.name),
        checksum=hashlib.sha256(data).hexdigest(),
    )


def _reencode_image(data: bytes) -> tuple[bytes, str]:
    """Decode and re-encode, which is what actually removes the risk.

    A re-encoded image carries none of the original file's metadata and none of
    its trailing bytes, so EXIF/GPS is gone and any payload smuggled alongside
    valid image data does not survive.
    """
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            has_alpha = image.mode in ("RGBA", "LA", "P")
            target = "PNG" if has_alpha else "JPEG"
            converted = image.convert("RGBA" if has_alpha else "RGB")
            out = io.BytesIO()
            # `exif` and other metadata blocks are simply not carried over.
            if target == "JPEG":
                converted.save(out, format="JPEG", quality=88, optimize=True)
            else:
                converted.save(out, format="PNG", optimize=True)
    except ValidationError:
        raise
    except Exception as exc:  # Pillow raises a wide variety for malformed input.
        raise ValidationError("Image could not be processed.") from exc

    return out.getvalue(), "image/jpeg" if target == "JPEG" else "image/png"


def _safe_name(name: str) -> str:
    """Keep a human-readable label without letting it influence any path."""
    cleaned = Path(name or "file").name.replace("\x00", "")
    return cleaned[:255] or "file"


# --- Storage ---------------------------------------------------------------


class Storage(ABC):
    """Adapter boundary.

    Local disk today, S3-compatible object storage later. Per the design rule
    in Section 4.1, nothing in the business logic knows which.
    """

    @abstractmethod
    def write(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalPrivateStorage(Storage):
    """Files under a private root, outside anything the web server serves."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.STORAGE_ROOT)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        # Refuse anything that escapes the storage root, whatever the key said.
        if not path.is_relative_to(self.root.resolve()):
            raise ValidationError("Invalid storage key.")
        return path

    def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def get_storage() -> Storage:
    if settings.STORAGE_BACKEND == "local":
        return LocalPrivateStorage()
    raise NotImplementedError(f"Unsupported storage backend '{settings.STORAGE_BACKEND}'.")


def build_key(purpose: str, owner_id: int, checksum: str) -> str:
    """An opaque key, never derived from the user-supplied filename."""
    return f"{purpose}/{owner_id}/{checksum[:16]}{secrets.token_hex(8)}"


def store(uploaded, *, owner, purpose: str, max_bytes: int | None = None):
    """Run the full pipeline and persist the result.

    Returns an unsaved-to-clean ``StoredFile`` that is already committed to
    storage and queued for scanning. It is not downloadable until the scan
    clears it.
    """
    from .models import StoredFile
    from .tasks import scan_file

    prepared = prepare_upload(uploaded, purpose, max_bytes=max_bytes)
    key = build_key(purpose, owner.pk, prepared.checksum)
    get_storage().write(key, prepared.data)

    record = StoredFile.objects.create(
        owner=owner,
        purpose=purpose,
        key=key,
        original_name=prepared.original_name,
        content_type=prepared.content_type,
        size_bytes=prepared.size,
        checksum=prepared.checksum,
    )
    scan_file.delay(record.pk)
    return record


# --- Signed access ---------------------------------------------------------


def sign(key: str, ttl: int | None = None) -> str:
    """Mint a short-lived token granting read access to exactly one object."""
    expires = int(time.time()) + (ttl or settings.FILE_URL_TTL_SECONDS)
    payload = f"{key}:{expires}".encode()
    signature = hmac.new(settings.FILE_SIGNING_KEY.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + b"." + signature).decode().rstrip("=")


#: A SHA-256 digest is always this long, which is what makes the split below
#: unambiguous.
_SIGNATURE_BYTES = hashlib.sha256().digest_size


def verify(token: str) -> str:
    """Return the storage key a token grants, or raise ``ValidationError``.

    The signature is split off by its known length rather than by searching for
    the ``.`` separator. Splitting on the delimiter looks equivalent and is not:
    the signature is 32 *raw* bytes, so roughly one token in eight contains a
    0x2E byte of its own, and `rsplit` would cut there instead — rejecting a
    token the server had just minted correctly.
    """
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload, separator, signature = (
            raw[: -_SIGNATURE_BYTES - 1],
            raw[-_SIGNATURE_BYTES - 1 : -_SIGNATURE_BYTES],
            raw[-_SIGNATURE_BYTES:],
        )
        if separator != b".":
            raise ValueError("Missing separator.")
        key, expires = payload.decode().rsplit(":", 1)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("Malformed file token.") from exc

    expected = hmac.new(settings.FILE_SIGNING_KEY.encode(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValidationError("Invalid file token.")
    if int(expires) < time.time():
        raise ValidationError("This link has expired.")
    return key


def signed_url(stored_file, ttl: int | None = None) -> str:
    from django.urls import reverse

    return reverse("signed-file", kwargs={"token": sign(stored_file.key, ttl)})
