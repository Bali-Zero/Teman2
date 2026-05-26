### A. Bridge from 114K regulatory KG to 30K WA messages

**Extraction layer**: add `whatsapp_extractions` to house facts swizzled from each message, then link into the existing `kg_entity_mentions` table.

```sql
CREATE TABLE whatsapp_extractions (
    id SERIAL PRIMARY KEY,
    msg_id INT NOT NULL REFERENCES wa_messages(id),
    practice_id INT REFERENCES practices(id),  -- filled later (C)
    entity_id INT REFERENCES kg_nodes(id),    -- filled if match found
    fact_type  TEXT NOT NULL,                 -- 'visa_type','kbli','document','fee','duration','penalty'
    fact_value TEXT,                          -- extracted string or normalized value
    confidence FLOAT CHECK (confidence BETWEEN 0 AND 1),
    matched_at TIMESTAMP DEFAULT now()
);
```

**Matching into `kg_entity_mentions`**: reuse the existing table without schema change.
- `collection_name = 'wa_messages'`
- `point_id = msg_id`
- `mention_text = substring from message that triggered the fact`
- `match_type = 'llm'` (or `'regex'` if using patterns; existing enum already contains both)
- `confidence` from the NER/extraction step

**How to answer the example queries**:
- *Apostille usage*: `SELECT count(*) FROM kg_entity_mentions WHERE entity_id = (SELECT id FROM kg_nodes WHERE name ILIKE '%apostille%') AND collection_name='wa_messages'`  
  join with `whatsapp_extractions` for fee values: `SELECT avg(fact_value::numeric) FROM whatsapp_extractions WHERE fact_type='fee' AND entity_id = <apostille_id>`.
- *KBLI 47299 blocking patterns*: retrieve all messages where `whatsapp_extractions.fact_type='kbli' and fact_value='47299'`, then look for follow‑up team messages containing keywords like “tolak”,“bermasalah”.
- *E33G re‑entry questions*: filter `wa_messages` where `whatsapp_extractions.fact_type='visa_type' AND fact_value='E33G'` AND message text contains “reentry” or “re‑entry permit”; aggregate linked `kg_entity_mentions` for “reentry permit” to see which response templates were used afterward.

`fact_type` candidates: precisely the node labels in `kg_nodes.node_type`—`dokumen`, `kbli`, `izin_usaha`, `biaya`, `jangka_waktu`, `vitas`, `kitas`, etc.

---

### B. Reuse of `kg_entity_mentions`

Zero new tables. The existing schema already supports `(entity_id, collection_name, point_id, mention_text, confidence, match_type)`.  
- `collection_name` for WhatsApp: `'wa_messages'` (new collection).  
- `point_id`: the primary key of `wa_messages` (message‑level; you can later roll up to `thread_id` if needed).  
- `match_type` enumerates `ner`, `regex`, `manual`, `llm`—confirmed by checking production `match_type` distinct values. `llm` will be the primary match for extracted facts.

No duplication; we simply INSERT rows with `collection_name='wa_messages'` after each extraction, exactly as was done for the regulatory corpus.

---

### C. Practice linking algorithm

Given a WhatsApp chat (a thread or a group of messages from the same folder), extract candidate `practice_id` with a weighted multi‑signal approach:

1. **Filename pattern**  
   Parse attachment names: regex `(D12|E33G|C313|KITAS|VITAS|...)\s+([A-Za-z]+)`.  
   Query:  
   ```sql
   SELECT p.id FROM practices p JOIN clients c ON p.client_id = c.id
   WHERE p.service_type = <extracted_type>
     AND c.name ILIKE '%' || <extracted_name> || '%'
   ```
   Score: Levenshtein distance between client name and extracted name (0→1.0, 3→0.5, etc.).

2. **Attachment fuzzy match**  
   Compare each attachment filename (after stemming and stop‑word removal) against the `documents` array of each candidate practice. Jaccard similarity of tokens.

3. **Temporal correlation**  
   If the practice has `start_date`/`end_date`, check overlap with message timestamp. Score = 1 if msg inside range, max(0, 1 − (days outside)/30).

Combine: `score = 0.5 * fname_score + 0.3 * fuzzy_doc_score + 0.2 * temporal_score`.  
Threshold for auto‑link: 0.70. Below that, push to `practice_linking_review` table for manual confirmation.

After linking, backfill `whatsapp_extractions.practice_id` and optionally add a `practice_id` column directly to `wa_messages` for fast queries.

---

### D. Action queue schema, triggers, dedup, UI, notifications

```sql
CREATE TABLE action_queue (
    id            SERIAL PRIMARY KEY,
    client_id     INT NOT NULL REFERENCES clients(id),
    practice_id   INT REFERENCES practices(id),
    reason        TEXT NOT NULL,              -- e.g., 'silence>72h_unresolved_promise'
    recommended_action TEXT NOT NULL,         -- human‑readable
    due_date      TIMESTAMPTZ,
    evidence      JSONB,                     -- msg_ids, extraction_ids, etc.
    owner         TEXT,                      -- team member login
    status        TEXT DEFAULT 'open',        -- open, in_progress, done, snoozed, dismissed
    snooze_until  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
-- Dedup index: one open action of the same reason per client per week
CREATE UNIQUE INDEX idx_action_queue_dedup
  ON action_queue (client_id, reason, (created_at::date))
  WHERE status IN ('open','snoozed');
```

**Deterministic triggers**:
- **Silence >72h + unresolved promise**:  
  Track promises in `team_promises`:
  ```sql
  CREATE TABLE team_promises (
      id SERIAL PRIMARY KEY,
      msg_id INT REFERENCES wa_messages(id),  -- team message containing promise
      client_id INT,
      promise_text TEXT,
      due_date TIMESTAMPTZ,
      resolved BOOLEAN DEFAULT false
  );
  ```
  Cron job every hour: for any promise past due AND no subsequent customer message containing thanks/acknowledgment within 24h, insert `action_queue` row with `reason='silence>72h_unresolved_promise'`.

**Snooze/Dismiss UX**: Buttons in UI call a simple API endpoint that updates `status` and `snooze_until`. Dismiss sets `status='dismissed'`.

**UI**: Add an `ActionQueue` page inside the existing Next.js `apps/wa-dashboard` (shadcn/ui table). Minimal overhead; team already uses it for chats.  
**Notifications**: Telegram personal via Bot API (store `telegram_chat_id` per user). No extra app installation needed; team already uses Telegram.

---

### E. 30‑day validation metrics, baselines, targets

| Metric                                | Baseline (today)       | 30‑day target |
|---------------------------------------|------------------------|---------------|
| Identity match % (entity extracted)   | 2%                    | 60%           |
| Action‑queue resolved/dismissed ratio | N/A (new)             | >80% handled  |
| Time‑to‑first‑response (median)       | ~120 min (estimate)   | <30 min       |
| Re‑engaged leads (dormant >7d reactivated by AI suggestion) | 0  | ≥8 per month  |
| Team satisfaction (1‑10 survey)       | N/A                   | ≥7.5          |

**Measurement**:
- Identity match: `SELECT count(distinct msg_id) FROM kg_entity_mentions WHERE collection_name='wa_messages'` / total WA messages.
- Resolved/dismissed: `SELECT status, count(*) FROM action_queue GROUP BY status` weekly.
- Time‑to‑first‑response: timestamp difference between first customer message of a thread and first non‑customer reply; compute with a window function over `thread_id`.
- Re‑engaged leads: mark a lead as “re‑engaged” if `action_queue` trigger for silence results in customer reply within 48h; log these.
- Survey: anonymous Google Form sent day 30.

All metrics shown on a daily refresh dashboard (Metabase or a simple Next.js route). We’ll iterate based on team feedback after the first week.
