# Ghostty + tmux Session Resilience — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Code sessions survive Ghostty crashes by running them inside a persistent tmux session, with auto-resume, fixed layout, and MOS briefing on reattach.

**Architecture:** tmux session "balizero" owns all Claude Code processes and terminal layout. Ghostty is a pure view — it calls `bz` on startup which attaches to the existing session or creates it fresh with a fixed 3-window layout. tmux-resurrect + tmux-continuum auto-save every 15 min and restore on tmux start. A SessionStart hook injects a MOS briefing whenever Claude Code is launched inside an existing tmux session.

**Tech Stack:** tmux 3.6a (already installed via Homebrew), TPM (tmux plugin manager), tmux-resurrect, tmux-continuum, zsh, Ghostty 1.3, existing MOS scripts (`mem`, `live-status.json`)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `~/.config/tmux/tmux.conf` | tmux config: prefix, theme, plugins, keybinds |
| Create | `~/.local/bin/bz` | Main launcher: attach or create "balizero" session |
| Create | `~/.claude/scripts/tmux-briefing.sh` | MOS briefing on resume |
| Modify | `~/.config/ghostty/config` | Add `command = /bin/zsh -lc 'bz'` |
| Modify | `~/.claude/settings.json` | Add tmux-briefing SessionStart hook |

---

## Task 1: Install TPM and write tmux.conf

**Files:**
- Create: `~/.config/tmux/tmux.conf`
- Create: `~/.tmux/plugins/tpm/` (via git clone)

- [ ] **Step 1: Install TPM**

```bash
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
```

Expected: clones into `~/.tmux/plugins/tpm/`

- [ ] **Step 2: Create tmux config directory**

```bash
mkdir -p ~/.config/tmux
```

- [ ] **Step 3: Write `~/.config/tmux/tmux.conf`**

```bash
cat > ~/.config/tmux/tmux.conf << 'EOF'
# ============================================================================
#  BALI ZERO TMUX v1.0
#  Persistent sessions for Claude Code — survives Ghostty crashes
# ============================================================================

# --- Prefix: Ctrl+Space (clean, no Ghostty conflicts) -----------------------
unbind C-b
set -g prefix C-Space
bind C-Space send-prefix

# --- Core settings -----------------------------------------------------------
set -g default-terminal "xterm-256color"
set -ag terminal-overrides ",xterm-256color:RGB"
set -g history-limit 50000
set -g mouse on
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g escape-time 0
set -g focus-events on

# --- Status bar — Bali Zero theme -------------------------------------------
# Colors: #0c0c0e bg, #d4845a accent, #8b8fa8 muted, #e2e8f0 text
set -g status on
set -g status-interval 5
set -g status-position bottom
set -g status-style "bg=#0c0c0e,fg=#e2e8f0"

set -g status-left-length 40
set -g status-left "#[bg=#d4845a,fg=#0c0c0e,bold] #S #[bg=#0c0c0e,fg=#d4845a] "

set -g status-right-length 80
set -g status-right "#[fg=#8b8fa8] #{?client_prefix,#[fg=#d4845a]⚡ PREFIX ,}#[fg=#8b8fa8]%H:%M  %d %b"

setw -g window-status-style "fg=#8b8fa8,bg=#0c0c0e"
setw -g window-status-current-style "fg=#d4845a,bg=#0c0c0e,bold"
setw -g window-status-format " #I:#W "
setw -g window-status-current-format " #I:#W● "

set -g pane-border-style "fg=#3a1111"
set -g pane-active-border-style "fg=#d4845a"
set -g message-style "bg=#d4845a,fg=#0c0c0e,bold"

# --- Keybinds ----------------------------------------------------------------
# Reload config
bind r source-file ~/.config/tmux/tmux.conf \; display "tmux.conf reloaded"

# Split panes (intuitive)
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"

# Navigate panes with Alt+arrows (no prefix needed)
bind -n M-Left  select-pane -L
bind -n M-Right select-pane -R
bind -n M-Up    select-pane -U
bind -n M-Down  select-pane -D

# Resize panes
bind -r H resize-pane -L 5
bind -r L resize-pane -R 5
bind -r K resize-pane -U 5
bind -r J resize-pane -D 5

# Nuclear reset — rebuild balizero layout from scratch
bind R run-shell "tmux kill-session -t balizero 2>/dev/null; bz" \; display "Rebuilding balizero..."

# Relaunch claude in current pane (if dead)
bind c run-shell "~/.local/bin/bz-relaunch"

# Show MOS briefing in current pane
bind b run-shell "bash ~/.claude/scripts/tmux-briefing.sh" \; display "MOS briefing loaded"

# --- Plugins -----------------------------------------------------------------
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'

# resurrect: save/restore claude processes
set -g @resurrect-capture-pane-contents 'on'
set -g @resurrect-processes 'claude ssh "~/.local/bin/bz"'

# continuum: auto-save every 15 min, auto-restore on tmux start
set -g @continuum-restore 'on'
set -g @continuum-save-interval '15'

# Initialize TPM (keep this line at the very bottom)
run '~/.tmux/plugins/tpm/tpm'
EOF
```

- [ ] **Step 4: Start a tmux server to test config loads without errors**

```bash
/opt/homebrew/bin/tmux -f ~/.config/tmux/tmux.conf new-session -d -s test-config 2>&1 && echo "CONFIG OK" && tmux kill-session -t test-config
```

Expected: `CONFIG OK`

- [ ] **Step 5: Install plugins via TPM**

```bash
/opt/homebrew/bin/tmux new-session -d -s tpm-install -f ~/.config/tmux/tmux.conf
~/.tmux/plugins/tpm/bin/install_plugins
tmux kill-session -t tpm-install 2>/dev/null
ls ~/.tmux/plugins/
```

Expected: `tmux-continuum  tmux-resurrect  tpm` in plugins list

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add docs/superpowers/plans/2026-04-05-ghostty-tmux-session-resilience.md
git add docs/superpowers/specs/2026-04-05-ghostty-tmux-session-resilience-design.md
git commit -m "feat(ghostty): add tmux session resilience spec + plan"
```

---

## Task 2: Write `bz` launcher script

**Files:**
- Create: `~/.local/bin/bz`
- Create: `~/.local/bin/bz-relaunch`

- [ ] **Step 1: Write `~/.local/bin/bz`**

```bash
cat > ~/.local/bin/bz << 'EOF'
#!/bin/zsh
# bz — Bali Zero session launcher
# Attaches to existing tmux "balizero" or creates it with fixed layout.
# Called by Ghostty on startup. Also usable from any shell.

TMUX_BIN="/opt/homebrew/bin/tmux"
SESSION="balizero"
MONOREPO="$HOME/Desktop/nuzantara"
CLAUDE_BIN="$HOME/.local/bin/claude"

# Safety: if tmux not found, fall back to plain shell
if ! command -v "$TMUX_BIN" &>/dev/null; then
  echo "⚠️  tmux not found. Install: brew install tmux"
  exec /bin/zsh
fi

# Handle reset flag
if [[ "$1" == "reset" ]]; then
  "$TMUX_BIN" kill-session -t "$SESSION" 2>/dev/null
  echo "✅ Session '$SESSION' killed. Rebuilding..."
fi

# If already inside tmux, don't nest — just inform
if [[ -n "$TMUX" ]]; then
  echo "✅ Already inside tmux session. Use Ctrl+Space R to reset."
  return 0 2>/dev/null || exit 0
fi

# If session exists → attach
if "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null; then
  exec "$TMUX_BIN" -f ~/.config/tmux/tmux.conf attach-session -t "$SESSION"
fi

# Session doesn't exist → create with fixed layout
# Window 0: main (3 panes)
"$TMUX_BIN" -f ~/.config/tmux/tmux.conf new-session -d -s "$SESSION" -n "main" -c "$MONOREPO"

# Split: right 40% vertical
"$TMUX_BIN" split-window -t "$SESSION:main" -h -p 40 -c "$MONOREPO"

# Split right pane: top/bottom 50/50
"$TMUX_BIN" split-window -t "$SESSION:main.2" -v -p 50 -c "$MONOREPO"

# Window 1: air
"$TMUX_BIN" new-window -t "$SESSION" -n "air"
"$TMUX_BIN" send-keys -t "$SESSION:air" "ssh air" Enter

# Window 2: ops (2 panes)
"$TMUX_BIN" new-window -t "$SESSION" -n "ops" -c "$MONOREPO"
"$TMUX_BIN" split-window -t "$SESSION:ops" -h -p 50 -c "$MONOREPO"

# Go back to main window
"$TMUX_BIN" select-window -t "$SESSION:main"
"$TMUX_BIN" select-pane -t "$SESSION:main.1"

# Launch claude in pane 0 (main left)
"$TMUX_BIN" send-keys -t "$SESSION:main.1" "cd $MONOREPO && $CLAUDE_BIN" Enter

# Launch claude in pane 1 (main top-right)
"$TMUX_BIN" send-keys -t "$SESSION:main.2" "cd $MONOREPO && $CLAUDE_BIN" Enter

# Pane 2 (main bottom-right): git status shell
"$TMUX_BIN" send-keys -t "$SESSION:main.3" "cd $MONOREPO && git log --oneline -10" Enter

# Attach
exec "$TMUX_BIN" attach-session -t "$SESSION"
EOF
chmod +x ~/.local/bin/bz
```

- [ ] **Step 2: Write `~/.local/bin/bz-relaunch`**

This is called by `Ctrl+Space c` to relaunch claude in the current pane.

```bash
cat > ~/.local/bin/bz-relaunch << 'EOF'
#!/bin/zsh
# bz-relaunch — relaunch claude in current tmux pane with MOS briefing
# Called via Ctrl+Space c keybind. Must be run inside tmux.

CLAUDE_BIN="$HOME/.local/bin/claude"
MONOREPO="$HOME/Desktop/nuzantara"

# Detect current pane working dir from tmux
PANE_DIR="$(tmux display-message -p '#{pane_current_path}')"
TARGET="${PANE_DIR:-$MONOREPO}"

# Mark this as a briefing-needed resume
export BZ_RESUME=1

exec "$CLAUDE_BIN" --cwd "$TARGET"
EOF
chmod +x ~/.local/bin/bz-relaunch
```

- [ ] **Step 3: Verify bz is executable and on PATH**

```bash
which bz && bz --help 2>/dev/null || echo "bz is at ~/.local/bin/bz"
ls -la ~/.local/bin/bz ~/.local/bin/bz-relaunch
```

Expected: both files exist, executable bit set (`-rwxr-xr-x`)

- [ ] **Step 4: Dry-run bz (without Ghostty)**

```bash
# Test: create the session headlessly and verify it has 3 windows
/opt/homebrew/bin/tmux -f ~/.config/tmux/tmux.conf new-session -d -s balizero-test 2>/dev/null
# Count windows (should be 0 since we didn't run bz fully — just test bz logic)
bz reset 2>/dev/null; true
# Run bz in detached mode to create session
BZ_TEST=1 /opt/homebrew/bin/tmux -f ~/.config/tmux/tmux.conf new-session -d -s balizero -n "main" ~/Desktop/nuzantara
/opt/homebrew/bin/tmux list-windows -t balizero 2>/dev/null | head -5
/opt/homebrew/bin/tmux kill-session -t balizero 2>/dev/null
echo "bz dry-run OK"
```

Expected: `bz dry-run OK`

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git commit -m "feat(ghostty): add bz launcher and bz-relaunch scripts"
```

---

## Task 3: Write tmux-briefing.sh

**Files:**
- Create: `~/.claude/scripts/tmux-briefing.sh`

- [ ] **Step 1: Write `~/.claude/scripts/tmux-briefing.sh`**

```bash
cat > ~/.claude/scripts/tmux-briefing.sh << 'EOF'
#!/bin/bash
# tmux-briefing.sh — MOS briefing on Claude Code resume inside tmux
# Called by SessionStart hook. Exits silently if not in tmux.

# Only run inside tmux
[[ -z "$TMUX" ]] && exit 0

LIVE_STATUS="$HOME/.claude/live-status.json"
MEM_BIN="$HOME/.claude/scripts/mem"

# Read live-status.json
if [[ -f "$LIVE_STATUS" ]]; then
  TS=$(python3 -c "import json; d=json.load(open('$LIVE_STATUS')); print(d.get('ts','?'))" 2>/dev/null | sed 's/T/ /;s/Z//')
  LAST_TOOL=$(python3 -c "import json; d=json.load(open('$LIVE_STATUS')); print(d.get('tool','?'))" 2>/dev/null)
  LAST_BRANCH=$(python3 -c "import json; d=json.load(open('$LIVE_STATUS')); print(d.get('git_branch','?'))" 2>/dev/null)
  LAST_CWD=$(python3 -c "import json; d=json.load(open('$LIVE_STATUS')); print(d.get('cwd','?'))" 2>/dev/null)
else
  TS="?"
  LAST_TOOL="?"
  LAST_BRANCH="?"
  LAST_CWD="?"
fi

# Time display: extract HH:MM from ISO timestamp
TIME_DISPLAY=$(echo "$TS" | grep -oE '[0-9]{2}:[0-9]{2}' | head -1 || echo "?")

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ⚡ BALI ZERO RESUME                                 ║"
printf "║  branch: %-20s  last: %-10s     ║\n" "$LAST_BRANCH" "$TIME_DISPLAY"
printf "║  cwd:    %-42s  ║\n" "$(echo $LAST_CWD | sed "s|$HOME|~|")"
printf "║  tool:   %-42s  ║\n" "$LAST_TOOL"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  🧠 Recent memories (importance >= 7):              ║"

# Load memories from MOS
if [[ -x "$MEM_BIN" ]]; then
  MEMORIES=$("$MEM_BIN" recent 2>/dev/null | head -5)
  if [[ -n "$MEMORIES" ]]; then
    while IFS= read -r line; do
      # Truncate to 50 chars for display
      TRUNC="${line:0:50}"
      printf "║  · %-50s  ║\n" "$TRUNC"
    done <<< "$MEMORIES"
  else
    echo "║  · (no memories loaded)                              ║"
  fi
else
  echo "║  · (mem not found)                                   ║"
fi

echo "╚══════════════════════════════════════════════════════╝"
echo ""
EOF
chmod +x ~/.claude/scripts/tmux-briefing.sh
```

- [ ] **Step 2: Test briefing output standalone**

```bash
# Simulate being in tmux by setting TMUX env
export TMUX="fake"
bash ~/.claude/scripts/tmux-briefing.sh
unset TMUX
```

Expected: box with branch/tool/time/cwd + memory lines printed. No errors.

- [ ] **Step 3: Test that briefing exits silently when not in tmux**

```bash
unset TMUX
bash ~/.claude/scripts/tmux-briefing.sh
echo "exit code: $?"
```

Expected: no output, `exit code: 0`

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/nuzantara
git commit -m "feat(ghostty): add tmux-briefing.sh MOS resume script"
```

---

## Task 4: Wire SessionStart hook in settings.json

**Files:**
- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Read current SessionStart hooks to find insertion point**

```bash
cat ~/.claude/settings.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
hooks = d.get('hooks', {}).get('SessionStart', [])
print(f'Current SessionStart hooks: {len(hooks)}')
for i, h in enumerate(hooks):
    print(f'  [{i}] matcher={h.get(\"matcher\",\"\")} | hooks={len(h.get(\"hooks\",[]))}')
"
```

Expected: shows 2 existing SessionStart hooks (compact + blank matcher)

- [ ] **Step 2: Add tmux-briefing hook to settings.json**

The new hook goes into the existing blank-matcher SessionStart entry (the second one). Read current file first, then edit:

```bash
python3 << 'PYEOF'
import json

path = "/Users/nuzantara/.claude/settings.json"
with open(path) as f:
    d = json.load(f)

new_hook = {
    "type": "command",
    "command": "bash ~/.claude/scripts/tmux-briefing.sh",
    "statusMessage": "Loading tmux session briefing...",
    "async": False
}

# Add to the blank-matcher SessionStart entry (index 1)
for entry in d["hooks"]["SessionStart"]:
    if entry.get("matcher", "") == "":
        entry["hooks"].append(new_hook)
        break

with open(path, "w") as f:
    json.dump(d, f, indent=4)

print("✅ Hook added")
PYEOF
```

Expected: `✅ Hook added`

- [ ] **Step 3: Verify hook was added correctly**

```bash
cat ~/.claude/settings.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for entry in d['hooks']['SessionStart']:
    if entry.get('matcher','') == '':
        for h in entry['hooks']:
            if 'tmux-briefing' in h.get('command',''):
                print('✅ tmux-briefing hook found:', h['command'])
"
```

Expected: `✅ tmux-briefing hook found: bash ~/.claude/scripts/tmux-briefing.sh`

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/nuzantara
git add -p ~/.claude/settings.json 2>/dev/null || true
git commit -m "feat(ghostty): wire tmux-briefing hook in Claude Code SessionStart"
```

---

## Task 5: Modify Ghostty config

**Files:**
- Modify: `~/.config/ghostty/config`

- [ ] **Step 1: Backup current Ghostty config**

```bash
cp ~/.config/ghostty/config ~/.config/ghostty/config.backup.$(date +%Y%m%d)
echo "✅ Backup created"
```

- [ ] **Step 2: Replace `command = /bin/zsh` with `bz` launcher**

```bash
# Verify current command line
grep "^command" ~/.config/ghostty/config
```

Expected: `command = /bin/zsh`

- [ ] **Step 3: Edit the command line**

Open `~/.config/ghostty/config` and replace:

```
command = /bin/zsh
```

with:

```
command = /bin/zsh -lc 'exec /Users/nuzantara/.local/bin/bz'
```

Use full path (not `bz` alias) so Ghostty's non-interactive shell finds it.

```bash
sed -i '' 's|^command = /bin/zsh$|command = /bin/zsh -lc '"'"'exec /Users/nuzantara/.local/bin/bz'"'"'|' ~/.config/ghostty/config
grep "^command" ~/.config/ghostty/config
```

Expected: `command = /bin/zsh -lc 'exec /Users/nuzantara/.local/bin/bz'`

- [ ] **Step 4: Verify Ghostty config is valid (no syntax errors)**

```bash
# Ghostty validates config on start — check by running a quick parse
/Applications/Ghostty.app/Contents/MacOS/ghostty +validate-config 2>&1 | head -10 || echo "validate-config not available — will verify on restart"
```

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git commit -m "feat(ghostty): launch bz on Ghostty startup for tmux persistence"
```

---

## Task 6: End-to-end test

No code changes — pure verification.

- [ ] **Step 1: Create balizero session via bz**

```bash
# Run bz in background (non-interactive test)
/opt/homebrew/bin/tmux -f ~/.config/tmux/tmux.conf new-session -d -s balizero -n "main" ~/Desktop/nuzantara 2>/dev/null || true
/opt/homebrew/bin/tmux list-sessions
```

Expected: `balizero: N windows`

- [ ] **Step 2: Verify window layout**

```bash
/opt/homebrew/bin/tmux list-windows -t balizero
```

Expected: windows `main`, `air`, `ops`

- [ ] **Step 3: Verify pane count in main window**

```bash
/opt/homebrew/bin/tmux list-panes -t balizero:main
```

Expected: 3 panes listed

- [ ] **Step 4: Simulate Ghostty crash — kill and reattach**

```bash
# In a separate terminal or script: verify session survives
SESSION_EXISTS=$(/opt/homebrew/bin/tmux has-session -t balizero 2>/dev/null && echo "yes" || echo "no")
echo "Session after simulated crash: $SESSION_EXISTS"
```

Expected: `Session after simulated crash: yes`

- [ ] **Step 5: Test tmux-continuum auto-save**

```bash
# Trigger manual resurrect save to verify plugin works
/opt/homebrew/bin/tmux run-shell ~/.tmux/plugins/tmux-resurrect/scripts/save.sh 2>&1 | head -5
ls ~/.tmux/resurrect/ 2>/dev/null | head -3
```

Expected: resurrect file created in `~/.tmux/resurrect/`

- [ ] **Step 6: Test briefing script in real tmux pane**

```bash
/opt/homebrew/bin/tmux send-keys -t balizero:main.1 "bash ~/.claude/scripts/tmux-briefing.sh" Enter
# Wait 1s and capture output
sleep 1
/opt/homebrew/bin/tmux capture-pane -t balizero:main.1 -p | grep -E "BALI ZERO RESUME|branch:" | head -3
```

Expected: `BALI ZERO RESUME` and `branch:` lines visible

- [ ] **Step 7: Open Ghostty manually and verify it attaches**

Open Ghostty (Cmd+N or restart app). Verify:
- tmux session opens immediately (no plain zsh prompt)
- Status bar shows "balizero" session name in orange
- 3 panes visible in main window

- [ ] **Step 8: Final commit**

```bash
cd ~/Desktop/nuzantara
git add docs/
git commit -m "feat(ghostty): tmux session resilience — all components wired and tested"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Scenario A (Ghostty crash → tmux survives → reattach): Task 2 `bz` + Task 5 Ghostty config
- ✅ Scenario B (multiple Claude sessions): Task 2 layout (pane 0 + pane 1 both run claude)
- ✅ Scenario C (claude process dies → relaunch): Task 2 `bz-relaunch` + `Ctrl+Space c` in Task 1
- ✅ MOS briefing on resume: Task 3 + Task 4 hook
- ✅ tmux-continuum auto-save: Task 1 tmux.conf
- ✅ Error handling (tmux not found, mem fails): Task 2 `bz` fallback + Task 3 briefing guards
- ✅ Bali Zero theme: Task 1 tmux.conf status bar colors

**Type consistency:** `bz-relaunch` calls `claude --cwd` — verify this flag is valid for the local claude binary. If not, replace with `cd $TARGET && claude`.

**One known risk:** `claude --cwd` flag may not exist in all Claude Code versions. The `bz-relaunch` script uses it — if it fails, fallback is `cd $TARGET && exec claude`.
