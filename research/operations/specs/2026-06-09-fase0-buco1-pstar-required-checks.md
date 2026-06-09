---
date: 2026-06-09
domain: operations
client_case: none
sources:
  - W69 cicatrix (.claude/rules/cicatrix-scars.md)
  - gh api repos/Balizero1987/Teman2/branches/main/protection/required_status_checks (live read 2026-06-09)
  - .github/workflows/verify-the-verifiers.yml, p1s2-mutation-incremental.yml
  - .github/CODEOWNERS
---

# FASE-0 BUCO #1 — make the P* workflows required-status-checks (sequenced, NOT executed)

> **Status: NOT EXECUTED this session — deliberately deferred.** Closing BUCO #1
> autonomously is blocked by two structural gates (below). This spec captures the
> empirical ground truth + the exact safe sequence so the next executor (operator
> or a follow-up session WITH Antonello's CODEOWNERS approval) can run it without
> tripping the pending-forever trap.

## Why it could not be done autonomously this session

1. **CODEOWNERS TIER-1 anti-injection** — `/.github/workflows/ @Balizero1987`
   (`.github/CODEOWNERS:27`). Every edit to a workflow file (needed for the
   skip→success sentinel) requires Antonello's review; it is NOT self-mergeable
   by an agent, by design. `verify-the-verifiers.yml` is additionally
   tamper-evident (sha256 `.github/verify-the-verifiers.sha256` + the workflow
   lists itself in its own `paths:`).
2. **The PUT must come AFTER the sentinel is on `main` + green-stable** (W69
   trap #1). The sentinel-workflow edits must be merged + observed reporting
   `success` on a path-miss PR BEFORE any `required_status_checks` PUT. That
   merge + multi-run confirmation cannot complete inside one session.

Doing the PUT before the sentinel is on main = the exact pending-forever trap
(`verify-the-verifiers` / `p1s2` are `paths:`-filtered → they do not run on a PR
that does not touch their paths → a required check that never runs blocks EVERY
such PR). Confirmed live: PR #1199 does NOT trigger `verify-the-verifiers` (its
paths are untouched) — had it been required, #1199 would be stuck pending.

## Empirical ground truth (live 2026-06-09)

**Current required_status_checks (strict=true) — PRESERVE ALL 9 in any PUT:**
```
E2E Tests (Playwright)
MCP Server Tests
Detect Secrets
Backend Tests (Python)
Bandit Python Security
CodeQL Analysis (python)
CodeQL Analysis (javascript)
root-guard
Frontend Tests (Next.js) (mouth, true)
```

**Green-stability of the 2 candidates on main:**
- `verify-the-verifiers.yml` — 5/5 `success` (last 2026-06-07). ✅ stable.
- `p1s2-mutation-incremental.yml` — `success` (2026-06-07). ✅ stable.
- NOT candidates (W69): `p6-federation-parallelize` (FAILURE on main),
  `p7`/`p8`/`p3`/`hot-zone` (NO-RUNS). Do NOT make these required yet.

**Both candidates are `pull_request: paths:`-filtered** → the trap applies to both.

## Step 1 — skip→success sentinel (separate the TRIGGER from the WORK)

For EACH of the 2 candidate workflows, change the top-level trigger so the
workflow ALWAYS runs on `pull_request`, and gate the expensive WORK on a
path-check step. The job NAME (= the required-check context) stays identical, and
a path-miss PR still ends the job `success`.

Pattern (apply to `verify-the-verifiers.yml` and `p1s2-mutation-incremental.yml`):
```yaml
on:
  pull_request:            # NO top-level paths: — always trigger
  push:
    branches: [main]
    paths: [ ...keep the existing push paths... ]

jobs:
  verify-the-verifiers:    # ← keep the SAME job name (= the required context)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with: { fetch-depth: 0 }
      - name: Did relevant paths change?
        id: relevant
        run: |
          base="${{ github.event.pull_request.base.sha }}"
          if git diff --name-only "$base"...HEAD | grep -qE \
            '^(scripts/verify_the_verifiers\.py|scripts/verify_the_verifiers_gates\.yaml|\.github/verify-the-verifiers\.sha256|\.github/workflows/verify-the-verifiers\.yml|\.github/workflows/hot-zone-pr-gate\.yml|scripts/tests/test_verify_the_verifiers\.py)$'; then
            echo "run=true"  >> "$GITHUB_OUTPUT"
          else
            echo "run=false" >> "$GITHUB_OUTPUT"
            echo "::notice::no relevant paths changed — sentinel success"
          fi
      # every real step below gains:  if: steps.relevant.outputs.run == 'true'
```
Notes:
- `verify-the-verifiers.yml` is tamper-evident — this edit needs Antonello's
  CODEOWNERS review AND must not alter the protected `.py`/sha256 (it doesn't;
  only the workflow YAML changes). Confirm the sha256 step still passes.
- Prefer the explicit `git diff` gate over `dorny/paths-filter` to avoid adding a
  third-party action to a TIER-1 anti-injection file.

## Step 2 — merge + confirm green-stable on main

After Antonello approves + the sentinel PR merges:
```
gh run list --workflow verify-the-verifiers.yml --branch main -L 5 --json conclusion
gh run list --workflow p1s2-mutation-incremental.yml --branch main -L 5 --json conclusion
```
Then open a throwaway markdown-only PR and confirm BOTH checks report `success`
(NOT skipped, NOT pending) on it. Only proceed if so.

## Step 3 — PUT required (preserve the 9, ADD the 2)

Get the EXACT check-context names first (job display names) from a recent PR's
check list — likely `verify-the-verifiers` and the p1s2 job name. Then:
```
# READ current, then PUT current+2 (NEVER overwrite blindly):
gh api repos/Balizero1987/Teman2/branches/main/protection/required_status_checks \
  > /tmp/req.json
python3 - <<'PY'
import json
d=json.load(open('/tmp/req.json'))
ctx=set(d['contexts'])
ctx.update(['verify-the-verifiers','<exact p1s2 context name>'])
json.dump({'strict':d['strict'],'contexts':sorted(ctx)}, open('/tmp/req-new.json','w'))
PY
gh api -X PUT repos/Balizero1987/Teman2/branches/main/protection/required_status_checks \
  --input /tmp/req-new.json
```

## Step 4 — GATE (falsifiable) + rollback

Open a markdown-only canary PR. It MUST NOT be stuck pending-forever; both new
checks must report `success` (sentinel path-miss). If it hangs pending → the
sentinel did not take → **ROLLBACK immediately**:
```
gh api -X PUT repos/Balizero1987/Teman2/branches/main/protection/required_status_checks \
  --input /tmp/req.json   # the original 9-context snapshot
```
The PUT is fully reversible in one command; the blast radius (PRs can't merge)
is caught by the canary and undone by the rollback.

## Out of scope (still)
p6/p7/p8/p3/hot-zone are NOT required-safe (failing or never-run). Re-evaluate
each only after it is green-stable on main with its own sentinel.
