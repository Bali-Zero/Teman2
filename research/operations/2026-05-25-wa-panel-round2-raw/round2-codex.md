La nuova evidenza cambia la priorità: il problema non è “costruire un KG”, è **attaccare i messaggi WA al KG regolatorio già vivo** e poi attaccare entrambi alle pratiche. Io farei Round 2 come pipeline interna per `kita`, non come feature client-facing: fonti, confidence, Drive/WA evidence e review restano backstage; verso `my` arrivano solo status e next steps approvati.

**A. Bridge KG Regolatorio ↔ WA**

Schema minimo:

```sql
create table whatsapp_extractions (
  extraction_id uuid primary key default gen_random_uuid(),
  message_id uuid not null,
  thread_id uuid,
  client_id uuid,
  practice_id uuid,
  fact_type text not null,
  fact_value jsonb not null,
  mention_text text not null,
  span_start int,
  span_end int,
  language_hint text,
  confidence numeric not null,
  extractor_version text not null,
  created_at timestamptz default now()
);

create table whatsapp_entity_links (
  extraction_id uuid references whatsapp_extractions(extraction_id),
  entity_id uuid not null references kg_nodes(entity_id),
  link_confidence numeric not null,
  link_method text not null,
  reviewer_status text default 'unreviewed',
  primary key (extraction_id, entity_id)
);
```

I `fact_type` da estrarre dai WA devono essere pochi e direttamente mappabili ai tipi forti del KG esistente:

`visa_type`: `D12`, `E33G`, `KITAS`, `VITAS`, `PT PMA investor KITAS`.

`kbli_code`: codici espliciti come `47299`, più descrizioni business fuzzy.

`dokumen`: `business plan`, `apostille`, `SKTT`, `NIB`, `NPWP`, `akta`, `passport`, `photo`, `domicile letter`.

`biaya`: importo, valuta, cosa copre, chi paga.

`jangka_waktu`: durata promessa, durata reale, deadline, “berapa hari”, “minggu depan”.

`perizinan/izin_usaha`: licenza, agency, OSS, immigration, notary, tax.

`blocker`: missing doc, mismatch name, foreign shareholder, expired passport, unavailable signature, wrong KBLI, payment pending.

`team_commitment`: “we will send tomorrow”, “I will check”, “already submitted”, with due date inferred.

`client_question`: normalized question class, e.g. `reentry_permit_question`, `apostille_required_question`.

La regola è: **estrazione prima, linking poi**. Non cercare direttamente `kg_nodes` sul raw WA. Prima produci fatti normalizzati con evidence span. Poi fai candidate generation su `kg_nodes` usando alias, exact code, normalized text, e embedding solo come fallback. Per “D12 + business plan italiano + apostille” dovresti ottenere tre estrazioni separate collegate a entity diverse, poi una query aggregata per co-occorrenza storica.

**B. Riuso `kg_entity_mentions`**

Io riuserei `kg_entity_mentions`, non creerei un duplicato. Però separerei chiaramente il livello “vector point”:

```sql
-- message-level mentions
collection_name = 'whatsapp_messages'
point_id = message_id::text

-- optional thread summary mentions
collection_name = 'whatsapp_threads'
point_id = thread_id::text

-- optional attachment OCR mentions
collection_name = 'whatsapp_attachments'
point_id = attachment_id::text
```

Non userei `thread_id` come `point_id` per mention estratte dal singolo messaggio, perché perderesti auditabilità: il team deve poter cliccare “questa entità viene da questa frase in questo messaggio”.

Per `match_type`, non inventerei l’enum: va letto dal DB.

```sql
select distinct match_type, count(*)
from kg_entity_mentions
group by 1
order by 2 desc;

select column_name, data_type, udt_name
from information_schema.columns
where table_name = 'kg_entity_mentions';
```

Se `match_type` è libero, aggiungerei valori come `exact_code`, `exact_alias`, `normalized_alias`, `fuzzy_alias`, `embedding_candidate`, `llm_verified`. Se è enum rigido, mappiamo ai valori esistenti e mettiamo il dettaglio in `whatsapp_entity_links.link_method`.

**C. Practice Linking**

Serve una tabella ponte probabilistica, non un update diretto brutale su `practice_id`.

```sql
create table whatsapp_practice_candidates (
  candidate_id uuid primary key default gen_random_uuid(),
  thread_id uuid,
  message_id uuid,
  practice_id uuid not null,
  confidence numeric not null,
  signals jsonb not null,
  status text default 'pending_review',
  reviewer_id uuid,
  reviewed_at timestamptz,
  created_at timestamptz default now()
);
```

Algoritmo concreto:

1. Candidate generation larga: da sender phone/email, client name, Drive folder name, attachment filename, service token, date window.

2. Filename/service parse: `D12 Catia`, `E33G Marco`, `PT PMA`, `KITAS investor`. Tokenizza service type e nomi; cerca practice compatibili.

3. Attachment match: normalizza nomi allegati e documenti pratica; match su `passport`, `business plan`, `akta`, `NPWP`, `apostille`, più similarity sul nome persona/company.

4. Temporal score: messaggi dentro `practice.created_at - 30d` e `practice.closed_at + 14d` valgono molto; fuori finestra valgono poco ma non zero.

5. Client/person score: telefono WA → person/client è il segnale più forte, ma visto il 2% identity match non deve bloccare tutto.

Scoring iniziale:

```text
+0.35 exact client/person match
+0.25 service_type token match
+0.15 attachment/document match
+0.15 temporal overlap
+0.10 company/person fuzzy name match
-0.25 conflicting service_type
-0.20 outside date window >90d
```

Auto-link solo `confidence >= 0.85` con almeno due segnali indipendenti. `0.60-0.85` review umana. Sotto `0.60` resta candidate nascosto, utile per analytics ma non per produzione.

**D. Action Queue**

Schema:

```sql
create table action_queue (
  action_id uuid primary key default gen_random_uuid(),
  client_id uuid,
  practice_id uuid,
  thread_id uuid,
  action_type text not null,
  reason text not null,
  recommended_action text not null,
  evidence jsonb not null,
  owner_user_id uuid,
  due_at timestamptz,
  status text not null default 'open',
  snoozed_until timestamptz,
  dedup_key text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index action_queue_open_dedup
on action_queue(dedup_key)
where status in ('open','snoozed');
```

Trigger deterministici iniziali:

`silence_72h_after_team_commitment`: ultimo commitment team con due date passata, nessun messaggio successivo del team che chiude.

`client_question_unanswered_24h`: client question rilevata, nessuna risposta team dopo.

`missing_doc_blocker`: blocker documentale ripetuto due volte e pratica ancora aperta.

`payment_or_fee_unresolved`: `biaya` citato + “belum bayar / invoice / transfer” senza follow-up chiuso.

`reentry_permit_repeated`: stesso client/practice chiede stesso topic >=2 volte in 30 giorni.

`stale_practice_active_chat`: pratica aperta, chat attiva, ma nessun status update interno >7 giorni.

Dedup key:

```text
sha256(action_type || ':' || coalesce(practice_id, client_id, thread_id) || ':' || normalized_topic)
```

UX minima: usare **Next.js dentro `apps/wa-dashboard`** se esiste già. Streamlit è più veloce ma diventa un secondo prodotto; per 9-10 persone serve login, ownership, audit, deep link a WA evidence, filtri per owner/status. Terminal TUI no.

UI: lista compatta con colonne `Client`, `Practice`, `Reason`, `Due`, `Owner`, `Evidence`, `Status`. Azioni: `Assign`, `Done`, `Snooze 1d/3d/7d/custom`, `Dismiss`, `Wrong link`. Ogni dismiss richiede reason breve, perché diventa training data. Notification: in-app come fonte primaria; Telegram personale solo per owner + due/overdue critici; email digest giornaliero, non realtime.

**E. Validazione 0-30 giorni**

Baseline attuale:

Identity match: 2%.

Practice link coverage: 0.7%, cioè 3/425.

WA volume: circa 150 msg/day live, 30k storico.

Language detection: baseline inutilizzabile; non usarla come gate.

Target realistici a 30 giorni:

Identity match: 2% → 35-45% auto/high-confidence, 60% includendo review umana.

Practice link coverage: 0.7% → 30% auto/reviewed, 50% candidate >=0.60.

Entity mentions su WA: almeno 40% dei messaggi business-relevant con >=1 linked entity; non contare “ok”, “thanks”, voice-only non trascritto.

Action queue quality: `resolved / (resolved + dismissed)` >= 55% entro giorno 30. Se è sotto 40%, i trigger sono rumorosi.

Dismiss reason: `wrong_client_or_practice` sotto 15% sulle action create dopo la settimana 2.

Time-to-first-response: misurare baseline settimana 0; target -20% mediano su nuovi messaggi business-hour. Non prometterei di più senza routing live.

Follow-up salvati: definizione oggettiva = client silente >72h, AI crea action, team invia follow-up, client risponde entro 7 giorni. Target 10-20 nel primo mese.

Team satisfaction: survey settimanale 1-10, target >=7 da almeno 6 utenti attivi, ma solo come metrica secondaria.

Piano 30 giorni: giorni 1-7 backfill storico + review 100 candidate practice; giorni 8-14 action queue read-only; giorni 15-21 notifiche Telegram solo owner; giorni 22-30 confronto baseline vs live. La decisione go/no-go deve basarsi su tre numeri: practice coverage, action precision, follow-up salvati. Tutto il resto è diagnostica.


