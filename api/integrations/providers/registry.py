"""Maps a `Provider` value to its adapter module, so views/tasks dispatch by
string without a chain of if/elif."""

from __future__ import annotations

from integrations.models import Provider

from . import figma, github, google_meet, notion, zoom

MODULES = {
    Provider.ZOOM: zoom,
    Provider.GOOGLE_MEET: google_meet,
    Provider.GITHUB: github,
    Provider.FIGMA: figma,
    Provider.NOTION: notion,
}


def get(provider: str):
    try:
        return MODULES[provider]
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {provider}") from exc
