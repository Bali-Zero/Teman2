# swallowed-exceptions census: overly-permissive except blocks in the backend, risk-ranked

Read-only analysis — no plan to edit/commit/push anything.

Search `apps/backend-rag/backend` for exception handlers that can swallow real
failures silently: `except Exception:` / bare `except:` / `except ... pass` /
`except ... continue` / handlers whose only body is a `logger.debug`. For each
hit, read enough surrounding context to say what failure class it can hide.

Why (scar family #2, cicatrix-superscar.md): swallowed exceptions are the
number-one mechanism behind "green but dead" organs in this repo (W64/W34
asyncpg silent-death, W104 refusal-swallowed class).

Classify each hit:

- HIGH: the handler sits on a production request path, a DB write, a cache
  invalidation, or an external API call whose failure the caller then treats
  as success
- MEDIUM: background/cron path where the failure is logged but no alert or
  state-file records it (silent degradation)
- LOW: genuinely optional work (best-effort telemetry, cosmetic)

Output a markdown table: file:line | handler form (truncated) | what failure
it can hide | risk | one-line reason. Sort HIGH first. Do not silently cap the
list — if you must cap for length, state how many you dropped and why.
