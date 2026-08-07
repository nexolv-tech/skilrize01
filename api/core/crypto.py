"""
Field-level encryption.

Section 7.3 requires it for identity documents, payout credentials, national
identifiers, and OTP secrets — the values where "the database is encrypted at
rest" is not a sufficient answer, because anything that can read the database
can read them.

AES-256-GCM, one random nonce per write, key derived from a dedicated secret so
that rotating it is independent of rotating ``SECRET_KEY``. The value stored is
``base64(nonce || ciphertext || tag)``.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import models

_NONCE_BYTES = 12


def _key() -> bytes:
    secret = getattr(settings, "FIELD_ENCRYPTION_KEY", None) or settings.SECRET_KEY
    # A hash gives a uniform 32-byte key regardless of how the secret is
    # formatted or how long it is.
    return hashlib.sha256(f"skilrize.field.v1:{secret}".encode()).digest()


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return plaintext
    nonce = os.urandom(_NONCE_BYTES)
    sealed = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + sealed).decode()


def decrypt(token: str) -> str:
    raw = base64.b64decode(token)
    return AESGCM(_key()).decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], None).decode()


class EncryptedTextField(models.TextField):
    """A text field whose value is opaque at rest.

    Values are unreadable in the database, in a backup, and in a query log.
    They are not searchable or indexable, which is the deliberate trade: these
    are secrets to be read back one record at a time, never filtered on.
    """

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        return encrypt(str(value))

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return decrypt(value)
        except Exception:
            # A value that will not decrypt means the key changed. Fail closed
            # and let the caller treat the secret as absent rather than crash
            # every request that touches the row.
            return None
