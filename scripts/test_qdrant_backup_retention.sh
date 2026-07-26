#!/usr/bin/env bash
# Tripwire test for qdrant_backup_retention.sh (guilt + innocence).
# Self-contained: builds a synthetic backups/qdrant-snapshots fixture in a temp
# dir, exercises dry-run / apply / idempotence / scope-guard / kill-switch /
# absent-dir, asserts exactly what is pruned and what is preserved.
# Targets /bin/bash 3.2 (fleet default). Run: bash scripts/test_qdrant_backup_retention.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/qdrant_backup_retention.sh"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/qretfix.XXXXXX")"
FIX="$ROOT/backups/qdrant-snapshots"
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }
have(){ [ -e "$FIX/$1" ]; }
cleanup(){ find "$ROOT" -mindepth 1 -delete 2>/dev/null || true; rmdir "$ROOT" 2>/dev/null || true; }
trap cleanup EXIT

build(){
  find "$ROOT" -mindepth 1 -delete 2>/dev/null || true
  mkdir -p "$FIX"
  # 9 tar.gz, increasing mtime t1..t9 (t9 newest) → keep 7 newest, remove 2 oldest
  i=1; for m in 202601010001 202601020001 202601030001 202601040001 202601050001 202601060001 202601070001 202601080001 202601090001; do
    f="$FIX/qdrant-2026010${i}-000${i}.tar.gz"; echo "dummy$i" > "$f"; touch -t "$m" "$f"; i=$((i+1)); done
  # collection A: 6 snapshots → keep 4 newest, remove 2 oldest
  i=1; for m in 202602010001 202602020001 202602030001 202602040001 202602050001 202602060001; do
    f="$FIX/colA_2026020${i}-000${i}.snapshot"; echo "a$i" > "$f"; touch -t "$m" "$f"; i=$((i+1)); done
  # collection B: 3 snapshots → keep all (under threshold)
  i=1; for m in 202603010001 202603020001 202603030001; do
    f="$FIX/colB_2026030${i}-000${i}.snapshot"; echo "b$i" > "$f"; touch -t "$m" "$f"; i=$((i+1)); done
  # orphan OLD session dir (mtime -30d) → sweep ; orphan RECENT (-2d) → keep
  mkdir -p "$FIX/20260101-0300"; echo x > "$FIX/20260101-0300/legal_hybrid.snapshot"; touch -t "$(date -v-30d +%Y%m%d%H%M 2>/dev/null || date -d '30 days ago' +%Y%m%d%H%M)" "$FIX/20260101-0300"
  mkdir -p "$FIX/20260718-0300"; echo y > "$FIX/20260718-0300/partial.snapshot";     touch -t "$(date -v-2d  +%Y%m%d%H%M 2>/dev/null || date -d '2 days ago'  +%Y%m%d%H%M)" "$FIX/20260718-0300"
  # decoys — must NEVER be touched
  echo readme > "$FIX/README.txt"
  mkdir -p "$FIX/not-a-timestamp"; echo z > "$FIX/not-a-timestamp/keep.me"; touch -t "$(date -v-99d +%Y%m%d%H%M 2>/dev/null || date -d '99 days ago' +%Y%m%d%H%M)" "$FIX/not-a-timestamp"
}

echo "═══ TEST 1: DRY-RUN removes nothing, reports the right candidates ═══"
build
OUT=$(QDRANT_BACKUP_ROOT="$FIX" bash "$SCRIPT" 2>&1); RC=$?
[ $RC -eq 0 ] && ok "dry-run exit 0" || no "dry-run exit $RC"
allpresent=true
for f in qdrant-20260101-0001.tar.gz colA_20260201-0001.snapshot 20260101-0300; do have "$f" || allpresent=false; done
$allpresent && ok "dry-run left ALL files on disk" || no "dry-run deleted something (must not)"
c=$(grep -c "WOULD-REMOVE" <<<"$OUT")
[ "$c" -eq 5 ] && ok "dry-run flagged exactly 5 (2 tar.gz + 2 colA + 1 orphan)" || no "dry-run flagged $c (expected 5)"

echo "═══ TEST 2: APPLY removes exactly the right set, keeps the rest ═══"
build
OUT=$(QDRANT_BACKUP_ROOT="$FIX" bash "$SCRIPT" --apply 2>&1); RC=$?
[ $RC -eq 0 ] && ok "apply exit 0" || no "apply exit $RC"
gone=true
for f in qdrant-20260101-0001.tar.gz qdrant-20260102-0002.tar.gz colA_20260201-0001.snapshot colA_20260202-0002.snapshot 20260101-0300; do have "$f" && gone=false; done
$gone && ok "removed the 5 expected (2 oldest tar.gz, 2 oldest colA, OLD orphan)" || no "some expected-removed still present"
kept=true
for f in qdrant-20260103-0003.tar.gz qdrant-20260109-0009.tar.gz colA_20260203-0003.snapshot colA_20260206-0006.snapshot colB_20260301-0001.snapshot colB_20260303-0003.snapshot 20260718-0300 20260718-0300/partial.snapshot README.txt not-a-timestamp not-a-timestamp/keep.me; do
  have "$f" || { kept=false; echo "    MISSING (should keep): $f"; }; done
$kept && ok "KEPT 7 tar.gz + 4 colA + 3 colB + recent-orphan + decoys" || no "deleted something it should keep"
n=$(find "$FIX" -maxdepth 1 -name 'qdrant-*.tar.gz' | wc -l | tr -d ' '); [ "$n" -eq 7 ] && ok "tar.gz count == 7" || no "tar.gz == $n (want 7)"
n=$(find "$FIX" -maxdepth 1 -name 'colA_*.snapshot' | wc -l | tr -d ' '); [ "$n" -eq 4 ] && ok "colA count == 4" || no "colA == $n (want 4)"

echo "═══ TEST 3: idempotent — 2nd apply is a NO-OP ═══"
OUT=$(QDRANT_BACKUP_ROOT="$FIX" bash "$SCRIPT" --apply 2>&1); RC=$?
c=$(grep -c "REMOVED" <<<"$OUT" || true)
[ $RC -eq 0 ] && [ "$c" -eq 0 ] && ok "2nd apply removed 0 (idempotent)" || no "2nd apply removed $c (rc=$RC)"

echo "═══ TEST 4: scope guard refuses a non-qdrant / \$HOME root ═══"
OUT=$(QDRANT_BACKUP_ROOT="/tmp/evil" bash "$SCRIPT" --apply 2>&1); RC=$?
[ $RC -eq 2 ] && ok "refused bad root (exit 2)" || no "bad root exit $RC (want 2)"
OUT=$(QDRANT_BACKUP_ROOT="$HOME" bash "$SCRIPT" --apply 2>&1); RC=$?
[ $RC -eq 2 ] && ok "refused \$HOME (exit 2)" || no "\$HOME exit $RC (want 2)"

echo "═══ TEST 5: kill switch ═══"
build
OUT=$(QDRANT_RETENTION_ENABLED=false QDRANT_BACKUP_ROOT="$FIX" bash "$SCRIPT" --apply 2>&1); RC=$?
c=$(find "$FIX" -maxdepth 1 -name 'qdrant-*.tar.gz' | wc -l | tr -d ' ')
[ $RC -eq 0 ] && [ "$c" -eq 9 ] && ok "kill switch = no-op (9 tar.gz untouched)" || no "kill switch acted (rc=$RC, tar.gz=$c)"

echo "═══ TEST 6: absent dir is a clean no-op ═══"
OUT=$(QDRANT_BACKUP_ROOT="/tmp/nope/backups/qdrant-snapshots" bash "$SCRIPT" --apply 2>&1); RC=$?
{ [ $RC -eq 0 ] && grep -q "root absent" <<<"$OUT"; } && ok "absent dir exit 0 'root absent'" || no "absent dir rc=$RC"

echo "═══ TEST 7: skips (exit 0, no prune) while a producer is running ═══"
build
# 2-command script body so `sh -c` does NOT exec-optimise the sentinel out of argv
/bin/sh -c ": SENTINEL_qretprod_$$ ; sleep 60" &
FAKE=$!
sleep 1
OUT=$(QDRANT_PRODUCER_PROC_RE="SENTINEL_qretprod_$$" QDRANT_BACKUP_ROOT="$FIX" bash "$SCRIPT" --apply 2>&1); RC=$?
kill "$FAKE" 2>/dev/null || true; wait "$FAKE" 2>/dev/null || true
n=$(find "$FIX" -maxdepth 1 -name 'qdrant-*.tar.gz' | wc -l | tr -d ' ')
{ [ $RC -eq 0 ] && grep -q "SKIP:" <<<"$OUT" && [ "$n" -eq 9 ]; } && ok "producer running → SKIP exit 0, 9 tar.gz + orphan untouched" || no "producer-skip failed (rc=$RC, tar.gz=$n)"
# and with NO producer running, the same sentinel pattern → normal prune resumes
OUT=$(QDRANT_PRODUCER_PROC_RE="SENTINEL_qretprod_nomatch_$$" QDRANT_BACKUP_ROOT="$FIX" bash "$SCRIPT" --apply 2>&1); RC=$?
n=$(find "$FIX" -maxdepth 1 -name 'qdrant-*.tar.gz' | wc -l | tr -d ' ')
{ [ $RC -eq 0 ] && [ "$n" -eq 7 ]; } && ok "no producer → prune resumes (tar.gz 9→7)" || no "resume failed (rc=$RC, tar.gz=$n)"

echo ""
echo "═══════════ RESULT: $PASS passed, $FAIL failed ═══════════"
[ $FAIL -eq 0 ]
