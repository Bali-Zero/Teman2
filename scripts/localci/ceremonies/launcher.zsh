#!/bin/zsh -f
# LocalCI ceremony launcher. Invoke under env -i as zero-ops with M and NAME.
# Body contract: $1 is verified M; $2 is the work directory; cwd is $2;
# $2/w.git holds M's objects. The body reads repository code only with
#   "$2/g" cat-file blob "${1}:path"
# and never runs bare git or reads FETCH_HEAD. Its supplied environment is
# exactly HOME, PATH and LC_ALL=C (zsh may materialize special parameters).
# The root-owned 0444 journal is replaced only by:
#   /usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 SOURCE JOURNAL
# Exit 0: success; 64: argv/name; 65: trust/config/history/internal refusal;
# 69: fetch failure; 70: fetch timeout; any other nonzero body status propagates.
# BSD find's -perm +0022 means either group or other write. With -exec {} +,
# the primary remains true; a failed link batch is carried by find's exit status.

setopt nounset pipefail
unsetopt BG_NICE
umask 077

(( $# == 2 )) || exit 64
M=$1; NAME=$2
[[ ${#M} -eq 40 && "$M" != *[^0-9a-f]* ]] || exit 64

BASE=/Users/zero-ops/ceremony
CLT=/Library/Developer/CommandLineTools
GIT="$CLT/usr/bin/git"
case "$NAME" in
  C3-bootstrap|C3) REMOTE='https://github.com/Bali-Zero/Teman2.git'; fetch_ref=main; transport=(-c protocol.allow=never -c protocol.https.allow=always); transport_expected=$'command line:\tprotocol.https.allow=always' ;;
  C12) REMOTE='file:///Users/nuzantara/.nuzantara-pilots/local-ci/merger/repo.git'; fetch_ref=refs/merger/base; transport=(-c protocol.allow=never -c protocol.file.allow=always); transport_expected=$'command line:\tprotocol.file.allow=always' ;;
  *) exit 64 ;;
esac
[[ ! -e /etc/zshenv && ! -L /etc/zshenv ]] || exit 65

TS=$(/bin/date -u +%Y%m%dT%H%M%SZ)
d="$BASE/$TS.$$"
cfg=(-c core.hooksPath=/dev/null -c core.fsmonitor=false -c maintenance.auto=false)
gcmd=(/usr/bin/env -i HOME="$d" PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 "$GIT" "${cfg[@]}" "${transport[@]}")
g() { "${gcmd[@]}" "$@"; }

link_ok='CLT=/Library/Developer/CommandLineTools; STOP=/; for p; do r=$(/bin/realpath "$p") || exit 1; case "$r" in /System/Volumes/Data|/System/Volumes/Data/*) exit 1 ;; "$CLT"|"$CLT"/*|/usr/bin|/usr/bin/*|/usr/lib|/usr/lib/*|/usr/libexec|/usr/libexec/*|/usr/share|/usr/share/*|/System|/System/*) ;; *) exit 1 ;; esac; q=$r; while true; do [[ -z "$(/usr/bin/find "$q" -prune \( ! -user root -o -perm +0022 -o -acl \) -print)" ]] || exit 1; [[ "$q" == "$STOP" ]] && break; [[ "$q" == / ]] && exit 1; q=${q:h}; done; done'
trust=(/ /Library /Library/Developer "$CLT" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" /bin /usr /usr/bin /System /usr/local /usr/local/localci /usr/local/localci/bin /usr/local/localci/bin/ceremony-launcher.zsh)
bad=$({ /usr/bin/find "${trust[@]}" -prune \( -type l \( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \) -o ! -type l \( ! -user root -o -perm +0022 -o -acl \) \) -print || exit 65; /usr/bin/find "$GIT" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core" /bin/realpath \( -type l \( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \) -o ! -type l \( ! -user root -o -perm +0022 -o -acl \) \) -print || exit 65; }) || exit 65
[[ -z "$bad" ]] || exit 65

/bin/mkdir -m 0700 "$d" || exit 65
[[ -z "$(/usr/bin/find "$d" ! -path "$d" -print -quit)" ]] || exit 65
finish() {
  local rc=$?
  trap - EXIT
  if [[ -d "$d" && ! -L "$d" ]]; then
    /usr/bin/find "$d" -mindepth 1 -maxdepth 1 -exec /bin/rm -rf {} + 2>/dev/null
    /usr/bin/printf 'M=%s\nname=%s\nrc=%d\n' "$M" "$NAME" "$rc" >"$d/receipt" 2>/dev/null
    /bin/chmod 0400 "$d/receipt" 2>/dev/null
  fi
  exit "$rc"
}
trap finish EXIT

g init --bare --template= "$d/w.git" || exit 65
expected=$'file:config\tcore.repositoryformatversion=0\nfile:config\tcore.filemode=true\nfile:config\tcore.bare=true\nfile:config\tcore.ignorecase=true\nfile:config\tcore.precomposeunicode=true\ncommand line:\tcore.hookspath=/dev/null\ncommand line:\tcore.fsmonitor=false\ncommand line:\tmaintenance.auto=false\ncommand line:\tprotocol.allow=never\n'"$transport_expected"
actual=$(g -C "$d/w.git" config --list --show-origin | /usr/bin/sort)
[[ "$actual" == "$(/usr/bin/printf '%s\n' "$expected" | /usr/bin/sort)" ]] || exit 65

watch_fetch() {
  zmodload zsh/zselect || return 65
  local pid=$1
  integer ticks=0
  while kill -0 "$pid" 2>/dev/null && (( ticks < 600 )); do zselect -t 100; (( ++ticks )); done
  kill -0 "$pid" 2>/dev/null || return 0
  kill -TERM "$pid" 2>/dev/null
  zselect -t 500
  kill -KILL "$pid" 2>/dev/null
  return 70
}
fetch_with_watchdog() {
  local fetch_pid watch_pid fetch_rc watch_rc
  ( exec "${gcmd[@]}" -C "$d/w.git" fetch --no-tags "$REMOTE" "$fetch_ref" ) & fetch_pid=$!
  watch_fetch "$fetch_pid" & watch_pid=$!
  wait "$watch_pid"; watch_rc=$?
  (( watch_rc == 0 )) || kill -TERM "$fetch_pid" 2>/dev/null
  wait "$fetch_pid"; fetch_rc=$?
  (( watch_rc == 70 )) && return 70
  (( watch_rc == 0 )) || return 65
  (( fetch_rc == 0 )) || return 69
  return 0
}
fetch_with_watchdog; fetch_rc=$?
(( fetch_rc == 0 )) || exit "$fetch_rc"

g -C "$d/w.git" cat-file -e "${M}^{commit}" || exit 65
g -C "$d/w.git" merge-base --is-ancestor "$M" FETCH_HEAD || exit 65
journal="$BASE/last-main"
if [[ -e "$journal" || -L "$journal" ]]; then
  [[ -f "$journal" && ! -L "$journal" && -r "$journal" ]] || exit 65
  PREV_M=$(/bin/cat "$journal")
  [[ ${#PREV_M} -eq 40 && "$PREV_M" != *[^0-9a-f]* ]] || exit 65
  g -C "$d/w.git" merge-base --is-ancestor "$PREV_M" "$M" || exit 65
else
  [[ "$NAME" == C3-bootstrap ]] || exit 65
fi

/usr/bin/printf '%s\n' '#!/bin/zsh -f' "exec /usr/bin/env -i HOME=\"$d\" PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 /Library/Developer/CommandLineTools/usr/bin/git -c core.hooksPath=/dev/null -c core.fsmonitor=false -c maintenance.auto=false -c protocol.allow=never -C \"$d/w.git\" \"\$@\"" >"$d/g" || exit 65
/bin/chmod 0500 "$d/g" || exit 65
g -C "$d/w.git" cat-file blob "${M}:docs/ceremonies/${NAME}.zsh" >"$d/ceremony.zsh" || exit 65
/bin/chmod 0500 "$d/ceremony.zsh" || exit 65
( cd "$d" || exit 65; /usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C /bin/zsh -f "$d/ceremony.zsh" "$M" "$d" )
ceremony_rc=$?
(( ceremony_rc == 0 )) || exit "$ceremony_rc"
/usr/bin/printf '%s\n' "$M" >"$d/last-main.new" || exit 65
/bin/chmod 0400 "$d/last-main.new" || exit 65
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 "$d/last-main.new" "$journal" || exit 65
