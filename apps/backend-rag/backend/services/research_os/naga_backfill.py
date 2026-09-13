"""D4/D5's production backfill CLI -- the one process authorized to move legacy `naga_claims`
rows into `research_os_objects` (R2-build-spec.md section 6, D10).

WHAT THIS MODULE DOES. `python -m backend.services.research_os.naga_backfill --cohort <name>`
runs, by default, a **dry-run**: it reads `naga_claims` (SELECT only, never written), decides
each row with `naga_admission.admit()`, and prints a report of counts and hashes -- never the
legacy claim text itself. `--apply --manifest <hash>` recomputes the exact same pipeline in this
process and, only if the recomputed manifest hash agrees with the one the caller names, writes
the admitted records through `naga_persistence` (never through a query this module issues
itself) in ONE transaction.

THE ONLY PRODUCTION COHORT IN THIS SLICE IS `legacy_naga_claims`. R1 declared its
`seed_public_regulatory` fixtures synthetic (`permenkumham-synth-*`) -- a TEST cohort, not a
production one (R2-build-spec.md section 6.1) -- so any other `--cohort` name is refused before
this module opens a connection.

ON TODAY'S LEGACY CORPUS THE EXPECTED DRY-RUN RESULT IS ZERO ADMITTED (see
`naga_admission`'s own module docstring): `naga_claims` carries none of the fields D4's rules
resolve against (`statement`, `source_span`, `document_content_hash`, `source_event_ref`,
`classification`, `retention`, `review`, `manifest_family_id`) -- every legacy row is fed to
`admit()` AS ITSELF, with an EMPTY `source_snapshot` (the legacy table carries no document body,
span, versions or IntelEvent -- fabricating one is forbidden), and the first rule
(`statement_not_from_source`) excludes it. A dry run that admits nothing, naming a reason per
record, is a PASS.

THE MANIFEST. `source_snapshot_hash` is the sha256 of a canonical JSON array, one entry per
legacy row ordered by `id`, of `{"id": str(id), "fields": {column: sha256(value), ...}}` -- the
row's OWN `id` stays in the clear (it is an opaque identifier, never claim content), every other
column's value is hashed before it enters the JSON, so no legacy claim text ever reaches the hash
input or the report. `manifest_hash` (the run id `research_os_naga_admission.run_id` uses) is the
sha256 of `{"cohort", "source_snapshot_hash", "decisions": [[legacy_claim_id, decision, reason_or_
family_id], ...]}` sorted by `legacy_claim_id`. Both are canonicalized with
`json.dumps(..., sort_keys=True, separators=(",", ":"))`.

WHAT `--apply` ACTUALLY WRITES. An `Admitted` decision only becomes a write when the admission
INPUT ITSELF carries a fully formed canonical claim payload (mirroring how R1's seed fixtures
pair a legacy-shaped admission record with a ready-made canonical object) -- `naga_claims` has no
such column, so on the production `legacy_naga_claims` cohort this is always absent and, were a
row ever admitted, it would be counted `rejected` with reason `canonical_payload_missing` rather
than fabricated (the statement atomizer is deferred). `EXCLUDED` decisions are never written to
`research_os_naga_admission` in this slice (Z2b caps production rows at 40; the report carries
the exclusions). Consequently `--apply` on `legacy_naga_claims` writes exactly 0 rows today --
the honest, valid D4 outcome, not a bug (R2-build-spec.md section 6.1).

HARD FENCE. This module never issues its own INSERT/UPDATE/DELETE/TRUNCATE/COPY -- objects are
written only via `naga_persistence.write_objects`, admission rows only via
`naga_persistence.record_admissions`. It never touches `naga_claims` except with a SELECT.
`test_naga_backfill_unit.py` scans this file's own source for every write-verb SQL literal and
asserts the fence.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

import asyncpg

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)
from backend.services.research_os.naga_admission import (
    AdmissionDecision,
    Admitted,
    Excluded,
    admit,
    summarize,
)
from backend.services.research_os.naga_persistence import (
    AdmissionRow,
    ObjectWrite,
    record_admissions,
    validate_object,
    write_objects,
)

__all__ = [
    "DEFAULT_DSN_ENV",
    "KINDS",
    "PRODUCTION_COHORT",
    "ApplyReport",
    "DryRunReport",
    "KindCounts",
    "SourceSnapshotDrifted",
    "compute_manifest",
    "compute_source_snapshot_hash",
    "main",
    "render_report",
    "run_apply",
    "run_dry_run",
]

logger = logging.getLogger(__name__)

#: The one production-eligible cohort this slice authorizes (R2-build-spec.md section 6.1).
PRODUCTION_COHORT = "legacy_naga_claims"

#: Name of the env var the DSN is read from, unless `--dsn-env` overrides it. The value is never
#: printed, logged or echoed -- only its NAME is, on the refusal path (`_require_dsn`).
DEFAULT_DSN_ENV = "NAGA_BACKFILL_DSN"

#: The four object kinds this slice's admission can, in principle, produce -- only `claim` is
#: reachable from a bare legacy row without the (deferred) statement atomizer.
KINDS: tuple[str, ...] = ("claim", "evidence", "object_successor_edge", "intel_event")

_MANIFEST_RE = re.compile(r"^[0-9a-f]{64}$")


# ------------------------------------------------------------------------------------------
# Legacy read (SELECT only -- see the module's hard fence).
# ------------------------------------------------------------------------------------------


async def _load_legacy_rows(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Explicit column list, ordered by `id` (never `SELECT *`) -- the columns the legacy
    writer `backend.services.naga.persist` populates in its own `naga_claims` INSERT, read back,
    never written."""

    records = await conn.fetch(
        "SELECT id, session_id, claim_text, claim_key, domain, verification_level, "
        "confidence, cross_ref_count, review_status, valid_as_of, expires_at, "
        "quality_score, claim_status FROM naga_claims ORDER BY id"
    )
    return [dict(record) for record in records]


async def _already_present_object_ids(
    conn: asyncpg.Connection, object_ids: Sequence[str]
) -> set[str]:
    """Read-only membership check against `research_os_objects` -- never a write."""

    if not object_ids:
        return set()
    rows = await conn.fetch(
        "SELECT object_id FROM research_os_objects WHERE object_id = ANY($1::text[])",
        list(object_ids),
    )
    return {row["object_id"] for row in rows}


#: The legacy table carries no document body, span, versions or IntelEvent -- an EMPTY snapshot,
#: never a fabricated one (R2-build-spec.md section 6). Shared, never mutated.
_EMPTY_SOURCE_SNAPSHOT: Mapping[str, Any] = {}


def _canonical_claim_payload(legacy_row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The admission input's own carried canonical payload, if any -- `naga_claims` has no such
    column, so this is always `None` on the production cohort; a fake row built by a test may
    carry one, the same way R1's seed fixtures pair a legacy-shaped record with one."""

    payload = legacy_row.get("canonical_claim_payload")
    return payload if isinstance(payload, Mapping) else None


# ------------------------------------------------------------------------------------------
# Manifest -- pure, deterministic, no I/O.
# ------------------------------------------------------------------------------------------


def _stable_repr(value: Any) -> str:
    """A deterministic string form for any JSON-ish or DB-scalar value (UUID, date, Decimal,
    ...) -- `default=str` covers the non-JSON-native types `asyncpg` returns."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _field_hash(value: Any) -> str:
    return hashlib.sha256(_stable_repr(value).encode("utf-8")).hexdigest()


def compute_source_snapshot_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    """sha256 over a canonical JSON array of `{"id": ..., "fields": {column: sha256(value)}}`,
    one entry per row IN THE ORDER GIVEN (the caller's `ORDER BY id`). `id` stays in the clear;
    every other column's value is hashed first, so no legacy text enters the hash input."""

    entries = [
        {
            "id": str(row.get("id")),
            "fields": {str(key): _field_hash(value) for key, value in row.items() if key != "id"},
        }
        for row in rows
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decision_tuple(decision: AdmissionDecision) -> tuple[str, str, str | None]:
    if isinstance(decision, Admitted):
        return (decision.legacy_claim_id, "admitted", decision.family_id)
    return (decision.legacy_claim_id, "excluded", decision.reason)


def compute_manifest(
    *,
    cohort: str,
    source_snapshot_hash: str,
    decisions: Sequence[tuple[str, str, str | None]],
) -> tuple[str, str]:
    """Canonical JSON of `{cohort, source_snapshot_hash, decisions}` (decisions sorted by their
    own `legacy_claim_id`) and its sha256 -- the `run_id` `research_os_naga_admission` uses."""

    ordered = sorted(decisions, key=lambda item: item[0])
    manifest_obj: dict[str, Any] = {
        "cohort": cohort,
        "source_snapshot_hash": source_snapshot_hash,
        "decisions": [list(item) for item in ordered],
    }
    manifest_json = json.dumps(manifest_obj, sort_keys=True, separators=(",", ":"))
    manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    return manifest_json, manifest_hash


@dataclass(frozen=True)
class _Computed:
    rows: list[dict[str, Any]]
    decisions: list[AdmissionDecision]
    source_snapshot_hash: str
    manifest_hash: str
    admitted: int
    excluded: int
    excluded_by_reason: Mapping[str, int]


async def _compute(conn: asyncpg.Connection, *, cohort: str) -> _Computed:
    """The one dry-run pipeline, fresh every call -- `run_apply` reruns this to detect drift."""

    rows = await _load_legacy_rows(conn)
    decisions: list[AdmissionDecision] = [
        admit(row, source_snapshot=_EMPTY_SOURCE_SNAPSHOT) for row in rows
    ]
    summary = summarize(decisions)
    source_snapshot_hash = compute_source_snapshot_hash(rows)
    _, manifest_hash = compute_manifest(
        cohort=cohort,
        source_snapshot_hash=source_snapshot_hash,
        decisions=[_decision_tuple(d) for d in decisions],
    )
    logger.info(
        "computed %s: legacy_rows=%d admitted=%d excluded=%d",
        cohort,
        len(rows),
        summary.admitted,
        summary.excluded,
    )
    return _Computed(
        rows=rows,
        decisions=decisions,
        source_snapshot_hash=source_snapshot_hash,
        manifest_hash=manifest_hash,
        admitted=summary.admitted,
        excluded=summary.excluded,
        excluded_by_reason=dict(summary.excluded_by_reason),
    )


# ------------------------------------------------------------------------------------------
# Report shape.
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class KindCounts:
    eligible: int = 0
    inserted: int = 0
    already_present: int = 0
    excluded: int = 0
    rejected: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "eligible": self.eligible,
            "inserted": self.inserted,
            "already_present": self.already_present,
            "excluded": self.excluded,
            "rejected": self.rejected,
        }


def _zero_kind_counts() -> dict[str, KindCounts]:
    return {kind: KindCounts() for kind in KINDS}


@dataclass(frozen=True)
class DryRunReport:
    mode: str
    cohort: str
    manifest_hash: str
    source_snapshot_hash: str
    legacy_rows_read: int
    admitted: int
    excluded: int
    excluded_by_reason: Mapping[str, int]
    kind_counts: Mapping[str, KindCounts]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "cohort": self.cohort,
            "manifest_hash": self.manifest_hash,
            "source_snapshot_hash": self.source_snapshot_hash,
            "legacy_rows_read": self.legacy_rows_read,
            "admitted": self.admitted,
            "excluded": self.excluded,
            "excluded_by_reason": dict(self.excluded_by_reason),
            "kinds": {kind: counts.as_dict() for kind, counts in self.kind_counts.items()},
        }


@dataclass(frozen=True)
class ApplyReport:
    mode: str
    cohort: str
    manifest_hash: str
    source_snapshot_hash: str
    legacy_rows_read: int
    admitted: int
    excluded: int
    excluded_by_reason: Mapping[str, int]
    kind_counts: Mapping[str, KindCounts]
    written: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "cohort": self.cohort,
            "manifest_hash": self.manifest_hash,
            "source_snapshot_hash": self.source_snapshot_hash,
            "legacy_rows_read": self.legacy_rows_read,
            "admitted": self.admitted,
            "excluded": self.excluded,
            "excluded_by_reason": dict(self.excluded_by_reason),
            "kinds": {kind: counts.as_dict() for kind, counts in self.kind_counts.items()},
            "written": [
                {"object_id": object_id, "object_hash": object_hash}
                for object_id, object_hash in self.written
            ],
        }


def render_report(report: DryRunReport | ApplyReport, *, as_json: bool = False) -> str:
    """Counts and hashes only -- never a legacy field's value. Same shape in text and JSON."""

    data = report.as_dict()
    if as_json:
        return json.dumps(data, sort_keys=True, indent=2)

    lines = [
        f"mode: {data['mode']}",
        f"cohort: {data['cohort']}",
        f"manifest_hash: {data['manifest_hash']}",
        f"source_snapshot_hash: {data['source_snapshot_hash']}",
        f"legacy_rows_read: {data['legacy_rows_read']}",
        f"admitted: {data['admitted']}",
        f"excluded: {data['excluded']}",
        "excluded_by_reason:",
    ]
    for reason in sorted(data["excluded_by_reason"]):
        lines.append(f"  {reason}: {data['excluded_by_reason'][reason]}")
    lines.append("kinds:")
    for kind in KINDS:
        counts = data["kinds"][kind]
        lines.append(
            f"  {kind}: eligible={counts['eligible']} inserted={counts['inserted']} "
            f"already_present={counts['already_present']} excluded={counts['excluded']} "
            f"rejected={counts['rejected']}"
        )
    if "written" in data:
        lines.append("written:")
        for entry in data["written"]:
            lines.append(f"  {entry['object_id']}: {entry['object_hash']}")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------
# Dry-run.
# ------------------------------------------------------------------------------------------


async def run_dry_run(conn: asyncpg.Connection, *, cohort: str) -> DryRunReport:
    computed = await _compute(conn, cohort=cohort)
    row_by_id = {str(row.get("id")): row for row in computed.rows}

    eligible = 0
    candidate_object_ids: list[str] = []
    for decision in computed.decisions:
        if not isinstance(decision, Admitted):
            continue
        eligible += 1
        payload = _canonical_claim_payload(row_by_id.get(decision.legacy_claim_id, {}))
        if payload is not None:
            candidate = payload.get("claim_id")
            if isinstance(candidate, str) and candidate:
                candidate_object_ids.append(candidate)
    already_present = await _already_present_object_ids(conn, candidate_object_ids)

    kind_counts = _zero_kind_counts()
    kind_counts["claim"] = KindCounts(
        eligible=eligible,
        inserted=0,
        already_present=len(already_present),
        excluded=computed.excluded,
        rejected=0,
    )
    return DryRunReport(
        mode="dry-run",
        cohort=cohort,
        manifest_hash=computed.manifest_hash,
        source_snapshot_hash=computed.source_snapshot_hash,
        legacy_rows_read=len(computed.rows),
        admitted=computed.admitted,
        excluded=computed.excluded,
        excluded_by_reason=computed.excluded_by_reason,
        kind_counts=kind_counts,
    )


# ------------------------------------------------------------------------------------------
# Apply.
# ------------------------------------------------------------------------------------------


class SourceSnapshotDrifted(Exception):
    """`--apply`'s recomputed manifest disagrees with the one the caller named. Zero writes."""

    def __init__(self, *, given: str, computed: str) -> None:
        self.given = given
        self.computed = computed
        super().__init__(f"source snapshot drifted: given={given} computed={computed}")


@dataclass(frozen=True)
class _ApplyOutcome:
    kind_counts: dict[str, KindCounts]
    written: tuple[tuple[str, str], ...]


async def _execute_apply(
    conn: asyncpg.Connection,
    *,
    manifest_hash: str,
    source_snapshot_hash: str,
    rows: Sequence[Mapping[str, Any]],
    decisions: Sequence[AdmissionDecision],
) -> _ApplyOutcome:
    """Rule: only an Admitted decision whose admission input carries a canonical payload becomes
    a write. Everything else (Excluded, or Admitted-without-payload) touches no connection here.
    One transaction wraps the whole batch (`write_objects` / `record_admissions` each nest their
    own via an asyncpg SAVEPOINT), so a mid-batch failure leaves neither table changed."""

    row_by_id = {str(row.get("id")): row for row in rows}
    eligible = excluded = rejected = 0
    pending: list[tuple[ObjectWrite, Admitted]] = []

    for decision in decisions:
        if isinstance(decision, Excluded):
            excluded += 1
            continue
        payload = _canonical_claim_payload(row_by_id.get(decision.legacy_claim_id, {}))
        if payload is None:
            rejected += 1
            continue
        write = ObjectWrite(
            object_kind="claim", object_id=str(payload.get("claim_id") or ""), payload=payload
        )
        validate_object(write)
        pending.append((write, decision))
        eligible += 1

    inserted_ids: tuple[str, ...] = ()
    already_present_ids: tuple[str, ...] = ()
    if pending:
        async with conn.transaction():
            write_result = await write_objects(conn, [write for write, _ in pending])
            inserted_ids = write_result.inserted_ids
            already_present_ids = write_result.already_present_ids
            admission_rows = [
                AdmissionRow(
                    run_id=manifest_hash,
                    legacy_claim_id=decision.legacy_claim_id,
                    family_id=decision.family_id,
                    claim_object_id=write.object_id,
                    claim_object_hash=str(write.payload["object_hash"]),
                    evidence_object_ids=(),
                    evidence_object_hashes=(),
                    source_snapshot_hash=source_snapshot_hash,
                    decision="admitted",
                    reason=None,
                )
                for write, decision in pending
            ]
            await record_admissions(conn, admission_rows)

    written = tuple(
        (write.object_id, str(write.payload["object_hash"]))
        for write, _ in pending
        if write.object_id in inserted_ids
    )
    kind_counts = _zero_kind_counts()
    kind_counts["claim"] = KindCounts(
        eligible=eligible,
        inserted=len(inserted_ids),
        already_present=len(already_present_ids),
        excluded=excluded,
        rejected=rejected,
    )
    return _ApplyOutcome(kind_counts=kind_counts, written=written)


async def run_apply(conn: asyncpg.Connection, *, cohort: str, manifest: str) -> ApplyReport:
    """Recomputes the dry-run pipeline fresh; refuses (zero writes) on any disagreement with
    `manifest` before opening a transaction."""

    computed = await _compute(conn, cohort=cohort)
    if computed.manifest_hash != manifest:
        raise SourceSnapshotDrifted(given=manifest, computed=computed.manifest_hash)

    outcome = await _execute_apply(
        conn,
        manifest_hash=manifest,
        source_snapshot_hash=computed.source_snapshot_hash,
        rows=computed.rows,
        decisions=computed.decisions,
    )
    return ApplyReport(
        mode="apply",
        cohort=cohort,
        manifest_hash=manifest,
        source_snapshot_hash=computed.source_snapshot_hash,
        legacy_rows_read=len(computed.rows),
        admitted=computed.admitted,
        excluded=computed.excluded,
        excluded_by_reason=computed.excluded_by_reason,
        kind_counts=outcome.kind_counts,
        written=outcome.written,
    )


# ------------------------------------------------------------------------------------------
# CLI.
# ------------------------------------------------------------------------------------------


def _refuse(code: int, message: str) -> NoReturn:
    print(message, file=sys.stderr)  # noqa: T201 -- the refusal message IS the operator output
    raise SystemExit(code)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.services.research_os.naga_backfill",
        description=(
            "D4/D5 NAGA legacy-claim backfill. Dry-run by default; --apply requires "
            "--manifest <64-hex> from a prior dry-run and writes only if it still agrees."
        ),
    )
    parser.add_argument(
        "--cohort",
        required=True,
        help=f"cohort name; only {PRODUCTION_COHORT!r} is production-eligible in this slice",
    )
    parser.add_argument("--dry-run", action="store_true", help="read-only (default mode)")
    parser.add_argument("--apply", action="store_true", help="write; requires --manifest")
    parser.add_argument("--manifest", help="64-hex manifest hash from a prior --dry-run")
    parser.add_argument(
        "--dsn-env",
        default=DEFAULT_DSN_ENV,
        help=f"name of the env var carrying the DSN (default {DEFAULT_DSN_ENV})",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.dry_run and args.apply:
        _refuse(2, "refused: --dry-run and --apply are mutually exclusive")
    if args.cohort != PRODUCTION_COHORT:
        _refuse(
            2,
            f"refused: unsupported cohort {args.cohort!r}; only {PRODUCTION_COHORT!r} is "
            "production-eligible in this slice",
        )
    if args.apply:
        if not args.manifest:
            _refuse(2, "refused: --apply requires --manifest <64-hex>")
        if _MANIFEST_RE.fullmatch(args.manifest) is None:
            _refuse(2, "refused: --manifest must be 64 lowercase hex characters")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    args = _build_parser().parse_args(argv)
    _validate_args(args)
    return args


def _require_dsn(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        _refuse(2, f"refused: environment variable {env_name} is not set")
    return value


async def _dry_run_main(dsn: str, *, cohort: str) -> DryRunReport:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET default_transaction_read_only = on")
        return await run_dry_run(conn, cohort=cohort)
    finally:
        await conn.close()


async def _apply_main(dsn: str, *, cohort: str, manifest: str) -> ApplyReport:
    conn = await asyncpg.connect(dsn)
    try:
        return await run_apply(conn, cohort=cohort, manifest=manifest)
    finally:
        await conn.close()


def _emit(text: str) -> None:
    """The ONE explicit writer function the report goes to stdout through."""

    print(text)  # noqa: T201 -- the report IS this CLI's output


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    dsn = _require_dsn(args.dsn_env)

    if args.apply:
        try:
            report: DryRunReport | ApplyReport = asyncio.run(
                _apply_main(dsn, cohort=args.cohort, manifest=args.manifest)
            )
        except SourceSnapshotDrifted as exc:
            logger.warning("apply refused: source snapshot drifted (given=%s)", exc.given)
            _refuse(3, "refused: source_snapshot_drifted")
    else:
        report = asyncio.run(_dry_run_main(dsn, cohort=args.cohort))

    _emit(render_report(report, as_json=args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
