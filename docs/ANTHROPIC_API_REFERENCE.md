# Anthropic API — Best Practices for Nuzantara

> Extracted from CLAUDE.md §17 on 2026-03-31 to reduce context window load.

## Adaptive Thinking (REQUIRED on Opus 4.6 / Sonnet 4.6)

`budget_tokens` is **deprecated** on 4.6 models. Always use:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    thinking={"type": "adaptive"},
    output_config={"effort": "medium"},  # "max" | "high" | "medium" | "low"
    messages=[...]
)
```

- `effort="medium"` — recommended for RAG/tool workflows
- `effort="high"` — default, for complex queries
- `effort="max"` — only for hardest problems (Opus 4.6 only)
- Interleaved thinking (between tool calls) is **automatic** on Opus 4.6 with adaptive

## Prompt Caching (-90% cost)

For KBLI knowledge base, large system prompts, or unchanging tool definitions:

```python
system=[
    {
        "type": "text",
        "text": KBLI_SYSTEM_PROMPT_OR_KNOWLEDGE,
        "cache_control": {"type": "ephemeral", "ttl": 3600}
    }
]

# Monitor cache usage
print(response.usage.cache_read_input_tokens)
print(response.usage.cache_creation_input_tokens)
```

Sonnet 4.6 pricing: write 5min $3.75/MTok, write 1h $6.00/MTok, **read $0.30/MTok**.
Minimum cacheable: 1,024 tokens.

## Batch API (50% discount)

For test suites, bulk KBLI analysis, evaluations:

```python
batch = client.messages.batches.create(requests=[...])
# Stacking: Batch 50% off + cache reads 90% off = minimal cost
```

## Tool Use Patterns

```python
# Strict schema for production
tools = [{"name": "...", "strict": True, "input_schema": {...}}]

# Fine-grained streaming for large tool output
tools = [{"name": "kbli_search", "eager_input_streaming": True, ...}]

# Tool result caching for large documents
{"type": "tool_result", "content": [{"type": "text", "text": doc, "cache_control": {"type": "ephemeral"}}]}
```

## Models for Nuzantara

| Use                      | Model                       | Why                                          |
| ------------------------ | --------------------------- | -------------------------------------------- |
| RAG, reasoning           | `claude-sonnet-4-6`         | Knowledge cutoff Jan 2026, adaptive thinking |
| Routing / classification | `claude-haiku-4-5-20251001` | $1/$5 MTok, fast                             |
| Critical tasks           | `claude-opus-4-6`           | 128K output, effort=max                      |
| KBLI explanations        | `claude-haiku-4-5-20251001` | Configured in kbli_notebook.py               |
