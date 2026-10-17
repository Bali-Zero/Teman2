#!/usr/bin/env bash
# mini_disk_janitor.sh — bounded, allowlisted daily disk hygiene for the Mini (payload of organ mini.disk_janitor).
#
# Why (measured 2026-10-17): the self-hosted runner container zero-runner-1 (Colima Docker VM, overlay
# disk fixed at 59G) hit 100% twice (2026-10-14 and 2026-10-17): /home/runner/.cache/pip 25G,
# .cache/uv 6.6G, /tmp 4.4G (pytest-of-runner, pip-unpack-*), _work/_tool 8G. Backend deploys died at
# "Set up job" with "No space left on device" and nothing alerted. Space freed INSIDE the VM does not
# return to the host until `fstrim` runs (36.9 GiB came back that way), and the host Data volume itself
# sat at 97% with ~/Library/Caches holding 11G. Nothing pruned the runner, trimmed the VM or watched
# the Mini host disk; Pro's organs (pro.disk_janitor, pro.janitor, pro.disk_floor) are Pro-only.
#
# Steps (each writes one receipt entry {step,status,reason,freed_kb}; freed_kb is the df -Pk delta on the
# Data volume across the step, never du):
#   runner_cache  zero-runner-1, ONLY while no Runner.Worker is running (polled up to
#                 MINI_DISK_JANITOR_BUSY_WAIT_MIN, then skipped runner-busy; the idle test is repeated
#                 inside the exec script itself). Removes exactly /home/runner/.cache/pip,
#                 /home/runner/.cache/uv, /tmp/pytest-of-runner, /tmp/pip-unpack-* and /tmp/tmp* older
#                 than a day (all maxdepth 1 / mindepth 1). `_work` is never touched (no exec script
#                 mentions it); never docker rm / stop / restart / volumes. The in-exec idle re-check
#                 fails CLOSED: ps failing or printing nothing -> exit 74 (step error idle-recheck-failed,
#                 nothing deleted). `docker inspect` failing for any reason other than "no such object"
#                 is a step error (inspect-failed) and floor level unknown, never "not running".
#                 Race: inside each exec script, after the idle re-check, every target is first renamed
#                 (atomic mv, same filesystem) to a `.janitor-trash-*` sibling and only then deleted, so a
#                 job that starts mid-run finds an empty cache that pip/uv/setup actions recreate. The
#                 residual window is the rename instant, not the delete. Leftover `.janitor-trash-*` from
#                 an interrupted run are swept at the start of every script (maxdepth 1, exact prefix).
#   docker        `docker image prune -f` and `docker builder prune -f` (dangling images, build cache).
#                 Never -a, never volume / container / system prune.
#   vm_trim       `colima ssh -- sudo fstrim -av`: hands the freed guest blocks back to the host.
#   user_caches   ALLOWLIST (fail-closed): regular files older than CACHE_DAYS inside ONLY the top-level
#                 names in MINI_DISK_JANITOR_CACHE_ALLOW (default: Homebrew Google Codex ollama pip
#                 go-build com.exafunction.windsurf.ShipIt) under the physical $HOME/Library/Caches;
#                 find -P -xdev, symlinks never followed, empty subdirectories removed afterwards.
#                 An unknown entry is never touched. A listed name that is path-like, "."/"..",
#                 com.apple.*, or a symlink is refused (step error, nothing deleted for it); an absent
#                 name is skipped silently. Counts and bytes are logged, never names.
#   npm           `npm cache verify` (garbage-collects its own cache).
#   uv            `uv cache prune` (a timeout means another uv holds the lock: skipped uv-lock-busy).
#   floor         receptor, always runs (also in dry-run): host free GiB + runner container / use%
#                 -> level ok | warning | critical | unknown. Apply mode notifies via tg_notify: warning ->
#                 tier digest (key mini-disk-warn-<host|runner>), critical -> tier p0 (key mini-disk-<host|runner>).
#                 A failed host df -> floor error + level unknown; a running container whose df probe fails ->
#                 floor error + level unknown; a container that is not running -> runner_pct na (never 0)
#                 and the level comes from the host alone.
#
# Deliberately absent: `brew cleanup` / `brew autoremove` / any brew command (a brew autoremove killed
# node on this Mini, lesson 2026-09-26; the Homebrew download cache is covered by user_caches), and
# ms-playwright* (installed browser binaries with old mtimes, not a regenerating cache: a manual wipe
# of ~/Library/Caches on 2026-10-17 deleted it and broke the production journey-sentinel until
# `npx playwright install chromium` was re-run), any cache entry not in the allowlist, and
# anything under ~/pro-offload, ~/icloud-*, ~/Desktop, ~/Downloads, ~/.ollama, ~/.cache/huggingface,
# `_work/_tool` (a job mid tool-setup breaks harder than one losing a pip cache, and recreating it from
# `docker exec` would give it the exec user's uid/umask, not the Runner.Worker's), OSINT data, Docker volumes, git worktrees (the broker owns them) and backups. `uv cache clean` is
# never used either (prune only).
#
# DRY-RUN by default: deletes nothing and runs no mutating command, but it DOES append its receipt to
# the journal (that is what makes a dry-run auditable). `--apply` acts. Every external command runs
# through bounded() (a real deadline). Exit 0 when no step errored, 1 otherwise; the last stdout line is
# `level=ok|warning|critical` for the wrapper (the line before it: `summary ...`). Test:
# scripts/tests/test_mini_disk_janitor.sh. /bin/bash 3.2 compatible.
set -uo pipefail

APPLY=false
[ "${1:-}" = "--apply" ] && APPLY=true
MODE=dry-run; $APPLY && MODE=apply

H="${HOME:-}"
while [ "${H%/}" != "$H" ]; do H="${H%/}"; done   # "/" becomes "" and is refused by user_caches
RUNNER="${MINI_DISK_JANITOR_RUNNER:-zero-runner-1}"
BUSY_WAIT_MIN="${MINI_DISK_JANITOR_BUSY_WAIT_MIN:-45}"
BUSY_POLL_S="${MINI_DISK_JANITOR_BUSY_POLL_S:-60}"
CACHE_DAYS="${MINI_DISK_JANITOR_CACHE_DAYS:-14}"
CACHE_ALLOW="${MINI_DISK_JANITOR_CACHE_ALLOW:-Homebrew Google Codex ollama pip go-build com.exafunction.windsurf.ShipIt}"
HOST_WARN_GB="${MINI_DISK_JANITOR_HOST_WARN_GB:-40}"
HOST_CRIT_GB="${MINI_DISK_JANITOR_HOST_CRIT_GB:-20}"
RUNNER_WARN_PCT="${MINI_DISK_JANITOR_RUNNER_WARN_PCT:-85}"
RUNNER_CRIT_PCT="${MINI_DISK_JANITOR_RUNNER_CRIT_PCT:-95}"
EXEC_TIMEOUT="${MINI_DISK_JANITOR_EXEC_TIMEOUT:-900}"
PROBE_TIMEOUT="${MINI_DISK_JANITOR_PROBE_TIMEOUT:-60}"
TRIM_TIMEOUT="${MINI_DISK_JANITOR_TRIM_TIMEOUT:-600}"
CACHE_TOOL_TIMEOUT="${MINI_DISK_JANITOR_TOOL_TIMEOUT:-300}"
REPO="${MINI_DISK_JANITOR_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
NOTIFY="${MINI_DISK_JANITOR_NOTIFY:-$REPO/scripts/tg_notify.py}"
DF_PATH="${MINI_DISK_JANITOR_DF_PATH:-/System/Volumes/Data}"; [ -d "$DF_PATH" ] || DF_PATH=/
JOURNAL="${MINI_DISK_JANITOR_JOURNAL:-}"
JOURNAL_REFUSED=false
if [ -z "$JOURNAL" ]; then
  if [ -n "$H" ]; then JOURNAL="$H/logs/mini-disk-janitor.receipts.jsonl"; else JOURNAL_REFUSED=true; fi   # HOME empty or /: never write /logs
fi

log() { echo "[$(date +%Y-%m-%dT%H:%M:%S%z)] mini-disk-janitor[$MODE] $*" >&2; }
for knob in BUSY_WAIT_MIN BUSY_POLL_S CACHE_DAYS HOST_WARN_GB HOST_CRIT_GB RUNNER_WARN_PCT \
            RUNNER_CRIT_PCT EXEC_TIMEOUT PROBE_TIMEOUT TRIM_TIMEOUT CACHE_TOOL_TIMEOUT; do
  case "${!knob}" in ''|*[!0-9]*) log "REFUSE: MINI_DISK_JANITOR_$knob must be a non-negative integer"; exit 2 ;; esac
done

# bounded SECONDS CMD...: a real deadline (no coreutils timeout on stock macOS). The child gets its own
# process group and /dev/null stdin; at the deadline the group gets TERM, then KILL after 2 s.
# rc 124 = timed out, otherwise the command's rc.
bounded() {
  local s=$1; shift
  perl -e 'use POSIX ":sys_wait_h"; my $t = shift; my $p = fork; defined $p or exit 127;
    if (!$p) { setpgrp(0, 0); open STDIN, "<", "/dev/null"; exec { $ARGV[0] } @ARGV or exit 127 }
    my ($end, $r, $to) = (time + $t, 0, 0);
    until (($r = waitpid($p, WNOHANG)) != 0) {
      if (!$to && time >= $end) { $to = 1; kill "TERM", -$p; kill "TERM", $p; $end = time + 2 }
      elsif ($to && time >= $end) { kill "KILL", -$p; kill "KILL", $p; $r = waitpid($p, 0); last }
      select(undef, undef, undef, 0.1);
    }
    kill "KILL", -$p if $to;
    exit 124 if $to; exit 127 if $r < 0;
    exit($? & 127 ? 128 + ($? & 127) : $? >> 8);' "$s" "$@"
}

host_free_kb() { df -Pk "$DF_PATH" 2>/dev/null | awk 'NR==2{print $4}'; }
ERRORS=0; STEPS=""; S_KB0=""; BUSY=0
step_begin() { S_KB0=$(host_free_kb); }
step_end() { # $1 step  $2 done|dry-run|skipped|error  $3 reason (never a path or a name)  $4 extra json fields
  local k1 freed=0; k1=$(host_free_kb)
  if $APPLY && [ -n "$S_KB0" ] && [ -n "$k1" ]; then freed=$((k1 - S_KB0)); fi
  [ "$2" = error ] && ERRORS=$((ERRORS + 1))
  STEPS="$STEPS${STEPS:+,}{\"step\":\"$1\",\"status\":\"$2\",\"reason\":\"${3:-}\",\"freed_kb\":$freed${4:+,$4}}"
  log "$1: $2${3:+ ($3)} freed_kb=$freed"
}

# Container df: "pct avail_kb" of the runner's / (empty when unreadable).
ctr_df() { bounded "$PROBE_TIMEOUT" docker exec "$RUNNER" df -Pk / 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5, $4}'; }
# 0 = Runner.Worker running (busy), 1 = idle, 2 = probe failed. Bracket: grep never matches itself.
PROBE_SCRIPT='out=$(ps -eo args 2>/dev/null) || exit 2; printf "%s\n" "$out" | grep -q "[R]unner\.Worker"'
runner_busy() {
  bounded "$PROBE_TIMEOUT" docker exec "$RUNNER" sh -c "$PROBE_SCRIPT" >/dev/null 2>&1; rc=$?
  case "$rc" in 0) return 0 ;; 1) return 1 ;; *) return 2 ;; esac
}
HAVE_DOCKER=false; command -v docker >/dev/null 2>&1 && HAVE_DOCKER=true
RUNNING=false; INSPECT=none   # none | running | stopped | absent | failed
if $HAVE_DOCKER; then
  ins=$(bounded "$PROBE_TIMEOUT" docker inspect -f '{{.State.Running}}' "$RUNNER" 2>&1); irc=$?
  if [ "$irc" -eq 0 ]; then
    if [ "$ins" = "true" ]; then RUNNING=true; INSPECT=running; else INSPECT=stopped; fi
  elif printf '%s' "$ins" | grep -qiE 'no such (object|container)'; then INSPECT=absent
  else INSPECT=failed; fi   # daemon down, timeout, permission: never read as "not running"
fi

KB_BEFORE=$(host_free_kb); PCT_BEFORE=""; $RUNNING && PCT_BEFORE=$(ctr_df | awk '{print $1}')

# ── runner_cache ────────────────────────────────────────────────────────────
# The exec script re-checks idleness itself: the runner can pick up a job between probe and rm.
SWEEP='find /home/runner/.cache /tmp -mindepth 1 -maxdepth 1 -name ".janitor-trash-*" -exec rm -rf {} + 2>/dev/null'
IDLE_CHECK='o=$(ps -eo args 2>/dev/null) || exit 74
[ -n "$o" ] || exit 74
printf "%s\n" "$o" | grep -q "[R]unner\.Worker" && exit 75'
CLEAN_SCRIPT="$IDLE_CHECK"'
'"$SWEEP"'
mv /home/runner/.cache/pip /home/runner/.cache/.janitor-trash-pip-$$ 2>/dev/null
mv /home/runner/.cache/uv /home/runner/.cache/.janitor-trash-uv-$$ 2>/dev/null
mv /tmp/pytest-of-runner /tmp/.janitor-trash-pytest-$$ 2>/dev/null
find /tmp -mindepth 1 -maxdepth 1 \( -name "pip-unpack-*" -o \( -name "tmp*" -mtime +0 \) \) 2>/dev/null | while IFS= read -r e; do
  mv "$e" "/tmp/.janitor-trash-e-$$-${e##*/}" 2>/dev/null
done
'"$SWEEP"'
exit 0'
step_begin
if ! $HAVE_DOCKER; then step_end runner_cache skipped docker-absent
elif [ "$INSPECT" = failed ]; then step_end runner_cache error inspect-failed
elif ! $RUNNING; then step_end runner_cache skipped container-not-running
else
  waited=0; limit=$((BUSY_WAIT_MIN * 60)); idle=false; pr=2
  while :; do
    runner_busy; pr=$?
    [ "$pr" -eq 1 ] && { idle=true; break; }
    [ "$pr" -eq 2 ] && break
    { $APPLY && [ "$waited" -lt "$limit" ]; } || break
    sleep "$BUSY_POLL_S"; waited=$((waited + BUSY_POLL_S))
  done
  if [ "$pr" -eq 2 ]; then step_end runner_cache error idle-probe-failed
  elif ! $idle; then BUSY=1; step_end runner_cache skipped runner-busy
  elif ! $APPLY; then step_end runner_cache dry-run idle
  else
    bounded "$EXEC_TIMEOUT" docker exec "$RUNNER" sh -c "$CLEAN_SCRIPT" >/dev/null 2>&1; rc=$?
    if [ "$rc" -eq 75 ]; then BUSY=1; step_end runner_cache skipped runner-busy
    elif [ "$rc" -eq 74 ]; then step_end runner_cache error idle-recheck-failed
    elif [ "$rc" -ne 0 ]; then step_end runner_cache error "$([ "$rc" -eq 124 ] && echo exec-timeout || echo exec-failed)"
    else step_end runner_cache "done"; fi
  fi
fi

# ── docker (dangling images + build cache only) ─────────────────────────────
step_begin
if ! $HAVE_DOCKER; then step_end docker skipped docker-absent
elif ! $APPLY; then step_end docker dry-run
else
  bounded "$EXEC_TIMEOUT" docker image prune -f >/dev/null 2>&1; r1=$?
  bounded "$EXEC_TIMEOUT" docker builder prune -f >/dev/null 2>&1; r2=$?
  if [ "$r1" -eq 0 ] && [ "$r2" -eq 0 ]; then step_end docker "done"; else step_end docker error prune-failed; fi
fi

# ── vm_trim ─────────────────────────────────────────────────────────────────
step_begin
if ! command -v colima >/dev/null 2>&1; then step_end vm_trim skipped colima-absent
elif ! $APPLY; then step_end vm_trim dry-run
else
  out=$(bounded "$TRIM_TIMEOUT" colima ssh -- sudo fstrim -av 2>&1); rc=$?
  trimmed=$(printf '%s\n' "$out" | sed -n 's/.*(\([0-9][0-9]*\) bytes).*/\1/p' | awk '{s+=$1} END{print s+0}')
  if [ "$rc" -eq 0 ]; then step_end vm_trim "done" "" "\"trimmed_bytes\":$trimmed"
  else step_end vm_trim error "$([ "$rc" -eq 124 ] && echo fstrim-timeout || echo fstrim-failed)" "\"trimmed_bytes\":$trimmed"; fi
fi

# ── user_caches ─────────────────────────────────────────────────────────────
user_caches() {
  local C phys physhome entry name f n=0 bytes=0 sz refused=0
  [ -n "$H" ] || { step_end user_caches error home-unsafe; return; }
  physhome=$(cd "$H" 2>/dev/null && pwd -P)
  { [ -n "$physhome" ] && [ "$physhome" != "/" ]; } || { step_end user_caches error home-unsafe; return; }
  C="$H/Library/Caches"
  [ ! -L "$C" ] || { step_end user_caches error caches-symlink; return; }
  [ -d "$C" ] || { step_end user_caches skipped no-caches; return; }
  phys=$(cd "$C" 2>/dev/null && pwd -P)
  case "$phys" in "$physhome"/*) : ;; *) step_end user_caches error caches-outside-home; return ;; esac
  set -f   # allowlist names are literal, never globs
  for name in $CACHE_ALLOW; do
    case "$name" in
      .|..|*/*|com.apple.*) refused=$((refused + 1)); log "user_caches: allowlist entry refused (reserved or path-like)"; continue ;;
    esac
    entry="$phys/$name"
    [ -L "$entry" ] && { refused=$((refused + 1)); log "user_caches: allowlist entry refused (symlink)"; continue; }
    [ -d "$entry" ] || continue   # absent names are fine
    while IFS= read -r -d '' f; do
      sz=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f" 2>/dev/null); case "$sz" in ''|*[!0-9]*) sz=0 ;; esac   # GNU first: BSD stat has no -c, GNU stat -f means filesystem
      n=$((n + 1)); bytes=$((bytes + sz))
      $APPLY && rm -f -- "$f" 2>/dev/null
    done < <(find -P "$entry" -xdev -type f -mtime +"$CACHE_DAYS" -print0 2>/dev/null)
    if $APPLY; then find -P "$entry" -xdev -mindepth 1 -type d -empty -delete 2>/dev/null; fi
  done
  set +f
  log "user_caches: files=$n bytes=$bytes"
  if [ "$refused" -gt 0 ]; then step_end user_caches error allow-refused "\"files\":$n,\"bytes\":$bytes,\"refused\":$refused"
  elif $APPLY; then step_end user_caches "done" "" "\"files\":$n,\"bytes\":$bytes"
  else step_end user_caches dry-run "" "\"files\":$n,\"bytes\":$bytes"; fi
}
step_begin; user_caches

# ── npm / uv ────────────────────────────────────────────────────────────────
step_begin
if ! command -v npm >/dev/null 2>&1; then step_end npm skipped npm-absent
elif ! $APPLY; then step_end npm dry-run
else
  bounded "$CACHE_TOOL_TIMEOUT" npm cache verify >/dev/null 2>&1; rc=$?
  if [ "$rc" -eq 0 ]; then step_end npm "done"; else step_end npm error "$([ "$rc" -eq 124 ] && echo npm-timeout || echo npm-failed)"; fi
fi
step_begin
if ! command -v uv >/dev/null 2>&1; then step_end uv skipped uv-absent
elif ! $APPLY; then step_end uv dry-run
else
  bounded "$CACHE_TOOL_TIMEOUT" uv cache prune >/dev/null 2>&1; rc=$?
  if [ "$rc" -eq 0 ]; then step_end uv "done"
  elif [ "$rc" -eq 124 ]; then step_end uv skipped uv-lock-busy
  else step_end uv error uv-failed; fi
fi

# ── floor receptor ──────────────────────────────────────────────────────────
KB_AFTER=$(host_free_kb); PCT_AFTER=""; $RUNNING && PCT_AFTER=$(ctr_df | awk '{print $1}')
case "$KB_AFTER" in ''|*[!0-9]*) KB_AFTER="" ;; esac
case "$PCT_AFTER" in ''|*[!0-9]*) PCT_AFTER="" ;; esac
case "$KB_BEFORE" in ''|*[!0-9]*) KB_BEFORE="" ;; esac
GB_BEFORE=$(( ${KB_BEFORE:-0} / 1048576 )); GB_AFTER=$(( ${KB_AFTER:-0} / 1048576 ))
HOST_LV=ok; RUN_LV=ok; FLOOR_ERR=""
if [ -z "$KB_AFTER" ]; then HOST_LV=unknown; FLOOR_ERR=host-df-failed
elif [ "$KB_AFTER" -lt $((HOST_CRIT_GB * 1048576)) ]; then HOST_LV=critical
elif [ "$KB_AFTER" -lt $((HOST_WARN_GB * 1048576)) ]; then HOST_LV=warning; fi
if [ "$INSPECT" = failed ]; then RUN_LV=unknown; FLOOR_ERR="${FLOOR_ERR:-inspect-failed}"
elif $RUNNING; then   # a stopped or absent container contributes nothing: runner_pct stays na, never 0
  if [ -z "$PCT_AFTER" ]; then RUN_LV=unknown; FLOOR_ERR="${FLOOR_ERR:-runner-df-failed}"
  elif [ "$PCT_AFTER" -ge "$RUNNER_CRIT_PCT" ]; then RUN_LV=critical
  elif [ "$PCT_AFTER" -ge "$RUNNER_WARN_PCT" ]; then RUN_LV=warning; fi
fi
if [ "$HOST_LV" = critical ] || [ "$RUN_LV" = critical ]; then LEVEL=critical
elif [ "$HOST_LV" = unknown ] || [ "$RUN_LV" = unknown ]; then LEVEL=unknown
elif [ "$HOST_LV" = warning ] || [ "$RUN_LV" = warning ]; then LEVEL=warning
else LEVEL=ok; fi
if [ -n "$FLOOR_ERR" ]; then ERRORS=$((ERRORS + 1)); FSTATUS=error; else FSTATUS="done"; fi
STEPS="$STEPS${STEPS:+,}{\"step\":\"floor\",\"status\":\"$FSTATUS\",\"reason\":\"${FLOOR_ERR:-$LEVEL}\",\"freed_kb\":0}"
log "floor: level=$LEVEL host_free_gb=$GB_AFTER runner_pct=${PCT_AFTER:-na}"

notify() { # $1 tier  $2 dedup-key  $3 message; never fails the run
  bounded 60 python3 "$NOTIFY" --tier "$1" --source mini.disk_janitor --dedup-key "$2" -- "$3" >/dev/null 2>&1 \
    || log "notify FAILED (ignored) key=$2"
}
if $APPLY; then
  case "$HOST_LV" in
    critical) notify p0 mini-disk-host "mini.disk_janitor: Mini host free ${GB_AFTER} GiB is below the critical ${HOST_CRIT_GB} GiB ceiling" ;;
    warning) notify digest mini-disk-warn-host "mini.disk_janitor: Mini host free ${GB_AFTER} GiB is below the ${HOST_WARN_GB} GiB warning line" ;;
  esac
  case "$RUN_LV" in
    critical) notify p0 mini-disk-runner "mini.disk_janitor: runner container disk ${PCT_AFTER}% is at or above the critical ${RUNNER_CRIT_PCT}% ceiling" ;;
    warning) notify digest mini-disk-warn-runner "mini.disk_janitor: runner container disk ${PCT_AFTER}% is at or above the ${RUNNER_WARN_PCT}% warning line" ;;
  esac
fi

# ── receipt ─────────────────────────────────────────────────────────────────
if $JOURNAL_REFUSED; then
  ERRORS=$((ERRORS + 1)); log "receipt REFUSED: HOME is empty or / and MINI_DISK_JANITOR_JOURNAL is not set (no default journal path)"
else
  mkdir -p "$(dirname "$JOURNAL")" 2>/dev/null
  printf '{"ts":"%s","mode":"%s","host":"%s","steps":[%s],"host_free_gb_before":%s,"host_free_gb_after":%s,"runner_pct_before":%s,"runner_pct_after":%s,"errors":%s,"level":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$(hostname -s)" "$STEPS" "$GB_BEFORE" "$GB_AFTER" \
    "${PCT_BEFORE:-null}" "${PCT_AFTER:-null}" "$ERRORS" "$LEVEL" >> "$JOURNAL" \
    || { ERRORS=$((ERRORS + 1)); log "receipt append FAILED"; }
fi
echo "summary freed_kb=$(( ${KB_AFTER:-0} - ${KB_BEFORE:-0} )) host_free_gb=$GB_AFTER runner_pct=${PCT_AFTER:-na} busy=$BUSY errors=$ERRORS"
echo "level=$LEVEL"
[ "$ERRORS" -eq 0 ]
