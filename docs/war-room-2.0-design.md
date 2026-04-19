# War Room 2.0 — Piano di progettazione

**Autore**: Claude Opus 4.7 · **Data**: 2026-04-18 · **Modalità**: design (non implementazione)
**File deliverable finale in codebase**: `~/Desktop/nuzantara/docs/war-room-2.0-design.md` (questo documento va poi committato lì in fase implementativa — oggi è un plan file)

---

## Context

Bali Zero pubblica ~1 carousel Instagram/giorno via pipeline `apps/war-room/pipeline.sh` (8 agent, ~20min). Analisi di 25 output reali (21 marzo → 18 aprile 2026): **100% tono cinico**, 70% contiene formule clickbait (`trap`, `death clock`, `nobody told you`, ALL-CAPS 8/10 slide), solo IG (X/LinkedIn/blog inattivi), zero metriche, zero feedback loop. Il `brand.json:42` autorizza 3 toni (ironico, istituzionale_severo, cinico): ne viene usato **uno solo**.

**Obiettivo**: evolvere la War Room in un centro di produzione mediatica multi-piattaforma, multi-registro, misurabile, auto-correttivo, allineato alle 7 Leggi e agli 8 Pilastri di `SYMBIOSIS.md`. Non riscrivere: innestare sul cell-core esistente.

**Vincolo cardine** (`SYMBIOSIS.md:174` — Legge 1): LLM via CLI subprocess (`claude -p`, `gemini -p`, `nlm query`). Eccezione concessa: DeepSeek HTTP API. **Image gen** (Imagen/Fireworks) non è LLM → permessa via HTTP come già oggi.

---

## Decisioni prese con l'utente (durante brainstorming)

| #   | Decisione                                                                                                               | Vincolo derivato                                                                                             |
| --- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| D1  | Review-then-publish con Telegram Approve/Edit/Reject                                                                    | Mai auto-publish. Legge 5 Zero ultima istanza enforced.                                                      |
| D2  | Selezione registro tonale via Consiglio multi-LLM                                                                       | Pilastro 4 Confronto operativo. 3 proponenti architetturalmente distinti (Claude/Gemini/DeepSeek) + giudice. |
| D3  | Imagen 4 Ultra cover ($0.06) + Imagen 4 Fast slide ($0.02) = $0.16/carousel (~$4.8/mese)                                | Qualità editoriale massima dove conta (primo scroll).                                                        |
| D4  | Metriche: UTM+CRM (primario) + Meta Graph API IG free + Playwright scraper lightweight X/LI 1/giorno                    | Costo zero, qualità alta, nessuna API a pagamento.                                                           |
| D5  | Trend-Hunter cron 2h, brief come nodi `TrendSignal` in KG                                                               | Riusa GraphRAG entity linker. Allineato Pilastro 6 Curiosità + 3 Condivisione.                               |
| D6  | Host runtime: Pro (Mac Studio M4 Pro). Trend-Hunter failover su Air se Pro down. Pipeline pesante salta quando Pro off. | Legge 6 Sovranità locale. Niente Fly.io per CLI.                                                             |

---

## Diagnosi War Room attuale (fatti verificati)

### File e pipeline

- Entry point: `apps/war-room/pipeline.sh` — orchestratore zsh, lock `/tmp/warroom_pipeline.lock`
- 8 agent: `agents/00_topic_selector.py` → `agents/07_delivery.sh`
- Last run: 2026-04-18 02:03 WITA, runtime 1207s
- Scheduler: NON identificato (launchd plist non trovato; sospetta `~/.cron-agent-python/` o OpenClaw)

### LLM usage map (CLI vs HTTP)

| Agent                           | Modello                                     | Invocazione                                      |
| ------------------------------- | ------------------------------------------- | ------------------------------------------------ |
| `00_topic_selector.py`          | DeepSeek Chat (primario), Gemini (fallback) | DeepSeek HTTP + `gemini -p` CLI                  |
| `03_gemini_strategist.py`       | Gemini 2.5 Pro                              | `gemini -p`                                      |
| `04_claude_director.py`         | Claude Opus/Sonnet                          | `claude -p` (strip `ANTHROPIC_API_KEY` pre-call) |
| `04_claude_director.py:286-287` | NLM NB-2..8                                 | `nlm query` CLI                                  |
| `05_image_brainstorm.py`        | DeepSeek + Gemini + Claude                  | Mix HTTP + CLI                                   |
| `05_image_brainstorm.py`        | Fireworks Flux.1 Dev                        | HTTP (image gen, non LLM)                        |
| `015_qwen_preprocessor.py`      | DeepSeek R1:32b → Qwen 3.5:9b fallback      | Ollama REST localhost                            |

**Nessun import SDK Anthropic/Google.** Il sistema attuale è già CLI-compliant per LLM testuali. ANTHROPIC_API_KEY è in `.env` ma viene strippata prima delle chiamate.

### Output storage

- Artefatti run: `apps/war-room/output/{raw,strategy,images,canva,master}`
- Storico carousel: `apps/war-room/output/canva_batch/{YYYYMMDD}_canva.json`
- **Nessuna tabella DB** per draft/post/metriche (tutto filesystem JSON)
- Pubblicazione IG: manuale via Canva MCP in sessione Claude Code interattiva + Telegram alert (`agents/07_delivery.sh`)

### Violazioni dottrinali rilevate

1. **Pilastro 4 Confronto** — un solo Director (`04_claude_director.py`) decide tone+concept. Nessun confronto plurale.
2. **Pilastro 7 Misura** — zero metriche post-pubblicazione. Impossibile sapere "se cresce".
3. **Pilastro 2 Accumulazione** — nessuna skill/scar salvata post-run. L'organismo non impara.
4. **Pilastro 1 Riflessione** — nessun input da cicli precedenti iniettato nei prompt.
5. **`brand.json:42`** autorizza 3 toni, il codice ne usa 1. Violazione del proprio contratto.
6. **Clickbait**: 70% output contiene formule espressamente da evitare per un brand compliance-first.

---

## Libri sacri — estratto operativo

Fonti canoniche verificate:

- `SYMBIOSIS.md` (Filosofia, 8 pilastri + 7 leggi)
- `VADEMECUM.md` (checklist operativa)
- `INDEX.md` (atlante)
- `CLAUDE.md` (DNA agenti)
- `.claude/rules/cicatrix-scars.md` (memoria antibodies)
- `apps/backend-rag/backend/prompts/zantara_core.py` (voice SSOT)

**8 Pilastri** (`SYMBIOSIS.md:29-171`): Riflessione · Accumulazione · Condivisione · Confronto · Sogno · Curiosità · Misura · Simbiosi
**7 Leggi** (`SYMBIOSIS.md:174-184`): CLI-only LLM · OSINT blindato · Event-driven · Graceful degradation · Zero ultima istanza · Sovranità locale · Numeri prima
**Ciclo vitale**: PulseLoop 6 fasi `sense→think→act→reflect→dream→mature` (`packages/cell-core/cell_core/pulse.py`)

Tri Hita Karana **non esplicitamente citato** — principi impliciti nella triade Pilastri-per-umani (4,8) / Pilastri-per-apprendimento (1,2,3) / Pilastri-per-sistema (5,6,7).

---

## Architettura moduli (14 moduli)

Ogni modulo = un **organo** cell-core con singola responsabilità. Comunicazione via Redis Streams (eventi operativi) + PG LISTEN/NOTIFY canale nuovo `war_room_event` (eventi persistenti). Payload eventi ≤8KB (sempre `{draft_id, status, uri}`, mai blob inline).

| ID  | Modulo                   | Responsabilità                                                          | Host               | Pilastri |
| --- | ------------------------ | ----------------------------------------------------------------------- | ------------------ | -------- |
| M1  | **Trend-Hunter**         | Segnali trending → nodi `TrendSignal` in KG                             | Pro (fallback Air) | 6, 3, 7  |
| M2  | **Intake**               | Decide se produrre oggi, seleziona topic da ultimi 12h TrendSignal      | Pro                | 8, 1     |
| M3  | **Research**             | Arricchisce brief (Exa + xAI + NLM, pattern esistente)                  | Pro                | 2, 6     |
| M4  | **Director + Consiglio** | 3 proponenti LLM + giudice → registro tonale + concept + slides.json    | Pro                | 4, 1, 7  |
| M5  | **Drafter**              | Variante copy per piattaforma (IG caption, X thread, LI post, MDX blog) | Pro                | 3, 1     |
| M6  | **Validator clickbait**  | Regex banlist + Claude Haiku semantic check                             | Pro                | 2, 7     |
| M7  | **Visual Generator**     | Imagen 4 Ultra (cover) + Fast (slide), fallback Fireworks               | Pro                | 7        |
| M8  | **QA Visivo**            | Ollama `qwen2.5vl:7b` + Claude Haiku judge                              | Pro                | 4, 7     |
| M9  | **Layout Renderer**      | HTML/CSS templates + Playwright MCP screenshot                          | Pro                | 6        |
| M10 | **QA Layout**            | qwen2.5vl vision + Claude CLI genera patch CSS (max 3 loop)             | Pro                | 4, 7     |
| M11 | **Review Gate**          | Telegram inline keyboard Approve/Edit/Reject, SLA 4h→48h                | Fly (webhook) + PG | 5, 8     |
| M12 | **Publisher**            | Pluggable per platform (IG/X/LI/Blog), parallel, graceful               | Pro                | 3, 4     |
| M13 | **Measurer**             | UTM+CRM + Meta Graph API + Playwright scraper, T+24h/72h/7g             | Pro (cron)         | 7        |
| M14 | **Learner**              | Score composito → genome skill o cicatrix scar → inject prossimo ciclo  | Pro (cron 03:00)   | 1, 2, 5  |

### Riuso codice esistente (citato con path:line)

| Pattern                | Path                                                                                 | Uso in War Room 2.0                                               |
| ---------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| EventBus + PG channel  | `apps/backend-rag/backend/services/events/event_bus.py:73` + `:46-55` PG_CHANNEL_MAP | Aggiungere `war_room_event`                                       |
| Approval Telegram      | `apps/backend-rag/backend/services/intel/intel_approval_service.py`                  | Template per M11                                                  |
| Webhook callback       | `apps/backend-rag/backend/app/routers/telegram_webhook.py`                           | Estendere con route `warroom:*`                                   |
| Multi-AI orchestration | `apps/backend-rag/backend/agents/services/multi_ai_adapter.py:496-504`               | Base Consiglio (DA VERIFICARE se HTTP o CLI)                      |
| Curiosity orchestrator | `apps/graph-engine/src/nuzantara_graph/curiosity/`                                   | Pattern per Trend-Hunter (orchestrator+grader+dispatchers)        |
| genome API             | `packages/cell-core/cell_core/genome.py`                                             | Learner M14 scrive skill/scar; Director legge prima del Consiglio |
| PulseLoop              | `packages/cell-core/cell_core/pulse.py`                                              | Moduli lunghi (Trend-Hunter, Publisher worker) girano come pulse  |
| Voice SSOT             | `apps/backend-rag/backend/prompts/zantara_core.py`                                   | Director/Drafter partono da qui + overlay registro                |
| Ollama client          | `backend/llm/ollama_client.py` (CLAUDE.md §10)                                       | QA M8/M10 con `qwen2.5vl:7b` + `think: false`                     |
| Playwright MCP         | `apps/nuzantara-mcp-browser`                                                         | M9 Renderer + M13 scraping                                        |
| Migration base + last  | `migration_111_notification_log.py`                                                  | `migration_112_war_room_tables.py` new                            |
| Olympus heartbeat      | `apps/backend-rag/backend/services/olympus/heartbeat.py`                             | Detection Pro down per failover                                   |

---

## Sistema registri tonali (7 registri)

Ritira "cinico" e "istituzionale_severo" da `brand.json:42`. Sostituisce con: **rituale, analitico, ironico, militante, pedagogico, poetico, tecnico**. Ciascun registro è un **overlay** sopra `zantara_core.py` + regole di selezione del Consiglio.

### Tassonomia (topic esempio: "estensione visa B211A")

| #   | Registro       | Voce                                    | Quando                                 | Piattaforma                    | Headline esempio                                                         | Anti-pattern                                     |
| --- | -------------- | --------------------------------------- | -------------------------------------- | ------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------ |
| 1   | **Rituale**    | solenne, ciclica, latino-giuridico      | scadenze annuali, ricorrenze normative | Newsletter, LinkedIn long      | "Il sesto mese del B211A. Una liturgia della proroga."                   | hashtag trend, clickbait, emoji                  |
| 2   | **Analitico**  | neutrale, dati prima di opinioni        | contenuti numerici (LKPM, KITAS stats) | LinkedIn, Blog, Newsletter     | "B211A: 60+60+60 giorni. Cosa cambia oltre la terza proroga."            | aggettivi enfatici, giudizi morali               |
| 3   | **Ironico**    | sottile, comic timing, detour narrativi | situazioni assurde sistema             | IG, X                          | "B211A: come pagare tre volte per restare turista."                      | sarcasmo amaro, cinismo, offesa                  |
| 4   | **Militante**  | diretta, performativa, chiamate azione  | denuncia pratiche predatorie           | IG reel copy, X corto          | "Ti hanno detto che il B211A è 'quasi come un KITAS'. Ti hanno mentito." | banlist ("quello che non ti dicono"), vittimismo |
| 5   | **Pedagogico** | paziente, una nozione/frase             | didattica, onboarding                  | Blog, Newsletter, IG educativo | "B211A spiegato semplice: il turistico che si allunga fino a 180gg."     | condiscendenza, emoji didattiche                 |
| 6   | **Poetico**    | immagini concrete, ritmo, sottrazione   | longform atmosferici, chiusura anno    | Newsletter, Blog               | "B211A: il visto che dura quanto una stagione secca."                    | metafore banali, vaghezza                        |
| 7   | **Tecnico**    | precisa, riferimenti normativi esatti   | update Peraturan, deep-dive pro        | LinkedIn long, Blog            | "Permenkumham 22/2023 art. 51: le tre condizioni per la quarta proroga." | semplificazioni, tono pedagogico                 |

### Banlist clickbait (enforcement M6)

**Due livelli**:

1. **Regex veloce** (zero costo): formule italiane/inglesi
2. **Semantic check** (Claude Haiku CLI): pattern latenti

```
# Formule italiane (banned verbatim)
"quello che non ti dicono" · "nessuno ti dice" · "ecco perché" · "la verità su"
"la cosa più importante" · "svelato" · "attenzione a" · "devi sapere"
"numero X ti stupirà"

# Formule angoscianti (cicatrice War Room v1 — vietate)
"trap"/"trappola" · "kill-switch" · "death clock" · "countdown" · "ghost"
"your next move"/"la tua prossima mossa" · "game over" · "don't be caught"

# Tipografici
ALL-CAPS > 3 parole consecutive nelle headline (eccetto acronimi: KBLI, KITAS, LKPM, NPWP, PMA, PT, OSS, NIB)
"!!!!" o "?????" · Emoji > 2 per headline · Headline > 12 parole
```

Ogni scar generato da Learner aggiunge formule alla banlist (crescita organica).

---

## Consiglio registro tonale — protocollo

### Composizione (3 voci + 1 giudice)

| Voce  | Modello                              | Persona prompt                                      |
| ----- | ------------------------------------ | --------------------------------------------------- |
| P1    | `claude -p` Opus/Sonnet 4.6          | Critico editoriale, economista behavioural          |
| P2    | `gemini -p` 2.5 Pro                  | Linguista pragmatico, retorica politica italiana    |
| P3    | DeepSeek R1 HTTP (Legge 1 eccezione) | Narratologo, mitopoiesi ed escatologia              |
| Judge | `claude -p` Sonnet (per costo)       | Ha accesso a storico 14gg, brand.json, scar recenti |

**Diversità strutturale** (`SYMBIOSIS.md:118-119`): 3 modelli architetturalmente diversi, non roleplay sullo stesso.

### Protocollo a 3 round

1. **Round 0 — Propose** (parallelo, ~60s): ogni P riceve `research.json` + `brand.json` + lista 7 registri + ultima riflessione propria. Output: `{register, rationale, risk, example_headline}`. **I 3 non si vedono.**
2. **Round 1 — Challenge** (parallelo, ~45s): ognuno riceve le 3 proposte + deve (a) scegliere la migliore **che non sia la propria** con motivazione, (b) stroncare la peggiore. Forza dissenso strutturale → previene groupthink.
3. **Round 2 — Judge** (sequenziale, ~30s): giudice riceve round 0+1 + storico 14gg registri + scar recenti. Applica hard rules:
   - Max 3 post consecutivi stesso registro
   - Max 3 "ironico"/settimana (prevenzione deriva verso comico/cinico)
   - Se concordanza round 0 >90%: veto + retry (max 1); se ancora concordanza, sceglie comunque registro diverso dal più frequente ultimi 7gg

### Costo stimato

- 3 × 2 round × ~3k token in / 1k token out
- 1 judge × 5k in / 1k out
- **~15 chiamate Claude CLI per carousel** (Council + Drafter + Validator)
- DeepSeek: ~$0.005/ciclo
- Claude: costo 0 (OAuth Max flat-rate)

---

## Pipeline immagini + QA visivo

### Routing Imagen 4

- Cover: `imagen-4.0-ultra-generate-001` ($0.06)
- Slide 2-N: `imagen-4.0-fast-generate-001` ($0.02)
- Aspect: 4:5 IG (1080×1350), 16:9 X, 1200×628 LinkedIn/Blog

### Prompt template (4 layer)

```
[SCENE_CORE]            — da slides.json image_prompt
[BRAND_SUFFIX]          — brand.json:51 "Editorial, Wired, Bloomberg, no stock, no handshakes, no passports, cinematic"
[STYLE_MODIFIERS]       — macrografia editoriale, surrealista
[NEGATIVE_PROMPT]       — hands holding objects, passport close-ups, stock photo, text overlays, watermark
```

### QA Visivo (M8) — due voci

1. **Ollama `qwen2.5vl:7b`** (unica vision che funziona su Pro, vedi `CLAUDE.md §10`): flag JSON binari `{matches_brief, has_banned_elements, brand_fit_0_10, text_area_available_ratio, readability_issues}`
2. **Claude Haiku CLI** (judge): legge flag + prompt + screenshot b64 → decide `pass | retry_with_modified_prompt | hard_reject`

**Retry policy**: max 3 per slide, poi fallback placeholder + Telegram alert "slide N senza immagine approvata".

### Storage

- Temp: `$WAR_ROOM_V2/state/{draft_id}/images/`
- Approvati post-Review: Tigris S3 `bali-zero-war-room/{YYYY}/{MM}/{draft_id}/`
- Cache Pro: 30gg auto-prune

**DA VERIFICARE**: Gemini CLI supporta image gen? Probabilmente no — serve Google Gen AI SDK HTTP. Non viola Legge 1 perché image gen ≠ LLM (stessa logica Fireworks attuale).

---

## Pipeline layout auto-correzione

### Template HTML/CSS

- `templates/ig_carousel.html` — 1080×1350, griglia CSS con vars `--headline`, `--body`, `--image-url`
- `templates/x_thread_image.html` — 1600×900
- `templates/linkedin_post.html` — 1200×628
- `templates/newsletter.html` — email-safe (tabelle, no flex moderno)

Font `LeagueSpartan-Bold`, `Montserrat-*` da `brand.json:21-40`. **DA VERIFICARE** installazione locale Pro; fallback `@font-face` Google Fonts CDN.

### Render (M9) + QA (M10)

- Playwright MCP Chromium headless: `page.goto(data_url_html) → page.screenshot()` per slide
- Budget: <3s/slide
- qwen2.5vl vision su screenshot: `{text_overflow, low_contrast, element_overlap, logo_visible, readability_0_10}`
- Se flag raised: Claude CLI riceve (screenshot b64 + HTML source + qwen output + brand constraints) → genera **solo patch CSS** (diff, no rewrite)
- Renderer riesegue; loop max 3; fallimento → Telegram escalation

---

## Trend-Hunter — dettaglio M1

### Fonti (cron 2h)

| Fonte                                             | Chiave                     | Metodo                           | Note                                               |
| ------------------------------------------------- | -------------------------- | -------------------------------- | -------------------------------------------------- |
| xAI Grok search                                   | `GROK_API_KEY` (in `.env`) | HTTP (OSINT locale Pro, Legge 2) | Pattern `agents/10_xai_researcher.py` esistente    |
| Google Trends                                     | pytrends lib               | Python                           | **DA VERIFICARE** installazione                    |
| Reddit r/bali, r/indonesia                        | PRAW OAuth                 | Python                           | **DA VERIFICARE** credenziali; fallback Playwright |
| RSS compliance (hukumonline, jakartapost, bisnis) | feedparser                 | 30min cron                       | Nessuna auth                                       |
| Bali Post, Antara                                 | Playwright MCP             | HTML scrape                      | Rate limit respect                                 |
| X public tweets                                   | X API free tier            | OAuth 2.0                        | **DA VERIFICARE** quota 2026 Basic                 |

### Schema `TrendBrief`

```
{
  id, source, source_url, topic, raw_title, raw_snippet, language,
  urgency_score: 0-100,            // momentum derivative
  bali_zero_relevance: 0-100,      // Gemini CLI scored
  timestamp, decay_half_life_hours: 12-72,
  entities_linked: [{id, type, confidence}]
}
```

### Insert KG

- Nodo `(:TrendSignal {id, topic, urgency, timestamp, source})`
- Edge `(:TrendSignal)-[:MENTIONS {confidence}]->(:Entity)`
- Edge `(:TrendSignal)-[:RELATES_TO]->(:Visa|:KBLI)` se matcha keyword
- Entity linker: **DA VERIFICARE path** in `apps/backend-rag/backend/services/knowledge_graph/`

### Continuità

- Primario Pro launchd cron 2h
- Se Olympus heartbeat Pro down >15min: Air esegue versione degradata (solo Gemini CLI + Ollama, no Claude, no xAI)

---

## Schema metriche — `migration_112_war_room_tables.py`

Segue pattern `migration_111_notification_log.py`. Idempotente (`CREATE TABLE IF NOT EXISTS`).

### 7 tabelle + 1 materialized view

```
war_room_drafts
  id UUID PK · topic · register · status (briefed|researched|concept|drafts|rendered|pending_review|approved|rejected|published|missed)
  brief_json · research_json · council_debate_json · slides_json · drafts_json (JSONB)
  rejection_reason · created_at · updated_at · approved_by · approved_at

war_room_posts
  id UUID PK · draft_id FK · platform (instagram|x|linkedin|blog|newsletter)
  post_external_id · post_url · register (denormalized) · published_at · final_text
  UNIQUE (draft_id, platform)

war_room_metrics
  id BIGSERIAL · post_id FK · metric_name (reach|impressions|saves|shares|clicks|leads_attributed|likes|comments)
  value · collected_at · source (meta_graph|playwright_scrape|utm_crm)
  INDEX (post_id, metric_name), (collected_at)

war_room_leads
  post_id FK · contact_id FK → contacts · utm_campaign · utm_medium · utm_source
  attributed_at · conversion_stage (lead|qualified|client) · revenue_idr

war_room_rejections
  id · draft_id FK · reason (tone|fact|visual|clickbait|other) · reason_detail
  rejected_by (zero|validator|qa_visual|qa_layout) · timestamp

war_room_missed_runs
  id · scheduled_at · skipped_reason (pro_offline|no_trend|hard_failure) · details_json · notified_zero

war_room_costs
  id BIGSERIAL · draft_id FK · cost_type (imagen_ultra|imagen_fast|deepseek_api|claude_cli|other)
  cost_usd · timestamp

-- Materialized view (refresh daily)
war_room_council_performance
  register · last_14d_posts · avg_composite_score · top_topic · last_used
```

### EventBus channel

Aggiungere in `event_bus.py:46-55` PG_CHANNEL_MAP:

```python
"war_room_event": "war_room.event"
```

Trigger PG su `war_room_drafts` (status change) e `war_room_posts` (INSERT). Payload ≤8KB: `{draft_id, status, uri}`, mai blob.

### Subscriber

- `review_handler.py` → Telegram su `status=ready_for_review`
- `publisher_worker.py` → pubblica su `status=approved`
- `measurer_worker.py` → schedule T+24h/72h/7gg su `status=published`
- `dashboard_sse.py` → SSE stream per `/war-room/metrics`

### Dashboard `/war-room/metrics`

- Path: `apps/admin-dashboard/app/war-room/metrics/page.tsx`
- Widget: timeline pubblicazioni (14/30/90gg colorate per registro) · heatmap registro×performance · pie distribuzione registri (alert se >40%) · funnel drafts→approved→published→leads · bar rejection reasons · table costi per draft
- **DA VERIFICARE**: Recharts già dipendenza?

---

## Review Gate M11 (Telegram interattivo)

1. M10 completa → trigger PG → `pg_notify('war_room_event', {status:'ready_for_review'})`
2. `review_handler.py` (Fly `nuzantara-rag`, endpoint webhook già esistente) carica draft da PG, cover da Tigris, invia a Zero:
   - `sendPhoto` cover + caption (prima slide IG + registro scelto + alternative scartate dal Consiglio, per trasparenza)
   - Inline keyboard: `[✅ Approva]` `[✏️ Edit]` `[❌ Rifiuta]`
3. Callback in `apps/backend-rag/backend/app/routers/telegram_webhook.py` (estendere) instrada `callback_data=warroom:<action>:<draft_id>`
4. Azioni:
   - **Approva** → `status=approved, approved_by, approved_at` → Publisher
   - **Edit** → chat libera "Cosa cambi?" → `edit_hint` a M5 Drafter → ciclo parziale (skip Consiglio)
   - **Rifiuta** → menu motivo `[tone|fact|visual|other]` → `war_room_rejections` + Learner scar

### SLA (mai auto-publish — Legge 5)

- 4h senza azione: alert soft
- 12h: alert ogni 2h
- 48h: auto-expire `status=rejected` motivo `sla_expired`. **Zero ripublica senza approvazione esplicita.**

### Sicurezza

- Solo `TELEGRAM_OWNER_CHAT_ID=1125336968` autorizzato (da `CLAUDE.md §14`)
- HMAC verify su webhook (pattern esistente)
- Idempotenza: doppio approve non ripubblica

---

## Publisher M12 (pluggable)

### Contratto (non codice)

```
Publisher (ABC):
  async def validate(draft) -> ValidationResult
  async def publish(draft) -> PublishResult
  async def delete(external_id) -> bool   # best-effort rollback
  property platform_name -> Platform
```

### Implementazioni

- **IGPublisher**: IG Graph API v20, long-lived token (60gg, watchdog rinnovo 7gg prima). `POST /{ig-user-id}/media` (container carousel N slide) + `media_publish`. Tigris signed URL 1h TTL.
- **XPublisher**: OAuth 2.0 user context + refresh. `POST /2/tweets` thread chained. **ATTENZIONE**: CRC attualmente broken (`CLAUDE.md §10`). Rifare OAuth. **DA VERIFICARE** X API Basic quota 2026.
- **LinkedInPublisher**: OAuth2 scope `w_member_social`, token 60gg. `POST /rest/posts`. Personal vs Company configurable. **DA VERIFICARE** API v202507+ deprecation ugcPost.
- **BlogPublisher**: git commit `apps/blog/content/war-room/{YYYY-MM-DD}-{slug}.mdx` + push → Vercel auto-deploy. **DA VERIFICARE** esistenza `apps/blog/` (non in CLAUDE.md §1).

### Graceful degradation (Legge 4)

- Piattaforme in parallelo. Una fallisce → altre continuano.
- `war_room_posts` row per ogni piattaforma riuscita.
- `war_room_publish_failures` row per fallite + Telegram alert.

---

## Learner M14 (feedback loop)

### Score composito

```
composite = 0.35*norm(reach) + 0.25*engagement_rate + 0.25*leads_per_1k_impressions + 0.15*save_rate
```

Normalizzazione: percentile su 90gg stessa piattaforma.

### Decisioni

- `composite > p70` → `genome.record_skill(name="war_room:{register}:{topic_category}", procedure, precondition, success_criterion, scope='Project')`
- `composite < p20` OR `rejected_by_zero` → SQLite `type='scar'` + narrativo come `cicatrix-scars.md`:
  - **TRAUMA**: cosa pubblicato, dove, quando
  - **ANTIBODY**: formula da evitare (regex → banlist)
  - **GOTCHA**: edge case

### Iniezione prossimo ciclo

All'avvio Consiglio M4:

- `genome.search("war_room")` top 5 skill per confidence
- `war_room_rejections` ultimi 14gg GROUP BY reason
- `war_room_council_performance` view
- Compatto in `<memoria_episodica>` max 2000 char (budget `SYMBIOSIS.md:43`)
- Iniettato nei prompt dei 3 proponenti E del giudice

---

## Continuity (Pro down)

### Detection

- Olympus heartbeat Pro (`apps/backend-rag/backend/services/olympus/heartbeat.py`): `last_beat > 15min` → stato `DOWN`
- Evento `olympus.pro_down` sottoscritto da scheduler Air

### Comportamento per modulo

- **Trend-Hunter**: Air esegue versione degradata (Gemini CLI + Ollama, no Claude/xAI)
- **Pipeline pesante**: **skip** giornata. Row in `war_room_missed_runs` con `skipped_reason='pro_offline'`. Alert Telegram soft se >48h consecutivi.
- **Catch-up**: quando Pro torna online, NON recupera auto. Zero riceve prompt "3 run missed: eseguo catch-up? [sì/no/solo più urgente]"

---

## Allineamento 8 Pilastri → moduli → metriche

| #   | Pilastro      | Modulo primario                            | Metrica                                        |
| --- | ------------- | ------------------------------------------ | ---------------------------------------------- |
| 1   | Riflessione   | M14 Learner, M4 injection                  | `reflection_injection_size_chars`              |
| 2   | Accumulazione | M14 → genome, M6 banlist growth            | `skill_count`, `scar_count`, `banlist_size`    |
| 3   | Condivisione  | Redis streams + canale PG `war_room_event` | `stream_events_24h`, `consumer_groups_active`  |
| 4   | Confronto     | M4 Consiglio, M8/M10 QA dual-voice         | `council_rounds_count`, `dissent_rate_round_1` |
| 5   | Sogno         | M14 cron notturno, homeostasis skill decay | `skill_silenced_7d`                            |
| 6   | Curiosità     | M1 Trend-Hunter                            | `trend_signals_24h`, `novel_topics_ratio`      |
| 7   | Misura        | M13 Measurer + dashboard                   | tutto `war_room_metrics`                       |
| 8   | Simbiosi      | M11 Review Gate Zero-centric               | `approval_rate`, `edit_rate`, `rejection_rate` |

---

## Rischi + mitigazioni

| Rischio                                                  | P   | I   | Mitigazione                                                             |
| -------------------------------------------------------- | --- | --- | ----------------------------------------------------------------------- |
| CLI Claude hang (documented)                             | M   | M   | Pro/Air macOS only (no Fly); timeout per call; fallback Gemini CLI      |
| Deriva tono (Consiglio sceglie sempre ironico/analitico) | M   | H   | Hard rule M4: max 3 registro/settimana; Learner penalizza ripetizione   |
| Claude OAuth Max overload                                | L   | M   | Log in `war_room_costs`; fallback Gemini su M5/M6 se avvicina quota     |
| Imagen 4 quality inconsistente                           | H   | M   | Ultra per cover; QA visivo 3-retry; fallback Fireworks esistente        |
| API IG/X/LI breaking                                     | M   | H   | Publisher pluggable; monitor changelog quadrimestrale                   |
| Scraping metriche rotto                                  | H   | L   | Graceful degradation, `source=partial`, UTM+Meta continuano             |
| Groupthink Consiglio                                     | L   | H   | Round 1 dissenso obbligatorio; judge veto >90% concordanza              |
| Pro down >48h                                            | L   | M   | Trend-Hunter failover Air; alert Telegram                               |
| Token IG scaduto (60gg)                                  | M   | H   | Watchdog pattern `scripts/drive_token_watchdog.py` replicato; alert 7gg |
| Clickbait passa Validator                                | M   | M   | Banlist cresce ad ogni scar; Haiku semantic-check                       |
| PG payload >8KB                                          | L   | M   | Invariant: `{draft_id, status, uri}` mai blob                           |
| DeepSeek API down                                        | M   | L   | Consiglio degrada a 2 voci; flag `council.degraded=true`                |

---

## Roadmap sprint (2-3 giorni ciascuno, 12 sprint totali)

### Sprint 1 — Foundation DB + EventBus

- `migration_112_war_room_tables.py` (7 tabelle + 1 view)
- Trigger PG → canale `war_room_event`
- `event_bus.py:PG_CHANNEL_MAP` update
- SQLAlchemy/Pydantic models in `backend/services/war_room/models.py`
- **Done**: migration up+down testata (Codex sandbox); PG `SELECT war_room_drafts` risponde; EventBus subscriber riceve evento fake
- **Dipendenze**: nessuna

### Sprint 2 — Trend-Hunter + KG

- `apps/war-room-v2/trend_hunter/` con 5 source adapters
- Entity linker integration
- Pro launchd cron 2h
- **Done**: 1 ciclo reale produce ≥10 TrendSignal; KG `MATCH (t:TrendSignal) count ≥ 100` dopo 24h staging
- **Dipendenze**: S1

### Sprint 3 — Consiglio tone v1

- `apps/war-room-v2/director/council.py` — 3 proponenti CLI + giudice
- Overlay registri su `zantara_core.py`
- Fixture matrix 10 topic → 10 consigli
- **Done**: 10/10 council <90s/ciclo; 7 registri rappresentati ≥1 su 30 run; no groupthink (≥2 registri diversi nelle 10 run)
- **Dipendenze**: S1

### Sprint 4 — Visual pipeline + QA

- M7 Imagen 4 Ultra/Fast + M8 qwen2.5vl + Claude Haiku judge
- Fallback Fireworks attivo
- **Done**: 10 cover + 50 slide; pass-rate QA ≥70%; costo medio ≤$0.20/carousel; cost tracking in `war_room_costs`
- **Dipendenze**: S1

### Sprint 5 — Layout renderer + QA

- HTML/CSS templates (ig, x, linkedin, newsletter)
- Playwright MCP render + qwen2.5vl QA + Claude patch-CSS
- **Done**: 20 carousel fixture render success 100%; ≤3 retry/slide; zero text overflow 20/20
- **Dipendenze**: S4

### Sprint 6 — Review Gate Telegram

- `review_handler.py` + estensione `telegram_webhook.py` callback
- Foto + inline keyboard + SLA expire worker
- **Done**: 5 draft fixture → 5 callback + stato DB aggiornato; SLA test con timer accelerato
- **Dipendenze**: S1, S5

### Sprint 7 — Publisher IG + X

- `IGPublisher` carousel upload; `XPublisher` OAuth 2.0 + thread; token watchdog
- **Done**: 1 carousel IG test account end-to-end; 1 thread X pubblicato
- **Dipendenze**: S6

### Sprint 8 — Publisher LinkedIn + Blog

- `LinkedInPublisher`; `BlogPublisher` git commit + Vercel deploy
- **DA VERIFICARE** `apps/blog/` esistenza (se assente, scaffolding minimale)
- **Done**: staging LI company post + MDX commit + Vercel preview
- **Dipendenze**: S7

### Sprint 9 — Measurer

- M13 con 3 fonti (UTM+CRM, Meta Graph, Playwright scraper)
- Cron T+24h/72h/7gg
- **Done**: 1 post reale con metriche complete dopo 72h; `war_room_metrics` ≥5 righe per post
- **Dipendenze**: S7, S8

### Sprint 10 — Learner + genome

- M14 scoring, genome write skill/scar, iniezione Consiglio
- Cron notturno 03:00 WITA
- **Done**: 10 post storici → 10 skill/scar; Consiglio log contiene `<memoria_episodica>`
- **Dipendenze**: S3, S9

### Sprint 11 — Dashboard `/war-room/metrics`

- Next.js page admin-dashboard + 6 widget + SSE real-time
- **Done**: 4/6 widget ≠ vuoti con dati 14gg; screenshot QA via `claude-in-chrome`
- **Dipendenze**: S9

### Sprint 12 — Hardening + continuity

- Failover Air Trend-Hunter; missed-runs alert; quota monitoring; runbook `docs/war-room-v2/README.md`
- Chaos test (Pro spento 2h, IG token expired, render fail)
- **Done**: 3/3 chaos test verdi; runbook operativo aggiornato
- **Dipendenze**: tutti

### Convention "Done"

1. Code merged su `main` con PR review
2. Test verdi (`PYTHONPATH=. pytest`)
3. Metrica accettazione verificata in staging
4. `mem save decision:...` + riflessione genome

---

## DA VERIFICARE (open questions prima di implementazione)

1. **Gemini CLI supporta image generation?** Probabilmente no; serve Google Gen AI SDK HTTP (non viola Legge 1, image gen ≠ LLM).
2. **`MultiAIAdapter` attuale usa HTTP o CLI?** `apps/backend-rag/backend/agents/services/multi_ai_adapter.py:496-504`. Se HTTP, creare nuovo `CouncilCLIAdapter`.
3. **Path KG entity linker** in `apps/backend-rag/backend/services/knowledge_graph/`.
4. **`apps/blog/` esiste?** Non elencato in `CLAUDE.md §1`. Se assente, Sprint 8 richiede scaffolding Next.js minimale.
5. **Recharts in admin-dashboard**: già dipendenza?
6. **Exa API HTTP**: Legge 1 lo include come LLM o come search tool? Oggi in produzione, assumo permesso.
7. **X API Basic quota 2026**: verificare limit post/mese.
8. **LinkedIn Posts API v202507+**: timeline deprecation ugcPost.
9. **Reddit API / pytrends credenziali**: disponibili?
10. **Font `LeagueSpartan-Bold`, `Montserrat-*`** (`brand.json:21-40`): installati su Pro o serve `@font-face` CDN?
11. **I 25 sample clickbait**: path per estrarre banlist completa (probabile `apps/war-room/output/canva_batch/`).
12. **Newsletter system esistente**: `apps/backend-rag/backend/services/communication/`? Se sì integrare, se no skip M12 newsletter.
13. **Canva MCP**: retained optional per design manuale Zero? M9 Renderer bypassa Canva per pipeline auto.
14. **Cron War Room v1 attuale**: come è schedulato (02:03 WITA)? launchd/crontab/OpenClaw?

---

## File critici per l'implementazione

- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/events/event_bus.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/intel/intel_approval_service.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/app/routers/telegram_webhook.py`
- `/Users/nuzantara/Desktop/nuzantara/packages/cell-core/cell_core/{genome,pulse,homeostasis}.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/war-room/config/brand.json` (update tone_of_voice)
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/prompts/zantara_core.py` (voice SSOT)
- `/Users/nuzantara/Desktop/nuzantara/apps/graph-engine/src/nuzantara_graph/curiosity/` (pattern Trend-Hunter)
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/migrations/migration_111_notification_log.py` (base per 112)
- `/Users/nuzantara/Desktop/nuzantara/apps/nuzantara-mcp-browser` (Playwright render)

---

## Verifica end-to-end (come testare War Room 2.0 completo)

1. **DB+EventBus**: `PYTHONPATH=. pytest backend/tests/services/war_room/` verde; `SELECT count(*) FROM war_room_drafts` risponde.
2. **Trend-Hunter 24h staging**: `MATCH (t:TrendSignal) RETURN count(t)` ≥ 100 in Neo4j; stream `cell:war_room:trend_signals` ha eventi ultimi 2h.
3. **Consiglio**: lanciare `python -m war_room_v2.director.council --topic "B211A extension"`; output JSON con 3 proposals + judge decision; log mostra dissenso round 1.
4. **Image + Layout**: run completa staging → `state/{draft_id}/rendered_final/` contiene 6 PNG, zero text overflow (ispezione manuale + qa_layout.json verde).
5. **Review Gate**: trigger `status=ready_for_review` → Telegram chat test riceve foto+keyboard; click Approve → stato `approved`; click Reject → riga `war_room_rejections`.
6. **Publisher**: account test IG (non produzione Bali Zero); 1 carousel pubblicato; `war_room_posts` riga con `post_external_id`.
7. **Measurer T+72h**: `SELECT * FROM war_room_metrics WHERE post_id=X` ≥ 5 righe da almeno 2 `source`.
8. **Learner**: `SELECT * FROM genome WHERE type='skill' AND name LIKE 'war_room:%'` ≥ 1 riga dopo 10 post; Consiglio log successivo contiene `<memoria_episodica>` con chars > 0.
9. **Dashboard**: apri `/war-room/metrics` in Chrome → 4/6 widget popolati, funnel mostra ≥1 conversione.
10. **Chaos**: spegni Pro 2h → Air assume trend hunting; riaccendi Pro → alert Zero per catch-up; cron IG watchdog simula token 6gg-to-expiry → Telegram alert.

---

## Prossimo passo

Questo è il **design document**. L'implementazione parte solo dopo:

1. User review di questo plan
2. Risoluzione dei 14 "DA VERIFICARE" (alcuni con grep rapido, altri con chiamate API)
3. `ExitPlanMode` → passaggio a `writing-plans` skill per piano d'implementazione Sprint 1

**Costo di lancio stimato**: implementazione 12 sprint × 2-3gg = **24-36gg** di lavoro sequenziale. Possibile parallelizzazione S4+S5 (visual+layout), S7+S8 (publisher). Tempo realistico con parallelizzazione: ~20gg.

**Costo operativo stimato mensile a regime**: Imagen ~$5/mese, DeepSeek ~$0.15/mese, Claude OAuth Max (flat), infra invariata. **Totale marginale: ~$6/mese** per un centro di produzione mediatica completamente automatizzato con review umana.

---

# PARTE II — Intel Scraper riposizionato + Sistema cognitivo a 4 livelli

**Estensione del design** (aggiunta 2026-04-18 in stessa sessione di brainstorming). La Parte I definisce War Room 2.0 come centro di produzione editoriale multi-piattaforma. La Parte II riposiziona Intel Scraper come **unico layer di ricerca** dell'organismo e aggiunge 4 livelli cognitivi che producono insight non derivabili dai singoli dossier.

## Context Parte II

Tre problemi irrisolti dalla Parte I:

1. **Duplicazione di ricerca**: il modulo M3 Research di War Room 2.0 (Exa + xAI + NLM) replica lavoro che `apps/bali-intel-scraper/` già fa (cron 03:00 WITA su Pro, pattern `scraper/` → `enricher/` → `publisher/` Qdrant `balizero_news`). Violazione Legge 7 "Numeri prima" — pagare la ricerca due volte.

2. **Volume editoriale sottostimato**: Parte I prevede 1 carousel IG/giorno. Bali Zero opera come newsroom compliance; target realistico è **3-8 articoli/giorno blog** + carousel/thread/newsletter derivati.

3. **Dossier senza consumatori**: se Intel produce 20 dossier/giorno e War Room ne usa 1-3, gli altri 17+ sono spreco. Pilastro 3 "Condivisione" richiede fanout multi-consumer.

## Decisioni prese con l'utente (Parte II)

| #   | Decisione                                                                                                 | Vincolo derivato                                                                      |
| --- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| D7  | Intel Scraper = **pure research** (nessuna prosa/drafting)                                                | Scarica M3 Research; Intel produce `TrendSignal` + `ResearchDossier`                  |
| D8  | War Room v2 = **pure production editoriale** multi-output                                                 | Blog primario 3-8 articoli/giorno + carousel/thread/newsletter derivati               |
| D9  | Volume blog target: **3-5 articoli/giorno** produzione standard, fino a 8 su urgenza                      | Configurabile per registro + fase lunare editoriale                                   |
| D10 | Gerarchia output: **articolo blog primario**, altri formati derivati in cascata                           | Coerenza narrativa, ammortizza costo ricerca                                          |
| D11 | Dossier ammortizzato su **10 consumatori** (cfr. §16)                                                     | Nessun dossier produce un solo artefatto                                              |
| D12 | **4 livelli cognitivi** sopra i dossier: Connector, Anomaly Detector, Strategos, Oracle                   | Realizza Pilastro 3 Livello 3 (`SYMBIOSIS.md:101`) oggi solo scritto come aspirazione |
| D13 | Oracle output va **solo a Zero** via Telegram (Legge 5 Zero ultima istanza)                               | Team non riceve "mosse ultra" senza approvazione                                      |
| D14 | Oracle cadence **weekly** (domenica 22:00 WITA)                                                           | Basso rumore, alto segnale                                                            |
| D15 | Dossier pre-generazione **hybrid**: top-20 per `urgency_score` pre-computati rolling 24h; resto on-demand | Velocità War Room + efficienza Intel                                                  |

---

## 15. Intel Scraper riposizionato — layer cognitivo sensoriale

### 15.1 Ruolo attuale (fatti verificati)

- Path: `apps/bali-intel-scraper/`
- Host: Pro locale via OpenClaw cron 03:00 WITA (`CLAUDE.md §8`)
- Struttura esistente: `backend/scrapers/` + `backend/processors/{classifier,quality_scorer}.py` + `backend/services/` + routers API
- Output oggi: Qdrant collection `balizero_news` + GitHub publisher (`apps/bali-intel-scraper/README.md:14`)
- Alimenta: War Room v1 via merge manuale + Zantara RAG via Qdrant

### 15.2 Ruolo futuro (ridefinizione)

Intel Scraper diventa **unico organo sensoriale** dell'organismo Nuzantara. Responsabilità:

1. **Sense** — raccogliere segnali grezzi da fonti Indonesia/compliance/visa/KBLI
2. **Normalize** — deduplicare, estrarre entità, scoring qualità
3. **Dossier** — comporre `ResearchDossier` strutturati per topic
4. **Publish** — depositare in KG (nodi `ResearchDossier` + `TrendSignal`) + PG + Qdrant

**Cosa NON fa più** (scarica fuori):

- Drafting editoriale (→ War Room Drafter M5)
- Selezione registro tonale (→ War Room Consiglio M4)
- Decisione pubblicazione (→ Zero via Review Gate M11)
- Fact-check applicato a prosa (→ Consiglio M4 valida citando dossier)

### 15.3 Due artefatti prodotti

| Artefatto             | Formato                                      | Cosa è                                                                                                      | TTL                   |
| --------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------- |
| **`TrendSignal`**     | Nodo KG + Redis Stream                       | Segnale grezzo normalizzato: `{source, topic, urgency_score, bz_relevance, timestamp, decay_half_life}`     | 48-72h                |
| **`ResearchDossier`** | Nodo KG + Row PG `research_dossiers` + JSONB | Dossier strutturato per topic: fatti verificati, numeri, citazioni normative, entità linkate, domini target | 30gg (poi archiviato) |

### 15.4 Schema `ResearchDossier`

```
research_dossiers
  id UUID PK
  slug TEXT UNIQUE          -- es. "permenkumham-22-2023-art-51-b211a-fourth-extension"
  title TEXT
  topic_category TEXT       -- visa|tax|kbli|property|compliance|cultural|macro
  domains JSONB             -- array target consumer: [chatbot, alerting, editorial, newsletter, notebook]

  facts JSONB               -- [{claim, source_url, confidence, verified_at}]
  numbers JSONB             -- [{metric, value, unit, period, source}]
  citations JSONB           -- [{norma, articolo, comma, quote_exact, year}]
  entities_linked JSONB     -- [{kg_entity_id, type, role}]
  precedents JSONB          -- [{dossier_id_related, relation}]

  confidence_0_1 NUMERIC
  freshness_expiry TIMESTAMPTZ

  source_signals JSONB      -- [trend_signal_id, ...]

  language TEXT             -- id|en|it (most facts in Indonesian source)
  summary_short TEXT        -- 140 char
  summary_medium TEXT       -- 500 char

  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ
  archived_at TIMESTAMPTZ NULL

  INDEX (topic_category), (freshness_expiry), (confidence_0_1)
  GIN INDEX on domains, entities_linked
```

### 15.5 Pre-generazione hybrid

- **Batch pre-compute** (cron 04:00 WITA dopo Intel 03:00): seleziona top-20 `TrendSignal` per `urgency_score × bz_relevance` → genera `ResearchDossier` per ciascuno
- **On-demand**: War Room Director M4 richiede `dossier_for(topic)` → se esiste e `freshness_expiry > now`, usa; altrimenti trigger compile sincrono (3-5min)
- **Refresh**: dossier con `freshness_expiry < 12h` viene ri-compilato al prossimo batch

### 15.6 Integrazione con War Room

War Room M3 Research (Parte I §1) **scompare** — sostituito da:

```
M4 Director riceve:
  ResearchDossier (da Intel)
  + TrendSignal ultime 12h (da Intel stream)
  + genome skills + scars (da Learner iniezione)
  + brand.json + zantara_core.py (voce)
```

Il Consiglio parte direttamente dal dossier strutturato. **Risparmio tempo**: 3-6min per ciclo.

---

## 16. Dossier ammortizzato — 10 consumatori

Ogni `ResearchDossier` è letto da ≤10 consumatori diversi con scopo distinto. Nessun dossier produce un solo artefatto.

### 16.1 Mappa consumatori (valore decrescente)

| #   | Consumatore                      | Path                                                                          | Uso dossier                                              | Output                            |
| --- | -------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------- | --------------------------------- |
| 1   | **Zantara chatbot RAG**          | `apps/backend-rag/backend/prompts/zantara_core.py`                            | Risposte a clienti visa/tax/KBLI; citazioni `📜 Sumber:` | Accuratezza +, escalation umana − |
| 2   | **CRM compliance alerting**      | `scripts/crm_automation_engine.py` (cron 07:00)                               | Join dossier con `clients` target → alert proattivi      | Email one-to-one targetizzata     |
| 3   | **NotebookLM feeders**           | NB-2 (immigration), NB-3 (company), NB-4 (tax), NB-5 (property), NB-8 (cross) | Upload dossier come source nuova                         | Notebook autoritativi evolvono    |
| 4   | **KG Curiosity Loop**            | `apps/graph-engine/src/nuzantara_graph/curiosity/`                            | Dossier chiude gap topic; CuriosityGrader input          | 56 gap topics progressivi         |
| 5   | **Consiglio v1** (LIVE)          | path da verificare                                                            | Input deliberazione invece di web search al volo         | Decisioni meglio informate        |
| 6   | **War Room Director M4**         | Parte I §1 + §3                                                               | Consiglio tone + concept parte da dossier                | Articoli blog + carousel + thread |
| 7   | **Newsletter settimanale** (NEW) | `apps/backend-rag/backend/services/communication/` (DA VERIFICARE)            | Roundup 5 dossier più importanti della settimana         | 1 email ogni lunedì               |
| 8   | **Guardian V5**                  | `.claude/rules/cicatrix-scars.md` + auto-calibration                          | Pattern mining su frequenza topic per evolvere regole    | Skill/scar promozione             |
| 9   | **Team Workspace search**        | `apps/kita` (Cmd+J) + MCP                                                     | Team (Damar, Adel, Dea) cerca dossier per caso cliente   | Knowledge interna ricercabile     |
| 10  | **Intel pubblica selettiva**     | Via War Room fast-track                                                       | Alert pubblici gratuiti (lead magnet) + press release    | Autorità brand                    |

### 16.2 Principio di ammortamento

Un dossier (costo ricerca ~$0.20-0.40 in LLM calls + tempo Intel) è letto ≥3 volte nei 30gg di validità → costo marginale per uso crolla. **ROI di Intel misurato in `dossier_reuse_ratio` (reads/dossier_compiled)**, target ≥5 dopo 60gg di maturità del sistema.

### 16.3 Regole di accesso

- **OSINT blindato** (Legge 2): `ResearchDossier.domains` include `public_safe` flag. Solo dossier con `public_safe=true` possono diventare artefatti pubblici (blog, newsletter, IG). Dossier sensibili (intelligence interna) restano per CRM alerting e team.
- **Freshness enforcement**: consumatore deve verificare `freshness_expiry` prima di usare. Dossier scaduti → trigger refresh.

---

## 17. Sistema cognitivo a 4 livelli

Sopra i dossier opera un sistema che **ragiona** invece di leggere. Realizza il Pilastro 3 Livello 3 (`SYMBIOSIS.md:101` — "Un LLM rilegge tutto e produce sintesi cross-sistema") oggi scritto solo come aspirazione.

### 17.1 Livello 1 — **Connector** (pattern cross-dossier)

**Responsabilità**: scansionare N dossier nel tempo e trovare connessioni non ovvie tra segnali separati.

**Esempio output reale**:

> Dossier A (3 settimane fa): "Bank Indonesia stringe regolazione crypto exchange"
> Dossier B (1 settimana fa): "Coretax introduce nuovo DPP tax su digital service"
> Dossier C (3 giorni fa): "OJK richiede KYC rafforzato per PSE digital"
>
> **Tesi Connector**: "Indonesia costruisce perimetro digital-compliance unificato 2026. Client PT PMA fintech/SaaS hanno 90 giorni prima che KYC+DPP+crypto-reg convergano."

**Meccanismo**:

- Cron notturno 04:00 WITA (dopo Intel batch + dossier pre-compute)
- Claude CLI con context 500K riceve 30 dossier più recenti + prompt "trova 3 tesi cross-dossier che nessun singolo dossier esprime"
- Output `CrossDossierThesis` JSON + insert KG nodo `(:Thesis)-[:SYNTHESIZES]->(:ResearchDossier)`

**Schema `cross_dossier_theses`**:

```
id · title · narrative · source_dossier_ids[] · confidence · implication
target_clients_query TEXT  -- SQL filter per clienti interessati
generated_at · valid_until
```

**Consumatori**: Strategos (§17.3), Oracle (§17.4), CRM alerting, Zero Telegram summary

### 17.2 Livello 2 — **Anomaly Detector** (contraddizioni e scostamenti)

**Responsabilità**: trovare contraddizioni numeriche/normative tra dossier o scostamenti dal baseline.

**Esempio output reale**:

> Dossier A: "DJP estende grace period PPh 2025 a giugno" (fatto: prorogato)
> Dossier B (stessa settimana): "Coretax emette 847 notifiche art.9 PPh per mancato pagamento Q1 2025" (fatto: sanzioni attive)
>
> **Anomalia**: grace period apparente + enforcement attivo = "proroga NON automatica, richiede domanda formale". Alert client PT PMA.

**Meccanismo**:

- Trigger: su ogni nuovo dossier inserito, job Python confronta claim numerici + normativi con dossier topic correlati ultimi 30gg
- Quando `contradiction_score > 0.7` (calcolato via embedding + keyword overlap + Claude CLI valutazione semantica)
- Output: `ComplianceAlert` in PG + Telegram a Zero + flag in CRM per clienti interessati

**Schema `compliance_alerts`**:

```
id · detected_at · dossier_a_id · dossier_b_id · contradiction_type · severity
suggested_action · affected_client_query · notified_zero · resolved
```

### 17.3 Livello 3 — **Strategos** (strategia editoriale + compliance)

**Responsabilità**: ragionare su dossier + performance storica War Room + cicatrici + metriche chatbot → proporre **direzione settimanale** a Zero.

**Esempio output reale**:

> Negli ultimi 14 giorni: 23 chiamate Zantara su Permenkumham 22/2023.
> Dossier D-47 e D-52 toccano art.51.
> War Room ha pubblicato 1 post analitico sul tema (reach sotto media 30gg).
> Cicatrix scar #18: post cinici su immigration performano male.
>
> **Tesi Strategos**: "Clienti vogliono chiarezza pedagogica, non allarme.
> **Azione proposta**: commissiona 3 articoli pedagogici + 1 webinar interno per team.
> **KPI settimana**: reach +20% su tema visa, escalation Zantara -30%."

**Meccanismo**:

- Cron weekly domenica 22:00 WITA
- Claude CLI con mega-context:
  - Dossier ultimi 30gg (top 50 per rilevanza)
  - Summary conversazioni Zantara ultimi 14gg aggregati per tema
  - `war_room_metrics` ultimi 30gg per piattaforma+registro
  - Genome skills + scars ultimi 30gg
  - Cross-dossier theses ultimi 7gg
- Output `WeeklyStrategicBrief` in PG + Telegram a Zero per approvazione lunedì mattina

**Schema `weekly_strategic_briefs`**:

```
id · week_of (DATE) · top_themes JSONB · proposed_actions JSONB
kpi_targets JSONB · team_assignments JSONB · zero_approval BOOLEAN · approved_at
```

**Differenza con Oracle**: Strategos propone direzione settimanale (pianificazione editoriale), Oracle propone mosse ultra singole non richieste (strategia opportunistica).

### 17.4 Livello 4 — **Oracle** (mosse ultra non richieste)

**Responsabilità**: sessione Consiglio multi-LLM periodica che propone ≤3 "mosse ultra" alla settimana che nessuno ha richiesto.

**Esempio output reale #1**:

> Dossier A+B+C suggeriscono che entro settembre DJP avvierà cross-check automatico NPWP↔BPJS↔OSS. Client PT PMA con discrepanze anagrafiche tra i tre sistemi verranno flaggati.
>
> **Mossa Oracle**: audit pre-flight su 458 client PMA (query SQL già eseguibile in CRM). Costo: 2 giorni lavoro. Valore: evitiamo flag automatico + upsell servizio compliance.

**Esempio output reale #2**:

> Kelingking Beach enforcement è precedente. Dossier D-89 parla di 3 altre spiagge target (Suluban, Padang-Padang, Bingin). Client con villa su queste 3 spiagge hanno 60gg prima che pattern arrivi.
>
> **Mossa Oracle**: email one-to-one con verifica NIB + IMB a 34 client identificati. Zero prezzo aggressivo, tono rituale-analitico.

**Meccanismo**:

- Cron weekly domenica 22:00 WITA (dopo Strategos)
- **Consiglio multi-LLM esteso** (non il Consiglio tone del War Room): 4 voci + 1 giudice
  - V1: `claude -p` Opus persona "strategic analyst, McKinsey style"
  - V2: `gemini -p` Pro persona "compliance lawyer, Indonesian bar"
  - V3: DeepSeek R1 HTTP persona "behavioural economist"
  - V4: Ollama `gemma4:26b` persona "skeptic devil's advocate"
  - Judge: `claude -p` Sonnet con accesso: Strategos brief + Connector theses + metriche chatbot + CRM segments
- Protocollo: 3 round come Consiglio tone (§3 Parte I) ma contesto più ampio e output prescrittivo
- Output: ≤3 `UltraMove` settimana in PG + Telegram a Zero "martedì mattina" (dopo che Zero ha visto Strategos lunedì)

**Schema `ultra_moves`**:

```
id · proposed_at · thesis · narrative · target_query · estimated_cost
estimated_value · recommended_tone_register · source_inputs JSONB
zero_decision (pending|approved|rejected|deferred) · decided_at · notes
```

**Regola Legge 5**: Oracle **non esegue nulla**. Solo propone. Zero decide.

---

## 18. Architettura cognitiva completa

```
FONTI GREZZE (web, social, RSS, gov sites)
       ↓
INTEL SCRAPER  (sense + normalize)
       ↓
   ┌───┴───┐
   ↓       ↓
TrendSignal  ResearchDossier
   ↓          ↓
   └──→ Consumer ×10 (RAG/alert/notebook/...) ←──┐
                                                  │
       ┌──────────────────────────────────────────┤
       ↓                                          │
[L1 Connector] → CrossDossierThesis ──────────────┤
       ↓                                          │
[L2 Anomaly]   → ComplianceAlert → Zero Telegram  │
       ↓                                          │
[L3 Strategos] → WeeklyStrategicBrief → Zero      │
       ↓                                          │
[L4 Oracle]    → UltraMove ×3/sett → Zero         │
       ↓                                          │
War Room Director (Consiglio tone) ←──────────────┘
       ↓
Drafter → Visual → Layout → Review Gate → Publisher (blog 3-8/gg + carousel + thread + newsletter)
       ↓
Measurer → Learner → genome (skill/scar)
       ↓
[iniezione prossimo ciclo]
```

**Ogni livello legge anche gli output dei livelli sotto.** Oracle vede Connector + Anomaly + Strategos + tutti i dossier + war_room_metrics + chatbot conversations. È il **culmine cognitivo** dell'organismo.

---

## 19. Volume editoriale target (produzione War Room v2)

### 19.1 Cadence standard

| Formato                 | Volume/giorno             | Volume/settimana | Derivato da                                |
| ----------------------- | ------------------------- | ---------------- | ------------------------------------------ |
| Articolo blog long-form | 3-5 (fino a 8 su urgenza) | 21-35            | Dossier diretto                            |
| Carousel IG             | 1-2                       | 7-14             | Articolo blog → compressione visuale       |
| Thread X                | 2-3                       | 14-21            | Articolo blog → snippets                   |
| Post LinkedIn           | 1-2                       | 7-14             | Articolo blog → registro tecnico/analitico |
| Newsletter              | —                         | 1 (lunedì)       | Roundup settimanale + Strategos brief      |
| Press release selective | 0-1                       | 0-3              | Oracle UltraMove approvata                 |

### 19.2 Gerarchia di output (cascata)

```
Dossier → Articolo blog (primario, ~800-1500 parole)
              ↓
              ├── Carousel IG (riassunto visuale 6-8 slide)
              ├── Thread X (6-10 tweet)
              ├── Post LinkedIn (stesso registro tecnico)
              └── Section newsletter (paragrafo roundup)
```

**Vantaggio**: coerenza narrativa garantita (tutto parte dallo stesso articolo → stessi fatti, stessa interpretazione, stesso registro tonale scelto dal Consiglio).

### 19.3 Distribuzione registri su 7 giorni (target)

Per evitare monotonia e rispettare hard rule Consiglio (max 3 stesso registro/settimana):

```
Lun: 1 analitico + 1 pedagogico + 1 rituale (settimana nuova)
Mar: 2 tecnico + 1 ironico
Mer: 1 militante + 1 analitico + 1 poetico
Gio: 1 tecnico + 2 pedagogico
Ven: 1 ironico + 1 analitico
Sab: 1 rituale (longform weekend)
Dom: OFF (solo Connector/Strategos/Oracle cognitive pipeline)
```

Il Consiglio rispetta questa distribuzione come soft target; può deviare se urgenza lo richiede.

---

## 20. Moduli nuovi (estensione Parte I)

Aggiunti ai 14 moduli M1-M14 della Parte I:

| ID      | Modulo                                    | Responsabilità                                                      | Host                    | Pilastri |
| ------- | ----------------------------------------- | ------------------------------------------------------------------- | ----------------------- | -------- |
| **M0a** | **Intel Scraper Dossier Compiler**        | Produce `ResearchDossier` da `TrendSignal` + fonti verificate       | Pro                     | 2, 6     |
| **M0b** | **Dossier Reuse Router**                  | Traccia quali consumatori usano ogni dossier; calcola `reuse_ratio` | Pro                     | 3, 7     |
| **M0c** | **Domain Fanout Dispatcher**              | Route dossier ai 10 consumatori secondo `domains` array             | Pro                     | 3        |
| **M15** | **Connector** (L1)                        | Pattern cross-dossier daily                                         | Pro (04:00 cron)        | 4, 6     |
| **M16** | **Anomaly Detector** (L2)                 | Contraddizioni event-driven                                         | Pro (on dossier insert) | 4, 7     |
| **M17** | **Strategos** (L3)                        | Brief strategico weekly                                             | Pro (dom 22:00)         | 1, 4, 7  |
| **M18** | **Oracle** (L4)                           | Mosse ultra weekly via Consiglio esteso                             | Pro (dom 22:30)         | 4, 6, 8  |
| **M19** | **Blog Publisher** (estensione M12)       | MDX commit multi-articolo/giorno                                    | Pro → GitHub → Vercel   | 3        |
| **M20** | **Newsletter Publisher** (estensione M12) | Email roundup settimanale lunedì                                    | Pro                     | 3        |

M3 Research (Parte I) **deprecato** — rimpiazzato da M0a+M0b+M0c.

---

## 21. Schema metriche esteso (Parte II)

Aggiunte alla `migration_112_war_room_tables.py` (Parte I §7.1):

```sql
-- Intel Scraper dossier
research_dossiers (schema §15.4)

dossier_reuses
  id · dossier_id FK · consumer_type (chatbot|crm|nlm|curiosity|council|warroom|newsletter|guardian|team|public)
  consumer_entity_id · used_at · context_meta JSONB
  INDEX (dossier_id, consumer_type), (used_at)

dossier_refresh_log
  dossier_id FK · refreshed_at · reason (expiry|new_source|manual|consumer_request)
  diff_summary TEXT · new_confidence NUMERIC

-- Sistema cognitivo
cross_dossier_theses (schema §17.1)
compliance_alerts (schema §17.2)
weekly_strategic_briefs (schema §17.3)
ultra_moves (schema §17.4)

-- Editoriale esteso
blog_posts
  id UUID · draft_id FK → war_room_drafts · slug UNIQUE · mdx_path TEXT
  word_count INT · register TEXT · published_at · vercel_preview_url TEXT

newsletter_issues
  id UUID · week_of DATE · section_dossier_ids JSONB · sent_at · subscribers_count
  open_rate · click_rate · unsubscribes INT
```

### 21.1 Metriche Intel

Nuove righe in `war_room_metrics` (o nuova tabella `intel_metrics`):

```
metric_name | source        | descrizione
------------+---------------+-------------------------------------------
dossier_compiled_24h           | intel_batch   | quanti dossier prodotti
dossier_reuse_ratio_30d        | dossier_reuses| reads/compiled
dossier_freshness_median       | dossier_batch | età media dossier attivi
consumer_coverage              | dossier_reuses| % consumer types attivati
cross_dossier_theses_7d        | connector     | quante tesi emerse
compliance_alerts_7d           | anomaly       | alert prodotti
ultra_moves_weekly             | oracle        | mosse proposte
zero_approval_rate_oracle      | ultra_moves   | % approvate Zero
```

---

## 22. Roadmap sprint esteso (Parte II)

Aggiungo Sprint 13-18 ai 12 sprint della Parte I. Possibile parallelizzazione con Sprint 3-5.

### Sprint 13 — Intel Scraper dossier schema + compiler (M0a)

- Migration `migration_113_research_dossiers.py` (tabelle §15.4 + §21)
- `apps/bali-intel-scraper/backend/processors/dossier_compiler.py` (nuovo)
- `ResearchDossier` Pydantic model + CRUD service
- **Done**: 10 dossier reali compilati da TrendSignal pipeline; schema valida via pytest
- **Dipendenze**: S1 (EventBus canale `war_room_event` esteso a `intel_event`)

### Sprint 14 — Dossier fanout + 10 consumer integration (M0b + M0c)

- `Domain Fanout Dispatcher` (cron post-Intel batch)
- Integrazione con 5 consumer priority: Zantara RAG (Qdrant upsert), CRM alerting (join query), NLM feeders (upload source), Curiosity grader (gap closure), War Room Director (read dossier)
- **Done**: dossier creato → 5 consumer leggono entro 30min; `dossier_reuses` table popolata
- **Dipendenze**: S13

### Sprint 15 — Connector L1

- `apps/cognitive/connector.py` (nuovo; path da decidere, probabile nuova app `apps/cognitive` o sub di mata-garuda)
- Cron 04:00 WITA con Claude CLI context 500K
- Schema `cross_dossier_theses` + KG insert
- **Done**: 7gg staging → ≥3 tesi cross-dossier/settimana; qualitative review Zero verde
- **Dipendenze**: S13

### Sprint 16 — Anomaly Detector L2

- `apps/cognitive/anomaly_detector.py` (nuovo)
- Event-driven su `intel_event:dossier_inserted`
- Contradiction scoring via embedding + Claude CLI semantic
- **Done**: fixture 20 coppie dossier note contraddittorie → recall ≥0.7; alert Zero funzionante
- **Dipendenze**: S13

### Sprint 17 — Strategos L3

- `apps/cognitive/strategos.py` (nuovo)
- Cron weekly dom 22:00 WITA
- Mega-context gathering (dossier + chatbot summaries + war_room_metrics + genome)
- Telegram delivery con inline keyboard approve/adjust
- **Done**: 4 settimane di brief staging → Zero approva ≥50% senza modifiche; KPI target misurabili
- **Dipendenze**: S13, S15, Parte I S10 (Learner)

### Sprint 18 — Oracle L4 (Consiglio cognitivo esteso)

- `apps/cognitive/oracle.py` (riusa `CouncilCLIAdapter` Parte I §3)
- 4 voci + giudice, 3 round, contesto full-stack
- Cron dom 22:30 WITA (dopo Strategos)
- Telegram a Zero martedì mattina con 3 UltraMove proposte
- **Done**: 4 settimane staging → ≥8 UltraMove proposte totali, ≥2 approvate Zero, zero esecuzione automatica
- **Dipendenze**: S17 + Parte I S6 (Review Gate pattern)

### Sprint 19 — Blog Publisher estensione (M19)

- Scaffold `apps/blog/` Next.js se assente (DA VERIFICARE)
- `BlogPublisher` multi-articolo/giorno con MDX front matter
- Volume target 3-5/giorno con hard rule max 8
- **Done**: 1 settimana staging → 21 articoli pubblicati su preview Vercel; distribuzione registri conforme §19.3
- **Dipendenze**: Parte I S8

### Sprint 20 — Newsletter Publisher (M20)

- `NewsletterPublisher` Brevo-based (pattern esistente `CLAUDE.md §10`)
- Roundup weekly domenica/lunedì 06:00 WITA con 5 top dossier + Strategos brief
- Template HTML email-safe
- **Done**: 2 newsletter test → open rate ≥20%, zero bounce
- **Dipendenze**: S17

**Tempo totale Parte I + II**: 20 sprint × 2-3gg = **40-60gg** sequenziali. Con parallelizzazione realistica (S13-S14 paralleli a S2-S3; S15-S16 paralleli a S4-S6; S19 parallelo a S8): **~35gg calendario**.

---

## 23. Costi operativi estesi

### 23.1 Intel Scraper (esistente + dossier)

- Oggi: ~$2/mese (Qdrant upsert + LLM enrichment)
- Dopo: +~$5/mese (20 dossier pre-generati × $0.20 in LLM = $4 + storage PG trascurabile)
- **Totale Intel: ~$7/mese**

### 23.2 Sistema cognitivo (4 livelli)

| Livello                | Cadenza                 | Costo/ciclo                                                               | Costo/mese   |
| ---------------------- | ----------------------- | ------------------------------------------------------------------------- | ------------ |
| Connector              | Daily                   | Claude CLI (OAuth flat) + $0.01 embedding                                 | ~$0.30       |
| Anomaly Detector       | Event-driven (~50/mese) | Claude CLI + $0.01                                                        | ~$0.50       |
| Strategos              | Weekly                  | Claude CLI OAuth flat                                                     | $0           |
| Oracle (Consiglio 4+1) | Weekly                  | 4 voci + judge (Claude OAuth + Gemini OAuth + DeepSeek $0.02 + Ollama $0) | ~$0.10       |
| **Totale cognitivo**   | —                       | —                                                                         | **~$1/mese** |

### 23.3 War Room produzione estesa

- Parte I baseline: ~$6/mese (1 carousel/giorno)
- Produzione blog 3-5 articoli/giorno: +2 carousel/giorno = $0.32 × 60 = ~$19/mese Imagen
- Newsletter weekly: zero costo incrementale (usa dossier esistenti)
- **Totale War Room esteso: ~$25/mese**

### 23.4 Grand total

**~$33/mese** (Intel + Cognitive + War Room) per un sistema cognitivo-editoriale che produce:

- 20+ dossier/settimana ammortizzati su 10 consumatori
- 21-35 articoli blog/settimana
- 7-14 carousel IG/settimana
- 14-21 thread X/settimana
- 1 newsletter/settimana
- 3 UltraMove/settimana
- 1 Strategos brief/settimana
- ~50 ComplianceAlert/mese
- ~12 CrossDossierTheses/mese

---

## 24. Rischi aggiuntivi Parte II + mitigazioni

| Rischio                                           | P   | I   | Mitigazione                                                                                                  |
| ------------------------------------------------- | --- | --- | ------------------------------------------------------------------------------------------------------------ |
| Dossier compilati ma non consumati (spreco)       | M   | M   | `dossier_reuse_ratio` metric; alert Zero se <2 dopo 30gg; Intel riduce volume                                |
| Connector allucina connessioni false              | M   | H   | Output valutato da giudice Oracle; Zero vede summary weekly; confidence minimum 0.7                          |
| Anomaly Detector false positive (flood Zero)      | H   | M   | `severity` threshold + daily digest invece di real-time; Zero può silenziare per topic                       |
| Strategos prescrive azioni irrealistiche          | M   | M   | Template action schema vincola a `{budget, timeline, team, KPI}`; Zero può rigettare                         |
| Oracle mosse pericolose (reputazione, legale)     | L   | H   | Veto umano obbligatorio Zero; Oracle flag `requires_legal_review` per topic sensibili                        |
| Volume blog degrada qualità                       | H   | H   | Consiglio hard rule: se `composite_score` ultimi 7 articoli < p40, riduce volume a 2/giorno finché recupera  |
| Newsletter unsubscribe cascade                    | M   | M   | A/B test tone; opt-in granulare (weekly/monthly/breaking); unsubscribe ≥5%/mese → alert                      |
| Dossier contraddizione con notebook NLM (NB-2..8) | M   | H   | Freshness check: dossier recente > notebook se age <14gg; altrimenti NLM wins                                |
| Privacy leak in dossier (cliente menzionato)      | L   | H   | `public_safe` flag validato da regex su entity_types (no `Client`, `Practice`, `Contact`) prima di fanout 10 |
| Cognitive infinite loop (L1→L3→L4 dipendono L1)   | L   | M   | DAG espliciti: L1 input=dossier only; L3/L4 input=L1+metrics; no cicli                                       |

---

## 25. Definizione di "fatto" per sistema cognitivo

**Intel Scraper (Parte II)**:

1. Dossier schema validato Pydantic
2. `dossier_reuse_ratio` ≥3 dopo 30gg staging
3. Coverage ≥6/10 consumer types attivi
4. Freshness SLA: 95% dossier con `freshness_expiry` rispettato

**Connector L1**:

1. ≥3 tesi/settimana generate
2. Qualitative review Zero ≥60% "interessanti"
3. Zero groupthink (tesi rifiutate se tutti dossier sorgente dello stesso tag)

**Anomaly Detector L2**:

1. Recall ≥0.7 su fixture 20 coppie note
2. False positive rate <20%
3. Zero flood: max 5 alert/giorno a Zero

**Strategos L3**:

1. Brief entro 6 ore domenica
2. Zero approva ≥50% senza modifiche in 4 settimane
3. KPI proposti misurabili (schema `{metric, target, deadline}` validato)

**Oracle L4**:

1. 3 UltraMove/settimana
2. ≥2/mese approvate Zero (ratio >0.16)
3. Zero esecuzione automatica (verifica manuale + PG audit)

**Blog Publisher M19**:

1. 21 articoli/settimana media su 4 settimane
2. Distribuzione registri conforme §19.3 (tolleranza ±20%)
3. Vercel preview deploy verde 100%

**Newsletter M20**:

1. Open rate ≥20% dopo 4 settimane
2. Unsubscribe ≤2%/mese
3. Click-through ≥5% su link principali

---

## 26. Pilastri 8 completi — mappa aggiornata con Parte II

| #   | Pilastro      | Moduli primari Parte I   | Moduli Parte II                           | Metrica chiave                               |
| --- | ------------- | ------------------------ | ----------------------------------------- | -------------------------------------------- |
| 1   | Riflessione   | M14 Learner              | M17 Strategos (legge storico)             | `reflection_injection_size`                  |
| 2   | Accumulazione | M14, M6 banlist          | M0a Intel compiler (ogni dossier = skill) | `dossier_count`, `skill_count`               |
| 3   | Condivisione  | EventBus + Redis         | M0c Fanout 10 consumer                    | `consumer_coverage`                          |
| 4   | Confronto     | M4 Consiglio tone        | M18 Oracle Consiglio esteso               | `council_rounds_weekly`                      |
| 5   | Sogno         | M14 notturno             | M17 Strategos consolidation weekly        | `weekly_brief_approval_rate`                 |
| 6   | Curiosità     | M1 Trend-Hunter          | M15 Connector, M0a dossier exploration    | `novel_theses_weekly`                        |
| 7   | Misura        | M13 Measurer + dashboard | Metriche Intel + cognitive                | `dossier_reuse_ratio`, ultra_move_acceptance |
| 8   | Simbiosi      | M11 Review Gate          | M18 Oracle (Zero decide mosse)            | `ultra_move_zero_decision_rate`              |

**Tutti e 8 i pilastri sono ora realizzati operativamente**, non solo aspirazionali. Il Livello 3 del Pilastro 3 (`SYMBIOSIS.md:101`) — scritto come aspirazione — diventa concreto nel Sistema cognitivo a 4 livelli.

---

## 27. Note finali Parte II

War Room 2.0 + Intel riposizionato + sistema cognitivo costituiscono il **cervello editoriale** dell'organismo Bali Zero. Gli organi sensoriali (Intel) raccolgono, gli organi cognitivi (Connector/Anomaly/Strategos/Oracle) ragionano, gli organi effettori (War Room production) producono, i consumatori ammortizzano, Zero decide (Legge 5).

Costo totale: **~$33/mese** per un newsroom compliance automatizzato con intelligenza strategica integrata.

Tempo di implementazione: **~35gg calendario** con parallelizzazione.

Valore: Bali Zero passa da _"pubblica 1 carousel/giorno con stesso tono"_ a _"newsroom autorevole con 3-5 articoli editoriali/giorno, ammortizzati su 10 canali, guidati da 4 livelli di ragionamento cognitivo sopra la ricerca primaria"_. Realizza concretamente la visione SYMBIOSIS — un organismo che non solo produce, ma pensa e propone.
