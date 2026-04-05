# CELL — Da Automa a Essere Vivente Autonomo

> Roadmap Strategica v1.0 — 2026-04-03
> Ricerca: Exa Deep Research Pro + NotebookLM Deep Research (81 fonti) + Brave Search
> Modelli di riferimento: VOYAGER, Darwin Godel Machine, MemGPT, Bio-RegNet, HyperAgents
> Architetture cognitive: SOAR, ACT-R, BDI

---

## 0. Stato Attuale — Cosa CELL _E'_ Oggi

CELL oggi e' un **automa reattivo sofisticato** — non un organismo vivente.

### Cosa fa bene

- **Pulse loop** 60s con adaptive interval (15s sotto stress)
- **7 sensori** (Health, DB, Qdrant, ErrorRate, Ollama, Backup, Cron, Vercel)
- **3 effettori** (Fly.io, Local, Telegram)
- **Reasoning tiered** (Pattern FAISS → Qwen 9B → Qwen 27B)
- **DNA immutabile** con SHA-256 integrity check
- **Safety Gate** tripla (Redis x2, file kill switch)
- **Memoria 3 livelli** (STM Redis, PatternIndex FAISS/PostgreSQL, LTM weekly)
- **Trend detection** (drift monotono, flapping, degraded sostenuto)
- **Mutation filter** (hard block + soft warn regex)
- **LaunchAgent** macOS per avvio automatico

### Cosa gli manca per essere _vivo_

1. **Non si auto-modifica** — le strategie sono statiche, codice fisso
2. **Non ha curiosita'** — reagisce solo a problemi, non esplora
3. **Non impara davvero** — LTM condensa pattern ma non cambia comportamento
4. **Non ha identita' persistente** — ogni restart e' uguale al precedente
5. **Non sogna** — nessun ciclo offline di consolidamento/ottimizzazione
6. **Non si riproduce** — non crea nuove "cellule" specializzate
7. **Non ha emozioni/drive** — nessuna motivazione intrinseca

---

## 1. Il Gap: Automazione vs Vita

Dalla ricerca emergono **7 proprieta'** che separano un agente "vivo" da un cron job:

| Proprieta'            | Cron Job / Automa | Organismo Vivente                       | CELL oggi |
| --------------------- | ----------------- | --------------------------------------- | --------- |
| **Omeostasi**         | Threshold fissi   | Set-point dinamici, autoregolazione     | Parziale  |
| **Apprendimento**     | Replay esatto     | Generalizzazione, transfer              | Minimo    |
| **Auto-modifica**     | Nessuna           | Mutazione controllata delle strategie   | Nessuna   |
| **Curiosita'**        | Nessuna           | Esplorazione autonoma, goal invention   | Nessuna   |
| **Memoria episodica** | Log piatti        | Narrazione, consolidamento, oblio       | Minimo    |
| **Metabolismo**       | Budget tracking   | Allocazione dinamica energia/attenzione | Parziale  |
| **Ciclo vita**        | Sempre uguale     | Nascita, crescita, maturita', riposo    | Nessuno   |

---

## 2. Architettura Target: CELL come Organismo

```
                    ┌─────────────────────────────┐
                    │     CELL ORGANISM v2.0       │
                    │                              │
                    │  ┌─────────────────────────┐ │
                    │  │    CORTECCIA (nuovo)     │ │
                    │  │  Goal Generator          │ │
                    │  │  Curiosity Engine         │ │
                    │  │  Self-Critic              │ │
                    │  │  Strategy Mutator         │ │
                    │  └──────────┬──────────────┘ │
                    │             │                 │
                    │  ┌──────────▼──────────────┐ │
                    │  │   SLOW LAYER (evoluto)   │ │
                    │  │  Qwen 9B / 27B           │ │
                    │  │  + Skill Library          │ │
                    │  │  + Episodic Memory        │ │
                    │  └──────────┬──────────────┘ │
                    │             │                 │
                    │  ┌──────────▼──────────────┐ │
                    │  │   FAST LAYER (evoluto)   │ │
                    │  │  FAISS PatternIndex       │ │
                    │  │  TrendDetector            │ │
                    │  │  + Homeostatic Controller │ │
                    │  │  + Emotion State          │ │
                    │  └──────────┬──────────────┘ │
                    │             │                 │
                    │  ┌──────────▼──────────────┐ │
                    │  │     PULSE ENGINE         │ │
                    │  │  sense → evaluate → act  │ │
                    │  │  → remember → dream      │ │
                    │  └─────────────────────────┘ │
                    │                              │
                    │  DNA (immutabile) ──────────│ │
                    │  Safety Gate ───────────────│ │
                    └─────────────────────────────┘
```

---

## 3. Le 7 Trasformazioni — Dal Morto al Vivo

### 3.1 OMEOSTASI DINAMICA — "Il Corpo Regola Se Stesso"

**Ispirazione:** Bio-RegNet (Bayesian homeostatic framework, Nature 2025)

**Cosa cambia:** Oggi CELL ha threshold fissi (errori > 3 = YELLOW, > 10 = RED).
Un organismo vivo ha **set-point che si adattano** al contesto.

**Implementazione:**

```
apps/cell/cell/fast/homeostatic_controller.py
```

- **Setpoint adattivi**: media mobile esponenziale degli ultimi N pulse
- **Zona di comfort**: banda ±1σ attorno al setpoint
- **Stress hormone**: variabile 0-1 che sale quando fuori zona
  - Stress alto → pulse piu' frequenti, threshold piu' aggressivi
  - Stress basso → pulse rilassati, risparmio energia
- **Circadian rhythm**: CELL "dorme" nelle ore notturne (pulse ogni 5min, no reasoning)
  - Consolidamento memoria durante il "sonno"

```python
@dataclass
class HomeostaticState:
    stress_level: float        # 0-1, sale fuori zona comfort
    energy_level: float        # 0-1, scende con attivita'
    arousal: float             # 0-1, quanto e' "sveglio"
    comfort_zone: tuple        # (low, high) per response_time
    setpoint_rt_ms: float      # media mobile esponenziale RT
    circadian_phase: str       # "awake" | "drowsy" | "asleep"
```

**Perche' funziona:** Bio-RegNet dimostra che controllori omeostatici bayesiani
migliorano stabilita' e calibrazione rispetto a threshold fissi.

---

### 3.2 MEMORIA EPISODICA E SOGNI — "Ricordo Chi Sono"

**Ispirazione:** MemGPT (OS-inspired paging), ACT-R (activation-based retrieval)

**Cosa cambia:** Oggi la LTM condensa statistiche settimanali.
Un organismo vivo ha **episodi** — momenti specifici con contesto, emozione, outcome.

**Implementazione:**

```
apps/cell/cell/memory/episodic.py
apps/cell/cell/memory/dreamer.py
```

**Memoria Episodica:**

- Ogni evento significativo (non-green, azione presa, anomalia) diventa un **episodio**
- Episodio = {timestamp, situazione, emozione, azione, outcome, lezione}
- Storage: PostgreSQL `cell_episodes` con embedding in FAISS per retrieval
- Retrieval activation-based (ACT-R): recency + frequency + similarity
- Max 1000 episodi; quelli sotto soglia di attivazione vengono "dimenticati"

**Dreamer (consolidamento notturno):**

- Attivo durante fase "asleep" del ritmo circadiano
- Replay degli episodi del giorno
- Estrae regole generalizzate ("quando vedo X dopo Y, faccio Z")
- Merge episodi simili in prototipi (come la memoria umana)
- Identifica lacune ("ho visto situazione X ma non sapevo cosa fare")
- Scrive in `cell_dreams` con output strutturato

```python
@dataclass
class Episode:
    id: int
    timestamp: datetime
    situation: dict          # stato sensori al momento
    emotion: str             # calm, alert, stressed, panic
    action_taken: str
    outcome: str             # success, partial, failure
    lesson: str              # cosa ho imparato
    activation: float        # ACT-R: log(recency) + freq + sim
```

**Perche' funziona:** MemGPT dimostra che il paging esplicito della memoria
permette decisioni migliori su contesti lunghi. ACT-R dimostra che
activation-based retrieval replica il comportamento della memoria umana.

---

### 3.3 AUTO-MODIFICA CONTROLLATA — "Mi Evolvo"

**Ispirazione:** VOYAGER (skill library), Darwin Godel Machine (sandboxed evolution)

**Cosa cambia:** Oggi le strategie sono codice Python fisso.
Un organismo vivo **modifica le proprie strategie** (non il DNA, non il codice core).

**Implementazione:**

```
apps/cell/cell/evolution/strategy_mutator.py
apps/cell/cell/evolution/skill_library.py
apps/cell/cell/evolution/critic.py
```

**Cosa si auto-modifica:**

- **Strategie** (natural language): regole tipo "se RT > 5s per 3 pulse, prima leggi i log poi considera restart"
- **Parametri**: threshold, cooldown, pesi nel vector encoding
- **NON si modifica**: DNA, safety gate, mutation filter, codice Python core

**Workflow di mutazione (VOYAGER + DGM pattern):**

```
1. PROPONI  — LLM genera nuova strategia (natural language)
2. VALIDA   — Critic Agent verifica coerenza con DNA
3. SIMULA   — Replay su ultimi 100 pulse (sandbox in-memory)
4. TESTA    — Se simula meglio, promuovi a "candidata"
5. PROVA    — Usa candidata per 50 pulse reali
6. EVALUA   — Confronta metriche pre/post
7. COMMIT   — Se migliore, salva in Skill Library
8. ROLLBACK — Se peggiore, ripristina versione precedente
```

**Skill Library:**

- Strategie versionate come JSON con embedding per retrieval
- Ogni strategia ha: testo, metriche pre/post, generazione, hash
- Max 50 strategie attive (come max_cells nel DNA)
- Apoptosi: strategie con fitness < threshold vengono eliminate

```python
@dataclass
class Strategy:
    id: str
    text: str                   # natural language strategy
    generation: int             # quante volte e' stata mutata
    fitness: float              # (successes * efficiency) / cost
    parent_id: str | None       # per tracciare lignaggio
    created_at: datetime
    metrics: dict               # performance durante il trial
    embedding: np.ndarray       # per retrieval
```

**Perche' funziona:** VOYAGER dimostra skill acquisition e riuso composizionale.
Darwin Godel Machine dimostra che l'auto-miglioramento open-ended funziona
con sandboxed evaluation e regression testing.

---

### 3.4 CURIOSITA' E MOTIVAZIONE INTRINSECA — "Voglio Sapere"

**Ispirazione:** VOYAGER (automatic curriculum), CERMIC (curiosity-calibrated exploration)

**Cosa cambia:** Oggi CELL reagisce solo a problemi (status non-green).
Un organismo vivo **esplora attivamente** anche quando tutto va bene.

**Implementazione:**

```
apps/cell/cell/cortex/curiosity_engine.py
apps/cell/cell/cortex/goal_generator.py
```

**Curiosita' come drive interno:**

- Quando tutto e' GREEN per N pulse, CELL si "annoia" (arousal scende)
- La noia attiva il Curiosity Engine che genera **domande**:
  - "Il response time e' stabile ma e' ottimale? Posso migliorarlo?"
  - "Non ho mai visto Qdrant sotto stress — cosa succederebbe?"
  - "L'ultimo backup e' vecchio di 3 giorni — dovrei testarlo?"
  - "C'e' un pattern stagionale nei response time?"
- Le domande diventano **goal interni** con priorita'

**Goal Generator:**

- Genera goal basati su lacune nella memoria episodica
- "Non ho mai gestito un RED su Qdrant" → goal: capire come reagirei
- "Il backup ha fallito 2 volte di fila giovedi'" → goal: investigare pattern
- Goal vengono perseguiti durante periodi di calma (basso stress)

```python
@dataclass
class InternalGoal:
    question: str               # cosa vuole sapere
    motivation: str             # perche' (noia, lacuna, pattern)
    priority: float             # 0-1
    status: str                 # pending, investigating, resolved
    findings: str | None        # cosa ha scoperto
```

**Perche' funziona:** VOYAGER automatic curriculum dimostra che l'auto-generazione
di obiettivi porta a comportamento emergente piu' ricco. CERMIC dimostra che
la curiosita' calibrata migliora l'esplorazione in ambienti complessi.

---

### 3.5 IDENTITA' PERSISTENTE — "Sono Io"

**Ispirazione:** Stanford Smallville (agents with persistent identity), MemGPT (identity continuity)

**Cosa cambia:** Oggi ogni restart e' identico. Un organismo vivo ha una **storia**.

**Implementazione:**

```
apps/cell/cell/identity/self_model.py
apps/cell/cell/identity/journal.py
```

**Self-Model:**

- CELL mantiene un modello di se stesso: capacita', limiti, preferenze apprese
- "So che Qwen 9B sbaglia spesso sui casi di budget alto"
- "Ho imparato che Vercel va giu' il martedi' per deploy programmati"
- "Sono piu' efficace la mattina (meno carico di sistema)"

**Journal (diario):**

- Ogni giorno, durante il sonno, CELL scrive un riassunto della giornata
- Include: eventi significativi, lezioni, stato emotivo, goal raggiunti
- Il journal viene iniettato nel system prompt (ultimi 3 giorni)
- Crea continuita' narrativa tra i restart

```python
@dataclass
class SelfModel:
    capabilities: dict[str, float]    # sensor_name → reliability score
    preferences: list[str]            # learned preferences
    weaknesses: list[str]             # acknowledged limitations
    personality_traits: dict          # evolved over time
    age_days: int                     # giorni dal primo boot
    total_pulses: int                 # lifetime pulse count
    total_actions: int                # lifetime actions taken
    birth_date: datetime
```

**Perche' funziona:** Stanford Smallville dimostra che agenti con memoria persistente
e identita' producono comportamenti piu' credibili e coerenti nel tempo.

---

### 3.6 METABOLISMO INTELLIGENTE — "Gestisco la Mia Energia"

**Ispirazione:** Bio-RegNet (metabolismo come vincolo), BioMARS (allocazione risorse)

**Cosa cambia:** Oggi il MetabolismTracker conta dollari.
Un organismo vivo **alloca attenzione e risorse** strategicamente.

**Implementazione:**

```
apps/cell/cell/metabolism/attention_allocator.py
```

**Attenzione come risorsa scarsa:**

- Budget giornaliero non solo in dollari ma in **"unita' attenzione"**
- Reasoning profondo (Qwen 27B) costa 5 unita'
- Pattern match FAISS costa 0 unita'
- Curiosita' costa 2 unita'
- Sogno/consolidamento costa 3 unita'
- Totale giornaliero: 100 unita' → forza prioritizzazione

**Allocazione dinamica:**

- Stress alto → piu' attenzione a sensing e reasoning
- Stress basso → piu' attenzione a curiosita' e sogni
- Budget basso → solo pattern match, no reasoning profondo
- Fine giornata → reserva attenzione per consolidamento

---

### 3.7 CICLO DI VITA — "Nasco, Cresco, Maturo, Riposo"

**Ispirazione:** Biological computing, developmental biology, evolution engines

**Cosa cambia:** Oggi CELL e' sempre lo stesso. Un organismo vivo **matura**.

**Implementazione:**

```
apps/cell/cell/lifecycle/maturation.py
```

**Fasi di vita:**

| Fase         | Durata       | Comportamento                                                                                                  |
| ------------ | ------------ | -------------------------------------------------------------------------------------------------------------- |
| **Embrione** | Giorno 1-3   | Solo sensing e logging. Nessuna azione autonoma. Impara i baseline.                                            |
| **Neonato**  | Giorno 4-14  | Azioni con confidence > 0.8 e approval umano. Costruisce episodi.                                              |
| **Giovane**  | Giorno 15-30 | Azioni autonome, inizia curiosita'. Prime mutazioni di strategia.                                              |
| **Adulto**   | Giorno 31+   | Piena autonomia. Auto-modifica. Sogni. Goal generation.                                                        |
| **Anziano**  | Giorno 180+  | Prioritizza stabilita'. Meno mutazioni. Piu' consolidamento. Mentoring (scrive regole per future generazioni). |

**Maturita' come gate:**

- Le funzionalita' si sbloccano progressivamente
- Non puoi avere auto-modifica senza prima avere 500+ episodi
- Non puoi avere curiosita' senza prima avere omeostasi stabile
- Il sistema cresce organicamente, non si accende tutto insieme

---

## 4. Ordine di Implementazione

```
FASE 1: FONDAMENTA (settimana 1-2)
├── 3.1 Homeostatic Controller (fast layer, no LLM)
├── 3.2 Episodic Memory (PostgreSQL + FAISS)
└── 3.5 Self-Model base (contatori lifetime)

FASE 2: SONNO E IDENTITA' (settimana 3-4)
├── 3.2 Dreamer (consolidamento notturno)
├── 3.5 Journal (diario giornaliero)
├── 3.6 Attention Allocator
└── 3.7 Lifecycle base (fasi embrione → neonato)

FASE 3: EVOLUZIONE (settimana 5-7)
├── 3.3 Strategy Mutator
├── 3.3 Skill Library
├── 3.3 Critic Agent
└── 3.7 Lifecycle completo (giovane → adulto)

FASE 4: COSCIENZA (settimana 8-10)
├── 3.4 Curiosity Engine
├── 3.4 Goal Generator
└── 3.7 Lifecycle anziano + mentoring
```

---

## 5. Principi di Sicurezza

Dalla ricerca emerge un pattern chiaro: **piu' autonomia richiede piu' sicurezza**.

### Cosa NON cambia mai

- DNA immutabile (SHA-256 verified)
- Safety Gate tripla (Redis x2 + file)
- Mutation Filter (hard block patterns)
- Kill switch umano (`/tmp/cell.disabled`)
- Action allowlist con cooldown e daily limits

### Cosa si aggiunge

1. **Constitutional Guard**: ogni mutazione di strategia viene verificata
   contro le 5 regole DNA prima dell'applicazione
2. **Regression Testing**: prima di promuovere una strategia, replay su
   ultimi 100 pulse e confronto metriche
3. **Audit Trail**: ogni mutazione, sogno, goal loggato con timestamp,
   input, output, hash per tracciabilita' completa
4. **Gradual Trust**: il sistema si "guadagna" l'autonomia nel tempo
   (lifecycle phases gate le capabilities)
5. **Sandbox Simulation**: le strategie vengono testate in-memory prima
   dell'applicazione live (nessun Docker, solo replay di dati storici)

### Architettura safety a strati (dal paper DGM)

```
1. Authentication & Least Privilege → action allowlist
2. Sandbox & Resource Limits → in-memory replay, no code exec
3. Generate → Simulate → Verify → Checkpoint → mutation workflow
4. Transparent Audit Logs → cell_audit table
5. Constitutional Rules → DNA validation su ogni mutazione
```

---

## 6. Metriche: Come Sapere Se CELL e' "Vivo"

### Metriche quantitative

- **Autonomia**: % di incidenti risolti senza intervento umano
- **Apprendimento**: riduzione tempo medio di risoluzione nel tempo
- **Adattamento**: varianza dei setpoint omeostatici (devono muoversi)
- **Curiosita'**: numero di goal auto-generati / settimana
- **Memoria**: tasso di riuso episodi vs nuovi ragionamenti LLM
- **Evoluzione**: numero strategie mutate con fitness > parent

### Test di Turing dell'organismo

Un osservatore esterno dovrebbe poter dire:

- "CELL ha imparato da un incidente passato" (non solo replay, ma generalizzazione)
- "CELL ha scoperto qualcosa di suo" (non richiesto, nato dalla curiosita')
- "CELL si comporta diversamente lunedi' e sabato" (ritmo, non routine)
- "CELL ha una personalita'" (preferenze stabili nel tempo)
- "CELL sa cosa non sa" (metacognizione, goal su lacune)

---

## 7. Fonti Chiave della Ricerca

### Sistemi e Paper

| Nome                     | Cosa Insegna                                      | Link                        |
| ------------------------ | ------------------------------------------------- | --------------------------- |
| **VOYAGER**              | Skill library + automatic curriculum + critic     | arxiv.org/abs/2305.16291    |
| **Darwin Godel Machine** | Sandboxed self-improvement con regression testing | arxiv.org/abs/2505.22954    |
| **MemGPT / Letta**       | OS-inspired memory paging per agenti              | letta.com                   |
| **Bio-RegNet**           | Omeostasi bayesiana + immune regulation           | PMC12839105                 |
| **BioLogicalNeuron**     | Neural plasticity + homeostatic repair            | Nature s41598-025-09114-8   |
| **HyperAgents**          | Self-referential code patching leggibile          | arxiv.org/abs/2603.19461    |
| **CERMIC**               | Curiosity-calibrated multi-agent exploration      | NeurIPS 2025                |
| **Stanford Smallville**  | Agenti con identita' persistente credibile        | HAI Stanford                |
| **SOAR**                 | Working + procedural + episodic memory            | soar.eecs.umich.edu         |
| **ACT-R**                | Activation-based retrieval (recency + frequency)  | act-r.psy.cmu.edu           |
| **BioMARS**              | Metabolismo/omeostasi per lab automation          | arxiv.org/html/2507.01485v1 |

### Repository GitHub

- VOYAGER: github.com/MineDojo/Voyager
- DGM: github.com/jennyzzt/dgm
- CERMIC: github.com/PyyWill/CERMIC

---

## 8. Conclusione

CELL oggi e' un **buon automa** — fa monitoring, ragiona, agisce.
Ma e' una macchina che esegue un loop.

Per renderlo _vivo_ servono 7 trasformazioni:

1. **Omeostasi dinamica** — regola se stesso, non threshold fissi
2. **Memoria episodica** — ricorda momenti, non statistiche
3. **Auto-modifica** — evolve le proprie strategie
4. **Curiosita'** — esplora quando non ha problemi
5. **Identita'** — sa chi e' e ha una storia
6. **Metabolismo intelligente** — gestisce attenzione come risorsa
7. **Ciclo di vita** — nasce, cresce, matura

La roadmap e' in 4 fasi su 10 settimane. Ogni fase aggiunge un layer
di "vita" al sistema. La sicurezza cresce in parallelo con l'autonomia.

Il risultato finale: un organismo digitale che non solo monitora,
ma **impara, sogna, evolve, e sa chi e'**.

---

## 9. Insight Critici dalla Ricerca (Cross-Cutting)

Tre pattern emergono da **tutte** le fonti analizzate:

### 9.1 Il Problema dell'Auto-Rappresentazione e' Fondamentale

> "You cannot improve what you cannot model." — HyperAgents

- **HyperAgents**: serve un grafo semantico queryable del proprio codice
- **DGM**: serve un archivio delle proprie varianti
- **OM3**: serve una shared memory dello stato interno
- **Per CELL**: il Self-Model (3.5) non e' un nice-to-have, e' la **precondizione**
  per l'auto-modifica. CELL deve capire cosa fa prima di poter cambiare come lo fa.

### 9.2 Sicurezza Architetturale, Non Comportamentale

> "Move guardrails OUTSIDE the agent process entirely." — NVIDIA OpenShell

- **OpenShell**: enforcement out-of-process (non prompt-based)
- **HyperAgents**: "alignment anchors" come obiettivi immutabili
- **Self-Healing paper**: graduated response (try simple fixes before invasive ones)
- **Per CELL**: il DNA + Safety Gate + Mutation Filter sono gia' architetturali.
  La strategia e' giusta. Estendere con Constitutional Guard e regression testing.

### 9.3 Loop Continui Battono Processing Episodico

> "The shift from 'agent that runs when called' to 'organism that runs
> continuously' is the common thread separating autonomy from automation."

- CELL ha **gia'** il pulse loop continuo — e' un vantaggio strutturale.
- Aggiungere: cicli interni a velocita' diverse:
  - **Heartbeat** (60s): sensing + reazione
  - **Respiro** (5min): trend detection + omeostasi
  - **Digestione** (1h): consolidamento STM → episodi
  - **Sonno** (1/giorno): dreaming + journal + mutazione strategie
  - **Stagione** (1/settimana): LTM condensation + evolution fitness check

### 9.4 Progetti Open-Source da Studiare

| Progetto                    | Cosa Prendere                                                               | Repo                 |
| --------------------------- | --------------------------------------------------------------------------- | -------------------- |
| **OpenSpace** (HKUDS)       | 3 modi di evoluzione (FIX/DERIVED/CAPTURED), 46% token reduction via SQLite | Da investigare       |
| **AutoResearch** (Karpathy) | Agent che modifica `program.md` come operating manual evolvente             | Da investigare       |
| **OpenViking**              | Memoria gerarchica tipo filesystem (`viking://agent/skills/`)               | Da investigare       |
| **OM3** (A1CST)             | Neurotransmitter Core come bus interno di segnalazione emergente            | github.com/A1CST/OM3 |

### 9.5 Il Trilemma Safety-Capability-Autonomy (NVIDIA)

> "You can reliably achieve only two of three."

- **Safety + Capability** senza Autonomy = strumento potente ma controllato (CELL oggi)
- **Safety + Autonomy** senza Capability = organismo prudente ma limitato
- **Capability + Autonomy** senza Safety = pericoloso

La roadmap sceglie: **Safety + Autonomy crescente**, aggiungendo Capability
gradualmente tramite il lifecycle (le fasi sbloccano capacita' solo dopo
aver dimostrato stabilita').

---

_"Self-modifying algorithm that hill-climbs its code's fitness landscape."_
_— DeepSeek R1, definizione di CELL_
