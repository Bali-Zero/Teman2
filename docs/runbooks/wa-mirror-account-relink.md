# Runbook — wa-mirror account re-link (QR)

> **Human-in-the-loop. NOT automatable.** A WhatsApp companion-device link can
> only be (re)created by scanning a QR with the account holder's physical phone.
> This runbook covers the three accounts that need a manual re-link as of
> 2026-06-09 (**sahira**, **vino**, **ari**) and the general procedure for any
> future logout.

## When you need this

A team WhatsApp bridge (`wa-mirror`, the Baileys engine that mirrors a team
member's personal/business line into intake) stops connecting and its log shows
a **terminal logout** rather than a transient disconnect:

- `Connection Failure → code:401 reason:"logged_out" terminal:true` — the linked
  device was removed **server-side** (the member unlinked it, the phone was
  offline > 14 days, or WhatsApp's anti-automation flagged it). Retrying in code
  is futile; only a fresh QR scan fixes it. (W67b)
- `no session yet` / no persisted `auth_info` — the account was never linked, or
  the session dir was wiped.

A bridge that is merely *disconnected* (network blip) reconnects on its own and
does **not** need this — see the W67/W67b scar. Disambiguate by reading the
account log, never by `status.sh` alone (it reports process-alive, **not**
WhatsApp-connected). The ghost-row janitor
(`com.nuzantara.wa-mirror-session-janitor`, PR #1209) marks dead rows
`disconnected` automatically so a re-link starts clean.

## Accounts needing re-link (2026-06-09)

| Name   | E.164          | QR file (after `--qr`)            | Status / reason                         |
|--------|----------------|----------------------------------|-----------------------------------------|
| sahira | +628213454723  | `/tmp/qr-628213454723.png`       | `loggedOut` 401 — device removed phone-side |
| vino   | +628213454727  | `/tmp/qr-628213454727.png`       | no persisted session                    |
| ari    | +628213454721  | `/tmp/qr-628213454721.png`       | no persisted session (orphan — confirm with operator it should be supervised) |

> **Note on ari/vino**: per the W67c scar these numbers are sequential Bali Zero
> lines that may NOT be in `WA_MIRROR_SUPERVISED_NAMES`. Confirm with the
> operator that the account *should* run before re-linking; do not link an
> account that has been dismissed.

## Procedure (per account)

Run **on the Pro** (the bridges live there; Mini's legacy monolithic instance
was disabled in W67c). You need the account holder's phone next to you.

1. **Force a fresh QR** (wipes the stale session, kills any running process):

   ```bash
   ssh pro
   bash ~/scripts/wa-mirror-launcher/start-one.sh <name> --qr
   ```

   Replace `<name>` with `sahira` / `vino` / `ari` (lowercase). The script:
   - kills any existing bridge for that employee,
   - `rm -rf` the session dir (forces a fresh scan),
   - spawns the bridge and waits up to ~15s for the QR.

2. **Open the QR** when the script prints `📱 QR ready`:

   ```bash
   open /tmp/qr-<digits>.png      # e.g. open /tmp/qr-628213454723.png
   ```

   (If you are on M5 / not at the Pro's screen: `scp pro:/tmp/qr-<digits>.png .`
   then open it locally, or have the operator at the Pro open it.)

3. **Scan on the phone** within ~20 seconds — on the account holder's device:

   **WhatsApp (Business) → Settings → Linked Devices → Link a Device** → point
   the camera at the QR.

4. **Confirm connection**. The script tails the log; success prints
   `✅ wa-mirror session connected`. If it times out, the QR expired — re-run
   step 1 (a new QR is generated each attempt).

5. **Verify it stays up** (W67b keepalive — the process must remain alive across
   a supervisor cycle, not just connect once):

   ```bash
   tail -n 20 /tmp/wa-mirror-logs/<name>.log
   # look for: "wa-mirror session connected" and NO subsequent "SIGTERM"/"401"
   pgrep -fl -- "--employee=<name>"   # process should persist > 1 min
   ```

## After re-link

- The supervisor (`com.balizero.wa-mirror-launcher` → `supervise-launcher.sh`,
  W67) keeps the bridge alive; `start-all.sh`'s pidfile guard will now log
  `⏭️ already running` for that account and not relaunch it.
- The session janitor leaves a live, fresh row alone (double condition: dead
  process **AND** stale `last_seen_at`).
- Incoming media on that line flows into intake via
  `wa_mirror_intake_sweeper.py` (new arrivals) — nothing else to do.

## Gotchas

- **Re-link does not prevent the next logout.** WhatsApp drops a companion device
  if the phone is offline > 14 days. To reduce QR frequency the member's phone
  must come online at least once every ~14 days. Not software-fixable. (W67b)
- **One QR per attempt, ~20s TTL.** Don't pre-open an old `/tmp/qr-*.png` — it's
  stale. Always re-run `--qr` and scan the freshly printed file.
- **`status.sh` 🟢 RUNNING ≠ connected.** It means the Node process is alive, not
  that WhatsApp accepted the session. Always read the per-account log for
  `session connected` vs `401 logged_out`. (W67c / ghost-session scar)
- **Wrong machine.** Bridges run on the **Pro** only. If you still see
  `reconnect_attempt=N` Telegram spam after fixing the Pro, check Mini for a
  stray legacy `com.balizero.wa-mirror` job (should be disabled per W67c).
- **Ghost row.** If a re-link fails with a unique-constraint error on
  `whatsapp_team_sessions`, a dead `connected`/`pending` row is blocking it — the
  janitor clears it within ~5 min, or run it once manually:
  `python3 ~/Desktop/nuzantara/scripts/wa_mirror_session_janitor.py`.

## References

- Scars: W67 (supervisor crash-loop), W67b (loggedOut retry-stop + keepalive),
  W67c (Mini active-active orphan), ghost-session crash-loop (2026-06-09).
- Scripts: `~/scripts/wa-mirror-launcher/{start-one,start-all,supervise-launcher}.sh`,
  `scripts/wa_mirror_session_janitor.py` (PR #1209),
  `scripts/wa_mirror_intake_sweeper.py`.
- LaunchAgents: `com.balizero.wa-mirror-launcher`,
  `com.nuzantara.wa-mirror-session-janitor`.
