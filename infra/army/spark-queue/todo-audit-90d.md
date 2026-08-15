# todo-audit: stale TODO/FIXME in the backend, risk-ranked

Read-only analysis. Search `apps/backend-rag` for `TODO`, `FIXME`, `XXX`,
and `HACK` comments. For each hit, run `git blame` on that line (or the
nearest surrounding block if blame attributes it to a bulk reformat commit)
to find the commit date, and keep only the ones older than 90 days from
today.

For each surviving TODO, classify risk:

- HIGH: touches auth, billing/pricing, PII handling, or a data-invariant
  documented in this repo's CLAUDE.md §9 (embedding model, evidence
  thresholds, KBLI payload shape)
- MEDIUM: touches a code path that runs in production request handling but
  isn't one of the above
- LOW: dead code, test-only, or cosmetic

Output as a markdown table: file:line | TODO text (truncated to ~80 chars)
| age (days) | risk | one-line reason for the risk call. Sort HIGH first.
If you find more than 40 qualifying TODOs, list all of them anyway (do not
silently cap — if you must cap for length, say explicitly how many you
dropped and why).
