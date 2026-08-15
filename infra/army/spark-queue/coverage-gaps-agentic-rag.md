# coverage-gaps: agentic RAG test gaps

Read-only analysis. Look at `apps/backend-rag/backend/services/rag/agentic/`
in this repository (do NOT edit anything — analysis only) and propose the
10 missing tests with the highest value-per-test, ranked.

For each of the 10, give:

- exact `file:line` of the function/branch/condition that is under-tested
  or untested
- the concrete failure scenario the missing test would catch (inputs/state
  → wrong output or crash), not a generic "add a test for X"
- why it ranks where it does relative to the others (e.g. "this branch
  silently swallows an exception and nothing catches a regression")

Prefer branches that are load-bearing for correctness (abstain-policy
thresholds, evidence scoring, subgraph routing) over pure plumbing. If the
directory has existing test files, read them first so you don't propose a
test that already exists under a different name.

Output as a markdown table: rank | file:line | scenario | why it matters.
