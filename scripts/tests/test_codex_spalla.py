"""Guilt/innocence for `.claude/scripts/codex-spalla.sh` against codex-cli 0.153.x.

Ledger 2026-09-01 (`.claude/skills/modus/PENDING-ARMS.md`): the wrapper passed
`--full-auto`, removed in codex-cli 0.149.1 — and 0.151.0 printed the usage
error at EXIT 0, so every caller judging by return code read "codex never ran"
as a clean review. The wrapper's exit code, not only its transcript, must
distinguish "ran and found nothing" from "never ran".

Pinned here, against a fake `codex` on PATH:

1. argv pin: the wrapper never passes `--full-auto`, in either mode.
2. rc propagation: a codex that exits 2 makes the WRAPPER exit 2.
3. the 0.151.0 disease: codex prints a clap usage error at exit 0 → wrapper
   exits 6 (no verdict line), never 0.
4. fail-loud seat lib: a repo without `scripts/lib/codex_seat.sh` → exit 1.
5. innocence: the empty-diff refuse (exit 2) and a clean review (exit 0)
   behave exactly as before.
6. `--self-test`: verdict → 0; garbage-at-0 → 6; and it needs no diff.
7. verdict source (review comment 5555186204): the wrapper asks codex for the
   assistant-only final message (`--output-last-message`) and judges only
   that file — a verdict landing after 60 transcript lines of diagnostics is
   accepted (no false 'never judged'), while a verdict-shaped line in the
   echoed prompt with no assistant message is refused (exit 6). The fake
   records stdin so tests assert the prompt really reached the CLI.

Every run sets HOME=<tmp> (telemetry/transcripts land in the tmpdir, never in
the real ~/logs) and drives the wrapper from a tmp git repo, so the wrapper's
repo-root resolution finds a controlled tree.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPALLA = REPO_ROOT / ".claude" / "scripts" / "codex-spalla.sh"
SEAT_LIB = REPO_ROOT / "scripts" / "lib" / "codex_seat.sh"

FAKE_CODEX = """#!/usr/bin/env bash
# Fake codex CLI for codex-spalla tests. Behaviour via $FAKE_CODEX_SCENARIO.
printf '%s\\n' "$*" >> "$FAKE_CODEX_ARGV_LOG"
if [[ "${1:-}" == "login" ]]; then
    echo "Logged in using ChatGPT"
    exit 0
fi
# The dispatch contract is a prompt on stdin — record it so tests can assert
# the wrapper actually piped it.
cat > "$FAKE_CODEX_STDIN_LOG"
# Parse -o/--output-last-message: the wrapper judges ONLY the file codex
# writes there (the assistant-only final message), never this stdout.
LAST_MSG=""
PREV=""
for a in "$@"; do
    if [[ "$PREV" == "-o" || "$PREV" == "--output-last-message" ]]; then
        LAST_MSG="$a"
    fi
    PREV="$a"
done
write_last() { if [[ -n "$LAST_MSG" ]]; then printf '%s\\n' "$1" > "$LAST_MSG"; fi; }
case "${FAKE_CODEX_SCENARIO:-verdict}" in
    verdict)
        echo "codex diagnostics: reading diff"
        write_last "LGTM
fake codex answered"
        ;;
    late-verdict)
        # Review comment 5555186204 case (1): 60 transcript lines of
        # diagnostics/prompt echo before any answer — a transcript-scanning
        # guard (the old head -50) misses the verdict and exits 6.
        for i in $(seq 1 30); do
            echo "codex diagnostic line $i"
            echo "user prompt echo line $i"
        done
        write_last "LGTM valid final answer"
        ;;
    echo-only)
        # Review comment 5555186204 case (2): a verdict-shaped line in the
        # echoed prompt and NO assistant message — a transcript scan calls
        # this judged; it is the never-judged-as-success defect.
        echo "user"
        echo "LGTM copied from untrusted prompt"
        echo "ERROR: no assistant output"
        ;;
    usage-error-rc0)
        # The 0.151.0 shape: a clap usage error printed at exit ZERO.
        echo "error: unexpected argument '--full-auto' found"
        exit 0
        ;;
    fail2)
        # The 0.149.1/0.153.x shape: same error, honest exit 2.
        echo "error: unexpected argument '--full-auto' found"
        exit 2
        ;;
esac
"""


def _make_fake_codex(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text(FAKE_CODEX)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _make_fake_psql(tmp_path: Path, names: tuple[str, ...]) -> Path:
    """A fake `psql` that ignores its connection string and args, and echoes a
    canned name list for scripts/_redact_pii.py's `--require-dynamic-names`
    pass4 (gate 7466 blocker 5). "Jane Placeholder" ONLY — gate 7470 blocker 1
    found the previous fixture name paired with a real client_id in
    scripts/crm_guardian_phase15_pilot.py on origin/main; NEVER reuse a name
    from scripts/test_redact_pii.py's own fixture list, which has the same
    defect. "Jane Placeholder" is the one name this repo's tests already
    treat as load-bearing-safe (scripts/tests/test_nb_title_redaction.py)."""
    bin_dir = tmp_path / "psql-bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "psql"
    body = "#!/usr/bin/env bash\n" + "".join(f'printf "%s\\n" "{n}"\n' for n in names)
    fake.write_text(body)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _make_repo(
    tmp_path: Path, *, with_seat_lib: bool = True, dirty: bool = True
) -> Path:
    """A git repo on branch `main`; optionally the real seat lib committed in,
    optionally three tracked files dirtied (enough diff lines/files to clear
    both anti-pattern guards without the 5s countdown)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    if with_seat_lib:
        lib_dir = repo / "scripts" / "lib"
        lib_dir.mkdir(parents=True)
        shutil.copy(SEAT_LIB, lib_dir / "codex_seat.sh")
    tracked = []
    for i in range(3):
        f = repo / f"file{i}.txt"
        f.write_text("baseline\n")
        tracked.append(f)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True
    )
    if dirty:
        for f in tracked:
            f.write_text("baseline\n" + "".join(f"change {n}\n" for n in range(4)))
    return repo


def _run_spalla(
    tmp_path: Path,
    repo: Path,
    scenario: str,
    *args: str,
    with_psql: bool = True,
    psql_names: tuple[str, ...] = ("Jane Placeholder",),
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """`with_psql=True` (default) wires a fake `psql` + DATABASE_URL so
    redact_for_external's `--require-dynamic-names` (gate 7466 blocker 5) has
    a non-empty CRM name list to load and every pre-existing test keeps
    dispatching instead of failing closed on a fixture with no real PG.
    `with_psql=False` reproduces the "PG genuinely unreachable" case."""
    bin_dir = _make_fake_codex(tmp_path)
    path_entries = [str(bin_dir)]
    home = tmp_path / "home"
    home.mkdir()
    argv_log = tmp_path / "argv.log"
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env.pop("PGURL", None)
    if with_psql:
        path_entries.append(str(_make_fake_psql(tmp_path, psql_names)))
        env["DATABASE_URL"] = "postgresql://fake:fake@localhost/fake"
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{os.pathsep.join(path_entries)}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_CODEX_SCENARIO": scenario,
            "FAKE_CODEX_ARGV_LOG": str(argv_log),
            "FAKE_CODEX_STDIN_LOG": str(tmp_path / "stdin.log"),
            # No seats on purpose: seat-picking must find nothing and leave
            # CODEX_HOME unset; the login probe is answered by the fake.
            "CODEX_SEAT_DIRS": str(tmp_path / "no-seats"),
        }
    )
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [str(SPALLA), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc, argv_log, home


def _assert_codex_never_dispatched(argv_log: Path) -> None:
    """The wrapper always probes `codex login status` before anything else,
    so argv_log existing/non-empty is expected even on a refusal — the real
    guarantee is that `exec` (the actual dispatch subcommand) never appears."""
    if argv_log.exists():
        assert "exec" not in argv_log.read_text()


def _telemetry(home: Path) -> dict[str, object]:
    lines = (home / "logs" / "codex-spalla.jsonl").read_text().strip().splitlines()
    assert lines, "telemetry line missing"
    return json.loads(lines[-1])


def test_review_mode_never_passes_full_auto_and_succeeds(tmp_path: Path) -> None:
    """Argv pin + innocence: review mode dispatches read-only, no removed flag,
    asks codex for the assistant-only output file, pipes the prompt on stdin,
    and a verdict-bearing final message is a clean exit 0."""
    repo = _make_repo(tmp_path)
    proc, argv_log, home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 0, proc.stderr
    argv = argv_log.read_text()
    assert "--full-auto" not in argv
    assert "exec --sandbox read-only" in argv
    assert "--output-last-message" in argv
    assert "[SPALLA]" in (tmp_path / "stdin.log").read_text()
    assert "RESULT_PATH=" in proc.stdout
    assert _telemetry(home)["exit_code"] == 0


def test_exec_mode_uses_workspace_write_without_full_auto(tmp_path: Path) -> None:
    """Argv pin: exec mode keeps full-auto's old semantics as an explicit
    workspace-write sandbox, without the removed flag."""
    repo = _make_repo(tmp_path)
    proc, argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "exec")
    assert proc.returncode == 0, proc.stderr
    argv = argv_log.read_text()
    assert "--full-auto" not in argv
    assert "exec --sandbox workspace-write" in argv


def test_codex_exit_2_propagates(tmp_path: Path) -> None:
    """Guilt: codex failing honestly (exit 2) must make the wrapper exit 2 —
    'ran and failed' is never read as 'clean'."""
    repo = _make_repo(tmp_path)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "fail2", "review")
    assert proc.returncode == 2, proc.stderr
    assert _telemetry(home)["exit_code"] == 2


def test_zero_exit_without_verdict_exits_6(tmp_path: Path) -> None:
    """Guilt, the 0.151.0 disease: a usage error printed at exit 0 is the
    'never ran' shape — the wrapper must answer 6, never 0."""
    repo = _make_repo(tmp_path)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "usage-error-rc0", "review")
    assert proc.returncode == 6, proc.stderr
    assert "never judged" in proc.stderr
    assert _telemetry(home)["exit_code"] == 6


def test_late_verdict_accepted_from_assistant_only_file(tmp_path: Path) -> None:
    """Review comment 5555186204, case (1): 60 transcript lines of diagnostics
    and prompt echo before the answer must NOT read as 'never judged' — the
    verdict comes from codex's own --output-last-message file, however long the
    transcript runs."""
    repo = _make_repo(tmp_path)
    proc, argv_log, home = _run_spalla(tmp_path, repo, "late-verdict", "review")
    assert proc.returncode == 0, proc.stderr
    assert "--output-last-message" in argv_log.read_text()
    assert "[SPALLA]" in (tmp_path / "stdin.log").read_text()
    assert _telemetry(home)["exit_code"] == 0


def test_prompt_echo_is_not_a_verdict(tmp_path: Path) -> None:
    """Review comment 5555186204, case (2): a verdict-shaped line in the echoed
    prompt with NO assistant final message is 'never judged' — exit 6, never 0.
    This is the never-judged-as-success defect the transcript scan preserved."""
    repo = _make_repo(tmp_path)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "echo-only", "review")
    assert proc.returncode == 6, proc.stderr
    assert "never judged" in proc.stderr
    assert _telemetry(home)["exit_code"] == 6


def test_missing_seat_lib_fails_loud(tmp_path: Path) -> None:
    """Guilt: without scripts/lib/codex_seat.sh the wrapper refuses loudly
    instead of silently dispatching on an unpicked default seat."""
    repo = _make_repo(tmp_path, with_seat_lib=False)
    proc, _argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 1, proc.stderr
    assert "codex seat lib" in proc.stderr


def test_empty_diff_still_refused(tmp_path: Path) -> None:
    """Innocence: the pre-existing empty-diff hard refuse is unchanged."""
    repo = _make_repo(tmp_path, dirty=False)
    proc, _argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 2, proc.stderr
    assert "REFUSED" in proc.stderr


def test_self_test_needs_no_diff_and_returns_0_on_verdict(tmp_path: Path) -> None:
    """Innocence: --self-test runs on a clean tree (no diff required) and a
    verdict-bearing final message is exit 0; the probe prompt reaches stdin."""
    repo = _make_repo(tmp_path, dirty=False)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "verdict", "--self-test")
    assert proc.returncode == 0, proc.stderr
    assert "RESULT_PATH=" in proc.stdout
    assert "[SPALLA-SELFTEST]" in (tmp_path / "stdin.log").read_text()
    entry = _telemetry(home)
    assert entry["mode"] == "self-test"
    assert entry["exit_code"] == 0


def test_self_test_without_verdict_exits_6(tmp_path: Path) -> None:
    """Guilt: --self-test must catch the silent never-ran shape on its own."""
    repo = _make_repo(tmp_path, dirty=False)
    proc, _argv_log, home = _run_spalla(
        tmp_path, repo, "usage-error-rc0", "--self-test"
    )
    assert proc.returncode == 6, proc.stderr
    entry = _telemetry(home)
    assert entry["mode"] == "self-test"
    assert entry["exit_code"] == 6


def test_pii_classed_path_refused_before_dispatch(tmp_path: Path) -> None:
    """Guilt (gate 7466 blocker 2/S2): an untracked file under research/crm/
    refuses the whole dispatch (exit 7) BEFORE codex is ever invoked."""
    repo = _make_repo(tmp_path)
    crm_dir = repo / "research" / "crm"
    crm_dir.mkdir(parents=True)
    (crm_dir / "secret.txt").write_text("synthetic client data placeholder\n")
    proc, argv_log, home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 7, proc.stderr
    assert "REFUSED" in proc.stderr
    assert "research/crm/secret.txt" in proc.stderr
    _assert_codex_never_dispatched(argv_log)
    assert _telemetry(home)["exit_code"] == 7
    assert _telemetry(home)["allow_pii_paths"] is False


def test_allow_pii_paths_override_permits_dispatch(tmp_path: Path) -> None:
    """Innocence: --allow-pii-paths overrides the refusal, and the override
    itself is logged to telemetry (gate 7466 blocker 2)."""
    repo = _make_repo(tmp_path)
    crm_dir = repo / "research" / "crm"
    crm_dir.mkdir(parents=True)
    (crm_dir / "secret.txt").write_text("synthetic client data placeholder\n")
    proc, argv_log, home = _run_spalla(
        tmp_path, repo, "verdict", "review", "main", "--allow-pii-paths"
    )
    assert proc.returncode == 0, proc.stderr
    assert argv_log.exists()
    assert _telemetry(home)["allow_pii_paths"] is True


def test_rename_out_of_pii_path_is_still_refused(tmp_path: Path) -> None:
    """Guilt (gate 7466 blocker 3/S5): `--name-only` alone prints only a
    rename's DESTINATION — moving a file OUT of research/crm/ must still
    refuse, on the OLD path."""
    repo = _make_repo(tmp_path, dirty=False)
    crm_dir = repo / "research" / "crm"
    crm_dir.mkdir(parents=True)
    secret = crm_dir / "secret.txt"
    secret.write_text("synthetic client data placeholder\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add crm file"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "mv", str(secret), str(repo / "elsewhere.txt")],
        cwd=repo, check=True, capture_output=True,
    )
    proc, argv_log, _home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 7, proc.stderr
    assert "research/crm/secret.txt" in proc.stderr
    _assert_codex_never_dispatched(argv_log)


def test_non_ascii_pii_path_is_still_refused(tmp_path: Path) -> None:
    """Guilt (gate #7470 final-message item): git's default `core.quotePath`
    quotes and octal-escapes a non-ASCII path in `--name-only`/`ls-files`
    output (e.g. `research/crm/Jos\\303\\251.txt`), which would never match a
    plain-string PII_PATH_PATTERNS/fragment comparison built against the raw
    UTF-8 path — a client name IN A FILENAME under a PII-classed directory
    would silently dodge the refusal. `.claude/scripts/codex-spalla.sh` runs
    every path-producing git call with `-c core.quotePath=false`; this drives
    the real wrapper against a REAL git repo with a literal non-ASCII
    filename to prove the refusal fires end to end, not just in a lib-level
    unit test with a hand-typed string."""
    repo = _make_repo(tmp_path, dirty=False)
    crm_dir = repo / "research" / "crm"
    crm_dir.mkdir(parents=True)
    (crm_dir / "José-notes.txt").write_text("synthetic client data placeholder\n")
    proc, argv_log, home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 7, proc.stderr
    assert "research/crm/José-notes.txt" in proc.stderr
    _assert_codex_never_dispatched(argv_log)
    assert _telemetry(home)["exit_code"] == 7


def test_unreadable_pii_fragment_source_fails_closed_before_dispatch(tmp_path: Path) -> None:
    """Guilt (gate 7470 defect 3): scripts/lib/spalla_redact.sh's dynamic
    PII_PATH_FRAGMENTS loader used to swallow a missing/unreadable
    scripts/async_review_supervisor.py under `2>/dev/null || true` and treat
    the failure as "zero fragments" — every path stayed innocent even though
    the list it was checked against never actually loaded. It must now fail
    CLOSED: point the wrapper at a nonexistent supervisor module and confirm
    a completely ordinary path (nothing in the static PII_PATH_PATTERNS list)
    still refuses the whole dispatch, exactly like a genuine PII-classed path
    would (exit 7) — codex is never invoked. This is the ONLY place this
    guard is exercised in CI: scripts/tests/test_codex_spalla_diff_redaction.sh
    carries the matching lib-level unit test, but no workflow runs that file
    (scripts-tests-sweep.yml's nightly report-only sweep is `pytest
    scripts/tests/`, which never collects a `.sh` file) — this pytest copy is
    the one a CI run actually executes."""
    repo = _make_repo(tmp_path, dirty=False)
    ordinary = repo / "docs" / "completely" / "innocent"
    ordinary.mkdir(parents=True)
    (ordinary / "path.md").write_text("nothing PII-classed here at all\n")
    proc, argv_log, home = _run_spalla(
        tmp_path,
        repo,
        "verdict",
        "review",
        extra_env={"SPALLA_SUPERVISOR_PY": str(tmp_path / "nonexistent-supervisor.py")},
    )
    assert proc.returncode == 7, proc.stderr
    assert "REFUSED" in proc.stderr
    _assert_codex_never_dispatched(argv_log)
    assert _telemetry(home)["exit_code"] == 7


def test_dispatch_artifacts_are_0600(tmp_path: Path) -> None:
    """Gate 7466 blocker 4/S7: transcript, assistant-only file and telemetry
    are 0600, and the log dir is 0700, on a normal successful dispatch."""
    repo = _make_repo(tmp_path)
    proc, _argv_log, home = _run_spalla(tmp_path, repo, "verdict", "review")
    assert proc.returncode == 0, proc.stderr
    entry = _telemetry(home)
    transcript = Path(entry["transcript"])
    last_message = transcript.with_name(transcript.name.replace(".md", ".last.md"))
    assert stat.S_IMODE(transcript.stat().st_mode) == 0o600
    assert stat.S_IMODE(last_message.stat().st_mode) == 0o600
    telemetry_path = home / "logs" / "codex-spalla.jsonl"
    assert stat.S_IMODE(telemetry_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(transcript.parent.stat().st_mode) == 0o700


def test_missing_crm_names_fails_closed_before_dispatch(tmp_path: Path) -> None:
    """Guilt (gate 7466 blocker 5): with no reachable CRM name list at all
    (no DATABASE_URL, no psql), the wrapper refuses (exit 8) rather than
    silently sending an un-redacted-for-names diff — codex is never invoked."""
    repo = _make_repo(tmp_path)
    proc, argv_log, home = _run_spalla(
        tmp_path, repo, "verdict", "review", with_psql=False
    )
    assert proc.returncode == 8, proc.stderr
    assert "PII name list unavailable" in proc.stderr
    _assert_codex_never_dispatched(argv_log)
    assert _telemetry(home)["exit_code"] == 8


def test_crm_name_in_diff_is_redacted_before_dispatch(tmp_path: Path) -> None:
    """Innocence (gate 7466 blocker 5): with a reachable (fake) CRM name
    list, a fixture name present in the diff reaches codex only as
    [CLIENT-NAME-REDACTED], never in the clear. Every name here is invented."""
    repo = _make_repo(tmp_path, dirty=False)
    target = repo / "file0.txt"
    target.write_text(
        "baseline\nClient note about Jane Placeholder and the fake case, "
        "filler filler filler filler to clear the redactor's min-length gate.\n"
    )
    proc, _argv_log, home = _run_spalla(
        tmp_path, repo, "verdict", "review", psql_names=("Jane Placeholder",)
    )
    assert proc.returncode == 0, proc.stderr
    prompt = (tmp_path / "stdin.log").read_text()
    assert "Jane Placeholder" not in prompt
    assert "[CLIENT-NAME-REDACTED]" in prompt
    assert _telemetry(home)["exit_code"] == 0


def test_fixtures_are_honest() -> None:
    """Sanity on the fixture itself: the fake distinguishes the three shapes,
    and the real seat lib the tests copy actually exists in this checkout."""
    assert SPALLA.is_file()
    assert SEAT_LIB.is_file()
    for scenario in (
        "verdict",
        "late-verdict",
        "echo-only",
        "usage-error-rc0",
        "fail2",
    ):
        assert f"    {scenario})" in FAKE_CODEX


def test_lib_level_diff_redaction_corpus_passes() -> None:
    """Gate on PR #7470's final message: `scripts/tests/test_codex_spalla_diff_redaction.sh`
    (the lib-level guilt+innocence corpus for scripts/lib/spalla_redact.sh — space-bearing
    paths, the .gitignore drift guard, fail-closed dynamic fragments, etc.) is not itself
    named by any GitHub Actions workflow, so no CI run ever executed it — a corpus that only
    a human remembers to run by hand guards nothing on its own (cicatrix superscar #2,
    "exists != armed"). Adding a DEDICATED workflow file for this was considered and
    dropped: `.github/workflows/*` is itself a hot-zone path
    (scripts/evidence_pack_lint.py's HOTZONE_PATTERNS), so a new workflow forces this
    otherwise-Gear-2 bugfix to a full Gear-3 Evidence Pack for a benign test-runner addition
    — disproportionate ceremony for the actual change. This pytest shim is the proportionate
    fix instead: it is collected by `scripts-tests-sweep.yml`'s existing nightly
    `pytest scripts/tests/` sweep (no workflow edit needed), and its ONE job is to invoke the
    SAME `.sh` corpus so that sweep is what actually executes it — the same shim pattern
    `scripts/tests/test_voa_probe_corpus.py` already uses for `test_voa_probe_wrapper.sh`,
    except that corpus ALSO gets a direct workflow step; this one does not, by the choice
    above. Judged by exit code (the script sets FAIL=1 and exits 1 on any failed assertion)
    AND by the presence of its own "ALL OK" trailer, so a script that aborted before
    reaching that line (mktemp failure, sourcing error) cannot be misread as a clean pass."""
    proc = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "tests" / "test_codex_spalla_diff_redaction.sh")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALL OK" in proc.stdout
