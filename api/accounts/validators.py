"""
Password policy.

Django ships length, similarity, common-corpus, and all-numeric checks. These
add the composition and predictability rules the platform requires on top:
every password must draw on all four character classes, and must not be built
out of runs, keyboard walks, or a single repeated character.

A note on the trade-off, recorded here rather than argued in a review: strict
composition rules do push some users toward predictable shapes (`Password1!`).
That is why they are paired here with a *high* floor (12 characters), the
breach-corpus check, and the pattern rules below — the composition requirement
alone would be the weakest of the four, but stacked on the others it closes the
"twelve lowercase letters" hole without leaving the classic `Xxxxxxxx1!` one
open in its place.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

#: Rows of a US keyboard, plus the ordered alphabets, used to spot walks.
_SEQUENCES = (
    "abcdefghijklmnopqrstuvwxyz",
    "01234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
    "!@#$%^&*()",
)

#: Four classes. `SYMBOL` is "anything that is not a letter, digit, or space",
#: so Unicode punctuation and currency marks all count — the rule is about
#: widening the search space, not about memorising an approved list.
_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a lowercase letter", re.compile(r"[a-z]")),
    ("an uppercase letter", re.compile(r"[A-Z]")),
    ("a digit", re.compile(r"\d")),
    ("a symbol", re.compile(r"[^A-Za-z0-9\s]")),
)


class ComplexityValidator:
    """Require every one of the four character classes."""

    def validate(self, password: str, user=None) -> None:
        missing = [name for name, pattern in _CLASSES if not pattern.search(password)]
        if missing:
            raise ValidationError(
                _("Password must contain %(missing)s.") % {"missing": _join(missing)},
                code="password_missing_classes",
                params={"missing": missing},
            )

    def get_help_text(self) -> str:
        return _(
            "Your password must contain a lowercase letter, an uppercase letter, "
            "a digit, and a symbol."
        )


class PredictabilityValidator:
    """Reject runs, keyboard walks, and single-character padding.

    These are the shapes people reach for when a composition rule forces them to
    add variety they did not want — `aaaa`, `1234`, `qwerty`. Catching them here
    is what stops the complexity rule from simply relocating the weakness.
    """

    #: Four is the shortest run that is clearly deliberate rather than incidental
    #: ("passed" contains a run of two; "aaaa" does not happen by accident).
    RUN_LENGTH = 4

    def validate(self, password: str, user=None) -> None:
        lowered = password.lower()

        if re.search(rf"(.)\1{{{self.RUN_LENGTH - 1},}}", lowered):
            raise ValidationError(
                _("Password must not repeat the same character %(n)d or more times in a row.")
                % {"n": self.RUN_LENGTH},
                code="password_repeated_character",
            )

        for sequence in _SEQUENCES:
            reverse = sequence[::-1]
            for start in range(len(sequence) - self.RUN_LENGTH + 1):
                window = sequence[start : start + self.RUN_LENGTH]
                if window in lowered or window[::-1] in lowered or window in reverse:
                    raise ValidationError(
                        _("Password must not contain a predictable sequence such as %(window)s.")
                        % {"window": window},
                        code="password_sequential",
                    )

    def get_help_text(self) -> str:
        return _(
            "Your password must not contain repeated characters or predictable "
            "sequences such as 1234 or qwer."
        )


def _join(parts: list[str]) -> str:
    """`a, b, and c` — a readable list for an error a user has to act on."""
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"
