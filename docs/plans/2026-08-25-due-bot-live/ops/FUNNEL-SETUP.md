# FUNNEL-SETUP.md — team-bot ingress network setup (F9, lane B5)

> Companion to `KILL-SWITCHES.md` / `TRIPWIRES.md` (lane B7) and
> `ops/packets/FUNNEL-PIVOT-PACKET.template.md` (the recorded Kimi dissent —
> read that if evidence accumulates against Funnel in production).

## Topology (F9 §4.2, frozen)

```text
Mini (primary):
  local listener: http://127.0.0.1:8765/webhooks/team-wa   (apps/team-bot/, B3)
  public Funnel:  https://<mini-dnsname>.<tailnet>.ts.net/webhooks/team-wa

Pro (standby):
  local listener: http://127.0.0.1:8765/webhooks/team-wa   (apps/team-bot/, B3)
  public Funnel:  https://<pro-dnsname>.<tailnet>.ts.net/webhooks/team-wa
  + team-bot-failoverd (this lane) — the ONLY process that may issue a
    WABA callback override (`POST /{WABA-ID}/subscribed_apps`) to move
    Meta's traffic from Mini's URL to Pro's.
```

Both nodes run the SAME `apps/team-bot/` app and the SAME local Funnel
setup. Only Pro also runs `team-bot-failoverd`. There is no Tailscale-native
mechanism that makes the two nodes share one public hostname (research
capture §4.1) — failover is entirely the WABA callback-override mechanism
this lane built (`backend/services/team_bot_ingress/`), never a DNS or
Funnel-level trick.

## Operator steps, in order

1. **Deploy and start `apps/team-bot/` on Mini** (B3's deliverable). Confirm
   it answers locally: `curl http://127.0.0.1:8765/livez`.
2. **Run the Funnel provisioning script on Mini**:
   `bash scripts/provision_team_bot_funnel.sh`
   It REFUSES if step 1 isn't done yet (see the script's own safety-gate
   comment) — this is deliberate, not a bug to work around.
3. **Give Meta the printed URL** (`https://<mini-dnsname>.../webhooks/team-wa`)
   in the WhatsApp Business API webhook config — owner switchboard item 1
   (`operator[gui]`), this repo cannot do it for you.
4. **Repeat steps 1-2 on Pro** (same app deployed, same script run there too)
   — Pro's Funnel front must be LIVE and ready BEFORE it is ever needed,
   not provisioned reactively during an actual incident.
5. **Provision `team-bot-failoverd` on Pro**:
   `sudo bash scripts/provision_team_bot_failoverd.sh`
   Then fill every `__FILL_ME__` value in
   `/Users/team-bot-failoverd/.team-bot-failoverd.env` (0600, operator-only
   — secrets, never touched by this repo's own scripts after the
   placeholder is written) and bootstrap the LaunchDaemon per the script's
   own printed instructions.
6. **Leave `TEAM_BOT_FAILOVER_AUTO_ENABLED=false`.** The daemon runs the
   moment it's bootstrapped and logs SHADOW_WOULD_PROMOTE_BUT_DISABLED
   decisions — that is the F9 "shadow intent" promotion rung, and it is
   meant to run for a while, observed, before anyone flips the switch.
   Owner switchboard item 7 names the promotion order; this is step one of
   the team side of it.
7. **Before ever setting `TEAM_BOT_FAILOVER_AUTO_ENABLED=true`**: the
   staging-WABA drill F9 requires (a second, disposable WABA/test number)
   must pass — this repo's synthetic drill
   (`backend/tests/duebot/failover/test_staging_drill.py`) proves the
   DECISION LOGIC; it explicitly does NOT and CANNOT prove Meta's real
   retry semantics against a new callback. Both must pass before arming.
   A third precondition, orthogonal to both drills: the F6/F9 pending-action epoch gap in [F6-F9-PENDING-ACTION-EPOCH-GAP.md](F6-F9-PENDING-ACTION-EPOCH-GAP.md) must be resolved or explicitly waived by whoever rules on it — a PendingAction can currently outlive a takeover with no live epoch check.

## What this lane deliberately left for other lanes / the operator

- `apps/team-bot/`'s actual webhook route, HMAC verification, and durable
  insert — B3's file ownership (`apps/team-bot/` does not exist yet as of
  this writing).
- `ollama_reachable` / `replication_lag_ok` / `identity_snapshot_valid` in
  `failoverd.py`'s self-prechecks — hardcoded `False` today with a loud
  startup warning (B4/B3's substance; see the function's own docstring).
- The Meta system-user token itself, and Meta webhook configuration — both
  operator[gui]/[credential], owner switchboard items 1 and 4.
