# Brainstorm #1 — Instructor — Gemini 3.1 Pro

**Date:** 2026-04-26 · **Model:** gemini-3.1-pro-preview

---

Here is a terse, specific analysis of your proposed integration of `instructor`, tailored to your Nuzantara multi-LLM setup and constraints.

### 1. Is `instructor` the right choice in 2026? What about competitors?
**Yes, but with caveats.** `instructor` is battle-tested, but the ecosystem has evolved.
*   **The case for `instructor`**: It standardizes the retry loop and Pydantic validation across different providers. It's excellent for Gemini and DeepSeek (via OpenAI compat).
*   **Competitors**: 
    *   **`pydantic-ai`**: The official framework from the Pydantic team. In 2026, it is highly favored for multi-agent/multi-LLM setups because it treats Pydantic V2 as a first-class citizen, whereas `instructor` is primarily a clever patch over SDKs.
    *   **`outlines`**: Better for open-weights, but requires you to run the model server (vLLM). Since you use Ollama, `outlines` is less relevant (though Ollama recently improved constrained decoding).
    *   **`mirascope`**: Much cleaner Pythonic syntax than `instructor`, but smaller community.
*   **Verdict**: If you only need simple JSON parsing, you might not need a framework at all. Modern Gemini SDK (`google-genai`) and OpenAI endpoints (DeepSeek/Ollama) natively support `response_schema` / Strict Structured Outputs. A thin wrapper doing `Model.model_validate_json(output)` might be enough, avoiding third-party dependency bloat.

### 2. Migration risk: Safest vs. Riskiest hot-spots
*   **Safest (Pilot) — `classification/` and `grading/*`**: Flat, simple schemas (e.g., Enums, Booleans, short string reasoning). If validation fails, gracefully degrading is trivial (e.g., defaulting to "unclassified" or a neutral grade).
*   **Riskiest — `kg_*.py`**: Highly nested, unbounded lists of nodes and edges. LLMs frequently fail to close brackets or hallucinate schema keys on massive outputs. `instructor` will attempt retries, which on massive context windows will absolutely torch your API costs and latency.
*   **Wildcard — `pdf_vision_service.py`**: Vision models (especially `qwen2.5vl:7b` locally) can be erratic with strict JSON constraints. Testing local vision structured output should be done in isolation before touching the main service.

### 3. Performance overhead for high-volume (RAG Grading ~3000/day)
`instructor` handles errors by appending the `ValidationError` to the prompt and re-calling the LLM. 
*   **Overhead**: If your base model has a 10% malformed JSON rate, you are doubling latency and token spend for those requests.
*   **Mitigation**: Set `max_retries=0` or `1` for grading. For grading, it is often cheaper and faster to just discard the malformed grade or fallback to a default heuristic rather than waiting for an LLM to correct itself.
*   **Optimization**: Always put a `reasoning: str` field **first** in your Pydantic schema, before the final `score: int` or `boolean` field. This forces the LLM to "think" before committing to the structured answer, drastically reducing validation failures.

### 4. Edge cases: Custom Claude CLI wrapper
`instructor` relies on patching official client SDKs (e.g., `client = instructor.from_openai(OpenAI())`). **It cannot patch a CLI shell-out.**
*   For your `claude_oauth_client.py`, you will have to manually implement the retry logic. 
*   You will call the CLI, get the stdout string, run `try: MySchema.model_validate_json(stdout)`, and if it throws a `ValidationError`, you must manually format that error, append it to your CLI prompt, and shell out again. 
*   Your proposed thin wrapper (`structured_call`) is exactly the right approach to hide this discrepancy from the rest of the app.

### 5. What you're missing
*   **The `<think>` constraint**: You noted `think: false` for Qwen 3.5. If you force strict JSON generation, local models often perform *worse* because they cannot output scratchpad thoughts before the JSON block. You must design your Pydantic schemas to include internal monologue fields (e.g., `chain_of_thought: str`) to compensate.
*   **Token inflation**: Forcing JSON means the LLM outputs the schema keys every single time. For `kg_*.py` (108k nodes), repeating `"source_node"`, `"target_node"`, `"relationship"` thousands of times consumes significant token bandwidth compared to a dense custom format (like CSV or pipe-delimited) parsed via simple script. 
*   **Native vs. Prompted**: Ensure your wrapper actually uses the underlying API's native structured output features (like `response_mime_type="application/json"` and `response_schema` in Gemini) rather than just appending "Output JSON" to the prompt, which is what older versions of `instructor` fell back to.

---

## Key insights to carry forward

1. **`pydantic-ai` is a strong alternative** — possibly better than instructor for our multi-LLM setup
2. **Native SDKs (Gemini + OpenAI compat) might suffice** — avoid bloat
3. **Pilot on `classification/` first** (safest), avoid `kg_*` (riskiest)
4. **Put `reasoning: str` FIRST in Pydantic schemas** — drastically reduces validation failures
5. **Token inflation on large outputs** — JSON schema keys repeat unnecessarily for KG extraction
6. **Local models + JSON forcing = degradation** — must include `chain_of_thought` field
