---
date: 2026-07-18
domain: marketing
client_case: none (WR2 editorial pipeline internal)
sources:
  - https://pike.psu.edu/publications/ecmlpkdd19.pdf (Evergreen news early detection, ECML-PKDD 2019 / Washington Post)
  - https://www.google.com/intl/en_us/search/howsearchworks/how-news-works/ (Google News ranking signals)
  - https://searchengineland.com/guide/query-deserves-freshness-qdf (QDF)
  - https://arxiv.org/abs/2602.02219 (position bias in rubric-based LLM-as-judge)
  - https://arxiv.org/abs/2604.06996 (self-preference bias in rubric evaluation)
  - https://arxiv.org/pdf/2605.16386 (central tendency bias in ordinal LLM scoring — additive rubrics)
  - https://arxiv.org/pdf/2605.09227 (score clustering / compression, Bayesian de-biasing)
  - https://arxiv.org/abs/2303.16634 (G-Eval)
  - https://www.nyckel.com/blog/llms-for-classification-best-practices-and-benchmarks/ (few-shot classification benchmarks)
  - https://arxiv.org/html/2603.00077v2 (Autorubric)
  - https://arxiv.org/abs/2103.04390 (RevDet event tracking)
  - https://www.gdeltproject.org/ (GDELT corroboration fields)
  - https://arxiv.org/abs/2001.08700 (EventMapper corroborative+probabilistic fusion)
  - https://www.newswhip.com/spike-real-time-media-monitoring/ (social velocity)
  - https://arxiv.org/abs/1711.04068 (Reuters Tracer — 4 orthogonal dimensions)
---

# WR2 liveness scoring redesign — growth-loop sprint R (2026-07-18)

## Question

The WR2 liveness scorer classifies every intel item breaking/developing/evergreen via an
additive LLM rubric. On real data it classifies EVERYTHING evergreen. What does newsroom-grade
SOTA do for news-lifecycle classification, and what should WR2's rewire adopt?

## Internal diagnosis (all file:line re-verified on disk 2026-07-18)

**Measured distribution, last 10 enriched runs on Pro (135 enriched articles):**
124 items score 0 · 11 items score **exactly 30** · 0 items above 30. The 11 at 30 include
objectively-live stories — "15 WNA China dan Vietnam Ditangkap" (dated arrests), "Immigration
Cuts Visa-Free Entry by 87.91%" (official figure), "Empat Marketplace Jadi Pemungut Pajak Mulai
Agustus" (dated policy change). All classified `evergreen`.

**Three legs, two already cured:**

1. **Rubric miscalibration (OPEN — this research's target).**
   `apps/bali-intel-scraper/scripts/claude_cli_enricher.py:71-88`: additive rubric
   (+40 decree-with-date, +30 dated-event, +30 official-figure; AND-gated conditions),
   tier buckets breaking≥80 / developing≥40. In practice a real story fires exactly ONE
   signal → 30 points → below developing=40 → evergreen. The rubric is calibrated for a
   multi-signal sum that essentially never occurs.
2. **Transport break (CURED in PR #2631, sibling growth-loop B1, in flight at time of
   writing).** The 3 liveness fields never left the `enrichment` dict: dropped by the
   pipeline submit payload (`run_intel_pipeline.py`), by the `ScraperSubmission` model, and
   by the `list_pending_items` 9-key projection. #2631 carries them end-to-end with
   validation + tier-derivation + defensive projection.
3. **Selector already correct.** `scripts/wr2_topic_selector.py:506-527`: live pool =
   `liveness_tier ∈ {breaking,developing} AND live_news_score ≥ WR2_LIVE_NEWS_FILTER_MIN`
   (default 40); `WR2_PREFER_LIVE_NEWS=true` IS armed in the live Pro plist (verified).
   Empty pool → graceful evergreen fallback, logged.

**Consequence:** even after #2631 lands, the live pool stays empty — max observed score is 30
and threshold is 40. The plumbing is fixed; the water is still all "evergreen". The scoring
itself is the remaining disease.

## External findings (15 sources, 3 filoni)

**The failure is structural, not a tuning miss.** Additive rubrics mathematically amplify
central-tendency bias: an extreme total requires ALL sub-criteria extreme simultaneously
(arXiv:2605.16386, clinical ordinal audit). Score clustering on round values (our 0-and-30
pattern) is a named, expected LLM-judge pathology reported independently by three papers
(2605.09227 "score clustering/compression", 2602.02219, 2605.16386). Raw 0-100 numeric scores
from LLMs are distrusted in production by ≥3 independent sources unless probability-weighted
(G-Eval) or post-hoc calibrated.

**No newsroom-grade system uses a single LLM scalar as its liveness signal.** Google News:
prominence = multi-source corroboration, freshness contextual, separate signals. QDF: breaking
= correlation of TWO independent streams (publication velocity × search volume). Reuters
Tracer: 4 orthogonal dimensions (newsworthiness/veracity/novelty/scope), never summed.
RevDet/GDELT: corroboration counted at the story-CLUSTER level after dedup — and even then
noisy (~55% field accuracy in GDELT; treat probabilistically).

**Best cost/benefit mitigation across the literature: forced-choice classification with
few-shot calibrated anchors.** Few-shot: 65.0%→77.5% consistency (G-Eval), plateau at ~4
examples/class (Nyckel), 80-87% accuracy with 5-shot calibration (Autorubric). Caveat: CoT is
NOT universally beneficial (Nyckel measured it slightly hurting) — A/B it, don't assume.
Evergreen is a heavily imbalanced class (<1% truly evergreen in the ECML-PKDD corpus): a
three-way forced choice with calibrated anchors is realistic; a finely-graded 0-100 scale is
not.

## LA RACCOMANDAZIONE (una)

**Adotta il forced-choice a 3 tier con anchor few-shot calibrati al posto della rubrica
additiva** (prossimo sprint B, solo `claude_cli_enricher.py` + test — nessuna nuova infra):

- The enricher prompt classifies `liveness_tier` DIRECTLY (forced choice breaking /
  developing / evergreen), guided by 3-4 calibrated anchor examples per tier drawn from OUR
  real corpus (e.g. the 11 known mis-scored stories become developing/breaking anchors;
  routine "How to apply for KITAS" guides stay evergreen anchors).
- `live_news_score` becomes DERIVED from the tier (breaking→90, developing→60, evergreen→10)
  for backward-compat with the selector's `≥40` filter and #2631's persistence contract —
  the score stops pretending to be a measurement.
- `live_news_reasons` unchanged (already load-bearing for the draft generator per #2631).
- Signal definitions from the old rubric (dated decree / dated event / official figure)
  survive as the DESCRIPTION of what makes a story developing/breaking — they inform the
  choice, they no longer gate a sum.

**Atteso (falsifiabile):** replaying the 11 known single-signal stories through the new
prompt classifies ≥8 as developing-or-breaking (guilt), while a set of 10 routine guides
stays 10/10 evergreen (innocence). In production: first non-empty live pool within a week of
deploy (probe: topic-selector log line "using live pool (N items)" with N≥1 on a real news
day).

**Esplicitamente rimandato (non in questa cura):** multi-source corroboration / velocity
signals (opzione C/D — the SOTA end-state, MEDIUM-HIGH cost: needs cluster-level dedup à la
RevDet first; revisit only if forced-choice alone proves insufficient after 2-4 weeks of
measured tiers). Bayesian post-hoc calibration (needs labeled history we don't have yet —
the new tier stream will CREATE that history).

## Follow-up chain

1. Sprint B (next): implement forced-choice enricher prompt + anchors + guilt/innocence
   replay tests. Depends on #2631 (merged) for the transport.
2. After 2-4 weeks of live tiers: measure precision on the live pool (how many "developing"
   picks were actually timely?) via the WR2 IG metrics loop; decide whether corroboration
   signals (opzione C) are worth the pipeline cost.
