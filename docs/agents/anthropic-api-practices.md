# Anthropic API best practices (Feb 2026, 4.6 era — see the staleness note)

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.
> **Stale by design:** this section is 4.6-era. For 5-family gotchas read `MODEL_ROSTER.md`
> and the CLAUDE.md 5-family notes. Builder Contract §3 governs whether any of these calls
> may be made at all: the paid per-token Anthropic endpoint is banned.

### Adaptive Thinking (OBBLIGATORIO su Opus 4.6 / Sonnet 4.6)

`budget_tokens` è **deprecato** sui modelli 4.6. Usare sempre:

```python
# ✅ CORRETTO — adaptive thinking
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    thinking={"type": "adaptive"},
    output_config={"effort": "medium"},  # "max" | "high" | "medium" | "low"
    messages=[...]
)

# ❌ DEPRECATO — non usare su 4.6
thinking={"type": "enabled", "budget_tokens": 10000}
```

- `effort="medium"` → raccomandato per workflow RAG/tool
- `effort="high"` → default, per query complesse
- `effort="max"` → solo per i problemi più difficili (solo Opus 4.6)
- L'interleaved thinking (tra tool call) è **automatico** su Opus 4.6 con adaptive

### Prompt Caching KBLI / Knowledge Base (-90% costo)

Ogni volta che scrivi chiamate API che includono il knowledge base KBLI, system prompt largo,
o definizioni di tool che non cambiano, usa `cache_control`:

```python
# ✅ System prompt con cache (risparmio 90% su letture successive)
system=[
    {
        "type": "text",
        "text": KBLI_SYSTEM_PROMPT_OR_KNOWLEDGE,
        "cache_control": {"type": "ephemeral", "ttl": 3600}  # 1 ora per batch
    }
]

# Monitoraggio cache
print(response.usage.cache_read_input_tokens)     # token da cache
print(response.usage.cache_creation_input_tokens)  # token scritti in cache
```

Prezzi Sonnet 4.6: scrittura 5min $3.75/MTok, scrittura 1h $6.00/MTok, **lettura $0.30/MTok**.
Minimo cacheable: 1.024 token.

### Batch API per elaborazioni massive (50% sconto)

Per test suite, analisi bulk KBLI, valutazioni:

```python
# Stacking: Batch 50% off + cache reads 90% off = costi minimi
batch = client.messages.batches.create(requests=[...])
```

### Tool Use — pattern corretti

```python
# Strict schema per produzione
tools = [{"name": "...", "strict": True, "input_schema": {...}}]

# Fine-grained streaming per tool con output grande
tools = [{"name": "kbli_search", "eager_input_streaming": True, ...}]

# Tool result caching per documenti grandi
{"type": "tool_result", "content": [{"type": "text", "text": doc, "cache_control": {"type": "ephemeral"}}]}
```

### Modelli consigliati per Nuzantara

| Uso                       | Modello                     | Perché                                       |
| ------------------------- | --------------------------- | -------------------------------------------- |
| RAG complesso, reasoning  | `claude-sonnet-4-6`         | Knowledge cutoff gen 2026, adaptive thinking |
| Routing / classificazione | `claude-haiku-4-5-20251001` | $1/$5 MTok, velocissimo                      |
| Task critici              | `claude-opus-4-6`           | 128K output, effort=max                      |
| Spiegazioni KBLI          | `claude-haiku-4-5-20251001` | Già configurato in kbli_notebook.py          |

---
