# Prompt di Ricerca — Super Agent Architettura 2026

## Contesto comune (da includere in entrambi i prompt)

```
Sto progettando un "Super Agent" autonomo per un backend Python FastAPI in produzione (88 routers, 244 servizi, ~4000 test). L'agente deve operare H24 su una macchina locale (M4 Pro, 48GB RAM) e migliorare progressivamente la qualità del codice senza supervisione umana diretta.

Stack: Python 3.11, FastAPI, asyncpg, Qdrant (vector DB), LangGraph, pytest, ruff.
Infra: Fly.io (prod), macchina locale (dev), OpenClaw come agent runtime (Claude Opus 4.6 + Gemini + Ollama locale).
Il codebase ha ~4000 test, 0 failing dopo il cleanup. L'agente non deve mai peggiorare la test suite.
```

---

## PROMPT 1 — Per GEMINI (Deep Research)

```
Sono un senior engineer che sta progettando un agente autonomo di code improvement per un backend Python FastAPI in produzione. Ho bisogno di una ricerca approfondita sullo stato dell'arte (marzo 2026) di questi temi specifici:

CONTESTO: [inserire contesto comune sopra]

RICERCA RICHIESTA — 5 aree:

1. AUTONOMOUS CODE IMPROVEMENT AGENTS (stato dell'arte marzo 2026)
   - Quali framework/tool esistono per agenti che migliorano codice autonomamente?
   - Cercare: SWE-Agent, SWE-bench, Devin, Factory Code Droid, Codegen (Poolside), Amazon Q Developer Agent, GitHub Copilot Workspace, Sweep AI, CodeRabbit, Qodo (ex-CodiumAI)
   - Per ognuno: architettura, come decidono COSA fixare, come validano i fix, come gestiscono il rollback
   - Quali usano il pattern "observe → plan → act → verify → commit"?
   - Quali supportano il running continuo (H24 cron) vs on-demand?

2. SAFETY PATTERNS per agenti che modificano codice in produzione
   - Come le aziende enterprise (Google, Meta, Spotify, Stripe) gestiscono gli agenti che committano codice?
   - Pattern "Shadow Mode" (l'agente propone ma non applica) vs "Autonomous Mode" (applica e rollbacka se rompe)
   - Guardrail patterns: file locking, scope limiting, diff size caps, branch isolation
   - Come si implementa un "watchdog" che monitora l'agente e lo ferma se devia?
   - Rollback automatico: git-based vs snapshot-based vs container-based
   - Quante aziende nel 2026 lasciano davvero agenti committare senza review umana? Quali guardrail usano?

3. ARCHITECTURE DECISION RECORDS (ADR) generati da AI
   - Il pattern "Repository-Native" dove l'agente salva le sue decisioni in markdown nel repo (.agent/decisions/)
   - Esiste un RFC, standard, o best practice per questo? O è ancora emergente?
   - Come strutturare un ADR auto-generato perché sia utile (non un dump di JSON)?
   - Esempi reali di aziende che usano ADR generati da AI
   - Differenza tra ADR e "commit message dettagliato" — quando serve uno vs l'altro?

4. TEST SUITE come GUARDRAIL per agenti autonomi
   - Pattern "baseline test count" — l'agente non può mai far scendere il numero di test che passano
   - Come implementare un "test oracle" che l'agente consulta prima e dopo ogni modifica
   - Mutation testing come metrica di qualità per i fix dell'agente (l'agente migliora davvero i test o li ammorbidisce?)
   - Coverage come constraint: l'agente non può ridurre la coverage
   - Integration testing per agenti: come testare che l'agente stesso funziona correttamente

5. CRON vs EVENT-DRIVEN vs CONTINUOUS per agenti di code quality
   - L'agente dovrebbe girare ogni N ore (cron), reagire a eventi (git push, test failure), o girare continuamente?
   - Pro/contro di ogni approccio per un backend con ~4000 test che richiede 7 minuti per la full suite
   - Come gestire la concorrenza se l'agente gira mentre lo sviluppatore sta committando?
   - Pattern "interruptible agent" — l'agente può essere fermato a metà senza corrompere lo stato

OUTPUT RICHIESTO:
- Per ogni area, riporta i 3-5 approcci più rilevanti con pro/contro
- Includi link a paper, repo GitHub, blog post o documentazione
- Distingui chiaramente tra "funziona in produzione in aziende reali" e "prototipo/ricerca"
- Alla fine, una RACCOMANDAZIONE sintetica su quale architettura adottare dato il mio contesto specifico
```

---

## PROMPT 2 — Per GROK (Web Real-time + X/Twitter sentiment)

```
Sto progettando un agente autonomo H24 che migliora il codice di un backend Python FastAPI in produzione. Ho bisogno di capire cosa sta REALMENTE funzionando nel mondo reale a marzo 2026, non solo in teoria.

CONTESTO: [inserire contesto comune sopra]

RICERCA RICHIESTA — focus su dati reali, opinioni di practitioners, e lesson learned:

1. REAL-WORLD FAILURES di agenti autonomi di codice (2025-2026)
   - Cercare su X/Twitter, Hacker News, Reddit (r/programming, r/ExperiencedDevs, r/MachineLearning): storie di agenti AI che hanno rotto codebase, introdotto bug sottili, o generato "Shadow Tech Debt"
   - Cercare: "AI agent broke production", "autonomous coding agent failure", "SWE-agent disaster", "Devin failure", "AI introduced bugs"
   - Quali sono i failure modes più comuni? (test che passano ma il codice è sbagliato, mock che nascondono bug reali, fix superficiali che spostano il problema)
   - Esiste un "hall of shame" o post-mortem pubblici?

2. COSA DICONO I PRACTITIONERS su autonomous code agents nel 2026
   - Sentiment su X/Twitter verso Devin, Factory, SWE-Agent, Codegen, Amazon Q Agent
   - Quali tool vengono effettivamente USATI in produzione vs quali sono solo demo/hype?
   - Thread di sviluppatori che descrivono il loro setup di code improvement automatico
   - Cercare opinioni di: @karpathy, @swaborhees, @alexalbert__, @simonw, @antirez, @gaborcselle, @emollick su autonomous coding agents
   - C'è consenso su "quando è pronto per produzione" vs "solo per side projects"?

3. PATTERN "WATCHDOG" e ROLLBACK nella pratica
   - Come implementano il rollback le CI/CD pipeline moderne (GitHub Actions, GitLab CI) quando un agente rompe qualcosa?
   - Cercare: "git bisect automated", "automatic rollback CI", "canary deployment for code changes"
   - Pattern "circuit breaker" applicato al code generation: dopo N fix falliti, l'agente si ferma
   - Cercare post su: come Cursor, Windsurf, Cline gestiscono i rollback quando generano codice sbagliato

4. OPENCLAW / CLAUDE CODE / GEMINI CLI come agent runtime
   - Come altri sviluppatori usano OpenClaw, Claude Code, o Gemini CLI come "motore" per agenti H24?
   - Cercare setup dove qualcuno ha messo Claude/Gemini in un cron job per migliorare codice
   - Cercare: "Claude Code automated", "Gemini CLI cron", "OpenClaw autonomous", "AI agent crontab"
   - Qualcuno ha già implementato un pattern simile a quello che sto progettando? Come è andato?

5. COST/BENEFIT reale di agenti autonomi di codice
   - Quanto costa in API calls far girare un agente H24? (token usage per fix, costo mensile stimato)
   - Quanto tempo di developer risparmia realmente?
   - Cercare: "AI code agent ROI", "automated refactoring cost", benchmark di tempo risparmiato
   - Il rapporto costo/beneficio migliora con modelli più piccoli (Haiku, Flash) per task semplici?
   - Strategie di "tiered reasoning": task semplici → modello piccolo, task complessi → Opus/Pro

OUTPUT RICHIESTO:
- Link diretti a thread X/Twitter, post Hacker News, post Reddit che supportano ogni punto
- Distinguere chiaramente tra "ho visto un demo su YouTube" e "lo uso in produzione da 6 mesi"
- Opinioni contrarian welcome — se c'è chi dice "non funziona e non funzionerà", riportarlo
- Alla fine: le 3 lezioni più importanti da chi ci ha provato prima di me
```

---

## PROMPT 3 — Per CLAUDE (quello che faccio io nel frattempo)

Mentre aspetto i risultati di Gemini e Grok, io analizzo:

1. L'architettura OpenClaw disponibile (`openclaw agent --help`, API, session management)
2. I pattern di test del nostro codebase — quali test sono fragili, quali sono robusti
3. Le metriche di qualità che il super agente dovrebbe ottimizzare
4. Il design del watchdog e dei guardrails specifici per il nostro progetto
