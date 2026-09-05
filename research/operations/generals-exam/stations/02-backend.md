## Station 2 — backend front (`apps/backend-rag`)

Two independent defects. Both are the kind a code reviewer should have caught. Neither has
a failing test today. Fix both, each with a regression test that fails before and passes
after.

### 2a — an authorization gap in E33 case creation

File: `apps/backend-rag/backend/app/routers/e33_cases.py` (`POST /api/e33/cases`), tests in
`backend/tests/routers/test_e33_cases.py`.

The request body carries `client_id` and an optional `practice_id`. Today a caller with
access to client A can create a case for client A that references a practice belonging to
client B — the foreign key proves the practice exists, not that it belongs to the requested
client. Before any insert, when `practice_id` is not null:

- read exactly one thing — the practice's owning client id (`SELECT client_id FROM practices
  WHERE id = $1`, via `conn.fetchval`);
- if it is missing, or differs from `body.client_id`, respond `422` with detail exactly
  `practice is not available for this client` and never call the repository insert;
- when `practice_id` is null or absent, do not perform the lookup at all;
- keep every existing behavior (principal-case access checks, RBAC, FK-violation handling)
  unchanged. The practice can still disappear between the lookup and the insert; the
  existing FK-violation path must still handle that.

### 2b — unescaped customer data in HTML emails

File: `apps/backend-rag/backend/services/garuda_orders/outbox_handlers.py`, tests in
`backend/tests/services/garuda_orders/test_outbox_handlers.py`.

`case_type` (and any other non-constant field) reaches the customer HTML email bodies raw,
interpolated into `<br>`-joined f-strings at render time. Count the HTML bodies, escape at
every site (`html.escape(..., quote=True)`), and do not touch the Telegram staff pages,
which are plain text / Markdown-escaped and out of scope. Do not escape URLs meant for
`href`/`src` — those need validation, not escaping — and do not double-escape anything
already escaped. Add a test that proves a `case_type` containing `<script>` or a `&` is
escaped in every HTML body.

Acceptance: from `apps/backend-rag`, `.venv/bin/python -m pytest
backend/tests/routers/test_e33_cases.py backend/tests/services/garuda_orders/test_outbox_handlers.py`
— your new tests green. Some tests in the outbox file error on this machine because the
test database lacks a table; that is environmental. Say so under UNRUN, with the count,
rather than claiming the file is green.
