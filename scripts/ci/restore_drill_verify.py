#!/usr/bin/env python3
"""restore_drill_verify.py — Level-5 application verification for the monthly
Postgres restore drill (`.github/workflows/restore-drill.yml`).

WHY THIS EXISTS: the drill used to declare success from a table CENSUS
(`TABLES=$(... information_schema.tables ...); test "$TABLES" -ge 50`) — a
restore producing 60 EMPTY tables passes that check. On 2026-06-06 a
`PGPASSWORD` env-prefix landed on the wrong side of a pipe, psql got no
password, the restore produced 0 tables, and the drill reported success
anyway: the exit code of a restore is not evidence the DATA arrived
(cicatrix-superscar.md family #2, "esiste != armato", applied to a backup
instead of a daemon).

WHAT THIS DOES INSTEAD: for five relations this repo has separately
hardened (file:line cited on each INVARIANTS entry below), it checks a
non-degenerate RESULT SHAPE — relation exists, every application-required
column is present, row count is not below a floor where zero is provably
wrong, JSON/JSONB columns hold the container shape the app promises
(never a bare scalar or an unparseable string), and each table's own
CHECK constraints are RE-VERIFIED at the app layer independently of
whether they survived the restore — a constraint the dump's DDL failed to
reinstate (possible under `ON_ERROR_STOP=0`, or a role lacking the
ledger-owner ALTER privilege some of these migrations require, see
cicatrix-scars.md W130) would otherwise let a broken row sit unnoticed.

A missing relation or a missing required column is a genuinely
diagnosable finding — scored FAIL, not CANNOT-VERIFY; only an UNTAKEN
measurement (query error, relation absent from the measurement set,
relation reported existing with zero columns, or a declared check absent
from the result) is CANNOT-VERIFY — never a silent PASS, never conflated
with a genuine FAIL (cicatrix-scars.md W106b / superscar #9: cannot-
measure is not measured-zero). Every invariant gets exactly one verdict
per run, reporting every reason found for it together — nothing dropped
because a worse-class reason also fired.

The violations query for a relation runs only once every column it names
is confirmed present (see the missing-column gate in `fetch_live`) — found
empirically: the first cut, run against a deliberately column-dropped
`conversations` table, reported a raw `column "messages" does not exist`
Postgres error where it should have reported the missing-column FAIL
directly. `pg_temp` objects (the `conversations` JSON-array check) are
SESSION-scoped, so the helper function and the query using it travel in
ONE `psql` invocation, never two.

REDACTION (SYMBIOSIS Law 2 / UU PDP): a measurement carries relation
names, column names, and COUNTS — never a row's own values. Fixtures
under scripts/tests/fixtures/restore_drill/ are synthetic only.

LIVE MODE talks to `psql` over a self-contained DSN in one argv token
(never a separately-exported `PGPASSWORD` prefixed onto one side of a pipe
— that construction is the 2026-06-06 bug class above), with
`-v ON_ERROR_STOP=1` so a broken query surfaces as an error, never a
truncated result.

Usage:
    restore_drill_verify.py --dsn postgresql://user:pass@host:port/db [--json]
    restore_drill_verify.py --fixture scripts/tests/fixtures/restore_drill/healthy.json
    restore_drill_verify.py --fixture scripts/tests/fixtures/restore_drill/degenerate.json --json

Exit codes:
    0   PASS — all five golden invariants verified clean
    1   FAIL — at least one invariant is genuinely violated (named per relation)
    2   usage error (argparse's own exit code)
    3   CANNOT-VERIFY — a measurement could not be taken. Never conflated
        with exit 0 or exit 1.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Optional, Sequence

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class Invariant:
    """One golden invariant. `checks` names the violation-count keys the
    measurement for this relation must report (each must be present in the
    measurement's `violations` dict, and each must be exactly 0)."""

    relation: str
    required_columns: tuple[str, ...]
    min_rows: Optional[int]
    checks: tuple[str, ...]

    def __post_init__(self) -> None:
        assert _IDENT_RE.match(self.relation), f"unsafe relation name: {self.relation!r}"


# Column lists and constraints below are taken from the migrations that
# introduced them, not invented — see the file:line cited on each relation.
INVARIANTS: tuple[Invariant, ...] = (
    # migrations_v2/143_legacy_conversations.sql: min_rows=1 (a production
    # restore to zero rows is degenerate); `messages` is TEXT but defaults
    # to '[]' — always meant to parse as a JSON array.
    Invariant(
        relation="conversations",
        required_columns=("id", "user_id", "messages", "created_at"),
        min_rows=1,
        checks=("messages_not_json_array",),
    ),
    # migrations_v2/136 (drive columns) + 223 (lead_metadata JSONB, an
    # OBJECT payload when present). client_type has only two values
    # codebase-wide but no DB CHECK constraint — why this re-check matters.
    Invariant(
        relation="clients",
        required_columns=(
            "id",
            "full_name",
            "client_type",
            "google_drive_folder_id",
            "created_at",
            "updated_at",
        ),
        min_rows=1,
        checks=("client_type_unknown", "lead_metadata_not_object"),
    ),
    # migrations_v2/252_visa_engine_write_substrate.sql: SHADOW-mode,
    # legitimately sparse/empty depending on backup timing — no row floor.
    # `citations` (JSONB array) and the TEMPORARILY_UNAVAILABLE/rule_pack_id
    # link both restate that migration's own CHECK constraints.
    Invariant(
        relation="visa_decisions",
        required_columns=(
            "id",
            "decision_id",
            "environment",
            "verdict",
            "citations",
            "rule_pack_id",
            "evaluated_at",
        ),
        min_rows=None,
        checks=(
            "verdict_unknown",
            "environment_unknown",
            "citations_not_array",
            "temporarily_unavailable_missing_pack",
        ),
    ),
    # migrations_v2/144_events_outbox.sql: pruned daily, legitimately
    # empty — no row floor. `payload` is JSONB NOT NULL (re-checked since a
    # partial restore may drop that constraint; a JSON `null` is as
    # degenerate as a SQL NULL). `consumed_at < created_at` is the ONE
    # check here with no existing DB constraint to restate — pure app-layer.
    Invariant(
        relation="events_outbox",
        required_columns=("id", "channel", "payload", "created_at", "consumed_at", "consumer_id"),
        min_rows=None,
        checks=("channel_blank", "payload_missing", "consumed_before_created"),
    ),
    # migrations_v2/264+268_visa_decision_retention_policy*.sql:
    # "deliberately seeds NO duration and NO policy row" (264's own
    # comment) — no row floor. The five checks restate that file's own
    # CHECK/UNIQUE constraints — the exact set an ON_ERROR_STOP=0 restore,
    # or a role missing ledger-owner ALTER (W130), could silently drop.
    Invariant(
        relation="visa_decision_retention_policies",
        required_columns=(
            "id",
            "environment",
            "policy_version",
            "retention_interval",
            "idempotency_retention_interval",
            "legal_hold_review_interval",
            "retention_anchor",
            "effective_period",
            "approved_by",
            "approval_reference",
            "created_at",
        ),
        min_rows=None,
        checks=(
            "environment_unknown",
            "retention_anchor_unknown",
            "idempotency_interval_out_of_bounds",
            "effective_period_invalid",
            "duplicate_environment_policy_version",
        ),
    ),
)

_INVARIANT_BY_RELATION: dict[str, Invariant] = {inv.relation: inv for inv in INVARIANTS}

# --- live-mode SQL: three queries per relation, in order ---------------
# 1) column probe (information_schema; safe even if the relation is absent)
# 2) row-count probe (names no column beyond the relation itself)
# 3) violations probe, run ONLY if every column its checks reference is
#    confirmed present. Every count is a scalar subquery so one bad row
#    can't fail the whole query — except `conversations`, which uses a
#    `pg_temp` helper so a malformed JSON row is COUNTED, not thrown.

_COLUMNS_SQL = (
    "SELECT to_jsonb(array_agg(column_name ORDER BY ordinal_position)) "
    "FROM information_schema.columns "
    "WHERE table_schema='public' AND table_name='{relation}';"
)

_ROW_COUNT_SQL = "SELECT count(*) FROM {relation};"

_CONVERSATIONS_VIOLATIONS_SQL = """
CREATE OR REPLACE FUNCTION pg_temp.try_jsonb_array(text) RETURNS boolean AS $$
BEGIN
  RETURN jsonb_typeof($1::jsonb) = 'array';
EXCEPTION WHEN OTHERS THEN
  RETURN false;
END;
$$ LANGUAGE plpgsql;
SELECT jsonb_build_object(
  'messages_not_json_array',
  (SELECT count(*) FROM conversations WHERE NOT pg_temp.try_jsonb_array(messages))
);
"""

_CLIENTS_VIOLATIONS_SQL = """
SELECT jsonb_build_object(
  'client_type_unknown',
  (SELECT count(*) FROM clients WHERE client_type NOT IN ('individual','company')),
  'lead_metadata_not_object',
  (SELECT count(*) FROM clients
     WHERE lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object')
);
"""

_VISA_DECISIONS_VIOLATIONS_SQL = """
SELECT jsonb_build_object(
  'verdict_unknown',
  (SELECT count(*) FROM visa_decisions WHERE verdict NOT IN (
     'NEEDS_INPUT','SUPPORTED_CANDIDATES','HUMAN_REVIEW_REQUIRED',
     'NO_SUPPORTED_PATH','TEMPORARILY_UNAVAILABLE')),
  'environment_unknown',
  (SELECT count(*) FROM visa_decisions WHERE environment NOT IN ('TEST','STAGING','PRODUCTION')),
  'citations_not_array',
  (SELECT count(*) FROM visa_decisions WHERE jsonb_typeof(citations) <> 'array'),
  'temporarily_unavailable_missing_pack',
  (SELECT count(*) FROM visa_decisions
     WHERE verdict <> 'TEMPORARILY_UNAVAILABLE' AND rule_pack_id IS NULL)
);
"""

_EVENTS_OUTBOX_VIOLATIONS_SQL = """
SELECT jsonb_build_object(
  'channel_blank',
  (SELECT count(*) FROM events_outbox WHERE channel IS NULL OR channel = ''),
  'payload_missing',
  (SELECT count(*) FROM events_outbox WHERE payload IS NULL OR jsonb_typeof(payload) = 'null'),
  'consumed_before_created',
  (SELECT count(*) FROM events_outbox WHERE consumed_at IS NOT NULL AND consumed_at < created_at)
);
"""

_VISA_RETENTION_POLICIES_VIOLATIONS_SQL = """
SELECT jsonb_build_object(
  'environment_unknown',
  (SELECT count(*) FROM visa_decision_retention_policies
     WHERE environment NOT IN ('TEST','STAGING','PRODUCTION')),
  'retention_anchor_unknown',
  (SELECT count(*) FROM visa_decision_retention_policies
     WHERE retention_anchor NOT IN ('EVALUATED_AT','CREATED_AT')),
  'idempotency_interval_out_of_bounds',
  (SELECT count(*) FROM visa_decision_retention_policies
     WHERE idempotency_retention_interval <= interval '0'
        OR idempotency_retention_interval > retention_interval),
  'effective_period_invalid',
  (SELECT count(*) FROM visa_decision_retention_policies
     WHERE isempty(effective_period) OR lower(effective_period) IS NULL),
  'duplicate_environment_policy_version',
  (SELECT COALESCE(SUM(c - 1), 0) FROM (
     SELECT count(*) AS c FROM visa_decision_retention_policies
     GROUP BY environment, policy_version HAVING count(*) > 1
   ) sub)
);
"""

_VIOLATIONS_SQL: dict[str, str] = {
    "conversations": _CONVERSATIONS_VIOLATIONS_SQL,
    "clients": _CLIENTS_VIOLATIONS_SQL,
    "visa_decisions": _VISA_DECISIONS_VIOLATIONS_SQL,
    "events_outbox": _EVENTS_OUTBOX_VIOLATIONS_SQL,
    "visa_decision_retention_policies": _VISA_RETENTION_POLICIES_VIOLATIONS_SQL,
}
assert set(_VIOLATIONS_SQL) == set(_INVARIANT_BY_RELATION), "every invariant needs a violations query"


def _run_psql(dsn: str, sql: str, psql_bin: str, timeout: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        [psql_bin, dsn, "-Atq", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def fetch_live(dsn: str, psql_bin: str = "psql", timeout: int = 30) -> list[dict[str, Any]]:
    """One measurement dict per declared invariant, in INVARIANTS order."""
    measurements: list[dict[str, Any]] = []
    for inv in INVARIANTS:
        try:
            rc, out, err = _run_psql(
                dsn, _COLUMNS_SQL.format(relation=inv.relation), psql_bin, timeout
            )
            if rc != 0:
                measurements.append({"relation": inv.relation, "error": err.strip() or f"psql exit {rc}"})
                continue
            raw = out.strip()
            columns = json.loads(raw) if raw else None
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            measurements.append({"relation": inv.relation, "error": f"{type(exc).__name__}: {exc}"})
            continue

        if columns is None:
            measurements.append({"relation": inv.relation, "exists": False})
            continue

        measurement: dict[str, Any] = {"relation": inv.relation, "exists": True, "columns": columns}

        # Row count names no column beyond the relation itself — safe either way.
        try:
            rc, out, err = _run_psql(
                dsn, _ROW_COUNT_SQL.format(relation=inv.relation), psql_bin, timeout
            )
            if rc != 0:
                measurements.append({"relation": inv.relation, "error": err.strip() or f"psql exit {rc}"})
                continue
            measurement["row_count"] = int(out.strip())
        except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
            measurements.append({"relation": inv.relation, "error": f"{type(exc).__name__}: {exc}"})
            continue

        # Only run this if the schema still has every column it names — a
        # missing column is already a FAIL via the evaluator's own
        # required-columns check; querying it anyway would instead surface
        # as an opaque Postgres parse error (measured, see the docstring).
        missing = [c for c in inv.required_columns if c not in columns]
        if not missing:
            try:
                rc, out, err = _run_psql(dsn, _VIOLATIONS_SQL[inv.relation], psql_bin, timeout)
                if rc == 0:
                    measurement["violations"] = json.loads(out.strip())
                # A nonzero rc needs no measurement error of its own:
                # `violations` stays absent and the evaluator already scores
                # a missing check as CANNOT-VERIFY, without discarding the
                # row_count/columns already measured successfully.
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                pass

        measurements.append(measurement)
    return measurements


# --- evaluation (pure, fixture-testable) --------------------------------


def _evaluate_one(spec: Invariant, measurement: Optional[dict[str, Any]]) -> dict[str, Any]:
    if measurement is None:
        return {
            "relation": spec.relation,
            "status": "CANNOT-VERIFY",
            "reasons": ["no measurement recorded for this relation"],
        }

    error = measurement.get("error")
    if error:
        return {"relation": spec.relation, "status": "CANNOT-VERIFY", "reasons": [f"query error: {error}"]}

    exists = measurement.get("exists")
    if exists is not True:
        return {"relation": spec.relation, "status": "FAIL", "reasons": ["relation missing from the restore"]}

    columns = measurement.get("columns")
    if not columns:
        # A relation cannot exist in Postgres with zero columns (a PRIMARY
        # KEY alone guarantees one) — the query is lying about its input.
        return {
            "relation": spec.relation,
            "status": "CANNOT-VERIFY",
            "reasons": ["relation reported as existing but zero columns were measured"],
        }

    # One combined reasons list: a FAIL-class finding and a CANNOT-VERIFY-
    # class one both get reported — nothing dropped for the worse class.
    reasons: list[str] = []
    cannot_verify = False

    missing_cols = [c for c in spec.required_columns if c not in columns]
    if missing_cols:
        reasons.append(f"missing required column(s): {', '.join(missing_cols)}")

    row_count = measurement.get("row_count")
    if row_count is None:
        reasons.append("row_count missing from measurement")
        cannot_verify = True
    elif spec.min_rows is not None and row_count < spec.min_rows:
        reasons.append(f"row_count {row_count} below floor {spec.min_rows}")

    violations = measurement.get("violations") or {}
    for check in spec.checks:
        if check not in violations:
            reasons.append(f"check '{check}' could not be measured (missing from result)")
            cannot_verify = True
            continue
        count = violations[check]
        # bool is an int subclass in Python (`True < 0` is False either
        # way) -- excluded so a fixture typo (`"x": true`) reads as
        # CANNOT-VERIFY, not a genuine-looking FAIL. --dsn can't hit this;
        # count(*) is always a bigint.
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            reasons.append(f"check '{check}' has a malformed value: {count!r}")
            cannot_verify = True
            continue
        if count != 0:
            reasons.append(f"{check}: {count} row(s) violate")

    if cannot_verify:
        status = "CANNOT-VERIFY"
    elif reasons:
        status = "FAIL"
    else:
        status = "PASS"
    return {"relation": spec.relation, "status": status, "reasons": reasons}


def evaluate(measurements: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure evaluator: exactly one verdict per declared invariant, driven by
    INVARIANTS — never by whichever relations happen to appear in the input.
    A relation the input silently drops is CANNOT-VERIFY, not a pass."""
    by_relation = {m["relation"]: m for m in measurements if isinstance(m, dict) and "relation" in m}
    per_invariant = [_evaluate_one(spec, by_relation.get(spec.relation)) for spec in INVARIANTS]

    statuses = {v["status"] for v in per_invariant}
    if "CANNOT-VERIFY" in statuses:
        aggregate = "CANNOT-VERIFY"
    elif "FAIL" in statuses:
        aggregate = "FAIL"
    else:
        aggregate = "PASS"

    return {"aggregate": aggregate, "invariants": per_invariant}


_EXIT_FOR_AGGREGATE = {"PASS": 0, "FAIL": 1, "CANNOT-VERIFY": 3}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--dsn", help="Postgres connection URI to probe live (postgresql://user:pass@host:port/db)")
    src.add_argument("--fixture", help="path to an offline fixture JSON (see scripts/tests/fixtures/restore_drill/)")
    parser.add_argument("--psql-bin", default="psql", help="psql executable to invoke in --dsn mode (default: psql)")
    parser.add_argument("--timeout", type=int, default=30, help="per-query timeout in seconds for --dsn mode (default: 30)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of prose")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.fixture:
        try:
            with open(args.fixture) as fh:
                data = json.load(fh)
            measurements = data["relations"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            if args.json:
                print(json.dumps({"aggregate": "CANNOT-VERIFY", "error": str(exc)}))
            else:
                print(f"CANNOT-VERIFY: unreadable fixture ({exc})", file=sys.stderr)
            return 3
    else:
        try:
            measurements = fetch_live(args.dsn, psql_bin=args.psql_bin, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001 — any failure here is CANNOT-VERIFY, never a silent pass
            if args.json:
                print(json.dumps({"aggregate": "CANNOT-VERIFY", "error": str(exc)}))
            else:
                print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
            return 3

    result = evaluate(measurements)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"AGGREGATE: {result['aggregate']}")
        for verdict in result["invariants"]:
            print(f"  {verdict['relation']}: {verdict['status']}")
            for reason in verdict["reasons"]:
                print(f"    - {reason}")

    return _EXIT_FOR_AGGREGATE[result["aggregate"]]


if __name__ == "__main__":
    sys.exit(main())
