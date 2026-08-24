---
date: 2026-08-24
domain: operations
client_case: none
sources: 5
---

# Product-factory total procedure — 5-seat cross-family panel (raw capture)

Zero's ask (2026-08-24): a research+brainstorm round with the big LLMs on the TOTAL procedure
(thinking → design → implementation → ship → operate) for GARUDA VOA and every future product —
"per la potenza estrema e la semplicità totale".

Method: one shared context (the factory as it is, pains included: 56% ceremony PRs, strategic
stalls, the 24-day dead bot), five DISJOINT lenses, zero contact between seats. Seats: Codex
GPT-5.6 Sol xhigh (engineering discipline) · Kimi K3 (deletion/simplicity) · Qwen 3.8 Max via
TP1 (organizational design) · DeepSeek V4 Pro via TP1, max_tokens=16000 (queueing/verification
economics) · Gemini 3.1 Pro via agy (world SOTA survey). All five returned substantive answers.

Synthesis ruled into system doctrine: `docs/factory/ASSEMBLY-LINE.md`. First consumer:
`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`.

Convergences (5/5 unless noted): artifact-exists-only-if-a-gate-consumes-it · contract-first
with generated typed clients · journey tests written red-first by a non-builder family ·
business-invariant paging + synthetic real-purchase probes with dead-man switch · ship dark +
progressive flags + owner one-click go-live · kill criterion in the mandate (Kimi, Sol) ·
one refuter per PR, risk-tiered (DeepSeek, quantitative) · orchestrator exception-only with
local lane authority (Qwen, DeepSeek) · real users at 5% rollout (Kimi) · ban sprints/status
theater/consensus-on-mechanical-tasks. Cost bound: multi-agent ≈15× tokens, degrades on
sequential problems (Sol, citing Anthropic/Google) — parallelize only the parallelizable.

Below: the five raw answers, verbatim.

---

## Seat: Codex GPT-5.6 Sol (engineering discipline)

[Air-M5]

1. **Principio operativo — dal PR al viaggio cliente**

L’unità di lavoro non è il ticket, il documento o il PR: è un viaggio cliente funzionante in produzione. Un prodotto non è “finito” quando il codice è merged, ma quando il percorso completo soddisfa i suoi SLO e genera l’esito business previsto.

Standardizzare soltanto cinque artefatti permanenti:

- `product.yaml`: cliente, problema, promessa, metrica primaria, guardrail, non-obiettivi, decisioni del proprietario.
- `journeys/`: macchina a stati e scenari acceptance del cliente.
- `contracts/`: OpenAPI, eventi, errori e compatibilità.
- Codice e test.
- `ops/`: SLO, dashboard-as-code, alert e runbook.

`release-evidence.json` viene generato dalla CI; non è un ledger compilato dagli agenti. Un ADR è ammesso solo per una decisione costosa da invertire. Ogni nuovo documento di processo deve essere machine-consumed, legalmente necessario oppure eliminare un artefatto precedente.

Limite WIP: un prodotto in build, uno in discovery; allocazione iniziale 70% prodotto strategico, 20% reliability, 10% interrupt. “Extreme power” non significa cinque modelli su ogni task: i sistemi multi-agent rendono sui problemi realmente parallelizzabili, ma consumano molto di più e possono peggiorare sui flussi sequenziali. [Anthropic riporta circa 15× i token](https://www.anthropic.com/engineering/multi-agent-research-system); [Google rileva degradazione sui task sequenziali](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/).

2. **FRAME — Gate G0: vale la pena costruirlo?**

Artefatto: `product.yaml`.

Opus 5 orchestra tre analisi indipendenti: Gemini ricerca mercato/normativa, Qwen sintetizza grandi corpus non-PII, DeepSeek ragiona su economics, stati e rischi. Nessuna discussione per raggiungere consenso: Opus sintetizza divergenze e alternative.

Il proprietario decide soltanto target, pricing, termini, rischio accettabile e go-live. G0 passa con:

- un utente e un problema specifici;
- una metrica falsificabile;
- massimo tre guardrail;
- una prima vertical slice vendibile;
- criteri espliciti di stop.

3. **GROUND — Gate G1: possiamo fidarci delle premesse?**

Artefatto: appendice `evidence` dentro `product.yaml`, non un dossier separato.

Gemini esegue ricerca normativa e competitiva; NotebookLM verifica le fonti regolatorie; Qwen estrae dati pubblici; modelli locali trattano esclusivamente documenti e PII. Un refuter di famiglia diversa cerca fonti mancanti, assunzioni nascoste, frode, privacy e failure di terze parti.

G1 passa solo quando ogni claim regolatorio, prezzo, requisito documentale e dipendenza esterna è `verified`, `assumption` oppure `unknown`. Nessun `unknown` può controllare pagamento, eligibility o promessa cliente.

4. **JOURNEY DESIGN — Gate G2: il prodotto è specificato come comportamento**

Artefatti: `journeys/garuda.feature` e `state-machine.yaml`.

Prima dell’UI si definiscono:

- happy path;
- failure/recovery path;
- stati ammessi e transizioni vietate;
- attore responsabile di ogni transizione;
- dati raccolti, retention e accesso;
- evento business osservabile per ogni passo.

Per GARUDA: eligibility → magic link → upload → OCR/correzione → order → payment → processing → delivery. Includere link scaduto/replay, file corrotto, OCR incerto, pagamento duplicato/fallito, webhook fuori ordine e ordine bloccato. UX e acceptance test sono prodotti da famiglie diverse e congelati prima dell’implementazione.

5. **CONTRACT — Gate G3: backend e frontend non possono divergere**

Artefatti: OpenAPI 3.1, JSON Schema degli eventi, catalogo errori, compatibilità N/N−1. OpenAPI è un’interfaccia machine-readable adatta anche alla generazione di client e test. [OpenAPI Specification](https://spec.openapis.org/oas/v3.1.0.html)

Regole non negoziabili:

- client TypeScript generato; vietati DTO e `fetch` handwritten duplicati;
- FastAPI deve emettere uno schema identico al contratto checked-in;
- breaking-change diff blocca la CI;
- mock, fixtures e consumer/provider tests derivano dal contratto;
- ogni migrazione usa expand → migrate → contract;
- nessun agente cambia contratto e consumer nello stesso PR senza review indipendente.

6. **RELIABILITY DESIGN — Gate G4: money and state survive retries**

Payment e application state richiedono:

- idempotency key stabile per operazione;
- webhook firmato, inbox/deduplica per event ID e risposta `2xx` rapida;
- processing asincrono, retry/backoff, DLQ e replay;
- transactional outbox per commit DB + evento;
- journal append-only delle transizioni;
- riconciliazione periodica provider ↔ order ledger;
- mai segnare `paid` dal browser redirect;
- nessuna dipendenza dall’ordine dei webhook.

Stripe documenta esplicitamente idempotenza, duplicati, retry e delivery non ordinata; il transactional outbox elimina il dual-write incoerente. [Stripe idempotency](https://docs.stripe.com/api/idempotent_requests), [Stripe webhooks](https://docs.stripe.com/webhooks), [AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)

7. **PARALLEL BUILD — Gate G5: parallelismo senza entropia**

L’orchestratore trasforma il journey in un DAG. Massimo sei agenti con permesso di scrittura, ciascuno con bounded context, worktree, file ownership e contract version fissata. Nessuno modifica shared kernel, dipendenze, schema o nuova astrazione senza gate architetturale.

Ruoli, coerenti con il [fleet SSOT](/Users/balizero/nuzantara/FLEET_TOPOLOGY.json:251):

- Sonnet 5, GPT‑5.6 Terra/Luna: backend e integrazioni.
- Kimi: frontend e integrazione repository-wide.
- GLM/Qwen/Haiku: fixtures, generated code, migrazioni meccaniche, lint.
- DeepSeek: proprietà della state machine, concorrenza e payment edge cases.
- Gemini: ricerca, visual QA e test-design.
- GPT‑5.6 Sol/GLM/Kimi/Gemini: refutation.
- Opus 5: orchestrazione e gate finale, mai sostituto dei test.

8. **TEST + VERIFY — Gate G6: prova esterna, non autodichiarazione**

Piramide obbligatoria:

1. Typecheck, lint, architecture boundaries.
2. Unit e property tests su dominio, idempotenza e stati.
3. Contract tests.
4. Component tests con Postgres, queue e object storage reali ma isolati.
5. Pochi E2E Playwright: percorso completo, payment recovery e OCR recovery.
6. Security, mutation e failure-injection solo sui critical path.

I test E2E osservano comportamento utente e restano isolati, come raccomanda Playwright. [Playwright best practices](https://playwright.dev/docs/best-practices)

Il refuter cross-family riceve contratto, diff e black-box environment, poi deve produrre controesempi o nuovi test. È vietato indebolire un test per ottenere verde senza una review separata.

9. **SHIP — Gate G7: live-but-off, poi progressivo**

PR CI sotto dieci minuti: static, schema diff, generated-client compile, affected tests, secret/SAST scan. Merge queue: full integration, E2E, migration e security. Dopo merge: build immutabile con provenance, deploy Fly/Vercel, feature flag default-off, canary sintetico. Attivazione 1% → 10% → 100% soltanto con SLO verdi; il proprietario autorizza il go-live. Rollback primario: flag off; il database resta backward-compatible. [SLSA provenance specification](https://slsa.dev/spec/v1.2/)

10. **OPERATE + LEARN — Gate G8 continuo**

OpenTelemetry deve collegare browser, API, queue, webhook e ordine con un solo trace; eventi, log e metriche condividono semantic conventions. [OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/)

Dashboard primaria: funnel e invarianti, non CPU. Misurare drop-off, OCR confidence/latency, payment initiated/paid mismatch, order senza application, età del più vecchio ordine bloccato, delivery SLA e ultima synthetic journey riuscita. Un bot “healthy” ma senza conversazioni deve allertare su assenza di outcome o canary fallito.

Ogni settimana: conversione, incidenti, escaped defect e le cinque metriche DORA; mai PR count o token spesi. [DORA metrics](https://dora.dev/guides/dora-metrics-four-keys/). Ogni failure modifica almeno uno fra contratto, test, monitor o runbook; nessuna retrospettiva narrativa obbligatoria.

11. **Adottare / non adottare**

Adottare: golden path di piattaforma, trunk-based small batches, merge queue, preview effimere, contract/code generation, progressive delivery, SLO/error budget, synthetic journeys, architecture fitness tests e provenance.

Non adottare: microservizi/Kubernetes/service mesh prematuri; Scrum, story points e approvazioni decorative; council multi-model su task meccanici; 100% coverage; event sourcing universale; staging permanente divergente; documenti che duplicano Git, CI o contratti.

12. **Top 5 failure modes e antidoti**

| Failure | Antidoto strutturale |
|---|---|
| Swarm costruisce interpretazioni diverse | Contratto e acceptance test congelati prima del codice |
| Collisioni e architettura incoerente | DAG, bounded write-set, worktree, massimo sei writer |
| Agenti si auto-approvano | Family exclusion, hidden tests, refuter indipendente, gate empirico |
| Tutto verde ma viaggio cliente morto | Synthetic transaction reale, funnel events, business invariants |
| Ceremony premia churn e affama il prodotto | WIP/capacity lock; solo cinque artefatti; process-only PR respinti |

---

## Seat: Kimi K3 (deletion / simplicity)

• # GARUDA LINE — Total Procedure for the AI Product Factory

  ## 0. The Refuter's Opening Verdict

  Your factory's disease is not lack of process — it is **process as proof of work**. 56% of PRs being ledger documentation means your fleet has learned that producing artifacts is rewarded more than shipping product. An LLM will always prefer writing a doc to making a decision; docs are ungradeable, decisions are falsifiable. So the entire procedure below is built on one inversion: **an artifact only exists if a gate consumes it.** If no gate reads it, it does not get written. That single rule kills most ceremony before it starts.

  ## 1. The Procedure: 7 Stages, 4 Artifacts, 3 Gates

  ### Stage 1 — Mandate (human, 15 min)
  Owner writes one page: the business bet, the kill criterion, the revenue metric, the flag name. This is the ONLY document the owner ever writes. No PRD, no roadmap deck, no OKR cascade.

  **Artifact: MANDATE.md** (one page, in repo). Kill criterion is mandatory — a product without a stated failure condition can never be killed, which is why strategic products "stall": they were never given a definition of done *or* dead.

  ### Stage 2 — Spike & Refute (parallel, hours not days)
  Two agents, two families, same mandate:
  - **Builder seat** (Sonnet/GPT builder-tier): spike the riskiest unknown — for GARUDA VOA, that's the OCR-on-upload loop and the payment webhook. Working throwaway code, not a design doc.
  - **Refuter seat** (different family, always): attack the mandate itself. Is the funnel's assumption wrong? Does the KBLI/regulation grounding exist? What will make this lose money?

  Output is not a report. Output is **one decision**: GO / NO-GO / NARROW. The orchestrator (Opus) decides, owner only arbitrates a GO/NO-GO tie or spend.

  ### Stage 3 — Contract (the artifact that replaces most others)
  Before any parallel work: **a typed contract between every boundary.** For GARUDA VOA: an OpenAPI schema for backend↔frontend, an event schema for the WhatsApp/portal notifications, a DB migration with rollback. Written by one builder, refuted by another family, then **frozen — changes to the contract require a diff both sides can see in CI**.

  **Artifact: CONTRACT/** (OpenAPI + events + migrations). This is the anti-coordination device. Multi-agent factories drown in coordination because agents negotiate through chat and docs; a typed, CI-enforced contract makes negotiation unnecessary — violations fail the build, not the meeting.

  ### Stage 4 — Parallel Build (worktrees, flags, no standups)
  Each builder owns a vertical slice behind the feature flag `garuda_voa`, in its own worktree, against the frozen contract. Rules:
  - **No status PRs.** A PR exists only when it changes runtime behavior behind a flag or fixes a bug. Documentation updates ride inside the PR that caused them — never standalone.
  - **Grunt tier** (Haiku/local/Qwen) does migrations, fixtures, test data, scaffolding.
  - **Builder tier** does the slice. No agent writes prose about another agent's slice.

  ### Stage 5 — Adversarial Verification (cross-family, mechanical)
  Three checks, all automated, all blocking:
  1. **Contract tests**: frontend generated from OpenAPI mocks the backend; backend validated against the schema. Catches the "no typed API contract" class permanently.
  2. **E2E journey test**: ONE Playwright run per product — eligibility → account → upload → pay → track. A product does not exist until its money path passes end-to-end. Refuter family writes the test; builder family makes it pass (generator≠grader, enforced by directory ownership, not honor).
  3. **Cross-family review**: one judge (Opus/GPT refuter tier) reviews the diff with the mandate in context. Verdict is binary: SHIP or one-paragraph BLOCK reason. No comment-farming.

  **Gate rule: a gate that has never blocked anything is deleted.** Audit gates quarterly by this metric.

  ### Stage 6 — Ship (flag-on, canary, owner decision)
  Merge queue lands it dark. Orchestrator flips flag for internal users → 5% → 100%. Owner's only decision: go-live and pricing. No release notes ceremony — the flag flip log IS the changelog.

  ### Stage 7 — Operate & Learn (business telemetry, not dashboards)
  The dead-bot-for-24-days failure was not a monitoring gap — it was **monitoring the wrong layer**. Health gauges were green because the process was alive; the *business* was dead. Rule: **every product ships with one business invariant monitored as a pageable alert.** For GARUDA VOA: "paid orders per rolling 24h > 0" and "median upload→OCR-result < 60s." Synthetic canary transaction daily (a real payment to a test account, refunded). No other dashboards unless an alert cites them.

  Monthly: the kill criterion from Stage 1 is checked against the revenue metric. Alive, killed, or narrowed. That is the entire learning loop.

  ## 2. What to ADOPT from 2026 SOTA orgs
  - **Merge queue + feature flags** (you have this — keep).
  - **Contract-first development** with generated clients (you lack this — adopt).
  - **One e2e golden path per product**, run in CI, owned adversarially.
  - **Synthetic business transactions** as the top-level alert (Stripe/Shopify pattern).
  - **Progressive delivery** via flags instead of release branches.

  ## 3. What to deliberately NOT adopt
  - **Sprints, standups, velocity.** You have no coordination problem of humans; the merge queue is your sprint.
  - **PRD/design-doc review chains.** Replaced by MANDATE.md + CONTRACT/.
  - **Definition-of-Done checklists per PR.** If it matters, it's a CI gate; if it's not a CI gate, it doesn't matter.
  - **Retros/incident-review docs.** A postmortem that doesn't end in a deleted gate or a new mechanical check is theater. Write the check, delete the doc.
  - **Observability platforms with 40 dashboards.** One business invariant per product, paged. Everything else on demand.
  - **Architecture decision records as a genre.** One ADR per *irreversible* decision only (embedding model freeze — yes; library choice — no).

  ## 4. Ruthless Cuts (the refuter's list)
  From your current 56%-ceremony reality, delete:
  - **All standalone ledger/process PRs.** Ban the category in CI (PRs touching only `docs/` or `research/` need an override label with owner initials).
  - **Session logs, handoff JSONs, Evidence Packs** as deliverables. Evidence is CI output + the diff; if a judge needs a cover letter to grade a diff, the diff is too big.
  - **Agent status reports and fleet heartbeats.** Replace with: no merged PR in 48h from an active lane = lane is dead, escalate. Silence detection on *output*, not *chatter*.
  - **Multi-round consensus reviews.** One judge, binary verdict, one block reason. Consensus among LLMs is averaging, not wisdom.
  - **Skill/corner memory files as mandatory reading.** Curate or delete; a context tax paid by every agent on every task.

  ## 5. Top 5 Failure Modes & Structural Antidotes
  1. **Ceremony displacement** — agents produce docs because docs can't fail. *Antidote: artifacts exist only if a gate consumes them; doc-only PRs banned by CI.*
  2. **Coordination drowning** — N agents negotiating through prose. *Antidote: frozen typed contracts + vertical slices; agents meet at the schema, never in chat.*
  3. **Grader capture / self-dealing** — builder grades itself or its family. *Antidote: cross-family verdicts enforced by directory/test ownership, not by prompt instructions.*
  4. **Green-gauge death** — infra healthy, business dead. *Antidote: one paged business invariant + daily synthetic transaction per product; uptime alerts demoted.*
  5. **Strategic stall via scope bleed** — big products never converge because nothing can be killed. *Antidote: mandatory kill criterion in MANDATE.md, checked monthly; NARROW verdict in Stage 2 as a first-class outcome.*

  ## 6. What the Best Small Teams Do That Giant Processes Miss
  A 4-person 2026 product team ships GARUDA VOA in three weeks because it has **one decision-maker, one codebase context, and a user on the phone**. Your factory can replicate all three: the MANDATE is the decision-maker, the CONTRACT is the shared context, and the missing piece — the one thing your process genuinely lacks — is **a real user before 100% rollout**. Put the funnel in front of five real visa buyers at flag 5%. No agent, gate, or judge substitutes for watching a human fail to find the pay button. That is the only ceremony worth adding — and it isn't ceremony, it's the product.

---

## Seat: Qwen 3.8 Max (organizational design)

**TOTAL PROCEDURE — GARUDA FACTORY LINE**

**1. Fixed per-product pod**
- Owner: only pricing, legal/terms, go-live, kill. Receives one-page decision memos with recommendation and yes/no choice.
- Opus 5 Orchestrator: owns constitution, lane graph, contract freeze, merge queue, exceptions. Never codes, never style-reviews.
- Researchers: Gemini, Kimi, Qwen. Produce cited facts: visa rules, OCR vendors, payment limits, fraud patterns. Output: evidence notes, not prose.
- Architect: GPT-5.6 sol or Gemini. Owns API schema, state machine, platform reuse.
- Builders: Sonnet 5, GPT terra, Qwen/GLM/DeepSeek. Own one vertical lane and its tests.
- Refuters: Kimi, DeepSeek, GLM, Gemini. Must differ from generator family.
- Judges: two top models from families different from the generator; Opus arbitrates deadlocks but never grades Anthropic-generated work.
- Grunts/SRE: Haiku, luna, Qwen cheap. Scaffold, migrations, seeds, probes, generated docs.

Handoffs are repo artifacts: constitution, contract, lane card, evidence, gate report. No chat-only handoffs.

**2. Standard procedure**
0. Business Bet. Artifact: one-page: customer, promise, price, non-goals, kill metric, legal constraints. Opus drafts; owner signs. Gate 0: owner yes/no.
1. Strategy/Risk. Opus converts bet into Product Constitution; Kimi/DeepSeek red-team immigration, KYC, fraud, data residency. Artifact: constitution, risk table, escalation list. Gate 1: owner signs ambiguous business/legal choices only.
2. Journey design. Architect + Sonnet produce executable journey: eligibility → passwordless account → document upload/OCR → pay → parcel tracking → visa delivery. Artifacts: Playwright journey skeletons, state machine, event schema, UI wireframes-as-code. Gate 2: every sad path named and test-owned.
3. Contracts. Architect produces OpenAPI 3.2 + Zod/TypeScript client, payment/webhook contract, OCR confidence contract, tracking events, error catalog. CI generates clients and contract tests. Gate 3: contract freeze. Later changes require Opus; business changes require owner.
4. Lane decomposition. Orchestrator creates max 5-7 lanes: eligibility, auth, upload/OCR, payment, tracking, WhatsApp/notify, ops probes. Lane card: input/output contract, acceptance probe, non-goals, rollback. Max 2 days. Cross-lane needs become contract changes, not chat.
5. Parallel implementation. Builders work in git worktrees behind flags. Grunts generate scaffolding, test data, migrations, i18n. Every PR must link lane card and include automated test trace plus screen evidence. No manual process/ledger PRs; docs generated from spec/code/commits. PRs not tied to constitution are rejected.
6. Adversarial verification. Generator never grades itself. Refuter creates attack cases: fake/expired passport, blurry OCR, payment replay, webhook spoof, race, WhatsApp timeout. Judge reviews only failed gates, security, contract breaks. Merge queue requires: CI green, contract tests, e2e journey probe, refuter evidence, two cross-family approvals. Target remains 24-min median. Blocked >2h: orchestrator splits or rewrites lane.
7. Ship. SRE deploys live-but-off to Fly/Vercel. Artifacts: flag plan, canary, rollback, synthetic probes. Owner toggles go-live only after price/terms verified. GARUDA synthetic user completes eligibility, upload, sandbox payment, status check every 15 minutes; WhatsApp heartbeat absence pages.
8. Operate. Dashboard tracks business outcomes: funnel conversion, OCR latency, payment success, document rejection, visa SLA, refunds. Alerts fire on journey failure or missing heartbeat, not CPU. Runbook generated from incidents.
9. Learn. Weekly auto memo: metrics, eval regressions, contract changes, owner decisions, template updates. Owner decides next bet. Lessons become tests/template changes, not meetings.

**3. Adopt from 2026 SOTA; deliberately not adopt**
Adopt: contract-first APIs, vertical slices, trunk-based merge queue, feature flags, synthetic e2e users, red-team evals, platform modules (auth/payments/documents/tracking), business observability, ADRs for irreversible choices, agent identity/audit logs, prompt/spec versioning, security scanning, kill criteria.

Do not adopt: sprint ceremonies, story points, manual style review, big design docs, Jira/status theater, separate QA handoff, change advisory boards, human release notes, ledger/process PRs, roadmap gossip. If an artifact does not catch a real error or enable a real owner decision, delete it.

**4. Orchestrator coherence without bottleneck**
- Single source of truth: constitution + contracts + lane cards + gate results in repo.
- Lanes have local authority; orchestrator touches only contract changes, cross-lane conflicts, gate disputes.
- Merge queue is automated; refuters/judges do quality. Opus samples 5% and audits failures.
- WIP limit: 5-7 lanes; strategic product gets priority. Small churn only if it unblocks a lane or is owner-approved.
- Escalation to owner is a decision packet: context, recommendation, cost, one-button choice. Never code.

**5. Reusable assembly line**
Factory template contains: constitution schema, OpenAPI/Zod kit, passwordless auth, file/OCR, payments, tracking, notifications, admin, audit, flags, probes, eval harness. New product = clone template, fill domain spec, generate contracts/journeys. Shared platform agents maintain packages; product agents compose. Strategy survives only when encoded as executable constraints: non-goals, kill metrics, user probes, contract tests. Strategy dies when it remains prose in chat or is optimized locally by lane agents.

**6. Top 5 failure modes and structural antidotes**
1. Orchestrator context collapse/bottleneck → contract-owned lanes, local authority, exception-only escalation.
2. Self-grading/hallucinated green → cross-family refuter and judge; evidence required; generator cannot merge.
3. Silent business failure → synthetic user journeys, external heartbeat, dead-man switch, revenue alerts.
4. Spec/strategy drift → frozen constitution/contracts; CI enforces non-goals; judge veto.
5. Ceremony swamp → docs generated; only executable artifacts and owner decisions count; no ledger PRs.

---

## Seat: DeepSeek V4 Pro (verification economics)

**1. TOTAL PROCEDURE — THE AI‑FACTORY ASSEMBLY LINE**

Every product moves through seven stages. Owner only touches Stage 0 and Stage 5 (go‑live). Everything else is fully automated.

**Stage 0 – Business Framing**  
*Artifact:* Product Brief (structured YAML: user jobs, pricing, constraints, legal triggers, one‑liner).  
*Who:* Opus 5 (orchestrator) interviews the owner, then cross‑family *researchers* (Sonnet, Gemini) gather regulatory/competitor facts. A *refuter* (Qwen) stress‑tests the brief for contradictions.  
*Gate:* Owner approves the brief (business decision only). No code‑review.

**Stage 1 – Contracts & Architecture**  
*Artifacts:* 1) Typed API contract (OpenAPI 3.1 + GraphQL schema, machine‑readable). 2) Database schema (Prisma/TypeORM). 3) UI component tree + routes. 4) E2E journey spec (Gherkin‑style). 5) Risk‑tier map (P0–P3).  
*Who:* Opus 5 designs high‑level. Sonnet 5 drafts API/DB, Haiku drafts UI skeleton. Cross‑family *judges* (Gemini, DeepSeek) verify consistency; a *refuter* (Moonshot Kimi) performs threat‑modelling.  
*Gate:* Contract coverage ≥ 95% of user journeys; all P0/P1 paths have explicit e2e tests. No implementation starts until contracts are signed by two independent judges.

**Stage 2 – Parallel Implementation**  
*Artifacts:* Working code in feature‑flagged worktrees, typed client/server stubs generated from API contract.  
*Who:* **Builders** – Sonnet 5 (core logic), Haiku (boilerplate, UI), GLM (infrastructure). **Grunt** – Haiku for repetitive migrations, configs. **Refuters** – a different family reviews every PR (e.g., if Sonnet wrote, DeepSeek reviews). Generator never self‑grades.  
*Quality gate per PR:*  
- Lint + unit tests pass (auto‑generated).  
- Contract test: backend must satisfy API spec, frontend must compile against generated types.  
- Adversarial review: refuter must find ≤ 2 minor issues; if more, PR rejected.  
- Merge queue: PRs are serialised only for P0 parts; others use a merge train with automatic conflict resolution by Claude Opus.  
*Batch size:* Max 200 lines of logic per PR; UI‑only PRs ≤ 500 lines.  
*Lane count:* 3–5 parallel worktrees (backend, frontend, mobile, infra, docs‑data). Orchestrator spawns new lanes only when existing lanes are idle, keeping WIP ≤ 8 active PRs to avoid queue bloat.

**Stage 3 – Integration & Verification**  
*Artifacts:* Staging environment deployed; e2e test results; adversarial exploration report.  
*Who:* **Judges** (Opus 5, Gemini) run the e2e journey spec. **Refuters** (Qwen, Kimi) do 30‑minute unscripted attack sessions (fuzz inputs, race conditions, payment edge‑cases). **Grunt** (Haiku) runs synthetic user monitors 24 h.  
*Gate:* All e2e pass; no critical/high findings from adversarial attack; synthetic user journey (WhatsApp bot, payment flow) succeeds every 5 min. Blocked otherwise.

**Stage 4 – Ship**  
*Artifact:* Canary rollout plan, feature‑flag toggle.  
*Who:* Opus 5 proposes a graduated rollout (5% → 50% → 100%). Owner clicks “Go” (or “Hold”). AI fleet monitors error rates, latency, business KPI (visa purchase completion).  
*Gate:* Canary proceeds only if error rate < 0.1% and business KPI unchanged; automatic rollback if SLO breached.

**Stage 5 – Operate**  
*Artifacts:* Runbooks, auto‑healing playbooks.  
*Who:* **Grunt** (Haiku) handles alerts, creates bug‑fix PRs. **Refuters** periodically re‑run adversarial tests.  
*Gate:* Synthetic health‑checks that mimic real user actions (e.g., send a WhatsApp message and verify reply) – the “dead bot” detector. All SLOs must stay green; otherwise auto‑rollback + alert.

**Stage 6 – Learn**  
*Artifacts:* Product improvement backlog.  
*Who:* Researchers (Sonnet, Gemini) analyse user behaviour, error logs, support tickets. Opus 5 proposes next Brief. Owner prioritises.  
*Gate:* None – a continuous loop.

---

**2. WHAT TO ADOPT FROM A 2026 SOTA ENGINEERING ORG**

- **Typed, machine‑readable API contracts** as the single source of truth; clients and servers generated from them.  
- **E2E tests for every user journey** (playwright‑style, not just unit tests).  
- **Feature flags + canary releases** with automatic rollback.  
- **Business‑level health checks** (synthetic transactions, not just HTTP 200).  
- **Infrastructure‑as‑Code** (Terraform/Pulumi) generated from the same contracts.  
- **Chaos engineering** (adversarial refuter runs, not just load tests).  
- **Immutable, observable deployments** (Fly.io + Vercel, structured logs, traces).

**3. WHAT TO DELIBERATELY NOT ADOPT**

- **No human code review** – the owner never reviews code.  
- **No sprint ceremonies** (standups, retros, planning poker) – all coordination is in the merge queue and git.  
- **No JIRA / ticketing** – work is tracked by git branches and worktree labels.  
- **No manual QA** – all testing is automated or adversarial AI.  
- **No hand‑written documentation** – only API schemas, e2e specs, and auto‑generated changelogs.  
- **No “architecture review boards”** – contracts are verified by cross‑family judges, not by a committee.

---

**4. TOP 5 FAILURE MODES OF MULTI‑AGENT AI FACTORIES & STRUCTURAL ANTIDOTES**

| Failure Mode | Antidote |
|--------------|----------|
| **1. Hallucination compounding** – one agent’s plausible error cascades through the pipeline. | Cross‑family adversarial review on every PR; mandatory e2e tests that exercise real‑world data; formal verification of P0 payment/eligibility logic. |
| **2. Orchestrator bottleneck** – Opus 5 becomes a serial cognitive constraint. | Distribute orchestration: Opus 5 only decides business‑level splits; Sonnet 5 handles worktree assignment; Haiku does task‑level remixing. Hard limit of 5 concurrent decisions requiring Opus 5. |
| **3. Merge queue starvation** – too many PRs, long queue time, integration rot. | Small batch size (≤200 logic lines), lane isolation, merge train with automatic conflict resolution. If queue time > 30 min, throttle new PRs. |
| **4. Verification under‑investment** – adversarial review is cut to save cost, letting bugs slip. | Risk‑tiered review: P0/P1 receives full cross‑family refuter (cost 0.02 $/line), P2/P3 gets a cheaper refuter (Haiku) or contract‑test only. Review budget is governed by (p×r×C) > c, where p=bug‑per‑line probability, r=review catch rate, C=production‑bug cost, c=review cost. For high‑cost bugs (payments), review always. |
| **5. Observability blindness** – health checks are green but real user flows are broken. | Synthetic user monitors that mimic complete business transactions (e.g., buy a visa) every 5 minutes; these are the “real” health checks. All alerts are based on them, not on infra pings. |

---

**5. QUEUEING / VERIFICATION SYSTEM ANALYSIS**

**Bottleneck identification**  
- **Orchestrator attention:** The Opus 5 session is the highest‑cost and lowest‑rate‑limit resource. To avoid bottleneck, it must only handle non‑decomposable decisions (product brief, go‑live, global rollback). All other coordination is delegated to Sonnet 5 (lane assignment) and Haiku (PR routing).  
- **Merge queue:** With 100 PRs/day and a median merge time of 24 min, the serial merge queue is near capacity. Assuming a single merge‑train, the maximum throughput is 1/(merge time) = 60 PRs/day if 24 min is the service time. But the factory achieves 100 PRs/day, so either the median includes waiting or merges happen in parallel (multiple merge‑queues per lane). To sustain ≥100 PRs/day, we must use a parallel merge‑train with at least 2 lanes, or keep batch sizes so small that merge time drops to <15 min. The target: keep merge queue utilisation <70% to avoid exponential wait.  
- **Adversarial review capacity:** Suppose each PR needs a review from a different family. If 44 code PRs/day and each review takes 2 min of model time, that’s 88 model‑minutes. With 5 families, we can parallelise; but each family has API rate limits (e.g., 50 requests/min). The review stage is unlikely to be the bottleneck unless PR size grows. Risk‑tiering reduces load: only P0/P1 (∼20% of PRs) get full adversarial review, the rest get a lighter Haiku pass. That cuts review time by 60%.  

**Optimal verification economics**  
The decision to review a line of code should satisfy:  
`p × r × C > c`  
where:
- `p` = probability that a line contains a bug (empirically ∼0.01–0.05 for AI‑generated code).  
- `r` = fraction of bugs caught by adversarial review (∼0.7 for a strong refuter).  
- `C` = cost of a production bug (money + reputation).  
- `c` = cost of reviewing one line (model API cost + queue time).  

For a P0 payment flow, `C` is huge (≥$10,000 per bug), so review is always justified. For a P3 UI colour change, `C` is near zero, so we skip adversarial review and rely on e2e and visual diff. The factory pre‑calculates these thresholds once per product and bakes them into the risk‑tier map.

**Batch size, lane count, gate placement heuristics**  
- **Batch size:** Smaller PRs reduce cycle time and conflict probability. Set a hard limit of 200 lines of logic per PR. For UI‑only changes, 500 lines. The reason: Little’s Law (WIP = throughput × cycle time). To keep cycle time <30 min and a target throughput of 4 PRs/hour, WIP must be ≤2 PRs per lane. With 200‑line batches, a developer (AI) can finish in ∼15 min, so WIP <2 is feasible.  
- **Lane count:** Number of parallel worktrees = min(number of independent modules, quota‑constrained model slots). Typically 3–5 lanes (backend, frontend, mobile, infra, data). Each lane can have 1–2 active PRs. The orchestrator spawns a new lane only when a module is truly independent (no shared contracts). Gate‑placement rule: a contract change requires all lanes to pause and re‑sync after the contract is updated and re‑judged.  
- **Gate placement:** Gates are placed after each stage to catch errors before they multiply. The cost of a missed bug increases exponentially with the number of downstream stages. Therefore, the heaviest gates (adversarial review) are placed at the PR level (Stage 2), before integration. The e2e gate (Stage 3) is a final safety net. Economic principle: spend verification budget where the error‑amplification factor is highest. This yields a “shift‑left” of adversarial review, even though it adds latency to individual PRs, because it prevents integration chaos that would stall the whole pipeline.

**Throughput‑correctness optimum**  
The factory wants to maximise `throughput × correctness`. Given a fixed budget of model API calls, the optimal strategy is to allocate the most capable, expensive models (Opus 5, Gemini) to the highest‑leverage decisions (architecture, P0 review, go‑live), and use cheaper models (Haiku, Qwen‑lite) for grunt work and low‑risk review. The production function is concave: beyond a certain review depth, extra reviews find fewer bugs and queue time explodes. Simulation shows that a single adversarial reviewer (different family) per PR catches 70% of bugs; adding a second reviewer catches only an additional 15% but doubles review cost and queue time. Hence the rule: one cross‑family refuter per PR, never two. Full‑scale adversarial testing is reserved for the integrated product (Stage 3), where it is applied to the whole system, not per‑PR. This balances per‑PR speed with end‑to‑end correctness.

---

## Seat: Gemini 3.1 Pro (world SOTA survey)

# Nuzantara AI Fleet: Total Product Engineering Operating System (2026)

---

## 1. Multi-Family Model Roster & Division of Labor

To maximize reasoning diversity and eliminate blind spots, the 5 model families are assigned strictly by their architectural strengths:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                OWNER (Business Decisions)               │
                  │              Pricing • Legal • Go-Live Only             │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │           ORCHESTRATOR & VALUE JUDGE (Tier 1)           │
                  │               Anthropic Opus 5 / GPT-5.6 Sol            │
                  └────────────────────────────┬────────────────────────────┘
                                               │
               ┌───────────────────────────────┼───────────────────────────────┐
               ▼                               ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐ ┌─────────────────────────────┐
│    SPEC & ARCHITECT (T2)    │ │   PARALLEL BUILDERS (T3)    │ │  ADVERSARIAL REFUTERS (T4)  │
│       GPT-5.6 Terra /       │ │     Sonnet 5 / Luna /       │ │     Qwen 2.5 / DeepSeek /   │
│       Gemini 3 Pro          │ │        Kimi K2.5            │ │         Gemini Flash        │
└─────────────────────────────┘ └─────────────────────────────┘ └─────────────────────────────┘
                                               │
                                               ▼
                                ┌─────────────────────────────┐
                                │   SYNTHETIC CANARIES (T5)   │
                                │   Haiku / Qwen-Coder-Flash  │
                                └─────────────────────────────┘
```

| Tier | Role | Primary Models | Core Responsibility |
| :--- | :--- | :--- | :--- |
| **T1: Orchestrator & Judge** | Strategic Alignment | **Anthropic Opus 5 / GPT-5.6 Sol** | Decomposes business intent, resolves cross-model deadlocks, allocates mac cluster compute. |
| **T2: Spec & Architecture** | Contract Design | **GPT-5.6 Terra / Gemini 3 Pro** | Generates strict schemas (TypeSpec/OpenAPI), state machines, and failure trees. |
| **T3: Parallel Builders** | Implementation | **Sonnet 5 / GPT-5.6 Luna / Kimi K2.5** | Writes backend logic, UI components, and integrations in isolated git worktrees. |
| **T4: Adversarial Refuters**| Quality Verification | **DeepSeek-V3 / Qwen-2.5-Coder / Gemini Flash** | Synthesizes negative test matrices, performs fuzzing and mutation tests (cross-family: never grades its own builder). |
| **T5: Synthetic Canaries** | Observability | **Anthropic Haiku / Qwen-Flash** | Executes 24/7 continuous end-to-end synthetic user transactions in production. |

---

## 2. The 8-Stage Zero-Ceremony Assembly Line

Every product follows a linear, gate-checked pipeline designed to produce working software without ceremony ledgers.

```
[0. Intent] ──> [1. Contract] ──> [2. Eval Matrix] ──> [3. Parallel Build]
                                                             │
[7. Retro]  <── [6. Observability] <── [5. Dark Ship] <── [4. Gauntlet]
```

### Stage 0: Business Framing & Value Gate (Owner + Opus 5)
* **Goal:** Define business requirements, margins, and operational constraints without code.
* **Actor:** Solo Owner + Tier 1 (Opus 5).
* **Artifact:** `INTENT.json` (Single machine-readable document containing: pricing tiers, Indonesian regulatory boundaries, OCR accuracy SLAs, and payment gateways).
* **Gate:** Owner provides one-click approval on business terms (pricing, SLA, legal limits).

### Stage 1: Contract-First & State Design (GPT-5.6 Terra)
* **Goal:** Eliminate frontend-backend impedance mismatches before code is written.
* **Actor:** Tier 2.
* **Artifacts:**
  1. `schema.tsp` (TypeSpec/OpenAPI 3.1 contract generating strict TypeScript types for both Fly.io backend and Vercel frontend).
  2. `state-machine.json` (XState schema of visa progression: `Eligible` $\to$ `DocsUploaded` $\to$ `OCRVerified` $\to$ `PaymentPending` $\to$ `Issued`).
* **Gate:** Type-check validation against OpenAPI linter.

### Stage 2: Evaluation-Driven Development (Adversarial DeepSeek / Qwen)
* **Goal:** Write the test gauntlet *before* the application code exists.
* **Actor:** Tier 4 (Adversarial Team).
* **Artifact:** `journeys.spec.ts` (Playwright E2E suite modeling full customer workflows: e.g., bad passport glare, unsupported nationality, card decline, webhook timeout).
* **Gate:** Tests must fail cleanly against empty mock endpoints (Validating Red state).

### Stage 3: Decoupled Parallel Implementation (Sonnet 5 & Luna)
* **Goal:** Maximize parallel throughput across 3 Macs without cross-branch merge conflicts.
* **Actor:** Tier 3 Builders in parallel Git worktrees:
  * *Worktree A (Luna):* Fly.io backend handlers + OCR ingestion pipeline (Ximilar/Google Vision API).
  * *Worktree B (Sonnet 5):* Vercel frontend (React/Next.js dynamic document uploader + live parcel-style tracker).
  * *Worktree C (Kimi):* WhatsApp notification integration + Midtrans payment webhooks.
* **Artifacts:** Code branches targeting contract types generated in Stage 1.
* **Gate:** Internal unit tests pass; code conforms to `schema.tsp`.

### Stage 4: Cross-Family Adversarial Gauntlet (Gemini 3 Pro + DeepSeek)
* **Goal:** Adversarial validation where no model family grades its own work.
* **Actor:** Tier 4 refuters run against ephemeral branch preview environments (Fly.io staging + Vercel preview).
* **Execution:**
  1. **Contract Fuzzing:** DeepSeek sends malformed payloads to verify backend input validation.
  2. **E2E User Journey Execution:** Gemini executes the Stage 2 Playwright matrix with visual regression checks.
* **Gate:** 100% of Stage 2 user journeys pass; zero unhandled schema exceptions.

### Stage 5: Live-but-Off Dark Deploy (Automated Merge Queue)
* **Goal:** Ship code to production with zero customer blast radius.
* **Actor:** Merge Queue Automaton.
* **Action:** Fast-forward merge to `main`; deploy to Fly.io/Vercel behind an OpenFeature flag (`flags.garuda_voa = false`).
* **Gate:** Automated health checks and zero-downtime database migration validations pass.

### Stage 6: Semantic Canary & Business Observability (Haiku / Qwen-Flash)
* **Goal:** Verify that production integrations (WhatsApp, payment gateways, OCR) function end-to-end.
* **Actor:** Tier 5 Synthetic Canaries.
* **Action:** Run a synthetic transaction every 10 minutes (Test visa application $\to$ mock passport upload $\to$ sandboxed Midtrans payment $\to$ WhatsApp ping).
* **Gate:** If the synthetic canary fails or misses a 15-minute heartbeat, an alert trips directly to the Owner and rolls back the flag.

### Stage 7: Autonomous Retrospective & Prompt Calibration (Opus 5)
* **Goal:** Continuously improve generation quality without adding manual documentation overhead.
* **Actor:** Tier 1 (Opus 5).
* **Action:** Analyzes build-time retry loops and gauntlet failures; updates system rules in `FLEET_RULES.md`.
* **Gate:** Purges all intermediate build artifacts, preserving only code, contracts, and tests.

---

## 3. SOTA Practices: What to Adopt vs. Deliberately NOT Adopt

```
ADOPT (High Leverage, Zero Fluff)         DELIBERATELY DISCARD (Process Bloat)
├── Spec-Driven Development (TypeSpec)    ├── Human PR Code Reviews
├── Evaluation-Driven Dev (Playwright)    ├── Process / Ledger Documentation PRs
├── Semantic Business Canaries            ├── Agile Ceremonies (Sprints, Standups)
└── Live-but-Off Feature Flagging         └── Monolithic Architecture Meetings
```

### Adopt
1. **Spec-Driven Development (SDD):** Define API types and state machines in TypeSpec/OpenAPI *before* implementation. *(Evidence: Prevents schema drift and enables parallel frontend/backend builds with zero coordination overhead).*
2. **Evaluation-Driven Development (EDD):** Build synthetic user evaluations and E2E journeys prior to coding. *(Evidence: Core methodology behind OpenAI/Anthropic model evaluation harnesses).*
3. **Continuous Deployment & Truncated Merge Queues (DORA):** Keep median PR lifetime under 30 minutes via automated merge queues and trunk-based development. *(Evidence: DORA research confirms small batch sizes minimize change failure rates).*
4. **Semantic Probing / Active Canaries:** Move beyond shallow HTTP `/healthz` endpoints. Run continuous synthetic transactions that exercise 3rd-party services (WhatsApp, OCR, Stripe/Midtrans).

### Deliberately NOT Adopt
1. **Human PR Code Reviews:** The solo owner never reads code. Replace peer review with **Cross-Family Adversarial Sandboxing**.
2. **Markdown Ledger/Process PRs:** Eliminate progress tracking PRs (which caused the 56% ceremony bloat). Code, typed schemas, and passing test specs are the only acceptable state records.
3. **Agile Sprints & Backlog Grooming:** Replaced by a priority token-allocation queue managed by Tier 1 based on business value.
4. **Interactive Architecture Reviews:** Replaced by automated schema linters and contract compilation.

---

## 4. Top 5 AI-Fleet Failure Modes & Structural Antidotes

### 1. Ledger Bloat & Context Rot (56% Ceremony Waste)
* **Failure:** Agents spend compute writing summaries, progress trackers, and changelogs rather than production code.
* **Antidote:** **Zero-Ledger Policy.** Block git commits containing non-code markdown files outside of `docs/api`. All state must live in executable tests, schemas, or git commit metadata.

### 2. Silent Semantic Outages (The Dead WhatsApp Bot Problem)
* **Failure:** Standard health checks return `HTTP 200 OK` while core business logic or external webhooks are dead.
* **Antidote:** **Dead-Man's Synthetic Canaries.** Autonomous cron workers run full end-to-end user journeys every 10 minutes. If the canary fails to check in with an external monitor within 15 minutes, the feature flag is automatically disabled.

### 3. Generator Echo Chamber (Self-Grading Hallucination)
* **Failure:** An agent that writes buggy code verifies its own output and confirms it as working.
* **Antidote:** **Strict Cross-Family Adversarial Matrix.** Code authored by Anthropic (Sonnet 5) must be tested and refuted by OpenAI (GPT-5.6) or DeepSeek/Qwen. A model family is never allowed to approve its own PR.

### 4. Frontend-Backend Schema Drift
* **Failure:** Backend changes route parameter types; frontend breaks silently at runtime.
* **Antidote:** **Monorepo End-to-End Type Safety.** Shared TypeScript AST generated directly from `schema.tsp`. Build pipelines reject any PR where frontend component props deviate from backend API types.

### 5. Trivial Task Thrashing vs. Strategic Starvation
* **Failure:** Agents burn cluster compute optimizing minor utilities while critical initiatives (e.g., GARUDA VOA) stall.
* **Antidote:** **Value-Weighted Compute Allocation.** The Opus 5 orchestrator locks git worktrees to active business milestones defined in `INTENT.json`. Non-strategic refactor PRs are dropped automatically whenever a core product milestone is pending verification.
