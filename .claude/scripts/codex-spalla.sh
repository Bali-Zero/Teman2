#!/usr/bin/env bash
# codex-spalla.sh — dispatch Codex CLI as "spalla" (adversarial second opinion)
#
# Usage:
#   .claude/scripts/codex-spalla.sh <mode> <base_branch> [focus_brief] [--allow-pii-paths]
#   .claude/scripts/codex-spalla.sh --self-test
#
# Args:
#   mode:        "review" (default) | "exec"
#   base_branch: base for diff comparison (default: main)
#   focus_brief: optional free-text focus area passed to Codex
#   --allow-pii-paths: overrides the PII-classed-path refusal below. Logged
#                to telemetry (`allow_pii_paths`); does NOT skip redaction —
#                the redactor still runs, with PROD CRM names still REQUIRED
#                (fails closed if unavailable). It does NOT confine codex's
#                OWN filesystem reads: `codex exec --sandbox read-only` runs
#                in $REPO_ROOT and the prompt invites it to grep the repo, so
#                an override still lets codex read the raw file itself — this
#                flag narrows what THIS WRAPPER embeds, not what codex can see.
#   --self-test: liveness probe, no diff needed — dispatches a trivial prompt
#                through the real `codex exec` path and requires a verdict line
#                back. Exit 0 proves flags, seat and auth are all live.
#
# PII (cicatrix W140, 2026-09-26): everything embedded in the prompt below
# leaves this machine for OpenAI's cloud. Before that happens the diff/
# uncommitted/untracked bodies are (a) refused outright if they touch a
# PII-classed path (union of a static list plus the live PII_PATH_FRAGMENTS
# tuple in scripts/async_review_supervisor.py, checked on EITHER side of a
# rename) unless --allow-pii-paths is passed, and (b) piped through the
# canonical `scripts/_redact_pii.py --require-dynamic-names` (fail-closed on
# error OR an unavailable CRM name list). Deleted lines of .jsonl/.csv/.xlsx
# files are never embedded at all — a PII-REMOVAL diff is the most PII-dense
# diff there is: the deleted lines ARE the data. NOT covered: the operator-
# typed FOCUS brief and the bare untracked-file PATH list (UNTRACKED_LIST)
# are not redacted — both are lower-risk (typed by a human, or paths only,
# not diff content) but a careless FOCUS could still paste something it
# shouldn't; known gap, not closed here.
#
# Behavior contract: see docs/superpowers/specs/2026-05-03-codex-spalla-design.md §4.3.
# Hard rules: see docs/decisions/2026-05-03-codex-spalla-architecture.md.
#
# codex-cli drift: `--full-auto` was removed in codex-cli 0.149.1 and every
# wrapper run after that judged NOTHING — worse, codex-cli 0.151.0 printed the
# usage error at exit 0, so callers judging by return code read "never ran" as
# "clean" (ledger 2026-09-01, PENDING-ARMS). Two rules follow: never pass a
# removed flag again, and never trust exit 0 without a verdict line (see
# verdict_present below).
#
# Exit codes:
#   0  = dispatch completed AND a verdict line landed (regardless of verdict)
#   1  = invalid args, git error, or codex seat lib missing
#   2  = hard refused (empty diff)
#   3  = anti-pattern guard cancelled by user (Ctrl-C during countdown)
#   4  = codex CLI not installed
#   5  = codex CLI not logged in
#   6  = codex returned 0 but produced no verdict line — never judged
#   7  = refused: diff touches a PII-classed path without --allow-pii-paths
#   8  = redaction pipeline failed closed (scripts/_redact_pii.py errored)
#   >8 = codex non-zero exit propagated (may also collide with codex's own)

set -euo pipefail

# Every artefact this wrapper writes (transcripts, .last.md, telemetry) is
# review material for an EXTERNAL diff and must never be group/world-readable
# (S7 / cicatrix W140 follow-up: 55/55 existing files were 0644 under the
# default 022 umask). Belt: umask here. Suspenders: explicit chmod after each
# create, below, in case a path pre-existed under a looser mode (umask alone
# never tightens an existing file/dir).
umask 077

# --allow-pii-paths can appear anywhere in argv; strip it before positional
# parsing so it doesn't shift MODE/BASE/FOCUS.
ALLOW_PII_PATHS="false"
declare -a _POSITIONAL_ARGS=()
for _arg in "$@"; do
    if [[ "$_arg" == "--allow-pii-paths" ]]; then
        ALLOW_PII_PATHS="true"
    else
        _POSITIONAL_ARGS+=("$_arg")
    fi
done
set -- "${_POSITIONAL_ARGS[@]}"

MODE="${1:-review}"
BASE="${2:-main}"
FOCUS="${3:-}"

SELF_TEST="false"
if [[ "$MODE" == "--self-test" ]]; then
    SELF_TEST="true"
    # MODE flows into the transcript filename and telemetry; the self-test
    # block below dispatches explicitly with --sandbox read-only regardless.
    MODE="self-test"
    FOCUS="self-test"
fi

if [[ "$MODE" != "review" && "$MODE" != "exec" && "$SELF_TEST" != "true" ]]; then
    echo "ERROR: mode must be 'review', 'exec' or '--self-test' (got: '$MODE')" >&2
    exit 1
fi

# SECURITY (Codex spalla self-review BLOCKER #1, 2026-05-03):
# git accepts branch names containing shell metacharacters (`pwn;id`,
# `pwn$(id)`, `pwn|id`); the previous implementation interpolated $BASE
# into a string and ran it via `eval`, which could execute injected
# commands. Validate $BASE against a strict whitelist BEFORE any use.
if ! printf '%s' "$BASE" | grep -qE '^[A-Za-z0-9._/-]+$'; then
    echo "ERROR: base branch name '$BASE' contains characters outside [A-Za-z0-9._/-]" >&2
    echo "(refusing to proceed for shell-injection safety)" >&2
    exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
    echo "ERROR: codex CLI not found. Install with: brew install codex" >&2
    exit 4
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "ERROR: not inside a git repo" >&2
    exit 1
fi
cd "$REPO_ROOT"

# strip_data_file_deletes / redact_for_external / pii_path_hit (Builder
# Contract rule 4 / cicatrix W140): shared with any sibling external-seat
# wrapper, so they live in scripts/lib/spalla_redact.sh, not here. Resolved
# relative to THIS SCRIPT's own on-disk location (not $REPO_ROOT): a test
# harness drives this exact file with `cwd` pointed at a synthetic fixture
# repo that carries no copy of scripts/lib/ — $REPO_ROOT there resolves to
# the fixture, not this checkout, and the source would 404 (scripts/tests/
# test_codex_spalla.py, 10/11 regressed this way at head 92e7cac0a8). This
# script's own path never moves, so BASH_SOURCE-relative is the one
# resolution that is correct in both the fixture and the real deploy.
_SPALLA_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$_SPALLA_SCRIPT_DIR/../../scripts/lib/spalla_redact.sh"

# Pick a seat that is actually logged in, alternating between the two ChatGPT
# Pro subscriptions, BEFORE asking codex whether it is logged in — the question
# is answered per CODEX_HOME. Measured 2026-08-12 on Pro: the default ~/.codex
# answers 401 while ~/.codex-acct2 is live, so the gate below would have
# refused with a paid seat one variable away.
#
# The lib is resolved from the REPO ROOT, not from this script's own path: the
# old `dirname BASH_SOURCE/../../scripts/lib` resolution silently skipped
# seat-picking for any copy of the script sitting at a different depth — the
# [ -f ] guard dodged a `source`-of-missing-file exit under set -e, at the
# price of dispatching on the default, possibly 401-dead, seat without saying
# so. A missing lib is now a loud refusal.
CODEX_SEAT_LIB="$REPO_ROOT/scripts/lib/codex_seat.sh"
if [[ ! -f "$CODEX_SEAT_LIB" ]]; then
    echo "ERROR: codex seat lib not found: $CODEX_SEAT_LIB" >&2
    echo "(resolved from the repo root; refusing to dispatch on an unpicked, possibly dead, default seat)" >&2
    exit 1
fi
# shellcheck disable=SC1090
. "$CODEX_SEAT_LIB"
CODEX_SEAT="$(codex_seat_pick 2>/dev/null || true)"
if [ -n "$CODEX_SEAT" ]; then
    export CODEX_HOME="$CODEX_SEAT"
    echo "[spalla] codex seat: $CODEX_SEAT" >&2
fi

if ! codex login status 2>&1 | grep -qi "Logged in using ChatGPT"; then
    echo "ERROR: codex CLI not logged in via ChatGPT OAuth (CODEX_HOME=${CODEX_HOME:-\$HOME/.codex}). Run: codex login" >&2
    echo "(Hard rule: do NOT set OPENAI_API_KEY — use OAuth only.)" >&2
    exit 5
fi

HEAD_REF="$(git rev-parse HEAD 2>/dev/null || echo HEAD)"

# Use array form (NOT eval) to safely pass refs to git.
declare -a DIFF_ARGS
if git rev-parse --verify --quiet "$BASE" >/dev/null; then
    DIFF_ARGS=(diff "${BASE}...${HEAD_REF}")
else
    DIFF_ARGS=(diff HEAD)
fi

DIFF_LINES="$(git -c core.quotePath=false "${DIFF_ARGS[@]}" 2>/dev/null | wc -l | tr -d ' ')"
FILES_CHANGED="$(git -c core.quotePath=false "${DIFF_ARGS[@]}" --stat 2>/dev/null | tail -1 | grep -oE '^[[:space:]]*[0-9]+ files? changed' | grep -oE '[0-9]+' | head -1 || echo 0)"

# Codex spalla BLOCKER #2 + #3: include uncommitted + untracked in the
# "what's about to ship" tally; otherwise fresh `Write` files look empty.
UNCOMMITTED_LINES="$(git -c core.quotePath=false diff HEAD 2>/dev/null | wc -l | tr -d ' ')"
# W104-class bug fixed 2026-08-14 (found by spalla-review on an unrelated PR):
# `grep -c .` ALWAYS prints a count to stdout (0 on no match) but STILL exits
# 1 when that count is 0 — under this script's own `set -o pipefail` (line
# 24), a zero-match pipeline is "failed", so the old `|| echo 0` fallback ran
# TOO, appending a second "0" after the one grep had already printed. The
# captured value on an empty diff was the two-line string "0\n0", which then
# broke `$((...))` arithmetic at TOTAL_FILES below with a hard `syntax error
# in expression` (reproduced verbatim: `printf '' | grep -c . 2>/dev/null ||
# echo 0` -> "0\n0"). Fix: `|| true` instead of `|| echo 0` — grep's own
# printed count is authoritative and the exit code carries no information
# worth reacting to (same lesson as W104: judge the output, not the exit
# code), so the fallback only needs to stop `set -e`/pipefail from treating
# "zero matches" as an error, never to supply its own value.
UNCOMMITTED_FILES="$(git -c core.quotePath=false diff HEAD --name-only 2>/dev/null | grep -c . 2>/dev/null || true)"
UNTRACKED_FILES="$(git -c core.quotePath=false ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')"
TOTAL_DIFF_LINES=$((DIFF_LINES + UNCOMMITTED_LINES))

WARNED="false"
CANCELLED="false"

if [[ "$SELF_TEST" != "true" ]] && [[ "$TOTAL_DIFF_LINES" -eq 0 ]] && [[ "$UNTRACKED_FILES" -eq 0 ]]; then
    echo "REFUSED: diff is empty against base '$BASE', no uncommitted changes, no untracked files." >&2
    echo "Nothing to review. Make some changes first." >&2
    exit 2
fi

# Set up telemetry + transcript path BEFORE the small-diff countdown.
# Codex spalla self-review #6: previously the trap was installed AFTER
# `sleep 5`, so Ctrl-C during the countdown would kill the script before
# `record_telemetry` could write the cancelled=true line. Now the trap
# is installed first and the function is defined upfront with a fallback
# transcript path.
TS="$(date -u +%Y%m%dT%H%M%SZ)"
# Codex spalla BLOCKER #7: race-safe random suffix so two same-second runs
# don't clobber the same transcript path.
RAND="$(printf '%04x' $(($$ ^ RANDOM)) 2>/dev/null || echo "$$")"
SLUG="$(echo "${FOCUS:-uncommitted}" | tr -c '[:alnum:]-' '-' | tr -s '-' | cut -c1-40 | sed 's/^-//;s/-$//')"
[[ -z "$SLUG" ]] && SLUG="diff"

LOG_DIR="$HOME/logs/codex-spalla"
TELEMETRY_FILE="$HOME/logs/codex-spalla.jsonl"
mkdir -p "$LOG_DIR"
# `mkdir -p`/`>>` on an ALREADY-EXISTING dir/file never changes its mode —
# umask only governs brand-new creates. Re-tighten every run regardless of
# history (S7): the lead is fixing the 55 pre-existing 0644 transcripts on
# M5 by hand, this is the going-forward guarantee.
chmod 0700 "$LOG_DIR" 2>/dev/null || true
if [[ -e "$TELEMETRY_FILE" ]]; then chmod 0600 "$TELEMETRY_FILE" 2>/dev/null || true; fi

# Codex spalla self-review #3: race-safe transcript creation. Use noclobber
# (set -C) to refuse-write if the path already exists; on collision, append
# an incrementing counter until we find a free path. Guarantees no two
# concurrent runs ever silently clobber each other's transcript.
TRANSCRIPT_BASE="$LOG_DIR/${TS}-${RAND}-${MODE}-${SLUG}"
TRANSCRIPT="${TRANSCRIPT_BASE}.md"
__counter=0
while ! ( set -C; : > "$TRANSCRIPT" ) 2>/dev/null; do
    __counter=$((__counter + 1))
    if [[ "$__counter" -gt 99 ]]; then
        echo "ERROR: cannot create unique transcript path after 100 attempts" >&2
        exit 1
    fi
    TRANSCRIPT="${TRANSCRIPT_BASE}-${__counter}.md"
done
chmod 0600 "$TRANSCRIPT" 2>/dev/null || true
# Empty file now exclusively owned; codex output below appends via >> not >.

# Assistant-only final output, written by codex itself (--output-last-message),
# derived from the same race-safe base as the transcript. This file — not the
# combined transcript — is the verdict source (see verdict_present below).
LAST_MESSAGE="${TRANSCRIPT_BASE}.last.md"

record_telemetry() {
    local exit_code="$1"
    local blocker="${2:-false}"
    local focus_json
    focus_json="$(printf '%s' "${FOCUS:-}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
    printf '{"ts":"%s","mode":"%s","base":"%s","focus":%s,"diff_lines":%s,"files_changed":%s,"untracked_files":%s,"warned":%s,"cancelled":%s,"exit_code":%s,"blocker":%s,"allow_pii_paths":%s,"transcript":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$MODE" "$BASE" "$focus_json" \
        "$DIFF_LINES" "$FILES_CHANGED" "$UNTRACKED_FILES" \
        "$WARNED" "$CANCELLED" "$exit_code" "$blocker" "$ALLOW_PII_PATHS" \
        "$TRANSCRIPT" >> "$TELEMETRY_FILE"
}

# ─── PII-classed path guard (Builder Contract rule 4 / cicatrix W140) ───
# PII_PATH_PATTERNS / pii_path_hit live in scripts/lib/spalla_redact.sh
# (sourced above) — the CONTENTS never leave this refusal, only the
# matched paths are printed.
if [[ "$SELF_TEST" != "true" ]]; then
    PII_HITS=()
    while IFS= read -r _tf; do
        [[ -z "$_tf" ]] && continue
        pii_path_hit "$_tf" && PII_HITS+=("$_tf")
    # --no-renames on both: `--name-only` alone prints only the DESTINATION of
    # a detected rename, so moving a file OUT of a PII-classed dir was never
    # refused and its context lines still rode along embedded (harness S5).
    # With renames off, git reports old+new as a plain delete+add pair — both
    # sides land in this list and either one tripping pii_path_hit refuses.
    done < <({ git -c core.quotePath=false "${DIFF_ARGS[@]}" --no-renames --name-only 2>/dev/null; git -c core.quotePath=false diff --no-renames HEAD --name-only 2>/dev/null; git -c core.quotePath=false ls-files --others --exclude-standard 2>/dev/null; } | sort -u)
    if [[ "${#PII_HITS[@]}" -gt 0 ]] && [[ "$ALLOW_PII_PATHS" != "true" ]]; then
        echo "REFUSED: diff touches PII-classed path(s) — refusing to send to an external seat without --allow-pii-paths:" >&2
        printf '  %s\n' "${PII_HITS[@]}" >&2
        echo "(paths only shown above; file CONTENTS never left this refusal — Builder Contract rule 4)" >&2
        record_telemetry 7 false
        echo "RESULT_PATH=$TRANSCRIPT"
        exit 7
    fi
fi

# A dispatch only counts as a review when a verdict line landed in the
# assistant's FINAL message. codex-cli has shipped two "never ran" shapes that
# both looked clean from outside: a clap usage error at exit 2 (0.149.1,
# honest) and the same error at exit 0 (0.151.0, silent — every caller judging
# by return code read it as "clean"; ledger 2026-09-01). The exit code alone
# cannot distinguish "ran and found nothing" from "never ran"; the verdict
# line can — but only when read from the assistant-only output, not the
# combined transcript (review loop-20260906-partner-gate-followups, comment
# 5555186204): the transcript carries diagnostics and an echo of the prompt
# (which embeds the untrusted diff), so a transcript scan both misses a
# verdict landing past the first 50 lines (false "never judged") and accepts a
# verdict-shaped line in the echoed prompt (false "judged" — the
# never-judged-as-success defect). `--output-last-message` makes codex itself
# write the final assistant message to $LAST_MESSAGE; that file is the only
# verdict source. A missing or empty file = never judged, however clean the
# transcript looks.
verdict_present() {
    [[ -s "$1" ]] && grep -qiE '^[[:space:]]*(BLOCKER|MEDIUM|LOW|LGTM)\b' "$1"
}

# --self-test: liveness probe for the dispatch path itself. The diff guards
# above are skipped (there is nothing to review); a trivial prompt goes through
# the real codex exec invocation and a verdict line must come back. Exists so
# the wrapper's own health is provable on demand, instead of being discovered
# by the next review that silently never happened.
if [[ "$SELF_TEST" == "true" ]]; then
    SELFTEST_PROMPT="[SPALLA-SELFTEST]

Liveness probe for the codex-spalla dispatch path — not a review. Do not
inspect the repository or run any tool. Reply with exactly one line whose first
word is one of: BLOCKER, MEDIUM, LOW, LGTM — then one short sentence
confirming the CLI answered."
    echo "[spalla] self-test: codex exec --sandbox read-only -c model_reasoning_effort=xhigh (trivial prompt)" >&2
    CODEX_EXIT=0
    printf '%s' "$SELFTEST_PROMPT" | codex exec --sandbox read-only \
        -c model_reasoning_effort=xhigh --output-last-message "$LAST_MESSAGE" \
        - >> "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
    # codex (a separate process) writes $LAST_MESSAGE itself; it inherits this
    # shell's umask 077, but re-tighten explicitly (S7) in case that ever changes.
    if [[ -e "$LAST_MESSAGE" ]]; then chmod 0600 "$LAST_MESSAGE" 2>/dev/null || true; fi
    if [[ "$CODEX_EXIT" -eq 0 ]] && ! verdict_present "$LAST_MESSAGE"; then
        echo "ERROR: self-test got exit 0 but no verdict line in the assistant-only output — codex never judged." >&2
        CODEX_EXIT=6
    fi
    if [[ "$CODEX_EXIT" -ne 0 ]]; then
        echo "ERROR: self-test failed (exit $CODEX_EXIT). Transcript: $TRANSCRIPT" >&2
        record_telemetry "$CODEX_EXIT" false
        echo "RESULT_PATH=$TRANSCRIPT"
        exit "$CODEX_EXIT"
    fi
    grep -iE -m 1 '^[[:space:]]*(BLOCKER|MEDIUM|LOW|LGTM)\b' "$LAST_MESSAGE" | sed 's/^/[spalla] self-test verdict: /' >&2
    record_telemetry 0 false
    echo "RESULT_PATH=$TRANSCRIPT"
    exit 0
fi

# Install INT trap BEFORE the small-diff countdown so Ctrl-C during sleep
# records cancelled=true telemetry and exits cleanly with code 3.
trap 'CANCELLED="true"; record_telemetry 3 false; echo "" >&2; echo "CANCELLED by user." >&2; exit 3' INT

# Scope-warning uses TOTAL_DIFF_LINES (committed + uncommitted) and
# TOTAL_FILES (committed + uncommitted + untracked) so that a branch with
# only large uncommitted edits across several tracked files is not
# misclassified as "small scope". (Codex spalla self-review #2 + #9.)
TOTAL_FILES=$((FILES_CHANGED + UNCOMMITTED_FILES + UNTRACKED_FILES))
if [[ "$TOTAL_DIFF_LINES" -lt 10 ]] || [[ "$TOTAL_FILES" -lt 3 ]]; then
    WARNED="true"
    printf '⚠ scope is small — Claude self-review may be cheaper.\n' >&2
    printf '⚠ proceeding in 5s (Ctrl-C to cancel) ...\n' >&2
    printf '⚠ logged warned=true to telemetry.\n' >&2
    sleep 5
fi

# strip_data_file_deletes / redact_for_external already sourced above.
_fail_closed_redaction() {
    echo "ERROR: redaction FAILED-CLOSED — refusing to send this content to codex." >&2
    record_telemetry 8 false
    echo "RESULT_PATH=$TRANSCRIPT"
    exit 8
}

# Capture diff bodies once for embedding in the prompt.
DIFF_BODY="$(git -c core.quotePath=false "${DIFF_ARGS[@]}" 2>/dev/null | head -2000 | strip_data_file_deletes || echo '<diff capture failed>')"
UNCOMMITTED_BODY="$(git -c core.quotePath=false diff HEAD 2>/dev/null | head -1000 | strip_data_file_deletes || true)"
DIFF_BODY="$(redact_for_external "$DIFF_BODY")" || _fail_closed_redaction
UNCOMMITTED_BODY="$(redact_for_external "$UNCOMMITTED_BODY")" || _fail_closed_redaction

# Codex spalla self-review #1: embed full content of each untracked file
# (with per-file line cap) so reviewers can actually inspect new files.
# Cap: max 25 files × 200 lines/file ≈ 5000 lines budget, plus skip binary.
UNTRACKED_FILES_FOR_DUMP="$(git -c core.quotePath=false ls-files --others --exclude-standard 2>/dev/null | head -25 || true)"
UNTRACKED_LIST="$(git -c core.quotePath=false ls-files --others --exclude-standard 2>/dev/null | head -50 || true)"
# Same class of bug as UNCOMMITTED_FILES above (`|| echo 0` doubling grep -c's
# own already-printed "0" under pipefail) — same fix, `|| true`.
UNTRACKED_TOTAL_FOR_DUMP="$(printf '%s\n' "$UNTRACKED_FILES_FOR_DUMP" | grep -c . 2>/dev/null || true)"
UNTRACKED_BODIES=""
if [[ -n "$UNTRACKED_FILES_FOR_DUMP" ]]; then
    while IFS= read -r ufile; do
        [[ -z "$ufile" ]] && continue
        # Skip binary / large files (>500KB) — embedding either would just
        # blow the token budget.
        if [[ ! -f "$ufile" ]]; then continue; fi
        if [[ "$(file --brief --mime-encoding "$ufile" 2>/dev/null)" == "binary" ]]; then
            UNTRACKED_BODIES+=$'\n----- BEGIN UNTRACKED FILE: '"$ufile"$' (binary, skipped) -----\n'
            continue
        fi
        if [[ "$(wc -c < "$ufile" 2>/dev/null || echo 0)" -gt 500000 ]]; then
            UNTRACKED_BODIES+=$'\n----- BEGIN UNTRACKED FILE: '"$ufile"$' (>500KB, skipped) -----\n'
            continue
        fi
        UNTRACKED_BODIES+=$'\n----- BEGIN UNTRACKED FILE: '"$ufile"$' -----\n'
        UNTRACKED_BODIES+="$(head -200 "$ufile" 2>/dev/null || echo '<read failed>')"
        UNTRACKED_BODIES+=$'\n----- END UNTRACKED FILE: '"$ufile"$' -----\n'
    done <<< "$UNTRACKED_FILES_FOR_DUMP"
fi
UNTRACKED_BODIES="$(redact_for_external "$UNTRACKED_BODIES")" || _fail_closed_redaction

PROMPT="[SPALLA]

You are Codex CLI in Spalla Mode (see ~/.codex/AGENTS.md). Claude Opus 4.7 has just produced the diff below and is about to commit/push. Adversarially review it.

Focus brief: ${FOCUS:-no specific focus — give a balanced adversarial review against CLAUDE.md and AGENTS.md rules.}

Base: $BASE
Committed diff stats: $DIFF_LINES lines across $FILES_CHANGED files.
Uncommitted lines: $UNCOMMITTED_LINES
Untracked files: $UNTRACKED_FILES

Output template (strict):
- Line 1: one of BLOCKER, MEDIUM, LOW, LGTM
- Para 2: one paragraph 'what Claude proposed'
- Bullets: edge cases / blind spots / CLAUDE.md or AGENTS.md drift, with file:line cites

Verify before asserting (grep the repo). No prose summary at end.

--- COMMITTED DIFF (truncated to 2000 lines) ---
${DIFF_BODY}
--- END COMMITTED DIFF ---

--- UNCOMMITTED DIFF (truncated to 1000 lines) ---
${UNCOMMITTED_BODY}
--- END UNCOMMITTED DIFF ---

--- UNTRACKED FILES (paths, truncated to 50) ---
${UNTRACKED_LIST}
--- END UNTRACKED FILES ---

--- UNTRACKED FILE CONTENTS (first 25 files, head -200 each, binary/>500KB skipped) ---
${UNTRACKED_BODIES}
--- END UNTRACKED FILE CONTENTS ---"

echo "Dispatching codex (mode=$MODE base=$BASE committed=${DIFF_LINES}L/${FILES_CHANGED}f uncommitted=${UNCOMMITTED_LINES}L untracked=${UNTRACKED_FILES})" >&2
echo "Transcript will be saved to: $TRANSCRIPT" >&2

CODEX_EXIT=0
# Append (>>) not truncate (>) — TRANSCRIPT was created exclusively above
# with set -C noclobber; another process clobbering it would already have
# been refused at creation, so >> is safe and idempotent.
if [[ "$MODE" == "review" ]]; then
    # `codex review --base BRANCH "$PROMPT"` is rejected:
    # "argument '--base <BRANCH>' cannot be used with '[PROMPT]'".
    # Use `codex exec --sandbox read-only` instead — it accepts our
    # custom [SPALLA] prompt while staying read-only on the workspace.
    # NEVER `--full-auto`: removed in codex-cli 0.149.1 (see the header drift
    # note); exec mode's old full-auto semantics are spelled out below as an
    # explicit workspace-write sandbox.
    printf '%s' "$PROMPT" | codex exec --sandbox read-only \
        -c model_reasoning_effort=xhigh --output-last-message "$LAST_MESSAGE" \
        - >> "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
else
    printf '%s' "$PROMPT" | codex exec --sandbox workspace-write \
        -c model_reasoning_effort=xhigh --output-last-message "$LAST_MESSAGE" \
        - >> "$TRANSCRIPT" 2>&1 || CODEX_EXIT=$?
fi
if [[ -e "$LAST_MESSAGE" ]]; then chmod 0600 "$LAST_MESSAGE" 2>/dev/null || true; fi

# The exit code, not only the transcript, must distinguish "ran and found
# nothing" from "never ran" (ledger 2026-09-01: codex-cli 0.151.0 printed a
# clap usage error at exit 0 and every caller read the run as a clean review).
# The verdict is judged from the assistant-only file only — a verdict-shaped
# line in the echoed prompt or diff is not a judge (loop
# 20260906-partner-gate-followups, comment 5555186204).
if [[ "$CODEX_EXIT" -eq 0 ]] && ! verdict_present "$LAST_MESSAGE"; then
    echo "ERROR: codex exited 0 but no verdict line (BLOCKER/MEDIUM/LOW/LGTM) in its final assistant message — codex never judged this diff." >&2
    echo "Transcript: $TRANSCRIPT (assistant-only output: $LAST_MESSAGE)" >&2
    CODEX_EXIT=6
fi

BLOCKER="false"
# Codex spalla self-review #8: BLOCKER detection scans only the head of the
# assistant-only final message (the verdict header per output template).
# Scanning the whole final message would false-positive on bullets that quote
# earlier BLOCKER verdicts (verify-after-fix runs cite previous transcripts).
if head -50 "$LAST_MESSAGE" 2>/dev/null | grep -qiE '^[[:space:]]*BLOCKER\b'; then
    BLOCKER="true"
    REVIEWS_DIR="$REPO_ROOT/docs/codex-reviews"
    mkdir -p "$REVIEWS_DIR"
    chmod 0700 "$REVIEWS_DIR" 2>/dev/null || true
    BLOCKER_COPY="$REVIEWS_DIR/${TS}-${RAND}-blocker-${SLUG}.md"
    cp "$TRANSCRIPT" "$BLOCKER_COPY"
    chmod 0600 "$BLOCKER_COPY" 2>/dev/null || true
    echo "BLOCKER detected — also copied to $BLOCKER_COPY" >&2
fi

record_telemetry "$CODEX_EXIT" "$BLOCKER"

echo "RESULT_PATH=$TRANSCRIPT"
exit "$CODEX_EXIT"
