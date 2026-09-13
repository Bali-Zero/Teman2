# Language protocol — worked Italian→engineering examples

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.
> `AGENTS.md` keeps the rule; the examples live here.

## 11. Language Protocol (Natural Language → Precise Engineering)

The user writes in **colloquial Italian**. You must automatically translate intent into precise technical action.

**Rules:**

- Never ask "what do you mean?" — infer from codebase context
- Short/vague prompt → deduce file, pattern, stack from existing code before acting
- Italian colloquial → English technical internally, respond in Italian
- If ambiguous between 2 interpretations, pick the most likely one and state your assumption in one line

**Examples:**

| User writes                      | You interpret as                                                                                                  |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| "aggiungi paginazione clienti"   | Cursor-based pagination on `GET /clients`, follow existing router patterns, async SQLAlchemy, add tests           |
| "fixa il bug del login"          | Search recent auth-related errors in routers/auth, identify root cause, fix with proper error handling            |
| "rendi più veloce la ricerca"    | Profile the search endpoint, identify bottleneck (N+1, missing index, no cache), fix the actual cause             |
| "aggiungi un campo alla tabella" | SQL migration in `migrations_v2/` (with ROLLBACK marker) + model update + schema update + router update, in order |

**Never** ask for clarification on standard dev tasks. Explore first, then act.

---
