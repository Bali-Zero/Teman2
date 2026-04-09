# Mata Garuda — HKUDS/AutoAgent Evaluation

> Data: 2026-04-09 | Sessione S04
> Repo: github.com/HKUDS/AutoAgent
> Stars: 9,065 | Forks: 1,278 | Last push: 2025-10-16 | License: MIT
> Paper: arXiv 2502.05957 (HKU Data Science Lab)
> Discovery via GitHub MCP API (no clone yet)

---

## TL;DR — Verdetto

**ISPIRAZIONE FORTE, NON FORK DIRETTO.**

AutoAgent ha pattern architetturali pregevoli (meta-agent, registry, RAG memory, agent self-creation) ma:
- È costruito su `litellm` con assunzioni profonde su API HTTP-based (OpenAI/Anthropic/Gemini/DeepSeek/Groq/Grok)
- L'esecuzione passa SEMPRE per Docker container
- Il "self-update" prevede git clone di un mirror del repo dentro il container
- Conversione a CLI-only richiede sostituire il cuore (`autoagent/core.py`) — ~700 LOC critiche

**Raccomandazione:** estrarre i 4 pattern chiave e reimplementarli puliti in Mata Garuda, NON forkare l'intero stack.

---

## 1. Cos'è AutoAgent

Framework Python "Fully-Automated & Zero-Code LLM Agent" del HKU Data Science Lab. In sostanza:

1. **MetaChain** = clone semplificato di OpenAI Swarm — un loop `completion → tool calls → next agent`
2. **Agent Editor / Workflow Editor** = meta-agent che CREA altri agenti scrivendo file Python
3. **Tool Registry** = registry decorator-based per agents/tools/workflows
4. **Memory layer** = code memory + RAG memory + tool memory (Chroma backend)
5. **Docker environment** = ogni esecuzione vive in `tjbtech1/metachain:latest` (immagine pre-built)
6. **GAIA benchmark winner** (Deep Research mode) — qualità validata

### Modi d'uso (3)

| Modo | Descrizione |
|---|---|
| `user mode` | Deep Research multi-agent (alternativa a OpenAI Deep Research) |
| `agent editor` | Crea singoli agenti via natural language |
| `workflow editor` | Crea workflow multi-agente via natural language |

### Stack tecnico chiave

```
litellm 1.55.0          # LLM provider abstraction (CRITICAL DEPENDENCY)
openai >= 1.52.0
chromadb                # Vector store per memory
playwright 1.39.0       # Browser env
browsergym 0.13.0       # Browser env
docling                 # Document parsing
sentence_transformers   # Embeddings
faster_whisper          # Audio
docker (esterno)        # Sandbox runtime
```

---

## 2. Architettura interna (verificata leggendo i sorgenti)

### Punto centrale — `autoagent/core.py`

```python
from litellm import completion, acompletion
# ...
class MetaChain:
    def get_chat_completion(self, agent, history, ...):
        # 700 LOC che chiamano direttamente litellm.completion(**create_params)
        completion_response = completion(**create_params)
```

**TUTTE le inferenze passano da `litellm.completion()` o `litellm.acompletion()`.**
Non c'è abstraction layer "ProviderAdapter" — `litellm` È l'abstraction layer.

### Meta-agent — `autoagent/agents/meta_agent/agent_editor.py`

Sorprendentemente compatto (40 righe):

```python
def get_agent_editor_agent(model: str) -> str:
    def instructions(context_variables):
        return f"""You are an agent editor agent...
The existing agents are shown below: {list_agents(context_variables)}
If you want to create a new agent, follow the format of `get_dummy_agent`:
```python
{read_file('autoagent/agents/dummy_agent.py')}
```
..."""
    tool_list = [list_agents, create_agent, delete_agent, run_agent, execute_command]
```

**Il meta-agent è semplicemente un agente con 5 tool: list/create/delete/run agents + execute_command.**
La "magia" è tutta nel prompt + nel registry decorator (`@register_agent`).

### Registry pattern — `autoagent/registry.py`

Decorator-based, walks recursively `autoagent/agents/**/*.py` e auto-importa:

```python
def import_agents_recursively(base_dir, base_package):
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.py'):
                importlib.import_module(...)
```

Pattern semplice ma potente: aggiungi un file → l'agente è disponibile.

### Memory — `autoagent/memory/`

5 tipi di memory, tutti basati su ChromaDB:
- `code_memory.py` — RAG su codebase
- `codetree_memory.py` — RAG con tree-sitter parsing
- `paper_memory.py` — RAG su paper accademici
- `rag_memory.py` — RAG generico
- `tool_memory.py` — semantic search su tools disponibili

### Environment — `autoagent/environment/`

**Bivio importante:** ci sono SIA `docker_env.py` (13KB) SIA `local_env.py` (4KB).

Il README spinge Docker, ma `local_env.py` esiste — significa che c'è una via per girare senza container. Da verificare se è prima-classe o second-class citizen.

### Anche c'è `browser_env.py` (28KB)

Browser automation completo basato su browsergym + playwright. Per OSINT scraping potrebbe essere riutilizzabile DIRETTAMENTE.

---

## 3. Fit con Mata Garuda — analisi punto per punto

### ✅ Cosa è ALLINEATO

| Requisito MG | Cosa offre AutoAgent |
|---|---|
| Meta-agent Lamarckian | Agent Editor + Workflow Editor (concept identico, manca solo GENOME.md) |
| Multi-agent runtime | MetaChain loop (Swarm-style) |
| RAG memory | 5 memory backends Chroma |
| Tool registry dinamico | Decorator `@register_agent` + auto-walk |
| Browser scraping | `browser_env.py` (browsergym + playwright) — utile per scraper OSINT |
| MIT license | Compatibile con uso interno e fork privato |

### ❌ Cosa è IN CONFLITTO con i vincoli MG

| Vincolo MG | Conflitto AutoAgent | Severity |
|---|---|---|
| **LLM CLI-only** (no API Anthropic/Gemini) | `litellm.completion()` ovunque, designed-for-API | 🔴 CRITICO |
| **OSINT blindato locale** | Default `git_clone=True` clona mirror su GitHub container, `auto deep-research` esegue in Docker pre-built `tjbtech1/metachain:latest` | 🔴 CRITICO |
| **One-way IN, no cloud leakage** | Default invia query a OpenAI/Anthropic via litellm | 🔴 CRITICO |
| **Stack minimale (Pro 48GB)** | Dipendenze pesanti: chromadb, browsergym, faster_whisper, sentence_transformers, docling, moviepy | 🟡 MEDIO |
| **Mai API Anthropic/Google** | README presenta Anthropic come default model | 🟡 MEDIO (solo config) |
| **Pattern semplici, niente abstrazioni speculative** | Litellm + Chroma + Docker + browsergym = stack pesante | 🟡 MEDIO |

### 🟢 Cosa si può ESTRARRE come ispirazione

1. **Pattern meta-agent** (40 righe `agent_editor.py`) — replicabile in 1 giorno
2. **Pattern registry recursive** (`autoagent/agents/__init__.py`) — 30 righe, copiabile
3. **Concept "case_resolved" / "case_not_resolved"** in `main.py` — fitness signal Lamarckian gratuito
4. **MetaChain loop** (`core.py` simplified) — vale come reference per il nostro runtime
5. **Browser env** — potenzialmente usabile come dependency standalone (browsergym + playwright)

---

## 4. Conversione CLI-only — analisi di invasività

**Domanda:** quanto codice devo riscrivere per renderlo CLI-only?

### Touchpoints litellm

Da grep `litellm` nel repo: ~13 file lo importano. I critici:

| File | Uso | Sostituibile? |
|---|---|---|
| `autoagent/core.py` | `from litellm import completion, acompletion` — heart del sistema | 🔴 Reimplementazione totale (~700 LOC) |
| `autoagent/fn_call_converter.py` | `litellm.types`, conversione function-call ↔ non-function-call | 🟡 Riscrivibile (~900 LOC) |
| `autoagent/agents/*` | Indirettamente via `MetaChain.run()` | 🟢 Funzionano se sostituisco core.py |

### Cosa significherebbe "CLI-only adapter"

Servirebbe scrivere una classe `CliCompletion` che:
1. Riceve `messages` in formato OpenAI
2. Lancia `claude --print` (o `gemini --print`, o `codex exec`) come subprocess
3. Parsa l'output → ritorna in formato `litellm.completion` (oggetto `ModelResponse`)
4. Gestisce tool calls — qui è il problema: i CLI Claude/Gemini NON espongono function calling nativo via stdin/stdout
5. Quindi servirebbe usare `NON_FN_CALL` mode di AutoAgent + parsing manuale dei tool call dal testo

**Stima:** 2-4 giorni di lavoro per un adapter funzionante, MA si perde:
- Streaming (i CLI non streamano in modo affidabile)
- Function calling nativo (degradato a JSON-in-text)
- Caching prompt
- Latenza (subprocess startup ~500ms-1s vs ~50ms HTTP)

### Vincolo bloccante: il meta-agent richiede modello forte

L'Agent Editor crea agenti via codice. Senza function calling robusto, i `create_agent`/`run_agent`/`execute_command` calls diventano fragili. Il meta-agent è proprio dove serve la qualità massima.

**Conclusione:** la conversione CLI-only è tecnicamente fattibile ma snatura il progetto.

---

## 5. Confronto con agent-taxonomy (40b)

| Dimensione | agent-taxonomy | HKUDS/AutoAgent |
|---|---|---|
| Tipo | Filosofia + GENOME.md template | Framework runtime completo |
| LOC | ~500 (markdown + small CLI) | ~50,000 (Python + deps) |
| LLM dependency | Nessuno (solo Markdown) | litellm/OpenAI hard-coupled |
| Lamarckian pattern | NATIVO (è il core insight) | NON esiste come tale, ma c'è il scaffold (`case_not_resolved` → retry) |
| Self-update | Via git commit di GENOME.md | Via clone mirror in container + write file |
| Adottabilità Mata Garuda | 🟢 Diretta (filosofia + 1 file Markdown) | 🔴 Pesante (refactor cuore) |

**Sinergia:** GENOME.md (agent-taxonomy) + meta-agent pattern (AutoAgent) sono complementari. Il primo è "cosa", il secondo è "come".

---

## 6. Decisione e prossimi step

### Decisione

**Non forkare AutoAgent.** Estrarre 4 pattern e reimplementarli puliti dentro Mata Garuda:

1. **Meta-agent loop** — adattamento del pattern `agent_editor.py` (40 righe) usando i nostri runtime CLI (Claude/Gemini/Codex)
2. **Registry recursive** — copia del pattern di `agents/__init__.py` (30 righe)
3. **Case resolved/not resolved** — fitness signal del MetaChain `main.py` (riusabile come "GENOME mutation trigger")
4. **Browser env standalone** — valutare se usare browsergym direttamente per gli scraper OSINT

### Cosa NON estrarre

- ❌ `autoagent/core.py` (litellm-coupled)
- ❌ `autoagent/memory/*` (preferiamo NLM + Qdrant locale già esistenti)
- ❌ `autoagent/environment/docker_env.py` (vincolo OSINT: niente container Docker generici)
- ❌ Stack chromadb/sentence_transformers/faster_whisper (overlap con stack Mata Garuda esistente)

### Prossimi micro-step

1. **40d-AUTOAGENT-PATTERNS.md** — documentare i 4 pattern in dettaglio con codice di riferimento (estratti puliti)
2. **02-ARCHITECTURE.md** — aggiornare: meta-agent layer ispirato ad AutoAgent + GENOME.md (agent-taxonomy)
3. **50-BUILD-ORDER.md** — sequenziare l'implementazione del meta-agent runtime
4. **POC**: scrivere `mata-garuda/meta-agent/loop.py` minimale (Python, ~150 LOC) che:
   - usa subprocess per chiamare `claude --print` / `gemini --print`
   - implementa il loop `instruction → tool calls → next agent`
   - registra agenti via decorator
   - ha un GENOME.md root che si aggiorna via Lamarckian pattern

### Tempistica realistica

Reimplementazione del nostro meta-agent runtime: ~3-5 giorni di lavoro focalizzato.
Forkare e adattare AutoAgent: ~2 settimane MIN, con risultato fragile e non aderente ai vincoli.

**Reimplementare conviene 3-4x.**

---

## 7. Open questions

1. ~~`local_env.py` di AutoAgent è first-class?~~ **RISOLTO 2026-04-09 in 40d**: NO. Richiede conda + env hard-coded `auto`, è un mock di Docker, non un runtime alternativo. Conferma decisione: reimplementare.
2. browsergym standalone è gestibile sul nostro stack? **DIFFERITO**: usare playwright direttamente (già in `apps/bali-intel-scraper/`), estrarre solo i 3 pattern observation/action/element-IDs come idea — vedi 40d Pattern 4.
3. ~~Pattern `case_resolved`/`case_not_resolved` merita doc?~~ **RISOLTO 2026-04-09**: documentato in 40d Pattern 3 con hook Lamarckian + escalation a meta_agent.
4. Vogliamo provare AutoAgent in `auto deep-research` mode una volta come benchmark di qualità (NON come dipendenza)? **APERTO** — utile ma non blocking.

---

## 8. Fonti verificate (no hallucination)

- ✅ `github.com/HKUDS/AutoAgent` — repo letto via GitHub MCP API (non clone)
- ✅ `LICENSE` letto: MIT
- ✅ `setup.cfg` letto: dipendenze confermate, `litellm==1.55.0` pinned
- ✅ `autoagent/core.py` letto integralmente (~700 LOC)
- ✅ `autoagent/main.py` letto integralmente
- ✅ `autoagent/agents/meta_agent/agent_editor.py` letto integralmente
- ✅ `autoagent/agents/__init__.py` letto integralmente (registry pattern)
- ✅ `autoagent/environment/` directory listing verificato
- ✅ `constant.py` letto (env vars, model defaults, NOT_USE_FN_CALL list)
- ⚠️ NON letto: `tools/`, `flow/`, `evaluation/` — non rilevanti per la decisione
- ⚠️ NON clonato localmente — analisi solo su GitHub. Se serviva ulteriore profondità, clonare in `/tmp/autoagent-eval` per ispezione interattiva.

---

**Status:** Discovery completata 2026-04-09. Decisione: ispirazione, non fork.
