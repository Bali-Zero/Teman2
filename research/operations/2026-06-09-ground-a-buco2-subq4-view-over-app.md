---
date: 2026-06-09
domain: operations
client_case: none
sources:
  - deep-research harness (20 fonti fetchate, 90 claim estratti, 25 verificati avversarialmente, 20 confermati / 5 uccisi) 2026-06-09 — run wf_1168ba50-a79
  - json-render (Vercel Labs) — github.com/vercel-labs/json-render (Apache-2.0, LICENSE verificato verbatim) + json-render.dev + InfoQ 2026/03 + LogRocket
  - OpenUI Lang (thesys) — github.com/thesysdev/openui (MIT) + openui.com/docs/openui-lang + docs.thesys.dev
  - RJSF — github.com/rjsf-team/react-jsonschema-form (Apache-2.0) + docs primary
  - Windmill auto-generated UIs — github.com/windmill-labs/windmill (AGPLv3+Apache) + windmill.dev/docs/core_concepts/auto_generated_uis
  - Ink & Switch malleable-software / Patchwork (essay + project page primary) + Simon Willison + Geoffrey Litt buttondown
  - Google A2UI — github.com/google/A2UI + developers.googleblog.com (declarative-render classification; self-host REFUTATO)
  - CopilotKit / AG-UI — github.com/copilotkit/copilotkit + copilotkit.ai 2026 taxonomy
status: CHIUSA — sub-domanda (4) di GROUND-A buco #2, era "REFUTATA per assenza" il 2026-06-08, ora PARTIAL-YES (cfr. 2026-06-08-ground-a-buco2-design-internal-app.md §4 + §6.4)
---

# GROUND-A buco #2 / sub-domanda (4) — «view-over-app / generated-not-maintained» (CHIUSA: PARTIAL-YES)

> **Perché esiste questo file.** Il pass dedicato del 2026-06-08 (`2026-06-08-ground-a-buco2-design-internal-app.md`
> §4 + open-question #6.4) lasciò UNA sola sub-domanda **refutata-per-assenza**: «view-over-app /
> generated-not-maintained» — UI interna rigenerata on-demand dal design-system invece che mantenuta a mano —
> aveva **ZERO evidenza primary-source sopravvissuta** (tutti i claim erano blog/marketing: getindigo.ai,
> Ink&Switch malleable-software, Geoffrey Litt, Google A2UI). Era l'**ultima open-question aperta di tutto GROUND-A**.
> Questo è il pass primary-source fresco richiesto. **Esito: ribalta il "refutato-per-assenza" in PARTIAL-YES** —
> il pattern È reale come primitivo self-hostable, ma NON come prodotto turnkey.

## 0. La domanda

Il pattern «view-over-app / generated-not-maintained» — un'UI interna (admin/dashboard) **rigenerata on-demand**
da un design-system + data-schema (generata fresh ogni vista, trattata come VISTA usa-e-getta), invece di essere
un'app persistente mantenuta a mano — è **davvero praticato in produzione** da qualcuno, con un primitivo
**local-first, self-hostable, verificabile** (non una SaaS cloud, non una demo di marketing)?

## 1. La risposta in una frase

**PARTIAL → YES.** Il pattern è reale come **primitivo self-hostable local-first** nelle sue forme
**schema-driven deterministica** e **LLM-vincolato-a-catalogo** — ma **NON esiste come prodotto turnkey**
"l'LLM rigenera un intero admin fresh ogni vista". Il solo-dev deve **assemblarlo** (catalogo Zod del proprio
design-system + LLM locale + un renderer come `json-render` o `OpenUI Lang`). È **lo stesso layer di
conformità-proprio** che il pass del 08-06 aveva già individuato come obbligatorio: il **catalogo Zod = la
CSS-var allowlist / token-linter incorporato nel render**.

## 2. FATTI-VERIFICATI (voto 3-0, primary-source) — i candidati che SOPRAVVIVONO alla barra

### 2.1 LLM-vincolato-a-catalogo (il vero "view-over-app" generativo) — 2 primitivi nuovi, self-hostable

- ✅ **json-render** (Vercel Labs, **Apache-2.0**, LICENSE verificato verbatim, ~13k★, 200+ release da gen-2026,
  v0.19.0 al 2026-05-12). L'LLM emette uno **spec JSON vincolato a un catalogo di componenti definito dallo
  sviluppatore** (`defineCatalog` + prop-schema Zod per-componente), renderizzato **live** client-side
  (React/Vue/Svelte/Solid/RN). Backend AI **pluggable** (Claude/ChatGPT/**locale**). Guardrail in codice:
  *"AI can only use components in your catalog"* + *"JSON output matches your schema, every time"*. InfoQ
  conferma: spec JSON vincolato a catalogo renderizzato progressivamente a runtime — **NON codegen v0/Lovable**.
- ✅ **OpenUI Lang** (thesys, **MIT**, 6.8k★, pacchetti `@openuidev/*` su npm). DSL streaming-first:
  Library(Zod+React) → Prompt Generator → Parser streaming → Renderer live. Scaffold + run locale via
  `npx @openuidev/cli@latest create … && npm run dev` (Next.js, localhost:3000); supporta `OPENAI_BASE_URL`
  per puntare a un **Ollama locale** → nessuna SaaS cloud obbligatoria. **Distinto** da thesys C1 (il prodotto
  cloud a pagamento opzionale).

### 2.2 Schema-driven deterministico (la metà matura e battle-tested) — lo schema È la source-of-truth

- ✅ **RJSF** (`react-jsonschema-form`, **Apache-2.0**). UI form generata da **JSON Schema a render-time**: lo
  schema È la form, il branch-switching avviene a runtime. Puro client-side, no SaaS, no per-seat.
  *Caveat: form-specifico, non dashboard arbitrari; deterministico, non LLM-generato.*
- ✅ **Windmill auto-generated UIs** (**AGPLv3+Apache-2.0**, self-host Docker/K8s). *"By analyzing the parameters
  of the main function, Windmill generates an input specification … in JSON Schema … then renders the UI from
  that specification"* — UI **derivata dallo schema, non mantenuta come artefatto separato**. Posizionato come
  "self-hostable alternative to Retool". *Caveat: Windmill offre ANCHE un app-editor drag&drop le cui UI custom
  sono artefatti persistiti/versionati → NON è un primitivo view-over-app PURO.*

## 3. REFUTATO (conferma il sospetto del 08-06)

- 🟥 **Malleable software / Ink & Switch (Patchwork, Potluck, Embark, Cambria; Geoffrey Litt)** — **3-0 refutato**.
  *Per ammissione degli autori stessi*: *"These projects aren't commercial products"*, rilascio open-source
  ancora al **futuro** (*"we plan to release Patchwork"*), Cambria *"we have not yet built a production-ready
  version"*. A ~1 anno dall'essay, **nessun repo `patchwork`** nell'org GitHub inkandswitch. E comunque Patchwork
  fa **version-control documenti** (Git-for-docs su CRDT Automerge), **non** rigenerazione UI da schema → non
  implementa nemmeno il pattern bersaglio. Citarlo come prova di "view-over-app in produzione" è **refutato**.
  (Corroborato da Simon Willison.)
- 🟥 **Google A2UI** — classificazione **corretta** (declarative-render: l'agente manda JSON-intent, il client
  renderizza coi propri componenti nativi — view-over-app, non codegen), MA: v0.8 **Public Preview**, spec in
  evoluzione, **zero deploy production documentati**; claim "self-hostable localhost" **refutato 0-3**; claim
  "rigenera incrementalmente come live-source" **refutato 1-2**. → supporta il *pattern*, non chiude la barra
  *production + local-first*.
- 🟥 **Retool / ToolJet / Appsmith / Budibase** — **3-0**: "build-and-maintain", NON view-over-app. L'app persistita
  e versionata È la source-of-truth; persino le feature AI 2026 fanno generate-once-then-edit. ToolJet **rifiuta
  esplicitamente** le disposable views: *"Every generated app is meant to be inspected, edited, extended, and
  governed — rather than creating disposable generated apps"*.
- 🟥 **CopilotKit / AG-UI** — **3-0**: è l'estremo "Static" (frontend mantenuto). "Generative UI" = l'agente
  renderizza/aggiorna componenti **pre-definiti** a runtime, non rigenera l'intera UI da schema. La tassonomia
  CopilotKit stessa: Static(AG-UI) vs Declarative(A2UI) vs Open-Ended(MCP Apps) → AG-UI nel build-and-maintain.
- 🟥 **ui-schema** — **0-3**: libreria form/UI di app-mantenute (binding MUI/Bootstrap), nessuna rigenerazione LLM.

## 4. IL CAVEAT LOAD-BEARING (lo scope-gap)

**Nessun candidato sopravvissuto è un PRODOTTO turnkey** "l'LLM rigenera un intero admin/dashboard fresh ogni
vista". Sopravvivono **primitivi/librerie** (`json-render`, `OpenUI Lang`) + **schema-renderer deterministici**
(RJSF, Windmill auto-UI). Per ottenere il pattern completo della sub-domanda, il solo-dev deve **ASSEMBLARE**
(schema/catalogo + LLM locale + uno di questi renderer). InfoQ lo dice esplicito: json-render *"functions as a
constrained generative-UI LIBRARY rather than regenerating UI on-demand"* come prodotto.

**Profondità di produzione SOTTILE + time-sensitive**: json-render (gen-2026) e OpenUI Lang (~mag-2026) hanno
**<2 mesi** al momento della sintesi; OpenUI Lang elenca solo **3 adopter** nominati (Standard Metrics,
Entelligence.AI, openui-forge). → "reale come primitivo self-hostable" = **SÌ**; "ampiamente production-practiced"
= **PARZIALE/aspirazionale**.

**Self-hosted ≠ zero-chiamate-esterne**: il default di OpenUI chiama OpenAI; la piena località richiede puntare
`OPENAI_BASE_URL` a Ollama — verificato possibile ma **non** out-of-box.

## 5. IMPLICAZIONE per il solo-dev (Apple Silicon, UU-PDP)

Esiste **oggi** un path local-first reale per il pattern view-over-app:
**`json-render` (o `OpenUI Lang`) + modello locale via Ollama (qwen/llama)**, col catalogo Zod = i componenti
`packages/` + `tokens.json` di Nuzantara come unica sorgente di componenti che l'LLM può usare.

Si **innesta esattamente** sul verdetto del buco #2 (§file 08-06):
- Il **catalogo Zod vincolante** È il "layer di conformità proprio" che nessun MCP forniva — qui è **incorporato
  nel render** (l'LLM *non può* emettere componenti fuori catalogo).
- Resta da aggiungere solo la **visual-regression Playwright→PNG** contro il brand atteso (già nello stack).

**MA**: per uso *production* (non spike), questo è **assemble-it-yourself**, non buy-it. Non è una FASE-0 di
riarmo strumentazione — è un'opzione ENRICH (stadio 6 del loop) da valutare *dopo* che il loop core è riarmato.

## 6. OPEN QUESTIONS (consegnate, non risolte)

1. Esiste un **account primary-source** (talk di un practitioner / repo con uso sostenuto) di un **admin/dashboard
   interno LLM-rigenerato fresh-ogni-vista in produzione** (non widget chat-embedded, non form) — cioè qualcuno
   che ha *assemblato* json-render/OpenUI nel prodotto view-over-app completo? → **ancora zero**.
2. `json-render` / `OpenUI Lang` reggono con un **modello locale Apple-Silicon** (Ollama qwen/llama) che produce
   spec JSON catalog-conformi a latenza/accuratezza accettabili, o serve de-facto ancora un modello frontier cloud?
3. Esiste un primitivo self-hostable che chiude l'estremo **OPEN-ENDED** (MCP Apps / superficie arbitraria) con
   le stesse garanzie local-first, o quella categoria è ancora solo cloud/vendor?
4. A2UI passerà da v0.8 Public Preview a un deploy production documentato con renderer self-hostable local-first?
   → ricontrollare al prossimo ciclo di release.

## 7. Caveat trasversali (da non nascondere)

- **TIME-SENSITIVITY**: il tooling generative-UI 2026 si muove veloce — json-render v0.19.0 e OpenUI Lang
  versioni/adozione vanno ri-verificate al momento dell'adozione; A2UI potrebbe uscire da Public Preview.
- **SPLIT-VOTE da trattare con cautela**: un sub-claim A2UI e la framing "json-render = vero view-over-app vs
  codegen" sono stati refutati a voto diviso (1-2) — il *meccanismo* di json-render regge 3-0, ma la sua
  classificazione purista "disposable-view" è contestata (è una *libreria* di rendering, non un prodotto-vista).
- **SOURCE QUALITY**: i claim di esistenza/meccanismo poggiano su repo + docs primary verificate; gli **outcome**
  ("widely practiced") restano PARZIALI — letti come adozione-early, non come risultato consolidato.
