---
date: 2026-07-18
domain: marketing
client_case: none — WR2 growth loop SPRINT R1
adversarial_review: codex
sources:
  - https://arxiv.org/abs/2406.02611 (LOLA — deep-read; characterization corrected after adversarial review, see below)
  - https://arxiv.org/abs/2401.09804 (Clickbait vs Quality, ACM WebConf 2024 — deep-read)
  - https://arxiv.org/abs/1908.06256 (Yahoo batched Thompson Sampling — deep-read)
  - https://mediacopilot.ai/how-the-salt-lake-tribune-uses-chartbeat-to-guide-editorial-decisions/ (vendor/trade blog — normative only)
  - https://www.socialinsider.io/social-media-benchmarks/instagram (vendor benchmark, 2025 posts, ER = likes+comments/follower — scope-limited)
  - https://smartocto.com/blog/ai-editorial-analytics-next-step/ (vendor blog)
  - internal: human-review-queue.json engagement_metrics n=49 (M5 mirror, hash-verified vs Pro SSOT 2026-07-17)
  - internal: ~/.claude/skills/bali-zero-brand/_proposed-amendments/2026-06-29-ig-insights.md (weekly analyst)
---

# Metrics→selection feedback for WR2: what the evidence actually supports, and the honest first step

**Question.** WR2 now measures real IG engagement per carousel (49 entries since #2578). The
weekly analyst turns metrics into BRAND amendments, but nothing feeds the TOPIC SELECTOR.
What is the evidence-based minimal design to close the metrics→selection loop without the
documented failure modes?

**Process note.** V1 of this capture was adversarially REFUTED (seat: codex, gpt-5.6-terra,
2026-07-18) — over-claimed sources and statistically indefensible per-domain inferences. This
is the amended, surviving version. Details in §Adversarial review.

## What the external evidence supports (corrected scope)

1. **Engagement-only optimization can degrade realized quality** (ACM WebConf 2024,
   arxiv 2401.09804): a game-theoretic equilibrium model of strategic creators, empirically
   motivated on Twitter data, shows engagement-optimizing recommendation can converge below
   random on consumed quality once producers can invest in gaming. It is a MODEL-CONDITIONAL
   warning, not a prescriptive design rule — but it motivates keeping any engagement tuner
   strictly behind the brand/accuracy gates.
2. **LLM engagement prediction is weak — weaker than v1 of this memo claimed** (LOLA,
   arxiv 2406.02611, Ye/Yoganarasimhan/Zheng, Upworthy 17,681 headline tests): per the
   abstract, prompt-based prediction performs POORLY and even embedding/fine-tuned models are
   only "marginally higher accuracy than random predictions". The hybrid (LLM prior + UCB
   bandit corrected by live traffic) beats A/B, pure bandit, and pure LLM, especially under
   limited traffic. Lesson that survives: never trust model-predicted engagement as more than
   a weak, decaying prior — live data must dominate.
3. **Batched (not per-item) updates are the production pattern** (Yahoo, arxiv 1908.06256):
   batched Thompson Sampling on live HEADLINE traffic beat static test-rollout (+3.69% clicks).
   Scope caveat: this validates batched allocation for headline variants at portal scale — it
   does NOT directly validate weekly cross-post topic weights on Instagram. We borrow the
   batching principle, not the effect size.
4. **Human veto is universal in credible practice** (smartocto explicitly; Salt Lake Tribune
   per a vendor-blog account — normative, not auditable evidence): no serious source documents
   fully autonomous weight rewrites as best practice.
5. **IG benchmark data is thin and definition-sensitive**: Socialinsider's benchmark (2025
   posts) defines engagement as likes+comments per follower — it CANNOT substantiate
   saves/shares-as-reward, a 72h maturation window, or any save-rate target. No source found
   quantifies a saves/shares→follower-growth regression. Treat all such claims as unmeasured
   marketing narrative.

## What our own 49 posts say — hypothesis-generating ONLY

n=49 observational posts; per-domain cells as small as n=2-5; domain is confounded with hook
shape, post age, format, timing, follower exposure, and execution quality. NO causal domain
claim is defensible from this data. Descriptively (unblinded, post-hoc reading):

- Variance is enormous: reach 515 → 141,240 (median 1,872); shares 0 → 5,870; saves 1 → 1,908.
- The highest-reach posts happen to be concrete-number/event hooks ("165 deported",
  "37,881 villas"); the lowest are abstract evergreens. This is CONSISTENT with the liveness
  rewire (B1) being valuable, but does not independently prove it — the reading was not
  pre-registered and has no denominator control.
- Tax posts show the highest save-rates in both our reading and the weekly analyst's
  2026-06-29 finding (+78% SL, n=5) — a hypothesis worth testing, not a fact.

## THE recommendation (amended after adversarial review)

**Build the metrics→selection loop in SHADOW MODE first; arm nothing until pre-registered
criteria are met.**

- **Phase 1 (build now, report-only)**: the weekly `wr2-ig-metrics-analyst` additionally emits
  `editorial-priors.json` as a DIAGNOSTIC artifact: per-domain (later per-tier) engagement
  summaries on posts ≥72h old, each cell carrying its n and an uncertainty interval; plus the
  hypothetical bonus it WOULD have applied and which past topic picks it would have changed
  (counterfactual log). The topic selector does NOT consume it. This produces the evidence to
  design Phase 2 honestly, at zero editorial risk.
- **Phase 2 (armed only if pre-registered criteria pass, each prior update behind explicit
  operator approval — auto-merge audit trail is NOT a veto)**: minimum per-cell sample
  (pre-declared, e.g. n≥10 in-window), bonus cap CALIBRATED against the measured historical
  score-margin distribution (not asserted), expiry + zero-on-stale-data, explicit
  rollback/kill thresholds, and quota-balanced exploration with propensity logging so the
  prior's own selection effect can be corrected (the self-reinforcement failure: topics chosen
  BY the prior then measured as "winning").
- At ~2 posts/week across 6 domains, ANY per-domain scheme accumulates ~2-3 observations per
  domain per 8-week half-life — Phase 2 may legitimately conclude "never arm per-domain;
  only per-liveness-tier or global format signals have enough data". Shadow mode will show this.

## Pitfalls checklist (extended)

Vanity-metric reward (likes) over saves/shares/completion · item-level bandit at 2/week
(underpowered) · per-post weight updates · scoring before 72h (late accumulation + possible
staged reach) · trusting LLM/analyst predictions as truth (LOLA: barely-better-than-random) ·
letting engagement trade against brand/accuracy gates · silent topic narrowing (entropy +
accuracy + lead-quality guardrails, human-reviewed — entropy alone is not enough) ·
self-reinforcing priors without propensity logging · metric API revisions / late-accumulating
counts · denominator instability at low reach · Simpson's paradox across liveness tiers ·
seasonality and news shocks · novelty fatigue · optimizing saves/shares at the expense of
qualified leads or regulatory accuracy · vendor numbers (Echobox +36%, "sends 3-5x likes")
as targets — unaudited, directional at best.

## Adversarial review

- **Seat**: codex (gpt-5.6-terra, read-only sandbox, 2026-07-18) — seat ≠ author (author:
  Fable 5 orchestrator session + Sonnet 5 web-research lane).
- **Verdict on v1: REFUTED** — 4 FATAL attacks: (1) LOLA mischaracterized (wrong affiliation,
  "83% ceiling" overstated — the abstract reports prompt-based prediction performs poorly and
  even fine-tuned models are only marginally above random; verified against the arxiv abstract
  and corrected); (2) n=49 observational with 2-5-post domain cells cannot establish domain
  effects (confounding); (3) "every top is concrete/every bottom abstract" was unblinded
  post-hoc coding presented as validation; (4) the proposed prior was self-reinforcing with no
  selection-bias correction. SERIOUS: Yahoo/WebConf/Socialinsider scope inflation; EMA math
  (~2-3 obs/domain/half-life); uncalibrated ±10 cap; auto-merge conflated with human veto.
- **What changed in v2**: sources re-scoped to what they actually show; internal analysis
  demoted to hypothesis-generating with confounds named; recommendation restructured to
  shadow-mode-first with pre-registered arming criteria, operator approval per prior update,
  propensity-logged exploration, and calibrated (not asserted) caps; pitfalls extended with
  the refuter's additions. The one-line recommendation survives in weakened form: build the
  measurement artifact now, earn the right to arm it later.
