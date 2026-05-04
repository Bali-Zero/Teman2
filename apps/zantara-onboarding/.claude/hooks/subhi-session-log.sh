#!/usr/bin/env bash
# subhi-session-log.sh — Stop hook, dual responsibility:
#   1. Append jsonl session log (raw, for Antonello weekly review)
#   2. Extract session summary → .claude/memory-mirror-subhi/<date>.md
#      (read by zantara-onboarding sub-agent for conversational continuity)
set -euo pipefail

INPUT=$(cat)
LOG_FILE="$HOME/zantara-onboarding/.claude/session-log.jsonl"
SUMMARY_DIR="$HOME/zantara-onboarding/.claude/memory-mirror-subhi"
mkdir -p "$(dirname "$LOG_FILE")" "$SUMMARY_DIR"

# === 1. Raw jsonl log ===
ENRICHED=$(echo "$INPUT" | python3 -c "
import sys, json, os
from datetime import datetime
d = json.load(sys.stdin)
d['_logged_at'] = datetime.utcnow().isoformat() + 'Z'
d['_machine'] = os.uname().nodename
print(json.dumps(d))
")
echo "$ENRICHED" >> "$LOG_FILE"

# === 2. Session summary ===
TODAY=$(date +%Y-%m-%d)
NOW=$(date +%H:%M)
SUMMARY_FILE="$SUMMARY_DIR/${TODAY}.md"

# Extract via Python — Stop hook input has session_id, transcript_path
SUMMARY=$(echo "$INPUT" | python3 <<'PYEOF'
import sys, json, os, re
from pathlib import Path

try:
    d = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

transcript_path = d.get("transcript_path", "")
session_id = d.get("session_id", "unknown")[:8]

# Read transcript if available
text = ""
if transcript_path and os.path.exists(transcript_path):
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "user":
                        c = msg.get("message", {}).get("content", "")
                        if isinstance(c, str):
                            text += c + "\n"
                        elif isinstance(c, list):
                            for item in c:
                                if isinstance(item, dict) and "text" in item:
                                    text += item["text"] + "\n"
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        pass

# Heuristic topic extraction
topics = set()
patterns = {
    "NB": r"NB-\d+|NotebookLM",
    "files": r"(FunnelFeature|analytics\.ts|ArticleClient|HeaderWhatsApp|sitemap|robots)",
    "domains": r"(visa|KITAS|KITAP|KBLI|tax|property|CoreTax|PT PMA)",
    "branches": r"sancho/[a-z0-9-]+",
    "git_ops": r"\b(commit|push|PR|pull request|merge|rebase)\b",
    "concepts": r"(GA4|funnel|CTA|tracking|UTM|Search Console|RBAC)",
}
for label, pat in patterns.items():
    for m in re.finditer(pat, text, re.IGNORECASE):
        topics.add(m.group(0))

topic_list = sorted(topics)[:15]  # cap at 15 to keep summary tight

# Output: emit a markdown block
print(f"## Sesi {session_id}")
if topic_list:
    print(f"**Topik:** {', '.join(topic_list)}")
print(f"**Reason:** {d.get('stop_hook_active', 'n/a')}")
PYEOF
)

if [[ -n "$SUMMARY" ]]; then
  {
    echo ""
    echo "<!-- Sesi $NOW -->"
    echo "$SUMMARY"
  } >> "$SUMMARY_FILE"
fi

exit 0
