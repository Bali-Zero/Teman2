# Brainstorm #2 — OpenLLMetry — Gemini 3.1 Pro

**Date:** 2026-04-26 · **Model:** gemini-3.1-pro-preview

---

Here is a direct, specific analysis of your OpenLLMetry injection plan, addressing your constraints and questions:

### 1. Is OpenLLMetry the right call? (Alternatives & Trade-offs)
**Yes, but OpenInference (Arize) is the strongest contender.**
- **OpenLLMetry (Traceloop):** Excellent drop-in auto-instrumentation. The ServiceNow acquisition guarantees enterprise backing, but OSS development velocity sometimes shifts. It strictly adheres to OTEL semantic conventions.
- **OpenInference (Arize):** Currently the gold standard for LLM semantic conventions. Highly compatible with OSS tools like Phoenix and Langfuse.
- **Langfuse SDK:** Vendor-locked. If you want portability, stick to OTEL (OpenLLMetry/OpenInference) and point the OTLP exporter to Langfuse.
- **Helicone:** Proxy-based. Bad for UU PDP compliance (sends data through a third party) and complicates local Ollama routing.
**Verdict:** Use OpenLLMetry or OpenInference + self-hosted Langfuse via OTLP. Both keep you vendor-neutral.

### 2. Trace Volume (15k-30k spans/day)
**Not a problem at all.**
- 30k spans/day is roughly ~0.35 spans/second. Any self-hosted backend (Langfuse, SigNoz, Jaeger) backed by Postgres or ClickHouse will handle this in its sleep.
- **Sampling:** At this low volume, keep 100% sampling. Head/tail sampling is unnecessary unless your prompt payloads are massive and you are strictly optimizing database storage costs.

### 3. PII Leakage & UU PDP Compliance
You have two concrete ways to handle this without losing token/latency metrics:
- **The nuke option (Safest):** Set `TRACELOOP_TRACE_CONTENT=false` (or `os.environ["TRACELOOP_TRACE_CONTENT"] = "false"`). This completely disables recording prompts and completions in the span attributes, retaining only metadata, token counts, and latency.
- **The surgical option:** Implement a custom OpenTelemetry `SpanProcessor` that intercepts spans before export and uses a local regex/NER model (like Microsoft Presidio) to mask PII (e.g., replacing names with `[REDACTED]`).

### 4. Coexistence with LangSmith
**They can coexist, but with caveats.**
- LangSmith uses its own SDK (`@traceable`) to track function executions and LangChain chains.
- OpenLLMetry patches the underlying provider clients (`openai`, `google.genai`).
- **Overhead:** Minimal, but you will trace the same logical operation twice (once at the function level via LangSmith, once at the network level via OpenLLMetry).
- **Recommendation:** Keep LangSmith decorators for high-level agent orchestration tracking while OpenLLMetry captures the raw LLM client calls. Fully cutover once Langfuse dashboards prove sufficient.

### 5. Failure Mode (Unreachable Endpoint)
**It fails open (silently drops data) and does NOT block.**
OpenTelemetry (which Traceloop wraps) uses a `BatchSpanProcessor` running on a background daemon thread.
- Spans are queued in memory.
- If the endpoint (Pro/Air or Fly.io Langfuse) is unreachable, the exporter retries with exponential backoff.
- Once the in-memory queue hits its limit (default usually 2048 spans), new spans are **silently dropped**.
- Your LLM calls and API endpoints will never be blocked by telemetry network failures.

### 6. Missing Architectural Concerns
- **Claude CLI Shell-out:** Since this bypasses HTTP clients, you **must** manually instrument it. Wrap the `subprocess.run` call:
  ```python
  from opentelemetry import trace
  tracer = trace.get_tracer("claude-shell")
  with tracer.start_as_current_span("claude_cli_execution") as span:
      # run subprocess
      span.set_attribute("gen_ai.system", "claude-cli")
      # manually parse and set tokens/latency if possible
  ```
- **Fly.io 2GB RAM Limit:** The OTEL `BatchSpanProcessor` queues spans in memory. If the telemetry endpoint goes down, the queue fills up. Ensure `max_queue_size` isn't set so high that it causes an OOM kill on your 2GB containers.
- **Distributed Tracing (W3C Context):** LLM traces are only half the picture. To link your Next.js frontend requests to the FastAPI backend RAG calls, you must ensure W3C `traceparent` headers are passed from `apps/mouth` to `apps/backend-rag`. Otherwise, LLM spans will be orphaned from the user's web request.

---

## Key insights to carry forward

1. **OpenInference (Arize) is a strong alternative** — possibly more compatible with OSS Langfuse
2. **Volume is non-issue** (0.35 spans/s) — keep 100% sampling
3. **PII: `TRACELOOP_TRACE_CONTENT=false`** is the simplest nuke option for UU PDP compliance
4. **Failure mode = silent drop** (background thread, never blocks LLM calls) — but watch `max_queue_size` on Fly.io 2GB
5. **Claude CLI requires MANUAL OTEL instrumentation** (subprocess wrapper)
6. **W3C traceparent propagation** is critical — orphan spans without it
