# Claude Seats — desk widget

Desktop widget for the six Claude seats: the 5h and the weekly usage of each, with their
resets. It lives at the desktop-icon level — under every app window, on every Space — so it is
there whenever the desktop is. ↻ re-measures; it also refreshes itself every 15 minutes, and
the reset countdowns tick every minute in between. Closed it is a small square (six seats, 5h
usage); open it is the full table. Numbers come from `scripts/claude_seat_quota.py --json` —
the widget never reads a token and never talks to the endpoint itself.

```bash
infra/seat-widget/build.sh                # Pro: measure locally (Keychain profiles live here)
infra/seat-widget/build.sh --remote pro   # M5 / Mini: read Pro's report over `ssh pro`
```

- **Where the numbers come from.** On Pro the widget runs `--deep --publish --peers ""`: a cold
  Keychain read returns expired tokens (zero seats), and the publish writes
  `~/.claude/seat-quota.json`. A `--remote` widget reads that report (`--from-report
  --max-age 40`) and measures on the peer only when it is missing or stale, so two desks do
  not double the calls that trip the endpoint's rate limiter. A seat answered with a 429 keeps
  its previous numbers, dimmed, with the time they were taken.
- **Size.** Drag the grip in the bottom-right corner, pinch on the trackpad, or right-click →
  Più grande / Più piccolo / Dimensione normale (0.6×–2.5×, remembered). The card is redrawn
  at the new size, not stretched, so text stays sharp.
- **Position.** Drag it anywhere; the position is remembered and always clamped to the screen.
- **Autostart.** `build.sh` installs `~/Library/LaunchAgents/com.nuzantara.claude-seats.plist`
  (RunAtLoad, `KeepAlive.SuccessfulExit=false`): back after login, reboot or crash, but a
  right-click → Esci stays closed until the next login. `--no-autostart` removes it.
- App: `~/Applications/Claude Seats.app` (ad-hoc signed, local use).
- Config: `~/Library/Application Support/Claude Seats/remote` — one host name, or absent for local.
- Log: `~/Library/Logs/SeatWidget.log` — one line per refresh (`ok 32s local seats=6 hidden=3 carried=0`).

The script and `FLEET_TOPOLOGY.json` are copied into the bundle at build time; rebuild after
either changes. Builds with the Command Line Tools as well as Xcode (no SwiftUI macros are
used — the CLT on M5 ship no `SwiftUIMacros` plugin). Colours: Claude orange card
(`#D97757` → `#C96442`), white type, white bars that turn ink once a window is at 85 % or more.
