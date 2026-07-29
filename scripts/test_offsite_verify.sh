#!/usr/bin/env bash
# Proof for scripts/lib/offsite_verify.sh — GUILT and INNOCENCE.
#
# The gate exists because the backup judged itself by reaching the end of the script
# instead of by the artifact (see the header of offsite_verify.sh). So the proof has to
# do the opposite of what the old code did: it must show the verifier says NO in every
# world where the object is not really there, including the worlds that look like success.
#
#   GUILT     — object absent; listing refused (bad creds); aws CLI missing; a name that
#               merely CONTAINS ours (`...sql.gz.partial`); a DIFFERENT object of the same
#               day. Each must return 1, because in each of them a backup does not exist.
#   INNOCENCE — the object is present, among many others -> 0. A legitimate success must
#               not be turned into an alarm, or the gate gets disabled and we are back to
#               superscar #2.
#
# The `.partial` and same-day cases are the ones a substring check would get wrong; they
# are here because the whole family this repo keeps re-living is guards that match a SHAPE
# and believe they matched an ENTITY.
#
# No network and no credential: `aws` is a stub that prints a listing per world.
set -uo pipefail
export OFFSITE_VERIFY_RETRY_SLEEP=0   # nessuna attesa nei test: le assenze qui sono vere, non transitorie

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
# absolute path: the last world under test strips PATH down to a dir with no aws,
# and a trap that cannot find `rm` turns a passing corpus into exit 127.
trap '/bin/rm -rf "$TMP"' EXIT

cat > "$TMP/aws" <<'STUB'
#!/bin/sh
# STUB_RC      -> exit code of the listing (non-zero = the listing itself failed)
# STUB_LISTING -> what the listing prints
[ "${STUB_RC:-0}" -ne 0 ] && { echo "An error occurred (InvalidAccessKeyId)" >&2; exit "$STUB_RC"; }
printf '%s\n' "$STUB_LISTING"
exit 0
STUB
chmod +x "$TMP/aws"

# shellcheck source=lib/offsite_verify.sh
. "$HERE/lib/offsite_verify.sh"

PASS=0; FAIL=0
KEY="nuzantara-fly-20260727-0300.sql.gz"
REAL_LISTING="2026-07-26 03:02:32  383945210 nuzantara-fly-20260726-0300.sql.gz
2026-07-27 03:02:32  383945210 $KEY
2026-07-27 03:22:42  383560761 nuzantara-fly-20260727-0320.sql.gz"

run () {  # run <name> <expected_rc> <PATH-has-aws?> ; env STUB_* set by caller
    local name="$1" want="$2" withaws="$3" got
    if [ "$withaws" = "yes" ]; then export PATH="$TMP:$PATH_ORIG"; else export PATH="$TMP/empty"; fi
    set +e; verify_offsite_object "nuzantara-backups" "https://fly.storage.tigris.dev" "$KEY" >/dev/null 2>&1; got=$?; set -e
    if [ "$got" = "$want" ]; then PASS=$((PASS+1)); printf '  ok    %-58s rc=%s\n' "$name" "$got"
    else FAIL=$((FAIL+1)); printf '  FAIL  %-58s rc=%s (atteso %s)\n' "$name" "$got" "$want"; fi
}
PATH_ORIG="$PATH"; mkdir -p "$TMP/empty"

echo "INNOCENCE — un successo vero non deve diventare un allarme"
STUB_RC=0 STUB_LISTING="$REAL_LISTING" run "oggetto presente tra gli altri" 0 yes

echo "GUILT — ogni mondo in cui il backup NON esiste"
STUB_RC=0 STUB_LISTING="2026-07-26 03:02:32 383945210 nuzantara-fly-20260726-0300.sql.gz" \
    run "oggetto assente (la notte del 15/7)" 1 yes
STUB_RC=1 STUB_LISTING="" \
    run "listing rifiutato (credenziali Tigris morte)" 1 yes
STUB_RC=0 STUB_LISTING="2026-07-27 03:02:32 12345 ${KEY}.partial" \
    run "un nome che CONTIENE il nostro (.partial)" 1 yes
STUB_RC=0 STUB_LISTING="2026-07-27 03:22:42 383560761 nuzantara-fly-20260727-0320.sql.gz" \
    run "altro oggetto dello stesso giorno, non il nostro" 1 yes
STUB_RC=0 STUB_LISTING="$REAL_LISTING" \
    run "aws assente — non si puo' verificare, quindi non si afferma" 1 no

echo
export PATH="$PATH_ORIG"
echo "pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
