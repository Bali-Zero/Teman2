# Zantara Persona Eval — Golden Corpus

Behavioral golden set for the client-facing WhatsApp persona (and any future
client channel). Born 2026-06-13 from the guard-family scars (W68 → W72 → W73 →
the 2026-06-13 language-gap sweep) and the knowledge-decay audit
(`research/operations/2026-06-13-knowledge-decay-audit-fable5.md`), which found
the systemic gap this corpus fills: **no SSOT of verified regulatory claims**
that every surface (bridge, site, DB, guides) can be diffed against.

## Files

- `golden_corpus.json` — 50 scenarios × 3 languages (en/id/it) = 150 question
  entries across visa / tax / company / property / persona. Every key fact
  carries a traceable `source` and, where load-bearing, the `verified_by`
  audit. Perishable facts carry `valid_until`.
- `validate_corpus.py` — schema + freshness lint.
  - default: schema errors exit 1, freshness warnings printed only
  - `--strict-freshness`: expired/expiring facts also exit 1 (cron path)
- CI binding: `apps/backend-rag/backend/tests/unit/scripts/test_zantara_golden_corpus.py`
  (schema blocking; cross-references guards against the live bridge module and
  the production `_REPLY_GUARD_CHAIN`).

## Expected-behavior classes

| class | meaning |
|---|---|
| `state_directly` | Stable published fact — deflecting to the team is a FAILURE (over-caution, W72) |
| `state_then_team` | Answer the substance, then note the team confirms client-specific application / live window |
| `defer` | Client-specific, live-window, or exact-pricing — deferral IS the correct answer |
| `guarded_canonical` | Wrong answers are clobbered by the named post-LLM guard |

## Maintenance rules

1. **Never add a fact without a source.** An unanchored "golden" fact is
   poisoned ground truth — worse than no entry.
2. **Perishable facts get `valid_until`.** When it expires, re-verify against
   the live source and update (the F11 LKPM time-bomb lesson). Run
   `validate_corpus.py --strict-freshness` weekly (cron + Telegram), not in
   PR-blocking CI.
3. **New guard ⇒ new scenarios.** The GUARD_MATRIX meta-gates already force
   pass/clobber/no_trigger × en/id/it test cases for every new `_guard_*`;
   add the corresponding corpus scenario for the behavior layer.
4. **The corpus describes BEHAVIOR, not phrasing.** `key_facts` are what a
   correct answer must assert; they are not verbatim reply templates.
