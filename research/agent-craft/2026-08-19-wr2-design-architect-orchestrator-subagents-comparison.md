---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-19-wr2-design-architect-orchestrator-subagents-comparison

**Date**: 2026-08-19
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 8 / Citations: 14

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **`wr2-design-architect` (Opus 4.7)**: L'unico orchestratore centrale del flusso caroselli. Non scrive brief o layout direttamente; avvia i sub-agenti specializzati stateless, gestisce la scrittura su disco temporaneo `/scratch/` ed esegue il rendering tramite Playwright [11, 12].

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (L'Orchestratore Centrale)**

*   **Identità e contratti di Fan-out dell'Orchestratore:**
    > *"name: wr2-design-architect description: \"MUST BE USED for every Bali Zero WR2 editorial carousel. ... Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex...\""* [1]
    
*   **Topologia e coordinamento a "Stato Centralizzato":**
    > *"You orchestrate four stateless specialist subagents. Invoke each via the Agent tool with subagent_type=<name> and pass the prior step's structured JSON as the prompt. Specialists read shared brand cortex files; they NEVER talk peer-to-peer (Google's 17.2× error-amplification finding). All inputs and outputs are JSON or files on disk."* [2]
    > *"The orchestrator (you) is responsible for: (a) sequencing these calls; (b) writing intermediate state to apps/war-room/output/carousel/<slug>/; (c) deciding retries based on critic verdicts; (d) triggering Playwright rendering between Step 4 and Step 5; (e) writing the final outputs (Step 6) and queue handoff (Step 7)."* [3]

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

*   **La razionalità economica del Model Routing:**
    > *"Worker downgrade rationale (R2): brief-interpreter, storyboarder, layout-composer perform structured I/O with predictable schemas — Sonnet 4.6 delivers identical output quality at ~25% the cost of Opus. Orchestrator (you) and critic stay on Opus 4.7 because they require nuanced judgment (sequencing, retry decisions, vision-based brand verdict). Target end-to-end cost: \$3-5/run..."* [3]

*   **La giustificazione del multi-agente sequenziale (Kim et al. 2025):**
    > *"For sequential pipelines (brief → storyboard → layout → critic in chain, like WR2): single-agent batte multi-agent di 39–70%. Multi-agent in WR2 is justified by context-isolation and model-routing economy (Sonnet workers + Opus critic + Haiku vision-pre-pass), not by parallelism gain."* [4]

*   **Integrazione del loop di Fallimento Asincrono (Human-in-the-Loop):**
    > *"If you cannot produce a carousel that passes critic panel after 2 retries: 1. Write STATUS: needs_human_edit to the output slides.json. 2. POST to http://localhost:8765/api/flag-needs-human-edit with {item_id, reason, retry_count, critic_report_path} so Damar's queue UI shows the yellow pill."* [5]
    > Questo si riflette nello stato della coda: *"drafted_needs_human_edit: orchestrator exhausted retry budget (2 critic rounds failed). Visible to Damar as a yellow-bordered row with \"needs human edit\" pill."* [6]

---

### **2. Confronto con l'Applicazione Reale nel nostro Stack (Bali Zero)**

Il funzionamento del nostro agente orchestratore `wr2-design-architect` implementa rigorosamente la separazione tra la logica di coordinamento e la scrittura dei contenuti:

*   **Isolamento del Contesto e Prevenzione del "Context Rot":**
    Come evidenziato dalle lezioni di Kim et al. [4] e dall'esperienza sul campo, forzare un singolo modello a gestire l'intera generazione (briefing, stesura testi, programmazione HTML e critica estetica) porta a una rapida saturazione del contesto e a deviazioni sistematiche dalle regole del brand. Il nostro orchestratore **non scrive mai codice HTML o bozze testuali direttamente** [1]. Al contrario, avvia programmaticamente sub-agenti lavoratori stateless, confinando le operazioni di calcolo intense (come l'estrazione RAG dei dati immigratori su `NB-1` eseguita da `wr2-brief-interpreter` [7]) all'interno di sessioni isolate che restituiscono solo payload JSON strutturati [2].
*   **Efficienza Economica del Routing dei Modelli:**
    Invece di adottare un approccio monolitico basato interamente su Opus (che farebbe lievitare i costi a oltre \$8 per singola esecuzione), l'orchestratore applica la **Worker Downgrade Rationale (R2)** [3]. Le fasi puramente strutturate (elaborazione del brief, stesura dello storyboard narrativo e composizione dei parametri HTML) vengono delegate a **Claude Sonnet 4.6** [2]. Opus 4.7 viene attivato solo per l'orchestrazione di alto livello e per la validazione estetica multimodale di `wr2-critic` [2, 3].
*   **Gestione dell'Ambiente di Esecuzione e Ispezione di `/scratch/`:**
    L'orchestratore supervisiona l'intera catena di compilazione scrivendo lo stato transitorio all'interno della directory `/workspace/scratch/<slug>/` (o `apps/war-room/output/carousel/<slug>/` in produzione) [3]. Sotto il cofano, l'orchestratore esegue un preflight di controllo unificato richiamando lo script di audit deterministico `_audit-checklist.sh` per verificare che l'ambiente sia pulito e privo di collisioni di lavoro prima di innescare il rendering Playwright [8].
*   **State Machine Fail-Safe e Notifiche Asincrone:**
    Quando si verifica un fallimento bloccante (ad esempio, se il layout compilato da `wr2-layout-composer` [9] fallisce per due volte consecutive il severo esame di contrasto e palette di `wr2-critic` [10]), l'orchestratore evita loop infiniti di riparazione [5]. Interrompe immediatamente la pipeline, scrive lo stato `needs_human_edit` [5] e invia un payload `POST` all'endpoint locale `http://localhost:8765/api/flag-needs-human-edit` [5], popolando la coda in `human-review-queue.json` [6].

---

### **3. Linea di Azione Concreta: Lo "State Checkpointer" nel modulo Orchestrator**

Attualmente, se uno dei sub-agenti fallisce o l'esecuzione della shell si interrompe a metà (ad esempio, durante la generazione dell'immagine o la compilazione Playwright), l'orchestratore non dispone di un punto di ripristino nativo e deve ricominciare l'intero processo da Step 1, sprecando token preziosi per rigenerare brief e storyboard già validi.

*   **Azione:** Implementare un modulo deterministico di **Episodic State Checkpointing** integrato nella libreria di orchestrazione di Bali Zero.
*   **Implementazione Operativa:**
    1.  **Generazione del file di stato `state_checkpoint.json`:**
        Configurare l'orchestratore per scrivere lo stato corrente serializzato nella directory temporanea `/workspace/scratch/<slug>/state_checkpoint.json` al termine di ogni fase andata a buon fine.
    2.  **Tracciamento dei Passaggi (Fasi 2-5):**
        ```json
        {
          "carousel_slug": "investor-kitas-pma-2026",
          "current_step": "Step 4 - Layout Generation",
          "completed_steps": {
            "Step 2 - Brief Interpretation": {
              "brief_json_path": "/workspace/scratch/investor-kitas-pma-2026/brief.json",
              "timestamp": "2026-08-18T16:30:00Z"
            },
            "Step 3 - Storyboarding": {
              "slides_json_path": "/workspace/scratch/investor-kitas-pma-2026/slides.json",
              "timestamp": "2026-08-18T16:31:00Z"
            }
          },
          "execution_metadata": {
            "retry_count": 0,
            "orchestrator_session_id": "92a63010-c526-4282-a225-e2d72f00dc9c"
          }
        }
        ```
    3.  **Algoritmo di Ripristino (Resume-on-Failure):**
        All'avvio, `wr2-design-architect` verificherà l'esistenza di un checkpoint valido per lo `<slug>` di riferimento. Se presente e intatto, caricherà in memoria i payload JSON già prodotti dai lavoratori stateless (scaltramente memorizzati in `/scratch/`), saltando le chiamate a `wr2-brief-interpreter` e `wr2-storyboarder` e riprendendo l'esecuzione esattamente dal punto in cui si era interrotta (es. rigenerando solo il codice HTML o ri-eseguendo Playwright), dimezzando i tempi di ripristino e azzerando i costi di rigenerazione duplicati.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Programmazione Estetica via Feedback Verbale:** In che modo l'orchestratore Opus 4.7 può convertire i riscontri qualitativi multimodali emessi da `wr2-critic` (es. *"La casella di testo su Slide 3 ha un contrasto insufficiente del 3.5:1 rispetto allo sfondo"* [10]) in parametri CSS o classi di layout deterministiche che il lavoratore Sonnet `wr2-layout-composer` [9] sia in grado di interpretare e applicare autonomamente per correggere il codice HTML durante il ciclo di retry?
2.  **Integrazione dei "Task Budgets" di Opus 4.7:** Sfruttando la funzionalità di *Task Budgets* introdotta in Claude Opus 4.7 [11], come possiamo configurare programmaticamente un tetto massimo di spesa in dollari per singolo carosello direttamente nell'orchestratore, assicurandoci che una sequenza instabile di retry del critic non superi mai un budget prefissato (es. \$5.00) e si autolimiti prima di esaurire le quote di sessione?
3.  **Asynchronous Dreaming per la Brand-Evolution:** Se abilitiamo il modulo di **"Dreaming"** (Asynchronous Reflection) [12, 13] sulle nostre code di produzione, come può l'orchestratore utilizzare i momenti di inattività del sistema per analizzare in background il database SQLite `wr2-episodic.db` [14] e redigere autonomamente proposte di patch strutturali alla `constitution.md` basate sulle discrepanze ricorrenti inserite manualmente da Damar?

## Sources used (8)

- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `354fe331-a3bd-4596-88c8-d4fb4c4da5a8`
- `2bf023eb-6410-4639-979a-6c19fe879fec`
- `e65a5f8f-9bac-44c8-bf39-a13841e40f93`
- `1826e81e-6d39-4285-956a-464b315e3f3f`
- `2edf7f4b-6748-422c-a00d-b7f724b625df`
- `7a8a7f72-4109-43ff-ac12-7645c1217cde`
- `74917ad2-2ae3-4a43-ba8c-e5876ec073fc`

## Citations verbatim (14)

### [1] source `d0adf453…`

> -------------------------------------------------------------------------------- name: wr2-design-architect description: "MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]", "draft a WR2 brief", or invokes the WR2 pipeline. Orchestrator-only: fans out to 4 specialist subagents (brief-interpreter, storyboarder, layout-composer, critic), NEVER writes brief.json/slides.json/HTML inline. Reads brand cortex (constitution + tokens + voice + 64 past carouseli), enforces 3 contracts (fan-out, NB ground-truth, imagegen no-silent-reuse), runs critic gate, emits queue handoff. Grows via Voyager skill library + Reflexion weekly synthesis." tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch model: opus isolation: worktree color: blue skills:

### [2] source `d0adf453…`

> You orchestrate four stateless specialist subagents. Invoke each via the Agent tool with subagent_type=<name> and pass the prior step's structured JSON as the prompt . Specialists read shared brand cortex files; they NEVER talk peer-to-peer (Google's 17.2× error-amplification finding). All inputs and outputs are JSON or files on disk. <cited_table>

### [3] source `d0adf453…`

> Worker downgrade rationale (R2) : brief-interpreter, storyboarder, layout-composer perform structured I/O with predictable schemas — Sonnet 4.6 delivers identical output quality at ~25% the cost of Opus. Orchestrator (you) and critic stay on Opus 4.7 because they require nuanced judgment (sequencing, retry decisions, vision-based brand verdict). Target end-to-end cost: $3-5/run (test-4 at $7.99 was Opus-everywhere). Concrete invocation pattern: The orchestrator (you) is responsible for: (a) sequencing these calls; (b) writing intermediate state to apps/war-room/output/carousel/<slug>/ ; (c) deciding retries based on critic verdicts; (d) triggering Playwright rendering between Step 4 and Step 5; (e) writing the final outputs (Step 6) and queue handoff (Step 7).

### [4] source `354fe331…`

> Corrected guidance for Bali Zero stack The old rule (wr2-design-architect.md:338, lines 91+129+338, also pre-T2.91, pre-T2.271): "NEVER let subagents talk to each other peer-to-peer (Google's 17.2× error-amplification finding)." The corrected rule : For sequential pipelines (brief → storyboard → layout → critic in chain, like WR2): single-agent batte multi-agent di 39–70% . Multi-agent in WR2 is justified by context-isolation and model-routing economy (Sonnet workers + Opus critic + Haiku vision-pre-pass), not by parallelism gain. Don't pretend it's a parallelism win. For parallelizable tasks (multi-perspective client case, multi-source regulatory check, cross-LLM bipolar verifier): centralized multi-agent batte single-agent di +80.9% . This is where agent teams shines. Peer-to-peer is not banned — it's 4× worse than centralized, but on parallelizable tasks it's still often better than single-agent. Use it when the task genuinely needs cross-agent challenge (devil's advocate, scientific debate pattern in agent-teams docs). Independent (no coordination) is the real trap — 17.2× amplification. Never spawn N parallel sessions and merge results without any lead.

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [5] source `d0adf453…`

> ~/.claude/agents/wr2-design-architect-resources/deep-research.md — academic + industry research synthesis. ~/.claude/agents/wr2-design-architect-resources/architecture-patterns.md — multi-vendor architecture patterns. NB-DESIGN-AGENT ( 815b081c-d477-48b0-9780-45f12c1d664f ) — 13 curated sources on agent design, accessible via mcp__notebooklm-mcp-cli__chat . Failure mode If you cannot produce a carousel that passes critic panel after 2 retries: Write STATUS: needs_human_edit to the output slides.json . POST to http://localhost:8765/api/flag-needs-human-edit with {item_id, reason, retry_count, critic_report_path} so Damar's queue UI shows the yellow pill. Surface the issue clearly to the user (which rubric failed, which slides). STOP.

### [6] source `2bf023eb…`

> Human-in-loop review queue schema Addresses Codex FLAW MEDIUM "human-in-loop under-specified". Damar publishes manually but without a queue schema, "ignored" cannot be distinguished from "approved". Storage location ~/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json Single JSON array. Append-only by orchestrator. Modified in-place by Damar's tooling (or by Antonello if Damar unavailable). Schema State machine State definitions drafted : agent produced carousel, queued for Damar. Initial state. drafted_needs_human_edit : orchestrator exhausted retry budget (2 critic rounds failed). Visible to Damar as a yellow-bordered row with "needs human edit" pill. Damar opens, reviews critic report ( needs_human_edit_critic_report ), edits manually in Canva, then transitions to reviewed . Set by POST /api/flag-needs-human-edit from wr2-design-architect . Required fields: needs_human_edit_reason , needs_human_edit_retry_count , needs_human_edit_critic_report , needs_human_edit_flagged_at . reviewed : Damar opened the Canva design and made a decision (any of next 4 transitions). published : Damar posted the carousel verbatim to Instagram. Most common case. published_with_edits : Damar made changes in Canva before publishing. The designer_override_diff MUST be filled — this is the gold-standard learning signal. rejected : Damar refused publication. damar_notes field MUST contain the reason. ignored : 14 days elapsed without review. Auto-transitioned by daily cron. NOT a learning signal — could mean "Damar busy" or "topic stale" or "carousel bad". Don't optimize against ignored. withdrawn : Antonello pulled before Damar acted. Reason in damar_notes (overloaded with withdrawn_reason semantics).

### [7] source `d0adf453…`

> Step 2 — Interpret the brief Receive a topic from user (or from wr2_supervisor.py pending state). Spawn wr2-brief-interpreter and pass through its full structured brief schema (orchestrator does NOT re-parse — passes verbatim to storyboarder Step 3): RAG step : for key_facts , query NotebookLM via mcp__notebooklm-mcp-cli__* against the relevant NB: visa/immigration → NB-1 tax → NB-4 property → NB-5 regulatory cross-domain (incl HR/labor/BPJS) → NB-INTEL family health (dengue, outbreaks, medical) → web research + NB-INTEL Press design/brand questions → NB-DESIGN-AGENT ( 815b081c-d477-48b0-9780-45f12c1d664f )

### [8] source `d0adf453…`

> Output is structured (KEY=value lines), parse via grep '^KEY=' . Exit code 0 = PASS, non-zero = audit failed (orchestrator must abort and report). Hard rule : in Step 0, run MODE=preflight ONCE. After Step 4, run MODE=hero-sha ONCE. After Playwright render, run MODE=render-check ONCE. Before READY emission, run MODE=final-audit ONCE. That is 4 audit Bash calls total , not 30+. Any verification you can derive from the script's output, do NOT re-run separately. Contract A — Fan-out (mandatory) You MUST invoke the four specialist subagents through the Agent tool. Inline replacement of their work is forbidden, even if you "could do it faster". The fan-out is what we're testing — not the artifact quality.

### [9] source `e65a5f8f…`

> -------------------------------------------------------------------------------- name: wr2-layout-composer description: "MUST BE USED by wr2-design-architect at Step 4 of every carousel run. Use IMMEDIATELY after storyboarder returns slides.json. Receives slide-spec JSON + brief JSON verbatim, retrieves matching layout from skill library, parameterizes HTML/CSS, writes render-ready files for Playwright. ENFORCES no silent placeholder reuse (Article 5.10): every hero image_source must be imagegen:<session> or anchor:<file> with sha256(hero) ≠ sha256(anchor) verification. Does NOT render itself (orchestrator drives Playwright)." tools: Read, Write, Edit, Glob, Grep, Bash model: sonnet color: yellow skills:

### [10] source `1826e81e…`

> -------------------------------------------------------------------------------- name: wr2-critic description: MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. Use IMMEDIATELY after Playwright renders PNGs. Reviews rendered carousel slides against Bali Zero brand constitution + brief verbatim. Receives PNG paths + slide-spec JSON + brief JSON + brand cortex pointer. Returns 4-rubric scores AND a binary verdict per slide (PASS / FAIL with one-line reason) plus retry feedback. Verifies Article 6.2 bilingual assist on first occurrence, Article 6.3 bullet-promise, Article 5.10 no silent placeholder reuse via sha256 anchor check. tools: Read, Write, Glob, Grep, Bash model: opus color: red memory: user skills:

### [11] source `2edf7f4b…`

> 2026-02-17 Claude Sonnet 4.6 is announced , retaining the 1-million-token beta context window introduced with Sonnet 4.5 and adding major improvements in coding and Computer Use. Early-access developers preferred Sonnet 4.6 to Opus 4.5 in 59% of evaluations. Model identifier claude-sonnet-4-6 . Source: Claude Sonnet 4.6 . 2026-04-16 Claude Opus 4.7 is announced as the current frontier model with substantial gains on the hardest coding tasks, higher-resolution vision input, a new xhigh effort level, file-system-based memory recall across sessions, and the Task Budgets public beta. Available on the Claude API, Amazon Bedrock, Google Cloud Vertex AI, and Microsoft Foundry. Model identifier claude-opus-4-7 . Source: Claude Opus 4.7 .

### [12] source `7a8a7f72…`

> This modularity is not an internal engineering detail, it is a product decision. It allows Anthropic to release, one month after the Managed Agents launch and at Code with Claude in San Francisco on May 6, 2026, a burst of new features without touching the components that are already stable: the research preview of "dreaming" , plus outcomes, multiagent orchestration, and webhooks pushed into public beta. Claude @claudeai · Follow Live from Code with Claude: we're launching dreaming in Claude Managed Agents as a research preview. Outcomes, multiagent orchestration, and webhooks are now in public beta.

### [13] source `7a8a7f72…`

> The media could not be played. Reload 9:46 AM · May 6, 2026 14.7K Reply Copy link Read 563 replies Dreaming is the ability for an agent to "think" between one task and the next, asynchronously reflecting on past results and proposing course corrections. Outcomes, multiagent orchestration, and webhooks moved into public beta in the same announcement. Four new pieces that drop into the same architectural skeleton without breaking anything already running on top. The Code with Claude 2026 conference was the public demonstration, one month after launch, of the principle stated in the April engineering blog.

### [14] source `74917ad2…`

> constitution.md — hard brand rules (palette, type, taboo) tokens.json — design tokens (machine-readable) voice/ — few-shot examples on-tone vs off-tone layouts/ — parametric layout skills (each = SKILL.md + render snippet) past/ — last N carousels as in-context reference (PNG + brief.md) Memory layers : Episodic : SQLite at ~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db — one row per carousel run. Semantic : brand cortex files (above). Procedural : skill library (above). Reflective : weekly cron synthesizes episodes into lessons appended to voice/ and skills/.
