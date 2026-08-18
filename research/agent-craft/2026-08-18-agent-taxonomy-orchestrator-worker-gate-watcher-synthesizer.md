# Agent-craft DR — 2026-08-18-agent-taxonomy-orchestrator-worker-gate-watcher-synthesizer

**Date**: 2026-08-18
**Mode**: fallback
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 30 / Citations: 47

## Question

> In italiano. Tema di oggi (round-robin giorno 2): tassonomia funzionale degli agenti: orchestrator vs worker vs gate vs watcher vs synthesizer. Mappa i nostri 16 agenti su queste famiglie.

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta. Termina con 3 domande aperte per il DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (Tassonomia e Topologia Multi-Agente)**

*   **L'Orchestratore e i Lavoratori Stateless (Centralized State):**
    > *"multi-agent with strict orchestrator is correct because specialist roles are genuinely different competencies; but Google's 17.2× error-amplification finding is a serious warning — architecture must be centralized state, stateless workers, not peer-to-peer. Avoid temptation to give each sub-agent its own memory."* [1]
    
*   **L'Impatto delle Topologie sull'Amplificazione degli Errori (Kim et al. 2025):**
    > *"Multi-agent error amplification 17.2× (Kim et al. 2025 arxiv 2512.08296) is real but task-dependent — orchestrator-led shrinks to 4.4×, sequential tasks favor single-agent, parallelizable tasks favor centralized multi-agent."* [2]
    
*   **La natura sequenziale del flusso e l'isolamento del contesto:**
    > *"For sequential pipelines (brief → storyboard → layout → critic in chain, like WR2): single-agent batte multi-agent di 39–70%. Multi-agent in WR2 is justified by context-isolation and model-routing economy (Sonnet workers + Opus critic + Haiku vision-pre-pass), not by parallelism gain."* [3]

*   **I Watcher ad ambito ristretto:**
    > *"This agent does NOT trigger downstream agents. It writes a file + sends a notification. If Antonello wants to act on a delta, he reads the file and decides manually."* [4]

*   **I Gate (I validatori e i red-team asincroni):**
    > *"A validator is a deterministic script embedded within a skill that verifies whether an agent's actions meet organizational standards—without requiring human approval... Validators shift the governance team's operational model from governance-as-approval [...] to governance-as-code"* [5, 6].
    > *"Client quotes are the highest-stakes deliverable [...]. Before Step 7 QA, invoke devils-advocate on the HTML draft"* [7].

---

### **2. Mappatura Funzionale della Flotta di 16 Agenti di Bali Zero / Nuzantara**

Nel nostro ecosistema reale di produzione, per evitare l'accumulo distruttivo di informazioni nella REPL principale ("context rot") e limitare i costi operativi, i nostri **16 agenti** sono suddivisi in cinque macro-famiglie funzionali basate sulle specifiche di design del brand cortex [8-10].

```
                                  [USER/SUPERVISOR]
                                         │
                                         ▼
                             1. WR2-DESIGN-ARCHITECT
                                  (Orchestrator)
                                         │
                      ┌──────────────────┼──────────────────┬─────────────────┐
                      ▼                  ▼                  ▼                 ▼
             2. WR2-BRIEF-INTEL   3. WR2-STORYBOARD  4. WR2-LAYOUT-COMP.  5. WR2-CRITIC
               (Synthesizer)          (Worker)           (Worker)            (Gate)
```

#### **A. Orchestrator (1 Agente)**
*Gestisce lo stato complessivo della pipeline, coordina le transizioni sequenziali ed esegue i loop di ri-esecuzione in base ai report di fallimento dei Gate.*
1.  **`wr2-design-architect` (Opus 4.7)**: L'unico orchestratore centrale del flusso caroselli. Non scrive brief o layout direttamente; avvia i sub-agenti specializzati stateless, gestisce la scrittura su disco temporaneo `/scratch/` ed esegue il rendering tramite Playwright [11, 12].

#### **B. Worker (7 Agenti)**
*Eseguono compiti meccanici o di scrittura strettamente delimitati. Consumano un input strutturato e producono un output deterministico (HTML, JSON o prompt specifici).*
2.  **`wr2-storyboarder` (Sonnet 4.6)**: Traduce il brief in una sequenza narrativa di 8-10 slide (delineando titoli, testi e indicazioni visive) [13].
3.  **`wr2-layout-composer` (Sonnet 4.6)**: Recupera i layout fisici dalla libreria e parametrizza il codice HTML/CSS, iniettando i contenuti generati dallo storyboarder [14].
4.  **`wr2-image-prompt-author` (Opus 4.7)**: Agisce come l'art director visuale; legge il brief ed elabora metafore visive traducendole in prompt per Codex/Gemini, evitando la monotonia visiva [15, 16].
5.  **`email-template-builder` (Sonnet 4.6)**: Costruisce i template e-mail in formato HTML Brevo applicando controlli di citazione regolatoria in preflight [17, 18].
6.  **`client-case-quote-generator` (Opus 4.7)**: Genera i preventivi ad alto valore per i clienti in formato PDF A4, assemblando dati fiscali e immigratori [19, 20].
7.  **`yield-optimizer` (Sonnet 4.6)**: Scansiona settimanalmente il CRM locale PostgreSQL in totale isolamento offline per estrarre opportunità commerciali e redigere bozze di messaggi WhatsApp tramite Ollama Qwen3.5 locale [21, 22].
8.  **`nb-curator` in Modalità A - Raccomandazione (Sonnet 4.6)**: Agisce da smistatore di interrogazioni a runtime, fornendo agli altri agenti l'esatto UUID del NotebookLM da interrogare in base al dominio del quesito [23].

#### **C. Gate / Adversarial Reviewer (2 Agenti)**
*Agiscono come barriere di qualità pre-pubblicazione. Stress-testano i file, le cifre e gli asset grafici per rilevare allucinazioni o deviazioni dal brand.*
9.  **`wr2-critic` (Opus 4.7 - Vision)**: Esegue il controllo finale sulle slide caricate in formato PNG contro i vincoli della costituzione di Bali Zero (colori, contrasto, lunghezza del testo, assist bilingue) [24].
10. **`devils-advocate` (Sonnet/DeepSeek)**: Un contrariano logico-legale. Tenta di distruggere le assunzioni di preventivi, ricerche o strategie prima che vengano sottoposti a revisione umana [25, 26].

#### **D. Watcher (3 Agenti)**
*Autonomi e non-invasivi, i Watcher monitorano costantemente fonti web o log operativi, scrivendo report e inviando notifiche asincrone su canali dedicati (Telegram).*
11. **`regulatory-watcher` (Sonnet 4.6)**: Gira giornalmente via cron per rilevare modifiche nelle leggi indonesiane registrate sulla press e nei NotebookLM di monitoraggio [27, 28].
12. **`competitor-monitor` (Sonnet 4.6)**: Elabora un digest mensile comparativo sui movimenti strategici dei competitor locali scansionando screenshot e canali social [29, 30].
13. **`wr2-external-bench` (Opus 4.7)**: Scansiona mensilmente il SOTA globale del design editoriale su Instagram per identificare nuovi trend visuali e proporre modifiche alla costituzione [31, 32].

#### **E. Synthesizer (3 Agenti)**
*Ingestiscono grandi moli di dati non strutturati o flussi di metriche, filtrano il rumore e li distillano in file di riferimento semantico a lungo termine.*
14. **`wr2-brief-interpreter` (Sonnet 4.6)**: Legge il brief grezzo dell'utente, esegue interrogazioni RAG sul NotebookLM di riferimento e compila il brief strutturato JSON consumato dai lavoratori successivi [33, 34].
15. **`wr2-ig-metrics-analyst` (Sonnet 4.6)**: Analizza le metriche di engagement reali dei caroselli pubblicati per estrarre relazioni matematiche (es. Save/Like ratio) e proporre patch strutturate alla costituzione di brand [35, 36].
16. **`nb-curator` in Modalità B/C (Sonnet 4.6)**: Steward del nostro arsenale di 60 NotebookLM; esegue controlli settimanali di integrità ed elabora proposte mensili di de-duplicazione e sintesi dei database cloud [23].

---

### **3. Linea di Azione Concreta: Hard-coded Tool Whitelists e Gating dei Privilegi**

Dall'analisi delle definizioni degli agenti e dei log, emerge che molti sub-agenti lavoratori (`Worker`) importano implicitamente o ereditano tutti i tool del genitore, aumentando il rischio di esecuzioni disordinate del filesystem o chiamate bash non autorizzate.

*   **Azione**: Implementare il principio del minimo privilegio (**Least Privilege Gating**) restringendo programmaticamente l'array `tools` nel frontmatter YAML di ciascuno dei nostri sub-agenti in `.claude/agents/` [37, 38].
*   **Procedura Operativa**:
    1.  **Workers di Sola Lettura / RAG**: Vincolare `wr2-brief-interpreter` e `wr2-storyboarder` ad accedere esclusivamente a `tools: [Read, Glob, Grep, Bash]` (bloccando `Edit` e `Write` nativi), forzandoli a delegare la persistenza delle bozze all'Orchestratore o a script deterministici isolati [39].
    2.  **Gating Rigido per il Layout Composer**: Riconfigurare `wr2-layout-composer.md` per consentire solo `tools: [Read, Write, Edit]` (omettendo esplicitamente `Bash` e `Agent` per evitare la generazione autonoma di codice o sub-sub-agenti) [40].
    3.  **Sanificazione dei Gate**: Assicurarsi che `wr2-critic.md` non possa in nessun caso invocare strumenti di modifica file: `disallowedTools: [Write, Edit]` [37].

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  Dato che Kim et al. documentano che l'amplificazione d'errore cala drasticamente da **17.2x a 4.4x** applicando una topologia centralizzata (orchestrator-led) [41], quali meccanismi di *state-rollback* o *checkpointing* a livello di disco (es. ripristino di `slides.json` tramite git-diff post-bocciatura del critic) possiamo integrare in `wr2-design-architect` per sanare automaticamente le allucinazioni prima del coinvolgimento umano [42]?
2.  I Watcher (es. `regulatory-watcher` o `competitor-monitor`) per definizione scrivono file locali e notificano, ma non innescano flussi downstream [4]. Come possiamo strutturare una **Event-Driven Knowledge Activation** (es. tramite un eventbus di file di lock o code Redis locali come `garuda:enriched`) affinché un Watcher possa "svegliare" l'Orchestratore in modo asincrono solo al superamento di una soglia di severità della novità legale [43, 44]?
3.  Nel calcolo del **Maturity-Aware Update Gating** per l'evoluzione automatica delle nostre skill [45], come deve essere ponderato l'apporto dei Gate (il giudizio asettico del `wr2-critic` basato sul brand) rispetto all'apporto dei Synthesizer (il feedback reale delle conversioni elaborato dal `wr2-ig-metrics-analyst`), garantendo che il comportamento dell'agente si adatti ai trend social senza mai violare la costituzione legale del brand [46, 47]?

📊 *Se lo desideri, posso lanciare una scansione della directory `.claude/agents/` per verificare la conformità di tutti i frontmatter correnti con la matrice dei permessi minimi descritta.*

## Sources used (30)

- `a1f286dd-f3bd-4cb5-8614-08f4deef3160`
- `354fe331-a3bd-4596-88c8-d4fb4c4da5a8`
- `d6bf2f6f-a93f-497d-9bf3-59746d866315`
- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `8d0ba049-2c1b-4b1e-a05f-c284d7abb3ec`
- `74917ad2-2ae3-4a43-ba8c-e5876ec073fc`
- `6445c350-5740-49cc-aa53-e5eb7fe9512f`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `f25859a8-ea63-45ef-bd96-b14148afcb39`
- `e65a5f8f-9bac-44c8-bf39-a13841e40f93`
- `5e5133d9-5195-4d2f-8fbb-a681220f87eb`
- `90405b91-8dd8-40cf-9086-8fce5459eb84`
- `3bcf9ef7-b926-4bfa-97d8-2d733b142a12`
- `9797c0de-9d7b-42fd-a15a-8f2deaf0bf7e`
- `357bc3cb-8dce-4893-a988-c4ffc8787bf5`
- `c676ecb8-5873-4ee0-a3dc-7a6303907135`
- `fcf012c1-0b7d-4305-af36-c23aec57b2a9`
- `1826e81e-6d39-4285-956a-464b315e3f3f`
- `e18bc146-7631-4fff-85e0-ddd2353ff34d`
- `c78af240-51bd-4558-a4ed-7c0a82b09c14`
- `25977454-d585-4327-bbeb-c7911897b175`
- `2c1da571-c4d1-408e-9d46-f7e2c07316c6`
- `9213dc12-3a9e-4e6f-9ca2-5279f33a52ef`
- `2c4791cd-68b5-4c9b-bc8c-6617157a078e`
- `2ad7dcc3-b3c0-402f-96d1-baa8f5e28b5e`
- `6f0873fe-c65c-42f0-a8da-86e46e0cda35`
- `41511dc3-8e29-456d-bc5d-01747901dc58`
- `ea7a4b5a-8934-46a2-aea4-0d440a94067e`
- `860ca133-6886-4b2e-8623-bbd53053d71b`
- `92b09121-412d-4ece-a88e-86b922424a15`

## Citations verbatim (47)

### [1] source `a1f286dd…`

> Quality gates (in order) : Token compliance (deterministic): all colors map to brand palette, all fonts map to brand stack — non-compliance = hard fail. Critic panel score ≥ threshold — soft fail = retry with feedback (max 2 retries). CLIP similarity ≥ threshold to curated set of past on-brand carousels — guards against subtle drift. Diffusion-variance hallucination check on any generated raster. Human review queue for final go/no-go on publish. Single agent vs multi-agent verdict : multi-agent with strict orchestrator is correct because specialist roles are genuinely different competencies; but Google's 17.2× error-amplification finding is a serious warning — architecture must be centralized state, stateless workers , not peer-to-peer. Avoid temptation to give each sub-agent its own memory.

### [2] source `354fe331…`

> -------------------------------------------------------------------------------- name: lessons-multi-agent-topology-kim-2025 description: "Multi-agent error amplification 17.2× (Kim et al. 2025 arxiv 2512.08296) is real but task-dependent — orchestrator-led shrinks to 4.4×, sequential tasks favor single-agent, parallelizable tasks favor centralized multi-agent. Agent teams in Claude Code = all Claude models only, no Gemini/Codex/DeepSeek as teammates." metadata: node_type: memory type: lessons originSessionId: 08bda0ef-5579-4fb2-a654-f16050486d01

### [3] source `354fe331…`

> Corrected guidance for Bali Zero stack The old rule (wr2-design-architect.md:338, lines 91+129+338, also pre-T2.91, pre-T2.271): "NEVER let subagents talk to each other peer-to-peer (Google's 17.2× error-amplification finding)." The corrected rule : For sequential pipelines (brief → storyboard → layout → critic in chain, like WR2): single-agent batte multi-agent di 39–70% . Multi-agent in WR2 is justified by context-isolation and model-routing economy (Sonnet workers + Opus critic + Haiku vision-pre-pass), not by parallelism gain. Don't pretend it's a parallelism win. For parallelizable tasks (multi-perspective client case, multi-source regulatory check, cross-LLM bipolar verifier): centralized multi-agent batte single-agent di +80.9% . This is where agent teams shines. Peer-to-peer is not banned — it's 4× worse than centralized, but on parallelizable tasks it's still often better than single-agent. Use it when the task genuinely needs cross-agent challenge (devil's advocate, scientific debate pattern in agent-teams docs). Independent (no coordination) is the real trap — 17.2× amplification. Never spawn N parallel sessions and merge results without any lead.

### [4] source `d6bf2f6f…`

> This agent does NOT trigger downstream agents. It writes a file + sends a notification. If Antonello wants to act on a delta, he reads the file and decides manually. Future enhancement: emit specific service_line events to a queue that other agents subscribe to (out of scope today).

### [5] source `f6c76ff7…`

> 5.5 Validators: Deterministic Governance Scripts While governance constraints (Section 5 ) declare the rules an agent must follow, validators enforce them automatically. A validator is a deterministic script embedded within a skill that verifies whether an agent's actions meet organizational standards—without requiring human approval for the verification itself. Validators transform governance from a declarative annotation into an executable guarantee. Three categories of validators address different points in the execution lifecycle:

### [6] source `f6c76ff7…`

> The composability of validators follows a type-safety analogy: just as well-typed functions compose into type-safe programs, skills with comprehensive validators compose into governance-safe workflows. When an agent composes an AI-Generated Golden Path—a workflow assembled at runtime from available skills—the composed path inherits the union of all constituent validators. Governance safety is achieved by construction rather than by post-hoc review. Validators shift the governance team's operational model from governance-as-approval —reviewing individual agent actions as they occur—to governance-as-code —authoring, testing, and maintaining deterministic validation scripts. This shift is analogous to the Infrastructure-as-Code transformation that freed operations teams from ticket-based provisioning: the governance team's mission becomes increasing validator coverage across the skill library, progressively moving more skills toward full autonomy as validator coverage expands.

### [7] source `8d0ba049…`

> Step 6 — Render to PDF Wait for completion. Verify the PDF exists and is non-trivial size (>20KB indicates rendering succeeded). Step 6.5 — Devil's Advocate red-team (mandatory pre-render gate) Client quotes are the highest-stakes deliverable (signed PDF, sent to client, IDR ##jt at stake). Before Step 7 QA, invoke devils-advocate on the HTML draft : Read returned verdict : BLOCK → 1+ critical (regulatory hallucination, math error, missing PMK citation). STOP. Surface to user. Do NOT proceed to PDF render. NEEDS_FIX → fix and re-invoke devils-advocate. Max 2 iterations. After 2 still NEEDS_FIX, surface to Antonello with [NEEDS HUMAN REVIEW] flag. PASS → continue to Step 7.

### [8] source `74917ad2…`

> Multi-agent shape (4 specialist subagents, all Claude): wr2-design-architect (orchestrator) — Opus 4.7 — main entry point wr2-brief-interpreter — Sonnet 4.6 — fast, RAG-over-NB, structured JSON out wr2-storyboarder — Sonnet 4.6 — narrative arc 8–10 slides wr2-layout-composer — Sonnet 4.6 — picks parametric skill from library, emits HTML wr2-critic — Opus 4.7 (vision-capable) — scores against brand rubric wr2-publisher — Haiku 4.5 — Canva apply + Tigris upload (cheap, mechanical) Skill library ( ~/.claude/skills/bali-zero-brand/ ):

### [9] source `74917ad2…`

> constitution.md — hard brand rules (palette, type, taboo) tokens.json — design tokens (machine-readable) voice/ — few-shot examples on-tone vs off-tone layouts/ — parametric layout skills (each = SKILL.md + render snippet) past/ — last N carousels as in-context reference (PNG + brief.md) Memory layers : Episodic : SQLite at ~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db — one row per carousel run. Semantic : brand cortex files (above). Procedural : skill library (above). Reflective : weekly cron synthesizes episodes into lessons appended to voice/ and skills/.

### [10] source `6445c350…`

> Tipo : Claude Code subagent (Type A) in ~/.claude/agents/wr2-design-architect.md Modello : Opus 4.7 via OAuth MAX (zero costi, CLAUDE.md HARD RULE compliance) Pattern : orchestrator centralizzato + 4 specialist subagents (NO peer-to-peer — Google 17.2× error amplification finding) Sub-agents pianificati : brief-interpreter (Sonnet), storyboarder (Sonnet), layout-composer (Sonnet), critic (Opus vision-capable), publisher (Haiku) Skill base : ~/.claude/skills/bali-zero-brand/ — closed-namespace tokens + constitution + voice + layouts Memory layers : episodic (SQLite), semantic (file cortex), procedural (skill library), reflective (weekly cron synthesis) Growth pattern : Voyager curriculum + Reflexion post-mortem Quality gates : token compliance → critic panel (4 rubric) → CLIP similarity → diffusion variance hallucination check → human review

### [11] source `d0adf453…`

> -------------------------------------------------------------------------------- name: wr2-design-architect description: "MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]", "draft a WR2 brief", or invokes the WR2 pipeline. Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex (constitution + tokens + voice + 64 past carouseli), enforces 3 contracts (fan-out, NB ground-truth, imagegen no-silent-reuse), runs critic gate, emits queue handoff. Grows via Voyager skill library + Reflexion weekly synthesis." tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch model: opus isolation: worktree color: blue skills:

### [12] source `d0adf453…`

> You orchestrate four stateless specialist subagents. Invoke each via the Agent tool with subagent_type=<name> and pass the prior step's structured JSON as the prompt . Specialists read shared brand cortex files; they NEVER talk peer-to-peer (Google's 17.2× error-amplification finding). All inputs and outputs are JSON or files on disk. <cited_table>

### [13] source `f25859a8…`

> -------------------------------------------------------------------------------- name: wr2-storyboarder description: "MUST BE USED by wr2-design-architect at Step 3 of every carousel run. Use IMMEDIATELY when brief-interpreter returns its structured brief. Receives the brief verbatim, returns 4-10 slide narrative spec (Hook + Frame + Discovery + Closing arc + optional elegant-close). Each slide-spec includes layout family, heading, body (with English assist for non-always-untranslated ID terms — Article 6.2), hero flag, image prompt. ENFORCES bullet-promise rule (Article 6.3): if heading/sub announces N items, body MUST deliver N bullets, never paragraph mappazza. No HTML. No rendering." tools: Read, Glob, Grep, Bash model: sonnet color: purple skills:

### [14] source `e65a5f8f…`

> -------------------------------------------------------------------------------- name: wr2-layout-composer description: "MUST BE USED by wr2-design-architect at Step 4 of every carousel run. Use IMMEDIATELY after storyboarder returns slides.json. Receives slide-spec JSON + brief JSON verbatim, retrieves matching layout from skill library, parameterizes HTML/CSS, writes render-ready files for Playwright. ENFORCES no silent placeholder reuse (Article 5.10): every hero image_source must be imagegen:<session> or anchor:<file> with sha256(hero) ≠ sha256(anchor) verification. Does NOT render itself (orchestrator drives Playwright)." tools: Read, Write, Edit, Glob, Grep, Bash model: sonnet color: yellow skills:

### [15] source `5e5133d9…`

> -------------------------------------------------------------------------------- name: wr2-image-prompt-author description: Authors original, vivid, editorial image-gen prompts for each hero slide of a WR2 carousel. Reads brief + storyboard + slide context, performs an editorial reading of THIS specific topic (not a template), proposes a visual metaphor, varies across 9 image-style modes (constitution Art 5.8), and outputs prompts ready for Codex $imagegen . Avoids the monotone-template trap from S11 (12 carouseli all "paper documents on dark desk"). Used by wr2-design-architect between Step 3 (storyboard) and Step 4 (image generation). tools: Read, Glob, Grep disallowedTools: Write, Edit model: opus color: pink

### [16] source `5e5133d9…`

> WR2 Image Prompt Author You author original visual prompts for editorial Bali Zero carousel hero images. You are NOT a generic prompt engineer. You are the visual editorial brain — equivalent to a magazine art director who reads each story and decides "what does THIS specific story look like?" Critical context: the S11 monotone failure In S11 (2026-05-09), 12 carouseli were produced with hero prompts that all reduced to variations of: "35mm film editorial, chiaroscuro teal-amber, dark mahogany desk, single overhead lamp, [generic paper/seal/document], no faces, photoreal macro, 4:5 portrait."

### [17] source `90405b91…`

> [ Airbyte Agents The Context Layer for AI Agents](https://airbyte.com/agentic-data/best-ai-agent-frameworks) product overview Developers Everything you need to build production-grade AI agents Context Store A unified context layer across every system your agents touch Docs SDK Connect your agents to SaaS in real-time with a few lines of Python MCP One MCP server for all your SaaS. Deploy from Claude, ChatGPT, CLIs, and more Data replication [ Data Replication The Airbyte Data Replication Platform](https://airbyte.com/data-replication)

### [18] source `3bcf9ef7…`

> Procedure (cap 2 queries per email, ~90s total): Verdict logic: Citation confirmed in NB-INTEL with matching source → email cleared Citation contradicted (NB says different number/date) → abort , return ERROR regulatory citation contradicted by NB-INTEL: email body says X, NB-INTEL-<domain> shows Y. Reject draft. Citation not found (empty result) → flag in output as WARNING claim unverified — operator must confirm before send but do not abort. Marketing/onboarding/general emails without regulatory content: skip Step 4b.

### [19] source `9797c0de…`

> Agent Tool name: Agent (previously Task , which is still accepted as an alias) Input: Output: AskUserQuestion Tool name: AskUserQuestion Asks the user clarifying questions during execution. See Handle approvals and user input for usage details. Input: Output: Bash Tool name: Bash Input: Output: Monitor Tool name: Monitor Runs a background script and delivers each stdout line to Claude as an event so it can react without polling. Monitor follows the same permission rules as Bash. See the Monitor tool reference for behavior and provider availability. Input:

### [20] source `8d0ba049…`

> -------------------------------------------------------------------------------- name: client-case-quote-generator description: Generates a Bali Zero internal-print A4 PDF client quote (visa/property/tax/regulatory) covering cost, timeline, risk, deliverables, and pricing. Loads bali-zero-brand skill (surface=internal-print-a4), uses Claude Opus 4.7 for brand-voice synthesis, delegates numerical math (tax projections, cost breakdowns, deadline arithmetic) to DeepSeek Reasoner ($0.01/q acceptable per CLAUDE.md), renders via existing surfaces/internal-print-a4/_render.py Playwright→PDF pipeline. Use when Antonello says "quote case for [client X]" or "draft brief for [Marta Reyes / Marina Pinyaylova / etc.]". tools: Read, Write, Edit, Bash, WebFetch model: opus isolation: worktree color: blue

### [21] source `357bc3cb…`

> Why multi-Agent frameworks matter A single-agent system needs a prompt, a model, and maybe some tools. Multi-agent systems need coordination primitives : how agents discover each other, share state, handle failures, and decide who acts next. Building these primitives from scratch means reinventing message passing, state checkpointing, handoff protocols, and failure recovery. Frameworks exist to solve this, so your team can focus on domain logic instead of distributed systems plumbing. The critical differences between frameworks lie in three areas: orchestration model (graph-based vs. role-based vs. swarm), state management (checkpointed vs. ephemeral vs. event-sourced), and communication pattern (handoffs vs. shared memory vs. message queues). Understanding this maps directly to the orchestration patterns we've covered previously.

### [22] source `c676ecb8…`

> -------------------------------------------------------------------------------- name: yield-optimizer description: Weekly CRM scanner that connects AI to revenue. Identifies clients with renewal/upgrade potential (KITAS expiring, business pivot signal, no recent contact, high engagement score). Drafts WhatsApp pitch via Ollama Qwen3.5:9b LOCAL (CRM data privacy — UU PDP scope, never to cloud). Scheduled Sunday 04:00 WITA. tools: Read, Bash model: sonnet color: orange Yield Optimizer (Commercial Engine)

### [23] source `fcf012c1…`

> -------------------------------------------------------------------------------- name: nb-curator description: NotebookLM inventory steward. Recommends which NB(s) to query for a given question, detects inventory gaps (e.g., "no NB covers Permenaker post-2025"), maintains health metrics for the 60-NB stack (~2970 sources), and surfaces broken/stale NBs. Other agents (deep-researcher, regulatory-watcher, wr2-brief-interpreter) call this BEFORE their own NB query step. Also runs weekly health-check via cron AND weekly+monthly curation (Mode C) that proposes dedup clusters / summarization bundles / stale-source cleanup for the 5 NB-INTEL (Press weekly because growth ~30/wk; other NB monthly; stale >90d weekly for all). tools: Read, Write, Bash, Glob, Grep model: sonnet color: purple memory: user

### [24] source `1826e81e…`

> -------------------------------------------------------------------------------- name: wr2-critic description: MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. Use IMMEDIATELY after Playwright renders PNGs. Reviews rendered carousel slides against Bali Zero brand constitution + brief verbatim. Receives PNG paths + slide-spec JSON + brief JSON + brand cortex pointer. Returns 4-rubric scores AND a binary verdict per slide (PASS / FAIL with one-line reason) plus retry feedback. Verifies Article 6.2 bilingual assist on first occurrence, Article 6.3 bullet-promise, Article 5.10 no silent placeholder reuse via sha256 anchor check. tools: Read, Write, Glob, Grep, Bash model: opus color: red memory: user skills:

### [25] source `e18bc146…`

> -------------------------------------------------------------------------------- name: devils-advocate description: "Red-team contrarian agent. Receives a finished dossier/research/quote/strategy and tries to DESTROY its assumptions. System prompt: "find the legal flaw, the tax miscalculation, the missing regulation, the hallucinated KBLI code, the contradiction between sentence A and sentence B." Used as mandatory pre-publish gate by deep-researcher, client-case-quote-generator, wr2-strategos for high-stakes outputs. Powered by DeepSeek Reasoner (excellent logical hole-finding, $0.01/q acceptable)." tools: Read, Bash, WebFetch disallowedTools: Write, Edit model: sonnet color: red

### [26] source `e18bc146…`

> Devil's Advocate (Red Teamer) You are the contrarian. You exist to STRESS-TEST conclusions before they reach a client or get published. You do NOT confirm. You do NOT congratulate. You attack. Identity Owner : Antonello Siano. Italian conversation, English findings. Stance : skeptical, surgical, irreverent. Better to surface a 5% concern than to silently let a 50% bug ship. Voice : terse, direct, citation-heavy. Like a veteran legal/tax/audit reviewer. NO marketing voice. NO niceties. Why DeepSeek Reasoner?

### [27] source `d6bf2f6f…`

> -------------------------------------------------------------------------------- name: regulatory-watcher description: Daily watcher over NB-INTEL family + web for new Indonesian regulations (Permenkumham, PMK, PP, Perpres, UU, Peraturan BKPM, Permenaker, Permenkes) affecting Bali Zero services. Emits Telegram alert + structured delta JSON to ~/Desktop/nuzantara/research/regulatory/<date>-delta.json . Runs autonomously via cron at 07:00 WITA daily. tools: Read, Write, Bash, WebFetch model: sonnet isolation: worktree color: orange memory: user

### [28] source `d6bf2f6f…`

> Regulatory Watcher You are the daily regulatory delta detector for Bali Zero. Your job is narrow: detect what changed in Indonesian law yesterday that might affect a Bali Zero service line, and surface it to Antonello in two channels (file + Telegram). You are NOT a researcher. You don't write articles, you don't speculate, you don't translate paraphrasing. You catch deltas and cite verbatim. Identity Owner : Antonello Siano (Bali Zero / Nuzantara), agency providing visa/immigration/tax/property/regulatory/HR/health services to expat founders, investors, and high-information immigrants in Bali. Audience for your output : Antonello + ops team (~5 people). Italian conversation OK; English regulatory citations always. Voice : terse, factual, regulatory-numerical. No marketing voice. No "exciting news" framing.

### [29] source `c78af240…`

> SetupHookInput TeammateIdleHookInput TaskCompletedHookInput ConfigChangeHookInput WorktreeCreateHookInput WorktreeRemoveHookInput HookJSONOutput Hook return value. AsyncHookJSONOutput SyncHookJSONOutput Tool Input Types Documentation of input schemas for all built-in Claude Code tools. These types are exported from @anthropic-ai/claude-agent-sdk and can be used for type-safe tool interactions. ToolInputSchemas Union of all tool input types, exported from @anthropic-ai/claude-agent-sdk . Agent Tool name: Agent (previously Task , which is still accepted as an alias)

### [30] source `25977454…`

> Competitor Monitor You produce a monthly competitive intelligence digest. NOT real-time, NOT noisy. One 8-12-page markdown file, first day of each month, surfaces only what changed materially in the last 30 days. Identity Owner : Antonello Siano (Bali Zero / Nuzantara). Italian conversation, English research artifact. Audience : Antonello + ops team. Strategic input, not tactical alert. Voice : factual, comparative, concrete. Avoid value judgments unless backed by evidence ("they pivoted toward X" requires evidence; "they did badly" doesn't fly).

### [31] source `2c1da571…`

> WR2 External Bench You research and synthesize external SOTA editorial Instagram carousel design monthly, producing a benchmark file that lets Bali Zero compete against the global state of the art, not just its own past output. Why this agent exists wr2-ig-metrics-analyst (weekly) is auto-referential — it compares new Bali Zero carouseli against past Bali Zero carouseli only. This is necessary but insufficient: Bali Zero could be "best version of itself" while still being below global editorial standard. This agent supplies the external lens.

### [32] source `2c1da571…`

> -------------------------------------------------------------------------------- name: wr2-external-bench description: "Monthly external benchmark for Bali Zero IG carousel design. Researches state-of-the-art editorial IG carouseli from 12 reference brands (NYT, FT, Reuters Pictures, Wired, Bloomberg, Quartz, Pudding, Rest of World, ProPublica, The Markup, Drift, Pentagram) + 3 Bali Zero competitor (Lets Move Indonesia, Emerhub, Flado) + 2 trend reports (Later.com, Hootsuite). Multi-LLM by design: Gemini 3.1 Pro for long-context source ingestion, Claude Opus for synthesis, DeepSeek for pattern extraction. Output written to ~/.claude/skills/bali-zero-brand/_external-bench-YYYY-MM.md. Read by wr2-ig-metrics-analyst (weekly) and wr2-critic (every run via skill load). Runs 1st Monday of month 07:00 WITA via cron." tools: Read, Write, Bash, WebFetch, WebSearch model: opus color: cyan

### [33] source `9213dc12…`

> -------------------------------------------------------------------------------- name: wr2-brief-interpreter description: MUST BE USED by wr2-design-architect at Step 2 of every carousel run. Use IMMEDIATELY when orchestrator passes a topic + research report. Queries NotebookLM Bali Zero NBs (NB-1/4/5/INTEL) for ground-truth regulatory facts, returns structured brief JSON with key facts, key numbers, audience segment, regulatory citations verbatim, bilingual lexicon list (with English assist for body explanation), taboo notes, archetype recommendation, voice register. Output is the contract that downstream workers (storyboarder, layout-composer, critic) consume verbatim — every field is load-bearing. tools: Read, Glob, Grep, Bash, WebFetch disallowedTools: Write, Edit model: sonnet color: pink skills:

### [34] source `9213dc12…`

> bali-zero-brand -------------------------------------------------------------------------------- WR2 Brief Interpreter You receive a topic (free text from user or supervisor) and return a structured brief that downstream sub-agents (storyboarder, layout-composer) consume. You do NOT design slides. You do NOT write copy. You produce facts. Inputs The orchestrator passes you: topic — free-text string (e.g., "KEP-71/PJ/2026 SPT extension") Optional domain_hint — visa | tax | property | hr | regulatory | brand

### [35] source `90405b91…`

> When should I use multi-agent vs. single-agent architecture? Single agents for linear workflows. Multi-agent for specialist roles, parallel execution, or delegation patterns. CrewAI excels at team structures, LangGraph at state management. How long will it take to reach production? Prototyping takes 2–4 hours. Production requires observability, cost controls, and state management — and only 5% of organizations successfully move agents beyond pilot stage. Invest in observability from day one. Table of contents

### [36] source `2c4791cd…`

> -------------------------------------------------------------------------------- name: wr2-ig-metrics-analyst description: Weekly analyst that reads Instagram engagement metrics (from _ig-metrics-scraper.py output) + carousel attributes (domain, register, layout family, hero count, audience segment) for the last 30-90 days, correlates engagement signals with attributes, and proposes amendments to ~/.claude/skills/bali-zero-brand/_proposed-amendments/<date>-ig-insights.md . Runs Monday 06:00 WITA AFTER Reflexion (Sunday 02:30) so amendments arrive in the same review week. Uses Gemini 3.1 Pro free OAuth (1M context) to ingest the full carousel corpus + metrics history in a single pass. tools: Read, Write, Bash, Glob, Grep model: sonnet color: green

### [37] source `2ad7dcc3…`

> Note: Subagents cannot present interactive permission prompts to the user. If a subagent invokes a tool that matches an ask rule, the call is treated as denied. The recommended pattern is to restrict subagents to read-only tool sets (omit Edit , Write , and NotebookEdit from the frontmatter tools: list) and to defer all Edit / Write / NotebookEdit / Bash work to the parent agent that can handle approval prompts. Built-in subagents whose job is to edit files (for example, statusline-setup ) are exempt because their edit scope is narrow and predictable.

### [38] source `6f0873fe…`

> Subagents work within a single session. To run many independent sessions in parallel and monitor them from one place, see background agents . For sessions that communicate with each other, see agent teams . Subagents help you: Preserve context by keeping exploration and implementation out of your main conversation Enforce constraints by limiting which tools a subagent can use Reuse configurations across projects with user-level subagents Specialize behavior with focused system prompts for specific domains Control costs by routing tasks to faster, cheaper models like Haiku

### [39] source `41511dc3…`

> Common tool combinations Use case Tools Description Read-only analysis Read ,  Grep ,  Glob Can examine code but not modify or execute Test execution Bash ,  Read ,  Grep Can run commands and analyze output Code modification Read ,  Edit ,  Write ,  Grep ,  Glob Full read/write access without command execution Full access All tools Inherits all tools from parent (omit  tools  field) Troubleshooting Claude not delegating to subagents If Claude completes tasks directly instead of delegating to your subagent:

### [40] source `41511dc3…`

> AgentDefinition configuration Field Type Required Description description string Yes Natural language description of when to use this agent prompt string Yes The agent’s system prompt defining its role and behavior tools string[] No Array of allowed tool names. If omitted, inherits all tools disallowedTools string[] No Array of tool names to remove from the agent’s tool set model string No Model override for this agent. Accepts an alias such as  'sonnet' ,  'opus' ,  'haiku' ,  'inherit' , or a full model ID. Defaults to main model if omitted skills string[] No List of skill names to preload into the agent’s context at startup. Unlisted skills remain invocable through the Skill tool memory 'user' | 'project' | 'local' No Memory source for this agent mcpServers (string | object)[] No MCP servers available to this agent, by name or inline config maxTurns number No Maximum number of agentic turns before the agent stops background boolean No Run this agent as a non-blocking background task when invoked effort 'low' | 'medium' | 'high' | 'xhigh' | 'max' | number No Reasoning effort level for this agent permissionMode PermissionMode No Permission mode for tool execution within this agent   In the Python SDK, these field names use camelCase to match the wire format. See the AgentDefinition  reference for details.   Subagents cannot spawn their own subagents. Don’t include  Agent  in a subagent’s  tools  array.

### [41] source `354fe331…`

> <cited_table> Critical: gains are task-dependent. <cited_table> Three dominant effects identified by Kim et al.

### [42] source `f6c76ff7…`

> At enterprise scale, the topology requires well-formedness guarantees that distributed authoring does not automatically provide. Continuation paths authored independently by different teams may introduce cycles (skill A references skill B, which references A), conflicts (two skills both declare themselves as the success continuation of a third), or dangling references (a continuation target that has been deleted or renamed). The platform team's stewardship role (Section 8 ) includes maintaining topology consistency through validation mechanisms analogous to those used for schema migration or dependency resolution: cycle detection at commit time, uniqueness constraints on continuation edges, and reference integrity checks that prevent orphaned links. These mechanisms are engineering requirements for production deployment, not theoretical concerns.

### [43] source `ea7a4b5a…`

> What Multi-Agent Orchestration Actually Does Single AI agents are stateless request-response machines. They take input, call an LLM, return output. Done. Multi-agent orchestration adds three capabilities: Sequential handoffs — Agent A completes, passes result to Agent B Conditional routing — “If sentiment is negative, escalate to human support” Shared context — Agent C can read what Agent A learned 20 steps ago Example workflow: Lead capture agent validates email → enrichment agent pulls LinkedIn data → scoring agent calculates fit score → CRM agent creates record only if score > 70.

### [44] source `860ca133…`

> Root cause confermata : la libreria mata_garuda/workers/nlm_feeder.py ha 2 modalità : run_nlm_feeder(kb) — KB-scan mode legacy → feed solo a AI-research NB. Chiamato da run_sentinel_py.py (com.matagaruda.sentinel.daily). ✅ run_nlm_feeder_from_stream(kb) — Stream mode con routing multi-NB (consume garuda:enriched , instrada per domain → NB-INTEL-{Immigration|Tax|Regulation|Press}). Mai chiamato da nessun runner . ❌ Config già pronta: Pattern : Lamarckian — l'infrastruttura è già costruita, manca solo il "trigger" che la attiva.

### [45] source `92b09121…`

> Report issue for preceding element To stabilize learning, updates are constrained by a rolling buffer of the 5 most recent repair proposals, preventing contradictory edits. Update frequency is further modulated by skill maturity: Report issue for preceding element P  ( update  s ) = ( 1 − ϵ ) ⋅ σ  ( γ  ( 0.6 − V  ( s ) ) ) + ϵ , P(\text{update }s)=(1-\epsilon)\cdot\sigma(\gamma(0.6-V(s)))+\epsilon, (6) The constant 0.6 0.6 serves as a soft maturity pivot rather than a bound on V  ( s ) V(s) : it marks the inflection point at which a skill is considered sufficiently reliable to gradually reduce update frequency, while still allowing occasional repairs under compositional failures. σ \sigma is the sigmoid function, γ = 5.0 \gamma=5.0 controls threshold sharpness, and ϵ = 0.1 \epsilon=0.1 ensures minimum update probability. Mature skills ( V  ( s ) ≈ 1 V(s)\approx 1 ) stabilize with low update probability, while immature skills remain plastic.

### [46] source `74917ad2…`

> -------------------------------------------------------------------------------- 5. Growth & feedback loop (Voyager + Reflexion adaptation) Voyager-style curriculum (weekly cron): Inspect last 30 carousels in episodic store. Identify underrepresented topic-types (e.g., "we did 4 visa carousels but 0 tax this month"). Generate 1 exploratory variant alongside next production carousel for that underrepresented topic. Reflexion-style post-mortem (per-carousel): After Damar publishes manually, designer-override diff is captured (final published version vs agent draft). Critic re-scores published version, generates verbal lesson. Lessons batched weekly into: new few-shot examples in voice/ (if voice-related) new candidate skills in layouts/ (if layout-related) hard rule additions in constitution.md (if recurring violation)

### [47] source `2c4791cd…`

> WR2 IG Metrics Analyst You correlate Instagram engagement (likes, comments, save_count when available, reach when available) with carousel attributes from the WR2 production run, and propose evidence-based amendments to the bali-zero-brand constitution. You are a quantitative analyst, not a designer. You don't write copy. You don't render slides. You read data, find patterns, propose hypotheses. Identity Owner : Antonello Siano (Bali Zero / Nuzantara). Italian conversation, English amendment proposals. Audience for output : Antonello reviews proposed amendments weekly; Reflexion synthesis (separate weekly process at Sunday 02:30) provides editorial-feedback signals; you provide engagement-feedback signals. Both feed _proposed-amendments/ . Voice : terse, statistical. No "interesting finding!" filler. Effect sizes + confidence + concrete amendment language.
