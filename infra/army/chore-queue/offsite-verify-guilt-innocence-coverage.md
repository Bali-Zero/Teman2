---
id: offsite-verify-guilt-innocence-coverage
title: Add guilt+innocence test coverage for scripts/lib/offsite_verify.sh
seat: haiku
scope: scripts/lib/offsite_verify.sh (read-only, do not edit), scripts/tests/test_offsite_verify.sh (new file)
acceptance: bash scripts/tests/test_offsite_verify.sh
status: pending
---

## Where

`scripts/lib/offsite_verify.sh`, function `verify_offsite_object` (the
whole file — it is a single function, ~46 lines). Verified: no file
anywhere under `scripts/tests/` references `offsite_verify` or
`verify_offsite_object` today (`grep -rn offsite_verify scripts/tests/`
returns nothing).

## What

This function exists (per its own header comment, 2026-07-27 backup
audit) specifically because a prior backup script judged its own success
by "reaching the end of the script" instead of by observing the remote
object — a `fly-pg-backup.sh` night that logged "Uploaded to Tigris" and
exited 0 with NO object actually in the bucket. `verify_offsite_object`
is the fix: it asks the REAL remote listing (`aws s3 ls`) whether the
object is there, and is deliberately NOT a substring match — the header
explicitly calls out `foo.sql.gz` must not be satisfied by
`foo.sql.gz.partial` or `other-foo.sql.gz` (cicatrix-superscar.md family
#3, guard-over-match). None of that documented behavior has a test
proving it actually holds.

Write `scripts/tests/test_offsite_verify.sh` (`#!/bin/bash` — the
function under test uses `local`, needs bash) that `source`s
`scripts/lib/offsite_verify.sh` directly (this file, unlike
`branch_graveyard_cleanup.sh`, is a pure function library with no
top-level executable code — it is safe to source) and stubs the `aws`
CLI with a fake shell function/script placed first on `PATH`, so the test
never makes a real network call. Cover at least:

- **G1 (guilt — must return 1)**: object absent from the listing entirely
  (fake `aws s3 ls` prints a listing with OTHER names, not the one being
  checked).
- **G2 (guilt)**: the anchoring the header promises — a listing containing
  `foo.sql.gz.partial` and `other-foo.sql.gz` but NOT the exact
  `foo.sql.gz` must still return 1 (proves the exact-basename match, not
  substring, per the header's own worked example).
- **G3 (guilt)**: `aws` CLI absent from `PATH` — must return 1 with the
  `"cannot verify, so cannot claim success"` message (line ~46-48), not a
  silent pass.
- **G4 (guilt)**: `aws s3 ls` itself fails (fake binary exits non-zero,
  e.g. simulating an auth/network error) on both attempts — must return 1
  after exhausting its 2-attempt retry (set `OFFSITE_VERIFY_RETRY_SLEEP=0`
  in the test so it does not actually sleep).
- **I1 (innocence)**: the exact basename IS present in the listing among
  other unrelated names — must return 0.
- **I2 (innocence — the retry path)**: fake `aws` fails on the FIRST call
  and succeeds with the right object on the SECOND — must return 0 (proves
  the two-attempt retry is real, not decorative).
- **I3 (innocence — errexit preservation)**: call the function from a
  caller that has `set -e` active BEFORE calling it, with a fixture that
  makes the function's internal `aws` call fail (G1-shaped listing); the
  CALLER must still be alive and able to report the function's return
  code afterward, proving the function's own `case $- in *e*)` /
  `set +e` / restore dance (lines ~40, ~54, ~57) doesn't leak `set -e`
  into a caller that never asked for it, and doesn't kill the caller
  outright.

## Why

This is the same class of defect this repo has already been bitten by
twice on this exact file's OWN motivating incident (silent backup
"success" with nothing actually off-site) — the fix for that incident has
never itself been proven correct by a test. Cicatrix-superscar.md family
#3 (guard-over-match) explicitly requires "nessuna guardia senza test di
innocenza E colpevolezza" for any guard deciding on textual/entity match,
which this function's anchored-basename comparison is one instance of.

## Scope fence

Do NOT edit `scripts/lib/offsite_verify.sh` — this chore is test-coverage
only. Do not touch any caller of this function (e.g. a Postgres backup
wrapper, if one sources it) and do not add a real `aws` CLI dependency —
the fake must be a shell function or a tiny script placed on `PATH`,
never a call to the real AWS/Tigris endpoint. Do not add a `pytest`
dependency; this is a pure-bash test to match the file under test.

## Acceptance

`bash scripts/tests/test_offsite_verify.sh` prints a PASS/FAIL line per
case above and exits 0 only when every case passes; exits non-zero (and
lists which case(s) failed) otherwise. Each case must call
`verify_offsite_object` for real inside the fixture and assert its
returned exit code — no case may pass merely because the fixture never
actually invoked the function under test.
