# DocSentinel — live derived state without tracked snapshots

`scripts/docs_sync.py` has two deliberately separate responsibilities:

1. `--json` generates current counts and enumerable atlases from the checked-out
   tree and optional live services.
2. `--check` protects small stable pointer blocks in tracked markdown from hand
   edits or malformed markers.

Volatile counts, tables, and inventories are not committed. This prevents a
repository-wide change from making an unrelated pull request fail because a
global snapshot drifted.

## Commands

```bash
# Current machine-readable state; never writes repository files
python3 scripts/docs_sync.py --json

# Validate every protected pointer
python3 scripts/docs_sync.py --check

# CI: validate only managed docs named by the merge-base delta
python3 scripts/docs_sync.py --check --changed-files-from /tmp/changed.txt

# Restore canonical pointer bodies after an accidental hand edit
python3 scripts/docs_sync.py

# Generate the full inventory and JSON files under .artifacts/
bash scripts/docs_inventory_regen.sh
```

The scheduled `docs-inventory-refresh.yml` workflow runs the last command and
publishes `docs-sync.json`, `docs-audit.json`, and `DOCS_INVENTORY.md` as a CI
artifact.

## Protected files

- `README.md` — technical-state pointer
- `INDEX.md` — apps, workflows, skills, and automation pointers
- `docs/AI_ONBOARDING.md` — quick-numbers pointer
- `docs/runbooks/README.md` — runbook-inventory pointer
- `docs/DOCS_INVENTORY.md` — full-inventory pointer

Every expected marker pair must exist exactly once. The body between its start
and end marker must equal the generator's stable template.

## Gate semantics

The required `check-docs-sync` workflow always starts. It enumerates the
merge-base delta and then:

- runs generator correctness tests when the generator or protected surface is
  relevant;
- validates only protected docs changed by the pull request;
- validates the whole protected surface when `scripts/docs_sync.py` itself
  changes;
- returns sentinel success for unrelated changes.

This gives both required properties:

- **guilt:** a hand edit inside a protected marker is red;
- **innocence:** a code change that alters a live count but does not edit a
  protected doc cannot become red from global drift.

## Unavailable live services

`--json` reports an explicit `status: unavailable` with `null` values when
Qdrant or Knowledge Graph credentials are absent. It never promotes a committed
cache or hardcoded historical count to apparently-current state.

## Adding a new protected pointer

Add the marker key to `EXPECTED_MARKERS`, add a stable no-count template to
`TEMPLATES`, add the tracked target to `TARGET_FILES`, and extend the unit
tests. A changing value belongs in JSON or the workflow artifact, not in the
tracked marker body.
