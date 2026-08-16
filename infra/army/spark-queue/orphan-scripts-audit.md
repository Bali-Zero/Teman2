# orphan-scripts audit: root scripts/ files nothing invokes, retirement-ranked

Read-only analysis. No plan to edit/commit/push anything — output is a report only.

Why: superscar #2 (esiste ≠ armato) has a mirror image — scripts that exist
and are armed NOWHERE. They cost audit attention on every sweep (W107's
producer census had to reason about files that turned out to be dead), they
rot silently, and some carry copies of logic whose live twin has since been
fixed (family #1 risk if anyone ever re-arms the stale copy).

Scope: every `*.py` and `*.sh` directly under `scripts/` (not recursive into
`scripts/tests/`, `scripts/ci/`, `scripts/lib/`, `scripts/army/` — those have
their own executors). For each file, search for references across:

- `infra/launchagents/*.plist` and `infra/launchagents/wrappers/*`
- `.github/workflows/*.yml`
- every other script under `scripts/` (including tests — a script whose ONLY
  reference is its own test corpus counts as "test-only", a distinct class)
- `docs/runbooks/`, `CLAUDE.md`, `INDEX.md`, skill files under `.claude/skills/`
- `package.json` / `Makefile` / `.husky/` hooks if present

Classify each unreferenced or weakly-referenced file:

- ORPHAN: zero references anywhere outside itself
- TEST-ONLY: referenced only by its own test corpus
- DOC-ONLY: referenced only in prose (runbook/skill/memory), no executor
- LIVE: referenced by an executor (plist/workflow/cron wrapper/another live script)

Output: a markdown table — file | class | references found (file:line, or
"none") | last commit date (git log -1) | one-line retirement recommendation
(retire / keep-as-doc-tool / needs-a-session-decision). Sort ORPHAN first,
then TEST-ONLY, then DOC-ONLY; omit LIVE from the table but report the
total counts per class so coverage is checkable. Do not silently cap — if
you must truncate, state exactly how many rows were dropped and from which
class. Caveat to carry in the report header: absence of a repo reference is
NOT proof nothing invokes the file — HOME crontabs and unc committed plists
on Pro/Mini can invoke repo scripts (family #1); the recommendation column
must say "retire" only for files whose name also fails a case-insensitive
grep against infra/home-fork/declared-pairs.json.
