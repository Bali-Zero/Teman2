#!/usr/bin/env bash
# Tripwire test for disk_janitor.sh (guilt + innocence).
# Self-contained: builds a synthetic HOME + scratch root in a temp dir, exercises dry-run /
# apply / idempotence / live-session guard / kill-switch / protected-set refusal (roots,
# ancestors, PII component, siblings) / scratch naming / missing registry / TMP_ROOT shape /
# open-file probe / symlinks / odd names / output boundary / the launchd wrapper, asserts
# exactly what is pruned and what is preserved. External tools and the qdrant delegate are
# disabled (DISK_JANITOR_TOOLS=false, DISK_JANITOR_QDRANT_RETENTION=""): they are other
# scripts' contracts. Targets /bin/bash 3.2. Run: bash scripts/test_disk_janitor.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/disk_janitor.sh"
WRAP="$HERE/../infra/launchagents/wrappers/pro-disk-janitor.sh"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/djfix.XXXXXX")" || { echo "mktemp failed"; exit 70; }
ROOT="$(cd "$ROOT" && pwd -P)"   # physical: macOS /var -> /private/var, and the payload refuses a symlinked TMP_ROOT chain
H="$ROOT/home"; T="$ROOT/claude-501"; FAKEBIN="$ROOT/bin"; PIDF="$ROOT/wrapper.pid"
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
no(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }
have(){ [ -e "$1" ] || [ -L "$1" ]; }
cleanup(){ find "$ROOT" -mindepth 1 -delete 2>/dev/null || true; rmdir "$ROOT" 2>/dev/null || true; }
trap cleanup EXIT
old(){ touch -h -t "$(date -v-"$2"d +%Y%m%d%H%M 2>/dev/null || date -d "$2 days ago" +%Y%m%d%H%M)" "$1"; }
mk(){ mkdir -p "$(dirname "$1")"; echo x > "$1"; }
U_DEAD=aaaaaaaa-0000-4000-8000-000000000001; U_LIVE=bbbbbbbb-0000-4000-8000-000000000002; U_NEW=cccccccc-0000-4000-8000-000000000003
MARK=ZZSENSITIVEZZ   # synthetic PII marker planted in candidate names: must never reach a log line
DECOYS="Desktop/OSINT-Nexus/x.jsonl wa-mirror-media/x.jsonl backups/fly-postgres/x.gz nuzantara-deploy/Nuzantara-PII-Quarantine/x .nuzantara-pilots/local-ci/x nuzantara/.worktrees/w/x .ollama/models/x .colima/default/x .cache/huggingface/hub/x .claude/backups/memory_20260101.db .claude/projects/p/x.jsonl"

build(){
  find "$ROOT" -mindepth 1 -delete 2>/dev/null || true
  mkdir -p "$H/.claude/sessions" "$H/logs"
  # scratch: old-dead (prune) · old-live (keep: uuid registered) · fresh (keep) · non-project parent · non-uuid child
  mk "$T/-Users-x-clients-$MARK/$U_DEAD/scratchpad/x"; old "$T/-Users-x-clients-$MARK/$U_DEAD" 10
  mk "$T/-proj/$U_LIVE/scratchpad/x";  old "$T/-proj/$U_LIVE" 10
  echo "{\"pid\":1,\"sessionId\":\"$U_LIVE\"}" > "$H/.claude/sessions/1.json"
  mk "$T/-proj/$U_NEW/scratchpad/x";   old "$T/-proj/$U_NEW" 1
  mk "$T/scratch_lab/__pycache__/x";   old "$T/scratch_lab/__pycache__" 30
  mk "$T/-proj/bash-edit-diff/x";      old "$T/-proj/bash-edit-diff" 30
  # codex: old (prune) · fresh (keep) · old non-jsonl (keep) · fresh empty dir (keep)
  mk "$H/.codex/sessions/2026/old-$MARK.jsonl"; old "$H/.codex/sessions/2026/old-$MARK.jsonl" 20
  mk "$H/.codex/sessions/2026/new.jsonl";    old "$H/.codex/sessions/2026/new.jsonl" 1
  mk "$H/.codex/sessions/notes.txt";         old "$H/.codex/sessions/notes.txt" 99
  mk "$H/.codex/archived_sessions/2025/a.jsonl"; old "$H/.codex/archived_sessions/2025/a.jsonl" 30
  mkdir -p "$H/.codex/sessions/2026/09/30"
  # log archive: old gz (prune) · fresh gz (keep) · old non-gz (keep)
  mk "$H/logs/archive/old-$MARK.log.gz";     old "$H/logs/archive/old-$MARK.log.gz" 90
  mk "$H/logs/archive/new.log.gz";           old "$H/logs/archive/new.log.gz" 5
  mk "$H/logs/archive/keep.txt";             old "$H/logs/archive/keep.txt" 99
  # decoys under every protected tree — ancient, must NEVER be touched
  for p in $DECOYS; do mk "$H/$p"; old "$H/$p" 400; done
}
OLD_SCRATCH="$T/-Users-x-clients-$MARK/$U_DEAD"; OLD_CODEX="$H/.codex/sessions/2026/old-$MARK.jsonl"; OLD_GZ="$H/logs/archive/old-$MARK.log.gz"
run(){ # $@ extra args → stdout+stderr
  DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="${DISK_JANITOR_TMP_ROOT:-$T}" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="${DISK_JANITOR_QDRANT_RETENTION-}" \
  DISK_JANITOR_SESSIONS_DIR="${DISK_JANITOR_SESSIONS_DIR:-$H/.claude/sessions}" DISK_JANITOR_LSOF="${DISK_JANITOR_LSOF:-lsof}" \
  DISK_JANITOR_LOG="$ROOT/j.log" DISK_JANITOR_JOURNAL="$ROOT/j.jsonl" bash "$SCRIPT" "$@" 2>&1
}
wrap(){ # wrapper with a fake node name from $FAKEBIN, everything else from the fixture
  HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PAYLOAD="$SCRIPT" PRO_DISK_JANITOR_PIDFILE="$PIDF" DISK_JANITOR_TMP_ROOT="$T" \
  DISK_JANITOR_SESSIONS_DIR="${DISK_JANITOR_SESSIONS_DIR:-$H/.claude/sessions}" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" bash "$WRAP" >/dev/null 2>&1
}
decoys_intact(){ for p in $DECOYS; do have "$H/$p" || return 1; done; }
fake_host(){ mkdir -p "$FAKEBIN"; printf '#!/bin/sh\necho %s\n' "$1" > "$FAKEBIN/hostname"; chmod +x "$FAKEBIN/hostname"; }
sidecar(){ cat "$H/.organism/last_seen/pro.disk_janitor.json" 2>/dev/null; }

echo "═══ TEST 1: DRY-RUN removes nothing, names the right candidates, never a name (O7/R4) ═══"
build
OUT=$(run); RC=$?
[ $RC -eq 0 ] && ok "dry-run exit 0" || no "dry-run exit $RC"
have "$OLD_SCRATCH" && have "$OLD_CODEX" && have "$OLD_GZ" && ok "dry-run left every candidate on disk" || no "dry-run deleted something"
echo "$OUT" | grep -q "scratch: would remove $U_DEAD" && ok "names the dead scratch dir by uuid only" || no "dead scratch dir not named"
echo "$OUT" | grep -q "scratch: keep $U_LIVE (session live)" && ok "live-session guard reported" || no "live-session guard missing"
[ "$(echo "$OUT" | grep -c "scratch: keep [0-9a-f]\{12\} (not a project dir)\|scratch: keep [0-9a-f]\{12\} (not a session uuid)")" -eq 2 ] && ok "non-project parent and non-uuid child kept, logged by hash (O2)" || no "scratch naming guard not reported"
echo "$OUT" | grep -q "codex: would remove [0-9a-f]\{12\} (" && ok "names the old codex transcript by hash" || no "old codex transcript not named/hashed"
echo "$OUT" | grep -q "logarch: would remove [0-9a-f]\{12\} (" && ok "names the old log archive by hash" || no "old log archive not named/hashed"
echo "$OUT" | grep -q "$MARK\|old-\|\.jsonl\|\.gz\|clients" && no "a candidate NAME leaked into the log (R4)" || ok "no candidate name or PII marker in any log line (R4)"
echo "$OUT" | grep -q "$U_NEW\|new.jsonl\|notes.txt\|keep.txt" && no "a keeper was named as candidate" || ok "no keeper named"
grep -q '"mode":"DRY-RUN"' "$ROOT/j.jsonl" && ! grep -q "$MARK" "$ROOT/j.jsonl" && ok "journal line written, no marker" || no "journal line missing or leaking"

echo "═══ TEST 2: APPLY prunes exactly the candidates, keeps keepers and decoys ═══"
build
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ok "apply exit 0" || no "apply exit $RC"
! have "$OLD_SCRATCH" && ok "dead scratch dir removed" || no "dead scratch dir survived"
have "$T/-proj/$U_LIVE" && have "$T/-proj/$U_NEW" && have "$T/scratch_lab/__pycache__" && have "$T/-proj/bash-edit-diff" \
  && ok "live, fresh, non-project and non-uuid scratch dirs kept" || no "a scratch keeper was removed"
! have "$OLD_CODEX" && ! have "$H/.codex/archived_sessions/2025/a.jsonl" && ok "old codex transcripts removed" || no "old codex transcript survived"
have "$H/.codex/sessions/2026/new.jsonl" && have "$H/.codex/sessions/notes.txt" && ok "fresh/non-jsonl codex files kept" || no "codex keeper removed"
have "$H/.codex/archived_sessions/2025" && ok "just-emptied codex subdir kept this run (mtime is now; the -mtime +1 sweep takes it later, O6)" || no "just-emptied codex subdir removed in the same run"
have "$H/.codex/sessions/2026/09/30" && ok "fresh empty codex dir kept (O6)" || no "fresh empty codex dir removed"
! have "$OLD_GZ" && ok "old log archive removed" || no "old log archive survived"
have "$H/logs/archive/new.log.gz" && have "$H/logs/archive/keep.txt" && ok "fresh/non-gz archive kept" || no "archive keeper removed"
decoys_intact && ok "all 11 protected-tree decoys intact" || no "a protected-tree decoy was touched"
grep -q '"mode":"APPLY".*"scratch":1,"codex":2,"logarch":1.*"errors":0' "$ROOT/j.jsonl" && ok "journal counts scratch=1 codex=2 logarch=1 errors=0" || no "journal counts wrong: $(tail -1 "$ROOT/j.jsonl")"
grep -q "$MARK" "$ROOT/j.log" && no "PII marker reached the log file (R4)" || ok "log file carries no candidate name (R4)"

echo "═══ TEST 3: second APPLY is a no-op (idempotent) ═══"
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && ok "re-apply exit 0" || no "re-apply exit $RC"
echo "$OUT" | grep -q "removed" && no "re-apply removed something" || ok "re-apply removed nothing"
decoys_intact && ok "decoys still intact" || no "decoy touched on re-apply"

echo "═══ TEST 4: kill switch ═══"
build
OUT=$(DISK_JANITOR_ENABLED=false run --apply); RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q DISABLED && ok "kill switch exits 0 with DISABLED" || no "kill switch not honoured"
have "$OLD_SCRATCH" && ok "kill switch removed nothing" || no "kill switch deleted a candidate"

echo "═══ TEST 5: a protected target is skipped as an ERROR and the run continues; a protected NAME is not a root (O1) ═══"
build
PT="$H/.nuzantara-pilots/claude-501"   # a scratch root misconfigured INTO a protected tree
mk "$PT/-proj/$U_DEAD/x"; old "$PT/-proj/$U_DEAD" 30
OUT=$(DISK_JANITOR_TMP_ROOT="$PT" run --apply); RC=$?
[ $RC -eq 1 ] && have "$PT/-proj/$U_DEAD" && echo "$OUT" | grep -q "scratch: REFUSE $U_DEAD (protected tree) — skipped" \
  && ok "target under a protected root: refused, kept, rc=1, no abort" || no "protected target handling wrong rc=$RC"
! have "$OLD_CODEX" && ! have "$OLD_GZ" && ok "later steps still pruned their candidates (no starvation)" || no "a later step was starved"
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

echo "═══ TEST 5b: --check-path refuses every protected root, its ancestors and the PII component; accepts siblings ═══"
n_ok=0; n_bad=0
for r in Desktop/OSINT-Nexus wa-mirror-media backups/fly-postgres .nuzantara-pilots nuzantara/.worktrees .ollama .colima .cache/huggingface .claude/backups .claude/projects; do
  run --check-path "$H/$r/deep/x" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    not refused: $r/deep/x"; }
  run --check-path "$H/$r" >/dev/null 2>&1;        [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    root not refused: $r"; }
done
for a in Desktop backups .cache .claude nuzantara; do   # ancestors of a protected root (R3)
  run --check-path "$H/$a" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    ancestor not refused: $a"; }
done
for c in "any/where/Nuzantara-PII-Quarantine/x" "clients/PII-Quarantine-2025/y" "x/PII-Quarantine" "x/pii-quarantine/y"; do
  run --check-path "$H/$c" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    PII component not refused: $c"; }
done
for k in "desktop/osint-nexus/x" ".OLLAMA/models" ".Claude/Backups/m.db"; do   # case-folded (APFS is case-insensitive)
  run --check-path "$H/$k" >/dev/null 2>&1; [ $? -eq 3 ] && n_ok=$((n_ok+1)) || { n_bad=$((n_bad+1)); echo "    case variant not refused: $k"; }
done
[ $n_bad -eq 0 ] && ok "$n_ok protected paths refused (10 roots x2, 5 ancestors, 4 PII-component shapes, 3 case variants)" || no "$n_bad protected paths NOT refused"
n_bad=0
for r in Desktop/OSINT-Nexus-2 wa-mirror-media-old backups/fly-postgres-x .cache/uv logs/archive .codex/sessions .claude/sessions; do
  run --check-path "$H/$r/x" >/dev/null 2>&1; [ $? -eq 0 ] || { n_bad=$((n_bad+1)); echo "    wrongly refused: $r"; }
done
[ $n_bad -eq 0 ] && ok "sibling names (prefix collisions) are NOT refused" || no "$n_bad sibling paths wrongly refused"
mkdir -p "$ROOT/real/.ollama"; ln -s "$ROOT/real" "$H/link"
run --check-path "$H/link/.ollama/x" >/dev/null 2>&1; RC=$?; run --check-path "$ROOT/real/.ollama/x" >/dev/null 2>&1; RC2=$?
[ $RC -eq 0 ] && [ $RC2 -eq 0 ] && ok "a protected NAME outside \$HOME is not a protected root (roots are exact, not names)" || no "name-based refusal leaked (rc=$RC/$RC2)"
mkdir -p "$ROOT/elsewhere/models"; rm -rf "$H/.ollama"; ln -s "$ROOT/elsewhere" "$H/.ollama"
run --check-path "$ROOT/elsewhere/models" >/dev/null 2>&1; RC=$?
[ $RC -eq 3 ] && ok "the physical target of a symlinked protected root is refused too" || no "symlinked protected root bypassed via its physical path (rc=$RC)"
OUT=$(DISK_JANITOR_HOME=/nonexistent/dj-home TMPDIR=/nonexistent bash "$SCRIPT" --check-path /nonexistent/dj-home/.ollama/model 2>&1); RC=$?
[ $RC -eq 3 ] && ok "protection needs no temp file: refused even with an unusable TMPDIR/HOME (R1)" || no "protection fell open without a temp file (rc=$RC: $OUT)"

echo "═══ TEST 6: fail-closed guards — registry, TMP_ROOT shape, open-file probe, odd names (O3/O4/O5/R2/R5) ═══"
build
OUT=$(DISK_JANITOR_SESSIONS_DIR="$H/nope" run --apply); RC=$?
[ $RC -eq 1 ] && have "$OLD_SCRATCH" && echo "$OUT" | grep -q "registry absent or empty" && ok "absent registry: scratch step skipped as ERROR, nothing deleted (O4)" || no "absent registry handling wrong rc=$RC"
build; rm -f "$H/.claude/sessions/1.json"
OUT=$(run --apply); have "$OLD_SCRATCH" && ok "empty registry: nothing deleted (O4)" || no "empty registry deleted scratch"
n_bad=0
for bad in "$ROOT/users" "$ROOT/claude-5junk" "$ROOT/claude-5/x" "$ROOT/claude-501/../claude-501" "relative/claude-501" "$ROOT//claude-501"; do
  build; OUT=$(DISK_JANITOR_TMP_ROOT="$bad" run --apply); RC=$?
  { [ $RC -eq 2 ] && echo "$OUT" | grep -q "REFUSE: DISK_JANITOR_TMP_ROOT" && have "$OLD_SCRATCH"; } || { n_bad=$((n_bad+1)); echo "    accepted: $bad (rc=$RC)"; }
done
[ $n_bad -eq 0 ] && ok "malformed TMP_ROOT shapes refused rc=2, nothing deleted (O3/R2)" || no "$n_bad malformed TMP_ROOT accepted"
build; ln -s "$T" "$ROOT/claude-777"
OUT=$(DISK_JANITOR_TMP_ROOT="$ROOT/claude-777" run --apply); RC=$?
[ $RC -eq 2 ] && have "$OLD_SCRATCH" && ok "symlinked TMP_ROOT refused (O3)" || no "symlinked TMP_ROOT accepted rc=$RC"
build; mkdir -p "$ROOT/realroot"; mv "$T" "$ROOT/realroot/claude-501"; ln -s "$ROOT/realroot" "$ROOT/viasym"
OUT=$(DISK_JANITOR_TMP_ROOT="$ROOT/viasym/claude-501" run --apply); RC=$?
[ $RC -eq 2 ] && have "$ROOT/realroot/claude-501/-Users-x-clients-$MARK/$U_DEAD" && ok "TMP_ROOT with a symlinked ancestor refused (R2)" || no "symlinked ancestor accepted rc=$RC"
build
OUT=$(DISK_JANITOR_LSOF=/nonexistent/lsof run --apply); RC=$?
[ $RC -eq 1 ] && have "$OLD_CODEX" && echo "$OUT" | grep -q "open-file probe .* unavailable — step skipped" && ok "no lsof: codex step skipped as ERROR, transcripts kept (R5)" || no "missing lsof handling wrong rc=$RC"
build; mkdir -p "$FAKEBIN"; printf '#!/bin/sh\nexit 2\n' > "$FAKEBIN/lsof-broken"; chmod +x "$FAKEBIN/lsof-broken"   # after build: build wipes $ROOT
OUT=$(DISK_JANITOR_LSOF="$FAKEBIN/lsof-broken" run --apply); RC=$?
[ $RC -eq 1 ] && have "$OLD_CODEX" && echo "$OUT" | grep -q "codex: probe failed rc=2" && ok "failing lsof: transcript kept, ERROR counted (R5)" || no "failing lsof handling wrong rc=$RC"
build
NL="$T/-proj/dddddddd-0000-4000-8000-00000000000
4"; mkdir -p "$NL"; old "$NL" 30   # a uuid-looking name broken by a newline: not a uuid → kept
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && have "$NL" && ok "newline in a name: kept, run exit 0" || no "newline name: rc=$RC present=$(have "$NL" && echo y || echo n)"
mk "$H/logs/archive/we ird [x].log.gz"; old "$H/logs/archive/we ird [x].log.gz" 90
OUT=$(run --apply); ! have "$H/logs/archive/we ird [x].log.gz" && [ "$(echo "$OUT" | grep -c 'logarch: removed')" -eq 1 ] && ok "spaces/brackets in a name: removed and logged once" || no "odd archive name mishandled"

echo "═══ TEST 6c: codex round-2 findings — protected descendant, gated sweep, unreadable registry, nested archive, unwritable journal ═══"
build
mk "$T/-proj/$U_DEAD/Nuzantara-PII-Quarantine/keep"; old "$T/-proj/$U_DEAD" 30   # a scratch dir carrying a PII child (R1)
OUT=$(run --apply); RC=$?
[ $RC -eq 1 ] && have "$T/-proj/$U_DEAD/Nuzantara-PII-Quarantine/keep" && echo "$OUT" | grep -q "scratch: REFUSE $U_DEAD (protected descendant) — skipped" \
  && ok "scratch dir with a PII-Quarantine descendant refused, kept, rc=1 (R1)" || no "protected descendant deleted or not reported rc=$RC"
build
mkdir -p "$H/.codex/sessions/2025/PII-Quarantine"; old "$H/.codex/sessions/2025/PII-Quarantine" 5; old "$H/.codex/sessions/2025" 5   # old EMPTY protected-named dir (R1 sweep)
OUT=$(run --apply); RC=$?
have "$H/.codex/sessions/2025/PII-Quarantine" && echo "$OUT" | grep -q "codex: REFUSE empty dir .* (protected tree) — skipped" \
  && ok "empty-dir sweep goes through the gate: protected-named empty dir kept, ERROR counted (R1)" || no "empty-dir sweep bypassed the gate rc=$RC"
build; chmod 000 "$H/.claude/sessions/1.json"   # registry present but unreadable → grep rc 2 (R2)
OUT=$(run --apply); RC=$?; chmod 644 "$H/.claude/sessions/1.json"
if [ "$(id -u)" -eq 0 ]; then echo "  ⏭  running as root: unreadable-registry case not exercisable"; else
  [ $RC -eq 1 ] && have "$OLD_SCRATCH" && echo "$OUT" | grep -q "scratch: keep $U_DEAD (registry unreadable rc=2)" \
    && ok "unreadable registry: candidate kept, ERROR counted, never 'dead' (R2)" || no "unreadable registry treated as dead rc=$RC"
fi
build; mk "$H/logs/archive/nested/ancient.log.gz"; old "$H/logs/archive/nested/ancient.log.gz" 400   # nested archive (R3)
OUT=$(run --apply); RC=$?
[ $RC -eq 0 ] && have "$H/logs/archive/nested/ancient.log.gz" && ! have "$OLD_GZ" && ok "logarch prunes direct children only: nested ancient .gz survives (R3)" || no "nested archive pruned or run failed rc=$RC"
build; mkdir -p "$ROOT/ro"; chmod 555 "$ROOT/ro"
if [ "$(id -u)" -eq 0 ]; then echo "  ⏭  running as root: unwritable-journal case not exercisable"; else
  OUT=$(DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" DISK_JANITOR_LOG="$ROOT/j.log" DISK_JANITOR_JOURNAL="$ROOT/ro/j.jsonl" bash "$SCRIPT" --apply 2>&1); RC=$?
  [ $RC -eq 2 ] && have "$OLD_SCRATCH" && echo "$OUT" | grep -q "REFUSE: log or receipts journal not writable" && ok "unwritable journal: run refused before any deletion (R4)" || no "unwritable journal not refused rc=$RC"
fi
chmod 755 "$ROOT/ro"
build
NLU="$T/-proj/$U_DEAD
"; mkdir -p "$NLU"; old "$NLU" 30   # uuid + trailing newline: $(basename) would strip it (codex R2 round 3)
OUT=$(run --apply); RC=$?
have "$NLU" && echo "$OUT" | grep -q "scratch: keep [0-9a-f]\{12\} (not a session uuid)" && ok "uuid with a trailing newline is not a uuid: kept (R2)" || no "trailing-newline uuid dir removed or not reported"
FAKEQ="$FAKEBIN/fake-qdrant-retention.sh"   # build() wipes $ROOT, so the fake delegate is re-planted after every build
fakeq(){ mkdir -p "$FAKEBIN"; printf '#!/bin/sh\necho "root=$QDRANT_BACKUP_ROOT" > "%s/qcall"\nexit 0\n' "$ROOT" > "$FAKEQ"; chmod +x "$FAKEQ"; }
build; fakeq; mk "$H/backups/qdrant-snapshots/20250101-0300/Nuzantara-PII-Quarantine/x"; old "$H/backups/qdrant-snapshots/20250101-0300" 400
OUT=$(QDRANT_BACKUP_ROOT="$H/.nuzantara-pilots/backups/qdrant-snapshots" DISK_JANITOR_QDRANT_RETENTION="$FAKEQ" run --apply); RC=$?
[ $RC -eq 1 ] && [ ! -e "$ROOT/qcall" ] && echo "$OUT" | grep -q "qdrant: REFUSE .* (protected tree or descendant) — delegation skipped" \
  && ok "qdrant delegation refused when the backup root carries a PII descendant; inherited QDRANT_BACKUP_ROOT ignored (R1)" || no "qdrant delegation not gated rc=$RC called=$( [ -e "$ROOT/qcall" ] && cat "$ROOT/qcall")"
build; fakeq; mkdir -p "$H/backups/qdrant-snapshots"
OUT=$(QDRANT_BACKUP_ROOT="$H/.nuzantara-pilots/backups/qdrant-snapshots" DISK_JANITOR_QDRANT_RETENTION="$FAKEQ" run --apply); RC=$?
[ $RC -eq 0 ] && grep -q "root=$H/backups/qdrant-snapshots" "$ROOT/qcall" 2>/dev/null && ok "qdrant delegate always receives the pinned root, never the inherited one (R1)" || no "delegate root not pinned: $(cat "$ROOT/qcall" 2>/dev/null) rc=$RC"

echo "═══ TEST 6b: an old codex transcript held open by a process is kept (real lsof) ═══"
if command -v lsof >/dev/null 2>&1; then
  build
  exec 3< "$OLD_CODEX"
  OUT=$(run --apply); RC=$?
  exec 3<&-
  [ $RC -eq 0 ] && have "$OLD_CODEX" && echo "$OUT" | grep -q "codex: keep .* (open)" && ok "open transcript kept and reported" || no "open transcript handling wrong rc=$RC"
else
  no "lsof absent on this runner: the open-file guard cannot be exercised (the payload would skip the codex step as an ERROR here)"
fi

echo "═══ TEST 7: launchd wrapper — node guard writes a visible heartbeat and never runs the payload ═══"
build; fake_host otherhost
wrap; RC=$?
[ $RC -eq 0 ] && sidecar | grep -q '"status":"disabled"' && ok "wrong node: exit 0 + sidecar status=disabled" || no "wrong node: rc=$RC sidecar=$(sidecar)"
have "$OLD_SCRATCH" && ok "wrong node: payload not invoked" || no "wrong node: payload ran"

echo "═══ TEST 8: launchd wrapper on its node — applies once, sidecar ok, log once, errors visible, lock respected ═══"
build; fake_host nuzantara
wrap; RC=$?
[ $RC -eq 0 ] && sidecar | grep -q '"status":"ok"' && ok "own node: exit 0 + sidecar status=ok" || no "own node: rc=$RC sidecar=$(sidecar)"
! have "$OLD_SCRATCH" && decoys_intact && ok "own node: payload applied, decoys intact" || no "own node: payload did not apply cleanly"
n=$(grep -c "scratch: removed $U_DEAD" "$H/logs/pro-disk_janitor/run.log" 2>/dev/null)
[ "${n:-0}" -eq 1 ] && ok "own node: each payload log line appears once in run.log (R6-1)" || no "own node: payload log line count=$n (expected 1)"
[ ! -e "$PIDF" ] && ok "own node: fixture pidfile cleaned by the trap; the live lock path is never used by the test (R7)" || no "fixture pidfile left behind"
build; fake_host nuzantara
DISK_JANITOR_SESSIONS_DIR="$H/nope" wrap
sidecar | grep -q '"status":"error"' && ok "own node: payload errors surface as sidecar status=error" || no "payload error not visible in sidecar"
build; fake_host nuzantara; echo $$ > "$PIDF"   # a live lock held by this very test process
wrap; RC=$?
have "$OLD_SCRATCH" && sidecar | grep -q '"status":"warn","note":"skipped: previous run alive"' && [ "$(cat "$PIDF")" = "$$" ] \
  && ok "own node: a live lock makes the run skip with sidecar status=warn (never ok), lock untouched (R7, kimi O-9)" || no "live lock not respected or reported as ok: $(sidecar)"
rm -f "$PIDF"
build; fake_host nuzantara
printf '#!/bin/sh\nkill -TERM $PPID\nsleep 2\n' > "$FAKEBIN/payload-killer.sh"; chmod +x "$FAKEBIN/payload-killer.sh"   # payload terminates the wrapper (R5)
HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PAYLOAD="$FAKEBIN/payload-killer.sh" PRO_DISK_JANITOR_PIDFILE="$PIDF" bash "$WRAP" >/dev/null 2>&1; RC=$?
sidecar | grep -q '"status":"error","note":"abnormal exit rc=143"' && [ ! -e "$PIDF" ] \
  && ok "own node: a SIGTERM mid-run still writes sidecar status=error (abnormal exit) and clears its own lock (R5)" || no "abnormal termination left no heartbeat: rc=$RC sidecar=$(sidecar)"
build; fake_host nuzantara; mkdir -p "$H/.organism"; : > "$H/.organism/last_seen"   # sidecar dir is a FILE: heartbeat cannot be written (R3 round 3)
ERR=$(HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PAYLOAD="$SCRIPT" PRO_DISK_JANITOR_PIDFILE="$PIDF" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" bash "$WRAP" 2>&1 >/dev/null); RC=$?
[ $RC -eq 1 ] && echo "$ERR" | grep -q "heartbeat write FAILED" && ok "own node: an unwritable sidecar is the one case that exits non-zero, with the reason on stderr (R3)" || no "unwritable sidecar silent: rc=$RC err=$ERR"

echo; echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
