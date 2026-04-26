# OSS Injection Brainstorm — 2026-04-26

Frozen artifacts from the brainstorm phase that produced [`docs/oss-injections-2026-04-26.md`](../../oss-injections-2026-04-26.md).

## What's here

| File | What it is |
|------|------------|
| [`_initial_report.md`](./_initial_report.md) | The original 16-candidate landscape scan. Identified Squawk/Atlas, Instructor, OpenLLMetry as top 3. |
| [`00_SYNTHESIS.md`](./00_SYNTHESIS.md) | Cross-LLM synthesis. Convergent ADOPT-PARTIAL on all three. |
| [`01_instructor_gemini.md`](./01_instructor_gemini.md) | Gemini 3.1 Pro on Instructor pattern. |
| [`01_instructor_deepseek.md`](./01_instructor_deepseek.md) | DeepSeek R1 on Instructor pattern. |
| [`02_openllmetry_gemini.md`](./02_openllmetry_gemini.md) | Gemini 3.1 Pro on OpenLLMetry. |
| [`02_openllmetry_deepseek.md`](./02_openllmetry_deepseek.md) | DeepSeek R1 on OpenLLMetry. |
| [`03_atlas_gemini.md`](./03_atlas_gemini.md) | Gemini 3.1 Pro on Atlas (later pivoted to Squawk — see `cicatrix-scars.md`). |
| [`03_atlas_deepseek.md`](./03_atlas_deepseek.md) | DeepSeek R1 on Atlas. |

## What's NOT here

Codex GPT-5.5 brainstorms (×3, one per tool) were not run — ChatGPT Plus quota
was exhausted at the time. The 2/3 LLM coverage was sufficient for ADOPT-PARTIAL
verdict; the third opinion was not load-bearing.

## How to read these

If you want to know **why** we picked a given approach over alternatives:
1. Start with `00_SYNTHESIS.md` (10-min read, decision-focused)
2. Drill into the per-tool Gemini/DeepSeek pair if you want the full reasoning
3. The `_initial_report.md` is the broader landscape — useful when planning future
   sprints (it lists ~13 OSS candidates we did **not** pick yet, with notes)

## Provenance

Each brainstorm was a single-shot LLM call with a structured prompt asking for:
- Architectural fit
- Edge cases and gotchas
- Counterfactual ("what if we don't adopt?")
- Final verdict: ADOPT / ADOPT-PARTIAL / DEFER / REJECT

Both LLMs converged on **ADOPT-PARTIAL** for all three tools. Independent
convergence between two reasoning models on the same verdict is the signal
we used to greenlight implementation.
