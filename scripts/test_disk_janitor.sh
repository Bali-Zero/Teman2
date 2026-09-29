#!/usr/bin/env bash
# Tripwire test for disk_janitor.sh (guilt + innocence).
# Self-contained: builds a synthetic HOME + scratch root in a temp dir, exercises dry-run /
# apply / idempotence / live-session guard / kill-switch / protected-tree refusal, asserts
# exactly what is pruned and what is preserved. External tools and the qdrant delegate are
# disabled (DISK_JANITOR_TOOLS=false, DISK_JANITOR_QDRANT_RETENTION=""): they are other
# scripts' contracts. Targets /bin/bash 3.2. Run: bash scripts/test_disk_janitor.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/disk_janitor.sh"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/djfix.XXXXXX")"
H="$ROOT/home"; T="$ROOT/tmp-claude"
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }
have(){ [ -e "$1" ]; }
cleanup(){ find "$ROOT" -mindepth 1 -delete 2>/dev/null || true; rmdir "$ROOT" 2>/dev/null || true; }
trap cleanup EXIT
old(){ touch -t "$(date -v-"$2"d +%Y%m%d%H%M 2>/dev/null || date -d "$2 days ago" +%Y%m%d%H%M)" "$1"; }
mk(){ mkdir -p "$(dirname "$1")"; echo x > "$1"; }

build(){
  find "$ROOT" -mindepth 1 -delete 2>/dev/null || true
  mkdir -p "$H/.claude/sessions" "$H/logs"
  # scratch: old-dead (prune) · old-live (keep: uuid registered in a session file) · fresh (keep)
  mk "$T/-proj/aaaa-old-dead/scratchpad/x";  old "$T/-proj/aaaa-old-dead" 10
  mk "$T/-proj/bbbb-old-live/scratchpad/x";  old "$T/-proj/bbbb-old-live" 10
  echo '{"pid":1,"sessionId":"bbbb-old-live"}' > "$H/.claude/sessions/1.json"
  mk "$T/-proj/cccc-fresh/scratchpad/x";     old "$T/-proj/cccc-fresh" 1
  # codex: old (prune) · fresh (keep) · old non-jsonl (keep)
  mk "$H/.codex/sessions/2026/old.jsonl";    old "$H/.codex/sessions/2026/old.jsonl" 20
  mk "$H/.codex/sessions/2026/new.jsonl";    old "$H/.codex/sessions/2026/new.jsonl" 1
  mk "$H/.codex/sessions/notes.txt";         old "$H/.codex/sessions/notes.txt" 99
  mk "$H/.codex/archived_sessions/2025/a.jsonl"; old "$H/.codex/archived_sessions/2025/a.jsonl" 30
  # log archive: old gz (prune) · fresh gz (keep) · old non-gz (keep)
  mk "$H/logs/archive/old.log.gz";           old "$H/logs/archive/old.log.gz" 90
  mk "$H/logs/archive/new.log.gz";           old "$H/logs/archive/new.log.gz" 5
  mk "$H/logs/archive/keep.txt";             old "$H/logs/archive/keep.txt" 99
  # decoys under protected trees — ancient, must NEVER be touched
  for p in "Desktop/OSINT-Nexus/x.jsonl" "wa-mirror-media/x.jsonl" "backups/fly-postgres/x.gz" \
           "nuzantara-deploy/Nuzantara-PII-Quarantine/x" ".nuzantara-pilots/local-ci/x" \
           ".claude/backups/memory_20260101.db" ".cache/huggingface/hub/x" ".ollama/models/x"; do
    mk "$H/$p"; old "$H/$p" 400; done
}
run(){ # $@ extra args → stdout+stderr
  DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="${DISK_JANITOR_TMP_ROOT:-$T}" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" \
  DISK_JANITOR_LOG="$ROOT/j.log" DISK_JANITOR_JOURNAL="$ROOT/j.jsonl" bash "$SCRIPT" "$@" 2>&1
}
decoys_intact(){
  for p in "Desktop/OSINT-Nexus/x.jsonl" "wa-mirror-media/x.jsonl" "backups/fly-postgres/x.gz" \
           "nuzantara-deploy/Nuzantara-PII-Quarantine/x" ".nuzantara-pilots/local-ci/x" \
           ".claude/backups/memory_20260101.db" ".cache/huggingface/hub/x" ".ollama/models/x"; do
    have "$H/$p" || return 1; done
}

echo "═══ TEST 1: DRY-RUN removes nothing, names the right candidates ═══"
build
OUT=$(run); RC=$?
[ $RC -eq 0 ] && ok "dry-run exit 0" || no "dry-run exit $RC"
have "$T/-proj/aaaa-old-dead" && have "$H/.codex/sessions/2026/old.jsonl" && have "$H/logs/archive/old.log.gz" \
  && ok "dry-run left every candidate on disk" || no "dry-run deleted something"
echo "$OUT" | grep -q "scratch: would remove .*aaaa-old-dead" && ok "names the dead scratch dir" || no "dead scratch dir not named"
echo "$OUT" | grep -q "scratch: keep .*bbbb-old-live (session live)" && ok "live-session guard reported" || no "live-session guard missing"
echo "$OUT" | grep -q "codex: would remove .*old.jsonl" && ok "names the old codex transcript" || no "old codex transcript not named"
echo "$OUT" | grep -q "logarch: would remove .*old.log.gz" && ok "names the old log archive" || no "old log archive not named"
echo "$OUT" | grep -q "cccc-fresh\|new.jsonl\|new.log.gz\|notes.txt\|keep.txt" && no "a keeper was named as candidate" || ok "no keeper named"
grep -q '"mode":"DRY-RUN"' "$ROOT/j.jsonl" && ok "journal line written (DRY-RUN)" || no "journal line missing"

echo "═══ TEST 2: APPLY prunes exactly the candidates, keeps keepers and decoys ═══"
build
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ok "apply exit 0" || no "apply exit $RC"
! have "$T/-proj/aaaa-old-dead" && ok "dead scratch dir removed" || no "dead scratch dir survived"
have "$T/-proj/bbbb-old-live" && ok "live scratch dir kept" || no "live scratch dir removed"
have "$T/-proj/cccc-fresh" && ok "fresh scratch dir kept" || no "fresh scratch dir removed"
! have "$H/.codex/sessions/2026/old.jsonl" && ! have "$H/.codex/archived_sessions/2025/a.jsonl" \
  && ok "old codex transcripts removed" || no "old codex transcript survived"
have "$H/.codex/sessions/2026/new.jsonl" && have "$H/.codex/sessions/notes.txt" && ok "fresh/non-jsonl codex files kept" || no "codex keeper removed"
! have "$H/.codex/archived_sessions/2025" && have "$H/.codex/archived_sessions" \
  && ok "emptied codex subdir removed, root kept" || no "emptied codex subdir handling wrong"
! have "$H/logs/archive/old.log.gz" && ok "old log archive removed" || no "old log archive survived"
have "$H/logs/archive/new.log.gz" && have "$H/logs/archive/keep.txt" && ok "fresh/non-gz archive kept" || no "archive keeper removed"
decoys_intact && ok "all 8 protected-tree decoys intact" || no "a protected-tree decoy was touched"
grep -q '"mode":"APPLY".*"scratch":1,"codex":2,"logarch":1' "$ROOT/j.jsonl" && ok "journal counts scratch=1 codex=2 logarch=1" || no "journal counts wrong: $(tail -1 "$ROOT/j.jsonl")"

echo "═══ TEST 3: second APPLY is a no-op (idempotent) ═══"
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ok "re-apply exit 0" || no "re-apply exit $RC"
echo "$OUT" | grep -q "removed" && no "re-apply removed something" || ok "re-apply removed nothing"
decoys_intact && ok "decoys still intact" || no "decoy touched on re-apply"

echo "═══ TEST 4: kill switch ═══"
build
OUT=$(DISK_JANITOR_ENABLED=false run --apply); RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q DISABLED && ok "kill switch exits 0 with DISABLED" || no "kill switch not honoured"
have "$T/-proj/aaaa-old-dead" && ok "kill switch removed nothing" || no "kill switch deleted a candidate"

echo "═══ TEST 5: a target under a protected tree aborts the run (rc=2) ═══"
build
mkdir -p "$ROOT/evil/.nuzantara-pilots/x"; old "$ROOT/evil/.nuzantara-pilots/x" 30
OUT=$(DISK_JANITOR_TMP_ROOT="$ROOT/evil" run --apply); RC=$?
[ $RC -eq 2 ] && echo "$OUT" | grep -q REFUSE && ok "protected target refused, rc=2" || no "protected target not refused (rc=$RC)"
have "$ROOT/evil/.nuzantara-pilots/x" && ok "protected target untouched" || no "protected target removed"

echo; echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
