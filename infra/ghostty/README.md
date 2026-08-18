# Ghostty — Nuzantara fleet profile

The terminal Antonello actually works in, on Pro / M5 / Mini, kept in one place
and under review instead of drifting per machine.

## Why this exists

Before this, the fleet ran three different terminals under one name. Measured
on 2026-08-18:

| | Pro | M5 | Mini |
|---|---|---|---|
| config file | `config.ghostty` (53 keys) | `config` (22 keys) | none at all |
| theme | Catppuccin Mocha | Catppuccin Macchiato | Ghostty default |
| font | `…Nerd Font Mono` | `…Nerd Font` | no Nerd font installed |
| ssh terminfo | on | **off** | — |
| splits / resize keys | none | yes | — |
| clipboard guards | yes | **none** | — |

Neither machine was wrong; they had simply been written months apart and never
reconciled. `~/.config` is not a git repository, so there was also no history
and no backup of either.

## Layout

```
infra/ghostty/
├── config              → installed as ~/.config/ghostty/config   (the entry point)
├── fleet.ghostty       → ~/.config/ghostty/fleet.ghostty         (shared base)
├── keys.ghostty        → ~/.config/ghostty/keys.ghostty          (keybinds + palette)
├── machines/
│   ├── pro.ghostty     ─┐
│   ├── m5.ghostty       ├→ ~/.config/ghostty/machine.ghostty     (one per host)
│   └── mini.ghostty    ─┘
├── install.sh          back up → install → validate → roll back on failure
├── verify.sh           prove it is installed, current, and working
└── verify-latest.sh    → ~/.config/ghostty/verify-latest.sh  (what nuz/v types — always runs origin/main's verify.sh, even on a behind checkout)
```

`~/.config/ghostty/local.ghostty` is yours: never installed, never in git,
loaded last, optional (`?` prefix). Put one-machine experiments there.

## Use

```bash
bash infra/ghostty/install.sh --dry-run   # what would change
bash infra/ghostty/install.sh             # do it (backs up first)
bash infra/ghostty/verify.sh              # prove it
```

The machine is detected by hostname; `--machine pro|m5|mini` overrides it.
Reload a running Ghostty with `cmd+shift+comma`. The reference states explicitly
that `background-opacity` needs a full quit and relaunch; blur and the Dock icon
are not documented either way, so relaunch is the reliable route for all three.

One location outranks all of this: macOS searches
`~/Library/Application Support/com.mitchellh.ghostty/config.ghostty` **before**
any XDG path. Ghostty.app creates that file empty by itself, which is harmless —
but if it ever carries settings they silently beat everything installed here, so
`verify.sh` checks its CONTENT (not its existence) and fails when it is non-empty.

Drift between the installed copy and this directory is caught two ways: locally
by `verify.sh`, and fleet-wide by `scripts/lint_home_fork.py --check`, which
arbitrates against `origin/main` rather than the local checkout (that
distinction is the W106b scar: on a machine whose checkout is behind, the naive
comparison blames the copy that is actually current).

## Config mechanics worth knowing

Measured against Ghostty 1.3.1 on macOS 27.0, not assumed:

- Ghostty auto-reads **two** filenames: `config` and `config.ghostty`. Both are
  read and merged when both exist.
- **An included file always beats a top-level value.** The reference is explicit:
  "configuration files do not take effect until after the entire configuration is
  loaded." Measured order: top-level `config` → top-level `config.ghostty` →
  `config`'s includes → `config.ghostty`'s includes.
- Among includes, declaration order is `fleet` → `keys` → `machine` → `local`,
  and **later wins — but only for scalar settings**. Repeatable ones accumulate:
  `font-family` builds a fallback chain rather than overriding (reset it with
  `font-family = ""` first), and `font-feature` / `command-palette-entry` append.
  `keybind` appends too, except that the same trigger declared again replaces
  its action.
- Relative include paths resolve against the directory of the file holding the
  directive — **not** the process working directory, and **not** the symlink
  target if the file is reached through a symlink.
- `~` is expanded in include paths. `$HOME` is **not** (it fails loudly).
- `?` before a path suppresses the error when the file is absent. Without it, one
  missing include makes the whole configuration fail to load.
- `scrollback-limit` is in **bytes, per surface** — not lines, not per app.
- `+show-config` prints the effective configuration but **drops keybind
  prefixes** — a `global:` bind shows as an ordinary one. It cannot be used to
  verify prefix state; read the file instead.
- `+list-keybinds --default=true` prefixes every line with `keybind = ` and
  prints Ghostty's normalised form (`cmd`→`super`, `left`→`arrow_left`,
  `comma`→`,`). Comparing your bindings against it without normalising reports
  everything as non-default.

## Two defects this profile addresses

**`xterm-ghostty` is unknown across the fleet.** `infocmp xterm-ghostty` exits 1
on both M5 and Mini, so every ssh out of a Ghostty window landed on a host that
could not describe the terminal. `shell-integration-features` now carries
`ssh-terminfo` (installs it on first connect, then caches the host) and
`ssh-env` (carries `COLORTERM`, and falls back to `xterm-256color` when the
install cannot happen). Check what has been cached with `ghostty +ssh-cache`.

**Nothing told you a long job had finished.** `notify-on-command-finish =
unfocused` with a 45s floor sends a macOS notification for deploys, test suites
and LLM panels — but only when you are looking elsewhere, and only for your own
interactive commands (it rides on OSC 133, which non-interactive tool shells do
not emit).

## Machine identity

Each host owns a colour, carried by the cursor, the split dividers and the Dock
icon: **Pro peach `#fab387`**, **M5 blue `#89b4fa`**, **Mini green `#a6e3a1`**.
It costs nothing and makes a screenshot, a screen-share or a Vision Pro virtual
display name its own machine.

`macos-icon = custom-style` is flagged experimental upstream ("we may change the
format of the custom styles in the future"). If a future release rejects the
value, `+validate-config` fails and `install.sh` refuses the install rather than
leaving a broken config; the fix is to drop three lines from the machine profile.

## Known gaps

- **Agent-team panes do not open in Ghostty.** Claude Code hosts teammate panes
  in tmux or iTerm2 only; in a bare Ghostty window it falls back to an external
  tmux session or fails outright. Running Claude Code inside `tmux` makes panes
  appear in the Ghostty window. The tmux binary is present on all three machines
  (measured 2026-08-18: Pro 3.7b, M5 3.7b, Mini 3.6a) but the binary is only the
  prerequisite — the panes appear when Claude Code actually runs INSIDE a
  session. The palette entry "Claude: agent-pane session (tmux)" and `cmd+alt+n,
  t` both type the attach command. See `docs/runbooks/ghostty-fleet.md`.
- **`global:` keybinds need a per-machine Accessibility grant.** Without it the
  quick-terminal binding is silently inert — no error, nothing happens. The
  grant cannot be probed remotely (the runbook documents the read-only local
  check); press the chord once after install to know.

Three gaps this file used to list are cured and guarded: Mini's missing Nerd
font (installed 2026-08-18; `verify.sh` still checks resolution), M5's missing
tmux (installed 2026-08-18), and `nuz/v` typing a dead path on a behind
checkout (closed 2026-08-19 — `nuz/v` now types `verify-latest.sh`, which
always runs origin/main's `verify.sh` regardless of local checkout freshness;
see the file's own header for why).
