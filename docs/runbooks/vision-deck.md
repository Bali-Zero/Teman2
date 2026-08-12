# Vision Deck — spatial control room for Apple Vision Pro

- **Status**: reboot-durable (P1 deck + P2 dev cockpit + cinema editorial QA), Zero-approved 2026-08-11, durability shipped 2026-08-12
- **Machine**: Pro only (Mini was SSH-unreachable at build time — see PENDING-ARMS)
- **Owner**: session (build+arm+durability)
- **Source study**: `research/operations/2026-08-11-apple-vision-pro-tailnet-leverage.md`

**2026-08-12 update**: the pilot originally shipped on raw `tmux` sessions, which died on a
Pro reboot overnight (confirmed live, not hypothetical — the session found all three tmux
sessions gone and manually restarted them). Replaced with three user LaunchAgents (see
"Backing services" below) — this is the durable fix the original PENDING-ARMS row called for.
The deck HTTP server was also re-pointed from the (reap-eligible, merged-PR) worktree to the
main checkout path — both PENDING-ARMS rows from 2026-08-11 are now closed.

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

## Backing services — user LaunchAgents (reboot-durable, shipped 2026-08-12)

The three backing processes each run as a **user LaunchAgent** in `~/Library/LaunchAgents/`,
loaded under `gui/$(id -u)` so they start automatically at every GUI login — no manual
re-arm needed after a reboot:

| Plist                               | Command                                                                                                                    | Purpose                                   |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `com.nuzantara.vision-deck.plist`   | `/opt/homebrew/bin/python3 -m http.server 18890 --directory /Users/nuzantara/nuzantara/infra/vision-deck --bind 127.0.0.1` | Serves the deck HTML (main checkout path) |
| `com.nuzantara.vision-cinema.plist` | `/opt/homebrew/bin/python3 -m http.server 18891 --directory /Users/nuzantara/vision-cinema --bind 127.0.0.1`               | Serves the editorial QA directory listing |
| `com.nuzantara.vision-term.plist`   | `/opt/homebrew/bin/ttyd -p 7681 --interface 127.0.0.1 -W zsh`                                                              | Terminal cockpit                          |

All three: `RunAtLoad=true`, `KeepAlive=true`, logs at `~/Library/Logs/vision-<name>.log`,
`PATH` env includes `/opt/homebrew/bin:/usr/bin:/bin`. `KeepAlive=true` is **correct** here
per cicatrix family #7 (daemon-vs-cron KeepAlive misconfig) precisely because all three are
long-running blocking servers (`http.server`, `ttyd`) that never exit on their own — the
family-#7 failure mode is `KeepAlive=true` wrapping a **one-shot** payload, which this is not.

List/inspect: `launchctl list | grep vision`. Manual restart of one: `launchctl kickstart -k
gui/$(id -u)/com.nuzantara.vision-<name>`. (This is also the standard reboot-survival proof —
`kickstart -k` simulates the process dying; a LaunchAgent with `KeepAlive=true` relaunches it
immediately, the same mechanism that fires after a real reboot once the plist is loaded at
login.)

**Predecessor (retired 2026-08-12)**: this pilot originally shipped on raw `tmux` sessions
(`vision-deck-srv`/`vision-cinema-srv`/`vision-term`), which do **not** survive a reboot —
confirmed live when all three died overnight and had to be manually restarted. If `tmux ls`
ever shows these names again, that's a regression back to the fragile predecessor, not a
legitimate alternate backing.

## Content update path

- **Deck** (`/deck/`): `python -m http.server` reads from disk on every request, so editing
  `infra/vision-deck/index.html` on the **main checkout**
  (`/Users/nuzantara/nuzantara/infra/vision-deck/`) is enough — no restart needed. As of
  2026-08-12 the LaunchAgent serves from the main checkout path directly (not a worktree), so
  this is the single canonical update path: edit the repo, merge to `origin/main`, and once the
  main checkout picks up the change (whenever it's next pulled — this pilot does not auto-pull
  it, per cicatrix #1 HOME-fork discipline) the served content updates on the next request with
  zero re-arm. If the main checkout ever falls behind `origin/main` on `infra/vision-deck/`
  specifically, the deck will serve stale content until the checkout catches up — check
  `git -C /Users/nuzantara/nuzantara diff origin/main -- infra/vision-deck/` to see if that's
  happening.
- **Cinema** (`/cinema/`): symlinks in `~/vision-cinema/` point at the live WR2/WR3 output
  roots (`apps/war-room/output/carousel/`, `apps/war-room/output/episode/`) — new carousels/
  episodes appear automatically, no re-arming needed.
- **Terminal** (`/term/`): live shell, nothing to update.

## Re-arm after reboot

Nothing to do — the LaunchAgents load automatically at GUI login (that is the entire point
of the 2026-08-12 durability fix). To verify after a reboot:

```bash
launchctl list | grep vision                        # all three should show a PID, not "-"
tailscale serve status                               # mounts persist independently, should already be intact
curl -sk https://nuzantara.tail461666.ts.net/deck/ | head -c 60
curl -sk https://nuzantara.tail461666.ts.net/cinema/ | head -c 60
curl -sk https://nuzantara.tail461666.ts.net/term/ | head -c 60
```

If any LaunchAgent is missing from `launchctl list` (e.g. the plist was removed, or
`gui/$(id -u)` bootstrap didn't fire at login), reload it manually:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.vision-<name>.plist
```

## Kill switches

Disable one surface without touching the others:

```bash
tailscale serve --https=443 --set-path /deck off
tailscale serve --https=443 --set-path /cinema off
tailscale serve --https=443 --set-path /term off
```

Kill the backing LaunchAgent (stops serving even if `tailscale serve` mount is left armed).
`bootout` unloads it until the next login/manual bootstrap; add `disable` to also prevent
`RunAtLoad` from bringing it back at the next login:

```bash
launchctl bootout gui/$(id -u)/com.nuzantara.vision-deck
launchctl bootout gui/$(id -u)/com.nuzantara.vision-cinema
launchctl bootout gui/$(id -u)/com.nuzantara.vision-term

# to also prevent RunAtLoad from reviving it at next login:
launchctl disable gui/$(id -u)/com.nuzantara.vision-<name>
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

- (a) **CLOSED 2026-08-12** — tmux-based serving replaced by three user LaunchAgents
  (`com.nuzantara.vision-{deck,cinema,term}.plist`); resurrection proven live via
  `launchctl kickstart -k`.
- (b) `ttyd` has no app-level auth — hardening decision pending (still open, unaffected
  by the durability work above).
- (c) `PENDING-ALIGN:mini` — this cockpit was conceived for Mini (H24 server role)
  but landed on Pro because Mini's sshd was unreachable on 2026-08-11. Should be
  reconsidered once Mini connectivity is restored, per Mini's architecture role
  (workhorse/H24, Pro = interactive dev). Still open, unaffected by the durability
  work above.
- **CLOSED 2026-08-12** — the separate worktree-reap risk for `vision-deck-srv` (it was
  serving `infra/vision-deck/` from `.worktrees/ops-avp-tailnet/`, a worktree whose PR
  #4022 was already merged and therefore reap-eligible) is also closed: the deck
  LaunchAgent now serves from the main checkout path
  (`/Users/nuzantara/nuzantara/infra/vision-deck/`), which both files were confirmed
  present on and byte-identical to at cutover time — no HOME-fork copy was needed.
