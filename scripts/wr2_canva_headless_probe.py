#!/usr/bin/env python3
"""A4 probe: does Canva block start-editing-transaction after a killed
mid-transaction process? Run on a THROWAWAY copy only. Read-only on prod.

A2 re-scope: plain --dangerously-skip-permissions (no --strict-mcp-config, which
would exclude account-hosted Canva). Canva reachable via ToolSearch."""
import re
import subprocess
import sys
import time

THROWAWAY_SOURCE = "DAHKzVykbbA"  # pilot design to copy; never edited directly


def claude(prompt: str, timeout: int) -> tuple[int, str]:
    p = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    # 1. make throwaway copy
    rc, out = claude(
        f"ToolSearch 'select:mcp__claude_ai_Canva__copy-design' then "
        f"copy-design design_id='{THROWAWAY_SOURCE}'. Report ONLY the new design id.",
        120,
    )
    m = re.search(r"DA[A-Za-z0-9_-]{8,}", out)
    if not m:
        print(f"PROBE FAIL: no copy id. {out[:300]}")
        return 1
    cavia = m.group(0)
    print(f"cavia={cavia}")

    # 2. open a transaction, ASSERT it opened, then KILL mid-transaction (F3).
    #    Use stream-json so we can PROVE a transaction_id was returned before the
    #    kill. The skill is told to open then sleep 600s so the 20s timeout lands
    #    WHILE the transaction is open (not after a normal exit). If no
    #    transaction_id appears in the captured stream, the probe is INVALID —
    #    abort rather than report a false result.
    # ROOT CAUSE of earlier INVALID runs (2026-05-29, 3 failed fixes): reading the
    # child stdout via subprocess.PIPE + a reader thread DEADLOCKED — claude -p does
    # not flush line-by-line into a pipe, so only the early SessionStart hook lines
    # (a few hundred bytes) reached the reader before the pipe buffer stalled; the
    # tool_use events stayed buffered until process end. The /tmp timing run that
    # DID see transaction_id at t=10s redirected stdout to a FILE (no pipe-buffer
    # deadlock). Fix: redirect to a temp file and poll the file — replicate exactly
    # the condition that worked.
    import os
    import tempfile

    stream_path = tempfile.mktemp(prefix="a4-probe-", suffix=".jsonl")
    stream_fh = open(stream_path, "w")
    proc_open = subprocess.Popen(
        # A2 re-scope: plain --dangerously-skip-permissions (no --strict-mcp-config,
        # which would exclude account-hosted Canva). Canva reachable via ToolSearch.
        # IMPORTANT (root cause of all earlier INVALID runs, 2026-05-29): the model
        # REFUSES a prompt that asks it to open a transaction and leave it dangling
        # ("apro una transazione e poi sleep 600s senza commit" → "Non eseguo questa
        # sequenza"). It correctly treats abandoning shared editing state as risky.
        # So we give it a LEGITIMATE task — open + perform many real edits + commit —
        # and create the dangling state by KILLING the process externally mid-edit
        # (after transaction_id appears, before commit). The dangling is caused by the
        # external kill, not by instructing the model to abandon the transaction.
        [
            "claude",
            "-p",
            f"ToolSearch 'select:mcp__claude_ai_Canva__start-editing-transaction,"
            f"mcp__claude_ai_Canva__get-design-content,mcp__claude_ai_Canva__perform-editing-operations,"
            f"mcp__claude_ai_Canva__commit-editing-transaction' then on design '{cavia}': "
            f"start-editing-transaction, then get-design-content (richtexts) to list every richtext "
            f"element, then for EACH richtext element call perform-editing-operations to replace its "
            f"text with 'A4 EDIT'. Do all elements one by one, then commit-editing-transaction. "
            f"This is a real edit task on a throwaway copy; proceed without asking.",
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
        ],
        stdout=stream_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    # poll the file every 2s for transaction_id (escaped form) — kill the moment the
    # transaction opens (mid legitimate edit), up to 150s, creating the dangling state.
    opened = False
    txn_pat = re.compile(r'transaction_id[\\"\s:]*\d')
    for _ in range(75):  # 75 * 2s = 150s
        time.sleep(2)
        try:
            data = open(stream_path).read()
        except Exception:
            data = ""
        if txn_pat.search(data):
            opened = True
            break
        if proc_open.poll() is not None:  # process exited before opening — abnormal
            break
    proc_open.kill()  # hard-kill while the txn is open (or after timeout if never opened)
    try:
        stream_fh.close()
    except Exception:
        pass
    captured = ""
    try:
        captured = open(stream_path).read()
    except Exception:
        pass
    try:
        os.unlink(stream_path)
    except Exception:
        pass
    if not opened:
        print(
            f"PROBE INVALID: no transaction_id observed within 150s — cannot "
            f"conclude anything about dangling behaviour. captured[-400:]={captured[-400:]}"
        )
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
