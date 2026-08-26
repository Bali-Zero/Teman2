# Team ladder, rung 1 — already satisfied by construction; only the proof is missing

Rung 1 of the team-bot ignition ladder reads: _"Ingress/audit only: proves the webhook
receives, HMAC-verifies, and durably logs real Meta traffic with zero model/tool
involvement — the lowest-risk 'is the pipe connected' proof."_

**Nothing needs to be built for it.** This was measured on 2026-08-26 while scoping a lane to
build a team-bot audit store. The lane was not dispatched, because the store already exists and
already covers the team number.

## Why it is already satisfied

The team number shares one Meta app with the public client number, therefore one webhook. In
`app/routers/whatsapp_chat.py`:

1. **HMAC** is verified at the endpoint, before anything else — unchanged, pre-existing.
2. **Ack-first persistence** (`~line 1678`, comment "Persist the verified payload BEFORE any
   business processing so a Fly machine crash mid-flight does not lose the webhook") loops over
   _every_ change with `field == "messages"` and persists _every_ message carrying an id to
   `inbound_webhooks`, dedup-keyed on Meta's own `message_id`. **It does not filter by
   `phone_number_id`.**
3. Only _afterwards_ (`~line 1755`) does B3b's team branch recognise the team pnid and divert
   it — with `TEAM_BOT_INGRESS_ENABLED` off, it logs and drops without reaching client logic.

So a staff message on the team number is durably stored, HMAC-verified, and touches no model
and no tool — which is rung 1's whole claim. Building a second audit table would have
duplicated a working one; this is why the reuse question gets asked before the build question.

## What IS missing: one real message

The number has never received one (0 messages ever, per WhatsApp Manager). Rung 1 says "real
Meta traffic", and a synthetic signed payload proves the code path, not the pipe. The only
action that closes it is **the owner sending one WhatsApp message to the team number** — which
he already offered to do as the ladder's guinea pig.

## The proof query, ready to run the moment that message lands

Read-only. Deliberately selects **no payload body** — Law 2: the proof needs the row to exist
and to be attributable, not its content.

```sql
SELECT id,
       channel,
       created_at,
       processed_at IS NOT NULL           AS processed,
       payload #>> '{entry,0,changes,0,value,metadata,phone_number_id}' AS pnid
FROM inbound_webhooks
WHERE channel = 'whatsapp'
  AND payload #>> '{entry,0,changes,0,value,metadata,phone_number_id}'
      = '1188469837692575'
ORDER BY created_at DESC
LIMIT 5;
```

Run it with `bash scripts/pg.sh -A -t -c "<query>"`.

**Rung 1 passes when**: at least one row comes back with the team `pnid`, AND the daemon/brain
logs show no model or tool call for it. A row with the team pnid that ALSO produced a client
reply would be a rung-1 FAILURE, not a partial pass — it would mean the divert did not hold.

## What this does not prove

That the team bot does anything. Rung 2 (shadow intent/tool selection) is the first rung that
involves a model at all, and it is downstream of B3's real handler replacing the drop-stub.
