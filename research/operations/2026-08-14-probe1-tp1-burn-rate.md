---
date: 2026-08-14
domain: operations
client_case: N/A — internal fleet governance (Alibaba Token Plan / TP1 wing PROBE-1-residual)
sources: 9
discovered_by: session (worktree .worktrees/ops-tp1-probe1, mandate from team-lead); economic section corrected same-day after independent WebSearch verification by team-lead against Alibaba's own docs; console ground truth (Part 4) read by Zero + team-lead directly from the Model Studio dashboard same-day
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
tokens over 7 days, cross-validated against the console's own 217.06M counter within ~2.5%),
console ground truth confirms usage is **within plan** (Pro Plan, 7-day rolling quota 56.31%
used, ~44% headroom, auto-renewal OFF — `operator[business]` before 2026-09-09) — and
qwen3.8-max, qwen3.7-plus, and deepseek-v4-flash-0731 are promoted PROBATION → ARMED in
`FLEET_TOPOLOGY.json` v1.4 on that mileage; deepseek-v4-pro and glm-5.2-via-TP1 stay PROBATION
(zero measured calls); MiniMax M2.5 and kimi-k2.x are reclassified **PHANTOM** — console- and
API-confirmed to not be part of this plan at all, making PROBE-4 moot.

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
   list pricing for Qwen3.8-Max, Qwen3.7-Plus, and general context-cache discount mechanics
   — cited inline where used, for the cost estimate only (not a confirmed TP1 contract term).
6. [help.aliyuncs.com/en/model-studio/deepseek-v4-flash](https://www.alibabacloud.com/help/en/model-studio/deepseek-v4-flash)
   — official per-model pricing (input/output/cached-input), fetched and confirmed 2026-08-14.
7. [help.aliyuncs.com/en/model-studio/token-plan-overview](https://www.alibabacloud.com/help/en/model-studio/token-plan-overview)
   — Token Plan Team Edition: Singapore-only, seat tiers $30/$100/$200/month, no $68 tier.
   Fetched and confirmed 2026-08-14.
8. [alibabacloud.com/blog — Token Plan for Individual](https://www.alibabacloud.com/blog/model-studio-token-plan-for-individual-one-subscription-for-every-ai-model-up-to-3x-more-value_603426)
   — Individual plan "Pro" tier = $68/month, rolling 5h/7d credit windows, "≈3× more usage
   than pay-as-you-go" claim. Fetched and confirmed 2026-08-14.
9. Model Studio console dashboard (Zero + team-lead, 2026-08-14, screenshots) — TP1's actual
   plan/quota/roster ground truth, see Part 4. Key stays masked in the console UI; never
   transcribed in clear.

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
| deepseek-v4-flash-0731 | $0.138 / $0.275 | $0.028/1M | **CORRECTED 2026-08-14** — all three numbers are Alibaba's own official published rate for this exact model ([help.aliyuncs.com/en/model-studio/deepseek-v4-flash](https://www.alibabacloud.com/help/en/model-studio/deepseek-v4-flash)), not an analogy/assumption as first written; the earlier $0.14/$0.28 rounding and "20%-rule" framing for the cache price is superseded by this citation (the values happen to coincide almost exactly) |

Applying these to the measured 7-day tokens (non-cached input priced at list, cached input at
the cache rate, output — including embedded thoughts tokens — priced at list output rate):

| Model | Estimated 7-day cost |
|---|---:|
| qwen3.8-max | $36.68 |
| qwen3.7-plus | $1.14 |
| deepseek-v4-flash-0731 | $4.44 |
| **Total** | **≈$42.26** |

Daily average ≈$6.04/day → naive 30-day run-rate ≈**$181/month**. Label this precisely: it is a
**metered-equivalent ceiling** — what this measured usage would cost paying per-token at
official Alibaba list prices with no subscription at all. It is NOT arithmetically comparable
to the documented "~$68/month tier" (§2.5/§8.4 of the fleet-order spec), and an earlier version
of this document made exactly that flawed comparison (≈2.7×) — **struck 2026-08-14** after
independent verification against Alibaba's own docs surfaced two compounding problems:

1. **Value multiplier, not 1:1.** The $68 figure is the Individual plan's "Pro" tier
   ([Alibaba blog: Token Plan for Individual](https://www.alibabacloud.com/blog/model-studio-token-plan-for-individual-one-subscription-for-every-ai-model-up-to-3x-more-value_603426)),
   whose stated claim is **"≈3× more usage than pay-as-you-go"** for the same spend — meaning
   $68 of Individual-plan credits could plausibly cover ≈$150-200 of list-equivalent usage. Our
   measured ≈$181 metered-equivalent could therefore land at-or-under that real ceiling, not
   2.7× over it. Comparing a metered-equivalent dollar figure directly against a subscription
   sticker price, without applying that multiplier, understates the tier's real capacity.
2. **Product/region mismatch.** TP1's actual endpoint
   (`token-plan.ap-southeast-1.maas.aliyuncs.com`) is the **Singapore** region. Alibaba's own
   [Token Plan (Team Edition) doc](https://www.alibabacloud.com/help/en/model-studio/token-plan-overview)
   states Team Edition is available **only** in Singapore, with seat tiers **$30 / $100 / $200
   per month** — no $68 tier exists in that product at all. The $68 figure is documented only
   for the Individual plan. Which product TP1 actually subscribes to cannot be resolved from
   the API alone (see Part 2) — this remains an `operator[gui]` item, now with a precise
   question: *which edition/tier is this key actually on, and how many credits remain this
   cycle?* Do not treat "$68/month" as a confirmed hard ceiling for planning until that's
   answered.

What IS solid, independent of which tier applies: the underlying token volume is real,
measured, and growing (see the per-day table above), and cache-hit-adjusted list pricing puts a
genuine dollar figure — ≈$181/month metered-equivalent — on it for the first time. That number
is worth tracking over the next few weeks regardless of which subscription product absorbs it.

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

## Part 4 — Console ground truth (2026-08-14, Zero + team-lead, Model Studio dashboard)

The credits-endpoint gap left by Part 2 (API confirmed silent) is closed here with a direct
console read — screenshots reviewed by Zero and the team-lead. This section supersedes the
`operator[gui]` placeholder wherever it appears above; the key itself stays masked in the
console UI and was never transcribed in clear anywhere in this repo or this report.

### Plan & renewal

**"Pro Plan"**, status ACTIVE, start 2026-08-08 17:47, end 2026-09-09. **Auto-Renewal NOT
Enabled.** New flag: `operator[business]` — decide renewal before 2026-09-09 or the whole TP1
wing lapses mid-cycle.

### Quota model — the real constraint

Not a flat monthly credit pool: a **7-Day rolling quota**, **56.31% used** as of 2026-08-14
21:32, resetting 2026-08-15 22:50 UTC+8, zero add-on credit packs purchased. **This is the
number that governs sustainability, not the $181/month metered-equivalent list-price figure
from Part 1** (which stays useful only as an external reference point, e.g. for comparing
against a pure pay-as-you-go alternative). **Economic verdict, corrected**: real usage is
**within plan** — 56.31% of the 7-day rolling window consumed during this probe's own
peak-burn period (2026-08-14 alone was 43% of the week's local-log total, per Part 1's per-day
table) leaves roughly **44% headroom**. The earlier "$181 vs $68 ≈ 2.7×" framing and its
"metered-equivalent ceiling, not confirmed overspend" softened replacement (both struck in the
prior commit) are both superseded by this direct measurement: there is no overspend signal at
all, measured or estimated — the plan's own quota dashboard says so directly.

### Cross-check: console counter vs local logs

| | Total tokens (2026-08-08→14) |
|---|---:|
| Console dashboard | 217,060,000 |
| Local logs (this doc, Part 1) | 211,699,042 |
| Delta | ~2.5% |

Console also reports **91% cache-hit** (195.87M cached / 215.70M input) — consistent with, if
slightly higher than, the per-model cache-hit rates computed from local logs in Part 1
(88-96% range). **Reported as a reconciliation, not smoothed over**: a console-side counter and
two independently-derived local log files agreeing within ~2.5% is a real cross-validation of
the burn-rate measurement, and the small residual gap is attributable to counting-boundary/
rollup-timing differences between the console's own aggregator and the local per-call log, not
to either source being wrong.

Console per-day totals (for comparison against Part 1's per-day table, which used the local
per-call log):

| Date | Console total tokens |
|---|---:|
| 2026-08-08 | 13,470,000 |
| 2026-08-09 | 35,490,000 |
| 2026-08-10 | 2,950,000 |
| 2026-08-11 | 11,950,000 |
| 2026-08-12 | 17,520,000 |
| 2026-08-13 | 43,270,000 |
| 2026-08-14 | 92,490,000 (partial — record day) |

Shape matches the local per-day table closely (both show 2026-08-14 as by far the largest day),
confirming the trend observation in Part 1 is real, not a local-log artifact.

### Roster reconciliation — MiniMax and kimi-k2.x are PHANTOM, not PROBATION

Console lists **14 models** on this plan, authoritative and directly contradicting the
2026-08-10 census in `FLEET_TOPOLOGY.json`'s prior text ("15 models... incl. MiniMax-M2.5,
kimi-k2.5/2.6/2.7"):

qwen3.8-max (flagged "Limited-time Night 50% Off"), qwen3.7-plus, qwen3.7-max, qwen3.6-flash,
qwen-audio-3.0-tts-plus, qwen-audio-3.0-realtime-plus, wan2.7-image, wan2.7-image-pro,
happyhorse-1.1-i2v, happyhorse-1.1-t2v, happyhorse-1.1-r2v, deepseek-v4-pro,
deepseek-v4-flash-0731, glm-5.2. **No MiniMax M2.5. No kimi-k2.x of any version.**

Re-probed `GET /compatible-mode/v1/models` (2026-08-14, same key, same non-destructive read as
Part 2) as an independent cross-check: it returns **11** models — exactly the console's 14
minus the 3 `happyhorse-1.1-*` video-gen models, which are console-listed but not exposed on
the OpenAI-compatible-mode models endpoint. 11 + 3 = 14, matching the console exactly. Two
independent surfaces (console UI, API endpoint) now agree MiniMax and kimi-k2.x are simply not
part of this plan — this is not a measurement gap to close with more probing, it's a roster
correction.

**Consequence**: `FLEET_TOPOLOGY.json`'s `grunt` and `batch_throughput` chains' `minimax-2.5`
entries are relabeled **PHANTOM** (not PROBATION) — PROBE-4 (the planned MiniMax sample-lot
verification) is now moot, since there is no live MiniMax seat on this account to verify. If
MiniMax capacity is still wanted, it requires either adding it to this Token Plan or sourcing a
different account — a decision, not a probe.

### Additional doors registered (no new seats invented)

- **Anthropic-protocol base**: `https://token-plan.ap-southeast-1.maas.aliyuncs.com/apps/anthropic`
  — same class of door as the z.ai `claude-glm` shim. Usable with `ANTHROPIC_AUTH_TOKEN`
  (OAuth-style bearer), **never** `ANTHROPIC_API_KEY` — CLAUDE.md §5's Anthropic-SDK ban
  applies identically to this endpoint. Registered as a door on the existing TP1 account, not a
  new role_chain seat.
- **Unexploited capabilities**, paid-for but wired into zero role_chains: image-gen
  (`wan2.7-image` / `wan2.7-image-pro`), video-gen (`happyhorse-1.1-i2v/t2v/r2v`), TTS/realtime
  audio (`qwen-audio-3.0-tts-plus` / `qwen-audio-3.0-realtime-plus`). Flagged only — whether and
  how to use them is a Zero decision, not this probe's to make.
- **Operational note**: qwen3.8-max carries a console-visible "Limited-time Night 50% Off"
  discount — future TP1-heavy H24 batch lanes should schedule at night to exploit this.

## Conclusion

PROBE-1-residual's condition ("burn-rate + credits endpoint") is satisfied by real production
data, now cross-validated twice: burn-rate is measured with per-call granularity, cross-checked
against the coarser local session log (Part 1), AND cross-checked against the Model Studio
console's own counter (Part 4, ~2.5% delta). The credits endpoint is confirmed absent from the
API surface (Part 2) but closed with direct console ground truth instead (Part 4): **usage is
within plan, ~44% headroom on the 7-day rolling quota, auto-renewal is OFF and needs an
operator decision before 2026-09-09.** The promotion applied is partial and evidence-scoped —
three seats ARMED on their own measured mileage, deepseek-v4-pro and glm-5.2-via-TP1 left in
PROBATION because their own mileage is zero, and MiniMax M2.5 (plus kimi-k2.x) reclassified
PHANTOM rather than PROBATION once the console roster proved they were never part of this plan
at all. Two real discrepancies were surfaced rather than papered over in this probe: the
`-pro` vs `-flash` naming mismatch (Part 3) and the MiniMax/kimi roster phantom (this part).
