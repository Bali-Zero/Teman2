"""Curated Q&A harvester (SPEC v2 D3, F1b).

Reads normalized JSONL rows from apps/backend-rag/data/curated_qa/*.jsonl
(schema documented in that directory's README.md) and writes them to two
independent sinks:

- --faq: the FAQ cache (Redis via NotebookLMCacheService), DOMAIN-SCOPED keys
  (notebook_id=domain_scope_id(row["domain"]), Phase-0 safety rail FATAL 1 —
  research/operations/2026-07-17-full-domain-cache-design.md §8) — this is
  what orchestrator_core.check_faq_cache() reads via
  faq_cache.get(query, notebook_id=domain_scope_id(classified_domain)), with
  a dual-read fallback to the legacy UNSCOPED key for entries written before
  this rail shipped (see that method's docstring). Provenance is enforced by
  NotebookLMCacheService.set() itself (P7): every row's metadata is required
  to carry source_ref/source_date/domain/confidence_class/source_priority.
- --qdrant: the curated_qa Qdrant collection (create-if-missing, 1536-dim
  Cosine), embedding the QUESTION with the frozen text-embedding-3-small,
  flat payload (no nested "metadata" dict — data invariant).

Question-only seeds (answer: null — prewarm/golden question banks with no
vetted answer yet) are silently SKIPPED for BOTH sinks: an FAQ/curated_qa
entry with no answer is meaningless and would violate the provenance
contract. They are still counted in the stats for coverage analysis.

FAQ-sink eligibility (Phase-0 safety rail FATAL 3): only rows that
independently RE-DERIVE (never a stored `verbatim_eligible` value) as
`confidence_class == "JELAS"` AND non-price AND non-`client_specific` are
written to the FAQ sink. Qdrant gets ALL answerable rows regardless of
eligibility (grounding-only for the rest). See `_derive_verbatim_eligible`.

Batch manifest gate (Phase-0 safety rail FATAL 2, MAJOR 9/10): loading a
file into either sink requires an APPROVED manifest to already exist at
data/curated_qa/_manifests/<batch_id>.json (batch_id =
<domain>-<source-file-sha256[:12]>) whose recorded hash matches the file's
CURRENT content — fail-closed. Write that manifest first with
--write-manifest. The two-sink load is Qdrant-staging-first /
FAQ-verbatim-last per batch, with a commit marker persisted to the manifest
after each phase — an interrupted run is safely re-runnable
(already-committed phases are skipped, not repeated). --purge-batch rolls
back a single batch from both sinks without touching sibling batches in the
same domain.

Staleness rails (Phase-0 safety rail MAJOR 7/8): every FAQ-sink write gets a
class-based TTL (JELAS=30d, DINAMIS=7d — see `_ttl_seconds_for_class`,
though only JELAS ever reaches the FAQ sink today per FATAL 3) instead of
the service's one-size-fits-all default, so a verbatim answer self-expires
on a schedule matched to how settled its underlying fact is. Every Qdrant
point is written with `active: true, invalidated_at: null`;
curated_qa_regen_trigger.py flips these on a regulatory-delta match, and
orchestrator_core._inject_curated_qa_grounding()'s per-hit filter honors
`active` so an invalidated point stops influencing answers without being
deleted (audit trail preserved).

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/curated_qa_harvest.py --write-manifest data/curated_qa/visa-batch.jsonl
    PYTHONPATH=. python scripts/curated_qa_harvest.py --faq --qdrant
    PYTHONPATH=. python scripts/curated_qa_harvest.py --faq --dry-run
    PYTHONPATH=. python scripts/curated_qa_harvest.py --purge-domain visa --faq --qdrant
    PYTHONPATH=. python scripts/curated_qa_harvest.py --purge-batch visa-abc123def456 --faq --qdrant
    PYTHONPATH=. python scripts/curated_qa_harvest.py --faq --qdrant --verbatim-all  # operator order only, see --help

Do NOT run against prod without Zero's review of the batch being loaded —
this writes into the same FAQ cache / curated_qa collection the live
orchestrator reads from.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("curated_qa_harvest")

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _SCRIPT_DIR.parent / "data" / "curated_qa"

_CURATED_QA_COLLECTION_NAME = "curated_qa"
_CURATED_QA_VECTOR_SIZE = 1536
_CURATED_QA_DISTANCE = "Cosine"

REQUIRED_ROW_KEYS: tuple[str, ...] = (
    "question",
    "answer",
    "domain",
    "lang",
    "source_ref",
    "source_date",
    "confidence_class",
    "law_refs",
    "source_priority",
    "verbatim_eligible",
    "client_specific",
)

# Phase-0 safety rail (FATAL 3): the confidence class that alone permits
# verbatim FAQ serving. BERSYARAT/BELUM_DIATUR_PUBLIK/KEBIJAKAN_PENYEDIA/
# DINAMIS rows are grounding-only forever — a "depends on your case" answer
# served verbatim with zero per-request reasoning is a wrong answer waiting
# for the wrong client.
_JELAS_CONFIDENCE_CLASS = "JELAS"

# Phase-0 safety rail (staleness, MAJOR 7): class-based TTL applied AT WRITE
# TIME to the FAQ (Redis) sink, on top of Redis's own expiry. JELAS is
# "settled" law/fact — 30 days. DINAMIS is "actively changing" — 7 days, so
# a verbatim-served answer about a fast-moving fact self-expires quickly.
# In practice, only JELAS rows ever reach the FAQ sink today (FATAL 3
# eligibility gate refuses DINAMIS/BERSYARAT/etc outright) so the DINAMIS
# entry is currently unreachable via harvest_to_faq — it is still defined
# here (not left implicit) so the mapping is visible in code and a future
# change to the eligibility gate can't silently inherit the wrong TTL.
_CLASS_TTL_SECONDS: dict[str, int] = {
    "JELAS": 30 * 24 * 3600,
    "DINAMIS": 7 * 24 * 3600,
}
_DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # any class with no explicit entry above


def _ttl_seconds_for_class(confidence_class: Any) -> int:
    """Class-based TTL lookup (MAJOR 7). Unknown/missing class falls back
    to the 30-day default rather than raising — a missing TTL entry is a
    generosity bug (entry outlives its class), never a hard failure."""
    return _CLASS_TTL_SECONDS.get(str(confidence_class), _DEFAULT_TTL_SECONDS)


@dataclass
class HarvestStats:
    """Per-class-labeled summary — see docstring: "skip nothing silently"."""

    total_rows: int = 0
    invalid_rows: int = 0
    malformed_lines: int = 0

    faq_written: int = 0
    faq_answerless_skipped: int = 0
    faq_collision_refused: int = 0
    faq_failed: int = 0
    faq_ineligible_skipped: int = 0
    faq_price_rejected: int = 0

    qdrant_written: int = 0
    qdrant_answerless_skipped: int = 0
    qdrant_failed: int = 0

    purged_faq: int = 0
    purged_qdrant: int = 0

    # Phase-0 batch-manifest fail-closed gate (FATAL 2, MAJOR 9/10).
    manifest_missing_rows: int = 0
    manifest_mismatch_rows: int = 0

    confidence_class_counts: dict[str, int] = field(default_factory=dict)

    def summary_lines(self) -> list[str]:
        lines = [
            f"total_rows={self.total_rows} invalid_rows={self.invalid_rows} "
            f"malformed_lines={self.malformed_lines}",
        ]
        if (
            self.faq_written
            or self.faq_answerless_skipped
            or self.faq_failed
            or self.faq_ineligible_skipped
            or self.faq_price_rejected
        ):
            lines.append(
                f"FAQ: written={self.faq_written} "
                f"answerless_skipped={self.faq_answerless_skipped} "
                f"collision_refused={self.faq_collision_refused} "
                f"ineligible_skipped={self.faq_ineligible_skipped} "
                f"price_rejected={self.faq_price_rejected} "
                f"failed={self.faq_failed}",
            )
        if self.qdrant_written or self.qdrant_answerless_skipped or self.qdrant_failed:
            lines.append(
                f"Qdrant: written={self.qdrant_written} "
                f"answerless_skipped={self.qdrant_answerless_skipped} "
                f"failed={self.qdrant_failed}",
            )
        if self.purged_faq or self.purged_qdrant:
            lines.append(f"Purge: faq={self.purged_faq} qdrant={self.purged_qdrant}")
        if self.manifest_missing_rows or self.manifest_mismatch_rows:
            lines.append(
                f"Manifest gate REFUSED: missing={self.manifest_missing_rows} "
                f"hash_mismatch={self.manifest_mismatch_rows}",
            )
        if self.confidence_class_counts:
            counts = ", ".join(f"{k}={v}" for k, v in sorted(self.confidence_class_counts.items()))
            lines.append(f"confidence_class counts: {counts}")
        return lines


# ── Load + validate ──────────────────────────────────────────────────────────


def load_jsonl_rows(paths: list[Path]) -> tuple[list[dict], int]:
    """Read one or more .jsonl files. Returns (rows, malformed_line_count).

    Blank lines are skipped silently (not counted as malformed). A line that
    fails to parse as JSON is logged and counted, but does not abort the load
    — one bad batch file should not block every other file.
    """
    rows: list[dict] = []
    malformed = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                malformed += 1
                logger.error("Malformed JSONL line %s:%d — %s", path, line_no, e)
    return rows, malformed


def validate_row(row: dict) -> str | None:
    """Return an error message if `row` is missing a required schema key,
    else None. `answer: null` (question-only seed) is valid — see module
    docstring."""
    missing = [k for k in REQUIRED_ROW_KEYS if k not in row]
    if missing:
        return f"missing keys: {missing}"
    return None


# Provenance value stamped on any row whose eligibility only cleared because
# of --verbatim-all (Zero's Legge-5 order, 2026-07-19: "far diventare
# verbatim tutte le risposte" — task #27, the 21 gated CHATKB dossiers). A
# CONSTANT, not an operator-supplied string: this override has exactly one
# sanctioned origin, so there is nothing to parametrize and no way to stamp
# an unaccountable provenance value by typo.
VERBATIM_OVERRIDE_PROVENANCE = "zero-legge5-2026-07-19"


def _default_verbatim_eligible(row: dict) -> bool:
    """The FATAL-3 default eligibility rule, unconditional of any override:
    confidence_class == JELAS AND NOT client_specific AND pricing-clean."""
    from backend.services.misc.curated_qa_pricing_detector import has_price_content

    if row.get("confidence_class") != _JELAS_CONFIDENCE_CLASS:
        return False
    if row.get("client_specific"):
        return False
    return not has_price_content(row.get("answer"))


def _derive_verbatim_eligible(row: dict, *, verbatim_all: bool = False) -> bool:
    """Independently RE-DERIVE FAQ-sink eligibility — Phase-0 safety rail
    (FATAL 3). NEVER trusts `row.get("verbatim_eligible")`; a stored value
    (converter best-effort guess, or a hand-edited JSONL) is informational
    only and is ignored here by construction. Default eligibility =
    confidence_class == JELAS AND NOT client_specific AND the answer text
    is pricing-clean (FATAL 13 detector).

    `verbatim_all` (Zero's Legge-5 operator order, task #27): when True,
    bypasses the confidence_class/client_specific gate entirely — EVERY
    answerable row is promoted to verbatim-eligible regardless of its
    CONFIDENCE class. The FATAL 13 pricing rail is the ONE check that is
    NEVER bypassed by this override, even under verbatim_all — a price
    figure must always come from PricingTool, never a cached verbatim
    answer, no matter which business order is in effect. Pricing is
    checked FIRST and unconditionally so this invariant reads as an
    early, unmissable return rather than something buried under a flag
    branch.
    """
    from backend.services.misc.curated_qa_pricing_detector import has_price_content

    if has_price_content(row.get("answer")):
        return False

    if verbatim_all:
        return True

    return _default_verbatim_eligible(row)


def _row_provenance_metadata(
    row: dict,
    *,
    batch_id: str | None = None,
    verbatim_all: bool = False,
) -> dict[str, Any]:
    eligible = _derive_verbatim_eligible(row, verbatim_all=verbatim_all)
    metadata: dict[str, Any] = {
        "source_ref": row["source_ref"],
        "source_date": row["source_date"],
        "domain": row["domain"],
        "confidence_class": row["confidence_class"],
        "source_priority": row["source_priority"],
        "client_specific": bool(row.get("client_specific", False)),
        # RE-DERIVED, not the row's own stored value (see
        # _derive_verbatim_eligible docstring) — this is what actually
        # gated the FAQ-sink write for this row.
        "verbatim_eligible": eligible,
    }
    if batch_id is not None:
        metadata["batch_id"] = batch_id
    # Provenance for the Legge-5 override (task #27): stamped whenever this
    # row is eligible under a verbatim_all run, so every FAQ/Qdrant entry
    # written under the order carries an auditable trail back to it — a
    # price-blocked row never gets eligible=True in the first place, so it
    # never gets this stamp either (the pricing rail's refusal stays clean).
    if verbatim_all and eligible:
        metadata["verbatim_override"] = VERBATIM_OVERRIDE_PROVENANCE
    return metadata


# ── Batch manifest (FATAL 2, MAJOR 9/10) ────────────────────────────────────
#
# A per-batch manifest (data/curated_qa/_manifests/<batch_id>.json) is the
# APPROVED artifact a prior review step (blind-verification pass, D3
# assembly) is expected to produce via --write-manifest. The load path
# (main_async, below) REFUSES to write a file's rows to either sink unless a
# manifest already exists on disk whose recorded source_file_sha256 matches
# the file's CURRENT content — fail-closed: a missing manifest, or a file
# edited after its manifest was approved, blocks that file's rows entirely
# rather than loading with stale/unapproved content. batch_id is
# deterministic (<domain>-<source-file-sha256[:12]>) so an edited file
# naturally produces a DIFFERENT batch_id and therefore finds no manifest —
# defense in depth on top of the explicit hash re-check below.

_MANIFEST_DIR_NAME = "_manifests"


def _compute_source_file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_batch_id(domain: str, source_file_sha256: str) -> str:
    """batch_id = <domain>-<source-file-sha256[:12]> (deterministic)."""
    return f"{domain}-{source_file_sha256[:12]}"


def _manifest_path(batch_id: str) -> Path:
    return _DEFAULT_DATA_DIR / _MANIFEST_DIR_NAME / f"{batch_id}.json"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).isoformat()


def _write_manifest_json(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_batch_manifest(path: Path, rows: list[dict]) -> dict[str, Any]:
    """Build the manifest dict for `rows` (already loaded+validated from
    `path`). Requires a SINGLE domain across all rows — a batch/manifest is
    scoped to one (domain, source-file) pair by construction; a file mixing
    domains is a generation-pipeline bug to fix upstream, not something a
    manifest can silently paper over.
    """
    from backend.services.misc.curated_qa_pricing_detector import has_price_content

    domains = {r["domain"] for r in rows}
    if len(domains) > 1:
        raise ValueError(
            f"{path}: batch manifest requires a single domain per file, "
            f"found {sorted(domains)} — split this file by domain first.",
        )
    domain = next(iter(domains)) if domains else "unknown"
    source_file_sha256 = _compute_source_file_sha256(path)
    batch_id = compute_batch_id(domain, source_file_sha256)

    class_histogram: dict[str, int] = {}
    price_bearing_rows = 0
    client_specific_rows = 0
    verbatim_eligible_rows = 0
    for r in rows:
        cc = str(r.get("confidence_class"))
        class_histogram[cc] = class_histogram.get(cc, 0) + 1
        if r.get("client_specific"):
            client_specific_rows += 1
        if _derive_verbatim_eligible(r):
            verbatim_eligible_rows += 1
        if has_price_content(r.get("answer")):
            price_bearing_rows += 1

    return {
        "batch_id": batch_id,
        "domain": domain,
        "source_file": str(path),
        "source_file_sha256": source_file_sha256,
        "row_count": len(rows),
        "class_histogram": class_histogram,
        "gate_flags": {
            "price_bearing_rows": price_bearing_rows,
            "client_specific_rows": client_specific_rows,
            "verbatim_eligible_rows": verbatim_eligible_rows,
        },
        "created_at": _now_iso(),
        # Two-sink commit markers (MAJOR 10): Qdrant staging first, FAQ
        # (verbatim) last — see load_batch(). An interrupted run is
        # re-runnable: an already-True phase is skipped on retry.
        "qdrant_committed": False,
        "qdrant_committed_at": None,
        "faq_committed": False,
        "faq_committed_at": None,
    }


def write_batch_manifest(path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Load+validate `path`'s rows and write its batch manifest to
    data/curated_qa/_manifests/<batch_id>.json. This is the APPROVAL step —
    run explicitly (separately from --faq/--qdrant loading) so the load
    gate is a real gate, not the harvester grading its own homework.
    """
    rows, _malformed = load_jsonl_rows([path])
    valid_rows = [r for r in rows if validate_row(r) is None]
    manifest = build_batch_manifest(path, valid_rows)
    if not dry_run:
        _write_manifest_json(_manifest_path(manifest["batch_id"]), manifest)
    return manifest


# ── FAQ sink ─────────────────────────────────────────────────────────────────


async def harvest_to_faq(
    rows: list[dict],
    cache: Any,
    *,
    dry_run: bool = False,
    stats: HarvestStats | None = None,
    batch_id: str | None = None,
    verbatim_all: bool = False,
) -> HarvestStats:
    """Write `rows` to the FAQ cache with DOMAIN-SCOPED keys
    (notebook_id=domain_scope_id(row["domain"])) — Phase-0 safety rail
    FATAL 1: without domain scoping, two domains with byte-identical
    question phrasing collide on the same MD5 key.

    Answer-less rows (question-only seeds) are skipped — an FAQ entry with no
    answer would violate NotebookLMCacheService.set()'s provenance contract
    and is meaningless to serve.

    FATAL 3 (verbatim_eligible): only rows that RE-DERIVE (never the row's
    own stored value) as eligible — confidence_class == JELAS, not
    client_specific, and pricing-clean — are written here, UNLESS
    `verbatim_all` is set (Zero's Legge-5 override, task #27), in which
    case every answerable, non-price-bearing row is eligible regardless of
    confidence_class/client_specific. A row that would otherwise be
    eligible except for a detected price in its answer is a hard error
    (the E33 "FINAL (client-facing)" text is meant to route prices through
    PricingTool, never state one) — logged at ERROR with the offending
    question, counted separately from routine ineligibility (BERSYARAT/
    DINAMIS/etc rows under the default policy, which are Qdrant-only by
    design, not an error). The pricing rail is NEVER bypassed by
    verbatim_all — see `_derive_verbatim_eligible`.
    """
    from backend.services.caching.notebooklm_cache_service import domain_scope_id
    from backend.services.misc.curated_qa_pricing_detector import has_price_content

    stats = stats or HarvestStats()
    for row in rows:
        if row.get("answer") is None:
            stats.faq_answerless_skipped += 1
            continue

        stored_eligible = row.get("verbatim_eligible")
        derived_eligible = _derive_verbatim_eligible(row, verbatim_all=verbatim_all)
        if stored_eligible is not None and bool(stored_eligible) != derived_eligible:
            logger.warning(
                "verbatim_eligible drift for '%.60s': stored=%r derived=%r "
                "— using DERIVED value (never trust a stored eligibility "
                "value, FATAL 3).",
                row.get("question"),
                stored_eligible,
                derived_eligible,
            )

        if not derived_eligible:
            # A direct pricing-content check (not a confidence_class proxy):
            # under verbatim_all EVERY row is a would-be-eligible candidate,
            # so "why did this one fail" is always answerable by asking the
            # pricing detector directly rather than inferring it from a
            # class check that only applied under the default policy.
            is_price_bearing = has_price_content(row.get("answer"))
            if is_price_bearing:
                stats.faq_price_rejected += 1
                logger.error(
                    "FAQ sink REFUSED (price-bearing row): '%.80s' "
                    "(source_ref=%s) — prices must come from PricingTool "
                    "only, never a cached verbatim answer.",
                    row.get("question"),
                    row.get("source_ref"),
                )
            else:
                stats.faq_ineligible_skipped += 1
            continue

        metadata = _row_provenance_metadata(row, batch_id=batch_id, verbatim_all=verbatim_all)
        if dry_run:
            stats.faq_written += 1
            continue

        try:
            ok = await cache.set(
                row["question"],
                row["answer"],
                metadata=metadata,
                notebook_id=domain_scope_id(row["domain"]),
                ttl_seconds=_ttl_seconds_for_class(row.get("confidence_class")),
            )
        except ValueError as e:
            # Provenance contract violation — should not happen given
            # validate_row(), but never crash the batch on one bad row.
            stats.faq_failed += 1
            logger.error("FAQ set() rejected row %r: %s", row.get("question"), e)
            continue

        if ok:
            stats.faq_written += 1
        else:
            # False = either infra failure or collision-policy refusal.
            # NotebookLMCacheService logs the specific reason itself.
            stats.faq_collision_refused += 1

    return stats


async def _purge_faq_by_metadata(
    cache: Any,
    metadata_key: str,
    metadata_value: str,
    *,
    dry_run: bool = False,
) -> int:
    """Delete every FAQ cache entry whose metadata[metadata_key] ==
    metadata_value.

    FAQ cache keys are opaque content hashes (MD5 of the normalized,
    domain-scoped question) — there is no key-pattern that encodes
    domain/batch_id, so this scans every key under the cache prefix and
    filters by decoded metadata. Not a hot path; purge is an operator/cron
    action, not a request-path call.
    """
    if not cache.redis_client:
        return 0

    to_delete: list[str] = []
    async for key in cache.redis_client.scan_iter(match=f"{cache.cache_prefix}*"):
        raw = await cache.redis_client.get(key)
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if entry.get("metadata", {}).get(metadata_key) == metadata_value:
            to_delete.append(key)

    if not dry_run:
        for key in to_delete:
            await cache.redis_client.delete(key)

    return len(to_delete)


async def purge_domain_faq(cache: Any, domain: str, *, dry_run: bool = False) -> int:
    """Delete every FAQ cache entry whose metadata.domain == `domain`."""
    return await _purge_faq_by_metadata(cache, "domain", domain, dry_run=dry_run)


async def purge_batch_faq(cache: Any, batch_id: str, *, dry_run: bool = False) -> int:
    """Delete every FAQ cache entry whose metadata.batch_id == `batch_id`
    (MAJOR 9: batch-scoped rollback — a single defective batch can be
    reverted without touching sibling batches in the same domain)."""
    return await _purge_faq_by_metadata(cache, "batch_id", batch_id, dry_run=dry_run)


# ── Qdrant sink ──────────────────────────────────────────────────────────────


async def ensure_qdrant_collection(qdrant_client: Any) -> bool:
    """Create the curated_qa collection if it doesn't exist yet.

    Returns True if a new collection was created, False if it already existed.
    """
    stats = await qdrant_client.get_stats()
    if not stats.get("error"):
        return False

    await qdrant_client.create_collection(
        vector_size=_CURATED_QA_VECTOR_SIZE,
        distance=_CURATED_QA_DISTANCE,
    )
    return True


def _stable_point_id(question: str, domain: str) -> str:
    """Deterministic Qdrant point id, DOMAIN-SCOPED (Phase-0 safety rail
    FATAL 1): without folding `domain` into the digest, two domains with
    byte-identical question text would upsert to the SAME point — the
    second write silently overwrites the first regardless of domain, and
    a single Qdrant hit can only ever carry one domain's answer.
    """
    import hashlib
    import uuid

    digest = hashlib.sha256(f"{domain}:{question.strip().lower()}".encode()).hexdigest()
    # Deterministic UUID5 from the digest — same (domain, question) always
    # maps to the same point id, so re-running the harvester upserts in place.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, digest))


async def harvest_to_qdrant(
    rows: list[dict],
    qdrant_client: Any,
    embedder: Any,
    *,
    dry_run: bool = False,
    batch_size: int = 100,
    stats: HarvestStats | None = None,
    batch_id: str | None = None,
    verbatim_all: bool = False,
) -> HarvestStats:
    """Embed the QUESTION of each row and upsert a flat payload into the
    curated_qa collection.

    Answer-less rows are skipped: the collection exists to serve
    grounding-injection evidence (orchestrator_core._inject_curated_qa_grounding),
    and an entry with no answer can never be used there — indexing it would
    only burn embedding cost and collection space for zero benefit. (They
    remain visible for coverage analysis via the FAQ-sink stats / the JSONL
    source files themselves.)

    `verbatim_all` (task #27, Zero's Legge-5 override) travels into the
    payload's `verbatim_eligible`/`verbatim_override` fields exactly like it
    does for the FAQ sink — Qdrant was never eligibility-GATED (it always
    got every answerable row), but the flag it carries must still reflect
    which policy computed it, so a grounding-injection audit and the FAQ
    sink agree on the same row's eligibility under the same run.
    """
    stats = stats or HarvestStats()

    answerable = [r for r in rows if r.get("answer") is not None]
    stats.qdrant_answerless_skipped += len(rows) - len(answerable)

    if dry_run:
        stats.qdrant_written += len(answerable)
        return stats

    for i in range(0, len(answerable), batch_size):
        batch = answerable[i : i + batch_size]
        questions = [r["question"] for r in batch]
        try:
            embeddings = await embedder.generate_embeddings(questions)
        except Exception as e:
            stats.qdrant_failed += len(batch)
            logger.error("Embedding generation failed for batch starting at %d: %s", i, e)
            continue

        metadatas = [
            {
                "answer": r["answer"],
                "domain": r["domain"],
                "lang": r["lang"],
                "source_ref": r["source_ref"],
                "source_date": r["source_date"],
                "confidence_class": r["confidence_class"],
                "law_refs": r["law_refs"],
                "source_priority": r["source_priority"],
                "client_specific": bool(r.get("client_specific", False)),
                # RE-DERIVED (FATAL 3) — Qdrant gets ALL answerable rows
                # regardless of eligibility (grounding-only for
                # BERSYARAT/DINAMIS/etc), but the flag travels with the
                # payload for audit/filtering.
                "verbatim_eligible": _derive_verbatim_eligible(r, verbatim_all=verbatim_all),
                # Staleness rail (MAJOR 7/8/11): every freshly-written row
                # starts active. curated_qa_regen_trigger.py flips this to
                # False (+ sets invalidated_at) when a regulatory delta
                # matches this row's citation — the row stays in Qdrant
                # (audit trail) but orchestrator_core's grounding-injection
                # filters it out client-side (never a native Qdrant filter —
                # see that function's docstring for why).
                "active": True,
                "invalidated_at": None,
                **({"batch_id": batch_id} if batch_id is not None else {}),
                # Same Legge-5 provenance stamp as the FAQ sink (task #27) —
                # only present when this row's eligibility was actually
                # computed under the override AND came out eligible; a
                # price-blocked row never carries it (the pricing rail's
                # refusal is unconditional, see _derive_verbatim_eligible).
                **(
                    {"verbatim_override": VERBATIM_OVERRIDE_PROVENANCE}
                    if verbatim_all and _derive_verbatim_eligible(r, verbatim_all=True)
                    else {}
                ),
            }
            for r in batch
        ]
        ids = [_stable_point_id(q, r["domain"]) for q, r in zip(questions, batch, strict=True)]

        result = await qdrant_client.upsert_documents(
            chunks=questions,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
            flatten_payload=True,
        )
        if result.get("success"):
            stats.qdrant_written += len(batch)
        else:
            stats.qdrant_failed += len(batch)
            logger.error("Qdrant upsert failed for batch starting at %d: %s", i, result)

    return stats


async def _purge_qdrant_by_metadata(
    qdrant_client: Any,
    metadata_key: str,
    metadata_value: str,
    *,
    dry_run: bool = False,
) -> int:
    matches = await qdrant_client.scroll(
        limit=10_000, metadata_filter={metadata_key: metadata_value}
    )
    ids = [m["id"] for m in matches]

    if not dry_run and ids:
        await qdrant_client.delete(ids=ids)

    return len(ids)


async def purge_domain_qdrant(qdrant_client: Any, domain: str, *, dry_run: bool = False) -> int:
    """Delete every curated_qa point whose flat `domain` field == `domain`."""
    return await _purge_qdrant_by_metadata(qdrant_client, "domain", domain, dry_run=dry_run)


async def purge_batch_qdrant(qdrant_client: Any, batch_id: str, *, dry_run: bool = False) -> int:
    """Delete every curated_qa point whose flat `batch_id` field ==
    `batch_id` (MAJOR 9: batch-scoped rollback)."""
    return await _purge_qdrant_by_metadata(qdrant_client, "batch_id", batch_id, dry_run=dry_run)


# ── Batch loader (two-sink atomicity, MAJOR 10) ─────────────────────────────


async def load_batch(
    batch_id: str,
    manifest_path: Path,
    manifest: dict[str, Any],
    rows: list[dict],
    *,
    faq_cache: Any | None = None,
    qdrant_client: Any | None = None,
    embedder: Any | None = None,
    do_faq: bool = False,
    do_qdrant: bool = False,
    dry_run: bool = False,
    stats: HarvestStats | None = None,
    verbatim_all: bool = False,
) -> HarvestStats:
    """Load one batch's `rows` into the requested sink(s) — Qdrant STAGING
    FIRST, then Redis (verbatim FAQ) LAST — persisting a commit marker to
    the manifest file after each phase succeeds.

    Idempotent re-run: if a prior run already committed a phase for this
    batch_id (manifest says qdrant_committed/faq_committed True), that
    phase is SKIPPED on retry rather than re-attempted — safe either way,
    since the underlying writes are independently idempotent by
    construction (deterministic Qdrant point-ids, domain-scoped MD5 FAQ
    keys), but skipping avoids a redundant embedding-API call. An
    interrupted run (crash/exception between the two phases) is therefore
    always safely re-runnable: Qdrant-committed-but-not-FAQ-committed picks
    up exactly at the FAQ phase on the next invocation.

    `manifest` is mutated in place and persisted after each successful
    phase — callers that need the final state should read it back from
    `manifest` after this returns (or re-read the JSON file).
    """
    stats = stats or HarvestStats()

    if do_qdrant and qdrant_client is not None and embedder is not None:
        if manifest.get("qdrant_committed") and not dry_run:
            logger.info(
                "Batch %s already qdrant_committed — skipping Qdrant re-load (idempotent).",
                batch_id,
            )
        else:
            await harvest_to_qdrant(
                rows,
                qdrant_client,
                embedder,
                dry_run=dry_run,
                stats=stats,
                batch_id=batch_id,
                verbatim_all=verbatim_all,
            )
            if not dry_run:
                manifest["qdrant_committed"] = True
                manifest["qdrant_committed_at"] = _now_iso()
                _write_manifest_json(manifest_path, manifest)

    if do_faq and faq_cache is not None:
        if manifest.get("faq_committed") and not dry_run:
            logger.info(
                "Batch %s already faq_committed — skipping FAQ re-load (idempotent).",
                batch_id,
            )
        else:
            await harvest_to_faq(
                rows,
                faq_cache,
                dry_run=dry_run,
                stats=stats,
                batch_id=batch_id,
                verbatim_all=verbatim_all,
            )
            if not dry_run:
                manifest["faq_committed"] = True
                manifest["faq_committed_at"] = _now_iso()
                _write_manifest_json(manifest_path, manifest)

    return stats


def _load_and_gate_batches(
    paths: list[Path],
    stats: HarvestStats,
) -> list[tuple[str, Path, dict[str, Any], list[dict]]]:
    """Load+validate each file in `paths`, then apply the fail-closed batch
    manifest gate (FATAL 2): a file's rows are refused entirely (both
    sinks) unless an approved manifest already exists on disk whose
    source_file_sha256 matches the file's CURRENT content. Returns the list
    of gate-passing (batch_id, manifest_path, manifest, rows) groups.
    """
    batches: list[tuple[str, Path, dict[str, Any], list[dict]]] = []

    for p in paths:
        rows, malformed = load_jsonl_rows([p])
        stats.malformed_lines += malformed
        stats.total_rows += len(rows)

        valid_rows: list[dict] = []
        for row in rows:
            error = validate_row(row)
            if error:
                stats.invalid_rows += 1
                logger.error("Invalid row %r: %s", row.get("question", "<unknown>"), error)
                continue
            valid_rows.append(row)
            confidence_class = str(row.get("confidence_class"))
            stats.confidence_class_counts[confidence_class] = (
                stats.confidence_class_counts.get(confidence_class, 0) + 1
            )

        if not valid_rows:
            continue

        domains = {r["domain"] for r in valid_rows}
        if len(domains) > 1:
            stats.invalid_rows += len(valid_rows)
            logger.error(
                "%s: mixed domains %s in one file — batch manifest requires "
                "a single domain per file, refusing all rows from this file.",
                p,
                sorted(domains),
            )
            continue

        domain = next(iter(domains))
        source_file_sha256 = _compute_source_file_sha256(p)
        batch_id = compute_batch_id(domain, source_file_sha256)
        manifest_path = _manifest_path(batch_id)

        if not manifest_path.exists():
            stats.manifest_missing_rows += len(valid_rows)
            logger.error(
                "REFUSED (fail-closed, FATAL 2): no manifest at %s for "
                "batch_id=%s (%s) — run --write-manifest first.",
                manifest_path,
                batch_id,
                p,
            )
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            stats.manifest_mismatch_rows += len(valid_rows)
            logger.error(
                "REFUSED (fail-closed, FATAL 2): unreadable manifest %s: %s", manifest_path, e
            )
            continue

        if manifest.get("source_file_sha256") != source_file_sha256:
            stats.manifest_mismatch_rows += len(valid_rows)
            logger.error(
                "REFUSED (fail-closed, FATAL 2): manifest hash mismatch for "
                "batch_id=%s — %s has changed since the manifest was approved.",
                batch_id,
                p,
            )
            continue

        batches.append((batch_id, manifest_path, manifest, valid_rows))

    return batches


# ── CLI ──────────────────────────────────────────────────────────────────────


def _resolve_input_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        p = Path(pattern)
        if p.is_file():
            paths.append(p)
        elif p.is_dir():
            paths.extend(sorted(p.glob("*.jsonl")))
        else:
            paths.extend(sorted(Path().glob(pattern)))
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Harvest curated Q&A JSONL into the FAQ cache and/or curated_qa Qdrant collection.",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        default=[str(_DEFAULT_DATA_DIR)],
        help="One or more .jsonl files, directories, or glob patterns (default: data/curated_qa/)",
    )
    parser.add_argument("--faq", action="store_true", help="Write to the FAQ cache (Redis)")
    parser.add_argument(
        "--qdrant", action="store_true", help="Write to the curated_qa Qdrant collection"
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    parser.add_argument(
        "--purge-domain",
        default=None,
        help="Delete every entry for this domain from the selected sink(s) instead of loading",
    )
    parser.add_argument(
        "--purge-batch",
        default=None,
        help=(
            "Delete every entry for this batch_id from the selected sink(s) "
            "instead of loading (MAJOR 9: batch-scoped rollback)"
        ),
    )
    parser.add_argument(
        "--write-manifest",
        default=None,
        help=(
            "Write the batch manifest for this single .jsonl file to "
            "data/curated_qa/_manifests/<batch_id>.json instead of loading "
            "(FATAL 2: run this — the approval step — before --faq/--qdrant "
            "will accept the file)."
        ),
    )
    parser.add_argument(
        "--source-attestation",
        default=None,
        help=(
            "Name/path of the reviewed dossier authorizing an --input path "
            "outside data/curated_qa/ (Phase-0 PII source allowlist, FATAL "
            "5). Not needed for paths already inside data/curated_qa/."
        ),
    )
    parser.add_argument(
        "--verbatim-all",
        action="store_true",
        help=(
            "OPERATOR-ORDERED OVERRIDE (task #27, Zero's Legge-5 ruling "
            "2026-07-19: 'far diventare verbatim tutte le risposte'). "
            "Bypasses the confidence_class==JELAS / non-client_specific "
            "FATAL-3 gate for the FAQ (Redis) sink and the Qdrant "
            "verbatim_eligible payload field — every answerable, "
            "non-price-bearing row is promoted regardless of its "
            "CONFIDENCE class. Does NOT touch the source allowlist (FATAL "
            "5) or the pricing detector (FATAL 13) — both stay in full "
            "force; a price-bearing row is refused either way. Every row "
            "whose eligibility this override actually decided is stamped "
            "metadata.verbatim_override='zero-legge5-2026-07-19' for "
            "audit. Use ONLY under an explicit operator business order — "
            "never as a default."
        ),
    )
    return parser.parse_args(argv)


async def main_async(args: argparse.Namespace) -> HarvestStats:
    stats = HarvestStats()

    if args.purge_domain:
        if args.faq:
            from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

            cache = NotebookLMCacheService()
            await cache.initialize()
            stats.purged_faq = await purge_domain_faq(
                cache, args.purge_domain, dry_run=args.dry_run
            )
        if args.qdrant:
            from backend.core.qdrant_db import QdrantClient

            client = QdrantClient(collection_name=_CURATED_QA_COLLECTION_NAME)
            stats.purged_qdrant = await purge_domain_qdrant(
                client,
                args.purge_domain,
                dry_run=args.dry_run,
            )
        return stats

    if args.purge_batch:
        if args.faq:
            from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

            cache = NotebookLMCacheService()
            await cache.initialize()
            stats.purged_faq = await purge_batch_faq(cache, args.purge_batch, dry_run=args.dry_run)
        if args.qdrant:
            from backend.core.qdrant_db import QdrantClient

            client = QdrantClient(collection_name=_CURATED_QA_COLLECTION_NAME)
            stats.purged_qdrant = await purge_batch_qdrant(
                client,
                args.purge_batch,
                dry_run=args.dry_run,
            )
        return stats

    if args.write_manifest:
        from scripts.curated_qa_source_allowlist import check_source_allowlist

        manifest_input_path = Path(args.write_manifest)
        check_source_allowlist(
            [manifest_input_path],
            source_attestation=args.source_attestation,
        )
        manifest = write_batch_manifest(manifest_input_path, dry_run=args.dry_run)
        logger.info(
            "Manifest for %s: batch_id=%s row_count=%d class_histogram=%s",
            manifest_input_path,
            manifest["batch_id"],
            manifest["row_count"],
            manifest["class_histogram"],
        )
        return stats

    paths = _resolve_input_paths(args.input)

    from scripts.curated_qa_source_allowlist import check_source_allowlist

    check_source_allowlist(paths, source_attestation=args.source_attestation)

    batches = _load_and_gate_batches(paths, stats)

    cache = None
    qdrant_client = None
    embedder = None
    if args.faq:
        from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

        cache = NotebookLMCacheService()
        await cache.initialize()
    if args.qdrant:
        from backend.core.embeddings import create_embeddings_generator
        from backend.core.qdrant_db import QdrantClient

        qdrant_client = QdrantClient(collection_name=_CURATED_QA_COLLECTION_NAME)
        if not args.dry_run:
            await ensure_qdrant_collection(qdrant_client)
        embedder = create_embeddings_generator(provider="openai")

    if args.verbatim_all:
        logger.warning(
            "⚠️  --verbatim-all ACTIVE (task #27, Zero's Legge-5 override "
            "2026-07-19): the confidence_class==JELAS FATAL-3 gate is "
            "BYPASSED for this run — every answerable, non-price-bearing "
            "row is being promoted to verbatim-eligible. Pricing detector "
            "(FATAL 13) and source allowlist (FATAL 5) remain in full "
            "force.",
        )

    for batch_id, manifest_path, manifest, rows in batches:
        await load_batch(
            batch_id,
            manifest_path,
            manifest,
            rows,
            faq_cache=cache,
            qdrant_client=qdrant_client,
            embedder=embedder,
            do_faq=args.faq,
            do_qdrant=args.qdrant,
            dry_run=args.dry_run,
            stats=stats,
            verbatim_all=args.verbatim_all,
        )

    return stats


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()
    stats = asyncio.run(main_async(args))
    logger.info("=== Curated QA Harvest Summary ===")
    for line in stats.summary_lines():
        logger.info("  %s", line)


if __name__ == "__main__":
    main()
