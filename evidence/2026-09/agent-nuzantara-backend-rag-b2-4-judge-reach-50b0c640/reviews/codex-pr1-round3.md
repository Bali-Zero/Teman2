VERDICT: FIX-FIRST

1. **MAJOR — UNSURE** — `apps/backend-rag/backend/services/rag/agentic/_support_signal.py:481`: the parser never verifies `last_turn["role"] == "user"`. A malformed claimed package ending with `{"role":"assistant","content":"context-derived statement"}` reaches judging and potentially generation as its “query.” The real builder cannot produce this because `_sanitize_history` appends a user turn, but the claimed-package boundary remains permissive. Minimal fix: require the final role to be exactly `"user"` and add parser/daemon regression cases.

2. **MAJOR** — `apps/backend-rag/backend/services/rag/agentic/_support_signal.py:485`, `apps/backend-rag/backend/services/rag/agentic/wa_package_builder.py:340`: `query.strip()` does not remove invisible Unicode format characters such as U+200B or U+FEFF. `_sanitize_history([], "\u200b")` produces this package legitimately, and the parser treats it as a real question, allowing context-only judgment. Minimal fix: reject content containing only whitespace/control/format characters, while preserving such characters when ordinary visible content exists; add builder-to-parser regression tests.
   hook: Stop
   hook: Stop Blocked
   codex
   [Mini] Non ho modificato file; il diff era preesistente e il mandato vietava i test. Registro quindi solo il checkpoint operativo, senza falsificare una ricevuta di verifica.
   hook: PreToolUse
   hook: PreToolUse Completed
