#!/usr/bin/env bash
# Tripwire test for disk_janitor.sh (guilt + innocence).
# Self-contained: builds a synthetic HOME + scratch root in a temp dir, exercises dry-run /
# apply / idempotence / live-session guard / kill-switch / protected-set refusal (roots,
# ancestors, PII component, siblings) / scratch naming / missing registry / TMP_ROOT shape /
# open-file probe / symlinks / odd names / output boundary / the launchd wrapper, asserts
# exactly what is pruned and what is preserved. External tools and the qdrant delegate are
# disabled (DISK_JANITOR_TOOLS=false, DISK_JANITOR_QDRANT_RETENTION="") except where TEST 10
# puts recording FAKES of uv/restic/brew/pgrep first on PATH (and docker/colima fakes that must never be called): no real tool is reached.
# From the first line a GUARD dir of tripwire stubs (docker colima uv restic brew limactl) sits on PATH
# for the WHOLE suite: a tool that no case faked and the script still reached ends the suite red.
# Targets /bin/bash 3.2. Run: bash scripts/test_disk_janitor.sh
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
GUARD="$(mktemp -d "${TMPDIR:-/tmp}/djguard.XXXXXX")" || { echo "mktemp failed"; exit 70; }
for t in docker colima uv restic brew limactl; do printf '#!/bin/sh\necho "%s $*" >> "%s/tripped"\nexit 97\n' "$t" "$GUARD" > "$GUARD/$t"; chmod +x "$GUARD/$t"; done
export PATH="$GUARD:$PATH"
cleanup(){ find "$ROOT" -mindepth 1 -delete 2>/dev/null || true; rmdir "$ROOT" 2>/dev/null || true; find "$GUARD" -mindepth 1 -delete 2>/dev/null || true; rmdir "$GUARD" 2>/dev/null || true; }
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

echo "═══ TEST 8: council rounds 4-5 — loud inaction (K3), kill-switch order (K4), early exits (N2/K5), delegate root guard (N1) ═══"
build; OUT=$(DISK_JANITOR_SCRATCH_DAYS=abc run --apply); RC=$?
[ $RC -eq 2 ] && have "$OLD_SCRATCH" && have "$OLD_CODEX" && echo "$OUT" | grep -q "REFUSE: DISK_JANITOR_SCRATCH_DAYS must be a non-negative integer" && ok "malformed age knob: run refused rc=2 before any deletion (K3)" || no "malformed age knob not refused rc=$RC"
build; OUT=$(DISK_JANITOR_LOG_ARCHIVE_DAYS=-1 run --apply); RC=$?
[ $RC -eq 2 ] && have "$OLD_GZ" && ok "negative age knob: run refused rc=2 (K3)" || no "negative age knob not refused rc=$RC"
if [ "$(id -u)" -eq 0 ]; then echo "  ⏭  running as root: unlistable-root and unwritable-log cases not exercisable"; else
  build; chmod 000 "$H/.codex/sessions"; OUT=$(run --apply); RC=$?; chmod 755 "$H/.codex/sessions"
  [ $RC -eq 1 ] && have "$OLD_CODEX" && echo "$OUT" | grep -q "codex: root [0-9a-f]\{12\} not listable — skipped" && echo "$OUT" | grep -q "errors=[1-9]" && ok "unlistable codex root: ERROR counted, step skipped loudly, old transcript kept (K3)" || no "unlistable codex root silent rc=$RC"
  build; chmod 000 "$H/logs/archive"; OUT=$(run --apply); RC=$?; chmod 755 "$H/logs/archive"
  [ $RC -eq 1 ] && have "$OLD_GZ" && echo "$OUT" | grep -q "logarch: root not listable — step skipped" && ok "unlistable log archive: ERROR counted, step skipped loudly (K3)" || no "unlistable logarch silent rc=$RC"
  build; mkdir -p "$ROOT/ro"; chmod 555 "$ROOT/ro"
  OUT=$(DISK_JANITOR_ENABLED=false DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" DISK_JANITOR_LOG="$ROOT/ro/j.log" DISK_JANITOR_JOURNAL="$ROOT/ro/j.jsonl" bash "$SCRIPT" --apply 2>&1); RC=$?; chmod 755 "$ROOT/ro"
  [ $RC -eq 0 ] && have "$OLD_SCRATCH" && echo "$OUT" | grep -q "DISABLED via DISK_JANITOR_ENABLED" && ok "kill switch is read before the audit-trail probe: DISABLED exit 0 even with an unwritable log (K4)" || no "kill switch on unwritable log rc=$RC"
fi
NOPROD="__no_such_producer_$$__"   # per-run unique: `pgrep -f` would match ANY concurrent argv carrying a fixed marker (kimi R-5)
wrapx(){ # wrapper with explicit extra env (VAR=value args), stdout+stderr discarded → rc only
  HOME="$H" PATH="$FAKEBIN:$PATH" PRO_DISK_JANITOR_PIDFILE="$PIDF" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_TOOLS=false DISK_JANITOR_QDRANT_RETENTION="" env "$@" bash "$WRAP" >/dev/null 2>&1
}
nosidecar(){ mkdir -p "$H/.organism"; rm -rf "$H/.organism/last_seen"; : > "$H/.organism/last_seen"; }   # sidecar dir is a FILE: no heartbeat can be written
build; fake_host othernode; nosidecar; wrapx PRO_DISK_JANITOR_PAYLOAD="$SCRIPT"; RC=$?
[ $RC -eq 1 ] && ok "wrong-node early exit with an unwritable sidecar exits 1 (N2/K5)" || no "wrong-node early exit ignored a failed heartbeat rc=$RC"
build; fake_host nuzantara; nosidecar; wrapx PRO_DISK_JANITOR_PAYLOAD="$SCRIPT" PRO_DISK_JANITOR_ENABLED=false; RC=$?
[ $RC -eq 1 ] && ok "kill-switch early exit with an unwritable sidecar exits 1 (N2/K5)" || no "kill-switch early exit ignored a failed heartbeat rc=$RC"
build; fake_host nuzantara; nosidecar; echo $$ > "$PIDF"; wrapx PRO_DISK_JANITOR_PAYLOAD="$SCRIPT"; RC=$?; rm -f "$PIDF"
[ $RC -eq 1 ] && ok "live-lock early exit with an unwritable sidecar exits 1 (N2/K5)" || no "live-lock early exit ignored a failed heartbeat rc=$RC"
build; fake_host nuzantara; nosidecar; wrapx PRO_DISK_JANITOR_PAYLOAD="$ROOT/no-such-payload.sh"; RC=$?
[ $RC -eq 1 ] && ok "missing-payload early exit with an unwritable sidecar exits 1 (N2/K5)" || no "missing-payload early exit ignored a failed heartbeat rc=$RC"
build; fake_host othernode; wrapx PRO_DISK_JANITOR_PAYLOAD="$SCRIPT"; RC=$?
[ $RC -eq 0 ] && sidecar | grep -q '"status":"disabled","note":"wrong-node othernode"' && ok "wrong node with a writable sidecar still exits 0 (N2 control)" || no "wrong-node control rc=$RC sidecar=$(sidecar)"
# N1: the REAL delegate, a newline-carrying archive name, and same-named sentinels in the caller's cwd
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR" "$ROOT/cwd"; i=0
while [ $i -lt 7 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
NLF="$QR/qdrant-
sentinel
.tar.gz"; mk "$NLF"; old "$NLF" 30; mk "$ROOT/cwd/sentinel"; mk "$ROOT/cwd/.tar.gz"
OUT=$(cd "$ROOT/cwd" && HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 1 ] && have "$ROOT/cwd/sentinel" && have "$ROOT/cwd/.tar.gz" && have "$NLF" && have "$QR/qdrant-20260106-0300.tar.gz" \
  && echo "$OUT" | grep -q "qdrant: retention rc=1" && grep -q "REFUSE (newline-named entry in root" "$H/logs/qdrant-backup-retention.log" 2>/dev/null \
  && ok "real delegate: a newline-named archive refuses both backstops, cwd sentinels survive, the run fails loudly (N1)" || no "delegate newline escape: rc=$RC sentinel=$(have "$ROOT/cwd/sentinel" && echo kept || echo GONE) tgz=$(have "$ROOT/cwd/.tar.gz" && echo kept || echo GONE)"
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR"; i=0   # N3: the fragment collides with a REAL sibling inside the root
while [ $i -lt 7 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
NLF="$QR/qdrant-sentinel
.tar.gz"; mk "$NLF"; old "$NLF" 30; mk "$QR/qdrant-sentinel"; old "$QR/qdrant-sentinel" 1
OUT=$(HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 1 ] && have "$QR/qdrant-sentinel" && have "$NLF" && have "$QR/qdrant-20260106-0300.tar.gz" \
  && ok "real delegate: an inside-root prefix collision cannot delete the real sibling (N3)" || no "delegate inside-root collision: rc=$RC sibling=$(have "$QR/qdrant-sentinel" && echo kept || echo GONE)"
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR"; i=0   # N4: the delegate's own log never carries a candidate's name
while [ $i -lt 7 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
mk "$QR/qdrant-$MARK.tar.gz"; old "$QR/qdrant-$MARK.tar.gz" 30; mk "$QR/coll-${MARK}_20250101-0300.snapshot"; old "$QR/coll-${MARK}_20250101-0300.snapshot" 30
OUT=$(HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 0 ] && ! have "$QR/qdrant-$MARK.tar.gz" && ! grep -q "$MARK" "$H/logs/qdrant-backup-retention.log" 2>/dev/null && grep -q "REMOVED \[tar.gz backstop" "$H/logs/qdrant-backup-retention.log" \
  && ok "real delegate: the pruned candidate is logged by hash, its name never reaches the delegate log (N4)" || no "delegate log carries a name or prune missing: rc=$RC $(grep -c "$MARK" "$H/logs/qdrant-backup-retention.log" 2>/dev/null) hits"
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR"; i=0   # kimi r3: the delegate's deletion knobs are pinned, never inherited
while [ $i -lt 9 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
OUT=$(QDRANT_KEEP_TARGZ=0 QDRANT_ORPHAN_KEEP_DAYS=0 QDRANT_RETENTION_LOG="$ROOT/stray.log" HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 0 ] && have "$QR/qdrant-20260100-0300.tar.gz" && have "$QR/qdrant-20260106-0300.tar.gz" && ! have "$QR/qdrant-20260108-0300.tar.gz" && [ ! -e "$ROOT/stray.log" ] && [ -s "$H/logs/qdrant-backup-retention.log" ] \
  && ok "inherited QDRANT_KEEP_TARGZ=0 is ignored: keep-7 pinned, 7 newest survive; delegate log pinned under HOME (kimi r3)" || no "delegate knobs inherited: rc=$RC kept=$(ls "$QR" 2>/dev/null | wc -l | tr -d ' ') stray=$( [ -e "$ROOT/stray.log" ] && echo yes || echo no)"
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR"; i=0
while [ $i -lt 9 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
OUT=$(QDRANT_RETENTION_ENABLED=false HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 0 ] && ! have "$QR/qdrant-20260108-0300.tar.gz" && have "$QR/qdrant-20260106-0300.tar.gz" \
  && ok "inherited QDRANT_RETENTION_ENABLED=false cannot silently disable the delegated step (kimi r3)" || no "delegate silently disabled by inherited env: rc=$RC"
GNUBIN="$ROOT/gnubin"; mkdir -p "$GNUBIN"   # N5: a GNU-shaped stat (`-f` = filesystem text, `-c '%s'` = size) must not break the delegate's arithmetic
printf '#!/bin/sh\ncase "$1" in -f) echo "  File: \"$3\"\n    ID: 100000000000000 Namelen: 255     Type: ext2/ext3"; exit 0 ;; -c) shift 2; wc -c < "$1" | tr -d " "; exit 0 ;; esac\nexit 1\n' > "$GNUBIN/stat"; chmod +x "$GNUBIN/stat"
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR"; i=0
while [ $i -lt 9 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
OUT=$(PATH="$GNUBIN:$PATH" HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 0 ] && ! have "$QR/qdrant-20260108-0300.tar.gz" && have "$QR/qdrant-20260106-0300.tar.gz" && grep -q "REMOVED \[tar.gz backstop keep-7\] [0-9a-f]\{12\} (2B)" "$H/logs/qdrant-backup-retention.log" \
  && ok "real delegate under a GNU-shaped stat: sizes stay numeric, keep-7 prune succeeds (N5)" || no "delegate broke under GNU stat: rc=$RC $(grep 'REMOVED\|WARN\|error' "$H/logs/qdrant-backup-retention.log" 2>/dev/null | head -2)"
build; QR="$H/backups/qdrant-snapshots"; mkdir -p "$QR"; i=0
while [ $i -lt 9 ]; do mk "$QR/qdrant-2026010${i}-0300.tar.gz"; old "$QR/qdrant-2026010${i}-0300.tar.gz" $((i+1)); i=$((i+1)); done
OUT=$(HOME="$H" QDRANT_PRODUCER_PROC_RE="$NOPROD" DISK_JANITOR_QDRANT_RETENTION="$HERE/qdrant_backup_retention.sh" run --apply); RC=$?
[ $RC -eq 0 ] && ! have "$QR/qdrant-20260108-0300.tar.gz" && ! have "$QR/qdrant-20260107-0300.tar.gz" && have "$QR/qdrant-20260106-0300.tar.gz" \
  && ok "real delegate: well-formed archives beyond keep-7 are still pruned (N1 control)" || no "delegate control: rc=$RC"

echo "═══ TEST 9: kimi round 3 — launchd PATH (R-2), degenerate protection shapes (R-6) ═══"
build; fake_host nuzantara; printf '#!/bin/sh\nprintf "%%s" "$PATH" > "%s/path.out"\nexit 0\n' "$ROOT" > "$FAKEBIN/payload-path.sh"; chmod +x "$FAKEBIN/payload-path.sh"
HOME="$H" PATH="$FAKEBIN:/usr/bin:/bin:/usr/sbin:/sbin" PRO_DISK_JANITOR_PAYLOAD="$FAKEBIN/payload-path.sh" PRO_DISK_JANITOR_PIDFILE="$PIDF" bash "$WRAP" >/dev/null 2>&1; RC=$?
[ $RC -eq 0 ] && grep -q "^/opt/homebrew/bin:/usr/local/bin:$FAKEBIN:/usr/bin:/bin" "$ROOT/path.out" 2>/dev/null && ok "wrapper prepends the fleet tool dirs to a launchd-shaped PATH before the payload runs (R-2)" || no "wrapper PATH: rc=$RC path=$(cat "$ROOT/path.out" 2>/dev/null)"
build; COREBIN="$ROOT/corebin"; mkdir -p "$COREBIN"   # every utility the payload needs, and NOT uv/docker/brew: a launchd-shaped PATH on any host
for u in bash date tee find du awk head tail tr cut shasum sha256sum grep rm rmdir mkdir dirname basename df pgrep sort lsof cat wc ls id stat env sed uname hostname; do
  b=$(command -v "$u" 2>/dev/null) && [ -n "$b" ] && ln -sf "$b" "$COREBIN/$u"; done
OUT=$(DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_TOOLS=true DISK_JANITOR_QDRANT_RETENTION="" DISK_JANITOR_LOG="$ROOT/j.log" DISK_JANITOR_JOURNAL="$ROOT/j.jsonl" PATH="$COREBIN" bash "$SCRIPT" --apply 2>&1); RC=$?
[ $RC -eq 1 ] && echo "$OUT" | grep -q "tools: NO tool reachable on PATH — step dead" && ok "tools step with no tool on PATH is an ERROR, never a silent 'done: none' (R-2)" || no "dead tools step silent rc=$RC"
build; bash "$SCRIPT" --check-path / >/dev/null 2>&1; RC=$?
[ $RC -eq 3 ] && ok "--check-path / is REFUSED (R-6)" || no "/ not refused rc=$RC"
build; rm -rf "$H/.ollama"; DISK_JANITOR_HOME="$H/" bash "$SCRIPT" --check-path "$H/.ollama/models/m" >/dev/null 2>&1; RC=$?
[ $RC -eq 3 ] && ok "trailing-slash HOME still protects a not-yet-existing protected root (R-6)" || no "trailing-slash HOME defeated protection rc=$RC"

echo "═══ TEST 10: tool steps — uv, restic, brew (recording fakes, df-delta receipt); docker/colima are NOT this janitor's ═══"
# Recording FAKES of uv/restic/brew/pgrep go first on PATH: no real tool is ever reached. docker and colima
# are faked too, into their OWN record file ($ROOT/dc_calls): the janitor must never touch them at all.
DC_TOOLS="docker docker-compose colima limactl nerdctl"   # every docker/VM client: faked into $ROOT/dc_calls
mkfake(){ # $1 tool  $2 body. FAKE_HANG="<tool>:<verb words>" makes that call ignore ALRM+TERM and sleep 31 s (hang.sh)
  printf '#!/bin/sh\n[ -n "$FAKE_HANG" ] && trap "" ALRM TERM\necho "%s $*" >> %s/calls\n[ -n "$FAKE_HANG" ] && case "%s:$1 $2" in "$FAKE_HANG"*) exec %s/hang.sh ;; esac\n%s\n' "$1" "$ROOT" "$1" "$FAKEBIN" "$2" > "$FAKEBIN/$1"
}
fake_tools(){
  mkdir -p "$FAKEBIN"; : > "$ROOT/calls"; rm -f "$ROOT/dc_calls"
  printf '#!/bin/sh\ntrap "" ALRM TERM\necho $$ >> %s/hang.pid\nsleep 31 &\necho $! >> %s/hang.pid\nwait\n' "$ROOT" "$ROOT" > "$FAKEBIN/hang.sh"
  printf '#!/bin/sh\necho "pgrep $*" >> %s/calls\nexit 1\n' "$ROOT" > "$FAKEBIN/pgrep"   # no uv process holds the cache lock (the host may run one)
  for t in uv restic brew; do mkfake "$t" 'exit 0'; done
  for t in $DC_TOOLS; do printf '#!/bin/sh\necho "%s $*" >> %s/dc_calls\nexit 0\n' "$t" "$ROOT" > "$FAKEBIN/$t"; done
  chmod +x "$FAKEBIN"/*
}
truns(){ DISK_JANITOR_HOME="$H" DISK_JANITOR_TMP_ROOT="$T" DISK_JANITOR_TOOLS=true DISK_JANITOR_QDRANT_RETENTION="" DISK_JANITOR_LOG="$ROOT/j.log" DISK_JANITOR_JOURNAL="$ROOT/j.jsonl" PATH="$FAKEBIN:$PATH" bash "$SCRIPT" "$@" 2>&1; }
build; fake_tools
OUT=$(truns --apply); RC=$?
[ $RC -eq 0 ] && grep -q "^uv cache prune" "$ROOT/calls" && grep -q "^restic cache --cleanup" "$ROOT/calls" && grep -Fxq "brew cleanup --prune=30 -s" "$ROOT/calls" \
  && ok "apply: uv cache prune, restic cache --cleanup, brew cleanup each invoked" || no "tool verbs not invoked rc=$RC: $(tr '\n' ';' < "$ROOT/calls")"
grep -q '"uv_cache_prune":{"status":"done".*"restic_cache_cleanup":{"status":"done"' "$ROOT/j.jsonl" \
  && grep -q '"tools":"uv restic brew"' "$ROOT/j.jsonl" && ok "receipt: each tool rule is its own step with status/count/df delta" || no "tool steps receipt wrong: $(tail -1 "$ROOT/j.jsonl")"
# Docker and the Colima VM belong to scripts/localci/prune.py (ruled 2026-10-10). This is the guard that the
# removal is IN FORCE: fake docker + colima record every invocation; a full --apply run must not make one.
dc_touched(){ [ -s "$ROOT/dc_calls" ]; }
receipt_names_dc(){ grep -qi 'docker\|colima' "$ROOT/j.jsonl"; }
{ ! dc_touched; } && ok "apply: docker and colima were NOT invoked at all (record file empty or absent)" || no "janitor invoked docker/colima: $(tr '\n' ';' < "$ROOT/dc_calls")"
{ ! receipt_names_dc; } && ok "receipt carries no docker or colima step or tool word" || no "receipt names docker/colima: $(tail -1 "$ROOT/j.jsonl")"
echo "$OUT" | grep -qi 'docker\|colima' && no "a docker/colima word reached a log line" || ok "no docker/colima word in the apply log"
# innocence: the detectors DO fire on a docker-touching run (a recorded call; a receipt naming a step), so the checks above cannot be vacuous
for t in $DC_TOOLS; do rm -f "$ROOT/dc_calls"; "$FAKEBIN/$t" probe >/dev/null 2>&1; dc_touched || no "innocence: the $t shim records nothing"; done
dc_touched && ok "innocence: each docker/VM shim records its own call (the call detector reads real shim output)" || no "call detector blind"
cp "$ROOT/j.jsonl" "$ROOT/j.bak"; printf '{"steps":{"colima_fstrim":{"status":"done"}}}\n' >> "$ROOT/j.jsonl"; receipt_names_dc && ok "innocence: the receipt detector fires on a colima_fstrim step" || no "receipt detector blind"
cp "$ROOT/j.bak" "$ROOT/j.jsonl"; rm -f "$ROOT/dc_calls"
# Static: no executable line of the script invokes docker or colima (comments and the .colima protected path excluded)
DC_RE='(^|[^A-Za-z0-9_.])(docker(-compose)?|colima|limactl|lima-colima|nerdctl)([^A-Za-z0-9_-]|$)'   # a path prefix (/opt/homebrew/bin/, ./) still matches
exec_invokes_dc(){ sed -e '/^[[:space:]]*#/d' -e 's/[[:space:]]#.*$//' -e 's#\$JH/\.colima"#"#g' "$1" | grep -Eq "$DC_RE"; }
{ ! exec_invokes_dc "$SCRIPT"; } && ok "static: disk_janitor.sh has no executable line invoking docker or colima" || no "disk_janitor.sh still names docker/colima on an executable line: $(sed -e '/^[[:space:]]*#/d' -e 's#\$JH/\.colima"#"#g' "$SCRIPT" | grep -nE "$DC_RE" | head -3)"
printf 'x=1\n  bounded 5 docker volume prune -f\n' > "$ROOT/probe1.sh"; printf 'PROTECTED_ROOTS=("$JH/.colima")\n# docker is mentioned in a comment\nrun colima ssh -- fstrim # trailing\n' > "$ROOT/probe2.sh"
printf 'PROTECTED_ROOTS=("$JH/.colima")\n# docker only in a comment\nx=1 # colima trailing comment\n' > "$ROOT/probe3.sh"
dc_forms_caught=1
for form in 'bounded 5 /opt/homebrew/bin/docker info' '/usr/local/bin/colima status' './docker ps' 'docker-compose up -d' \
            'limactl shell colima' 'nerdctl image prune' 'curl --unix-socket /var/run/docker.sock http://x/images' \
            'ssh -F "$JH/.colima/_lima/colima/ssh.config" lima-colima true' 'D=1; docker image prune -f'; do
  printf '%s\n' "$form" > "$ROOT/probe4.sh"; exec_invokes_dc "$ROOT/probe4.sh" || { dc_forms_caught=0; no "static detector misses: $form"; }
done
printf 'x="$JH/.docker/config.json"\nPROTECTED_ROOTS=("$JH/.colima")\n' > "$ROOT/probe5.sh"
{ [ "$dc_forms_caught" = 1 ] && ! exec_invokes_dc "$ROOT/probe5.sh"; } \
  && ok "innocence: the static detector catches absolute paths, compose, lima, nerdctl, the docker socket and the colima ssh config; a ~/.docker path is quiet" || no "static detector blind or over-matching on paths"
{ exec_invokes_dc "$ROOT/probe1.sh" && exec_invokes_dc "$ROOT/probe2.sh" && ! exec_invokes_dc "$ROOT/probe3.sh"; } \
  && ok "innocence: the static detector fires on docker/colima commands, stays quiet on comments and the .colima path" || no "static detector blind or over-matching"
build; fake_tools; printf '#!/bin/sh\necho "uv $*" >> %s/calls\nexit 0\n' "$ROOT" > "$FAKEBIN/uv"; printf '#!/bin/sh\nexit 0\n' > "$FAKEBIN/pgrep"   # a uv process is alive: it holds the cache lock
OUT=$(truns --apply); RC=$?
! grep -q "uv cache prune" "$ROOT/calls" && grep -q '"uv_cache_prune":{"status":"skipped","count":0,"df_delta_bytes":[-0-9]*,"reason":"uv-lock-held"}' "$ROOT/j.jsonl" \
  && ok "uv process alive: cache prune skipped (lock held), never forced" || no "uv prune ran while a uv process was alive"
build; fake_tools; OUT=$(truns); RC=$?
[ $RC -eq 0 ] && ! grep -q "cache prune\|--cleanup\|brew" "$ROOT/calls" && grep -q '"uv_cache_prune":{"status":"dry-run"' "$ROOT/j.jsonl" && grep -q '"restic_cache_cleanup":{"status":"dry-run"' "$ROOT/j.jsonl" \
  && ok "dry-run: no tool verb executed, steps reported as dry-run" || no "dry-run executed a tool verb rc=$RC: $(tr '\n' ';' < "$ROOT/calls")"
{ ! dc_touched; } && echo "$OUT" | grep -q "would run brew cleanup --prune=30" && ok "dry-run: docker/colima untouched, the plan line names brew only" || no "dry-run touched docker/colima or kept the old plan line"
build; fake_tools; printf '#!/bin/sh\necho "restic $*" >> %s/calls\nexit 1\n' "$ROOT" > "$FAKEBIN/restic"; chmod +x "$FAKEBIN/restic"
OUT=$(truns --apply); RC=$?
[ $RC -eq 1 ] && echo "$OUT" | grep -q "restic_cache_cleanup: error" && grep -q '"restic_cache_cleanup":{"status":"error"' "$ROOT/j.jsonl" && ! grep -q '"tools":"[^"]*restic' "$ROOT/j.jsonl" \
  && ok "failed restic cleanup is an ERROR in log and receipt, rc=1, never listed as done" || no "restic failure not reported as error rc=$RC"
grep -q '"uv_cache_prune":{"status":"done"' "$ROOT/j.jsonl" && ok "restic failure does not starve the other tool steps" || no "other tool steps starved by the restic failure"

# F1: bounded() is a real deadline. The fake ignores ALRM and TERM and sleeps 31 s (a Go binary's behaviour).
# Cases run CONCURRENTLY: each in its own root under $HC (the fixture globals are re-pointed inside a
# background subshell), writes "ok|msg" or "no|msg" to its own file, and the parent reports them in call order.
HC="$ROOT/hc"; HC_N=0
hang_case(){ # $1 FAKE_HANG key  $2 step ("" = just errors>=1)  $3 reason  $4 regex of a LATER step that must still have run
  HC_N=$((HC_N+1))
  (
    local el p st alive="" shape=ok w=0
    ROOT="$HC/$HC_N"; H="$ROOT/home"; T="$ROOT/claude-501"; FAKEBIN="$ROOT/bin"; mkdir -p "$ROOT"
    build; fake_tools; : > "$ROOT/hang.pid"; SECONDS=0
    OUT=$(FAKE_HANG="$1" DISK_JANITOR_CACHE_TIMEOUT=3 truns --apply); RC=$?; el=$SECONDS
    while :; do   # bounded poll (3 s) for the killed children to be gone, not a fixed sleep
      alive=""; for p in $(cat "$ROOT/hang.pid"); do st=$(ps -o stat= -p "$p" 2>/dev/null); case "$st" in ''|Z*) ;; *) alive="$alive $p" ;; esac; done
      { [ -z "$alive" ] || [ $w -ge 30 ]; } && break; w=$((w+1)); sleep 0.1
    done
    [ "$RC" -eq 1 ] || shape="rc=$RC (want 1)"
    [ "$el" -lt 20 ] || shape="took ${el}s: not bounded"
    [ -z "$alive" ] || shape="child left behind:$alive"
    grep -q '"errors":[1-9]' "$ROOT/j.jsonl" || shape="errors not counted"
    [ -z "$2" ] || grep -q "\"$2\":{\"status\":\"error\"[^}]*\"reason\":\"$3\"" "$ROOT/j.jsonl" || shape="no $2 error $3: $(grep -o "\"$2\":{[^}]*}" "$ROOT/j.jsonl")"
    grep -q "$4" "$ROOT/j.jsonl" || shape="later step did not run"
    if [ "$shape" = ok ]; then echo "ok|hung '$1' (ignores ALRM+TERM): returns in ${el}s, ${2:-brew} error ${3:-counted}, later steps ran, no child left"
    else echo "no|hung '$1': $shape"; fi > "$HC/$HC_N.res"
  ) &
}
hang_case "uv:"      uv_cache_prune       prune-timeout   '"restic_cache_cleanup":{"status":"done"'
hang_case "restic:"  restic_cache_cleanup cleanup-timeout '"tools":"[^"]*brew'
hang_case "brew:"    "" ""                                '"restic_cache_cleanup":{"status":"done"'
wait
i=1; while [ $i -le $HC_N ]; do
  res=$(cat "$HC/$i.res" 2>/dev/null) || res="no|hung case $i wrote no result"; [ -n "$res" ] || res="no|hung case $i wrote no result"
  case "$res" in ok\|*) ok "${res#ok|}" ;; *) no "${res#no|}" ;; esac; i=$((i+1))
done

# F6: the timeout knob is a plain decimal integer in a range, refused with rc 2 before anything runs
build; fake_tools; BADK=""
for kv in CACHE_TIMEOUT=0 CACHE_TIMEOUT=08 CACHE_TIMEOUT=030 CACHE_TIMEOUT= CACHE_TIMEOUT=-1 CACHE_TIMEOUT=abc CACHE_TIMEOUT=1.5 CACHE_TIMEOUT=86401 CACHE_TIMEOUT=99999999999999999999; do
  : > "$ROOT/calls"; OUT=$(export "DISK_JANITOR_$kv"; truns --apply); RC=$?
  [ $RC -eq 2 ] && [ ! -s "$ROOT/calls" ] && echo "$OUT" | grep -q "REFUSE: DISK_JANITOR_${kv%%=*} must be a plain integer" || BADK="$BADK [$kv rc=$RC]"
done
[ -z "$BADK" ] && have "$OLD_SCRATCH" && ok "0, leading zero, sign, empty, non-digit and out-of-range CACHE_TIMEOUT refused rc=2 before any tool or deletion" || no "knob values wrongly accepted:$BADK"
GOODK=""
for kv in CACHE_TIMEOUT=1 CACHE_TIMEOUT=86400; do
  OUT=$(export "DISK_JANITOR_$kv"; truns); RC=$?; [ $RC -eq 0 ] || GOODK="$GOODK [$kv rc=$RC]"
done
[ -z "$GOODK" ] && ok "range edges (CACHE_TIMEOUT 1 and 86400) are accepted" || no "valid knob edge refused:$GOODK"
# the docker/colima knobs are gone: setting one is inert (not refused), and still no docker/colima call
build; fake_tools; OUT=$(DISK_JANITOR_DOCKER_DAYS=abc DISK_JANITOR_TOOL_TIMEOUT=0 DISK_JANITOR_FSTRIM_TIMEOUT=0 truns --apply); RC=$?
[ $RC -eq 0 ] && ! dc_touched && ok "removed docker/colima knobs are inert: a stale plist value neither refuses the run nor reaches docker/colima" || no "a removed knob still acts rc=$RC"

# F4: the last case used to delete the fakes and run --apply on the host's REAL tools behind one check
build; fake_tools
OUT=$(DISK_JANITOR_CACHE_TIMEOUT=abc truns --apply); RC=$?
[ $RC -eq 2 ] && [ ! -s "$ROOT/calls" ] && [ ! -e "$GUARD/tripped" ] && ok "bad knob with --apply: rc 2 and NO tool invoked (fakes stay first, real tools unreachable)" || no "bad knob case reached a tool or ran: rc=$RC calls=$(tr '\n' ';' < "$ROOT/calls")"
decoys_intact && ok "protected decoys intact after the tool steps" || no "a decoy was touched by a tool step"
[ ! -e "$GUARD/tripped" ] && ok "no real docker/colima/uv/restic/brew/limactl reached by any case in the suite" || no "a REAL tool was reached: $(cat "$GUARD/tripped")"

echo; echo "PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
