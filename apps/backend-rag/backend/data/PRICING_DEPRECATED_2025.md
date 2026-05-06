# `bali_zero_official_prices_2025.json` — DEPRECATED 2026-05-06

This file is no longer the source of truth for Bali Zero pricing.

The authoritative pricing JSON is now
[`bali_zero_official_prices_2026.json`](./bali_zero_official_prices_2026.json),
loaded by `backend.services.pricing.pricing_service.PricingService` and surfaced
through `PricingTool` (Tool #2).

## Why is the 2025 file still on disk?

It is intentionally kept as a **rollback artefact**: if the 2026 migration
needs to be reverted in production we want the previous JSON one
`git checkout` away. The file MUST NOT be loaded by any production code
path — `git grep "bali_zero_official_prices_2025"` should now only show:

* this README;
* historical migration `migration_066_populate_practice_types_from_pricing.py`
  (immutable history — already ran against the 2025 schema in production);
* `apps/backend-rag/scripts/generate_brochure.py` (one-off brochure
  generator that predates the 2026 schema; out of scope for the migration).

If a new reference to the 2025 file appears anywhere else, that is a bug.

## What changed in 2026?

| Aspect | 2025 | 2026 |
|---|---|---|
| Top-level keys | `services`, `metadata` | `version` (new), `effective_date` (new), `metadata`, `services` |
| Categories | 8 | 9 |
| `urgent_services` | exists | **renamed** `urgent_processing` |
| `visa_extensions` | exists | **dropped** — `C1 Tourism Extension` moved into `single_entry_visas` |
| `tax_accounting` | absent | **NEW** — has 4 sub-blocks (`monthly_tax_basic`, `monthly_tax_bundled`, `annual_basic_packages`, `annual_standalone`), one extra nesting level |
| `consultant_services` | absent | **NEW** — 7 entries (Close PMA, NPWPD, BPJS×2, NPWP Personal, Update Data, EFIN) |
| Service entry shape | `price`, `notes`, `text` (markdown), `duration`, `validity` | adds `name`, `description_en`, `icon_id`, `tier_range` (list of 2 strings or `null`); the `text` field was DROPPED |
| `tier_range` semantics | absent | when non-null, replaces single `price` with a low–high range (e.g. `["1.800.000 IDR", "2.000.000 IDR"]`) |
| Contact metadata | `info@balizero.com` / `+62 813 3805 1876` / `Canggu` | `zero@balizero.com` / `+62 821 31 07 363` / `Kerobokan` / `balizero.com` |
| Total services | ~57 | 98 |

## When can the 2025 file be deleted?

Only after the 2026 file has been live in production for at least a few
weeks without a forced rollback. Deletion is a separate PR; do not bundle
it into a feature commit.

## Migration commit reference

The migration to 2026 ships across these commits on
`feat/email-branding-followup`:

* `feat(pricing-rag): migrate PricingService to 2026 JSON source` —
  PricingService loader / search / formatter, revenue_estimator,
  whatsapp_persona, test fixtures realigned.
* `feat(pricing-mouth): surface 2026 pricing categories in chat renderer` —
  TS types and `PricingTable.tsx` learn `tier_range` and the new categories.
* `docs(pricing): point all references to bali_zero_official_prices_2026.json` —
  CLAUDE.md, DEVELOPER_GUIDE, FEDERATION_OPPORTUNITY_MAP, prepare_payloads,
  inline docstrings.
* `chore(pricing): mark 2025 JSON deprecated, keep file for rollback` —
  this README.
