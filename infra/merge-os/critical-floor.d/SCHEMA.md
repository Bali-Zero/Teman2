# critical-floor.d/ — the POSITIVE never-quarantine manifest (Merge-OS v3, step 6 slice 1)

Spec: same disposition as `infra/merge-os/quarantine.d/SCHEMA.md` (Codex F6,
`research/operations/2026-08-14-merge-os-v3-research-council.md` §5/§6 step
6). The critical floor is **never the complement of an unused marker** — it
is its own positive, populated, verified manifest. A test category earns a
place here by being enumerated and pattern-matched against the REAL tree in
this PR, not by inheriting from whatever the `critical` pytest marker would
have covered (it covers nothing — that is the defect this replaces).

## One YAML file per category

`infra/merge-os/critical-floor.d/<slug>.yaml`, one category per file, same
W109b rationale as the quarantine directory: independent categories should
be independently addable/editable without two unrelated PRs colliding on
one shared file.

## Fields

| field                  | type            | meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ---------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`                   | string          | Slug matching the filename (without `.yaml`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `category`             | string          | Human-readable name.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `description`          | string          | What this category protects and why it can never be quarantined.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `patterns`             | list of strings | Each entry is either (a) a `pathlib.Path.glob()`-syntax pattern relative to the repo root (supports `**` for recursive matching), or (b) a literal file path relative to the repo root (no wildcard characters). `scripts/ci/quarantine_lint.py` verifies every pattern/path matches **at least one real file on disk** — a pattern matching zero files is an ORPHAN and FAILs the lint (anti-decorative: a floor category that protects nothing is exactly the same defect as the unused `critical` marker it replaces, just wearing a YAML file instead of a pytest marker). |
| `rationale`            | string          | Why this category is load-bearing enough to never quarantine — usually a one-line pointer to the invariant it guards (CLAUDE.md golden rule, data invariant, etc).                                                                                                                                                                                                                                                                                                                                                                                                             |
| `verified_match_count` | integer         | The number of real files this category's patterns matched **at the time this file was written**, recorded so a future reader can tell "did this shrink to zero without anyone noticing" from the file's own history (`git blame`/`git log` on the count), independent of re-running the linter. This is a snapshot, not re-validated automatically to stay in sync — the linter re-derives the live count on every run and is the actual source of truth; this field is a breadcrumb, not a cache someone should trust over the linter's own verdict.                          |

## Cross-check against quarantine.d/

`scripts/ci/quarantine_lint.py` rejects any quarantine entry (see
`infra/merge-os/quarantine.d/SCHEMA.md`) whose `node_id` file-path matches
any pattern here. The floor always wins.

## Not wired into CI yet

Same declared scope as the quarantine directory: this PR ships the
manifests + the validator + its test corpus. Nothing in `tests.yml` reads
either directory yet — that wiring is a follow-up PR, after the sibling
push:main-removal PR (#4181) lands and one full cycle is observed (Merge-OS
v3 build order step 2's own ordering discipline, applied here too: don't
stack a new dependency on a hot file mid-flight).
