---
date: 2026-07-18
domain: marketing
client_case: none
sources:
  - https://github.com/dgrtwo/ebbr
  - https://metricgate.com/docs/empirical-bayes-shrinkage/
  - https://andrewpwheeler.com/2018/07/23/sorting-rates-using-empirical-bayes/
  - https://medium.com/@iqra.bismi/thompson-sampling-a-powerful-algorithm-for-multi-armed-bandit-problems-95c15f63a180
  - https://vkteam.medium.com/contextual-multi-armed-bandits-for-content-recommendation-or-not-by-bernoulli-alone-21d52be00f0
adversarial_review: codex
---

# WR2 growth-loop SPRINT R — closing the engagement→editorial loop into the topic-selector

**Question.** WR2 now has live IG engagement per published carousel, but the component that
decides WHAT to make next — `scripts/wr2_topic_selector.py::score_item` — is blind to it. How
should past engagement feed back into topic selection so that, all else equal, a topic in a
historically high-performing attribute-bucket scores higher — WITHOUT over-fitting a tiny,
skewed sample or starving exploration?

## Ground truth (verified on disk 2026-07-18)

- **The gap is real.** `score_item` = `freshness + keyword-relevance + tier + live_news_bonus`
  (`TIER_WEIGHT`, `LIVE_NEWS_BONUS_DIVISOR`). `grep -c engagement scripts/wr2_topic_selector.py`
  = **0**. The existing loop (`wr2-ig-metrics-analyst`, weekly) emits qualitative brand
  *amendments*; nothing re-weights *selection*.
- **The reward data.** `wr2_ig_metrics_scraper.py` writes `engagement_metrics`
  (`likes, comments, reach, saved, shares, total_interactions`) onto **published queue entries**
  (`human-review-queue.json`, keyed by `ig_media_id`) — **NOT** the `war_room_drafts` DB table
  (column absent, confirmed by a failed prod probe). n = **49 live + 17 archived = ~66** published
  carousels with metrics.
- **The distribution is heavy-tailed.** reach: min 515 / **median 1880 / max 141,240** (~75×
  median); saved: 1 / 23 / 1908; total_interactions: 11 / 96 / 11,093. A handful of carousels
  carry almost all the reach — the value is in the outliers, so any loop that only exploits the
  known-good buckets will systematically miss the next outlier.

## SOTA synthesis

1. **Empirical-Bayes (Beta-Binomial) shrinkage** is the correct estimator for engagement rates
   with small per-group counts ([ebbr](https://github.com/dgrtwo/ebbr),
   [MetricGate](https://metricgate.com/docs/empirical-bayes-shrinkage/),
   [Wheeler](https://andrewpwheeler.com/2018/07/23/sorting-rates-using-empirical-bayes/)). Fit one
   Beta prior to the whole corpus, then shrink each bucket's observed rate toward the global mean
   *in proportion to how few observations it has*. A bucket seen 3× is pulled almost entirely to the
   mean; a bucket seen 30× keeps most of its signal. This is the right tool ONLY at the coarsest
   usable granularity: WR2 has just **45** usable rows, so any multi-way cut has median n=1 (see the
   adversarial review) — EB is what lets even a single-dimension marginal (e.g. `domain`) be used
   without over-trusting a bucket seen twice. It does NOT rescue a three-way prior; nothing does at
   this n.
2. **Thompson sampling / bandit framing** supplies the explore-exploit balance
   ([Thompson sampling](https://medium.com/@iqra.bismi/thompson-sampling-a-powerful-algorithm-for-multi-armed-bandit-problems-95c15f63a180),
   [contextual bandits](https://vkteam.medium.com/contextual-multi-armed-bandits-for-content-recommendation-or-not-by-bernoulli-alone-21d52be00f0)):
   treat the (few) usable buckets as arms and *sample* from the posterior rather than taking the
   point estimate — undersampled buckets have wide posteriors and thus keep getting picked
   occasionally. Weight-class caveat (adversarial review): a per-CANDIDATE Beta draw is a MISUSE — it
   hands more lottery tickets to buckets with more candidates; the correct explore primitive here is
   a **pool-level ε/quota applied after the safety filters**, plus diversity injected at candidate
   generation. A full contextual bandit is overkill at ~1 carousel/day.
3. **Reward choice matters more than the algorithm.** Absolute `reach` is dominated by
   event virality/timing — which `live_news_score` already rewards upstream; ranking on reach
   would **double-count** that. Prefer a **rate** — `saved / reach` ("I want to keep this", the
   KB-adjacent evergreen signal) — but note it only normalises SCALE; it does NOT de-confound
   virality/timing/algorithmic distribution (`reach` is a post-treatment denominator), so it needs a
   maturation window + min-reach floor + a carousel-level hierarchical model before use.

## Recommendation (revised after adversarial review — the naive version is FALSIFIED)

**Do NOT build a three-way `(domain, register, layout)` engagement prior into `score_item`.** A
Codex `sol` red-team CADE'd it and disk verification (2026-07-18) sustained every objection. Two
independent fatal axes:

- **The keys don't exist at the decision point.** `score_item` sees only the RAW staging article:
  `title, content/summary, detected_at/published_at, tier/qwen_tier, live_news_score, liveness_tier`
  (verified — it reads no `domain`/`register`/`layout` and never references `domain`). `domain` is
  derived AFTER selection, `register` is chosen by the composer, `layout_family` is derived from the
  generated slides. Two of the three "attributes" are DOWNSTREAM OUTCOMES, not candidate features —
  you cannot key a selection-time prior on them.
- **n is fatal for interactions.** Only 45 published records carry usable numeric metrics (the 17
  "archive" entries have NULL metrics and are `applied_ready_for_damar`, not published). Even a
  3-way cut gives ~27 observed cells with **median n = 1, 16/27 singletons, max n = 4** — every cell
  posterior collapses to the global mean, so the "prior" is a near-constant. `archetype` is `None`
  on all 49 (my earlier "45/49" wrongly counted key-presence, not value) — not a usable key either.

**What survives (the narrow, weaker, honest path):**

1. **Marginal-only, selection-time-feature-only.** The only prior that is both observable at
   `score_item` AND identifiable at n≈45 is a single-dimension, heavily EB-shrunk prior on a feature
   the raw article already has — the **keyword-cluster** `score_item` already computes, or the
   **source**. Defer all interactions and all post-composition attributes until n is in the hundreds.
2. **Fix the reward before using it.** `saved/reach` normalises scale but does NOT de-confound
   virality/timing/algorithmic distribution (`reach` is a post-treatment denominator). Required
   first: a uniform maturation window, a min-reach floor / effective-sample-size cap, a
   carousel-level hierarchical (overdispersed Beta-Binomial) model — NOT cell-rate aggregation — and
   a sensitivity check across pooled-rate vs median-deck-rate. (The earlier "neutralises the
   audience-size confound" claim is withdrawn.)
3. **Architecture: queue and selector are BOTH Pro-side.** The selector runs on the **Pro** via
   `~/.openclaw/bin/wr2/wr2-script-wrapper.sh` (querying the Fly staging endpoint) — there is no
   "Pro→Fly" export (that boundary was invented). Any prior is a **local, versioned,
   freshness-checked artifact on the Pro** the wrapper reads.
4. **Exploration must live at candidate GENERATION, not the score.** Thompson-at-`score_item`
   explores only inside an already-filtered pool (pending only, <72 h, and under
   `WR2_PREFER_LIVE_NEWS=true` restricted to breaking/developing, then top-20). A per-candidate draw
   also mis-uses Thompson sampling — it hands more lottery tickets to buckets with more candidates.
   Correct: diversify candidate generation upstream, add a pool-level ε/quota AFTER the safety
   filters, and log selection propensities.

**Bottom line (the actionable recommendation).** The highest-leverage engagement→editorial surface
is NOT the topic-selector — it is the EXISTING `wr2-ig-metrics-analyst` → brand-amendment loop
(post-hoc, qualitative), which hits none of these blockers. Concretely: **(a)** extend the weekly
analyst to emit a marginal, EB-shrunk **`domain`-level `saved/reach` table** (domain IS knowable
post-hoc) as a decision aid for the human/brand loop; **(b)** do NOT wire an engagement term into
`score_item` until BOTH a selection-time feature is chosen AND n ≥ ~200 matured decks exist. Atteso:
avoids shipping statistical theatre now, and preserves a real, identifiable loop for later.

## Data facts (verified on disk 2026-07-18, so the next session doesn't re-learn them)

- **Usable reward rows = 45**, not 66: only published queue entries have real numeric metrics; the
  17 "archive" entries carry NULL metrics and are `applied_ready_for_damar`, not published.
- **Attribute availability at published-carousel level:** `domain` present on 45/49 (value-non-null),
  `topic_slug` 47/49, `tone_register_primary` and `layout_family_primary` present; `archetype`,
  `register`, `layout_family`, `tier`, `audience`/`audience_segment` are **absent or all-`None`** on
  published entries. Do not key on those.
- **Attribute availability at `score_item` time = keyword-cluster / source / freshness / tier /
  live_news only.** `domain`/`register`/`layout` do NOT exist on the staging candidate — they are
  produced downstream. This is the constraint that kills any attribute-keyed *selection* prior.

## Checklist for the FEASIBLE path (not the CADE'd three-way prior)

- [x] Confirm the gap, the reward data, the skew, the field availability, the run-host (all above).
- [ ] Extend `wr2-ig-metrics-analyst` (weekly, Pro) to emit a marginal EB-shrunk **`domain`-level
      `saved/reach`** table + a maturation-window/min-reach guard, as a human-loop decision aid.
- [ ] (Deferred, GO-gated) Only once a *selection-time* feature (keyword-cluster/source) is chosen
      AND n ≥ ~200 matured decks: a single-dimension, bounded, pool-level-explored engagement term in
      `score_item`, kept additively separate from `live_news_bonus`. Not before.
- [ ] Never revive the `(domain, register, layout)` prior or a "Pro→Fly export" — both are falsified.

## Adversarial review

Reviewed by Codex `gpt-5.6-sol` (high effort), generator≠grader — the author did not grade it.
**Verdict: CADE**, and disk verification (this session) sustained all five objections — the naive
recommendation was rewritten wholesale, not merely "sharpened":

1. **Statistical power — REAL DEFECT.** 45 usable records ⇒ ~27 observed cells, median n=1, 16/27
   singletons, max n=4 (no cell near the fictional "n=30"). The three-way EB prior is statistical
   theatre; only regularized *marginal* effects are identifiable. → the recommendation now forbids
   interactions and keys on a single selection-time feature.
2. **Reward de-confounding — REAL DEFECT.** (My attack's arithmetic was wrong — the reach-515 deck
   has 1 save, `saved/reach`=0.0019 < global 0.0108, doesn't swamp.) But the substance held:
   `saved/reach` does not de-confound virality/timing; needs maturation window + min-reach floor +
   carousel-level hierarchical model. → "neutralises the confound" withdrawn.
3. **Ground-truth — REAL DEFECT (the killer).** Verified: `score_item` reads none of
   domain/register/layout; the staging projection carries none of them; `domain` is derived post-
   selection, `register` chosen by the composer, `layout` derived from generated slides — two of
   three keys are downstream outcomes. `archetype` is `None` on all 49. → the whole keying scheme was
   built on features unavailable at the decision point.
4. **ETL boundary — REAL DEFECT.** The selector runs on the **Pro** (verified plist wrapper), not
   Fly; "Pro→Fly export" was invented. → prior is a local Pro-side artifact.
5. **Feedback pathology — REAL DEFECT.** The explore floor acts after the pool is already filtered
   (pending / <72 h / breaking-only / top-20); a per-candidate Thompson draw multiplies tickets by
   bucket size (Russo et al.). → exploration moved to candidate generation + a pool-level ε/quota.

**Net:** the sprint's value is a *negative/constraint result* — the naive engagement→selector prior
is non-applicable (keys) and non-identifiable (n); the feasible loop is the marginal `domain`-level
analyst aid + a deferred, selection-time-feature, n≥~200 revisit. This is exactly what generator≠grader
is for: it caught the recommendation being built on phantom attributes and an invented data path.
