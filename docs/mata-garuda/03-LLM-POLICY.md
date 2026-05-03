# Mata Garuda — LLM Policy

> Data: 2026-04-08 | [DECIDED]

## Regola Fondamentale

**Claude e Gemini: SOLO via CLI (abbonamento flat). MAI via API a pagamento.**

## Stack LLM

| LLM | Accesso | Costo | Uso in Mata Garuda |
|-----|---------|-------|---------------------|
| **Ollama locale** | HTTP localhost:11434 | Zero | Bulk: NER, classification, dedup, filtering, scoring |
| **Claude CLI** (`claude -p`) | subprocess stdin/stdout | Flat (abbonamento) | Enrichment articoli, briefing generation, analisi complesse |
| **Gemini CLI** (`gemini -p`) | subprocess stdin/stdout | Flat (abbonamento) | Grounding normativo, cross-check, exploration, fact verification |
| **Codex CLI** (`codex`) | subprocess | Flat (abbonamento) | Code generation, sandbox tasks se necessario |
| **DeepSeek API** | httpx async | Pay-per-use (centesimi) | Reasoning pesante (R1), batch tasks dove Ollama non basta |
| **Ollama modelli** | | | |
| - gemma4:26b | locale | Zero | MoE, classification, JSON extraction |
| - qwen3.5:9b | locale | Zero | NER rapido, filtering |
| - deepseek-r1:32b | locale | Zero | Reasoning locale (finestra 01:00-06:05 su Air) |
| - qwen2.5vl:7b | locale | Zero | Vision/OCR (unico con vision weights) |

## Pattern di invocazione CLI

```python
import subprocess
import json

async def call_claude(prompt: str, system: str = "") -> str:
    """Invoke Claude CLI — flat cost via subscription."""
    cmd = ["claude", "-p", prompt]
    if system:
        cmd = ["claude", "-p", prompt, "--system", system]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.stdout.strip()

async def call_gemini(prompt: str) -> str:
    """Invoke Gemini CLI — flat cost via subscription."""
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True, timeout=120
    )
    return result.stdout.strip()
```

## LLM Router Logic

```
Task ricevuto
  │
  ├─ Bulk/cheap (NER, classify, dedup, score)
  │   └─ Ollama locale (gemma4 o qwen3.5)
  │
  ├─ Enrichment/briefing (qualita alta, testo lungo)
  │   └─ Claude CLI
  │
  ├─ Grounding/fact-check (verifica normativa)
  │   └─ Gemini CLI
  │
  ├─ Reasoning complesso (analisi multi-step)
  │   └─ DeepSeek API (R1) o deepseek-r1:32b locale se in finestra
  │
  └─ Vision/OCR
      └─ qwen2.5vl:7b locale
```

## Budget Mensile Stimato

| Voce | Costo |
|------|-------|
| Claude CLI (abbonamento) | Gia pagato |
| Gemini CLI (abbonamento) | Gia pagato |
| Codex CLI (abbonamento) | Gia pagato |
| Ollama | Zero (locale) |
| DeepSeek API | ~$5-10/mese stimati |
| Exa API | Gia nel scraper budget |
| Tavily | Free tier (1000/mese) |
| Brave Search | Gia in MCP |
| **Totale aggiuntivo** | **~$5-10/mese** |

## [OPEN] Da approfondire

- CLI throughput: quante chiamate/minuto supporta Claude CLI senza throttling?
- Gemini CLI: supporta stdin pipe per batch?
- Wrapper async: subprocess vs asyncio.create_subprocess per non bloccare event loop
