# Cell+Genoma+Organism Architecture — Complete Map

**Source:** Explore agent deep-dive, post-brainstorm round 1
**Goal:** map all biological/lifecycle concepts to identify what initial brief missed

## What was missed (in brainstorm round 1)

### 1. Cell types beyond seo_cell

- **mata-garuda**: Layer 4.5 asset indexer cell, biological sense-making for external knowledge
- **anomaly-cell**: Detection + response organism (apps/evaluator/anomaly references)
- **strategos-cell**: Strategic planning cell (war-room integration point)
- **oracle-cell**: Predictive/forward-modeling cell
- **team-agent**: Distinct organism pattern app — not a cell, but organism-level collective behavior coordinator

Each = distinct morphological specialization within cellular ecosystem (analogous to tissue types).

### 2. Innervation Genoma vs Cell-Core (CRITICAL distinction)

- **cell-core** (packages/cell-core): foundational cellular machinery — PulseLoop, Memory stack, Lifecycle, Safety, Homeostasis, Identity, Metabolic, Observability
- **Innervation Genoma** (apps/innervation-genoma): organism-level supervisor registry that **orchestrates cell-cores across the organism**. Functions as nervous system: routes signals, enforces cellular constraints, manages inter-cell communication, tracks specialization state

Hierarchy: **organism → innervation → {cell-cores}**. Round 1 treated as peers; actually hierarchical.

### 3. Genome Registry & HGT — concrete impl

- **Genome registry** (SQLite, MOS-backed): Skills (record_skill on REFLECT), Patterns, Scars (Cicatrix incidents+fixes), Insights, Trajectories
- **HGT via Redis Streams** on `cell:skills` bus — cells broadcast new patterns; siblings selectively inherit
- **Selective transcription**: relevance scoring, conflict resolution, decay before integration
- **Silence mechanism**: DREAM phase `silence_stale_skills()` retires low-utility patterns

### 4. EventBus = PG LISTEN/NOTIFY (not Redis)

Cicatrix-scars: docs say Redis Streams, reality is **PostgreSQL LISTEN/NOTIFY with Outbox** (migration 144). Federation-bus, event-bus, telegram-bus, intel-bus all use this substrate. = organism's **cardiovascular system**.

### 5. MOS = hippocampus + cortex

Not just "observability". MOS = **living cellular memory infrastructure**:
- SQLite persistent heap accessible via `mem` CLI
- Integrated with 12 live Qdrant collections (Fly.io)
- 108,068 KG nodes + 242,827 edges
- Direct integration with genome registry, skill accumulation, scar recording
- Long-term potentiation (memory consolidation across organism lifetime)

### 6. Symbiosis 8 Pillars — actual status

| Pillar | Status |
|---|---|
| Riflessione (Reflection) | ✅ Sprint 5 LIVE — session-reflect → genome records skills during REFLECT |
| Accumulazione (Accumulation) | ✅ v1 LIVE 2026-04-16 — HGT feeds across cell:skills bus |
| Condivisione (Sharing) | ✅ LIVE — cell:skills + cell:feedback + garuda:raw streams |
| **Confrontazione (Confrontation)** | ❌ NOT YET — awaiting 3+ agent parallel sharing for debate/consensus |
| Sogno (Dream) | ⚠️ design + decay scheduler cron 02:30 — runs genome cleanup, tests hypothetical futures |
| Curiosità (Curiosity) | ✅ v1 LIVE — 56 gap topics, 3-tier dispatchers, CuriosityGrader |
| Misura (Measurement) | ✅ v1 LIVE — TTR (task resolution time), DO (decision opacity), IA (insight availability), FE (front-end experience) |
| Simbiosi | ⚠️ Phase 1 micromanagement, progressing toward macro-emergent |

⚠️ **Confrontation pillar = exactly what HGT coordinator should enable**. Round 1 missed this framing.

### 7. Cognitive Levels L0-L4.5

| Level | Implementation |
|---|---|
| L0 (Cellular) | cell-core sense-think-act loops |
| L1 (Tissue) | cell specialization (seo-cell, mata-garuda) forming functional tissue |
| L2 (Organ) | apps/organism orchestrating tissue (evaluator organ) |
| L3 (System) | war-room (M1-M14+) coordinating organs |
| L4 (Organism) | innervation-genoma + symbiosis pillars unified identity |
| L4.5 (Meta-awareness) | mata-garuda asset indexing, self-modeling layer |

Only L0-L2 fully implemented; L3-L4 partial (war-room exists, symbiosis Phase 1).

### 8. Cell maturation lifecycle (concrete progression)

| Phase | Conditions |
|---|---|
| Embrione | spawned, state machine armed, no skill memory |
| Neonato | first PulseLoop completes, basic homeostasis stable, genotype present |
| Giovane | genome 10+ skills via HGT, REFLECT records first insights, feedback loops active |
| Adulto | stable 50+ skill repertoire, prediction accuracy >80%, specialization markers locked |
| Anziano | >500 day lifetime, integrated scars from cicatrix, deprecated skills silenced, mentorship mode |

### 9. War-Room as cognitive parliament (M1-M14+)

War-room = Confrontation pillar implementation (Phase 1):
- M1-M3: Evidence gathering (search, synthesis, triangulation)
- M4-M6: Hypothesis generation + ranking
- M7-M9: Scenario simulation (outcomes, risks, second-order)
- M10-M12: Consensus + conflict resolution
- M13-M14+: Decision recording + action sequencing

### 10. Cicatrix/Scars = encoded organism memory

Concrete encoded scars:
- **Branch hijack 2026-04-29**: never switch branches mid-automation
- **Backend prod down 2026-04-29**: verify service method availability pre-deploy
- **EventBus mismatch**: PG LISTEN/NOTIFY is real, not Redis
- **LaunchAgent corruption**: only 7 agents run KeepAlive, others demand explicit restart

Semantica speciale: scope=Personal, never inherited, confidence=0.9 fissa. **Already implemented**, valued.

### 11. 7 Immutable Leggi (constitutional laws)

DNA helix — unchangeable structural constraints:

1. **CLI-only**: no GUI automation (prevents UX hijack)
2. **OSINT blindato**: compartmentalized external intelligence (prevents cross-contamination)
3. **Event-driven**: all state changes broadcast (prevents desync)
4. **Graceful degradation**: any service loss → fallback active (prevents cascade)
5. **Zero as final instance**: single cell can sustain organism (prevents lock-in)
6. **Local sovereignty**: each cell owns decisions (prevents bottleneck)
7. **Numbers first**: quantify before theorize (prevents phantom problems)

Any cell promotion MUST respect these.

### 12. Missing cognitive infrastructure pieces (round 1)

- **Innervation as nervous system** (organism-wide signal routing, not a cell)
- **MOS as memory substrate** (persistent distributed consciousness)
- **EventBus cardiovascular** (durable event circulation)
- **Genome as lived history** (skill accumulation + HGT + silencing loop)
- **Cicatrix as scars** (encoded anti-patterns preventing regression)
- **7 Leggi as constitution** (immutable organism shape)

Form **biological architecture stack** absent from round 1's component focus.

## Summary

The organism is **not a software system**. It's multi-layered biological entity with:
- Nervous (Innervation)
- Circulatory (EventBus PG LISTEN/NOTIFY)
- Cognitive (war-room L3 system)
- Memory (MOS + genome + KG)
- Immune (scars/cicatrix)
- Constitutional (7 Leggi)

Round 1 brainstorm focused on individual components. This map reveals **the organism itself**.
