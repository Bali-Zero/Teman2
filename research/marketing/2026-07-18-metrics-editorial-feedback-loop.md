---
date: 2026-07-18
domain: marketing
client_case: none — WR2 growth loop SPRINT R1
sources:
  - https://arxiv.org/abs/2401.09804 (Clickbait vs Quality, ACM WebConf 2024 — deep-read)
  - https://arxiv.org/html/2406.02611v2 (LOLA, Wharton/Upworthy — deep-read)
  - https://arxiv.org/abs/1908.06256 (Yahoo batched Thompson Sampling — deep-read)
  - https://mediacopilot.ai/how-the-salt-lake-tribune-uses-chartbeat-to-guide-editorial-decisions/ (deep-read)
  - https://www.socialinsider.io/social-media-benchmarks/instagram (2026 Q2 measured benchmarks — deep-read)
  - https://smartocto.com/blog/ai-editorial-analytics-next-step/ (deep-read)
  - internal: human-review-queue.json engagement_metrics n=49 (M5 mirror, hash-verified vs Pro SSOT 2026-07-17)
  - internal: ~/.claude/skills/bali-zero-brand/_proposed-amendments/2026-06-29-ig-insights.md (weekly analyst)
---

# Metrics-driven editorial feedback for WR2: what SOTA actually does, what our 49 posts say, and the one thing to build

**Question.** WR2 now measures real IG engagement per carousel (49 entries with reach/saves/shares
since #2578). The weekly analyst turns metrics into BRAND amendments, but nothing feeds the
TOPIC SELECTOR: selection is still blind to what the audience amplifies. What is the
evidence-based minimal design to close the metrics→selection loop without the documented
failure modes?

## What the evidence says (external)

1. **Engagement-only optimization can be worse than random.** Formal result (ACM WebConf 2024,
   validated on Twitter data): when producers can invest in "gaming" as well as quality, a pure
   engagement-optimizing recommender converges to LOWER average realized quality than random
   selection. Any WR2 auto-tune must therefore sit BEHIND the brand/accuracy gates, never trade
   against them.
2. **LLM judgment is a useful but capped prior.** LOLA (17,681 real Upworthy headline tests):
   LLM-alone engagement prediction plateaus ~83% accuracy and overfits if trusted statically;
   hybrid LLM-prior + live-bandit beats both pure A/B and pure bandit. Translation: the weekly
   analyst's proposals are a PRIOR to be corrected by measured data, not ground truth.
3. **At low throughput, tune STRATEGIES, not items.** Item-level bandits need volume we will
   never have (2 post/week ≈ 104/yr). ACM UMAP 2026: bandit over k curated strategy profiles is
   the tractable, editorially-bounded form. Yahoo (production): BATCHED updates (+3.69% clicks
   vs static) — per-post reweighting is neither needed nor sound.
4. **Delay the reward.** Saves/shares/reach accumulate for days (and IG reportedly stages
   audience expansion); scoring a post before ~48-72h reads noise.
5. **Every credible operation keeps a human veto.** smartocto ("the editor remains the one to
   decide"), Salt Lake Tribune ("viral ≠ important" norm on top of Chartbeat). No serious source
   documents autonomous weight-rewrite as best practice.
6. **Vanity metrics are explicitly de-weighted everywhere**: engaged-time/completion/recirculation
   (news vendors), saves+shares over likes (IG ecosystem, though the "sends 3-5x likes" figure is
   marketing paraphrase, not Meta documentation).

## What our own 49 posts say (internal, measured 2026-07-17)

- Massive variance: reach 515 → 141,240 (median 1,872); shares 0 → 5,870; saves 1 → 1,908.
- **Every top-reach post is a concrete-number/event hook** ("165 foreigners deported",
  "37,881 villas", "$7B mega-project shut down"); every bottom post is an abstract evergreen
  ("Own a PT PMA", "Your company doesn't stay still"). This independently validates the
  liveness rewire (SPRINT B1): the audience amplifies exactly the breaking/developing register
  the pipeline could not see until now.
- Per-domain medians (n=45 joinable): property med reach 4,144 / save-rate 1.01%; visa 3,094 /
  0.70%; regulatory 1,946 / 0.59%; tax 1,416 but save-rate 1.82% (highest utility — matches the
  analyst's +78% SL finding); company 719 / 0.28% (structurally weak).
- The weekly analyst (2026-06-29) already produces solid brand-side findings but emits only
  human-readable prose — nothing machine-readable ever reaches selection.

## THE recommendation (one, actionable)

**Adopt a bounded weekly "editorial prior" file — not a bandit, not a rewrite.**

- The weekly `wr2-ig-metrics-analyst` additionally emits a machine-readable
  `editorial-priors.json`: per-domain (and later per-liveness-tier) additive bonus derived from
  measured save-rate + share-rate on posts ≥72h old, EMA-decayed (half-life ~8 weeks so the
  prior corrects itself as data accumulates, per LOLA).
- `wr2_topic_selector.score_item` adds it as ONE soft term, **hard-capped at ±10 points**
  (~10% of typical scores — the same magnitude as the routine-title penalty), reading the file
  defensively (missing/stale file → 0, like live_news_score today).
- Guardrails wired from day one: (a) the cap; (b) critic/brand gates untouched and upstream-
  unaware of the prior (accuracy floor per ACM WebConf 2024); (c) a topic-category entropy
  monitor line in the weekly report — if selected-domain entropy falls while engagement rises,
  the analyst FLAGS for review, never auto-suspends silently; (d) the prior file lands via PR
  (auto-merge) so every weight change is a reviewable diff — Zero's veto surface, zero new
  ceremony.
- **Expected effect**: selection tilts toward tax/property/concrete-event topics (the measured
  amplification) within ~2 weeks of arming, verifiable in the next monthly window as median
  save-rate ↑ vs the 1.02% corpus baseline, with domain entropy not collapsing below current
  6-domain spread.

This is seed #5 of the growth-loop backlog, now evidence-shaped: build it as a SPRINT B after
the liveness chain (B1) is proven live, since the prior's per-tier leg consumes B1's fields.

## Pitfalls we explicitly avoid (from the checklist)

Item-level bandit at our cadence (underpowered) · per-post weight updates (batched weekly
only) · scoring before 72h (staged reach) · trusting analyst predictions as truth (decaying
prior) · letting engagement trade against the brand/accuracy gates (cap + unchanged critic) ·
silent narrowing (entropy flag, human-reviewed) · treating vendor numbers (Echobox +36%,
"sends 3-5x likes") as targets — directional only, unaudited.
