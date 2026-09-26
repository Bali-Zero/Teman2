# Kimi council: generated OpenAPI contract cure

Actual stateless kimi-code/k3 subscription CLI review, supplied generated delta and backend models. No runtime re-review or historical withdrawal is claimed.

• **Verdict: PASS** — minimal, correct cure for the OpenAPI pin failure. Scope limited to the supplied delta per instructions; no re-review of prior runtime/CI findings implied.

**Findings**

1. **Pin failure addressed at root cause.** Prior candidate failed only the pin test: runtime source added `idempotency_key`/`delivery_uncertain` backend-side without regenerating `schema.d.ts`. This delta is exactly the regeneration artifact + pin bump, nothing else. That is the minimal fix, not a workaround.

2. **Semantic alignment — response side.** `delivery_uncertain: bool = False` in a Pydantic v2 response model is serialized on every response, and FastAPI emits response schemas in serialization mode, where defaulted fields appear as _required_ with `default: false`. The generated `delivery_uncertain: boolean;` (no `?`) with `@default false` JSDoc matches that precisely. Placing it before `message`/`success` preserves openapi-typescript's alphabetical ordering. No missing nullable mapping: backend is non-optional `bool`, TS is non-nullable `boolean`. ✓

3. **Semantic alignment — request side.** `idempotency_key: UUID | None = None` → `idempotency_key?: string | null;` is the correct triple mapping: optional (`?`), nullable (`| null`), UUID→`string` (openapi-typescript never brands `format: uuid`; the JSDoc title line is standard). Insertion point between `email_type` and `subject` is alphabetically consistent with the generator. ✓

4. **No guard weakening.** Diff touches only a generated `.d.ts` declaration file and its sha256 pin. Zero runtime logic, zero validation, zero type-assertion loosening (`any`/`as`/non-null assertions absent). Additive optional request field + additive response field = backward-compatible for existing callers.

5. **Completeness sweep.** Both new backend fields appear; no other model fields in the supplied backend excerpt are missing from the delta (`assigned_to`, `attachments`, etc. predate it, correctly untouched). Prettier normalization and `typecheck exit 0` (supplied) confirm no stale mock constructions broke on the now-required response field.

**Caveats (evidence-based, not tool-verified):**

- I cannot independently recompute the sha256 against the regenerated file; I rely on the supplied `contract:visa-oracle` success and focused pin test (1 passed, 8.38s). That is the correct evidence chain for a pin artifact.
- Minor inherent limitation (not a defect): TS `string` for UUID means format enforcement remains backend-side (422 on malformed input). Standard for this pipeline.

No release authority expressed or implied.
