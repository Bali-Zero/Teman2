---
date: 2026-06-06
domain: operations
client_case: none
sources:
  - deep-research harness (24 fonti, 114 claim, 25 verificati avversarialmente, 8 refutati) 2026-06-06
  - council 4-LLM asimmetrico (Claude proponente + Gemini red-team + Codex costruttivo + DeepSeek logico)
  - reuse-first interno (5 file SOTA repo Nuzantara, 15+ paper arXiv 2024-2026)
  - Anthropic "When AI builds itself" (reference_anthropic_recursive_self_improvement_2026_06_06)
status: STUDY-PHASE — ricerca dell'avanguardia, decisione architetturale (orchestrare vs greenfield) RINVIATA
---

# SOTA del meta-workflow di sviluppo software agentico end-to-end (2026)

> Fase: **studio dell'avanguardia**, NON implementazione. Per scelta esplicita di Antonello:
> "si deve prima vedere come lavora l'avanguardia". La decisione orchestrare-esistente vs
> greenfield viene DOPO, informata da questa ricerca.
>
> Metodo: SOTA-architecture-loop (FRAME→GROUND→REASON→COUNCIL→CAPTURE) + reuse-first + deep-research.
> Tre direttive di Antonello rispettate: panel 4-LLM, deep-research, reuse-first sui repo globali.

## TL;DR (per Antonello)

1. **Non ti sei perso "dei pezzi" — ti sei perso 9 pezzi precisi**, elencati sotto. I 3 più importanti
   (verifica-a-ogni-giuntura, test-in-container-come-prod, accumulo-memoria) sono load-bearing e oggi
   mancano o sono rotti.
2. **Il collo di bottiglia non è la velocità di generazione, è la VERIFICA.** Tu non sei dev e non
   revisioni codice → il gate automatico DEVE sostituire la tua review. Tutto il loop va progettato
   attorno a questo. (Confermato da Anthropic "When AI builds itself" + da MAST: 37% dei fallimenti
   multi-agente sono di verifica/terminazione.)
3. **Per il tuo stack (Mac+Ollama, no-paid-Anthropic) il SOTA NON è "comprare Devin".** È:
   `scaffold sovrano (OpenHands/Claude Code) + sandbox microVM locale (microsandbox) + design-system-as-MCP
   + cascade-as-routing (già ce l'hai) + verifica avversariale come review delegata`. Tutto local-first.
4. **Una verità scomoda, verificata 3 volte**: lo stack 100%-locale NON regge da solo per coding
   autonomo complesso. I modelli locali su Mac fanno realisticamente molto meno dei leaderboard. Serve
   **burst-to-cloud per i task difficili** (Claude CLI per codice; mai PII). Questo non è un fallimento
   del piano — è il confine reale da accettare.
5. **Il 70% dell'infrastruttura esiste già in casa** (worktree broker, lease, merge-queue, repomap,
   federation orchestrator, MOS, 4-LLM panel). Reuse-first dice: orchestrare l'esistente, non greenfield.

---

## 1. FRAME — il loop richiesto, scomposto

Antonello vuole, a velocità siderale:
`studia → ricerca feature → disegna architettura → organizza squadre → costruisce pezzo-per-pezzo
(parallelo dove si può) → arricchisce → design + app internal → testa in container come fosse produzione → ship`

Scomposto in 11 stadi-mattone (+ 1 trasversale):

| # | Stadio | Cosa fa |
|---|---|---|
| 0 | STUDY | reuse-first + cicatrix + recall memoria prima di toccare codice |
| 1 | SPEC | artefatto-contratto verificabile (non un check finale) |
| 2 | ARCH | decisione architetturale con council quando serve |
| 3 | PLAN/SQUAD | decompone + decide SE/COME parallelizzare + assegna |
| 4 | BUILD∥ | costruzione parallela in worktree isolati |
| 5 | SEAM-VERIFY | verifica a ogni giuntura PRIMA di assemblare |
| 6 | ENRICH | design + internal-app dentro il brand |
| 7 | TEST-PROD | test in ambiente isomorfo a produzione |
| 8 | REVIEW | verifica avversariale = review delegata (sostituisce Antonello) |
| 9 | SHIP | merge-gate + branch protection |
| 10 | LEARN | accumulo memoria/skill (Reflexion/Voyager) |
| * | GOVERN | observability adoption + cost budget |

---

## 2. GROUND-A — cosa fa l'avanguardia (deep-research, verificato avversarialmente)

> Metodo: 24 fonti fetchate, 114 claim estratti, **25 verificati con voto 3-su-3, 8 REFUTATI 0-3**.
> Riporto solo ciò che è SOPRAVVISSUTO alla verifica + i refuti notevoli.

### 2.1 Test-in-container-come-produzione (buco interno #1) — FATTI VERIFICATI

- **Modello dominante 2026**: isolamento **kernel-level/hardware** (microVM o sandboxed-kernel), NON
  container shared-kernel. Firecracker microVM (kernel dedicato per sandbox: E2B, Vercel Sandbox, Fly Sprites)
  o gVisor (kernel user-space: Modal). Daytona usa Docker plain (esplicitamente il tier più debole). [3-0]
- **Performance Firecracker**: ~125ms boot, <5 MiB overhead/VM, 150 microVM/sec/host. Snapshot-resume da
  template "warm" → startup **sotto 1 secondo** (4ms Firecracker ufficiale, p50 4.1ms Fly.io). Questa è la
  base tecnica della "velocità siderale". [3-0]
- **PER IL TUO STACK (verificato 3-0, il fatto più importante della ricerca)**:
  - **microsandbox** (Apache-2.0, libkrun microVM) gira **localmente su Apple Silicon via Hypervisor.framework**
    (NON KVM — KVM è solo-Linux), boot <100ms, modi **persistent (`msr`) + ephemeral (`msx`, leave-no-trace)**.
    È l'UNICA opzione VM-isolation davvero deployabile sul tuo Mac. Fit perfetto coi vincoli.
  - **qbox / Firecracker / E2B = Linux+KVM only** → **NON girano su Mac** (né Pro né Mini, entrambi Apple Silicon).
    Per usarli servirebbe aggiungere un box Linux. [3-0]
  - **DevContainer Anthropic reference** (Cursor/Claude Code dentro Docker + egress-firewall allowlist) rende
    `--dangerously-skip-permissions` sicuro per run non sorvegliati. 100% locale, tier "container" (più debole
    di microVM ma più semplice).
- **Closed-loop validation**: **signadot-validate** (skill MCP per Claude Code/Codex/Cursor) spinna un sandbox
  isolato col solo servizio modificato, tira le dipendenze reali (Postgres/Kafka/Redis) da un baseline cluster
  live, gira E2E/integration, e **rimanda i fallimenti all'agente che si corregge e ri-testa**. [3-0]
  **MA richiede Kubernetes** → NON locale. Il *pattern* è il bersaglio; l'infra va riprodotta con microsandbox+Docker.

### 2.2 Design + internal-app dentro il brand (buco interno #2) — ✅ VERIFICATO (pass dedicato 2026-06-08)

> **Storia (onestà del harness)**: il 2026-06-06 quest'area produsse **ZERO claim sopravvissuti** — i claim
> erano deboli/marketing e furono filtrati. Era l'unico dei 3 buchi GROUND-A rimasto non-verificato (cfr. NEXT #4
> riga 404). **Chiuso dal pass dedicato 2026-06-08** (deep-research run wf_4a6766ac-8f4: 23 fonti, 107 claim,
> 25 verificati 3-su-3, 6 uccisi). Dettaglio completo + checklist: **`2026-06-08-ground-a-buco2-design-internal-app.md`**.

Verdetto sintetico (fatti 3-0, il dettaglio è nel file dedicato):
- ✅ **Storybook MCP** (`@storybook/addon-mcp`, `localhost:6006/mcp` sul TUO dev server) = primitivo **genuinamente
  local-first** per esporre props/stories dei componenti `packages/` reali. È la metà component-source del 2-MCP.
- ✅ **design-system-as-MCP su token-JSON** (`yajihum/design-system-mcp`: `getTokens`+`getComponentProps` via Style
  Dictionary) = **blueprint esatto** per esporre il nostro `tokens.json` localmente. Demo-scale ma implementabile.
- ✅ **Atlassian `@atlaskit/ads-mcp`** = prova-di-produzione del 2-MCP completo, ma **template di packaging** (espone
  il loro DS), non un modo di puntare a un sistema arbitrario.
- ❌ **Figma Dev Mode MCP** = REALE ma **cloud-coupled** (file SaaS, seat a pagamento, 4 sub-claim "local" refutati 0-3)
  → **escluso dallo stack sovrano UU-PDP**.
- ✅ **bolt.diy** = unico self-hostable (MIT, Ollama/LM Studio) ma **non brand-aware out-of-box** (brand-agent è nel
  commerciale bolt.NEW; modelli <7b inaffidabili). v0/Lovable non self-hostable.
- 🟥 **RISULTATO NEGATIVO load-bearing (3-0)**: un MCP token/prop è un **DATA-PROVIDER, non un CONFORMANCE-ENFORCER**.
  Nessun MCP esaminato verifica l'output → il solo-dev deve costruire il **proprio** layer di lint/verifica
  (CSS-var allowlist + token-linter + visual-regression Playwright-PNG). Filo-2 del verdetto applicato allo stadio DESIGN.
- ✅ **Sub-domanda (4)** «view-over-app / generated-not-maintained» = **CHIUSA 2026-06-09, PARTIAL-YES** (era
  refutata-per-assenza il 06-06/08). Pass dedicato (run wf_1168ba50-a79): il pattern È reale come **primitivo
  self-hostable local-first** (json-render Apache-2.0 + OpenUI Lang MIT, LLM-vincolato-a-catalogo Zod, gira local
  via Ollama; + schema-driven deterministico RJSF/Windmill) ma **NON come prodotto turnkey** — il solo-dev assembla.
  Il canone malleable-software (Ink&Switch Patchwork) **refutato 3-0**: research-prototyping per ammissione autori,
  non produzione. Il catalogo Zod vincolante = il "conformance-enforcer" del punto sopra, incorporato nel render.
  Dettaglio: **`2026-06-09-ground-a-buco2-subq4-view-over-app.md`**. **Era l'ultima open-question aperta di GROUND-A.**

### 2.3 Stato-prodotto commerciale + sovranità (buco interno #3) — FATTI VERIFICATI

- **SCAFFOLD > MODELLO (3-0, Epoch-corroborato)**: lo stesso LLM oscilla **15-22 punti** su SWE-bench a
  seconda dell'agent-wrapper. Implicazione diretta per un solo-dev: **investi nello scaffold/tool-orchestration,
  non nel modello più grande.** È la leva che controlli.
- **OpenHands ~66%** (5 tentativi, critic Qwen fine-tuned pubblico su HuggingFace), gira **free su modello
  user-supplied**; SWE-Agent ~50-55%. [2-1, OpenHands primary-source]. Path sovrano reale.
- **OpenHands Index (Gen 2026)**: benchmark che misura il MIDDLE del loop (issue-resolution, greenfield,
  frontend, testing, info-gathering) ma **NON copre deploy/ship né architecture-come-fase**. [3-0]
- **8 SCORE SWE-BENCH DA AGGREGATORI REFUTATI 0-3**: "Claude Code Opus 4.7 ~77%", "Augment 72%",
  "Devin 45.8%", "Cursor Composer ~71%", "Daytona sub-90ms fastest", lo swing "43.2→59.8 Cline" — TUTTI
  refutati. **Non fidarsi dei leaderboard aggregati. Solo primary-source.** (Questo include un numero che
  era nel mio draft iniziale.)

### 2.4 Caveat espliciti del deep-research (da non nascondere)

- Fonti sandbox-comparison pesano su blog vendor (Northflank, ecc.), ma i fatti tecnici load-bearing
  (microVM vs container, boot times) ri-verificati contro AWS/Fly/Docker/arXiv e hanno tenuto.
- Nessun teardown indipendente di qbox o microsandbox specificamente.
- Sovranità: l'unica opzione cleanly-Mac è microsandbox (HVF). Tutto il resto richiede Linux+KVM o K8s.

---

## 3. GROUND-B — cosa esiste GIÀ in casa (reuse-first)

> reuse-first ha ripagato: il 70% della ricerca SOTA sul loop agentico era già nel repo (5 file,
> 15+ paper arXiv 2024-2026 verificati). NON l'ho rifatto.

### Mattoni interni già pronti
| Stadio loop | Mattone interno | Stato |
|---|---|---|
| BUILD∥ (worktree) | `scripts/agent_start.py` (L1 broker) | shippato, **OPT-IN (adoption ~0%)** |
| Lock cross-agent | Redis lease registry (L2) | shippato + kill-switch |
| SHIP (merge gate) | merge-queue L3 + CODEOWNERS | shippato, hardening pending |
| Context injection | repomap cron (L4) | shippato (floor, non SOTA) |
| PLAN/SQUAD | `federation_orchestrator.py` (LangGraph) | esiste, **manca gate "SE parallelizzare"** |
| Mappa lane live | `orchestrator_live_map.py` | esiste |
| ARCH (loop decisionale) | skill `sota-architecture-loop` | esiste |
| Memory | MOS (`mem save`) + SessionStart hook | esiste (passiva) |
| LEARN (Reflexion/Voyager) | agent-library-evolver weekly | **ROTTO** (scar W50: worktree condiviso, 32h drift) |
| REVIEW (avversariale) | devils-advocate, spalla-review, 4-LLM panel | esiste (invocato manualmente) |

### Verdetto interno (file reuse-first 2026-06-06, coerente)
"NON installare un nuovo runtime multi-agent nel core dell'organismo. La gerarchia attuale
(L0 deterministico → L1/L2 giudizio limitato → L3 Consiglio solo per irreversibili → Human/Zero)
è lo scheletro giusto. Il fan-out resta utile in ricerca/review read-only, non per repair autonomo."

---

## 4. I 9 PEZZI MANCANTI (risposta diretta a "mi sono perso dei pezzi?")

**6 mancavano nella formulazione iniziale di Antonello:**
1. **SPEC come artefatto-cardine** (non check finale) — è il 4-LLM panel promosso a fondamenta.
2. **SEAM-VERIFY** (verifica a ogni giuntura, non solo alla fine) — MAST: 37% fallimenti = verifica/terminazione.
3. **Gate "decidere SE parallelizzare"** — fan-out degrada −70% su task sequenziali/coding (Google Science of Scaling).
4. **LEARN (Reflexion/Voyager)** — progettato ma ROTTO (W50).
5. **GOVERN (observability + cost budget)** — senza metrica adoption il loop non sa dove migliora.
6. **Rollback/blast-radius** — worktree isolation + branch protection (questo già ce l'hai).

**3 erano buchi anche nella ricerca interna (colmati dal deep-research):**
7. **TEST-PROD (microVM locale)** — zero copertura interna → microsandbox è la risposta verificata.
8. **ENRICH (design/internal-app)** — ✅ chiuso dal pass dedicato 2026-06-08: Storybook-MCP (componenti) +
   token-JSM-MCP (tokens.json) locali + verificatore-conformità proprio. Vedi `2026-06-08-ground-a-buco2-design-internal-app.md`.
9. **Stato-prodotto commerciale** — i file citavano i paper ma non il "come chiudono il loop davvero".

---

## 5. REASON — modello dell'avanguardia per il caso Antonello

> Council 4-LLM completato (Gemini+Codex+DeepSeek, 3 panelisti su modelli diversi; Claude=proponente).
> La tesi sotto è stata attaccata e RIFORMULATA — vedi §6 per i difetti e §8 per la versione difendibile.

**Tesi centrale**: per Antonello (solo-dev, locale-sovrano, non-dev, no-paid-Anthropic), il loop SOTA è
comporre 5 strati già posseduti al 70%, colmando i 3 buchi con primitivi local-first verificati:

```
META-DEV-LOOP (proposta da validare)
  0. STUDY      reuse-first + cicatrix + MOS recall        → skill session-study (manca)
  1. SPEC       artefatto-cardine verificabile              → 4-LLM panel come fondamenta (esiste)
  2. ARCH       sota-architecture-loop 8-step               → esiste (skill)
  3. PLAN/SQUAD federation_orchestrator + gate "SE-fan-out" → gate manca
  4. BUILD∥     agent_start.py worktree                     → esiste, da rendere DEFAULT non opt-in
  5. SEAM-VERIFY verifica a ogni giuntura                   → manca (MAST 37%)
  6. ENRICH     design/internal (Storybook-MCP?)            → BUCO APERTO, serve pass dedicato
  7. TEST-PROD  microsandbox locale (HVF, msx ephemeral)    → primitivo verificato, da integrare
  8. REVIEW     verifica avversariale = review delegata     → esiste, da rendere GATE bloccante
  9. SHIP       merge-queue L3 + branch protection          → esiste
 10. LEARN      Reflexion/Voyager skill-evolution           → ROTTO (W50), da riparare
  *. GOVERN     observability adoption + cost budget        → manca
```

**Il principio-guida** (da Anthropic "When AI builds itself" + verifica empirica):
> Per un non-dev, "velocità siderale" senza verifica-automatica-come-review-delegata NON è una feature:
> è il rischio #1. Il 60% dello sforzo va su SEAM-VERIFY + TEST-PROD + REVIEW, non sulla velocità di build.

---

## 6. COUNCIL 4-LLM asimmetrico — difetti trovati

> Ruoli su modelli DIVERSI (sota-architecture-loop): Claude=proponente, Gemini=red-team,
> Codex=costruttivo, DeepSeek=logico. Mai consenso.

### 6.1 Gemini (red-team) — difetti CRITICI/ALTI confermati
1. **[CRITICO] L'illusione della "review delegata"**: un panel di LLM (anche locali) condivide bias e
   pattern di allucinazione col generatore. Se l'agente scrive un bug + test basati sulle stesse assunzioni
   errate, il panel convalida ("i test passano"). Per un non-dev = software rotto con "test verdi 100%",
   non diagnosticabile. → **Il single point of failure dell'intero piano.**
2. **[CRITICO] OpenHands 68.4% è su Claude Sonnet CLOUD, non Ollama locale** — i modelli locali fanno
   <20-25%. (CONVERGE col deep-research che ha refutato 0-3 lo stesso claim.) → lo stack 100%-locale non regge da solo.
3. **[ALTO] Sovranità-PII vs Claude CLI**: la CLI manda dati ad Anthropic. OK per codice, VIETATO se nel
   prompt finiscono PII/DB reali. Il piano deve distinguere esplicitamente i due path.
4. **[ALTO] VRAM thrashing**: N agenti LLM 32B paralleli saturano la memoria unificata Mac → OOM, <1 tok/s.
   Uccide la "velocità siderale". Il parallelismo locale ha un tetto fisico basso.
5. **[ALTO] Ipertrofia per solo-dev**: Redis lease + merge-queue + federation = infra per team di decine.
   Per 1 utente non-dev aggiunge punti di guasto (lock orfani, merge-conflict auto).
6. **[ALTO] SmolVM <200ms-da-Mac = condizioni di laboratorio** (kernel minimo, no rete, no mount complessi).
   Con Postgres+deps reali l'overhead I/O è insormontabile. (Il deep-research conferma: microsandbox è
   l'opzione reale, non SmolVM.)
7. **[ALTO] Reward-hacking nei test autogenerati**: senza validazione esterna deterministica, l'agente
   indebolisce i test (`assert True`, mock vuoti) per passare il gate. → copertura 100% + zero funzione reale.
8. **[MEDIO] "Senza nuovo runtime nel core" è falso**: microsandbox+Redis+Postgres+Storybook+LiteLLM = 5 runtime nuovi.
9. **[MEDIO] Mancano barriere statiche deterministiche** (AST, type-check, linter bloccanti, security scanner)
   prima di "far discutere gli LLM" su errori che un compilatore prende in ms.
10. **[MEDIO] LEARN (Voyager) già rotto** — auto-riscrittura skill senza supervisione senior = degradazione progressiva.
11. **[MEDIO] GOVERN inutile per solo-dev locale** — telemetria che l'unico utente ignorerà.

### 6.2 Codex GPT-5.5 (costruttivo) — come salvare e semplificare l'idea
> Prospettiva costruttiva: minimum-viable-loop + sequenza + tool OSS concreti (URL verificabili).

1. **MINIMUM VIABLE LOOP (taglia l'ipertrofia)**: domani fai solo
   `STUDY → SPEC → BUILD-in-worktree → SEAM-VERIFY → TEST-lite → REVIEW-evidence → CAPTURE` (7 non 11),
   riusando `agent_start.py` + `sota-architecture-loop` + pre-commit + pytest + Playwright. 80% del valore,
   zero overhead degli stadi enterprise. → risolve Gemini #5 + DeepSeek #12.
2. **`session-study` come artefatto fisso**: produce `run_context.md` (memory-hits, file-caldi, rischi-PII,
   test-plan, criteri-accettazione) via rg + MOS + repomap. Evita agenti che partono senza contesto.
3. **gate parallelizzare**: fan-out SOLO se path disgiunti + contratti espliciti tra pezzi
   (`git merge-tree` per pre-check conflitti). Copre i due-agenti-stesso-file.
4. **checkpoint/resume obbligatorio**: ledger JSONL/SQLite per stage (commit, hash I/O, tool, test, verdict).
   Gestisce crash-a-metà-build, **quota Claude esaurita mid-loop**, Pro irraggiungibile, agenti zombie.
   → risolve un edge-case che né Gemini né DeepSeek avevano colto.
5. **SEAM-VERIFY deterministico**: ogni giuntura ha contratto I/O + check minimi (ruff, mypy,
   `pytest-json-report` [output macchina-processabile], eslint/tsc, actionlint).
6. **verify-the-verifiers anti-false-solve (CRITICO-1, lato tool)**: Semgrep custom rules + mutation-testing
   mirato + OPA/Conftest per policy → blocca test-indeboliti/assertion-rimosse/snapshot-aggiornate-senza-motivo.
   "Verifica = evidenza, non fiducia cieca."
7. **sandbox in DUE livelli**: SUBITO Dev-Container/Docker-Compose su **Pro** (non M5) con seed-DB-sanificato +
   egress-allowlist; POI microVM dietro adapter. Risolve "test-verdi-prod-rotto" senza roba pesante su M5.
8. **NON rendere SmolVM load-bearing** (CONVERGE con la correzione post-deep-research): microsandbox è più
   maturo (local/on-prem/air-gapped, OCI, network-policy, no-telemetry); SmolVM è giovane → backend opzionale,
   benchmark locale prima di promettere <200ms.
9. **router modello/budget esplicito (CRITICO-2, lato tool)**: PII+routine su Ollama/OpenHands locale; cloud
   SOLO per codice/spec sanificati; stop/resume su quota-bassa. OpenHands+LiteLLM (Ollama + retry/fallback +
   cost-tracking). OpenHands stesso **avvisa che servono modelli potenti e contesto grande** → conferma CRITICO-2.
10. **Storybook incrementale**: parti con 5 primitive + stories + a11y(axe-core) + Playwright-snapshot; il
    Storybook-MCP completo dopo. Dà verifiche VISIVE a un non-dev (rosso/verde, non codice).
11. **gate umani minimi (CRITICO-1, lato umano — la lista concreta)**: Antonello approva SOLO:
    auth/RBAC · billing/pricing · migrazioni irreversibili · delete-dati · deploy-prod · secrets/env ·
    egress-PII · contenuti-pubblici/legali · daemon/launchd. Via GitHub rulesets/CODEOWNERS + branch-protection
    + OPA. **Il non-dev non legge codice, ma blocca i rischi business irreversibili.** → risolve il vincolo #1.
12. **CASO PILOTA: "Agent Run Evidence Dashboard"** (il pilota È la soluzione): internal-tool che legge
    ledger + diff + test-JSON + worktree-attivi + seam-verdict + hot-zone + rollback-plan, e mostra ad Antonello
    **rosso/verde/evidenze invece di codice**. Valida l'intero loop senza toccare clienti E gli dà la review
    delegata resa leggibile. (Next.js admin esistente + SQLite/Postgres locale + pytest-json-report + Playwright.)

### 6.3 DeepSeek V4 Pro (logico) — difetti di ragionamento confermati
> Modello verificato: `deepseek-v4-pro` (non flash). 12 item, rigore-paper.

1. **[PARADOSSO DEL VERIFICATORE, #4+#8] (il difetto più profondo, CONVERGE con Gemini #1)**: il piano
   *cita* "verify-the-verifiers" ma **non lo implementa nel loop**. Se i modelli imbrogliano i benchmark
   (reward-hacking ammesso), possono imbrogliare anche il verificatore avversariale. Il vincolo #1
   (Antonello non revisiona) **chiude la via di fuga umana**. → senza un livello esplicito che verifichi
   l'output del verificatore (meta-verifier su modello diverso + metriche ortogonali + gate umano sui
   sospetti false-solve), il loop è fragile in coda.
2. **[NUMERI GRATUITI, #6+#11+#7]**: "60% dello sforzo su verifica", "−70% fan-out (Google Science of
   Scaling)", "37% MAST" — quantificazioni senza fonte puntuale (DOI/arXiv ID) né derivazione. Vanno
   o referenziate con precisione o degradate a qualitativo ("priorità massima alla verifica", non "60%").
3. **[SOVRANITÀ-PII VIOLATA SILENZIOSAMENTE, #9+#10]**: Signadot (K8s cloud), v0/Bolt/Lovable (cloud) —
   se ci passano design-system con logica business o dati riconducibili a clienti, **violano il vincolo #2**.
   Serve: (a) equivalente OSS self-hosted, (b) burst-cloud solo su dati sintetici/mock mai-da-DB-con-PII,
   (c) sanitizer automatico prima di qualsiasi routing esterno.
4. **[CLAIM LOCALI GONFIATI, #5+#2] (CONVERGE con Gemini #2 e col deep-research)**: OpenHands 68.4% e
   SmolVM <200ms sono claim su cloud/laboratorio, non riproducibili localmente senza benchmark. Da
   degradare a "potenziale esecuzione locale con qualità ridotta" finché non misurati su Mac+Qwen.
5. **[FALLACIA DEL PRIMO PILOTA, #12]**: "internal-tool a basso blast-radius" è prudente ma se troppo
   semplice NON stressa i componenti critici (TEST-PROD) → falso positivo. Il pilota DEVE includere
   metriche di stress reali: ≥1 migrazione schema DB + ≥1 API esterna mocked + ≥1 rollback automatico.

### 6.4 CONVERGENZA dei panelisti (il segnale forte)
I 3 LLM, indipendentemente, hanno colpito gli **stessi 2 difetti CRITICI**:
- **CRITICO-1**: la "review delegata" è un'illusione SE il verificatore condivide i bias del generatore
  e non c'è un meta-livello che lo controlla. (Gemini #1 + DeepSeek #1/#8) → **è il rischio #1 del piano**.
- **CRITICO-2**: i numeri di capability locale sono gonfiati; lo stack 100%-locale non regge da solo per
  task complessi. (Gemini #2 + DeepSeek #5 + deep-research refuta 0-3) → **burst-cloud è obbligatorio, non opzionale**.

---

## 7. CHECKLIST pattern adottabili (derivata da fatti verificati + council)

> Ogni pattern marcato: ✅ già in casa · 🔧 da costruire · 🌍 OSS da riusare · ⚠️ vincolato.
> Ordinati per leva (impatto sul rischio), non per stadio del loop.

### Verifica (il 60%→"priorità massima" dopo correzione DeepSeek #2 — il collo di bottiglia reale)
- [ ] 🔧 **verify-the-verifiers come livello esplicito del loop** (chiude CRITICO-1). Non basta "verifica
      avversariale": serve un meta-livello che controlli il verificatore. Composizione minima:
      (a) **barriere deterministiche PRIMA degli LLM** — compilatore/type-check/linter-bloccante/security-scanner
      (un compilatore prende in ms errori su cui gli LLM "discuterebbero" — Gemini #9); (b) verificatore su
      **modello diverso** dal generatore con **metriche ortogonali**; (c) **gate umano minimo** sui sospetti
      false-solve e sulle classi irreversibili (auth/billing/migration) — Antonello firma SOLO questi, non tutto.
- [ ] 🔧 **anti-reward-hacking**: detector che flagga test indeboliti (`assert True`, mock vuoti, asserzioni
      rimosse) prima del merge. Senza, copertura 100% = teatro (Gemini #7, DeepSeek #4).
- [ ] ✅ **4-LLM panel asimmetrico** (Claude+Gemini+Codex+DeepSeek, ruoli diversi) — già usato, da rendere
      gate bloccante non opzionale per spec/architettura.

### Test-in-container-come-prod (buco #1 — primitivo verificato)
- [ ] 🌍 **microsandbox** (Apache-2.0, libkrun, HVF su Apple Silicon, msx ephemeral) come sandbox locale
      isomorfa-a-prod. UNICA opzione VM-vera sul Mac. [verificato 3-0]
- [ ] ⚠️ **NO Firecracker/qbox/E2B localmente** — Linux+KVM only, non girano su Pro né Mini (Apple Silicon).
      Se mai servisse hardware-VM Firecracker → 1 box Linux dedicato (trade-off non quantificato).
- [ ] 🔧 **riprodurre il pattern signadot-validate SENZA K8s**: microsandbox/Docker-Compose come target
      isomorfo + Claude-Code/Codex MCP che gira E2E e rimanda i fallimenti all'agente. (signadot richiede
      K8s → non locale; il *pattern* sì.)
- [ ] ✅ **DevContainer + egress-firewall allowlist** (Anthropic reference) per run agentici non sorvegliati
      sicuri. Tier "container" (più semplice, più debole di microVM).

### Capability / sovranità (CRITICO-2 — confine reale)
- [ ] ⚠️ **burst-to-cloud OBBLIGATORIO per task hard** (Claude CLI per CODICE; mai PII). Lo stack 100%-locale
      non regge per coding autonomo complesso. [convergenza tripla]
- [ ] 🔧 **router task→modello con sanitization**: task "hard" → cloud SOLO su dati sintetici/mock, mai
      branch da DB con PII; sanitizer automatico prima di ogni routing esterno (DeepSeek #9). È il
      "cascade-as-routing" di Factory MA con confine PII esplicito.
- [ ] ✅ **multi-LLM cascade** (già ce l'hai: Claude/Gemini/Codex/DeepSeek/Ollama) = validato esternamente
      come pattern Factory-droids.
- [ ] 🔧 **mini-benchmark locale prima di credere ai numeri**: 10 task SWE-bench-style con OpenHands+Qwen3-Coder
      su Mac → punteggio REALE, non da leaderboard (8 score aggregati refutati 0-3).

### Scaffold (la leva dominante — 15-22pt > qualsiasi modello)
- [ ] 🌍 **OpenHands** (MIT) come scaffold autonomo build/test, gira su modello tuo via LiteLLM. Path sovrano.
- [ ] **investi nel HARNESS, non nel modello** — è la leva che controlli (verificato 3-0, Epoch-corroborato).

### Parallelismo (con tetto fisico)
- [ ] ✅ **worktree isolation** (`agent_start.py` L1) — da rendere DEFAULT non opt-in (adoption ~0% oggi).
- [ ] 🔧 **gate "SE parallelizzare"** in federation_orchestrator (fan-out degrada su task sequenziali —
      claim da ri-referenziare con fonte puntuale, DeepSeek #11).
- [ ] ⚠️ **cap concorrenza per VRAM**: N agenti LLM-32B paralleli → OOM su Mac. Il parallelismo locale ha
      tetto basso; i worker paralleli che NON girano LLM-locali (orchestrazione, I/O) scalano, quelli che
      girano inferenza-locale no (Gemini #4).

### Design/internal-app (buco #2 — ✅ VERIFICATO 2026-06-08)
- [x] ✅ **pass di ricerca dedicato FATTO** → `2026-06-08-ground-a-buco2-design-internal-app.md` (23 fonti, 25 claim 3-su-3).
- [ ] 🟢 **Storybook-MCP** sul dev server `packages/` (props/stories reali) — primitivo genuinamente locale, ADOTTARE.
- [ ] 🟢 **MCP custom su token-JSON** (pattern yajihum) per esporre `tokens.json` — blueprint da costruire, locale+offline.
- [ ] 🟡 **layer verifica/conformità proprio** (CSS-var allowlist + token-linter + visual-regression Playwright-PNG) —
      OBBLIGATORIO: nessun MCP impone conformità, forniscono solo ground-truth (risultato negativo 3-0).
- [ ] 🔴 **Figma-MCP** ESCLUSO (cloud-coupled, UU-PDP); **v0/Bolt/Lovable** = cloud → solo ispirazione-pattern, mai
      chiamate esterne con design-system che contiene logica business (DeepSeek #10); bolt.diy self-host opzionale ma non brand-aware out-of-box.

### Memoria / apprendimento
- [ ] 🔧 **riparare LEARN (Reflexion/Voyager)** — oggi ROTTO (W50). Pattern: worktree dedicato per l'evolver,
      mai condiviso. E auto-evoluzione skill SOLO con gate (degradazione altrimenti — Gemini #10).

### Anti-ipertrofia (Karpathy + Gemini #5 + DeepSeek)
- [ ] ⚠️ **NON adottare tutti gli 11 stadi insieme.** Per un solo-dev non-dev, Redis-lease + merge-queue +
      federation = infra da team-di-decine → punti di guasto (lock orfani). Adottare il **minimum viable loop**
      e crescere per evidenza. [Codex compilerà la sequenza minima — §6.2]

## 8. DECISIONE / NEXT (proposta, NON eseguita — fase studio)

### La domanda rinviata ("orchestrare vs greenfield") — ora si può rispondere
**Orchestrare l'esistente. NON greenfield.** Motivi convergenti:
- reuse-first interno: 70% già in casa; il file 2026-06-06 conclude esplicitamente "NON nuovo runtime nel core".
- Il council: greenfield aggraverebbe l'ipertrofia (5 nuovi runtime già contestati da Gemini #8).
- I buchi reali (verify-the-verifiers, microsandbox-test, gate-fan-out) sono **innesti**, non un sistema nuovo.

### Riformulazione del loop DOPO il council (da 11 stadi a spina-dorsale difendibile)
Il loop NON va costruito attorno alla *velocità*. Va costruito attorno ai **2 CRITICI**:
1. **verify-the-verifiers** (barriere deterministiche + meta-verificatore + gate-umano-sui-irreversibili)
   come spina dorsale, non come stadio finale.
2. **router con confine-PII** (locale-default, burst-cloud-su-mock-per-hard) come sostrato di esecuzione.

### Il MINIMUM VIABLE LOOP (Codex #1) — cosa è fattibile DOMANI con ciò che hai
```
STUDY → SPEC → BUILD-in-worktree → SEAM-VERIFY → TEST-lite → REVIEW-evidence → CAPTURE
```
7 stadi (non 11), tutti su mattoni esistenti: `agent_start.py` + `sota-architecture-loop` + pre-commit +
pytest(`--json-report`) + Playwright. Gli stadi enterprise (Redis-lease, merge-queue, federation, GOVERN)
si aggiungono SOLO per evidenza, non all'inizio. Il primo "arricchimento" è il **checkpoint/resume ledger**
(Codex #4) che gestisce quota-Claude-esaurita-mid-loop — l'edge-case più probabile per te.

### Il caso pilota che È la soluzione (Codex #12)
**"Agent Run Evidence Dashboard"**: un internal-tool che legge il ledger + diff + test-JSON + seam-verdict +
hot-zone + rollback-plan e mostra ad Antonello **rosso/verde/evidenze invece di codice**. Risolve due cose:
(a) valida l'intero loop senza toccare clienti; (b) **È** la "review delegata resa leggibile" — il vincolo #1
diventa un'interfaccia, non un atto di fede. Stack: Next.js admin esistente + SQLite/Postgres + pytest-json-report.
Metriche di stress obbligatorie nel pilota (DeepSeek #12): ≥1 migrazione DB + ≥1 API-mocked + ≥1 rollback.

### NEXT proposti (non eseguiti, attendono tua scelta — in ordine di leva)
1. **Spike microsandbox su Mac** — verifica empirica boot-time + Postgres-deps reali (Gemini #6 + Codex #8 dubitano).
   È il primitivo più load-bearing e il meno verificato indipendentemente.
2. **Mini-benchmark locale** OpenHands+Qwen3-Coder su Mac (10 task SWE-bench-style) — il numero REALE, per sapere
   quanto burst-cloud serve davvero (chiude CRITICO-2 con un dato tuo, non da leaderboard).
3. **Costruire il MVL a 7 stadi** come spina dorsale, con verify-the-verifiers (barriere deterministiche +
   meta-verificatore + gate-umano-lista-Codex#11) come cardine — NON la velocità.
4. ~~Pass di ricerca dedicato sul buco #2 (design/internal-app)~~ — ✅ **FATTO 2026-06-08** → `2026-06-08-ground-a-buco2-design-internal-app.md`.
   ~~Residuo: sub-domanda (4) «view-over-app»~~ — ✅ **CHIUSA 2026-06-09 (PARTIAL-YES)** → `2026-06-09-ground-a-buco2-subq4-view-over-app.md`. **GROUND-A ora interamente verificato, zero open-question.**
5. **Caso pilota "Agent Run Evidence Dashboard"** con le metriche di stress, poi 4-LLM panel sull'architettura.

> **NB anti-hallucination**: questo report cita numeri (microsandbox <100ms, OpenHands ~66%, 15-22pt swing).
> Quelli marcati [3-0]/[2-1] sono verificati avversarialmente; il resto sono LEAD da ri-verificare prima di
> costruirci sopra (cf. cicatrix "autopsy hallucinated 3 file:line").
