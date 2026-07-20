#!/usr/bin/env python3
"""subagent_stop_verify.py guilt+innocence suite (pattern: test_hook_innocence.py /
test_w85_stash_readonly.py — synthetic repo in a tempdir, real hook invoked via
subprocess with JSON on stdin, exit code is the contract).

GUILT  (the hook must still catch the real danger): a dirty worktree, no
       intent marker, no stop_hook_active, no kill switch → BLOCK (exit 2)
       with constructive guidance on stderr.

INNOCENCE (the hook must NOT wall a legitimate/benign case):
  - clean worktree → ALLOW
  - dirty + explicit intent marker in the transcript → ALLOW
  - `stop_hook_active: true` (anti-loop, PRIMA DI TUTTO) → ALLOW
  - kill switch SUBAGENT_STOP_VERIFY_OFF=1 → ALLOW
  - kill switch STOP_VERIFY_ALLOW_DIRTY=1 (T2.6 parity) → ALLOW
  - second invocation for the SAME transcript after a block (marker file
    belt-and-suspenders anti-loop) → ALLOW
  - cwd is not a git repo → ALLOW
  - malformed stdin → ALLOW (fail-open)

MARKER SWEEP (P3): a marker file older than 24h must be swept the next time
the hook drops a fresh marker in the same directory (best-effort GC — markers
otherwise accumulate in $TMPDIR forever).

BLOCK MESSAGE WORDING (P3): the block message must never suggest a blanket
`git add -A` (a shared main checkout can capture a sibling session's files —
cicatrix family #5) and must explicitly point at path-by-path staging.

INSTALLER ROLLBACK (P2-9): install_subagent_stop_verify.sh, exercised via a
fake $HOME (never touches the real ~/.claude/), covers:
  - a byte-identical pre-existing hook + a forced self-verify failure ->
    the file is left IN PLACE (not deleted) — the tri-state HOOK_STATE fix;
  - a freshly-installed (no pre-existing file) hook + forced failure -> the
    file IS removed (nothing to restore);
  - settings.json missing -> FAIL-VISIBLE exit 1 (not the old silent exit 0),
    while the hook file itself is still installed.
All three installer cases short-circuit before the real self-verify suite
ever runs (forced failure replaces it; missing-settings exits before it),
so none of them can recurse into this file via the installer's own
self-verify step.

Run:  python3 infra/claude-hooks/test_subagent_stop_verify.py
      (exit 0 = all clean, 1 = at least one regression)
Also a pytest target: pytest infra/claude-hooks/test_subagent_stop_verify.py -q

Reference: research/operations/specs/T2.6-stop-verify-hook.md (Stop-hook sibling
this mirrors) · cicatrix-scars.md W80 / wave15-live-reap.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "subagent_stop_verify.py"
INSTALL_SCRIPT = HERE / "install_subagent_stop_verify.sh"


def _make_git_repo(dirty: bool) -> str:
    """A fresh git repo in an isolated tempdir. `dirty=True` drops an
    untracked file so `git status --porcelain` is non-empty."""
    d = tempfile.mkdtemp(prefix="subagent_stop_verify_repo_")
    subprocess.run(["git", "init", "-q", d], check=True, capture_output=True)
    # a plausible identity so `git commit` would work if the hook ever needed it
    subprocess.run(["git", "-C", d, "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "test"], check=True, capture_output=True)
    if dirty:
        (pathlib.Path(d) / "untracked.txt").write_text("wip\n")
    return d


def _make_transcript(text: str) -> str:
    f = tempfile.NamedTemporaryFile(prefix="transcript_", suffix=".jsonl", delete=False, mode="w")
    f.write(text)
    f.close()
    return f.name


def run_hook(payload_text: str | None, payload: dict | None = None,
             tmpdir_override: str | None = None, extra_env: dict | None = None) -> tuple[int, str]:
    """Invoke the real hook file as Claude Code does: JSON on stdin. Returns
    (exit_code, stderr). Pass either `payload` (dict, will be json.dumps-ed) or
    raw `payload_text` (to test malformed stdin)."""
    stdin_data = payload_text if payload_text is not None else json.dumps(payload or {})
    env = dict(os.environ)
    # isolate TMPDIR per case so the marker-file anti-loop doesn't leak across
    # unrelated cases (they'd all hash the same empty transcript_path otherwise)
    env["TMPDIR"] = tmpdir_override or tempfile.mkdtemp(prefix="subagent_stop_verify_tmp_")
    env.pop("SUBAGENT_STOP_VERIFY_OFF", None)
    env.pop("STOP_VERIFY_ALLOW_DIRTY", None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_data, capture_output=True, text=True, timeout=15, env=env,
    )
    return (proc.returncode, proc.stderr)


def evaluate() -> list[str]:
    failures: list[str] = []

    # --- GUILT --------------------------------------------------------
    dirty_repo = _make_git_repo(dirty=True)
    code, err = run_hook(None, {"cwd": dirty_repo, "transcript_path": ""})
    if code != 2:
        failures.append(f"GUILT MISS: dirty worktree, no marker/intent → expected BLOCK(2), got {code}")
    elif "SUBAGENT STOP BLOCKED" not in err:
        failures.append(f"GUILT MISS: exit 2 but stderr lacks guidance: {err!r}")
    elif "untracked.txt" not in err:
        failures.append(f"GUILT MISS: stderr does not list the dirty file: {err!r}")

    # --- INNOCENCE ------------------------------------------------------
    clean_repo = _make_git_repo(dirty=False)
    code, err = run_hook(None, {"cwd": clean_repo, "transcript_path": ""})
    if code != 0:
        failures.append(f"INNOCENT BITTEN: clean worktree → expected ALLOW(0), got {code}, stderr={err!r}")

    dirty_repo2 = _make_git_repo(dirty=True)
    transcript = _make_transcript("assistant: WIP: checkpoint here, leave dirty for the orchestrator\n")
    code, err = run_hook(None, {"cwd": dirty_repo2, "transcript_path": transcript})
    if code != 0:
        failures.append(f"INNOCENT BITTEN: dirty + intent marker → expected ALLOW(0), got {code}, stderr={err!r}")

    dirty_repo3 = _make_git_repo(dirty=True)
    code, err = run_hook(None, {"cwd": dirty_repo3, "transcript_path": "", "stop_hook_active": True})
    if code != 0:
        failures.append(f"INNOCENT BITTEN: stop_hook_active=true (anti-loop) → expected ALLOW(0), got {code}, stderr={err!r}")

    dirty_repo4 = _make_git_repo(dirty=True)
    code, err = run_hook(None, {"cwd": dirty_repo4, "transcript_path": ""},
                          extra_env={"SUBAGENT_STOP_VERIFY_OFF": "1"})
    if code != 0:
        failures.append(f"INNOCENT BITTEN: SUBAGENT_STOP_VERIFY_OFF=1 → expected ALLOW(0), got {code}, stderr={err!r}")

    dirty_repo5 = _make_git_repo(dirty=True)
    code, err = run_hook(None, {"cwd": dirty_repo5, "transcript_path": ""},
                          extra_env={"STOP_VERIFY_ALLOW_DIRTY": "1"})
    if code != 0:
        failures.append(f"INNOCENT BITTEN: STOP_VERIFY_ALLOW_DIRTY=1 (T2.6 parity) → expected ALLOW(0), got {code}, stderr={err!r}")

    # second invocation for the SAME transcript, SAME TMPDIR → marker must fire
    dirty_repo6 = _make_git_repo(dirty=True)
    shared_tmpdir = tempfile.mkdtemp(prefix="subagent_stop_verify_shared_")
    same_payload = {"cwd": dirty_repo6, "transcript_path": ""}
    first_code, first_err = run_hook(None, same_payload, tmpdir_override=shared_tmpdir)
    second_code, second_err = run_hook(None, same_payload, tmpdir_override=shared_tmpdir)
    if first_code != 2:
        failures.append(f"SETUP: first block for marker-reuse case did not fire (got {first_code}) — cannot test anti-loop marker")
    elif second_code != 0:
        failures.append(f"INNOCENT BITTEN: second invocation, same transcript, marker present → expected ALLOW(0), got {second_code}, stderr={second_err!r}")

    non_git_dir = tempfile.mkdtemp(prefix="subagent_stop_verify_nogit_")
    code, err = run_hook(None, {"cwd": non_git_dir, "transcript_path": ""})
    if code != 0:
        failures.append(f"INNOCENT BITTEN: cwd not a git repo → expected ALLOW(0), got {code}, stderr={err!r}")

    code, err = run_hook("{not valid json::")
    if code != 0:
        failures.append(f"INNOCENT BITTEN: malformed stdin → expected ALLOW(0) (fail-open), got {code}, stderr={err!r}")

    # --- BLOCK MESSAGE WORDING (P3) --------------------------------------
    # Re-use the GUILT block above's stderr: no bare `git add -A`, and an
    # explicit path-by-path instruction instead (family #5, sibling-race —
    # a subagent that obeys "commit your work" verbatim on a shared main
    # checkout must never be told to stage everything).
    dirty_repo_msg = _make_git_repo(dirty=True)
    _, msg_err = run_hook(None, {"cwd": dirty_repo_msg, "transcript_path": ""})
    if "git add -A" in msg_err:
        failures.append(f"BLOCK MESSAGE: still suggests a blanket `git add -A` — sibling-race risk: {msg_err!r}")
    if "path by path" not in msg_err:
        failures.append(f"BLOCK MESSAGE: missing explicit path-by-path staging guidance: {msg_err!r}")

    # --- MARKER SWEEP (P3) -----------------------------------------------
    # A stale (>24h) sibling marker in the SAME tmpdir must be swept the next
    # time the hook drops a fresh marker there (best-effort GC).
    sweep_tmpdir = tempfile.mkdtemp(prefix="subagent_stop_verify_sweep_")
    stale_marker = pathlib.Path(sweep_tmpdir) / "subagent_stop_verify_deadbeefdeadbeefdeadbeefdeadbeefdeadbeef.once"
    stale_marker.touch()
    stale_ts = time.time() - (25 * 3600)  # >24h old
    os.utime(stale_marker, (stale_ts, stale_ts))

    dirty_repo_sweep = _make_git_repo(dirty=True)
    sweep_code, sweep_err = run_hook(
        None, {"cwd": dirty_repo_sweep, "transcript_path": ""}, tmpdir_override=sweep_tmpdir
    )
    if sweep_code != 2:
        failures.append(f"SETUP: block for marker-sweep case did not fire (got {sweep_code}) — cannot test sweep")
    elif stale_marker.exists():
        failures.append("MARKER SWEEP: a >24h-old sibling marker was NOT removed when a fresh marker was dropped")

    # a marker younger than 24h in the same dir must survive the sweep
    fresh_marker = pathlib.Path(sweep_tmpdir) / "subagent_stop_verify_cafebabecafebabecafebabecafebabecafebabe.once"
    fresh_marker.touch()
    dirty_repo_sweep2 = _make_git_repo(dirty=True)
    run_hook(None, {"cwd": dirty_repo_sweep2, "transcript_path": ""}, tmpdir_override=sweep_tmpdir)
    if not fresh_marker.exists():
        failures.append("MARKER SWEEP: a fresh (<24h) sibling marker was incorrectly swept")

    failures.extend(evaluate_installer())

    return failures


# ------------------------------------------------------------- installer ---
def _run_installer(
    home_dir: str, extra_env: dict | None = None, create_settings: bool = True
) -> tuple[int, str, str]:
    """Invoke install_subagent_stop_verify.sh against a FAKE $HOME (never
    touches the real ~/.claude/). Returns (exit_code, stdout, stderr)."""
    hooks_dir = pathlib.Path(home_dir) / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    if create_settings:
        settings_path = pathlib.Path(home_dir) / ".claude" / "settings.json"
        if not settings_path.exists():
            settings_path.write_text("{}\n")
    env = dict(os.environ)
    env["HOME"] = home_dir
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        capture_output=True, text=True, timeout=60, env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def evaluate_installer() -> list[str]:
    """Shell-driven installer tests (P2-9). Every case here forces the
    self-verify step to fail via SUBAGENT_INSTALL_VERIFY_CMD=false, or hits
    the missing-settings.json early-exit BEFORE self-verify runs — so none
    of these can recurse into the real test_subagent_stop_verify.py suite
    via the installer's own self-verify invocation."""
    failures: list[str] = []
    hook_bytes = HOOK.read_text()

    # Case 1 (the P2-9 headline): dest pre-exists BYTE-IDENTICAL to the repo
    # copy, self-verify is forced to fail -> the file must be LEFT IN PLACE,
    # not deleted, and no backup should have been created for it.
    home1 = tempfile.mkdtemp(prefix="subagent_stop_verify_installer_identical_")
    dst1 = pathlib.Path(home1) / ".claude" / "hooks" / "subagent_stop_verify.py"
    dst1.parent.mkdir(parents=True, exist_ok=True)
    dst1.write_text(hook_bytes)
    rc1, out1, err1 = _run_installer(home1, extra_env={"SUBAGENT_INSTALL_VERIFY_CMD": "false"})
    if rc1 != 1:
        failures.append(f"INSTALLER preexisting-identical+forced-fail: expected exit 1, got {rc1}. stdout={out1!r} stderr={err1!r}")
    if not dst1.exists():
        failures.append("INSTALLER preexisting-identical+forced-fail: hook file was DELETED — P2-9 regression (a live healthy hook was destroyed)")
    elif dst1.read_text() != hook_bytes:
        failures.append("INSTALLER preexisting-identical+forced-fail: hook file content changed unexpectedly")
    stray_backups = list(dst1.parent.glob("subagent_stop_verify.py.bak-*"))
    if stray_backups:
        failures.append(f"INSTALLER preexisting-identical+forced-fail: unexpected backup file(s) for an identical pre-existing hook: {stray_backups}")

    # Case 2: dest does NOT pre-exist (fresh install), self-verify forced to
    # fail -> the newly-created file must be REMOVED (nothing to restore).
    home2 = tempfile.mkdtemp(prefix="subagent_stop_verify_installer_new_")
    dst2 = pathlib.Path(home2) / ".claude" / "hooks" / "subagent_stop_verify.py"
    rc2, out2, err2 = _run_installer(home2, extra_env={"SUBAGENT_INSTALL_VERIFY_CMD": "false"})
    if rc2 != 1:
        failures.append(f"INSTALLER new+forced-fail: expected exit 1, got {rc2}. stdout={out2!r} stderr={err2!r}")
    if dst2.exists():
        failures.append("INSTALLER new+forced-fail: hook file should have been removed on rollback (nothing pre-existed to restore)")

    # Case 3: settings.json missing -> FAIL-VISIBLE exit 1 (not the old
    # silent exit 0), even though the hook file itself still gets installed.
    home3 = tempfile.mkdtemp(prefix="subagent_stop_verify_installer_nosettings_")
    dst3 = pathlib.Path(home3) / ".claude" / "hooks" / "subagent_stop_verify.py"
    rc3, out3, err3 = _run_installer(home3, create_settings=False)
    combined3 = out3 + err3
    if rc3 != 1:
        failures.append(f"INSTALLER missing-settings: expected FAIL-VISIBLE exit 1, got {rc3}. output={combined3!r}")
    if "FATAL" not in combined3:
        failures.append(f"INSTALLER missing-settings: expected a clear FATAL message, got: {combined3!r}")
    if "settings.json" not in combined3:
        failures.append(f"INSTALLER missing-settings: FATAL message does not mention settings.json: {combined3!r}")
    if not dst3.exists():
        failures.append("INSTALLER missing-settings: hook file should still be installed even though registration failed")

    return failures


def test_subagent_stop_verify():
    failures = evaluate()
    assert not failures, "SubagentStop hook guilt+innocence regressions:\n" + "\n".join(failures)


if __name__ == "__main__":
    fails = evaluate()
    if fails:
        print(f"=== {len(fails)} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    print("=== ALL OK (guilt caught, no innocent bitten) ===")
    sys.exit(0)
