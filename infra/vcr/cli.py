#!/usr/bin/env python3
"""infra/vcr/cli.py — the accessor's shell-callable CLI contract (R6).

Errexit-immune caller pattern (W101/W108 — a bare assignment under `set -e`
can abort before the check runs): out=$(cmd 2>&1); rc=$?; judge the JSON,
never the rc alone in isolation (W104 — a rc alone can't distinguish
"not-yet-true" from "cannot verify" from "verifier itself is broken").

Exit codes (checked in this PRECEDENCE order — a verifier problem dominates
everything else, since nothing downstream can be trusted if the checker
itself can't be trusted):
  5 = verifier DRIFTED/FAILED
  4 = CANNOT-VERIFY — either coverage MISSING (no observation exists, e.g.
      remote host or never probed; distinct from "failing") OR the caller
      asked about a (seat, host, auth_context) triple that isn't in the
      expected-claim registry at all (UnregisteredClaimError — a caller
      error, not a claim this pilot tracks). The two are distinguished in
      the JSON body (`{"error": "unregistered_claim", ...}` vs a full
      MaterializedState with coverage_state="MISSING") — judge the JSON,
      never the rc alone (see module docstring above).
  3 = STALE/EXPIRED freshness (a probe was attempted or allowed but the
      state is still not CURRENT)
  2 = truth_state != TRUE
  0 = all four axes healthy

Usage:
    python3 -m infra.vcr.cli check --seat claude --host m5 --auth-context interactive
    python3 -m infra.vcr.cli check --seat claude --host m5 --auth-context interactive --no-probe
    python3 -m infra.vcr.cli findings --json
    python3 infra/vcr/cli.py findings --json   # direct-file invocation also works
                                                # (proprioception's "wrap" probes call
                                                # scripts by file path, not -m)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support direct-file invocation (`python3 infra/vcr/cli.py ...`), not only
# `-m infra.vcr.cli` — proprioception.py's wrap-probe existence pre-check
# expects argv[1] to be a real file path, so this file must also work when
# executed directly. `-m` gets the repo root on sys.path via cwd
# automatically; direct-file execution does not, so bootstrap it here,
# BEFORE the infra.vcr imports below (idempotent — a no-op under `-m`).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from infra.vcr import accessor
from infra.vcr.records import HEALTHY, PRESENT
from infra.vcr.registry import load_registry


def exit_code_for(state) -> int:
    if state.verifier_state != HEALTHY:
        return 5
    if state.coverage_state != PRESENT:
        return 4
    if state.freshness_state != "CURRENT":
        return 3
    if state.truth_state != "TRUE":
        return 2
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        state = accessor.get_state(
            args.seat, args.host, args.auth_context, allow_probe=not args.no_probe,
        )
    except accessor.UnregisteredClaimError as e:
        print(json.dumps({"error": "unregistered_claim", "detail": str(e)}, ensure_ascii=False))
        return 4
    print(json.dumps(state.to_dict(), ensure_ascii=False))
    return exit_code_for(state)


def _unhealthy_reason(state) -> str:
    """Synthesizes a status string from the axes that are ACTUALLY unhealthy —
    never the raw last-observation status (Codex red-team finding,
    2026-08-03): reporting obs[-1].raw_status here let a verifier-DRIFTED or
    hysteresis-not-yet-confirmed claim surface as e.g. "LIVE" — the exact
    arsenal_probe vocabulary that proprioception's OTHER (sibling)
    arsenal_seats entry treats as healthy. The two entries read different
    contracts; conflating their vocabularies silently defeated the pilot's
    one converted consumer. Every token here is a VCR axis name, which will
    never collide with an arsenal_probe raw status."""
    parts = []
    if state.verifier_state != HEALTHY:
        parts.append(f"VERIFIER_{state.verifier_state}")
    if state.coverage_state != PRESENT:
        parts.append(f"COVERAGE_{state.coverage_state}")
    if state.freshness_state != "CURRENT":
        parts.append(f"FRESHNESS_{state.freshness_state}")
    if state.truth_state != "TRUE":
        parts.append(f"TRUTH_{state.truth_state}")
    return "_".join(parts) if parts else "UNKNOWN_UNHEALTHY"  # all_healthy() was False elsewhere


def cmd_findings(args: argparse.Namespace) -> int:
    """Proprioception-compatible {"findings": [...]} — a drop-in for
    arsenal_probe.py --read-last --json, but routed through the enforced
    accessor (hysteresis-debounced, verifier-audited) instead of a raw file
    parse. Cache-only (allow_probe=False): the live refresh stays
    healer-run.sh's job, unchanged — this subcommand must never itself
    trigger a dispatch (it runs inside proprioception's own budgeted probe
    loop, which does not expect a nested live LLM call).

    Every entry emitted here is ALREADY unhealthy (state.all_healthy() is
    False) — the corresponding proprioception registry entry's ok_values
    MUST stay empty; there is no secondary "ignore this subtype" concept."""
    reg = load_registry()
    local_machine = accessor.local_machine_label()
    findings = []
    for claim in reg:
        if claim.host != local_machine:
            continue
        state = accessor.get_state(
            claim.seat, claim.host, claim.auth_context, allow_probe=False,
        )
        if not state.all_healthy():
            findings.append({"seat": claim.seat, "status": _unhealthy_reason(state)})
    print(json.dumps({"findings": findings}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="check one (seat, host, auth_context) claim")
    p_check.add_argument("--seat", required=True)
    p_check.add_argument("--host", required=True)
    p_check.add_argument("--auth-context", required=True, dest="auth_context")
    p_check.add_argument("--no-probe", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_findings = sub.add_parser("findings", help="proprioception-compatible findings list")
    p_findings.add_argument("--json", action="store_true")  # accepted for symmetry; always JSON
    p_findings.set_defaults(func=cmd_findings)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
