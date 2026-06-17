---
date: 2026-06-08
domain: operations
client_case: none
sources:
  - deep-research harness (23 fonti fetchate, 107 claim estratti, 25 verificati avversarialmente voto 3-su-3, 6 uccisi) 2026-06-08 — run wf_4a6766ac-8f4
  - Storybook MCP docs primary (storybook.js.org/docs/ai/mcp/overview + github.com/storybookjs/mcp)
  - Figma Dev Mode MCP docs primary (figma.com/blog/introducing-figma-mcp-server + developers.figma.com/docs/figma-mcp-server)
  - yajihum/design-system-mcp (github primary, token-JSON pattern)
  - Atlassian @atlaskit/ads-mcp (npm registry primary + engineering blog)
  - bolt.diy (github.com/stackblitz-labs/bolt.diy primary, MIT + FAQ)
status: VERIFICATO — chiude il buco #2 (design/internal-app) di GROUND-A, l'unico rimasto NON-VERIFICATO dal harness originale (cfr. 2026-06-06-sota-agentic-dev-workflow.md §2.2)
---

# GROUND-A buco #2 — Design / internal-app dentro il brand (VERIFICATO)

> **Perché esiste questo file.** Il deep-research originale del 2026-06-06 (`2026-06-06-sota-agentic-dev-workflow.md`)
> produsse **ZERO claim sopravvissuti** sull'area design-generation: §2.2 fu marcata **NON VERIFICATO**, con
> solo LEAD grezzi (Storybook MCP, Figma Dev Mode MCP). Il verdetto degli eserciti (`2026-06-07-sota-9-spec-armies-verdict.md`)
> e i NEXT del doc madre (riga 404) lo nominano **«l'unico rimasto non-verificato dal harness»**. Questo è il
> pass di ricerca dedicato richiesto. Gli altri 2 buchi GROUND-A NON richiedevano ricerca: #1 (container-test)
> è già verificato 3-0 (microsandbox HVF) con residuo *empirico* (spike boot-time, NEXT #1); #3 (stato-prodotto
> commerciale) è già verificato 3-0 (scaffold>modello, OpenHands ~66%, 8 leaderboard refutati).

## 0. La domanda

Come fa l'avanguardia dei coding-agent (2026) a generare UI / internal-tooling **dentro** un design-system
esistente **senza allucinare componenti**, per un solo-dev local-first su Apple Silicon che già possiede
`tokens.json` (WCAG-AAA, Montserrat, "Legibility Armor") + renderer HTML/CSS→PNG via Playwright + componenti
React in `packages/`, con vincolo **niente Anthropic API a pagamento (solo Claude CLI MAX)** e **sovranità dati
(UU PDP)**?

## 1. La risposta in una frase

Il pattern **«2-MCP» (intent-source + component-source) è REALE e documentato in produzione nel 2026**, ma
**solo la metà component-source soddisfa il vincolo local-first/sovranità**. Per Nuzantara il path verificato è:
**esporre il `tokens.json` + i componenti `packages/` esistenti come un MCP custom locale** (Storybook-MCP per
i componenti, sul TUO dev server + un MCP su token-JSON), far interrogare quello dalla Claude CLI **prima** di
generare, e **tenere un layer di verifica/lint separato e tuo** — perché **nessun MCP esaminato impone
conformità: forniscono solo ground-truth, non la verificano**.

## 2. FATTI-VERIFICATI (voto 3-0, primary-source)

### 2.1 Storybook MCP — il primitivo genuinamente local-first ✅
- **`@storybook/mcp` / `@storybook/addon-mcp`** (ultima `@storybook/mcp@0.7.0`, 2026-04-14), org ufficiale
  `storybookjs`, install `npx storybook add @storybook/addon-mcp`. Gira **DENTRO** il dev server Storybook su
  `http://localhost:6006/mcp`, **zero dipendenze esterne** (serve solo Node 24+/pnpm).
- Espone 3 tool docs-toolset: `list-all-documentation`, `get-documentation` (props + prime 3 stories di un
  componente), `get-documentation-for-story`. La doc istruisce: **interroga l'MCP per una prop prima di usarla**
  su un componente del design-system.
- **Sovranità**: il SERVER è genuinamente locale/offline. L'inferenza no — i metadata vanno comunque all'endpoint
  LLM dell'agente. **Claude CLI MAX è OK** (è il path MAX-plan sanzionato, NON un endpoint PII di terze parti).
- ⚠️ Sub-claim REFUTATO 1-2: «la doc *vieta esplicitamente* di allucinare» è overreach sul wording. La sostanza
  verificata è che **i tool esistono e forniscono props/stories reali**, non che il testo proibisca alcunché.

Fonti: `storybook.js.org/docs/ai/mcp/overview`, `github.com/storybookjs/mcp`

### 2.2 design-system-as-MCP su token-JSON — il blueprint esatto per il nostro tokens.json ✅
- **`yajihum/design-system-mcp`** espone esattamente 2 tool: **`getTokens`** (legge JSON di design-token locali:
  `color.json`/`typography.json`/`spacing.json`/`radius.json` via **Style Dictionary**) + **`getComponentProps`**.
  Built su Deno, **file-based, nessuna dipendenza cloud** → soddisfa local-first/sovranità.
- ⚠️ **CAVEAT**: progetto demo-scale (~6 commit, ~25 star). **PROVA** che il pattern è implementabile (≥1 volta),
  NON che esista tooling di produzione maturo. **Per Nuzantara è il blueprint architetturale da copiare** —
  esporre `tokens.json` + props dei componenti `packages/` via un MCP locale custom — non un prodotto off-the-shelf.

Fonte: `github.com/yajihum/design-system-mcp`

### 2.3 Atlassian @atlaskit/ads-mcp — prova-di-produzione del 2-MCP completo ✅
- **`npx -y @atlaskit/ads-mcp`** (nome npm confermato via registry, publisher `atlassianartifactteam`, 78 versioni,
  ultima 0.21.1, bin `ads-mcp`). Espone componenti/token/icone/a11y dell'Atlassian Design System.
- Il blog Atlassian documenta il workflow **2-MCP esatto**: **Figma Desktop MCP** (`get_design_context` + `get_screenshot`)
  = **intent-source**; **ADS MCP** (`ads_plan`) = **component/token-source**. È l'existence-proof che il pattern
  intent+component gira in produzione.
- ⚠️ **CAVEAT**: espone il design-system *di Atlassian* → è un **TEMPLATE di come pacchettizzare il proprio**, non
  un modo di puntare a un sistema arbitrario esterno. Il sub-claim "ALL components" è marketing; l'outcome-claim
  (la demo 20-min produsse token reali invece di hex) è stato **REFUTATO 0-3** (promozionale, non verificato indip.).

Fonti: `atlassian.com/blog/development/redesigning-homepage-20-minutes-with-rovo-dev`, `registry.npmjs.org/@atlaskit/ads-mcp`

### 2.4 Figma Dev Mode MCP — REALE ma NON adatto al vincolo UU-PDP ✅ (esistenza) / ❌ (sovranità)
- Esiste, ufficiale (beta giugno 2025), gira in Cursor/Copilot/Windsurf/Claude Code. Espone `get_design_context`,
  `get_variable_defs` (token: colori/spacing/typography), `get_screenshot` (18 tool totali). Variante desktop su
  `http://127.0.0.1:3845/mcp`.
- **`Code Connect`** (3-0 sul meccanismo condizionale): mappa un componente Figma al path-file di codice esatto e
  ne espone la sintassi → l'agente **importa componenti reali** invece di duplicarli. Funziona **SE** le mapping
  esistono. Bug documentati: `get_design_context` ritorna token base-component (non variant), remote ritorna `{}`,
  gap Angular/non-React, cap 25k-token.
- ⚠️ **CAVEAT CRITICO**: il processo ascolta su localhost, ma il **file di design è SaaS cloud** con login richiesto;
  Figma ora **«raccomanda fortemente» il server REMOTO** (`mcp.figma.com/mcp`). **4 sub-claim "è local/offline"
  REFUTATI 0-3.** Figma MCP è cloud-coupled + gated dietro seat Dev/Full a pagamento → **escluso dallo stack sovrano**.

Fonti: `figma.com/blog/introducing-figma-mcp-server`, `developers.figma.com/docs/figma-mcp-server/tools-and-prompts`

### 2.5 bolt.diy — l'unico self-hostable dei tre, ma non brand-aware out-of-box ✅
- **MIT, self-hostable**, gira con LLM locali (Ollama `127.0.0.1:11434`, LM Studio) → soddisfa sovranità dati.
- ⚠️ **NEGATIVI critici**: (1) la doc bolt.diy **non menziona** design-system custom / token / awareness non-ShadCN
  (solo template "Next.js + shadcn/ui"); i "Design System Agents" stanno nel **commerciale bolt.NEW**. (2) FAQ:
  modelli <7b «mancano la capacità di interagire con bolt» → brand-aware locale NON è path verificato di qualità.
  (3) WebContainers API richiede licenza commerciale separata per produzione for-profit (self-host solo-dev/internal
  rientra nell'esenzione). **v0 e Lovable NON sono self-hostable.**

Fonti: `github.com/stackblitz-labs/bolt.diy`, `github.com/stackblitz-labs/bolt.diy/blob/main/FAQ.md`

## 3. RISULTATO NEGATIVO IMPORTANTE — il gap di conformità (3-0)

> **Un MCP token/prop è un DATA-PROVIDER, non un CONFORMANCE-ENFORCER.**

`design-system-mcp` ha **zero menzioni** di conformance-checking, verifica dell'output, linting o validazione.
La conformità vive in *altri* tool (Figma Code Connect, Storybook), non nell'MCP token-JSON. **Conseguenza pratica
per il solo-dev**: esporre i token via MCP **riduce l'allucinazione fornendo ground-truth**, ma **devi aggiungere
il TUO step di verifica/lint** — nessun MCP esaminato garantisce che il codice generato sia brand-conforme.

Primitivi di verifica candidati (da decidere, vedi §6):
- **CSS-var allowlist** — il codice generato può usare solo le variabili nel `tokens.json`.
- **token-usage linter** — flag su hex hardcoded / valori fuori-palette.
- **visual-regression contro il renderer Playwright→PNG esistente** — confronto pixel col brand atteso.

## 4. sub-domanda (4) — ✅ CHIUSA il 2026-06-09 (era APERTA): PARTIAL-YES

«**view-over-app / generated-not-maintained**» (UI rigenerata on-demand dal design-system invece che mantenuta a
mano). Il 2026-06-08 era **ZERO evidenza sopravvissuta** (claim blog/marketing: getindigo.ai, ink&switch,
geoffreylitt, A2UI Google) → registrato come open-question.

**Chiuso dal pass dedicato 2026-06-09** (deep-research run wf_1168ba50-a79: 20 fonti, 90 claim, 20 confermati / 5
uccisi). **Esito: PARTIAL → YES.** Il pattern È reale come **primitivo self-hostable local-first** — ma NON come
prodotto turnkey. Sopravvivono 2 primitivi nuovi LLM-vincolato-a-catalogo (**json-render** Vercel Labs Apache-2.0;
**OpenUI Lang** thesys MIT, gira local via Ollama) + lo schema-driven deterministico maturo (RJSF, Windmill
auto-UI). **3-0 REFUTATO** il sospetto del 08-06: il canone malleable-software (Ink&Switch Patchwork) è
research-prototyping per ammissione degli autori, NON produzione. Il catalogo Zod vincolante = lo stesso "layer
di conformità proprio" del §2, **incorporato nel render**. Dettaglio completo + 6 finding citati:
**`2026-06-09-ground-a-buco2-subq4-view-over-app.md`**.

## 5. CHECKLIST — primitivi local-first adottabili (ordine di leva)

- [ ] 🟢 **Storybook MCP** (`@storybook/addon-mcp`) sul dev server dei componenti `packages/` → l'agente interroga
      props/stories REALI prima di generare. **Genuinamente locale.** Leva più alta, costo più basso.
- [ ] 🟢 **MCP custom su token-JSON** (pattern `yajihum/design-system-mcp`): esporre `tokens.json` via `getTokens`
      + `getComponentProps`. Da **costruire** (blueprint, non prodotto). Local + offline.
- [ ] 🟡 **Layer di verifica/conformità PROPRIO** (il gap che nessun MCP riempie): CSS-var allowlist + token-linter
      + visual-regression Playwright-PNG. **Obbligatorio** — senza questo l'MCP riduce ma non elimina la deriva.
- [ ] 🟡 **bolt.diy self-host** SOLO se serve un canvas generativo full; ma quality-experimental, non brand-aware
      out-of-box, modelli <7b inaffidabili. Opzionale, basso.
- [ ] 🔴 **Figma Dev Mode MCP** — ESCLUSO dallo stack sovrano (cloud-coupled, seat a pagamento, 4 claim-local refutati).
      Usabile solo se si accetta il cloud Figma per il design (NON per i dati cliente).
- [ ] ⚪ **Atlassian ads-mcp** — NON adottare (espone il loro DS); usare solo come **template di packaging** del nostro.

## 6. OPEN QUESTIONS (consegnate, non risolte)

1. Feedare un MCP token-JSON + Storybook MCP alla Claude CLI MAX **riduce misurabilmente** l'allucinazione di
   componenti rispetto a un semplice riferimento token in `CLAUDE.md`? E quale primitivo di verifica/lint chiude
   meglio il gap di conformità?
2. Il Figma Dev Mode DESKTOP (`127.0.0.1:3845`) può operare su file cached/offline per uno stack UU-PDP, o richiede
   SEMPRE auth cloud live? (Esiste un path air-gapped o Figma va escluso del tutto?)
3. Qual è il **modello coder locale minimo** su Apple Silicon (Qwen-2.5-Coder 7b/14b/32b) che produce React
   design-system-conforme contro un set token MCP, dato il fail-mode <7b di bolt.diy? Tiene per un brand arbitrario
   vs ShadCN?
4. ~~«generated-not-maintained / view-over-app» è davvero praticato da qualcuno con un primitivo local-first verificato?~~
   → ✅ **CHIUSA 2026-06-09 (PARTIAL-YES)**: sì come PRIMITIVO (json-render/OpenUI Lang self-hostable), no come prodotto.
   Vedi §4 + `2026-06-09-ground-a-buco2-subq4-view-over-app.md`.

## 7. Caveat trasversali (da non nascondere)

- **TIME-SENSITIVITY**: tooling 2026 in movimento rapido — Figma MCP beta→remoto→"raccomanda remoto"; Storybook MCP
  0.7.0 (apr 2026); ads-mcp 78 versioni. **Ri-verificare le versioni prima di adottare.**
- **SOURCE QUALITY**: diversi finding poggiano su doc-vendor primarie (Figma/Atlassian/StackBlitz) sui propri
  prodotti — accettate per claim di esistenza/meccanismo, ma gli **outcome/efficacia** (demo 20-min, "pixel-perfect")
  sono stati **REFUTATI 0-3** e vanno letti come marketing, non come risultati misurati.
- **LOCAL-FIRST È L'ASSE PIÙ DEBOLMENTE VERIFICATO**: ogni MCP di tool-design cloud (Figma, brand-agent bolt.new) ha
  fallito il test offline/sovranità (4 sub-claim "è local" refutati). Gli unici primitivi genuinamente sovrani
  verificati sono (a) Storybook MCP server-side e (b) il pattern design-system-as-MCP su token-JSON — ma il secondo
  è demo-scale, ed **entrambi** lasciano comunque trapelare metadata componenti all'endpoint LLM dell'agente (Claude
  CLI MAX accettabile).
- **ARBITRARY-DESIGN-SYSTEM GAP**: ads-mcp e design-system-mcp espongono i LORO token → adottarli significa
  **pacchettizzare il nostro** `tokens.json`/`packages/` in un MCP custom, non puntare un tool esistente a un sistema
  arbitrario esterno.

## 8. Aggancio alla decisione del 2026-06-06 (renderer HTML/CSS)

Questo conferma e rafforza `decision_wr2_renderer_html_css_over_canva_2026_06_06`: il renderer HTML/CSS→PNG +
`tokens.json` + Legibility Armor È già la "component-source" giusta. Il pezzo mancante che questa ricerca individua
è il **doppio innesto**: (1) esporre quei componenti/token a un agente via MCP locale così che generi *dentro* il
brand, e (2) il **verificatore di conformità proprio** (Playwright-PNG visual-regression = primitivo già posseduto)
— perché l'MCP fornisce ground-truth ma non la verifica. È esattamente il Filo-2 del verdetto eserciti
(«il verificatore è imperfetto → tutto gated + auto-testante») applicato allo stadio DESIGN/ENRICH del loop.
