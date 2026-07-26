"""Test for `recover_delta()` in infra/launchagents/wrappers/regulatory-watcher-run.sh.

Context (task #68, 2026-07-27): a manually-produced, COMPLETE regulatory delta for
2026-07-25 sat for two days under `.worktrees/regulatory-watcher-2026-07-25/research/
regulatory/`, renamed to `2026-07-25-delta.json.manual-session-DO-NOT-RECOVER`
specifically to defeat `recover_delta()`'s exact-name glob — and nothing in the log
said so. The fix adds a near-miss detector: files under `.worktrees/*/research/
regulatory/` that mention today's date but do not match the exact expected basename
get LOGGED (not auto-recovered — an unverified rename could be untrustworthy content)
so the evasion leaves a trace instead of being indistinguishable from a quiet day.

Isolation: the whole script is NOT sourced (its top-level does a live TCC probe, a
lock-file dance and an LLM cascade). Only the `recover_delta` function body is
extracted by marker and sourced into a throwaway zsh driver with a fake `$HOME` —
same "test one function in isolation" approach the Python hook tests in
infra/claude-hooks/ use via importlib, applied to the zsh side.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "regulatory-watcher-run.sh"

_FUNC_RE = re.compile(r"\nrecover_delta\(\) \{.*?\n\}\n", re.DOTALL)


def _extract_recover_delta() -> str:
    text = _WRAPPER.read_text(encoding="utf-8")
    m = _FUNC_RE.search(text)
    assert m, "recover_delta() function not found in the wrapper — anchor drifted"
    return m.group(0)


def _run(tmp_path: Path, date: str, extra_files: dict[str, str]) -> tuple[int, str, str]:
    """Set up `$HOME/nuzantara/.worktrees/*/research/regulatory/` per `extra_files`
    (relative path -> content) and call `recover_delta` for `date`. Returns
    (returncode, log contents, DELTA_JSON contents-or-empty).
    """
    home = tmp_path / "home"
    for rel, content in extra_files.items():
        p = home / "nuzantara" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    log = tmp_path / "watcher.log"
    delta_json = tmp_path / f"{date}-delta.json"
    (home / "nuzantara").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=home / "nuzantara", capture_output=True)

    driver = tmp_path / "driver.sh"
    driver.write_text(
        "#!/bin/zsh\n"
        f"HOME={home}\n"
        f'DATE="{date}"\n'
        f'DELTA_BASENAME="{date}-delta.json"\n'
        f'DELTA_JSON="{delta_json}"\n'
        f'LOG="{log}"\n'
        + _extract_recover_delta()
        + "\nrecover_delta\n"
        "exit $?\n",
        encoding="utf-8",
    )
    proc = subprocess.run(["zsh", str(driver)], capture_output=True, text=True, timeout=15)
    log_text = log.read_text(encoding="utf-8") if log.exists() else ""
    delta_text = delta_json.read_text(encoding="utf-8") if delta_json.exists() else ""
    return proc.returncode, log_text, delta_text


def test_no_hit_no_near_miss_logs_nothing(tmp_path) -> None:
    """INNOCENCE: an ordinary quiet day (nothing under .worktrees/ at all) must not
    print a W105-#68 line — that would be a false near-miss alarm on every clean run.
    """
    rc, log, delta = _run(tmp_path, "2026-07-25", extra_files={})
    assert rc == 1
    assert "W105-#68" not in log
    assert delta == ""


def test_exact_match_still_recovers_unchanged(tmp_path) -> None:
    """GUILT/regression: the pre-existing exact-name recovery path must be untouched
    by the near-miss addition — this is the behavior task #64/#3244 already relies on.
    """
    rc, log, delta = _run(
        tmp_path,
        "2026-07-26",
        extra_files={".worktrees/some-lane/research/regulatory/2026-07-26-delta.json": '{"real":true}\n'},
    )
    assert rc == 0
    assert "W81-fix: recovered delta from worktree file" in log
    assert delta.strip() == '{"real":true}'
    # the near-miss path must not ALSO fire when the exact match already returned.
    assert "W105-#68" not in log


def test_near_miss_glob_is_scoped_to_worktrees_dir(tmp_path) -> None:
    """INNOCENCE, scope check: the near-miss glob only looks under
    `.worktrees/*/research/regulatory/` (mirroring the exact-match glob above it) —
    a same-date file living directly under `research/regulatory/` (the ordinary,
    already-on-main location) must NOT trigger a W105-#68 line. That path is not a
    stranded/quarantined candidate; it is either already captured or none of
    recover_delta()'s business.
    """
    rc, log, delta = _run(
        tmp_path,
        "2026-07-25",
        extra_files={
            "research/regulatory/2026-07-25-delta.json"
            ".manual-session-DO-NOT-RECOVER": '{"real":true,"quarantined":true}\n'
        },
    )
    assert rc == 1
    assert "W105-#68" not in log
    assert delta == ""


def test_near_miss_under_worktree_shaped_dir_is_logged(tmp_path) -> None:
    """The real incident shape: `.worktrees/<name>/research/regulatory/<date>-delta
    .json.manual-session-DO-NOT-RECOVER` — a directory that is not even a registered
    git worktree, per task #68's guard finding. `recover_delta()` globs by
    filesystem shape only (no `git worktree list` check), so it should already see
    into it; the fix is making it SPEAK when what it sees does not match."""
    rc, log, delta = _run(
        tmp_path,
        "2026-07-25",
        extra_files={
            ".worktrees/regulatory-watcher-2026-07-25/research/regulatory/"
            "2026-07-25-delta.json.manual-session-DO-NOT-RECOVER": '{"real":true,"quarantined":true}\n'
        },
    )
    assert rc == 1  # never auto-recovered — content is unverified by shape alone
    assert delta == ""  # DELTA_JSON must stay empty, not silently populated
    assert "W105-#68" in log
    assert "2026-07-25-delta.json.manual-session-DO-NOT-RECOVER" in log
    assert "NOT auto-recovered" in log
