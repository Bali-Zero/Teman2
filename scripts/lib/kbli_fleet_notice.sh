#!/usr/bin/env bash
# kbli_fleet_notice.sh — say, truthfully, whether the macOS KBLI Navigator fleet is
# carrying the canonical dataset. Sourced by scripts/sync_kbli_dataset.sh.
#
# WHY THIS IS A FUNCTION IN ITS OWN FILE (superscar #3, guard-over/under-match):
# it used to be eight inline lines that compared ONE file and, on that basis, printed
# "already matches canonical". Two different files are involved:
#
#   Resources/  — what the NEXT build will ship. build.sh refreshes it from canonical on
#                 every build, so it agrees with canonical the moment anyone builds.
#   the .app    — what a colleague opening the icon TODAY actually reads.
#
# Between a build and a deploy the first matches while the second is stale, and the old
# wording answered with the reassuring sentence over exactly that gap. Measured 2026-08-02:
# M5/Pro/Mini sat 20 codes behind, every one of them promising MORE foreign ownership than
# the truth (25200 arms and 30400 military vehicles at 100% vs 49%, 51101/51102 airlines
# likewise, 79122 Umrah/Hajj at 100% vs 0%) — while this notice had been reachable all
# along. A guard that can print the good news over a bad world is worse than no guard.
#
# It is also here so it can be TESTED: inline, it sat behind `-z "${CI:-}"` and a $HOME
# hardcode, i.e. it could never run in CI and never be pointed at a fake world.
# Corpus: scripts/tests/test_kbli_fleet_notice.py (guilt AND innocence).

# kbli_fleet_notice <canonical> <app_repo> <bundle_dir> [hostname]
# Prints a verdict. ALWAYS returns 0 — see the comment at the end.
kbli_fleet_notice() {
  local canonical="$1" app_repo="$2" bundle_dir="$3"
  local host="${4:-$(hostname -s 2>/dev/null || echo this machine)}"

  # No app repo on this machine (Pro, Mini, CI): nothing to say, and silence is correct —
  # there is no fleet copy here to be stale.
  [[ -d "$app_repo" ]] || return 0

  local app_copy="$app_repo/Resources/KBLI_2025_FINAL_CLEAN.json"
  local app_bundle="$bundle_dir/Contents/Resources/KBLI_2025_FINAL_CLEAN.json"
  local -a stale=()

  cmp -s "$canonical" "$app_copy" 2>/dev/null || stale+=("Resources/ (the next build's input)")
  if [[ -e "$app_bundle" ]]; then
    cmp -s "$canonical" "$app_bundle" 2>/dev/null || stale+=("the .app installed on $host")
  else
    # Absent is NOT aligned. A missing bundle must never read as "fine" (W84).
    stale+=("no .app on $host to check")
  fi

  echo ""
  if ((${#stale[@]})); then
    printf '⚠︎ native app fleet NOT aligned with the new canonical — stale: %s\n' "${stale[*]}"
    echo "   $app_repo/deploy/install-3mac.sh        # build + deploy M5/Pro/Mini + content probe"
    echo "   $app_repo/deploy/make-team-installer.sh # refresh the team zip"
    echo "   $app_repo/deploy/check-fleet.sh         # verify (read-only)"
  else
    echo "native app: Resources/ AND the .app on $host both match canonical."
  fi
  # Printed in BOTH branches on purpose: this function does no ssh, so it can never speak
  # for the other two machines or for the team zip. Only check-fleet.sh does.
  echo "   (Pro/Mini bundles + the team zip are NOT covered here — only check-fleet.sh speaks for them.)"

  # ALWAYS 0, even when stale. The kbli_filiera cure compilers call sync_kbli_dataset.sh
  # unconditionally under errexit, so a non-zero exit here would abort a DATA cure in order
  # to deliver a DEPLOY reminder. The 2026-08-02 ledger line proposed exiting non-zero;
  # reading the callers refuted it. Loud and honest, not fatal.
  return 0
}
