#!/usr/bin/env python3
"""organ_birth.py — the organ BIRTH generator: genes imprinted by default.

DNA/GENOME mutation (research/operations/2026-07-06-dna-self-healing-genome.md):
this is the point where organs are born. It scaffolds plist + wrapper with every
gene from infra/organ-conformance/genes.json already implanted, so inheritance
is vertical (birth) instead of horizontal (copy-paste from the last healthy
organ). Opting OUT of a gene means deleting code — not remembering to add it.

Genes imprinted in the emitted artifacts:
  G1_registry        — organs_registry.yaml entry (applied with --apply, else printed)
  G2_heartbeat       — sidecar written on success, error, disabled AND wrong-node paths
  G3_declared_pair   — declared-pairs.json entry for the live HOME copy
  G4_node_guard      — hostname != assigned node -> heartbeat status=disabled + exit 0
                       (VISIBLE graceful exit — panel 2026-07-06: never a silent skip)
  G5_kill_switch     — <ID>_ENABLED=false honored, final heartbeat status=disabled
  G6_spawn_hardened  — (--kind llm-cron) claude -p with the 4 headless gotchas cured:
                       W84 ssh-localhost trampoline, --strict-mcp-config + empty MCP,
                       </dev/null stdin, wall-clock watchdog
  G7_ledger          — PENDING-ARMS line printed for .claude/skills/modus/PENDING-ARMS.md
  G8_keepalive_sane  — cron -> StartInterval (no KeepAlive); daemon -> KeepAlive with
                       a real blocking loop in the wrapper (#7 antidote)
  G9_fail_visible    — set -u, timestamped log function, no swallowed exits
  G10_single_instance— pidfile + liveness probe + trap cleanup

The conformance gate (infra/organ-conformance/check_organ_conformance.py) verifies
these same genes at merge time — genes.json is the shared contract, and
test_organ_conformance.py fails if generator and gate ever diverge on it.

Usage:
  python3 scripts/organ_birth.py --id mini.foo_bar --node mini --schedule 14400 \
      --kind cron --description "what this organ does" [--apply]

Default is print-mode (snippets to paste). --apply additionally writes the
registry entry (+ checksum) and the declared-pair into THIS worktree — safe:
they land in your branch and travel through the normal PR gate.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(
    subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    ).stdout.strip() or "."
).resolve()

GENES_PATH = REPO / "infra/organ-conformance/genes.json"
REGISTRY_PATH = REPO / "apps/organism/organism/organs_registry.yaml"
PAIRS_PATH = REPO / "infra/home-fork/declared-pairs.json"
WRAPPER_DIR = REPO / "infra/launchagents/wrappers"
PLIST_DIR = REPO / "infra/launchagents"

# Lowercase canon: `hostname -s` case differs by macOS name source (Mini
# reports "mini-pro2" while its ComputerName is "Mini-Pro2") — the guard
# lowercases both sides before comparing, so the map must be lowercase too.
NODE_HOSTNAMES = {"mini": "mini-pro2", "pro": "nuzantara"}
# M5 is EXCLUDED by design: interactive laptop, no daemon fleet (CLAUDE.md §1).


def sh_var(organ_id: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", organ_id.upper())


def wrapper_template(organ_id: str, node: str, kind: str, description: str) -> str:
    var = sh_var(organ_id)
    hostname = NODE_HOSTNAMES[node]
    llm = kind == "llm-cron"
    daemon = kind == "daemon"

    head = f'''#!/bin/bash
# {organ_id} — {description}
# Born via scripts/organ_birth.py (DNA/GENOME 2026-07-06): genes imprinted at birth.
# Canon: infra/launchagents/wrappers/{organ_id.replace(".", "-")}.sh
# Live:  ~/scripts/{organ_id.replace(".", "-")}.sh (declared pair, node={node})

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="{organ_id}"
LOG_DIR="$HOME/logs/{organ_id.replace(".", "-")}"
LOG="$LOG_DIR/run.log"
mkdir -p "$LOG_DIR"
SIDECAR_DIR="$HOME/.organism/last_seen"
PIDFILE="/tmp/nuzantara-{organ_id.replace(".", "-")}.pid"

ts() {{ date '+%Y-%m-%d %H:%M:%S'; }}
log() {{ echo "[$(ts)] $*" >> "$LOG"; }}

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() {{ # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{{"ts":"%s","status":"%s","note":"%s"}}\\n' \\
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}}

# G4_node_guard — wrong node exits VISIBLY (heartbeat), never silently (#10)
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "{hostname}" ]; then
    log "node guard: $(hostname -s) != {hostname} — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ
if [ "${{{var}_ENABLED:-true}}" = "false" ]; then
    log "kill switch {var}_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# G10_single_instance — pidfile + liveness probe + trap cleanup
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT
'''

    if llm:
        body = f'''
# ---- G6_spawn_hardened: headless claude with the 4 gotchas cured ------------
# (1) bypass-acceptance: ~/.claude.json needs bypassPermissionsModeAccepted=true
#     on THIS machine (one-time, operator) — else silent hang at spawn.
# (2) folder-trust: cd into the repo BEFORE spawning — else trust-dialog hang.
# (3) TCC is PER-BINARY (W84): under launchd, bash may read ~/Desktop while the
#     node binary behind claude blocks on invisible consent. Cure: UNCONDITIONAL
#     ssh-localhost trampoline in non-ssh contexts (sshd holds FDA, children inherit).
# (4) hygiene: stdin </dev/null; empty MCP config (each server is a sync-init
#     hang risk in -p mode); OAuth token from env, Keychain can be LOCKED here.
REPO="$HOME/nuzantara"
MAX_WALL_S="${{{var}_MAX_WALL_S:-3300}}"
# claude binary is NOT at the same path fleet-wide (Mini: /opt/homebrew symlink;
# Pro: ~/.local/bin only — healer-pro first tick died exit=127 on a hardcoded
# homebrew default). Env override wins; otherwise probe, then PATH.
CLAUDE_BIN="${{{var}_CLAUDE_BIN:-}}"
if [ -z "$CLAUDE_BIN" ]; then
    for _c in /opt/homebrew/bin/claude "$HOME/.local/bin/claude" /usr/local/bin/claude; do
        if [ -x "$_c" ]; then CLAUDE_BIN="$_c"; break; fi
    done
fi
[ -n "$CLAUDE_BIN" ] || CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"
MODEL="${{{var}_MODEL:-claude-sonnet-5}}"

if [ -z "${{{var}_TRAMPOLINED:-}}" ] && [ -z "${{SSH_CONNECTION:-}}" ]; then
    if [ -f "$HOME/.ssh/id_local_trampoline" ]; then
        log "W84: non-ssh context — re-exec via ssh-localhost trampoline (TCC is per-binary)"
        rm -f "$PIDFILE"
        exec ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \\
            -i "$HOME/.ssh/id_local_trampoline" localhost "{var}_TRAMPOLINED=1 bash '$0'"
    fi
    log "WARN: no trampoline key — claude child may TCC-hang (watchdog will reap)"
fi
if ! /bin/ls "$REPO/CLAUDE.md" >/dev/null 2>&1; then
    log "FATAL: TCC denies $REPO in this context"; heartbeat "error" "TCC denied"; exit 78
fi
cd "$REPO" || {{ heartbeat "error" "repo missing"; exit 1; }}

[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
if [ -z "${{CLAUDE_CODE_OAUTH_TOKEN:-}}" ] && [ -n "${{CLAUDE_CODE_OAUTH_TOKEN_1:-}}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_1"
fi

SESSION_LOG="$LOG_DIR/session-$(date +%Y%m%d-%H%M%S).log"
if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
    log "FATAL: no claude binary (env {var}_CLAUDE_BIN, /opt/homebrew, ~/.local, /usr/local, PATH all empty)"
    heartbeat "error" "no claude binary"
    exit 1
fi
"$CLAUDE_BIN" -p "TODO: your standing mandate here" \\
    --model "$MODEL" --dangerously-skip-permissions \\
    --strict-mcp-config --mcp-config '{{"mcpServers":{{}}}}' \\
    </dev/null > "$SESSION_LOG" 2>&1 &
CPID=$!
( sleep "$MAX_WALL_S"; kill -0 "$CPID" 2>/dev/null && kill "$CPID" && \\
    echo "[$(ts)] WATCHDOG: killed after ${{MAX_WALL_S}}s" >> "$LOG" ) &
WPID=$!
wait "$CPID"; RC=$?
kill "$WPID" 2>/dev/null

if [ $RC -eq 0 ]; then heartbeat "ok" "session done"; else heartbeat "error" "session exit=$RC"; fi
log "done rc=$RC"
exit 0
'''
    elif daemon:
        body = '''
# ---- G8_keepalive_sane: DAEMON — a real blocking loop, launchd never cycles (#7)
heartbeat "starting" "daemon loop entering"
while true; do
    # TODO: one unit of daemon work here
    heartbeat "ok" "loop alive"
    log "tick"
    sleep 60
done
'''
    else:  # cron
        body = '''
# ---- payload (cron one-shot; G8_keepalive_sane: plist uses StartInterval, no KeepAlive)
log "run start"
# TODO: the organ's actual work here
RC=$?

if [ $RC -eq 0 ]; then
    heartbeat "ok" "run done"
else
    heartbeat "error" "rc=$RC"   # G9: failure is VISIBLE in the sidecar too
fi
log "run done rc=$RC"
exit 0
'''
    return head + body


def plist_template(label: str, wrapper_live: str, kind: str, schedule: int) -> str:
    if kind == "daemon":
        # G8_keepalive_sane: KeepAlive legitimate — wrapper holds a blocking loop
        timing = "    <key>KeepAlive</key><true/>\n    <key>RunAtLoad</key><true/>"
    else:
        timing = (
            f"    <key>StartInterval</key><integer>{schedule}</integer>\n"
            "    <key>RunAtLoad</key><false/>"
        )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{wrapper_live}</string>
    </array>
{timing}
    <key>StandardOutPath</key><string>/tmp/{label}.out</string>
    <key>StandardErrorPath</key><string>/tmp/{label}.err</string>
</dict>
</plist>
'''


def registry_entry(organ_id: str, node: str, kind: str, schedule: int,
                   label: str, wrapper_repo: str, description: str) -> str:
    organ_type = "daemon" if kind == "daemon" else "cron"
    return f'''- id: {organ_id}
  runtime: {node}_launchd
  type: {organ_type}
  expected_hb_seconds: {schedule}
  owner_module: {wrapper_repo}
  dependencies: []
  recovery_action: launchctl_kickstart
  recovery_params:
    host: {node}
    label: {label}
  severity_on_silence: warning
  notes: '{description} (born via organ_birth.py, genes imprinted 2026+)'
  cicatrix_refs: []
  bridge_source:
    type: state_file
    path: ~/.organism/last_seen/{organ_id}.json
    timestamp_field: ts
    status_field: status
'''


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Birth a new organ with genes imprinted")
    ap.add_argument("--id", required=True, help="organ id, e.g. mini.foo_bar")
    ap.add_argument("--node", required=True, choices=sorted(NODE_HOSTNAMES))
    ap.add_argument("--kind", default="cron", choices=["cron", "daemon", "llm-cron"])
    ap.add_argument("--schedule", type=int, default=3600,
                    help="StartInterval seconds (also expected_hb_seconds)")
    ap.add_argument("--description", required=True)
    ap.add_argument("--label", default=None, help="launchd label (default com.nuzantara.<id>)")
    ap.add_argument("--apply", action="store_true",
                    help="also write registry entry (+checksum) and declared-pair in this worktree")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+", args.id):
        print(f"invalid organ id: {args.id!r} (want e.g. mini.foo_bar)", file=sys.stderr)
        return 2

    dash = args.id.replace(".", "-").replace("_", "-")
    label = args.label or f"com.nuzantara.{dash.split('-', 1)[-1] if dash.startswith(args.node) else dash}"
    wrapper_name = f"{dash}.sh"
    wrapper_repo_rel = f"infra/launchagents/wrappers/{wrapper_name}"
    wrapper_live = f"/Users/nuzantara/scripts/{wrapper_name}"
    plist_path = PLIST_DIR / f"{label}.plist"
    wrapper_path = WRAPPER_DIR / wrapper_name

    for p in (plist_path, wrapper_path):
        if p.exists():
            print(f"refusing to overwrite existing {p}", file=sys.stderr)
            return 2

    genes = json.loads(GENES_PATH.read_text(encoding="utf-8"))["genes"]

    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text(
        wrapper_template(args.id, args.node, args.kind, args.description), encoding="utf-8")
    wrapper_path.chmod(0o755)
    plist_path.write_text(
        plist_template(label, wrapper_live, args.kind, args.schedule), encoding="utf-8")

    reg_snippet = registry_entry(args.id, args.node, args.kind, args.schedule,
                                 label, wrapper_repo_rel, args.description)
    pair_snippet = {"live": f"~/scripts/{wrapper_name}", "repo": wrapper_repo_rel,
                    "machines": [args.node]}
    pair_snippet_plist = {"live": f"~/Library/LaunchAgents/{label}.plist",
                          "repo": f"infra/launchagents/{label}.plist",
                          "machines": [args.node]}

    applied = []
    if args.apply:
        # G1_registry — append + checksum (travels through the normal PR gate)
        reg_text = REGISTRY_PATH.read_text(encoding="utf-8")
        REGISTRY_PATH.write_text(reg_text.rstrip("\n") + "\n" + reg_snippet, encoding="utf-8")
        subprocess.run(
            [sys.executable, "-m", "organism.tools.validate_organs_registry",
             str(REGISTRY_PATH), "--update-checksum"],
            env={"PYTHONPATH": str(REPO / "apps/organism"), "PATH": "/usr/bin:/bin"},
            check=True, capture_output=True, text=True,
        )
        applied.append(str(REGISTRY_PATH.relative_to(REPO)))
        # G3_declared_pair — wrapper AND plist pairs
        pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
        pairs["pairs"].extend([pair_snippet, pair_snippet_plist])
        PAIRS_PATH.write_text(json.dumps(pairs, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
        applied.append(str(PAIRS_PATH.relative_to(REPO)))

    print(f"BORN {args.id} ({args.kind}, node={args.node}) — {len(genes)} genes in contract")
    print(f"  wrote {wrapper_path.relative_to(REPO)}")
    print(f"  wrote {plist_path.relative_to(REPO)}")
    for a in applied:
        print(f"  applied {a}")
    if not args.apply:
        print("\n--- G1_registry: append to apps/organism/organism/organs_registry.yaml"
              " then run --update-checksum ---")
        print(reg_snippet)
        print("--- G3_declared_pair: add to infra/home-fork/declared-pairs.json ---")
        print(json.dumps([pair_snippet, pair_snippet_plist], indent=2))
    print("\n--- G7_ledger: add to .claude/skills/modus/PENDING-ARMS.md ---")
    print(f"- [ ] {args.id}: built via organ_birth.py — NOT ARMED until plist installed on "
          f"{args.node} (`launchctl bootstrap`), live pair copied, first heartbeat verified "
          f"in ~/.organism/last_seen/{args.id}.json")
    print("\nNext: fill the TODO payload, run "
          "`python3 infra/organ-conformance/check_organ_conformance.py`, open the PR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
