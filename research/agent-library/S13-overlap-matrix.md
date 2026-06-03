# S13 — Agent Overlap Matrix (2026-06-02)

> Companion to `S13-evolution-FROZEN.json`. Human-readable map of the 6 capability
> overlap clusters across the 34 custom agents (13 interactive + 8 WR2 + 13 WR3).
> Verdicts: `intentional` (by-design separation), `consolidate-pattern` (twins —
> extract shared shape), `redundant` (duplicated logic, gap-fill candidate).
> **All verdicts survived a cross-vendor adversarial pass (DeepSeek V4 Pro + Codex
> GPT-5.5).** The adversaries' load-bearing correction is recorded at the bottom.

## Method note (Law-4 cascade honored)

Intended ingestion engine `agy` (Gemini 3.1 Pro, 1M ctx) was **OAuth-unauthenticated
in headless context** on M5 + Pro + Mini (interactive Google login required, timed
out). Per Symbiosis Law 4 (graceful degradation), ingestion fell to Claude-native
full-context (corpus ~643KB fits comfortably). The adversarial pass DID run on the
designated engines: DeepSeek V4 Pro (API key, no OAuth) + Codex GPT-5.5 (OAuth alive
on Pro). This is documented degradation, **not** a skipped step.

## Overlap clusters

| ID    | Cluster                                                 | Agents                                                                                                                                         | Verdict                 | Shared-shape candidate                                                           |
| ----- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------- |
| OVL-1 | Adversarial / quality-review gate                       | devils-advocate, spalla-review, wr2-critic, wr3-critic, wr3-pre-render-gatekeeper                                                              | **intentional**         | review-gate-protocol → **KILLED by adversaries**                                 |
| OVL-2 | NotebookLM ground-truth consumer                        | wr2-brief-interpreter, wr3-brief-interpreter, nb-curator, deep-researcher, regulatory-watcher                                                  | **intentional**         | nb-ground-truth-protocol → **REVISE (split routing-config from call-authority)** |
| OVL-3 | SOTA bench + engagement-metrics (WR2↔WR3 twins)         | wr2-external-bench, wr3-editorial-bench, wr2-ig-metrics-analyst, wr3-yt-metrics-analyst                                                        | **consolidate-pattern** | metrics-analyst-protocol → **REVISE (keep gate+schema, defer correlation)**      |
| OVL-4 | Orchestrator (fan-out + critic-gate + contract-enforce) | wr2-design-architect, wr3-design-architect                                                                                                     | **consolidate-pattern** | orchestrator-contract-protocol → **DOWNGRADE to contract-test**                  |
| OVL-5 | Brief-interpreter (brief.json producer)                 | wr2-brief-interpreter, wr3-brief-interpreter                                                                                                   | **consolidate-pattern** | brief-schema-protocol (folded into OVL-2 revision)                               |
| OVL-6 | Provider-cascade implementers                           | regulatory-watcher, deep-researcher, wr2-external-bench, wr3-editorial-bench, wr3-reflexion-synth, wr3-audio-asset-producer, wr3-clip-renderer | **redundant**           | provider-cascade-protocol → **REVISE (executable runner, not prose)**            |

### OVL-1 — Adversarial / quality-review gate (intentional)

5 agents read a finished artifact and return PASS/FAIL + findings. They are **NOT
redundant**: the anti-self-approval contract (02-patterns#7) requires reviewer ≠
author, and each carries a distinct rubric + lifecycle position (devils-advocate =
adversarial-destroy; spalla-review = constructive; wr2/wr3-critic = domain-rubric;
pre-render-gatekeeper = pre-spend cliché/cost/safety). The only true duplication is
the ≤3-iteration cap + verdict-JSON shape — but **both adversaries killed** the idea
of a shared review-gate skill: it would homogenize intentionally-distinct reviewers
and add coupling without improving rubric quality. The cap-3 rule belongs in a
contract-test (S13-P7), not a shared skill.

### OVL-2 — NotebookLM ground-truth consumer (intentional, Contract-2-load-bearing)

5 agents touch NB ground truth, but **WR3 Contract 2** mandates that only
`wr3-brief-interpreter` _calls_ NB within the WR3 pipeline (audit P1-18: zero
violations). What IS duplicated/missing across all 5: the domain→NB routing table
(visa→NB-2, tax→NB-4, property→NB-5) and the freshness-check (02-patterns#6 marks it
**not yet implemented** — a stale NB source returns confidently-wrong ground truth).
Adversarial correction: do **not** ship a single "NB protocol" skill that any agent
loads — that erodes Contract 2. **Split** routing/freshness _metadata_ (a config file

- retrieval-side check) from NB _call-authority_ (only approved interpreters load
  callable NB procedures).

### OVL-3 — SOTA bench + engagement-metrics (WR2↔WR3 twins)

`wr2-external-bench`/`wr3-editorial-bench` and `wr2-ig-metrics-analyst`/
`wr3-yt-metrics-analyst` are near-identical twins differing only by surface (IG
carousel vs video reel). Both metrics-analysts are **starved**: 1/10 IG published,
0/3 YT manifests-with-metrics → 5 consecutive "insufficient-data" stubs, **zero real
amendments produced**. Adversarial correction: the starvation is **upstream** (publish
volume), not analyst logic — keep the visible no-data gate + shared output schema, but
**defer** building a correlation protocol until enough observations exist to validate
it.

### OVL-4 — Orchestrator (consolidate → contract-test)

`wr2-design-architect` and `wr3-design-architect` copy-paste the 3-contracts
enforcement (fan-out, NB-ground-truth, no-silent-asset-reuse) + Voyager-graduation
prose. DeepSeek: extract a shared skill (KEEP). Codex: **KILL** — that prose is
load-bearing pipeline contract; a shared skill blurs WR2/WR3 differences and creates
false universality; enforce drift with **contract tests**, not a skill. Split verdict
→ resolved toward Codex's framing: fold into the S13-P7 contract-test harness.

### OVL-6 — Provider-cascade implementers (redundant → executable runner)

7 agents re-implement the multi-LLM / asset-fallback cascade independently, and **all
miss** the breaker-state + degraded-mode marking (02-patterns#4 is explicitly
PARTIAL). S13 itself hit this twice: `agy` OAuth-blocked headless (silent until
ingestion), and `DEEPSEEK_API_KEY` env-drift FATAL-ed the auto-evolver on 2026-05-31.
Both adversaries: the gap is real but a **prose skill won't enforce it** — it needs an
**executable shared runner/library** (breaker state file, cooldown, per-tier
health-ping, degraded-mode flag), with thin skill docs on top. DeepSeek goes further:
a centralized provider router/proxy may be the correct fix, making per-agent cascade
logic disappear entirely.

---

## Adversarial load-bearing correction (both red-teamers, independent)

> **"Most proposals treat duplication-of-WORDS as duplication-of-BEHAVIOR. The real
> failure mode is non-enforcement: a skill loaded as guidance does not guarantee
> breaker state, NB authority boundaries, orchestrator contracts, or loop closure —
> only executable checks and receipts do."**

Both independently surfaced the **same missed gap**: there is no contract-test/audit
harness for the agent library. Nothing verifies frontmatter skills load, WR3
NB-exclusivity holds, reviewer ≠ author, the inventory count matches reality (it
drifted **16 → 34 agents undetected for 17 days**), or that providers are healthy
before a cascade. That harness is promoted to **S13-P7** and is, with **S13-P6**
(repair the never-closed evolution loop), the highest-value outcome of this cycle.

See `_proposed/` for the 7 revised skill drafts and `S13-evolution-FROZEN.json` for
the full machine-readable record (loop-health verdicts, per-agent unsynthesized
lessons, per-proposal cross-vendor verdicts).
