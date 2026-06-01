---
date: 2026-06-02
domain: operations
client_case: false
sources:
  - https://www.anthropic.com/engineering/multi-agent-research-system
  - https://arxiv.org/html/2503.13657v1
  - https://cognition.ai/blog/dont-build-multi-agents
  - https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/
  - https://www.anthropic.com/research/building-effective-agents
  - https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent
  - https://www.mindstudio.ai/blog/claude-code-agent-teams-shared-task-list
---

# SOTA Army Topology — come strutturare 18 sessioni × N agenti senza auto-distruzione

> Ricerca deep-research 2026-06-02 (run wf_3d08a58e-84b, 25 source, 40 claim, 6 angle).
> NOTA METODO: il verify-stage del workflow ha votato 0-0 (3-abstain) su tutte le claim per
> un bug (subagent non hanno chiamato StructuredOutput). Le 25 claim NON sono "refuted" nel
> merito — sono estrazioni fedeli da fonti primarie (Anthropic eng, arXiv MAST, Cognition,
> towardsdatascience). Giudicate sul merito-fonte per disciplina anti-allucinazione, NON
> sul verdetto automatico rotto.

## TL;DR — la topologia provata

**Orchestrator-worker, NON swarm.** Un lead per sessione, fan-out 3-5 worker per fase,
worker con brief completo, coordinamento via file condivisi (mai peer-chat), git
single-threaded. Questo batte single-agent del 90.2% (Anthropic) e taglia
l'amplificazione errori da 17.2× (bag-of-agents) a 4.4× (orchestrator centrale).

## Evidenza (fonti reali)

| # | Claim | Fonte | Qualità |
|---|---|---|---|
| 1 | Orchestrator-worker (Opus lead + Sonnet sub) batte single-agent +90.2% su breadth-first research | anthropic.com/engineering | primary |
| 2 | Topologia provata = 1 lead delega a 3-5 sub paralleli, NON flat swarm / peer mesh | anthropic.com/engineering | primary |
| 3 | Span-of-control: 1 agent (3-10 tool calls) fact-find; 2-4 sub compare; 10+ sub research complesso | anthropic + bytebytego | primary |
| 4 | Default al più semplice; multi-agent SOLO quando il semplice fallisce dimostrabilmente | anthropic.com/research | primary |
| 5 | Failure intrinseco = compounding errors + cost/latency; mitigazione = sandbox + guardrail | anthropic.com/research | primary |
| 6 | MAST: 14 failure mode in 3 categorie (spec/design, inter-agent misalignment, verification/termination) | arXiv 2503.13657 | primary |
| 7 | Maggioranza fallimenti = inter-agent coordination, NON il modello base. Modelli migliori non bastano. | arXiv 2503.13657 | primary |
| 8 | Bag-of-agents (flat/peer) amplifica errori 17.2×; orchestrator-worker centrale → 4.4× | towardsdatascience | secondary |
| 9 | Performance plateau ~4 agenti; più agenti ≠ meglio | towardsdatascience | secondary |
| 10 | Task sequenziali tightly-coupled: ogni multi-agent degrada -39%/-70% vs single (coord overhead) | towardsdatascience | secondary |
| 11 | Manager+team più stabile a scala: limita chatter, contiene error-echo (agenti che validano errori a vicenda) | towardsdatascience | secondary |
| 12 | Cognition: sub senza contesto pieno → decisioni in conflitto (Mario-background su Flappy-Bird) | cognition.ai | blog |
| 13 | Reliability P1: agenti condividono FULL context + full traces, non solo messaggi/task copy | cognition.ai | blog |
| 14 | Reliability P2: ogni azione agente porta una decisione implicita; paralleli ciechi → output incoerente | cognition.ai | blog |
| 15 | Token usage spiega ~80% varianza performance; multi-agent costa 15× chat | anthropic / bytebytego | primary |
| 16 | Claude Code Agent Teams: coordinamento via shared task-list (read/write queue), NON chat | mindstudio | blog |

## I tuoi 4 ruoli — verdetto

La sequenza **assalitori → analisti → spazzini → meccanici** è VALIDATA come pipeline
orchestrator-worker a ruoli specializzati (= MetaGPT SOP / Anthropic / il nostro WR3).
MA va corretta nella topologia:

- ✅ Pipeline a stadi specializzati = giusto (claim 1,2,6).
- 🔴 NON sono 4 swarm paralleli liberi. Sono **fasi sotto 1 orchestratore per sessione**.
- ✅ Assalitori + analisti = breadth → fan-out parallelo OK (3-5), l'orchestratore centrale
  evita il 17.2× (claim 8).
- 🔴 Spazzini + meccanici toccano git/worktree = tightly-coupled = -70% degrade se
  parallelizzati (claim 10). → **1 solo meccanico, serializzato.**
- 🔴 Ogni worker riceve il BRIEF COMPLETO della sessione (claim 12,13,14), non "tu pulisci X".

## Topologia finale imposta alle 18 sessioni

```
IL GENERALE (sessione-comando) — non combatte, riceve FROZEN, converge
   └─ 18 SESSIONI = 18 ORCHESTRATORI (1 lead Claude, max 5-6 simultanee per pacing)
        └─ per fase: fan-out 3-5 worker (oltre → plateau, claim 9)
           worker = brief completo (anti-Cognition)
           coord = shared files nel proprio worktree (blackboard, mai peer-chat)
           ┌────────────┬────────────┬───────────┬──────────────┐
           ASSALITORI    ANALISTI      SPAZZINI     MECCANICO
           fan-out 3-5   fan-out adv   1-2 NON      1 SOLO serial:
           breadth       verify asym   parallel-git commit→push→PR→STOP
           ◄── pipeline SENZA barriera tra stadi (item-by-item) ──►
```

## 3 leggi anti-auto-distruzione (MAST + Cognition + scar W59/W62)

1. **Mai peer-to-peer** tra worker — coord solo via file condivisi (17.2×→4.4×, claim 8).
2. **Worker = brief completo** della sessione, non frammenti (no conflitti git, claim 12-14).
3. **Git single-threaded** — 1 meccanico serializza commit/push; breadth parallelizza,
   git no (claim 10).

## Mappa sulla nostra infra esistente

| SOTA primitive | Nostro equivalente già shippato |
|---|---|
| Worktree isolation | `scripts/agent_start.py` (broker L1, TTL, --cleanup WIP-safe) |
| Lease/lock | `.git/hooks/pre-commit` + Redis `agent_lock:<resource>` (AGENT_LEASE_ENFORCEMENT) |
| Branch-hijack guard | `.git/hooks/pre-commit` W59 (`BRANCH_EXPECTED`) |
| Shared task-list/blackboard | file JSON nel worktree (slides.json/brief.json pattern WR3) |
| Orchestrator-only (no inline) | WR3/WR2 design-architect Contract 1 (fan-out) |
| Critic/verification gate | wr2-critic / wr3-critic / devils-advocate |
| Checkpoint/resume | Workflow journal (resumeFromRunId) |

Conclusione: **non dobbiamo costruire il motore — esiste già e mappa 1:1 sullo stato-dell'arte.**
Dobbiamo COMANDARLO con la disciplina giusta. Le 18 sessioni impongono questa topologia.
