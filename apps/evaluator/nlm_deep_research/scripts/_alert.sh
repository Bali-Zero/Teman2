# shellcheck shell=bash
# =============================================================================
# _alert.sh — the one way these cron wrappers speak.
#
# WHY. All 18 wrappers in this directory alarmed like this (verbatim,
# run_nb3_pipeline.sh:56-62 before this change):
#
#   if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
#       curl -s -X POST ".../sendMessage" -d ... >/dev/null 2>&1 || true
#   fi
#
# Three layers of silence stacked on the ONE path that only executes when
# something is already broken:
#
#   1. the `if` makes the no-token world do NOTHING, and leave no trace of it —
#      and the token-poor environment is precisely the launchd/cron one that
#      produces the failures the alarm exists to report;
#   2. `>/dev/null 2>&1` throws away the API's reply, so a 401, a wrong chat_id
#      and a delivered message are indistinguishable (W104: judge the REPLY,
#      never the exit code);
#   3. `|| true` swallows curl's own failure on top.
#
# An alarm conditioned on the health of its environment works exactly in the
# cases where it isn't needed.
#
# WHAT THIS DOES INSTEAD. `scripts/tg_notify.py` owns the token chain
# (env -> ~/.nuzantara-secrets.env -> ssh relay -> spool) and never fails its
# caller: what it cannot deliver now, it spools. So the caller stops needing a
# token at all. The only remaining failure — the gateway itself being absent —
# is the LOUD branch, because "could not send" must never read like "sent".
#
# Usage:
#   . "$(dirname "$0")/_alert.sh"      # tolerant: see the fallback note below
#   ALERT_SOURCE="nb3_pipeline"        # optional; defaults to the script name
#   alert p0 "⚠️ NB-3 pipeline FAILED (exit $EXIT_CODE)"
#
# Tiers are tg_notify's: p0 (wakes someone) · digest (grouped) · log (recorded).
# =============================================================================

# Four levels up from scripts/ is the repo root:
# apps/evaluator/nlm_deep_research/scripts -> apps/evaluator/nlm_deep_research
# -> apps/evaluator -> apps -> <repo>.  Derived from THIS file's location, never
# from $HOME: the gateway must be the one that ships with these wrappers, not
# whatever a HOME copy happens to carry (superscar #1 — HOME-fork).
_ALERT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
TG_NOTIFY="${TG_NOTIFY:-$(cd "$_ALERT_LIB_DIR/../../../.." && pwd)/scripts/tg_notify.py}"

# ── One voice per failure (2026-08-07) ───────────────────────────────────────
# Nineteen of the twenty wrappers in this directory run under a cron wrapper
# that ALSO alarms on their non-zero exit, so one failure produced two P0s ~2s
# apart. Measured on the archived pair for run_nb2_pipeline, they carry
# DIFFERENT information and neither contains the other:
#
#   script:   "🚨 NB2 Immigration pipeline FAILED (exit 1) — check <log path>"
#   wrapper:  "CRON FAIL <host> / Job: … / Exit: 1 / Duration: 3s" + 600 bytes
#             of raw tail — registry counts, a JSON run blob, no log path.
#
# So silencing either one loses something real. Instead the wrapper hands the
# job its own sentence: a wrapper that will alarm on our failure AND can
# capture our output exports CRON_ALARM_OWNER, and we print the text for it to
# carry instead of sending a second message.
#
# The default direction is the safe one — with the variable unset we send
# exactly as before. run_peraturan_ingestion.sh runs from crontab with NO
# wrapper at all, so an unconditional deferral would have made it mute; the
# opt-in is what keeps it speaking. The wrapper only claims the voice when it
# can actually carry the words (cron-runner exports this only once its capture
# tmpfile exists), so "deferred" can never mean "dropped".
#
# Marker string duplicated rather than sourced: the alarm path must not gain a
# dependency that can fail the way the thing it reports fails (W108). The three
# copies are pinned in agreement by scripts/test_cron_single_voice.sh.
CRON_ALERT_MARKER="CRON_ALERT_P0:"

alert() {  # alert <tier> <text...>
    local tier="$1"
    shift
    local source_name="${ALERT_SOURCE:-$(basename "${0:-nlm-deep-research}" .sh)}"

    if [ "$tier" = "p0" ] && [ -n "${CRON_ALARM_OWNER:-}" ]; then
        # Newlines collapsed: the wrapper greps this back out line-anchored.
        printf '%s %s\n' "$CRON_ALERT_MARKER" "$(printf '%s' "$*" | tr '\n' ' ')"
        echo "tg[p0] deferred to wrapper ${CRON_ALARM_OWNER} (single voice)" >&2
        return 0
    fi

    if [ ! -f "$TG_NOTIFY" ]; then
        echo "ALERT NOT SENT — gateway missing at $TG_NOTIFY [$tier]: $*" >&2
        return 1
    fi

    local out rc
    if out=$(/usr/bin/python3 "$TG_NOTIFY" --tier "$tier" --source "$source_name" "$*" 2>&1); then
        rc=0
    else
        rc=$?
    fi
    echo "tg[$tier] rc=$rc ${out:-<no output>}" >&2
    return $rc
}
