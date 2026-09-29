# Spec — wa-attention: guard the RESULT, not the SQL spelling (2026-09-29)

Owner: WA-mirror attention lane (conductor-dispatched builder). Due: 2026-10-06.
Discharges: conditions C1-C3 of the fresh gate on PR #7656
(pull/7656#issuecomment-5889013583). Read that comment first; it lists the 10 surviving mutants.

## Why a spec and not another patch

`scripts/wa-mirror-attention-telegram.py` has had three gate rounds in one day
(#7635 → #7652 → #7656). Each round hardened the test that reads the SQL **text**
(first a `full_name` spelling pin, then a rendered-SQL column allow-list). Each round
left survivors of the same family: a value reaches the output through a shape the
text check does not spell out. For example:

- a `#>>` / `->>` JSON path read (vCard, message text);
- the whole `raw_baileys_event` selected under an allowed alias;
- an implicit or lower-case alias.

This is superscar #3: the guard judges a substring, not the entity. Under the
Builder Contract's fix-of-a-fix depth rule, the next round changes the method.

## Method: seed sentinels, assert on what comes back

Use the throwaway real-PG cluster the attention tests already spin up.

1. **Sentinel fixture.** Seed one client and a set of inbound messages. Put a unique,
   obviously fake sentinel string in EVERY name- or content-bearing place that
   exists in production:
   - `clients.full_name`, `clients.company_name` and `clients.email`, plus any other
     text column of `clients` that the schema has at test time. Enumerate these from
     `information_schema`, not from a hand list.
   - In `raw_baileys_event`: `pushName`, `verifiedBizName`, message text/caption
     paths and vCard.
   - Message body columns.
     Sentinels are synthetic, for example `SENTINEL-FULLNAME-7f3a`. No real data.
2. **Result contract per selector.** For `fetch_high_unresolved` and
   `fetch_digest_metrics`, declare the exact result key-set in the test, then assert:
   - the returned key-set equals the contract **exactly**, with no extra keys;
   - no sentinel appears anywhere in any returned value. Walk dicts, lists and JSON
     recursively and stringify scalars.
3. **Rendered output.** Build the realtime and digest Telegram texts from those rows
   through the real composing functions, not re-implementations. Assert that no
   sentinel appears and that the label shape is exactly `client #<id> — <masked>`,
   or masked only for a new lead.
4. **Keep the #7656 rendered-SQL allow-list** as a cheap first layer, but it is no
   longer the guard of record. The result assertions are.

## Backlog and window (C1, C2)

Seed HIGH/MEDIUM, 1:1/group and resolved/unresolved rows at ages 0, 6, 8, 10 and 40
days. Then assert these exact counts:

- the roster contains only the unresolved 1:1 HIGH rows younger than `HIGH_WINDOW_DAYS`;
- `high_backlog` counts only the unresolved 1:1 HIGH rows at or beyond the window.
  Resolved, group and MEDIUM rows at 40 days are excluded, so the C1 fixture is no
  longer vacuous;
- the 6-day and 8-day rows pin the window at 7 (C2 seam). A drift to 30 days, or a
  realtime/digest divergence, turns red.
- "Everything is acknowledged" never prints while `high_backlog > 0`.

## Acceptance

- Tests first: each of the #7656 gate's surviving mutants turns ≥1 new test red. Show
  a table of mutant → red test, using `cp` backup and restore. The accepted
  `HIGH_WINDOW_DAYS` 7→30 survivor is now red too, via the seam rows.
- Production code changes only if a test proves a real leak. The expected diff is
  tests-only. If a leak is found, stop and report before fixing: the output boundary
  is Builder Contract §4.
- The tests run in `check-wa-attention-pii` (real-PG, skip gate). Any new test file
  must match `test_wa_attention_*.py`.
- This spec is committed in the same PR as `docs/specs/2026-09-29-wa-attention-result-guard-spec.md`.

## Out of scope

- Making `check-wa-attention-pii` a required check. That is a branch-protection admin
  action for the owner.
- The classifier's local raw-phone log (F1 of the #7635 gate), which needs an owner ruling.
- Any change to alert cadence, dedup or copy.
