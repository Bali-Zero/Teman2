# Vision Deck — spatial control room for Apple Vision Pro

- **Status**: pilot (P1 deck + P2 dev cockpit + cinema editorial QA), Zero-approved 2026-08-11
- **Machine**: Pro only (Mini was SSH-unreachable at build time — see PENDING-ARMS)
- **Owner**: session (build+arm), Zero (adoption of durable LaunchAgent)
- **Source study**: `research/operations/2026-08-11-apple-vision-pro-tailnet-leverage.md`

## What this is

A tailnet-only spatial home screen for the Apple Vision Pro (node `apple-vision-pro`,
`100.97.28.18`). Three surfaces, all served from Pro, all reachable **only** inside
Zero's tailnet (`tail461666.ts.net`) — never on the public internet:

| Path       | What                                                                                        | Backing                                               |
| ---------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `/deck/`   | The Vision Deck itself — static HTML launcher linking every ops surface + cinema + terminal | Static file(s) in `infra/vision-deck/`                |
| `/cinema/` | Editorial QA — WR2 carousel PNGs + WR3 episode MP4s at wall scale                           | Directory listing over symlinks in `~/vision-cinema/` |
| `/term/`   | Full shell on Pro (`zsh`, `claude` CLI reachable)                                           | `ttyd`                                                |

## What is mounted where (DO NOT TOUCH the pre-existing two)

`tailscale serve` on Pro carries these mounts. The first two existed before this
pilot and are **out of scope** — never edit, remove, or re-map them from this
runbook or any vision-deck automation:

- `https://nuzantara.tail461666.ts.net/` → `127.0.0.1:18789` (OpenClaw Control) — **pre-existing, untouched**
- Public Funnel `:8443` → `127.0.0.1:8789` (FastAPI) — **pre-existing, untouched, PUBLIC — never confuse with the tailnet-only paths below**
- `https://nuzantara.tail461666.ts.net/deck/` → static `infra/vision-deck/` (directly, or via a local HTTP server on `18790` if `tailscale serve --set-path` cannot target a directory) — **new, this pilot**
- `https://nuzantara.tail461666.ts.net/cinema/` → `127.0.0.1:18791` (`python3 -m http.server` over `~/vision-cinema/`) — **new, this pilot**
- `https://nuzantara.tail461666.ts.net/term/` → `127.0.0.1:7681` (`ttyd`) — **new, this pilot**

Verify the full live mount table any time with:

```bash
tailscale serve status
```

## tmux sessions

The two backing services that are plain processes (not `tailscale serve` targeting
a directory directly) run inside `tmux` so they survive the SSH/interactive session
that started them:

| tmux session                                            | Command                                                                                                  | Purpose                                   |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `vision-deck-srv` (only if directory-serve unsupported) | `python3 -m http.server 18790 --directory /Users/nuzantara/nuzantara/infra/vision-deck --bind 127.0.0.1` | Serves the deck HTML                      |
| `vision-cinema-srv`                                     | `python3 -m http.server 18791 --directory /Users/nuzantara/vision-cinema --bind 127.0.0.1`               | Serves the editorial QA directory listing |
| `vision-term`                                           | `ttyd -p 7681 --interface 127.0.0.1 -W zsh`                                                              | Terminal cockpit                          |

List them: `tmux ls`. Attach: `tmux attach -t <name>`. Kill one: `tmux kill-session -t <name>`.

## Content update path

- **Deck** (`/deck/`): if `tailscale serve --set-path` targets the directory directly,
  editing `infra/vision-deck/index.html` on **main** (after merge) updates the deck live —
  no restart needed, it's a static file read on each request. If instead a
  `python -m http.server` is fronting it, same story (it reads from disk on each request) —
  just make sure the merged commit landed in `/Users/nuzantara/nuzantara` (the main checkout,
  not a worktree — cicatrix #1 HOME-fork discipline).
- **Cinema** (`/cinema/`): symlinks in `~/vision-cinema/` point at the live WR2/WR3 output
  roots (`apps/war-room/output/carousel/`, `apps/war-room/output/episode/`) — new carousels/
  episodes appear automatically, no re-arming needed.
- **Terminal** (`/term/`): live shell, nothing to update.

## Re-arm after reboot (Pro restarts / tmux sessions die)

`tailscale serve --bg` mounts persist across `tailscaled` restarts (they're stored in
tailscale's local state), but the **backing tmux sessions do not survive a full reboot**.
After a Pro reboot:

```bash
# 1. Recreate the cinema HTTP server
tmux new -d -s vision-cinema-srv "python3 -m http.server 18791 --directory /Users/nuzantara/vision-cinema --bind 127.0.0.1"

# 2. Recreate the terminal cockpit
tmux new -d -s vision-term "ttyd -p 7681 --interface 127.0.0.1 -W zsh"

# 3. (only if deck needed its own http.server — check `tailscale serve status` first)
tmux new -d -s vision-deck-srv "python3 -m http.server 18790 --directory /Users/nuzantara/nuzantara/infra/vision-deck --bind 127.0.0.1"

# 4. Re-verify all serve mounts are intact (should already be, tailscale persists them)
tailscale serve status
```

**Durable fix pending**: this pilot ships on raw `tmux`, not a `launchd` LaunchAgent —
see PENDING-ARMS entry (a). A LaunchAgent would survive reboot without the manual
re-arm above. Not shipped in this pilot pending Zero's adoption decision (KeepAlive
misconfig is cicatrix family #7 — any LaunchAgent here needs a real blocking loop or
`StartInterval`, never bare `KeepAlive=true` around a one-shot `python -m http.server`).

## Kill switches

Disable one surface without touching the others:

```bash
tailscale serve --https=443 --set-path /deck off
tailscale serve --https=443 --set-path /cinema off
tailscale serve --https=443 --set-path /term off
```

Kill the backing process (stops serving even if `tailscale serve` mount is left armed):

```bash
tmux kill-session -t vision-cinema-srv
tmux kill-session -t vision-term
tmux kill-session -t vision-deck-srv   # only if it exists
```

Full nuclear option (also removes `/` and `:8443` — **do not use for this pilot's
issues alone**, it takes down OpenClaw Control and the public Funnel too):

```bash
tailscale serve reset
```

## Security posture (declared, tracked in PENDING-ARMS)

- **Auth boundary = tailnet membership only.** The tailnet (`tail461666.ts.net`)
  contains only Zero's own devices. Tailnet-only `serve` (not `funnel`) is the
  auth boundary for this pilot — anyone who can join the tailnet can reach `/deck/`,
  `/cinema/`, `/term/` with zero additional login.
- **`ttyd` has no app-level authentication.** A full shell on Pro (`zsh`, reads the
  `claude` CLI, secrets in env) is reachable by anything on the tailnet with no
  password/basic-auth in front of it. This is a **known, declared gap** — the original
  P2 proposal in the source study called for basic-auth on top of tailnet identity;
  this pilot ships without it. Tracked in PENDING-ARMS entry (b) — hardening (basic-auth,
  or gate behind `tailscale serve`'s own auth if/when available) is pending a decision,
  not silently accepted as fine.
- **Cinema directory listing is read-only** (`python -m http.server` has no write path)
  and is symlink-scoped to editorial output only (WR2 carousel renders, WR3 episode
  renders) — never intake/CRM/client-document directories. See the boundary note in
  `~/vision-cinema/README.txt` if the symlinks could not be confidently placed.
- **Never use `tailscale funnel`** for any of these three paths — that would expose
  them to the public internet. This pilot is `serve`-only by design.

## Related PENDING-ARMS entries (see `.claude/skills/modus/PENDING-ARMS.md`)

- (a) tmux-based serving, not a durable LaunchAgent — adoption pending Zero.
- (b) `ttyd` has no app-level auth — hardening decision pending.
- (c) `PENDING-ALIGN:mini` — this cockpit was conceived for Mini (H24 server role)
  but landed on Pro because Mini's sshd was unreachable on 2026-08-11. Should be
  reconsidered once Mini connectivity is restored, per Mini's architecture role
  (workhorse/H24, Pro = interactive dev).
