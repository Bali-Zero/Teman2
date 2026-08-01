---
date: 2026-08-01
domain: operations
client_case: none
adversarial_review: codex
sources:
  - GitHub code scanning alerts (Bali-Zero/Teman2), 262 open high/critical on main
  - 18-agent triage workflow, 9 lanes by rule family, cross-family verify seats
  - live Postgres (nuzantara_readonly) for the schema/coverage measurements
discovered_by: session (M5)
---

# CodeQL: triage of the 262 open high/critical alerts on main

Machine output of the triage run, preserved because a worktree is ephemeral and losing the
reasoning behind 262 verdicts would mean redoing all of it.

## READ THIS BEFORE TRUSTING A `reason` FIELD

**On the 22 overturned entries the `reason` text argues the OPPOSITE of the verdict, and the
refuter's own reasoning was not preserved.** This is a defect in the artifact, found by the
adversarial review of this very report, and it is the single most dangerous thing here: a
reader who opens `RESULT.json`, reads alert #4673's reason — *"Only an 8-character prefix of
the API key is logged … not the full secret"* — and dismisses it, has just silently undone
the overturn that the whole cross-family verify stage exists to produce.

How it happened: each lane's first-pass analyst wrote a verdict + reason. A verify seat then
challenged the FP claims and overturned 22. The merge kept the analyst's **reason** and the
refuter's **verdict**, and dropped the refuter's argument.

The two shapes it takes:

- **SSRF lane (4 entries, `fix_hint` non-empty).** The reason is *correct* as an answer to
  the question CodeQL asked — the host really is a hardcoded literal, so it really is not
  SSRF. The overturn was because a **different** vulnerability sits at that line, and only
  the `fix_hint` names it: *"For the IDOR angle (not this alert): verify file_id belongs to a
  document/client the requesting user is authorized to access."* Those four are #791, #792,
  #2868, #2869 — the IDOR fixed in PR #3496. **The verdict answers "is there a real problem
  here"; the reason answers "is CodeQL's rule violated". They are not the same question.**
- **clear-text-logging (11) + url-substring-sanitization (1): `fix_hint` is EMPTY.** No
  surviving rationale at all. The likeliest reading is that logging a client's own email /
  user_id is a PII exposure under UU PDP even when CodeQL's `(password)` label is wrong — a
  Bali Zero concern CodeQL cannot know about — but **that is inference, not a record.** Treat
  those 12 as *unresolved and needing a fresh first-principles read*, not as adjudicated.
  **→ Now adjudicated; see "Update" below. The inference above turned out to be half right and
  to miss the load-bearing half.**
  <br>**CORRECTION (2026-08-01, later):** an earlier draft said the 12th orphan came from the
  *transport-and-hashing* lane. It does not. Selecting on empty `fix_hint` and joining the
  per-lane files for the rule gives exactly **11 `py/clear-text-logging-sensitive-data` + 1
  `js/incomplete-url-substring-sanitization`** (`apps/mouth/src/lib/security/xss.ts:87`). Both
  lanes show `overturned=1`, so "an exact per-lane match" picked the wrong one of two equally
  plausible candidates — a coincidence read as an identification.

Identifying which 22: the per-lane `overturned` counts below say how many per lane, not which
ones. 12 are identifiable by their self-contradicting reason text plus an empty `fix_hint`.
The other 10 are not individually identifiable from this data.

## Update 2026-08-01, after this artifact was reviewed — the 12 orphans are adjudicated

Appended rather than merged into the body above, so the reviewed record and its correction
stay separately auditable.

**All twelve sit in code that does not execute.** Not "low severity" — *unreachable*:

| n | where | how that was established |
|---|---|---|
| 9 | `app/streaming.py` | no chat-stream route exists in either live process. Deleted in **PR #3499**; CodeQL closed all 9 on the next scan. |
| 2 | `app/services/api_key_auth.py` (S03 auto-migration) | **0** `S03:` lines in a 99-line prod log window, against a positive control of 73 for `zantara.backend` |
| 1 | `apps/mouth/src/lib/security/xss.ts:87` | `getSafeLinkProps` has **zero callers** — only its definition and a barrel re-export |

**Why the overturns had no usable rationale, and what the pipeline was missing.** The refuter
judged the code *as written* and was right on every count: an email really is logged (in
`streaming.py` `user_id = user_email or …`, so the "it's only a session identifier" defence
was false), a key prefix really is logged, the substring check really is incomplete. The
analyst judged *severity*. **Neither asked the third question — does this code run?** On any
scanner backlog, ask reachability BEFORE severity; it is the cheapest filter and it dominates.

**Reachability has one honest instrument: the live route table of EVERY process.** An
importer-count probe written for this pass failed in both directions and was discarded — TS
basename matching over-matched (`page.tsx` → "page" = 919 "importers"), and Python grouped
multi-line imports under-matched, so it reported the fully-registered `admin_zoho_auth` as a
zero-importer dead router. Measured properly against `api` (555 paths) ∪ `rag` (229) = **756**,
**all 7 finding-bearing routers are live**: `intel_scraper` is 100% rag-only, `crm_enhanced` 6
of 8 rag-only, `legal_ingest` 6 of 9. Querying only the `api` table would have declared three
live routers dead. Two related traps in the same pass: building `create_app()` in a throwaway
process reports 6 routes because no lifespan runs, and the `rag` process binds `::`, so an
IPv4 probe's "connection refused" proves nothing.

**Where the numbers stand now** (server-side, `state=open&per_page=100` with `--paginate`):

| | |
|---|---|
| dismissed in the original sweep | 164 |
| dismissed after the fix shipped (the 4 `py/partial-ssrf`, IDOR cured and proven live) | 4 |
| closed by CodeQL itself when `streaming.py` was deleted | 9 |
| **open high/critical now** | **85** = 83 REAL + 2 uncertain |

262 − 164 − 4 − 9 = 85. The 4 SSRF alerts would never have auto-closed: the rule fires on the
URL interpolation, which the fix does not and should not remove — the host is a hardcoded
literal, so *that rule* genuinely does not apply. Left open, the next triage re-derives an
IDOR that is already fixed; each dismissal comment names #3496 and the live result.

**Still not adjudicated:** nothing from the 12. `api_key_auth.py` carries **four** findings:
two are orphans adjudicated above (#4672, #4673, clear-text logging on the dead S03 path); the
other two — **#4669 and #4670, `py/weak-sensitive-data-hashing`** on `hashlib.sha256(api_key…)`
— are untouched here. They are a design question about how keys are stored and compared, and
downstream of the standing recommendation to delete the S03 second door rather than arm it.

### How to re-measure the runtime claims

Everything above that is *not* a repo fact is listed here with the command that produced it —
an artifact asserting runtime state without a way to re-derive it is an assertion, not a
record (raised by the adversarial review below):

```bash
# live route table of BOTH processes (api binds 127.0.0.1, rag binds :: — IPv4 alone lies)
#   inside the container; ADMIN_API_KEY is read from env and never printed
#   api:  flyctl ssh console -a nuzantara-rag --machine <api-machine>  -C "python -"
#   rag:  flyctl ssh console -a nuzantara-rag --machine <rag-machine>  -C "python -"
#   httpx.get("http://127.0.0.1:8080/openapi.json" | "http://[::1]:8080/openapi.json",
#             headers={"X-Debug-Key": os.environ["ADMIN_API_KEY"]})
# open high/critical, server-side filter + pagination (a bare `gh api` returns page 1 only)
gh api --paginate "repos/Bali-Zero/Teman2/code-scanning/alerts?state=open&per_page=100" \
  --jq '.[] | select(.rule.security_severity_level=="high" or .rule.security_severity_level=="critical") | .number' | wc -l
# the S03 path's silence, WITH a positive control beside it
flyctl logs -a nuzantara-rag --no-tail | grep -c 'S03:'            # 0
flyctl logs -a nuzantara-rag --no-tail | grep -c 'zantara.backend' # 73 — the window is alive
gh pr view 3499 --json state,mergedAt
```

Declared limit of that log check: `--no-tail` returned a 99-line window, i.e. *recent* traffic,
not all history. It is consistent with the structural facts (migration 089 never applied,
`api_key_records` absent, no caller passes a `conn`) but on its own it is a sample.

## Totals

| | |
|---|---|
| findings examined | 262 / 262 |
| REAL (final) | **96** |
| — with a surviving rationale | 74 |
| — flagged by an overturn, rationale NOT recorded | 22 |
| safe to dismiss | **164** |
| uncertain | 2 |

96 + 164 + 2 = 262, no overlaps. **`totals.real` in the JSON is `74` — that is the PRE-verify
number**; the `real` array holds 96. 74 + 22 overturns = 96.

The overturn count is the load-bearing number. The first-pass lanes claimed 186 false
positives; cross-family verify seats (GLM on 8 lanes, Codex on 1) rejected 22 of those
claims. **The SSRF lane's analyst called all 11 of its findings false positives; the refuter
overturned 4** — two of which were the IDOR in `documents_proxy`. Same-family agreement
measures transcription fidelity, not truth (W100): never let the lane that produced a verdict
be the only one that grades it.

| lane | examined | real | fp | overturned | verify seat |
|---|---|---|---|---|---|
| clear-text-logging | 70 | 13 | 55 | 11 | glm |
| path-injection | 46 | 26 | 20 | 0 | glm |
| url-substring-sanitization | 38 | 5 | 33 | 1 | glm |
| injection-tail | 25 | 6 | 19 | 1 | glm |
| redos | 23 | 8 | 15 | 4 | codex |
| overly-permissive-file | 22 | 0 | 22 | 0 | glm |
| transport-and-hashing | 14 | 6 | 8 | 1 | glm |
| insecure-randomness | 13 | 10 | 3 | 0 | glm |
| ssrf | 11 | 0 | 11 | 4 | glm |

(The `real` column is each lane's own pre-verify count; the lane totals sum to 262.)

## Files

- `RESULT.json` — `lanes`, `totals` (pre-verify), `real` (96), `safe_to_dismiss` (164, each
  with `number`/`path`/`line`/`reason`), `uncertain` (2). Entries carry `surface` but **not**
  `rule`; join on the alert number against the per-lane files to recover it.
- the nine per-lane files — the alert INPUT per rule family:
  `n`/`rule`/`sev`/`path`/`line`/`msg`/`surface`.

## Disposition of the 164

Dismissed on the GitHub side on 2026-08-01, each with its own reason as the dismissal comment
(`used in tests` where the path is a test, `false positive` otherwise), 164 API calls, every
one checked for a non-zero return individually rather than through a chained `&&`.

Verified from the server afterwards, not from the loop's own claim: open high/critical went
**262 → 98**, counted with a server-side `state=open&per_page=100` filter and `--paginate`.
98 = 96 REAL + 2 uncertain. Dismissals are reversible from the alert page.

Before dismissing, 6 of the 164 were re-probed by hand from the two classes judged riskiest —
3 `url-substring` (all test-file assertions, one of them a test that a security property
HOLDS) and 3 `path-injection` in production (`intel_staging_service.py:168-174`). The
path-injection re-probe enumerated all four call sites of `save_staging_item` independently:
two are FastAPI path params, two receive a server-generated id (`generate_item_id`) or a dedup
record, and the other path component is not concatenated (`get_staging_dir` branches on a
`Literal["visa","news"]`).

**Caveat recorded rather than smoothed over:** the path-param sites are safe because of the
ASGI layer, not because of anything asserted in that function — uvicorn percent-decodes before
routing, so `%2F` yields a 404 instead of an injected separator (confirmed by the review). That
is inherited safety. A shape check on `item_id` before it is interpolated into a path would be
strictly better, and is the same lesson as the `documents_proxy` fix.

## The 96 REAL — full distribution

14 distinct rules, summing to 96 (an earlier draft of this table printed only the top 8 and
summed to 87 — a display cap presented as a distribution, W97):

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
| 3 | `py/weak-sensitive-data-hashing` |
| 2 | `js/xss` |
| 1 | `py/incomplete-url-substring-sanitization` |
| 1 | `py/command-line-injection` |
| 1 | `py/reflective-xss` |
| 1 | `py/redos` |

By surface: 60 backend-prod · 15 frontend-prod · 14 tooling · 7 other.

Densest production files: `app/streaming.py` (9), `services/intel/intel_staging_service.py`
(5), `app/services/api_key_auth.py` (4), `services/intel/intel_cover_handler.py` (4),
`core/parsers.py` (4), `core/legal/structure_parser.py` (4), `app/routers/crm_enhanced.py`
(3), `app/routers/telegram_webhook.py` (3).

## Where to start, and why NOT by count

- **`api_key_auth.py` (4) before `streaming.py` (9).** Nine findings in a streamer are one
  shape repeated — and, checked: **all nine are clear-text-logging of the caller's own email
  or user_id**, seven of them overturns with no recorded rationale. The four on the
  authentication module split 2 + 2: two are prefix-masked key logging (#4672, #4673 — both
  overturns), two are `py/weak-sensitive-data-hashing` on SHA-256 of the API key (#4669,
  #4670), and only the latter pair is a design question about how keys are stored and
  compared. So the real starting point is **two** alerts, not four.
- **The 24 `clear-text-logging` are 13 adjudicated + 11 unresolved overturns.** On an agency
  handling KTP/passport/NPWP this class is UU PDP, not cosmetics — but "REAL" here can also
  mean "logs a field whose NAME looks sensitive", which is the same form-versus-entity trap
  that hid `companies.tax_dept_folder_id` during this run. Read them one by one; do not sweep.

## Closed from this triage

PR #3496 — `documents_proxy` served any Drive file the service account could see to any
authenticated JWT (`db_pool` injected, never queried), plus the twin in
`crm_enhanced._download_drive_file`. See that PR for the fix and for the two gaps it
deliberately leaves open (per-user access, blocked on 17% `assigned_to` coverage; and the
registry being self-authorising for a caller who can write).

## Adversarial review

Seat: **codex** (`gpt-5.6-terra`, high effort), reviewing this report against the JSON beside
it and against the repo. Generator ≠ grader: the session authored both the triage and this
summary, so it cannot be the one to certify them.

Raised 6, of which **4 changed the document** and 2 were partially rejected:

1. **The 96-REAL table summed to 87, not 96** — 6 rule rows missing. CONFIRMED and fixed; the
   cause was `most_common(8)`, a truncated print read as a complete distribution. This is the
   report's own W97.
2. **Entries in `real` whose reason argues they are not real** — CONFIRMED, and on
   re-investigation it is worse and more useful than the reviewer stated: it is not sloppy
   wording but a structural loss, exactly the 22 overturns, proven by an exact per-lane match
   (clear-text-logging overturned=11 ↔ 11 contradictory entries; transport-and-hashing 1 ↔ 1).
   Promoted to the warning at the top of this file.
3. **`totals.real` is 74 while the array is 96** — CONFIRMED, now stated as pre-verify with
   the arithmetic shown.
4. **"`RESULT.json` does not repeat rule and surface" is imprecise** — CONFIRMED, `surface` is
   present on `real` entries; corrected to name only `rule`.
5. **"four distinct questions about who gets in" overclaims `api_key_auth`** — CONFIRMED,
   corrected to 2 + 2 with the split named.
6. **"the 164 were dismissed … not verifiable from the JSON or the repo"** — PARTIALLY
   ACCEPTED. Correct that the artifact carried no evidence; the claim itself holds and the
   evidence has been added (262 → 98 measured server-side, 98 = 96 + 2). Per-alert dismissal
   state lives on GitHub by design, not in this directory.

Not raised by the reviewer and worth stating: it verified the uvicorn `%2F` claim
independently and confirmed the per-file counts, the SSRF sentence, and the partition
arithmetic.

### Second review — the "Update 2026-08-01" section

Seat: **codex** (`gpt-5.6-terra`, medium effort), read-only against the repo. The section is
authored by the same session that did the work it corrects, so it cannot certify itself.

Five claims put up for falsification, **all CONFIRMED**: `streaming.py` absent from `HEAD`
with no surviving reference including router registration · `getSafeLinkProps` has only its
definition and the barrel re-export in `apps/` and `packages/` · 262 − 164 − 4 − 9 = 85 · the
empty-`fix_hint` join yields exactly 11 `py/clear-text-logging-sensitive-data` + 1
`js/incomplete-url-substring-sanitization` (#2144) · #4669/#4670 are
`py/weak-sensitive-data-hashing`.

**One overstatement raised and fixed:** the runtime claims (live route tables, PR #3499, the
CodeQL closure) are not verifiable from the repository — they needed their measurement
attached, not just their result. That is what the "How to re-measure" block above now is. The
reviewer also flagged that "the 2 remaining `api_key_auth.py` findings" read ambiguously when
the file carries four; corrected to name all four and their disposition.
