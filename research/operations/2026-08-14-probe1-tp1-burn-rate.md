---
date: 2026-08-14
domain: operations
client_case: N/A — internal fleet governance (Alibaba Token Plan / TP1 wing PROBE-1-residual)
sources: 5
discovered_by: session (worktree .worktrees/ops-tp1-probe1, mandate from team-lead)
---

# PROBE-1-residual — TP1 burn-rate measured from 7 days of production use

**Trigger**: `research/operations/2026-08-10-fleet-order-spec.md` §2.5 marks every Alibaba Token
Plan (TP1) seat — Qwen 3.8 Max, Qwen 3.7, GLM 5.2-via-TP1, DeepSeek v4, MiniMax M2.5 — as
**PROBATION "until PROBE-1-residual (burn-rate + credits endpoint)"**. The `qwen` CLI has been
in real use since 2026-08-08 (PONG verified 2026-08-10 per memory
`discovery_m5_claude_oauth_revoked_deploy_rerouted_via_glm_2026_08_08` and the 2026-08-08
qwen-seat-integration doc). Zero ordered the probation reviewed against actual measured usage
instead of the originally-scoped "3 sample tasks". This is that measurement.

**1-sentence outcome**: PROBE-1-residual is CLOSED — burn-rate is measured (1330 calls, 211.7M
tokens over 7 days, no credits endpoint exposed via API) — and qwen3.8-max, qwen3.7-plus, and
deepseek-v4-flash-0731 are promoted PROBATION → ARMED in `FLEET_TOPOLOGY.json` v1.3 on that
mileage; deepseek-v4-pro, glm-5.2-via-TP1, and MiniMax M2.5 stay PROBATION because they show
**zero** measured calls in the same window.

## Data sources

1. `~/.qwen/usage_record.jsonl` (43 rows) — **session-level aggregate**: one row per `qwen`
   CLI session, with a `models` dict summing per-model requests/tokens for that session. No
   `id` field.
2. `~/.qwen/usage/token-usage-2026-08.jsonl` (1330 rows) — **per-API-call log**: one row per
   call, unique `id`, `model`/`source`/`authType`/token breakdown/`apiDurationMs`.
3. `research/operations/2026-08-10-fleet-order-spec.md` §2.5 / §6 / §8.4 — TP1 roster,
   PROBE ledger definition, "~$68 tier" figure.
4. `research/operations/2026-08-08-qwen-code-seat-integration-and-system-review.md` — first
   PONG confirmation, "6.95M tokens this session = new billing domain" precedent, "METERED
   Token Plan" characterization.
5. Web search, Aug 2026: Alibaba Cloud Model Studio / DashScope international (Singapore)
   list pricing for Qwen3.8-Max, Qwen3.7-Plus, DeepSeek-V4-Flash, and context-cache discount
   — cited inline where used, for the cost estimate only (not a confirmed TP1 contract term).

## ⚠️ Correction to the mandate's assumption — the two log files do NOT need `id`-dedup merging

The task brief assumed both files carry per-event records identifiable by `id` that overlap and
need deduplicating before summing. **Measured, not assumed**: `usage_record.jsonl` has **no
`id` field at all** — it is a session-level rollup (43 sessions), while `token-usage-2026-08.jsonl`
is the per-call log (45 sessions, 1330 calls, 1330 unique `id`s — zero duplicates within itself).
42 of the 43 `usage_record.jsonl` sessions also appear in the per-call log; 3 sessions in the
per-call log are absent from the rollup (not yet flushed to the coarser file). Comparing the two
representations for the same session (`35d1ba86-…`) shows the SAME underlying activity at
different grain and **the numbers don't match exactly**: the rollup reports 3 requests /
86,639 tokens for `qwen3.8-max`, the per-call sum for that session gives 2 requests / 85,484
tokens — a real, reported (not smoothed-over) discrepancy of 1 call / ~1,150 tokens, i.e. the
rollup and the per-call log are close (<2%) but not bit-identical.

**Conclusion**: `usage_record.jsonl` is redundant with `token-usage-2026-08.jsonl` at a coarser
grain, not an additive second source. Adding both together would double-count essentially all
of the volume. This document uses **`token-usage-2026-08.jsonl` alone** (per-call, dedup-safe by
construction, the more complete of the two) as the source of truth for every table below, and
uses `usage_record.jsonl` only as a cross-check (which it passes, within ~2%).

## Part 1 — Measured burn-rate (2026-08-08 → 2026-08-14, 7 days)

1330 calls, 211,699,042 total tokens. `totalTokens == inputTokens + outputTokens` in every row
checked (verified per-row and per-model-aggregate); `cachedTokens` is a **subset** of
`inputTokens` (cache-hit portion, not additive), `thoughtsTokens` is a **subset** of
`outputTokens` (reasoning-token portion). No GLM or MiniMax model appears anywhere in the log —
zero measured usage for those two families this window.

### Per model

| Model | Calls | Input tokens | Output tokens | Cached tokens (⊆input) | Thoughts tokens (⊆output) | Total tokens | Avg API duration | Median API duration |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3.8-max | 459 | 73,554,221 | 504,832 | 64,833,793 | 337,225 | 74,059,053 | 30.0 s | 16.8 s |
| qwen3.7-plus | 65 | 6,328,912 | 91,790 | 4,818,495 | 59,326 | 6,420,702 | 29.3 s | 10.2 s |
| deepseek-v4-flash-0731 | 806 | 130,434,007 | 785,280 | 125,240,064 | 449,933 | 131,219,287 | 12.7 s | 9.3 s |
| **Total** | **1330** | **210,317,140** | **1,381,902** | **194,892,352** | **846,484** | **211,699,042** | — | — |

Cache-hit rate is extreme (qwen3.8-max 88% of input tokens served from cache, deepseek-v4-flash
96%) — consistent with agentic-loop usage (repeated large system/tool-context prefixes), not
one-shot Q&A.

### Per day (`localDate`)

| Date | Total tokens | Model mix (tokens) |
|---|---:|---|
| 2026-08-08 | 12,934,300 | qwen3.8-max 12,934,300 |
| 2026-08-09 | 34,687,470 | qwen3.8-max 31,687,880 · qwen3.7-plus 2,999,590 |
| 2026-08-10 | 2,953,435 | qwen3.7-plus 2,953,435 |
| 2026-08-11 | 11,415,898 | deepseek-v4-flash 9,162,078 · qwen3.7-plus 445,435 · qwen3.8-max 1,808,385 |
| 2026-08-12 | 16,873,977 | deepseek-v4-flash 14,415,849 · qwen3.8-max 2,435,886 · qwen3.7-plus 22,242 |
| 2026-08-13 | 42,225,561 | deepseek-v4-flash 18,183,537 · qwen3.8-max 24,042,024 |
| 2026-08-14 | 90,608,401 | deepseek-v4-flash 89,457,823 · qwen3.8-max 1,150,578 |

Volume is sharply accelerating, not flat — day 7 (2026-08-14, partial day at capture time) alone
is 43% of the 7-day total, almost entirely deepseek-v4-flash-0731. This is a real trend, not
noise: report it as-is rather than averaging it away.

### Per (source, authType) — who the consumers are

| source | authType | Calls | Total tokens | Model split (calls) |
|---|---|---:|---:|---|
| main | openai | 981 | 183,933,000 | qwen3.8-max 388 · qwen3.7-plus 61 · deepseek-v4-flash 532 |
| general-purpose | openai | 251 | 24,486,926 | qwen3.8-max 18 · deepseek-v4-flash 233 |
| managed-auto-memory-extractor | openai | 34 | 1,288,146 | qwen3.8-max 13 · qwen3.7-plus 4 · deepseek-v4-flash 17 |
| managed-auto-memory-dreamer | openai | 40 | 1,037,940 | deepseek-v4-flash 24 · qwen3.8-max 16 |
| Explore | openai | 24 | 953,030 | qwen3.8-max 24 |

`authType` is `openai` for every single call — 100% of TP1 traffic goes through the
OpenAI-compatible-mode endpoint (`~/.qwen/settings.json` `providerMetadata.token-plan.baseUrl`),
none through a native DashScope auth path. `source: "main"` (the interactive `qwen` CLI
session) is the dominant consumer at 74% of calls / 87% of tokens; `general-purpose` and the
`managed-auto-memory-*` sources are subagent/background-task consumers riding the same key —
i.e. this key is already load-bearing for more than just interactive use.

### Part 1 — economic estimate (assumptions declared, not smoothed over)

The repo does **not** contain a per-token price table for TP1 — only the flat "~$68 tier"
figure (`fleet-order-spec.md` §2.5/§8.4) and the characterization "a METERED Token Plan" (2026-08-08
qwen-seat doc, §2.5 Q3). No per-token rate is documented on disk. To produce a number, this
report uses **public Aug-2026 Alibaba Cloud Model Studio / DashScope international (Singapore)**
list prices found via web search — explicitly **not verified against the actual TP1 contract
meter**, which the repo itself states is unconfirmed (plan type/reset/overage/concurrency all
open per the 2026-08-08 doc §2.6):

| Model | List price in / out (per 1M tok) | Cached-input price used | Note |
|---|---|---|---|
| qwen3.8-max | $2.00 / $6.00 | $0.25/1M (Model Studio's own published cached-input rate for this model) | direct match |
| qwen3.7-plus | $0.40 / $1.60 | $0.08/1M (20%-of-input rule, generic Model Studio cache discount) | closest public match found for this exact model string; cache rate is a generic assumption, not confirmed for this specific model |
| deepseek-v4-flash-0731 | $0.14 / $0.28 | $0.028/1M (20%-of-input rule) | cache discount rate assumed by analogy, NOT independently confirmed for this model |

Applying these to the measured 7-day tokens (non-cached input priced at list, cached input at
the cache rate, output — including embedded thoughts tokens — priced at list output rate):

| Model | Estimated 7-day cost |
|---|---:|
| qwen3.8-max | $36.68 |
| qwen3.7-plus | $1.14 |
| deepseek-v4-flash-0731 | $4.45 |
| **Total** | **≈$42.27** |

Daily average ≈$6.04/day → naive 30-day run-rate ≈**$181/month**, i.e. **≈2.7×** the documented
"~$68 tier". **This is flagged, not asserted as overspend**: it is entirely possible the $68
tier buys a bulk-discounted monthly credit allocation whose real unit economics differ from
metered public list pricing, or that the plan is a flat allowance rather than pay-per-token —
the repo explicitly says this mechanism is unconfirmed. What IS solid: real usage this week, at
public list rates, would already exceed the documented tier if it were metered 1:1 against
those rates. Recommend Zero/operator confirm the actual tier mechanics at the Model Studio
console (same visit as the credits-endpoint check below) before treating $68/month as a hard
ceiling for planning purposes.

## Part 2 — credits/usage API endpoint

Base URLs probed (key read from `~/.qwen/settings.json` → `env.BAILIAN_TOKEN_PLAN_API_KEY`,
used only in an `Authorization: Bearer` header inside a throwaway Python process — never
echoed, logged, or placed in argv):

- `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` (the configured base)
- `https://token-plan.ap-southeast-1.maas.aliyuncs.com` (its root)
- `https://dashscope-intl.aliyuncs.com/api/v1` (documented general DashScope intl endpoint)

Paths tried on each base: `/usage`, `/credits`, `/quota`, `/billing`, `/account/usage`,
`/dashboard/usage`, `/balance`, `/tokens/usage`, `/aigc/usage` — **20 requests, 20× HTTP 404**.

Sanity check: `GET {compat_base}/models` → **HTTP 200**, returns the real model roster
(`qwen3.7-max`, `qwen3.7-plus`, `qwen3.6-flash`, …) — confirms the key is live and the
compatible-mode gateway is reachable; the 404s above are "no such route", not an auth failure.
The `dashscope-intl.aliyuncs.com` 404s came back as structured application JSON
(`{"status":404,"error":"Not Found",...}`) rather than an empty gateway 404, meaning that host
also has a live backend behind it, just none of the guessed paths.

**Outcome**: endpoint crediti non esposto via API — verifica console Model Studio =
`operator[gui]`. This is a valid, closed outcome for PROBE-1-residual's credits-endpoint leg,
per the original scope ("if none respond: declare closed, this is a valid outcome").

## Part 3 — promotions applied

`FLEET_TOPOLOGY.json` bumped to `_version: "1.3"`:

- **PROBATION → ARMED** (real measured mileage this window): `qwen3.8-max`, `qwen3.7-plus`,
  `deepseek-v4-flash-0731`. Updated at `accounts.alibaba.slots.TP1` (full breakdown) and at the
  three `role_chains` rows that reference `qwen-3.8-max` without a prior probation note
  (`strategy_panel`, `doc_mass_nonpii`, `normative_search`) — each now carries an explicit
  `"ARMED 2026-08-14"` note citing this document.
- **Stays PROBATION, note corrected** (`builder_primary`'s `glm-5.2` chain entry): the old
  `"PROBATION until PROBE-1"` wording is now misleading — PROBE-1-residual IS closed, but
  GLM-via-TP1 specifically has **zero** measured calls this window (z.ai remains its active
  door). Reworded so a future reader doesn't read "PROBE-1 closed" as "GLM auto-promotes".
- **Stays PROBATION, discrepancy flagged**: `deepseek-v4-pro` (both the `refuter` and
  `reasoner` role_chains entries). **This is the one number that did not match the mandate's
  framing and is reported as-is rather than smoothed over**: the mandate names "deepseek-v4"
  as one of the seats with proven mileage, but the actual model measured in the logs is
  `deepseek-v4-flash-0731` — a different tier from `deepseek-v4-pro`, which is the model
  `FLEET_TOPOLOGY.json`'s existing `refuter`/`reasoner` chains reference. `deepseek-v4-pro`
  shows **zero** calls in the 7-day window. Promoting `-pro` on `-flash`'s mileage would be
  exactly the kind of unverified claim CLAUDE.md's anti-hallucination discipline forbids, so
  `-pro` stays PROBATION with a clarifying note, and a PENDING-ARMS line records the open
  question (does `-flash` substitute for `-pro` in these chains, or does it need its own row —
  an operator/session decision, not this probe's to make unilaterally).
- **Untouched, confirmed correct**: `MiniMax M2.5` (both `grunt` and `batch_throughput` entries)
  stays PROBATION — zero measured calls, PROBE-4 explicitly still open. `kimi-*` models listed
  under TP1 are untouched — out of PROBE-1 scope, Allegro/K1 remains the load-bearing Kimi door.
- **Untouched by design**: the hard NOs (§2.5, PII/client-facing/merge-deploy/final-gate/
  credentials-in-env), family-exclusion rule, and the Gear-3 fable_gate_gear3 chain — none of
  these are conditioned on PROBATION status, promotion does not touch them.
- `scripts/arsenal_probe.py`'s `probe_qwen_cloud_code()` comment/message corrected: the
  "operator rotation pending, gate 2026-08-08" framing was stale — the Keychain entry
  `qwen-cloud-code-token` is present on this machine (confirmed via
  `security find-generic-password -s qwen-cloud-code-token`, existence only, value never
  read) and the seat has carried the entire 7-day burn-rate above through
  `~/.qwen/settings.json`. No test corpus references this specific code path
  (`grep`ped `scripts/tests/test_arsenal_probe.py` — no hits), so no test update was needed.
  Probe *logic* (the Keychain-presence gate itself, and the `classify_generic` PONG check) is
  UNCHANGED per the mandate — only the comment and the fallback message text were corrected;
  the gate is a legitimate live-host check (a locked/absent Keychain today still correctly
  returns AUTH_DEAD), not a stale policy flag to remove.

## Conclusion

PROBE-1-residual's condition ("burn-rate + credits endpoint") is satisfied by real production
data: burn-rate is measured with per-call granularity and cross-checked against the coarser
session log; the credits endpoint is confirmed absent from the API surface (console-only). The
promotion applied is partial and evidence-scoped — three seats ARMED on their own measured
mileage, three seats explicitly left in PROBATION because their own mileage is zero (not
because PROBE-1 is still open), and one real naming discrepancy (`-pro` vs `-flash`) surfaced
rather than papered over.
