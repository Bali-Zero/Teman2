#!/usr/bin/env python3
"""zero_population_monitor.py — generalized "kill switch off + table never
written" probe (megatopics-1-5 action plan #1, part 2; 2026-08-03).

Origin: the E33 guarantee-scan finding from the VCR reconciliation
(research/operations/2026-08-03-verified-claim-reconciliation.md) — a cron
has posted HTTP 200 `{"status":"blocked",...}` every day of its life because
its kill switch (`e33_guarantee_scan_enabled`) has NO ROW AT ALL in
`system_settings` (never provisioned) and its target table (`e33_cases`) has
0 rows: green, doing nothing (scar family #2, "esiste != armato" —
`.claude/rules/cicatrix-superscar.md`). Confirmed live via
`scripts/pg.sh -c "SELECT ..."` on 2026-08-03. This script generalizes that
ONE finding into a reusable, declared-registry probe so the next instance of
this shape doesn't need its own investigation.

Pure signaler: it never writes to the ledger, the switch, or the target
table. It only reads and reports. The only way it affects control flow is
its own exit code.

Exit codes:
    0   clean — every registry entry checked successfully and none alert
    1   >=1 registry entry alerts (see ALERT RULE below) — never returned if
        any entry could not be checked (see exit 2, which takes precedence)
    2   >=1 registry entry's query genuinely could not run (DB connection
        failure, pg.sh missing, timeout, unparseable output, or an unsafe
        registry identifier refused before querying). "Could not check" is
        NEVER silently reported as "clean" (W84 — a scan that could not look
        is not a clean scan) and never masked by an alert found elsewhere in
        the same run: an unverifiable entry makes the WHOLE verdict
        untrustworthy.

ALERT RULE (documented design decision — read before "fixing" this):
    The megatopics plan states the base rule as "alert if BOTH (switch
    unprovisioned) AND (table has zero rows) hold" — matching the live E33
    case exactly. This script alerts on that case
    (UNPROVISIONED_AND_EMPTY). It ALSO alerts when the switch IS provisioned
    (truthy) but the table is STILL empty (PROVISIONED_BUT_EMPTY) — a
    documented widening, not an oversight: a provisioned-but-never-written
    organ is arguably a WORSE finding than an unprovisioned one (the switch
    says "on", so whatever is supposed to write here should have fired at
    least once by now — the classic scar-family-#2 shape, "green cron that
    does nothing"). Silently NOT flagging that shape would leave exactly the
    failure mode this probe exists to catch sitting one field short of
    detection. A populated table NEVER alerts either way, regardless of
    provisioning — this probe is scoped to "has anything EVER landed here",
    not to auditing row correctness.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Registry entry shape: {"name": str, "switch_key": str, "table": str}.
# Seeded 2026-08-03 with the one live, verified finding (VCR §1): the kill
# switch has NO row in system_settings and the target table has 0 rows
# (both confirmed live via scripts/pg.sh SELECT, 2026-08-03).
DEFAULT_REGISTRY: List[Dict[str, str]] = [
    {
        "name": "e33_guarantee_scan",
        "switch_key": "e33_guarantee_scan_enabled",
        "table": "e33_cases",
    },
]

# Both patterns are deliberately conservative (word-chars, dot, dash, colon,
# underscore). The registry is a small, internally-declared, reviewed list —
# not user input — but a SQL identifier/literal built by string interpolation
# gets validated anyway as defense-in-depth (this org's own "match the
# entity, not a substring" discipline — family #3's antidote, applied here to
# SQL construction instead of a text guard).
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_SWITCH_KEY_RE = re.compile(r"^[a-zA-Z0-9_.:-]+$")


@dataclass
class QueryOutcome:
    """Result of one query_fn(sql) call. Never raise — degrade to ok=False."""

    ok: bool
    rows: List[List[str]] = field(default_factory=list)
    detail: str = ""


def _sql_quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _default_query_fn(sql: str) -> QueryOutcome:
    """Shell out to scripts/pg.sh -A -t -F'|' -c "<sql>" (read-only Fly proxy).

    -A -t -F'|' = unaligned, tuples-only, pipe-delimited: each output line is
    one row, columns pipe-split, no header noise to strip. Never raises: a
    missing pg.sh, a connection failure, a timeout, or a non-zero exit all
    collapse to ok=False with the diagnosis in .detail — the caller must
    treat that as "could not check", never as "zero rows" (W104: judge the
    reply, never assume success from bare non-crash).
    """
    pg_sh = Path(__file__).resolve().parent / "pg.sh"
    try:
        proc = subprocess.run(
            [str(pg_sh), "-A", "-t", "-F|", "-c", sql],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return QueryOutcome(ok=False, detail=f"{pg_sh} not found")
    except (subprocess.SubprocessError, OSError) as exc:
        return QueryOutcome(ok=False, detail=f"pg.sh invocation failed: {type(exc).__name__}")

    if proc.returncode != 0:
        reason = (proc.stderr or "").strip().splitlines()
        return QueryOutcome(ok=False, detail=reason[-1] if reason else f"pg.sh exited {proc.returncode}")

    rows = [line.split("|") for line in (proc.stdout or "").splitlines() if line.strip() != ""]
    return QueryOutcome(ok=True, rows=rows, detail="ok")


def _is_truthy_setting(raw: str) -> bool:
    """system_settings.value is stored as free-text; treat common truthy spellings.

    Anything else (including a present-but-explicitly-falsy value like
    'false'/'0'/'off'/'no') counts as NOT provisioned-on — a row existing
    with a falsy value is functionally the same as no row for this probe's
    purposes: the switch is not actually letting the organ run.
    """
    return raw.strip().lower() in {"true", "t", "1", "yes", "on", "enabled"}


def check_entry(
    entry: Dict[str, str],
    query_fn: Callable[[str], QueryOutcome] = _default_query_fn,
) -> Dict[str, Any]:
    """Check ONE registry entry. Never raises.

    Returns a dict: name, checked, provisioned, table_empty, alert, reason,
    detail. "checked" False means a query genuinely could not run (or an
    unsafe identifier was refused before ever querying) — provisioned/
    table_empty are then None and alert is always False; the caller must not
    read that as "clean" (see module docstring, exit code 2).
    """
    name = entry.get("name", "?")

    def _cannot_verify(detail: str, provisioned: Optional[bool] = None) -> Dict[str, Any]:
        return {
            "name": name,
            "checked": False,
            "provisioned": provisioned,
            "table_empty": None,
            "alert": False,
            "reason": "cannot-verify",
            "detail": detail,
        }

    table = entry.get("table", "")
    switch_key = entry.get("switch_key", "")
    if not _IDENTIFIER_RE.match(table):
        return _cannot_verify(f"refusing unsafe table identifier {table!r}")
    if not _SWITCH_KEY_RE.match(switch_key):
        return _cannot_verify(f"refusing unsafe switch_key {switch_key!r}")

    switch_sql = f"SELECT value FROM system_settings WHERE key = {_sql_quote_literal(switch_key)} LIMIT 1;"
    switch_result = query_fn(switch_sql)
    if not switch_result.ok:
        return _cannot_verify(f"switch check failed: {switch_result.detail}")
    provisioned = (
        bool(switch_result.rows)
        and bool(switch_result.rows[0])
        and _is_truthy_setting(switch_result.rows[0][0])
    )

    count_sql = f"SELECT count(*) FROM {table};"
    count_result = query_fn(count_sql)
    if not count_result.ok:
        return _cannot_verify(f"table count failed: {count_result.detail}", provisioned=provisioned)

    try:
        row_count = int(count_result.rows[0][0]) if count_result.rows and count_result.rows[0] else None
    except (ValueError, TypeError):
        row_count = None
    if row_count is None:
        return _cannot_verify(f"unparseable row count from {table!r}", provisioned=provisioned)

    table_empty = row_count == 0

    if not table_empty:
        # A populated table never alerts, regardless of provisioning — this
        # probe is scoped to "has anything EVER landed here", not row
        # auditing.
        reason = "healthy (table has rows)"
        alert = False
    elif not provisioned:
        reason = "UNPROVISIONED_AND_EMPTY (kill switch has no row / falsy value — the live E33 shape)"
        alert = True
    else:
        # Documented widening (see module docstring ALERT RULE): provisioned
        # but still zero rows also alerts — a provisioned-but-never-written
        # organ is at least as suspicious as an unprovisioned one.
        reason = "PROVISIONED_BUT_EMPTY (switch is on, table has never been written)"
        alert = True

    return {
        "name": name,
        "checked": True,
        "provisioned": provisioned,
        "table_empty": table_empty,
        "alert": alert,
        "reason": reason,
        "detail": "ok",
    }


def run(
    registry: List[Dict[str, str]],
    query_fn: Callable[[str], QueryOutcome] = _default_query_fn,
) -> List[Dict[str, Any]]:
    return [check_entry(entry, query_fn) for entry in registry]


def render_report(results: List[Dict[str, Any]]) -> str:
    lines = ["# zero-population-monitor report", ""]
    for r in results:
        lines.append(
            f"- {r['name']}: checked={r['checked']} provisioned={r['provisioned']} "
            f"table_empty={r['table_empty']} alert={r['alert']} — "
            f"{r['reason']} ({r['detail']})"
        )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zero_population_monitor.py",
        description=(
            "Pure signaler: for each declared {name, switch_key, table} triple, "
            "alert if a kill-switch-gated organ's target table has zero rows "
            "(generalizes the 2026-08-03 E33 finding). Never mutates anything."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a markdown report.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # NOTE: calls the module-global `_default_query_fn` by name (not
    # check_entry's/run's own default-parameter binding) so tests can
    # monkeypatch this module's `_default_query_fn` attribute and have it
    # actually take effect on the CLI path — a default-parameter value is
    # captured once at `def` time and would NOT observe a later monkeypatch.
    results = run(DEFAULT_REGISTRY, query_fn=_default_query_fn)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(render_report(results), end="")

    # Precedence: "could not check" beats "found a problem" beats "clean" —
    # an unverifiable entry makes the whole verdict untrustworthy (W84: a
    # scan that could not look is not a clean scan), so it must never be
    # masked by an alert found elsewhere in the same run.
    if any(not r["checked"] for r in results):
        return 2
    if any(r["alert"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
