# wa-mirror — Bali Zero team WhatsApp → CRM bridge

**Status**: scaffolding 2026-05-13 (LEVA WA-Mirror, transparent multi-account)
**Runs on**: Mini-Pro2 (24/7 server)
**Language**: Node.js 22 + `@whiskeysockets/baileys`
**Data store**: PostgreSQL `nuzantara_rag` (tables `whatsapp_*`, migrations 173/175/177)

## Goal

Every one-to-one WhatsApp message on a configured **Bali Zero team member** account lands in `whatsapp_message_context` within a few seconds. CRM matches are linked to the client/practice timeline; unknown numbers are stored as `client_id=NULL` prospects/leads.

Today: team members (Surya, Adit, Sahira, Ari, Krisna, etc.) use **their personal WhatsApp numbers** to chat with clients. Conversations live only on their phones. Zero audit trail. Zero continuity when someone is on leave / leaves the company. Compliance gap on UU PDP 27/2022 record-keeping for KYC/visa workflows.

After this bridge: each team member's WhatsApp is registered as a **WhatsApp Web "Linked Device"** of the wa-mirror service. The service reads inbound + outbound messages, matches the counterpart phone against `clients.phone`, and writes the message to `whatsapp_message_context`. A match gets `client_id` plus best open `practice_id`; no match is still stored as a prospect/lead.

## What is NOT this bridge

- **NOT** a reply bot. Team members keep using WhatsApp normally. v1 captures the one-to-one message stream for audit/continuity and does not send messages.
- **NOT** a replacement for the Meta Cloud API at `backend/channels/whatsapp/` — that handles the official Bali Zero number `+62 821 31 07 363`. wa-mirror handles the **personal numbers** of the team in parallel.
- **NOT** a Meta API integration. Uses Baileys (reverse-engineered WhatsApp Web protocol). Operates within the standard "Linked Devices" surface — see "Risks" below.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Team member phones (Surya, Adit, etc.)                             │
│     │                                                                │
│     │  WhatsApp Web "Linked Device" QR scan                          │
│     ▼                                                                │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│  Mini-Pro2 — wa-mirror daemon (Node.js)                             │
│     │                                                                │
│     │  Baileys session manager (1 session per team member)           │
│     │     ├─ persistent auth state in apps/wa-mirror/sessions/<phone>│
│     │     ├─ message event handler                                   │
│     │     │     ├─ counterpart phone in clients?                     │
│     │     │     │     ├─ YES → write client_id/practice_id           │
│     │     │     │     └─ NO  → write client_id=NULL prospect row     │
│     │     │     ├─ media download queue → ~/wa-mirror-media/...      │
│     │     │     ├─ best-effort OCR for images/PDF if endpoint exists │
│     │     │     └─ EventBus emit `whatsapp_message_received`         │
│     │     └─ heartbeat → cell_pulse_observed                         │
│     │                                                                │
│     ▼                                                                │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│  Fly.io nuzantara-rag                                                │
│     │                                                                │
│     ├─ PG: whatsapp_message_context (existing, 14k rows) +          │
│     │       whatsapp_team_sessions (new, migration 173)              │
│     │                                                                │
│     ├─ FastAPI /api/wa/messages?practice_id=N                        │
│     │                                                                │
│     └─ kita.balizero.com practice timeline panel                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Privacy contract (transparent, NOT covert)

This is the **load-bearing onboarding contract**. Every team member receives this
in writing AND in person before scanning the QR code.

1. The bridge logs one-to-one WhatsApp conversations for configured Bali Zero
   team accounts. The counterpart phone is matched against the `clients` table:

   ```sql
   SELECT id FROM clients
   WHERE phone_normalized = $counterpart_phone_normalized
      OR whatsapp = $counterpart_phone_raw;
   ```

   No match → the message is stored with `client_id=NULL` and `practice_id=NULL`.
   These rows are prospects/leads and must not be dropped at capture time.

2. The bridge does NOT send messages on behalf of the team member. It is
   **read-only** with respect to outbound. (Phase 2 may add "send via dashboard"
   but is out of scope for v1.)

3. The team member can **disconnect at any time** by removing the linked
   device in WhatsApp → Settings → Linked Devices. The bridge session dies
   immediately. No data is exfiltrated post-disconnect.

4. The bridge stores neither contacts list nor group membership beyond what
   already exists in `whatsapp_contacts` (legacy export, 8548 rows).

5. Audit trail: every team member's bridge session writes a heartbeat row in
   `whatsapp_team_sessions` (new table) with `connected_at`, `last_seen_at`,
   `disconnected_at`. The team member can query their own session log.

6. The team member retains right of access + erasure per UU PDP 27/2022 art.
   16-17. Procedure: email zero@balizero.com → bridge session rotated, their
   historical mirror rows soft-deleted within 30 days.

## Risks

### Baileys ToS compliance (Meta)

Baileys is a reverse-engineered library of the WhatsApp Web protocol. It is
NOT an official Meta product. Meta ToS technically prohibits "automated
processing of WhatsApp messages" outside the Cloud API. In practice:

- Used by thousands of SE Asia businesses (Wati, Zoko, Chatfuel build on it)
- Risk: number ban if rate-limit exceeded or pattern detection triggers
- Mitigation: low rate-limit (read-only v1, no message sending), respect
  human-like timing, no bulk operations

If you prefer the safer-but-more-restrictive Meta Cloud API path: each team
member needs to register their personal number as a Business API number,
which costs $0.005/message and **removes WhatsApp from their phone**. They
would need to use a separate "WhatsApp Business" app. Not what we want.

### Single point of failure

All team conversations flow through Mini-Pro2. If Mini goes down, conversations
keep happening on phones (WhatsApp works normally) but the CRM mirror has a
gap. After Mini recovery the bridge does NOT backfill missed messages —
they only exist on team member phones. This is by design (no historical
sweep). For v1 acceptable. v2 may add a "manual export + import" tool.

### Phone number changes

If a team member changes phone number, their bridge session breaks. They must
re-onboard with the new number. Their historical messages remain linked to
the OLD `whatsapp_team_sessions` row.

## Deploy plan

| Step | Owner | ETA |
|---|---|---|
| 1. Migration 173 (whatsapp_team_sessions + index extensions) | claude | 30min |
| 2. Baileys Node.js daemon scaffolding | claude | 4h |
| 3. Deploy on Mini-Pro2 (launchd plist + secrets) | claude | 1h |
| 4. Onboard Antonello first (validation) | claude+ant | 10min |
| 5. Onboard Adit (trusted second user) | ant+adit | 15min |
| 6. Onboard Surya | ant+surya | 15min |
| 7. Onboard rest of team | ant + each | 30min × 8 = 4h spread over 2 days |
| 8. FastAPI router /api/wa/messages | claude | 2h |
| 9. kita.balizero.com practice timeline panel | claude | 3h |

## Integration with existing code

- **Reuses**: `whatsapp_contacts` + `whatsapp_message_context` tables (no
  rebuild, append rows)
- **Extends**: migration 177 adds `client_id`, `practice_id`,
  `team_member_phone`, `counterpart_phone`, body/media/OCR columns, raw Baileys
  JSON, and the `baileys_message_id` dedup index.
- **Hooks into**: existing EventBus (PG NOTIFY) on channel
  `whatsapp_message_received`
- **CRM**: timeline rendering reuses existing practice timeline panel,
  conditional on `client_id` match

## Files

```
apps/wa-mirror/
├── README.md                    (this file)
├── package.json                 (Node deps: baileys, pg, dotenv)
├── tsconfig.json
├── bridge/
│   ├── index.ts                 (entry, session orchestrator)
│   ├── session.ts               (1 Baileys connection per team member)
│   ├── filters.ts               (JID helpers and match classifier)
│   ├── media.ts                 (async media download + OCR trigger)
│   ├── message_capture.ts       (Baileys payload → DB row)
│   ├── phone.ts                 (E.164 normalization)
│   ├── pg.ts                    (Postgres pool wrapper)
│   ├── telegram.ts              (owner alerts)
│   ├── events.ts                (EventBus PG NOTIFY emit)
│   └── heartbeat.ts             (write whatsapp_team_sessions)
├── docs/
│   ├── PRIVACY_CONTRACT_TEAM.md (signed by each team member)
│   └── PKWT_CLAUSE.md           (1-line for employment contract)
└── scripts/
    ├── onboard.ts               (QR code flow for new team member)
    └── status.ts                (list active sessions)
```
