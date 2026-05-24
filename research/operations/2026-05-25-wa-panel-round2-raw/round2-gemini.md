Ecco un proposal concreto e architetturale, strutturato esattamente sulle tue 5 nuove questioni, mirato a risolvere i gap operativi attuali e a capitalizzare sull'enorme potenziale del Knowledge Graph (KG) regolatorio già esistente.

### A. Bridge KG Regolatorio ↔ WA Copilot
Per collegare i 114k nodi regolatori ai messaggi WA in modo scalabile e preciso, non possiamo fare entity linking on-the-fly su ogni messaggio. La strategia è un processo asincrono a due step: estrazione e linking.

1. **Estrazione (`whatsapp_extractions`)**: Un LLM in batch analizza i `wa_messages` per estrarre `fact_type` ad alto valore. I tipi da estrarre devono mappare direttamente le ontologie del KG: `VISA_TYPE` (es. D12, E33G), `KBLI_CODE`, `DOCUMENT_REQ` (es. BP, apostille), `FEE_AMOUNT`, e `DURATION_DAYS`.
2. **Entity Link**: Una pipeline esegue il match tra l'extracted text e il `kg_nodes.name` (o alias). Se la similarity supera una certa soglia, creiamo il record in `kg_entity_mentions`.

In questo modo, una query come *"KBLI 47299 + cliente straniero: ci sono pattern bloccanti?"* diventa una banale JOIN SQL tra `wa_messages` ↔ `kg_entity_mentions` ↔ `kg_nodes` (filtrando per `node_type = 'kbli' AND name = '47299'`), permettendo al RAG di recuperare istantaneamente sia la normativa (edge regolatori) sia lo storico risoluzioni su WA.

### B. Pattern riusabilità `kg_entity_mentions`
La tabella `kg_entity_mentions` esistente è perfetta come ponte universale. Per integrare WA senza duplicare schemi:
- **`collection_name`**: Utilizza rigorosamente `'wa_messages'` (nome tabella sorgente).
- **`point_id`**: Utilizza il `message_id` (UUID). Mappare a livello di singolo messaggio è fondamentale perché permette di ereditare istantaneamente il timestamp, il sender e l'ordine nel thread, fondamentali per capire *chi* ha menzionato un'entità e *quando*.
- **`match_type`**: Se non presenti, estendi l'enum esistente per includere: 
  - `'EXACT'` (es. menzione diretta di "E33G")
  - `'FUZZY_TRIGRAM'` (match basato su pg_trgm su typo nei messaggi WA)
  - `'LLM_EMBEDDING'` (link dedotto semanticamente)

### C. Strategia di Practice Linking (da 0.7% a +50%)
Il link manuale delle practices fallisce perché il team non ha tempo. L'algoritmo deve essere probabilistico, girare in background e proporre link auto-approvati se la confidence è alta.

1. **Candidate Generation (Metadata)**: Partiamo associando il `client_id` (identity match). Se il numero WA o il nome contatto matchano un cliente con pratiche aperte, quelle pratiche diventano candidate.
2. **Fuzzy & Pattern Match**: Cerca nel testo di WA e nei nomi degli allegati (es. "D12", "KITAS", "RPTKA") per matchare il `service_type` o la description in `practices`.
3. **Temporal Correlation**: Restringi il campo. Un documento inviato il 15 Maggio appartiene plausibilmente a una pratica creata/attiva a Maggio (`msg_date BETWEEN p.created_at AND p.resolved_at`).

**Calcolo Confidence**: 
`Score = (0.5 * client_match) + (0.3 * text_attachment_match) + (0.2 * temporal_proximity)`
- **Score > 0.85**: Auto-link (scrittura diretta di `practice_id` sul WA thread).
- **Score tra 0.6 e 0.85**: Manda in `action_queue` per "Human Review" con un bottone UI "Confermi che questa chat riguarda la pratica X?".

### D. Action Queue: Schema concreto + UI minimo
L'Action Queue deve trasformare le intuizioni passive dell'AI in task operativi ineludibili.

**Schema SQL**:
```sql
CREATE TABLE action_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES crm_client(id),
    practice_id UUID REFERENCES practices(id), -- Nullable
    reason VARCHAR(255) NOT NULL, -- es. 'SLA_VIOLATION_72H', 'PRACTICE_LINK_REVIEW'
    recommended_action TEXT NOT NULL,
    evidence JSONB, -- es. {"wa_thread_id": "123", "last_msg": "Aiuto!"}
    due_date TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, DISMISSED, RESOLVED, SNOOZED
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Dedup logic a livello di DB: non inserire se esiste già un'azione PENDING per la stessa combo
CREATE UNIQUE INDEX idx_action_dedup ON action_queue (client_id, practice_id, reason) WHERE status = 'PENDING';
```

**Trigger Rule Deterministiche** (eseguite da CRON o dbt ogni ora):
- *SLA Breach*: `last_client_msg_date < NOW() - INTERVAL '72 hours' AND last_team_reply_date < last_client_msg_date`.
- *Missing Document*: Estratto da WA che un documento X è richiesto, ma non risulta uploadato in Drive/CRM entro 7 giorni.

**UI e Notifiche**:
- **Framework UI**: Per un team di 9-10 persone che deve operare in velocità, usa la **Next.js app esistente (`apps/wa-dashboard`)**. Streamlit è ottimo per la data science, ma limitato per creare workflow operativi custom (snooze, assign, inline chat view).
- **Notifiche**: **Telegram Bot** per le urgenze (`due_date < NOW()`), postando nel gruppo del team. Le email vengono ignorate.

### E. Validazione Empirica 0-30 Giorni
Per misurare oggettivamente il successo a 30 giorni e validare l'adozione al "Bali Zero scale" (150 msg/day), ecco le metriche:

1. **Identity & Practice Coverage**:
   - *Identity Match*: Target > 60% (attuale 2%).
   - *Practice Link Match*: Target > 40% (attuale 0.7%).
2. **Action Queue Engagement**:
   - *Resolution Rate*: Target > 80% delle `action_queue` items processate in < 24h.
   - *Dismissal Rate*: Se > 20% dei suggerimenti vengono "Dismissed", la logica di trigger è troppo rumorosa e va stretta.
3. **Time-to-resolution (TTR)**:
   - Misurare il tempo medio dal primo messaggio del cliente al messaggio di "pratica avviata" o "problema risolto". Target realistico: riduzione del 25% sfruttando il recupero di contesto istantaneo dal RAG.
4. **Follow-up Reactivation (Revenue Impact)**:
   - Contare il numero di pratiche/deal in stallo che sono stati chiusi positivamente entro 7 giorni dopo un "ping" suggerito dall'AI in `action_queue`.
5. **Team Satisfaction (Qualitativo ma critico)**:
   - Survey di 1 sola domanda post-lancio (1-10): *"Quanto ti fidi delle informazioni suggerite dall'AI durante le chat clienti?"* (Il trust è la metrica regina per l'adozione). Target: > 7.5.
