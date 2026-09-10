# Council read of v5 — Gemini 3.1 Pro (costruttivo seat)

Seat: `agy --model gemini-3.1-pro --effort high`, 2026-09-11 ~03:35 WITA, 277 s, packet inline (no file access). Verdict: REWORK, 4 findings + 2 additions; disposition in `README.md` §Adversarial review (G3 rejected). Verbatim output:

VERDICT: REWORK

1. **Severity: BLOCKER (Deadlock on Generation)**
   **Evidence:** `B1-design.md` §4 (B1.4) requires evaluating LLMs (Ollama, Codex) for the support signal, which `B2-engine.md` §4 (B2.1) must implement into the real scorer if chosen. However, `B2-engine.md` §2 explicitly forbids "everything in B1 §2's forbidden list except the two named exceptions above". `B1-design.md` §2's forbidden list includes "any embedding / generation / reranking API call". Because B2 drops B1's exceptions and replaces them with its own, the B2 Dux is strictly forbidden from making generation calls, deadlocking the window if an LLM is chosen.
   **Exact edit:** `B2-engine.md` §2 Owned perimeter, Writable section: append to the exceptions: ", and generation calls ONLY IF required by the support signal chosen in B1.4".

2. **Severity: BLOCKER (Unmeasurable PII Posture)**
   **Evidence:** `B1-design.md` §4 (B1.4) mandates the production design "consumes the REDACTED query... that raw argument [original query]... are never sent to the seat". However, `wa_package_builder.py:576` does not redact the standalone `query` variable. The text acknowledges "the scorer at :597 still receives the original query", meaning `calculate_evidence_score` has no redacted query to consume. A Dux following this literally cannot satisfy the PII constraint.
   **Exact edit:** `B1-design.md` §4 (B1.4): Add: "B2.1 must update `calculate_evidence_score`'s signature to receive the redacted query (e.g., extracted from the redacted history) instead of the original query, so the chosen signal can consume it and satisfy the PII requirement."

3. **Severity: BLOCKER (Inescapable Failure on Delivery Policy)**
   **Evidence:** `B2-engine.md` §4 B2.1(g) mandates that "unsupported substantive advice is an acceptance FAILURE even when labelled 'cautioned'". Yet, the test must cross the "REAL finalizer (wa_finalize, unchanged — D8)". `README.md` D8 explicitly states that `wa_finalize.py:822-845` "deliberately releases substantive, cautioned answers carrying abstain=true". Since unsupported advice receives a low score (abstain=true) and is passed with substantive text, the unchanged finalizer WILL release it as cautioned. This forces a guaranteed acceptance failure and window suspension.
   **Exact edit:** `B2-engine.md` §4 B2.1(g): Change "unsupported substantive advice is an acceptance FAILURE even when labelled 'cautioned'" to "unsupported substantive advice delivered WITHOUT a caution is an acceptance FAILURE".

4. **Severity: BLOCKER (Unmeasurable Criterion)**
   **Evidence:** `B2-engine.md` §4 B2.1(a) asserts that "the four spec pairs land within one band of each other across context languages". There is no definition, identification, or measurement path for "the four spec pairs" anywhere in the packet (unlike the ≥8 counterfactual pairs or the strict xfails).
   **Exact edit:** `B2-engine.md` §4 B2.1(a): Replace "the four spec pairs" with "the counterfactual pairs", or explicitly define "the four spec pairs" in the B1.3 manifest description.

OWN ADDITIONS:

- The packet must explicitly authorize the B2 Dux to refactor the synchronous `calculate_evidence_score` into an `async def` function (and update all its synchronous callers and unit tests with `await` and `pytest.mark.asyncio`) if an asynchronous support signal (like `CodexExecClient.generate`) is chosen. Without this, the Dux will either illegally block the event loop or fail the entire test suite with coroutine type errors.
- `B1-design.md` §4 (B1.5) conditional logic should explicitly handle the `_unanswered_` case to align with B2.2. Change "If item 7 is declined, B1.5 is skipped..." to "If item 7 is declined or unanswered, B1.5 is skipped...".
