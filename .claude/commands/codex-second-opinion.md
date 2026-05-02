---
allowed-tools: Bash(.claude/scripts/codex-spalla.sh:*), Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(cat:*), Bash(wc:*), Read, Write
description: Dispatch Codex CLI as adversarial second opinion ("spalla") on the current diff or a focused scope
disable-model-invocation: false
---

Ask Codex CLI for an adversarial second opinion before commit/push. Pattern B (review) by default; Pattern A (autonomous exec) if `--mode=exec` is in the args.

**Arguments:** $ARGUMENTS

**Steps you (Claude) MUST follow:**

1. Parse $ARGUMENTS:
   - Detect `--mode=exec` → Pattern A. Otherwise → Pattern B (default).
   - Detect `--base=<branch>` → use that base. Default = `main`.
   - Remaining free text = focus brief (passed to Codex).

2. Sanity check before dispatch:
   - Run `git status` to confirm cwd is the repo root and the working tree is sensible.
   - Show the user one line: "Dispatching Codex spalla — mode=<mode>, base=<base>, brief=<first 60 chars>".

3. Delegate to the helper script. The script is executable; invoke it
   DIRECTLY (not via `bash <script>`) so the allowed-tools whitelist
   matches (Codex spalla self-review BLOCKER #4):

   ```bash
   .claude/scripts/codex-spalla.sh "<mode>" "<base>" "<focus brief>"
   ```

   The helper handles:
   - anti-pattern guard (empty diff → hard refuse; small diff → 3-line warning + 5s countdown)
   - diff capture
   - dispatch (`codex review --base ...` for Pattern B, `codex exec --full-auto ...` for Pattern A)
   - transcript saved to `~/logs/codex-spalla/<ts>-<slug>.md`
   - BLOCKER-grade transcripts also copied to `docs/codex-reviews/<ts>-blocker-<slug>.md`
   - telemetry one-line JSON to `~/logs/codex-spalla.jsonl`

4. Read the helper's stdout. The last non-empty line will be `RESULT_PATH=<path>`. Read that file.

5. Surface the verdict to the user:
   - One-line verdict (parse first non-empty line of transcript: `BLOCKER`, `MEDIUM`, `LOW`, or `LGTM`).
   - If `BLOCKER` or `MEDIUM`: quote findings inline with line cites.
   - Always include link to the saved transcript path.
   - Suggest next action:
     - `BLOCKER` → "I'll fix these and re-run /codex-second-opinion."
     - `MEDIUM` → "I recommend addressing these before commit."
     - `LOW` / `LGTM` → "Ready to commit."

**Hard rules — DO NOT violate:**

- Never use `--dangerously-bypass-approvals-and-sandbox` in any dispatch.
- Never set `OPENAI_API_KEY` env var; the helper relies on existing OAuth (`codex login status` should show "Logged in using ChatGPT").
- If the helper exits non-zero (other than the hard-refuse exit code 2 for empty diff), surface the stderr to the user and DO NOT silently retry.
- Do NOT run this in a Codex session — it's circular. This command is for Claude Code sessions only.

**When NOT to invoke this command (anti-patterns A1/A2/A3 from CODEX_SPALLA.md):**

- Brainstorming or design dialogue → stay in Claude session.
- Trivial fixes (typos, missing imports) → Claude handles directly.
- UI/visual frontend work → use Claude + claude-in-chrome MCP instead.

The helper script's anti-pattern guard catches A2 (small diff = trivial fix proxy). It cannot detect A1 or A3 — that's on you (Claude) and the user.
