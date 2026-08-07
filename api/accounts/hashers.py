"""
Password hashing parameters.

Django's Argon2id defaults are already strong, but they are *defaults* — they
move between releases, and a future upgrade could lower them without anything
in this repository changing. Pinning them here makes the cost factor an
explicit, reviewable decision, and Django's `must_update` machinery re-hashes
every user transparently on their next login whenever these numbers rise.

Current settings, against OWASP's 2024 Argon2id floor (m=19 MiB, t=2, p=1):

    memory_cost  102400 KiB (100 MiB)   ~5x the floor
    time_cost    3 passes               above the floor
    parallelism  4 lanes

Raising `memory_cost` is the most effective single change against GPU and ASIC
attackers, which is where the headroom went.
"""

from __future__ import annotations

from django.contrib.auth.hashers import Argon2PasswordHasher


class SkilRizeArgon2Hasher(Argon2PasswordHasher):
    """Argon2id with cost factors pinned rather than inherited."""

    memory_cost = 102_400
    time_cost = 3
    parallelism = 4
