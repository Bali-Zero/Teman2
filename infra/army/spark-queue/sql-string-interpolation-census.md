# SQL string-interpolation census: query construction by f-string/concat in the backend, risk-ranked

Read-only analysis — no plan to edit/commit/push anything.

Search `apps/backend-rag/backend` (and any other Python app under `apps/`
that talks to Postgres) for SQL queries built by f-string, `%`-format,
`.format()`, or string concatenation instead of parameterized `$1`-style
placeholders (asyncpg) / bound parameters.

For each hit:

- file:line | the interpolated fragment (truncated ~80 chars)
- what the interpolated value is (a column/table name chosen from a fixed
  internal set? a limit/offset integer? free text from a request?)
- verdict: SAFE-BY-CONSTRUCTION (identifier from a hardcoded whitelist,
  int-cast), FRAGILE (currently safe but one caller change away from
  injection), or UNSAFE (request-derived text reaches the SQL string)

Why: the CRM/RAG backend is client-facing; one UNSAFE site is a data-breach
class defect (UU PDP exposure), and FRAGILE sites are how UNSAFE ones are
born. Golden Rule #9: verify against actual code, never presume the ORM
covers everything.

Output a markdown table sorted UNSAFE → FRAGILE → SAFE (SAFE may be counted
rather than listed if numerous — state the count). N of M, never a silent
cap.
