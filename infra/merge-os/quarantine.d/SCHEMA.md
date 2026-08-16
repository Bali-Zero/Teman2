# quarantine.d/ — the quarantine ALLOWLIST (Merge-OS v3, step 6 slice 1)

Spec: `research/operations/2026-08-14-merge-os-v3-research-council.md` §5 row
"Codex F6 (vacuous critical marker)" + §6 step 6. Disposition: **invert the
polarity**. Today nothing quarantines a test from blocking CI — a test either
passes or it hard-fails the required check. The pytest `critical` marker
registered in `apps/backend-rag/pytest.ini` was meant to be the complement
("everything NOT critical can be quarantined") but is applied to **zero**
tests (verified: `grep -rn "pytest.mark.critical" apps/backend-rag/` → no
hits) — an unused marker is not a barrier, it is the appearance of one
(cicatrix-superscar.md family #2, "esiste != armato").

This directory is the fix: **default-deny**. A flaky/broken test is
blocking-by-default; it is excused from blocking ONLY by an explicit,
time-boxed, owned entry in here — never by the absence of a marker on it.
`scripts/ci/quarantine_lint.py` is the judge (see that file's own docstring
for the full validation contract); this file is the schema it enforces.

**This directory starts EMPTY at this PR** (aside from this schema file) —
no test is quarantined today. Wiring `quarantine_lint.py`'s verdict into
`tests.yml` (i.e. actually skipping/soft-failing a quarantined node_id in
CI) is a declared follow-up PR, not this one (`tests.yml` is a hot file with
a sibling PR #4181 already in the merge queue — built here, armed later;
scar family #2, declared not silently assumed).

## One YAML file per entry — never a monolithic list

Each quarantine grant is its own file, `infra/merge-os/quarantine.d/<slug>.yaml`,
where `<slug>` is a short kebab-case identifier for the quarantined node
(e.g. `backend-tests-flaky-redis-timeout.yaml`). This is deliberate, not
incidental: a single shared file that many unrelated PRs each shrink or grow
independently is exactly the shape of cicatrix-superscar.md's W109b
("two PRs that shrink the same monotone registry are coupled even with zero
shared lines") — two quarantine grants opened the same week, from different
bases, would silently fight each other in a merge. A directory of one-entry
files makes every grant/removal a genuinely independent diff.

## Required fields (every one mandatory — `quarantine_lint.py` FAILs on any entry missing a field, per the mandate: "an exemption wants its own justification, not a free pass")

| field                 | type                | meaning                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `node_id`             | string              | The quarantined unit — either a bare file path (`apps/backend-rag/backend/tests/foo/test_bar.py`) or a pytest node id (`...test_bar.py::test_baz`). The validator matches the file-path portion (everything before the first `::`) against the critical floor.                                                                                                                                                                                   |
| `owner`               | string              | Who is accountable for triaging this — a GitHub login or team handle, never a bare "TBD".                                                                                                                                                                                                                                                                                                                                                        |
| `issue`               | string              | A tracking reference (issue URL, or this repo's own tracking convention) — where the actual fix/triage work is recorded.                                                                                                                                                                                                                                                                                                                         |
| `failure_fingerprint` | string              | A short, stable string identifying THIS failure signature (e.g. a truncated stack-trace hash, or `"asyncpg.InterfaceError: connection was closed"`) — distinguishes "same known flake, still happening" from "a NEW failure landed on an already-quarantined test", which must not hide silently behind an old grant.                                                                                                                            |
| `first_seen`          | date (`YYYY-MM-DD`) | When this quarantine was granted. Must not be in the future.                                                                                                                                                                                                                                                                                                                                                                                     |
| `expires_at`          | date (`YYYY-MM-DD`) | Hard cap: **at most 14 days after `first_seen`**. `quarantine_lint.py` FAILs the entry both if the 14-day cap is violated at grant time AND if `expires_at` has already passed as of the lint run ("expired quarantine = test goes back to blocking" — an expired grant is not read as "still excused", it is read as a violation, because the alternative is a quarantine that renews itself by nobody ever running the linter on a quiet day). |
| `sample_size`         | integer ≥ 1         | How many observed runs the flake-rate estimate below is based on.                                                                                                                                                                                                                                                                                                                                                                                |
| `observed_flake_rate` | number, `0.0`–`1.0` | Measured failure rate over `sample_size` runs — never a guess; if you don't have the number yet, you don't have grounds for a quarantine yet.                                                                                                                                                                                                                                                                                                    |
| `reason`              | string              | Free-text: what's actually going on, in enough detail that the next reader doesn't have to reconstruct it from the fingerprint alone.                                                                                                                                                                                                                                                                                                            |

## The other half of the contract: the critical floor

A `node_id` may **never** be quarantined if it (or the file it belongs to)
matches any pattern in `infra/merge-os/critical-floor.d/` — see that
directory's own `SCHEMA.md`. `quarantine_lint.py` cross-checks every
quarantine entry against every floor pattern and FAILs the entry if it
collides — the floor wins even if someone opens a technically well-formed
quarantine grant against it.

## Example entry (illustrative only — not a real grant; this repo has none at this PR)

```yaml
# infra/merge-os/quarantine.d/example-backend-tests-redis-timeout.yaml
node_id: apps/backend-rag/backend/tests/services/cache/test_semantic_cache_ttl.py::test_ttl_expiry_under_load
owner: subhi
issue: https://github.com/Bali-Zero/Teman2/issues/9999
failure_fingerprint: "redis.exceptions.TimeoutError: Timeout reading from socket"
first_seen: "2026-08-14"
expires_at: "2026-08-21"
sample_size: 12
observed_flake_rate: 0.25
reason: >
  Fails ~1-in-4 on the shared CI Redis service container under load;
  reproduces locally only under artificial network latency injection.
  Root cause not yet isolated — tracked in the linked issue. Quarantined
  for one week while a dedicated container health-check is added; NOT
  quarantined indefinitely.
```
