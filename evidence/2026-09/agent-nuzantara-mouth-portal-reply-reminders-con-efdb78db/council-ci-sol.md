# Sol council: CI bootstrap cure

Verdict: PASS. No P0/P1 blockers or concrete P2 findings.

Seat codex-gpt-5.6-sol, xhigh; existing native council agent /root/portal_reply_council_sol, follow-up read-only review. Reviewed commit 9f4c3c085e plus the exact 36-line CI-bootstrap delta.

Mechanical normalized DDL comparison returned [true, true, true, true] against legacy migration_031_client_portal.py for the table and all three indexes. Placement after create_all satisfies clients/practices FKs before migration321. Every statement uses IF NOT EXISTS. The actual CI workflow runs bootstrap before apply-all.

Checks executed by this seat: static DDL equivalence and git diff --check. Inspected root's real empty-database reproduction and replay receipt: both pipelines passed, two FKs and three indexes preserved; migration321 unchanged. No pytest or database reproduction rerun by the seat. Local PostgreSQL17.8 differs from CI PostgreSQL15; required CI remains authoritative. No edits, sends, production rows or release actions.
