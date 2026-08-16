#!/usr/bin/env python3
"""QW-6a — HRR reason audit: repo-side scripts/queries.

Re-measures the conclusive-rate and per-reason-code counts on the LIVE
``visa_decisions`` ledger, post rule-pack seq-7 activation, the moment a
read-only DSN is available (that execution step is QW-6b, gated on an
operator credential — NOT run by this task).

GROUNDING (verified on disk, this session — cite, do not re-derive; see
``hrr_reason_audit.sql`` header for the migration-line citations):

* ``visa_decisions.verdict`` is the 5-value ``DecisionState`` CHECK enum
  (migration 252) — NOT a generic conclusive/inconclusive tri-state.
* There is NO ``review_reason_codes`` column anywhere on ``visa_decisions``
  (252 explicitly defers it). The reason codes live INSIDE the
  ``grounding_summary`` JSONB array (migration 255) as claims shaped
  ``{"claim_kind": "REVIEW_REASON", "claim_code": "<reason code>",
  "source_record_ids": [...]}`` — built by
  ``backend/services/visa_engine/shadow.py::_build_grounding_summary``.
* ``traffic_source`` (migration 256) is nullable TEXT IN ('real',
  'synthetic_gold', 'synthetic_driver'); NULL means "legacy/unknown
  provenance" and must never be silently folded into 'real'. This module
  buckets NULL as ``"legacy_unknown"`` everywhere, on purpose — the
  contamination guard QW-6a exists to enforce.
* ``visa_rule_packs.sequence`` (migration 250) is the pack-activation
  sequence number the plan's "pack seq-7" baseline refers to. It is UNIQUE
  only per ``(environment, jurisdiction, decision_domain)`` (250's own
  constraint), NOT globally — a TEST-environment pack and a PRODUCTION
  pack can both be "sequence 7". ``visa_decisions.jurisdiction`` and
  ``.decision_domain`` are each single-valued CHECK enums today ('ID' /
  'IMMIGRATION_VISA' only — 252), so fixing ``environment`` (below) is
  sufficient to make "seq-7" mean one thing.
* ``visa_decisions.environment`` (migration 252) is a CHECK enum IN
  ('TEST', 'STAGING', 'PRODUCTION'). This module filters/reports on
  PRODUCTION only by default (``--environment``) — kimi adversarial review
  finding F1/F2 (2026-08-16): without this, TEST/STAGING rows pollute the
  "live ledger" conclusive-rate this audit exists to measure, and combined
  with the per-scope ``sequence`` above, a TEST pack "seq 7" and a
  PRODUCTION pack "seq 7" would silently collapse into one bucket.

CONTRACT: this module contains ONLY pure computation
(``compute_reason_counts`` / ``compute_conclusive_rate`` /
``compute_sequence_activation_split``) plus a thin, optional asyncpg fetch
path (``fetch_decisions_pg``) used ONLY when a DSN is supplied. The pure
functions are exercised by the fixture-driven pytest suite
(``tests/test_hrr_reason_audit.py``) with ZERO network/prod access. QW-6b
runs this same module against the live ledger once a read-only credential
exists.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

logger = logging.getLogger("hrr_reason_audit")

# migration 252's DecisionState CHECK enum, verbatim — closed vocabulary.
VALID_VERDICTS = frozenset(
    {
        "NEEDS_INPUT",
        "SUPPORTED_CANDIDATES",
        "HUMAN_REVIEW_REQUIRED",
        "NO_SUPPORTED_PATH",
        "TEMPORARILY_UNAVAILABLE",
    }
)

# migration 256's CHECK enum, verbatim.
VALID_TRAFFIC_SOURCES = frozenset({"real", "synthetic_gold", "synthetic_driver"})

LEGACY_UNKNOWN_BUCKET = "legacy_unknown"

# Verdicts counted as "conclusive" for the conclusive-rate gate: anything
# that is NOT HUMAN_REVIEW_REQUIRED / NEEDS_INPUT / TEMPORARILY_UNAVAILABLE.
# NO_SUPPORTED_PATH is conclusive too (the engine reached a definite
# negative answer) — only the three "we could not decide" states are not.
INCONCLUSIVE_VERDICTS = frozenset(
    {"HUMAN_REVIEW_REQUIRED", "NEEDS_INPUT", "TEMPORARILY_UNAVAILABLE"}
)

DEFAULT_MIN_SEQUENCE = 7


def _traffic_bucket(raw: str | None) -> str:
    """Map a raw traffic_source value to its reporting bucket.

    NULL/legacy and any value outside the migration-256 CHECK enum both land
    in ``legacy_unknown`` — fail-closed, matches shadow_evidence.py's own
    "reported as legacy, counted toward NEITHER gate" precedent (256 header).
    """

    if raw in VALID_TRAFFIC_SOURCES:
        return raw
    return LEGACY_UNKNOWN_BUCKET


@dataclass(frozen=True)
class DecisionRow:
    """One flattened ``visa_decisions`` row, as consumed by this module.

    Field names mirror the SQL column names in ``hrr_reason_audit.sql``
    Query 1-3 so a Postgres row (via ``fetch_decisions_pg``) and a JSON
    fixture row need no field-renaming step.
    """

    decision_id: str
    verdict: str
    traffic_source: str | None
    rule_pack_sequence: int | None
    ruleset_activation_id: str | None
    grounding_summary: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    # Optional (default None = "unknown scope"): fixtures that predate the
    # F1/F2 fix may omit these. filter_rows() treats None as "does not match
    # any concrete --environment/--engine-mode filter" (fail-closed, not
    # fail-open) so an old fixture without these keys is simply excluded by
    # a scoped filter rather than silently counted as PRODUCTION/SHADOW.
    environment: str | None = None
    engine_mode: str | None = None

    def __post_init__(self) -> None:
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(
                f"decision {self.decision_id!r} has unknown verdict {self.verdict!r} "
                f"(not in migration 252's DecisionState enum)"
            )

    @property
    def traffic_bucket(self) -> str:
        return _traffic_bucket(self.traffic_source)

    @property
    def review_reason_codes(self) -> list[str]:
        """claim_code of every REVIEW_REASON claim in grounding_summary."""

        codes, _malformed = self._review_reason_codes_and_malformed_count()
        return codes

    def _review_reason_codes_and_malformed_count(self) -> tuple[list[str], int]:
        codes: list[str] = []
        malformed = 0
        for claim in self.grounding_summary:
            if not isinstance(claim, Mapping):
                continue
            if claim.get("claim_kind") != "REVIEW_REASON":
                continue
            code = claim.get("claim_code")
            if isinstance(code, str) and code:
                codes.append(code)
            else:
                # F9 (kimi adversarial review, QW-6a): a REVIEW_REASON claim
                # with a missing/non-string claim_code is exactly the "dirty
                # data" an audit must surface, not silently drop — counted
                # so build_report can report it instead of hiding it.
                malformed += 1
        return codes, malformed


def row_from_mapping(raw: Mapping[str, Any]) -> DecisionRow:
    """Build a DecisionRow from a loosely-typed mapping (asyncpg Record or
    a JSON fixture dict). Tolerates a JSON-encoded-string grounding_summary
    (asyncpg returns jsonb columns as str by default unless a codec is set)
    as well as an already-decoded list.
    """

    grounding_raw = raw.get("grounding_summary") or []
    if isinstance(grounding_raw, str):
        try:
            grounding_raw = json.loads(grounding_raw)
        except json.JSONDecodeError:
            logger.warning(
                "decision %s: grounding_summary is not valid JSON, treating as empty",
                raw.get("decision_id"),
            )
            grounding_raw = []
    if not isinstance(grounding_raw, list):
        grounding_raw = []

    rule_pack_sequence = raw.get("rule_pack_sequence")
    if rule_pack_sequence is not None:
        rule_pack_sequence = int(rule_pack_sequence)

    return DecisionRow(
        decision_id=str(raw["decision_id"]),
        verdict=str(raw["verdict"]),
        traffic_source=raw.get("traffic_source"),
        rule_pack_sequence=rule_pack_sequence,
        ruleset_activation_id=(
            str(raw["ruleset_activation_id"])
            if raw.get("ruleset_activation_id") is not None
            else None
        ),
        grounding_summary=tuple(grounding_raw),
        environment=raw.get("environment"),
        engine_mode=raw.get("engine_mode"),
    )


# ---------------------------------------------------------------------------
# Pure computation — fixture-tested, zero I/O.
# ---------------------------------------------------------------------------

DEFAULT_ENVIRONMENT = "PRODUCTION"
DEFAULT_ENGINE_MODE = "SHADOW"
SCOPE_FILTER_ALL = "ALL"


def filter_rows(
    rows: Iterable[DecisionRow],
    *,
    environment: str | None = DEFAULT_ENVIRONMENT,
    engine_mode: str | None = DEFAULT_ENGINE_MODE,
) -> list[DecisionRow]:
    """Scope the ledger to one (environment, engine_mode) pair before any
    other computation runs (kimi review F1/F2/F8, 2026-08-16).

    ``environment``/``engine_mode`` of ``None`` (or the sentinel
    ``SCOPE_FILTER_ALL``) disables that filter — use only for an explicit
    cross-scope debugging pass, never as the audit's default, because
    ``visa_rule_packs.sequence`` is unique only within one (environment,
    jurisdiction, decision_domain) triple (migration 250): mixing
    environments makes "pack seq-7" mean two different packs at once.
    """

    want_env = None if environment in (None, SCOPE_FILTER_ALL) else environment
    want_mode = None if engine_mode in (None, SCOPE_FILTER_ALL) else engine_mode

    out: list[DecisionRow] = []
    for row in rows:
        if want_env is not None and row.environment != want_env:
            continue
        if want_mode is not None and row.engine_mode != want_mode:
            continue
        out.append(row)
    return out


def compute_reason_counts(
    rows: Iterable[DecisionRow], *, min_sequence: int = DEFAULT_MIN_SEQUENCE
) -> dict[str, dict[str, dict[str, int]]]:
    """(a) count per reason-code across HUMAN_REVIEW_REQUIRED decisions,
    split by traffic_source bucket (mandatory) and gated to
    rule_pack_sequence >= min_sequence ("post-seq-7").

    Returns {traffic_bucket: {reason_code: {"reason_count": N,
    "decisions_with_this_reason": M}}}.
    """

    counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"reason_count": 0, "decisions_with_this_reason": 0})
    )
    for row in rows:
        if row.verdict != "HUMAN_REVIEW_REQUIRED":
            continue
        if row.rule_pack_sequence is None or row.rule_pack_sequence < min_sequence:
            continue
        codes = row.review_reason_codes
        seen_this_decision: set[str] = set()
        for code in codes:
            bucket = counts[row.traffic_bucket][code]
            bucket["reason_count"] += 1
            if code not in seen_this_decision:
                bucket["decisions_with_this_reason"] += 1
                seen_this_decision.add(code)
    return {bucket: dict(reasons) for bucket, reasons in counts.items()}


def compute_malformed_review_reason_claims(
    rows: Iterable[DecisionRow], *, min_sequence: int = DEFAULT_MIN_SEQUENCE
) -> dict[str, int]:
    """Count REVIEW_REASON claims with a missing/non-string claim_code, per
    traffic_source bucket, on HUMAN_REVIEW_REQUIRED rows in scope (kimi
    review F9, 2026-08-16). Dirty data an audit must surface, not hide."""

    malformed: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.verdict != "HUMAN_REVIEW_REQUIRED":
            continue
        if row.rule_pack_sequence is None or row.rule_pack_sequence < min_sequence:
            continue
        _codes, count = row._review_reason_codes_and_malformed_count()
        if count:
            malformed[row.traffic_bucket] += count
    return dict(malformed)


def compute_conclusive_rate(
    rows: Iterable[DecisionRow], *, min_sequence: int = DEFAULT_MIN_SEQUENCE
) -> dict[str, dict[str, Any]]:
    """(b) conclusive-rate split: verdict counts + share per traffic_source
    bucket, gated to rule_pack_sequence >= min_sequence ("post-seq-7").

    Returns {traffic_bucket: {"total": N, "conclusive": C, "inconclusive": I,
    "conclusive_rate_pct": pct, "by_verdict": {verdict: count}}}.
    """

    by_bucket: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if row.rule_pack_sequence is None or row.rule_pack_sequence < min_sequence:
            continue
        by_bucket[row.traffic_bucket][row.verdict] += 1

    report: dict[str, dict[str, Any]] = {}
    for bucket, verdict_counts in by_bucket.items():
        total = sum(verdict_counts.values())
        inconclusive = sum(
            n for v, n in verdict_counts.items() if v in INCONCLUSIVE_VERDICTS
        )
        conclusive = total - inconclusive
        report[bucket] = {
            "total": total,
            "conclusive": conclusive,
            "inconclusive": inconclusive,
            "conclusive_rate_pct": round(100.0 * conclusive / total, 2) if total else None,
            "by_verdict": dict(verdict_counts),
        }
    return report


def compute_sequence_activation_split(
    rows: Iterable[DecisionRow],
) -> dict[str, dict[str, dict[str, dict[str, int]]]]:
    """(d) optional split by rule_pack sequence / ruleset_activation_id,
    still carrying traffic_source (mandatory contamination guard).

    Returns {sequence_key: {activation_key: {traffic_bucket: {verdict: count}}}}
    where sequence_key/activation_key are strings ("unknown" for NULL).
    """

    report: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    )
    for row in rows:
        seq_key = str(row.rule_pack_sequence) if row.rule_pack_sequence is not None else "unknown"
        act_key = row.ruleset_activation_id or "unknown"
        report[seq_key][act_key][row.traffic_bucket][row.verdict] += 1

    return {
        seq: {
            act: {bucket: dict(verdicts) for bucket, verdicts in buckets.items()}
            for act, buckets in acts.items()
        }
        for seq, acts in report.items()
    }


def build_report(
    rows: Sequence[DecisionRow],
    *,
    min_sequence: int = DEFAULT_MIN_SEQUENCE,
    environment: str | None = DEFAULT_ENVIRONMENT,
    engine_mode: str | None = DEFAULT_ENGINE_MODE,
) -> dict[str, Any]:
    """Filter rows to (environment, engine_mode) FIRST (F1/F2/F8), then run
    every other computation only on that scoped set — including the
    un-gated sequence_activation_split, which would otherwise mix scopes
    that happen to share a rule_pack.sequence number.
    """

    scoped = filter_rows(rows, environment=environment, engine_mode=engine_mode)
    return {
        "min_sequence": min_sequence,
        "environment_filter": environment,
        "engine_mode_filter": engine_mode,
        "total_rows_fetched": len(rows),
        "total_rows_in_scope": len(scoped),
        "reason_counts": compute_reason_counts(scoped, min_sequence=min_sequence),
        "malformed_review_reason_claims": compute_malformed_review_reason_claims(
            scoped, min_sequence=min_sequence
        ),
        "conclusive_rate": compute_conclusive_rate(scoped, min_sequence=min_sequence),
        "sequence_activation_split": compute_sequence_activation_split(scoped),
    }


# ---------------------------------------------------------------------------
# I/O boundary — fixture loader (tests) + Postgres fetch (QW-6b, live only).
# ---------------------------------------------------------------------------


def load_fixture(path: Path) -> list[DecisionRow]:
    """Load a JSON fixture: a list of decision-row dicts, same shape as
    ``hrr_reason_audit.sql`` Query 3's flattened columns. No network access.
    """

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"fixture {path} must contain a JSON array of decision rows")
    return [row_from_mapping(item) for item in data]


async def fetch_decisions_pg(dsn: str) -> list[DecisionRow]:
    """Fetch the flattened decision rows straight from the live ledger via a
    READ-ONLY DSN (QW-6b execution only — never called by this task or its
    tests). Async per CLAUDE.md golden rule #4/#10; a one-shot audit script,
    not a persistent-server hot path, so a fresh connection is correct here.
    """

    import asyncpg  # local import: keeps this module importable without

    # asyncpg installed when only the pure computation path is exercised.

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET default_transaction_read_only = on")
        rows = await conn.fetch(
            """
            SELECT
                d.decision_id::text                  AS decision_id,
                d.verdict                            AS verdict,
                d.traffic_source                     AS traffic_source,
                d.environment                        AS environment,
                d.engine_mode                        AS engine_mode,
                rp.sequence                          AS rule_pack_sequence,
                d.ruleset_activation_id::text        AS ruleset_activation_id,
                d.grounding_summary::text            AS grounding_summary
            FROM public.visa_decisions d
            LEFT JOIN public.visa_rule_packs rp ON rp.id = d.rule_pack_id
            WHERE d.engine_surface = 'MATCH'
            """
            # No environment/engine_mode WHERE clause here on purpose: this
            # fetch stays scope-agnostic (mirrors hrr_reason_audit.sql Query
            # 3), and filter_rows() applies the (environment, engine_mode)
            # scope in build_report() — one place decides the scope, not two
            # (kimi review F1/F2/F8: d.decision_id, not the surrogate d.id).
        )
    finally:
        await conn.close()
    return [row_from_mapping(dict(record)) for record in rows]


def _write_output(report: Mapping[str, Any], out: Path | None) -> None:
    text = json.dumps(report, indent=2, sort_keys=True)
    if out is None:
        print(text)
    else:
        out.write_text(text + "\n", encoding="utf-8")
        logger.info("wrote report to %s", out)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Path to a JSON fixture (list of decision-row dicts). No network access.",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help=(
            "Read-only Postgres DSN. Falls back to $VISA_DECISIONS_RO_DSN "
            "ONLY when --fixture is not given (kimi review F3, 2026-08-16: "
            "an operator with VISA_DECISIONS_RO_DSN exported must still be "
            "able to run --fixture for a dry run). QW-6b execution only — "
            "never pass this in a test."
        ),
    )
    parser.add_argument(
        "--min-sequence",
        type=int,
        default=DEFAULT_MIN_SEQUENCE,
        help=f"rule_pack.sequence cutoff for the 'post-seq-N' gate (default {DEFAULT_MIN_SEQUENCE}).",
    )
    parser.add_argument(
        "--environment",
        default=DEFAULT_ENVIRONMENT,
        help=(
            f"visa_decisions.environment to scope to (default {DEFAULT_ENVIRONMENT}). "
            f"Pass {SCOPE_FILTER_ALL} to disable this filter — debugging only, "
            "never for a reported figure (see filter_rows() docstring)."
        ),
    )
    parser.add_argument(
        "--engine-mode",
        default=DEFAULT_ENGINE_MODE,
        help=(
            f"visa_decisions.engine_mode to scope to (default {DEFAULT_ENGINE_MODE}). "
            f"Pass {SCOPE_FILTER_ALL} to disable this filter."
        ),
    )
    parser.add_argument("--out", type=Path, help="Write JSON report here instead of stdout.")
    args = parser.parse_args(argv)

    if args.fixture and args.dsn:
        parser.error("pass either --fixture or --dsn, not both")
    if not args.fixture and not args.dsn:
        args.dsn = os.environ.get("VISA_DECISIONS_RO_DSN")
    if not args.fixture and not args.dsn:
        parser.error("pass --fixture (offline) or --dsn/VISA_DECISIONS_RO_DSN (live ledger)")

    if args.fixture:
        rows = load_fixture(args.fixture)
    else:
        import asyncio

        rows = asyncio.run(fetch_decisions_pg(args.dsn))

    report = build_report(
        rows,
        min_sequence=args.min_sequence,
        environment=args.environment,
        engine_mode=args.engine_mode,
    )
    _write_output(report, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
