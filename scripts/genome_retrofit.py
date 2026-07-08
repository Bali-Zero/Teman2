#!/usr/bin/env python3
"""genome_retrofit.py — deterministic gene GRAFT for grandfathered organs.

CONVERGENCE v2 (§CONVERGENCE of the genome doc, panel round-2 hardened):
the retrofit is a template transplant, NEVER LLM authorship — the gene blocks
below are the same shapes `organ_birth.py` imprints at birth, parametrized only
by organ id and node. This kills the reward-hacking vector (GLM S2: under
shrink-pressure a model emits gene-shaped theater; a template cannot).

What it does (idempotent, conservative, refuses > guesses):
  - G9_fail_visible      : insert `set -u` after the shebang/comment head
  - G2_heartbeat         : insert ORGAN_ID + heartbeat() (env-overridable sidecar
                           dir, disabled/ok/error aware) + trap-side "ok" is NOT
                           auto-wired — a success heartbeat is appended ONLY as an
                           EXIT-trap so it fires on every exit path with the real
                           exit code mapped to ok/error (no per-callsite guessing)
  - G5_kill_switch       : insert <VAR>_ENABLED=false gate writing a disabled
                           heartbeat before exit 0
  - G4_node_guard        : insert hostname guard (visible disabled heartbeat)
                           when --node is known
  - G10_single_instance  : insert pidfile + liveness probe + trap cleanup
  - G1_registry          : print (or --apply append+checksum) a registry entry

Dry-fire (Grok rail 2): --dry-fire runs the EDITED wrapper with
<VAR>_ENABLED=false and ORGANISM_LAST_SEEN_DIR pointed at a temp dir — this
executes the real interpreter through set -u, node-guard, kill-switch and
heartbeat WITHOUT touching the payload, and must exit 0 leaving a `disabled`
sidecar. A graft that cannot survive its own dry-fire never reaches a PR.

Refusals (exit 3): no shebang; wrapper already defines a conflicting
heartbeat()/PIDFILE with different semantics it cannot reconcile; non-bash.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(
    subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() or "."
).resolve()

NODE_HOSTNAMES = {"mini": "Mini-Pro2", "pro": "Nuzantara"}


def sh_var(organ_id: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", organ_id.upper())


def gene_blocks(organ_id: str, node: str | None) -> dict[str, str]:
    """The SAME shapes organ_birth imprints — single semantic source."""
    var = sh_var(organ_id)
    blocks = {
        "G9_fail_visible": "set -u   # G9_fail_visible (genome retrofit)\n",
        "G2_heartbeat": f'''ORGAN_ID="{organ_id}"
_GENOME_SIDECAR_DIR="${{ORGANISM_LAST_SEEN_DIR:-$HOME/.organism/last_seen}}"
# G2_heartbeat (genome retrofit) — sidecar every exit path
heartbeat() {{ # $1 status, $2 note
    mkdir -p "$_GENOME_SIDECAR_DIR" 2>/dev/null || return 0
    printf '{{"ts":"%s","status":"%s","note":"%s"}}\\n' \\
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$_GENOME_SIDECAR_DIR/$ORGAN_ID.json" 2>/dev/null || true
}}
_genome_exit_heartbeat() {{
    _rc=$?
    if [ "$_rc" -eq 0 ]; then heartbeat "ok" "run done"; else heartbeat "error" "rc=$_rc"; fi
}}
trap _genome_exit_heartbeat EXIT
''',
        "G5_kill_switch": f'''# G5_kill_switch (genome retrofit)
if [ "${{{var}_ENABLED:-true}}" = "false" ]; then
    heartbeat "disabled" "kill switch" 2>/dev/null || true
    trap - EXIT
    exit 0
fi
''',
        "G10_single_instance": f'''# G10_single_instance (genome retrofit)
_GENOME_PIDFILE="/tmp/nuzantara-{organ_id.replace(".", "-")}.pid"
if [ -f "$_GENOME_PIDFILE" ] && kill -0 "$(cat "$_GENOME_PIDFILE" 2>/dev/null)" 2>/dev/null; then
    heartbeat "ok" "skipped: previous run alive" 2>/dev/null || true
    trap - EXIT
    exit 0
fi
echo $$ > "$_GENOME_PIDFILE"
trap 'rm -f "$_GENOME_PIDFILE"; _genome_exit_heartbeat' EXIT
''',
    }
    if node:
        hostname = NODE_HOSTNAMES[node]
        blocks["G4_node_guard"] = f'''# G4_node_guard (genome retrofit) — visible wrong-node exit
if [ "$(hostname -s)" != "{hostname}" ]; then
    heartbeat "disabled" "wrong-node $(hostname -s)" 2>/dev/null || true
    trap - EXIT
    exit 0
fi
'''
    return blocks


# graft order matters: heartbeat must exist before guards that call it
GRAFT_ORDER = ["G9_fail_visible", "G2_heartbeat", "G4_node_guard",
               "G5_kill_switch", "G10_single_instance"]


def find_anchor(text: str) -> int:
    """Insertion offset: after shebang + leading comment/blank head."""
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].startswith("#!"):
        return -1
    idx = 1
    while idx < len(lines) and (
        lines[idx].startswith("#") or lines[idx].strip() == ""
    ):
        idx += 1
    return sum(len(l) for l in lines[:idx])


def graft(wrapper_text: str, organ_id: str, missing: list[str],
          node: str | None) -> tuple[str, list[str], list[str]]:
    """Returns (new_text, grafted, refused)."""
    blocks = gene_blocks(organ_id, node)
    grafted: list[str] = []
    refused: list[str] = []

    anchor = find_anchor(wrapper_text)
    if anchor < 0:
        return wrapper_text, [], [f"no shebang anchor for {organ_id}"]

    # conflict scan — refuse rather than guess (panel: conservative transform)
    if "G2_heartbeat" in missing and re.search(r"\bheartbeat\s*\(\)\s*\{", wrapper_text):
        refused.append("G2: wrapper already defines heartbeat() with unknown semantics")
        missing = [m for m in missing if m != "G2_heartbeat"]
    if "G10_single_instance" in missing and re.search(r"\bPIDFILE\b|\bflock\b", wrapper_text):
        refused.append("G10: wrapper already manages a pidfile/flock")
        missing = [m for m in missing if m != "G10_single_instance"]
    if ("G2_heartbeat" in missing or "G10_single_instance" in missing) and re.search(
            r"^\s*trap\b.*\bEXIT\b", wrapper_text, re.M):
        # a later trap silently REPLACES ours — the exit-heartbeat would be lost
        # on every run while looking grafted (silent theater, GLM S2 class)
        refused.append("G2/G10: wrapper sets its own EXIT trap — graft would be "
                       "silently overridden; operator retrofit")
        missing = [m for m in missing if m not in ("G2_heartbeat", "G10_single_instance")]
    if "G9_fail_visible" in missing and re.search(r"^\s*set\s+-[a-zA-Z]*u", wrapper_text, re.M):
        missing = [m for m in missing if m != "G9_fail_visible"]  # already there

    # guards depend on heartbeat(): the disabled-exit must stay VISIBLE (panel:
    # a kill-switch nobody can observe is how healers resurrect stopped organs).
    # If G2 is neither being grafted nor already a local function, dependent
    # genes are REFUSED — never silently downgraded to a mute exit.
    will_have_heartbeat = (
        "G2_heartbeat" in missing
        or re.search(r"\bheartbeat\s*\(\)\s*\{", wrapper_text) is not None
    )
    if not will_have_heartbeat:
        for dep in ("G4_node_guard", "G5_kill_switch", "G10_single_instance"):
            if dep in missing:
                refused.append(
                    f"{dep}: needs a local heartbeat() (wrapper uses a library "
                    f"writer or none) — visible-disabled invariant, operator retrofit"
                )
                missing = [m for m in missing if m != dep]

    insertion = ""
    for gene in GRAFT_ORDER:
        if gene not in missing or gene not in blocks:
            continue
        insertion += "\n" + blocks[gene]
        grafted.append(gene)

    if not insertion:
        return wrapper_text, [], refused or ["nothing graftable"]

    new_text = wrapper_text[:anchor] + insertion + "\n" + wrapper_text[anchor:]
    return new_text, grafted, refused


def dry_fire(wrapper_path: Path, organ_id: str) -> tuple[bool, str]:
    var = sh_var(organ_id)
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env[f"{var}_ENABLED"] = "false"
        env["ORGANISM_LAST_SEEN_DIR"] = td
        try:
            r = subprocess.run(
                ["bash", str(wrapper_path)], env=env,
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            return False, "dry-fire TIMEOUT (kill-switch path did not exit)"
        sidecar = Path(td) / f"{organ_id}.json"
        if r.returncode != 0:
            return False, f"dry-fire exit={r.returncode} stderr={r.stderr[-200:]}"
        if not sidecar.exists():
            return False, "dry-fire wrote no sidecar (heartbeat path dead)"
        try:
            status = json.loads(sidecar.read_text())["status"]
        except Exception as exc:  # noqa: BLE001
            return False, f"sidecar malformed: {exc}"
        if status != "disabled":
            return False, f"sidecar status={status!r}, expected 'disabled'"
        return True, "dry-fire OK: exit 0 + disabled sidecar"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic gene graft (genome retrofit)")
    ap.add_argument("--wrapper", required=True, help="repo-relative wrapper path")
    ap.add_argument("--organ-id", required=True)
    ap.add_argument("--node", choices=["mini", "pro"], default=None)
    ap.add_argument("--genes", required=True, help="comma-separated missing genes")
    ap.add_argument("--apply", action="store_true", help="write the grafted wrapper")
    ap.add_argument("--dry-fire", action="store_true", help="execute kill-switch path in a sandbox")
    args = ap.parse_args(argv)

    wrapper_path = (REPO / args.wrapper).resolve()
    if not wrapper_path.exists():
        print(f"wrapper missing: {wrapper_path}", file=sys.stderr)
        return 2
    text = wrapper_path.read_text(encoding="utf-8")
    missing = [g.strip() for g in args.genes.split(",") if g.strip()]

    new_text, grafted, refused = graft(text, args.organ_id, missing, args.node)
    result = {"organ": args.organ_id, "grafted": grafted, "refused": refused}

    if not grafted:
        print(json.dumps(result, indent=1))
        return 3

    # syntax gate before anything touches disk
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as tf:
        tf.write(new_text)
        tmp = Path(tf.name)
    try:
        rc = subprocess.run(["bash", "-n", str(tmp)], capture_output=True, text=True)
        if rc.returncode != 0:
            result["error"] = f"bash -n failed: {rc.stderr[-300:]}"
            print(json.dumps(result, indent=1))
            return 2

        if args.dry_fire:
            ok, why = dry_fire(tmp, args.organ_id)
            result["dry_fire"] = why
            if not ok:
                print(json.dumps(result, indent=1))
                return 2

        if args.apply:
            wrapper_path.write_text(new_text, encoding="utf-8")
            result["applied"] = str(wrapper_path.relative_to(REPO))
    finally:
        tmp.unlink(missing_ok=True)

    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
