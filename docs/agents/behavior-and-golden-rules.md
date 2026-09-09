# Agent behavior rules and golden rules

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

## 2. Agent Behavior Rules (IMPORTANT)

**DO NOT ask the user to write code.** You are authorized to edit, write, and execute code directly.

- Use `Edit`, `Write`, `Bash` without asking permission
- `defaultMode: acceptEdits` means act first, ask if blocked
- Only ask if you genuinely need user input (e.g., choosing between multiple valid approaches)
- **NEVER** ask "should I write this?" or "do you want me to...?" — just do it

**Exception:** Only ask for decisions on:

- Architecture choices with trade-offs (use `AskUserQuestion`)
- Production deployments (use risk/reversibility judgment)
- Destructive operations (rm, git reset --hard, etc.)

## 4. Golden Rules (ENFORCE STRICTLY)

1. **Virtualenv Mandatory** - Never use system Python. Always activate venv first.
2. **No Root Execution** - Use `PYTHONPATH=. python -m backend.module`, never run modules directly.
3. **Path Discipline** - Absolute imports only: `from backend.core import config`, never relative.
4. **Async First** - Use `httpx` for HTTP, never `requests`. All I/O must be async.
5. **Type Hints Required** - Every function must have full type annotations.
6. **No Hardcoded Secrets** - Use environment variables or secrets manager.
7. **Data/Logic Separation** - Business logic separate from data access layer.
8. **Clean Logging** - Use `logger`, never `print()` statements.
9. **Quality Standards** - Tests, error handling, graceful degradation required.
10. **Verify Sources** - Never presume, always verify against actual data sources.
