---
date: 2026-07-18
domain: operations
client_case: none
sources:
  - 6 parallel reader agents (backend-rag call-sites, channels/guards, intake/OCR, cron fleet, WR2/WR3, training-data census) — file:line evidence re-verified same-turn
  - Codex GPT-5.6-sol xhigh red-team (242k tokens, independent live repo re-grounding)
  - Gemini via agy red-team (independent second attack)
  - Live probes: launchctl, Ollama inventories Pro+Mini, Postgres row counts, log greps
---

# SLM Fine-Tuning Essentiality Audit — where fine-tuned small models are (and are not) essential in Nuzantara

**Mandate** (Zero, 2026-07-18): "penso che stiamo sottovalutando la potenzialità degli SLM fine-tunati... analisi completa di dove e come sarebbero essenziali (non solo importanti). No teatro; red team obbligatorio su ogni posizione."

**Method**: Gear-3 modus. 6 parallel readers mapped every LLM call-site in the organism; Fable synthesized 7 candidate positions (E1-E7); two heterogeneous red-teams (Codex sol xhigh + Gemini agy) attacked independently; Fable re-verified every load-bearing refutation on disk same-turn before adopting it.

## Verdict (one line)

**The intuition is half right: the system underuses small local models — but nowhere today is a *fine-tuned* SLM essential. What is essential is the middle ladder the system has never climbed: constrained decoding, few-shot retrieval, off-the-shelf cross-encoders, semantic caches, statistical calibrators. Fine-tuning is the last rung, and two positions will genuinely reach it — once their data exists.**

Both red-teams, independently, converged on the same structural diagnosis: the draft (and the organism) conflates four distinct needs —
1. need for **local processing** (PII/UU PDP) — proven in several places;
2. need for a **local fallback** (quota fragility) — proven by logs;
3. need for **structured output** (JSON schema) — proven by scars;
4. need for **fine-tuning** — proven **nowhere yet**.

## The positions and how they survived contact

| # | Position | Draft grade | Codex | agy | Final (Fable, after re-verification) |
|---|---|---|---|---|---|
| E1 | CRM-Guardian L1 extraction | ESSENTIAL | DEMOLITA | DEMOLITA | **Compliance gap is real; fine-tune is not the fix (yet)** |
| E2 | Intake doc-classifier + extractor | ESSENTIAL | DEMOLITA | DEMOLITA | **Future fine-tune candidate #1 — blocked on data, not on model** |
| E3 | Ops immune system (DLQ/sentinel/monitors) | ESSENTIAL | DEMOLITA | DEMOLITA | **Local fallback tier essential; fine-tune wrong tool** |
| E4 | Surface router + reranker | ESSENTIAL (rerank swap) | REGGE-CON-MODIFICA | REGGE-CON-MODIFICA | **Already mostly solved; future fine-tune candidate #2** |
| E5 | WR2 fact extract/check + cliché gate | important | DEMOLITA | DEMOLITA | **Already deterministic-first; no case** |
| E6 | WA guard layer → SLM verifier | NOT essential | REGGE-CON-MODIFICA | DEMOLITA | **No-FT confirmed; but the legacy path is ALIVE (verified)** |
| E7 | Translation right-sizing | important | DEMOLITA | DEMOLITA | **Right-size with off-the-shelf MT + MDX parser, not LoRA** |

### E1 — CRM-Guardian L1 (the genuine compliance finding)
Fact (verified): the worker sends **cleartext OCR text of passports/NPWP/akta to Gemini cloud** via agy for the actual identity/compliance extraction (706 eligible clients, 5-min cadence, 900s timeout, ~12h full cycle). This contradicts the "PII processing stays local-sovereign" stance — the 2026-06-20 relaxation covered *transit*, not cloud *reasoning over* cleartext PII.
Red-team demolition of the fine-tune (adopted): the 2026-05-17 identity-hallucination scar was caused by the model **never seeing document content** (Phase 1 metadata-only), not by model capability; 706 Gemini outputs are teacher outputs, not gold labels; distilling them freezes the teacher's residual errors into weights; an adapter trained on client docs is itself a PII artifact (retention/deletion/memorization obligations); L1 is ~6 tasks wearing one schema, not a narrow task.
**Do instead**: move the extraction to a LOCAL off-the-shelf model with constrained decoding (JSON schema enforced at decode time), deterministic parsers first (MRZ/checksums/NPWP/NIB formats — much of this already exists in intake), per-field provenance, null/abstain on missing evidence. Fine-tune only if this baseline fails a real eval on Indonesian docs.

### E2 — Intake classifier/extractor (future fine-tune candidate #1)
Fact-check that killed the draft's core claim (verified `auto_attach.py:23,129`): auto-commit is blocked by a **deliberate governance killswitch** (`INTAKE_AUTO_ATTACH_ENABLED` default OFF) and double-concordance policy — NOT by the generic model's capped confidence. The caps (0.55/0.60) are policy constants, not calibrated probabilities; a fine-tuned model's higher confidence would be *overconfidence with better branding* and would silently bypass human review — the exact failure the caps exist to prevent.
Still true: 21-class closed taxonomy, ~900 lines of hand-regex, SEA-LION-32B registered but never used live (latency budget), PII locks everything local forever. This is the single most fine-tune-shaped surface in the organism.
**Blocked on**: `intake_corrections` (textbook preference-pair schema: ai_value vs human_value, confidence, outcome) has **0 rows in prod**. The collector was built; nothing feeds it.
**Do instead now**: arm the corrections flow so every human review writes a row; add few-shot retrieval of confusion pairs (kitas↔passport) + constrained decoding on the existing local models; revisit LoRA on a 0.5-2B classifier **when corrections reach ~thousands** — with client- and time-disjoint splits and an OOD/unknown class.

### E3 — Ops immune system (essential = local tier, not fine-tune)
Facts (verified from logs): dlq_autopilot logged **94 full Anthropic-token-exhaustion events in ~94 days**; sentinel budget-caps itself to 5 Haiku calls/run out of quota fear; the 14-job SDK fleet (monitors, analysts, orchestrators) has **zero cross-vendor fallback** — one exhausted 5h window blinds the monitoring layer.
Red-team demolition (adopted): 75k log lines are inputs, not (error → approved-fix) pairs; the fix distribution shifts with every code/OS/launchd change — a fine-tune learns to solve *last month's* bugs; the recorded DLQ incidents were caused by empty last_error, dead bridge and retry logic, not by weak semantics; and putting the monitor's brain on the same host it monitors adds a shared failure domain.
**Do instead**: (1) signature registry + semantic error cache (embed the log, ≥0.95 similarity → replay the dev-approved fix, <5ms, zero LLM); (2) off-the-shelf local Qwen with constrained JSON for genuinely novel errors, execution only through registered deterministic handlers; (3) cloud escalation only on low local confidence. This removes the Anthropic dependency without freezing the past into weights.

### E4 — Retrieval path (already half-solved; future fine-tune candidate #2)
Correction to the draft (verified `config.py:307`): the canonical reranker default is **already a local cross-encoder** (MiniLM-L-6-v2); Ze-Rank external API is opt-in via `RERANKER_BACKEND=zerank2`. The "PII egress on every live request" claim was wrong. The surface_router is default-OFF (shadow), deterministic-first, Haiku second.
**Do instead**: force/lock the local backend, add a non-egress test, benchmark BGE-reranker vs current MiniLM on nDCG@10/MRR/p95. A domain fine-tuned reranker becomes the second legitimate future candidate **once relevance judgments + hard negatives exist** (none today).

### E5/E6/E7 — demolished, with one liveness correction
- WR2 fact-checker is deterministic-first with `WR2_FACT_CHECKER_LLM` **default false** (verified line 756); cliché library is a closed-set lint → Aho-Corasick, not a model. Fact-checking must not live in parametric memory at all (freshness).
- WA guard layer: no-SLM conclusion stands, but Codex's live probe (confirmed by my own: LaunchAgent `com.nuzantara.openclaw-whatsapp-bridge` state=running, POST /reply 200s current) shows the legacy path is **alive** — the earlier "probably dead" framing is retracted. Open question for a separate pass: which surface consumes it (eval loop vs real traffic). The right evolution is declarative guard rules with guilt+innocence fixtures (scar family #3 antidote), plus isotonic/Platt calibration of the RAG evidence score — classical ML, kilobytes, not an SLM.
- Translation: the worker's real defects are upstream of the model (silent no-output history, >12k-word truncation, 50-char-only validation, no MDX-structure/number/link checks). Fix the harness; try NLLB/MADLAD-class local MT or quantized Qwen with glossary locking before any LoRA.

## §Meta-pattern (the malattia-delle-malattie)

The draft proposed: "the system hand-compiles knowledge (900 regex lines, substring guards, cliché lists) that a fine-tune would learn." **Both red-teams demolished this as a category error, and the demolition survives verification**: a regex is deterministic, auditable, diffable, testable with guilt/innocence fixtures, rollbackable in minutes, PII-free, and its drift is *visible*. Scar family #3 does not prove "rules are wrong"; it proves *bare substring without boundary/intent/innocence-tests* is a bad rule.

The real second-order disease, refined: **the organism knows only the two extremes of the model ladder — hand-written rules at the bottom, frontier cloud models at the top — and treats "local model" as synonymous with "generic zero-shot prompt".** The entire middle of the ladder is unexplored: constrained decoding (zero uses), few-shot retrieval from own corrections (zero uses), off-the-shelf task-specific small models (one use: MiniLM reranker), statistical calibrators (zero), semantic caches (zero), and fine-tuning (zero — MLX + mlx_lm installed, LoRA never invoked once).

Corollary disease, second occurrence pattern: **collectors without consumers** — `intake_corrections` (0 rows), review_queue (0 rows), designer-override diffs (no store). The organism builds the organ that would make fine-tuning possible and then never switches it on, so "the data doesn't exist yet" stays true forever by construction.

## The conditional roadmap (what makes a fine-tune become essential)

1. **Now (no training)**: arm the correction collectors (intake_corrections write path); local off-the-shelf + constrained decoding for CRM-Guardian L1 (closes the PII-cloud gap); semantic error cache + local tier for DLQ/sentinel/monitors (closes the quota blindness); lock reranker to local + non-egress test.
2. **Trigger for fine-tune #1 (intake classifier)**: intake_corrections ≥ low thousands of human-verified rows → LoRA bake-off on 0.5-2B vs the few-shot baseline, client/time-disjoint splits, OOD class, calibration metrics. Only ship if it beats baseline on quality AND calibration AND TCO.
3. **Trigger for fine-tune #2 (domain reranker)**: relevance judgments + hard negatives collected from real query logs → fine-tuned cross-encoder vs BGE off-the-shelf on nDCG@10.
4. **Standing precondition for any fine-tune**: the shared eval harness (the existing golden-set + runner pattern in apps/evaluator, expanded to per-class/confusion/OOD/calibration) — without it, per Codex: "fare fine-tuning significa volare alla cieca". A PII-derived adapter must be treated as a PII artifact (access, retention, deletion).

## Incidental findings (outside the SLM question, worth their own lanes)

- **P1 compliance**: CRM-Guardian L1 cloud-reasoning over cleartext passport/NPWP/akta OCR (E1 above) — the only place in the organism where this happens; every other PII surface (intake, vision, portal recap) is exemplary local-first.
- **Policy gap**: `kg_langgraph_orchestrator.py` falls back to paid `gpt-4o-mini` (OpenAI) when the claude CLI is unavailable — violates the free-first/authorization rule; should fall back to Ollama.
- **MODEL_TOPOLOGY.json drift**: role `translation: gemma3:27b` is stale (live worker hardcodes SEA-LION-32B); `intake_extraction: SEA-LION-32B` never used live (plist overrides to qwen3.5:9b); glm-ocr and qwen3-vl:8b are pulled on disk but referenced nowhere.
- **Cascade health-check theater**: claude-cascade.sh checks binary existence, not live auth/quota (family #2 Esiste≠Armato); yield-optimizer lost 4 of 9 runs to full-cascade death because the Ollama tier refuses `--agent` mode.
- **Legacy WA bridge liveness**: alive and serving; its relationship to the live Meta number needs one decisive trace before any investment/decommission decision.

## §Solo-operatore

- Decision (Legge 5): whether to adopt the conditional roadmap above — in particular arming `intake_corrections` (touches the human review workflow of the team).
- Leave-dirty declared: `research/regulatory/2026-06-30-delta.json` in the MAIN checkout carries a one-line `run_at` timestamp overwrite — collateral from a runaway agy session resumption during this audit (agy re-executed a stale regulatory-watcher scratch script instead of answering the prompt; second lesson: invoke agy with the prompt as argv, never via stdin pipe when a prior session context exists). Revert: `git checkout -- research/regulatory/2026-06-30-delta.json` (blocked for agent sessions by the worktree hook; one-liner for the operator or an ops-lane session).
