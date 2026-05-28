# WR2 Canva Headless Actuator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile AppleScript-GUI Canva actuator with a headless `claude -p /canva-apply` subprocess, behind a `WR2_CANVA_ACTUATOR` flag, hardened per the 4-LLM panel (lease, MCP scope, duplica-poi-edita, quota, fail-closed guards).

**Architecture:** The `canva_pending.json` contract and the DB flow stay unchanged. We add a headless actuator path that (1) acquires a PG advisory lock on `template_design_id`, (2) preflights MAX-plan quota, (3) launches `claude -p` with an MCP-scoped config invoking the `/canva-apply` skill (refactored to duplica-poi-edita), (4) verifies Canva tools loaded via stream-json fail-closed, (5) writes `carousel_canva.json` from the actuator (option-c) for downstream consumers, (6) releases the lock in `finally`. The old AppleScript path is retained as fallback (`WR2_CANVA_ACTUATOR=desktop`).

**Tech Stack:** Python 3.11 (`apps/backend-rag/.venv`), asyncpg, `claude` CLI (MAX OAuth), Canva MCP (`mcp__claude_ai_Canva__*`), PG advisory locks.

**Spec:** `research/operations/specs/2026-05-29-wr2-canva-headless-actuator.md` (iter-2, panel APPROVE_WITH_AMENDMENTS 3/3)
**Feasibility evidence:** `research/operations/2026-05-29-wr2-canva-headless-feasibility.md`
**Plan review iter-2 (2026-05-29):** Codex REJECT + DeepSeek APPROVE_WITH_FIXES → 9 fixes F1-F9 incorporated below. Two Codex claims empirically verified on this machine: (F1) `--mcp-config` does NOT isolate without `--strict-mcp-config`; (F2) `.mcp.json` has NO Canva entry — Canva is claude.ai-hosted remote at `https://mcp.canva.com/mcp` (`claude mcp list` → "claude.ai Canva ✓ Connected").

## CLI flag facts (verified `claude --version` 2.1.153, this machine)

- `--mcp-config <file>` LOADS additional MCP servers (MERGE, not replace).
- `--strict-mcp-config` — "Only use MCP servers from --mcp-config" (THIS is the isolation flag; REQUIRED for A2).
- `--disallowedTools <tools...>` / `--allowedTools <tools...>` / `--tools <tools...>` — scope BUILT-IN tools (Bash, filesystem, etc.). `--strict-mcp-config` only scopes MCP servers, NOT built-ins — so A2 needs BOTH `--strict-mcp-config` AND `--disallowedTools Bash` (+ any other dangerous built-in) when running with `--dangerously-skip-permissions`.
- Canva MCP is NOT in `.mcp.json`; it is claude.ai-account-hosted (remote SSE/HTTP at `https://mcp.canva.com/mcp`). The scoped config must declare it as a remote server, NOT copy a local entry.

---

## CRITICAL ORDERING

**Task 0 (A4) is a BLOCKING empirical gate.** If Canva blocks `start-editing-transaction` after a killed mid-transaction process and provides no cancellation path, the headless actuator is NOT viable without a transaction-quarantine mechanism, and the rest of the plan must be re-scoped. Do Task 0 FIRST and report the result before writing any actuator code.

---

## File Structure

| File                                                                     | Responsibility                                                                                                    | Action                               |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `scripts/wr2_canva_headless_probe.py`                                    | One-shot empirical probe for A4 (dangling-transaction behaviour)                                                  | Create (throwaway, may delete after) |
| `~/.claude/skills/canva-apply.md` + `infra/claude-skills/canva-apply.md` | The skill: add step-0 ToolSearch, duplica-poi-edita refactor (A6), hardcoded no-AskUserQuestion defaults (A7)     | Modify                               |
| `scripts/wr2_canva_mcp_scoped.json`                                      | Stripped MCP config loading ONLY Canva + ToolSearch (A2)                                                          | Create                               |
| `scripts/wr2_canva_headless_apply.py`                                    | New headless actuator: lease (A1), quota preflight (A5), launch+verify (A8), option-c write (A3), finally-release | Create                               |
| `scripts/wr2_canva_desktop_apply.py`                                     | Add `WR2_CANVA_ACTUATOR` dispatch: `desktop` (existing) vs `headless` (delegate to new)                           | Modify                               |
| `scripts/tests/test_wr2_canva_headless_apply.py`                         | Unit tests for the new actuator (lease, quota, fail-closed, finally-release)                                      | Create                               |
| `infra/launchagents/com.balizero.wr2.canva-apply.plist`                  | Export `WR2_CANVA_ACTUATOR`, `WR2_HEADLESS_TIMEOUT_SEC=900`                                                       | Modify (cutover only)                |

**Reuse (do NOT reinvent):** `acquire_carousel_lock` / `release_carousel_lock` in `scripts/wr2_carousel_orchestrator.py:78-89` (PG advisory lock via sha256→int key). The new actuator imports/mirrors this pattern keyed on `template_design_id`.

---

## Task 0: A4 — Empirical probe of dangling-transaction behaviour (BLOCKING GATE)

**Files:**

- Create: `scripts/wr2_canva_headless_probe.py`

- [ ] **Step 1: Write the probe script**

```python
#!/usr/bin/env python3
"""A4 probe: does Canva block start-editing-transaction after a killed
mid-transaction process? Run on a THROWAWAY copy only. Read-only on prod."""
import subprocess, sys, time

THROWAWAY_SOURCE = "DAHKzVykbbA"  # pilot design to copy; never edited directly

def claude(prompt: str, timeout: int) -> tuple[int, str]:
    p = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def main() -> int:
    # 1. make throwaway copy
    rc, out = claude(
        f"ToolSearch 'select:mcp__claude_ai_Canva__copy-design' then "
        f"copy-design design_id='{THROWAWAY_SOURCE}'. Report ONLY the new design id.",
        120,
    )
    import re
    m = re.search(r"DA[A-Za-z0-9_-]{8,}", out)
    if not m:
        print(f"PROBE FAIL: no copy id. {out[:300]}"); return 1
    cavia = m.group(0)
    print(f"cavia={cavia}")

    # 2. open a transaction, ASSERT it opened, then KILL mid-transaction (F3).
    #    Use stream-json so we can PROVE a transaction_id was returned before the
    #    kill. The skill is told to open then sleep 600s so the 20s timeout lands
    #    WHILE the transaction is open (not after a normal exit). If no
    #    transaction_id appears in the captured stream, the probe is INVALID —
    #    abort rather than report a false result.
    import re as _re
    proc_open = subprocess.Popen(
        ["claude", "-p",
         f"ToolSearch 'select:mcp__claude_ai_Canva__start-editing-transaction' then "
         f"start-editing-transaction design_id='{cavia}' user_intent='A4 dangling probe'. "
         f"After it returns, sleep 600 seconds doing nothing (do NOT commit, do NOT cancel).",
         "--dangerously-skip-permissions", "--mcp-config", "scripts/wr2_canva_mcp_scoped.json",
         "--strict-mcp-config", "--disallowedTools", "Bash",
         "--output-format", "stream-json", "--verbose"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, text=True,
    )
    time.sleep(20)
    proc_open.kill()  # hard-kill the process group while the txn is open
    captured = ""
    try:
        captured = proc_open.stdout.read() if proc_open.stdout else ""
    except Exception:
        pass
    if not _re.search(r'"transaction"\s*:\s*\{[^}]*"transaction_id"', captured):
        print(f"PROBE INVALID: no transaction_id observed before kill — cannot "
              f"conclude anything about dangling behaviour. captured[:300]={captured[:300]}")
        print(f"cavia to trash: {cavia}")
        return 1
    print("CONFIRMED: transaction was open when process was killed")

    time.sleep(5)

    # 3. immediately try a FRESH transaction on the same cavia, and CLEAN UP
    #    whatever it opens (F3 — don't leave a second dangling txn).
    rc2, out2 = claude(
        f"ToolSearch 'select:mcp__claude_ai_Canva__start-editing-transaction,"
        f"mcp__claude_ai_Canva__cancel-editing-transaction' then "
        f"start-editing-transaction design_id='{cavia}' user_intent='A4 retry after dangling'. "
        f"If it succeeds, IMMEDIATELY call cancel-editing-transaction on the returned id (cleanup) "
        f"and report 'FRESH OK <transaction_id> CANCELLED'. If it fails, report 'BLOCKED <error>'.",
        120,
    )
    print(f"=== RESULT ===\n{out2[:600]}")
    print(f"cavia to trash: {cavia}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the probe**

Run: `cd /Users/nuzantara/Desktop/nuzantara && claude -p` is on PATH; `python scripts/wr2_canva_headless_probe.py`
Expected: prints either `FRESH OK <txn>` (Canva allows overlapping/fresh transactions → headless viable as specced) OR `BLOCKED <error>` (Canva locks → need transaction-quarantine before proceeding).

- [ ] **Step 3: Record the verdict in the spec**

Append the result to `research/operations/2026-05-29-wr2-canva-headless-feasibility.md` under a new "A4 probe result" heading. Move the throwaway cavia to folder `FAHK-KcnLVk` (trash).

- [ ] **Step 4: GATE DECISION**

- If `FRESH OK`: proceed to Task 1. The skill's Phase-0 wipe handles the dirty master.
- If `BLOCKED`: STOP. Add a transaction-cancellation step (Task 0b, not yet written) to the actuator's timeout handler before any further task. Report to operator.

- [ ] **Step 5: Commit the probe + result**

```bash
git add scripts/wr2_canva_headless_probe.py research/operations/2026-05-29-wr2-canva-headless-feasibility.md
git commit -m "test(wr2): A4 dangling-transaction probe + verdict"
```

---

## Task 1: A2 — Scoped MCP config (Canva + ToolSearch only)

**Files:**

- Create: `scripts/wr2_canva_mcp_scoped.json`

- [ ] **Step 1: Write the scoped MCP config (F2 — Canva is a REMOTE claude.ai server, NOT in .mcp.json)**

`.mcp.json` has NO Canva entry. First read the canonical remote definition:

```bash
claude mcp get "claude.ai Canva"
```

Expected output names the transport (HTTP/SSE) + url `https://mcp.canva.com/mcp` + the OAuth it uses.
Write `scripts/wr2_canva_mcp_scoped.json` declaring ONLY that remote server, in the shape `claude mcp get` reports. It is a claude.ai-account-hosted server (OAuth bound to the logged-in account), so the scoped file references the URL; it does NOT carry a command/args local entry.

```json
{
  "mcpServers": {
    "claude_ai_Canva": {
      "type": "http",
      "url": "https://mcp.canva.com/mcp"
    }
  }
}
```

(Match `type`/keys to whatever `claude mcp get` reports — `http` vs `sse`. If it requires an auth header/token reference, copy that verbatim from the `mcp get` output.)

- [ ] **Step 2: Verify isolation with `--strict-mcp-config` + `--disallowedTools` (F1 — the A2 gate)**

`--mcp-config` alone MERGES (does not replace). Isolation requires `--strict-mcp-config`. Built-in tools (Bash, filesystem) are NOT scoped by MCP flags — disallow them explicitly when using `--dangerously-skip-permissions`.

```bash
claude -p "ToolSearch for tool names. Report whether you can see ANY mcp__postgres / mcp__github / mcp__nuzantara tools, and whether the Bash tool is available. Reply 'ISOLATED' if only Canva MCP + ToolSearch and NO Bash, else list what leaked." \
  --mcp-config scripts/wr2_canva_mcp_scoped.json --strict-mcp-config \
  --disallowedTools Bash --dangerously-skip-permissions </dev/null
```

Expected: `ISOLATED`. If postgres/github/nuzantara MCP or Bash leak through, A2 is NOT satisfied — STOP and fix the flag set before any further task. This is the security gate; do not proceed on a leak.

- [ ] **Step 3: Commit**

```bash
git add scripts/wr2_canva_mcp_scoped.json
git commit -m "feat(wr2): scoped MCP config for headless canva (A2 blast-radius limit)"
```

---

## Task 2: A6 — Refactor skill to duplica-poi-edita + step-0 ToolSearch + hardcoded defaults

**Files:**

- Modify: `~/.claude/skills/canva-apply.md` (canonical, installed)
- Modify: `infra/claude-skills/canva-apply.md` (repo mirror — keep in sync)

- [ ] **Step 1: Add STEP -2 (ToolSearch) at the top of the skill body**

Insert before the existing STEP 0:

```
STEP -2 — Carica i tool Canva MCP (headless-safe, idempotente)
Se NON vedi i tool mcp__claude_ai_Canva__* tra quelli disponibili, caricali via
ToolSearch select:mcp__claude_ai_Canva__start-editing-transaction,mcp__claude_ai_Canva__perform-editing-operations,mcp__claude_ai_Canva__commit-editing-transaction,mcp__claude_ai_Canva__cancel-editing-transaction,mcp__claude_ai_Canva__get-design,mcp__claude_ai_Canva__get-design-content,mcp__claude_ai_Canva__upload-asset-from-url,mcp__claude_ai_Canva__copy-design,mcp__claude_ai_Canva__resize-design,mcp__claude_ai_Canva__move-item-to-folder
In sessione interattiva (o Claude Desktop) dove i tool Canva sono già caricati e/o ToolSearch non esiste, questo è un no-op: la condizione "se NON vedi i tool" è falsa, salti a STEP 0. NON forzare ToolSearch incondizionatamente (F7-bis: il path desktop usa lo STESSO file skill via AppleScript — un ToolSearch obbligatorio fallirebbe lì se Desktop ha i tool ma non ToolSearch). La frase è condizionale per design.
```

(F7-bis note: the desktop actuator does NOT invoke this skill file — it drives Claude Desktop GUI via AppleScript and the desktop app may or may not load this exact skill. The conditional phrasing keeps the skill safe in BOTH a headless `claude -p` context and any interactive context. Verified by DeepSeek: desktop path uses AppleScript, not this skill read — but keep the step conditional regardless, since the skill body is shared text.)

- [ ] **Step 2: Invert the phase order — duplica-poi-edita, master STRICTLY read-only (A6 core + F4 + F5)**

Rewrite the phase sequence so the master is NEVER opened in an editing transaction at all (F4: the old Phase -1 `start-editing-transaction` on the master would still leave a dangling master txn on crash). Validation uses READ-ONLY tools. Wipe happens on the WORKING COPY, not the master (F5: duplicate-first would otherwise copy residual dirt into every carousel).

```
NEW ORDER:
Phase -1 VALIDATE master — READ-ONLY (F4): use get-design + get-design-content (content_types
         ['richtexts']) to count live_pages and eligible richtexts (width>=30). DO NOT call
         start-editing-transaction on the master. If live_pages<11 OR eligible_richtexts<18 →
         ERROR + abort (no Canva mutation happened). The master is never opened for editing.
Phase A' DUPLICATE: resize-design on the master → new design_id = WORKING COPY. Move WORKING COPY
         to folder_id (on failure: log "🪂 dup not moved, manual move needed", proceed — A7).
Phase B' NORMALIZE + EDIT the WORKING COPY (F5): open ONE editing transaction on the WORKING COPY.
         First wipe ALL richtext (width>=30) to " " (this is the old Phase 0, now on the copy — kills
         any residue the master carried). Then build the live-template-map from the WORKING COPY,
         remap element_ids by role_index (top-asc), apply the text+image ops. Commit.
Phase C' (DELETED) — no master reset: the master was never opened.
Phase D persist: write design_id = WORKING COPY id, status=applied into pending JSON.
```

Rationale comment in the skill: "Master is opened read-only only (get-design\*). A crash leaves it pristine — only an orphan working-copy to GC. The wipe runs on the copy, so master residue cannot leak into output. Eliminates master corruption, dangling master-transaction, and the shared-master sibling-race (D4)."

- [ ] **Step 3: Hardcode no-AskUserQuestion defaults (A7)**

Add to Hard rules, replacing any generic "safe default":

```
- NEVER call AskUserQuestion. Hardcoded fallbacks for the D3-class ambiguities:
  - folder_id invalid / move fails → skip the move, log "🪂 dup not moved, manual move needed", proceed (do NOT abort).
  - topic contains "do not publish" / "test" → IGNORE as a content flag; it is editorial text, not a control signal. Proceed.
  - slides[] empty BUT operations[] non-empty → proceed using operations (slides[] is optional metadata).
  - operations[] empty → THIS is the only hard-stop: report "ERROR no operations" and exit. Never silently produce a blank carousel.
```

- [ ] **Step 4: Verify the skill changes present + DELIBERATE mirror sync (F7)**

Verify STEP -2 landed (grep returns the block, non-empty exit 0 = present):

```bash
grep -q "^STEP -2" ~/.claude/skills/canva-apply.md && echo "step-2 present" || echo "MISSING step-2"
grep -q "Phase A' DUPLICATE\|DUPLICATE: resize-design" ~/.claude/skills/canva-apply.md && echo "A6 present" || echo "MISSING A6"
```

Expected: `step-2 present` + `A6 present`.

F7 sync hazard: the installed `~/.claude/skills/canva-apply.md` (v3, edited here) and the repo mirror `infra/claude-skills/canva-apply.md` are MATERIALLY DIVERGENT today (v3 vs older). Do NOT blind-`cp` (it could overwrite the mirror's newer/different WR2 path logic OR clobber the installed version). Instead, treat the INSTALLED file as source-of-truth (it's what runs) and update the mirror with a reviewed diff:

```bash
diff ~/.claude/skills/canva-apply.md infra/claude-skills/canva-apply.md | head -60   # inspect divergence FIRST
```

Only after inspecting: copy installed → mirror IF the only differences are the edits made here. If the mirror has unrelated newer content, merge by hand. Commit the mirror, not the installed file (the install path is user-global, not git-tracked).

- [ ] **Step 5: Empirical end-to-end on a throwaway (duplica-poi-edita)**

Run a headless invocation of the refactored skill on a throwaway copy with a 3-op text pending (reuse the feasibility-study harness pattern), `--mcp-config scripts/wr2_canva_mcp_scoped.json`, timeout 900. Verify via interactive MCP that: the WORKING COPY has the new text, and the SOURCE master is UNCHANGED (pristine).
Expected: working copy edited, master untouched. Move throwaway to trash folder.

- [ ] **Step 6: Commit**

```bash
git add infra/claude-skills/canva-apply.md
git commit -m "feat(wr2): canva-apply duplica-poi-edita + step-0 ToolSearch + hardcoded defaults (A2/A6/A7)"
```

(Note: `~/.claude/skills/` is user-global, not git-tracked — committed via the repo mirror; the install sync is a manual step the operator runs.)

---

## Task 3: A1 — Fenced lease module (reuse advisory-lock pattern)

**Files:**

- Create: `scripts/wr2_canva_headless_apply.py` (lease functions first)
- Test: `scripts/tests/test_wr2_canva_headless_apply.py`

- [ ] **Step 1: Write the failing lease test**

```python
import hashlib
from unittest.mock import AsyncMock
import pytest
from scripts.wr2_canva_headless_apply import acquire_master_lock, release_master_lock

@pytest.mark.asyncio
async def test_acquire_master_lock_uses_template_id_key():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    got = await acquire_master_lock(conn, "DAHKzVykbbA")
    assert got is True
    key = int(hashlib.sha256(b"DAHKzVykbbA").hexdigest()[:15], 16)
    conn.fetchval.assert_awaited_once_with("SELECT pg_try_advisory_lock($1)", key)

@pytest.mark.asyncio
async def test_release_master_lock():
    conn = AsyncMock()
    await release_master_lock(conn, "DAHKzVykbbA")
    key = int(hashlib.sha256(b"DAHKzVykbbA").hexdigest()[:15], 16)
    conn.execute.assert_awaited_once_with("SELECT pg_advisory_unlock($1)", key)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd apps/backend-rag && source .venv/bin/activate && cd ../.. && PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -v`
Expected: FAIL — module/function not defined.

- [ ] **Step 3: Implement the lease functions** (mirror `wr2_carousel_orchestrator.py:78-89`, keyed on template_design_id)

```python
import hashlib
import asyncpg

def _lock_key(template_design_id: str) -> int:
    return int(hashlib.sha256(template_design_id.encode()).hexdigest()[:15], 16)

async def acquire_master_lock(conn: asyncpg.Connection, template_design_id: str) -> bool:
    """pg_try_advisory_lock keyed on template_design_id. False if held by Pro OR Mini
    (session-level advisory locks are cluster-global on the shared Fly Postgres)."""
    return await conn.fetchval("SELECT pg_try_advisory_lock($1)", _lock_key(template_design_id))

async def release_master_lock(conn: asyncpg.Connection, template_design_id: str) -> None:
    await conn.execute("SELECT pg_advisory_unlock($1)", _lock_key(template_design_id))
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/wr2_canva_headless_apply.py scripts/tests/test_wr2_canva_headless_apply.py
git commit -m "feat(wr2): fenced master lease via pg advisory lock keyed on template_design_id (A1)"
```

**Note on TTL (A1) — reviewed:** `pg_try_advisory_lock` is SESSION-scoped and cluster-global ON THE SAME shared Fly Postgres database (Pro + Mini both connect there → the lock IS cross-machine effective; verified-correct by both plan reviewers). It auto-releases when the asyncpg connection closes. CAVEAT (Codex F-note): "no lease-of-the-dead" holds only AFTER Postgres detects the connection loss — a HUNG parent process that still holds the asyncpg connection (not crashed, just stuck) keeps the lock until the PG TCP keepalive / `idle_in_transaction_session_timeout` fires. Mitigation: the `subprocess.run(timeout=HEADLESS_TIMEOUT_SEC)` bounds the child; the actuator's own asyncpg connection is the lock holder and is released in `finally`. If the ACTUATOR itself hangs (not the claude child), the LaunchAgent's own timeout + next-tick is the backstop. This is acceptable: a hung actuator is a separate failure class from the D4 race, and the lock-on-shared-PG still prevents two healthy runs from racing the master.

---

## Task 4: A5 — Quota preflight check

**Files:**

- Modify: `scripts/wr2_canva_headless_apply.py`
- Test: `scripts/tests/test_wr2_canva_headless_apply.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch
from scripts.wr2_canva_headless_apply import quota_ok_to_run

def test_quota_ok_when_auth_status_clean():
    with patch("subprocess.run") as m:
        m.return_value.returncode = 0
        m.return_value.stdout = "Logged in as kaiser198719871987@gmail.com"
        assert quota_ok_to_run() is True

def test_quota_blocked_on_limit_string():
    with patch("subprocess.run") as m:
        m.return_value.returncode = 0
        m.return_value.stdout = "usage limit reached, resets in 2h"
        assert quota_ok_to_run() is False
```

- [ ] **Step 2: Run to verify fail**

Run: `PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -k quota -v`
Expected: FAIL — `quota_ok_to_run` not defined.

- [ ] **Step 3: Implement quota preflight**

```python
import subprocess

_QUOTA_BLOCK_PATTERNS = ("usage limit", "out of extra usage", "quota exceeded",
                         "rate limit", "429", "exhausted", "resets in")

def quota_ok_to_run() -> bool:
    """BEST-EFFORT quota signal (F9): `claude auth status` is NOT a reliable MAX
    rolling-window oracle — it reports login state, not remaining quota. This scan
    only catches the case where the CLI surfaces an explicit limit string. Treat a
    True result as "no obvious block", NOT "quota confirmed available". Fail-open on
    probe error. The real protection against a 3am quota outage is the LaunchAgent
    cadence + Telegram alert on repeated headless failures, not this check."""
    try:
        r = subprocess.run(["claude", "auth", "status"], capture_output=True,
                           text=True, timeout=15)
    except Exception:
        return True  # fail-open on probe error: don't block pipeline on a flaky probe
    text = (r.stdout + r.stderr).lower()
    return not any(p in text for p in _QUOTA_BLOCK_PATTERNS)
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -k quota -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/wr2_canva_headless_apply.py scripts/tests/test_wr2_canva_headless_apply.py
git commit -m "feat(wr2): MAX-plan quota preflight to defer headless run near cap (A5)"
```

---

## Task 5: Headless launch + A8 fail-closed verify + A3 option-c write + finally-release

**Files:**

- Modify: `scripts/wr2_canva_headless_apply.py`
- Test: `scripts/tests/test_wr2_canva_headless_apply.py`

- [ ] **Step 1: Write the failing test for fail-closed tool verification**

```python
from scripts.wr2_canva_headless_apply import canva_tools_loaded_in_stream

def test_canva_tools_loaded_true_when_present():
    jsonl = '{"type":"system","tools":["ToolSearch"]}\n{"message":{"content":[{"type":"tool_use","name":"mcp__claude_ai_Canva__start-editing-transaction"}]}}\n'
    assert canva_tools_loaded_in_stream(jsonl) is True

def test_canva_tools_loaded_false_when_absent():
    jsonl = '{"type":"system","tools":["ToolSearch"]}\n{"message":{"content":[{"type":"text","text":"NO CANVA MCP"}]}}\n'
    assert canva_tools_loaded_in_stream(jsonl) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -k tools_loaded -v`
Expected: FAIL — function not defined.

- [ ] **Step 3: Implement the fail-closed verifier**

```python
import json

def canva_tools_loaded_in_stream(stream_jsonl: str) -> bool:
    """A8 fail-closed: scan stream-json for an actual mcp__claude_ai_Canva__* tool_use.
    If the skill never invoked a Canva tool, the run did NOT touch Canva — caller must
    NOT mark the draft rendered."""
    for line in stream_jsonl.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message", {})
        content = msg.get("content")
        if isinstance(content, list):
            for blk in content:
                if (isinstance(blk, dict) and blk.get("type") == "tool_use"
                        and str(blk.get("name", "")).startswith("mcp__claude_ai_Canva__")):
                    return True
    return False
```

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -k tools_loaded -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Implement the orchestrating `apply_headless` coroutine**

```python
import asyncio, json, os, subprocess, time
from pathlib import Path

HEADLESS_TIMEOUT_SEC = int(os.environ.get("WR2_HEADLESS_TIMEOUT_SEC", "900"))
# F1: absolute path relative to this file, not cwd-dependent.
SCOPED_MCP = str(Path(__file__).resolve().parent / "wr2_canva_mcp_scoped.json")

def _build_command_text(skill_body: str, pending_path: Path) -> str:
    return (
        "Execute the Canva carousel apply flow below. STEP -2 first (load Canva tools "
        "via ToolSearch). The pending JSON is at the path below. NEVER call "
        "AskUserQuestion; use the hardcoded fallbacks. This is pre-authorized.\n\n"
        f"Pending file path: {pending_path}\n\n---\n\n{skill_body}"
    )

async def apply_headless(conn, pending_path: Path, template_design_id: str,
                         output_path: Path) -> tuple[str, str, str | None] | None:
    """Returns (design_id, edit_url, view_url) on success, None on failure.
    Acquires master lock, runs headless, fail-closed verifies, writes option-c file."""
    if not quota_ok_to_run():
        return None  # caller logs + Telegram defer
    if not await acquire_master_lock(conn, template_design_id):
        return None  # another run (Pro/Mini) holds the master — defer, do not corrupt
    try:
        skill_body = (Path.home() / ".claude/skills/canva-apply.md").read_text(encoding="utf-8")
        if skill_body.startswith("---"):
            skill_body = skill_body.split("---", 2)[2].lstrip()
        cmd_text = _build_command_text(skill_body, pending_path)
        proc = subprocess.run(
            # F1: --strict-mcp-config isolates MCP servers; --disallowedTools Bash
            # removes the built-in shell (MCP flags don't scope built-ins). Both are
            # mandatory under --dangerously-skip-permissions (A2 blast-radius).
            ["claude", "-p", cmd_text, "--dangerously-skip-permissions",
             "--mcp-config", SCOPED_MCP, "--strict-mcp-config",
             "--disallowedTools", "Bash",
             "--output-format", "stream-json", "--verbose"],
            capture_output=True, text=True, timeout=HEADLESS_TIMEOUT_SEC,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            return None  # F1: non-zero exit (auth fail, crash) → do NOT mark rendered
        stream = proc.stdout or ""
        if not canva_tools_loaded_in_stream(stream):
            return None  # A8: Canva never touched — do NOT mark rendered
        pending = json.loads(pending_path.read_text())
        if pending.get("status") != "applied" or not pending.get("design_id"):
            return None
        design_id = pending["design_id"]
        edit_url = pending.get("design_url") or f"https://www.canva.com/design/{design_id}/edit"
        view_url = pending.get("view_url")
        # A3 option-c: actuator writes carousel_canva.json for reconcile + upload-waste
        output_path.write_text(json.dumps({
            "design_id": design_id, "design_url": edit_url, "view_url": view_url,
            "topic": pending.get("topic"), "slides_count": pending.get("slides_count"),
            "status": "applied", "applied_at": pending.get("applied_at"),
        }, indent=2), encoding="utf-8")
        return design_id, edit_url, view_url
    except subprocess.TimeoutExpired:
        return None  # caller logs timeout + Telegram; lock released in finally
    finally:
        await release_master_lock(conn, template_design_id)
```

- [ ] **Step 6: Write the failing test for the option-c write on success**

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_apply_headless_writes_carousel_canva_json(tmp_path):
    pending = tmp_path / "canva_pending.json"
    out = tmp_path / "carousel_canva.json"
    pending.write_text(json.dumps({"status": "applied", "design_id": "DAHKxyz",
                                    "topic": "t", "slides_count": 11}))
    conn = AsyncMock(); conn.fetchval.return_value = True
    stream = '{"message":{"content":[{"type":"tool_use","name":"mcp__claude_ai_Canva__commit-editing-transaction"}]}}'
    # F6: apply_headless reads ~/.claude/skills/canva-apply.md via Path.read_text.
    # That file may not exist in CI → FileNotFoundError before the test can assert.
    # Patch Path.read_text so the skill-body read returns a dummy. The pending/out
    # reads use tmp_path real files; to avoid clobbering them, route the dummy ONLY
    # for the skills path via a side_effect that inspects the path.
    real_read = Path.read_text
    def _read(self, *a, **k):
        if self.name == "canva-apply.md":
            return "DUMMY SKILL BODY"
        return real_read(self, *a, **k)
    with patch("scripts.wr2_canva_headless_apply.quota_ok_to_run", return_value=True), \
         patch.object(Path, "read_text", _read), \
         patch("subprocess.run") as m:
        m.return_value.stdout = stream
        m.return_value.returncode = 0
        from scripts.wr2_canva_headless_apply import apply_headless
        res = await apply_headless(conn, pending, "DAHKtmpl", out)
    assert res[0] == "DAHKxyz"
    assert json.loads(out.read_text())["design_id"] == "DAHKxyz"
    conn.execute.assert_awaited()  # release called
```

- [ ] **Step 7: Run all tests**

Run: `PYTHONPATH=. pytest scripts/tests/test_wr2_canva_headless_apply.py -v`
Expected: PASS (all tests green).

- [ ] **Step 8: Commit**

```bash
git add scripts/wr2_canva_headless_apply.py scripts/tests/test_wr2_canva_headless_apply.py
git commit -m "feat(wr2): headless apply orchestration — fail-closed verify (A8) + option-c write (A3) + finally-release (A1)"
```

---

## Task 6: Wire the `WR2_CANVA_ACTUATOR` dispatch into the existing entrypoint

**Files:**

- Modify: `scripts/wr2_canva_desktop_apply.py:357-517` (the `_apply_one` flow)

- [ ] **Step 1: Add the dispatch branch in `_apply_one`**

After the pending JSON is written (line ~378) and before the AppleScript block (line ~418), insert:

```python
actuator = os.environ.get("WR2_CANVA_ACTUATOR", "desktop")
if actuator == "headless":
    from wr2_canva_headless_apply import apply_headless
    template_design_id = pending["template_design_id"]
    result = await apply_headless(conn, CANVA_PENDING_PATH, template_design_id, CANVA_OUTPUT_PATH)
    if not result:
        _send_telegram(f"WR2 headless apply failed/deferred — draft {draft_id}")
        return False
    design_id, edit_url, view_url = result
    await _persist_result(conn, draft_id, design_id, edit_url, view_url)
    _send_telegram(f"WR2 carousel ready (headless)\nDesign: {design_id}\nOpen: {edit_url}")
    return True
# else: fall through to existing AppleScript path (actuator == "desktop")
```

- [ ] **Step 2: Verify desktop path unchanged (regression)**

Run: `WR2_CANVA_ACTUATOR=desktop python scripts/wr2_canva_desktop_apply.py --dry-run`
Expected: same dry-run output as before (lists drafts, no actuator invoked).

- [ ] **Step 3: Shadow-validate headless on ONE real draft (operator-supervised)**

Run: `WR2_CANVA_ACTUATOR=headless python scripts/wr2_canva_desktop_apply.py --draft-id <a-real-eligible-draft>`
Expected: headless run completes ~250s, draft marked rendered, `carousel_canva.json` written, Canva design verified via interactive MCP. Confirm the SOURCE master is pristine (A6).

- [ ] **Step 4: Commit**

```bash
git add scripts/wr2_canva_desktop_apply.py
git commit -m "feat(wr2): WR2_CANVA_ACTUATOR dispatch — headless path behind flag, desktop fallback intact"
```

---

## Task 7: Cutover (only after shadow validation is green over several drafts)

**Files:**

- Modify: `infra/launchagents/com.balizero.wr2.canva-apply.plist`

- [ ] **Step 1: Add env to the plist**

In `EnvironmentVariables`: `WR2_CANVA_ACTUATOR=headless`, `WR2_HEADLESS_TIMEOUT_SEC=900`.

- [ ] **Step 2: INSTALL the repo plist to LaunchAgents, then reload (F8)**

The repo `infra/launchagents/...plist` is the source; launchd loads from `~/Library/LaunchAgents/`. They diverge today — you MUST copy before reload, else the edit never takes effect. Diff first, then install:

```bash
diff infra/launchagents/com.balizero.wr2.canva-apply.plist ~/Library/LaunchAgents/com.balizero.wr2.canva-apply.plist | head -40   # inspect divergence (F8)
# If the only diff is the env vars added in Step 1, install. If the installed plist has
# unrelated newer content (different ProgramArguments path, secrets), merge by hand instead.
cp infra/launchagents/com.balizero.wr2.canva-apply.plist ~/Library/LaunchAgents/com.balizero.wr2.canva-apply.plist
launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-apply 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-apply.plist
launchctl print gui/$(id -u)/com.balizero.wr2.canva-apply | grep -E "last exit code|WR2_CANVA_ACTUATOR"
```

Expected: `WR2_CANVA_ACTUATOR = headless` visible in the loaded config; exit 0 on next eligible draft.

- [ ] **Step 3: Commit**

```bash
git add infra/launchagents/com.balizero.wr2.canva-apply.plist
git commit -m "chore(wr2): cutover canva-apply LaunchAgent to headless actuator"
```

- [ ] **Step 4: Update cicatrix-scars.md**

Add the INFO+REVERSAL scar drafted in the feasibility study (the 2026-05-13 wall fell; headless shipped with A1-A8 hardening; D4 re-validated lease-watchdog).

---

## Self-review notes (spec coverage)

- A1 lease → Task 3 (advisory-lock, session-scoped = no lease-of-the-dead). ✅
- A2 MCP scope → Task 1 (scoped config) + Task 5 (--mcp-config). ✅
- A3 option-c → Task 5 Step 5 (actuator writes carousel_canva.json). ✅
- A4 dangling-transaction → Task 0 (BLOCKING probe). ✅
- A5 quota → Task 4. ✅
- A6 duplica-poi-edita → Task 2 Step 2. ✅
- A7 hardcoded defaults → Task 2 Step 3. ✅
- A8 fail-closed → Task 5 Steps 1-4. ✅
- Cutover flag → Task 6 + Task 7. ✅

## Plan-review fixes incorporated (iter-2, Codex + DeepSeek, 2026-05-29)

- F1 `--strict-mcp-config` + `--disallowedTools Bash` (MCP-config alone merges, doesn't isolate; built-ins not scoped by MCP flags) → CLI-facts header + Task 1 Step 2 + Task 5 Step 5. ✅ empirically verified.
- F2 Canva is claude.ai-hosted remote (`https://mcp.canva.com/mcp`), NOT in `.mcp.json` → Task 1 Step 1 rewritten. ✅ empirically verified.
- F3 Task 0 probe now asserts a transaction_id was observed before kill (stream-json) + cancels the retry txn → no false-pass, no second dangling txn. ✅
- F4 A6 master STRICTLY read-only in Phase -1 (get-design/get-design-content, no start-editing-transaction on master) → Task 2 Step 2. ✅
- F5 wipe moved onto the WORKING COPY (Phase B'), not the master → no master-residue leak into output. ✅
- F6 Task 5 Step 6 test patches `Path.read_text` for the skill-body read → no `FileNotFoundError` in CI. ✅
- F7 Task 2 Step 4 grep-based verify (not inverted diff) + deliberate mirror sync (no blind cp). ✅
- F7-bis ToolSearch step phrased conditional (desktop path safety). ✅
- F8 Task 7 adds the install copy (repo plist → ~/Library/LaunchAgents) before reload. ✅
- F9 quota check labelled BEST-EFFORT (not a reliable MAX oracle); real protection = cadence + alert. ✅
- Lease note: cross-machine-correct on shared PG; caveat about a hung (not crashed) parent holding the lock documented. ✅
