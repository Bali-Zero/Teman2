# Claude Seats — desk widget

Floating panel (no Dock icon) showing, for each of the six Claude seats, the 5h and the
weekly usage with their resets. One button (↻) re-measures; it also refreshes itself
every 30 minutes. Numbers come from `scripts/claude_seat_quota.py --json` — the widget
never reads a token and never talks to the endpoint itself.

```bash
infra/seat-widget/build.sh                # Pro: measure locally (Keychain profiles live here)
infra/seat-widget/build.sh --remote pro   # M5 / Mini: measure over `ssh pro`
```

- App: `~/Applications/Claude Seats.app` (ad-hoc signed, local use). Close the panel to quit.
- Config: `~/Library/Application Support/Claude Seats/remote` — one host name, or absent for local.
- Log: `~/Library/Logs/SeatWidget.log` — one line per refresh (`ok 32s local seats=6 hidden=3`).
- Login item: System Settings → General → Login Items → add the app (GUI action, owner's call).

The script and `FLEET_TOPOLOGY.json` are copied into the bundle at build time; rebuild
after either changes. Colours follow the claude.ai palette (ivory card, clay accent, kraft →
clay → ember as a window fills).
