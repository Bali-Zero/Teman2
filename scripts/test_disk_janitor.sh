#!/usr/bin/env bash
# Tripwire test for disk_janitor.sh (guilt + innocence).
# Self-contained: builds a synthetic HOME + scratch root in a temp dir, exercises dry-run /
# apply / idempotence / live-session guard / kill-switch / protected-tree refusal per root /
# scratch naming / missing registry / symlinks / odd names / the launchd wrapper, asserts
# exactly what is pruned and what is preserved. External tools and the qdrant delegate are
# disabled (DISK_JANITOR_TOOLS=false, DISK_JANITOR_QDRANT_RETENTION=""): they are other
# scripts' contracts. Targets /bin/bash 3.2. Run: bash scripts/test_disk_janitor.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/disk_janitor.sh"
WRAP="$HERE/../infra/launchagents/wrappers/pro-disk-janitor.sh"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/djfix.XXXXXX")"
H="$ROOT/home"; T="$ROOT/claude-501"; FAKEBIN="$ROOT/bin"
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }
have(){ [ -e "$1" ] || [ -L "$1" ]; }
cleanup(){ find "$ROOT" -mindepth 1 -delete 2>/dev/null || true; rmdir "$ROOT" 2>/dev/null || true; rm -f /tmp/nuzantara-pro-disk_janitor.pid; }
trap cleanup EXIT
old(){ touch -h -t "$(date -v-"$2"d +%Y%m%d%H%M 2>/dev/null || date -d "$2 days ago" +%Y%m%d%H%M)" "$1"; }
mk(){ mkdir -p "$(dirname "$1")"; echo x > "$1"; }
U_DEAD=aaaaaaaa-0000-4000-8000-000000000001; U_LIVE=bbbbbbbb-0000-4000-8000-000000000002; U_NEW=cccccccc-0000-4000-8000-000000000003
DECOYS="Desktop/OSINT-Nexus/x.jsonl wa-mirror-media/x.jsonl backups/fly-postgres/x.gz nuzantara-deploy/Nuzantara-PII-Quarantine/x .nuzantara-pilots/local-ci/x nuzantara/.worktrees/w/x .ollama/models/x .colima/default/x .cache/huggingface/hub/x .claude/backups/memory_20260101.db .claude/projects/p/x.jsonl"

build(){
  find "$ROOT" -mindepth 1 -delete 2>/dev/null || true
  mkdir -p "$H/.claude/sessions" "$H/logs"
  # scratch: old-dead (prune) · old-live (keep: uuid registered) · fresh (keep) · non-project parent · non-uuid child
  mk "$T/-proj/$U_DEAD/scratchpad/x";  old "$T/-proj/$U_DEAD" 10
  mk "$T/-proj/$U_LIVE/scratchpad/x";  old "$T/-proj/$U_LIVE" 10
  echo "{\"pid\":1,\"sessionId\":\"$U_LIVE\"}" > "$H/.claude/sessions/1.json"
  mk "$T/-proj/$U_NEW/scratchpad/x";   old "$T/-proj/$U_NEW" 1
  mk "$T/scratch_lab/__pycache__/x";   old "$T/scratch_lab/__pycache__" 30
  mk "$T/-proj/bash-edit-diff/x";      old "$T/-proj/bash-edit-diff" 30
  # codex: old (prune) · fresh (keep) · old non-jsonl (keep) · fresh empty dir (keep)
  mk "$H/.codex/sessions/2026/old.jsonl";    old "$H/.codex/sessions/2026/old.jsonl" 20
  mk "$H/.codex/sessions/2026/new.jsonl";    old "$H/.codex/sessions/2026/new.jsonl" 1
  mk "$H/.codex/sessions/notes.txt";         old "$H/.codex/sessions/notes.txt" 99
  mk "$H/.codex/archived_sessions/2025/a.jsonl"; old "$H/.codex/archived_sessions/2025/a.jsonl" 30
  mkdir -p "$H/.codex/sessions/2026/09/30"
  # log archive: old gz (prune) · fresh gz (keep) · old non-gz (keep)
  mk "$H/logs/archive/old.log.gz";           old "$H/logs/archive/old.log.gz" 90
  mk "$H/logs/archive/new.log.gz";           old "$H/logs/archive/new.log.gz" 5
  mk "$H/logs/archive/keep.txt";             old "$H/logs/archive/keep.txt" 99
  # decoys under every protected tree — ancient, must NEVER be touched
  for p in $DECOYS; do mk "$H/$p"; old "$H/$p" 400; done
}
run(){ # $@ extra args → stdout+stderr
  DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="${DISK_JANITOR_TMP_ROOT:-$T}" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" \
  DISK_JANITOR_SESSIONS_DIR="${DISK_JANITOR_SESSIONS_DIR:-$H/.claude/sessions}" \
  DISK_JANITOR_LOG="$ROOT/j.log" DISK_JANITOR_JOURNAL="$ROOT/j.jsonl" bash "$SCRIPT" "$@" 2>&1
}
decoys_intact(){ for p in $DECOYS; do have "$H/$p" || return 1; done; }
fake_host(){ mkdir -p "$FAKEBIN"; printf '#!/bin/sh\necho %s\n' "$1" > "$FAKEBIN/hostname"; chmod +x "$FAKEBIN/hostname"; }

echo "═══ TEST 1: DRY-RUN removes nothing, names the right candidates ═══"
build
OUT=$(run); RC=$?
[ $RC -eq 0 ] && ok "dry-run exit 0" || no "dry-run exit $RC"
have "$T/-proj/$U_DEAD" && have "$H/.codex/sessions/2026/old.jsonl" && have "$H/logs/archive/old.log.gz" \
  && ok "dry-run left every candidate on disk" || no "dry-run deleted something"
echo "$OUT" | grep -q "scratch: would remove -proj/$U_DEAD" && ok "names the dead scratch dir" || no "dead scratch dir not named"
echo "$OUT" | grep -q "scratch: keep -proj/$U_LIVE (session live)" && ok "live-session guard reported" || no "live-session guard missing"
echo "$OUT" | grep -q "scratch: keep scratch_lab/__pycache__ (not a project dir)" && ok "non-project parent kept (O2)" || no "non-project parent not reported"
echo "$OUT" | grep -q "scratch: keep -proj/bash-edit-diff (not a session uuid)" && ok "non-uuid child kept (O2)" || no "non-uuid child not reported"
echo "$OUT" | grep -q "codex: would remove .codex/sessions/2026/[0-9a-f]\{12\}.jsonl" && ok "names the old codex transcript by hash, not by name (O7)" || no "old codex transcript not named/hashed"
echo "$OUT" | grep -q "old.jsonl" && no "codex basename leaked into the log" || ok "codex basename never logged"
echo "$OUT" | grep -q "logarch: would remove logs/archive/old.log.gz" && ok "names the old log archive" || no "old log archive not named"
echo "$OUT" | grep -q "$U_NEW\|new.jsonl\|new.log.gz\|notes.txt\|keep.txt" && no "a keeper was named as candidate" || ok "no keeper named"
grep -q '"mode":"DRY-RUN"' "$ROOT/j.jsonl" && ok "journal line written (DRY-RUN)" || no "journal line missing"

echo "═══ TEST 2: APPLY prunes exactly the candidates, keeps keepers and decoys ═══"
build
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ok "apply exit 0" || no "apply exit $RC"
! have "$T/-proj/$U_DEAD" && ok "dead scratch dir removed" || no "dead scratch dir survived"
have "$T/-proj/$U_LIVE" && have "$T/-proj/$U_NEW" && have "$T/scratch_lab/__pycache__" && have "$T/-proj/bash-edit-diff" \
  && ok "live, fresh, non-project and non-uuid scratch dirs kept" || no "a scratch keeper was removed"
! have "$H/.codex/sessions/2026/old.jsonl" && ! have "$H/.codex/archived_sessions/2025/a.jsonl" \
  && ok "old codex transcripts removed" || no "old codex transcript survived"
have "$H/.codex/sessions/2026/new.jsonl" && have "$H/.codex/sessions/notes.txt" && ok "fresh/non-jsonl codex files kept" || no "codex keeper removed"
have "$H/.codex/archived_sessions/2025" && ok "just-emptied codex subdir kept this run (its mtime is now; the -mtime +1 sweep takes it later, O6)" || no "just-emptied codex subdir removed in the same run"
have "$H/.codex/sessions/2026/09/30" && ok "fresh empty codex dir kept (O6)" || no "fresh empty codex dir removed"
! have "$H/logs/archive/old.log.gz" && ok "old log archive removed" || no "old log archive survived"
have "$H/logs/archive/new.log.gz" && have "$H/logs/archive/keep.txt" && ok "fresh/non-gz archive kept" || no "archive keeper removed"
decoys_intact && ok "all 11 protected-tree decoys intact" || no "a protected-tree decoy was touched"
grep -q '"mode":"APPLY".*"scratch":1,"codex":2,"logarch":1.*"errors":0' "$ROOT/j.jsonl" && ok "journal counts scratch=1 codex=2 logarch=1 errors=0" || no "journal counts wrong: $(tail -1 "$ROOT/j.jsonl")"

echo "═══ TEST 3: second APPLY is a no-op (idempotent) ═══"
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ok "re-apply exit 0" || no "re-apply exit $RC"
echo "$OUT" | grep -q "removed" && no "re-apply removed something" || ok "re-apply removed nothing"
decoys_intact && ok "decoys still intact" || no "decoy touched on re-apply"

echo "═══ TEST 4: kill switch ═══"
build
OUT=$(DISK_JANITOR_ENABLED=false run --apply); RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q DISABLED && ok "kill switch exits 0 with DISABLED" || no "kill switch not honoured"
have "$T/-proj/$U_DEAD" && ok "kill switch removed nothing" || no "kill switch deleted a candidate"

echo "═══ TEST 5: a protected target is skipped as an ERROR and the run continues; a protected NAME is not a root (O1) ═══"
build
PT="$H/.nuzantara-pilots/claude-501"   # a scratch root misconfigured INTO a protected tree
mk "$PT/-proj/$U_DEAD/x"; old "$PT/-proj/$U_DEAD" 30
OUT=$(DISK_JANITOR_TMP_ROOT="$PT" run --apply); RC=$?
[ $RC -eq 1 ] && have "$PT/-proj/$U_DEAD" && echo "$OUT" | grep -q "scratch: REFUSE -proj/$U_DEAD (protected tree) — skipped" \
  && ok "target under a protected root: refused, kept, rc=1, no abort" || no "protected target handling wrong rc=$RC"
! have "$H/.codex/sessions/2026/old.jsonl" && ! have "$H/logs/archive/old.log.gz" \
  && ok "later steps still pruned their candidates (no starvation)" || no "a later step was starved"
grep -q '"mode":"APPLY".*"errors":1' "$ROOT/j.jsonl" && ok "journal written with errors=1" || no "journal missing/wrong after error: $(tail -1 "$ROOT/j.jsonl")"
build
mk "$T/-Users-x-Desktop-OSINT-Nexus/$U_DEAD/x"; old "$T/-Users-x-Desktop-OSINT-Nexus/$U_DEAD" 30
mk "$H/.codex/sessions/link/real.jsonl"; rm -f "$H/.codex/sessions/link/real.jsonl"
ln -s "$H/Desktop/OSINT-Nexus/x.jsonl" "$H/.codex/sessions/link/real.jsonl"; old "$H/.codex/sessions/link/real.jsonl" 30
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ! have "$T/-Users-x-Desktop-OSINT-Nexus/$U_DEAD" \
  && ok "a scratch dir whose PROJECT name merely contains a protected name is ordinary scratch: removed, rc=0" || no "project-name substring treated as protected (O1 regression) rc=$RC"
have "$H/Desktop/OSINT-Nexus/x.jsonl" && have "$H/.codex/sessions/link/real.jsonl" \
  && ok "symlinked codex jsonl into a protected tree: not a candidate, target intact" || no "symlink or its target removed"

echo "═══ TEST 5b: --check-path refuses every protected root and the PII component, accepts siblings ═══"
n_ok=0; n_bad=0
for r in Desktop/OSINT-Nexus wa-mirror-media backups/fly-postgres .nuzantara-pilots nuzantara/.worktrees .ollama .colima .cache/huggingface .claude/backups .claude/projects; do
  run --check-path "$H/$r/deep/x" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    not refused: $r"; }
  run --check-path "$H/$r" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    root not refused: $r"; }
done
run --check-path "$H/any/where/Nuzantara-PII-Quarantine/x" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || n_bad=$((n_bad+1))
[ $n_bad -eq 0 ] && ok "$n_ok protected paths refused (10 roots x2 + PII component)" || no "$n_bad protected paths NOT refused"
n_bad=0
for r in Desktop/OSINT-Nexus-2 wa-mirror-media-old backups/fly-postgres-x .cache/uv logs/archive .codex/sessions; do
  run --check-path "$H/$r/x" >/dev/null 2>&1; [ $? -eq 0 ] || { n_bad=$((n_bad+1)); echo "    wrongly refused: $r"; }
done
[ $n_bad -eq 0 ] && ok "sibling names (prefix collisions) are NOT refused" || no "$n_bad sibling paths wrongly refused"
mkdir -p "$ROOT/real/.ollama"; ln -s "$ROOT/real" "$H/link"; run --check-path "$H/link/.ollama/x" >/dev/null 2>&1; RC=$?
run --check-path "$ROOT/real/.ollama/x" >/dev/null 2>&1; RC2=$?
[ $RC -eq 0 ] && [ $RC2 -eq 0 ] && ok "a protected NAME outside \$HOME is not a protected root (roots are exact, not names)" || no "name-based refusal leaked (rc=$RC/$RC2)"

echo "═══ TEST 6: fail-closed guards — missing session registry, bad TMP_ROOT, odd names (O3/O4/O5) ═══"
build
OUT=$(DISK_JANITOR_SESSIONS_DIR="$H/nope" run --apply); RC=$?
[ $RC -eq 1 ] && have "$T/-proj/$U_DEAD" && echo "$OUT" | grep -q "registry .* absent or empty" && ok "absent registry: scratch step skipped as ERROR, nothing deleted (O4)" || no "absent registry handling wrong rc=$RC"
build; rm -f "$H/.claude/sessions/1.json"
OUT=$(run --apply); RC=$?
have "$T/-proj/$U_DEAD" && ok "empty registry: nothing deleted (O4)" || no "empty registry deleted scratch"
build
OUT=$(DISK_JANITOR_TMP_ROOT="$ROOT/users" run --apply); RC=$?
[ $RC -eq 2 ] && echo "$OUT" | grep -q "REFUSE: DISK_JANITOR_TMP_ROOT" && ok "TMP_ROOT not shaped claude-<uid>: refused rc=2 (O3)" || no "bad TMP_ROOT accepted rc=$RC"
ln -s "$T" "$ROOT/claude-777"
OUT=$(DISK_JANITOR_TMP_ROOT="$ROOT/claude-777" run --apply); RC=$?
[ $RC -eq 2 ] && have "$T/-proj/$U_DEAD" && ok "symlinked TMP_ROOT refused, nothing deleted (O3)" || no "symlinked TMP_ROOT accepted rc=$RC"
build
NL="$T/-proj/dddddddd-0000-4000-8000-00000000000
4"; mkdir -p "$NL"; old "$NL" 30   # a uuid-looking name broken by a newline: not a uuid → kept
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && have "$NL" && ok "newline in a name: kept, run exit 0" || no "newline name: rc=$RC present=$(have "$NL" && echo y || echo n)"
mk "$H/logs/archive/we ird [x].log.gz"; old "$H/logs/archive/we ird [x].log.gz" 90
OUT=$(run --apply); ! have "$H/logs/archive/we ird [x].log.gz" && echo "$OUT" | grep -q 'removed logs/archive/we ird \[x\].log.gz' && ok "spaces/brackets in a name: removed and logged once" || no "odd archive name mishandled"

echo "═══ TEST 6b: an old codex transcript held open by a process is kept (lsof guard) ═══"
if command -v lsof >/dev/null 2>&1; then
  build
  exec 3< "$H/.codex/sessions/2026/old.jsonl"
  OUT=$(run --apply); RC=$?
  exec 3<&-
  [ $RC -eq 0 ] && have "$H/.codex/sessions/2026/old.jsonl" && echo "$OUT" | grep -q "codex: keep .* (open)" \
    && ok "open transcript kept and reported" || no "open transcript handling wrong rc=$RC present=$(have "$H/.codex/sessions/2026/old.jsonl" && echo y || echo n)"
else
  echo "  ⏭  lsof absent on this runner — open-file guard not exercised here (fail-open path logs 'lsof absent')"
fi

echo "═══ TEST 7: launchd wrapper — node guard writes a visible heartbeat and never runs the payload ═══"
build; fake_host otherhost
HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PAYLOAD="$SCRIPT" DISK_JANITOR_TMP_ROOT="$T" \
  DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" bash "$WRAP" >/dev/null 2>&1; RC=$?
[ $RC -eq 0 ] && grep -q '"status":"disabled"' "$H/.organism/last_seen/pro.disk_janitor.json" 2>/dev/null \
  && ok "wrong node: exit 0 + sidecar status=disabled" || no "wrong node: rc=$RC sidecar=$(cat "$H/.organism/last_seen/pro.disk_janitor.json" 2>/dev/null)"
have "$T/-proj/$U_DEAD" && ok "wrong node: payload not invoked" || no "wrong node: payload ran"

echo "═══ TEST 8: launchd wrapper on its node — applies once, sidecar ok, log lines written once ═══"
build; fake_host nuzantara
HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PAYLOAD="$SCRIPT" DISK_JANITOR_TMP_ROOT="$T" \
  DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" bash "$WRAP" >/dev/null 2>&1; RC=$?
[ $RC -eq 0 ] && grep -q '"status":"ok"' "$H/.organism/last_seen/pro.disk_janitor.json" 2>/dev/null \
  && ok "own node: exit 0 + sidecar status=ok" || no "own node: rc=$RC sidecar=$(cat "$H/.organism/last_seen/pro.disk_janitor.json" 2>/dev/null)"
! have "$T/-proj/$U_DEAD" && decoys_intact && ok "own node: payload applied, decoys intact" || no "own node: payload did not apply cleanly"
n=$(grep -c "scratch: removed -proj/$U_DEAD" "$H/logs/pro-disk_janitor/run.log" 2>/dev/null)
[ "${n:-0}" -eq 1 ] && ok "own node: each payload log line appears once in run.log (R6-1)" || no "own node: payload log line count=$n (expected 1)"
build; fake_host nuzantara
HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PAYLOAD="$SCRIPT" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_SESSIONS_DIR="$H/nope" \
  DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" bash "$WRAP" >/dev/null 2>&1
grep -q '"status":"error"' "$H/.organism/last_seen/pro.disk_janitor.json" 2>/dev/null && ok "own node: payload errors surface as sidecar status=error" || no "payload error not visible in sidecar"

echo; echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
