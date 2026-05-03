# Design: Zan & The Specialists — Agentic Framework Integration

**Date:** 2026-03-04
**Status:** Approved
**Author:** Zero + Claude Opus 4.6

---

## 1. Obiettivo

Potenziare OpenClaw (ZAN) con framework agentici specializzati Python, mantenendo l'architettura "orchestratore + specialisti" e la regola zero-costi-per-token.

## 2. Decisioni Architetturali

| Decisione    | Scelta                                                 | Motivazione                                    |
| ------------ | ------------------------------------------------------ | ---------------------------------------------- |
| Integrazione | **Mix intelligente** — canale diverso per framework    | Ogni framework ha esigenze diverse             |
| LLM          | **Claude MAX Proxy** (`localhost:3456/v1`)             | $0, Opus/Sonnet/Haiku, richiede Claude Desktop |
| Runtime      | **Locale su Pro** (MacBook Pro M4 Pro 48GB)            | Massima velocita iterazione, nessun deploy     |
| Formato      | **OpenClaw Skills** in `~/.openclaw/workspace/skills/` | Funziona oggi, venv isolati                    |
| Ordine       | KBLI Validator → CRM Query → War Room Crew             | Crescente complessita                          |

## 3. I 4 Pilastri Agentici

| #   | Framework             | Ruolo                                                        | Tipo              | Stato           |
| --- | --------------------- | ------------------------------------------------------------ | ----------------- | --------------- |
| 1   | **PydanticAI**        | Ispettore Legale — validazione KBLI type-safe                | Skill (stateless) | Da implementare |
| 2   | **Agno** (ex Phidata) | Archivista CRM — query PostgreSQL in linguaggio naturale     | Skill (stateless) | Da implementare |
| 3   | **CrewAI**            | Potenzia war_room — orchestrazione intelligente multi-agente | Skill (stateless) | Da implementare |
| 4   | **LangGraph**         | Gia nel backend-rag — Knowledge Graph agentic                | Backend router    | Esistente       |

## 4. POC #1: KBLI Validator (PydanticAI)

### Scopo

Input: descrizione business in linguaggio naturale
Output: JSON strutturato con codice KBLI, risk level, PMA eligibility, Coretax flags

### Schema Output

```python
class KBLIValidation(BaseModel):
    kbli_code: str                    # es. "47911"
    kbli_title_id: str                # titolo ufficiale indonesiano
    kbli_title_en: str                # titolo inglese
    confidence: float                 # 0.0-1.0
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    pma_eligible: bool
    pma_max_ownership: Optional[int]  # percentuale, es. 67
    coretax_flags: list[str]          # es. ["REQUIRES_TAX_AUDIT", "DNI_RESTRICTED"]
    requires_special_license: bool
    notes: str                        # spiegazione breve
```

### Data Source

`source_documents/KBLI_2025_FINAL_CLEAN.json` (1,563 codici con campo `intel_2026`)

### LLM Config

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

model = OpenAIChatModel(
    "claude-sonnet-4",
    provider=OpenAIProvider(
        base_url="http://localhost:3456/v1",
        api_key="not-needed"
    )
)
agent = Agent(model, output_type=KBLIValidation)
```

### Flusso

1. ZAN chiama `validate.py --input "ristorante italiano con delivery a Bali"`
2. Script carica JSON KBLI come contesto
3. PydanticAI con Claude proxy analizza e produce output tipizzato
4. Risultato JSON su stdout → ZAN lo legge e risponde

### File

```
~/.openclaw/workspace/skills/kbli-validator/
├── SKILL.md
├── validate.py          # entry point CLI
├── models.py            # KBLIValidation + sub-models
├── requirements.txt     # pydantic-ai>=1.0
└── .venv/               # isolated deps
```

## 5. POC #2: CRM Query Agent (Agno)

### Scopo

Input: domanda in linguaggio naturale sul CRM
Output: risposta formattata con dati reali dal database PostgreSQL locale

### Agent Config

```python
from agno.agent import Agent
from agno.tools.postgres import PostgresTools

agent = Agent(
    model=OpenAIChat(
        id="claude-sonnet-4",
        api_key="not-needed",
        base_url="http://localhost:3456/v1"
    ),
    tools=[PostgresTools(
        db_url="postgresql://nuzantara@localhost:5432/nuzantara_dev",
        read_only=True  # CRITICO: solo lettura
    )],
    instructions=[
        "Sei l'archivista CRM di Bali Zero.",
        "Rispondi SOLO con dati dal database. Mai inventare.",
        "Tabelle principali: clients, practices, interactions, invoices.",
        "Formatta i risultati in modo leggibile."
    ]
)
```

### Sicurezza

- `read_only=True` nel PostgresTools
- Utente PostgreSQL con `GRANT SELECT` only (da verificare/creare)

### File

```
~/.openclaw/workspace/skills/crm-query/
├── SKILL.md
├── query.py             # entry point CLI
├── agent_config.py      # Agno Agent + PG tools
├── requirements.txt     # agno, psycopg2-binary
└── .venv/               # isolated deps
```

## 6. POC #3: War Room Crew (CrewAI)

### Scopo

Potenziare la pipeline `~/war_room/` con orchestrazione CrewAI intelligente, senza sostituire gli script esistenti.

### Principio: CrewAI come brain, war_room scripts come muscle

CrewAI wrappa gli script war_room esistenti come "tools" dei Crew agents. Non tocca nessun file in `~/war_room/`.

### Crew (4 agenti)

| Agente                | Ruolo                                             | Tool                                                             |
| --------------------- | ------------------------------------------------- | ---------------------------------------------------------------- |
| **Intel Gatherer**    | Lancia scraping e preprocessa dati                | `run_grok_scraper`, `run_intel_scraper`, `run_qwen_preprocessor` |
| **Strategist**        | Genera 3 concept asimmetrici                      | `run_gemini_strategist`                                          |
| **Creative Director** | Sceglie best concept, valida, produce JSON slides | `run_claude_director`                                            |
| **Producer**          | Genera immagini e assembla Keynote                | `run_gemini_images`, `run_keynote_builder`, `run_delivery`       |

### Tool Pattern (wrapping script esistenti)

```python
from crewai.tools import tool
import subprocess
from pathlib import Path

WAR_ROOM = Path.home() / "war_room"

@tool
def run_grok_scraper(topic: str) -> str:
    """Esegue 01_grok_scraper.py e ritorna il dump JSON."""
    output_path = "/tmp/crew_grok_dump.json"
    result = subprocess.run([
        str(WAR_ROOM / ".venv/bin/python3"),
        str(WAR_ROOM / "agents/01_grok_scraper.py"),
        "--topic", topic,
        "--output", output_path
    ], capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return Path(output_path).read_text()
```

### Vantaggi rispetto a pipeline.sh

1. **Decisioni AI** — se Grok fallisce, CrewAI decide come procedere (non `if/else` bash)
2. **Retry intelligente** — re-prova con prompt diverso, non solo `|| true`
3. **Handoff tipizzato** — output validato tra agenti
4. **Logging strutturato** — CrewAI traccia ogni decisione

### File

```
~/.openclaw/workspace/skills/war-room-crew/
├── SKILL.md
├── crew.py              # Crew definition + Process
├── agents.py            # 4 agents (gatherer, strategist, director, producer)
├── tasks.py             # Task chain definition
├── tools.py             # Wrapper degli script war_room esistenti
├── requirements.txt     # crewai>=1.9
└── .venv/               # isolated deps
```

## 7. Relazione tra Componenti

```
bali-intel-scraper            war_room/
(data gathering)              (content production)
                    │
unified_scraper.py            01_grok_scraper.py
run_intel_pipeline.py         02_manus_launcher.py
claude_cli_enricher.py        015_qwen_preprocessor.py
         │                    03_gemini_strategist.py
         └── intel_output     04_claude_director.py
              _latest.json    05_gemini_images.py
                    │         06_keynote_builder.py
                    └────────▶07_delivery.sh
                   (war_room legge intel se < 8h)

                        ▲
                        │ CrewAI wrappa come tools
                        │
              war-room-crew/ (POC #3)
```

## 8. Dipendenze e Isolamento

Ogni skill ha il proprio venv per evitare conflitti:

| Skill          | Dipendenze principali | Peso stimato |
| -------------- | --------------------- | ------------ |
| kbli-validator | pydantic-ai, httpx    | ~50MB        |
| crm-query      | agno, psycopg2-binary | ~100MB       |
| war-room-crew  | crewai                | ~200MB       |

## 9. LLM Routing

Tutti usano Claude MAX Proxy (`localhost:3456/v1`):

| Agent                   | Modello suggerito | Perche                                 |
| ----------------------- | ----------------- | -------------------------------------- |
| KBLI Validator          | `claude-sonnet-4` | Buon bilanciamento precisione/velocita |
| CRM Query               | `claude-sonnet-4` | SQL generation affidabile              |
| CrewAI agents           | `claude-sonnet-4` | Multi-agent, serve velocita            |
| Task critico (fallback) | `claude-opus-4`   | Quando serve ragionamento profondo     |

Fallback: se Claude Desktop e chiuso → Gemini CLI via OAuth ($0 Ultra).

## 10. SKILL.md Pattern

Ogni skill segue il pattern OpenClaw standard:

```yaml
---
name: kbli-validator
description: |
  Validate KBLI codes from natural language business descriptions.
  Returns type-safe JSON with risk level, PMA eligibility, and Coretax flags.
  Uses PydanticAI for guaranteed output schema compliance.
compatibility: Requires Claude Desktop running (localhost:3456 proxy)
metadata:
  author: balizero
  version: "1.0"
---
```

## 11. Ordine di Implementazione

1. **POC #1: KBLI Validator** — piu semplice, valore immediato, nessuna dipendenza esterna
2. **POC #2: CRM Query** — richiede test con DB PostgreSQL reale
3. **POC #3: War Room Crew** — il piu complesso, dipende da war_room funzionante

Ogni POC e indipendente e puo essere testato isolatamente.

---

**Approvato:** 2026-03-04
