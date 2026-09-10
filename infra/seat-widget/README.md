# Claude Seats — desk widget

Desktop widget for the six Claude seats: the 5h and the weekly usage of each, with their
resets. It lives at the desktop-icon level — under every app window, on every Space — so it is
there whenever the desktop is. ↻ re-measures; it also refreshes itself every 30 minutes.
Closed it is a small square (six seats, 5h usage); open it is the full table. Numbers come
from `scripts/claude_seat_quota.py --json` — the widget never reads a token and never talks
to the endpoint itself.

```bash
infra/seat-widget/build.sh                # Pro: measure locally (Keychain profiles live here)
infra/seat-widget/build.sh --remote pro   # M5 / Mini: measure over `ssh pro`
```

- App: `~/Applications/Claude Seats.app` (ad-hoc signed, local use). Drag it anywhere; the
  position is remembered. Right-click → Aggiorna / Riduci / Esci.
- Config: `~/Library/Application Support/Claude Seats/remote` — one host name, or absent for local.
- Log: `~/Library/Logs/SeatWidget.log` — one line per refresh (`ok 32s local seats=6 hidden=3`).
- Login item: System Settings → General → Login Items → add the app (GUI action, owner's call).

The script and `FLEET_TOPOLOGY.json` are copied into the bundle at build time; rebuild after
either changes. Colours: Claude orange card (`#D97757` → `#C96442`), white type, white bars
that turn ink once a window is at 85 % or more.
