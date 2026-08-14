# MODEL_ROSTER.md — every model, its strengths, its doors

> **Zero ruling 2026-08-14 (verbatim):** _"cambia questa vecchia regola e ricorda che hai diversi
> modelli e diversi effort in anthropic e devi stamparti (per ogni orchestratore, ricorda che posso
> aprire sessione con chiunque) in testa la lista di tutti i modelli llm e loro punti di forza."_
>
> Every conductor — Claude, Codex, agy/Antigravity, Kimi, Qwen (AGENTS.md §17.1: "conductor is a
> role, not a model", same law, different door) — reads this file **before choosing a seat**.
> Implementer routing is no longer "always Sonnet": it is a **per-task choice across the full
> roster** below. See §Routing rule at the bottom.

## SSOT boundaries (don't restate, point)

| What                                                | SSOT                                                                                         |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Cloud accounts, role fallback chains, gate taxonomy | `FLEET_TOPOLOGY.json` (repo root) + `research/operations/2026-08-10-fleet-order-spec.md`     |
| Local Ollama model↔machine assignment               | `MODEL_TOPOLOGY.json`                                                                        |
| **This file**                                       | models × strengths × effort levels × invocation door — the catalogue, not the account ledger |
| Doctrine / role-chain prose                         | `.claude/skills/modus/SKILL.md` §THE ARSENAL, `AGENTS.md` §17, `CLAUDE.md` §5                |

Every row below was checked against those files on 2026-08-14 in this run. Where the source
dictation for this doc conflicted with what's on disk, disk won — conflicts are logged in the PR
body, not silently smoothed over.

---

## Anthropic — door: `claude` CLI, OAuth only (SDK / `ANTHROPIC_API_KEY` banned, CLAUDE.md §5)

| Model                                                                                      | Role / strengths                                                                                                                                                                                                                                                                                                                            | Effort notes                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claude-fable-5`                                                                           | **Final on-disk gate, unconditional** (last empirical grep/disk check of every task) + WR2 content gate + Phase-2 council judge. Orchestrator-only, never a builder. Never cascades — window dead → task SUSPENDS. Team-seat inclusion caps at ~50%/week; past that it's paid credits, barred by the Fable-paid contingency (CLAUDE.md §5). | max, always                                                                                                                                                                         |
| `claude-opus-5`                                                                            | Interactive conductor default (ratified 2026-07-25). Architecture, red-team, long-horizon agentic work. **Thinks by default** — omitting `thinking` now thinks; `max_tokens` caps thinking+answer. Separate rate-limit bucket from the 4.x pool.                                                                                            | `low`/`medium` punch above their weight — primary cost/latency lever. `xhigh` = coding/agentic sweet spot. `thinking:{disabled}` only accepted at effort ≤ `high` (400 above that). |
| `claude-opus-4-8`                                                                          | Valid pin, non-Fable-capable seat — drop-in predecessor of Opus 5 at the same price ($5/$25 MTok). Not deprecated.                                                                                                                                                                                                                          | same 5-level scale                                                                                                                                                                  |
| `claude-sonnet-5`                                                                          | **Implementer workhorse** — structured I/O, BUILD-stage default in modus §Arsenal ("Fable designs, Sonnet builds, Fable verifies"). New tokenizer: **~+30% tokens** for the same text vs 4.6 — re-measure `max_tokens`/compaction triggers with `count_tokens`, never a blanket multiplier.                                                 | `xhigh` sweet spot                                                                                                                                                                  |
| `claude-sonnet-4-6`                                                                        | Valid pin — legacy HOME wrappers (`~/scripts/`) not yet migrated, and the nb-agents slug micro-prompt exception (probe wobble on 5).                                                                                                                                                                                                        | —                                                                                                                                                                                   |
| `claude-haiku-4-5` (`claude-haiku-4-5-20251001` — only family member with a real dated ID) | Grunt lane inside workflows (format/extract/classify) + cheap VLM pre-pass.                                                                                                                                                                                                                                                                 | default                                                                                                                                                                             |

Whole-family-5 gotchas (CLAUDE.md §5, non-obvious): min cacheable prompt drops to 512 tokens on
Opus 5 (1024 on 4.8); `temperature`/`top_p`/`top_k`/`budget_tokens` removed (400 if sent), no
last-assistant-turn prefill; a declined request returns HTTP 200 + `stop_reason:"refusal"` — check
`stop_reason` before touching `content`.

---

## OpenAI — door: `codex exec --sandbox read-only|workspace-write` (never `--dangerously-bypass`)

Two ChatGPT Pro accounts: O1 `~/.codex` (refuter primary), O2 `~/.codex-o2` (builders + Sol backup)
— `FLEET_TOPOLOGY.json`.

| Model                 | Role / strengths                                                                                                                                                                                                                                                         | Effort notes                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| Account default model | Explicit slugs (`sol`/`terra`/`luna`) went **DEAD 2026-07-21** ("not supported when using Codex with a ChatGPT account") after an account rotation — the account's default model carries the seat until a live probe proves a slug name again. Never pass `-m` on faith. | —                                                         |
| `sol` (when live)     | Red-team + empirical sandbox: migrations (upgrade+downgrade), high-stakes diffs, council red-team seat.                                                                                                                                                                  | xhigh/max; `ultra` = max reasoning + auto task delegation |
| `terra` (when live)   | Standard second-opinion / sandbox builder.                                                                                                                                                                                                                               | medium (own default)                                      |
| `luna` (when live)    | Mechanical/grunt lanes.                                                                                                                                                                                                                                                  | low/medium                                                |
| `$imagegen`           | gpt-image-2, image generation via Codex.                                                                                                                                                                                                                                 | —                                                         |

**Not yet SSOT** — PR #4179 ("spark standing lane — H24 read-only analysis on the idle
`gpt-5.3-codex-spark` bucket") is **OPEN, not merged** as of 2026-08-14. Treat as proposed until it
lands; don't route work assuming it's armed.

---

## Google — door: `agy` CLI (AI Ultra), NotebookLM MCP

| Seat                                                     | Role / strengths                                                                                                                                                        |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemini-3.1-pro`                                         | Final architectural synthesis, 1M-ctx corpus ingestion, KBLI/visa/regulatory search — Claude hallucinates regulations, this is the CLAUDE.md federation-trigger reason. |
| `gemini-3.5-flash`                                       | Default council/constructive-width seat (faster, high reasoning).                                                                                                       |
| NotebookLM (`mcp__notebooklm-mcp__*`, profile `default`) | Ground-truth **verifier**, bipolar pattern (1 LLM + 1 NB) — it verifies, it does not synthesize. Check source-date freshness before trusting a numeric verdict (W90).   |

Fence (unchanged, MODEL_TOPOLOGY notes): candidate-only — no KG writes, no merge-identity actions,
no scraping private accounts, no PII.

**Not yet SSOT** — PR #4180 ("Jules standing lane — queued dispatch + async cloud implementer") is
**OPEN, not merged** as of 2026-08-14. Same caveat as Codex Spark above.

---

## Moonshot — door: `kimi` CLI (Allegro flat subscription, OAuth device-code, no API key)

| Model                       | Role / strengths                                                                                                                                                                        |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `k3` (`kimi-code/k3`)       | Refuter #2 in the fixed 3-seat council (after Codex Sol), 1M-ctx long-context auditor, **multimodal Evidence-Pack verifier** (screenshots/PDFs/visual artifacts). Never the final gate. |
| `kimi-for-coding`           | Alternative coding frontend / cross-family implementer — never load-bearing on hot-zone alone.                                                                                          |
| `kimi-for-coding-highspeed` | Grunt coding lane.                                                                                                                                                                      |

Zero-trust fence (`kimi.md`): no credentials in the Kimi environment ever, worktree-only, network
scoped to what the task declares.

---

## z.ai — door: `claude-glm` shim (Anthropic-Messages-compatible endpoint, z.ai Coding Plan)

| Model     | Role / strengths                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `glm-5.2` | Counter-builder (parallel implementations that dogfood dissent against a Sonnet candidate) + general refuter-ladder hop. **ARMED** via z.ai Coding Plan (`scripts/claude-glm.sh`); the Alibaba TP1 door is its PROBATION backup — Zero's ruling 2026-08-10: do not renew z.ai when it lapses, let the TP1 door take over once burn-rate is measured. `clear_thinking:false` mandatory in agent use. Never architecture, never client-facing, never merge. |

---

## Alibaba Token Plan (TP1) — PROBATION overall; doors: DashScope OpenAI-compatible **and**

Anthropic-Messages-compatible baseURL (`~/.qwen/settings.json`, 0600, `BAILIAN_TOKEN_PLAN_API_KEY`)

15 models registered 2026-08-10 (verbatim, `research/operations/2026-08-10-fleet-order-spec.md`):
`qwen3.8-max-preview`, `qwen3.7-max`, `qwen3.7-plus`, `qwen3.6-plus`, `qwen3.6-flash`,
`deepseek-v4-pro`, `deepseek-v4-flash`, `deepseek-v3.2`, `kimi-k2.7-code`, `kimi-k2.6`,
`kimi-k2.5`, `glm-5.2`, `glm-5.1`, `glm-5`, `MiniMax-M2.5`.

| Model                             | Role / strengths                                                                                                                                                                                                                                                                                                                              | Status               |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| Qwen 3.8 Max                      | 3rd strategy voice in panels (with Opus 5 + Gemini); rigorous-instruction pipeline executor; non-PII mass doc/video engine; fenced GUI-agent. Documented weakness: hallucinates on compliance-exact extraction — mandatory NotebookLM/Anthropic-seat verification on that class. Never coding hot-zone alone, never PII, never client quotes. | PROBATION            |
| Qwen 3.7 (max/plus)               | Reserve — economical second opinion, second-line batch. Never load-bearing alone.                                                                                                                                                                                                                                                             | PROBATION            |
| Qwen 3.6 (plus/flash)             | Available, not yet role-assigned beyond "cheap classification" candidate.                                                                                                                                                                                                                                                                     | PROBATION            |
| DeepSeek v4-pro / v4-flash / v3.2 | Second reasoner — refuter-chain reserve hop, math/logic second-opinion. `eligible_for_quorum:false` until promoted ARMED. **Re-admitted 2026-08-10**: the 2026-07-19 retirement was the standalone per-token balance dying (HTTP 402), not a quality verdict — PII boundary unchanged and absolute.                                           | PROBATION            |
| GLM 5.2 (TP1 door)                | Same seat as the z.ai row above, second door — backup only while z.ai is alive.                                                                                                                                                                                                                                                               | PROBATION            |
| MiniMax M2.5                      | "The Grinder" — repetitive tests/docs/mechanical batches. Gated on **PROBE-4** (a sample lot verified by an Anthropic seat) before any use — **not usable yet**.                                                                                                                                                                              | PROBATION, gated     |
| kimi-k2.5 / k2.6 / k2.7-code      | **Older than K3, second-line redundancy only** (explicit note, `.claude/skills/modus/SKILL.md` §Arsenal) — present in the TP1 model list, not a phantom line, but the Allegro K3 door above stays load-bearing for Kimi.                                                                                                                      | PROBATION, redundant |
| Wan                               | Media-gen (image/video), WR2 radar candidate.                                                                                                                                                                                                                                                                                                 | listed, not active   |

Batch economics: `qwen.md`/`QWEN.md` note a conditional off-peak window ("Qoder window, if included
in the plan: 14:00–00:00 UTC = 22:00–08:00 WITA → nightly batch lane") — this is the only on-disk
support for a "cheaper at night" claim; treat it as conditional on plan inclusion, not a confirmed
blanket discount, until PROBE-1's burn-rate measurement closes the gap.

**Hard NOs, whole wing** (spec §2.5): client PII (Law 2 — PII intake is SEA-LION/local, never this
wing), client-facing outputs, merge/deploy, final gates, NUZANTARA/infra credentials in the
model-visible env.

---

## Local Ollama — Pro/Mini, $0, PII-safe (SSOT: `MODEL_TOPOLOGY.json`)

Roster is **not auto-replicated cross-machine** — always `ollama list` per machine before assuming
presence. Known-live lanes (CLAUDE.md §9 data invariants + machine facts):

- `qwen3.5:9b` — classifier, **`think:false` required** (Ollama client contract).
- `deepseek-r1:32b` — offline reasoning.
- `qwen2.5vl:7b` — **sole vision/OCR seat** (data invariant: `qwen3.5` Q4_K_M strips vision
  weights — never substitute).
- `gemma4:26b` — translation cron.
- `bge-m3` / `nomic-embed-text` — multilingual / general embedding.

---

## Routing rule (Zero ruling 2026-08-14)

Implementer routing is **task-shaped across the full roster above**, not Sonnet-by-default:

- **Grunt** → `haiku-4-5` / `codex-luna` / `kimi-for-coding-highspeed`.
- **Standard** → `sonnet-5` (still the modus §Arsenal BUILD default) / `codex-terra` /
  `kimi-for-coding`.
- **Hard / architectural / red-team** → `opus-5` at `xhigh` / `codex-sol` at xhigh-max.
- **Effort is a dial, not a constant** — pick per task; `low`/`medium` on Opus 5 are a real
  cost/latency lever, not a quality compromise to avoid by reflex.
- Any multi-PR campaign should route **at least one lane through a non-Anthropic builder**
  (heterogeneity per modus §Arsenal's inversion rationale).
- **Refuter always a different family from the builder** — generator≠grader, family-exclusion is
  hard (fleet-order-spec §3.2).
- **The final on-disk gate remains Fable, unconditional** — this ruling does not touch it, adds no
  classifier or task-shape logic in front of it, and is not a precedent for doing so
  (CLAUDE.md §5, AGENTS.md §17.2). Same invariant for the WR2 content gate.

This widens the implementer menu; it does not remove Sonnet 5 as the sane default for
well-specified, testable BUILD units.
