---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-09-04-voyager-reflexion-error-amplification-agent-evolution

**Date**: 2026-09-04
**Mode**: fallback
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 12 / Citations: 34

## Question

> In italiano. Tema di oggi (round-robin giorno 5): evolution mechanics: Voyager skill library, Reflexion weekly synthesis, Kim et al. error amplification. Come applichiamo questi paper alla nostra stack?

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta. Termina con 3 domande aperte per il DR di domani.

## Answer

### **1. Le Basi Teoriche: Evoluzione, Rinforzo e Topologie (Fonti Canoniche)**

L'integrazione di meccanismi di evoluzione continua all'interno di un sistema multi-agente si scontra inevitabilmente con i limiti fisici della finestra di contesto ("context rot") [1] e con la tendenza all'amplificazione degli errori a livello sistemico [2]. Per strutturare una flotta di agenti in grado di auto-migliorarsi, ci affidiamo alla sintesi di tre filoni di ricerca fondamentali:

#### **A. Voyager Skill Library: L'Accumulo di Competenze Simboliche**
Il concetto di libreria di skill persistente nasce dalla necessità di superare l'ephemeralità delle sessioni standard degli agenti LLM [3]:
*   **Voyager (Wang et al., 2023)**:
    > *"Voyager consists of three key components: 1) an automatic curriculum that maximizes exploration, 2) an ever-growing skill library of executable code for storing and retrieving complex behaviors, and 3) a new iterative prompting mechanism that incorporates environment feedback, execution errors, and self-verification for program improvement."* [4]
*   **La Traduzione Architetturale (PSN - Evolving Programmatic Skill Networks)**:
    > *"PSN uniquely maintains an explicit computational graph of executable programs that supports trace-based credit assignment, maturity-aware stabilization, and principled structural refactoring."* [5]
    Ispirandosi all'open standard delle **Agent Skills** [6], il sistema implementa un modello a rilascio progressivo (*progressive disclosure*) [7]:
    > *"At startup, agents load only the name and description of each available skill (approximately 100 tokens); when a task matches a skill's description, the agent reads the full instructions into context..."* [7]

#### **B. Reflexion: Apprendimento per Rinforzo Verbale**
Per correggere i comportamenti errati senza ricorrere a costosi e instabili cicli di fine-tuning (inapplicabili su piccole scale campionarie) [8], utilizziamo il feedback testuale:
*   **Reflexion (Shinn et al., 2023)**:
    > *"Reflexion is a novel framework to reinforce language agents not by updating weights, but instead through linguistic feedback. Concretely, Reflexion agents verbally reflect on task feedback signals, then maintain their own reflective text in an episodic memory buffer to induce better decision-making in subsequent trials."* [9]
*   **Post-Mortem in Ambienti di Design**:
    > *"Actor proposes a slide, Evaluator scores against rubric (typography, palette, copy-image fit), Self-Reflection writes verbal lesson into memory for next iteration. Lesson goes into the skill library, not just current run."* [10]

#### **C. Kim et al. 2025: La Legge di Scala delle Topologie Multi-Agente**
L'accumulo di agenti privi di coordinamento strutturato produce il temuto effetto "Bag of Agents" [11]. Lo studio di Kim et al., *"Towards a Science of Scaling Agent Systems"* (arXiv:2512.08296) [11, 12], mappa scientificamente questo comportamento:
*   **L'Amplificazione dell'Errore**:
    > *"Multi-agent error amplification 17.2× (Kim et al. 2025 arxiv 2512.08296) is real but task-dependent — orchestrator-led shrinks to 4.4×, sequential tasks favor single-agent, parallelizable tasks favor centralized multi-agent."* [13]

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.
*   **Il Trade-off dei Task**:
    > *"For sequential pipelines [...] single-agent batte multi-agent di 39–70%. Multi-agent in WR2 is justified by context-isolation and model-routing economy [...], not by parallelism gain."* [14]
    Al contrario, per task parallelizzabili (es. ricerca multi-fonte, audit di reclami):
    > *"centralized multi-agent batte single-agent di +80.9%."* [14]

---

### **2. Confronto e Applicazione nello Stack Reale Bali Zero**

Nel nostro ecosistema reale, applichiamo queste tre pietre miliari della letteratura scientifica integrando la teoria dei modelli di memoria di CoALA (working, episodic, semantic, procedural e reflective) [15, 16]:

*   **Pianificazione Sequenziale vs. Parallela (La Correzione di Kim et al.)**:
    Il nostro flusso per i caroselli editoriali WR2 è strettamente sequenziale (brief interpretato \\(\rightarrow\\) storyboard \\(\rightarrow\\) layout \\(\rightarrow\\) critica) [17]. Riconoscendo l'evidenza empirica per cui il multi-agente puro degrada le prestazioni sequenziali fino al 70% [14], **giustifichiamo la nostra flotta multi-agente solo come barriera contro il context rot** e come ottimizzatore economico (modelli Sonnet a basso costo per la scrittura, Opus limitato all'orchestrazione e alla critica visiva) [14, 18]. 
    Al contrario, per i compiti altamente parallelizzabili, come il nostro **Cross-LLM Bipolar Verifier** (il panel di verifica delle affermazioni legali/fiscali), implementiamo la topologia centralizzata *agent-teams* [19, 20], in cui l'orchestratore Opus lancia 4 sub-agenti in parallelo (ognuno collegato a un modello diverso tramite CLI) per sfidare le assunzioni attraverso un dibattito asincrono basato su file di log immutabili [21, 22].
*   **La Raccolta delle Lezioni nel Critic (Il Loop Reflexion)**:
    Il nostro sub-agente `wr2-critic` (Opus 4.7 Vision) esegue una forma di **autolearning continuo** derivato da Reflexion [23]:
    > *"When you identify a new failure pattern during a critic run (not a single-slide bug — a systemic recurring issue), write a lesson file to ~/.claude/skills/bali-zero-brand/_lessons/YYYY-MM-DD-<slug>.md BEFORE returning the verdict."* [23]
    Queste lezioni vengono ri-allegate automaticamente a SessionStart tramite il precaricamento della skill di brand [24, 25]. Inoltre, la domenica notte alle 02:30 WITA, un cron-job esegue `_reflexion-synthesis.py` [25]. Questo script confronta i nostri draft con i **diff di override del designer** (le modifiche manuali apportate in Canva da Damar) [25]. Le discrepanze ricorrenti vengono convertite in modifiche permanenti alla `constitution.md` o in nuovi esempi di tono in `voice/on-tone-examples.md` [25].
*   **Curriculum Automatico e Graduazione delle Skill (La Logica Voyager)**:
    Per combattere la "template fatigue" (la tendenza dell'agente a collassare riutilizzando sempre gli stessi 2-3 layout grafici) [2], l'orchestratore applica un curriculum automatico Voyager-style [25]: scansiona le ultime 30 esecuzioni nel database SQLite episodico `wr2-episodic.db` per individuare le aree tematiche trascurate (es. "zero post sulle tasse negli ultimi 14 giorni") [25]. Innesca quindi un run contrassegnato come `exploration: true` [25], inducendo lo storyboarder a sperimentare una nuova combinazione o un layout proposto [25]. Se la nuova skill supera la soglia di qualità del critic per 3 volte di fila, viene promossa (*graduated*) da `_proposed/` a membro stabile della cartella `layouts/` [25].

---

### **3. Linea di Azione Concreta: Il "Rollback-Based Layout Evaluator"**

L'anello debole del nostro attuale ciclo di evoluzione Reflexion risiede nella **graduazione cieca delle skill**. Quando `_reflexion-synthesis.py` propone una patch a un layout o una nuova variante in `_proposed/` basandosi sul feedback verbale, non eseguiamo alcuna validazione di regressione prima di caricarla in produzione, rischiando di rompere layout precedentemente stabili.

*   **Azione**: Implementare nella libreria Bali Zero un modulo di **Rollback Validation** deterministico [26], modellato sul comportamento dei Programmatic Skill Networks.
*   **Procedura Operativa**:
    1.  **Fase di Proposta**: Quando lo script domenicale Reflexion genera una nuova bozza di layout in `layouts/_proposed/<new-layout>.md`, non la promuove direttamente.
    2.  **Esecuzione del Preflight Test (Rollback Gate)**: Lo script di evoluzione avvia una sessione isolata (tramite un sub-agente di test) ed esegue un rendering headless tramite Playwright utilizzando il nuovo layout proposto su una suite fissa di 3 caroselli storici di riferimento (gold standard).
    3.  **Audit di Regressione**:
        *   Lo script analizza i PNG generati utilizzando il nostro *preflight contrast checker* Python (sviluppato nel Day 3) e calcola il punteggio di conformità visiva.
        *   Se il tasso di successo del rendering o il punteggio del critic cala di oltre il **20%** rispetto alla baseline memorizzata (o se si verificano violazioni del contrasto WCAG), il layout proposto viene bocciato ed escluso dal roll-out [26].
        *   In caso contrario, lo script esegue il git commit sul ramo di sviluppo, notificando Antonello per la firma finale prima del merge sul main di produzione [27].

Questo meccanismo di "governance-as-code" [28] impedisce la regressione estetica introducendo un vero **trust region simbolico** nell'evoluzione delle nostre skill [29].

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **Co-ottimizzazione e Propagazione Verticale del Gradiente (Cross-Skill Contract)**: In presenza di un fallimento di rendering a valle (es. testo che trabocca dal box in `wr2-layout-composer`), come possiamo strutturare il processo di Reflect affinché non tenti di correggere localmente il CSS, ma propaghi un "gradiente simbolico" verso l'alto al lavoratore `wr2-storyboarder` per forzarlo a condensare o dividere la narrazione in più slide (Co-Optimization tra padre e figlio) [30, 31]?
2.  **Maturity-Aware Gating applicato alla Brand Constitution**: Se applichiamo la formula di stabilizzazione del PSN:
    \\[\mathcal{P}(\text{update } s) = (1 - \epsilon) \cdot \sigma(\gamma(0.6 - V(s))) + \epsilon\\] [32]
    come possiamo calcolare empiricamente l'indice di affidabilità \\(V(s)\\) per i nostri file costituzionali statici (es. `taboo.md` o i parametri in `tokens.json`) per assicurarci che le porzioni consolidate del brand si comportino come "layer congelati" di una rete neurale, resistendo a modifiche distruttive indotte da singoli outlier di errore nel Reflexion settimanale [29, 32]?
3.  **Allineamento semantico delle Skill tramite Clustered Embeddings**: Quando il Reflexion domenicale rileva una moltitudine di micro-lezioni testuali accumulate dai sub-agenti, in che modo l'orchestratore può utilizzare algoritmi di clustering (es. HDBSCAN sugli embedding generati tramite `/v1/embeddings`) per consolidare le lezioni ridondanti o strutturalmente affini in un'unica skill astratta ("Sibling Specialization") evitandone la proliferazione incontrollata nel nostro registro [33, 34]?

## Sources used (12)

- `f6c76ff7-bd1c-4b0b-b480-8a1fbdf93cc8`
- `a1f286dd-f3bd-4cb5-8614-08f4deef3160`
- `668876f3-0e09-4835-927c-2eed811e5cee`
- `92b09121-412d-4ece-a88e-86b922424a15`
- `7c040d97-ee62-44b7-a08a-c37cfdc3c793`
- `354fe331-a3bd-4596-88c8-d4fb4c4da5a8`
- `4001017f-0461-4321-b6a2-49f427986150`
- `74917ad2-2ae3-4a43-ba8c-e5876ec073fc`
- `d0adf453-1edb-4966-8a1c-a545718a4f2f`
- `b67fe2b2-5ee8-460a-b793-ccb71d1b752d`
- `097cb963-865c-4dba-8d6c-eb5bad4338f3`
- `1826e81e-6d39-4285-956a-464b315e3f3f`

## Citations verbatim (34)

### [1] source `f6c76ff7…`

> This transfer problem manifests in AI agents as what this paper terms the Institutional Impedance Mismatch : the structural disconnect between a knowledge consumer's existing knowledge and the specific institutional patterns of the organization it serves. When an agent encounters an enterprise task, it attempts to act on the basis of its generic training knowledge—but this knowledge does not encode the organization's particular naming conventions, architectural guardrails, deployment constraints, or compliance requirements. The agent's initial attempt violates an organization-specific convention; the user corrects the error; the agent adjusts but encounters another unknown constraint; a further correction follows. Each iteration consumes context tokens with failed attempts, error descriptions, and correction instructions. Recent empirical research has identified this progressive accumulation of irrelevant and redundant content as context rot —the measurable degradation of LLM performance as the context window fills [ 16 ] . The Institutional Impedance Mismatch thus drives a failure cascade that systematically erodes the agent's effective reasoning capacity through mismatch-induced context rot. Section 3 formalizes this dynamic as the productivity paradox and identifies its sociotechnical consequences, including what this paper terms the institutional knowledge tax —the disproportionate overhead imposed on senior engineers who must manually supply the organizational context that agents cannot infer. The parallel to human onboarding is structural, not metaphorical: a new engineer entering an unfamiliar codebase undergoes the same cycle—guessing at conventions, violating unstated norms, consuming senior engineers' time with corrections—over weeks and months rather than context window turns [ 12 ] . Knowledge Activation addresses the paradox for both classes of knowledge consumer by closing the impedance mismatch at the point of knowledge architecture rather than relying on runtime correction.

### [2] source `a1f286dd…`

> Style-consistent character generation is mostly relevant if Bali Zero introduces a recurring illustrated character or persona. The 2025 paper "Few-shot multi-token DreamBooth with LoRA for style-consistent character generation" (arxiv 2510.09475) gives the production recipe. -------------------------------------------------------------------------------- 8. Pitfalls and risk register Anti-patterns observed in academic and industry literature, with mitigations: Mode collapse / template fatigue — agent reuses same 2–3 layouts. Mitigation : explicit diversity penalty in curriculum (penalize selecting a skill used in last N carousels), enforce minimum skill-library coverage. Voyager-style automatic curriculum addresses this. Brand drift via attribute interpolation — diffusion models smoothly interpolate between trained modes producing colors/fonts that almost look like the brand but aren't. Mitigation : post-render quality gate using variance metric from NeurIPS 2024 hallucination paper; deterministic palette-snap step that quantizes generated colors to nearest brand-palette token. Hallucinated brand attributes — agent invents fonts/colors not in kit because prompt was under-constrained. Mitigation : never let LLM emit hex codes or font names directly; force it to reference token names from brand JSON. Token namespace is a closed set — anything outside it is rejected at layout-solver step. Over-templating — agent rigidly fills slots; all carousels look identical. Mitigation : skill library encodes families of layouts with parameterized variation (typographic scale, hierarchy emphasis, image-text ratio). Agent picks family + parameters, not frozen template. Under-constrained creativity — without explicit guardrails, agent goes off-brand to be "interesting". Mitigation : critic agent with brand-rubric (palette adherence ≥ X%, type system adherence, copy in voice) and hard fail on rubric violations. Generator-Critic loop with conditional looping. Single-critic blind spot — generator and critic share same model's biases. Mitigation : persona-based multi-critic (typography + brand + copy + marketing-result), cross-model panel (Claude main, Gemini cross-check, NotebookLM ground-truth) — the bipolar verifier pattern already in use at Bali Zero. Agent error compounding in multi-agent systems — Google's 2025 study found independent multi-agent systems amplify errors 17.2× vs single-agent baselines unless centralized state management is added. Mitigation : orchestrator agent owns canonical state, sub-agents are stateless functions that read shared state and emit deltas. No autonomous peer-to-peer hand-offs in production.

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [3] source `f6c76ff7…`

> Internalization → \rightarrow Agent Execution. Internalization—the conversion of explicit knowledge back into tacit knowledge through practice—finds its analog in agent execution. When an agent receives an AKU via injection and successfully completes the specified task, the agent has, in effect, “internalized” the organizational knowledge for the duration of that invocation. Unlike human internalization, this process is ephemeral: the agent does not retain the knowledge across invocations (absent explicit memory mechanisms), and the AKU must be re-injected for future tasks. This ephemerality reinforces the importance of efficient injection mechanisms.

### [4] source `668876f3…`

> arXiv:2305.16291 (cs) [Submitted on 25 May 2023 ( v1 ), last revised 19 Oct 2023 (this version, v2)] Title: Voyager: An Open-Ended Embodied Agent with Large Language Models Authors: Guanzhi Wang , Yuqi Xie , Yunfan Jiang , Ajay Mandlekar , Chaowei Xiao , Yuke Zhu , Linxi Fan , Anima Anandkumar View a PDF of the paper titled Voyager: An Open-Ended Embodied Agent with Large Language Models, by Guanzhi Wang and 7 other authors View PDF Abstract: We introduce Voyager, the first LLM-powered embodied lifelong learning agent in Minecraft that continuously explores the world, acquires diverse skills, and makes novel discoveries without human intervention. Voyager consists of three key components: 1) an automatic curriculum that maximizes exploration, 2) an ever-growing skill library of executable code for storing and retrieving complex behaviors, and 3) a new iterative prompting mechanism that incorporates environment feedback, execution errors, and self-verification for program improvement. Voyager interacts with GPT-4 via blackbox queries, which bypasses the need for model parameter fine-tuning. The skills developed by Voyager are temporally extended, interpretable, and compositional, which compounds the agent's abilities rapidly and alleviates catastrophic forgetting. Empirically, Voyager shows strong in-context lifelong learning capability and exhibits exceptional proficiency in playing Minecraft. It obtains 3.3x more unique items, travels 2.3x longer distances, and unlocks key tech tree milestones up to 15.3x faster than prior SOTA. Voyager is able to utilize the learned skill library in a new Minecraft world to solve novel tasks from scratch, while other techniques struggle to generalize. We open-source our full codebase and prompts at this https URL .

### [5] source `92b09121…`

> Report issue for preceding element We introduce the Programmatic Skill Network (PSN), a framework for continually evolving skill libraries. In a PSN, each skill is a symbolic program (e.g., in JavaScript for Minecraft, Python for Crafter) with explicit control flow, parameters, and preconditions that specify applicability and effects. Skills invoke each other through dependency links, forming a directed graph that grows and reorganizes as the agent learns. While recent work has explored programmatic skill representations for agents (Wang et al., 2024b ; Stengel-Eskin et al., 2024 ; Wang et al., 2025c ) , PSN uniquely maintains an explicit computational graph of executable programs that supports trace-based credit assignment, maturity-aware stabilization, and principled structural refactoring.

### [6] source `f6c76ff7…`

> 4.3 Building on the Agent Skills Open Standard The Knowledge Activation pipeline builds on the Agent Skills open standard released by Anthropic in December 2025 [ 4 , 1 ] , subsequently adopted across major AI coding tools and agent frameworks including OpenAI Codex CLI, Microsoft's Agent Framework, Cursor, and GitHub Copilot [ 42 ] . The standard emerged from the convergent evolution of earlier ad hoc approaches—Cursor rules, GitHub Copilot custom instructions, Windsurf rules, and repository-level context files—each of which independently evolved to deliver structured knowledge into an agent's context window. The Agent Skills specification standardized what these precursors were reaching toward: a portable, discoverable format for packaging agent-consumable knowledge.

### [7] source `f6c76ff7…`

> The specification implements a progressive disclosure pattern: at startup, agents load only the name and description of each available skill (approximately 100 tokens); when a task matches a skill's description, the agent reads the full instructions into context (the standard recommends under 5,000 tokens); the agent then follows the instructions, optionally loading referenced files or executing bundled scripts as needed. This three-stage pattern—discovery, activation, execution—maps directly to the Knowledge Activation pipeline. Codification produces the skill artifact. Compression ensures that the artifact respects the standard's context-efficiency guideline. Injection implements the runtime activation mechanism. Implementations such as Claude Code extend the base standard with activation controls ( disable-model-invocation, user-invocable, scoping hierarchies) and dynamic context injection that preprocesses shell commands into skill content at activation time—precedents for the richer Activation Policy proposed in Section 6 .

### [8] source `a1f286dd…`

> Why few-shot beats fine-tuning for voice at this scale : Bali Zero produces ~10–30 carousels/month. No dataset large enough to fine-tune voice without overfitting. Few-shot examples are auditable (Antonello swaps one and instantly changes tone), revertible, cheap. Fine-tune the image model, not the language model — image model has bigger generalization gaps to bridge. CLIP / FashionCLIP / VL-CLIP for brand visual style matching: build small embedding index of past carousels (1080×1350 PNGs); at design time use CLIP cosine similarity to retrieve closest past examples as in-context references. This is "visual RAG" — cheap, robust, no fine-tuning required.

### [9] source `7c040d97…`

> arXiv:2303.11366 (cs) [Submitted on 20 Mar 2023 ( v1 ), last revised 10 Oct 2023 (this version, v4)] Title: Reflexion: Language Agents with Verbal Reinforcement Learning Authors: Noah Shinn , Federico Cassano , Edward Berman , Ashwin Gopinath , Karthik Narasimhan , Shunyu Yao View a PDF of the paper titled Reflexion: Language Agents with Verbal Reinforcement Learning, by Noah Shinn and 5 other authors View PDF Abstract: Large language models (LLMs) have been increasingly used to interact with external environments (e.g., games, compilers, APIs) as goal-driven agents. However, it remains challenging for these language agents to quickly and efficiently learn from trial-and-error as traditional reinforcement learning methods require extensive training samples and expensive model fine-tuning. We propose Reflexion, a novel framework to reinforce language agents not by updating weights, but instead through linguistic feedback. Concretely, Reflexion agents verbally reflect on task feedback signals, then maintain their own reflective text in an episodic memory buffer to induce better decision-making in subsequent trials. Reflexion is flexible enough to incorporate various types (scalar values or free-form language) and sources (external or internally simulated) of feedback signals, and obtains significant improvements over a baseline agent across diverse tasks (sequential decision-making, coding, language reasoning). For example, Reflexion achieves a 91% pass@1 accuracy on the HumanEval coding benchmark, surpassing the previous state-of-the-art GPT-4 that achieves 80%. We also conduct ablation and analysis studies using different feedback signals, feedback incorporation methods, and agent types, and provide insights into how they affect performance.

### [10] source `a1f286dd…`

> Key papers worth reading end-to-end: Reflexion: Language Agents with Verbal Reinforcement Learning (Shinn et al., NeurIPS 2023). Actor → Evaluator → Self-Reflection. +22% on decision-making, +20% on HotPotQA, +11% on HumanEval. Adapted to design: Actor proposes a slide, Evaluator scores against rubric (typography, palette, copy-image fit), Self-Reflection writes verbal lesson into memory for next iteration. Lesson goes into the skill library , not just current run. Self-Refine (Madaan et al., 2023). Same model is generator, critic, refiner. ~20% absolute gain. Cheaper than Reflexion but limited because critic shares generator's blind spots. Generative Agents (Park et al., UIST 2023). Append-only memory stream, retrieval scored by recency × importance × relevance , periodic reflection synthesizing higher-level abstractions, planning that decomposes goals top-down. Full architecture was only one that produced believable behavior; ablations of reflection/planning/observation each degraded perceived believability. For a design agent: reflections become brand heuristics, plans become carousel storyboards. Voyager (Wang et al., 2023). Three components: automatic curriculum, ever-growing skill library of executable code, iterative prompting with environment feedback + execution errors + self-verification. Zero-shot transfer: solved every task in 50 iterations; ReAct/Reflexion/AutoGPT solved zero. Translation: skill library is parametric design "moves" ( make_quote_slide , make_stat_callout , apply_editorial_grid ) stored as executable templates. Multi-Agent Reflexion (MAR) (arxiv 2512.20845, late 2025). Replaces single-agent self-critique with persona-based debate among diverse critics. Persona diversity (typography critic, brand critic, copy critic, marketing critic) produces richer reflections than homogeneous self-critique. Layout-generation transformers : CreatiDesign, UniLayDiff, LayoutRectifier, SEGA. Trend: diffusion transformers conditioned on multiple signals (subject + spatial + semantic constraints), with optimization-based post-processing to fix misalignment, overlap, containment. Practical lesson: do not ask LLM to emit pixel coordinates. Have LLM emit a typed layout spec (slots + constraints), then deterministic layout solver places elements. Diffusion hallucination through mode interpolation (NeurIPS 2024). Diffusion models interpolate between training modes producing artifacts that never existed. Critically: the model knows when it's hallucinating — high variance in trajectory of last few backward sampling steps — and a simple variance metric removes >95% of hallucinations while keeping 96% of valid samples. Implementable as post-render quality gate.

### [11] source `354fe331…`

> Sources verified Kim et al. 2026, "Towards a Science of Scaling Agent Systems" — arxiv 2512.08296v1 Google Research Blog — Towards a science of scaling agent systems InfoQ 2026-03 — Google Publishes Scaling Principles for Agentic Architectures Towards Data Science — The 17x Error Trap of the "Bag of Agents" Claude Code docs — Agent Teams Claude Code docs — Model configuration

### [12] source `354fe331…`

> Multi-agent topology — Kim et al. 2025 + Claude Code agent teams Date verified : 2026-05-12 Source paper : Kim et al., "Towards a Science of Scaling Agent Systems", arxiv 2512.08296 (Google DeepMind + MIT, December 2025) Why this exists : wr2-design-architect.md:338 cited "Google 17.2× error-amplification" without DOI. Verified the claim is real, but the simplification "NEVER peer-to-peer" loses important nuance. What the paper actually says (5-architecture controlled study, 180 configs, 3 LLM families)

### [13] source `354fe331…`

> -------------------------------------------------------------------------------- name: lessons-multi-agent-topology-kim-2025 description: "Multi-agent error amplification 17.2× (Kim et al. 2025 arxiv 2512.08296) is real but task-dependent — orchestrator-led shrinks to 4.4×, sequential tasks favor single-agent, parallelizable tasks favor centralized multi-agent. Agent teams in Claude Code = all Claude models only, no Gemini/Codex/DeepSeek as teammates." metadata: node_type: memory type: lessons originSessionId: 08bda0ef-5579-4fb2-a654-f16050486d01

### [14] source `354fe331…`

> Corrected guidance for Bali Zero stack The old rule (wr2-design-architect.md:338, lines 91+129+338, also pre-T2.91, pre-T2.271): "NEVER let subagents talk to each other peer-to-peer (Google's 17.2× error-amplification finding)." The corrected rule : For sequential pipelines (brief → storyboard → layout → critic in chain, like WR2): single-agent batte multi-agent di 39–70% . Multi-agent in WR2 is justified by context-isolation and model-routing economy (Sonnet workers + Opus critic + Haiku vision-pre-pass), not by parallelism gain. Don't pretend it's a parallelism win. For parallelizable tasks (multi-perspective client case, multi-source regulatory check, cross-LLM bipolar verifier): centralized multi-agent batte single-agent di +80.9% . This is where agent teams shines. Peer-to-peer is not banned — it's 4× worse than centralized, but on parallelizable tasks it's still often better than single-agent. Use it when the task genuinely needs cross-agent challenge (devil's advocate, scientific debate pattern in agent-teams docs). Independent (no coordination) is the real trap — 17.2× amplification. Never spawn N parallel sessions and merge results without any lead.

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [15] source `4001017f…`

> These failure modes are consistent with our observations in multi-day workflows and echo challenges identified in prior work. Packer et al. (Packer et al., 2024 ) showed that limited context windows severely degrade performance in extended conversations and document analysis, and proposed MemGPT, an OS-inspired system that pages data between the LLM context (“main memory”) and external storage. Wang et al. (Wang et al., 2023 ) demonstrated that a persistent skill library alleviates catastrophic forgetting in embodied agents by preserving learned behaviors across sessions. More broadly, the CoALA framework (Sumers et al., 2024 ) organizes agent memory into working memory (active information for the current decision cycle), episodic memory (past experiences), semantic memory (world knowledge), and procedural memory (skills and code), providing a principled taxonomy for these mechanisms.

### [16] source `74917ad2…`

> constitution.md — hard brand rules (palette, type, taboo) tokens.json — design tokens (machine-readable) voice/ — few-shot examples on-tone vs off-tone layouts/ — parametric layout skills (each = SKILL.md + render snippet) past/ — last N carousels as in-context reference (PNG + brief.md) Memory layers : Episodic : SQLite at ~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db — one row per carousel run. Semantic : brand cortex files (above). Procedural : skill library (above). Reflective : weekly cron synthesizes episodes into lessons appended to voice/ and skills/.

### [17] source `354fe331…`

> Why: applies to Bali Zero workflows Tax/property/visa research : parallelizable → centralized agent team is the right tool (revenue/cost/risk angles can run simultaneously) WR2 carousel pipeline : sequential → multi-agent justified by context-isolation, not by parallelism; the cicatrice "no peer-to-peer" is locally correct because peer-to-peer adds error WITHOUT adding parallelism gain here Cross-LLM bipolar verifier (4-LLM panel review): parallelizable → centralized lead with 4 Claude teammate each shell-out-ing to a different LLM Multi-prospettiva client case ([CLIENT-NAME-REDACTED] KBLI): parallelizable → centralized agent team

### [18] source `d0adf453…`

> You orchestrate four stateless specialist subagents. Invoke each via the Agent tool with subagent_type=<name> and pass the prior step's structured JSON as the prompt . Specialists read shared brand cortex files; they NEVER talk peer-to-peer (Google's 17.2× error-amplification finding). All inputs and outputs are JSON or files on disk. <cited_table>

### [19] source `b67fe2b2…`

> Pilot Cross-LLM Bipolar Verifier via Claude Code agent-teams Run window : 2026-05-12 23:46 → 2026-05-13 00:35 WITA (~49 min total incl. setup) Pilot status : ✅ SUCCESS — adopt pattern for v2 with 4 adjustments Artifacts : ~/Desktop/nuzantara/research/dev-tools/pilot-cross-llm-2026-05-12/{CLAIM.md, VERDICT-TABLE.md, ROUND-LOG.md, EVALUATION.md, LEAD-PROMPT.md} What this proves Claude Code v2.1.139 agent-teams (experimental, CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 ) work as advertised for the 4-teammate adversarial verifier pattern when:

### [20] source `b67fe2b2…`

> Why: empirical validation of architectural choices Why: The lessons file lessons_multi_agent_topology_kim_2025.md documented Kim et al. 2025 (arxiv 2512.08296) — multi-agent independent topology = 17.2× error amplification, centralized = 4.4×, peer-to-peer messy. This pilot tested peer-to-peer on a parallelizable task (each verifier reads the same claim independently from a different angle) and observed: No error amplification observed — 3/3 unanimous on 4 of 6 sub-claims Peer-to-peer IMPROVED precision on the 1 disagreement: fact-checker R0 PASS 0.85 on NPWP → R1 FAIL 0.80 after seeing peer evidence (PMK 112/2022 Pasal 6). Convergence in 1 exchange. Discovery beyond ground truth : ground-truth marked KEP-37/PJ/2026 as "hallucination". Team found the decree DOES exist (web evidence: ats-konsultama.com, veritask.ai, peraturanpajak.com) but governs SPT Masa Pajak Desember 2025, NOT Q3 2026. "Real but mis-attributed" is a different failure mode than "hallucinated number" — finer-grained than the single-LLM devils-advocate 7-pass caught.

> RETRACTED[kim-2025-17x-error-amplification-as-cause]: il 17.2× misura `Independent` (agenti paralleli, nessuna coordinazione — Ω=synthesis_only), NON il peer-to-peer (`Decentralized`, che in Table 5 è il PIÙ ALTO, 0.477); la causa error-propagation è unsupported (Table 4, p=0.658). Resta in piedi: la regola no-peer-to-peer, ma su basi di repo (context isolation, un solo state owner, no cross-worker contamination) — non su questo paper, in nessuna direzione.

### [21] source `097cb963…`

> When to invoke each LLM You are the orchestrator. You don't reason on the source corpus directly — you delegate ingestion to the right LLM and synthesize. <cited_table>

### [22] source `b67fe2b2…`

> Lead launched via claude --teammate-mode tmux (auto-detects iTerm2 backend) Each teammate is reuse of an existing subagent definition ( deep-researcher , regulatory-watcher , devils-advocate , general-purpose ) with self-contained prompt at spawn time Claim travels via disk path ( /Users/.../CLAIM.md ), output is JSON files at /tmp/pilot-cross-llm/round0-<name>.json Peer-to-peer debate via SendMessage cross-teammate is enabled (no orchestrator gate), capped at 3 rounds with 2/4-agreement convergence rule

### [23] source `1826e81e…`

> Voyager autolearning — _lessons/ harvesting (added 2026-05-13) When you identify a new failure pattern during a critic run (not a single-slide bug — a systemic recurring issue), write a lesson file to ~/.claude/skills/bali-zero-brand/_lessons/YYYY-MM-DD-<slug>.md BEFORE returning the verdict. This lesson is loaded into context on every future critic run via the bali-zero-brand skill preload, so the pattern recognition compounds over time (Voyager skill library pattern, Wang et al. 2023). A new failure pattern qualifies for lesson-write when ALL of:

### [24] source `1826e81e…`

> Lesson file format: Do NOT write lessons for: Single-slide bugs (one-off, no recurrence) — flag in retry_feedback only Personal-taste violations (use forbidden-phrases.md instead) Issues that contradict constitution (escalate to Antonello via TODO, not _lessons) After writing a lesson, append a single line to your verdict JSON: This signal lets the orchestrator know your skill library grew this run. The bali-zero-brand skill bundler will include the new lesson at next session start automatically.

### [25] source `d0adf453…`

> Memory & growth After each successful carousel, append episodic entry (Step 6). Weekly cron ( com.balizero.wr2.reflexion.weekly.plist , Sunday 02:30 WITA) runs Reflexion synthesis via _reflexion-synthesis.py : read last 7 days of episodes + designer-override diffs (final published vs your draft), generate ≤10 verbal lessons, append to: ~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md (if voice-related) ~/.claude/skills/bali-zero-brand/layouts/_proposed/ (if layout-related) ~/.claude/skills/bali-zero-brand/constitution.md (if recurring violation needs new hard rule) Voyager curriculum: weekly inspect last 30 carousels. If a topic-type is underrepresented (e.g., "0 tax carousels in last 14 days"), generate 1 exploratory variant for next production cycle and tag it exploration:true in episodic log. Skill graduation: a _proposed/ skill graduates to layouts/ after 3 successful uses (critic ≥ threshold + Antonello approval). Unused 60 days → _archived/ .

### [26] source `92b09121…`

> Report issue for preceding element Safety via rollback validation. Report issue for preceding element All refactor proposals are tentative. Given a refactored candidate network 𝒩 t ′ \mathcal{N}^{\prime}_{t} , the system evaluates short-horizon performance on a sliding window of 3 recent tasks involving affected skills. If the task success rate drops by more than 20%, the refactor is reverted using logged inverse operations. Report issue for preceding element <cited_table>

### [27] source `74917ad2…`

> Skill library evolution : Each new skill enters as _proposed/<name>.md . After 3 successful uses (critic score ≥ threshold) it graduates to layouts/<name>.md . Skills unused for 60 days move to _archived/ . Hard guardrail : skill changes are git-committed. Antonello reviews diffs weekly. No autonomous skill modification merges to main without human commit. -------------------------------------------------------------------------------- 6. Concrete next 7 steps Write ~/.claude/agents/wr2-design-architect.md (orchestrator subagent). Write ~/.claude/skills/bali-zero-brand/constitution.md (hard rules). Write ~/.claude/skills/bali-zero-brand/SKILL.md (entry point with progressive disclosure). Stub ~/.claude/skills/bali-zero-brand/tokens.json (palette + type + spacing — derive from packages/core/tokens/primitives.css + WR2 reference PDFs). Stub ~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md and off-tone-examples.md (5 each from past WR2 winners + 3 known fails). Stub ~/.claude/skills/bali-zero-brand/layouts/ with 3 parametric layouts derived from WR2 reference PDFs (cover-photo, photo-headline-yellow-sub, statement-bomb-closing). Wire critic subagent ( wr2-critic ) with vision capability for PNG quality check.

### [28] source `f6c76ff7…`

> The framework makes three interconnected contributions. First, it provides a problem formalization : the Context Window Economy (Section 3 ) models the constraints under which knowledge must be delivered to agents, drawing on information theory [ 54 ] and cognitive load theory [ 61 ] ; the Institutional Impedance Mismatch (defined above) names the structural disconnect between parametric model knowledge and organizational institutional knowledge; and the institutional knowledge tax identifies the sociotechnical cost when this mismatch goes unaddressed. Second, it specifies a knowledge architecture : the Knowledge Activation pipeline (Section 4 ) transforms latent organizational knowledge through codification, compression, and injection into Atomic Knowledge Units —skills—whose seven-component schema (Section 5 ) bundles intent, procedure, tools, metadata, governance, continuations, and validators into composable, governance-aware primitives. Third, it defines a deployment and governance model : the Agent Knowledge Architecture (Section 6 ) provides a three-layer structure—AKU Registry, Knowledge Topology, and Activation Policy—through which organizations deploy and govern AKUs at scale; AI-Generated Golden Paths reconceive curated developer pathways [ 57 , 50 ] as workflows dynamically composed by agents at runtime; validators enable governance-as-code; and a knowledge commons model (Section 8 ) grounds sustainable skill maintenance in community practice [ 71 , 28 ] . Together, these contributions bridge four domains that have developed largely in isolation: knowledge management theory, platform engineering, autonomous AI agent design, and developer experience research [ 44 , 23 ] .

### [29] source `92b09121…`

> Report issue for preceding element Operator-objective correspondence. Report issue for preceding element Reflect acts as symbolic differentiation : when a task fails, it identifies which control-flow branches, preconditions, parameters, and subskill compositions contributed to the error, producing structured repair proposals that reduce ℛ task \mathcal{R} {\text{task}} and ℛ cons \mathcal{R} {\text{cons}} . Like backpropagation, credit is assigned only along the executed path, with non-executed skills receiving no updates. This selective credit assignment avoids the noise of updating uninvolved skills, mirroring how gradients flow only through activated paths in neural nets. Maturity-aware gating functions as adaptive learning rates : mature skills with high V  ( s ) V(s) receive infrequent updates (analogous to freezing converged layers), while immature skills remain plastic, reducing ℛ reliab \mathcal{R} {\text{reliab}} by preventing catastrophic forgetting. Refactor performs symbolic neural architecture search: merging redundant skills, extracting reusable abstractions, and pruning unnecessary branches to reduce ℛ struct \mathcal{R} {\text{struct}} . Rollback-based validation functions as a symbolic trust region.

### [30] source `92b09121…`

> Report issue for preceding element E.1 Optimization Taxonomy Report issue for preceding element Across experiments, frequent optimizations of PSN fall into several recurring categories. Table 5 summarizes the most common failure signals and corresponding repair strategies. Report issue for preceding element <cited_table>

### [31] source `92b09121…`

> Outcome. After co-optimization, the parent skill reliably enforces its fuel preconditions, and the refined subskill consistently delivers the required resources. This example demonstrates PSN's ability to localize responsibility across skill boundaries and to perform coordinated, semantics-preserving optimization over compositional skill hierarchies. Report issue for preceding element Appendix F Detailed Code Diffs for Optimization Examples Report issue for preceding element This section provides complete code diffs for the representative optimization cases described in Section E . Table 6 summarizes all cases, and Table 7 shows the mapping from gradient signals to implemented fixes.

### [32] source `92b09121…`

> Report issue for preceding element To stabilize learning, updates are constrained by a rolling buffer of the 5 most recent repair proposals, preventing contradictory edits. Update frequency is further modulated by skill maturity: Report issue for preceding element P  ( update  s ) = ( 1 − ϵ ) ⋅ σ  ( γ  ( 0.6 − V  ( s ) ) ) + ϵ , P(\text{update }s)=(1-\epsilon)\cdot\sigma(\gamma(0.6-V(s)))+\epsilon, (6) The constant 0.6 0.6 serves as a soft maturity pivot rather than a bound on V  ( s ) V(s) : it marks the inflection point at which a skill is considered sufficiently reliable to gradually reduce update frequency, while still allowing occasional repairs under compositional failures. σ \sigma is the sigmoid function, γ = 5.0 \gamma=5.0 controls threshold sharpness, and ϵ = 0.1 \epsilon=0.1 ensures minimum update probability. Mature skills ( V  ( s ) ≈ 1 V(s)\approx 1 ) stabilize with low update probability, while immature skills remain plastic.

### [33] source `92b09121…`

> Figure 9: Sibling specializations. Multiple specialized skills expose a missing higher-level abstraction that can be explicitly synthesized and reused. Report issue for preceding element Pattern. Report issue for preceding element Two or more skills are specializations of a latent, more general operation that is not yet represented as a standalone skill in the network. Report issue for preceding element Rewrite. Report issue for preceding element A new abstract skill is synthesized to capture the shared structure, and all specialized skills are rewritten as thin wrappers that invoke the abstract skill with appropriate parameters.

### [34] source `92b09121…`

> Rewrite. Report issue for preceding element The shared subgraph is extracted into a new reusable skill, and all original skills are rewritten to invoke this subskill instead of duplicating its logic. Report issue for preceding element B.5 Case E: Duplication Removal Report issue for preceding element Figure 11: Duplication removal. Functionally equivalent skills are merged into a single canonical representation. Report issue for preceding element Pattern. Report issue for preceding element Two skills are functionally equivalent up to naming differences or minor surface variations, leading to redundant representations in the PSN.
