"""NLM Notebook Registry — static mapping of domains to NotebookLM notebook IDs.

# R5 Phase 6 DEPRECATED (2026-05-17): NLM routing removed from RAG pipeline.
# NB UUIDs here (NB-2..NB-8) are preserved for human-facing NLM UI and NAGA agent.
# RAG orchestrator no longer routes queries through these notebooks.

Each domain has:
- notebook_id: operational notebook (NB-Xb) — T2+T3 verified guides
- primary_notebook_id: oracle notebook (NB-Xa) — T0+T1 law only (None until created)
- keywords: used by resolve_notebook() to route queries

Stale-ingestion gate (S1.3, 2026-04-25): resolve_notebook() can refuse to
return a notebook_id when its most recent ingestion canary verification
(written by apps.evaluator.nlm_deep_research.freshness_monitor.verify_ingestion_uuid)
is failing or missing within the configured staleness window. The caller
in nlm_orchestrator falls back to Qdrant-only when this happens.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

NLM_NOTEBOOKS: dict[str, dict] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",  # NB-2b operational
        "primary_notebook_id": None,  # NB-2a not yet created
        "label": "Immigration & Visa",
        "keywords": {
            "visa",
            "kitas",
            "kitap",
            "tka",
            "immigration",
            "imigrasi",
            "work permit",
            "stay permit",
            "foreigner",
            "expat",
        },
    },
    "company": {
        "notebook_id": "933509f9-1561-403d-bd44-4a7a67a36df2",  # NB-3
        "primary_notebook_id": None,
        "label": "Company & Licensing",
        "keywords": {
            "company",
            "kbli",
            "pma",
            "oss",
            "licensing",
            "nib",
            "investment",
            "business",
            "pt ",
            "perseroan",
        },
    },
    "tax": {
        "notebook_id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # NB-4
        "primary_notebook_id": None,
        "label": "Tax & Compliance",
        "keywords": {
            "tax",
            "compliance",
            "lkpm",
            "npwp",
            "pph",
            "ppn",
            "coretax",
            "bpjs",
            "fiscal",
            "pajak",
        },
    },
    "property": {
        "notebook_id": "d9438180-5e63-4e2a-a473-6061101f6a8d",  # NB-5
        "primary_notebook_id": None,
        "label": "Property & Zoning",
        "keywords": {
            "property",
            "zoning",
            "land",
            "hgb",
            "hak pakai",
            "building",
            "villa",
            "real estate",
            "leasehold",
        },
    },
    "operations": {
        "notebook_id": "85207af3-352f-4554-8d2a-18f42cc541ba",  # NB-6
        "primary_notebook_id": None,
        "label": "Operations",
        "keywords": {"sop", "team", "pricing", "crm", "workflow", "competitor"},
    },
    "editorial": {
        "notebook_id": "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8",  # NB-7
        "primary_notebook_id": None,
        "label": "Editorial & Market",
        "keywords": {
            "seo",
            "content",
            "market",
            "intel",
            "trends",
            "news",
            "article",
            "editorial",
        },
    },
    "lifestyle": {
        "notebook_id": "4fd8cd0f-93f1-4e43-9c9e-86c0d581852c",  # NB-8
        "primary_notebook_id": None,
        "label": "Expat Life",
        "keywords": {
            "lifestyle",
            "expat",
            "healthcare",
            "cost of living",
            "culture",
            "digital nomad",
            "education",
            "school",
        },
    },
}

# Keywords that indicate the user wants T0/T1 primary law sources
_PRIMARY_LAW_KEYWORDS = frozenset(
    {"pasal", "uu ", "pp ", "peraturan", "permenkumham", "permen", "undang"},
)


# ── Stale-ingestion gate (S1.3) ──────────────────────────────────────────────


def _default_freshness_state_path() -> Path | None:
    """Resolve the in-repo default path for freshness_monitor_state.json.

    Returns the monorepo path when the file is reachable, otherwise ``None``.

    Layout assumption: this module lives at
        <repo>/apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py
    so the repo root is ``parents[5]``. On Fly Docker the source tree is
    flattened to ``/app/backend/...`` (4 ancestors only), and ``parents[5]``
    raises ``IndexError``. The lookup is wrapped in try/except so the
    Docker import path stays clean — callers that need the freshness gate
    set ``NLM_FRESHNESS_STATE_FILE`` explicitly via env var; callers that
    don't need it (e.g. the orchestrator import on every query) tolerate
    a ``None`` default and fall through to the existing
    ``never_verified`` graceful-degradation branch in
    ``is_freshness_state_fresh``.
    """
    try:
        repo_root = Path(__file__).resolve().parents[5]
    except IndexError:
        return None
    return (
        repo_root / "apps" / "evaluator" / "nlm_deep_research"
        / "freshness_monitor_state.json"
    )


_DEFAULT_MAX_STALE_HOURS = 24

# Sentinel path used when neither the env override nor the repo default is
# resolvable. ``read_text`` on a non-existent path raises ``FileNotFoundError``,
# which ``is_freshness_state_fresh`` already treats as ``never_verified`` —
# so the gate degrades gracefully instead of crashing the orchestrator import.
_MISSING_STATE_PATH = Path("/nonexistent/nlm_freshness_state_unavailable.json")


def _resolve_state_path() -> Path:
    """State file path is resolvable from env var or repo default.

    The freshness_monitor lives under ``apps/evaluator``; the backend-rag
    process either runs from the same monorepo (Pro Mac local) or from a
    Docker image that mounts/copies the state file. Allow override via
    ``NLM_FRESHNESS_STATE_FILE`` env var so tests and Fly.io deploys can
    pin a path explicitly.

    When the env var is unset AND the repo-default path cannot be resolved
    (e.g. Fly Docker, where ``parents[5]`` does not exist), returns a
    sentinel path that ``is_freshness_state_fresh`` will treat as
    ``never_verified`` — graceful degradation, no crash.
    """
    env = os.environ.get("NLM_FRESHNESS_STATE_FILE")
    if env:
        return Path(env)
    default = _default_freshness_state_path()
    if default is not None:
        return default
    return _MISSING_STATE_PATH


def _max_stale_hours() -> int:
    raw = os.environ.get("NLM_MAX_STALE_HOURS")
    if not raw:
        return _DEFAULT_MAX_STALE_HOURS
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_STALE_HOURS


def check_ingestion_freshness(
    notebook_id: str,
    *,
    max_stale_hours: int | None = None,
    state_path: Path | None = None,
) -> dict[str, object]:
    """Inspect the most recent ingestion canary for a notebook.

    Reads ``freshness_monitor_state.json`` and returns a verdict suitable
    for gating oracle queries.

    Args:
        notebook_id: NLM notebook UUID.
        max_stale_hours: Override threshold (default 24, env override
            ``NLM_MAX_STALE_HOURS``).
        state_path: Override state file path (test injection).

    Returns:
        Dict with keys:
          - ``status`` — "fresh", "stale", "never_verified"
          - ``last_status`` — "ok", "stale", "error", or None
          - ``age_hours`` — float or None
          - ``last_uuid`` — last canary UUID or None
          - ``reason`` — short string, present when not fresh

    The function never raises on disk errors — a missing/corrupt state
    file is treated as ``never_verified`` so oracle behavior degrades
    gracefully (caller may decide whether to fail-open or fail-closed).
    """
    threshold = max_stale_hours if max_stale_hours is not None else _max_stale_hours()
    path = state_path or _resolve_state_path()

    verdict: dict[str, object] = {
        "status": "never_verified",
        "last_status": None,
        "age_hours": None,
        "last_uuid": None,
    }

    try:
        raw = path.read_text()
    except FileNotFoundError:
        verdict["reason"] = f"freshness state file not found: {path}"
        return verdict
    except OSError as exc:
        logger.warning("freshness state unreadable (%s): %s", path, exc)
        verdict["reason"] = f"state file unreadable: {exc}"
        return verdict

    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("freshness state malformed: %s", exc)
        verdict["reason"] = "state file malformed"
        return verdict

    verifications = state.get("ingestion_verifications") or {}
    entry = verifications.get(notebook_id)
    if not entry:
        verdict["reason"] = "no canary verification on record"
        return verdict

    last = entry.get("last") or {}
    started_at = last.get("started_at")
    last_status = last.get("status")
    verdict["last_status"] = last_status
    verdict["last_uuid"] = last.get("uuid")

    if not started_at:
        verdict["reason"] = "last verification has no timestamp"
        return verdict

    try:
        ts = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        verdict["reason"] = f"timestamp not parseable: {started_at}"
        return verdict

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    age = datetime.now(tz=timezone.utc) - ts
    age_hours = age.total_seconds() / 3600
    verdict["age_hours"] = round(age_hours, 2)

    if last_status != "ok":
        verdict["status"] = "stale"
        verdict["reason"] = f"last canary status={last_status}"
        return verdict

    if age_hours > threshold:
        verdict["status"] = "stale"
        verdict["reason"] = (
            f"last canary {age_hours:.1f}h ago > threshold {threshold}h"
        )
        return verdict

    verdict["status"] = "fresh"
    return verdict


def resolve_multi_notebook(
    query: str,
    threshold: int = 1,
    max_notebooks: int = 4,
) -> list[dict[str, object]]:
    """Resolve a query to multiple matching notebooks (ARCH-4 cross-notebook).

    Returns ordered list (by match score) of matching domains.
    Returns empty list if fewer than 2 domains match.

    Args:
        query: Free-text user query.
        threshold: Minimum keyword hits to include a domain.
        max_notebooks: Maximum notebooks to include in fan-out.

    Returns:
        List of dicts with keys ``domain``, ``notebook_id``, ``label``, ``score``.
        Empty list if < 2 domains match (single-domain query).
    """
    if not query:
        return []

    query_lower = query.lower()
    scored: list[tuple[int, str]] = []

    for domain, data in NLM_NOTEBOOKS.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score >= threshold:
            scored.append((score, domain))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_notebooks]

    if len(top) < 2:
        return []  # Not a multi-domain query

    return [
        {
            "domain": domain,
            "notebook_id": NLM_NOTEBOOKS[domain]["notebook_id"],
            "label": NLM_NOTEBOOKS[domain]["label"],
            "score": score,
        }
        for score, domain in top
    ]


def resolve_notebook(
    query: str,
    *,
    enforce_freshness: bool | None = None,
    max_stale_hours: int | None = None,
) -> dict[str, object] | None:
    """Resolve a user query to the best-matching NLM notebook.

    When a primary notebook exists for the domain, returns it for
    regulation-heavy queries (pasal, uu, pp, permenkumham, etc.).
    Otherwise returns the operational notebook.

    Args:
        query: Free-text user query.
        enforce_freshness: If True, gate the result on ingestion canary
            freshness (S1.3). When the chosen notebook has no recent
            successful canary, return ``None`` (the caller falls back to
            Qdrant-only retrieval). Defaults to the env var
            ``NLM_ENFORCE_FRESHNESS`` (any truthy value enables it),
            else False — backward compatible no-op.
        max_stale_hours: Override the freshness threshold (default 24h,
            env ``NLM_MAX_STALE_HOURS``).

    Returns:
        A dict with keys ``domain``, ``notebook_id``, ``label``,
        ``keywords``, ``primary_notebook_id``, plus ``freshness`` (the
        verdict from check_ingestion_freshness) when that check is
        actually performed. Returns ``None`` if no domain matches OR
        when enforce_freshness is on and the chosen notebook is stale.
    """
    if not query:
        return None

    query_lower = query.lower()
    wants_primary = any(kw in query_lower for kw in _PRIMARY_LAW_KEYWORDS)

    best_domain: str | None = None
    best_score: int = 0

    for domain, data in NLM_NOTEBOOKS.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score > best_score:
            best_score = score
            best_domain = domain

    if best_domain is None:
        return None

    data = NLM_NOTEBOOKS[best_domain]
    primary = data.get("primary_notebook_id")
    active_id = primary if (wants_primary and primary) else data["notebook_id"]

    # Resolve enforce_freshness: explicit arg > env var > False (legacy default)
    if enforce_freshness is None:
        enforce_freshness = os.environ.get("NLM_ENFORCE_FRESHNESS", "").lower() in (
            "1", "true", "yes", "on",
        )

    result: dict[str, object] = {
        "domain": best_domain,
        "notebook_id": active_id,
        "primary_notebook_id": data.get("primary_notebook_id"),
        "label": data["label"],
        "keywords": frozenset(data["keywords"]),
    }

    if enforce_freshness:
        verdict = check_ingestion_freshness(
            active_id,  # type: ignore[arg-type]
            max_stale_hours=max_stale_hours,
        )
        result["freshness"] = verdict
        if verdict["status"] != "fresh":
            logger.info(
                "NLM oracle gate: refusing notebook %s (%s) — %s",
                active_id,
                best_domain,
                verdict.get("reason"),
            )
            return None

    return result
