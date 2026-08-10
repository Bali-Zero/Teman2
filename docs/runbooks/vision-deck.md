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
- `https://nuzantara.tail461666.ts.net/deck/` → `127.0.0.1:18890` (`python3 -m http.server` over `infra/vision-deck/`) — **new, this pilot**
- `https://nuzantara.tail461666.ts.net/cinema/` → `127.0.0.1:18891` (`python3 -m http.server` over `~/vision-cinema/`) — **new, this pilot**
- `https://nuzantara.tail461666.ts.net/term/` → `127.0.0.1:7681` (`ttyd`) — **new, this pilot**

**Directory-serve confirmed NOT supported on this Mac** (proven live, not hypothetical): `tailscale serve --bg --set-path /deck <directory>` fails with
`error: failed apply web serve: Path serving is not supported on macOS due to sandbox restrictions.` —
the App Store / GUI-installed `tailscaled` variant on macOS cannot target a directory directly.
Every path here is `python -m http.server` fronted, always. Don't re-attempt directory-serve
expecting a different result without first switching to the open-source `tailscaled` distribution
(see the error message's own link, https://tailscale.com/kb/1065/macos-variants) — that switch is
out of scope for this pilot.

**Ports 18790/18791 are NOT free on Pro — do not reuse them.** The pilot's original design used
`18790`/`18791`; live on 2026-08-11 those turned out to be already bound by unrelated pre-existing
services (`18790` = `~/venvs/nlm-bridge` uvicorn NotebookLM bridge, `18791` =
`~/scripts/automap/automap_server.py`). Neither was touched. The pilot uses `18890`/`18891`
instead — always `lsof -i :<port>` before reusing/reassigning a port in this stack.

Verify the full live mount table any time with:

```bash
tailscale serve status
```

## tmux sessions

The two backing services that are plain processes (not `tailscale serve` targeting
a directory directly) run inside `tmux` so they survive the SSH/interactive session
that started them:

| tmux session                                                                | Command                                                                                            | Purpose                                   |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `vision-deck-srv` (always — directory-serve confirmed unsupported on macOS) | `python3 -m http.server 18890 --directory <vision-deck content path — see below> --bind 127.0.0.1` | Serves the deck HTML                      |
| `vision-cinema-srv`                                                         | `python3 -m http.server 18891 --directory /Users/nuzantara/vision-cinema --bind 127.0.0.1`         | Serves the editorial QA directory listing |
| `vision-term`                                                               | `ttyd -p 7681 --interface 127.0.0.1 -W zsh`                                                        | Terminal cockpit                          |

List them: `tmux ls`. Attach: `tmux attach -t <name>`. Kill one: `tmux kill-session -t <name>`.

## Content update path

- **Deck** (`/deck/`): `python -m http.server` reads from disk on every request, so editing
  `infra/vision-deck/index.html` and having it land in the directory `vision-deck-srv` actually
  points at is enough — no restart needed. **Known gap, live 2026-08-11**: at pilot-arm time the
  MAIN checkout's working tree (`/Users/nuzantara/nuzantara/infra/vision-deck/`) did not yet have
  the merged files on disk (checkout was behind `origin/main`, and per cicatrix #1 HOME-fork
  discipline an agent does not `git pull` the main checkout unilaterally) — `vision-deck-srv` was
  pointed at the **worktree** copy (`.worktrees/ops-avp-tailnet/infra/vision-deck/`) instead,
  verified byte-identical to `origin/main` at arm time. **This means the served deck will silently
  go stale relative to `origin/main` the moment anyone edits `infra/vision-deck/` on main without
  re-pointing `vision-deck-srv`** — check `tmux capture-pane -t vision-deck-srv -p` or the tmux
  command line (`ps -ef | grep http.server`) to see which directory is actually being served
  before assuming an edit went live. Re-pointing to the main checkout once it catches up is
  tracked as a PENDING-ARMS item, not yet done.
- **Cinema** (`/cinema/`): symlinks in `~/vision-cinema/` point at the live WR2/WR3 output
  roots (`apps/war-room/output/carousel/`, `apps/war-room/output/episode/`) — new carousels/
  episodes appear automatically, no re-arming needed.
- **Terminal** (`/term/`): live shell, nothing to update.

## Re-arm after reboot (Pro restarts / tmux sessions die)

`tailscale serve --bg` mounts persist across `tailscaled` restarts (they're stored in
tailscale's local state), but the **backing tmux sessions do not survive a full reboot**.
After a Pro reboot:

```bash
# 1. Recreate the deck HTTP server — point at wherever the current merged content
#    actually lives on disk (main checkout if it's caught up, otherwise a worktree —
#    see "Content update path" above); this example assumes the main checkout is current
tmux new -d -s vision-deck-srv "python3 -m http.server 18890 --directory /Users/nuzantara/nuzantara/infra/vision-deck --bind 127.0.0.1"

# 2. Recreate the cinema HTTP server
tmux new -d -s vision-cinema-srv "python3 -m http.server 18891 --directory /Users/nuzantara/vision-cinema --bind 127.0.0.1"

# 3. Recreate the terminal cockpit
tmux new -d -s vision-term "ttyd -p 7681 --interface 127.0.0.1 -W zsh"

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
