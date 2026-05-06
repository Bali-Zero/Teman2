"""nlm CLI based freshness collector.

Best-effort: cookie has 5min TTL. Any error path returns None and signals
`cookie_refresh_pending` upstream (the run loop translates None into
instrumentation_status). Spec §7.2.
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


def fetch_source_count(uuid: str) -> int | None:
    """Return the number of sources in the notebook, or None on any failure."""
    out = _run_nlm(["notebook", "info", uuid, "--json"])
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    sources = data.get("sources")
    if not isinstance(sources, list):
        return None
    return len(sources)


def fetch_source_freshness_age_days(uuid: str, now_iso: str | None = None) -> int | None:
    """Return median age (days) of NB sources at `now_iso`, or None on failure."""
    out = _run_nlm(["notebook", "info", uuid, "--json"])
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
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
