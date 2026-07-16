#!/bin/bash
# world-scan-run.sh — weekly external failure-pattern scan for the evolver.
#
# Reuse-first (2026-06-04): forked from ~/scripts/wr2-external-bench-run.sh.
# ~80% reused (multi-LLM ingest+extract via a Claude agent, DeepSeek translate
# via world_scan_translate.py, devils-advocate-style gate built into the
# translator's deterministic grade, _proposed/ staging, Telegram). The only NEW
# code is world_scan_translate.py (pattern -> draft executable probe).
#
# Pipeline:
#   1. INGEST+EXTRACT (Claude Opus agent w/ web search): scan SRE/security/
#      agent-failure sources -> JSON list of failure patterns.
#   2. TRANSLATE (world_scan_translate.py + DeepSeek): each pattern -> draft probe
#      with a DETERMINISTIC executability gate (ADOPT/OBSERVE/REJECT).
#   3. STAGE: write drafts to research/operations/_proposed/<date>-world-scan.md.
#   4. NOTIFY: Telegram summary to Antonello. NEVER auto-merge; human promotes
#      an ADOPT draft into scar_probes.py by hand.
#
# Cron: weekly (1st-of-week guard inside). Schedule via LaunchAgent.
# Cost: ~$0.05/week (Gemini/Claude OAuth + DeepSeek translate calls).

set -euo pipefail

LOGDIR="${HOME}/logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/world-scan.log"
ERR="$LOGDIR/world-scan.err.log"

HARNESS_DIR="${SCAR_REPLAY_DIR:-${HOME}/nuzantara-deploy/agent-library/scar_replay}"
REPO_ROOT="${WORLD_SCAN_REPO_ROOT:-${HOME}/nuzantara-deploy}"
WEEK_TAG="$(date +%Y-W%V)"
PROPOSED_DIR="${REPO_ROOT}/research/operations/_proposed"
OUTPUT_FILE="${PROPOSED_DIR}/${WEEK_TAG}-world-scan-probes.md"
PATTERNS_JSON="/tmp/world-scan-patterns-${WEEK_TAG}.json"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

# telegram_alert: reused verbatim from scar-replay-run.sh (#1090). Resolves token
# + chat id from sanctioned vaults; tolerates OWNER vs APPROVAL chat-id naming
# drift; suppresses silently if creds unresolved (Law 4 — never block on outage).
telegram_alert() {
  local msg="$1"
  local tok="${TELEGRAM_BOT_TOKEN:-}"
  local chat="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_APPROVAL_CHAT_ID:-}}"
  if [[ -z "${tok}" || -z "${chat}" ]]; then
    for f in "${HOME}/.nuzantara-secrets.env" "${HOME}/.openclaw/workspace/.env.master"; do
      [[ -f "$f" ]] || continue
      [[ -z "${tok}"  ]] && tok="$(grep -m1 -E '^TELEGRAM_BOT_TOKEN=' "$f" 2>/dev/null | cut -d= -f2- | tr -d '"')"
      [[ -z "${chat}" ]] && chat="$(grep -m1 -E '^TELEGRAM_(OWNER|APPROVAL)_CHAT_ID=' "$f" 2>/dev/null | cut -d= -f2- | tr -d '"')"
    done
  fi
  if [[ -z "${tok}" || -z "${chat}" ]]; then
    log "WARN: telegram creds unresolved — human-alert suppressed: ${msg}"
    return 0
  fi
  curl -sS --max-time 20 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
    -d "chat_id=${chat}" -d "text=${msg}" >/dev/null 2>&1 || true
}

log "world-scan starting (week=${WEEK_TAG}, out=${OUTPUT_FILE})"

# --- idempotence: one scan per week ---
if [ -s "$OUTPUT_FILE" ]; then
  log "skip: ${OUTPUT_FILE} already exists ($(wc -l < "$OUTPUT_FILE") lines). Delete to re-run."
  exit 0
fi

# --- worktree-isolation guard (same discipline as scar-replay-run.sh): never
#     run from inside the shared deploy worktree ---
case "$(pwd -P)/" in
  "${REPO_ROOT}/"*) log "REFUSE: cwd inside shared deploy worktree; aborting."; exit 0 ;;
esac

# --- secrets: DEEPSEEK_API_KEY (with vault drift fallback) + telegram ---
DS_KEY="${DEEPSEEK_API_KEY:-}"
if [ -z "$DS_KEY" ]; then
  for f in "${HOME}/.nuzantara-secrets.env" "${HOME}/.openclaw/workspace/.env.master"; do
    [ -f "$f" ] || continue
    line=$(grep -m1 -E '^DEEPSEEK_API_KEY=' "$f" 2>/dev/null || true)
    [ -n "$line" ] && { DS_KEY="${line#DEEPSEEK_API_KEY=}"; DS_KEY="${DS_KEY%\"}"; DS_KEY="${DS_KEY#\"}"; break; }
  done
fi
if [ -z "$DS_KEY" ]; then
  log "FATAL: DEEPSEEK_API_KEY not found in any vault — cannot translate. Aborting."
  exit 2
fi
export DEEPSEEK_API_KEY="$DS_KEY"

mkdir -p "$PROPOSED_DIR"

# --- Step 1: INGEST + EXTRACT via Claude Opus agent (OAuth-only, web search) ---
# Reuse of the wr2-external-bench invocation shape. The agent does the web
# research and emits a strict JSON array of failure patterns to PATTERNS_JSON.
INGEST_PROMPT="You are world-scan, the evolver's external research scout.

Research the LAST ~30 days of public best-practices and post-mortems on:
  - SRE / reliability engineering (toil, retries, idempotency, locking, queues)
  - chaos engineering & fault injection
  - autonomous-agent / LLM-agent failure modes (loops, drift, tool misuse, state)
  - CI/CD & git-worktree / deploy hazards
Use web search. Prefer concrete engineering write-ups (incident reports, SRE
books/blogs, postmortems), NOT listicles.

Extract 6-12 DISTINCT failure patterns relevant to a self-improving ops agent
that runs local git worktrees, LaunchAgent cron, shell scripts, Postgres.

Write ONLY a strict JSON array to ${PATTERNS_JSON}, each item:
  {\"title\": \"...\", \"text\": \"2-4 sentence description of the failure mode and why it bites\", \"source\": \"url or outlet\"}
No prose around the JSON. Reject vague/cultural advice — only concrete, testable failure mechanics."

CLAUDE_BIN="${HOME}/.local/bin/claude"; [ -x "$CLAUDE_BIN" ] || CLAUDE_BIN="/opt/homebrew/bin/claude"

log "step1: ingest+extract via claude opus (web search)"
timeout 1800 "$CLAUDE_BIN" -p \
  --model claude-opus-4-8 \
  --permission-mode bypassPermissions \
  "$INGEST_PROMPT" >> "$LOG" 2>> "$ERR" || log "WARN: ingest agent exit=$?"

if [ ! -s "$PATTERNS_JSON" ]; then
  log "FATAL: no patterns JSON produced at ${PATTERNS_JSON}. Aborting."
  # Telegram: this needs a human (ingest produced nothing).
  telegram_alert "⚠️ world-scan ${WEEK_TAG}: ingest produced no patterns. Check ${ERR}."
  exit 3
fi
log "step1 done: $(wc -c < "$PATTERNS_JSON") bytes of patterns"

# --- Step 2+3: TRANSLATE each pattern + STAGE drafts ---
log "step2: translate patterns -> draft probes (DeepSeek + deterministic gate)"
PYTHONPATH="${HARNESS_DIR}" python3 - "$PATTERNS_JSON" "$OUTPUT_FILE" "$WEEK_TAG" <<'PYEOF' >> "$LOG" 2>> "$ERR"
import json, sys, os, datetime
sys.path.insert(0, os.environ["PYTHONPATH"])
import world_scan_translate as wt

patterns_path, out_path, week = sys.argv[1], sys.argv[2], sys.argv[3]
key = os.environ["DEEPSEEK_API_KEY"]
patterns = json.load(open(patterns_path))
if not isinstance(patterns, list):
    print("patterns JSON is not a list — abort"); sys.exit(4)

drafts = []
for p in patterns:
    title = (p.get("title") or "untitled").strip()
    text = (p.get("text") or "") + "\nSource: " + (p.get("source") or "")
    d = wt.translate_pattern(key, title, text)
    d.source_refs = p.get("source") or title
    drafts.append(d)

adopt = [d for d in drafts if d.category == "ADOPT"]
observe = [d for d in drafts if d.category == "OBSERVE"]
reject = [d for d in drafts if d.category == "REJECT"]

header = (
    f"# World-Scan draft probes — {week}\n\n"
    f"> Auto-generated by world-scan (reuse-first fork of wr2-external-bench). "
    f"These are DRAFT replay-probes proposed from external failure patterns. "
    f"**Nothing here is live.** A human promotes an ADOPT draft into "
    f"`agent-library/scar_replay/scar_probes.py` by hand (fixture + assertion as "
    f"code) and commits it. Never auto-merged (Law 5).\n\n"
    f"**Summary:** {len(adopt)} ADOPT · {len(observe)} OBSERVE · {len(reject)} REJECT "
    f"(of {len(drafts)} patterns scanned).\n\n---\n\n"
)
body = "".join(wt.render_draft_md(d) for d in (adopt + observe + reject))
open(out_path, "w").write(header + body)
print(f"WORLD_SCAN_SUMMARY adopt={len(adopt)} observe={len(observe)} reject={len(reject)} total={len(drafts)}")
PYEOF

if [ ! -s "$OUTPUT_FILE" ]; then
  log "FATAL: translation produced no output file. Check ${ERR}."
  telegram_alert "⚠️ world-scan ${WEEK_TAG}: translation failed. Check ${ERR}."
  exit 5
fi

SUMMARY=$(grep -h "WORLD_SCAN_SUMMARY" "$LOG" | tail -1 || echo "summary unavailable")
log "step3 done: ${OUTPUT_FILE} ($(wc -l < "$OUTPUT_FILE") lines) — ${SUMMARY}"

# --- Step 4: notify (human reviews; never auto-merge) ---
telegram_alert "🌐 world-scan ${WEEK_TAG} done. ${SUMMARY}. Draft probes staged at research/operations/_proposed/${WEEK_TAG}-world-scan-probes.md — review & promote ADOPT drafts by hand."
log "DONE world-scan ${WEEK_TAG}"
exit 0
