# Intel staging fixtures

10 anonymized real-world staging documents for regression testing the
validator pipeline. Distribution:

- 5 valid (gov.id source, resolvable URL, body > 50 chars)
- 3 borderline (non-whitelisted domain OR transient 5xx)
- 2 invalid (malformed URL, empty title)

Generate synthetic docs with `scripts/gen_intel_fixtures.py`
(see apps/bali-intel-scraper) — do NOT include PII.
