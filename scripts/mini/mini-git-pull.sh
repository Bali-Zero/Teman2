#!/bin/bash
# Mini-side periodic git pull for ~/nuzantara on main.
#
# Runs ON Mini via com.nuzantara.git-pull-main.5min LaunchAgent.
# Pattern: detect-mismatch → stash → fetch pro+origin → ff to most-advanced → stash pop.
#
# Hardened against the 2026-05-06 incident where a tracked symlink in
# main collided with a 762 MB local directory (.venv) on Mini, causing
# silent 8+ retry failures because `git stash --include-untracked` tried
# to stash the entire dir.
#
# Hardening:
#   1. Detect symlink-vs-dir / dir-vs-symlink mismatches BEFORE stash and
#      skip with Telegram alert (these need human triage).
#   2. Stash only tracked-modified paths via `git stash push --keep-index`
#      pattern, never `--include-untracked` blindly. Untracked files
#      survive a ff-only pull anyway.
#   3. Bound the stash retention: if stash list exceeds N entries, alert
#      (sign that pop has been failing).
#   4. Telegram alert on every non-trivial WARN/ERROR via the same
#      bot used by login-healthcheck (TELEGRAM_BOT_TOKEN secret on Mini).
#
# Source-of-truth selection (2026-07-05 fix — M5 era):
#   Fetch BOTH `pro/main` and `origin/main` (best-effort each), then ff to the
#   MOST-ADVANCED of the two. The pre-M5 policy was Pro-first with origin only
#   as unreachable-fallback — it silently left Mini stale whenever Pro was
#   reachable but itself behind origin (M5 pushes straight to GitHub; on
#   2026-07-02 Mini sat 13 commits behind origin logging "ahead of pro/main;
#   skip pull" every 5 min).
#   If pro/main and origin/main have DIVERGED, prefer origin/main (GitHub is
#   authoritative) and Telegram-alert so Pro's unpushed work gets human triage.
#
# Cron: StartInterval=300 on Mini.
# Log:  ~/logs/mini-git-pull.log
# Error: ~/logs/mini-git-pull.error.log

set -u

REPO="$HOME/nuzantara"
LOG_FILE="$HOME/logs/mini-git-pull.log"
LOCK_FILE="/tmp/mini-git-pull.lock"
BACKUP_ROOT="${MINI_GIT_PULL_BACKUP_ROOT:-$HOME/.git-pull-collision-backup}"  # recoverable moved-aside untracked collisions
STASH_RETENTION_THRESHOLD=5  # alert if more stashes than this accumulate
TELEGRAM_ALERT_COOLDOWN=3600  # 1h cooldown per alert key
TELEGRAM_STATE_DIR="$HOME/.agent/decisions/state"

mkdir -p "$(dirname "$LOG_FILE")" "$TELEGRAM_STATE_DIR"

# Force literal pathspecs so an exotic incoming filename (`*`, `:(glob)**`, `:/`) fed to
# `git ls-files -- "$f"` can never be read as pathspec magic and match unrelated files.
export GIT_LITERAL_PATHSPECS=1

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# Telegram alert with per-key cooldown (avoid notification storms).
telegram_alert() {
  local key="$1"
  local message="$2"
  local state_file="$TELEGRAM_STATE_DIR/mini-git-pull-alert-${key}.ts"
  local now last_ts
  now=$(date +%s)
  if [ -f "$state_file" ]; then
    last_ts=$(cat "$state_file" 2>/dev/null || echo "0")
    if [ $((now - last_ts)) -lt "$TELEGRAM_ALERT_COOLDOWN" ]; then
      return 0  # within cooldown, skip
    fi
  fi
  # Source secrets if available — Telegram bot token must be there.
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
    set +a
  fi
  local token="${TELEGRAM_BOT_TOKEN:-}"
  local chat="${TELEGRAM_OWNER_CHAT_ID:-8847435604}"
  if [ -z "$token" ]; then
    log "  (telegram skipped — TELEGRAM_BOT_TOKEN not in env)"
    return 0
  fi
  curl -s --max-time 8 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    -d "chat_id=${chat}" \
    -d "text=[mini-git-pull] ${message}" >/dev/null 2>&1 || true
  echo "$now" > "$state_file"
}

TARGET_REF="origin/main"
TARGET_REMOTE="origin"

# Detect tracked-symlink vs local-dir (or vice versa) mismatches.
# Returns 0 if clean, 1 if mismatch found (caller skips).
#
# Walks the FULL target tree of symlinks (tree mode 120000) and the
# subset of "tree" entries (mode 040000). For each, compares the local
# filesystem reality against origin's expectation. The 2026-05-06
# incident path (.venv: tracked symlink, local 762 MB dir) is the
# canonical case.
#
# Cost-bounded: typical repo has <100 symlinks; full scan is ~50 ms.
#
# 2026-08-20 hardening (W120, family #3 guard-over-match): a raw
# local-FS-vs-origin-tree comparison can't tell "foreign content that a
# checkout would destroy" (the .venv case above) from "content that is
# EXACTLY what our own HEAD already tracks, just an older type than
# origin/main's" — a plain type-change commit (e.g. a directory
# converted to a symlink upstream) reads identically to the dangerous
# case unless we also ask HEAD. `git merge --ff-only` handles a clean
# type-change natively; it only needs protecting from local drift HEAD
# doesn't know about. So for every mismatching path we also resolve
# HEAD's own tracked kind and only flag when local disagrees with HEAD
# too — a stale-but-clean checkout (local == HEAD) is safe to let the
# ff-only merge resolve on its own.
_head_tracked_kind() {
  local line
  line=$(git ls-tree HEAD -- "$1" 2>/dev/null)
  case "$line" in
    120000\ *) echo "symlink" ;;
    040000\ *) echo "dir" ;;
    100644\ *|100755\ *) echo "file" ;;
    *) echo "absent" ;;
  esac
}

check_type_mismatch() {
  local mismatch_count=0
  local mismatch_first=""

  # Pass 1: every symlink declared in origin/main must be a symlink
  # locally (or absent — pull will create it). If it's a real file or
  # dir, we have a mismatch — UNLESS local matches what our own HEAD
  # already tracks (safe stale-checkout type-change, see note above).
  # ls-tree format is `<mode> SP <type> SP <hash> TAB <path>`. We extract
  # the path field (everything after the TAB) via awk.
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    # Path absent locally is fine (pull will create it).
    [ -e "$path" ] || [ -L "$path" ] || continue
    local fs_kind="other"
    if [ -L "$path" ]; then fs_kind="symlink"
    elif [ -d "$path" ]; then fs_kind="dir"
    elif [ -f "$path" ]; then fs_kind="file"
    fi
    if [ "$fs_kind" != "symlink" ]; then
      [ "$(_head_tracked_kind "$path")" = "$fs_kind" ] && continue
      mismatch_count=$((mismatch_count + 1))
      [ -z "$mismatch_first" ] && mismatch_first="$path (origin=symlink, local=$fs_kind)"
    fi
  done < <(git ls-tree -r "$TARGET_REF" 2>/dev/null | awk -F'\t' '$1 ~ /^120000/ {print $2}')

  # Pass 2: every regular file declared in origin/main must NOT be a
  # local dir or symlink (same HEAD-matches-local exemption as Pass 1).
  # (Files are 100644/100755.) Dirs in git are implicit (tree entries
  # appear when -t flag is used; we don't use -t so this pass only sees
  # files. We focus on files-vs-dir conflicts.)
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    [ -e "$path" ] || [ -L "$path" ] || continue
    local fs_kind="other"
    if [ -L "$path" ]; then fs_kind="symlink"
    elif [ -d "$path" ]; then fs_kind="dir"
    elif [ -f "$path" ]; then fs_kind="file"
    fi
    if [ "$fs_kind" != "file" ]; then
      [ "$(_head_tracked_kind "$path")" = "$fs_kind" ] && continue
      mismatch_count=$((mismatch_count + 1))
      [ -z "$mismatch_first" ] && mismatch_first="$path (origin=file, local=$fs_kind)"
    fi
  done < <(git ls-tree -r "$TARGET_REF" 2>/dev/null | awk -F'\t' '$1 ~ /^10064[45]|^10075[5]/ {print $2}')

  if [ "$mismatch_count" -gt 0 ]; then
    log "ERROR: $mismatch_count type-mismatch path(s) detected, refusing pull."
    log "  first: $mismatch_first"
    log "  HINT: human triage needed. Likely a tracked symlink in main has been"
    log "        materialized as a real dir/file on Mini. mv it aside before retry."
    telegram_alert "type-mismatch" \
      "${mismatch_count} path type-mismatch (e.g. ${mismatch_first}). Pull refused. Manual triage on Mini."
    return 1
  fi
  return 0
}

# RESOLVE untracked/ignored local files that occupy a path the incoming merge also touches.
# `git merge --ff-only` refuses when an UNTRACKED file collides with a path the target ref
# introduces, AND (verified on Pro, scar H) SILENTLY OVERWRITES an IGNORED one — so both must
# be handled. The old behavior SKIPPED the whole tick (exit 1), which for genuinely-transient
# sibling WIP self-resolves in a tick or two, but (a) left Mini blind to the ignored-file
# silent-clobber, and (b) stalled indefinitely if the collision persisted. Mirroring
# scripts/pro/pro-git-pull.sh, we now back each colliding path up to a timestamped,
# PID-unique, no-clobber backup and MOVE IT ASIDE so the ff can land — recoverable (nothing
# deleted; every move logged + alerted), so a genuine sibling WIP can be restored from backup.
#
# Iterate the INCOMING diff (small, clean git names), classifying each path as untracked by
# "tracked? no ∧ exists on disk" — so a huge ignore tree (.venv) is never enumerated and
# ignored collisions ARE caught (unlike `git ls-files --others --exclude-standard`, which
# skips ignored files). Tracked-modified paths are left to the stash step below.
#
# Returns 0 on success (incl. nothing to do); 1 on ANY failure (fail-safe: caller skips tick).
resolve_untracked_collision() {
  local changed_paths f backup n=0 first="" ts
  changed_paths=$(git -c core.quotepath=false diff --name-only HEAD "$TARGET_REF" 2>/dev/null)
  [ -z "$changed_paths" ] && return 0
  ts="$(date '+%Y%m%d-%H%M%S')-$$"
  backup="$BACKUP_ROOT/$ts"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    # tracked paths → handled by the stash step; only UNTRACKED/IGNORED collide here.
    git ls-files --error-unmatch -- "$f" >/dev/null 2>&1 && continue
    # collision only if it actually exists on disk (-L: a dangling symlink blocks/loses too)
    [ -e "$REPO/$f" ] || [ -L "$REPO/$f" ] || continue
    mkdir -p "$backup/$(dirname "$f")" 2>>"$LOG_FILE" || { log "ERROR: mkdir backup for $f"; return 1; }
    if mv -n "$REPO/$f" "$backup/$f" 2>>"$LOG_FILE" && [ ! -e "$REPO/$f" ]; then
      n=$((n + 1)); [ -z "$first" ] && first="$f"
      log "  moved colliding untracked/ignored → backup: $f -> $backup/$f"
    else
      log "ERROR: mv failed / backup dest existed for $f — skip tick (fail-safe)"; return 1
    fi
  done < <(printf '%s\n' "$changed_paths")
  if [ "$n" -gt 0 ]; then
    log "Resolved $n untracked/ignored collision(s) with incoming $TARGET_REF into $backup (recoverable)."
    telegram_alert "untracked-resolved" \
      "Mini pull: backed up + moved aside ${n} untracked file(s) colliding with incoming ${TARGET_REMOTE}/main (e.g. ${first}) into ${backup}. Restore from backup if any was real sibling WIP."
  fi
  return 0
}

# ===== MAIN =====

# Single-instance lock
if [ -f "$LOCK_FILE" ]; then
  PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    log "Already running (PID $PID), skip"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$REPO" 2>/dev/null || { log "FATAL: $REPO not found"; exit 1; }

# Sane PATH under launchd (no shell rc files sourced).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# ---- heartbeat (temporary, 2026-08-12) -------------------------------------
# I have been reasoning about this host instead of measuring it. Three things
# are unknown and all three are answerable with one line down the channel that
# is already proven to work (the Mini opened Pro:22 at 05:58:46, seen in
# netstat from the Pro side): does this script actually run, what is this
# machine's REAL short hostname — the SOS probe's node guard compares against
# a literal "mini-pro2" and exits 0 in silence if it differs, which is
# indistinguishable from every other failure — and which commit is checked out
# here. Unconditional, before every guard and every exit, so its silence means
# "the script did not run" and nothing else.
ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new \
    -o IdentitiesOnly=yes -i "$HOME/.ssh/id_ed25519" pro \
    "echo \"$(date '+%F %T') host=$(hostname -s) head=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null) branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)\" >> /tmp/mini-heartbeat.log" \
    >/dev/null 2>&1 || log "  heartbeat to pro failed (ignored)"

# ---- SOS probe (temporary, 2026-08-11) -------------------------------------
# Every INBOUND connection to this host has been reset ~250 ms after the
# handshake since 2026-08-10 (sshd, VNC, redis, ollama, ARD alike) while this
# pull's own outbound SSH works perfectly, a power-cycle changed nothing, and
# the site has no keyboard. This pull is therefore the only proven-live code
# path into the Mini, so it carries a probe that reports out through the SSH
# direction that still works.
#
# IT RUNS HERE, NOT AT THE END, AND THAT PLACEMENT IS THE WHOLE POINT. The
# first version sat after the pull logic and therefore below FOUR early exits —
# not on main, both fetches failed, already-up-to-date (by far the common case:
# ~287 of every 288 daily ticks), local-ahead. A rescue instrument that only
# fires when main happens to move is not a rescue instrument, it is a
# side-effect of unrelated merge traffic. Here it runs on every tick that gets
# past the single-instance lock, which is what "every 5 minutes" was supposed
# to mean. (Second time in one day I built an instrument structurally incapable
# of reporting the thing it was built for — cf. the merge monitor that only
# watched for success and so could not distinguish a red PR from a slow one.)
#
# Fail-open by construction: it can neither block nor fail the pull, which
# remains this script's actual job. Remove this block together with the probe
# once the Mini is reachable again.
if [ -f "$REPO/scripts/mini/mini_sos_report.sh" ]; then
  /bin/bash "$REPO/scripts/mini/mini_sos_report.sh" || \
    log "  SOS probe exited non-zero (ignored — the pull is what matters)"
fi

# Skip if not on main — Mini may be temporarily on a feature branch.
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$BRANCH" != "main" ]; then
  log "On branch '$BRANCH' (not main), skip"
  exit 0
fi

# Fetch BOTH remotes best-effort, then follow the most-advanced ref. Pro may
# hold commits not yet pushed to GitHub, and origin may hold commits Pro has
# not pulled (M5 pushes straight to GitHub) — either side can be ahead.
PRO_SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes -i $HOME/.ssh/id_ed25519"
PRO_FETCHED=0
ORIGIN_FETCHED=0
if GIT_SSH_COMMAND="$PRO_SSH" git fetch --quiet pro main 2>>"$LOG_FILE"; then
  PRO_FETCHED=1
else
  log "WARN: git fetch pro failed"
fi
if git fetch --quiet origin main 2>>"$LOG_FILE"; then
  ORIGIN_FETCHED=1
else
  log "WARN: git fetch origin failed"
fi

if [ "$PRO_FETCHED" = "0" ] && [ "$ORIGIN_FETCHED" = "0" ]; then
  log "git fetch failed for both pro and origin (network?), skip"
  telegram_alert "fetch-failed" "Mini could not fetch pro/main or origin/main. Sync skipped."
  exit 0
elif [ "$PRO_FETCHED" = "0" ]; then
  TARGET_REF="origin/main"
  TARGET_REMOTE="origin"
elif [ "$ORIGIN_FETCHED" = "0" ]; then
  TARGET_REF="pro/main"
  TARGET_REMOTE="pro"
elif git merge-base --is-ancestor pro/main origin/main 2>/dev/null; then
  # origin/main contains pro/main (equal counts as ancestor) — origin wins.
  TARGET_REF="origin/main"
  TARGET_REMOTE="origin"
elif git merge-base --is-ancestor origin/main pro/main 2>/dev/null; then
  # pro/main is strictly ahead (Pro has commits not yet on GitHub).
  TARGET_REF="pro/main"
  TARGET_REMOTE="pro"
else
  # Diverged: Pro has unpushed commits AND origin moved past Pro. Follow
  # origin (GitHub authoritative); Pro's unpushed work needs human triage.
  log "WARN: pro/main and origin/main have diverged; following origin/main"
  telegram_alert "pro-origin-diverged" \
    "pro/main and origin/main diverged. Mini follows origin/main; Pro has unpushed commits needing manual push/rebase."
  TARGET_REF="origin/main"
  TARGET_REMOTE="origin"
fi

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse "$TARGET_REF" 2>/dev/null)

# Already up to date — silent (avoid log noise on every 5-min tick).
if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

# Refuse if HEAD has diverged from target ref (not ff-able).
if ! git merge-base --is-ancestor HEAD "$TARGET_REF" 2>/dev/null; then
  if git merge-base --is-ancestor "$TARGET_REF" HEAD 2>/dev/null; then
    log "Local main is ahead of $TARGET_REF; skip pull"
    exit 0
  fi
  log "WARN: HEAD diverged from $TARGET_REF (not ff-able)."
  log "  local=$LOCAL  remote=$REMOTE"

  # 2026-08-11 hardening (W88 discipline — verify by CONTENT, never by SHA-ancestor
  # alone): "diverged" can mean either (a) genuine conflicting local work, or
  # (b) a local commit whose content already landed on the target ref under a
  # DIFFERENT sha (squash-merge, rework, or the recurring case of a cron job —
  # e.g. nb-curator — committing a report directly on this main checkout that
  # later got superseded by the same content merged via a PR). In case (b),
  # HEAD's tree is byte-identical to the target ref's tree despite the
  # divergent history, so resetting to the target ref discards zero content.
  # Self-heal ONLY when the whole-repo diff is empty (not just the file the
  # local commit touched) AND the working tree carries no uncommitted
  # tracked/staged changes to lose. If either fails, fall through to the
  # existing telegram_alert path unchanged.
  if git diff --quiet HEAD "$TARGET_REF" 2>/dev/null \
     && git diff --quiet HEAD 2>/dev/null \
     && git diff --quiet --cached HEAD 2>/dev/null; then
    log "  content-identical to $TARGET_REF (different history, same tree) — attempting self-heal"
    SELFHEAL_OK=0
    if command -v flock >/dev/null 2>&1; then
      exec 9>/tmp/repo-mutating.lock
      if flock --exclusive --timeout 30 9; then
        if git reset --hard --quiet "$TARGET_REF" 2>>"$LOG_FILE"; then
          SELFHEAL_OK=1
        fi
        flock -u 9 2>/dev/null || true
      else
        log "WARN: could not acquire repo-mutating lock for content-identical self-heal, skip this tick"
      fi
    else
      log "WARN: flock not installed; skipping content-identical self-heal (unsafe without lock)"
    fi
    if [ "$SELFHEAL_OK" = "1" ]; then
      log "OK content-identical divergence resolved: reset to $(git rev-parse --short HEAD) (was ${LOCAL:0:9})"
      telegram_alert "diverged-selfheal" \
        "Mini main HEAD had diverged from ${TARGET_REF} but content was identical (local=${LOCAL:0:9}, same tree as remote=${REMOTE:0:9} under a different history) — auto-reset, no content lost."
      exit 0
    fi
    log "  content-identical self-heal did not complete; falling back to alert"
  fi

  # 2026-08-12 hardening (generalizes the block above; recurring shape seen
  # 2026-07-11, 2026-08-09, 2026-08-10, 2026-08-11 — same disease each time):
  # the whole-tree check above only fires when HEAD's ENTIRE tree already
  # matches $TARGET_REF, i.e. ahead-N-behind-0. It CANNOT fire on the far
  # more common shape — ahead N *and* behind M (M>0) — because M legitimate
  # upstream commits also differ from HEAD's tree, so the whole-repo diff is
  # never empty even though the one local-only commit is itself harmless
  # (this is exactly what happened here: a local-only nb-curator report
  # commit landed on this checkout, the SAME content was independently
  # promoted to origin/main under a different sha via a PR, and by the time
  # anyone looked the checkout had also fallen dozens of commits further
  # behind — so the old check could never engage and this cron alerted on
  # cooldown indefinitely with no path to recovery short of an interactive
  # reset). Same W88 discipline, narrowed correctly: verify by CONTENT only
  # the paths HEAD's local-only commit(s) (merge-base..HEAD) actually
  # touched. If EVERY one of those paths already matches $TARGET_REF's
  # current content, `reset --hard $TARGET_REF` provably discards nothing —
  # paths it did not touch are untouched by this decision; they simply gain
  # the legitimate upstream advance, which is the whole point of the pull.
  # Same clean-tree requirement, same lock, same telegram_alert. Falls
  # through unchanged if the merge-base is unknown or a touched path still
  # genuinely differs.
  #
  # 2026-08-12: zero-touched-paths is ALSO safe, not a fall-through case.
  # A local-only commit that changes no files (e.g. an empty merge commit
  # produced when something here merges origin/main instead of
  # fast-forwarding) has, by definition, nothing to lose on reset — the
  # `-eq 0 ||` short-circuit below fires before the unsafe
  # "${TOUCHED_PATHS[@]}" expansion is ever reached. Order matters: bash
  # 3.2 under `set -u` raises unbound-variable on that expansion when the
  # array is empty, so the length check MUST be first and MUST short-
  # circuit (`||`), never `-gt 0 &&` (which silently refused this case
  # instead of crashing — 850 refused ticks 2026-05-10..2026-08-12).
  if [ "${SELFHEAL_OK:-0}" != "1" ]; then
    MERGE_BASE=$(git merge-base HEAD "$TARGET_REF" 2>/dev/null)
    if [ -n "$MERGE_BASE" ] \
       && git diff --quiet HEAD 2>/dev/null \
       && git diff --quiet --cached HEAD 2>/dev/null; then
      TOUCHED_PATHS=()
      while IFS= read -r -d '' _p; do
        TOUCHED_PATHS+=("$_p")
      done < <(git diff --name-only -z "$MERGE_BASE" HEAD 2>/dev/null)
      if [ "${#TOUCHED_PATHS[@]}" -eq 0 ] \
         || git diff --quiet HEAD "$TARGET_REF" -- "${TOUCHED_PATHS[@]}" 2>/dev/null; then
        log "  every path HEAD's local-only commit(s) touched already matches $TARGET_REF (ahead+behind shape, ${#TOUCHED_PATHS[@]} path(s)) — attempting narrow self-heal"
        SELFHEAL_OK=0
        if command -v flock >/dev/null 2>&1; then
          exec 9>/tmp/repo-mutating.lock
          if flock --exclusive --timeout 30 9; then
            if git reset --hard --quiet "$TARGET_REF" 2>>"$LOG_FILE"; then
              SELFHEAL_OK=1
            fi
            flock -u 9 2>/dev/null || true
          else
            log "WARN: could not acquire repo-mutating lock for narrow self-heal, skip this tick"
          fi
        else
          log "WARN: flock not installed; skipping narrow self-heal (unsafe without lock)"
        fi
        if [ "$SELFHEAL_OK" = "1" ]; then
          log "OK ahead+behind divergence resolved (narrow content-check): reset to $(git rev-parse --short HEAD) (was ${LOCAL:0:9})"
          telegram_alert "diverged-selfheal-narrow" \
            "Mini main HEAD had local-only commit(s) diverged from ${TARGET_REF}, but every path they touched already matched target content — auto-reset, no content lost (${LOCAL:0:9} -> $(git rev-parse --short HEAD))."
          exit 0
        fi
        log "  narrow self-heal did not complete; falling back to alert"
      fi
    fi
  fi

  telegram_alert "diverged" \
    "Mini main HEAD diverged from ${TARGET_REF} (local=${LOCAL:0:9} vs remote=${REMOTE:0:9}). Manual rebase needed."
  exit 1
fi

# 2026-05-06 hardening: detect symlink↔dir mismatches BEFORE attempting stash.
# These happened with apps/backend-rag/.venv (origin symlink, Mini real 762MB dir).
if ! check_type_mismatch; then
  exit 1
fi

# 2026-07-11 hardening (2026-07-17 skip→resolve): back up + move aside untracked/ignored
# collisions BEFORE the stash step so the ff can land (self-heals instead of stalling, and
# catches the ignored-file silent-clobber the old --exclude-standard check missed — scar H).
# See resolve_untracked_collision() above.
if ! resolve_untracked_collision; then
  log "ERROR: untracked-collision resolve failed; skip tick (fail-safe)"
  telegram_alert "untracked-resolve-failed" "Mini pull: untracked-collision resolve errored; tick skipped, nothing merged. Check ~/logs/mini-git-pull.log."
  exit 1
fi

# 2026-05-10 Fase 0c hardening: acquire repo-mutating exclusive lock so
# Cluster C/D cron jobs do not read half-rewritten .py / .yaml during git
# pull. Cron jobs use `flock --shared` on the same lock during their
# startup phase. Timeout 30s — if not acquired, skip this 5min tick.
if ! command -v flock >/dev/null 2>&1; then
  log "WARN: flock not installed (brew install flock); skipping repo-mutating lock"
else
  REPO_LOCK="/tmp/repo-mutating.lock"
  exec 8>"$REPO_LOCK"
  if ! flock --exclusive --timeout 30 8; then
    log "WARN: could not acquire $REPO_LOCK in 30s — cron job is reading repo, skip this tick"
    exit 0
  fi
  # Lock auto-released on exit (fd 8 closes); add to trap so explicit cleanup is safe.
  trap 'flock -u 8 2>/dev/null || true; rm -f "$LOCK_FILE"' EXIT
fi

# Check stash retention (sign of repeated pop failures).
STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')
if [ "$STASH_COUNT" -gt "$STASH_RETENTION_THRESHOLD" ]; then
  log "WARN: $STASH_COUNT stashes accumulated (threshold $STASH_RETENTION_THRESHOLD)."
  telegram_alert "stash-bloat" \
    "Mini has ${STASH_COUNT} stashes accumulated. Likely repeated pop conflicts. \`git stash list\` on Mini."
fi

COMMITS_BEHIND=$(git rev-list --count HEAD.."$TARGET_REF" 2>/dev/null || echo "?")

# Stash only tracked dirty files. Untracked survive ff-only pulls
# untouched anyway, no need to stash them (and they may be huge — like
# the 762 MB .venv dir that bit us).
STASHED=0
DIRTY_TRACKED=$(git diff --name-only HEAD 2>/dev/null)
DIRTY_STAGED=$(git diff --cached --name-only 2>/dev/null)
if [ -n "$DIRTY_TRACKED" ] || [ -n "$DIRTY_STAGED" ]; then
  STASH_MSG="mini-git-pull-auto $(date +%Y-%m-%d_%H:%M:%S)"
  # `git stash push` without `--include-untracked` only stashes tracked
  # changes. This is what we want.
  if git stash push --quiet -m "$STASH_MSG" 2>>"$LOG_FILE"; then
    STASHED=1
    log "Stashed tracked changes ('$STASH_MSG'), pulling $COMMITS_BEHIND commits from $TARGET_REF..."
  else
    log "ERROR: git stash failed, skip"
    telegram_alert "stash-failed" "git stash failed on Mini. Manual triage."
    exit 1
  fi
else
  log "Clean tracked tree, pulling $COMMITS_BEHIND commits from $TARGET_REF..."
fi

# Pull ff-only.
if ! git merge --ff-only --quiet "$TARGET_REF" 2>>"$LOG_FILE"; then
  log "ERROR: git merge --ff-only $TARGET_REF failed"
  telegram_alert "pull-failed" "git merge --ff-only ${TARGET_REF} failed on Mini. Probably new mismatch type appeared."
  if [ "$STASHED" = "1" ]; then
    log "  attempting to restore stash..."
    git stash pop --quiet 2>>"$LOG_FILE" || \
      log "  WARN: stash pop failed too — stash retained"
  fi
  exit 1
fi

NEW_HEAD=$(git rev-parse --short HEAD)
log "OK pulled to $NEW_HEAD ($COMMITS_BEHIND commits from $TARGET_REMOTE)"

# Keep the launchd-safe deployed script in sync with the repo source. The
# LaunchAgent executes ~/scripts/mini-git-pull.sh because macOS TCC can block
# direct execution from ~/Desktop.
mkdir -p "$HOME/scripts" 2>/dev/null
if [ -f "$REPO/scripts/mini/mini-git-pull.sh" ]; then
  if ! cmp -s "$REPO/scripts/mini/mini-git-pull.sh" "$HOME/scripts/mini-git-pull.sh" 2>/dev/null; then
    cp "$REPO/scripts/mini/mini-git-pull.sh" "$HOME/scripts/mini-git-pull.sh" 2>>"$LOG_FILE" && \
      chmod 755 "$HOME/scripts/mini-git-pull.sh" 2>/dev/null && \
      log "  updated ~/scripts/mini-git-pull.sh from repo source"
  fi
fi

# 2026-05-11 TCC-safe sync via git checkout (cp falliva su TCC, ma
# git binary ha FDA implicito quindi git --git-dir + --work-tree va).
# git esce 0 anche per "no change", quindi check exit + verifica file.
mkdir -p "$HOME/agent-config" 2>/dev/null
if git --git-dir="$REPO/.git" --work-tree="$HOME/agent-config" \
       checkout "$TARGET_REF" -- config/job-ownership.yaml 2>>"$LOG_FILE"; then
  if [ -f "$HOME/agent-config/config/job-ownership.yaml" ]; then
    # Move into root for backwards compat ($HOME/agent-config/job-ownership.yaml)
    mv "$HOME/agent-config/config/job-ownership.yaml" \
       "$HOME/agent-config/job-ownership.yaml" 2>/dev/null || true
    rmdir "$HOME/agent-config/config" 2>/dev/null || true
    log "  synced config/job-ownership.yaml -> ~/agent-config/ (via git checkout)"
  fi
else
  log "  WARN: failed to sync job-ownership.yaml to ~/agent-config/"
fi

# Restore stash. Conflict-tolerant: on conflict, leave stash for human review.
if [ "$STASHED" = "1" ]; then
  if git stash pop --quiet 2>>"$LOG_FILE"; then
    log "  stash restored cleanly"
  else
    log "  WARN: stash pop conflict — stash retained."
    telegram_alert "stash-pop-conflict" \
      "stash pop conflict on Mini after ff-pull to ${NEW_HEAD}. \`git status\` + \`git stash list\` on Mini."
    # Don't exit error — pull succeeded. Conflict is a separate issue.
  fi
fi
