"""
Automated grading: runs Lighthouse against a submitted URL.

An adapter, deliberately — same shape as `core.tasks._scan_bytes` for ClamAV.
`LIGHTHOUSE_ENABLED` gates whether this shells out to a real `lighthouse` CLI
at all, and is off by default: the worker image does not carry Node and
headless Chromium yet, and adding several hundred MB of Chromium to a
container that also has to fit comfortably on a 12GB free-tier VM is an
infrastructure decision on its own, not something to slip in as a side effect
of a feature change. What is real here is everything *around* that call — URL
safety, timeout handling, score extraction, the failure taxonomy. The day
Chromium lands in `api/Dockerfile`, this starts working with zero further
code changes.
"""

from __future__ import annotations

import json
import logging
import subprocess

from django.conf import settings

from .url_safety import UnsafeURLError, assert_safe_url

logger = logging.getLogger(__name__)

#: Composite score is an unweighted average across these. Equal weighting
#: rather than favouring performance on purpose — a challenge submission that
#: renders fast but fails every accessibility check is not a good submission
#: just because it is fast.
_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]


class GradingUnavailable(Exception):
    """Lighthouse is not configured, or the URL failed the SSRF check.

    Distinct from `GradingFailed`: this is an expected, environment-level
    state, not a broken submission — `Participation.automated_status` records
    it as UNAVAILABLE rather than FAILED for exactly that reason.
    """


class GradingFailed(Exception):
    """Lighthouse was configured and ran, but produced no usable result."""


def grade_url(url: str) -> dict:
    """Run Lighthouse against ``url``. Returns ``{"score": int, "report": dict}``.

    Raises `GradingUnavailable` if Lighthouse is not enabled or the URL fails
    the SSRF check, `GradingFailed` if it ran but the result could not be
    used. Callers are expected to catch both and record `automated_status`
    accordingly — neither is treated as a crash.
    """
    if not settings.LIGHTHOUSE_ENABLED:
        raise GradingUnavailable("Lighthouse is not enabled in this environment.")

    try:
        assert_safe_url(url)
    except UnsafeURLError as exc:
        raise GradingUnavailable(str(exc)) from exc

    try:
        completed = subprocess.run(  # noqa: S603 — argv is a fixed list, url is the one variable and is SSRF-checked above
            [  # noqa: S607 — "lighthouse" is resolved via PATH deliberately; the
                # container image is the one place its absolute path is guaranteed,
                # and that image doesn't exist yet either (LIGHTHOUSE_ENABLED is off)
                "lighthouse",
                url,
                "--output=json",
                "--output-path=stdout",
                "--quiet",
                "--chrome-flags=--headless=new --no-sandbox --disable-gpu",
                f"--max-wait-for-load={settings.LIGHTHOUSE_TIMEOUT_SECONDS * 1000}",
            ],
            capture_output=True,
            timeout=settings.LIGHTHOUSE_TIMEOUT_SECONDS + 30,
            check=True,
            text=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("lighthouse_run_failed url=%s error=%s", url, exc)
        raise GradingFailed(str(exc)) from exc

    try:
        payload = json.loads(completed.stdout)
        categories = payload["categories"]
        scores = {key: round(categories[key]["score"] * 100) for key in _CATEGORIES}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("lighthouse_unparseable url=%s error=%s", url, exc)
        raise GradingFailed(f"Could not parse Lighthouse output: {exc}") from exc

    composite = round(sum(scores.values()) / len(scores))
    return {"score": composite, "report": scores}
