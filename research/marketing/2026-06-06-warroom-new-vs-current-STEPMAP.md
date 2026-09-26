# War Room — Nuova architettura ║ WR2 attuale (step-by-step, cosa deve cambiare)

**Captured**: 2026-06-06
**Author**: Claude Opus 4.8 (orchestrator) + 2 agenti freschi (audit-codice-vivo Sonnet + architetto Opus)
**Companion del report**: `2026-06-06-sota-carousel-automation.md` (i 7 bricks + gap P1-P7). Questo file è il **confronto operativo affiancato** che Antonello ha chiesto.
**Metodo**: agenti freschi su world-state reale. Ogni riga "ATTUALE" è dal codice vivo (file:riga). Ogni riga "NUOVA" è legata a un brick del report.

> ⚠️ **Scoperta capitale dall'audit del codice vivo**: WR2 oggi ha **DUE pipeline che non si parlano**.
>
> - **PATH A** (vivo H24, cron, tabella `war_room_drafts`): è quello che produce davvero. **NON ha critic di brand/qualità.**
> - **PATH B** (scritto ma plist `.example`, NON installato, tabella `wr2_carousel_runs`): è dove vivono i 5 subagent + il critic. **Non gira.**
>
> Questo conferma l'autopsy del 2026-06-04 ("A intelligente = dead-code, B che pubblica = text-swap"). La nuova architettura **fonde i due path in uno**: il path-A vivo eredita il critic e l'intelligenza del path-B, dentro un control-flow durevole.

---

## 0. Il quadro in una figura

```
                     WR2 ATTUALE (Path A vivo)                    │   NUOVA WAR ROOM (path unico, LangGraph)
─────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────
 cron 05:10                                                       │   LangGraph StateGraph (orchestratore Opus unico)
   │                                                              │   route_on_status(state)→next  [edge legge enum,
   ▼  INSERT status='briefed'                                     │                                  non la prosa LLM]
 topic_selector.py ──NOTIFY──► supervisor.py ──launchctl──┐       │   checkpoint Postgres ogni nodo (crash-resume)
   │ (scoring deterministico)        kickstart             │      │        │
   ▼                                                       ▼      │        ▼
 draft_generator.py (opus-4-7)  ── slides_json 11 slide          │   [1] topic_selector (invariato) + legge negative-lib
   │ brief TRONCATO 25% (full-prompt OFF default!)               │   [2] brief-interpreter + NotebookLM + instructor✓
   ▼                                                              │   [3] storyboarder + instructor✓ (schema enforced)
 image_generator.py  ── 4 hero (Codex→FlowKit→Playwright)        │   [4] hero-gen: Nano Banana Pro 14-ref ($0) ⇐ P1
   │  VLM gate qwen2.5vl SOLO prompt↔img (NON brand)             │        consistenza cross-slide (luce/palette coerenti)
   ▼                                                              │   [5] render ReportLab→Canva (TENUTO — D2)
 fact_extractor.py (opus) ─► fact_checker.py                     │   [6] CRITIC VLM brand+qualità (Opus vision) ⇐ NUOVO
   │  fact_checker NO-OP default (disabled!)                     │        binario PASS/FAIL + context-isolation + retry_priority
   ▼  status='drafts_imaged_checked'                             │   [7] human gate: Canva editabile + Telegram (Legge 5)
 canva_renderer (300s, lease) ── ReportLab PDF→Tigris→Canva MCP  │        LangGraph interrupt() durevole
   │  ⚠️ ZERO critic brand in tutto il path A                    │   [8] Reflexion settimanale + negative-example library ⇐ P7
   ▼  status='rendered'  → Telegram → STOP (Legge 5)             │
                                                                  │   STOP a status='rendered'/'pending_review' (Legge 5 invariata)
─────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────
 PATH B (5 subagent + critic) = SCRITTO MA .example, NON GIRA    │   ⇒ Path B viene ASSORBITO qui: i subagent + il critic
                                                                  │     diventano i nodi [2][3][6] del path unico
```

---

## 1. Confronto stadio-per-stadio (la tabella affiancata)

Legenda: **=** invariato · **+** aggiunta SOTA · **⚑** decisione controcorrente · 🔴 fragilità attuale che si chiude.

### Stadio 0 — Orchestrazione / control-flow

|           | WR2 ATTUALE                                                                                                                                                        | NUOVA WAR ROOM                                                                                                         | Cosa cambia                                                                                  |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Chi guida | `wr2_supervisor.py` (daemon) + NOTIFY `wr2_status_change` + `launchctl kickstart`. Script-driven imperativo (37KB tra supervisor+orchestrator).                    | **LangGraph `StateGraph`**, orchestratore Opus unico, `route_on_status(state)→next_node` su enum.                      | **D1/P6.** Il gate non è più "il modello decide", è una conditional-edge che legge `status`. |
| Stato     | `war_room_drafts.status` (17 valori, mig 163) + CAS-lease (mig 170).                                                                                               | **Stessa tabella** (è già la macchina a stati) + checkpoint `langgraph.checkpoint*` per il nodo-in-corso.              | Riusa `get_checkpointer()` **già in-tree** (`services/workflow/checkpointer.py`).            |
| Resume    | 🔴 draft persi su deploy-restart (W64/503-family: macchina stuck-stopped). `_recently_dispatched` in-memory → double-kickstart post-restart (`supervisor.py:126`). | Crash-resume dal checkpoint; retry-3 del critic non riparte dallo stadio 1; `interrupt()` umano sopravvive al restart. | 🔴→✅ chiude la classe "stato perso al riavvio".                                             |
| Costo     | $0                                                                                                                                                                 | $0 (+6 conn Postgres/macchina)                                                                                         | —                                                                                            |

> **Quando shipparlo: PER ULTIMO.** È l'unico refactor _breaking_ (Fase 4). Dietro feature-flag, con la pipeline-script come fallback, shadow-run N volte prima del cutover. Il report stesso lo "parcheggia fino al prossimo incidente draft-loss".

### Stadio 1 — Topic selection

|                    | ATTUALE                                                                                                           | NUOVA                                                                                                      | Cambia                          |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Esegue             | `wr2_topic_selector.py` (cron 05:10, `StartCalendarInterval`), scoring deterministico. INSERT `status='briefed'`. | **= stesso script**, + Sonnet ranking editoriale.                                                          | **=** invariato nella sostanza. |
| Memoria fallimenti | 🔴 selezione **cieca** rispetto ai rifiuti critic intra-settimana (causa "monotono+sbagliato").                   | **+** legge `dominant_mode` degli ultimi rifiuti per topic_type → non ripropone combinazioni già bocciate. | **P7-adjacent.**                |

### Stadio 2 — Brief / ground-truth (NotebookLM)

|           | ATTUALE                                                                                                                                     | NUOVA                                                                                             | Cambia                                                                      |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Esegue    | `draft_generator.py` chiama NB? In realtà il brief vive nel topic_selector/draft_generator. Path-B ha `wr2-brief-interpreter`.              | Agente `wr2-brief-interpreter` (Sonnet) + `mcp__notebooklm-mcp__chat`. **= stesso schema brief.** | **=** la sostanza RAG-NotebookLM è già SOTA (brick 2 — qui WR2 è in testa). |
| Materiale | 🔴 `WR2_USE_FULL_ENRICHED_PROMPT` **default FALSE** → Claude vede solo `summary[:3500]` = **25% del materiale** (`draft_generator.py:378`). | **+** full-enriched ON di default + `instructor` (Pydantic, auto-retry su JSON malformo).         | 🔴→✅ il brief non è più troncato; **D4/P2**.                               |

### Stadio 3 — Storyboard / copy strutturato

|        | ATTUALE                                                                              | NUOVA                                                                                                                                          | Cambia                                  |
| ------ | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Esegue | `draft_generator.py` (opus-4-7) emette `slides_json` 11 slide "by convention".       | Agente `wr2-storyboarder` (Sonnet) riceve brief verbatim, emette 8-10 slide-spec.                                                              | path-B assorbito nel path unico.        |
| Schema | 🔴 JSON by-convention → deriva → mappazza / whitelist-strip (bug-class documentata). | **+ `instructor` `SlideSpec` Pydantic**: enum-layout, body 25-50 parole, hero-flag solo su layout capace (hard-rule 16) enforced nello schema. | 🔴→✅ **D4/P2**, elimina la classe-bug. |

### Stadio 4 — Hero image-gen + **consistenza cross-slide** (il guadagno-titolo)

|             | ATTUALE                                                                                                                                                             | NUOVA                                                                                                                                               | Cambia                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Generatore  | `image_generator.py`: cascade Codex `$imagegen` → FlowKit → Playwright+Gemini. 4 hero.                                                                              | **Tier-1A NUOVO: Nano Banana Pro** (Gemini 3 Pro Image) via FlowKit, **$0** (Google AI Ultra). Codex Tier-1B fallback. FLUX-Mini Tier-2 (PII-safe). | **D3/P1.**                                                                    |
| Consistenza | 🔴 ogni hero generata **in isolamento** → carosello visivamente disomogeneo. anchor-reuse+sha256 previene solo riuso **esatto**, non coerenza luce/palette/framing. | **+** passa slide-1..N-1 come **reference (fino a 14 img)** → identità visiva ancorata lungo il carosello.                                          | 🔴→✅ **il brick più debole** del report (§0.3). Costo incrementale **zero**. |
| VLM gate    | `qwen2.5vl:7b` score≥0.5 — SOLO prompt↔immagine, **NON** brand.                                                                                                     | Resta come pre-check tecnico; il giudizio brand passa allo Stadio 6.                                                                                | —                                                                             |
| Costo       | ~$0.04-0.08/img (Codex primario)                                                                                                                                    | **$0** quando Nano Banana regge                                                                                                                     | ↓ costo.                                                                      |

### Stadio 5 — Render / layout ⚑ (decisione controcorrente)

|            | ATTUALE                                                                                                                            | NUOVA                                                                                                                                                                                                  | Cambia                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Renderer   | **ReportLab + Pillow** (`wr2_canva_pdf_render.py`, 1080×1350, una pagina-PDF/slide) → Tigris → Canva MCP `import-design-from-url`. | **= SI TIENE ReportLab.** **NON** si migra a HTML/Satori/Playwright.                                                                                                                                   | **⚑ D2 — contro la raccomandazione generica del report (P4/P5).** |
| Perché     | hard-rule 15 (renderer canonico), 14 layout_family mappate, incidente `/tmp/*_LOCAL.py` già cicatrizzato.                          | Il **PDF text-layered è ciò che rende il design editabile in Canva** (testo come oggetti). open-carrusel/Satori producono **PNG-flat** → perdono l'editabilità → rompono Legge-5 (Damar deve editare). | Il vincolo Canva-editabile che il report **non modellava**.       |
| Eredità P4 | due path ambigui (ReportLab prod + HTML staging).                                                                                  | **+** principio "UN render-contract": ReportLab unico path prod; `wr2_image_generator.py` HTML declassato a **staging esplicito**.                                                                     | chiarezza, rimuove l'ambiguità a-due-path.                        |
| Lease      | CAS-lease (`lease_owner`/`lease_acquired_at`) previene doppia-render.                                                              | **=** + lease-watchdog (status='rendering' stale >15min).                                                                                                                                              | **=** già robusto.                                                |

### Stadio 6 — **Critic VLM gate** (il pezzo mancante nel path vivo)

|          | ATTUALE                                                                                                                             | NUOVA                                                                                                                                                  | Cambia                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| Esiste?  | 🔴 **NO critic di brand/qualità nel path A vivo.** Il critic-as-agent (`wr2-critic`, opus) vive solo nel **path B non installato**. | **+ Critic VLM attivo nel path unico**: Haiku pre-pass binario/hero (~$0.20) + `wr2-critic` Opus vision (4 rubriche).                                  | 🔴→✅ **il buco più grande.**                         |
| Verdetto | (path-B) score-ish.                                                                                                                 | **binario PASS/FAIL** per rubrica — **confermato statisticamente corretto** (arXiv:2604.25235: i VLM rankano ma non scorano in assoluto).              | **=** design verdetto giusto, **non** introdurre 1-5. |
| Input    | (path-B) riceveva contesto a monte.                                                                                                 | **+ context-isolation: SOLO `{image, brief, rubric}`**, mai la CoT dell'image-prompt-author (anti-snowballing, arXiv:2407.00569: −31% se contaminato). | **P3a.**                                              |
| Output   | —                                                                                                                                   | **+ Pydantic `CriticVerdict` con `retry_priority: hero\|text\|layout\|none`** → l'agente di retry sa _cosa_ aggiustare.                                | **P3c**, chiude il gap "retry indovina la causa".     |
| Rubriche | —                                                                                                                                   | **+ scalari → binarie pulite**: hue-in-palette? / legible-at-320px? / safe-zone-clear? / subject-matches-topic?                                        | **P3b.**                                              |
| Loop     | —                                                                                                                                   | hard-fail rubrica 1-2 → loop-back storyboarder/layout; max 2 retry → `needs_human_edit` + POST queue Damar.                                            | gate conditional-edge nel grafo.                      |

### Stadio 7 — Human review / Canva / Telegram (Legge 5)

|            | ATTUALE                                                                                                          | NUOVA                                                                                                                      | Cambia                                                                     |
| ---------- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Stop       | `canva_renderer_v2/orchestrator.py` scrive Canva via MCP + Telegram. `status='rendered'`. Publish manuale Damar. | **= stesso gate umano.** `published` solo a mano. Nessuno scheduler auto-publish (Postiz/Mixpost = pattern, mai adottati). | **=** Legge 5 invariata (brick 7: auto-publish è **non-goal deliberato**). |
| Durabilità | 🔴 se Pro/deploy riavvia mentre un draft attende Damar, lo stato può perdersi.                                   | **+ LangGraph `interrupt()` durevole**: il run si sospende sul checkpoint, l'approvazione lo riprende.                     | 🔴→✅ pattern da `langchain-ai/social-media-agent` (MIT).                  |

### Stadio 8 — Feedback loop

|                    | ATTUALE                                                                                          | NUOVA                                                                                                                 | Cambia                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Reflexion          | cron `com.balizero.wr2.reflexion.weekly` (saves/reach) + `wr2-ig-metrics-analyst` (Gemini free). | **= invariato** (è la forma SOTA: metric-grounded, l'unico self-improvement che funziona).                            | **=** difendere.                                                                               |
| Memoria fallimenti | 🔴 i draft critic-rejected vengono **scartati**, non memorizzati.                                | **+ `carousel_negative_examples`**: storyboarder RAG-querya gli ultimi 3 rifiuti per topic*type \_prima* di generare. | **P7** — memoria-di-fallimento → evitamento **intra-run**, non solo retrospettiva settimanale. |

---

## 2. Le 5 decisioni che la nuova War Room prende diversamente

| #        | Decisione                                                                                  | Scartata                                              | Motivo                                                                                                                                          | Brick                                                                          | Rischio / mitigazione                                                        |
| -------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **D1**   | Control-flow → **LangGraph** `route_on_status` su enum, riusa `get_checkpointer()` in-tree | restare script-driven (`wr2_supervisor.py`)           | gate strutturali che l'LLM non razionalizza + crash-resume + interrupt durevole; il `war_room_drafts` enko a 17 stati È già la macchina a stati | P6 / §1 (arXiv:2512.08296)                                                     | unico breaking → Fase 4, feature-flag, shadow-run, fallback script           |
| **D2** ⚑ | **TENERE ReportLab**; HTML/Playwright resta staging                                        | unificare su HTML/CSS+Satori/Playwright (P4/P5)       | il PDF text-layered è ciò che rende il design **editabile in Canva** (Legge-5); PNG-flat lo rompe                                               | P4/P5 (decisione _contro_ il report, motivata dal vincolo Canva non modellato) | ReportLab è battle-tested; adottiamo solo il _principio_ one-render-contract |
| **D3**   | **Nano Banana Pro 14-ref** consistenza cross-slide ($0)                                    | Recraft `style_id` (paid, gate Zero) / anchor-attuale | brick più debole, fix a **costo zero** (già in Google AI Ultra)                                                                                 | P1 (guadagno-titolo)                                                           | dipendenza FlowKit bearer-token → Codex Tier-1B fallback                     |
| **D4**   | **`instructor`** (Pydantic+retry) su brief/storyboard/critic-verdict                       | JSON by-convention                                    | uccide la classe-bug mappazza/whitelist-strip                                                                                                   | P2+P3c / brick 3                                                               | MIT, $0, additivo, gira con OAuth-Claude `auth_token`+Ollama                 |
| **D5**   | **negative-example library** intra-run + critic context-isolation                          | solo Reflexion settimanale                            | converte fallimento in evitamento _prima_ del prossimo errore; esito verificabile (critic binario+IG)                                           | P7+P3a                                                                         | tabella cresce → pruning; read-only worker, write solo orchestratore         |

---

## 3. Migrazione — sequenza (additivo prima, refactor per ultimo)

| Fase  | Cosa                                                                                                                                                                                                                      | Breaking?                              | Effort | Note                                                                                      |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------ | ----------------------------------------------------------------------------------------- |
| **1** | D4 `instructor` (brief+storyboard+CriticVerdict) · P3a context-isolation · P3b rubriche binarie · declassa HTML a staging esplicito · **+ accendi `WR2_USE_FULL_ENRICHED_PROMPT` + fact_checker** (fix 🔴 di default OFF) | **No**                                 | Low    | parte subito, in parallelo. _Questi chiudono 3 fragilità documentate._                    |
| **2** | D3/P1 Nano Banana 14-ref come Tier-1A — **prima prototipo misurato su 1 carosello reale** (coerenza vs anchor), poi default con Codex fallback                                                                            | **No** (cascade preserva path attuale) | Med    | il guadagno-titolo                                                                        |
| **3** | D5/P7 `carousel_negative_examples` (migrazione + write post-critic + read pre-storyboard)                                                                                                                                 | **No** (additivo)                      | Med    | + **attiva il critic VLM brand nel path vivo** (Stadio 6) — il buco più grande            |
| **4** | D1/P6 migrazione LangGraph (`CarouselState`, `route_on_status`, `interrupt()`, riuso checkpointer)                                                                                                                        | **SÌ** (control-flow)                  | High   | per ultimo; feature-flag + shadow-run; parcheggiato fino al prossimo incidente draft-loss |

> Nota d'ordine: il report consigliava P2+P3+P4+P5 → P1 → P7 → P6. Qui **P4/P5 cadono** (D2: teniamo ReportLab) e al loro posto la Fase 1 include i fix delle 3 fragilità (full-prompt, fact-checker, ambiguità due-path) che l'audit del codice vivo ha rivelato. La Fase 3 esplicita ciò che il report sottintendeva: **il critic brand va acceso nel path vivo** — oggi semplicemente non c'è.

---

## 4. Cosa NON cambiare (già SOTA — difendere)

1. Topologia **orchestratore centrale + worker stateless, no peer-to-peer** (arXiv:2512.08296).
2. Critic **binario PASS/FAIL + Haiku pre-pass + closed-source judge** (arXiv:2604.25235). Mai score 1-5, mai judge open-source (bias text-in-image — i nostri design _contengono_ testo).
3. **Ground-truth NotebookLM verbatim** (Contratto B) — più autoritativo di pgvector generico per la normativa ID.
4. **17 hard-rule costituzione brand** (1080×1350, palette token-only, logo ogni slide, citazioni verbatim, lexicon bilingue mai-tradotto, anti-cliché, 25-50 parole, statement-bomb, hard-rule 15+16).
5. **Legge 5 / human-in-loop**: stop a Canva editabile + Damar/Telegram; `published` solo a mano; nessuno scheduler.
6. **Sovranità (Law 2)**: brief/NB-query/PII non lasciano il Pro; hero locali FLUX-Mini quando serve no-cloud.
7. **Costo zero**: solo OAuth MAX + sub pagate; mai `ANTHROPIC_API_KEY`; Imagen4/Recraft solo con autorizzazione Zero + non-PII.
8. **Reflexion settimanale metric-grounded** (P7 la estende, non la sostituisce).

---

## 5. File rilevanti per la build (path assoluti)

- Renderer canonico (D2): `scripts/wr2_canva_pdf_render.py`
- Checkpointer riusabile (D1/P6, già in-tree): `apps/backend-rag/backend/services/workflow/checkpointer.py`
- LangGraph orchestrator di riferimento in-tree: `apps/backend-rag/backend/services/rag/kg_langgraph_orchestrator.py`
- State+lease+enum: `apps/backend-rag/backend/db/migrations_v2/{127,154,162,163,170}_*.sql`
- Canva apply (Stadio 5/7): `apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py`
- Telegram gate (Stadio 7): `scripts/wr2_telegram_publish_gate.py`
- Topic selector (Stadio 1): `scripts/wr2_topic_selector.py`
- Le 3 fragilità da fixare in Fase 1: `wr2_draft_generator.py:378` (full-prompt), `wr2_fact_checker.py:760` (fact-checker disabled), `wr2_image_generator.py` (declassa HTML a staging)
- Agent-def orchestratore: `~/.claude/agents/wr2-design-architect.md`

---

## 6. Onestà / da ri-verificare prima della build (anti-allucinazione)

- Verificati dall'orchestratore: arXiv:2512.08296, arXiv:2604.25235, `open-carrusel`/`wrapSlideHtml()`, esistenza tabella `war_room_drafts` a 17 stati + lease, `get_checkpointer()` in-tree, renderer ReportLab.
- **NON ri-verificati indipendentemente** (alta probabilità ma re-fetch prima di dipenderci): i prezzi-per-immagine Nano Banana/FLUX/Recraft; il numero esatto di reference-image Nano Banana (14, da lane); star/date dei ~20 repo del report; che `WR2_USE_FULL_ENRICHED_PROMPT` e il fact-checker siano _ancora_ OFF di default (l'audit le ha lette nel codice oggi — ma riconfermare il valore prima di "accenderle" in Fase 1, potrebbero essere già state cambiate da sessioni parallele).
- Le 2 fragilità "default OFF" (full-prompt, fact-checker) sono lette dall'audit-agent dal codice vivo; **prima di shipparle in Fase 1, ri-grep il valore corrente** (rule anti-allucinazione 1-2).
