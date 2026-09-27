"""Test for `recover_delta()` in infra/launchagents/wrappers/regulatory-watcher-run.sh.

Context (task #68, 2026-07-27): a manually-produced, COMPLETE regulatory delta for
2026-07-25 sat for two days under `.worktrees/regulatory-watcher-2026-07-25/research/
regulatory/`, renamed to `2026-07-25-delta.json.manual-session-DO-NOT-RECOVER`
specifically to defeat `recover_delta()`'s exact-name glob — and nothing in the log
said so. The fix adds a near-miss detector: files under `.worktrees/*/research/
regulatory/` that mention today's date but do not match the exact expected basename
get LOGGED (not auto-recovered — an unverified rename could be untrustworthy content)
so the evasion leaves a trace instead of being indistinguishable from a quiet day.

Context (PR #7515 gate REWORK-BUILD on head 7753eac1, 2026-09-27): the first cut of
the tier-1 scratch-path recovery (added to fix a DIFFERENT bug — worktree_isolation.py
blocking a direct write into the tracked checkout) did a blind `cp` from a
world-writable, predictable `/tmp` path straight into `DELTA_JSON`, which
`promote_delta_via_pr()` then commits/pushes/auto-merges into the PUBLIC repo. The
gate proved live, using this exact commit's own functions, that a markdown file, a
schema-invalid JSON object, and a symlink to a canary secrets file were all promoted
(rc=0, canary content copied) — only `partial:true` was rejected. The cure: the
scratch path moved to a private (0700) directory under `$HOME` (defense layer 1,
not exercised by this test — it is a directory-permission property, not a function
behavior), and `recover_delta()` itself refuses a symlink or a file it does not own
BEFORE reading anything, then promotes ONLY through `extract_delta_from_output()`'s
schema check + re-serialization (never a byte-for-byte copy), with `delta_is_partial()`
hardened to a three-way exit code (0=partial, 1=confirmed valid, 2=invalid/unparsable)
so a `partial:true` delta and a `partial:false` delta and un-parseable garbage are
never conflated (defense layer 2, exercised below).

Isolation: the whole script is NOT sourced (its top-level does a live TCC probe, a
lock-file dance and an LLM cascade). `recover_delta()` now calls two sibling
functions (`extract_delta_from_output`, `delta_is_partial`), both also extracted by
marker and sourced into the same throwaway zsh driver alongside it — same "test the
real functions in isolation" approach the Python hook tests in infra/claude-hooks/
use via importlib, applied to the zsh side.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "regulatory-watcher-run.sh"

# Ownership ([ -O ]) is checked in the wrapper's code but is not exercised here: a
# hermetic test running as a single OS user cannot manufacture a file it does not
# own without root, and mocking the shell's own `[ -O ]` test operator is not
# meaningfully different from asserting the literal source line is present — done
# separately below as a static assertion, not a behavioral one.
_FUNC_NAMES = ("recover_delta", "extract_delta_from_output", "delta_is_partial")


def _extract_functions() -> str:
    text = _WRAPPER.read_text(encoding="utf-8")
    bodies = []
    for name in _FUNC_NAMES:
        pattern = re.compile(rf"\n{re.escape(name)}\(\) \{{.*?\n\}}\n", re.DOTALL)
        m = pattern.search(text)
        assert m, f"{name}() function not found in the wrapper — anchor drifted"
        bodies.append(m.group(0))
    return "".join(bodies)


def test_ownership_check_is_present_in_source() -> None:
    """Static guard: `[ -O ]` (this-process-owns-the-file) must be checked before
    `recover_delta()` ever reads the scratch file's content. Not independently
    exercised behaviorally above — see the module docstring's ownership note.
    """
    text = _WRAPPER.read_text(encoding="utf-8")
    m = re.compile(r"\nrecover_delta\(\) \{.*?\n\}\n", re.DOTALL).search(text)
    assert m, "recover_delta() function not found in the wrapper — anchor drifted"
    assert "[ ! -O \"$DELTA_SCRATCH\" ]" in m.group(0)


def test_codex_tier_uses_an_explicit_env_allowlist_not_the_inherited_environment() -> None:
    """Static guard for PR #7515's Blocker 2 (gate finding on head c59dad25,
    2026-09-27): the wrapper's `set -a; source ~/.nuzantara-secrets.env` above
    exports ~27 vars (DATABASE_URL, REDIS_PASSWORD, GOOGLE_APPLICATION_
    CREDENTIALS, ZOHO_*, NUZANTARA_API_KEY, ...) into its OWN shell, and the
    codex tier's untrusted-content shell tool now has real network egress
    (this same PR) — a prompt-injection surface that could exfiltrate any of
    them to an arbitrary host if they reached that shell's environment.

    `-c shell_environment_policy.inherit=core` (the gate's first-suggested
    cure) was tested live on Pro and found INEFFECTIVE, as were `=none` and
    `-c allow_login_shell=false` (which additionally broke the TELEGRAM_* vars
    this tier needs): none of them stop codex's `exec` shell tool from
    re-applying GITHUB_PERSONAL_ACCESS_TOKEN (exported at this account's
    `~/.zshrc:9`) and STARSHIP_SESSION_KEY (from `starship init`) through
    codex's own interactive SHELL SNAPSHOT feature. The verified-effective
    fix is three-layered: `env -i` plus an explicit small allowlist (HOME,
    PATH, the seat's CODEX_HOME, and only the two TELEGRAM_* vars this
    tier's prompt uses to alert) so none of the `.nuzantara-secrets.env`
    names reach the child's `env`, PLUS `-c features.shell_snapshot=false`
    so codex does not re-apply the shell-snapshot-sourced names on top —
    which, verified live, ALSO drops the allowlist's own TELEGRAM_* vars,
    so `-c shell_environment_policy.inherit=all` is required alongside it
    (with the snapshot off, `inherit` is the only thing governing what of
    codex's now-minimal own process env reaches the shell tool).

    Guilt: reverting the invocation to the pre-fix `env "${CODEX_SEAT_ENV[@]}"`
    (full inherited environment) makes this test fail, since that string would
    no longer be paired with `env -i` and the block would still carry the
    unrestricted call the assertions below reject.
    """
    text = _WRAPPER.read_text(encoding="utf-8")
    start = text.index("# Tier 3: Codex GPT-5.5")
    end = text.index("\nfi\n", start)
    block = text[start:end]
    # Code-only view (drops comment lines) for the name-allowlist checks below —
    # this function's own docstring/inline comments legitimately NAME the leaked
    # secrets and the old vulnerable call as prose, which must not self-fail.
    code_block = "\n".join(
        line for line in block.splitlines() if not line.strip().startswith("#")
    )

    assert 'env -i "${CODEX_ENV_ALLOWLIST[@]}"' in block, (
        "codex tier must launch through `env -i` plus an explicit allowlist array "
        "— not the wrapper's inherited environment"
    )
    assert "-c features.shell_snapshot=false" in code_block, (
        "codex's interactive shell-snapshot feature re-applies ~/.zshrc/starship "
        "exports (GITHUB_PERSONAL_ACCESS_TOKEN, STARSHIP_SESSION_KEY) on top of "
        "the env -i allowlist regardless of shell_environment_policy — must be "
        "disabled for this call"
    )
    assert "-c shell_environment_policy.inherit=all" in code_block, (
        "shell_snapshot=false ALONE also drops this allowlist's own "
        "TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID (verified live) — with the "
        "snapshot disabled, inherit=all is required for codex to pass its own "
        "(env -i-minimal) process env through to the shell tool at all"
    )
    assert 'env "${CODEX_SEAT_ENV[@]}" \\\n' not in code_block, (
        "the pre-fix CALL SITE (`env \"${CODEX_SEAT_ENV[@]}\"` immediately preceding "
        "the codex binary, no `-i`) hands codex this wrapper's ENTIRE environment, "
        "including every .nuzantara-secrets.env var — must not reappear (a mention "
        "of the old string in an explanatory comment is fine; the call site is not)"
    )
    for leaked_name in (
        "DATABASE_URL",
        "REDIS_PASSWORD",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ZOHO_CLIENT_SECRET",
        "NUZANTARA_API_KEY",
        "HEALTHCHECK_PIN",
    ):
        assert leaked_name not in code_block, (
            f"{leaked_name} must never be named inside the codex-tier block's CODE — "
            "it is not on the explicit allowlist and has no reason to be"
        )
    for allowed_name in ("HOME=", "PATH=", "TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_CHAT_ID"):
        assert allowed_name in code_block, f"expected allowlist entry {allowed_name!r} missing"


def _run(
    tmp_path: Path,
    date: str,
    extra_files: dict[str, str],
    scratch_content: str | None = None,
    scratch_symlink_to: str | None = None,
) -> tuple[int, str, str]:
    """Set up `$HOME/nuzantara/.worktrees/*/research/regulatory/` per `extra_files`
    (relative path -> content) and call `recover_delta` for `date`. `scratch_content`,
    when given, is written to the tier-1 scratch path (`$DELTA_SCRATCH`) before the
    call. `scratch_symlink_to`, when given, makes `$DELTA_SCRATCH` a symlink to that
    absolute path instead (mutually exclusive with `scratch_content`). Returns
    (returncode, log contents, DELTA_JSON contents-or-empty).
    """
    assert not (scratch_content is not None and scratch_symlink_to is not None)
    home = tmp_path / "home"
    for rel, content in extra_files.items():
        p = home / "nuzantara" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    log = tmp_path / "watcher.log"
    delta_json = tmp_path / f"{date}-delta.json"
    delta_scratch = tmp_path / f"scratch-{date}-delta.json"
    if scratch_content is not None:
        delta_scratch.write_text(scratch_content, encoding="utf-8")
    elif scratch_symlink_to is not None:
        delta_scratch.symlink_to(scratch_symlink_to)
    (home / "nuzantara").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=home / "nuzantara", capture_output=True)

    driver = tmp_path / "driver.sh"
    driver.write_text(
        "#!/bin/zsh\n"
        f"HOME={home}\n"
        f'DATE="{date}"\n'
        f'DELTA_BASENAME="{date}-delta.json"\n'
        f'DELTA_JSON="{delta_json}"\n'
        f'DELTA_SCRATCH="{delta_scratch}"\n'
        f'LOG="{log}"\n'
        f'PYBIN="{sys.executable}"\n'
        + _extract_functions()
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


# ---------------------------------------------------------------------------
# Scratch-path recovery: hardened per PR #7515 gate REWORK-BUILD (head 7753eac1).
# One INNOCENCE case (a genuine, complete, schema-valid, non-partial delta) and
# four GUILT cases (non-JSON, symlink, schema-invalid, partial:true) — every
# GUILT case must promote nothing and return nonzero with a named reason.
# ---------------------------------------------------------------------------

_VALID_DELTA = json.dumps(
    {
        "run_at": "2026-09-27T07:00:00+08:00",
        "today": "2026-09-27",
        "new_today_count": 0,
        "partial": False,
        "unreachable_sources": [],
        "sources_checked_no_delta": [],
        "nb_query_errors": [],
        "deltas": [],
        "seen_citations": [],
    }
)


def test_scratch_file_is_recovered_and_removed(tmp_path) -> None:
    """INNOCENCE: a genuine, complete, schema-valid, non-partial delta at the
    scratch path is promoted into DELTA_JSON (as the SAME JSON value — re-
    serialized via `extract_delta_from_output`'s `json.dump`, so formatting may
    differ but the data must not) and the scratch copy is removed so a stale
    file can't be replayed on a later run.

    Regression note: this test previously asserted the FLAW the gate found — its
    payload (`{"real":true,"new_today_count":0}`) has no `deltas` key and would
    now be correctly REJECTED as schema-invalid. Replaced with a fully schema-
    valid payload; the schema-invalid shape is now its own GUILT test below.
    """
    rc, log, delta = _run(
        tmp_path,
        "2026-09-27",
        extra_files={},
        scratch_content=_VALID_DELTA + "\n",
    )
    assert rc == 0
    assert "recovered delta from tier-1 scratch file" in log
    assert json.loads(delta) == json.loads(_VALID_DELTA)
    assert not (tmp_path / "scratch-2026-09-27-delta.json").exists()
    # the scratch path takes precedence — the worktree-glob paths must not also fire.
    assert "W81-fix" not in log
    assert "W105-#68" not in log


def test_no_scratch_file_falls_through_unchanged(tmp_path) -> None:
    """INNOCENCE: an ordinary run where tier 1 never touched the scratch path (any
    other tier, or no run at all) must behave exactly as before the scratch-path
    addition — no false "recovered" line, no crash on the now-referenced variable.
    """
    rc, log, delta = _run(tmp_path, "2026-09-27", extra_files={}, scratch_content=None)
    assert rc == 1
    assert "recovered delta from tier-1 scratch file" not in log
    assert delta == ""


def test_scratch_non_json_is_refused(tmp_path) -> None:
    """GUILT: a markdown/prose file at the scratch path (no parseable `{..}` object
    matching the delta schema anywhere in it) — one of the three shapes the gate
    proved were promoted rc=0 pre-fix. Must be refused, nothing promoted."""
    rc, log, delta = _run(
        tmp_path,
        "2026-09-27",
        extra_files={},
        scratch_content="# Not a delta\n\nJust some prose, no JSON object at all.\n",
    )
    assert rc == 1
    assert delta == ""
    assert "REFUSED" in log
    assert "not parseable JSON matching the delta schema" in log


def test_scratch_symlink_is_refused_without_reading_target(tmp_path) -> None:
    """GUILT: the scratch path is a symlink to a canary secrets-shaped file — the
    exact shape the gate used to prove a canary secret could be promoted into the
    PUBLIC repo. Must be refused BEFORE the target is ever read: the canary's
    content must never appear in DELTA_JSON or the log."""
    canary = tmp_path / "canary-secret.txt"
    canary.write_text('{"new_today_count": 0, "deltas": [], "TOTALLY_A_SECRET": "canary-do-not-leak"}\n', encoding="utf-8")
    rc, log, delta = _run(
        tmp_path,
        "2026-09-27",
        extra_files={},
        scratch_symlink_to=str(canary),
    )
    assert rc == 1
    assert delta == ""
    assert "REFUSED" in log
    assert "is a symlink" in log
    assert "TOTALLY_A_SECRET" not in log
    assert "canary-do-not-leak" not in log


def test_scratch_schema_invalid_missing_deltas_key_is_refused(tmp_path) -> None:
    """GUILT: valid JSON, but missing the required `deltas` key — the second shape
    the gate proved was promoted rc=0 pre-fix (`{"hello":"world"}` in the gate's
    own reproduction; this uses a closer near-miss that even has the OTHER
    required key, to prove the check is a real AND, not an OR)."""
    rc, log, delta = _run(
        tmp_path,
        "2026-09-27",
        extra_files={},
        scratch_content='{"new_today_count": 0}\n',
    )
    assert rc == 1
    assert delta == ""
    assert "REFUSED" in log
    assert "not parseable JSON matching the delta schema" in log


def test_scratch_partial_true_is_refused(tmp_path) -> None:
    """GUILT: a schema-VALID delta that honestly admits `partial:true` — the one
    shape the pre-fix code already rejected correctly. Kept as a regression test:
    `recover_delta()` must still reject it after the schema-validation rewrite,
    now via an explicit rc==0 branch on `delta_is_partial` rather than the old
    unconditional-cp-then-let-the-caller-decide shape."""
    partial_delta = json.loads(_VALID_DELTA)
    partial_delta["partial"] = True
    rc, log, delta = _run(
        tmp_path,
        "2026-09-27",
        extra_files={},
        scratch_content=json.dumps(partial_delta) + "\n",
    )
    assert rc == 1
    assert delta == ""
    assert "REFUSED" in log
    assert "partial:true" in log
