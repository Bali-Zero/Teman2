---
date: 2026-08-01
domain: operations
client_case: none
sources:
  - GitHub code scanning alerts (Bali-Zero/Teman2), 262 open high/critical on main
  - 18-agent triage workflow, 9 lanes by rule family, cross-family verify seats
  - live Postgres (nuzantara_readonly) for the schema/coverage measurements
discovered_by: session (M5)
---

# CodeQL: triage of the 262 open high/critical alerts on main

Machine output of the triage run, preserved because a worktree is ephemeral and
losing the reasoning behind 262 verdicts would mean redoing all of it.

## Totals

| | |
|---|---|
| findings examined | 262 / 262 |
| REAL | **96** |
| safe to dismiss | **164** |
| uncertain | 2 |
| FP claims **overturned** by an independent verify seat | **22** |

The overturn count is the load-bearing number. The first-pass lanes claimed 186
false positives; cross-family verify seats (GLM on 8 lanes, Codex on 1) rejected
22 of those claims. **The SSRF lane's analyst called all 11 of its findings false
positives; the refuter overturned 4** — and two of those four were the IDOR in
`documents_proxy` fixed in PR #3496. Same-family agreement measures transcription
fidelity, not truth (W100): never let the lane that produced a verdict be the only
one that grades it.

## Files

- `RESULT.json` — merged verdicts: `lanes`, `totals`, `real` (96), `safe_to_dismiss`
  (164, each with `number`/`path`/`line`/`reason`), `uncertain` (2).
- the nine per-lane files — the alert INPUT for each rule family, carrying
  `n`/`rule`/`sev`/`path`/`line`/`msg`/`surface`. Join on the alert number to
  recover a verdict's rule and surface; `RESULT.json` does not repeat them.

## Disposition

The 164 were dismissed on the GitHub side on 2026-08-01, each with its own reason
as the dismissal comment (`used in tests` where the path is a test, `false
positive` otherwise). Dismissals are reversible: reopen from the alert page.

Before dismissing, 6 of the 164 were re-probed by hand from the two classes judged
riskiest — 3 `url-substring` (all test-file assertions, one of them a test that a
security property HOLDS) and 3 `path-injection` in production
(`intel_staging_service.py:168-174`). The path-injection re-probe enumerated all
four call sites of `save_staging_item` independently: two are FastAPI path params,
two receive a server-generated id (`generate_item_id`) or a dedup record, and the
other path component is not concatenated (`get_staging_dir` branches on a
`Literal["visa","news"]`).

**Caveat recorded rather than smoothed over:** the path-param sites are safe
because of the ASGI layer, not because of anything asserted in that function —
uvicorn percent-decodes before routing, so `%2F` produces a 404 instead of an
injected separator. That is inherited safety. A shape check on `item_id` before it
is interpolated into a path would be strictly better, and is the same lesson as
the `documents_proxy` fix.

## The 96 REAL — shape, for whoever picks this up

By surface: 60 backend-prod · 15 frontend-prod · 14 tooling · 7 other.

| n | rule |
|---|---|
| 26 | `py/path-injection` |
| 24 | `py/clear-text-logging-sensitive-data` |
| 11 | `py/polynomial-redos` |
| 10 | `js/insecure-randomness` |
| 5 | `js/incomplete-url-substring-sanitization` |
| 4 | `py/request-without-cert-validation` |
| 4 | `py/partial-ssrf` |
| 3 | `js/command-line-injection` |

Densest production files: `app/streaming.py` (9), `services/intel/intel_staging_service.py`
(5), `app/services/api_key_auth.py` (4), `services/intel/intel_cover_handler.py` (4),
`core/parsers.py` (4), `core/legal/structure_parser.py` (4),
`app/routers/crm_enhanced.py` (3), `app/routers/telegram_webhook.py` (3).

Two notes on ORDER, because the biggest number is not the biggest risk:

- **`api_key_auth.py` (4) before `streaming.py` (9).** Nine findings in a streamer
  are most likely one shape repeated; four on an authentication module are four
  distinct questions about who gets in.
- **The 24 `clear-text-logging` deserve one-by-one reading, not a bulk sweep.** That
  is the class where the verifier overturned the most (11 of the 22), and on an
  agency handling KTP/passport/NPWP it is UU PDP, not cosmetics — but "REAL" there
  can also mean "logs a field whose NAME looks sensitive", which is the same
  form-versus-entity trap that hid `companies.tax_dept_folder_id` during this run.

## Closed from this triage

PR #3496 — `documents_proxy` served any Drive file the service account could see to
any authenticated JWT (`db_pool` injected, never queried), plus the twin in
`crm_enhanced._download_drive_file`. See that PR for the fix and for the two gaps it
deliberately leaves open (per-user access, blocked on a 17% `assigned_to` coverage;
and the registry being self-authorising for a caller who can write).
