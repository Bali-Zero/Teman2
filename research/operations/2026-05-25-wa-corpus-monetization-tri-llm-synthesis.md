---
date: 2026-05-25
domain: operations
client_case: bali-zero-internal
sources:
  - tri-LLM panel (Gemini 3.1 Pro + Codex GPT-5.5 + DeepSeek V4 Pro reasoning_effort=high)
  - Empirical postgres query nuzantara_readonly 2026-05-25
  - Round 1 panel artifacts: /tmp/wa-monetization-panel/{gemini-3.1-pro,gpt-5.5-codex,deepseek-v4-pro}.md
  - Round 2 deep-dive on empirical findings (pending)
status: draft
---

# WA Corpus Monetization — Tri-LLM Synthesis + System Study

> **Pre-decisional document**. Antonello must approve embedding/schema/start-point choices before S1 dev kickoff.

## TL;DR

30k+ messaggi WhatsApp clienti (3 batch storici aziendali 26.743 msg + 188 chat individuali 1.88 GB ancora non ingested + live capture continua 16.655 msg) → trasformare in **memoria operativa event-sourced** che alimenta un **copilot interno team-first** (NON chatbot cliente). Pattern dominante 2026 enterprise (Salesforce Conversation Insights, Gong AI Deal Monitor, Zendesk auto-intent, Intercom topic clustering): estrarre evidence-linked facts → action queue per team. Zero auto-write su CRM core. Strategic moat = 4 anni di evidenze operative codificate che competitor (Lets Move, Emerhub, Flado) non possono replicare.

## Empirical state 2026-05-25 (verified)

### Volume

| Tabella | Rows | Note |
|---|---:|---|
| `whatsapp_message_context_enriched` | 16.655 | Live capture (Brevo 14.847 + Baileys 1.808), 19 dic 2022 → 24 mag 2026 |
| `whatsapp_export_messages_staging` | 26.743 | 3 batch storici aziendali (YOPO 12 + EITK 670 + INVOICE 26.061) + pilot Catia 53 |
| `whatsapp_export_documents_staging` | 556 + 4 (Catia) | OCR-ready ma OCR=0 done |
| `whatsapp_contacts` | 8.639 | Anagrafica contatti |
| `whatsapp_lid_phone_map` | 141 | LID→phone canonicalization (sotto-utilizzato) |
| `whatsapp_team_sessions` | 8.212 | Baileys auth sessions |
| 188 ZIP NOT ingested | ~30k msg stimati | `~/Downloads/drive-download-20260524T182039Z-3-001.zip` 1.88 GB |

### Identity resolution: blocking #1

| Metrica | Valore | Target S1 |
|---|---:|---:|
| Total msgs live capture | 16.655 | 16.655 |
| `client_id` set | 331 | ~10.000 |
| **% matched** | **2.0%** | **60%+** |
| `crm_full_name` resolved | 419 | — |
| `needs_lid_resolve` pending | 549 | < 100 |
| Unique phones seen | 61 | — |

### Practice linking: peggio del previsto

| Metrica | Valore | Target S1 |
|---|---:|---:|
| Practices totali | 425 | 425 |
| Practices con WA msg | **3 (0.7%)** | 200+ (50%) |

Quasi tutte le pratiche aperte/chiuse degli ultimi 2 anni NON hanno conversazione WhatsApp collegata. Il sistema vede pratica come dato isolato dal canale di interazione.

### KG state — già esistente ma sganciato

| KG layer | Rows | Cosa contiene | Uso WA? |
|---|---:|---|---|
| `kg_nodes` postgres | **114.176** | Regulatory ground-truth: dokumen 42k, kbli 13k, pasal 10k, izin_usaha 9k, biaya 9k, undang_undang 3.7k, jangka_waktu 3.7k, pt_pma 1.4k, vitas 413, kitas 403, ppn 274 | ❌ |
| `kg_edges` postgres | **251.872** | REQUIRES 66k, APPLIES_TO 39k, REFERENCES 32k, PART_OF 31k, HAS_DURATION 10k, PENALTY_FOR 8k, REQUIRED_FOR 8k, ISSUED_BY 6k, HAS_FEE 4k | ❌ |
| `crm_kg_nodes` | 852 | crm_document 418, crm_client 325, crm_person 109 | ❌ |
| `crm_kg_edges` | 711 | BELONGS_TO 418, CONTEMPORANEOUS 176, DESCRIBES 117 | ❌ |
| `kg_entity_mentions` | **76.218** | Schema `(entity_id, collection_name, point_id, mention_text, confidence, match_type)` — infrastruttura riusabile | ❌ |
| Mata Garuda SQLite knowledge.db | varies | OSINT-specific, separato | ❌ |

**Opportunity gap**: il KG regulatorio è massivo + popolato + funzionante, ma non viene **interrogato** durante le conversazioni cliente. Quando Catia chiede "che fee per D12?" il team risponde a memoria — il KG ha già `kitas:D12 + HAS_FEE + biaya`, mai consultato.

### Senders top (3 batch aziendali)

Sahira 6.574, Amanda 5.023, Ari 4.572, Antonello 3.078, Adit 2.638, Krisna 1.127, Suryadi 1.021, Asya 923, Surya 778, Adi 561. Conferma RBAC scopes — Sahira è epicentro (anche se nominalmente in probation post-30 apr).

## Tri-LLM Panel Synthesis (Round 1)

### Convergenza 3/3

| Pattern | Verdict |
|---|---|
| GraphRAG > flat RAG (chat frammentate) | Build KG cliente-servizio-doc-outcome |
| Agentic copilot TEAM-FIRST (≥6 mesi prima di chatbot cliente) | Confermato per dominio legale/visa |
| Human-in-the-loop su CRM writes | `suggested_next_stage` mai write diretto su `practices` |
| PII scrub locale Ollama PRIMA di Claude/cloud | Edge presidio obbligatorio (UU PDP + Symbiosis Law 2) |
| Identity resolution = BLOCKING #1 | Senza phone↔client_id, tutto è vanity |
| No sentiment per-msg | Vanity in B2B regulatorio operativo |
| Estrai: action items, next_due_date, objections, blockers, doc requested/provided | Core set ROI-positive |
| Ollama locale per batch processing | Cost zero + sovranità |

### Divergenza che richiede scelta esplicita

| Tema | Gemini | DeepSeek | Codex | Mia raccomandazione |
|---|---|---|---|---|
| **Embedding model** | Keep `text-embedding-3-small` | Sostituisci con `BGE-M3` | Hybrid: nuova collection locale BGE-M3 + freeze 3-small per non-sensitive | **Codex** — Qdrant locale BGE-M3 per WA (privacy + multilingua), keep cloud 3-small frozen per RAG legal |
| **Schema strategy** | Nuova tabella `conversation_semantic_threads` | Colonne in-place su `whatsapp_message_context_enriched` | 5 tabelle nuove (`whatsapp_conversations` + `_attachments` + `_extractions` append-only + `conversation_rollups` + `action_queue`) | **Codex** — `_extractions` append-only è killer feature per audit legale + model migration safe |
| **NotebookLM ruolo** | Mese 3 process mining | ❌ NON caricarci 30k msg | Solo procedure approvate post-human review | **Codex+DeepSeek** — NB ground-truth solo per procedure consolidate |
| **Cron cadence** | Event-driven + nightly | Cron 7:00 WITA + event-driven | 3 ritmi: event + daily 07:30 + weekly procedure-miner | **Codex** — 3 ritmi distinti |
| **Effort 0-30gg** | 30h | 10-12h | 45-70h | **Codex** realistico (identity v1 + extraction + action_queue) |
| **Lifecycle stage** | Generic funnel | enum 6 stati | `lifecycle_stage` + `outcome` (won/lost/completed) | **Codex** — outcome esplicito = label per future ML |

### Idee uniche Codex (non in altri 2)

1. **`whatsapp_extractions` append-only** con `evidence_start/evidence_end` char offsets + `prompt_version`. Ogni claim AI auditabile + ri-eseguibile a model change. **Killer feature legal-grade.**
2. **`action_queue` come UNICA superficie team** — un solo posto da guardare la mattina. Anti-pattern: "non misurare success in messaggi processati, misura follow-up chiusi".
3. **Citazioni live** Salesforce Conversation Insights / Gong AI Deal Monitor / Zendesk auto-intent / Meta Cloud API webhook / UU PDP / WhatsApp Business policy / OpenAI embeddings → conferma empirica che pattern "team copilot" è dominante 2026 nel B2B regolatorio.

### Idee uniche DeepSeek

1. **Q-LoRA fine-tune** Qwen2.5-14B su 1-2k msg annotati via Gemini few-shot → Qwen7B locale inference $0. Self-improving dataset.
2. **Embedding di passaporti recuperabili via similarity search** (case fintech Singapore reale). Mai embeddare testo non-redatto.
3. **Numeri ROI espliciti**: +10% conversion su 100 lead/mese → +5-6 pratiche × €1.500 ≈ **€8k/mese**, payback < 2 mesi.

### Idee uniche Gemini

1. **Friction score 1-10** per turno conversazione (deal velocity proxy).
2. **Edge_Case tagging** — NON scartare anomalie (PMA durato 6 mesi vs 1) → sono training material che competitor non hanno.
3. **Process mining mese 3** via NB → "manuale dinamico basato su come si fa davvero".

## Architettura proposta

### 4 ritmi · 5 layer · 1 superficie

```
┌─────────────────────────────────────────────────────────────────┐
│  ACTION_QUEUE — UNICA superficie team (UI mattina)              │
│  client | practice | reason | suggested_action | due | evidence │
└─────────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────────┐
│  AGENTIC LOOPS (LangGraph orchestration)                        │
│  • Event-driven: nuovo msg → identity → extract → enqueue       │
│  • Daily 07:30 WITA: NBA generator + churn/deadline monitor     │
│  • Weekly Mon 02:00: procedure-miner (chiusi → approve → NB)    │
│  • Nightly 03:00: compliance archivist (PII + retention)        │
└─────────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE GRAPH (kg_nodes/kg_edges esistenti + nuovo bridge)   │
│  Person ─ Phone ─ Service ─ Document ─ Conversation ─ Outcome   │
│  via kg_entity_mentions (76k esistente, RIUSABILE)              │
│  + WA messages → kg_entity_mentions(collection='wa_messages')   │
│  + valid_from/to + confidence + evidence_message_ids            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────────┐
│  EXTRACTIONS APPEND-ONLY (whatsapp_extractions — NEW)           │
│  Ollama qwen3.5 → fact_type | value_json | evidence_offsets     │
│  | confidence | prompt_version | review_status                  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
┌─────────────────────────────────────────────────────────────────┐
│  RAW (whatsapp_message_context_enriched ESISTENTE)              │
│  + whatsapp_conversations (NEW) — conversation_id grouping      │
│  + body_encrypted (existing body) + body_redacted (NEW) + hash  │
└─────────────────────────────────────────────────────────────────┘
```

### Schema migration concreto (Codex hybrid)

```sql
-- Migration 200: WhatsApp copilot infrastructure
-- Append-only design per audit/legal proof bundle

CREATE TABLE whatsapp_conversations (
  conversation_id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  practice_id BIGINT REFERENCES practices(id),
  phone_e164 TEXT NOT NULL,
  lid TEXT,
  source_group_id TEXT,  -- chat di gruppo
  service_line TEXT,     -- D12 / KITAS_E33G / PMA / TAX / ...
  lifecycle_stage TEXT,  -- inquiry / qualifying / proposal / won / service / retention / lost
  outcome TEXT,          -- won / lost / completed / abandoned
  owner_team_member TEXT,
  started_at TIMESTAMPTZ,
  last_customer_at TIMESTAMPTZ,
  last_team_at TIMESTAMPTZ,
  confidence NUMERIC(3,2),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE whatsapp_extractions (
  extraction_id BIGSERIAL PRIMARY KEY,
  message_id BIGINT NOT NULL,  -- FK su whatsapp_message_context_enriched.id
  conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  extractor_name TEXT NOT NULL,    -- 'ollama_qwen3.5_extract_v1'
  model TEXT NOT NULL,             -- 'qwen3.5:9b'
  prompt_version TEXT NOT NULL,    -- 'wa_extract_v1.0'
  fact_type TEXT NOT NULL,         -- 'intent' / 'next_action' / 'doc_requested' / 'price_mention' / 'objection' / 'blocker'
  value_json JSONB NOT NULL,
  confidence NUMERIC(3,2),
  evidence_start INTEGER,          -- char offset in body
  evidence_end INTEGER,
  review_status TEXT DEFAULT 'pending',  -- pending / verified / rejected
  reviewed_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON whatsapp_extractions (message_id, fact_type);
CREATE INDEX ON whatsapp_extractions (conversation_id, fact_type, confidence DESC);

CREATE TABLE action_queue (
  action_id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  practice_id BIGINT REFERENCES practices(id),
  conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  reason TEXT NOT NULL,            -- 'silence_72h' / 'deadline_5d' / 'doc_missing' / 'churn_risk' / 'upsell_renewal'
  recommended_action TEXT NOT NULL,
  suggested_message_draft TEXT,    -- pre-cooked reply per copy-paste
  due_at TIMESTAMPTZ,
  evidence_message_ids BIGINT[],
  owner TEXT,                      -- team member email
  priority INTEGER DEFAULT 5,      -- 1-10
  status TEXT DEFAULT 'open',      -- open / snoozed / done / dismissed
  snoozed_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  resolution_notes TEXT
);
CREATE UNIQUE INDEX ON action_queue (client_id, reason) WHERE status='open';
CREATE INDEX ON action_queue (owner, status, priority DESC, due_at);

-- Upgrade whatsapp_message_context_enriched (additive only)
ALTER TABLE whatsapp_message_context_enriched
  ADD COLUMN conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  ADD COLUMN source_system TEXT,         -- 'brevo' / 'baileys' / 'drive_import'
  ADD COLUMN external_message_id TEXT,
  ADD COLUMN sender_role TEXT,           -- 'client' / 'team' / 'internal_group' / 'vendor'
  ADD COLUMN team_member_id BIGINT,
  ADD COLUMN identity_confidence NUMERIC(3,2),
  ADD COLUMN identity_method TEXT,       -- 'phone_canonical' / 'lid_map' / 'fuzzy_name' / 'practice_inference' / 'manual'
  ADD COLUMN language_primary TEXT,      -- ISO 639-1
  ADD COLUMN has_sensitive_pii BOOLEAN DEFAULT false,
  ADD COLUMN retention_class TEXT,
  ADD COLUMN legal_hold BOOLEAN DEFAULT false,
  ADD COLUMN body_redacted TEXT,         -- PII-scrubbed copy for embedding/Claude
  ADD COLUMN body_hash TEXT,
  ADD COLUMN ingest_batch_id BIGINT REFERENCES whatsapp_export_batches(id),
  ADD COLUMN schema_version TEXT DEFAULT 'v1.0';
```

### Bridge KG regulatorio ↔ WA (NUOVO design)

```sql
-- Riusa kg_entity_mentions con collection_name='wa_messages'
-- Quando extraction estrae "D12 visa" da msg, crea mention:
INSERT INTO kg_entity_mentions
  (entity_id, collection_name, point_id, mention_text, confidence, match_type)
SELECT 
  n.entity_id,
  'wa_messages',
  m.id::text,        -- point_id = message_id
  '<extracted fragment>',
  0.85,
  'extract_v1'
FROM kg_nodes n
WHERE n.entity_type IN ('kitas', 'vitas', 'kbli', 'izin_usaha', 'pt_pma')
  AND n.name ILIKE '%D12%';

-- Query power-user: "tutti i msg che menzionano visto D12 + cliente italiano"
SELECT m.id, m.message_date, m.sender_display_name, m.body
FROM whatsapp_message_context_enriched m
JOIN kg_entity_mentions km ON km.point_id = m.id::text
  AND km.collection_name = 'wa_messages'
JOIN kg_nodes kn ON kn.entity_id = km.entity_id
  AND kn.entity_type = 'vitas' AND kn.name ILIKE '%D12%'
WHERE m.language_primary = 'it'
ORDER BY m.message_date DESC LIMIT 50;
```

Questo trasforma il KG da statico (regulatory KB) a **vivo** (regulatory + casi reali). Ogni mention diventa "evidence" che D12 è stato fatto X volte con risultato Y.

## Roadmap S1/S2/S3 — 30/60/90 giorni

### S1 (30 giorni · 45-70h dev)

**Goal**: foundation + identity + action queue MVP.

| Sprint | Task | Effort | Output |
|---|---|---:|---|
| 1.1 | Mass-ingest 188 ZIP (pipeline Catia pronta) | 4-6h | +30k msg in `whatsapp_export_messages_staging`, +500+ docs |
| 1.2 | Migration 200 (schema sopra) | 4-6h | Tabelle pronte |
| 1.3 | Identity resolver v1: phone E.164 + LID map + fuzzy sender name + Drive folder path + practice keyword | 10-12h | Match 2% → 60%+ su 16.655 + nuovi 30k |
| 1.4 | Conversations grouping cron (24h window + lifecycle stage init) | 6-8h | `whatsapp_conversations` popolato |
| 1.5 | Extraction pipeline Ollama qwen3.5 batch (intent / next_action / doc_requested / objection) | 8-10h | `whatsapp_extractions` per ogni msg |
| 1.6 | Action_queue rules engine v1 (silence/deadline/doc_missing) | 6-8h | Queue popolata |
| 1.7 | UI MVP (Streamlit o estensione `apps/wa-dashboard`) | 6-10h | Team vede la lista mattina |
| 1.8 | Empirical eval set (50 query reali da team) | 2-4h | Baseline metrics |

**Expected outcome**:
- Identity 2% → 60%
- Practices linked 0.7% → 30-40%
- Team risparmia 5-10h/settimana (Codex estimate)
- Action_queue daily volume 20-30 items
- Follow-up persi -30% (DeepSeek estimate)
- Lead storici riattivabili identificati

### S2 (60 giorni · +60-90h dev)

**Goal**: KG bridge + dashboard BI + embedding upgrade.

| Sprint | Task | Effort | Output |
|---|---|---:|---|
| 2.1 | KG bridge wa↔kg_entity_mentions (entity_id linking durante extract) | 10-12h | Query power-user attive |
| 2.2 | Embedding BGE-M3 collection Qdrant locale + indexing thread-level | 12-15h | Multilingua recall@10 >70% |
| 2.3 | NBA agent event-driven (LangGraph): nuovo msg → context KG+history → draft reply | 15-20h | Draft messaggi suggeriti contestualmente |
| 2.4 | Dashboard BI: deal velocity / objections / blockers / response SLA / per-team conversion | 12-15h | Visibility manageriale |
| 2.5 | Procedure miner weekly batch (chiusi → pattern → human approve) | 10-15h | Manuale dinamico draft |
| 2.6 | Q-LoRA fine-tune Qwen2.5-14B su 1-2k msg annotati (opzionale) | 8-12h | Inference locale qualità migliorata |

**Expected outcome**:
- Conversion +10% (€8k/mese ROI DeepSeek estimate)
- Time-to-resolution -20% su casi ripetitivi
- Onboarding nuovo team member 50% più veloce
- Pricing/playbook data-driven

### S3 (90 giorni · +80-120h dev)

**Goal**: moat + legal proof + Zantara corpus.

| Sprint | Task | Effort | Output |
|---|---|---:|---|
| 3.1 | Procedure miner approvato → Zantara corpus sanificato → NB-AGENTS update | 15-20h | Strategic moat consolidato |
| 3.2 | Legal proof bundle per pratica (audit trail extractions + msg redacted) | 15-20h | Difendibilità legale |
| 3.3 | Retention automation (UU PDP compliance) | 10-15h | Compliance posture |
| 3.4 | WhatsApp template approvati follow-up (utility/marketing/auth) | 15-20h | Outreach scalabile |
| 3.5 | Eval set multilingua + regression test ext | 10-15h | Qualità misurata |
| 3.6 | Cliente-facing (opzionale, NOT auto-reply): self-service tracking status pratica | 15-30h | Riduzione "dove siamo?" inquiry |

**Expected outcome**:
- 4 anni di evidenze operative codificate = competitor cannot replicate
- Legal audit-grade compliance
- Onboarding nuovo team member: 50% → 70% più veloce

## Decisioni che richiedono Antonello OK

### Decisione 1: Embedding strategy

**Opzione raccomandata: hybrid Codex**
- Nuova collection Qdrant **locale** (Docker su Pro/Mini) con BGE-M3 (multilingua, gira gratis Ollama) per WA corpus (privacy UU PDP + qualità bahasa/ru/it)
- **Freeze** Qdrant cloud `text-embedding-3-small` per RAG legal/regulatory esistente (NB-IO sources, 93.283 vectors)
- Cost: $0 (BGE-M3 local) vs $0.02/1k tokens (3-small cloud)

### Decisione 2: Schema strategy

**Opzione raccomandata: Codex 5-tabelle**
- `whatsapp_conversations` (grouping)
- `whatsapp_extractions` (append-only **legal-grade**)
- `action_queue` (UNICA UI team)
- Colonne additive su `whatsapp_message_context_enriched` (additive only, zero break)
- Skip `whatsapp_attachments` standalone (riusa `whatsapp_export_documents_staging` esistente)
- Skip `conversation_rollups` (derivabile da extractions)

Migration 200 sopra.

### Decisione 3: Start point S1.1

**Opzione raccomandata: Mass-ingest 188 ZIP PRIMA poi identity v1**
- Identity v1 funziona meglio su corpus completo (più data points per match)
- Pipeline mass-ingest già validata col pilot Catia
- Tempo: 4-6h ingest + 10-12h identity = 14-18h totali, identity attiva su ~46k msg invece di 16k

## Pitfall noti (da panel + esperienza)

1. **Hallucinated CRM update**: AI marca `practices.stage='approved'` su msg ambiguo. Mitigation: `suggested_*` mai write diretto.
2. **Privacy leak via embedding**: passport recuperabili via similarity search (case Singapore fintech). Mitigation: solo `body_redacted` in Qdrant, mai raw.
3. **Latency Ollama real-time**: qwen2.5-14B >5s per msg. Mitigation: small model (Qwen3:0.5B) per intent first-pass, batch resto.
4. **Over-engineering pre-identity**: tutto è vanity con 2% match. Identity FIRST, sempre.
5. **NotebookLM saturation**: 60 NB / 3.6k src già; aggiungere 30k raw msg → ingestibile + hallucination.
6. **Sentiment per-msg**: vanity in B2B operativo. Misura deal velocity instead.
7. **Chatbot cliente prematuro**: dominio legale/visa, allucinazione = perdita cliente + reputazione. Team copilot 6+ mesi prima.
8. **Mix internal group chat + cliente**: `sender_role` enum obbligatorio per non addestrare segnali tossici (chat "INVOICE BALI ZERO" è team-to-team, non cliente).
9. **Vector trap su WA**: cosine similarity restituisce *frasi simili al problema*, non *soluzioni*. KG obbligatorio.
10. **Measure success wrong**: NO "messaggi processati", SI "follow-up chiusi / lead riattivati / pratiche completed / dispute risolte con proof bundle".

## Anti-pattern (NON FARE)

- ❌ Inviare JSON/PDF cliente grezzi a Claude OAuth senza PII scrub (UU PDP violation)
- ❌ Embeddare conversazioni intere con `text-embedding-3-small` (mediocre multilingua)
- ❌ Addestrare modello da zero (non hai data labeled abbastanza)
- ❌ Aspettare "pipeline perfetta" per iniziare (start con action_queue MVP, iterare)
- ❌ Lasciare anomalie fuori (edge case = training material che competitor non hanno)
- ❌ Esporre KG/Drive ID a `my.balizero.com` (audience separation rigida `kita`/`my`)

## Strategic moat — perché competitor non possono replicare

| Asset Bali Zero | Competitor (Lets Move/Emerhub/Flado) |
|---|---|
| 4 anni di chat reali codificate | Trello + Google Sheet |
| KG regulatorio 114k entities popolato | Sito statico + FAQ |
| Pattern italiani vs russi vs bahasa empirici | Generic content |
| Procedure mined da casi chiusi reali | SOP statico copiato da web |
| Legal proof bundle audit-grade | "ti mando email se serve" |
| Identity resolution cross-channel WA+Brevo+CRM | Solo CRM isolato |

Il moat è **outcome-labeled operational memory** + **procedure graph derivato da casi reali** + **evidence-backed next action**, aggiornato ogni giorno.

## Metriche di successo S1 (30 giorni)

| Metrica | Baseline 2026-05-25 | Target S1 |
|---|---:|---:|
| Identity match % | 2.0% | ≥60% |
| Practices linked % | 0.7% | ≥30% |
| Time-to-first-response nuovo msg | sconosciuto (baseline) | <2h business hours |
| Follow-up persi (>72h silence + open intent) | sconosciuto | -30% |
| Lead storici riattivati | 0 | ≥20 |
| Team h/settimana risparmiate | 0 | 5-10 |
| Action_queue items resolved/dismissed | n/a | ≥70% resolved |
| Team satisfaction (1-10 survey) | n/a | ≥7 |

## Costi previsti (S1+S2+S3 = 90 giorni)

| Voce | Costo |
|---|---:|
| Dev hours (Antonello + Claude) | 185-280h |
| Ollama BGE-M3 + qwen3.5 inference | $0 (locale) |
| Claude OAuth MAX (extraction validation) | $0 (subscription esistente) |
| DeepSeek V4 Pro (panel/red-team occasionale) | <$5/mese |
| Postgres storage extra (~10GB extractions) | $0 (Fly.io existing) |
| Qdrant cloud (no change) | $0 marginale |
| **Totale incremental cost** | **~$5-15/mese** |

ROI target: +€8k/mese DeepSeek estimate (10% conversion uplift su 100 lead/mese). **Payback < 2 mesi**.

## Round 2 panel — sintesi convergente

Round 2 completato 2026-05-25 su 5 questioni deep-dive emerse da empirical study. **Convergenza 3/3 schiacciante** su 4/5 questioni — divergenze solo su numeri target (E).

### A. Bridge KG regolatorio (114k) ↔ WA copilot — UNANIME 3/3

Tutti propongono pipeline 2-step **estrazione → linking**, NON entity-linking on-the-fly:

1. **Estrazione**: LLM batch produce facts normalizzati da messaggi WA (intent, doc, fee, durata, blocker, team commitment)
2. **Linking**: candidate generation contro `kg_nodes` via exact-alias / fuzzy / embedding fallback
3. Risultato in `whatsapp_extractions` (fact_type + value + evidence span) + `whatsapp_entity_links` (extraction ↔ kg_node)

**Fact_type da estrarre**, mapping diretto a `kg_nodes.entity_type` esistente:
- `visa_type` → `kitas`/`vitas`/`itk` (esistono 413+403+...)
- `kbli_code` → `kbli` (13.418 nodi)
- `dokumen` → `dokumen` (42.245 nodi)
- `biaya` → `biaya` (9.180 nodi)
- `jangka_waktu` → `jangka_waktu` (3.653 nodi)
- `perizinan/izin_usaha` → `izin_usaha` (9.462 nodi)
- `blocker` (custom): missing doc, mismatch name, expired passport, payment pending
- `team_commitment` (custom): promises with inferred due date
- `client_question` (custom): normalized class

Quando linking arriva, query power-user diventano triviali (vedi sezione "KG bridge queries" sotto).

### B. Pattern `kg_entity_mentions` — UNANIME RIUSO (no duplicazione)

**Empirical state verificato 2026-05-25**: la tabella è `text` per ogni campo (ZERO ENUM constraint), quindi possiamo aggiungere valori liberamente.

| Campo | Valore esistente | Valore nuovo per WA |
|---|---|---|
| `collection_name` | `legal_unified_hybrid_hybrid` (76.218 row) | aggiungi `wa_messages` (msg-level), `wa_threads` (thread-level), `wa_attachments` (OCR allegati) |
| `point_id` | UUID Qdrant point | `message_id::text` (Codex+DeepSeek concordi: msg-level NON thread-level per auditabilità) |
| `match_type` | `exact` (33k), `doc_propagation` (28k), `book_title_law` (14k) | aggiungi `extract_v1`, `exact_code`, `fuzzy_alias`, `embedding_candidate`, `llm_verified` |

**Zero schema migration** per `kg_entity_mentions`. Solo INSERT con nuovi valori.

### C. Practice linking 0.7% → 30%+ — UNANIME multi-signal probabilistico

Algoritmo Codex (più rigoroso):

```python
def score_practice_candidate(msg, practice) -> tuple[float, dict]:
    signals = {}
    # +0.35 client/person match
    if msg.client_id == practice.client_id:
        signals['client_match'] = 0.35
    # +0.25 service_type token match
    extracted = extract_service_type(msg.body, msg.attachment_names)
    if extracted == practice.service_type:
        signals['service_type'] = 0.25
    elif conflicts(extracted, practice.service_type):
        signals['service_conflict'] = -0.25
    # +0.15 attachment fuzzy match
    signals['attachment'] = 0.15 * jaccard_tokens(msg.attachments, practice.required_documents)
    # +0.15 temporal overlap
    if practice.created_at - 30d <= msg.date <= practice.closed_at + 14d:
        signals['temporal'] = 0.15
    elif abs(msg.date - practice.created_at).days > 90:
        signals['temporal_far'] = -0.20
    # +0.10 fuzzy name match
    signals['name_fuzzy'] = 0.10 * levenshtein_norm(sender_name, practice.client.name)
    return sum(signals.values()), signals
```

**Soglie**:
- ≥ 0.85 + ≥2 segnali indipendenti → auto-link
- 0.60-0.85 → review umana via UI button "Confermi pratica X?"
- < 0.60 → candidate hidden per analytics

Tabella `whatsapp_practice_candidates` separata (NON update brutale su `practice_id`).

### D. Action queue — UNANIME 3/3 su 3 elementi, leggere divergenze

**Schema concordi**: PK + client_id + practice_id + reason + recommended_action + due_at + evidence JSONB + owner + status + snoozed_until. **Unique constraint dedup** WHERE status IN ('open', 'snoozed').

**Dedup key choice**: Codex `sha256(action_type || practice_id || normalized_topic)` — più granulare.

**Trigger deterministici** (unione 3 panelisti):
1. `silence_72h_after_team_commitment` — promise scaduta senza msg chiusura
2. `client_question_unanswered_24h` — domanda + no team reply
3. `missing_doc_blocker_repeat` — blocker ≥2 volte + practice aperta
4. `payment_unresolved` — `biaya` citato + "belum bayar" senza follow-up
5. `topic_repeated` — stesso topic ≥2 volte in 30gg
6. `stale_practice_active_chat` — practice aperta + chat attiva + no internal update >7gg
7. `sla_breach_72h` — last_client > 72h, last_team < last_client
8. `visa_expiry_60d` — kitas/vitas expiry ≤ 60gg
9. `churn_risk_silence_7d` — DeepSeek

**Tabella `team_promises` ausiliaria** (DeepSeek unique):
```sql
CREATE TABLE team_promises (
  promise_id BIGSERIAL PRIMARY KEY,
  message_id BIGINT REFERENCES whatsapp_message_context_enriched(id),
  client_id BIGINT,
  promise_text TEXT,
  promise_type TEXT,
  due_at TIMESTAMPTZ,
  resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  resolved_by_message_id BIGINT
);
```

Estrai promises da team msg con LLM, marca resolved quando team msg successivo conferma.

**UI framework — UNANIME 3/3 Next.js `apps/wa-dashboard`** (NON Streamlit, NON terminal). Motivo Codex: "per 9-10 persone serve login + ownership + audit + deep link a WA evidence + filtri."

**Notification — convergenza 3/3**:
- **In-app** = sorgente primaria
- **Telegram** = only owner per due/overdue critici (NON gruppo, evita noise)
- **Email digest giornaliero** non realtime
- Telegram chat_id per user → tabella `users.telegram_chat_id`

### E. Validazione 30 giorni — convergenza con target leggermente diversi

| Metrica | Codex | Gemini | DeepSeek | Pick |
|---|---:|---:|---:|---|
| Identity match auto | 35-45% | >60% | 60% | **40% auto + 60% with review** |
| Practice link auto | 30% | >40% | n/a | **30%** |
| Action resolved/dismissed | ≥55% | >80% | >80% | **55% min** (cold start) |
| Dismiss `wrong_link` post-week-2 | <15% | <20% | n/a | **<15%** |
| Time-to-first-response improvement | -20% mediano BH | -25% | -75% (120min→<30min) | **-20% mediano** |
| Re-engaged leads/mese | 10-20 | n/a | ≥8 | **10-15** |
| Team satisfaction | ≥7 da ≥6 utenti | ≥7.5 | ≥7.5 | **≥7 da ≥6 utenti** |

**Codex daily plan (ESSENZIALE)**:
- **gg 1-7**: backfill storico + review 100 candidate practice (silenzioso)
- **gg 8-14**: action queue **read-only** (UI visibile, no Telegram)
- **gg 15-21**: notifiche Telegram solo owner
- **gg 22-30**: confronto baseline vs live, go/no-go

**Go/no-go basato su 3 numeri** (Codex): practice coverage / action precision / follow-up salvati. Resto è diagnostica.

### Idee uniche Round 2

**Codex unico**:
1. `whatsapp_entity_links` separata da `whatsapp_extractions` — permette N:M
2. **Dismiss reason mandatory** in UI: training data
3. **Daily ramp-up structured** 7/14/21/30gg

**DeepSeek unico**:
1. `team_promises` table dedicata
2. `fact_value::jsonb` ricca ({amount, currency, covers})
3. SQL diretto per metriche measurement (window functions)

**Gemini unico**:
1. dbt scheduling (probably overkill)
2. Survey 1-domanda: *"Quanto ti fidi delle informazioni AI durante le chat?"* — trust regina

## Architettura finale — Migration 200 consolidata

```sql
BEGIN;

-- A. Conversation grouping
CREATE TABLE whatsapp_conversations (
  conversation_id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  practice_id BIGINT REFERENCES practices(id),
  phone_e164 TEXT NOT NULL,
  lid TEXT,
  source_group_id TEXT,
  service_line TEXT,
  lifecycle_stage TEXT,
  outcome TEXT,
  owner_team_member TEXT,
  started_at TIMESTAMPTZ,
  last_customer_at TIMESTAMPTZ,
  last_team_at TIMESTAMPTZ,
  confidence NUMERIC(3,2),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON whatsapp_conversations (phone_e164);
CREATE INDEX ON whatsapp_conversations (client_id, lifecycle_stage);
CREATE INDEX ON whatsapp_conversations (practice_id);
CREATE INDEX ON whatsapp_conversations (last_customer_at DESC);

-- B. Extractions append-only (audit-grade)
CREATE TABLE whatsapp_extractions (
  extraction_id BIGSERIAL PRIMARY KEY,
  message_id BIGINT NOT NULL,
  conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  client_id BIGINT REFERENCES clients(id),
  practice_id BIGINT REFERENCES practices(id),
  fact_type TEXT NOT NULL,
  fact_value JSONB NOT NULL,
  mention_text TEXT NOT NULL,
  span_start INTEGER,
  span_end INTEGER,
  language_hint TEXT,
  confidence NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),
  extractor_name TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  review_status TEXT DEFAULT 'pending',
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON whatsapp_extractions (message_id, fact_type);
CREATE INDEX ON whatsapp_extractions (conversation_id, fact_type, confidence DESC);
CREATE INDEX ON whatsapp_extractions (practice_id, fact_type);

-- C. Entity links (N:M extraction ↔ kg_nodes)
CREATE TABLE whatsapp_entity_links (
  link_id BIGSERIAL PRIMARY KEY,
  extraction_id BIGINT REFERENCES whatsapp_extractions(extraction_id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL,
  link_confidence NUMERIC(3,2) CHECK (link_confidence BETWEEN 0 AND 1),
  link_method TEXT NOT NULL,
  reviewer_status TEXT DEFAULT 'unreviewed',
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (extraction_id, entity_id)
);
CREATE INDEX ON whatsapp_entity_links (entity_id);

-- D. Practice candidates (probabilistic)
CREATE TABLE whatsapp_practice_candidates (
  candidate_id BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  message_id BIGINT,
  practice_id BIGINT NOT NULL REFERENCES practices(id),
  confidence NUMERIC(3,2) NOT NULL,
  signals JSONB NOT NULL,
  status TEXT DEFAULT 'pending_review',
  reviewer_id TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON whatsapp_practice_candidates (conversation_id, confidence DESC);
CREATE INDEX ON whatsapp_practice_candidates (status) WHERE status='pending_review';

-- E. Team promises
CREATE TABLE team_promises (
  promise_id BIGSERIAL PRIMARY KEY,
  message_id BIGINT NOT NULL,
  conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  client_id BIGINT REFERENCES clients(id),
  promise_text TEXT NOT NULL,
  promise_type TEXT,
  due_at TIMESTAMPTZ,
  resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  resolved_by_message_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON team_promises (resolved, due_at) WHERE resolved=false;

-- F. Action queue (THE UI Surface)
CREATE TABLE action_queue (
  action_id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  practice_id BIGINT REFERENCES practices(id),
  conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  action_type TEXT NOT NULL,
  reason TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  suggested_message_draft TEXT,
  due_at TIMESTAMPTZ,
  evidence JSONB NOT NULL,
  owner TEXT,
  priority INTEGER DEFAULT 5,
  status TEXT DEFAULT 'open',
  snoozed_until TIMESTAMPTZ,
  dismiss_reason TEXT,
  dedup_key TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  resolution_notes TEXT
);
CREATE UNIQUE INDEX action_queue_open_dedup
  ON action_queue(dedup_key) WHERE status IN ('open', 'snoozed');
CREATE INDEX ON action_queue (owner, status, priority DESC, due_at);
CREATE INDEX ON action_queue (status, due_at);

-- G. Upgrade existing whatsapp_message_context_enriched (additive only)
ALTER TABLE whatsapp_message_context_enriched
  ADD COLUMN IF NOT EXISTS conversation_id BIGINT REFERENCES whatsapp_conversations(conversation_id),
  ADD COLUMN IF NOT EXISTS source_system TEXT,
  ADD COLUMN IF NOT EXISTS external_message_id TEXT,
  ADD COLUMN IF NOT EXISTS sender_role TEXT,
  ADD COLUMN IF NOT EXISTS team_member_id BIGINT,
  ADD COLUMN IF NOT EXISTS identity_confidence NUMERIC(3,2),
  ADD COLUMN IF NOT EXISTS identity_method TEXT,
  ADD COLUMN IF NOT EXISTS language_primary TEXT,
  ADD COLUMN IF NOT EXISTS has_sensitive_pii BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS retention_class TEXT,
  ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS body_redacted TEXT,
  ADD COLUMN IF NOT EXISTS body_hash TEXT,
  ADD COLUMN IF NOT EXISTS ingest_batch_id BIGINT REFERENCES whatsapp_export_batches(id),
  ADD COLUMN IF NOT EXISTS schema_version TEXT DEFAULT 'v1.0';

-- H. User notification prefs
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT,
  ADD COLUMN IF NOT EXISTS notify_in_app BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS notify_telegram BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS notify_email_digest BOOLEAN DEFAULT true;

COMMIT;
-- ROLLBACK section: DROP TABLE IF EXISTS action_queue, team_promises,
--   whatsapp_practice_candidates, whatsapp_entity_links, whatsapp_extractions,
--   whatsapp_conversations CASCADE; ALTER TABLE whatsapp_message_context_enriched DROP COLUMN IF EXISTS ...
```

## KG bridge queries — power-user examples

```sql
-- 1. Per cliente italiano D12, fee storica vs media
SELECT 
  c.full_name,
  AVG((ext.fact_value->>'amount_idr')::numeric) AS avg_fee_idr,
  COUNT(*) AS sample_size
FROM whatsapp_extractions ext
JOIN whatsapp_entity_links lnk ON lnk.extraction_id = ext.extraction_id
JOIN kg_nodes kn ON kn.entity_id = lnk.entity_id 
  AND kn.name ILIKE '%D12%' AND kn.entity_type = 'vitas'
JOIN clients c ON c.id = ext.client_id
WHERE ext.fact_type='biaya'
GROUP BY c.full_name;

-- 2. Pattern bloccanti per KBLI 47299 (co-occorrenza intra-conversation)
SELECT 
  ext_block.fact_value->>'blocker_type' AS blocker,
  COUNT(*) AS occurrences,
  ARRAY_AGG(DISTINCT c.full_name) AS clients
FROM whatsapp_extractions ext_kbli
JOIN whatsapp_extractions ext_block 
  ON ext_block.conversation_id = ext_kbli.conversation_id 
  AND ext_block.fact_type = 'blocker'
JOIN whatsapp_entity_links lnk ON lnk.extraction_id = ext_kbli.extraction_id
JOIN kg_nodes kn ON kn.entity_id = lnk.entity_id 
  AND kn.name = '47299' AND kn.entity_type='kbli'
JOIN clients c ON c.id = ext_kbli.client_id
WHERE ext_kbli.fact_type = 'kbli_code'
GROUP BY blocker
ORDER BY occurrences DESC;

-- 3. Reentry permit questions per E33G clients
SELECT DISTINCT c.full_name, c.id, ext_q.mention_text, ext_q.created_at
FROM whatsapp_extractions ext_visa
JOIN whatsapp_extractions ext_q 
  ON ext_q.conversation_id = ext_visa.conversation_id
  AND ext_q.fact_type = 'client_question'
JOIN clients c ON c.id = ext_visa.client_id
WHERE ext_visa.fact_type = 'visa_type'
  AND (ext_visa.fact_value->>'code') = 'E33G'
  AND ext_q.mention_text ILIKE '%reentry%'
ORDER BY ext_q.created_at DESC LIMIT 50;
```

## Roadmap rivista S1 (R1+R2 fusi)

| Sprint | Task | Effort | Output |
|---|---|---:|---|
| 1.1 | Mass-ingest 188 ZIP (pilot Catia ready) | 4-6h | +30k msg in staging, +500+ docs |
| 1.2 | Migration 200 (8 tabelle + colonne additive) | 6-8h | Schema pronto |
| 1.3 | Identity resolver v1 (phone E.164 + LID + fuzzy + folder) | 10-12h | Match 2% → 40-60% |
| 1.4 | Conversations grouping cron (24h window + lifecycle init) | 6-8h | `whatsapp_conversations` popolato |
| 1.5 | Extraction pipeline Ollama qwen3.5 (9 fact_types) | 10-12h | `whatsapp_extractions` per ogni msg |
| 1.6 | KG bridge: extract → link → INSERT kg_entity_mentions | 4-6h | Query power-user attivabili |
| 1.7 | Practice candidate scorer + review UI | 6-8h | 30% auto-link, 50% review queue |
| 1.8 | Team promises extractor + resolver | 4-6h | Trigger silence_72h accurato |
| 1.9 | Action queue rules engine (9 trigger) | 6-8h | Queue popolata |
| 1.10 | UI MVP estensione `apps/wa-dashboard` | 8-12h | Team vede lista mattina |
| 1.11 | Telegram notification per owner | 2-4h | Push alert |
| 1.12 | Eval set (50 query reali) + baseline metrics | 2-4h | Misurazione oggettiva |

**S1 effort consolidato: 68-94h** (~2-3 settimane full-time).

## S1 daily ramp-up (Codex MUST)

| Giorni | Phase | Activity |
|---|---|---|
| 1-7 | **Backfill silente** | Ingest + identity + extraction batch — zero notifiche |
| 8-14 | **Action queue read-only** | UI visibile, NO Telegram — observe team behavior |
| 15-21 | **Telegram solo owner** | Per-owner notification, NO gruppo |
| 22-30 | **Confronto baseline** | Survey + metriche + go/no-go |

## Open questions

1. Dove gira il backend del copilot? Riusa `apps/backend-rag` (FastAPI esistente) o nuovo modulo `apps/wa-copilot`?
2. UI: Streamlit su Pro+Mini interno, estensione `apps/wa-dashboard` Next.js, o nuovo Next.js `apps/copilot`?
3. Notification: Telegram personal a Antonello, in-app, email, o tutti?
4. Subhi RBAC: scope copilot include lui o no? (probation status)
5. Approval workflow: `suggested_action` deve approvare chi? Owner conversation, or admin?

## Pending Antonello decisions

- [ ] Embedding strategy (raccomando Codex hybrid)
- [ ] Schema migration (raccomando Codex 5-tabelle additive)
- [ ] Start point S1.1 (raccomando ingest 188 ZIP poi identity)
- [ ] Backend host (raccomando estendere `apps/backend-rag`)
- [ ] UI framework (raccomando estensione `apps/wa-dashboard`)
- [ ] Notification channel (raccomando in-app + Telegram P2 escalation)

---

*Document version 1.0 — pre-Round-2 panel sintesi.*
*Authoritative changes only via commit con cicatrix entry.*
