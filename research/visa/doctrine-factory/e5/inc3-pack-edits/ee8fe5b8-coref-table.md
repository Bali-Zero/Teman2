---
adversarial_review: exempt-generated-artifact # regenerable snapshot emitted by fold_pack.py, not a research deliverable
---

# ee8fe5b8 per-rule co-source coverage — E5 increment 3 seq-9 fold

Assembly decision #5 (2026-08-19-e5-increment3-spec.md): for every RULE
citing `ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2` (general "Izin Tinggal
Keimigrasian" landing page, freshness-2026-08-19.md verdict CHANGED —
the page's "Persyaratan Dokumen" section does not corroborate the 5
facts these rules co-cite it for), drop the co-ref if the rule retains
at least 1 other in-force source; keep it (and declare a residual) if
dropping it would leave the rule with zero sources.

18 rules cited ee8fe5b8 in seq-7. 18 were processed here.
Residuals (rules that would end at zero refs): 0.

| rule_id | other refs remaining | action |
|---|---|---|
| `el.d1-multi-entry-support` | 2 | DROPPED (co-ref removed) |
| `el.d1-passport-validity` | 2 | DROPPED (co-ref removed) |
| `el.d1-funds-usd-2000` | 2 | DROPPED (co-ref removed) |
| `el.d1-cv-required` | 2 | DROPPED (co-ref removed) |
| `el.d1-itinerary-required` | 2 | DROPPED (co-ref removed) |
| `el.d1-support-letter` | 2 | DROPPED (co-ref removed) |
| `el.d2-multi-entry-support` | 2 | DROPPED (co-ref removed) |
| `el.d2-passport-validity` | 2 | DROPPED (co-ref removed) |
| `el.d2-funds-usd-2000` | 2 | DROPPED (co-ref removed) |
| `el.d2-cv-required` | 2 | DROPPED (co-ref removed) |
| `el.d2-itinerary-required` | 2 | DROPPED (co-ref removed) |
| `el.d2-support-letter` | 2 | DROPPED (co-ref removed) |
| `el.d12-multi-entry-support` | 2 | DROPPED (co-ref removed) |
| `el.d12-passport-validity` | 2 | DROPPED (co-ref removed) |
| `el.d12-funds-usd-5000` | 2 | DROPPED (co-ref removed) |
| `el.d12-cv-required` | 2 | DROPPED (co-ref removed) |
| `el.d12-itinerary-required` | 2 | DROPPED (co-ref removed) |
| `el.d12-support-letter` | 2 | DROPPED (co-ref removed) |

## Scope note — products NOT touched

Assembly decision #5 reads "for every rule citing it" — the 3
PRODUCT-level co-refs (D1, D2, D12), which also cite ee8fe5b8
alongside 2 other sources each, are deliberately left untouched by
this fold. This keeps ee8fe5b8 itself referenced in seq-9 (by those
3 products) even though its rule-level ref count drops to 0 — so it
stays in `source_records`, not dropped like 0497cb52. Re-pointing
the D1/D2/D12 product source_refs is a decision the spec's own
Step 4 write-up (freshness-2026-08-19.md) flags as future CP3
scope, not attempted here.

