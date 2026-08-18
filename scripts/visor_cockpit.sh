#!/bin/bash
# visor_cockpit.sh — tmux fleet cockpit for the Vision Pro Mac Virtual Display (32:9 ultra-wide).
# 6-pane snapshot of the Nuzantara organism: PR queue, main landings, escalations, system load,
# a free shell in the repo, and a lightweight read-only organism report.
# Primary target: Pro (nuzantara@Nuzantara, ~/nuzantara). Machine-agnostic via $HOME/nuzantara
# (M5: /Users/balizero/nuzantara). Never installs anything on its own.
set -u

SESSION="cockpit"
REPO="$HOME/nuzantara"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found. Install it first:" >&2
  echo "  brew install tmux" >&2
  exit 2
fi

# Reattach if the session is already up, regardless of how we were called.
if tmux has-session -t "$SESSION" 2>/dev/null; then
  exec tmux attach-session -t "$SESSION"
fi

if [ "${1:-}" = "--attach" ]; then
  echo "No '$SESSION' session running yet — run without --attach to create it." >&2
  exit 1
fi

if [ ! -d "$REPO" ]; then
  echo "Warning: repo not found at $REPO — panes that read it will show errors." >&2
fi

# --- pane commands ---
# `watch` ships with neither Pro nor M5 (not a macOS default, needs a separate brew formula) —
# a while/sleep loop gives the same "refresh every N seconds" behavior without a hard dependency,
# and doubles as the resilience wrapper: one failed probe prints its error and the pane lives on.

PANE_PRS='while true; do clear; date "+--- PR queue (%H:%M:%S) ---"; gh pr list --limit 15 --json number,state,headRefName --template "{{range .}}{{.number}}{{\"\t\"}}{{.state}}{{\"\t\"}}{{.headRefName}}{{\"\n\"}}{{end}}" 2>&1; sleep 90; done'

PANE_MAIN="while true; do clear; date '+--- origin/main landings (%H:%M:%S) ---'; git -C \"$REPO\" fetch origin main --quiet 2>&1; git -C \"$REPO\" log --oneline -12 origin/main 2>&1; sleep 120; done"

PANE_ESC="while true; do clear; date '+--- escalations_pro.jsonl, last 10 (%H:%M:%S) ---'; F=\"$REPO/shared/escalations_pro.jsonl\"; if [ -f \"\$F\" ]; then if command -v jq >/dev/null 2>&1; then tail -10 \"\$F\" | jq -r '[(.ts // 0 | strftime(\"%H:%M:%S\")), (.machine // \"?\"), (.status // \"?\"), (.job // .type // \"?\")] | @tsv' 2>&1; else tail -10 \"\$F\" 2>&1; fi; else echo \"(no escalations file at \$F)\"; fi; sleep 60; done"

if command -v htop >/dev/null 2>&1; then
  PANE_SYS='htop'
else
  PANE_SYS='top -o cpu'
fi

PANE_SHELL="cd \"$REPO\" 2>/dev/null; exec \${SHELL:-/bin/zsh} -l"

if [ -f "$REPO/scripts/pending_arms_report.py" ]; then
  PANE_ORG="while true; do clear; date '+--- pending_arms_report.py, W81 ledger (%H:%M:%S) ---'; python3 \"$REPO/scripts/pending_arms_report.py\" 2>&1; sleep 300; done"
else
  PANE_ORG="while true; do clear; date '+--- \$HOME/logs, most recent (%H:%M:%S) ---'; ls -lt \"\$HOME/logs\" 2>&1 | head -20; sleep 300; done"
fi

tmux new-session -d -s "$SESSION" -n fleet "$PANE_PRS"
tmux split-window -h -t "$SESSION" "$PANE_MAIN"
tmux split-window -h -t "$SESSION" "$PANE_ESC"
tmux split-window -h -t "$SESSION" "$PANE_SYS"
tmux split-window -h -t "$SESSION" "$PANE_SHELL"
tmux split-window -h -t "$SESSION" "$PANE_ORG"
tmux select-layout -t "$SESSION" tiled

tmux select-pane -t "$SESSION.0" -T "PR queue"
tmux select-pane -t "$SESSION.1" -T "main landings"
tmux select-pane -t "$SESSION.2" -T "escalations"
tmux select-pane -t "$SESSION.3" -T "system"
tmux select-pane -t "$SESSION.4" -T "shell ($REPO)"
tmux select-pane -t "$SESSION.5" -T "organism"
tmux set-option -t "$SESSION" -g pane-border-status top
tmux set-option -t "$SESSION" -g pane-border-format "#{pane_index} #{pane_title}"

exec tmux attach-session -t "$SESSION"
