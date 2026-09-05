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

| Model                                                                                      | Role / strengths                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Effort notes                                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claude-fable-5`                                                                           | **Consul seat (RULED 2026-09-06, AGENTS.md §17.1a): Zero opens Fable 5.1 by hand as one of the two consuls, with full powers incl. ship; the other consul (GPT Astra) reviews its work. Still no automated role (RULED 2026-08-20 — Fable out of every auto-routed workflow).** Existing, valid alias — Zero may still open a session on it manually (`/model claude-fable-5`); no doctrine, skill, cron, or script auto-routes to it. Was: final on-disk gate for the Gear-3/large-feature class + WR2 content gate + Phase-2 council judge (see `claude-opus-5` row below for where those roles live now). | n/a — manual only                                                                                                                                                                                         |
| `claude-opus-5`                                                                            | Interactive conductor default (ratified 2026-07-25) **+ final on-disk gate for ALL gears, WR2 content gate, and Phase-2 council judge (RULED 2026-08-20, superseding the 2026-08-19 Gear-3/Gear-1-2 split — those roles no longer route to Fable at all)**. Architecture, red-team, long-horizon agentic work. Gate roles: xhigh effort, never cascades to a weaker model, window dead → task SUSPENDS. **Thinks by default** — omitting `thinking` now thinks; `max_tokens` caps thinking+answer. Separate rate-limit bucket from the 4.x pool.                                                             | `low`/`medium` punch above their weight — primary cost/latency lever. `xhigh` = coding/agentic sweet spot; gate roles run `max`. `thinking:{disabled}` only accepted at effort ≤ `high` (400 above that). |
| `claude-opus-4-8`                                                                          | Valid pin, non-gate seat — drop-in predecessor of Opus 5 at the same price ($5/$25 MTok). Not deprecated.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | same 5-level scale                                                                                                                                                                                        |
| `claude-sonnet-5`                                                                          | **Implementer workhorse** — structured I/O, BUILD-stage default in modus §Arsenal ("Opus 5 designs, Sonnet builds, Opus 5 verifies"). New tokenizer: **~+30% tokens** for the same text vs 4.6 — re-measure `max_tokens`/compaction triggers with `count_tokens`, never a blanket multiplier.                                                                                                                                                                                                                                                                                                                | `xhigh` sweet spot                                                                                                                                                                                        |
| `claude-sonnet-4-6`                                                                        | Valid pin — legacy HOME wrappers (`~/scripts/`) not yet migrated, and the nb-agents slug micro-prompt exception (probe wobble on 5).                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | —                                                                                                                                                                                                         |
| `claude-haiku-4-5` (`claude-haiku-4-5-20251001` — only family member with a real dated ID) | Grunt lane inside workflows (format/extract/classify) + cheap VLM pre-pass. Grunt door (2026-08-27): 7 pinned `.claude/agents/` defs route here with no explicit `model` kwarg needed — `ledger-writer`, `lint-fixer`, `i18n-sync`, `fixture-gen`, `log-triage`, `catalog-meta`, `docs-sync`.                                                                                                                                                                                                                                                                                                                | default                                                                                                                                                                                                   |

Whole-family-5 gotchas (CLAUDE.md §5, non-obvious): min cacheable prompt drops to 512 tokens on
Opus 5 (1024 on 4.8); `temperature`/`top_p`/`top_k`/`budget_tokens` removed (400 if sent), no
last-assistant-turn prefill; a declined request returns HTTP 200 + `stop_reason:"refusal"` — check
`stop_reason` before touching `content`.

---

## OpenAI — door: `codex exec --sandbox read-only|workspace-write` (never `--dangerously-bypass`)

**Consul seat (RULED 2026-09-06, AGENTS.md §17.1a):** GPT Astra (ChatGPT desktop / Codex, the model the
account binds) is the second consul, equal to Fable 5.1 — merge (= arm the mechanical ship path), deploy,
every authorization — with Fable reviewing its work before ship. This is the one exception to "no
external seat ever merges"; every other OpenAI seat below keeps the old fence.

Two ChatGPT Pro accounts: O1 `~/.codex` (refuter primary), O2 (builders + Sol backup) —
`FLEET_TOPOLOGY.json`. **O2's `CODEX_HOME` dirname has per-machine drift, measured 2026-08-14**:
`~/.codex-o2` on M5, `~/.codex-acct2` on Pro (neither name exists on the other machine) — the
Codex Spark lane's default targets Pro's name since that's where it runs. Probe the actual dir
on whichever machine you're on before assuming either name.

| Model                 | Role / strengths                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Effort notes                                              |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Account default model | Explicit BARE slugs (`-m sol`/`-m terra`/`-m luna`) went **DEAD 2026-07-21** ("not supported when using Codex with a ChatGPT account") after an account rotation. **The versioned door is live** (verified 2026-08-27, see the three rows below): `-m gpt-5.6-sol`/`-m gpt-5.6-terra`/`-m gpt-5.6-luna`, reached via `seat_build.sh --seat codex --tier sol/terra/luna` (PR #5044). Absent an explicit `-m`, the account's default model still carries the seat.                                                                                                                                                                                                                               | —                                                         |
| `sol`                 | Red-team + empirical sandbox: migrations (upgrade+downgrade), high-stakes diffs, council red-team seat. **LIVE** via `-m gpt-5.6-sol` (2026-08-27) — the bare `-m sol` slug from the account-rotation note above is still dead; this is a different, versioned slug. Door: `seat_build.sh --seat codex --tier sol` (PR #5044) → `-m gpt-5.6-sol`. Proof: PR #5044's own refuter round ran `codex exec -m gpt-5.6-sol -c model_reasoning_effort="high"` successfully (~16:30Z, teammate-reported) plus an independent live 1-token probe in this PR (`codex exec --sandbox read-only --skip-git-repo-check -m gpt-5.6-sol "reply pong" < /dev/null` → exit 0, 1581 stdout chars, reply `pong`). | xhigh/max; `ultra` = max reasoning + auto task delegation |
| `terra`               | Standard second-opinion / sandbox builder. **LIVE** via `-m gpt-5.6-terra` (2026-08-27, live 1-token probe in this PR: `codex exec --sandbox read-only --skip-git-repo-check -m gpt-5.6-terra "reply pong" < /dev/null` → exit 0, 1595 stdout chars, reply `pong`). Door: `seat_build.sh --seat codex --tier terra` (PR #5044) → `-m gpt-5.6-terra`.                                                                                                                                                                                                                                                                                                                                           | medium (own default)                                      |
| `luna`                | Mechanical/grunt lanes. **LIVE** via `-m gpt-5.6-luna` (2026-08-27, live 1-token probe in this PR: `codex exec --sandbox read-only --skip-git-repo-check -m gpt-5.6-luna "reply pong" < /dev/null` → exit 0, 1582 stdout chars, reply `pong`). Door: `seat_build.sh --seat codex --tier luna` (PR #5044) → `-m gpt-5.6-luna`.                                                                                                                                                                                                                                                                                                                                                                  | low/medium                                                |
| `$imagegen`           | gpt-image-2, image generation via Codex.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | —                                                         |

**SSOT since 2026-08-15** — PR #4179 ("spark standing lane — H24 read-only analysis on the idle
`gpt-5.3-codex-spark` bucket") **MERGED 2026-08-15**; first-tick defects cured in #4217. The lane is
LIVE on Pro (`com.nuzantara.army-spark`, 2h tick; queue `infra/army/spark-queue/`, reports
`~/army/spark/reports/`). H24 mandate (Zero 2026-08-15, reconfirmed 2026-08-19): the lane must
never starve — feeding the queue is part of every conductor session's CLEAN stage.

---

## Google — door: `agy` CLI (AI Ultra), NotebookLM MCP

| Seat                                                     | Role / strengths                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemini-3.1-pro`                                         | Final architectural synthesis, 1M-ctx corpus ingestion, KBLI/visa/regulatory search — Claude hallucinates regulations, this is the CLAUDE.md federation-trigger reason.                                                                                                                                                                                                                                                                                                                                                            |
| `gemini-3.5-flash`                                       | Default council/constructive-width seat (faster, high reasoning).                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| NotebookLM (`mcp__notebooklm-mcp__*`, profile `default`) | Ground-truth **verifier**, bipolar pattern (1 LLM + 1 NB) — it verifies, it does not synthesize. Check source-date freshness before trusting a numeric verdict (W90).                                                                                                                                                                                                                                                                                                                                                              |
| Gemini Spark (`CANDIDATE→ACTIVATING`)                    | Agentic assistant H24 on Gmail/Workspace surfaces (Gemini 3.5 + Antigravity-class harness). From 2026-07 requires only AI Pro, 160+ countries (EU/UK excluded; Indonesia unconfirmed at spec-time — **confirmed present on Zero's consumer account from Indonesia, 2026-08-14 evening**, live-verified: the Agent tab is there). **Consumer accounts only, never Workspace.** GUI-only, no API — same operator-driven class as Antigravity/Kimi Desktop, not schedulable. Standing mandate being drafted by the conductor session. |

Fence (unchanged, MODEL_TOPOLOGY notes): candidate-only — no KG writes, no merge-identity actions,
no scraping private accounts, no PII.

**SSOT since 2026-08-15** — PR #4180 ("Jules standing lane — queued dispatch + async cloud
implementer") **MERGED 2026-08-15**. The lane is LIVE on Pro (`com.nuzantara.army-jules-dispatch`
09:00 WITA + harvest every 3h; queue `infra/army/jules-queue/`; `jules-api-key` present in the Pro
Keychain since 2026-08-18). Cap `ARMY_JULES_DAILY_CAP=3`; tasks land in that queue only with real
anchors (queue README contract: "Jules generates; the session verifies and grades").

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

## Alibaba Token Plan (TP1) — "Pro Plan", mixed ARMED/PROBATION; doors: DashScope

OpenAI-compatible base URL
`https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`; the key is read by
`load_tp1_settings_key()` from `~/.qwen/settings.json` (0600, field
`env.BAILIAN_TOKEN_PLAN_API_KEY`); optional Anthropic-protocol adapter base
`https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic` uses
`ANTHROPIC_AUTH_TOKEN` only, never `ANTHROPIC_API_KEY`.

**Console-verified 2026-08-14** — see `FLEET_TOPOLOGY.json`'s
`accounts.alibaba.slots.TP1.console_verified_2026_08_14` block and
`research/operations/2026-08-14-probe1-tp1-burn-rate.md` (PROBE-1-residual CLOSED). **14 models**
on this plan, not the 15 in the 2026-08-10 census — that older list wrongly included MiniMax M2.5
and kimi-k2.5/2.6/2.7, which the console and the `/models` endpoint (11 of 14 exposed there, the
3 missing being the `happyhorse-1.1-*` video models) both confirm are **not part of this plan at
all**. Plan: 7-day rolling quota, 56.31% used at the 2026-08-14 21:32 console read (~44%
headroom) — **not** the flat monthly figure earlier drafts assumed. **Auto-renewal: ENABLED by
Zero 2026-08-14 evening** (the console read at 21:32 caught it NOT enabled; Zero flipped it that
same evening — see `FLEET_TOPOLOGY.json`).

**Binding owner rulings:** Zero 2026-08-22, _"deepseek va usato, e' nei modelli con nostro piano
con alibaba"_; Zero 2026-08-23, _"armiamo i modelli alibaba che possiamo usare"_. These rulings
re-open DeepSeek only through the subscription-backed TP1 door; the retired standalone
per-token DeepSeek door remains dead and must never be topped up.

**Live door verification 2026-08-23 13:4x WITA:** `GET /models` on the OpenAI-compatible TP1
door returned the seven exact text slugs below. `deepseek-v4-flash-0731` is load-bearing spelling;
the bare `deepseek-v4-flash` slug is not an alias and returns access denied. The effort column is
an orchestration-routing recommendation, not a claim that this door accepts a provider-side
`reasoning_effort` parameter. All seven seats may implement or refute; none is a final gate and
none is quorum-eligible pending a separate owner promotion.

`TP1-OAI` door: `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions`.

| Model                    | Door                        | Role / strengths                                                                                                                                                                                                    | Effort notes                       | Gate / quorum                                                                                   |
| ------------------------ | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------- |
| `deepseek-v4-pro`        | `TP1-OAI`                   | Hard logic, complex implementation, architecture counter-analysis, and adversarial refutation. Subscription door only; never conflate it with the retired standalone per-token endpoint.                            | high/max task class                | Implementer/refuter only; final: no; quorum: no                                                 |
| `deepseek-v4-flash-0731` | `TP1-OAI`                   | High-throughput reasoner for batch implementation, math/logic second opinions, and fast refuter-chain hops. Exact dated slug required.                                                                              | low/medium; high for bounded tasks | Implementer/refuter only; final: no; quorum: no                                                 |
| `glm-5.2`                | `tp1-glm-5.2` via `TP1-OAI` | Counter-builder and general refuter-ladder hop; useful for independent implementations that challenge an incumbent candidate.                                                                                       | medium/high                        | Implementer/refuter only; final: no; quorum: no                                                 |
| `qwen3.8-max`            | `TP1-OAI`                   | Strategy-panel voice, rigorous instruction following, non-PII mass-document work, and complex pipeline execution. Compliance-exact extraction still requires an independent NotebookLM/Anthropic verification lane. | medium/high                        | Implementer/refuter; final: no; **quorum: YES** — the ONLY TP1 seat that counts, see note below |
| `qwen3.7-max`            | `TP1-OAI`                   | Strong general implementation and refutation reserve for work that needs more depth than the plus/flash lanes.                                                                                                      | medium/high                        | Implementer/refuter only; final: no; quorum: no                                                 |
| `qwen3.7-plus`           | `TP1-OAI`                   | Economical standard implementer, second-line batch reviewer, and constructive second opinion.                                                                                                                       | low/medium                         | Implementer/refuter only; final: no; quorum: no                                                 |
| `qwen3.6-flash`          | `TP1-OAI`                   | Fast grunt lane for classification, extraction, formatting, and bounded implementation iterations.                                                                                                                  | low; medium for bounded review     | Implementer/refuter only; final: no; quorum: no                                                 |

> **Why exactly one TP1 seat says `quorum: YES` (RULED Zero 2026-09-02).** Six of the seven TP1
> models never count toward the Gear-3 council quorum. `qwen3.8-max` does, and it is the only
> one, because it is the only TP1 seat that was **promoted ARMED** — 2026-08-14, on 459 measured
> calls / 74.1M tokens (`FLEET_TOPOLOGY.json`, `research/operations/2026-08-14-probe1-tp1-burn-rate.md`).
> The quorum tuple that enforces this is `COUNCIL_REVIEW_SEATS` in `scripts/evidence_pack_lint.py`
> (R9: a Gear-3 pack needs >=2 DISTINCT seats from it posting `role: review, ok: true`).
>
> This row read `quorum: no` until 2026-09-02 while the lint counted the seat anyway — a doctrine
> file and an enforced gate saying opposite things, which went unnoticed for the ~2.5 weeks the
> gate was still a NOTICE and would have started failing real PRs the day it turned hard. The
> mechanism was not carelessness: `.claude/skills/modus/SKILL.md` had written the eligibility as
> "never counts ... **until promoted ARMED**", the promotion happened, and nothing walked the
> escape clause back to the two files that stated the pre-promotion answer as a fact. **When a
> doc encodes a conditional that some future event flips, the event has to update the doc — or
> write the condition where a machine can evaluate it, not where a reader must remember it.**
> Pinned against silent re-drift by `test_roster_quorum_column_matches_the_lint` in
> `scripts/tests/test_lint_roster_dispatch.py`.

Non-text plan families remain outside `arsenal_probe.py` TP1 coverage in this task:

| Model family                                 | Role / status                                                                         |
| -------------------------------------------- | ------------------------------------------------------------------------------------- |
| Wan 2.7 (`image`, `image-pro`)               | Image generation; listed but not wired into a role chain.                             |
| HappyHorse 1.1 (`i2v`, `t2v`, `r2v`)         | Video generation; console-only, absent from the OpenAI-compatible `/models` response. |
| Qwen-Audio 3.0 (`tts-plus`, `realtime-plus`) | TTS/realtime audio; listed but not wired into a role chain.                           |

**Not on this plan at all** (reclassified from PROBATION to **PHANTOM** 2026-08-14, console- and
API-confirmed): MiniMax M2.5, kimi-k2.5/2.6/2.7. PROBE-4 (the planned MiniMax sample-lot
verification) is moot — there is nothing on this account to probe. Using either requires adding
it to this plan or sourcing a different account, a Zero decision, not a probe.

### Coding-plan models measured 2026-08-21 (qwen-seat-fleet arming, empirical CLI probe)

**⚠️ Contradicts the 2026-08-14 PHANTOM line above — flagged, NOT auto-resolved here.** This
session's task was arming the seat + wrapper fleet-wide, not re-auditing TP1 billing; the
discrepancy below needs a console-side check (which underlying balance a call draws from) before
either classification is trusted blindly. Two independent measurements, both empirical, disagree
with each other AND with the 2026-08-14 console read:

1. `GET /v1/models` on both DashScope base URLs (`coding-intl` and `coding`, identical response)
   returned exactly 10 ids: `qwen3-coder-plus`, `qwen3-max-2026-01-23`, `qwen3-coder-next`,
   `glm-4.7`, `kimi-k2.5`, `qwen3.5-plus`, `glm-5`, `MiniMax-M2.5`, `qwen3.6-plus`,
   `qwen3.7-plus`.
2. Live `qwen -p "..." --model <id>` calls (the thing that actually matters) show **4 of those
   10 listed ids return `403 Access to model denied`** (`kimi-k2.5`, `glm-5`, `MiniMax-M2.5`,
   `qwen3.6-plus`) — the listing endpoint is not a reliable access oracle (own W-class: judge the
   reply, never a name/listing proxy) — while **16 ids NOT in that listing return PONG**,
   including `kimi-k2`, `kimi-k2.7`, `kimi-k3`, `MiniMax-M2.7`, `MiniMax-M3` — i.e. the specific
   _dated_ kimi/MiniMax snapshots the 2026-08-14 census marked PHANTOM fail, but _other_ numbered
   snapshots of the same model families succeed live, under the same `BAILIAN_TOKEN_PLAN_API_KEY`.
   Open question this session did not resolve: do the PASS-ing kimi/MiniMax calls draw from the
   flat TP1 quota, or silently fall through to metered pay-as-you-go billing outside the plan? A
   console spend-ledger check is needed before routing any real traffic to them.

**PASS (26/26 on M5, Pro, AND Mini — probed once per model per machine, `qwen -p "Reply with
exactly: PONG-<id>" --model <id>`, judged by output content, watchdog-guarded)**:
`qwen3-coder-plus` · `qwen3-coder` · `qwen3-coder-flash` · `qwen3-coder-next` ·
`qwen3-max-2026-01-23` · `qwen3-max` · `qwen3.5-plus` · `qwen3.6-flash` · `qwen3.7-plus` ·
`qwen3.7-max` · `qwen3.8-max` · `qwen3.8-max-preview` · `qwen3-vl-plus` · `qwen3-asr-flash` ·
`glm-4` · `glm-4.5` · `glm-4.7` · `glm-5.2` · `kimi-k2` · `kimi-k2.7` · `kimi-k3` ·
`MiniMax-M2.7` · `MiniMax-M3` · `deepseek-v3` · `deepseek-v4` · `deepseek-v4-pro`.

**FAIL (M5 only, `403 Access to model denied` — plan-account-level, so presumed identical on
Pro/Mini; not re-probed there since the denial is a token-scope property, not a machine
property)**: `kimi-k2.5` · `kimi-k2.6` · `glm-5` · `glm-5.1` · `MiniMax-M2.5` · `qwen3.6-plus` ·
`deepseek-v4-flash` (note: distinct from the ARMED `deepseek-v4-flash-0731` above — a bare
`deepseek-v4-flash` alias without the date suffix is denied; the dated one that's in production
use is unaffected by this finding).

Remote-probe recipe used (avoids the ssh-eats-the-loop trap, W-class: `ssh` without `-n` inside a
`while read` loop consumes the loop's own stdin — first attempt silently ran only 1 of 26 models
per machine before this was caught and fixed):

```bash
ssh -n -o BatchMode=yes -o ConnectTimeout=15 <pro|mini> \
  "export PATH=/opt/homebrew/bin:\$PATH; perl -e 'alarm 150; exec @ARGV' qwen -p '<prompt>' --model '<id>' < /dev/null"
```

**Hard NOs, whole wing** (spec §2.5): client PII (Law 2 — PII intake is SEA-LION/local, never this
wing), client-facing outputs, merge/deploy, final gates, NUZANTARA/infra credentials in the
model-visible env.

---

## Local Ollama — door: `ollama run <model>` (Pro/Mini, $0, PII-safe; SSOT: `MODEL_TOPOLOGY.json`)

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
- **Model is fixed before turn 1 (2026-09-02)** — set interactive `--model` before it begins;
  never `/model` after turn 1: start a new session instead. Fable 5.1 cache reads cost `$0.25/M`,
  so the cost lever is cache **WRITE**: model switches, tool-list changes, and system-prompt changes.
  Fable 5.1 pricing row added to `~/.tokenaudit/pricing.json` on Pro 2026-09-02 (source recorded there).
- Multi-PR campaigns must route **at least one lane through a non-Anthropic builder** — enforced by `scripts/evidence_pack_lint.py` (NOTICE until 2026-08-24, then FAIL — grace shortened from 2026-09-05 by owner ruling 2026-08-23) and the `model_routing_gate.py` routing floor hook.
- **Refuter always a different family from the builder** — generator≠grader, family-exclusion is
  hard (fleet-order-spec §3.2).
- **Final gate, all gears (ruling Zero 2026-08-20, supersedes the 2026-08-19 gear split)** — **Opus 5,
  xhigh effort** is the final reviewer for every gear, the Gear-3 harness verdict gate, and the WR2
  content gate. Fable 5 is out of the workflow (CLAUDE.md §5, AGENTS.md §17.1, FLEET_TOPOLOGY
  `_invariants`) — used only when Zero opens a session on it manually.

This widens the implementer menu; it does not remove Sonnet 5 as the sane default for
well-specified, testable BUILD units.

---

## Throughput doctrine (ruling Zero 2026-08-19 — "costantemente in movimento")

- **Workhorse-first, intensified**: the Alibaba TP1 wing (`qwen3.7-plus`, `qwen3.6-flash`,
  `deepseek-v4-flash-0731`; `qwen3.8-max` for strategy voices and night-discount batches) and the
  Gemini doors (`agy` flash lanes, Gemini Spark) are the DEFAULT implementer/batch/review-iteration
  tier — reach for them BEFORE any Anthropic implementer. Sonnet 5 is for units that genuinely
  need Anthropic behavior (harness-native Agent/Workflow lanes, Anthropic-specific contracts).
  Anthropic seats = orchestration, judgment, final gates (workhorse-first doctrine 2026-08-15,
  binding).
- **H24 standing lanes must WORK, not exist** (famiglia #2): Codex Spark (2h tick), Jules (3/day
  cap), Gemini Spark (operator-driven schedules). A lane ticking on an empty queue is a starved
  lane — feeding `infra/army/spark-queue/` (and anchored Jules tasks) is part of every conductor
  session's CLEAN stage.
- **Consumption dashboard is INFORMATIVE, never a limiter** (Zero verbatim 2026-08-19: "che non
  sia un limite!"): orchestrators read `~/.agent/cost-ledger/seat_usage_snapshot.json` +
  `~/.agent/seat-usage/console_quota_snapshot.json` to ROUTE — pick the least-loaded door — never
  to refuse work. When a seat is hot, the answer is another door, not a stop.
