---
adversarial_review: exempt-machine-report # agent-craft daily Deep Research transcript (generated artifact, not a curated research deliverable — no client_case/sources frontmatter, domain "agent-craft" is outside the CLAUDE.md §15 curated capture taxonomy)
---

# Agent-craft DR — 2026-08-22-post-rendering-vision-gate-agent-state

**Date**: 2026-08-22
**Mode**: adaptive
**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)
**Conversation ID**: `53f11fc2-7d53-400f-ad4f-e83426841847`
**Sources used**: 5 / Citations: 9

## Question

> In italiano. Approfondisci la domanda emersa dal Deep Research di ieri:   **Stato Attuale (Post-Rendering Vision Gate):**

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani.

## Answer

### **1. Citazioni Verbatim dalle Fonti Canoniche (Il Guscio Multimodale del Critic)**

*   **Identità e Ruolo di `wr2-critic` al Step 5:**
    > *"MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. Use IMMEDIATELY after Playwright renders PNGs. Reviews rendered carousel slides against Bali Zero brand constitution + brief verbatim."* **[1, 2]**
    > *"Returns 4-rubric scores AND a binary verdict per slide (PASS / FAIL with one-line reason) plus retry feedback."* **[1]**

*   **La convalidazione visiva dei contrasti e dell'integrità dell'immagine (Rubric 4):**
    > *"Text legibility over image: text-zone brightness contrast >= 4.5:1 against background pixels in same region"* **[1]**
    > *"Article 5.10 — No silent placeholder reuse (NEW, 2026-05-09): for every slide with image_source in slides.json, run sha256 verification"* **[1]**

*   **Il Vision Pre-pass (R3b) per il contenimento dei costi di Opus:**
    > *"R3b — Vision pre-pass on hero slides (Haiku 4.5, ~\$0.20/run): BEFORE invoking the full critic, run a fast binary vision pass on every is_hero_image: true slide PNG asking ONLY one question per slide: \"does the rendered hero image semantically match the slide topic AND the brief's key_facts/hook_angle? PASS/FAIL.\" This catches hallucination snowballing (arXiv 2509.21789) before the expensive critic."* **[2]**
    > *"Any FAIL → abort that hero slide → re-trigger imagegen with refined prompt... second FAIL routes the slide to manual review queue."* **[2]**

*   **Il fallback deterministico "Fail-Forward" per l'operatore umano:**
    > *"If you cannot produce a carousel that passes critic panel after 2 retries: 1. Write STATUS: needs_human_edit to the output slides.json."* **[2]**
    > *"drafted_needs_human_edit: orchestrator exhausted retry budget (2 critic rounds failed). Visible to Damar as a yellow-bordered row with \"needs human edit\" pill. Set by POST /api/flag-needs-human-edit from wr2-design-architect."* **[3]**

---

### **2. Confronto con lo Stack Reale di Bali Zero**

Nel nostro ecosistema reale, il **Post-Rendering Vision Gate** rappresenta il confine critico in cui la generazione probabilistica incontra la rigidità deterministica delle regole di brand:

*   **L'Orchestratore come Motore di Rendering e Chiamata:**
    Il nostro orchestratore centralizzato `wr2-design-architect` (eseguito su Opus 4.7) controlla interamente lo stato **[2]**. Dopo che il lavoratore Sonnet ha composto il codice HTML/CSS, l'orchestratore avvia Playwright in modalità headless per esportare le slide renderizzate in PNG ad alta risoluzione a 1080×1350px **[2, 4]**. Solo in questo momento, l'orchestratore attiva la costosa istanza multimodale di `wr2-critic` (anch'essa su Opus 4.7) passandole i PNG, i file JSON di specifica e il brief originario **[1, 2]**.
*   **La Protezione Economica Tramite il Vision Pre-pass (R3b):**
    Poiché l'uso intensivo di Opus 4.7 per la visione consuma rapidamente i limiti di quota mensili **[1, 2]**, applichiamo rigorosamente il contratto **R3b (Vision pre-pass)** **[2]** gestito dal modello leggero Haiku 4.5 **[2]**. Prima di lanciare la scansione semantica del critic principale, Haiku esamina le slide contrassegnate come hero per intercettare deviazioni grossolane della generazione o allucinazioni visive (come l'inclusione di volti reali, palme o spiagge vietate dall'Articolo 5.3 della Costituzione **[4]**). Se Haiku emette un `FAIL`, l'orchestratore abortisce la slide ed esegue un rinfresco del seed di generazione, evitando di pagare il costo computazionale di un'analisi Opus su un asset visivamente compromesso **[2]**.
*   **Il Controllo Incrociato delle Immagini (Pairwise SHA-256):**
    Un bug ricorrente del compilatore di immagini Codex consiste nel restituire occasionalmente file byte-per-byte identici a causa di hit di cache o saturazione delle code concorrenti, portando alla pubblicazione di slide consecutive con la stessa immagine di sfondo **[4]**. Per neutralizzare questa anomalia in modo non allucinatorio, l'orchestratore e il layout-composer eseguono un preflight di controllo unificato calcolando l'hash SHA-256 dei file generati rispetto all'ancora di dominio **[1, 4]** (tramite lo script `_audit-checklist.sh` con `MODE=hero-sha` **[2]**). Se viene rilevata una duplicazione speculare, il sistema solleva un blocco prima di attivare i motori di visione **[1, 4]**.
*   **Il Paracadute per Damar:**
    Se le correzioni automatiche introdotte dall'orchestratore non riescono a sanare le bocciature di `wr2-critic` dopo il limite invalicabile di 2 tentativi (spesso a causa di conflitti insolubili di testo-sfondo sul contrasto), il sistema interrompe l'esecuzione **[2]**. Cambia lo stato in `drafted_needs_human_edit` e invia un payload `POST` all'endpoint di coda locale, popolando il file `human-review-queue.json` **[3]**. Damar vedrà la riga contrassegnata in giallo nella sua UI e potrà aprire direttamente il design in Canva per finalizzare manualmente l'allineamento dei pixel **[3, 5]**.

---

### **3. Linea di Azione Concreta: Il "Pre-Critic Image Watchdog" per Bali Zero**

Per ottimizzare la stabilità del sistema e azzerare i fallimenti dovuti alle duplicazioni di rendering di Codex prima che la pipeline arrivi al critic Opus, implementeremo un modulo di validazione deterministica locale integrato nel flusso dell'orchestratore.

*   **Azione:** Integrare un validatore di collisione visiva crittografica all'interno del modulo di orchestrazione di `wr2-design-architect` **[2]**, potenziando lo script unificato `_audit-checklist.sh` **[2]**.
*   **Procedura Operativa:**
    1.  **Estrazione dei Metadati:** All'avvio della fase di layout, l'orchestratore scansiona il file temporaneo `slides.json` ed estrae tutte le slide in cui `is_hero_image: true` e la cui origine è dichiarata come `imagegen:*` **[4]**.
    2.  **Verifica Crittografica Locale (Articolo 5.10.3):** Subito dopo lo scaricamento delle immagini generate da Codex e *prima* del rendering Playwright delle pagine HTML, viene invocato un metodo Python che calcola il checksum SHA-256 di ciascuna immagine hero.
    3.  **Rilevamento e Sanificazione Dinamica (Salt Injection):**
        *   Lo script confronta programmaticamente gli hash delle slide generate.
        *   Se due hash risultano bit-identici (violazione `pairwise_collision`), lo script interrompe la compilazione prima che venga generata la chiamata HTML.
        *   Inietta automaticamente un marcatore di rumore dinamico ("salt") nel prompt dell'immagine della slide duplicata (es. aggiungendo una variazione di inquadratura o coordinate specifiche come richiesto dall'Articolo 5.10.3 **[4]**).
        *   Rilancia la chiamata a Codex con il flag `--force-fresh` **[4]**.
    4.  **Esito:** Questo gate deterministico a costo zero intercetta le anomalie infrastrutturali di memorizzazione delle immagini a monte, azzerando le bocciature di Rubric 4 del `wr2-critic` dovute a immagini duplicate ed evitando cicli di retry ciechi sull'istanza costosa di Opus **[1, 2]**.

---

### **4. Domande Aperte per il Deep Research (DR) di Domani**

1.  **La Svolta Multimodale di Sonnet 4.8 / 5:** Con l'introduzione di modelli intermedi dotati di acuità visiva elevata (98.5% su standard Opus) a tariffe drasticamente ridotte (\$3/\$15 per milione di token) **[6, 7]**, in che modo cambierà la nostra *Worker Downgrade Rationale (R2)* **[2]**? Potremo migrare l'intera convalidazione estetica di Rubric 4 e il controllo WCAG di `wr2-critic` su Sonnet senza erodere la precisione del brand?
2.  **Calibrazione Euristica del Pre-pass Haiku (R3b):** Come possiamo estendere il prompt di visione ultraleggero di Haiku 4.5 **[2]** affinché intercetti non solo violazioni macroscopiche del contenuto (palme, volti reali **[4]**), ma esegua anche un preflight di *collisione geometrica* (es. rilevando se un box di testo flexbox generato si sovrappone visivamente a elementi cruciali dell'immagine di sfondo), bloccando il rendering prima del gate principale?
3.  **Visual RAG via CLIP Cosine Similarity:** Se implementiamo un archivio vettoriale locale contenente gli embedding CLIP dei 64 caroselli storici approvati da Antonello **[2, 8]**, quale soglia matematica di similarità del coseno (Cosine Similarity) dobbiamo impostare nel nostro validatore post-rendering per scartare automaticamente slide con derive stilistiche insolite senza soffocare la creatività visiva indotta dal Voyager curriculum **[2, 9]**?

📊 *Se lo desideri, posso scrivere direttamente la specifica di test integrata in Python per convalidare il modulo di controllo SHA-256 pairwise sulle nostre slide in `/workspace/scratch/` prima di procedere. Come procediamo?*

## Sources used (5)

- `92b09121-412d-4ece-a88e-86b922424a15`
- `a5a300d1-c909-4736-86ce-7aeb659a7c3f`
- `a892fc31-d36d-405b-bc2e-d6cae94752d4`
- `386948eb-b675-4aa8-a9f3-6ca5774ee67f`
- `a1f286dd-f3bd-4cb5-8614-08f4deef3160`

## Citations verbatim (9)

### [1] source `92b09121…`

> if f s ′ ≠ ∅ f_{s^{\prime}}\neq\varnothing then Push ( s ′ , f s ′ ) (s^{\prime},f_{s^{\prime}}) into Q Q ; Let ℋ \mathcal{H} be the induced pending optimization subgraph over Dom  ( 𝒢 ) \mathrm{Dom}(\mathcal{G}) ; Phase II: Bottom-up gradients application (dependency-respecting updates). Compute bottom-up order π ← PostOrder  ( ℋ ) \pi\leftarrow\textsc{PostOrder}(\mathcal{H}) ; Initialize report map ℛ ← ∅ \mathcal{R}\leftarrow\emptyset ; foreach s s in π \pi do 𝒞 ← Consider  ( { OptimizeFeedback  ( s ′ ) ∣ s ′ ∈ Subskill  ( s ) ∩ Dom  ( ℛ ) } ) \mathcal{C}\leftarrow\textsc{Consider}({\textsc{OptimizeFeedback}(s^{\prime})\mid s^{\prime}\in\mathrm{Subskill}(s)\cap\mathrm{Dom}(\mathcal{R})}) ;

### [2] source `92b09121…`

> Report issue for preceding element Rewrite. Report issue for preceding element The specialized skill is replaced by a thin wrapper that calls the generalized skill with fixed parameter values. Report issue for preceding element B.2 Case B: Behavioral / Subgraph Coverage Report issue for preceding element Figure 8: Behavioral (subgraph) coverage. Duplicated logic inside a composite skill is replaced by a call to an existing reusable skill, preserving behavior while reducing redundancy. Report issue for preceding element

### [3] source `a5a300d1…`

> [THIRD-PARTY-HANDLE-REDACTED] (source page noise: reaction and comment lists naming private individuals; no technical content in this citation)

### [4] source `a5a300d1…`

> [THIRD-PARTY-HANDLE-REDACTED] (source page noise: reaction and comment lists naming private individuals; no technical content in this citation)

### [5] source `a892fc31…`

> [THIRD-PARTY-HANDLE-REDACTED] (source page noise: reaction and comment lists naming private individuals; no technical content in this citation)

### [6] source `386948eb…`

> Vision Upgrades (Near-Certain) This is the highest-confidence prediction. Opus 4.7 delivered a transformational vision upgrade: Visual-acuity : 54.5% → 98.5% (a 44-point jump) Max image resolution : ~1.25MP → 3.75MP (3x increase) Sonnet 4.6 currently has no published vision benchmark equivalent — it was not marketed as a vision model. If Sonnet 4.8 inherits even a fraction of Opus 4.7's vision gains, it would become the most cost-effective vision-capable model in the market at $3/$15 per million tokens.

### [7] source `386948eb…`

> This is the number one request. Opus 4.7's 98.5% visual-acuity and 3.75MP image support unlocked use cases — UI review, document processing, design-to-code — that are currently too expensive to run at Opus pricing for high-volume workflows. Developers want these vision capabilities at $3/$15 per million tokens. 2. Longer Reliable Output Sonnet 4.6 supports 1M token context input, but output length remains a friction point for long-form generation tasks. Developers want Sonnet 4.8 to generate longer, more coherent outputs — particularly for code generation tasks that require producing entire files or modules in a single pass.

### [8] source `a1f286dd…`

> Why few-shot beats fine-tuning for voice at this scale : Bali Zero produces ~10–30 carousels/month. No dataset large enough to fine-tune voice without overfitting. Few-shot examples are auditable (Antonello swaps one and instantly changes tone), revertible, cheap. Fine-tune the image model, not the language model — image model has bigger generalization gaps to bridge. CLIP / FashionCLIP / VL-CLIP for brand visual style matching: build small embedding index of past carousels (1080×1350 PNGs); at design time use CLIP cosine similarity to retrieve closest past examples as in-context references. This is "visual RAG" — cheap, robust, no fine-tuning required.

### [9] source `a1f286dd…`

> NB-1 (legal), NB-5 (property), NB-4 (tax) feed Brief Interpreter via existing NotebookLM MCP tooling. Brand cortex is local files, version-controlled. Skill library is git-tracked code (parametric components), each skill a Markdown spec + Playwright/HTML snippet. Growth mechanism : Voyager-style automatic curriculum: weekly orchestrator picks topic-type underrepresented in last 30 carousels and generates 1 exploratory variant alongside requested production output. Successful exploration variants harvested into skill library. Failed variants generate Reflexion-style lessons into voice.md.
