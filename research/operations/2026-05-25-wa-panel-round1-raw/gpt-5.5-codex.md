**Tesi**
Il valore non è nei “30k messaggi” come archivio RAG. Il valore nasce quando li trasformi in una memoria operativa event-sourced: ogni messaggio diventa evidenza temporale collegata a cliente, pratica, servizio, documento, prezzo, rischio, promessa fatta, prossima azione e outcome. Le aziende enterprise nel 2026 non vendono più “search nei transcript”: Salesforce Conversation Insights estrae obiezioni, pricing, next step e menzioni decision-maker e usa questi segnali per aggiornare CRM, deal guidance e follow-up contestuali; Gong usa agenti come Deal Monitor per warning su ghosting, pricing non discusso, red flag e stage stalled; Zendesk classifica intent, sentiment, lingua ed entità per routing/priorità; Intercom usa topic clustering, query type e suggerimenti settimanali per chiudere gap di automazione. Questo è il benchmark reale da copiare, non “chatbot sopra WhatsApp”. ([salesforce.com](https://www.salesforce.com/products/sales-conversation-intelligence/)) ([help.gong.io](https://help.gong.io/docs/understanding-the-ai-deal-monitor)) ([support.zendesk.com](https://support.zendesk.com/hc/en-us/articles/4550640560538-Automatically-classifying-customer-intent-sentiment-and-language)) ([intercom.com](https://www.intercom.com/help/en/articles/10576273-how-to-analyze-fin-and-get-insights-from-3-ai-powered-dashboards))

**Pipeline Consigliata**
Tieni `whatsapp_message_context_enriched` come tabella messaggi normalizzata, ma non gonfiarla con 80 colonne AI. Aggiungi layer separati.

`whatsapp_conversations`: `conversation_id`, `client_id`, `practice_id`, `phone_e164`, `lid`, `source_group_id`, `service_line`, `lifecycle_stage`, `owner_team_member`, `started_at`, `last_customer_at`, `last_team_at`, `outcome`, `confidence`.

`whatsapp_message_context_enriched` upgrade minimo: `conversation_id`, `source_system` (`brevo`, `baileys`, `drive_import`), `external_message_id`, `sender_role` (`client`, `team`, `internal_group`, `vendor`), `team_member_id`, `identity_confidence`, `identity_method`, `language_primary`, `has_sensitive_pii`, `retention_class`, `legal_hold`, `body_redacted`, `body_hash`, `ingest_batch_id`, `schema_version`.

`whatsapp_attachments`: message, media path, OCR status, document type, extracted IDs hashed, linked Drive file, redaction status.

`whatsapp_extractions`: append-only facts: `message_id`, `conversation_id`, `extractor_name`, `model`, `prompt_version`, `fact_type`, `value_json`, `confidence`, `evidence_start`, `evidence_end`, `review_status`. Questo evita di sovrascrivere verità storica quando cambi modello.

`conversation_rollups`: una riga per stato operativo: summary breve, open questions, missing docs, promised action, due date, blocker, urgency, price_mentions, objection_tags, next_best_action, evidence_message_ids.

`action_queue`: l’unica cosa che il team deve vedere ogni mattina: `client`, `practice`, `reason`, `recommended_action`, `due_at`, `evidence`, `owner`, `status`. Nessun auto-update distruttivo in CRM senza review.

**Estrazioni ROI-Positive**
Alta priorità: identity resolution, sender role, lingua, service/practice type, lifecycle stage, document requested/provided/missing, next action + due date, price/discount/payment signal, objection category, blocker, urgency/escalation, customer silence, team silence, outcome won/lost/completed, consent/opt-out, proof-of-service milestones.

Media priorità: sentiment solo a livello conversazione o ultimo blocco cliente, non per messaggio; topic clustering settimanale; quality score per collaboratore; procedure-step mining dai casi chiusi.

Bassa priorità/vanity: emotion fine-grained per messaggio, “personality profiling”, word cloud, summary lunghi senza evidence IDs, prediction churn ML prima di avere outcome puliti. Gong stesso basa deal scoring su segnali storici, attività, progressione e conversazioni, ricalcolati giornalmente: senza outcome labels locali, meglio regole trasparenti che un modello finto sofisticato. ([help.gong.io](https://help.gong.io/docs/explainer-under-the-hood-of-deal-likelihood-scores))

**Embeddings**
Non re-vectorizzare tutto in Qdrant cloud con raw WhatsApp. Hai vincolo “no cloud egress” per dati sensibili: per corpus clienti usa embeddings locali, per esempio `bge-m3` o `multilingual-e5-large` via SentenceTransformers/Ollama-side service, in Qdrant locale o pgvector locale. Mantieni la collection esistente `text-embedding-3-small` congelata per contenuti non sensibili o già sanificati. OpenAI conferma che `text-embedding-3-small` è 1536 dimensioni e `3-large` 3072, ma il punto qui non è il benchmark astratto: è la sovranità dati. Fonte: [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings#how-to-get-embeddings).

Indicizzazione utile: non “one vector per message” soltanto. Crea tre livelli: messaggio atomico per evidence retrieval, window conversazionale da 10-30 messaggi per contesto, rollup conversazione/pratica per search operativa. Retrieval ibrido: metadata filter (`service_line=D12`, `stage=docs_missing`, `language=it`) + BM25/keyword per nomi documenti + vector.

**Knowledge Graph**
Ontologia minima: `Person`, `PhoneAlias`, `Company`, `TeamMember`, `Conversation`, `Message`, `Attachment`, `Document`, `ServiceLine`, `Practice`, `ProcedureStep`, `RegulatoryRequirement`, `Intent`, `Objection`, `Quote`, `Invoice`, `Payment`, `Outcome`, `EvidenceSpan`.

Relazioni: `PERSON_HAS_PHONE`, `PERSON_APPLIES_FOR_SERVICE`, `CONVERSATION_HANDLED_BY`, `MESSAGE_MENTIONS_ENTITY`, `CLIENT_REQUESTED_SERVICE`, `TEAM_REQUESTED_DOCUMENT`, `CLIENT_PROVIDED_DOCUMENT`, `PRACTICE_BLOCKED_BY`, `MESSAGE_EVIDENCES_STEP`, `QUOTE_ACCEPTED`, `INVOICE_PAID`, `OUTCOME_OF_CONVERSATION`, `PROCEDURE_STEP_DERIVED_FROM_CASE`. Ogni relazione importante deve avere `valid_from`, `valid_to`, `confidence`, `evidence_message_ids`. Il KG deve essere auditabile, non solo bello in graph view.

**Agentic Loops**
Event-driven ingest agent: ack rapido da webhook, enqueue processing async. Meta Cloud API è webhook-heavy; il tuo handler non deve aspettare OCR o LLM. ([meta-preview.mintlify.io](https://meta-preview.mintlify.io/docs/whatsapp/cloud-api/overview))

Identity resolver: su ogni nuovo messaggio e nightly batch. Usa phone canonical, LID map, sender name, Drive folder path, attachment names, practice references. Obiettivo 30 giorni: portare match da 2% a 40-60%, non 100%.

Extraction agent locale: Ollama/qwen3.5 per JSON schema stretto, con confidence e evidence. Batch sui 188 export, streaming sul live.

Next-best-action agent: cron 07:30 e trigger su eventi: cliente non risposto >24h, team promessa scaduta, documento mancante, payment reminder, visa expiry/compliance. Output solo `action_queue`.

Deal intelligence agent: daily scoring semplice: response latency, number of touches, price objection, docs provided, explicit urgency, decision-maker/company owner present, stalled days, competitor mention. Gong espone warning simili perché sono interpretabili e azionabili. ([help.gong.io](https://help.gong.io/docs/using-deal-warnings))

Procedure miner: weekly sui casi completati. Estrae “D12 successful path”, “E23 blocker patterns”, “company setup KBLI flow”. Human approve prima di promuovere a Zantara/NotebookLM.

Compliance archivist: nightly PII classification, redaction, retention class, legal-hold bundle. WhatsApp richiede opt-in, rispetto opt-out, template approvati fuori dalla finestra 24h e policy/privacy notice; UU PDP richiede base legale, diritti data subject e disciplina su accesso/cancellazione. ([whatsappbusiness.com](https://whatsappbusiness.com/policy/)) ([pasal.id](https://pasal.id/peraturan/uu/uu-no-27-tahun-2022))

**Privacy**
Raw message body e allegati: cifrati, accesso ristretto, audit log. Derived analytics: pseudonimizzati con `client_key` e phone hash con pepper. Documenti sensibili: passport/NPWP/NIB/akta mai in prompt cloud; OCR locale; nei rollup salva “passport received” e document type, non numero documento. A query-time: reveal PII solo per ruolo autorizzato su `kita`; `my.balizero.com` mostra solo status, next steps e download mediati dal backend, mai Drive ID, raw source trace o OCR backstage.

**30-60-90**
30 giorni, 45-70h dev: ingest idempotente dei 188 export, conversazioni canoniche, identity resolver v1, extraction JSON per next action/document/payment/objection, action queue interna. Return: recupero follow-up persi, meno dipendenza da memoria del team, 5-10h/settimana risparmiate, primi lead storici riattivabili.

60 giorni, +60-90h: dashboard BI: deal velocity per servizio, conversione per team member, obiezioni prezzo, document blockers, response SLA, lost reasons. KG v1 cliente-servizio-documento-outcome. Return: pricing e playbook reali; anche 3-5 conversioni/mese recuperate su visa/company possono ripagare il lavoro.

90 giorni, +80-120h: procedure miner approvato, Zantara corpus sanificato, eval set multilingua, legal proof bundle per pratica, retention automation, template follow-up WhatsApp utility/compliance. Return: assistente cliente ground-truth, onboarding collaboratori più veloce, difendibilità legale.

**Moat**
Lets Move/Emerhub/Flado possono copiare ads, Trello, Google Sheet e forse un chatbot. Non possono copiare 4 anni di micro-evidenze: quali frasi convertono italiani vs russi, quali documenti bloccano D12, quali collaboratori risolvono più velocemente, quali segnali anticipano mancato pagamento, quali passaggi reali fanno completare una KITAS. Il moat è outcome-labeled operational memory + procedure graph + evidence-backed next action, aggiornato ogni giorno.

**Pitfall / Non Fare**
Non partire da chatbot cliente. Parti da team copilot interno. Non scrivere automaticamente CRM/pratiche da LLM: crea suggerimenti con evidence e review. Non mischiare chat interne “INVOICE BALI ZERO” con chat cliente senza `sender_role`, altrimenti addestri segnali tossici. Non fidarti del sentiment monolingua: Gong stesso segnala limiti su warning in lingue non inglesi; il tuo corpus è multilingua. Non fare KG enorme prima della action queue. Non mettere raw WhatsApp in NotebookLM/Claude se contiene sensitive PII. Non rendere visibili sorgenti interne su `my`. Non misurare successo in “numero di messaggi processati”: misura follow-up chiusi, documenti mancanti risolti, lead riattivati, tempo risposta, revenue attribuita, dispute risolte con proof bundle.


