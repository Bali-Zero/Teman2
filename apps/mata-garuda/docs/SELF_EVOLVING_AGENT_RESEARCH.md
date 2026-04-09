# Mata Garuda — Ricerca: L'Organismo Intelligente che Evolve

> Generato: 2026-04-09
> Fonti: Exa Deep Research Pro (49 citazioni), NLM Deep Research (65 fonti, 57 importate), Exa Papers (15 paper)
> NLM Notebook: `305f5f2e-d2f4-4f77-a771-c2b7aa0867e4` (Mata Garuda — Self-Evolving Agent Research)

---

## 1. IL PROBLEMA DI MATA GARUDA OGGI

Il Lamarckian attuale fa **una sola cosa**: quando un agente fallisce, logga il perché e propone una constraint difensiva al GENOME. È un sistema immunitario primitivo — accumula cicatrici, non muscoli.

Un organismo veramente intelligente deve:
- Imparare dai **successi** (non solo dai fallimenti)
- **Accumulare conoscenza** che persiste e cresce
- **Migliorare le proprie strategie** autonomamente
- **Scoprire** nuove capacità da solo
- Diventare **più denso** di intelligenza ad ogni ciclo

---

## 2. I 6 PATTERN FONDAMENTALI (dalla ricerca)

### Pattern 1: REFLEXION — Memoria episodica verbale

**Paper:** Shinn et al., 2023 — "Reflexion: Language Agents with Verbal Reinforcement Learning"

L'agente genera **riflessioni in linguaggio naturale** dopo ogni run e le salva in un buffer persistente. Le riflessioni successive vengono iniettate nel prompt per guidare il comportamento futuro.

```
Run → Esito → Riflessione testuale → Buffer episodico → Prossimo prompt arricchito
```

**Meccanismo:** NON modifica pesi del modello. Modifica il **contesto** che il modello riceve. È puro prompt engineering persistente.

**Per Mata Garuda:** Perfettamente compatibile. Ogni agente dopo ogni run (successo O fallimento) genera una riflessione testuale via `claude --print`, salvata in `reflections/{agent_name}.md`. Le prossime esecuzioni iniettano le ultime N riflessioni nel prompt. **Nessuna dipendenza extra.**

### Pattern 2: VOYAGER — Skill Library come DNA acquisito

**Paper:** Wang et al., 2023 — "Voyager: An Open-Ended Embodied Agent with Large Language Models"

L'agente genera **codice eseguibile** per ogni skill scoperta, lo salva in una libreria indicizzata, e lo **riusa per comporre comportamenti complessi**.

```
Task → Genera codice → Esegui → Successo? → Salva skill con embedding → Riusa
```

**Meccanismo chiave:** Le skill sono **codice**, non testo. Persistono, sono composabili, trasferibili ad altri agenti. Niente catastrophic forgetting perché la conoscenza è nel filesystem, non nei pesi.

**Per Mata Garuda:** Il GENOME.md è già uno schema simile ma **passivo** (è documentazione). Il pattern Voyager suggerisce di rendere il GENOME **attivo**: non solo "regole", ma **procedure eseguibili** salvate come snippet riusabili. Esempio: un Regulation Watcher che impara un nuovo pattern regex lo salva come skill, e il JDIH Harvester lo eredita.

### Pattern 3: DARWIN GÖDEL MACHINE (DGM) — Auto-modifica del codice

**Paper:** Zhang et al., 2025 — "Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents"

L'agente **modifica il proprio codice sorgente**, testa la modifica in sandbox, e la accetta solo se migliora i benchmark. Mantiene un **archivio di versioni** per branching e rollback.

```
Agente → Propone patch al proprio codice → Sandbox test → Benchmark ↑? → Merge
                                                          Benchmark ↓? → Rollback + archivia
```

**Risultati concreti:** SWE-bench da 20% → 50%. Le auto-scoperte includono tool migliori, gestione contesto, peer review.

**Per Mata Garuda:** Il Meta Agent potrebbe proporre modifiche al codice degli agenti (non solo al GENOME.md) — testare in sandbox (pytest), e accettare solo se i test passano. Il vincolo "NO auto-apply GENOME" di CLAUDE.md resterebbe per le mutazioni di strategia, ma le mutazioni **tecniche** (regex, parsing, timeout) potrebbero essere auto-applicate con gate pytest.

### Pattern 4: EvoPrompt / OPRO — Evoluzione dei prompt

**Paper:** Guo et al., 2023 — "EvoPrompt: Connecting LLMs with Evolutionary Algorithms"

I prompt stessi sono trattati come **genomi** soggetti a mutazione, crossover, e selezione fitness-based.

```
Popolazione di prompt → Mutazione via LLM → Test su dev set → Fitness score → Selezione
```

**Per Mata Garuda:** Le **instructions** dentro ogni Agent Pydantic model sono prompt. Potrebbero essere soggette a evoluzione: generare 3 varianti, testarle su un dataset di regolazioni note, e selezionare la migliore. I GENOME.md diventano il **genotipo** e le instructions il **fenotipo**.

### Pattern 5: Memoria Ibrida — SQLite + Semantic + Graph

**Fonti:** Mem0 (2025), MemMachine (2026), AWS AgentCore, Sparkco evaluation

I sistemi reali usano **3 tier di memoria**:

| Tier | Cosa | Dove | Quando |
|------|------|------|--------|
| **Episodico** | Raw events, log di ogni run | SQLite append-only | Sempre, write-once |
| **Semantico** | Fatti estratti, knowledge condensato | SQLite FTS5 o vector | Consolidamento periodico |
| **Relazionale** | Connessioni tra entità (reg→ministero→impatto) | Graph o tabelle JOIN | Cross-query |

**Risultati:** Mem0 → 26% accuracy improvement, 91% lower latency, 90% fewer tokens. SQLite → 1-10ms reads su dataset < 1GB.

**Per Mata Garuda:** SQLite è il match perfetto (zero dipendenze, locale, ACID). Tre tabelle: `runs` (episodico), `knowledge` (semantico con FTS5), `relations` (reg→tag→impatto). Niente vector DB (troppo pesante per i vincoli), FTS5 basta.

### Pattern 6: Sandbox + Checkpoint + Revert

**Fonti:** DGM, EVOSEAL, Hermes Agent Self-Evolution

Pattern universale per auto-modifica sicura:

```python
snapshot = checkpoint(current_agent)
candidate = mutate(current_agent)
results = test_in_sandbox(candidate)
if results.fitness > baseline.fitness:
    accept(candidate)
else:
    rollback(snapshot)
    archive_failure(candidate, results)
```

**Per Mata Garuda:** Già implementato parzialmente (fitness.py + auto-revert). Manca: sandbox reale (eseguire l'agente mutato in un ambiente di test prima di applicare), e archivio delle varianti fallite (utile per non riprovare la stessa mutazione).

---

## 3. COSA MANCA A MATA GARUDA PER DIVENTARE INTELLIGENTE

### 3.1 Reflection Loop (impara da tutto, non solo dai fallimenti)

**Oggi:** Solo `case_not_resolved` → feedback
**Domani:** Ogni run (successo o fallimento) → riflessione

```
Dopo ogni run:
  1. claude --print "Analizza questo run: {result}. 
     Cosa ha funzionato? Cosa poteva andare meglio?
     Cosa hai imparato che è riusabile?"
  2. Salva in reflections/{agent}_{timestamp}.md
  3. Prossimo run: inietta ultime 5 riflessioni nel prompt
```

**Implementazione:** ~50 LOC in `runtime/reflection.py`. Nessuna dipendenza.

### 3.2 Knowledge Base con FTS5 (memoria semantica)

**Oggi:** Redis stream volatile, nessuna persistenza strutturata
**Domani:** SQLite con FTS5 per search full-text in indonesiano

```sql
CREATE TABLE knowledge (
    id INTEGER PRIMARY KEY,
    agent TEXT,           -- chi ha prodotto questa conoscenza
    type TEXT,            -- fact, insight, pattern, skill
    content TEXT,         -- il contenuto
    source TEXT,          -- da dove viene
    confidence REAL,      -- 0.0-1.0
    created_at TEXT,
    accessed_count INTEGER DEFAULT 0,
    last_accessed TEXT
);
CREATE VIRTUAL TABLE knowledge_fts USING fts5(content, source);
```

**Consolidamento:** Periodicamente, `claude --print` rilegge le ultime N entries e produce un summary condensato. Le entry vecchie con `accessed_count = 0` decadono.

### 3.3 Success Pattern Learning (Voyager-style)

**Oggi:** I successi non vengono analizzati
**Domani:** Ogni successo produce una **skill** riusabile

```
Run successo → claude --print "Estrai la procedura che ha funzionato come skill riusabile"
  → Salva in skills/{agent}/{skill_name}.md
  → Indicizza in SQLite knowledge (type=skill)
  → Disponibile per tutti gli agenti via tool get_skill()
```

**Cross-agente:** Se il Regulation Watcher scopre che un certo User-Agent bypassa un 403, salva la skill. Il JDIH Harvester la eredita automaticamente.

### 3.4 Meta-Cognition periodica

**Oggi:** Il Meta Agent non pensa mai da solo
**Domani:** Cron settimanale dove il Meta Agent rilegge TUTTO e ragiona

```
Ogni domenica:
  1. Leggi tutti i fitness.jsonl di tutti gli agenti
  2. Leggi tutte le riflessioni recenti
  3. Leggi la knowledge base (ultimi 7 giorni)
  4. claude --print "Sei il Meta Agent di Mata Garuda. 
     Analizza lo stato del sistema. Cosa va bene?
     Cosa va male? Quali agenti servono che non esistono?
     Quali strategie cambiare? Proponi 3 azioni concrete."
  5. Salva il report in meta_cognition/{date}.md
  6. Alert TG a Zero con le 3 proposte
```

### 3.5 Evoluzione dei prompt (EvoPrompt-style)

**Oggi:** Instructions statiche nel codice Python
**Domani:** Instructions come GENOME evolvibile

```
Ogni 30 run di un agente:
  1. Genera 3 varianti delle instructions via claude --print
  2. Testa ognuna su 5 task di riferimento (benchmark locale)
  3. Misura fitness (success rate, token usage, latency)
  4. Se variante > current → proponi a Zero (o auto-apply per varianti tecniche)
  5. Archivia tutte le varianti con scores
```

### 3.6 Dual Feedback (processo + esito)

**Oggi:** Solo esito binario (resolved/not_resolved)
**Domani:** Anche valutazione del **processo**

```
Dopo ogni run:
  1. Esito: case_resolved? (binario)
  2. Processo: claude --print "Valuta il PROCESSO di questo run:
     - L'agente ha usato i tool nell'ordine giusto?
     - Ha sprecato chiamate?
     - Ha fatto ragionamenti ridondanti?
     - Score 1-10 per efficienza del processo"
  3. Salva entrambi: fitness tracka esito E processo
  4. Pattern: successo con processo inefficiente → skill da migliorare
            fallimento con buon processo → problema esterno, non agente
```

---

## 4. L'ARCHITETTURA DELL'ORGANISMO INTELLIGENTE

```
                    ┌──────────────────────┐
                    │    META COGNITION     │ ← cron settimanale
                    │  (analizza, propone)  │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │     META AGENT        │
                    │  (crea, gestisce,     │
                    │   evolve agenti)      │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                     │
   ┌──────▼──────┐    ┌───────▼───────┐    ┌───────▼───────┐
   │  HARVESTER   │    │  HARVESTER    │    │  HARVESTER    │
   │  Reg Watcher │    │  Pasal.id     │    │  JDIH Bali    │
   └──────┬──────┘    └───────┬───────┘    └───────┬───────┘
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │    garuda:raw         │ Redis Stream
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │    NORMALIZER         │ → SQLite KB
                    │    (dedup, schema)    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  RELEVANCE SCORER     │ → claude --print
                    │  (score 1-5, tag)     │
                    └──────────┬───────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
        ┌──────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐
        │  ANALYST     │ │ TG ALERT  │ │ NLM BRIEFING│
        │  (deep dive) │ │ (score≥4) │ │ (weekly)    │
        └──────┬──────┘ └───────────┘ └─────────────┘
               │
    ┌──────────▼───────────┐
    │    KNOWLEDGE BASE     │ SQLite FTS5
    │    (facts, skills,    │
    │     patterns,         │
    │     reflections)      │
    └──────────┬───────────┘
               │
    ┌──────────▼───────────┐
    │    REFLECTION LOOP    │ ← dopo OGNI run
    │    (successi +        │
    │     fallimenti)       │
    └──────────┬───────────┘
               │
    ┌──────────▼───────────┐
    │    SKILL LIBRARY      │ ← Voyager-style
    │    (procedure         │
    │     riusabili,        │
    │     cross-agente)     │
    └──────────┬───────────┘
               │
    ┌──────────▼───────────┐
    │    FITNESS LANDSCAPE  │
    │    (multi-objective:  │
    │     esito + processo  │
    │     + token cost      │
    │     + novelty)        │
    └──────────┬───────────┘
               │
    ┌──────────▼───────────┐
    │    GENOME EVOLUTION   │
    │    (EvoPrompt-style,  │
    │     sandbox + test    │
    │     + accept/revert)  │
    └───────────────────────┘
```

---

## 5. PRINCIPI DELL'ORGANISMO (dalla ricerca)

### Il Sayan Protocol

| Principio | Meccanismo | Paper di riferimento |
|-----------|-----------|---------------------|
| **Più si fa male, più potere** | Feedback → riflessione → skill → GENOME mutation | Reflexion + Voyager |
| **Impara dai successi** | Success pattern extraction → skill library | Voyager |
| **Memoria che cresce** | SQLite episodico + semantico + relazionale | Mem0 + MemMachine |
| **Auto-modifica sicura** | Sandbox + benchmark + checkpoint + revert | DGM + EVOSEAL |
| **Evoluzione dei prompt** | Popolazione + mutazione + fitness selection | EvoPrompt + OPRO |
| **Meta-cognizione** | Self-analysis periodica del sistema intero | ADAS + Meta Agent Search |
| **Cross-agente** | Skill library condivisa, inheritance di conoscenza | AgentSpawn + Voyager |
| **Open-ended** | Scoperta autonoma di nuove capacità/fonti | OMNI-EPIC + DGM |

### Differenza critica con l'attuale Lamarckian

| Aspetto | Oggi | Organismo |
|---------|------|-----------|
| Impara da | Solo fallimenti | Tutto (successi + fallimenti + processo) |
| Tipo di apprendimento | Constraint difensive | Skill attive + strategy evolution |
| Memoria | Redis volatile + fitness.jsonl | SQLite persistente multi-tier |
| Cross-agente | Zero condivisione | Skill library condivisa |
| Meta-cognizione | Mai | Settimanale automatica |
| Evoluzione prompt | Mai | Ogni 30 run |
| Sandbox test | No | Sì (pytest gate) |

---

## 6. RIFERIMENTI CHIAVE

### Paper fondamentali (tutti nel notebook NLM)

| Paper | Contributo per Mata Garuda |
|-------|---------------------------|
| **Reflexion** (Shinn 2023) | Reflection loop: riflessioni verbali persistenti |
| **Voyager** (Wang 2023) | Skill library: codice riusabile come conoscenza |
| **DGM** (Zhang 2025) | Auto-modifica codice con sandbox + benchmark |
| **EvoPrompt** (Guo 2023) | Evoluzione dei prompt come genomi |
| **ADAS** (Hu 2024) | Meta Agent Search: design automatico di agenti |
| **Self-Refine** (Madaan 2023) | Critica interna iterativa |
| **OMNI-EPIC** (Zhang 2024) | Open-endedness: scoperta autonoma di task |
| **Mem0** (2025) | Memoria persistente: 26% accuracy, 90% fewer tokens |
| **EVOSEAL** | Checkpoint + regression detector + rollback |
| **Hermes** (NousResearch) | Git-based evolution con test gate |
| **StepORLM** (2025) | Dual feedback: processo + esito |
| **AgentSpawn** (2025) | Inheritance di memoria/skill tra agenti |
| **CORAL** (2026) | Multi-agent evolution autonoma |

### Repository da studiare

- `github.com/noahshinn/reflexion` — Reflexion
- `github.com/minedojo/voyager` — Voyager
- `github.com/jennyzzt/dgm` — Darwin Gödel Machine
- `github.com/beeevita/EvoPrompt` — EvoPrompt
- `github.com/MaximeRobeyns/self_improving_coding_agent` — OMNI-EPIC
- `github.com/Arvid-pku/Godel_Agent` — Gödel Agent
- `github.com/SHA888/EVOSEAL` — EVOSEAL
- `github.com/NousResearch/hermes-agent-self-evolution` — Hermes
- `github.com/Human-Agent-Society/CORAL` — CORAL

---

## 7. VINCOLI DI IMPLEMENTAZIONE

Tutto quanto sopra DEVE rispettare:

- **CLI-only**: riflessioni, analisi, evoluzione prompt → tutto via `claude --print` / `gemini --print`
- **Zero dipendenze**: SQLite è stdlib Python. FTS5 è incluso. Niente vector DB, niente graph DB
- **OSINT blindato**: la knowledge base è locale, le skill sono locali, le riflessioni sono locali
- **Lamarckian safe**: auto-apply solo per mutazioni tecniche (regex, timeout) con pytest gate. Mutazioni strategiche (GENOME) restano con review Zero
- **Sayan**: ogni componente deve rendere il sistema più forte, mai più fragile
