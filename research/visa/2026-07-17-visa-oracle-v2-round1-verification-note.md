---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 1 (lane: fable-orchestrator-verification)
status: round-1 raw lane output, faithfully preserved
---

# Round 1 — Orchestrator verification note (Fable, on-disk spot-checks 2026-07-17)
Codex red-team P0 claims spot-checked against the live checkout, CONFIRMED:
1. `apps/backend-rag/backend/services/visa_check/match_tree.py` — literal line `del nationality  # reserved for future visa-waiver rules`: the deterministic matcher collects then DISCARDS nationality. CONFIRMED verbatim.
2. `apps/backend-rag/backend/app/routers/visa_oracle.py` (~line 699) — comment: "If the user mentioned an obsolete code, DON'T ABSTAIN even with weak scores. We have enough pretraining context + SYSTEM_PROMPT rules..." → ABSTAIN promoted to CAUTIOUS on LLM pretraining grounds. CONFIRMED (scoped to obsolete-code mentions, narrower than the generic claim but the mechanism is real).
3. `apps/backend-rag/backend/services/visa_check/pricing_bridge.py` — `_SEARCH_HINTS` maps VisaType codes to substrings "likely to appear in the price JSON keys", with "best-effort" comments. Fuzzy substring pricing CONFIRMED (scar-family #3 flavor: guard-over-match applied to money).
4. `apps/mouth/src/components/visa/ConsentBanner.tsx` — "By continuing, you agree to our Privacy Policy" single-action consent. CONFIRMED.
5. `apps/backend-rag/backend/migrations/migration_080a_visa_oracle_sessions.py` — header claims "No PII stored — only ip_hash (SHA-256) and quiz answers" while quiz answers include nationality/family data (UU PDP personal data). CONFIRMED.
Consequence adopted by the panel: the rebuild is NOT aesthetics-only — the deterministic core must be rebuilt (Codex launch-gates 0-4) for the "content impeccabile" goal to be honest. Product contract reframed: "zero wrong answers" → "zero unsupported recommendations".
