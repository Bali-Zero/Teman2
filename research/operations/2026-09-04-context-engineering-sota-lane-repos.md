# Context management nei coding agent open-source — meccanismi concreti
(lane research-repos, 2026-09-04)

## 1. Aider — repomap tree-sitter + PageRank

**Meccanismo**: aider parsa ogni file sorgente con tree-sitter (AST language-specific), estrae tag `def` (definizioni: funzioni/classi/metodi) e `ref` (usi/riferimenti). Costruisce un grafo dove i file sono nodi e le dipendenze (chi referenzia chi) sono archi, poi esegue un **PageRank personalizzato** con restart-vector "biased" verso i simboli presenti nella chat corrente — un simbolo chiamato da 20 funzioni pesa più di un helper privato chiamato una volta. Il risultato: la repomap mostra solo *signatures* (non file interi), scelte per densità informativa/token.

**Numeri**: token budget default **1.000 token** (`--map-tokens`), fitting via **binary search** su `get_ranked_tags_map()` per restare entro ~15% del budget target (`max_map_tokens` default 1.024).

**Trade-off dichiarato**: anche solo la repomap può eccedere la context window per repo molto grandi → serve filtering selettivo, non inclusione comprensiva.

Fonti: aider.chat/2023/10/22/repomap.html · anishgandhi.com/aider-pagerank-codebase-ranking/ · agentpatterns.ai/context-engineering/repository-map-pattern/

## 2. Cline / Roo Code — Memory Bank + .clinerules

**Meccanismo**: "Memory Bank" = sistema di file markdown strutturati (`activeContext.md`, `progress.md`, ecc.) che **devono essere letti a inizio di OGNI task** — trasforma un agente stateless in uno con continuità cross-sessione. `.clinerules` è trattato come codice (versionabile, condivisibile) e può contenere sia istruzioni di memory-bank sia configurazioni custom.

**Auto-compaction**: "Auto Compact" agisce da buffer quando la window si riempie; il comando `/smol` o `/compact` fa la stessa compressione ma triggerabile manualmente dentro lo stesso task (utile in debugging profondo per non rompere il flow).

**Trade-off**: nessun numero di token esplicito nelle fonti trovate — il pattern è dichiarativo (istruzioni scritte dall'utente), non algoritmico come la repomap di aider.

Fonti: cline.bot/blog/how-to-think-about-context-engineering-in-cline · docs.cline.bot/features/memory-bank · github.com/cline/prompts/blob/main/.clinerules/memory-bank.md

## 3. OpenHands (ex OpenDevin) — Condenser + Event Stream + Microagents

**Architettura**: la history è uno **event stream** append-only (azioni + osservazioni). Un **EventLog persistente** consente replay completo anche dopo compressione.

**Condenser** (famiglia di classi): `NoOpCondenser` (pass-through) · `LLMSummarizingCondenser` (usa un LLM, spesso più economico del reasoning LLM, per riassumere) · `PipelineCondenser` (concatena più condenser) · `RollingCondenser` (classe base con trigger a soglia).

**Numeri concreti**: trigger automatico quando il conteggio eventi supera `max_size` = **120 eventi** (default); trigger manuale via evento `CondensationRequest` su context-error. Pattern "rolling window": preserva i primi `keep_first`=**4** eventi, riassume la porzione centrale, preserva la coda recente; target output ≈ **60 eventi** (`max_size // 2`) post-condensazione. Il riassunto viene inserito come testo a un `summary_offset` specifico e gli eventi "dimenticati" restano tracciati (`forgotten_event_ids`) — mai cancellati fisicamente dal log.

**Microagents**: convenzioni/knowledge di progetto che si caricano **automaticamente su trigger** (l'agente "conosce" il repo appena atterra) — pattern di context injection selettiva, non sempre-caricato.

**Trade-off dichiarato**: senza condensazione, la gestione del contesto scala **quadraticamente** nel tempo; con condensazione scala **linearmente**.

Fonti: docs.openhands.dev/sdk/arch/condenser · openhands.dev/blog/openhands-context-condensensation-for-more-efficient-ai-agents · github.com/OpenHands/OpenHands/pull/7311

## 4. SWE-agent (Princeton) — Agent-Computer Interface (ACI)

**Tesi centrale**: l'interfaccia con cui l'agente vede/manipola il computer è determinante quanto il prompt — un agente senza ACI ben tarata (baseline shell-only) fa molto peggio dello stesso modello con ACI dedicata.

**File viewer a finestra**: comando `open` mostra **100 righe per turno** con numeri di riga + statistiche file; navigazione con `scroll up/down` o `goto <linea>`. Trovato empiricamente che 100 righe è il punto ottimale (non "tutto il file").

**Altri elementi ACI**: linter automatico sui comandi di edit (blocca codice sintatticamente errato prima del submit); search directory che elenca **solo i file con match** (dettagli per-match "troppo confusi per il modello" — scelta deliberata di compattezza su completezza); messaggi espliciti su output vuoto ("comando riuscito, nessun output").

**Risultati**: SWE-agent + GPT-4 Turbo → 12.47% pass@1 su SWE-bench full, 18.00% su SWE-bench Lite, +64% relativo rispetto a un agente shell-only su Lite (SOTA all'epoca).

**Principi**: simplicity, compactness, concise feedback, error guardrails — ottimizzati per l'interazione LM, non umana.

Fonti: swe-agent.com/latest/background/aci/ · paper NeurIPS 2024 (arXiv 2405.15793)

## 5. MemGPT / Letta — Virtual context management (OS-like paging)

**Architettura a 3 livelli**, ispirata alla memoria virtuale OS (l'LLM è il proprio "memory manager"):
- **Core memory**: analoga alla RAM — persona + contesto critico sempre nella context window, editabile dall'agente stesso (self-editing).
- **Recall memory**: storico completo delle interazioni, ricercabile ma fuori dalla finestra attiva; in Letta salva su disco automaticamente.
- **Archival memory**: knowledge esplicitamente elaborata, indicizzata su vector DB esterno — a differenza della recall (raw), contenuto processato/strutturato.

**Meccanismo**: l'agente sposta dati tra core memory (in-context) e archival/recall (esterne) tramite **tool call espliciti** — illusione di memoria illimitata dentro un limite fisso di token.

Fonti: letta.com/blog/agent-memory/ · vectorize.io/articles/mem0-vs-letta · vectorize.io/articles/hindsight-vs-letta

## 6. Gemini CLI — GEMINI.md hierarchy + compressione a soglia

**Hierarchy di caricamento**: `~/.gemini/GEMINI.md` (globale) → risalita da cwd fino a project root → scansione sub-directory per istruzioni component-specific; più specifico sovrascrive più generale.

**Compressione**: `/compress` sostituisce l'INTERA chat history con un summary. Soglia configurabile `chatCompression` come % della finestra (es. 0.6 = trigger a 60%). La compressione NON salva in memoria a lungo termine — è locale alla conversazione — mentre le voci in GEMINI.md sopravvivono perché vivono fuori dal chat context.

**Checkpointing**: `/restore` cattura stato working directory + workspace; il restore sovrascrive i file E resetta la conversazione a quello snapshot (rollback combinato codice+contesto).

Fonti: geminicli.com/docs/cli/gemini-md/ · aipositive.substack.com/p/a-look-at-context-engineering-in · google-gemini.github.io/gemini-cli/docs/cli/commands.html

## 7. Codex CLI (OpenAI) — AGENTS.md + compaction a doppio percorso

**AGENTS.md**: concatenato nella context window all'inizio di OGNI sessione — la prima cosa che Codex legge. Costruito camminando il filesystem (hierarchy), pensato come "README per agenti".

**Compaction a due percorsi**: per modelli NON-Codex, summarization locale via LLM con compaction-prompt visibile nel codice (summary con prefisso `_summary` anti-loop). Per i modelli Codex, endpoint remoto `POST /v1/responses/compact` → blob AES-encrypted la cui chiave resta sui server OpenAI; al turno successivo il server decripta e antepone un "handoff prompt".

Fonti: codex.danielvaughan.com/2026/03/31/codex-cli-context-compaction-architecture/ · thepromptshelf.dev/blog/agents-md-codex-setup-guide-2026/

## 8. Claude Code — CLAUDE.md hierarchy + skills progressive disclosure + subagent

**CLAUDE.md come "table of contents"**: root file = indice, skill = capitoli, agent guide = appendici — l'agente carica solo ciò che serve.

**Skills — progressive disclosure a 3 livelli** (fonte Anthropic engineering):
1. **Livello 1 (metadata)**: `name` + `description` di ogni skill pre-caricati nel system prompt — pochi token, Claude sa che esiste senza pagarne il body.
2. **Livello 2 (core content)**: su rilevanza, legge il `SKILL.md` completo via tool call.
3. **Livello 3+ (risorse bundled)**: file referenziati dentro SKILL.md caricati SOLO quando servono.
"Il contenuto bundlabile in una skill è di fatto illimitato" — con filesystem access l'agente evita di caricare tutto. Design: separare i path quando i contesti sono "mutuamente esclusivi o usati raramente insieme".

**Subagent**: "spawna un agente nel momento in cui un task inquinerebbe il context principale"; anti-pattern: 20 file-read + 12 grep nella sessione principale e poi pianificare col rumore caricato — meglio: subagent di ricerca → report pulito → planning pulito.

**Auto-compact**: "il modello è al suo punto meno intelligente proprio durante l'auto-compact" — gestirlo proattivamente, non subirlo.

**Confronto soglie di compaction (7 agenti, fonte comparativa 2026-04)**:
| Agent | Soglia trigger | Formula |
|---|---|---|
| Gemini CLI | ~50% | default, configurabile |
| Roo Code | ~86–92% | `contextWindow × 0.9 − maxOutputTokens` |
| Claude Code | ~89% | `contextWindow − min(maxOutput, 20k) − 13k` |
| Codex CLI | ~90% | hard ceiling, configurabile solo al ribasso |
| Pi | ~92% | `contextTokens > window − 16.384` |
| OpenCode | ~96–99% | `contextTokens ≥ context − reserved` |
| OpenHands | event-based | 120 eventi o trigger manuale |

Claude Code usa **5 meccanismi di difesa**: microcompact (senza LLM), clearing output tool, summarization LLM completa, cache reuse, compact guidato dall'utente. Gemini CLI: two-pass summarization con self-critique, preserva verbatim il 30% finale. OpenCode: protegge gli ultimi 40.000 token (soglia minima prunable 20.000).

**Costo nascosto (KV cache)**: una compaction su 125.000 token ≈ $0.40 — ~21 turni cache-hit ($0.019 vs $0.23 per 60k token). Checklist pre-compaction su 7 categorie (path, decisioni, errori, firme, test, env var, task) → +49% qualità summary a costo trascurabile ($0.013).

Fonti: anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills · alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/ · codex.danielvaughan.com/2026/04/10/context-compaction-showdown-coding-agents/

## 9. LangChain/LangGraph — framework "Write / Select / Compress / Isolate"

**Definizione**: context engineering = "l'arte e la scienza di riempire la context window con esattamente l'informazione giusta a ogni step della traiettoria dell'agente".

**4 strategie**:
- **Write**: salvare contesto FUORI dalla window per uso futuro — pattern "scratchpad".
- **Select**: tirare DENTRO ciò che serve (retrieval mirato).
- **Compress**: mantenere solo i token necessari al task.
- **Isolate**: dividere il contesto (sub-agenti con contesti separati) per evitare cross-contamination.

LangGraph implementa via **checkpointing di stato** (thread-scoped memory) + long-term memory esterna.

Fonti: langchain.com/blog/context-engineering-for-agents · github.com/langchain-ai/context_engineering · deepwiki.com/langchain-ai/context_engineering/2-context-engineering-strategies

## 9bis. Tendenze 2026

- Context engineering = "successore del prompt engineering": gli agenti falliscono per **state-management failure**, non per prompt failure.
- 4 failure mode ricorrenti: **context poisoning**, **context distraction**, **context confusion**, **context clash**.
- Ecosistema memoria agentica: ~21 framework, ~20 vector store, 3 modelli hosting — disciplina matura.

Fonti: mem0.ai/blog/state-of-ai-agent-memory-2026 · sourcegraph.com/blog/context-engineering · jobsbyculture.com/blog/context-engineering-guide-2026

---

## Principi operativi estraibili

- **Rank, don't dump** (Aider): grafo riferimenti + PageRank battono "includi tutto" — signatures pesate per centralità.
- **Memory esterna leggibile a inizio task, non nel prompt system** (Cline Memory Bank, MemGPT): persistenza cross-sessione in file/DB letti ESPLICITAMENTE all'avvio, mai stipata nel context permanente.
- **Mai cancellare, sempre marcare "dimenticato"** (OpenHands `forgotten_event_ids`): history compressa recuperabile — event sourcing, non distruzione.
- **Interfaccia > prompt** (SWE-agent ACI): finestre fisse (100 righe), search compatta, messaggi espliciti su output nullo.
- **Soglia di trigger esplicita e misurabile** (tabella 7 agenti): formula percentuale/evento-based dichiarata, mai "quando si riempie".
- **Progressive disclosure a 3 livelli = standard** (Claude Skills, GEMINI.md hierarchy, repomap): metadata sempre in context, corpo su match, risorse profonde solo se referenziate.
- **La compaction ha costo economico misurabile e non lineare** (KV cache): checklist pre-compaction 7 categorie = +49% qualità a costo trascurabile.
- **Isolamento per sotto-task > contesto condiviso grande** (LangGraph Isolate, subagent pattern, microagents): "fan-out a contesto pulito, poi report sintetico".
