#!/usr/bin/env bash
# test_cron_agent_fingerprint_map.sh — P2 no-op suppression sourced from the
# repo-tracked FINGERPRINT_MAP (infra/launchagents/cron-agent-fingerprints.json)
# instead of the per-crontab-line CRON_AGENT_SKIP_IF_UNCHANGED env var. This is
# what lets a job get armed by merging a PR — no crontab edit — so the tests
# pin exactly the properties that make that safe: env var still overrides the
# map (explicit beats implicit), a missing/malformed map is silent no-op (never
# blocks the agent), and a map-sourced fingerprint obeys the same fail-open +
# store-on-success-only rules as the env-var path (test_cron_agent_context_diet.sh
# already pins those for the env-var source; this file pins them again for the
# map source because the lookup is a DIFFERENT code path that could silently
# diverge).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"
[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "FAIL: jq not found — required by the map lookup"; exit 2; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/cronfpmap.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
FAILED=0
ok()  { echo "  ok   — $1"; }
bad() { echo "  FAIL — $1"; FAILED=1; }

PROMPT="$SANDBOX/prompt.txt"; echo "say hello" > "$PROMPT"
CALL_LOG="$SANDBOX/calls.log"

cat > "$SANDBOX/claude" <<'FAKE'
#!/usr/bin/env bash
echo CALL >> "$CALL_LOG"
echo "fake answer"
exit 0
FAKE
chmod +x "$SANDBOX/claude"

cat > "$SANDBOX/claude_fail" <<'FAKE'
#!/usr/bin/env bash
echo CALL >> "$CALL_LOG"
echo "boom" >&2
exit 9
FAKE
chmod +x "$SANDBOX/claude_fail"

cat > "$SANDBOX/timeout" <<'FAKE'
#!/usr/bin/env bash
shift
exec "$@"
FAKE
chmod +x "$SANDBOX/timeout"

run_agent_job() {  # $1=job name, $2=claude bin, $3=map file (or "" for none), rest = extra env
    local job="$1" bin="$2" map="$3"; shift 3
    : > "$CALL_LOG"
    env HOME="$SANDBOX" CALL_LOG="$CALL_LOG" \
        CRON_AGENT_CLAUDE_BIN="$bin" CRON_AGENT_TIMEOUT_BIN="$SANDBOX/timeout" \
        CRON_AGENT_FINGERPRINT_MAP="$map" \
        CLAUDE_CODE_OAUTH_TOKEN_1=faketoken \
        TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= \
        "$@" \
        bash "$WRAPPER" agent "$job" "$PROMPT" > "$SANDBOX/stdout.txt" 2>"$SANDBOX/stderr.txt"
    echo $?
}
calls() { wc -l < "$CALL_LOG" | tr -d ' '; }

# ── M1 guilt: map-sourced fingerprint, unchanged -> 2nd tick skips entirely ──
MAP1="$SANDBOX/map1.json"
cat > "$MAP1" <<JSON
{"mapped-job": "echo CONSTANT"}
JSON
rc1=$(run_agent_job mapped-job "$SANDBOX/claude" "$MAP1")
c1=$(calls)
rc2=$(run_agent_job mapped-job "$SANDBOX/claude" "$MAP1")
c2=$(calls)
if [ "$rc1" = "0" ] && [ "$c1" = "1" ] && [ "$rc2" = "0" ] && [ "$c2" = "0" ]; then
    ok "map-sourced fingerprint unchanged: 1st run calls claude, 2nd run skips"
else
    bad "map guilt: run1(rc=$rc1 calls=$c1) run2(rc=$rc2 calls=$c2) — want 1 then 0"
fi

# ── M2 innocence: explicit env var overrides the map, even for the same job ──
MAP2="$SANDBOX/map2.json"
cat > "$MAP2" <<JSON
{"override-job": "echo MAP_CONSTANT"}
JSON
rc1=$(run_agent_job override-job "$SANDBOX/claude" "$MAP2" CRON_AGENT_SKIP_IF_UNCHANGED="echo ENV_V1")
c1=$(calls)
rc2=$(run_agent_job override-job "$SANDBOX/claude" "$MAP2" CRON_AGENT_SKIP_IF_UNCHANGED="echo ENV_V2")
c2=$(calls)
if [ "$rc1" = "0" ] && [ "$c1" = "1" ] && [ "$rc2" = "0" ] && [ "$c2" = "1" ]; then
    ok "explicit env var wins over the map: a changing env fingerprint still re-runs (map's constant would have skipped)"
else
    bad "env-overrides-map: run1(rc=$rc1 calls=$c1) run2(rc=$rc2 calls=$c2) — want 1 then 1"
fi

# ── M3 innocence: job absent from the map -> no fingerprint configured, always runs ──
rc1=$(run_agent_job unmapped-job "$SANDBOX/claude" "$MAP1")
c1=$(calls)
rc2=$(run_agent_job unmapped-job "$SANDBOX/claude" "$MAP1")
c2=$(calls)
if [ "$rc1" = "0" ] && [ "$c1" = "1" ] && [ "$rc2" = "0" ] && [ "$c2" = "1" ]; then
    ok "job not in the map: runs every tick, same as before this feature existed"
else
    bad "unmapped job: run1(rc=$rc1 calls=$c1) run2(rc=$rc2 calls=$c2) — want 1 then 1 (never skip)"
fi

# ── M4 innocence: missing map file entirely -> no-op, agent still runs ───────
rc1=$(run_agent_job no-map-job "$SANDBOX/claude" "$SANDBOX/does-not-exist.json")
c1=$(calls)
if [ "$rc1" = "0" ] && [ "$c1" = "1" ]; then
    ok "missing map file: fails open, agent runs"
else
    bad "missing map file: rc=$rc1 calls=$c1 — want the agent to run"
fi

# ── M5 innocence: malformed JSON map -> jq fails, treated as no fingerprint ──
MAP5="$SANDBOX/map5.json"
printf '{not valid json,,,' > "$MAP5"
rc1=$(run_agent_job broken-map-job "$SANDBOX/claude" "$MAP5")
c1=$(calls)
if [ "$rc1" = "0" ] && [ "$c1" = "1" ]; then
    ok "malformed JSON map: fails open, agent runs (never blocked by a bad map)"
else
    bad "malformed map: rc=$rc1 calls=$c1 — want the agent to run"
fi

# ── M6 innocence: map-sourced fingerprint command that itself FAILS -> fail-open ──
MAP6="$SANDBOX/map6.json"
cat > "$MAP6" <<JSON
{"failopen-job": "exit 3"}
JSON
rc1=$(run_agent_job failopen-job "$SANDBOX/claude" "$MAP6")
c1=$(calls)
if [ "$rc1" = "0" ] && [ "$c1" = "1" ]; then
    ok "map fingerprint command fails (exit 3): fail-open, agent still runs"
else
    bad "map fail-open: rc=$rc1 calls=$c1 — want the agent to run"
fi

# ── M7 the sharp one: a FAILED claude run must NOT store the map-sourced
#        fingerprint, so the next tick still does the work it never did ────
MAP7="$SANDBOX/map7.json"
cat > "$MAP7" <<JSON
{"failstore-job": "echo SAME"}
JSON
rc1=$(run_agent_job failstore-job "$SANDBOX/claude_fail" "$MAP7")
rc2=$(run_agent_job failstore-job "$SANDBOX/claude" "$MAP7")
c2=$(calls)
if [ "$c2" = "1" ]; then
    ok "failed run stores no map-sourced fingerprint: next tick re-runs the work"
else
    bad "failed-run fingerprint (map source): 2nd tick calls=$c2 (rc1=$rc1 rc2=$rc2) — want 1 (must NOT skip)"
fi

# ── M8 guilt: a CHANGED map-sourced fingerprint must still run ───────────────
MAP8_A="$SANDBOX/map8a.json"; cat > "$MAP8_A" <<JSON
{"changed-job": "echo V1"}
JSON
MAP8_B="$SANDBOX/map8b.json"; cat > "$MAP8_B" <<JSON
{"changed-job": "echo V2"}
JSON
rc1=$(run_agent_job changed-job "$SANDBOX/claude" "$MAP8_A")
rc2=$(run_agent_job changed-job "$SANDBOX/claude" "$MAP8_B")
c2=$(calls)
if [ "$rc2" = "0" ] && [ "$c2" = "1" ]; then
    ok "map fingerprint value changed: agent runs again"
else
    bad "changed map fingerprint: rc2=$rc2 calls=$c2 — want the agent to run"
fi

echo
[ "$FAILED" -eq 0 ] && { echo "PASS — cron-agent fingerprint map (P2 no-op suppression, repo-sourced)"; exit 0; } || { echo "FAIL"; exit 1; }
