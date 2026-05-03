# Brainstorm #1 — Instructor — DeepSeek R1

**Date:** 2026-04-26 · **Model:** deepseek-reasoner (R1) · **Reasoning tokens:** 979

---

# Architectural Deep Dive: Instructor for Nuzantara

## A. Architectural Fit – It's Better Than You Think, But Not a Panacea

Nuzantara already lives in Pydantic territory. Every router, every model, every validation path is built on Pydantic's type system. Instructor's core promise—**schema-as-code, validated inside the LLM call**–aligns directly with your existing design culture. The `LLMProviderRegistry` and `provider_registry.py` currently abstract raw API calls; adding a thin `structured.py` wrapper that returns `BaseModel` instances instead of raw strings is a natural extension of that abstraction. The registry can expose a `generate_structured(model, response_model)` method that internally wraps the appropriate client with instructor (or replicates its pattern for Claude).

**Second‑order effects to watch:**

1. **Instructor's patching style** – It mutates the SDK client object at construction time (`instructor.from_gemini(client)`). This breaks the assumption that a client is a transparent HTTP wrapper. Your registry currently treats clients as stateless singletons; injecting instructor means the registry must decide _per call_ whether to patch, or keep a patched copy. Implementing a factory that returns a new patched client for each structured call is safe but introduces object‑creation overhead. Given your call volumes (5000+ clients, but LLM calls per user likely modest), this is acceptable.

2. **Ollama's local models** – Their low latency makes the extra token overhead (~500 tokens for schema injection) a real cost, especially for 80% of grading calls. Instructor offers `mode=INSTRUCTOR_MODE` for local models that uses the schema in the system prompt rather than function calling—same overhead you'd have with manual prompting. The retry/validation logic is still valuable: a local model's occasional JSON failures are caught and re‑prompted automatically, reducing silent errors. The cost of a single retry is 2× tokens—acceptable for mission‑critical grading.

3. **Provider agnosticism** – Instructor supports Gemini, DeepSeek (via OpenAI), and Ollama seamlessly. Your four clients are covered except Claude.

## B. The `claude_oauth_client.py` Problem – A Clean Architectural Trade‑off

You have three options. From a **purity** standpoint, option 2 (manual replication) is the worst: you're duplicating instructor's retry logic, breaking the single source of truth. Option 3 (no instructor at all) throws away the benefits for all providers just to keep Claude structured outputs, which is disproportional.

**Option 1 – Drop Claude for structured outputs** is the architectural right call _if_ Claude's role is non‑critical or easily replaced. The `claude` CLI integration is already an outlier—unsupported, fragile, and slow (subprocess overhead). For structured output tasks, Gemini and DeepSeek are modern, SDK‑based, and cheaper. If Claude is used only for unstructured chat or niche tasks, keep those calls outside instructor. If structured outputs are required on Claude, invest in switching to the Anthropic SDK (even without paid API, you can use the SDK against a local proxy?) or accept that some tasks remain in the old `try/except` world.

**Recommendation:** Treat Claude as a legacy client. Do not bend the architecture to support it. Structured outputs for Gemini/DeepSeek/Ollama gain 95% of the benefit. Claude remains in the old path until a proper SDK integration is possible.

## C. The KG Extraction Edge Case – A Clear Boundary for Partial Adoption

KG extraction is the perfect counterexample for instructor. The nested Pydantic schemas add 500–1000 tokens per call—on a task that often hits token limits with local models. Worse, `ValidationError` retries double the cost on a model (qwen3.5) that already struggles with deep nesting. The current prompt‑engineered approach, while hacky, has worked for 108k nodes. **Do not migrate KG extraction to instructor.** Keep it prompt‑engineered with your existing `try/except + regex` fallback. This is a pragmatic carve‑out: instructor's value is highest for simple, deterministic schemas (classifications, graders, yes/no answers), not deeply nested entity graphs.

## D. Counterfactual: The Cost of Doing Nothing

Over 18+ months, the current pattern accumulates:

- **Silent bug rate**: Every `json.loads` failure that falls through to regex silently degrades output quality. In a production platform with 5000+ clients, these are invisible tickets and angry users.
- **Onboarding friction**: New developers must read a dozen prompt templates to understand expected output shapes. With instructor, the schema _is_ the documentation.
- **Test complexity**: Without schema‑forged responses, tests need precise JSON mocking. With instructor, you pass a `BaseModel` and assert fields directly.
- **Technical debt**: As you add more structured outputs (you will), the `try/except` pattern spreads, making a future migration harder.

The current cost is manageable today but growing linearly with app count. Instructor caps that growth.

## E. Long‑Term: Instructor vs. Pydantic‑AI (2027–2028)

Pydantic‑AI is from the same team, but it's a different beast—an agent framework, not just a structured output patch. It's expressive but opinionated (dependency injection, tool‑based). Instructor is simpler, more stable, and widely adopted. By wrapping instructor behind your own `structured.py` abstract interface, you can later swap to Pydantic‑AI without touching the 141 routers. The abstraction is the key: don't let instructor leak into your business logic. Do that, and you're safe either way.

# Recommendation: **ADOPT-PARTIAL**

Adopt `instructor` with the following boundaries:

1. **Implement** `backend/llm/structured.py` as a thin wrapper that internally uses instructor for Gemini and DeepSeek, and a hand‑rolled retry loop for Ollama (matching instructor's logic) to avoid unnecessary JSON injection overhead when not needed.
2. **Migrate** the five hot‑spots _except_ KG extraction. Start with classification (lowest risk).
3. **Drop** structured outputs on Claude (keep its calls unstructured or move to Gemini/DeepSeek).
4. **Carve out** KG extraction: keep prompt‑engineered, but consider a lightweight Pydantic model for validation _after_ extraction (not inline with instructor).
5. **Abstract** via `structured.py` so that swapping to pydantic‑AI later requires changing only the wrapper, not 21 apps.

This gives you 80% of the benefits with 20% of the risk. The architecture remains clean, the registry unchanged, and Claude's legacy doesn't hold you back.

---

## Key insights to carry forward

1. **Recommendation: ADOPT-PARTIAL** (Gemini ✅, DeepSeek ✅, Ollama ✅, Claude ❌, KG ❌)
2. **The wrapper itself is the architecture decision** — protects against instructor→pydantic-ai future migration
3. **Pilot order: classification → graders → KBLI → OCR akta** (NEVER KG extraction)
4. **Claude OAuth: declared legacy** — don't twist the architecture for it
5. **Cost of doing nothing scales linearly** with new feature additions
6. **Both Gemini and DeepSeek converge on the same conclusion** about instructor's place
