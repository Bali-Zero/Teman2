#!/bin/zsh
# regulatory-watcher cron wrapper — multi-LLM cascade
# Order: all Claude OAuth seats (Sonnet 5) → Gemini 3.1 Pro free → Codex GPT-5.5 → Ollama qwen3.5:9b local
# Cost: 0$ (4 tier all subscription/free/local)
#
# TAC-2 A4 (2026-07-05) — the 07-05 run failure taught four lessons, all cured here:
#   1. sonnet-5 in --print mode spawned its 6-step work as a BACKGROUND task; the CLI
#      terminated it at the 600s print ceiling and exited 0 → wrapper marked SUCCESS
#      with no delta on disk. Cure: raise the ceiling + tell the model to work inline.
#   2. "exit 0 + no quota marker" is NOT success for a job whose contract is a file.
#      Cure: every tier's success now requires the delta file to EXIST (ensure_delta).
#   3. Tiers 2-4 print JSON to stdout but cannot write files → they were alert-theater.
#      Cure: ensure_delta extracts a valid delta JSON from the tier's output.
#   4. The launchd context can lose TCC on ~/Desktop (W84; Pro reboot 07-04) making the
#      whole contract unfulfillable. Cure: fail FAST and LOUD (exit 78) instead of
#      burning 4 LLM tiers to then discover the file can't land.

# NO `-e`: each tier may exit non-zero and the cascade MUST survive to capture
# EXIT=$? and fall through to the next tier (guardian-of-guardians audit 2026-06-11;
# with -e the script died at the first failing tier and fallback never fired).
set -uo pipefail

# Defense-in-depth: never pay-per-token Anthropic
unset ANTHROPIC_API_KEY

# nlm-profile (2026-06-10): single-account consolidation. zero@balizero.com is
# DECOMMISSIONED as an NLM account (login problems / expiring). All NB live under
# antonellosiano@gmail.com = the `default` profile (86 NB, 3622 sources). The old
# `zero` profile was itself logged in as antonellosiano@ and has been deleted.
# Empirically verified 2026-06-10: default sees identical NB-INTEL UUIDs.
export NLM_PROFILE=default

[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

# sshd (W84 trampoline) and bare launchd contexts carry a minimal PATH — codex
# is a node shebang script and dies with "env: node: No such file or directory"
# without homebrew on PATH (proved live 2026-07-06 05:09).
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

# Which ChatGPT Pro seat tier 3 uses.
#
# TWO candidate paths on purpose, and the second is the load-bearing one HERE:
# the live copy of this wrapper on Pro is a REAL FILE at ~/scripts (a declared
# HOME-fork pair, family #1), not a symlink into the checkout — so the
# script-relative path resolves to /Users/scripts/lib/... and finds nothing,
# and the cure would have been inert on the one machine that needs it. The
# script-relative path still comes first so a worktree tests its OWN lib.
#
# Missing lib degrades to codex's own default seat, i.e. the pre-2026-08-12
# behaviour. A bare `source` of an absent file is a special builtin that EXITS
# the shell under set -e, hence the [ -f ] guard rather than an `|| true`.
codex_seat_pick() { :; }
for _seat_lib in "${0:A:h}/../../../scripts/lib/codex_seat.sh" \
                 "$HOME/nuzantara/scripts/lib/codex_seat.sh"; do
    if [ -f "$_seat_lib" ]; then
        source "$_seat_lib"
        break
    fi
done

mkdir -p "$HOME/nuzantara/research/regulatory" "$HOME/logs"

LOG="$HOME/logs/regulatory-watcher.log"
DATE=$(TZ=Asia/Makassar date +%Y-%m-%d)
DELTA_JSON="$HOME/nuzantara/research/regulatory/${DATE}-delta.json"
DELTA_BASENAME="${DATE}-delta.json"
# worktree_isolation.py is a HARD, never-bypassed guard (PENDING-ARMS L1464/L2361):
# it blocks an agent SESSION (tier 1 is a real Claude session) from writing into
# the tracked main checkout, even though this wrapper's OWN git ops below are
# plain shell and are not bound by it. Measured live 2026-09-27: tier 1 did the
# full analysis (NB-INTEL + 11 web sources) then hit the guard at Step 5 and
# stalled asking the operator for a decision — the completed, non-partial delta
# sat unused at /tmp/${DATE}-delta.json. Tier 1's agent spec (Step 5) now writes
# to a scratch path outside the tracked tree; recover_delta() promotes it.
#
# NOT /tmp (fixed post-merge, gate REWORK-BUILD on head 7753eac1): /tmp is
# world-writable with a predictable, guessable name — the gate proved live that
# ANY local process (including tier 3's own codex, which this same PR just gave
# real network access) could drop a markdown file, a schema-invalid JSON, or a
# symlink to a secrets file at that exact path and have it promoted straight
# into the PUBLIC repo via promote_delta_via_pr(), since the old recover_delta()
# did a blind `cp` with no validation. Cure has two independent layers: (1) this
# directory is private (0700, this user only) instead of world-writable, and
# (2) recover_delta() below refuses a symlink or a file it doesn't own, and
# promotes ONLY through extract_delta_from_output()'s schema check +
# re-serialization — never a byte-for-byte copy of untrusted content.
DELTA_SCRATCH_DIR="$HOME/.agent/regulatory-watcher/${DATE}"
mkdir -p "$DELTA_SCRATCH_DIR" && chmod 0700 "$DELTA_SCRATCH_DIR"
DELTA_SCRATCH="$DELTA_SCRATCH_DIR/${DELTA_BASENAME}"

# W84 fail-fast probe (TAC-2 A4): if this launchd context cannot READ ~/Desktop
# (TCC grant lost — observed on Pro after the 2026-07-04 reboot: the zsh job got
# "Operation not permitted" while a bash-rooted job read ~/Desktop fine), the
# delta can never land. Abort loudly with exit 78 (config error) BEFORE burning
# LLM tiers; launchd's non-zero exit is picked up by launchd_liveness_detector.
# NB: must be a REAL read (head -c 1), not `[ -r ]` — TCC denies at open(2),
# while access(2) can still say yes (the probe itself must not be a proxy).
if ! head -c 1 "$HOME/nuzantara/CLAUDE.md" >/dev/null 2>&1; then
    # W84 TRAMPOLINE (2026-07-06): before aborting, re-exec THIS wrapper through
    # `ssh localhost` — the sshd context has Full Disk Access, so the whole run
    # (zsh, node/claude, file writes under ~/Desktop) works uniformly regardless
    # of which per-binary TCC rows launchd lost at the last reboot. Probe matrix
    # 2026-07-06 04:52 on Pro (launchd ctx): zsh/head/bash-builtin/python3 all
    # DENIED, bash+head OK — per-binary whack-a-mole, while sshd reads fine.
    # Same-user localhost key (no privilege change), from=127.0.0.1/::1
    # restriction in authorized_keys. REGWATCH_TRAMPOLINED guards exec loops
    # if sshd were ALSO denied.
    if [ -z "${REGWATCH_TRAMPOLINED:-}" ] && [ -f "$HOME/.ssh/id_local_trampoline" ]; then
        echo "[$(date)] W84: TCC denies ~/Desktop in this launchd context — re-exec via ssh-localhost trampoline (sshd has FDA)" >> "$LOG"
        exec ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i "$HOME/.ssh/id_local_trampoline" localhost "REGWATCH_TRAMPOLINED=1 '$0'"
    fi
    echo "[$(date)] FATAL: TCC denies ~/nuzantara in this launchd context (W84) and no trampoline key — re-grant Full Disk Access to the job's interpreter. Aborting before any LLM tier." >> "$LOG"
    exit 78
fi

# sonnet-5 --print + background tasks (2026-07-05): the CLI kills backgrounded
# work after 600s by default. 30 min ceiling keeps a legitimate long run alive;
# the prompt below also forbids backgrounding outright.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

# Organism heartbeat (heartbeat-organs TAC 2026-07-02): reverse-promoted from the
# M5 HOME copy 2026-07-03 — the instrumentation lived only in ~/scripts and never
# reached the repo canon (#1 HOME-fork reverse debt, caught by proprioception).
# Lib resolution prefers ~/scripts/lib (OUTSIDE the TCC-protected ~/Desktop —
# superscar #1 antidote: relocate payloads out of Desktop) and falls back to the
# repo canon. Arming the ~/scripts/lib copy on Pro/M5 is tracked in PENDING-ARMS.
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
    HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$HOME/scripts/lib/heartbeat.sh" ]; then
    HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
else
    HEARTBEAT_LIB="$HOME/nuzantara/scripts/lib/heartbeat.sh"
fi
ORGANISM_HB_STATUS="starting"
ORGANISM_HB_NOTE="regulatory watcher start"

organism_hb_set() {
    ORGANISM_HB_STATUS="$1"
    ORGANISM_HB_NOTE="${2:-}"
}

organism_hb_finalize() {
    local rc="${1:-0}"
    if [ "$rc" -eq 0 ]; then
        if [ "$ORGANISM_HB_STATUS" = "starting" ]; then
            organism_hb_set ok "completed"
        fi
    elif [ "$ORGANISM_HB_STATUS" = "starting" ] || [ "$ORGANISM_HB_STATUS" = "ok" ]; then
        organism_hb_set error "rc=${rc}"
    fi
    if [ -f "$HEARTBEAT_LIB" ]; then
        bash "$HEARTBEAT_LIB" "pro.regulatory_watcher_daily" "$ORGANISM_HB_STATUS" "$ORGANISM_HB_NOTE" || true
    fi
}

# Single-instance lock (2026-07-06): two instances ran CONCURRENTLY today —
# this session's induced test + a sibling session's (#1999) — racing on the
# same delta file with duplicate bus emits and duplicate-Telegram risk
# (family #5 sibling-race, on the DATA instead of the repo). macOS ships no
# flock(1), so: atomic mkdir + pid-liveness. A concurrent duplicate
# SELF-RESOLVES — it logs its own launch-context (forensic breadcrumb) and
# exits 0, no operator in the loop. A stale lock (crashed run, dead pid) is
# taken over automatically. Placed AFTER the W84 trampoline block so only
# the run that will actually do the work holds it.
REGWATCH_LOCKDIR="$HOME/.regulatory-watcher.lock"
if ! mkdir "$REGWATCH_LOCKDIR" 2>/dev/null; then
    OTHER_PID=$(cat "$REGWATCH_LOCKDIR/pid" 2>/dev/null || echo "")
    if [ -n "$OTHER_PID" ] && kill -0 "$OTHER_PID" 2>/dev/null; then
        echo "[$(date)] duplicate instance suppressed: lock held by live pid=$OTHER_PID; suppressed launch-context: pid=$$ ppid=$PPID parent=$(ps -o comm= -p $PPID 2>/dev/null || echo dead) lang=${LANG:-unset} ssh=${SSH_CONNECTION:-none} trampolined=${REGWATCH_TRAMPOLINED:-0}" >> "$LOG"
        exit 0
    fi
    echo "[$(date)] stale lock (pid=${OTHER_PID:-none} dead) — taking over" >> "$LOG"
    rm -rf "$REGWATCH_LOCKDIR"
    if ! mkdir "$REGWATCH_LOCKDIR" 2>/dev/null; then
        echo "[$(date)] lock race lost after stale takeover — exiting clean" >> "$LOG"
        exit 0
    fi
fi
echo $$ > "$REGWATCH_LOCKDIR/pid"

trap 'rc=$?; organism_hb_finalize "$rc"; rm -rf "$REGWATCH_LOCKDIR"' EXIT

echo "[$(date)] regulatory-watcher run starting for $DATE" >> "$LOG"
# Forensic breadcrumb (2026-07-06): an unexplained parallel instance appeared at
# 09:19:58 (orphaned before inspection — ppid already 1, no ssh session, no cron,
# no launchd label matched). Log enough launch-context that the NEXT unexplained
# instance names its own parent while it is still alive in the log line.
echo "[$(date)] launch-context: pid=$$ ppid=$PPID parent=$(ps -o comm= -p $PPID 2>/dev/null || echo dead) lang=${LANG:-unset} ssh=${SSH_CONNECTION:-none} trampolined=${REGWATCH_TRAMPOLINED:-0}" >> "$LOG"

PROMPT_CLAUDE="Run the regulatory-watcher agent for today ($DATE). Execute all 6 workflow steps autonomously. Read ~/.claude/agents/regulatory-watcher.md for full spec. Today is $DATE WITA. Yesterday's delta file (if any) is in ~/nuzantara/research/regulatory/ (read-only lookup, that path is fine). Emit JSON to the private SCRATCH path named in the spec's Step 5 (${DELTA_SCRATCH}) — NOT directly into ~/nuzantara/research/regulatory/, which the worktree_isolation guard blocks for an agent session, and NOT /tmp — and Telegram alert only if new_today_count > 0. IMPORTANT: do ALL the work INLINE in this session — never spawn background tasks or background agents: this is a one-shot print-mode run and backgrounded work is terminated at exit, leaving no file on disk (incident 2026-07-05)."

# Generic prompt re-usable across LLMs (no Claude-specific syntax)
PROMPT_GENERIC="You are the regulatory-watcher for Bali Zero (Indonesian business services agency). Today is $DATE WITA. Task: detect new Indonesian regulations published in last 48h that affect Bali Zero service lines (visa/immigration, tax, property, regulatory/HR, health). Sources to query (use whichever you can reach): Hukumonline, Ortax, DDTC, MUC, IKPI (news at ikpi.or.id/berita/ — NOT /news/, which 404s), JDIH Kemenkumham/Kemenkeu/Kemnaker, peraturan.go.id (with Mozilla User-Agent), pajak.go.id. Filter to reg-types: Permenkumham, PMK, PP, Perpres, UU, Permenaker, Permenkes, Peraturan BKPM. Emit JSON to ~/nuzantara/research/regulatory/${DATE}-delta.json with schema: {run_at, today, new_today_count, partial:bool, unreachable_sources:[{url,reason,note?}] (default [], reason one of http_403|http_404|timeout|ssl_error|empty_shell — genuine fetch failures ONLY), sources_checked_no_delta:[{url,reason,note?}] (default [], reason one of checked_no_new|outside_window — a source you DID read successfully and found nothing new in; never put these in unreachable_sources), nb_query_errors:[] (default [], always present even when empty), deltas:[{citation,title_id,title_en,service_line,summary,source,verbatim_excerpt}], seen_citations}. Each source you attempt goes in exactly one of unreachable_sources or sources_checked_no_delta — never free-text prose, never omitted keys. Retry a dead source at most once, then record it and move on — never loop on a source. If new_today_count>0, send Telegram via curl to api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/sendMessage chat_id=\$TELEGRAM_OWNER_CHAT_ID. Cite verbatim. No paraphrasing. No emoji in JSON."

TMPOUT=$(mktemp)
SUCCESS=0
USED_LLM=""
CASCADE_BIN="${REGWATCH_CLAUDE_CASCADE_BIN:-$HOME/scripts/claude-cascade.sh}"
[ -x "$CASCADE_BIN" ] || CASCADE_BIN="$HOME/nuzantara/infra/launchagents/wrappers/claude-cascade.sh"

# Stdlib-only python for the output-extractor (json only — no redis needed here).
# The pyenv pin below (eventbus block) stays Pro-specific; this one must work on
# any machine the wrapper is deployed to.
PYBIN="${REGWATCH_PYTHON:-$(command -v python3 || echo /usr/bin/python3)}"

# W81-fix (2026-06-15), zsh-native rewrite (TAC-2 A4): the cron `claude` runs with
# W79 worktree-isolation hooks active, so it may write the delta to a worktree
# branch instead of the main checkout. Recover it. (N.om) = null_glob + plain
# files + mtime-desc: the old `ls -t glob` printed "no matches found" noise AND
# would have listed the whole cwd under null_glob with an empty expansion.
recover_delta() {
    # Tier 1 writes here now (see DELTA_SCRATCH above) instead of attempting a
    # direct write the worktree_isolation guard would refuse. Check it before
    # the worktree-glob paths below — it is the common case, not a fallback.
    #
    # HARDENED post-merge (gate REWORK-BUILD on head 7753eac1): the previous
    # version did a blind `cp` — no symlink check, no ownership check, no
    # content validation. Proved live: a markdown file, `{"hello":"world"}`,
    # and a symlink to a canary secrets file were all promoted (rc=0, canary
    # content copied) straight toward promote_delta_via_pr()'s commit+push+
    # auto-merge into the PUBLIC repo; only partial:true was rejected. Even
    # with DELTA_SCRATCH now under a private 0700 dir (defense layer 1), this
    # function never trusts what it finds there (defense layer 2) — it
    # refuses a symlink or a file it does not own BEFORE reading anything,
    # and promotes ONLY through extract_delta_from_output()'s schema check +
    # re-serialization, never a byte-for-byte copy.
    if [ -L "$DELTA_SCRATCH" ]; then
        echo "[$(date)] REFUSED: $DELTA_SCRATCH is a symlink — not promoted (untrusted staging path; possible attack)" >> "$LOG"
        return 1
    fi
    if [ -e "$DELTA_SCRATCH" ]; then
        if [ ! -f "$DELTA_SCRATCH" ]; then
            echo "[$(date)] REFUSED: $DELTA_SCRATCH exists but is not a regular file — not promoted" >> "$LOG"
            return 1
        fi
        if [ ! -O "$DELTA_SCRATCH" ]; then
            echo "[$(date)] REFUSED: $DELTA_SCRATCH is not owned by this process (uid mismatch) — not promoted" >> "$LOG"
            return 1
        fi
        if ! extract_delta_from_output "$DELTA_SCRATCH"; then
            echo "[$(date)] REFUSED: $DELTA_SCRATCH is not parseable JSON matching the delta schema (no {..} object with new_today_count+deltas keys) — not promoted, left in place for manual inspection" >> "$LOG"
            return 1
        fi
        delta_is_partial
        local _partial_rc=$?
        if [ "$_partial_rc" -eq 1 ]; then
            echo "[$(date)] recovered delta from tier-1 scratch file $DELTA_SCRATCH -> main (schema-validated + re-serialized via extract_delta_from_output; worktree_isolation blocks a direct session write)" >> "$LOG"
            rm -f "$DELTA_SCRATCH"
            return 0
        fi
        rm -f "$DELTA_JSON"
        if [ "$_partial_rc" -eq 0 ]; then
            echo "[$(date)] REFUSED: $DELTA_SCRATCH parsed but partial:true — recover_delta only lands COMPLETE deltas, not promoted" >> "$LOG"
        else
            echo "[$(date)] REFUSED: $DELTA_SCRATCH extracted but delta_is_partial rejected it as invalid (rc=$_partial_rc) — not promoted" >> "$LOG"
        fi
        return 1
    fi
    setopt local_options null_glob
    local -a _hits
    _hits=( "$HOME"/nuzantara/.worktrees/*/research/regulatory/"$DELTA_BASENAME"(N.om) )
    if (( ${#_hits} > 0 )); then
        cp "${_hits[1]}" "$DELTA_JSON" && echo "[$(date)] W81-fix: recovered delta from worktree file ${_hits[1]} -> main" >> "$LOG"
        return 0
    fi
    local _wt_branch
    _wt_branch="$(cd "$HOME/nuzantara" && git for-each-ref --sort=-committerdate --format='%(refname:short)' 'refs/heads/agent/*/intel/watcher-*' 2>/dev/null | head -1)"
    if [ -n "$_wt_branch" ] && (cd "$HOME/nuzantara" && git cat-file -e "$_wt_branch:research/regulatory/$DELTA_BASENAME" 2>/dev/null); then
        (cd "$HOME/nuzantara" && git show "$_wt_branch:research/regulatory/$DELTA_BASENAME") > "$DELTA_JSON" \
          && echo "[$(date)] W81-fix: recovered delta from branch $_wt_branch -> main" >> "$LOG"
        return 0
    fi
    # W105-#68 (2026-07-27): an exact-name miss above is not proof nothing exists
    # for today. Measured live 2026-07-25: a manually-produced, COMPLETE
    # (non-partial) delta with real findings sat for two days under
    # .worktrees/regulatory-watcher-2026-07-25/research/regulatory/, renamed to
    # `...manual-session-DO-NOT-RECOVER` specifically to defeat the glob above —
    # and nothing logged that it had happened, so the evasion was indistinguishable
    # from an honest absence. Do NOT auto-recover a near-miss (an unverified rename
    # could be untrustworthy content the operator meant to discard) but DO log it,
    # so the next reader of this log can go look instead of assuming a clean day.
    setopt local_options null_glob
    local -a _near_misses
    _near_misses=( "$HOME"/nuzantara/.worktrees/*/research/regulatory/*"$DATE"*(N.om) )
    if (( ${#_near_misses} > 0 )); then
        echo "[$(date)] W105-#68: ${#_near_misses} file(s) under .worktrees/*/research/regulatory/ mention $DATE but do not match the exact expected name $DELTA_BASENAME — NOT auto-recovered, needs a manual look: ${_near_misses[*]}" >> "$LOG"
    fi
    return 1
}

# Tiers 2-4 print JSON to stdout but cannot write files (agy/ollama are pure
# text-out) — without this they were alert-theater: "success" with no artifact.
# Extract the first parseable object carrying the delta schema and land it.
extract_delta_from_output() {
    local _src="$1"
    "$PYBIN" - "$_src" "$DELTA_JSON" <<'PYEOF' 2>>"$LOG"
import json, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8", errors="replace").read()
best = None
for start in [i for i, ch in enumerate(text) if ch == "{"]:
    depth = 0
    for end in range(start, min(len(text), start + 200_000)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start:end + 1]
                try:
                    obj = json.loads(chunk)
                except Exception:
                    break
                if isinstance(obj, dict) and "new_today_count" in obj and "deltas" in obj:
                    best = obj
                break
    if best is not None:
        break
if best is None:
    sys.exit(1)
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(best, fh, ensure_ascii=False, indent=2)
print(f"extracted delta JSON from LLM output -> {dst}")
PYEOF
}

# The tier contract (TAC-2 A4): a tier SUCCEEDED only if the delta file exists —
# on disk, recovered from a worktree, or extracted from the tier's own output.
# "exit 0" alone marked the 2026-07-05 hallucinated/backgrounded run as green.
ensure_delta() {
    local _out="$1"
    [ -f "$DELTA_JSON" ] && return 0
    recover_delta && [ -f "$DELTA_JSON" ] && return 0
    extract_delta_from_output "$_out" && [ -f "$DELTA_JSON" ] && return 0
    return 1
}

# 2026-07-20 live find: a delta can satisfy the schema (new_today_count + deltas
# keys) while the model admits `partial:true` — proved live when Claude+agy+Codex
# all missed on the same run and ollama qwen3.5 (no web access) answered "I cannot
# browse JDIH/peraturan.go.id... I will provide a JSON structure reflecting zero
# new findings" and then emitted a schema-valid {new_today_count:0, partial:true}
# stub. ensure_delta()'s schema check (has the right KEYS) cannot tell that stub
# apart from a real completed scan that genuinely found nothing — only `partial`
# does. A false "0 new" is worse than a visible gap: a gap is honestly absent,
# this looks like a clean day and silently is not one.
#
# THREE-way exit code, not two (hardened post-merge, gate REWORK-BUILD on head
# 7753eac1): unparsable/non-dict JSON used to exit(1) — the SAME code as a
# genuinely valid partial:false delta — so a caller checking only "0 vs
# nonzero" (the original `if delta_is_partial; then ...` shape) could not
# tell "confirmed clean" from "garbage, never even parsed" and silently
# accepted garbage as clean. 0 = partial:true (reject, cascade, as before);
# 1 = confirmed valid JSON with partial:false/absent (accept, unchanged);
# 2 = invalid — did not parse, or parsed to something other than a JSON
# object (MUST be treated as worse than partial by every caller: reject and
# say why, never fall through as "not partial").
delta_is_partial() {
    [ -f "$DELTA_JSON" ] || return 1
    "$PYBIN" -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(2)
if not isinstance(d, dict):
    sys.exit(2)
sys.exit(0 if d.get("partial") else 1)
' "$DELTA_JSON"
}

# --- self-commit cure (cure-A, PR #7 mandate) --------------------------------
# The delta above lands straight into the main checkout's TRACKED tree
# ($REPO_ROOT/research/regulatory/) and this wrapper never committed it — same
# disease scripts/translate-articles-cron-wrapper.sh cured for the mouth hourly
# translations (PR #3762). PR #3756 already promoted the one-shot backlog
# (9 stranded deltas, 2026-06-30..2026-08-07) — this is the missing structural
# half: promote the delta THIS run lands, every run, via an ephemeral worktree
# (scripts/agent_start.py) + auto-merge PR. The main checkout itself is never
# touched by git — only files inside the worktree are added/committed/pushed.
# Kill switch: REGWATCH_PROMOTE_ENABLED=false skips this step (deliberate stop,
# the delta itself and its Telegram alert/eventbus emission are unaffected).
REGWATCH_REPO_ROOT="$HOME/nuzantara"

# gh-cwd fix (2026-08-31, W-promote-silence twin): cwd-safety in this function
# was applied per-TOOL (every `git` call below is `git -C "$_wt" ...`), not per
# REQUIREMENT ("this command needs to know which repo it's in") — the two `gh`
# calls were missed. `gh` resolves its target repo from the PROCESS cwd, which
# under launchd is not inside any git checkout, so both calls failed resolution
# before ever reaching the GitHub API: `fatal: not a git repository (or any of
# the parent directories): .git`, ten consecutive days in
# ~/logs/regulatory-watcher.log, every day right after the push succeeded.
# `-C "$_wt"` (the flag the `git` calls use) has no `gh` equivalent that helps
# here; `--repo owner/repo` is `gh`'s own cwd-independent form. Proved live:
# `(cd /tmp && gh pr create --repo Bali-Zero/Teman2 --head <nonexistent> ...)`
# reaches the GraphQL API (fails on the fake branch, not on repo resolution),
# while the same command without `--repo` reproduces the exact log string
# above. Matches the existing convention in scripts/lane_ship.sh.
REGWATCH_GH_REPO="${REGWATCH_GH_REPO:-Bali-Zero/Teman2}"
promote_delta_via_pr() {
    local _rel="research/regulatory/${DELTA_BASENAME}"
    [ -f "$DELTA_JSON" ] || return 0
    if [ "${REGWATCH_PROMOTE_ENABLED:-true}" = "false" ]; then
        echo "[$(date)] promote: REGWATCH_PROMOTE_ENABLED=false — skipping (deliberate stop)" >> "$LOG"
        return 0
    fi

    # Already on origin/main with identical bytes? Nothing to promote — covers
    # a manual re-run after a successful promotion the same day.
    if (cd "$REGWATCH_REPO_ROOT" && git show "origin/main:$_rel" 2>/dev/null | cmp -s - "$DELTA_JSON"); then
        echo "[$(date)] promote: $_rel already on origin/main, byte-identical — nothing to do" >> "$LOG"
        return 0
    fi

    (cd "$REGWATCH_REPO_ROOT" && python3 scripts/agent_start.py --cleanup) >> "$LOG" 2>&1

    local _task_id="regwatch-$(date +%Y%m%d%H%M%S)"
    local _create_out
    _create_out=$(cd "$REGWATCH_REPO_ROOT" && python3 scripts/agent_start.py --lane intel --task-id "$_task_id" --ttl-min 30 2>>"$LOG")
    local _wt
    _wt=$(print -r -- "$_create_out" | awk '/^WORKTREE_READY/ {print $2}')
    if [ -z "$_wt" ] || [ ! -d "$_wt" ]; then
        echo "[$(date)] promote: FATAL worktree creation failed: $_create_out" >> "$LOG"
        return 1
    fi

    mkdir -p "$_wt/research/regulatory"
    cp "$DELTA_JSON" "$_wt/$_rel"

    local _changed
    _changed=$(git -C "$_wt" status --porcelain -- "$_rel" | wc -l | tr -d ' ')
    if [ "$_changed" -eq 0 ]; then
        echo "[$(date)] promote: no diff inside worktree after copy — releasing" >> "$LOG"
        (cd "$REGWATCH_REPO_ROOT" && python3 scripts/agent_start.py --release "$_task_id") >> "$LOG" 2>&1
        return 0
    fi

    local _branch
    _branch=$(git -C "$_wt" branch --show-current)
    git -C "$_wt" add "$_rel"
    git -C "$_wt" commit -m "$(cat <<EOF
chore(regulatory): promote ${DATE} delta (${USED_LLM:-unknown-tier})

Auto-generated by infra/launchagents/wrappers/regulatory-watcher-run.sh
(com.balizero.regulatory-watcher.daily). The delta lands straight into the
main checkout's tracked tree and this wrapper never committed it (same
disease PR #3762 cured for translate-articles.py; PR #3756 did the one-time
promotion of the backlog — this is the recurring structural half). Run in an
isolated worktree so the main checkout is never touched by git.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
    )" >> "$LOG" 2>&1

    git -C "$_wt" push -u origin "$_branch" >> "$LOG" 2>&1
    if [ $? -ne 0 ]; then
        echo "[$(date)] promote: push failed — leaving worktree $_wt for manual recovery" >> "$LOG"
        return 1
    fi

    local _pr_url
    _pr_url=$(gh pr create --repo "$REGWATCH_GH_REPO" --base main --head "$_branch" \
        --title "chore(regulatory): promote ${DATE} delta" \
        --body "Automated promotion of $_rel. See infra/launchagents/wrappers/regulatory-watcher-run.sh." \
        2>>"$LOG")
    if [ $? -ne 0 ]; then
        echo "[$(date)] promote: gh pr create failed — branch $_branch pushed, PR NOT opened, manual recovery: gh pr create --head $_branch" >> "$LOG"
        return 1
    fi
    echo "[$(date)] promote: opened PR $_pr_url" >> "$LOG"
    local _pr_num
    _pr_num=$(print -r -- "$_pr_url" | grep -oE '[0-9]+$')
    # NOT --squash: once a merge queue governs main, the ruleset owns the merge
    # method and --squash is rejected outright (pipeline-ship skill).
    if gh pr merge "$_pr_num" --repo "$REGWATCH_GH_REPO" --auto >> "$LOG" 2>&1; then
        echo "[$(date)] promote: auto-merge armed on PR #$_pr_num" >> "$LOG"
    else
        echo "[$(date)] promote: WARN could not arm auto-merge on PR #$_pr_num — needs manual arm" >> "$LOG"
    fi
    echo "[$(date)] promote: worktree $_wt left in place pending merge (next run's --cleanup collects it once merged)" >> "$LOG"
    return 0
}

# Tiers 1-3 use this: a partial stub does NOT count as success — remove it (so
# the next tier's ensure_delta() does not short-circuit on the stale file via
# its own "[ -f "$DELTA_JSON" ] && return 0" check) and let the cascade continue.
# Tier 4 (last resort, nothing left to cascade to) calls plain ensure_delta()
# and handles partial-acceptance itself (DEGRADED, never silent-clean).
ensure_full_delta() {
    local _out="$1"
    ensure_delta "$_out" || return 1
    # Exact rc check, not `if delta_is_partial; then` (hardened post-merge,
    # gate REWORK-BUILD on head 7753eac1): that shape treats ANY nonzero exit
    # as "not partial, proceed" — collapsing rc=1 (confirmed valid,
    # partial:false) and rc=2 (invalid/unparsable JSON) into the same "accept"
    # branch. rc=2 must reject exactly like rc=0, just for a different reason.
    delta_is_partial
    local _partial_rc=$?
    if [ "$_partial_rc" -eq 0 ]; then
        echo "[$(date)] delta landed but partial=true (tier admitted incomplete/no-access scan) — rejecting, cascading to next tier" >> "$LOG"
        rm -f "$DELTA_JSON"
        return 1
    elif [ "$_partial_rc" -ne 1 ]; then
        echo "[$(date)] delta landed but failed validation (delta_is_partial rc=$_partial_rc — invalid/unparsable JSON) — rejecting, cascading to next tier" >> "$LOG"
        rm -f "$DELTA_JSON"
        return 1
    fi
    return 0
}

# Tier 1: every isolated Claude OAuth seat. `--claude-only` is load-bearing:
# this wrapper owns the cross-provider tiers because each has a different
# prompt and file-landing contract. The canonical cascade must stop before
# Gemini/Kimi/Codex/Ollama so ensure_full_delta remains the sole success gate.
echo "[$(date)] tier 1 — Claude subscription seat cascade" >> "$LOG"
# Quota gate (tokenaudit Phase 7 / S3, canon since 2026-09-02): ask "may a headless
# Claude job run now?" BEFORE spending a seat call that would die at the weekly cap.
# Contract of quota_gate.sh: exit 0=GO, 3=SKIP (best seat >= 85%), 4=DEGRADE (>= 75%);
# it FAILS OPEN (exit 0) on any error and never picks the Team seat. Here both SKIP and
# DEGRADE skip the whole Claude tier and let the cascade fall to tier 2 exactly as an
# ordinary tier-1 failure would; gate absent, disabled, or GO -> the cascade behaves
# exactly as before. NOT byte-identical, and the distinction was earned: two cross-family
# review seats (tp1-qwen3.8-max, codex-gpt-5.6-sol), convened separately with no shared
# context on 2026-09-02, independently named the same defeating state — a gate that exits 0
# but PRINTS still appends its own output to $LOG through the redirection below, so the log
# bytes differ even on GO. The tier-1 call itself is untouched.
# Kill switch: REGWATCH_QUOTA_GATE=0. The gate lives outside the repo on purpose (it reads
# ~/.claude/seat-quota.json, a per-machine measurement) — same shape as CASCADE_BIN above.
QUOTA_GATE_BIN="${REGWATCH_QUOTA_GATE_BIN:-$HOME/.tokenaudit/ingest/quota_gate.sh}"
QUOTA_GATE_RC=0
if [ "${REGWATCH_QUOTA_GATE:-1}" != "0" ] && [ -x "$QUOTA_GATE_BIN" ]; then
    "$QUOTA_GATE_BIN" >>"$LOG" 2>&1
    QUOTA_GATE_RC=$?
fi
if [ "$QUOTA_GATE_RC" -eq 3 ] || [ "$QUOTA_GATE_RC" -eq 4 ]; then
    echo "[$(date)] quota_gate rc=$QUOTA_GATE_RC ($([ "$QUOTA_GATE_RC" -eq 3 ] && echo SKIP || echo DEGRADE)) — skipping the whole Claude tier, cascading to tier 2" >> "$LOG"
    echo "quota_gate: Claude tier skipped (rc=$QUOTA_GATE_RC)" >"$TMPOUT"
    EXIT=75
elif [ -x "$CASCADE_BIN" ]; then
    "$CASCADE_BIN" "$PROMPT_CLAUDE" --claude-only --model claude-sonnet-5 >"$TMPOUT" 2>&1
    EXIT=$?
else
    echo "canonical Claude cascade missing: $CASCADE_BIN" >"$TMPOUT"
    EXIT=127
fi
if [ $EXIT -eq 0 ] && ! grep -qE "out of extra usage|usage limit|quota exceeded|rate.limit" "$TMPOUT" && ensure_full_delta "$TMPOUT"; then
    SUCCESS=1
    USED_LLM="claude-sonnet-5-subscription-cascade"
elif [ $EXIT -eq 0 ]; then
    echo "[$(date)] Claude seat cascade exit 0 but NO delta file landed (hallucinated/backgrounded output?) — cascading cross-provider" >> "$LOG"
fi
cat "$TMPOUT" >> "$LOG"

# Tier 2: agy (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
if [ $SUCCESS -eq 0 ]; then
    echo "[$(date)] tier 1 failed/exhausted — falling back to agy (Gemini 3.1 Pro)" >> "$LOG"
    > "$TMPOUT"
    # `-p`/`--print` TAKES A VALUE (measured live 2026-08-13, both forms exit 0):
    # `-p --print-timeout 5m` binds the literal string "--print-timeout" as the
    # prompt and leaves "5m" a stray positional — agy never reads stdin. Prompt
    # must be `-p`'s own argv value; --print-timeout stays a separate flag.
    # NOTE: agy v1.1.12 has no stdin path, so the prompt now travels on argv —
    # visible via `ps` to every other user on this machine while the process
    # runs (see PR body for the PII disclosure this forces).
    /Users/nuzantara/.local/bin/agy -p "$PROMPT_GENERIC" --print-timeout 5m >"$TMPOUT" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ] && ! grep -qiE "quota|limit|429|exhausted|TerminalQuotaError|auto-denied|headless mode cannot prompt|no output produced" "$TMPOUT" && ensure_full_delta "$TMPOUT"; then
        SUCCESS=1
        USED_LLM="gemini-3.1-pro-agy"
    fi
    cat "$TMPOUT" >> "$LOG"
fi

# Tier 3: Codex GPT-5.5
if [ $SUCCESS -eq 0 ]; then
    echo "[$(date)] tier 2 failed/exhausted — falling back to codex" >> "$LOG"
    > "$TMPOUT"
    # `</dev/null` is load-bearing: codex blocks reading an open stdin (proved
    # live 2026-07-06 09:20 "Reading additional input from stdin..."); cron/ssh
    # contexts run from $HOME which is not a trusted repo → --skip-git-repo-check.
    #
    # CODEX_HOME picks a seat that is actually logged in, alternating between
    # the two ChatGPT Pro subscriptions. Measured 2026-08-12: on Pro — this
    # wrapper's own machine — the default ~/.codex answers 401, so this tier
    # produced nothing while a paid live seat sat one variable away. Empty means
    # "no seat at all", and then codex is left to its own default rather than
    # being handed an empty CODEX_HOME.
    CODEX_SEAT="$(codex_seat_pick 2>/dev/null || true)"
    typeset -a CODEX_SEAT_ENV
    CODEX_SEAT_ENV=()
    if [ -n "$CODEX_SEAT" ]; then
        CODEX_SEAT_ENV=(CODEX_HOME="$CODEX_SEAT")
        echo "[$(date)] codex seat: $CODEX_SEAT" >> "$LOG"
    fi
    # workspace-write's DEFAULT sandbox has no outbound network for shell-executed
    # commands. Measured live 2026-09-27: every `curl` inside `exec` failed with
    # "Could not resolve host" (DNS itself blocked) for every .go.id/.org/.co.id
    # target, while codex's own web-search tool (a separate path) worked — so the
    # agent could search but not fetch/verify, self-reported partial:true on an
    # otherwise-complete 0-new scan, and ensure_full_delta rightly rejected it,
    # cascading to tier 4 for no real reason. `sandbox_workspace_write.network_
    # access=true` alone is NOT enough — proved live on Pro: it still blocked
    # https://www.google.com with "domain is not on the allowlist for the
    # current sandbox mode" (this account's `~/.codex/config.toml` sets
    # `features.network_proxy = true`, a domain-allowlist proxy with nothing on
    # the list). Disabling that proxy for THIS invocation only is what actually
    # opened it — confirmed live against hukumonline.com (HTTP:200) after this
    # exact flag pair. Neither flag widens to --sandbox danger-full-access.
    #
    # Env exposure to this tier's shell (untrusted external content -> prompt
    # injection surface, now with real egress): this wrapper's own `set -a;
    # source .nuzantara-secrets.env` above exports ~27 vars including
    # DATABASE_URL/REDIS_PASSWORD/GOOGLE_APPLICATION_CREDENTIALS into ITS OWN
    # shell, and `env "${CODEX_SEAT_ENV[@]}"` used to hand codex that whole
    # inherited environment. Measured live 2026-09-27: `-c shell_environment_
    # policy.inherit=core`/`=none`/`-c allow_login_shell=false` are ALL
    # INEFFECTIVE — codex's `exec` shell tool re-applies GITHUB_PERSONAL_
    # ACCESS_TOKEN (exported at this account's `~/.zshrc:9`) and
    # STARSHIP_SESSION_KEY (from `starship init`) through its own interactive
    # SHELL SNAPSHOT feature regardless of any of those flags, and
    # `allow_login_shell=false` also dropped the TELEGRAM_* vars this tier
    # needs. Verified effective, gate-measured rc 0: `env -i` plus an
    # explicit allowlist (HOME, PATH, the seat's CODEX_HOME, only the two
    # TELEGRAM_* vars this tier's prompt uses) so none of the
    # .nuzantara-secrets.env names reach codex's own process env, PLUS `-c
    # features.shell_snapshot=false` so codex does not re-apply
    # ~/.zshrc/starship's own exports on top. `shell_snapshot=false` ALONE
    # (verified live, own re-check) also drops this allowlist's own
    # TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID — disabling the snapshot
    # makes `shell_environment_policy.inherit` the ONLY thing governing what
    # of codex's (now `env -i`-minimal) own process env reaches the shell
    # tool, so `inherit=all` must be explicit alongside it: verified live,
    # 39 names, GITHUB_PAT=0, STARSHIP=0, both TELEGRAM_* present. Pre-
    # existing gap named, not fixed here: tier 1 (Claude) still inherits
    # this wrapper's full `set -a` environment too, now with network access.
    typeset -a CODEX_ENV_ALLOWLIST
    CODEX_ENV_ALLOWLIST=(HOME="$HOME" PATH="$PATH")
    CODEX_ENV_ALLOWLIST+=("${CODEX_SEAT_ENV[@]}")
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && CODEX_ENV_ALLOWLIST+=(TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}")
    [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ] && CODEX_ENV_ALLOWLIST+=(TELEGRAM_OWNER_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-}")
    env -i "${CODEX_ENV_ALLOWLIST[@]}" \
        /opt/homebrew/bin/codex exec --sandbox workspace-write \
        -c sandbox_workspace_write.network_access=true \
        -c features.network_proxy=false \
        -c features.shell_snapshot=false \
        -c shell_environment_policy.inherit=all \
        --skip-git-repo-check "$PROMPT_GENERIC" </dev/null >"$TMPOUT" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ] && ! grep -qE "usage.limit|quota|exhausted" "$TMPOUT" && ensure_full_delta "$TMPOUT"; then
        SUCCESS=1
        USED_LLM="codex-gpt-5.5"
    fi
    cat "$TMPOUT" >> "$LOG"
fi

# Verifies the MODEL is actually installed, not just the `ollama` binary. Before
# this check, a missing model reached `ollama run` directly: measured live
# 2026-08-20 on Pro, that spends several seconds attempting a network
# pull-manifest round-trip ("pulling manifest" spinner) before failing with a
# generic `Error: pull model manifest: file does not exist` (exit 1) — a real
# non-zero exit, but slow, unnecessarily network-dependent for a tier whose
# whole point is local/offline, and logged identically to a daemon-down or OOM
# failure. Reads /api/tags (not `ollama list`, which has an independent history
# in this repo of answering empty while the API answers correctly) so a known
# miss is fast, local-only, and distinguishable in the log from "daemon
# unreachable".
_ollama_model_ready() {
    local model="$1"
    local base="${OLLAMA_API_BASE:-http://127.0.0.1:11434}"
    # Overridable (mirrors the other provider-binary overrides in this cascade) —
    # a hermetic test harness fakes the whole `ollama` binary via PATH-free
    # absolute overrides, but this precheck talks HTTP directly (by design:
    # see the comment above `_ollama_model_ready`, not the `ollama` binary),
    # so without its own seam it always hits a real, unreachable 127.0.0.1
    # in CI and the tier silently vanishes from every test scenario.
    local curl_bin="${CLAUDE_CASCADE_OLLAMA_CURL_BIN:-curl}"
    local tags
    tags="$("$curl_bin" -sf -m 5 "${base}/api/tags" 2>/dev/null)"
    if [ -z "$tags" ]; then
        echo "  [ollama-precheck] daemon unreachable at ${base}" >&2
        return 1
    fi
    if printf '%s' "$tags" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
names = {m.get('name') for m in data.get('models', [])}
sys.exit(0 if '$model' in names else 1)
"; then
        return 0
    fi
    echo "  [ollama-precheck] model '$model' not installed (daemon reachable, tags checked)" >&2
    return 1
}

# Tier 4: Ollama local (always available, lower quality but free + unlimited).
# Last resort — nothing left to cascade to, so a partial result is accepted
# rather than discarded, but it is marked DEGRADED (never silently "clean")
# so proprioception/heartbeat can distinguish "genuinely 0 new" from "no tier
# could actually check".
DEGRADED=0
if [ $SUCCESS -eq 0 ]; then
    if ! _ollama_model_ready "qwen3.5:9b" 2>>"$LOG"; then
        echo "[$(date)] tier 4 ollama — model qwen3.5:9b not ready (missing or daemon down), skipping" >> "$LOG"
    else
        echo "[$(date)] tier 3 failed/exhausted — falling back to ollama qwen3.5:9b local" >> "$LOG"
        > "$TMPOUT"
        /opt/homebrew/bin/ollama run qwen3.5:9b "$PROMPT_GENERIC" >"$TMPOUT" 2>&1
        EXIT=$?
        if [ $EXIT -eq 0 ] && ensure_delta "$TMPOUT"; then
            # Exact rc check (hardened post-merge, gate REWORK-BUILD on head
            # 7753eac1): `if delta_is_partial; then` treated rc=2
            # (invalid/unparsable JSON) the same as rc=1 (confirmed valid,
            # not partial) — silently accepting garbage as a clean SUCCESS
            # with no DEGRADED flag at all, the last-resort tier's own
            # version of the same bug fixed above for tiers 1-3.
            delta_is_partial
            _partial_rc=$?
            if [ "$_partial_rc" -eq 0 ]; then
                SUCCESS=1
                USED_LLM="ollama-qwen3.5:9b-local"
                DEGRADED=1
                echo "[$(date)] tier 4 landed but partial=true — ALL 4 tiers failed to complete a real scan, accepting as DEGRADED (not a clean 0-new day)" >> "$LOG"
            elif [ "$_partial_rc" -eq 1 ]; then
                SUCCESS=1
                USED_LLM="ollama-qwen3.5:9b-local"
            else
                rm -f "$DELTA_JSON"
                echo "[$(date)] tier 4 landed invalid/unparsable JSON (delta_is_partial rc=$_partial_rc) — discarding, NOT accepted as success" >> "$LOG"
            fi
        fi
        cat "$TMPOUT" >> "$LOG"
    fi
fi

# Names the seat + tool set actually used, so the log answers "did this tier
# have real tools" without needing to re-derive it from the tier's raw output.
TOOLS_USED="unknown"
case "$USED_LLM" in
    claude-sonnet-5-subscription-cascade) TOOLS_USED="Claude agent session: Read/Write/Bash/WebFetch (NB-INTEL + web); delta written to /tmp scratch, promoted via worktree" ;;
    gemini-3.1-pro-agy) TOOLS_USED="agy print-mode: model-native browsing only, no local shell tool" ;;
    codex-gpt-5.5) TOOLS_USED="codex exec --sandbox workspace-write, network_access=true + network_proxy=false + shell_snapshot=false + inherit=all, env -i allowlist (HOME/PATH/CODEX_HOME/TELEGRAM_*): shell (curl) + web-search" ;;
    ollama-qwen3.5:9b-local) TOOLS_USED="none — local text-only model, no browsing/shell, by design (last resort)" ;;
esac

if [ $SUCCESS -eq 1 ] && [ $DEGRADED -eq 1 ]; then
    echo "[$(date)] regulatory-watcher run DEGRADED — used: $USED_LLM — tools: $TOOLS_USED (partial: no tier completed a real scan)" >> "$LOG"
    organism_hb_set degraded "used ${USED_LLM}, partial=true — no tier completed a real scan"
elif [ $SUCCESS -eq 1 ]; then
    echo "[$(date)] regulatory-watcher run complete — used: $USED_LLM — tools: $TOOLS_USED" >> "$LOG"
    organism_hb_set ok "used ${USED_LLM}"

    # W1.4: emit eventbus events for any new regulatory deltas in today's JSON.
    # Recovery/extraction already ran per-tier inside ensure_delta(); SUCCESS=1
    # implies the file exists. The guard below stays as a belt (a sibling process
    # could remove the file between the tier check and here — seen 2026-05-13).
    if [ ! -f "$DELTA_JSON" ]; then
        echo "[$(date)] WARNING: $USED_LLM reported success but $DELTA_JSON does NOT exist on disk — possible hallucinated tool output, skipping eventbus publish" >> "$LOG"
    fi

    if [ -f "$DELTA_JSON" ]; then
        # Pin pyenv python3 explicitly (PATH propagation through zsh -lc resolves
        # to Homebrew 3.14 which lacks `redis`; pyenv 3.11.11 has redis 7.3.0).
        /Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json, sys
sys.path.insert(0, '$HOME/scripts')
from eventbus import publish
try:
    d = json.load(open('$DELTA_JSON'))
except Exception as e:
    print(f'cannot parse {\"$DELTA_JSON\"}: {e}', file=sys.stderr); sys.exit(0)
deltas = d.get('deltas', [])
if not deltas:
    print(f'no deltas to emit ({d.get(\"new_today_count\", 0)} new)')
    sys.exit(0)
for delta in deltas:
    sl = delta.get('service_line', [])
    if isinstance(sl, str): sl = [sl]
    try:
        eid = publish('regulatory.delta.detected', {
            'citation': delta.get('citation', 'unknown'),
            'regulation_type': (delta.get('citation') or '').split()[0] if delta.get('citation') else 'unknown',
            'service_lines': sl or ['unknown'],
            'summary': (delta.get('summary') or '')[:500],
            'urgency': delta.get('urgency', 'medium'),
            'source': delta.get('source', 'regulatory-watcher'),
            'detected_at': delta.get('first_seen_at') or d.get('run_at'),
        }, emitted_by='regulatory-watcher')
        print(f'emitted {eid} for {delta.get(\"citation\", \"?\")}')
    except Exception as e:
        print(f'emit failed for {delta.get(\"citation\")}: {e}', file=sys.stderr)

# Intel Lake Wave 4 (2026-05-12): enqueue each delta to the Intel Lake
# outbox so the unified pipeline sees regulatory findings alongside other
# producers. Best-effort — never block the watcher run.
try:
    import hashlib
    from intel_lake_outbox import enqueue as _lake_enqueue
    for delta in deltas:
        cit = delta.get('citation', 'unknown')
        url = delta.get('source') or f'regulatory-watcher://delta/{cit}'
        title = delta.get('title_en') or delta.get('title_id') or cit
        ch = hashlib.sha256((cit + ' ' + title).encode()).hexdigest()[:32]
        sl = delta.get('service_line', [])
        if isinstance(sl, str): sl = [sl]
        try:
            _lake_enqueue('regulatory_watcher', {
                'producer_name': 'regulatory_watcher',
                'canonical_url': url,
                'content_hash': ch,
                'title': (cit + ' — ' + title)[:500],
                'summary': (delta.get('summary') or '')[:2000],
                'source_domain': delta.get('source_domain') or 'regulatory-watcher',
                'language': 'id',
                'jurisdiction': 'ID-national',
                'topic_tags': ['regulation', delta.get('regulation_type','regulation')] + (sl or []),
                'published_at': delta.get('first_seen_at') or d.get('run_at'),
                'score': None,
                'raw_payload': {
                    'citation': cit,
                    'urgency': delta.get('urgency','medium'),
                    'verbatim_excerpt': (delta.get('verbatim_excerpt') or '')[:2000],
                },
            })
        except Exception as e2:
            print(f'lake enqueue failed for {cit}: {e2}', file=sys.stderr)
except Exception as e:
    print(f'intel_lake_outbox import skipped: {e}', file=sys.stderr)
" >> "$LOG" 2>&1
    fi
else
    echo "[$(date)] regulatory-watcher ALL TIERS FAILED — manual investigation needed" >> "$LOG"
    organism_hb_set error "all tiers failed"
fi

# Promote whatever delta landed on disk this run (SUCCESS or DEGRADED — a
# degraded/partial-accepted tier-4 delta is still worth committing; only "ALL
# TIERS FAILED" leaves no $DELTA_JSON for promote_delta_via_pr to act on).
#
# W-promote-silence (2026-08-31): called bare, this function's `return 1` used
# to vanish — organism_hb_finalize (the EXIT trap) reads only the SCRIPT's own
# rc, which is an unconditional `exit 0` below no matter how promotion went.
# Result, measured live: pro.regulatory_watcher_daily said "ok" every day for
# ten days while gh pr create failed every single run (cwd bug, cured above) —
# detection+alerting genuinely succeeded each day, so the script exiting 0 was
# correct, but the heartbeat's NOTE kept saying "used <tier>" as if delivery
# had too. Capture the rc and surface it WITHOUT failing the run: the fix is
# to stop the heartbeat lying, not to turn a successful scan into a failed one.
promote_delta_via_pr
_PROMOTE_RC=$?
if [ "$_PROMOTE_RC" -ne 0 ]; then
    echo "[$(date)] promote: FAILED rc=$_PROMOTE_RC — delta detected but not promoted to main (see promote: lines above for cause)" >> "$LOG"
    organism_hb_set error "promote_delta_via_pr failed rc=${_PROMOTE_RC} — delta on disk, not promoted to main"
fi


# --- modus autoloop enqueue (PR #2307) ---
# When regulatory-watcher confirmed a real delta on disk this run, deposit ONE
# green-class task into the modus escalation queue so the autonomous loop can
# capture it into research/regulatory/** (a low-risk, in-perimeter mandate — NOT
# "apply the regulation", which would be a business/legal decision and NOT green).
# One task per RUN (not per delta). Idempotent (modus_enqueue skips same pending
# job). Fail-open: never break the watcher.
if [ -f "$DELTA_JSON" ]; then
    _mod_n=$(/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "import json;print(len(json.load(open('$DELTA_JSON')).get('deltas',[])))" 2>/dev/null || echo 0)
    if [ "${_mod_n:-0}" -gt 0 ]; then
        ( cd "$HOME/nuzantara" && \
          /Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 scripts/modus_enqueue.py \
            --job "regulatory-delta-capture-$DATE" \
            --source "regulatory-watcher" \
            --mandate "Capture today's $_mod_n regulatory delta(s) from $DELTA_JSON into a research/regulatory note; only record, do NOT apply or advise." \
            --class green \
            --perimeter "research/regulatory/**" \
        ) >> "$LOG" 2>&1 || echo "[$(date)] modus_enqueue failed (non-fatal)" >> "$LOG"
    fi
fi

rm -f "$TMPOUT"
exit 0
