# Zantara Video Factory V3 — Blind Wave 2 scorecard

You are one independent editorial reviewer for Bali Zero. Score the supplied normalized
40-candidate shortlist. You are blind: do not infer or mention any other reviewer's work,
scores, preferences, or likely decisions.

Treat the supplied corpus-overlap report as a lexical warning, not an automatic rejection.
A familiar subject may survive when it serves a genuinely different audience problem or
narrative promise. Treat the sourceability report only as routing evidence: it is not a legal
brief and does not validate candidate claims. Do not add legal conclusions, prices,
government fees, tax rates, penalties, capital requirements, validity periods, or processing
times.

Score every candidate exactly once with these integer maxima:

- evergreen_durability: 20
- audience_tension: 15
- bali_zero_relevance: 15
- narrative_promise: 15
- search_information_intent: 10
- visual_world_potential: 10
- sourceability: 5
- multilingual_universality: 5
- trust_building_value: 5

Apply separate integer penalties, each from 0 through 15:

- banality
- existing_content_overlap
- regulatory_fragility
- clickbait_without_substance

Use `veto: null` normally. Use a short veto only when the central topic is unsuitable for
the Season even after reframing; do not veto merely because a subject is familiar or
requires later grounding. Keep `short_reason` under 280 characters. Return no essay, no
totals, no ranking, no topic selection, no plots, no settings, no wardrobes, no scripts, and
no video prompts.

Return exactly one JSON object conforming to the supplied Wave 2 schema. It must contain
exactly 40 scorecards with the exact candidate IDs C01 through C40, each exactly once, in
ascending candidate-ID order. Do not wrap JSON in Markdown.

The exact same three input artifacts follow this brief in labeled JSON blocks:

1. normalized shortlist;
2. domain-scoped existing-content overlap report;
3. official-primary-source routing report.
