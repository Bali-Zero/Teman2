# Brainstorm #2 — OpenLLMetry — DeepSeek R1

**Date:** 2026-04-26 · **Model:** deepseek-reasoner (R1) · **Reasoning tokens:** 1275

---

## Architectural Analysis: Adopting OpenTelemetry LLM Observability for Nuzantara

### A. Architectural Fit – "Magic" vs. Explicit Control

OpenLLMetry's auto-instrumentation is powerful but opaque. For a production system serving 5,000 clients with PII-laden prompts, the "transparent magic" is a double‑edged sword:

- **Upside**: Zero‑code instrumentation for Gemini and OpenAI‑compatible clients (DeepSeek, Ollama) instantly gives span coverage where today only 3 files use `@traceable`. This lifts observability from ~20% coverage to ~80% of all LLM calls with no engineering effort.
- **Downside**: Engineers lose visibility into _what_ is traced and _where_ PII could leak. A hidden import in `__init__.py` suddenly captures every prompt. Without explicit `@traceable` annotations, teams may forget to configure PII scrubbing or miss inadvertent attribute enrichment.

At Nuzantara's maturity level (FastAPI, moderate volume, compliance‑critical), **explicit instrumentation is safer** for the sensitive data flows. However, OpenLLMetry can be configured to require opt‑in: instead of a global `Traceloop.init`, we can wrap only the specific clients with `instrument_openai` / `instrument_google_genai` and add manual spans for Claude. This hybrid preserves developer awareness while reducing boilerplate.

**Verdict**: Adopt OpenLLMetry's client‑specific instrumentors, **not** the blanket `init()`. Keep `@traceable` (or manual OTEL spans) for application‑level orchestration. This gives explicit control without sacrificing automation where it's safe.

### B. The "Instrument What We Don't Own" Problem – Claude Blind Spot

Four LLM clients, only two auto‑instrumentable. Claude's CLI shell‑out is a major gap. Partial auto‑instrumentation (Gemini + OpenAI) creates a **two‑tier observability system**:

- Spans from auto‑instrumented clients will have rich attributes (model, token count, latency, full prompt/response).
- Claude spans (if added manually) may lack the same structured attributes or be omitted entirely.

**Is partial visibility worse than zero auto + full manual?**
No—partial visibility is far better than today's ~20% manual coverage. The key is to **bridge the gap uniformly**:

- Wrap the Claude shell‑out in a custom `@otel.trace` (or `traceloop.workflow`) that manually captures `gen_ai.*` attributes (model name, request/response, latency).
- Use the same semantic conventions that OpenLLMetry emits (e.g., `gen_ai.system=claude`).
- This yields a consistent span model across all four clients. The extra effort is minimal (~2 days) and eliminates the blindness.

Thus, the two‑tier problem is solvable. The bigger risk is **not** doing it—Claude handles internal tooling and PII; skipping its observability is unacceptable.

### C. PII / UU PDP Compliance – A Non‑Negotiable Gate

Indonesian DPA and GDPR require:

- No **default** capture of full prompts with NIK/NPWP/names.
- Right to erasure of old traces.

**OpenLLMetry + Self‑hosted Langfuse** gives us **full control**:

- `TRACELOOP_TRACE_CONTENT=false` is insufficient (loses debugging).
- Instead, implement a custom `SpanProcessor` that uses Presidio (or a regex‑based scrubbing) to redact sensitive fields _before_ they reach the OTLP exporter. This retains sanitised payloads for debugging while meeting compliance.
- Langfuse's self‑hosted database allows us to delete traces on user request (GDPR Art. 17). LangSmith's SaaS may have less control.

**Cost**: ~2 weeks to build and validate the Presidio integration, plus ongoing maintenance. For 15‑30k spans/day, the engineering cost is small relative to compliance risk.

### D. Migration Strategy – Risk Management for 5,000 Clients

Three options:

1. **Cold cutover** – too risky. A single bug in auto‑instrumentation (e.g., IP leak, 10x span volume) would impact production immediately.
2. **Parallel run** – run both LangSmith and Langfuse for 2 weeks. This doubles observability cost temporarily but allows direct comparison. Acceptable.
3. **Layered** – keep LangSmith `@traceable` for orchestration spans (RAG flow, retrieval) while adding OpenLLMetry for raw LLM client spans. This isolates the new instrumentation to a known area, reducing blast radius.

**Recommendation**: **Layered + Parallel in staging**.

- Start by adding OpenLLMetry (with PII scrubbing) **alongside** existing LangSmith in a staging environment. Validate span accuracy, volume, and scrubbing.
- Then roll out to production in a layered fashion: LangSmith remains the primary observability tool for application logic; OpenLLMetry enriches LLM details.
- After 2 weeks of parallel production, drop LangSmith (or keep it as a secondary sink for compliance‑irrelevant data). This gives a safety net and minimises risk.

### E. Long‑Term OTEL Stability – Early Adopter Risk

The OpenTelemetry GenAI semantic conventions are still experimental (as of early 2026). However:

- The core OTEL framework (spans, attributes, exporters) is stable.
- Breaking changes in GenAI attributes (e.g., `gen_ai.response.finish_reason` renaming) would require a one‑time migration of dashboards and scripts.
- **Counter‑risk**: LangSmith's proprietary format is also unstable – any LangSmith API change or pricing shift forces a migration. With OTEL, we own the pipeline.

**Mitigation**: Abstract attribute access behind an internal helper library (e.g., `get_model_name(span)`), so spec changes only require a single code change. This is standard practice for any fast‑moving domain.

### F. Counterfactual – Keep LangSmith Forever

- **Cost**: Paid plan, lock‑in. At 15‑30k spans/day, likely >$500/month.
- **Stability**: Proven, zero migration risk, native LangChain support.
- **Compliance**: LangSmith can scrub content (via API settings), but erasure requests need manual tickets. No self‑hosted option.

**Trade‑off**: Accepting a predictable cost and limited control vs. investing in an open, compliant future. Given Nuzantara's Indonesian client data and the growing regulatory burden, **self‑hosted observability is a strategic necessity**, not a nice‑to‑have.

---

## Final Recommendation: **ADOPT-PARTIAL**

**Rationale**: A full cold‑cutover is too risky; a full deferral perpetuates vendor lock and compliance gaps. ADOPT‑PARTIAL means we adopt OpenLLMetry for all LLM client instrumentation, paired with self‑hosted Langfuse, while keeping LangSmith for orchestration spans during a transitional parallel period.

### Concrete Migration Sequence

1. **Phase 0 – PII Scrubbing & Claude Instrumentation**
   - Implement a custom `SpanProcessor` using Presidio to redact Indonesian PII (NIK, NPWP, names) from OTEL attributes.
   - Wrap the Claude shell‑out in a manual OTEL span that emits `gen_ai.*` attributes.
   - Deploy only the scrubbing logic (without enabling OpenLLMetry) to verify no regressions.

2. **Phase 1 – Staging Parallel**
   - Enable OpenLLMetry for Gemini and OpenAI‑compat clients in staging. Run with data scrubbing.
   - Compare span counts, latency, and content with LangSmith's traces for one week.
   - Adjust attribute schema and scrubbing rules.

3. **Phase 2 – Production Layering**
   - Deploy OpenLLMetry to production, **but continue to run LangSmith** as the primary observability tool for application‑level `@traceable` spans.
   - Langfuse receives only raw LLM spans (no orchestration).
   - Monitor for unexpected volume, errors, or PII leaks.

4. **Phase 3 – Cutover (after 2 weeks)**
   - Once confident in OTEL data quality, add `@traceable` for Langfuse (export via OTEL) and remove LangSmith's `@traceable` decorators.
   - Remove LangSmith SDK dependency.
   - Retire LangSmith subscription.

5. **Phase 4 – Long‑term**
   - Build OTEL‑based dashboards in Grafana/Langfuse.
   - Subscribe to OTEL GenAI semantic convention updates and update internal helpers.
   - Implement automated GDPR erasure via Langfuse API.

**Risk mitigation**: Always maintain the ability to fall back to LangSmith by keeping its API key configured but unused. The layered approach ensures zero downtime.

**Verdict**: **ADOPT-PARTIAL** – adopt OpenTelemetry strategically with explicit manual instrumentation for blind spots, proper PII scrubbing, and a phased migration that preserves stability for 5,000 clients.

---

## Key insights to carry forward

1. **Recommendation: ADOPT-PARTIAL** with layered migration strategy
2. **Don't use blanket `Traceloop.init()`** — use client-specific instrumentors (`instrument_openai`, `instrument_google_genai`) for explicit control
3. **PII Scrubbing via custom SpanProcessor + Presidio** is non-negotiable for UU PDP
4. **Phase 0 = Claude manual instrumentation + PII scrubber FIRST**, before turning on OpenLLMetry
5. **Phase 2 = layered (LangSmith for orchestration, OpenLLMetry for LLM client spans)** for 2 weeks before cutover
6. **GDPR erasure** is solved by Langfuse self-hosted (LangSmith SaaS doesn't expose direct DB access)
7. **OTEL gen-ai conventions still experimental** — abstract behind helper library so future spec changes are localised
