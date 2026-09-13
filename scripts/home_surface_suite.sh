#!/usr/bin/env bash
# scripts/home_surface_suite.sh — test suite for the machine-local Claude surface.
#
# The repo side of the context diet (CLAUDE.md, rules, hooks) is covered by CI. The
# HOME side (~/.claude/settings.json, ~/.claude/agents, ~/.claude.json, the four
# SessionStart hooks as they run on THIS machine) had no suite at all: the 2026-09-04
# fleet apply on Pro and Mini was measured before/after and never tested. Zero's
# question ("ma mica deve fare suite test????") is the reason this file exists.
#
# Sections (select with --only a,b,c):
#   settings  ~/.claude/settings.json parses; env.ENABLE_TOOL_SEARCH == "true";
#             permissions.deny is a list; ~/.claude.json chrome flag is REPORTED.
#   agents    every ~/.claude/agents/*.md opens with frontmatter carrying name + description.
#   hooks     the four SessionStart hooks exit 0 and emit <= SESSIONSTART_HOOK_MAX_BYTES (1500).
#   homefork  scripts/lint_home_fork.py — REPORTED by default (its own failures predate the
#             diet and are owned by proprioception); --strict-homefork makes it gate.
#   budget    scripts/context_budget_audit.py --live total <= --max-tokens (default 30000).
#
# HOME is honoured, so a test can point the suite at a fixture directory.
# Exit 0 = PASS, 1 = FAIL, 2 = usage. Never prints a credential: settings.json is
# parsed for two structural keys and nothing else is echoed.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONLY="settings,agents,hooks,homefork,budget"
MAX_TOKENS="${HOME_SURFACE_MAX_TOKENS:-30000}"
STRICT_HOMEFORK=0

while [ $# -gt 0 ]; do
  case "$1" in
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --max-tokens) MAX_TOKENS="$2"; shift 2 ;;
    --strict-homefork) STRICT_HOMEFORK=1; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "usage: $0 [--repo-root DIR] [--only a,b,c] [--max-tokens N] [--strict-homefork]" >&2; exit 2 ;;
  esac
done

cd "$REPO_ROOT" || { echo "FAIL repo root not found: $REPO_ROOT"; exit 2; }
FAIL=0
want() { case ",$ONLY," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
ok()   { echo "ok    $*"; }
bad()  { echo "FAIL  $*"; FAIL=1; }
info() { echo "info  $*"; }

echo "home_surface_suite host=$(hostname -s 2>/dev/null || hostname) HOME=$HOME repo=$REPO_ROOT"

if want settings; then
  if out="$(python3 - "$HOME" <<'PY' 2>&1
import json, sys, pathlib
home = pathlib.Path(sys.argv[1])
s = json.loads((home / ".claude" / "settings.json").read_text())
ts = str(s.get("env", {}).get("ENABLE_TOOL_SEARCH", ""))
if ts != "true":
    raise SystemExit(f"env.ENABLE_TOOL_SEARCH is {ts!r}, expected 'true' (MCP + built-ins deferred)")
deny = s.get("permissions", {}).get("deny")
if not isinstance(deny, list):
    raise SystemExit("permissions.deny is not a list")
chrome = None
cj = home / ".claude.json"
if cj.exists():
    chrome = json.loads(cj.read_text()).get("claudeInChromeDefaultEnabled")
print(f"tool_search=true deny_entries={len(deny)} claudeInChromeDefaultEnabled={chrome}")
PY
)"; then ok "settings: $out"; else bad "settings: $out"; fi
fi

if want agents; then
  if out="$(python3 - "$HOME" <<'PY' 2>&1
import re, sys, pathlib
adir = pathlib.Path(sys.argv[1]) / ".claude" / "agents"
files = sorted(adir.glob("*.md")) if adir.is_dir() else []
broken = []
for f in files:
    text = f.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---") or text.count("---") < 2:
        broken.append(f"{f.name}(no-frontmatter)"); continue
    fm = text.split("---", 2)[1]
    for key in ("name", "description"):
        if not re.search(rf"^{key}:\s*\S", fm, re.M):
            broken.append(f"{f.name}(no-{key})")
if broken:
    raise SystemExit(f"{len(broken)} broken of {len(files)}: " + " ".join(broken[:8]))
print(f"{len(files)} agents, frontmatter intact")
PY
)"; then ok "agents: $out"; else bad "agents: $out"; fi
fi

if want hooks; then
  cap="${SESSIONSTART_HOOK_MAX_BYTES:-1500}"
  for h in escalations_alert_sessionstart proprioception_sessionstart organism_digest_sessionstart memory_recall_sessionstart; do
    hook="scripts/hooks/$h.sh"
    [ -f "$hook" ] || { bad "hooks: $hook missing"; continue; }
    bytes="$(CLAUDE_PROJECT_DIR="$REPO_ROOT" bash "$hook" 2>/dev/null </dev/null | wc -c | tr -d ' ')"
    rc="${PIPESTATUS[0]}"
    if [ "$rc" = 0 ] && [ "$bytes" -le "$cap" ]; then ok "hooks: $h bytes=$bytes rc=0"
    else bad "hooks: $h bytes=$bytes rc=$rc cap=$cap"; fi
  done
fi

if want homefork; then
  if [ -f scripts/lint_home_fork.py ]; then
    python3 scripts/lint_home_fork.py >/dev/null 2>&1; rc=$?
    if [ "$rc" = 0 ]; then ok "homefork: lint_home_fork exit 0"
    elif [ "$STRICT_HOMEFORK" = 1 ]; then bad "homefork: lint_home_fork exit $rc (1=diverged 2=undeclared 4=scan-error 8=.bak)"
    else info "homefork: lint_home_fork exit $rc — owned by proprioception, not gating here"; fi
  else info "homefork: scripts/lint_home_fork.py absent"; fi
fi

if want budget; then
  if total="$(python3 scripts/context_budget_audit.py --live --json --repo-root "$REPO_ROOT" 2>/dev/null \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["total_est_tokens"])' 2>&1)"; then
    if [ "$total" -le "$MAX_TOKENS" ] 2>/dev/null; then ok "budget: live surface est. ${total} tokens <= ${MAX_TOKENS}"
    else bad "budget: live surface est. ${total} tokens > ${MAX_TOKENS}"; fi
  else bad "budget: context_budget_audit failed: $total"; fi
fi

if [ "$FAIL" = 0 ]; then echo "SUITE_RESULT=PASS"; exit 0; fi
echo "SUITE_RESULT=FAIL"; exit 1
