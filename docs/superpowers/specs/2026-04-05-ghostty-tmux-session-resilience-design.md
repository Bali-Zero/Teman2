# Ghostty + tmux Session Resilience — Design Spec

**Date:** 2026-04-05  
**Status:** Approved  
**Author:** Bali Zero AI Team

---

## Problem

Ghostty crashes or closes → Claude Code process dies → session context lost. No automatic way to resume exactly where you left off (working directory, branch, layout, MOS briefing).

---

## Goals

- **A)** Ghostty crash/restart → auto-reopen + re-attach tmux → Claude Code still running
- **B)** Multiple Claude Code sessions → each in its own tmux pane, all resumable
- **C)** Claude Code process dies → relaunch in one keystroke with MOS briefing

---

## Architecture

```
Ghostty (terminal emulator)
    └── tmux session "balizero" (persistent, survives Ghostty crash)
            ├── window 0: "main"
            │     ├── pane 0 (left 60%):        claude ~/Desktop/nuzantara
            │     ├── pane 1 (top-right 20%):   claude <worktree or task>
            │     └── pane 2 (bottom-right 20%): shell (git log / status)
            ├── window 1: "air"
            │     └── pane 0:                   ssh air
            └── window 2: "ops"
                  ├── pane 0:                   fly logs / tail -f
                  └── pane 1:                   free shell
```

**Key principle:** tmux owns layout and process lifetime. Ghostty is a view into tmux, nothing more. `claude` processes live inside tmux panes — they survive Ghostty crashes.

---

## Components

### 1. `~/.local/bin/bz` — Main launcher

Entry point for everything. Called by Ghostty on startup.

```
bz
├── if tmux session "balizero" exists → attach
└── else → create session with fixed layout → launch claude in each pane
```

No arguments needed for normal use. Optional: `bz reset` to tear down and rebuild layout.

### 2. `~/.config/tmux/tmux.conf` — tmux configuration

- Prefix: `Ctrl+Space` (avoids conflict with Ghostty `Ctrl+b` is unused anyway, but cleaner)
- Theme: Bali Zero colors (`#0c0c0e` bg, `#d4845a` accent) matching terminal theme
- Plugins via TPM:
  - `tmux-plugins/tmux-resurrect` — saves/restores sessions including processes
  - `tmux-plugins/tmux-continuum` — auto-save every 15 min + restore on tmux start
- Status bar: shows session name, window, pane, git branch, time

Key bindings:
| Keybind | Action |
|---------|--------|
| `Ctrl+Space r` | Resurrect restore (manual) |
| `Ctrl+Space R` | Nuclear reset — rebuild layout from scratch |
| `Ctrl+Space b` | Show MOS briefing in current pane |
| `Ctrl+Space c` | Relaunch `claude` in current pane (if dead) |

### 3. `~/.ghostty/config` changes

```
command = /bin/zsh -lc 'bz'
```

This replaces the bare `command = /bin/zsh`. On every new Ghostty window, it calls `bz` which attaches to tmux. `window-save-state = always` (already set) ensures Ghostty remembers the window position/size.

### 4. `~/.claude/scripts/tmux-briefing.sh` — MOS briefing generator

Runs as part of SessionStart hook when `$TMUX` is set and the tmux session already existed (resume scenario vs. fresh start).

Output (printed to terminal before Claude reads first prompt):

```
⚡ RESUME — branch: main | last tool: Edit @ 14:32
📍 CWD: ~/Desktop/nuzantara
🧠 Recent memories:
   decision: C5 CELL completato ...
   fact: deps/orchestrator.py è la nuova location ...
   [3 more]
```

Detection logic:
- `$TMUX` present → inside tmux
- `tmux list-sessions | grep balizero` already existed before this attach → resume
- Uses `~/.claude/live-status.json` for last tool/cwd/branch
- Uses `mem recent` for last 5 memories (importance >= 7)

### 5. `~/.claude/settings.json` — SessionStart hook addition

Add to the existing SessionStart hooks array:

```json
{
  "type": "command",
  "command": "bash ~/.claude/scripts/tmux-briefing.sh",
  "statusMessage": "Loading tmux session briefing..."
}
```

Runs only when `$TMUX` is set (script exits 0 silently if not in tmux).

---

## Data Flow

### Scenario A — Ghostty crash + reopen

```
Ghostty crashes
    → tmux session "balizero" continues running on macOS
    → claude processes in panes continue running

User reopens Ghostty
    → Ghostty restores window (window-save-state = always)
    → command = bz runs
    → bz detects session "balizero" exists → tmux attach
    → view snaps back to exact pane layout
    → claude in each pane is still running, conversation intact
```

### Scenario B — Claude Code process dies inside pane

```
User presses Ctrl+Space c (or types bz in the dead pane)
    → bz detects pane working dir from tmux
    → launches: claude <detected_dir>
    → SessionStart hook runs tmux-briefing.sh
    → briefing printed: last tool, branch, top-5 memories
    → Claude Code starts with context
```

### Scenario C — Fresh machine restart (tmux-continuum)

```
Mac restarts
    → tmux-continuum auto-restores session "balizero" on first tmux start
    → bz is called by Ghostty → attaches
    → claude processes NOT alive (continuum restores layout but not live processes)
    → each pane shows: "Press Ctrl+Space c to relaunch Claude"
    → or: bz detects dead panes and auto-relaunches with briefing
```

---

## Implementation Sequence

1. Install tmux + TPM
2. Write `~/.config/tmux/tmux.conf` with Bali Zero theme + plugins + keybinds
3. Install TPM plugins (`tmux-resurrect`, `tmux-continuum`)
4. Write `~/.local/bin/bz` launcher script
5. Write `~/.claude/scripts/tmux-briefing.sh`
6. Modify `~/.config/ghostty/config`: add `command = /bin/zsh -lc 'bz'`
7. Add SessionStart hook to `~/.claude/settings.json`
8. Test: open Ghostty → verify layout builds → kill Ghostty → reopen → verify attach

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `bz` called but tmux not installed | Prints install instructions, falls back to plain zsh |
| Session "balizero" exists but window count wrong | `bz reset` tears down and rebuilds |
| `mem` command fails in briefing | Briefing skips memory section, shows only live-status.json |
| Ghostty opens but `bz` hangs | Ghostty timeout 5s → falls back to plain shell |
| tmux-continuum fails to restore | `bz` catches missing session and builds from scratch |

---

## Out of Scope

- Air machine (different layout, different concern)
- Multiple Ghostty windows (one window = one tmux session is sufficient)
- iTerm2 / Warp compatibility
- Remote tmux sessions via SSH

---

## Success Criteria

- [ ] Ghostty crash + reopen in < 3 seconds, Claude Code still running
- [ ] `bz` from any shell attaches or creates session deterministically  
- [ ] MOS briefing visible at top of each Claude Code resume
- [ ] `Ctrl+Space c` relaunches dead claude in < 2 seconds
- [ ] tmux-continuum saves state every 15 min automatically
