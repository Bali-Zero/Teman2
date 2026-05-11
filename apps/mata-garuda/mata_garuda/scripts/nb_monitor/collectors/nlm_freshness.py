"""nlm CLI based freshness collector.

Best-effort: cookie has 5min TTL. Any error path returns None and signals
`cookie_refresh_pending` upstream (the run loop translates None into
instrumentation_status). Spec §7.2.

Schema note (verified empirically 2026-05-08, nlm CLI v0.x):
`nlm notebook get <uuid> --json` returns sources as `[{"id", "title"}]`
without timestamp fields. `fetch_source_freshness_age_days` therefore
returns None on every call until an alternative timestamp source is
wired (tracked in design doc 2026-05-08-nb-source-freshness-alternative).
This file remains for the cookie/auth check side-effect (returncode=0)
and `fetch_source_count` which works correctly.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Sequence

logger = logging.getLogger(__name__)

NLM_BINARY = "nlm"
DEFAULT_TIMEOUT_S = 15
COOKIE_ERROR_MARKERS = ("authentication required", "re-run nlm login", "cookie expired")


class NLMFreshnessError(Exception):
    """Raised by callers that explicitly want the failure to bubble. Default path returns None."""


def _run_nlm(args: Sequence[str], timeout: int = DEFAULT_TIMEOUT_S) -> str | None:
    try:
        proc = subprocess.run(
            [NLM_BINARY, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("nlm_freshness: subprocess failure: %s", e)
        return None
    if proc.returncode != 0:
        merged = (proc.stdout + proc.stderr).lower()
        if any(m in merged for m in COOKIE_ERROR_MARKERS):
            logger.warning("nlm_freshness: cookie/auth error")
        else:
            logger.warning(
                "nlm_freshness: nlm returncode=%d stderr=%s",
                proc.returncode,
                proc.stderr[:200],
            )
        return None
    return proc.stdout


def _extract_sources(data: dict) -> list | None:
    """Normalize the two response shapes seen in practice.

    `nlm notebook get <uuid> --json` (verified 2026-05-08) wraps the body in
    `{"value": {"notebook_id": ..., "sources": [...]}}`. Older mocks/tests
    pass the body flat at top-level. Accept either; return None if neither
    has a list at `sources`.
    """
    sources = data.get("sources")
    if not isinstance(sources, list):
        nested = data.get("value", {})
        if isinstance(nested, dict):
            sources = nested.get("sources")
    return sources if isinstance(sources, list) else None


def fetch_source_count(uuid: str) -> int | None:
    """Return the number of sources in the notebook, or None on any failure."""
    out = _run_nlm(["notebook", "get", uuid, "--json"])
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    sources = _extract_sources(data)
    if sources is None:
        return None
    return len(sources)


def fetch_source_freshness_age_days(uuid: str, now_iso: str | None = None) -> int | None:
    """Return median age (days) of NB sources at `now_iso`, or None on failure.

    Currently always returns None: `nlm notebook get` does not expose source
    timestamps. Kept as a stub so callers (run.py L222-224) keep type contract.
    Replacement source for timestamps tracked in design doc
    `docs/superpowers/specs/2026-05-08-nb-source-freshness-alternative.md`.
    """
    out = _run_nlm(["notebook", "get", uuid, "--json"])
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    sources = _extract_sources(data)
    if not sources:
        return None

    now = (
        datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        if now_iso
        else datetime.now(timezone.utc)
    )
    ages: list[int] = []
    for s in sources:
        updated = s.get("updated_at") or s.get("created_at")
        if not isinstance(updated, str):
            continue
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError:
            continue
        ages.append((now - ts).days)
    if not ages:
        return None
    ages.sort()
    return ages[len(ages) // 2]
