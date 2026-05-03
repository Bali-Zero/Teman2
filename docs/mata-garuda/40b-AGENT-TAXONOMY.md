# Mata Garuda — agent-taxonomy Integration

> Data: 2026-04-09 | Sessione S03
> Repo: github.com/suryast/agent-taxonomy (stesso autore di civic-stack)
> Citato da: @karpathy, Marzo 2026
> Product Hunt: "Pokedex for AI Agents"
> Interactive: agent-taxonomist.dev

---

## Cos'e

**Agent Taxonomy e' un framework evolutivo per self-improvement di AI agents**. Tratta la configurazione di un agent come un organismo vivente con:
- **Genoma** (GENOME.md) che evolve via **Lamarckian inheritance**
- **Horizontal gene transfer** tra agent
- **Human selection pressure** via review
- **Fitness metrics** per misurare miglioramento
- **Auto-revert** quando una mutazione peggiora le performance

## Il Core Insight

```
failure → rule → habit → identity
```

Un fallimento viene loggato. Il log diventa una regola. La regola modella
il comportamento futuro. Ogni sessione eredita questi tratti acquisiti.

**Questa e' evoluzione Lamarckiana** — piu veloce dell'evoluzione Darwiniana
perche ogni fallimento migliora direttamente la prossima generazione.

**GENOME.md** e' il meccanismo che rende questa ereditarieta esplicita,
tracciabile, ed evolvibile.

## Come Funziona

```
Agent runs tasks → Success?
    │
    ├─ Yes → Reinforce behavior → loop
    │
    └─ No → Log failure to feedback.md
            → Extract pattern
            → Propose mutation to GENOME.md
            → Human review?
                ├─ Accept → Mutation applied
                │           → Measure fitness metrics
                │           → Improved?
                │               ├─ Yes → Keep mutation ✅
                │               └─ No  → Auto-revert ↩️
                └─ Reject → Discarded
```

## La Tassonomia Evolutiva

8 livelli biologici per classificare agent:

```
🌍 Domain (Autonomy)
    ↓
👑 Kingdom (Architecture)
    ↓
🧠 Phylum (Memory)
    ↓
🧬 Class (Evolution)
    ↓
⏱️ Order (Mutation Rate)
    ↓
🎯 Family (Selection)
    ↓
🔧 Genus (Specialization)
    ↓
🏷️ Species (Instance)
```

### Domain — Autonomy Level

| Domain | Descrizione | Esempio |
|--------|-------------|---------|
| **Automatia** | Comportamento fisso, no learning | Bash scripts, cron jobs |
| **Adaptia** | Impara in sessione, no persistence | ChatGPT conversations |
| **Evolventia** | Memoria persistente + self-modification | **OpenClaw, Mata Garuda** |

### Kingdom — Architecture

| Kingdom | Descrizione | Esempio |
|---------|-------------|---------|
| **Monagentia** | Single agent | Solo coding assistant |
| **Polyagentia** | Multi-agent con specializzazione | **Mata Garuda** (Harvester, Classifier, Briefing, Distributor) |
| **Swarmia** | Emergent behavior da agent semplici | Ant colony task swarms |

## Classificazione di Mata Garuda

Dopo il design che abbiamo fatto, Mata Garuda sarebbe classificato come:

```
Domain:    Evolventia    (memoria persistente + self-modification L2)
Kingdom:   Polyagentia   (multi-agent con specializzazione)
Phylum:    ?             (da studiare - tipo di memoria)
Class:     ?             (tipo di evoluzione: Lamarckian desiderato)
Order:     ?             (mutation rate - weekly?)
Family:    Hybrid        (automatic + human selection pressure per L2/L3)
Genus:     Intelligence  (specializzato in OSINT/regulatory/news)
Species:   Garuda        (istanza unica)
```

## Integrazione con Mata Garuda

### Pattern 1: GENOME.md per Ogni Agent Mata Garuda

Ogni analyst agent di Mata Garuda ha il suo GENOME.md:

```
mata-garuda/
├── agents/
│   ├── daily-briefing/
│   │   ├── agent.py
│   │   ├── GENOME.md          ← Regole apprese dalle failures
│   │   └── feedback.md        ← Log di tutti i fallimenti
│   ├── regulation-alert/
│   │   ├── agent.py
│   │   ├── GENOME.md
│   │   └── feedback.md
│   └── source-health/
│       ├── agent.py
│       ├── GENOME.md
│       └── feedback.md
```

Esempio GENOME.md per Daily Briefing Agent:

```markdown
# Daily Briefing Agent — GENOME

## Acquired Traits

### 2026-04-10 — Never include regulation drafts as "confirmed"
**Origin**: feedback.md entry #23 — Zero corrected briefing
that labeled a proposed regulation as active.
**Rule**: Always verify regulation_status == "PUBLISHED" before including.
**Fitness delta**: +12% accuracy on Zero's confirm/deny feedback.

### 2026-04-14 — Prioritize immigration over tax in briefing header
**Origin**: feedback.md entry #31 — Zero dwelled longer on
immigration section than tax.
**Rule**: If both immigration and tax have score > 0.7, immigration first.
**Fitness delta**: +8% dwell time on headline topics.

### 2026-04-17 — Use Indonesian names format
**Origin**: feedback.md entry #38 — Zero corrected "Jokowi"
to "Joko Widodo" in briefing.
**Rule**: Always use official full name format for government officials.
**Fitness delta**: +5% Zero satisfaction rating.
```

### Pattern 2: Meta-Agent come Evolutionary Engine

Il meta-agent Mata Garuda implementa il loop agent-taxonomy:

```python
class MataGarudaMetaAgent:
    async def evolutionary_cycle(self):
        # 1. Per ogni agent, analizza feedback.md della settimana
        for agent_dir in glob("agents/*/"):
            feedback = read_feedback(agent_dir)
            
            # 2. Extract failure patterns
            patterns = await self.extract_patterns(feedback)
            
            # 3. Propose mutations to GENOME.md
            mutations = await self.propose_mutations(agent_dir, patterns)
            
            # 4. Human review for L3+ mutations
            approved = await self.review_with_zero(mutations)  # Telegram
            
            # 5. Apply approved mutations
            for mutation in approved:
                await self.apply_mutation(agent_dir, mutation)
            
            # 6. Measure fitness over next cycle
            # Se fitness peggiora → auto-revert
            # Se migliora → keep
```

### Pattern 3: Horizontal Gene Transfer

Quando un agent impara qualcosa utile, puo condividerlo con altri:

```python
# Daily Briefing Agent impara che i draft non sono confermati
# → Questa regola viene propagata a Regulation Alert Agent
# → E a Contradiction Agent
# → E al KB Update Agent

async def horizontal_transfer(source_agent, rule):
    compatible_agents = find_compatible_agents(rule)
    for target in compatible_agents:
        await propose_mutation(target, rule, source=source_agent)
```

## Differenze vs AutoAgent/Meta-Harness

| Aspetto | AutoAgent | agent-taxonomy |
|---------|-----------|----------------|
| Target | Agent harness (infrastructure) | Agent configuration (GENOME.md) |
| Evoluzione | Propose-run-evaluate loop | Lamarckian inheritance |
| Review | Automatic (LLM-as-judge) | Human review centrale |
| Tracciabilita | Run logs | GENOME.md versioned |
| Compound | 10% a settimana | Ogni failure = miglioramento |
| Focus | Performance benchmark | Identity evolution |

**Per Mata Garuda usiamo ENTRAMBI**:
- **AutoAgent** per ottimizzare classification/scoring (task misurabili)
- **agent-taxonomy GENOME.md** per apprendere da feedback Zero qualitativo

## Azioni [DECIDED]

1. [ ] Clonare agent-taxonomy e studiare il codice sorgente completo
2. [ ] Creare struttura `mata-garuda/agents/*/GENOME.md`
3. [ ] Integrare il loop Lamarckian nel Meta-Agent
4. [ ] Configurare feedback.md per ogni agent con pattern estrattori
5. [ ] Testare interactive classifier su agent-taxonomist.dev per Mata Garuda
6. [ ] Documentare classificazione tassonomica di ogni agent
