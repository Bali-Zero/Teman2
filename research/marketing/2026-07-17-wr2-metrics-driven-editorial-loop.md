---
date: 2026-07-17
domain: marketing
client_case: none
sources:
  - https://ar5iv.labs.arxiv.org/html/2007.13019
  - https://knightcolumbia.org/content/recommenders-with-values-developing-recommendation-engines-in-a-public-service-organization
  - https://research.atspotify.com/publications/explore-exploit-explain-personalizing-explainable-recommendations-with-bandits
  - https://arxiv.org/abs/1902.10730
---

# WR2 metrics-driven editorial loop — feeding IG engagement into topic selection without a filter bubble

**Date**: 2026-07-17 · **Domain**: marketing · **Author**: deep-researcher (Antonello/Bali Zero) · **Status**: draft · **Sprint**: R (WR2 growth loop)

## Question

How should measured Instagram engagement feed back into WR2 *topic selection* — into `scripts/wr2_topic_selector.py::score_item()` (line 123) — WITHOUT overfitting to vanity metrics or building a filter bubble that starves regulatory-important-but-low-engagement topics?

## TL;DR

- Engagement must enter `score_item()` as a **bounded per-domain tie-breaker** (`perf_score`, cap ±10 pts), never as a ranking driver — because one core regulatory keyword (kitas=25, visa=20) already outweighs the full engagement swing.
- Filter-bubble defence is three explicit mechanisms in the term itself: an **importance floor** (duty domains clamp to `[0,+cap]` — engagement can only add, never demote), an **explore budget** (~15% of days ignore engagement), and **decay** (60-day half-life so old winners don't ossify).
- The signal is read at **domain aggregate** only, from an index the `wr2-ig-metrics-analyst` already computes (per-domain mean/median deviation) — no per-item, no per-client, no `ig_media_id` in the selector.

## Ground truth (verified on disk this session)

- `scripts/wr2_topic_selector.py::score_item()` returns `total = fresh_score + kw_score + tier_score + live_bonus - routine_penalty` (line 178). No engagement term. `fresh_score` 0–30, `tier_score` 5/15/30, `live_bonus` 0–50, `routine_penalty` 0/20; `kw_score` is the sum of `BZ_KEYWORDS` weights (line 41), where core regulatory hits are large: `investor kitas`=30, `kitas`/`kbli`/`kitap`=25, `visa`/`imigrasi`/`npwp`/`pma`=20, `tax`=12, `bpjs`=10. `SCORE_THRESHOLD`=40.
- `.claude/agents/wr2-ig-metrics-analyst.md` Step 2 already computes **mean/median engagement per domain bucket and flags >50% deviation** as under/outperforming, on a 30–90d window, with an N≥5 / effect≥30% discipline. It currently emits only prose amendments to `~/.claude/skills/bali-zero-brand/_proposed-amendments/<date>-ig-insights.md`.
- THE GAP: that per-domain aggregate never reaches `score_item()`. Topic selection is blind to past performance; the analyst tunes voice/layout, not *which domains get picked*.

## Findings — what SOTA content/recsys practice does

### 1. Explore–exploit (bandits) is the canonical frame, but news is non-stationary
Spotify's production system (McInerney et al., RecSys 2018) frames the loop as two forces: **exploitation** "recommends content ... with the highest predicted user engagement", **exploration** "recommends content with uncertain predicted user engagement for the purpose of gathering more information" — and bandits exist to "balance exploration with exploitation to deal with uncertainty", with measured live-traffic gains ([Spotify Research](https://research.atspotify.com/publications/explore-exploit-explain-personalizing-explainable-recommendations-with-bandits)). The standard mechanisms are ε-greedy (pick random with probability ε, else greedy) and UCB (add an uncertainty bonus so rarely-shown arms get explored). Critically, news relevance is **non-stationary** — relevance shifts with breaking events — so any engagement estimate must decay, or it fossilises last quarter's winners.

### 2. Engagement-only retraining provably amplifies popularity bias and kills diversity
Mansoury et al. (CIKM 2020) formalise the degenerate loop: recommend popular → users interact → interactions re-enter training → popularity is further amplified; they give the per-iteration amplification `K·θt/(|Dt|+K)` and show **aggregate diversity (catalog coverage) steadily declines across every algorithm tested** ([ar5iv 2007.13019](https://ar5iv.labs.arxiv.org/html/2007.13019)). Jiang et al. (2019) name the two failure modes and "offer practical solutions to slow down system degeneracy", disentangling the echo chamber from the filter-bubble effect ([arXiv 1902.10730](https://arxiv.org/abs/1902.10730)). The lesson for WR2: an engagement term with no floor and no exploration will, over months, starve low-engagement regulatory domains — the exact editorial failure to avoid.

### 3. Public-service editors solve duty-vs-engagement with post-ranking floors, not by ranking on clicks
BBC R&D's "Recommenders With Values" describes the concrete pattern: editors "stress test the recommender" with flagged important content, then **"re-rank or subset candidate items" and "apply business rules which may filter out undesired content"**, iterating until quality scores clear a threshold — engagement (CTR) is measured *after*, never the sole objective ([Knight Columbia / BBC](https://knightcolumbia.org/content/recommenders-with-values-developing-recommendation-engines-in-a-public-service-organization)). The public-service literature (BBC/NRK/RTBF) treats exploration and serendipity as an editorial *value*: surface content citizens would not otherwise reach, i.e. importance is a first-class term, engagement a secondary re-ranker. This maps directly onto WR2: `kw_score`/`tier_score`/`live_bonus` are the importance layer; engagement should only re-order *within* it.

## §Recommendation (concrete, wired)

Add ONE new bounded term to `score_item()`: **`perf_score`**, a per-domain engagement adjustment.

**Shape.** `total = fresh_score + kw_score + tier_score + live_bonus - routine_penalty + perf_score`, with `perf_score ∈ [-PERF_MAX_POINTS, +PERF_MAX_POINTS]`, `PERF_MAX_POINTS = 10.0`. The cap is deliberately ≤ the smallest core regulatory keyword weight (`bpjs`=10; `tax`=12; `visa`=20; `kitas`=25). Consequence, provable from the score arithmetic above: **a single core regulatory keyword hit outweighs the entire engagement swing**, so engagement can re-order items that are near-tied on importance but can never lift a low-relevance lifestyle item above a genuine visa/tax item. It is a tie-breaker by construction, not a driver.

**How it reads engagement (aggregate only, no PII).** The `wr2-ig-metrics-analyst` already computes per-domain deviation; extend its Step 4 to also emit a small machine-readable index it already has the numbers for:
`~/.claude/skills/bali-zero-brand/_domain-engagement-index.json`
```json
{ "generated_at": "2026-07-17T06:00:00Z", "half_life_days": 60,
  "metric": "saves_plus_shares_per_reach_zscore",
  "domains": { "visa": {"index": 0.4, "n": 22}, "tax": {"index": -0.1, "n": 14},
               "property": {"index": 0.9, "n": 9}, "generic": {"index": -0.6, "n": 31} } }
```
`index ∈ [-1,+1]` is a **decayed** (60-day half-life) z-score of **saves+shares per reach** — intent signals, NOT reach/impressions/likes (the vanity-metric guard: reach is attention, saves/shares are value). `score_item()` maps the item to its dominant `BZ_KEYWORDS` bucket (visa / tax / property / generic — already grouped in the code comments), looks up that domain, and computes `perf_score = clamp(index,-1,1) * PERF_MAX_POINTS`. The selector reads the JSON best-effort and defaults `perf_score=0` if the file is missing or older than 14 days (same graceful-degrade + staleness discipline as the existing freshness cutoff and `wr2_grounding` block).

**How it avoids the filter bubble — three mechanisms, all inside the term:**
1. **Importance floor (hard).** `REGULATORY_DOMAINS = {"visa","tax"}` (duty domains) clamp `perf_score` to `[0, +cap]` — engagement may only *add* to a regulatory topic, never subtract. A low-engagement KEP/PMK change is therefore never demoted for being unpopular. Only property/generic can receive a negative `perf_score`.
2. **Explore budget (ε-greedy, deterministic per-day).** On ~15% of days (`PERF_EXPLORE_EPSILON=0.15`, selected via `sha1(run_date)%100 < 15` so same-day reruns stay idempotent), `perf_score=0` for all items — the ranking runs blind to engagement, keeping under-favoured domains in rotation. Additionally, any domain with `n < PERF_MIN_SAMPLES` (5, matching the analyst's own N-gate) gets `perf_score=0`: bandit "optimism under uncertainty" — you never penalise a domain you have not measured.
3. **Decay.** The index is a 60-day half-life rolling z-score, so a domain that won six months ago fades to neutral; no permanent winners, matching the non-stationarity of news.

**Expected effect.** Adopt the ±10 `perf_score` tie-breaker for the *ordering of candidates already above `SCORE_THRESHOLD` and already deduped*; expected outcome: a modest lift in property/lifestyle carousels' share of published output (roughly 1 slot in 7, bounded by the explore budget) with **zero displacement of breaking/live regulatory items**, because `live_bonus` (0–50) plus core keywords dominate the ±10 band.

**Smallest first experiment (shadow mode, operator-gated).** Compute `perf_score` and log it in `detail["rules"]["perf_score"]` for **4 weeks WITHOUT adding it to `total`**. Each day, record the counterfactual: would the top pick change if `perf_score` were live, and would any `liveness_tier ∈ {breaking,developing}` item ever be displaced (must be 0)? After 4 weeks, review the audit; only on explicit operator GO (Legge 5) flip the term into `total`. Generator ≠ grader: the analyst proposes the index, a session verifies the shadow audit, the human approves the wiring.

## Checklist for action
- [ ] Extend `wr2-ig-metrics-analyst` Step 4 to emit `_domain-engagement-index.json` (metric = decayed saves+shares/reach z-score, per domain, with `n`).
- [ ] Add `perf_score` (cap ±10, importance floor, ε=0.15 explore, N≥5 gate, 14-day staleness) to `score_item()` in **shadow mode** — logged in `score_detail`, NOT summed into `total`.
- [ ] Run the 4-week shadow audit; confirm zero displacement of breaking/developing items before proposing the live wiring.
- [ ] Operator GO (Legge 5) required before `perf_score` enters `total`. Never autonomous.

## §Risks / what could go wrong
- **Vanity-metric capture.** Reach/impressions reward clickbait, not value. Mitigation: index is built on saves+shares (intent), never reach/likes; this is a hard part of the metric definition, not a tuning knob.
- **Degenerate feedback loop.** Boosting a domain feeds it more carousels → more data → more boost (Mansoury's amplification). Mitigation: explore budget zeroes engagement ~15% of days; under-measured domains never penalised; 60-day decay prevents ossification.
- **Regulatory starvation.** The core failure the sprint forbids. Mitigation: duty-domain clamp `[0,+cap]` + cap ≤ smallest reg keyword makes demotion of a visa/tax item by engagement arithmetically impossible.
- **Domain mislabelling.** Coarse keyword→bucket mapping (a visa piece mentioning "villa"). Mitigation: use the *dominant* (max-weight) keyword bucket; the ±10 cap bounds the cost of any misattribution.
- **Analyst output poisoning / PII leak.** Mitigation: selector whitelists only `{index, n}` per domain and rejects any `ig_media_id`/per-client field; index is domain-aggregate by construction (SYMBIOSIS Law 2 / UU PDP).
- **Stale index ossifies old winners** if the weekly analyst dies. Mitigation: 14-day staleness cutoff → `perf_score=0`, mirroring the existing `MAX_ARTICLE_AGE_HOURS` policy.
- **Autonomy overreach (Legge 5).** The term only re-orders candidates already past threshold and dedup; it never lowers the threshold, never bypasses the age/live filters, never publishes. Shadow-first + operator GO enforced.

## Sources
1. [Feedback Loop and Bias Amplification in Recommender Systems](https://ar5iv.labs.arxiv.org/html/2007.13019) — Mansoury et al., CIKM 2020 (fetched 2026-07-17). Popularity-amplification formula + measured decline in aggregate diversity/catalog coverage.
2. [Recommenders With Values: Developing recommendation engines in a public service organization](https://knightcolumbia.org/content/recommenders-with-values-developing-recommendation-engines-in-a-public-service-organization) — BBC R&D / Knight First Amendment Institute (fetched 2026-07-17). Stress-test, business-rule re-rank/subset, editorial threshold, engagement measured after not optimised.
3. [Explore, Exploit, Explain: Personalizing Explainable Recommendations with Bandits](https://research.atspotify.com/publications/explore-exploit-explain-personalizing-explainable-recommendations-with-bandits) — McInerney et al., Spotify, RecSys 2018 (fetched 2026-07-17). Exploitation vs exploration definitions; bandits balance uncertainty; live-traffic engagement gains.
4. [Degenerate Feedback Loops in Recommender Systems](https://arxiv.org/abs/1902.10730) — Jiang et al., AIES 2019 (abstract fetched 2026-07-17). Disentangles echo chamber vs filter bubble; practical solutions to slow degeneracy.

Further reference (canonical UCB-for-news, not quoted): Li et al., "A Contextual-Bandit Approach to Personalized News Article Recommendation", WWW 2010 (arXiv 1003.0146).

## Grader verification (session, 2026-07-18)
Independently verified before capture (generator≠grader, Fable final gate): (1) the crux arithmetic — `scripts/wr2_topic_selector.py:178` `total = fresh_score + kw_score + tier_score + live_bonus - routine_penalty` and the `BZ_KEYWORDS` weights (`investor kitas`=30; `kitas`/`kbli`/`kitap`=25; `visa`/`imigrasi`/`npwp`/`pma`=20; `tax`=12; `bpjs`=10) confirmed byte-for-byte on disk — so the "±10 cap ≤ smallest core-regulatory weight ⇒ a visa/tax item is arithmetically never demoted" guarantee genuinely holds; (2) sources 1 (Mansoury et al., CIKM'20 — per-iteration amplification formula `K·θ^t/(|D^t|+K)` + aggregate-diversity decline) and 3 (BBC/Knight — editorial stress-test + business-rule re-rank/subset, engagement/CTR measured post-live) were fetched this session and confirmed to state what is cited. **Implementation refinement (not a research flaw):** the importance-floor's `REGULATORY_DOMAINS` must map to the code's existing "tax/company" keyword *group* (`kbli`/`pma`/`npwp`/`nik`/`pajak`/`bpjs`), NOT the literal string `"tax"` — otherwise a `kbli`/`pma` item could receive a negative `perf_score`. Fold this into the shadow-mode wiring.
