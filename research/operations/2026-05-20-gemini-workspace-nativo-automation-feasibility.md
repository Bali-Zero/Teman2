---
date: 2026-05-20
domain: operations
client_case: crm-workspace-ai-snapshots-pipeline-feasibility
sources: 18
---

# Gemini Workspace nativo (Drive AI / Ask Gemini in Drive) — feasibility per automatismo programmabile

**Status**: draft · **Author**: deep-researcher (Antonello/Bali Zero) · **Question**: la sintesi multi-file che la UI mostra a `drive.google.com/drive/ai/<folder_id>` è raggiungibile via API in modo programmabile per popolare `crm_workspace_ai_snapshots`? Se no, qual è il path canonico Google-blessed?

## TL;DR (verdict per le 6 Q)

- **Q1 — Public API per Drive AI native folder synthesis**: NO. La feature "Ask Gemini in Drive" (GA aprile 2026, [Workspace Updates](https://workspaceupdates.googleblog.com/2026/04/ask-gemini-in-drive-now-generally-available.html)) è una superficie UI 1P (Wiz framework + Protobuf streaming + token SAPISID dinamici) — nessun endpoint REST documentato del tipo `POST /v1/folders/{folderId}:synthesize`. Confermato da Gemini 3.1 Pro Preview interrogato in questo turn (output `/tmp/deep-research-gemini-workspace-q1-out.txt`).
- **Q2 — Pattern canonico Gemini API multi-file**: Files API (50 MB/PDF, 1000 pp/PDF, ~258 token/pagina, 48h retention, 20 GB storage per project) + singolo `generateContent` su `gemini-3.1-pro-preview` con context window 1M+ token. Caching `cachedContents` utile solo se prompt > 4096 token e riuso ripetuto (TTL default 1h, configurabile).
- **Q3 — Browser automation viability**: SCONSIGLIATA. Tre rischi convergenti: (a) Workspace AUP vieta esplicitamente accesso "via metodi diversi dall'interfaccia che forniamo" e bot/scraping ([AUP §automated access](https://workspace.google.com/intl/en/terms/use_policy.html)); (b) UI è renderizzata via framework proprietario Wiz con classi CSS hash-mutate (selettori instabili); (c) telemetria reCAPTCHA Enterprise v3 rileva entropia non-organica → shadowban / 429 / disabilitazione feature AI. Anche con `claude-in-chrome` MCP su sessione reale.
- **Q4 — NotebookLM API come alternativa**: PARZIALE. NLM ha MCP attivo (`mcp__notebooklm-mcp__*`) e `cross_notebook_query` esiste, ma upload batch programmatico di 200 cartelle/giorno non è il caso d'uso target di NLM (free OAuth ma rate-limit aggressivi non documentati; lato "studio" più che pipeline). Utile per casi singoli ad-hoc, non per cron 6h.
- **Q5 — Architettura raccomandata**: Opzione E refined: Service Account Drive API (`files.list` con `q='{folderId}' in parents`) → download blob → Files API upload → `generateContent` su Gemini 2.5 Flash (paid tier) con `responseSchema` Pydantic + Drive `changes.watch` per trigger event-driven con webhook su Pro (channel TTL 24h folder watch, renewal manuale obbligatorio).
- **Q6 — Costi**: Gemini 3.1 Pro Preview $54/cliente/anno (refresh giornaliero, scenario B) → proibitivo a scala. Gemini 2.5 Flash $8.61/cliente/anno (B) o $3.36/cliente/anno (C, weekly+webhook). Vertex AI Search Enterprise tier free copre interamente lo scenario C (78 query/giorno × 30 = 2340/mese < 10k free quota), ma è 1 query = 1 sintesi senza contesto multi-document iniettato — diverso prodotto. **Cheapest production-ready: Gemini 2.5 Flash paid tier, $8.61/cliente/anno scenario B**.

## Q1 — Public API per Drive AI native folder synthesis?

**Risposta secca: NO endpoint REST pubblico.**

La feature "Ask Gemini in Drive" (URL pattern `drive.google.com/drive/ai/<folder_id>`) è disponibile dall'aprile 2026 per Workspace Business Standard+, Enterprise, e Google AI Pro/Ultra ([annuncio GA](https://workspaceupdates.googleblog.com/2026/04/ask-gemini-in-drive-now-generally-available.html)). Quote testuale dell'annuncio: *"This feature is available by default if Gemini for Workspace in Drive is enabled"* — focus end-user e admin, zero menzioni di accesso programmatico.

Verifiche fatte:
- **Gemini API doc** ([ai.google.dev/gemini-api/docs/document-processing](https://ai.google.dev/gemini-api/docs/document-processing)): "The API requires explicit file uploads or inline data for each document. No dedicated folder synthesis endpoint or integration with Google Drive's native folder view".
- **Workspace Add-ons SDK** ([developers.google.com/workspace/add-ons](https://developers.google.com/workspace/add-ons/overview)): nessun riferimento a Gemini in Drive folder synthesis.
- **Gemini Enterprise Agent Platform** (ex-Vertex AI, rebrand Cloud Next 2026, [blog announcement](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform)): espone agent orchestration e model garden 200+ modelli, ma non un endpoint che chiama nativamente la sintesi UI di Drive.
- **Gemini 3.1 Pro Preview interrogato in questo turn**: "Non esiste alcun endpoint REST pubblico tipo `POST /v1/folders/{folderId}:synthesize` nelle API standard di Google Drive. La feature 'Ask Gemini in Drive' è attualmente un'integrazione UI proprietaria (1P) di Google Workspace".
- **HTTP probe** (turno precedente): `GET drive.google.com/drive/ai/<folder_id>` → 302 → `accounts.google.com/ServiceLogin` — UI route autenticata, non REST.

L'unica superficie "Google-blessed" che si avvicina è **Vertex AI Search Enterprise** con Workspace data store (vedi Q5 sotto), ma è una capacità diversa (RAG/search con generative answers, NON il prompt strutturato che la UI mostra).

## Q2 — Pattern canonico Gemini API multi-file synthesis

Pattern documentato ufficialmente ([Files API guide](https://ai.google.dev/gemini-api/docs/files)):

| Vincolo | Valore | Fonte |
|---|---|---|
| Max file size generico | 2 GB | Files API doc |
| Max file size PDF | 50 MB | Document processing doc |
| Max pages PDF | 1000 | Document processing doc |
| Token equivalenza | ~258 token/pagina PDF | Document processing doc |
| File retention | 48h | Files API doc |
| Total project storage | 20 GB | Files API doc |
| Max files per request | Non specificato; binding constraint = context window | Document processing doc |
| Context window 3.1 Pro | 1M token | [Pricing page](https://ai.google.dev/pricing) (tier ≤200k vs >200k input price) |

Per Bali Zero (30 PDF/cliente × 8 pp/PDF × 258 token = ~62k token input/cliente — ampiamente entro 200k tier): **un singolo `generateContent` con 30 file attachment è fattibile**.

**Context caching** ([caching doc](https://ai.google.dev/gemini-api/docs/caching)): utile solo se hai un prompt sistema riusabile > 4096 token (3.1 Pro min) e lo invochi ripetutamente. Per folder synthesis cliente — dove ogni cartella ha contenuto diverso — caching del **prompt sistema** (es. schema Pydantic+istruzioni estrazione, ~5-8k token) ha senso; caching dei **file PDF** non perché cambiano per cliente. Risparmio: rate non specifico ma "reduced rate" per token cached.

**Structured output** ([blog announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/), [doc](https://ai.google.dev/gemini-api/docs/structured-output)): Pydantic schemas direttamente come `responseSchema` su tutti Gemini 2.5+, ordering preserved. Pattern perfetto per popolare le 5 facts (identity/person/compliance/gap/next_action) del DB.

## Q3 — Browser automation Drive AI UI: NON FATTIBILE

Convergenza Gemini 3.1 Pro Preview + WebSearch (community 2026):

**TOS-side ([Workspace AUP](https://workspace.google.com/intl/en/terms/use_policy.html))**:
> "to alter, disable, interfere with or circumvent any aspect of the Services" + "to test or reverse-engineer the Services in order to find limitations or vulnerabilities" + "to access any other Google product or service in a manner that violates the terms of service".

Anche su account proprio, automazione UI non è esente.

**Tech-side**:
- UI Drive renderizzata via framework Google proprietario **Wiz** (compilatore Closure) → classi CSS hash come `.xYa .aBc` mutano a ogni micro-rilascio. Selettori instabili by-design.
- Risposta AI streammata in chunk Protobuf su XHR/WebSocket → richiede `MutationObserver` via CDP per intercettare stato "completato", molto fragile.
- CSP `script-src 'self' 'nonce-...'` → click injection JS bloccata; obbligatori i trusted events nativi CDP (`page.mouse.click`).
- Telemetria reCAPTCHA Enterprise v3 rileva entropia comportamentale non-organica → outcome tipico **non** è ban account ma shadowban / 429 / disabilitazione feature AI sulla UI.

Empiricamente in scena 2026 ([Brightdata anti-bot 2026](https://brightdata.com/blog/web-data/puppeteer-real-browser)): puppeteer-real-browser/rebrowser project announced no-updates Feb 2026; battle escalation continua. Anche `claude-in-chrome` con sessione reale autenticata `antonellosiano@gmail.com` non sfugge alle euristiche behaviorali Google su 50-200 folder/giorno.

**Verdict**: opzione viable solo per **debug interattivo umano**, non per cron H24.

## Q4 — NotebookLM API come fallback

Opzione confrontata:
- **Capacità**: `mcp__notebooklm-mcp__source_add` permette `source_type=drive` con `document_id`. `cross_notebook_query` esiste ma usa NB già curati, non NB temp per cliente.
- **Workflow possibile**: crea NB temp/cliente → upload batch PDF → `notebook_query` con prompt strutturato → delete NB.
- **Limiti**: rate-limit NLM non documentati pubblicamente; quota OAuth free non SLA-grade; latency 3-8s/query (memory `mem`); NB creation overhead.
- **Use case fit**: PERFETTO per casi ad-hoc complessi (es. due-diligence singolo cliente con 80+ documenti, output cinematic studio). MALE per pipeline cron 200 clienti × giorno (overhead NB lifecycle + rate-limit unpredictable).

Inventario NB attivi Bali Zero (60 NB, snapshot 2026-05-03, memory `reference_notebooklm_arsenal_full.md`): nessun NB dedicato "Workspace AI / Drive synthesis" — non c'è una superficie di consultation ground-truth specifica per questa decisione.

**Verdict**: NLM resta strumento per casi singoli, NON per popolare `crm_workspace_ai_snapshots` in cron.

## Q5 — Architettura end-to-end raccomandata (Opzione E refined)

**Trigger ibrido** (memo `reference_pro_mini_sync_daemons.md` pattern):
- Cron 6h baseline su Mini-Pro2 (workhorse H24): refresh cartelle non aggiornate da > 7 giorni
- Drive `changes.watch` ([push doc](https://developers.google.com/workspace/drive/api/guides/push)) su ogni folder cliente: webhook → endpoint HTTPS Pro/Mini (Cloudflare Tunnel) → enqueue immediate synthesis
- TTL channel **1 day per folder watch** (vs 7 days per `files`) → cron renewal-channels ogni 23h obbligatorio. Webhook payload **empty body** — solo header `X-Goog-Resource-ID` + `X-Goog-Changed` (content/properties/parents/children/permissions).

**Producer (Python service)**:
```
SA download → Files API upload (batch 30 PDF) →
generateContent(model='gemini-2.5-flash', contents=[file_refs, prompt],
                responseSchema=WorkspaceAISnapshot)
→ Pydantic v2 validate → INSERT crm_workspace_ai_snapshots(provider='gemini', ...)
```

Riuso scripts esistenti (verificati su disco questo turn):
- `scripts/gemini_extract_company_data.sh` (101 LOC, parallel 20 sessions) — adatta da single-PDF a multi-file
- `scripts/batch_extract_company_capital.py` (237 LOC, SA download + asyncio parallel 5) — adatta da `gemini-2.5-flash --approval-mode yolo` shell-out a `genai` Python SDK con `responseSchema`

**Schema Pydantic** (popola 5 facts): `IdentityFact`, `PersonFact[]`, `ComplianceFact`, `GapFact[]`, `NextActionFact[]` come campi nidificati. Gemini 2.5+ preserva ordering ([blog announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/)).

**Idempotency**: hash sha256 di `(folder_id, sorted(file_id+modifiedTime list))` → skip se snapshot esistente con stesso hash. Drive `files.list` ritorna `modifiedTime` — basta.

**SA esistente verificata questo turn**: `nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com` (project `nuzantara`), key in `/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json`. Scope `drive.readonly` adatto; per `changes.watch` serve **anche** `drive.metadata.readonly` o `drive` — verificare scope SA prima di deploy.

**Auto-approve policy**: continua a usare v2 "workspace-ai-v2-consultant-narrative" già definita, ma il `provider` enum del DB ora corrisponde alla realtà (non più `gemini` mock-templating).

## Q6 — Costi e SLA realistici

**Gemini API pricing** ([ai.google.dev/pricing](https://ai.google.dev/pricing) verificata in questo turn):

| Modello | Input $/1M | Output $/1M | Free tier |
|---|---|---|---|
| Gemini 3.1 Pro Preview | $2.00 ≤200k / $4.00 >200k | $12.00 ≤200k / $18.00 >200k | **Non disponibile** |
| Gemini 2.5 Pro | $1.25 ≤200k / $2.50 >200k | $10.00 / $15.00 | Limitato |
| Gemini 2.5 Flash | $0.30 | $2.50 | 10 RPM, 250 RPD, 250k TPM |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | Comparabile |
| Gemini 3.5 Flash | $1.50 | $9.00 | n/d |

Free tier Gemini 2.5 Flash insufficiente per Bali Zero: 250 RPD + 250k TPM ≪ scenario B (200 req/giorno con 62k token input cad).

**Proiezione costi DeepSeek V4 Pro** (output completo `/tmp/deep-research-deepseek-cost-out.json`):

Scenario B = refresh giornaliero tutti 200 clienti (12.4M input + 400k output token/giorno):

| Modello / Servizio | $/giorno | $/anno | $/cliente/anno |
|---|---|---|---|
| Gemini 2.5 Flash | $4.72 | $1,723 | **$8.61** |
| Gemini 3.1 Pro Preview | $29.60 | $10,804 | $54.02 |
| Vertex AI Search Enterprise (paid) | $1.20 | $438 | $2.19 |
| Vertex AI Search Enterprise (free 10k/m) | $0 (sotto quota) | $0 | $0 |

Scenario C = weekly refresh + 50 on-change events/giorno (4.8M input + 156k output/giorno):

| Modello / Servizio | $/giorno | $/anno | $/cliente/anno |
|---|---|---|---|
| Gemini 2.5 Flash | $1.84 | $672 | **$3.36** |
| Gemini 3.1 Pro Preview | $11.54 | $4,213 | $21.07 |
| Vertex AI Search Enterprise (paid) | $0.47 | $171 | $0.85 |

**Vertex AI Search Enterprise** ([cloud.google.com/generative-ai-app-builder/pricing](https://cloud.google.com/generative-ai-app-builder/pricing?hl=en) via WebSearch): $4/1k standard query, $6/1k advanced, 10k free/mese, $1/GB/mese storage indexing. Per scenario C (78 query/giorno × 30 = 2,340/mese) la free tier copre interamente — ma è un **prodotto diverso** (search RAG con generative answer, non multi-doc context injection con structured output Pydantic).

**Verdict costi**: per il caso d'uso vero (snapshot multi-fact con schema Pydantic strict), **Gemini 2.5 Flash paid tier scenario C = $3.36/cliente/anno** è il punto dolce. Scenario B ($8.61) se serve daily refresh. Gemini 3.1 Pro Preview giustificato solo se 2.5 Flash dimostra accuracy < 85% su un test set rappresentativo (akta, NPWP, NIB, IMTA italiani+bahasa misti).

## Matrice fattibilità

| Opzione | tech_feasible | cost_eur_year_200c | Law2/Law6 | reliability | maintenance | verdict |
|---|---|---|---|---|---|---|
| A — Browser scrape `drive.google.com/drive/ai/` con `claude-in-chrome` | ❌ TOS-violating + fragile Wiz selectors | $0 OAuth | NO (UI scrape Workspace AUP) | Bassa (shadowban risk) | Alta (UI mutate ogni release) | **REJECT** |
| B — Vertex AI Search Enterprise (Workspace data store) | ✅ documentato | ~$400 scenario C, $0 sotto free tier 10k/m | OK | Alta | Bassa | Buono se search-RAG basta — diverso prodotto da snapshot multi-fact |
| C — NotebookLM API (NB temp/cliente) | ⚠️ tecnicamente sì, ma overhead | $0 OAuth free, rate-limit n/d | OK | Bassa-Media | Alta (NB lifecycle) | Solo casi ad-hoc |
| D — Apps Script + GeminiWithFiles library | ✅ documentato (`tanaikech/GeminiWithFiles`) | Same as E (paga API) | OK | Media (6min exec limit) | Media | Alternativa se preferisci no-server, ma 6min cap rompe batch 200c |
| **E — SA Drive API + Gemini Files API + generateContent (Python service)** | ✅ canonico Google-blessed | **~$672/anno scenario C, ~$1,723 scenario B (Flash)** | OK | Alta | Bassa (codice nostro) | **RACCOMANDATO** |
| F — Status quo (`drive_autowatcher_service.py` Python templating + `provider='gemini'` mislabel) | tech ok ma è mock | $0 | OK | Bassa (no LLM) | Bassa | Honest fix: relabel `provider='manual'` o sostituire con E |

## Architettura raccomandata (Opzione E dettagliata)

**Stack** (gira su Mini-Pro2 H24, fallback Pro):
- **Trigger**: `crm_workspace_drive_watch` table → 1 row per folder cliente, `channel_id`, `resource_id`, `expires_at`. Cron 23h-fixed sweep `expires_at - 1h` → ricreare watch via `changes.watch`. Cron 6h baseline pull list folder no-snapshot or stale > 7d.
- **Webhook receiver**: nuovo router `apps/backend-rag/backend/app/routers/drive_webhook.py` con endpoint `POST /api/drive/webhook` (PUBLIC_ENDPOINTS allowlist required, validate `X-Goog-Channel-Token` come HMAC secret). Su POST: enqueue Redis `garuda:workspace_ai_jobs` con `folder_id`.
- **Worker**: `apps/backend-rag/backend/services/workspace_ai/synthesizer.py` consuma Redis stream → SA Drive API `files.list` → asyncio gather `aiogoogle` per download → batch upload Files API → `genai.generate_content_async(model='gemini-2.5-flash', contents=[...], generation_config=GenerationConfig(response_schema=WorkspaceAISnapshot, response_mime_type='application/json'))`.
- **Output**: Pydantic v2 `WorkspaceAISnapshot.model_validate_json(...)` → asyncpg `INSERT INTO crm_workspace_ai_snapshots (folder_id, provider, snapshot_hash, identity, persons, compliance, gaps, next_actions, generated_at) VALUES ($1, 'gemini', $2, $3::jsonb, ...)`. **Anti-`json.dumps()` + `::jsonb` trap** (memory `discovery_jsonb_double_encoding_systemic_2026_05_14.md`): usa `asyncpg.connect(init=...)` con codec jsonb OR INSERT senza cast esplicito.
- **HTTPS for webhook**: Cloudflare Tunnel verso Mini-Pro2:8080 — già esistente per WhatsApp/Telegram channels. Cert auto, no self-signed (requisito Drive push).
- **Channel renewal**: launchd `com.balizero.workspace-ai.channel-renewal.plist` ogni 23h, idempotente, con KeepAlive=true (memory cicatrix § "53 LaunchAgents Pro").
- **Telegram alert**: su synth fail (Gemini API 5xx persistent) o channel renewal fail → `@Balizerobot` chat_id 1125336968.

## Risk register

| # | Rischio | Probabilità | Impatto | Mitigation |
|---|---|---|---|---|
| 1 | Channel renewal 23h missed (cron fail) → folder watch scaduto silenziosamente | Media | Alto (eventi persi 24-48h) | Telegram alert se < 6h to expiry. Doppia cron Pro+Mini con leader election. Drive `changes.list` weekly catch-up come safety net. |
| 2 | Gemini API rate-limit / quota burst Tier 1 | Bassa-Media | Medio (job in queue ritardati) | Backoff esponenziale + DLQ Redis `garuda:workspace_ai_dlq`. Upgrade Tier 2 ($100 spend, 3d elapsed). |
| 3 | UU PDP scope (NPWP, KITAS, passport in payload) | Media | Alto (regolatorio) | Confine: solo Google (Vertex/Gemini) — già OK per Workspace data sovereignty. Mai DeepSeek/Anthropic API per snapshot data. Langfuse `hide_input_messages=true` (memory CLAUDE.md §14 Observability). |
| 4 | Falsi positivi sintesi (es. capital 10M letto 100M) | Media | Alto (decisioni cliente errate) | Confidence score: secondary pass Gemini 2.5 Pro su evidence < 0.6. Manual review queue per snapshot con `auto_approve=false`. Test set 30 cartelle golden + RAGAS eval. |
| 5 | Costo runaway (Gemini 3.1 Pro accidentale) | Bassa | Medio ($30/giorno se daily refresh tutti) | Hard env var `WORKSPACE_AI_MODEL=gemini-2.5-flash`. Daily cost guardrail: Telegram alert se Gemini bill > $5/giorno. |

## Decision recommendation

**Procedi con Opzione E (SA Drive API + Gemini 2.5 Flash + Files API + `responseSchema` Pydantic), trigger ibrido cron 6h + Drive `changes.watch` webhook, costo proiettato $3.36/cliente/anno scenario C (weekly + on-change) o $8.61/cliente/anno scenario B (daily).** Relabel l'attuale `drive_autowatcher_service.py` a `provider='manual'` finché Opzione E non sostituisce il pipeline. Escludi scrape UI Drive AI (TOS-violating + fragile + costo opportunità: 1 settimana dev per rompere a primo Wiz update). Considera Vertex AI Search Enterprise come Phase 2 se Bali Zero scala a 1000+ clienti o se serve search cross-folder (es. "trova tutti i clienti con KBLI 93290").

## Sources

1. [Workspace Updates — Ask Gemini in Drive GA, aprile 2026](https://workspaceupdates.googleblog.com/2026/04/ask-gemini-in-drive-now-generally-available.html) — GA announcement, SKUs richiesti, zero API mention
2. [Gemini API Document Processing](https://ai.google.dev/gemini-api/docs/document-processing) — 50 MB/PDF, 1000 pp, 258 token/pagina, multi-file in single request
3. [Gemini API Files API](https://ai.google.dev/gemini-api/docs/files) — 2 GB/file, 20 GB/project, 48h retention
4. [Gemini API Context Caching](https://ai.google.dev/gemini-api/docs/caching) — minimum 4096 token per 3.1 Pro, TTL configurabile
5. [Gemini API Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits) — Free/Tier 1/2/3, RPM/TPM/RPD per-project
6. [Gemini API Pricing](https://ai.google.dev/pricing) — verified $2-4/1M input 3.1 Pro, $0.30/1M Flash, no free 3.1 Pro
7. [Google Drive Push Notifications](https://developers.google.com/workspace/drive/api/guides/push) — channel TTL 1d folder vs 7d files, empty webhook payload + X-Goog headers, HTTPS required
8. [Workspace Acceptable Use Policy](https://workspace.google.com/intl/en/terms/use_policy.html) — vieta automation UI, reverse-engineering, accesso non-interface
9. [Gemini API Structured Outputs blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/) — Pydantic + responseJsonSchema, ordering preserved Gemini 2.5+
10. [Gemini Enterprise Agent Platform (ex Vertex AI rebrand)](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform) — Cloud Next 2026, agent orchestration
11. [Vertex AI Search Enterprise pricing](https://cloud.google.com/generative-ai-app-builder/pricing?hl=en) (via WebSearch — $4/1k standard, $6/1k advanced, 10k free/m, $1/GB storage)
12. [Workspace AI features page](https://workspace.google.com/products/drive/ai/) — feature description, no API
13. [GeminiWithFiles Apps Script library](https://github.com/tanaikech/GeminiWithFiles) — alternative Opzione D, OAuth+API key, 6min exec limit GAS
14. [AppsScriptPulse May 2026](https://pulse.appsscript.info/p/2026/05/google-workspace-developer-news-gemini-powered-apps-script-core-service-news-and-more/) — Apps Script Core Service Jun 2026, no folder synthesis API
15. [n8n Drive push notifications template](https://n8n.io/workflows/6106-monitor-file-changes-with-google-drive-push-notifications/) — reference implementation (POC-level)
16. Gemini 3.1 Pro Preview Q1 — `/tmp/deep-research-gemini-workspace-q1-out.txt` — verdict converge: no public synthesis endpoint, canonical path = Files API + generateContent OR Vertex AI Search Workspace data store
17. Gemini 3.1 Pro Preview Q2 — `/tmp/deep-research-gemini-workspace-q2-out.txt` — verdict converge: Wiz framework instability, AUP violation, Apps Script no bridge to Drive AI
18. DeepSeek V4 Pro cost projection — `/tmp/deep-research-deepseek-cost-out.json` — scenario B/C × 3 models math chain, verified manually (12.4M × $0.30 = $3.72 input Flash scenario B daily ✓)

## Disagreements / open questions

- **Disagreement risolto**: Gemini 3.1 Pro Preview Q1 ha citato URL `cloud.google.com/generative-ai-app-builder/docs/create-data-store-es#workspace` — WebFetch redirect verso `docs.cloud.google.com/...` ha tornato 404 in questo turn. URL probabilmente esiste ma con path leggermente diverso; **non verificato direttamente**. Fall-back affidabile: blog Cloud Next 2026 (source #10) menziona Workspace data store come capability.
- **Aperto**: scope SA Drive `drive.readonly` può fare `changes.watch` o serve scope esteso? Verificare prima di deploy con test API call. CLI: `gcloud iam service-accounts get-iam-policy nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com`.
- **Aperto**: confidence score primario / secondary pass — quanti % di sintesi accuracy `>= 0.85` su Gemini 2.5 Flash su corpus akta+NPWP+NIB italiano+bahasa misto? Serve test set 30-50 cartelle gold-standard prima di committare scenario B.

## Checklist for action

- [ ] Verificare scope SA Drive `nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com` — può fare `changes.watch`? Se no, aggiornare key con `drive` o `drive.metadata.readonly` scope
- [ ] Relabel immediato `drive_autowatcher_service.py` `provider='manual'` (è templating Python, non LLM call) — fix anti-honesty in `crm_workspace_ai_snapshots`
- [ ] Test set: 30 cartelle cliente Bali Zero golden-standard con 5 facts annotate → benchmark accuracy Gemini 2.5 Flash vs 2.5 Pro vs 3.1 Pro
- [ ] Scaffold `apps/backend-rag/backend/services/workspace_ai/synthesizer.py` (worker) + `apps/backend-rag/backend/app/routers/drive_webhook.py` (webhook receiver) + migration N°N `crm_workspace_drive_watch` table
- [ ] Cloudflare Tunnel route `drive-webhook.balizero.com` → Mini-Pro2:8080 verificato e signed cert valid (Drive push requirement)
- [ ] launchd `com.balizero.workspace-ai.channel-renewal.plist` con KeepAlive=true, EnvironmentVariables completi, log persistente `/var/log/...` non `/tmp/` (cicatrix §"53 LaunchAgents Pro")
- [ ] Hard env var `WORKSPACE_AI_MODEL=gemini-2.5-flash` + cost guardrail Telegram alert > $5/giorno spend Gemini API
- [ ] Pydantic v2 schema `WorkspaceAISnapshot` con `IdentityFact`, `PersonFact[]`, `ComplianceFact`, `GapFact[]`, `NextActionFact[]` (5 facts CRM)
- [ ] DLQ Redis `garuda:workspace_ai_dlq` per re-try failed synth + sentinel daily check
- [ ] RAGAS eval cron weekly su 30 cartelle golden — alert se accuracy < 0.85
