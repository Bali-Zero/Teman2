# Brief: come trasformare 30k+ messaggi WhatsApp clienti storici in valore strategico

## Contesto sistema (Bali Zero / Nuzantara, 2026-05-25)

**Chi siamo**: agenzia indonesiana visa+company+tax+property. Solo-dev (Antonello) + 9-10 collaboratori. Stack AI: Claude OAuth MAX, Gemini 3.1 Pro, DeepSeek V4 Pro, NotebookLM (60 NB, ~3618 sources), Ollama locale (qwen3.5/deepseek-r1/qwen2.5vl). Postgres su Fly.io, repo monorepo Python + TS.

**Stack consumer/CRM esistente**:
- `clients` table (~11.680 clienti, full_name + phone canonical + drive folder)
- `whatsapp_message_context_enriched` (16.655 msg live capture, 14.847 da meta_cloud_api + 1.808 da wa-mirror Baileys)
- `whatsapp_contacts` (8.639), `whatsapp_team_sessions` (8.212 sessioni Baileys), `whatsapp_lid_phone_map` (141)
- `practices` (pratiche visa/company), `conversation_messages`, `conversation_threads`
- Channel live attivi: WhatsApp (Brevo Cloud API), Telegram, Instagram, Web Chat
- Identity resolution: solo 331/16655 (2%) ai client_id matchati
- OCR Phase 1.5 (qwen2.5vl:7b) per allegati cliente — già operativo (cicatrix 2026-05-18)
- Knowledge Graph (kg_entities/kg_relations) backed by SQLite, alimentato da NER worker qwen3.5
- Vector DB: Qdrant cloud (93.283 vectors text-embedding-3-small 1536d, FROZEN)
- RAG backend FastAPI con LangGraph orchestration

## Materiale da valorizzare

**Volume**: 30k+ messaggi tra:
- **3 batch già ingested 21 mag** (chat collettive aziendali):
  - YOPO company (12 msg, ago 2022-mag 2026, 17 senders interni)
  - E-ITK ONLINE (670 msg, feb 2024-mag 2026, 13 senders)
  - INVOICE BALI ZERO (26.061 msg, ago 2022-mag 2026, 17 senders — Sahira 6574, Amanda 5023, Ari 4572, Antonello 3078, Adit 2638)
- **188 chat individuali cliente in coda** (1.88 GB scaricate da Drive, mai ingested), folder per team member (Adit 2 / Ari 30 / Krisna 52 / Sahira 51 / Surya 54). Esempio: Catia Sabatini D12 visa, periodo 17 giorni, 4 allegati (passport photos, CV)
- **Live capture continua**: ~150-300 msg/giorno via Brevo Cloud API + Baileys mirror

**Caratteristiche dati**:
- Lingue: bahasa indonesia (team interno), inglese (cliente expat), italiano (cliente IT), russo, francese, spagnolo, tedesco — mix in singole conversation
- Domini: visa application (D12, C1, KITAS E23/E31/E33F/E33G), company setup (PMA, KBLI), tax (SPT/PPh/PPN), property due diligence
- Allegati: passport, CV, akta notarile, NIB, NPWP, fatture, photo selfie+identità
- Timeline asimmetrica: alcune chat 4 anni (2022-2026), altre 17 giorni
- Sentiment: pre-sale negoziazione, mid-service problem solving, post-service compliance reminder

**Vincoli legali/etici**:
- UU PDP (Indonesia data protection law) — analogo GDPR
- Cloud egress vietato per dati cliente sensitive (Symbiosis Law 2: OSINT blindato Pro+Mini, NO frontend, NO team)
- Anthropic SDK paid-tier banned — solo OAuth CLI via subprocess o auth_token SDK
- Ollama locale OK per qualunque processing (Pro+Mini sovereignty)

## Domanda (ricerca profonda + system-fit)

**Come massimizzare il valore di questo corpus 30k+ messaggi WhatsApp** (clienti storici + live capture continua) per:

1. **Operatività interna** — drive next-best-action al team (reminder follow-up, lead qualification, churn prediction, upsell triggers)
2. **Sales/business intelligence** — pattern di vendita, deal velocity, objection categories, pricing elasticity, conversion funnel
3. **Knowledge asset** — costruire ground-truth regulatory/procedure (es. workflow KITAS step-by-step da chat reali), corpus addestramento per Zantara assistente cliente
4. **Compliance/auditability** — proof-of-service per dispute legali, retention policy, PII protection
5. **Strategic moats** — cosa NESSUN concorrente (Lets Move Indonesia, Emerhub, Flado) può replicare se ha solo Google Sheet+Trello

## Cosa serve dal panelist

1. **Deep research best practices 2026** (data dal vivo, NON memoria training): come stato dell'arte enterprise tratta WhatsApp business corpus (es. Salesforce Conversation Insights, Gong.io, Chorus.ai, custom LLM pipelines, retrieval+entity-extraction, RAG-over-conversations, agentic next-best-action). Cita fonti/aziende specifiche se possibile.

2. **System-fit analysis**: dato lo stack Bali Zero descritto sopra (Postgres+Qdrant+NotebookLM+Ollama locale+OAuth Claude), come dovrei strutturare la pipeline. Concretamente:
   - Schema upgrades su `whatsapp_message_context_enriched`?
   - Quali estrazioni (entità/intent/sentiment/topic) sono ROI-positivo vs vanity?
   - Embeddings: re-vectorize con conversation-aware model vs riusare 3-small?
   - Knowledge Graph: quale ontology cliente↔servizio↔intent↔outcome?
   - Agentic loops che agenti dovrebbero girare (cron daily? event-driven?)
   - Privacy: cosa va anonimizzato a riposo vs at-query-time?

3. **Priorità ROI 30-60-90 giorni** con stima effort (h dev) e expected return (qualitativo o $)

4. **Pitfall noti** (cose viste fallire in aziende simili — privacy leak, hallucinated CRM updates, over-engineering, latenza inaccettabile, ROI invisibile)

5. **Cosa NON fare** — anti-pattern frequenti

Risposta tecnica concreta, 800-1500 parole, no fluff, no boilerplate disclaimers. Cita esempi reali se sai di aziende che hanno fatto lo stesso.
