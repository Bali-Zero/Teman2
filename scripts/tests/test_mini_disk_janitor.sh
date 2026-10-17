#!/bin/bash
# test_mini_disk_janitor.sh — corpus for organ mini.disk_janitor (payload scripts/ops/mini_disk_janitor.sh +
# wrapper infra/launchagents/wrappers/mini-disk-janitor.sh). Everything runs against a fake HOME with stub
# docker/colima/npm/uv/python3(notifier)/df/hostname that RECORD their argv; no real tool is reached.
# MJ_PAYLOAD / MJ_WRAPPER override the files under test (the mutant harness points them at mutated copies).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD="${MJ_PAYLOAD:-$HERE/scripts/ops/mini_disk_janitor.sh}"
WRAPPER="${MJ_WRAPPER:-$HERE/infra/launchagents/wrappers/mini-disk-janitor.sh}"
REAL_PY="$(command -v python3)"
SYS_PATH="/usr/bin:/bin:/usr/sbin:/sbin"
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
no() { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
ROOT_ALL="$(mktemp -d)"; trap 'rm -rf "$ROOT_ALL"' EXIT
OLD=202001010000

build() { # fresh fake world: $ROOT, $H (HOME), $FB (stub dir), $FX (fixtures)
  ROOT="$(mktemp -d "$ROOT_ALL/w.XXXXXX")"; H="$ROOT/home"; FB="$ROOT/bin"; FX="$ROOT/fx"; OUTSIDE="$ROOT/outside"
  export MJ_ROOT="$ROOT" MJ_FX="$FX"
  mkdir -p "$H/Library/Caches" "$H/logs" "$FB" "$FX" "$ROOT/scripts" "$OUTSIDE/a" "$OUTSIDE/b"
  echo 60000000 > "$FX/host_kb"       # ~57 GiB free: level ok
  echo 40 > "$FX/ctr_pct"; echo 20000000 > "$FX/ctr_kb"
  echo "/: 5 GiB (5368709120 bytes) trimmed on /dev/vda1" > "$FX/fstrim"
  cat > "$FB/docker" <<'STUB'
#!/bin/bash
{ printf 'CALL'; printf ' [%s]' "$@"; printf '\n'; } | tr '\n' ' ' >> "$MJ_ROOT/docker.log"; echo >> "$MJ_ROOT/docker.log"
case "$1" in
  inspect)
    case "$(cat "$MJ_FX/inspect_mode" 2>/dev/null)" in
      absent) echo "Error: No such object: zero-runner-1" >&2; exit 1 ;;
      fail) echo "Cannot connect to the Docker daemon" >&2; exit 1 ;;
    esac
    cat "$MJ_FX/running" 2>/dev/null || echo true; exit 0 ;;
  exec)
    if [ "$3" = df ]; then
      [ -e "$MJ_FX/ctr_fail" ] && exit 1
      printf 'Filesystem 1024-blocks Used Available Capacity Mounted\noverlay 61000000 1 %s %s%% /\n' "$(cat "$MJ_FX/ctr_kb")" "$(cat "$MJ_FX/ctr_pct")"; exit 0
    fi
    if [ "$3" = sh ] && [ "$4" = -c ]; then
      case "$5" in
        *"exit 75"*) n=$(ls "$MJ_ROOT/scripts" | wc -l | tr -d ' '); printf '%s' "$5" > "$MJ_ROOT/scripts/$n.sh"
                     exit "$(cat "$MJ_FX/exec_rc" 2>/dev/null || echo 0)" ;;
        *"exit 2"*)  [ -e "$MJ_FX/busy" ] && exit 0; exit 1 ;;
      esac
    fi
    exit 0 ;;
  *) exit 0 ;;
esac
STUB
  cat > "$FB/colima" <<'STUB'
#!/bin/bash
echo "CALL $*" >> "$MJ_ROOT/colima.log"; cat "$MJ_FX/fstrim"; exit "$(cat "$MJ_FX/colima_rc" 2>/dev/null || echo 0)"
STUB
  cat > "$FB/npm" <<'STUB'
#!/bin/bash
echo "CALL $*" >> "$MJ_ROOT/npm.log"; exit 0
STUB
  cat > "$FB/uv" <<'STUB'
#!/bin/bash
echo "CALL $*" >> "$MJ_ROOT/uv.log"; [ -e "$MJ_FX/uv_hang" ] && exec sleep 30; exit 0
STUB
  cat > "$FB/python3" <<'STUB'
#!/bin/bash
echo "CALL $*" >> "$MJ_ROOT/notify.log"; exit "$(cat "$MJ_FX/notify_rc" 2>/dev/null || echo 0)"
STUB
  cat > "$FB/df" <<'STUB'
#!/bin/sh
[ -e "$MJ_FX/df_fail" ] && exit 1
printf 'Filesystem 1024-blocks Used Available Capacity Mounted\n/dev/x 900000000 1 %s 50%% /\n' "$(cat "$MJ_FX/host_kb")"
STUB
  printf '#!/bin/sh\necho Mini-Pro2\n' > "$FB/hostname"
  chmod +x "$FB"/*
  # caches fixture: old + fresh files, a com.apple.* entry, empty/emptied dirs, two symlinks to outside dirs
  C="$H/Library/Caches"; mkdir -p "$C/Homebrew/emptydir" "$C/Homebrew/nest" "$C/com.apple.x" "$C/app"
  for f in old1.bin Homebrew/old.tgz Homebrew/nest/only-old com.apple.x/old; do : > "$C/$f"; touch -t $OLD "$C/$f"; done
  : > "$C/fresh.bin"; : > "$C/Homebrew/fresh.tgz"
  : > "$OUTSIDE/a/oldfile"; touch -t $OLD "$OUTSIDE/a/oldfile"; : > "$OUTSIDE/b/oldfile"; touch -t $OLD "$OUTSIDE/b/oldfile"
  mkdir -p "$C/ms-playwright/chromium-1" "$C/SomeApp"
  for f in ms-playwright/chromium-1/chrome SomeApp/old; do : > "$C/$f"; touch -t $OLD "$C/$f"; done
  ln -s "$OUTSIDE/b" "$C/Homebrew/lnk3"   # nested symlink inside an allowlisted entry
}
runp() { # args to the payload; extra env via RUNP_ENV (word-split)
  HOME="$H" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_JOURNAL="$ROOT/journal.jsonl" MINI_DISK_JANITOR_DF_PATH=/ \
    MINI_DISK_JANITOR_BUSY_WAIT_MIN=0 MINI_DISK_JANITOR_TOOL_TIMEOUT=2 MINI_DISK_JANITOR_NOTIFY="$ROOT/tg_notify.py" \
    env ${RUNP_ENV:-} bash "$PAYLOAD" "$@" > "$ROOT/out.txt" 2> "$ROOT/err.txt"
  RC=$?
}
tree() { (cd "$H" && find Library -print | LC_ALL=C sort); }
receipt() { tail -1 "$ROOT/journal.jsonl" 2>/dev/null; }
step_status() { receipt | "$REAL_PY" -c 'import json,sys; d=json.loads(sys.stdin.read()); s=[x for x in d["steps"] if x["step"]==sys.argv[1]]; print(s[0]["status"]+":"+s[0]["reason"] if s else "none")' "$1" 2>/dev/null; }
clean_script() { for f in "$ROOT"/scripts/*.sh; do [ -f "$f" ] && grep -q 'cache/pip' "$f" && cat "$f"; done; }

echo "== T1 dry-run mutates nothing =="
build; echo 10000000 > "$FX/host_kb"; BEFORE=$(tree); runp
[ "$RC" -eq 0 ] && ok "dry-run exits 0" || no "dry-run rc=$RC"
[ "$BEFORE" = "$(tree)" ] && ok "dry-run leaves the caches tree untouched" || no "dry-run changed the tree"
! grep -Eq 'prune|rm -rf' "$ROOT/docker.log" 2>/dev/null && ok "no mutating docker argv in dry-run" || no "mutating docker call in dry-run"
{ [ ! -s "$ROOT/colima.log" ] && [ ! -s "$ROOT/npm.log" ] && [ ! -s "$ROOT/uv.log" ]; } && ok "no colima/npm/uv call in dry-run" || no "colima/npm/uv called in dry-run"
[ ! -s "$ROOT/notify.log" ] && ok "dry-run never pages, even at critical" || no "dry-run paged"
receipt | grep -q '"mode":"dry-run"' && receipt | grep -q '"level":"critical"' && ok "dry-run still journals and still computes the level" || no "dry-run receipt"
tail -1 "$ROOT/out.txt" | grep -q '^level=critical$' && ok "last stdout line is level=" || no "level line"

echo "== T2c allowlisted top-level entry survives when it becomes empty (-mindepth 1) =="
build; C="$H/Library/Caches"; mkdir -p "$C/Homebrew/deep"; rm -rf "$C/Homebrew"; mkdir -p "$C/Homebrew/sub"; : > "$C/Homebrew/sub/o.tgz"; touch -t $OLD "$C/Homebrew/sub/o.tgz"
runp --apply
{ [ -d "$C/Homebrew" ] && [ ! -e "$C/Homebrew/sub" ]; } && ok "Homebrew/ itself survives when emptied; its subdir is pruned" || no "top-level entry removed or not pruned"

echo "== T2 apply removes old cache files only =="
build; runp --apply; C="$H/Library/Caches"
[ "$RC" -eq 0 ] && ok "apply exits 0" || no "apply rc=$RC err=$(head -3 "$ROOT/err.txt")"
{ [ ! -e "$C/Homebrew/old.tgz" ] && [ ! -e "$C/Homebrew/nest/only-old" ]; } && ok "old files under an allowlisted entry removed" || no "old allowlisted files survived"
{ [ -e "$C/fresh.bin" ] && [ -e "$C/Homebrew/fresh.tgz" ]; } && ok "fresh files survive" || no "fresh file deleted"
[ -e "$C/com.apple.x/old" ] && ok "com.apple.* top-level entry skipped" || no "com.apple.x/old deleted"
{ [ -e "$OUTSIDE/b/oldfile" ] && [ -L "$C/Homebrew/lnk3" ]; } && ok "nested symlink target and link survive (never followed)" || no "symlink followed or removed"
{ [ -e "$C/ms-playwright/chromium-1/chrome" ] && [ -e "$C/SomeApp/old" ] && [ -e "$C/old1.bin" ]; } && ok "ms-playwright, unknown SomeApp and loose top-level files survive (allowlist, fail-closed)" || no "unlisted cache entry deleted"
{ [ ! -d "$C/Homebrew/emptydir" ] && [ ! -d "$C/Homebrew/nest" ] && [ -d "$C/Homebrew" ]; } && ok "empty subdirs pruned, depth-1 entries kept" || no "empty-dir pruning wrong"
! grep -qE 'old1|only-old|Homebrew|SomeApp|playwright' "$ROOT/err.txt" && ok "no candidate names in logs" || no "names leaked to log"
"$REAL_PY" -c 'import json,sys; [json.loads(l) for l in open(sys.argv[1])]' "$ROOT/journal.jsonl" && ok "receipt is valid JSON" || no "receipt invalid"

echo "== T2b allowlist refusals =="
build; C="$H/Library/Caches"; ln -s "$OUTSIDE/a" "$C/Codex"

HOME="$H" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_JOURNAL="$ROOT/journal.jsonl" MINI_DISK_JANITOR_DF_PATH=/ MINI_DISK_JANITOR_BUSY_WAIT_MIN=0 MINI_DISK_JANITOR_NOTIFY="$ROOT/n.py" \
  MINI_DISK_JANITOR_CACHE_ALLOW="Homebrew com.apple.x Codex ../escape a/b . .. Missing" bash "$PAYLOAD" --apply > "$ROOT/out.txt" 2> "$ROOT/err.txt"; RC=$?
{ [ "$(step_status user_caches)" = "error:allow-refused" ] && [ "$RC" -eq 1 ]; } && ok "refused allowlist entries -> step error, exit 1" || no "refusal status: $(step_status user_caches) rc=$RC"
{ [ -e "$C/com.apple.x/old" ] && [ -e "$OUTSIDE/a/oldfile" ] && [ -L "$C/Codex" ]; } && ok "com.apple.* listed in env survives; listed symlink not followed" || no "refused entry touched"
[ ! -e "$C/Homebrew/old.tgz" ] && [ -e "$C/Homebrew/fresh.tgz" ] && ok "valid entries still processed beside refused ones; fresh survives" || no "valid entry skipped"
receipt | grep -q '"refused":6' && ok "refusals counted (6)" || no "refused count: $(receipt | grep -o '"refused":[0-9]*')"

echo "== T3 busy runner =="
build; touch "$FX/busy"; runp --apply
[ "$(step_status runner_cache)" = "skipped:runner-busy" ] && ok "busy -> skipped runner-busy" || no "busy status: $(step_status runner_cache)"
{ [ -z "$(clean_script)" ] && ! grep -q 'rm -rf' "$ROOT/docker.log"; } && ok "no rm exec issued while busy" || no "rm issued while busy"
grep -q 'busy=1' "$ROOT/out.txt" && ok "summary flags busy for the wrapper" || no "busy flag"
[ "$RC" -eq 0 ] && ok "busy skip is not an error" || no "busy rc=$RC"

echo "== T4 idle runner: exact allowlist =="
build; runp --apply; S="$(clean_script)"
for p in /home/runner/.cache/pip /home/runner/.cache/uv /tmp/pytest-of-runner 'pip-unpack-\*'; do
  printf '%s' "$S" | grep -Eq -- "$p" && ok "clean script removes $p" || no "clean script lacks $p"
done
{ printf '%s' "$S" | grep -q 'tmp\*' && printf '%s' "$S" | grep -q -- '-mtime +0'; } && ok "tmp* only when older than a day" || no "tmp* age guard"
{ ! printf '%s' "$S" | grep -E '(^|[|;] *)find ' | grep -qv -- '-mindepth 1'; } && ok "every /tmp find is mindepth 1 (never /tmp itself)" || no "mindepth missing"
if printf '%s' "$S" | grep -Eq '_work/|_actions|rm -rf /( |$)|volume|[[:space:]]-a[[:space:]]'; then no "forbidden token in clean script"; else ok "no _work / _actions / rm of / / volume / -a"; fi
{ printf '%s' "$S" | head -1 | grep -qF 'ps -eo args' && printf '%s' "$S" | head -3 | grep -q 'exit 74' && printf '%s' "$S" | head -3 | grep -q 'exit 75'; } && ok "fail-closed idle re-check is the first thing the exec script does" || no "idle re-check not first"
{ ! cat "$ROOT"/scripts/*.sh "$ROOT/docker.log" | grep -q '_work'; } && ok "no exec script or docker call mentions _work" || no "_work mentioned"
IC="$(printf '%s' "$S" | head -3)"
for m in "fail:74" "empty:74" "worker:75" "idle:0"; do
  mkdir -p "$ROOT/ps-${m%%:*}"
  case "${m%%:*}" in
    fail) printf '#!/bin/sh\nexit 1\n' ;;
    empty) printf '#!/bin/sh\nexit 0\n' ;;
    worker) printf '#!/bin/sh\necho "/bin/bash"\necho "/home/runner/bin/Runner.Worker spawnclient 1 2"\n' ;;
    idle) printf '#!/bin/sh\necho "/bin/bash"\necho "sleep 5"\n' ;;
  esac > "$ROOT/ps-${m%%:*}/ps"; chmod +x "$ROOT/ps-${m%%:*}/ps"
  PATH="$ROOT/ps-${m%%:*}:$SYS_PATH" sh -c "$IC
:"; r=$?
  [ "$r" -eq "${m##*:}" ] && ok "in-container ps ${m%%:*} -> idle re-check rc ${m##*:}" || no "idle re-check ${m%%:*}: rc=$r want ${m##*:}"
done
build; echo 74 > "$FX/exec_rc"; runp --apply
{ [ "$(step_status runner_cache)" = "error:idle-recheck-failed" ] && [ "$RC" -eq 1 ]; } && ok "exec rc 74 -> step error idle-recheck-failed" || no "rc74 mapping: $(step_status runner_cache) rc=$RC"
grep -Eq '^CALL \[(rm|stop|restart|kill|volume|system)\]' "$ROOT/docker.log" && no "forbidden docker verb" || ok "no docker rm/stop/restart/volume/system"

echo "== T4b rename-then-delete =="
build; runp --apply; S="$(clean_script)"
for t in "/home/runner/.cache/pip /home/runner/.cache/.janitor-trash-pip-" "/home/runner/.cache/uv /home/runner/.cache/.janitor-trash-uv-" "/tmp/pytest-of-runner /tmp/.janitor-trash-pytest-"; do
  printf '%s' "$S" | grep -qF "mv $t" && ok "atomic mv to trash: ${t%% *}" || no "no mv for ${t%% *}"
done
{ ! printf '%s\n' "$S" | grep 'rm -rf' | grep -qv 'janitor-trash-'; } && ok "every rm -rf names only .janitor-trash-* (no direct delete of a target)" || no "direct rm -rf of a target"
{ ia=$(printf '%s' "$S" | grep -n 'ps -eo args' | head -1 | cut -d: -f1); rn=$(printf '%s' "$S" | grep -n 'mv /home/runner/.cache/pip' | cut -d: -f1)
  dl=$(printf '%s' "$S" | grep -n 'rm -rf' | head -1 | cut -d: -f1); sw=$(printf '%s' "$S" | grep -n 'rm -rf' | tail -1 | cut -d: -f1)
  [ "$ia" -lt "$rn" ] && [ "$rn" -lt "$dl" ] && [ "$dl" -lt "$sw" ]; } && ok "order: idle re-check, renames, this run's trash, leftover sweep last" || no "exec script order"
printf '%s' "$S" | grep 'rm -rf' | head -1 | grep -qF -- '-name ".janitor-trash-*-$$"' && ok "this run's trash is deleted by its own pid suffix" || no "own-trash delete missing"
printf '%s' "$S" | grep -E 'rm -rf' | grep -qF -- '-mindepth 1 -maxdepth 1 -name ".janitor-trash-*"' && ok "sweep is bounded (mindepth 1, maxdepth 1, exact prefix)" || no "sweep unbounded"

echo "== T4c exec script run against a scratch tree (newline-safe /tmp handling) =="
build; runp --apply; S="$(clean_script)"
SC="$ROOT/ctr"; mkdir -p "$SC/tmp" "$SC/home/runner/.cache/pip" "$SC/home/runner/.cache/uv" "$SC/tmp/pytest-of-runner" "$ROOT/ps-idle"
printf '#!/bin/sh\necho "sleep 5"\n' > "$ROOT/ps-idle/ps"; chmod +x "$ROOT/ps-idle/ps"
mkdir "$SC/tmp/pip-unpack-1" "$SC/tmp/tmpold" "$SC/tmp/tmpnew" "$SC/tmp/keep-me" "$SC/tmp/victim"
touch "$SC/home/runner/.cache/pip/f" "$SC/home/runner/.cache/other"
mkdir "$SC/tmp/.janitor-trash-leftover" "$SC/home/runner/.cache/.janitor-trash-old"
touch -t $OLD "$SC/tmp/tmpold"
NLN="pip-unpack-nl
victim"                              # one file name that spans two lines; line 2 is another entry's name
: > "$SC/tmp/$NLN"
printf '%s' "$S" | sed -e 's#/home/runner#@H@#g' -e 's#/tmp#@T@#g' -e "s#@H@#$SC/home/runner#g" -e "s#@T@#$SC/tmp#g" > "$ROOT/exec-sb.sh"
( cd "$SC/tmp" && PATH="$ROOT/ps-idle:$SYS_PATH" sh "$ROOT/exec-sb.sh" ); r=$?
[ "$r" -eq 0 ] && ok "exec script runs clean against the scratch tree" || no "exec script rc=$r"
{ [ ! -e "$SC/tmp/pip-unpack-1" ] && [ ! -e "$SC/tmp/tmpold" ] && [ ! -e "$SC/home/runner/.cache/pip" ] && [ ! -e "$SC/home/runner/.cache/uv" ] && [ ! -e "$SC/tmp/pytest-of-runner" ]; } && ok "declared set removed" || no "declared set survived"
{ [ -d "$SC/tmp/tmpnew" ] && [ -d "$SC/tmp/keep-me" ] && [ -e "$SC/home/runner/.cache/other" ]; } && ok "fresh tmp*, other /tmp entries and other cache files survive" || no "undeclared entry removed"
[ -d "$SC/tmp/victim" ] && ok "entry named like line 2 of a multi-line name is neither moved nor deleted" || no "newline name made the script delete an entry outside the set"
[ ! -e "$SC/tmp/$NLN" ] && ok "the multi-line name itself is in the declared set and removed whole" || no "multi-line name left behind"
{ [ ! -e "$SC/tmp/.janitor-trash-leftover" ] && [ ! -e "$SC/home/runner/.cache/.janitor-trash-old" ] && [ -z "$(find "$SC/tmp" -mindepth 1 -maxdepth 1 -name ".janitor-trash-*")" ]; } && ok "leftover and own trash all swept" || no "trash left behind"
build; runp --apply; S="$(clean_script)"; printf '%s' "$S" | grep -qE 'read -r|while ' && no "exec script re-splits lines (read/while loop)" || ok "no line loop in the exec script"

echo "== T5 docker / colima / npm / uv argv =="
build; runp --apply
P=$(grep -c 'prune' "$ROOT/docker.log")
{ grep -qF 'CALL [image] [prune] [-f]' "$ROOT/docker.log" && grep -qF 'CALL [builder] [prune] [-f]' "$ROOT/docker.log" && [ "$P" -eq 2 ]; } && ok "exactly image prune -f and builder prune -f" || no "prune argv wrong ($P)"
grep -Eq '\[-a\]|\[--all\]|\[volume\]|\[system\]' "$ROOT/docker.log" && no "wide prune flag" || ok "never -a / volume / system"
grep -qF 'CALL ssh -- sudo fstrim -av' "$ROOT/colima.log" && ok "colima ssh -- sudo fstrim -av" || no "fstrim argv"
receipt | grep -q '"trimmed_bytes":5368709120' && ok "trimmed bytes parsed from fstrim output" || no "trimmed bytes"
{ grep -qF 'CALL cache verify' "$ROOT/npm.log" && grep -qF 'CALL cache prune' "$ROOT/uv.log"; } && ok "npm cache verify + uv cache prune" || no "npm/uv argv"
grep -qiE 'clean|autoremove' "$ROOT/uv.log" && no "uv cache clean used" || ok "no uv cache clean"

echo "== T6 degraded tools =="
build; touch "$FX/uv_hang"; runp --apply
{ [ "$(step_status uv)" = "skipped:uv-lock-busy" ] && [ "$RC" -eq 0 ]; } && ok "uv timeout -> skipped uv-lock-busy, run exit 0" || no "uv timeout: $(step_status uv) rc=$RC"
build; echo 1 > "$FX/colima_rc"; runp --apply
{ [ "$(step_status vm_trim)" = "error:fstrim-failed" ] && [ "$RC" -eq 1 ]; } && ok "failed fstrim -> error, exit 1" || no "fstrim failure handling"
build; echo false > "$FX/running"; runp --apply
[ "$(step_status runner_cache)" = "skipped:container-not-running" ] && ok "stopped container -> skipped" || no "container-not-running"
build; echo absent > "$FX/inspect_mode"; runp --apply
{ [ "$(step_status runner_cache)" = "skipped:container-not-running" ] && grep -q 'runner_pct=na' "$ROOT/out.txt" && [ "$RC" -eq 0 ]; } && ok "inspect: no such object -> container absent, skipped, runner_pct na, exit 0" || no "inspect absent: $(step_status runner_cache) rc=$RC"
build; echo fail > "$FX/inspect_mode"; runp --apply
{ [ "$(step_status runner_cache)" = "error:inspect-failed" ] && [ "$(step_status floor)" = "error:inspect-failed" ] && tail -1 "$ROOT/out.txt" | grep -q '^level=unknown$' && [ "$RC" -eq 1 ]; } && ok "inspect: any other failure -> runner_cache error, floor level unknown" || no "inspect fail: $(step_status runner_cache) $(step_status floor) rc=$RC"
! grep -q 'rm -rf' "$ROOT/docker.log" && ok "nothing deleted when inspect failed" || no "deleted despite inspect failure"
build; mkdir "$ROOT/nodocker"
for u in bash sh perl find sed awk grep rm cat date tail head tr ls wc env stat touch dirname mkdir hostname sleep printf df; do ln -s "$(command -v $u)" "$ROOT/nodocker/$u" 2>/dev/null; done
HOME="$H" PATH="$ROOT/nodocker" MINI_DISK_JANITOR_JOURNAL="$ROOT/journal.jsonl" MINI_DISK_JANITOR_DF_PATH=/ bash "$PAYLOAD" --apply >/dev/null 2>&1
{ [ "$(step_status runner_cache)" = "skipped:docker-absent" ] && [ "$(step_status vm_trim)" = "skipped:colima-absent" ] && [ "$(step_status npm)" = "skipped:npm-absent" ]; } && ok "absent tools -> skipped, not error" || no "absent-tool statuses"

echo "== T7 floor =="
build; echo 30000000 > "$FX/host_kb"; runp --apply
{ tail -1 "$ROOT/out.txt" | grep -q '^level=warning$' && [ "$(wc -l < "$ROOT/notify.log" | tr -d ' ')" = 1 ] \
  && grep -q -- '--tier digest --source mini.disk_janitor --dedup-key mini-disk-warn-host' "$ROOT/notify.log" && ! grep -q -- '--tier p0' "$ROOT/notify.log"; } && ok "host free < warn -> warning, ONE digest notify, no p0" || no "warning level: $(cat "$ROOT/notify.log" 2>/dev/null)"
build; echo 10000000 > "$FX/host_kb"; runp --apply
{ tail -1 "$ROOT/out.txt" | grep -q '^level=critical$' && [ "$(wc -l < "$ROOT/notify.log" | tr -d ' ')" = 1 ] \
  && grep -q -- '--tier p0 --source mini.disk_janitor --dedup-key mini-disk-host' "$ROOT/notify.log"; } && ok "host critical -> level critical, ONE p0 page" || no "critical level: $(cat "$ROOT/notify.log" 2>/dev/null)"
build; echo 10000000 > "$FX/host_kb"; echo 1 > "$FX/notify_rc"; runp --apply
[ "$RC" -eq 0 ] && ok "notifier failure does not change the exit code" || no "notifier failure rc=$RC"
build; echo 90 > "$FX/ctr_pct"; runp --apply
{ tail -1 "$ROOT/out.txt" | grep -q '^level=warning$' && grep -q 'dedup-key mini-disk-warn-runner' "$ROOT/notify.log"; } && ok "runner >= 85 -> warning + runner digest" || no "runner warning"
build; echo 97 > "$FX/ctr_pct"; runp --apply
{ grep -q 'dedup-key mini-disk-runner' "$ROOT/notify.log" && tail -1 "$ROOT/out.txt" | grep -q '^level=critical$'; } && ok "runner >= 95 -> critical + runner page" || no "runner critical"
build; runp --apply
{ tail -1 "$ROOT/out.txt" | grep -q '^level=ok$' && receipt | grep -q '"runner_pct_before":40'; } && ok "healthy host -> level ok, receipt carries runner pct" || no "ok level"

echo "== T8 guards =="
build; mkdir "$ROOT/trip"
for u in find rm; do printf '#!/bin/sh\necho "%s $*" >> "%s/trip.log"\nexit 1\n' "$u" "$ROOT" > "$ROOT/trip/$u"; chmod +x "$ROOT/trip/$u"; done
HOME=/ PATH="$ROOT/trip:$FB:$SYS_PATH" MINI_DISK_JANITOR_JOURNAL="$ROOT/journal.jsonl" MINI_DISK_JANITOR_DF_PATH=/ MINI_DISK_JANITOR_BUSY_WAIT_MIN=0 bash "$PAYLOAD" --apply >/dev/null 2>&1; RC=$?
{ [ "$(step_status user_caches)" = "error:home-unsafe" ] && [ "$RC" -eq 1 ] && [ ! -e "$ROOT/trip.log" ]; } && ok "HOME=/ -> user_caches error, find/rm never called" || no "HOME=/ guard: $(step_status user_caches) $(cat "$ROOT/trip.log" 2>/dev/null)"
build; rm -rf "$H/Library/Caches"; mkdir -p "$ROOT/elsewhere"; : > "$ROOT/elsewhere/old"; touch -t $OLD "$ROOT/elsewhere/old"; ln -s "$ROOT/elsewhere" "$H/Library/Caches"
runp --apply
{ [ "$(step_status user_caches)" = "error:caches-symlink" ] && [ -e "$ROOT/elsewhere/old" ]; } && ok "Library/Caches symlinked away -> error, nothing deleted" || no "caches symlink guard"
build; mkdir -p "$ROOT/outer/Library"; mv "$H/Library/Caches" "$ROOT/outer/Library/Caches"; rm -rf "$H/Library"; ln -s "$ROOT/outer/Library" "$H/Library"
runp --apply
{ [ "$(step_status user_caches)" = "error:caches-outside-home" ] && [ -e "$ROOT/outer/Library/Caches/old1.bin" ]; } && ok "Library symlinked outside HOME -> error, nothing deleted" || no "outside-home guard: $(step_status user_caches)"
build; RUNP_ENV="MINI_DISK_JANITOR_CACHE_DAYS=abc"; runp --apply
[ "$RC" -eq 2 ] && ok "non-integer knob refused (exit 2)" || no "knob validation rc=$RC"; RUNP_ENV=""

echo "== T9 wrapper =="
wrap() { # $1 payload stdout, $2 payload rc; extra env in WENV
  rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"
  printf '#!/bin/bash\nprintf "%%b" "$MJ_STDOUT"\nexit ${MJ_RC:-0}\n' > "$ROOT/payload-stub.sh"
  HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_PAYLOAD="$ROOT/payload-stub.sh" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" \
    MJ_STDOUT="$1" MJ_RC="${2:-0}" env ${WENV:-} /bin/bash "$WRAPPER" >/dev/null 2>&1
  WRC=$?; HB="$ROOT/home2/.organism/last_seen/mini.disk_janitor.json"
}
hbstatus() { sed -n 's/.*"status":"\([^"]*\)".*/\1/p' "$HB" 2>/dev/null; }
build; WENV=""
wrap 'summary freed_kb=10485760 host_free_gb=50 runner_pct=40 busy=0 errors=0\nlevel=ok\n' 0
{ [ "$(hbstatus)" = ok ] && grep -q 'freed 10GiB host_free 50GiB runner 40%' "$HB"; } && ok "level ok -> heartbeat ok, note carries freed/host/runner" || no "ok mapping: $(cat "$HB" 2>/dev/null)"
wrap 'summary freed_kb=0 host_free_gb=30 runner_pct=40 busy=0 errors=0\nlevel=warning\n' 0
{ [ "$(hbstatus)" = ok ] && grep -q 'level=warning' "$HB"; } && ok "level warning -> heartbeat ok, note level=warning" || no "warning mapping: $(cat "$HB")"
wrap 'summary freed_kb=0 host_free_gb=50 runner_pct=40 busy=1 errors=0\nlevel=ok\n' 0
{ [ "$(hbstatus)" = ok ] && grep -q 'runner-busy' "$HB"; } && ok "runner-busy skip -> heartbeat ok, note runner-busy" || no "busy mapping: $(cat "$HB")"
wrap 'summary freed_kb=0 host_free_gb=5 runner_pct=40 busy=0 errors=0\nlevel=critical\n' 0
[ "$(hbstatus)" = error ] && ok "level critical -> heartbeat error" || no "critical mapping"
wrap 'summary freed_kb=0 host_free_gb=50 runner_pct=40 busy=0 errors=1\nlevel=ok\n' 1
[ "$(hbstatus)" = error ] && ok "payload exit 1 -> heartbeat error" || no "rc1 mapping"
wrap 'summary freed_kb=0 host_free_gb=0 runner_pct=na busy=0 errors=1\nlevel=unknown\n' 0
[ "$(hbstatus)" = error ] && ok "level unknown -> heartbeat error" || no "unknown mapping"
wrap 'summary freed_kb=0 host_free_gb=5 runner_pct=40 busy=0 errors=0\nlevel=bogus\n' 0
[ "$(hbstatus)" = error ] && ok "unrecognised level -> heartbeat error" || no "bogus level mapping"
wrap '' 0
[ "$(hbstatus)" = error ] && ok "silent payload -> heartbeat error (no level proves nothing)" || no "silent payload"
WENV="MINI_DISK_JANITOR_ENABLED=false"; wrap 'level=ok\n' 0
{ [ "$(hbstatus)" = disabled ] && [ "$WRC" -eq 0 ]; } && ok "kill switch -> heartbeat disabled" || no "kill switch"
WENV=""; printf '#!/bin/sh\necho Other-Host\n' > "$FB/hostname"; wrap 'level=ok\n' 0
{ [ "$(hbstatus)" = disabled ] && grep -q 'wrong-node' "$HB"; } && ok "wrong hostname -> heartbeat disabled" || no "node guard"
printf '#!/bin/sh\necho Mini-Pro2\n' > "$FB/hostname"
rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"
HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_PAYLOAD="$ROOT/none.sh" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" /bin/bash "$WRAPPER" >/dev/null 2>&1; HB="$ROOT/home2/.organism/last_seen/mini.disk_janitor.json"
{ [ "$(hbstatus)" = error ] && grep -q 'payload missing' "$HB"; } && ok "missing payload -> heartbeat error" || no "missing payload"
rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"; sleep 30 & SP=$!; echo $SP > "$ROOT/w.pid"
HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_PAYLOAD="$PAYLOAD" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" /bin/bash "$WRAPPER" >/dev/null 2>&1; kill $SP 2>/dev/null; wait $SP 2>/dev/null
{ [ "$(hbstatus)" = ok ] && grep -q 'previous-run-active' "$HB"; } && ok "live pidfile -> heartbeat ok, note previous-run-active, payload not run" || no "single-instance: $(cat "$HB")"
rm -f "$ROOT/w.pid"
rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"
printf '#!/bin/bash\nkill -TERM $PPID\nsleep 1\n' > "$ROOT/payload-term.sh"
HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_PAYLOAD="$ROOT/payload-term.sh" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" /bin/bash "$WRAPPER" >/dev/null 2>&1
{ [ "$(hbstatus)" = error ] && [ ! -e "$ROOT/w.pid" ]; } && ok "signal mid-run -> EXIT trap writes error heartbeat and frees the lock" || no "abnormal exit: $(hbstatus)"
grep -q 'KeepAlive' "$HERE/infra/launchagents/com.nuzantara.mini-disk-janitor.plist" && no "plist has KeepAlive" || ok "plist is one-shot (no KeepAlive)"

echo "== T9b stale lock and deadline =="
build; WENV=""; rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"
printf '#!/bin/bash\nprintf "summary freed_kb=0 host_free_gb=50 runner_pct=40 busy=0 errors=0\\nlevel=ok\\n"\n' > "$ROOT/payload-ok.sh"
sleep 30 & SP=$!; echo $SP > "$ROOT/w.pid"; touch -t 202001010000 "$ROOT/w.pid"
HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_PAYLOAD="$ROOT/payload-ok.sh" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" /bin/bash "$WRAPPER" >/dev/null 2>&1; kill $SP 2>/dev/null; wait $SP 2>/dev/null
HB="$ROOT/home2/.organism/last_seen/mini.disk_janitor.json"
{ [ "$(hbstatus)" = ok ] && grep -q 'level=ok' "$HB" && ! grep -q 'previous-run-active' "$HB"; } && ok "live pid on an OLD pidfile -> stale lock removed, run proceeds" || no "stale lock: $(cat "$HB")"
rm -f "$ROOT/w.pid"; rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"
printf '#!/bin/bash\nexec sleep 30\n' > "$ROOT/payload-hang.sh"
T0=$(date +%s)
HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_PAYLOAD="$ROOT/payload-hang.sh" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" MINI_DISK_JANITOR_DEADLINE_S=1 /bin/bash "$WRAPPER" >/dev/null 2>&1; WRC=$?
{ [ "$(hbstatus)" = error ] && grep -q 'deadline' "$HB" && [ "$WRC" -eq 0 ] && [ $(( $(date +%s) - T0 )) -lt 15 ]; } && ok "payload past the deadline -> killed, heartbeat error note deadline" || no "deadline: $(cat "$HB") rc=$WRC"

echo "== T10 wrapper robustness, floor, journal, plist =="
build; rm -rf "$ROOT/home2"; mkdir -p "$ROOT/home2"; : > "$ROOT/afile"
HOME="$ROOT/home2" PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_SIDECAR_DIR="$ROOT/afile/sub" MINI_DISK_JANITOR_PAYLOAD="$PAYLOAD" MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" MINI_DISK_JANITOR_ENABLED=false /bin/bash "$WRAPPER" >/dev/null 2>"$ROOT/we.txt"; WRC=$?
{ [ "$WRC" -eq 1 ] && grep -q 'heartbeat write FAILED' "$ROOT/we.txt"; } && ok "sidecar write failure -> wrapper exit 1 (stderr names it)" || no "HB_FAIL rc=$WRC"
env -i PATH="$FB:$SYS_PATH" /bin/bash "$WRAPPER" >/dev/null 2>"$ROOT/we.txt"; WRC=$?
{ [ "$WRC" -eq 1 ] && grep -q 'HOME is unset' "$ROOT/we.txt"; } && ok "HOME unset -> visible exit 1, no set -u crash" || no "HOME unset rc=$WRC $(cat "$ROOT/we.txt")"
rm -rf "$ROOT/sc"; env -i PATH="$FB:$SYS_PATH" MINI_DISK_JANITOR_SIDECAR_DIR="$ROOT/sc" MINI_DISK_JANITOR_ENABLED=false MINI_DISK_JANITOR_PIDFILE="$ROOT/w.pid" /bin/bash "$WRAPPER" >/dev/null 2>&1; HB="$ROOT/sc/mini.disk_janitor.json"
[ "$(hbstatus)" = disabled ] && ok "HOME unset with an injected sidecar dir still writes the heartbeat" || no "HOME-less heartbeat"
build; echo 1 > "$FX/df_fail"; runp --apply
{ [ "$(step_status floor)" = "error:host-df-failed" ] && tail -1 "$ROOT/out.txt" | grep -q '^level=unknown$' && [ "$RC" -eq 1 ]; } && ok "host df failure -> floor error, level unknown, exit 1" || no "df failure: $(step_status floor) rc=$RC"
build; echo false > "$FX/running"; runp --apply
{ grep -q 'runner_pct=na' "$ROOT/out.txt" && receipt | grep -q '"runner_pct_after":null' && tail -1 "$ROOT/out.txt" | grep -q '^level=ok$' && [ "$RC" -eq 0 ]; } && ok "container not running -> runner_pct na (never 0), level from host alone" || no "not-running floor: $(cat "$ROOT/out.txt")"
build; touch "$FX/ctr_fail"; runp --apply
{ [ "$(step_status floor)" = "error:runner-df-failed" ] && tail -1 "$ROOT/out.txt" | grep -q '^level=unknown$'; } && ok "running container with failing df probe -> floor error, level unknown" || no "runner df failure: $(step_status floor)"
build; mkdir "$ROOT/trip"
for u in find rm; do printf '#!/bin/sh\necho "%s $*" >> "%s/trip.log"\nexit 1\n' "$u" "$ROOT" > "$ROOT/trip/$u"; chmod +x "$ROOT/trip/$u"; done
env -u MINI_DISK_JANITOR_JOURNAL HOME=/ PATH="$ROOT/trip:$FB:$SYS_PATH" MINI_DISK_JANITOR_DF_PATH=/ MINI_DISK_JANITOR_BUSY_WAIT_MIN=0 bash "$PAYLOAD" --apply >/dev/null 2>"$ROOT/err.txt"; RC=$?
{ [ "$RC" -eq 1 ] && grep -q 'receipt REFUSED' "$ROOT/err.txt" && [ ! -e /logs ]; } && ok "HOME=/ -> default journal refused (error), /logs never written" || no "journal guard rc=$RC"
PL="$HERE/infra/launchagents/com.nuzantara.mini-disk-janitor.plist"
"$REAL_PY" -c 'import plistlib,sys; d=plistlib.load(open(sys.argv[1],"rb")); c=d.get("StartCalendarInterval"); sys.exit(0 if c=={"Hour":3,"Minute":30} and "StartInterval" not in d and "KeepAlive" not in d and d.get("RunAtLoad") is False else 1)' "$PL" && ok "plist: StartCalendarInterval 03:30, RunAtLoad false, no StartInterval/KeepAlive" || no "plist schedule"

echo
echo "mini_disk_janitor: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
