# Runbook — Ghostty across the fleet

Config source and design: [`infra/ghostty/README.md`](../../infra/ghostty/README.md).
This runbook covers operating it: installing, reloading, the ssh terminfo mesh,
and the one integration that does **not** work in Ghostty.

## Install / reinstall

```bash
bash infra/ghostty/install.sh --dry-run   # what would change
bash infra/ghostty/install.sh             # backs up, installs, validates
bash infra/ghostty/verify.sh              # proves it
```

The host is detected by hostname (`Nuzantara`→pro, `Air-M5`→m5, `Mini-Pro2`→mini);
`--machine` overrides. If validation fails the installer restores the backup and
exits non-zero — a machine is never left with a config Ghostty cannot load.

**What a reload does and does not pick up.** `cmd+shift+comma` re-reads the
config, but `background-opacity`, `background-blur` and the Dock icon only change
on a full quit and relaunch. A reload that "did nothing" is usually this.

## The two filenames trap

Ghostty auto-reads **`config` and `config.ghostty`** and merges both. Measured
load order on 1.3.1:

1. top-level `config`
2. top-level `config.ghostty`
3. the files `config` included
4. the files `config.ghostty` included

An **included** file therefore always beats a top-level value — the reference is
explicit that "configuration files do not take effect until after the entire
configuration is loaded". A leftover `config.ghostty` does not cleanly override
this profile: it loses every key the included files set and wins every key they
do not. The installer retires it to `config.ghostty.retired-<stamp>`;
`verify.sh` fails if one reappears.

## SSH terminfo mesh

`TERM=xterm-ghostty` is meaningless to a host that has never seen Ghostty. Before
2026-08-18 neither M5 nor Mini knew it (`infocmp xterm-ghostty` exited 1 on both),
so every ssh out of a Ghostty window degraded silently.

`shell-integration-features = ssh-terminfo` installs it on first connect and
caches the host. The cache is per-machine:

```bash
ghostty +ssh-cache                      # what this machine has already set up
ghostty +ssh-cache --host=user@host     # is this one done?  (exit 1 = no)
ghostty +ssh-cache --add=user@host      # record a manual install
ghostty +ssh-cache --remove=user@host   # forget one
```

Cache targets are `user@hostname` **as `ssh -G <alias>` resolves them**, not the
alias you type. Check with `ssh -G mini | awk '/^user |^hostname /'`. An alias
that does not exist on that machine resolves to a literal, which caches a host
that cannot be reached — remove such entries rather than leaving them.

To install by hand (what the shell wrapper does internally):

```bash
infocmp -0 -x xterm-ghostty | ssh <host> 'tic -x -'
ssh <host> 'infocmp xterm-ghostty >/dev/null 2>&1; echo rc=$?'   # 0 = installed
```

The `tic` warning about "older tic versions may treat the description field as an
alias" is benign; judge by the `infocmp` exit code afterwards, not by the warning.

**The wrapper is a shell function.** It exists only in interactive shells that
loaded the shell integration. Ssh from a script, a cron job or an agent tool-call
shell and none of this runs — which is why the cache can sit empty on a machine
whose config has had `ssh-terminfo` enabled for a long time.

## Agent-team panes do not open in Ghostty

Claude Code hosts teammate panes in **tmux or iTerm2 only**. With
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` set (it is, in `~/.claude/settings.json`)
its backend registry resolves, in order:

- inside tmux (`$TMUX` set) → panes in the current tmux session
- inside iTerm2 → panes via the `it2` CLI, which additionally needs iTerm2's
  Python API enabled _and iTerm2 running_
- otherwise, tmux installed → an **external** tmux session you cannot see
- otherwise → `No pane backend available`

In a bare Ghostty window the third or fourth branch is taken. Observed live on
2026-08-18: subagent spawns failing with _"Failed to create iTerm2 split pane —
there was a problem connecting to iTerm2"_ while the operator was in Ghostty and
iTerm2 was not running.

**The fix is to run Claude Code inside tmux**, which makes the panes appear inside
the Ghostty window:

```bash
tmux new-session -s claude    # then start claude inside it
```

tmux is now present on all three: Pro 3.7b, M5 3.7b (installed 2026-08-18 —
until then the primary workstation had no backend at all), Mini 3.6a. Installing
the binary only makes the fix _available_; the panes appear only when Claude Code
is actually running **inside** a session, because the first branch tests `$TMUX`.

Work that does not need a pane is unaffected: background agents, the Workflow
tool, and MCP-hosted seats (for example the Codex second-opinion server) run as
subprocesses and were used successfully from Ghostty on the same day.

## Keys worth remembering

|                         |                                                                 |
| ----------------------- | --------------------------------------------------------------- |
| `cmd+shift+p`           | command palette (built-ins **plus** the Nuzantara entries)      |
| `cmd+f`                 | search the scrollback · `cmd+g` / `shift+cmd+g` next / previous |
| `cmd+up` / `cmd+down`   | jump to the previous / next **shell prompt**                    |
| `cmd+d` / `cmd+shift+d` | split right / down · `cmd+alt+arrows` to move between           |
| `cmd+r` then arrows     | resize mode; `=` equalises, `esc` leaves                        |
| `cmd+shift+enter`       | zoom the current split                                          |
| `cmd+shift+s`           | dump the whole scrollback to a file and open it                 |
| `cmd+alt+p`             | pin the window on top · `cmd+alt+o` toggle transparency         |
| `cmd+alt+r`             | read-only mode (blocks input to a running job)                  |
| `cmd+alt+grave`         | quick terminal from anywhere (needs Accessibility)              |
| `cmd+shift+comma`       | reload the config                                               |

`global:` bindings need Ghostty in **System Settings → Privacy & Security →
Accessibility**. Without the grant the binding is silently inert — there is no
error, so verify by pressing it.

It is `cmd+alt+grave`, not `cmd+grave`: macOS already owns `cmd+grave` for
"Cycle Through Windows", and a `global:` bind "will always consume the input",
so binding it there breaks window cycling in every application on the machine.

Two things make this easy to get wrong:

- **`+show-config` silently drops keybind prefixes.** A `global:` bind prints as
  an ordinary one, so the command cannot tell you whether the bind is global.
  Only the file on disk knows. Grep `~/.config/ghostty/keys.ghostty`.
- **The grant is per machine and the check is not remotable.** Read it directly
  (read-only, no `tccutil` — resetting TCC is machine-wide, never a probe):

  ```bash
  sqlite3 "file:///Library/Application%20Support/com.apple.TCC/TCC.db?mode=ro" \
    "select client, auth_value from access where service='kTCCServiceAccessibility';" \
    | grep -i ghostty
  ```

  `…|2` means granted; no row means never granted. Measured 2026-08-18: **Pro
  granted**, **Mini no row** (headless server — the quick terminal is pointless
  there anyway), **M5 the query answers `authorization denied` over ssh**, because
  sshd on that host lacks Full Disk Access. That is CANNOT-VERIFY, not
  "not granted" — run it in a local M5 terminal to actually know.

## Recovery

Every install leaves `~/.config/ghostty/.backup-<stamp>/`. To go back:

```bash
cp ~/.config/ghostty/.backup-<stamp>/* ~/.config/ghostty/
```

For a one-machine tweak that must survive reinstalls, use
`~/.config/ghostty/local.ghostty` — loaded last, never installed, never in git.
It is included with a `?` prefix, so it is optional; but if it exists and is
**invalid**, the whole config fails to load. Validate after editing:

```bash
ghostty +validate-config; echo "rc=$?"
```
