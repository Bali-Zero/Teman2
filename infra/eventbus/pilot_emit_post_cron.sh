#!/bin/zsh
# pilot_emit_post_cron.sh — wrapper script that runs ORIGINAL cron job, then emits eventbus event
#
# Usage: pilot_emit_post_cron.sh <agent_name> <event_type> <original_cmd...>
#
# Pattern: cron-driven AND event-driven coexist. Original cron keeps running,
# we just emit a corresponding event after success so downstream subscribers wake up.

set -uo pipefail

AGENT_NAME="${1:?agent_name required}"
EVENT_TYPE="${2:?event_type required}"
shift 2

LOG="$HOME/logs/pilot-emit-${AGENT_NAME}.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] starting agent=$AGENT_NAME event=$EVENT_TYPE cmd=$*" >> "$LOG"

# Run original command, capture exit
"$@"
EXIT=$?

echo "[$(date)] original cmd exit=$EXIT" >> "$LOG"

# Only emit on success (exit 0)
if [ $EXIT -eq 0 ]; then
    # Build minimal payload — agent-specific real payload should come from agent itself
    # For pilot phase: emit a "completion" event with timestamp + exit + pointer to log
    case "$EVENT_TYPE" in
        intel.collected)
            PAYLOAD=$(cat <<EOF
{
  "source": "$AGENT_NAME",
  "citation_or_url": "cron-completion-marker://$AGENT_NAME",
  "raw_payload": {"completion_log": "$LOG", "exit": $EXIT},
  "collected_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "agent_name": "$AGENT_NAME"
}
EOF
)
            ;;
        regulatory.delta.detected)
            # Extract delta from regulatory-watcher's most recent output JSON
            DATE=$(TZ=Asia/Makassar date +%Y-%m-%d)
            DELTA_JSON="$HOME/Desktop/nuzantara/research/regulatory/${DATE}-delta.json"
            if [ -f "$DELTA_JSON" ]; then
                COUNT=$(python3 -c "import json; d=json.load(open('$DELTA_JSON')); print(d.get('new_today_count', 0))" 2>/dev/null || echo "0")
                if [ "$COUNT" -gt 0 ]; then
                    # Emit one event per delta
                    python3 -c "
import json, sys
sys.path.insert(0, '$HOME/scripts')
from eventbus import publish
d = json.load(open('$DELTA_JSON'))
for delta in d.get('deltas', []):
    eid = publish('regulatory.delta.detected', {
        'citation': delta.get('citation', 'unknown'),
        'regulation_type': delta.get('citation', '').split()[0] if delta.get('citation') else 'unknown',
        'service_lines': delta.get('service_line', []) if isinstance(delta.get('service_line'), list) else [delta.get('service_line', 'unknown')],
        'summary': delta.get('summary', '')[:500],
        'urgency': delta.get('urgency', 'medium'),
        'source': delta.get('source', 'regulatory-watcher'),
        'detected_at': delta.get('first_seen_at', '$(date -u +%Y-%m-%dT%H:%M:%SZ)'),
    }, emitted_by='$AGENT_NAME')
    print(f'emitted {eid}')
" >> "$LOG" 2>&1
                else
                    echo "[$(date)] no deltas to emit (new_today_count=0)" >> "$LOG"
                fi
            fi
            PAYLOAD=""  # Already emitted above
            ;;
        topic.candidate.created)
            # wr2-topic-selector writes its picks to war_room_drafts in Postgres; we emit a marker
            PAYLOAD=$(cat <<EOF
{
  "topic_slug": "cron-marker-$(date +%s)",
  "domain": "regulatory",
  "audience_segment": "founder",
  "score": 0,
  "source_intel_event_id": "cron-marker",
  "key_facts": [],
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
            ;;
        content.draft.ready)
            # wr2-supervisor / draft-generator output
            PAYLOAD=$(cat <<EOF
{
  "topic_slug": "cron-marker",
  "slides_path": "/tmp/none",
  "brief_path": "/tmp/none",
  "critic_report_path": "/tmp/none",
  "slide_count": 0,
  "hero_count": 0,
  "status": "pass",
  "ready_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
)
            ;;
        publish.completed)
            PAYLOAD=$(cat <<EOF
{
  "item_id": "cron-marker-$(date +%s)",
  "published_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "channel": "instagram"
}
EOF
)
            ;;
        *)
            echo "[$(date)] unknown event_type $EVENT_TYPE — no emit" >> "$LOG"
            PAYLOAD=""
            ;;
    esac

    if [ -n "$PAYLOAD" ]; then
        EID=$(python3 -c "
import json, sys
sys.path.insert(0, '$HOME/scripts')
from eventbus import publish
print(publish('$EVENT_TYPE', json.loads('''$PAYLOAD'''), emitted_by='$AGENT_NAME'))
" 2>>"$LOG")
        echo "[$(date)] emitted event_id=$EID" >> "$LOG"
    fi
fi

exit $EXIT
