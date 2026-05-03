# S12 — LLM Layer Solidification

**Session:** air-c2 · **Date:** 2026-04-18 · **Branch:** `solidification/s12-llm`
**Commits:** `314fd32dd` (FIX-1..5) · `13b5b37e9` (R1+R2+R5)

---

## Audit

| File | LOC | Broad except | Bare except | Inline httpx | Structured log |
|------|-----|--------------|-------------|--------------|----------------|
| ollama_client.py | 210 | 3 | 1 | 0 | ❌→✅ |
| claude_oauth_client.py | 226 | 0 | 1 | 0 | ✅ |
| genai_client.py | 617 | 5 | 0 | 0 | ❌→✅ |
| providers/ollama.py | 216 | 3 | 1 | 2 | ❌ |
| retry_handler.py | 109 | 0 | 0 | 0 | ✅ |
| zantara_ai_client.py | 705 | 1 | 0 | 0 | ❌ (future) |
| *others (8 files)* | 808 | 3 | 0 | 0 | — |
| **Total** | **2,781** | **12** | **2** | **2** | |

Critical findings pre-S12:
- `providers/ollama.py`: `self._async_client` used in `_get_async_client()` but never initialized in `__init__` → latent `AttributeError` on first call
- `providers/ollama.py`: dead `async def check()` with inline `httpx.AsyncClient()` (S04 violation)
- `retry_handler.py`: no error classification — 429/503/timeout all treated identically, no jitter
- `genai_client.py` + `ollama_client.py`: zero structured logging → observability blind spot
- `ollama_client.py:is_ollama_available`: bare `except:` silently swallowing errors

---

## Fix applicati

### FIX-1 — `providers/ollama.py`: persistent client + `__init__` init
- Added `self._async_client: httpx.AsyncClient | None = None` in `__init__`
- Removed dead `async def check()` with inline `httpx.AsyncClient` (S04 violation)
- `_init_client()` simplified to one-liner

### FIX-2 — `retry_handler.py`: error classification + jitter
- New `_classify_error(msg) → 'rate_limit' | 'overload' | 'transient' | 'permanent'`
- `_compute_delay()`: exponential backoff + ±25% jitter; rate-limit base=10s, cap=60s vs transient base=2s
- Permanent errors fail immediately (no retry budget consumed)
- Structured log extras: `operation`, `attempt`, `error_class`, `delay_s`, `error`
- `RETRYABLE_ERROR_KEYWORDS` kept as backward-compat alias

### FIX-3 — `genai_client.py`: structured logging
- `generate_content`: INFO log `{provider, model, latency_ms, prompt_tokens, completion_tokens}` on success; ERROR log `{provider, model, latency_ms, error}` on failure
- `generate_content_stream`: INFO log `{provider, model, latency_ms, chunks}` after stream completes; ERROR on failure
- `import time` added

### FIX-4 — `ollama_client.py`: structured logging on all three call paths
- `ollama_generate`, `ollama_chat`, `ollama_chat_kg`: INFO log with native Ollama token fields (`prompt_eval_count`, `eval_count`)
- `import time` added

### FIX-5 — `ollama_client.py`: bare except upgrade
- `is_ollama_available`: `except:` → `except Exception as e: logger.debug(...)`

---

## Fix applicati — R1+R2+R5 (seconda ondata)

### R1 — `zantara_ai_client.py`: stream retry unificato
- Import `_classify_error`, `_compute_delay` da `retry_handler`
- Loop stream sostituisce formula backoff raw con `_compute_delay()` — gain: jitter + classificazione rate-limit/transient/permanent
- Permanent errors → `break` immediato (nessun retry sprecato)
- Structured log extras: `user_id`, `attempt`, `error_class`, `delay_s`

### R2 — `genai_client.py`: timeout su ogni chiamata API
- `DEFAULT_TIMEOUT_MS = 120_000` (2 minuti) come class attribute
- `_get_config()` inietta `http_options=types.HttpOptions(timeout=...)` in `GenerateContentConfig`
- `generate_content` + `generate_content_stream` espongono `timeout_ms` kwarg per override
- Nessuna chiamata può più bloccarsi indefinitamente

### R5 — `backend/llm/metrics_emitter.py`: LLMMetricsEmitter → Redis Stream
- Nuovo modulo `metrics_emitter.py` (56 LOC)
- Stream key: `llm:metrics`, MAXLEN 10K sliding window
- Campi per entry: `provider`, `model`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `status`, `ts`
- Integrato in `genai_client` (generate + stream) e `ollama_client` (3 call path)
- Graceful degradation: Redis down → no-op, zero eccezioni propagate
- Consumer: `XREAD llm:metrics` per future cost/latency dashboard

---

## Test coverage

| Suite | Before | Dopo FIX-1..5 | Dopo R1+R2+R5 |
|-------|--------|---------------|---------------|
| `backend/tests/unit/llm/` | 135 | 155 | **166** |
| S12-specific | 0 | 20 | **31** |
| Failures | 0 | 0 | **0** |
| Skipped | 1 | 1 | 1 |

New test file: `backend/tests/unit/llm/test_s12_solidification.py`

---

## Provider × Scenario behavior matrix

| Provider | 429 Rate Limit | 503 Overload | Timeout | Connect Error |
|----------|---------------|--------------|---------|---------------|
| Ollama | N/A (local) | N/A | returns `None` | returns `None` |
| Gemini (genai_client) | ↑ retry via RetryHandler (10s base) | retry (2s base) | retry (2s base) | raises |
| Claude OAuth | retry via own logic | retry | raises | raises |
| OllamaProvider | raises RuntimeError | raises RuntimeError | raises RuntimeError | raises RuntimeError |

---

## Raccomandazioni future (aperte)

**R3** — `providers/ollama.py`: aggiungere structured logging in `generate`/`generate_stream` (stesso pattern di `ollama_client.py`). Attualmente nessun log strutturato.

**R4** — `claude_oauth_client.py`: bare `except:` a riga 163 → `except Exception as e: logger.debug(...)`.

**R6** — `llm:metrics` consumer: aggiungere router `GET /api/admin/llm/metrics` che legge gli ultimi N record dal Redis Stream per cost tracking real-time in admin dashboard.
