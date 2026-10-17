#!/usr/bin/env bash
# The flip runbook's carry-over command (scripts/localci/README.md) carries a pre-flip arm only when the merger (B42) would count its label:
# the arm is by admin/maintain, or by the write-role author of their own same-repo PR. The README line itself runs, against a fake gh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cmd=$(grep -m1 '^gh pr list .*--limit 500' "$ROOT/scripts/localci/README.md")
[ -n "$cmd" ] || { echo "FAIL: carry-over command not found in README"; exit 1; }
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin" "$work/scripts"
printf '#!/usr/bin/env bash\necho "CARRY $1"\n' > "$work/scripts/signal_merge_intent.sh"
chmod +x "$work/scripts/signal_merge_intent.sh"
cat > "$work/bin/gh" <<'GH'
#!/usr/bin/env bash
jq_arg() { while [ $# -gt 0 ]; do [ "$1" = --jq ] && { printf '%s' "$2"; return; }; shift; done; }
f=$(jq_arg "$@")
case "$1 $2" in
  "pr list") jq -r "$f" "$FIXTURE" ;;
  "api repos/Bali-Zero/Teman2/collaborators/"*)
    login=${2#repos/Bali-Zero/Teman2/collaborators/}; login=${login%/permission}
    [ "$login" = flaky ] && exit 1
    grep -m1 "^$login " "$ROLES" | cut -d' ' -f2 ;;
  *) exit 9 ;;
esac
GH
chmod +x "$work/bin/gh"
printf '%s\n' "boss admin" "maint maintain" "writer write" "Writer write" "triager triage" "reader read" "flaky write" > "$work/roles"
# pr NUMBER ARM_ACTOR AUTHOR [AUTHOR_IS_BOT FORK ARM_IS_BOT LABELS]
pr() { printf '{"number":%s,"labels":%s,"autoMergeRequest":{"enabledBy":{"login":"%s","is_bot":%s}},"author":{"login":"%s","is_bot":%s},"isCrossRepository":%s}' "$1" "${7:-[]}" "$2" "${6:-false}" "$3" "${4:-false}" "${5:-false}"; }
{
  echo '['
  pr 1 boss someone-else; echo ,                                  # admin arm on another's PR: carried (as before)
  pr 2 maint someone-else true true; echo ,                       # maintain arm, bot author, fork: carried (as before)
  pr 3 writer writer; echo ,                                      # INNOCENCE: write arm on its own same-repo PR: carried
  pr 4 writer someone-else; echo ,                                # write arm on someone else's PR: not carried
  pr 5 triager triager; echo ,                                    # triage role, own PR: not carried
  pr 6 reader reader; echo ,                                      # read role, own PR: not carried
  pr 7 writer writer false true; echo ,                           # write arm on its own PR from a fork: not carried
  pr 8 writer writer true; echo ,                                 # write arm, author is a bot: not carried
  pr 9 Writer writer; echo ,                                      # login differs only in case: not carried
  pr 10 flaky flaky; echo ,                                       # role unreadable: not carried
  pr 11 gh-actions gh-actions false false true; echo ,            # arm by a bot: not selected
  pr 12 writer writer false false false '[{"name":"localci:merge-shadow-ok"}]'; echo ,   # already labelled: not selected
  printf '{"number":13,"labels":[],"autoMergeRequest":null,"author":{"login":"writer","is_bot":false},"isCrossRepository":false}'
  echo ']'
} > "$work/fixture"
got=$(cd "$work" && FIXTURE="$work/fixture" ROLES="$work/roles" PATH="$work/bin:$PATH" bash -c "$cmd" 2>/dev/null | grep '^CARRY' | tr '\n' ' ')
[ "$got" = "CARRY 1 CARRY 2 CARRY 3 " ] || { echo "FAIL: expected 'CARRY 1 CARRY 2 CARRY 3 ', got '$got'"; exit 1; }
echo "PASS"
