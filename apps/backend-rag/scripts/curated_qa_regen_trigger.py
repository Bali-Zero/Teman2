"""Delta quarantine trigger for the curated_qa verbatim cache (Phase-0
safety rail, FATAL 4 / MAJOR 6 —
research/operations/2026-07-17-full-domain-cache-design.md §8).

Reads a regulatory-watcher delta file
(research/regulatory/<date>-delta.json, schema {run_at, today,
new_today_count, partial, deltas:[{citation, title_id, title_en,
service_line, summary, source, verbatim_excerpt}], seen_citations} —
`service_line` is a LIST of strings, e.g. ["tax", "company"], NOT a bare
string), maps each delta's service_line(s) to a curated_qa domain via a
DETERMINISTIC table (never an LLM classification step — misrouting a delta
means a stale answer stays cached), and substring-matches `citation`
against every same-domain row's `law_refs` across the committed
data/curated_qa/*.jsonl corpora.

A match is a CANDIDATE, not a proof (a citation appearing is a signal, not
confirmation the row is actually invalidated) — it is written to
data/curated_qa/_regen-candidates/<date>.jsonl for the next generation
batch to review with priority, AND quarantined THE SAME DAY, fail-safe:
- FAQ (Redis) sink copy is deleted immediately (both the domain-scoped key
  and, defensively, the legacy unscoped key).
- Qdrant copy STAYS (still useful as grounding-injection evidence) but its
  payload is flagged regulatory_flagged=true — "stale/non-authoritative
  evidence", not deleted.

An unmapped service_line, or a `partial: true` delta run, is NEVER a
silent no-op — both are surfaced as alerts. Only `new_today_count == 0 AND
partial == false` is a true no-op.

This script makes NO LLM calls, ever — domain mapping is a lookup table,
citation matching is a substring scan, and the Qdrant "flag" re-upsert
reuses the ALREADY-STORED embedding (fetched via QdrantClient.get()) rather
than generating a new one.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/curated_qa_regen_trigger.py
    PYTHONPATH=. python scripts/curated_qa_regen_trigger.py --date 2026-07-18
    PYTHONPATH=. python scripts/curated_qa_regen_trigger.py --dry-run

Do NOT run against prod without confirming the Redis/Qdrant targets are
correct — this deletes/flags entries in the same sinks the live
orchestrator reads from.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import date as _date
from pathlib import Path
from typing import Any

logger = logging.getLogger("curated_qa_regen_trigger")

_SCRIPT_DIR = Path(__file__).resolve().parent
# scripts/ -> apps/backend-rag -> apps -> repo root
_REPO_ROOT = _SCRIPT_DIR.parents[2]
_REGULATORY_DIR = _REPO_ROOT / "research" / "regulatory"
_CURATED_QA_DATA_DIR = _SCRIPT_DIR.parent / "data" / "curated_qa"
_REGEN_CANDIDATES_DIR = _CURATED_QA_DATA_DIR / "_regen-candidates"

# Deterministic service_line -> curated_qa domain mapping (never an LLM
# classification step). Lookup is case-insensitive on the raw service_line
# token. Any service_line NOT in this table is UNMAPPED — surfaced as an
# alert, never silently dropped.
SERVICE_LINE_TO_DOMAIN: dict[str, str] = {
    "visa": "visa",
    "immigration": "visa",
    "tax": "tax",
    "company": "kbli",
    "business": "kbli",
    "oss": "kbli",
    "property": "property",
    "land": "property",
}


# ── Delta loading ────────────────────────────────────────────────────────────


def load_delta(date_str: str, *, delta_path: Path | None = None) -> dict[str, Any]:
    path = delta_path or (_REGULATORY_DIR / f"{date_str}-delta.json")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Corpus scan ──────────────────────────────────────────────────────────────


def _iter_corpus_jsonl_files() -> list[Path]:
    """Committed curated_qa corpora only — a plain, non-recursive glob on
    data/curated_qa/*.jsonl naturally excludes the _manifests/,
    _regen-candidates/, _archived/ subdirectories (this script's own
    machinery, never source corpora)."""
    if not _CURATED_QA_DATA_DIR.exists():
        return []
    return sorted(_CURATED_QA_DATA_DIR.glob("*.jsonl"))


def load_rows_by_domain(corpus_files: list[Path]) -> dict[str, list[tuple[Path, dict]]]:
    """domain -> [(source_file, row), ...] for every row across all corpus
    files. Malformed lines are skipped (best-effort scan, not the harvester's
    strict validate_row gate — this is a read-only candidate search)."""
    by_domain: dict[str, list[tuple[Path, dict]]] = {}
    for path in corpus_files:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            domain = row.get("domain")
            if not domain:
                continue
            by_domain.setdefault(domain, []).append((path, row))
    return by_domain


def match_citation_against_law_refs(citation: str, law_refs: list) -> bool:
    """Simple case-insensitive substring match — the same class of gate the
    guard-conformance family (cicatrix-superscar.md #3) says never to trust
    ALONE. Here it produces a CANDIDATE list, not an auto-invalidation —
    the next generation batch re-verifies with priority."""
    if not citation or not law_refs:
        return False
    citation_lower = citation.lower()
    return any(citation_lower in str(ref).lower() for ref in law_refs)


# ── Candidate matching ───────────────────────────────────────────────────────


def find_quarantine_candidates(
    deltas: list[dict],
    rows_by_domain: dict[str, list[tuple[Path, dict]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (candidate_records, unmapped_service_line_entries).

    candidate_records: one dict per (delta, matched row) pair — the schema
    written to data/curated_qa/_regen-candidates/<date>.jsonl.
    unmapped_service_line_entries: {citation, service_line} for every
    service_line token with no domain mapping — NEVER silently dropped,
    always surfaced as an alert by the caller.
    """
    candidates: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []

    for delta in deltas:
        citation = delta.get("citation", "")
        service_lines = delta.get("service_line") or []
        if isinstance(service_lines, str):
            service_lines = [service_lines]

        mapped_domains: set[str] = set()
        for sl in service_lines:
            domain = SERVICE_LINE_TO_DOMAIN.get(str(sl).strip().lower())
            if domain:
                mapped_domains.add(domain)
            else:
                unmapped.append({"citation": citation, "service_line": sl})

        for domain in mapped_domains:
            for source_file, row in rows_by_domain.get(domain, []):
                if match_citation_against_law_refs(citation, row.get("law_refs") or []):
                    candidates.append(
                        {
                            "citation": citation,
                            "domain": domain,
                            "question": row.get("question"),
                            "source_ref": row.get("source_ref"),
                            "source_file": str(source_file),
                            "law_refs": row.get("law_refs"),
                        },
                    )

    return candidates, unmapped


# ── Quarantine action (fail-safe, same-day) ─────────────────────────────────


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).isoformat()


async def quarantine_row(
    row: dict[str, Any],
    *,
    faq_cache: Any,
    qdrant_client: Any,
    citation: str,
) -> None:
    """Delete the FAQ-sink copy (domain-scoped key + legacy unscoped key,
    defensively) and flag the Qdrant copy `regulatory_flagged=true` — the
    Qdrant point STAYS (grounding-only evidence, now marked
    stale/non-authoritative), never deleted.

    Re-upserts using the SAME embedding already stored in Qdrant (fetched
    via qdrant_client.get()) — never a fresh embedding call. This function,
    and the module as a whole, makes NO LLM/embedding-API calls.
    """
    from backend.services.caching.notebooklm_cache_service import domain_scope_id
    from scripts.curated_qa_harvest import _CURATED_QA_COLLECTION_NAME, _stable_point_id

    domain = row["domain"]
    question = row["question"]

    await faq_cache.delete(question, notebook_id=domain_scope_id(domain))
    await faq_cache.delete(question)  # legacy unscoped key — defensive

    point_id = _stable_point_id(question, domain)
    existing = await qdrant_client.get(ids=[point_id], include=["embeddings", "payload"])
    if not existing.get("ids"):
        logger.warning(
            "Qdrant point %s not found for regulatory flag (question=%.60s, "
            "collection=%s) — FAQ copy was still deleted.",
            point_id,
            question,
            _CURATED_QA_COLLECTION_NAME,
        )
        return

    metadata = dict(existing["metadatas"][0])
    metadata["regulatory_flagged"] = True
    metadata["regulatory_flagged_citation"] = citation
    metadata["regulatory_flagged_at"] = _now_iso()

    await qdrant_client.upsert_documents(
        chunks=[existing["documents"][0]],
        embeddings=[existing["embeddings"][0]],
        metadatas=[metadata],
        ids=[point_id],
        flatten_payload=True,
    )


# ── Orchestration ────────────────────────────────────────────────────────────


async def run(
    date_str: str,
    *,
    delta_path: Path | None = None,
    dry_run: bool = False,
    faq_cache: Any | None = None,
    qdrant_client: Any | None = None,
) -> dict[str, Any]:
    """Top-level orchestration — no LLM calls anywhere in this path.

    `faq_cache`/`qdrant_client` are injectable for tests; when omitted and
    quarantine actions are actually needed (dry_run=False and candidates
    exist), real services are constructed.
    """
    delta = load_delta(date_str, delta_path=delta_path)

    summary: dict[str, Any] = {
        "date": date_str,
        "new_today_count": delta.get("new_today_count", 0),
        "partial": bool(delta.get("partial", False)),
        "no_op": False,
        "alerts": [],
        "quarantined": [],
        "unmapped_service_lines": [],
    }

    if delta.get("partial"):
        summary["alerts"].append(
            f"ALERT: {date_str} regulatory-watcher run was PARTIAL — do not "
            "treat as a complete signal; candidates below (if any) are from "
            "an incomplete scan.",
        )

    if delta.get("new_today_count", 0) == 0 and not delta.get("partial"):
        summary["no_op"] = True
        logger.info(
            "%s: new_today_count=0, partial=false — true no-op, zero LLM calls.",
            date_str,
        )
        return summary

    corpus_files = _iter_corpus_jsonl_files()
    rows_by_domain = load_rows_by_domain(corpus_files)
    candidates, unmapped = find_quarantine_candidates(delta.get("deltas", []), rows_by_domain)

    summary["unmapped_service_lines"] = unmapped
    for u in unmapped:
        summary["alerts"].append(
            f"ALERT: unmapped service_line {u['service_line']!r} for "
            f"citation {u['citation']!r} — no domain mapping, not checked "
            "against any corpus.",
        )

    if not candidates:
        logger.info(
            "%s: %d delta(s) checked, zero quarantine-candidate matches.",
            date_str,
            len(delta.get("deltas", [])),
        )
        return summary

    candidates_path = _REGEN_CANDIDATES_DIR / f"{date_str}.jsonl"
    if not dry_run:
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        with candidates_path.open("w", encoding="utf-8") as f:
            for c in candidates:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    summary["quarantined"] = candidates

    if not dry_run:
        if faq_cache is None:
            from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

            faq_cache = NotebookLMCacheService()
            await faq_cache.initialize()
        if qdrant_client is None:
            from backend.core.qdrant_db import QdrantClient
            from scripts.curated_qa_harvest import _CURATED_QA_COLLECTION_NAME

            qdrant_client = QdrantClient(collection_name=_CURATED_QA_COLLECTION_NAME)

        for c in candidates:
            await quarantine_row(
                {"domain": c["domain"], "question": c["question"]},
                faq_cache=faq_cache,
                qdrant_client=qdrant_client,
                citation=c["citation"],
            )
            try:
                from backend.app.metrics import curated_qa_quarantined_rows_total

                curated_qa_quarantined_rows_total.labels(domain=c["domain"]).inc()
            except ImportError:
                pass

    return summary


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Quarantine curated_qa verbatim FAQ entries invalidated by a "
            "regulatory-watcher delta (same-day, fail-safe)."
        ),
    )
    parser.add_argument(
        "--date",
        default=None,
        help="YYYY-MM-DD delta date to process (default: today)",
    )
    parser.add_argument(
        "--delta-path",
        type=Path,
        default=None,
        help="Override path to the delta JSON (default: research/regulatory/<date>-delta.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report candidates without writing the regen-candidates file or quarantining anything",
    )
    return parser.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()
    date_str = args.date or _date.today().isoformat()
    summary = asyncio.run(run(date_str, delta_path=args.delta_path, dry_run=args.dry_run))
    logger.info("=== Curated QA Regen Trigger Summary ===")
    logger.info(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    for alert in summary["alerts"]:
        logger.warning(alert)


if __name__ == "__main__":
    main()
