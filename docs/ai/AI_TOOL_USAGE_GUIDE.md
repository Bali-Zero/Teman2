# AI Tool Usage Guide: Claude Code vs Cursor

In Project Nuzantara, we leverage two distinct AI modalities. Understanding when to use which is key to efficiency.

## 1. Claude Code (The "Architect") 🧠
**Role:** Strategy, Reasoning, Deep Analysis.

Use **Claude Code** (or the CLI Agent) when you need to **THINK**:
*   **High-Level Planning:** "How should we architect the new Notification System?"
*   **Deep Debugging:** "Here are 5 files and a complex traceback. Find the root cause."
*   **Massive Refactoring:** "Rewrite the entire `crm` module to use the new `AutoCRM` pattern."
*   **Documentation:** "Analyze the codebase and update `LIVING_ARCHITECTURE.md`."
*   **Safety Checks:** "Review this code for security vulnerabilities before I commit."

**Why:** It excels at holding large context and performing multi-step reasoning without getting distracted by syntax details.

## 2. Cursor (The "Mechanic") 🛠️
**Role:** Tactics, Speed, Flow.

Use **Cursor** (the IDE) when you need to **DO**:
*   **Writing Code:** Implementing a function you've already planned.
*   **Quick Fixes:** "Fix this lint error." "Typos."
*   **Navigation:** Jumping between definitions to understand local flow.
*   **Autocomplete:** Letting Tab/Copilot finish your boilerplate.
*   **Inline Edits:** "Change this loop to a list comprehension" (Cmd+K).

**Why:** It is integrated into the editor. It is faster for small, iterative changes where you don't want to context-switch out of your flow.

## ⚡ The "Handover" Workflow
efficiency comes from switching modes:

1.  **Draft with Claude:** "Plan the User Profile migration." -> Returns a step-by-step plan.
2.  **Execute with Cursor:** Open the files and implement the plan step-by-step, using Cursor to write the actual lines.
3.  **Review with Claude:** "Here is what I wrote. Did I miss anything from the original plan?"
