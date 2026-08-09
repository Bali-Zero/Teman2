#!/usr/bin/env bash
# test_tg_sender_migration.sh — the senders migrated to the gateway must
# actually REACH it, not merely contain its name.
#
# Batch 1 (2026-08-09, #3913): six organs, ~2,350 wake-ups a day.
# Batch 2 (2026-08-10): post_publish_poller.py (288/day) and
# runtime-reconcile.sh (48/day). The poller is a special case worth naming: its
# LaunchAgent passes no TELEGRAM_BOT_TOKEN, so its raw POST returned at the
# first `if not TELEGRAM_BOT_TOKEN` and the organ was MUTE. Migrating it GIVES
# it a voice, which is why its tier is `digest` by deliberate choice — five
# pipeline-degradation alerts do not each deserve a P0 slot.
#
# Why this exists. Six organs that between them wake ~2,350 times a day used to
# POST straight to Telegram: outside the tier router, outside the P0 budget,
# outside the dedup ladder, and absent from the ledger that answers "how much
# did the organism send today?". Two of them (skills_bridge_consumer,
# wr2_plist_watchdog) had no cooldown of any kind, so a persistent fault was one
# message per run — 192 and 96 a day respectively, all restating one fact.
#
# A static grep would prove only that the string `tg_notify` appears. What has
# to be true is stronger and only an execution shows it (W107): the gateway is
# INVOKED, with a dedup key that names a CONDITION rather than a measurement,
# through an ABSOLUTE interpreter (W108), and when the gateway is missing the
# organ leaves a trace of not having spoken instead of failing silent.
#
# Run: bash scripts/tests/test_tg_sender_migration.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); printf '  ✓ %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  ✗ %s\n' "$1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (atteso=$3 ottenuto=$2)"; fi; }

# The six files this migration moved, plus supervisor_liveness_watchdog.sh —
# already on the gateway but brought to the same absolute-interpreter form,
# because curing one of two twins only moves which one is unguarded (W106b).
MIGRATED=(
  "scripts/intel-lake-outbox-drain/intel-lake-outbox-drain.py"
  "apps/cell/scripts/skills_bridge_consumer.py"
  "infra/scripts/pg-organism-bridge-watchdog.sh"
  "scripts/intake_review_reader_liveness.sh"
  "scripts/cost_breaker_deadman.sh"
  "scripts/wr2_plist_watchdog.sh"
  "scripts/supervisor_liveness_watchdog.sh"
  "apps/bali-intel-scraper/scripts/post_publish_poller.py"
  "scripts/runtime-reconcile.sh"
)

echo "── struttura (tutti e ${#MIGRATED[@]})"
for rel in "${MIGRATED[@]}"; do
  f="$REPO_ROOT/$rel"
  base="$(basename "$rel")"
  if [ ! -f "$f" ]; then bad "$base: file assente"; continue; fi

  # GUILT-by-absence: no raw sender may survive. Counted on the send host so a
  # docstring that merely NAMES the endpoint does not read as one — the lint
  # itself is stricter, and that asymmetry is deliberate: prose can be reworded,
  # a concatenated URL cannot be spotted by eye.
  raw=$(grep -cE 'api\.telegram\.org/bot' "$f" || true)
  check "$base: zero sender grezzi" "$raw" "0"

  gw=$(grep -c 'tg_notify\.py' "$f" || true)
  if [ "$gw" -gt 0 ]; then ok "$base: risolve il gateway"; else bad "$base: non nomina il gateway"; fi

  key=$(grep -c -- '--dedup-key' "$f" || true)
  if [ "$key" -gt 0 ]; then ok "$base: passa una dedup-key"; else bad "$base: nessuna dedup-key"; fi

  # NOTE on what is NOT asserted here. Earlier drafts also grep'd for
  # `sys.executable` / `/usr/bin/python3` and for a fail-loud phrase, and both
  # checks SURVIVED mutation: each property appears twice per file, so deleting
  # one occurrence left the other and the count stayed above zero. Counting
  # mentions across a whole file asserts that the file TALKS about the property,
  # not that the branch HAS it — form, not entity. Both moved below, where they
  # are proven by running the branch instead of reading it.
  :
done

# A dedup key that carries a MEASUREMENT mints a fresh key per firing and
# defeats every window — the exact defect #3677 cured at the sentinel. Keys may
# interpolate a HOST (stable), never a count, a duration or a clock.
echo
echo "── le chiavi nominano una condizione, non una misura"
badkeys=0
while IFS= read -r line; do
  keyval="${line#*--dedup-key}"
  if printf '%s' "$keyval" | head -c 120 | grep -qE '\$\{?(n|N|LAG_MIN|CODE|GAP|rejected|total|accepted|elapsed)\b'; then
    bad "chiave con misura: $(printf '%s' "$line" | cut -c1-100)"
    badkeys=$((badkeys + 1))
  fi
done < <(cd "$REPO_ROOT" && grep -rh -A2 -- '--dedup-key' "${MIGRATED[@]}" 2>/dev/null | grep -- '--dedup-key' || true)
check "nessuna chiave porta una misura" "$badkeys" "0"

# ── mondo finto: il gateway viene DAVVERO invocato ────────────────────────────
# The two Python organs are function-level testable, so they get executed for
# real against a fake gateway that records its argv. This is the half a static
# scan cannot do: it distinguishes "names the gateway" from "reaches it".
echo
echo "── esecuzione contro un gateway finto"
FAKE="$(mktemp -d "${TMPDIR:-/tmp}/tgmig.XXXXXX")"
trap 'rm -rf "$FAKE"' EXIT
mkdir -p "$FAKE/nuzantara/scripts" "$FAKE/scripts"
cat > "$FAKE/nuzantara/scripts/tg_notify.py" <<'FAKEGW'
import pathlib
import sys
pathlib.Path(__file__).parent.joinpath("CALLED.txt").write_text("\n".join(sys.argv[1:]))
print("tg_notify: spooled", file=sys.stderr)
FAKEGW
CALLED="$FAKE/nuzantara/scripts/CALLED.txt"

# intel-lake runs from a FLAT ~/scripts copy in production, not from the repo
# subdirectory — so the fake reproduces that layout, or it would prove the easy
# case and miss the live one (W108 GOTCHA-2: a poor fake measures its poverty).
cp "$REPO_ROOT/scripts/intel-lake-outbox-drain/intel-lake-outbox-drain.py" "$FAKE/scripts/"
cp "$REPO_ROOT/scripts/intel-lake-outbox-drain/intel_lake_outbox.py" "$FAKE/scripts/" 2>/dev/null || true

# httpx stub. The drain imports httpx at module level for its POST to the Fly
# backend; `_alert_rejected` never touches it. This job is deliberately hermetic
# — it installs no third-party packages, precisely so that a dependency gap can
# never mask a regrowth violation (the split documented at the top of
# tg-gateway.yml) — so the stub keeps it that way instead of adding an install
# line. It also removes a false green: with httpx present locally and absent in
# CI, this corpus passed on the dev machine and failed on the runner, which is
# the same "the dev box cannot reproduce the red" shape as W108. The stub sits
# in $FAKE/scripts, which is first on sys.path for the driver below only.
cat > "$FAKE/scripts/httpx.py" <<'HTTPXSTUB'
"""Minimal stand-in: imported by the drain, unused by the alert path."""


class Client:  # pragma: no cover - never called from _alert_rejected
    def __init__(self, *a, **k):
        raise RuntimeError("httpx stub: the alert path must not make HTTP calls")


def post(*a, **k):  # pragma: no cover
    raise RuntimeError("httpx stub: the alert path must not make HTTP calls")
HTTPXSTUB
rm -f "$CALLED"
HOME="$FAKE" python3 - "$FAKE" <<'PYDRIVE' >/dev/null 2>&1
import importlib.util
import sys
fake = sys.argv[1]
sys.path.insert(0, f"{fake}/scripts")
spec = importlib.util.spec_from_file_location("d", f"{fake}/scripts/intel-lake-outbox-drain.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Record which httpx actually won the import, so the assertion below can prove
# this run took the same path a runner without httpx installed would take.
import httpx
open(f"{fake}/httpx_origin.txt", "w").write(httpx.__file__ or "<none>")
m._alert_rejected(7, 3, 10)
PYDRIVE
# The stub must SHADOW a real httpx when one is installed, or the local run is
# not representative of CI and the next false green goes unnoticed.
if grep -q "^$FAKE/" "$FAKE/httpx_origin.txt" 2>/dev/null; then
  ok "intel-lake: importa lo stub httpx (corsa identica a un runner senza httpx)"
else
  bad "intel-lake: ha importato l'httpx REALE ($(cat "$FAKE/httpx_origin.txt" 2>/dev/null)) — la corsa locale non riproduce la CI"
fi
if [ -f "$CALLED" ]; then
  ok "intel-lake: gateway raggiunto dal layout HOME piatto"
  grep -q '^intel-lake-outbox:rejected$' "$CALLED" \
    && ok "intel-lake: chiave = intel-lake-outbox:rejected" \
    || bad "intel-lake: chiave inattesa ($(grep -A1 -- '--dedup-key' "$CALLED" | tail -1))"
  grep -q '^p0$' "$CALLED" && ok "intel-lake: tier p0" || bad "intel-lake: tier inatteso"
else
  bad "intel-lake: il gateway NON è stato invocato"
fi

# Same organ, gateway removed: it must complain, not vanish.
mv "$FAKE/nuzantara/scripts/tg_notify.py" "$FAKE/nuzantara/scripts/tg_notify.hidden"
out=$(HOME="$FAKE" python3 - "$FAKE" <<'PYDRIVE2' 2>&1
import importlib.util
import sys
fake = sys.argv[1]
sys.path.insert(0, f"{fake}/scripts")
spec = importlib.util.spec_from_file_location("d", f"{fake}/scripts/intel-lake-outbox-drain.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m._alert_rejected(5, 0, 5)
PYDRIVE2
)
printf '%s' "$out" | grep -q 'NOT sent' \
  && ok "intel-lake: senza gateway lascia traccia (fail-loud)" \
  || bad "intel-lake: senza gateway è muto — $(printf '%s' "$out" | tail -1)"
mv "$FAKE/nuzantara/scripts/tg_notify.hidden" "$FAKE/nuzantara/scripts/tg_notify.py"

# post_publish_poller resolves the gateway from parents[3] of its own path, so
# the fake reproduces the REAL tree (apps/bali-intel-scraper/scripts/...) rather
# than the convenient flat one — otherwise the assertion would exercise the
# home-relative fallback and leave the branch that actually runs in production
# unproven.
POLLER_DIR="$FAKE/nuzantara/apps/bali-intel-scraper/scripts"
mkdir -p "$POLLER_DIR"
cp "$REPO_ROOT/apps/bali-intel-scraper/scripts/post_publish_poller.py" "$POLLER_DIR/"
poller_drive() {
  HOME="$FAKE" "${1:-python3}" - "$POLLER_DIR" <<'PYPOLL' 2>&1
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("pp", f"{sys.argv[1]}/post_publish_poller.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.send_telegram_alert("prova", dedup_key="post-publish:cover-skipped-codex-down")
PYPOLL
}
rm -f "$CALLED"
poller_drive >/dev/null 2>&1
if [ -f "$CALLED" ]; then
  ok "post-publish-poller: gateway raggiunto dal layout reale (parents[3])"
  grep -qx 'post-publish:cover-skipped-codex-down' "$CALLED" \
    && ok "post-publish-poller: chiave = post-publish:cover-skipped-codex-down" \
    || bad "post-publish-poller: chiave inattesa"
  # digest, not p0 — a deliberate tier choice, so it is asserted and not assumed.
  grep -qx 'digest' "$CALLED" \
    && ok "post-publish-poller: tier digest" \
    || bad "post-publish-poller: tier inatteso (atteso digest)"
else
  bad "post-publish-poller: il gateway NON è stato invocato"
fi

# Gateway gone: it must say it did not speak. This organ was MUTE before the
# migration, so a silent failure here would restore exactly the state cured.
mv "$FAKE/nuzantara/scripts/tg_notify.py" "$FAKE/nuzantara/scripts/tg_notify.hidden"
pollout="$(poller_drive)"
printf '%s' "$pollout" | grep -q 'NOT sent' \
  && ok "post-publish-poller: senza gateway lascia traccia (fail-loud)" \
  || bad "post-publish-poller: senza gateway è muto"
mv "$FAKE/nuzantara/scripts/tg_notify.hidden" "$FAKE/nuzantara/scripts/tg_notify.py"

# The shell organs: their sender function is self-contained, so it is extracted
# and run on its own. `$HOME` points at the fake, which is the fallback branch
# every one of them resolves to when no sibling gateway exists.
# Extra harness lines a given sender needs to run standalone. runtime-reconcile
# reads its own cooldown stamp and logs through a `log` helper defined outside
# the extracted function; without these the harness dies on `set -u` and the
# organ would be scored mute for the harness's poverty, not its own (W108).
_extra_env() {
  case "$1" in
    runtime-reconcile.sh)
      echo "ALERT_STAMP=$FAKE/rr_stamp"
      echo "ALERT_COOLDOWN_SEC=0"
      echo 'log() { printf "%s\n" "$*" >> "$LOG"; }'
      ;;
  esac
}

run_shell_sender() {
  local rel="$1" fn="$2" expect_key="$3" base
  base="$(basename "$rel")"
  rm -f "$CALLED"
  # Harness named after the FILE, not the function: intake_review_reader_liveness
  # and supervisor_liveness_watchdog both call theirs `send_telegram`, and keying
  # on the function would have one silently overwrite the other's harness.
  local harness="$FAKE/harness_${base}.sh"
  {
    echo 'set -uo pipefail'
    echo "LOG_FILE=$FAKE/harness.log"
    echo "LOG=$FAKE/harness.log"
    _extra_env "$base"
    # Extract the function verbatim, from its opening line to the closing brace
    # in column 1 — running the REAL body, not a paraphrase of it.
    awk "/^${fn}\(\) \{/,/^\}/" "$REPO_ROOT/$rel"
    if [ "$fn" = "telegram_backup" ]; then
      echo "$fn 'probe:key' 'messaggio di prova'"
    else
      echo "$fn 'messaggio di prova'"
    fi
  } > "$harness"
  HOME="$FAKE" bash "$harness" >/dev/null 2>&1
  if [ -f "$CALLED" ]; then
    ok "$base: gateway raggiunto"
    if grep -qx "$expect_key" "$CALLED"; then
      ok "$base: chiave = $expect_key"
    else
      bad "$base: chiave inattesa (attesa $expect_key)"
    fi
  else
    bad "$base: il gateway NON è stato invocato"
  fi
}

HOST="$(hostname -s 2>/dev/null || echo unknown)"
run_shell_sender "infra/scripts/pg-organism-bridge-watchdog.sh" "telegram_backup" "probe:key"
run_shell_sender "scripts/wr2_plist_watchdog.sh" "_telegram" "wr2-plist-watchdog:drift"
run_shell_sender "scripts/cost_breaker_deadman.sh" "tg_alert" "cost-breaker-deadman:governance-mute"
# The twins. Both call theirs `send_telegram`, and both were missing from this
# list until mutation exposed it: killing the gateway call in
# intake_review_reader_liveness.sh left the suite GREEN. A dynamic corpus proves
# only the organs it actually runs.
run_shell_sender "scripts/intake_review_reader_liveness.sh" "send_telegram" "intake-review-reader:stalled:${HOST}"
run_shell_sender "scripts/supervisor_liveness_watchdog.sh" "send_telegram" "supervisor-liveness:${HOST}"
run_shell_sender "scripts/runtime-reconcile.sh" "alert" "runtime-reconcile:invariant-breach"

# ── W108, proven by behaviour instead of by spelling ──────────────────────────
# A POISONED python3 goes first on PATH. An organ that resolves its interpreter
# from PATH runs the poison and never reaches the gateway; an organ holding an
# absolute path steps straight over it. This replaces the grep that mutation
# showed to be decorative: it cannot be satisfied by a second mention elsewhere
# in the file, only by the branch actually being absolute.
echo
echo "── interprete assoluto (PATH avvelenato)"
POISON="$FAKE/poison"
mkdir -p "$POISON"
cat > "$POISON/python3" <<'POISONED'
#!/bin/sh
echo "POISONED python3 ran" >&2
exit 97
POISONED
chmod +x "$POISON/python3"

poisoned_still_reaches() {
  local rel="$1" fn="$2" base harness
  base="$(basename "$rel")"
  rm -f "$CALLED"
  harness="$FAKE/poisoned_${base}.sh"
  {
    echo 'set -uo pipefail'
    echo "LOG_FILE=$FAKE/harness.log"
    echo "LOG=$FAKE/harness.log"
    _extra_env "$base"
    awk "/^${fn}\(\) \{/,/^\}/" "$REPO_ROOT/$rel"
    if [ "$fn" = "telegram_backup" ]; then
      echo "$fn 'probe:key' 'con PATH avvelenato'"
    else
      echo "$fn 'con PATH avvelenato'"
    fi
  } > "$harness"
  HOME="$FAKE" PATH="$POISON:$PATH" bash "$harness" >/dev/null 2>&1
  if [ -f "$CALLED" ]; then
    ok "$base: raggiunge il gateway anche col PATH avvelenato"
  else
    bad "$base: interprete risolto da PATH — l'allarme muore col suo ambiente (W108)"
  fi
}
poisoned_still_reaches "infra/scripts/pg-organism-bridge-watchdog.sh" "telegram_backup"
poisoned_still_reaches "scripts/wr2_plist_watchdog.sh" "_telegram"
poisoned_still_reaches "scripts/cost_breaker_deadman.sh" "tg_alert"
poisoned_still_reaches "scripts/intake_review_reader_liveness.sh" "send_telegram"
poisoned_still_reaches "scripts/supervisor_liveness_watchdog.sh" "send_telegram"
poisoned_still_reaches "scripts/runtime-reconcile.sh" "alert"

# Same discriminator for the Python organs: sys.executable is absolute by
# construction, a literal "python3" is not.
rm -f "$CALLED"
# The DRIVER must not eat the poison itself. Resolved absolutely before PATH is
# poisoned — the first draft ran `python3 - "$FAKE"` under the poisoned PATH,
# died at exit 97 and reported the ORGAN as PATH-resolved: the probe measuring
# its own poverty, not the code under test (W108 GOTCHA-2).
DRIVER_PY="$(command -v python3)"
HOME="$FAKE" PATH="$POISON:$PATH" "$DRIVER_PY" - "$FAKE" <<'PYPOISON' >/dev/null 2>&1
import importlib.util
import sys
fake = sys.argv[1]
sys.path.insert(0, f"{fake}/scripts")
spec = importlib.util.spec_from_file_location("d", f"{fake}/scripts/intel-lake-outbox-drain.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m._alert_rejected(1, 9, 10)
PYPOISON
[ -f "$CALLED" ] \
  && ok "intel-lake: raggiunge il gateway anche col PATH avvelenato" \
  || bad "intel-lake: interprete risolto da PATH (W108)"

rm -f "$CALLED"
PATH="$POISON:$PATH" poller_drive "$DRIVER_PY" >/dev/null 2>&1
[ -f "$CALLED" ] \
  && ok "post-publish-poller: raggiunge il gateway anche col PATH avvelenato" \
  || bad "post-publish-poller: interprete risolto da PATH (W108)"

# ── fail-loud, per BRANCH ─────────────────────────────────────────────────────
# Run each shell sender with no gateway anywhere and demand a line in its log.
# The earlier version grep'd the file for a fail-loud phrase and survived having
# one of two such phrases deleted; this one can only pass if THIS branch speaks.
echo
echo "── senza gateway lasciano traccia (ramo eseguito)"
mv "$FAKE/nuzantara/scripts/tg_notify.py" "$FAKE/nuzantara/scripts/tg_notify.hidden"
shell_fail_loud() {
  local rel="$1" fn="$2" base harness logf
  base="$(basename "$rel")"
  logf="$FAKE/loud_${base}.log"
  : > "$logf"
  harness="$FAKE/loud_${base}.sh"
  {
    echo 'set -uo pipefail'
    echo "LOG_FILE=$logf"
    echo "LOG=$logf"
    _extra_env "$base"
    awk "/^${fn}\(\) \{/,/^\}/" "$REPO_ROOT/$rel"
    if [ "$fn" = "telegram_backup" ]; then
      echo "$fn 'probe:key' 'nessun gateway'"
    else
      echo "$fn 'nessun gateway'"
    fi
  } > "$harness"
  # stderr folded in: wr2_plist_watchdog reports to stderr, the others to a log.
  HOME="$FAKE" bash "$harness" >>"$logf" 2>>"$logf"
  if grep -qiE 'NOT sent|NO GATEWAY|not found' "$logf"; then
    ok "$base: dice di NON aver spedito"
  else
    bad "$base: muto quando il gateway manca — '$(tail -1 "$logf")'"
  fi
}
shell_fail_loud "infra/scripts/pg-organism-bridge-watchdog.sh" "telegram_backup"
shell_fail_loud "scripts/wr2_plist_watchdog.sh" "_telegram"
shell_fail_loud "scripts/cost_breaker_deadman.sh" "tg_alert"
shell_fail_loud "scripts/intake_review_reader_liveness.sh" "send_telegram"
shell_fail_loud "scripts/supervisor_liveness_watchdog.sh" "send_telegram"
shell_fail_loud "scripts/runtime-reconcile.sh" "alert"
mv "$FAKE/nuzantara/scripts/tg_notify.hidden" "$FAKE/nuzantara/scripts/tg_notify.py"

echo
echo "── il registro grandfathered si è RIDOTTO"
# Monotone register: it may only shrink. Two PRs shrinking it from different
# bases block each other with zero shared lines (W109b), which is why this
# migration ships as one sequential PR per batch and never in parallel.
count=$(python3 -c "import json;print(len(json.load(open('$REPO_ROOT/infra/tg-gateway/grandfathered.json'))['files']))")
if [ "$count" -le 146 ]; then ok "registro a $count voci (≤146)"; else bad "registro CRESCIUTO a $count"; fi

echo
echo "════ PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
