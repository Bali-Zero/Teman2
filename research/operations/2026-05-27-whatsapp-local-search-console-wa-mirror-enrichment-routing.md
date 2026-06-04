---
date: 2026-05-27
domain: operations
client_case: whatsapp-local-search-console-wa-mirror-enrichment-routing
status: implementation-design
privacy: local-only-raw-whatsapp
---

# WhatsApp Local Search Console, wa-mirror, Enrichment, Routing

## Executive Decision

The WhatsApp corpus should become a local operational intelligence layer, not a
one-off research dump.

The architecture is:

1. `wa-mirror` captures live team WhatsApp messages and writes identity-rich
   rows into `whatsapp_message_context`.
2. The local WhatsApp Search Console reads two sources:
   - live/backfilled Postgres rows from `whatsapp_message_context`;
   - historical export rows from `research/personal/wa-corpus/full/*.local.sqlite`.
3. The identity resolver links messages to `client_id`, `practice_id`,
   `conversation_id`, `team_member_id`, and a confidence score.
4. Local extraction converts messages into structured facts, without uploading
   raw text to cloud LLMs.
5. Only derived facts, local references, hashes, confidence, and action records
   are channelled into internal CRM/workspace surfaces.

Raw WhatsApp text remains local. `my.balizero.com` must not expose raw WhatsApp
messages, source files, internal evidence payloads, or local search indexes.

## Verified Current Inputs

The full local corpus pipeline already exists and produced these verified
aggregate outputs:

| Item | Verified value |
|---|---:|
| Parsed messages | 162,162 |
| Total body characters | 12,052,705 |
| Files with messages | 699 |
| Non-quarantined mined signal hits | 62,309 |
| Messages with at least one mined signal | 42,735 |
| Files with at least one mined signal | 605 |

The live/backfill schema already has the correct primitives:

| Component | Existing location | Role |
|---|---|---|
| Live message store | `whatsapp_message_context` | Raw/live WA rows plus identity columns |
| Conversation grouping | `whatsapp_conversations` | Conversation windows per client/practice/contact |
| Structured facts | `whatsapp_extractions` | Append-only extracted facts |
| Identity audit | `whatsapp_identity_audit` | Every match/skip/ambiguous decision |
| LID bridge | `wa_lid_phone_map` | WhatsApp LID to phone/client bridge |
| Ops actions | `action_queue` | Work queue for follow-up, blockers, deadlines |
| Export staging | `whatsapp_export_*_staging` | Historical import path |
| Local cleartext archive | `full_messages.local.sqlite` | Pro-only FTS/search source |
| Local signal archive | `full_gold_signals.local.sqlite` | Pro-only mined signal source |

## Target Topology

```text
                         LIVE TEAM WHATSAPP
                               |
                               v
                    apps/wa-mirror, Baileys
                               |
                               | seconds
                               v
                 whatsapp_message_context, Postgres
                  | client_id, practice_id if matched
                  | phone, LID, sender_push_name
                  | team_member_email, source='wa_mirror'
                  |
       +----------+---------------------+
       |                                |
       v                                v
identity_resolver.py             wa_dashboard_stream.py
phone/LID/name/team               live internal stream
audit in identity_audit
       |
       v
conversations_grouper.py
conversation_id windows
       |
       v
extraction_pipeline.py, local Ollama
facts in whatsapp_extractions
       |
       v
action_queue_rules.py
ops tasks, no raw cloud upload


              HISTORICAL EXPORTS, PRO LOCAL ONLY
                               |
                               v
parse_full_corpus.py -> full_messages.local.sqlite, FTS5
quarantine_spicy_conversations.py -> exclude spicy/private candidates
mine_full_gold_signals.py -> full_gold_signals.local.sqlite
                               |
                               v
build_workspace_enrichment.py, proposed
match historical rows to CRM using wa-mirror/CRM/name/phone signals
                               |
                               v
workspace_enrichment.local.sqlite, proposed
                               |
                               v
apply_workspace_enrichment.py, proposed
write only internal derived facts/actions
```

## Local Search Console

The console is the local operator cockpit for the corpus. It should not be a
public or client-facing page. It can be implemented as a local-only backend
route plus a workspace UI, or as a separate local app if production routing
cannot guarantee raw-data isolation.

### Required Capabilities

| View | Purpose | Data source |
|---|---|---|
| Global search | Full-text search across local corpus | `full_messages.local.sqlite` FTS5 |
| Live mirror inbox | Recent wa-mirror rows with client/practice links | `whatsapp_message_context` |
| Match inspector | Show why a row maps to a client/practice | `whatsapp_identity_audit`, enrichment DB |
| Client 360 panel | Show derived facts for one client | `whatsapp_extractions`, proposed facts table |
| Ops queue | Follow-ups, blockers, payment, deadlines | `action_queue` |
| Unmatched prospects | High-value unknown contacts | `client_id IS NULL` rows, local enrichment DB |
| Team analytics | Aggregate workload/latency, no private raw export | `whatsapp_conversations`, aggregate queries |

### Console Filters

The console needs these filters from day one:

| Filter | Why |
|---|---|
| `client_id` / `practice_id` | Jump from CRM profile to related WhatsApp evidence |
| Contact name / sender name / chat title | Name is a real match signal, especially for exports |
| Phone / LID | Highest precision identity bridge |
| Source | Distinguish `wa_mirror`, `export_backfill`, ZIP, iCloud/Drive |
| Team member | Workload, response ownership, trust boundary |
| Date range | Case reconstruction and deadline mining |
| Signal group | Visa, tax, payment, document, blocker, relationship memory |
| Identity confidence | Separate automatic writes from review/ambiguous buckets |
| Quarantine status | Prevent private/spicy conversations from channeling |

## Identity And Match Matrix

`wa-mirror` already performs automatic CRM recognition. That recognition must be
the first input to enrichment, not something the Search Console tries to
rediscover from scratch.

| Match signal | Strength | Automatic decision |
|---|---:|---|
| Existing `whatsapp_message_context.client_id` from wa-mirror inline phone match | 1.00 | Treat as authoritative unless later CRM merge invalidates the client |
| Existing `whatsapp_message_context.practice_id` from wa-mirror best open practice | 0.95 | Use as preferred practice, but allow conversation/fact evidence to refine |
| Existing `conversation_id` from `whatsapp_conversations` | 0.95 | Use as canonical conversation window |
| Exact phone match against `clients.phone_normalized`, `clients.whatsapp`, or `clients.phone` | 0.95 | Auto-link to client |
| LID to phone to client via `wa_lid_phone_map` or Baileys mapping | 0.90 | Auto-link when map confidence is high |
| `team_member_email` to active team member | 1.00 for team identity | Mark sender as team; does not identify client by itself |
| `sender_push_name_snapshot` to active team member name | 0.85 when unique | Mark sender as team if fuzzy match is unique |
| Export chat title / file label / Drive folder parsed name to `clients.full_name` | 0.75-0.90 | Auto-link only if unique and above threshold |
| Sender display name to `clients.full_name` via pg_trgm | 0.70-0.90 | Auto-link if unique above threshold; otherwise keep candidate |
| Exact company name / PT name / brand name in body to company/practice | 0.70-0.85 | Stage as candidate unless combined with client signal |
| Email/passport/KITAS/NIB/NPWP mention matching CRM documents | 0.75-0.90 | Strong supporting signal, but avoid writing sensitive values into public views |
| First name only, nickname only, or common Indonesian/Italian name | 0.30-0.60 | Never auto-link alone |

### Name Handling

Name must be explicit in the matcher because the historical exports contain
name-rich labels that are not always available as phones.

Name sources:

| Source | Field / origin | Reliability |
|---|---|---|
| wa-mirror push name | `sender_push_name_snapshot` | Medium; user-controlled |
| WhatsApp export sender | `sender_display_name` | Medium; useful for group/team role |
| Export chat title | file/chat label | Medium-high if it is a client full name |
| Drive/iCloud folder label | `whatsapp_export_batches.source_label` | Medium-high if naming is standardized |
| CRM client name | `clients.full_name` | Canonical target |
| CRM company name | company tables / practice titles | Supporting target |
| Team names | `team_members.full_name`, aliases | Needed to avoid misclassifying staff as clients |

Rules:

1. Phone/LID/wa-mirror `client_id` beats name.
2. Name is auto-applied only when unique: top candidate must beat the second
   candidate by a margin.
3. Team name detection runs before client-name detection.
4. Name-only matches create audit rows even when not applied.
5. Personal/family/spicy quarantine blocks enrichment even if name matches a CRM
   person.

## Extraction Timing

### Live Path

| Timing | Job | Output |
|---|---|---|
| 0-5 seconds | `wa-mirror` captures message | Row in `whatsapp_message_context` |
| Same write | Inline phone lookup | `client_id`, `practice_id` when known |
| Every 5 minutes | Identity resolver catch-up | Fill missing `client_id`, `sender_role`, `team_member_id`; audit decisions |
| Every 5 minutes | Conversation grouper | Fill `conversation_id`, update conversation windows |
| Every 10 minutes | Deterministic signal miner | Cheap regex signals: payment, visa, document, deadline, blocker |
| Hourly | Local Ollama extractor | Structured facts in `whatsapp_extractions` |
| Hourly | Action queue rules | Internal CRM/ops actions |
| Daily 02:00 local | Re-score unresolved/ambiguous | Better matches after CRM/contact updates |

### Historical Backfill Path

| Timing | Job | Output |
|---|---|---|
| One-time or new export drop | `parse_full_corpus.py` | `full_messages.local.sqlite` |
| Immediately after parse | `quarantine_spicy_conversations.py` | private/spicy exclude list |
| Immediately after quarantine | `mine_full_gold_signals.py` | `full_gold_signals.local.sqlite` |
| Next | proposed `build_workspace_enrichment.py` | `workspace_enrichment.local.sqlite` |
| Next | proposed `apply_workspace_enrichment.py --apply` | internal CRM facts/actions |
| Nightly | local semantic re-index | refreshed search vectors / summaries |

### Re-index Policy

Use incremental IDs:

| Source | Increment cursor |
|---|---|
| wa-mirror live | max `whatsapp_message_context.id` |
| Postgres export staging | max `whatsapp_export_messages_staging.id` |
| local full SQLite | `message_id` plus file hash |
| gold signals | signal DB primary key / body hash |

No job should reprocess the whole corpus by default. Full rebuild is a manual
maintenance mode.

## Enrichment Model

The enrichment layer should distinguish between raw messages, extracted facts,
and channel destinations.

### Proposed Local Output

Create:

```text
research/personal/wa-corpus/full/workspace_enrichment.local.sqlite
```

Tables:

| Table | Purpose |
|---|---|
| `candidate_matches` | message/file/conversation to client/practice candidates |
| `candidate_facts` | extracted structured facts before CRM write |
| `candidate_actions` | proposed action queue rows before write |
| `run_metrics` | counts, thresholds, timestamps |
| `blocked_records` | why something was not channelled |

The local DB may contain raw local references but must remain gitignored.

### Proposed Internal CRM Table

Add a durable table for derived profile facts instead of mutating `clients`
directly:

```sql
CREATE TABLE crm_whatsapp_enrichment_facts (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES clients(id),
    practice_id BIGINT REFERENCES practices(id),
    conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
    source_message_id BIGINT,
    source_body_hash TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    fact_value JSONB NOT NULL,
    confidence NUMERIC(3,2) NOT NULL,
    identity_method TEXT,
    extractor_name TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'internal_only',
    retention_class TEXT NOT NULL DEFAULT 'ops',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_at TIMESTAMPTZ
);
```

This makes enrichment reversible, auditable, and safe. CRM profile pages can
read from this table without treating LLM-extracted facts as canonical legal
truth.

### Fact Types To Channel

| Fact type | Destination | Auto-write condition |
|---|---|---|
| Preferred language | Internal CRM profile side panel | confidence >= 0.90 or repeated |
| Service interest | Lead/practice suggestion | confidence >= 0.80 |
| Visa type / permit class | Practice candidate / CRM fact | confidence >= 0.85 |
| Document requested/sent/missing | Document checklist / action queue | confidence >= 0.80 |
| Payment mentioned/confirmed/pending | Finance action queue | confidence >= 0.85 |
| Deadline / expiry / appointment | Compliance alert / action queue | confidence >= 0.85 |
| Team promise | `team_promises` / action queue | confidence >= 0.80 |
| Client question | action queue if unanswered | confidence >= 0.75 |
| Complaint / urgency | action queue priority | confidence >= 0.75 |
| Relationship/memory note | internal note only | confidence >= 0.90 and not private/quarantined |

## Routing / Canalizzazione

The same extracted WhatsApp fact can feed different internal surfaces. Routing
must be explicit.

| Channel | Receives | Must never receive |
|---|---|---|
| Local Search Console | Raw message text, raw local context, full FTS | Cloud upload, public URLs |
| Internal CRM workspace | Derived facts, confidence, local reference IDs, action summaries | Raw private chats, spicy quarantine, raw source paths |
| Practice timeline | CRM-safe message snippets or derived events linked to practice | Raw group internals, raw Baileys JSON |
| `action_queue` | Follow-up tasks, blockers, due dates, payment tasks | Speculative low-confidence matches |
| Knowledge base draft | De-identified regulatory/process knowledge | Client identities, phones, family/private details |
| Team dashboard | Aggregate response-time/workload metrics | Personal raw chat bodies |
| Client portal `my.balizero.com` | Only explicit client-safe status fields | Raw WhatsApp, internal evidence, hashes, model confidence |

## Automatic Thresholds

The user does not want manual approval. So the system should automate with hard
thresholds and automatic quarantine gates.

| Band | Behavior |
|---|---|
| `>= 0.95` identity | Write directly to internal CRM enrichment/actions |
| `0.85-0.94` identity + strong fact | Write internal fact; include audit provenance |
| `0.70-0.84` useful but uncertain | Create internal candidate/action only when low-risk |
| `0.40-0.69` ambiguous | Keep in local console/audit; do not channel to CRM profile |
| `< 0.40` | Ignore except aggregate metrics |
| quarantine hit | Block from all enrichment writes |

There is no owner approval queue in the default path. The safety mechanism is
deterministic gating, confidence thresholds, deduplication, and audit logging.

## Implementation Plan

### Phase 1: Local Connector And Enrichment Builder

Create:

```text
scripts/whatsapp_corpus/build_workspace_enrichment.py
scripts/tests/test_whatsapp_corpus_workspace_enrichment.py
```

Responsibilities:

1. Read `full_messages.local.sqlite`.
2. Read `full_gold_signals.local.sqlite`.
3. Read local CRM/Postgres identity tables when available:
   `clients`, `companies`, `practices`, `whatsapp_message_context`,
   `whatsapp_conversations`, `whatsapp_identity_audit`, `wa_lid_phone_map`.
4. Build `workspace_enrichment.local.sqlite`.
5. Compute match strengths with the matrix above.
6. Emit safe aggregate summary only:
   `research/personal/wa-corpus/full/workspace_enrichment_summary.md`.

### Phase 2: Internal Apply Writer

Create:

```text
scripts/whatsapp_corpus/apply_workspace_enrichment.py
scripts/tests/test_whatsapp_corpus_apply_workspace_enrichment.py
apps/backend-rag/backend/db/migrations_v2/202_wa_whatsapp_enrichment_facts.sql
```

Responsibilities:

1. Create `crm_whatsapp_enrichment_facts`.
2. Write only facts/actions above threshold.
3. Write `whatsapp_identity_audit` for applied, skipped, ambiguous, and blocked
   enrichment decisions.
4. Deduplicate by `(client_id, fact_type, source_body_hash, extractor_version)`.
5. Never write raw body text to profile facts.

### Phase 3: Local Search API

Create:

```text
apps/backend-rag/backend/app/routers/wa_search_console.py
apps/backend-rag/backend/services/wa_copilot/search_console_index.py
apps/backend-rag/backend/tests/unit/routers/test_wa_search_console.py
```

Routes:

| Route | Role |
|---|---|
| `GET /api/local/wa-search/messages` | Local-only FTS / filtered search |
| `GET /api/local/wa-search/conversation/{id}` | Local conversation context |
| `GET /api/local/wa-search/match/{message_id}` | Match explanation |
| `GET /api/local/wa-search/client/{client_id}/facts` | Derived facts |
| `POST /api/local/wa-search/reindex` | Admin local re-index |

Guardrails:

1. Bind only to `127.0.0.1` for raw local console mode.
2. Require admin auth even locally.
3. Never deploy raw local routes to Vercel/Fly public production.
4. Response models must forbid extra fields.
5. Privacy audit tests must fail if raw source paths or phone numbers enter
   tracked markdown reports.

### Phase 4: Workspace UI

Update or replace:

```text
apps/mouth/src/app/(workspace)/whatsapp/page.tsx
apps/mouth/src/components/whatsapp/*
apps/mouth/src/lib/api/whatsapp/*
```

Current workspace WhatsApp page is a basic conversation viewer. The new console
needs:

1. Three-pane layout: conversation list, message/search results, enrichment
   inspector.
2. Match-signal column with strength.
3. Filters for client/practice/source/team/date/signal/confidence.
4. One-click jump from CRM client profile to local WA evidence.
5. Clear visual split between:
   - raw local evidence;
   - internal CRM derived facts;
   - action queue rows.

## First Execution Target

Start with Phase 1.

The next concrete task is:

```bash
source .venv/bin/activate
PYTHONPATH=. python -m scripts.whatsapp_corpus.build_workspace_enrichment \
  --messages-db research/personal/wa-corpus/full/full_messages.local.sqlite \
  --signals-db research/personal/wa-corpus/full/full_gold_signals.local.sqlite \
  --output-db research/personal/wa-corpus/full/workspace_enrichment.local.sqlite \
  --summary research/personal/wa-corpus/full/workspace_enrichment_summary.md
```

Minimum useful Phase 1 output:

| Output | Meaning |
|---|---|
| `candidate_matches` | Which WhatsApp files/messages can attach to CRM clients |
| `match_signal` | `wa_mirror_client_id`, `phone_exact`, `lid_map`, `name_exact`, `name_trgm`, etc. |
| `match_strength` | Numeric confidence |
| `identity_decision` | `auto_apply`, `candidate_only`, `ambiguous`, `blocked` |
| `blocked_reason` | quarantine/private/personal/low confidence/no CRM target |

Once this exists, automatic CRM/workspace enrichment becomes a controlled write
problem rather than a corpus-mining problem.
