#!/usr/bin/env bash
# Proof that ONE failing backup phase does not take the other down with it.
#
# infra/scripts/fly-backup.sh runs Postgres then Qdrant and reports a PARTIAL result if
# either fails. Under `set -euo pipefail` a bare pipeline aborts the script, so on a PG
# failure bash never reached `PG_EXIT=${PIPESTATUS[0]}`: Phase 2 was skipped and the PARTIAL
# report was dead code on the one path it exists for. Measured 2026-07-27: the qdrant
# nightly is missing for 2026-07-26 — the night the PG backup failed — and present on every
# neighbouring day in the retention window.
#
#   GUILT     — PG fails: Qdrant must STILL run, the script must exit non-zero, and the log
#               must name which phase failed.
#   INNOCENCE — both succeed: exit 0, both phases ran, no PARTIAL line (an alarm that fires
#               on success is an alarm someone turns off).
#   SYMMETRY  — Qdrant fails: same treatment, PG already done. Asserted because a fix that
#               only covers the phase that bit you is half a fix.
#
# Both child scripts are stubs under a tmp HOME, so nothing touches Fly, Tigris or the disk
# of the real machine.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
WRAPPER="$REPO_ROOT/infra/scripts/fly-backup.sh"
[ -f "$WRAPPER" ] || { echo "fly-backup.sh not found at $WRAPPER"; exit 1; }

TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
check () {  # check <name> <condition-result>
    if [ "$2" = "0" ]; then PASS=$((PASS+1)); printf '  ok    %s\n' "$1"
    else FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; fi
}

run_case () {  # run_case <pg-exit> <qdrant-exit> ; sets RC and $TMP/home/logs/*
    rm -rf "$TMP/home"
    mkdir -p "$TMP/home/scripts" "$TMP/home/logs"
    cat > "$TMP/home/scripts/fly-pg-backup.sh" <<EOF
echo "pg ran" ; : > "$TMP/home/pg.ran" ; exit $1
EOF
    cat > "$TMP/home/scripts/fly-qdrant-backup.sh" <<EOF
echo "qdrant ran" ; : > "$TMP/home/qdrant.ran" ; exit $2
EOF
    HOME="$TMP/home" bash "$WRAPPER" >"$TMP/out" 2>&1
    RC=$?
}

echo "GUILT — se il PG fallisce, Qdrant deve girare LO STESSO"
run_case 1 0
check "Fase 1 eseguita" "$([ -f "$TMP/home/pg.ran" ] && echo 0 || echo 1)"
check "Fase 2 NON saltata dal fallimento della Fase 1" "$([ -f "$TMP/home/qdrant.ran" ] && echo 0 || echo 1)"
check "lo script esce non-zero" "$([ "$RC" != "0" ] && echo 0 || echo 1)"
check "il log dice QUALE fase e' caduta (PG=1)" "$(grep -q 'PARTIAL: PG=1 Qdrant=0' "$TMP/out" && echo 0 || echo 1)"

echo "SIMMETRIA — e se cade Qdrant, stesso trattamento"
run_case 0 1
check "Fase 1 eseguita" "$([ -f "$TMP/home/pg.ran" ] && echo 0 || echo 1)"
check "Fase 2 eseguita" "$([ -f "$TMP/home/qdrant.ran" ] && echo 0 || echo 1)"
check "lo script esce non-zero" "$([ "$RC" != "0" ] && echo 0 || echo 1)"
check "il log dice QUALE fase e' caduta (Qdrant=1)" "$(grep -q 'PARTIAL: PG=0 Qdrant=1' "$TMP/out" && echo 0 || echo 1)"

echo "INNOCENZA — a due fasi sane non si allarma nessuno"
run_case 0 0
check "exit 0" "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "entrambe le fasi eseguite" "$([ -f "$TMP/home/pg.ran" ] && [ -f "$TMP/home/qdrant.ran" ] && echo 0 || echo 1)"
check "nessuna riga PARTIAL" "$(grep -q 'PARTIAL' "$TMP/out" && echo 1 || echo 0)"
check "il log conferma il successo" "$(grep -q 'Backup complete' "$TMP/out" && echo 0 || echo 1)"

echo
echo "pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
