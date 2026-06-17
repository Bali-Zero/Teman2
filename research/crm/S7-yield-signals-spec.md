---
date: 2026-06-02
domain: crm
client_case: false
sources:
  - postgres nuzantara_rag (read-only role nuzantara_readonly)
  - ~/.claude/agents/yield-optimizer.md (existing weekly agent)
  - client_expiry_alerts_view, clients, practices, whatsapp_contacts, client_segments
---

# S7 — CRM Yield Signals Spec (revenue-signal extension of `yield-optimizer`)

Extends the existing **`yield-optimizer`** agent (weekly, Sunday 04:00 WITA) with a
concrete, schema-accurate set of revenue signals over the **1,450 actionable
clients** (the non-deleted slice of the 11,702 gross rows). The original agent
referenced a `crm_clients` table and columns (`engagement_score`,
`total_spend_ytd`, `kitap_expiry_date`) that **do not exist** in production. This
spec maps each opportunity rule to the **real** schema and to a reproducible SQL
query (implemented in `scripts/s7_yield_draft_local.py`).

## Privacy contract (HARD — UU PDP / SYMBIOSIS Law 2)

- Segment **counts and team-owner routing** are public/aggregate → live in
  `research/crm/S7-yield-FROZEN.json` (committed).
- Per-client **PII** (names, expiry dates, contact) is read by a **read-only**
  Postgres role and drafted **only by local Ollama `qwen3.5:9b`**. Drafts land in
  the gitignored local staging dir `~/.nuzantara-staging/s7-yield/`. **Never**
  committed, **never** sent to a cloud LLM, **never** printed to stdout (logs
  carry `client_id` only).
- **Nothing is sent.** Drafts are for the ops team to review and send manually
  (SYMBIOSIS Law 5).

## Data-coverage caveats (drive the rule design)

| Field | Coverage | Consequence |
|---|---|---|
| `clients.last_interaction_date` | 338 / 1450 | Recency is partial; S4 treats NULL as "no recent contact". |
| `client_preferences.language` | 2 / 1450 | Draft language **inferred from `nationality`**. |
| `practices` date span | 2026-01-21 .. 2026-06-01 (~4.5mo) | **No practice-age dormancy exists** → classic "dormant 6mo+" segment = 0 (real, not a bug). |
| `practices.next_renewal_date` / `expiry_date` due ≤90d | 0 rows | Renewal pipeline driven by **`client_expiry_alerts_view`**, not by practices. |

## Revenue segments (canonical)

All counts are **distinct clients**, `deleted_at IS NULL`, as of 2026-06-02.

| ID | Signal | Trigger (real schema) | Clients | Priority | Pitch |
|----|--------|-----------------------|--------:|----------|-------|
| **S1** | Renewal pipeline | `client_expiry_alerts_view`: visa/kitas/e-visa expiring `0..90d` | **61** | P0 | Renewal + KITAP eligibility check |
| **S2** | Expired win-back | same view, `days_until_expiry < 0` | **67** | P0 | Re-activate before penalties |
| **S3** | Passport pre-block | same view, `document_type='passport'`, `0..180d` | **9** | P2 | Early passport renewal |
| **S4** | Active, no-contact | `status='active'` AND `last_interaction_date` NULL or `< now()-120d` | **403** | P1 | Check-in / needs discovery |
| **S5** | Corporate expansion | (`npwp` OR `nib` not null) AND **no practice** | **286** | P1 | Monthly tax & compliance retainer |
| **S6** | WhatsApp-warm | linked WA contact `last_message_at < 60d` AND no practice | **30** | P1 | Convert enquiry → service plan |
| **S7** | Unconverted leads | `status IN (prospect,lead)` AND no practice | **712** | P3 | Nurture funnel (NOT weekly 1:1) |
| **S8** | Repeat buyers | `>=2` paid practices | **47** | P2 | Priority/retainer upsell |

**Replaces** the old agent's R1–R6 (KITAS, KITAP-eligible, business-pivot,
tax-expansion, dormant-high-value, engagement-spike). Mapping: R1→S1, R5→(S2+S4),
R4→S5, R6→S6/S8; R2/R3 deferred (no `kitap_expiry_date` / SHGB columns yet).

## Weekly execution (cap 20/week, ops bandwidth)

Priority order: **S1 → S2 → S6 → S5 → S8 → S4 → S3**. S7 (712 leads) is a
top-of-funnel **nurture** concern, excluded from weekly 1:1 drafting.

```bash
# PII-safe local drafting (Pro only; Ollama must be up — no cloud fallback)
python scripts/s7_yield_draft_local.py --segment S1 --limit 20   # one segment
python scripts/s7_yield_draft_local.py --all --limit 5           # spread across all
python scripts/s7_yield_draft_local.py --segment S1 --dry-run    # list only, no Ollama
```

Drafts: `~/.nuzantara-staging/s7-yield/<SEG>-<ts>-drafts.md` (40–80 words, no
emoji, no buzzwords, language per nationality). Pilot 2026-06-02 produced S1
(54/65/57 words) and S5 (65/57/57 words) — all in-spec.

## Owner routing (S1 renewal + S4 re-engagement)

S1 (doc-level): ari.firda 28 · surya 12 · adit 10 · krisna 9 · sahira 5 · vino 2 · damar 1.
S4 (client-level): krisna 76 · adit 68 · ari.firda 59 · vino 49 · sahira 37 · damar 32 · surya 30 · dea 24 · (unassigned 18) · ruslana 8.

## Failure modes

- **Ollama down** → STOP, no cloud fallback (privacy). Script exits non-zero.
- **DB unreachable** → STOP (read-only role via pg-proxy 15432).
- **Draft out of spec** (length/language) → ops re-prompts or skips that row.

## Reference

- FROZEN aggregates: `research/crm/S7-yield-FROZEN.json`
- Drafter + canonical SQL: `scripts/s7_yield_draft_local.py`
- Existing agent: `~/.claude/agents/yield-optimizer.md` (column refs corrected to match this spec)
