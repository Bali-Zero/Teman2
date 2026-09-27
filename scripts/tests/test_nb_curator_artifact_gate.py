"""Guilt + innocence for the nb-curator artifact gate, and a fake-world proof
that the wrapper actually WIRES it (W107: a cure you only wrote is not a cure
you armed — run it in a fake world and watch it bite).

The unit half pins the gate's five verdicts. The wrapper half runs the REAL
`scripts/nb-curator-daily.sh` with $HOME redirected to tmp and a fake brain
planted at $HOME/.local/bin/agy, so the whole "brain -> artifact -> alarm ->
exit code" chain executes without one live nlm call, one Telegram, or one token.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "scripts/nb_curator_artifact_gate.py"
WRAPPER = REPO / "scripts/nb-curator-daily.sh"

BODY = "# NB Arsenal Health Report — 2026-07-27\n\n## Health Summary\n- Total: 58 notebooks\n"
MANDATED = (
    "---\nadversarial_review: exempt-machine-report # nb-curator daily health "
    "snapshot (generated artifact, not a research deliverable)\n---\n"
)

MISSING, REFUSED, NEEDS_FIX = 3, 4, 5

# The wrapper runs the gate under /usr/bin/python3 (Pro has PyYAML there; M5 does not).
# Without PyYAML the redactor cannot load and the gate must REFUSE — so the fake-world
# happy path is asserted where the redactor can run, and the refusal where it cannot.
SYSTEM_PY_HAS_YAML = (
    Path("/usr/bin/python3").exists()
    and subprocess.run(["/usr/bin/python3", "-c", "import yaml"], capture_output=True).returncode == 0
)


def _run_gate(report: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), "--report", str(report), *extra],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def _r1_verdict(report: Path) -> subprocess.CompletedProcess:
    """Ask the REAL required CI gate, not our idea of it.

    `--files` is mandatory (a bare positional exits 2 = argparse usage error,
    which is NOT a rejection — an early draft of this test read that 2 as "R1
    rejects it" and its preconditions passed for the wrong reason). And every
    fixture MUST live under a path containing `research/`: `is_in_scope` silently
    passes anything else, so a fixture outside it would make these assertions
    green without the gate ever looking at the file.
    """
    assert "research" in report.parts, "fixture is out of R1 scope — the check would be vacuous"
    return subprocess.run(
        [sys.executable, str(REPO / "scripts/check_adversarial_review.py"), "--files", str(report)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def _report(tmp_path: Path, name: str) -> Path:
    """A fixture path R1 actually considers in scope."""
    d = tmp_path / "research" / "nb-health"
    d.mkdir(parents=True, exist_ok=True)
    return d / name


# --------------------------------------------------------------- GUILT (unit)


def test_absent_report_is_a_failure_not_a_shrug(tmp_path):
    """The disease in one line: the brain printed SUMMARY, wrote nothing, and the
    old wrapper called that OK."""
    proc = _run_gate(_report(tmp_path, "2026-07-27-health.md"), "--fix")
    assert proc.returncode == MISSING
    assert "ARTIFACT MISSING" in proc.stderr
    assert "2026-07-27-health.md" in proc.stderr


def test_empty_report_is_a_failure(tmp_path):
    report = _report(tmp_path, "r.md")
    report.write_text("\n   \n", encoding="utf-8")
    proc = _run_gate(report, "--fix")
    assert proc.returncode == MISSING
    assert "ARTIFACT EMPTY" in proc.stderr


def test_report_without_frontmatter_is_repaired_and_then_passes_the_real_r1_gate(tmp_path):
    """The measured 2026-07-27 case: report written, no frontmatter, PR #3254
    merged with the required R1 check red."""
    report = _report(tmp_path, "2026-07-27-curation.md")
    report.write_text(BODY, encoding="utf-8")

    assert _r1_verdict(report).returncode != 0, "precondition: R1 must reject it before the fix"

    proc = _run_gate(report, "--fix")
    assert proc.returncode == 0, proc.stderr
    assert "REPAIRED" in proc.stdout

    fixed = report.read_text(encoding="utf-8")
    assert fixed.startswith(MANDATED)
    assert BODY in fixed, "the body must survive the repair byte-for-byte"
    assert _r1_verdict(report).returncode == 0, "the repair must satisfy the gate that blocks PRs"


def test_frontmatter_without_the_key_gets_the_key_inside_the_existing_block(tmp_path):
    report = _report(tmp_path, "r.md")
    report.write_text(f"---\ndate: 2026-07-27\ndomain: nb-health\n---\n\n{BODY}", encoding="utf-8")

    assert _run_gate(report, "--fix").returncode == 0
    fixed = report.read_text(encoding="utf-8")

    assert fixed.count("---\n") == 2, "one frontmatter block, not two stacked ones"
    assert "date: 2026-07-27" in fixed and "domain: nb-health" in fixed
    assert "adversarial_review: exempt-machine-report" in fixed
    assert _r1_verdict(report).returncode == 0


def test_a_research_deliverable_is_REFUSED_not_stamped_as_a_machine_artifact(tmp_path):
    """The exemption CLAIMS "generated artifact, not a research deliverable". On a
    document that cites sources that claim is false, and the R1 gate would then
    pass it on a false basis.

    Shape taken from the real one: research/nb-health/2026-05-28-nb3-kbli-corrections.md
    is a human correction report verified against a 623-page primary source, sitting
    in the curator's own OUTPUT directory with frontmatter but no R1 key — exactly
    the shape --fix rewrites. Judged by location it is a machine artifact; judged by
    what it IS, it is not.
    """
    report = _report(tmp_path, "r.md")
    original = (
        "---\ndate: 2026-05-28\ndomain: nb-health\ntype: correction-report\n"
        "discovered_by: deep-researcher\nsources:\n  - PRIMARY: Peraturan BPS 7/2025\n"
        f"---\n\n{BODY}"
    )
    report.write_text(original, encoding="utf-8")

    proc = _run_gate(report, "--fix")
    assert proc.returncode == REFUSED
    assert "REFUSING TO EXEMPT" in proc.stderr
    assert "sources" in proc.stderr and "discovered_by" in proc.stderr
    assert report.read_text(encoding="utf-8") == original, "a deliverable must not be stamped"


def test_a_plain_health_snapshot_is_still_repaired(tmp_path):
    """Innocence for the refusal above: the discriminator must not swallow the
    ordinary case the gate exists for — frontmatter, no R1 key, no deliverable
    markers — or the refusal has quietly disarmed the whole organ."""
    report = _report(tmp_path, "r.md")
    report.write_text(f"---\ndate: 2026-07-27\ndomain: nb-health\n---\n\n{BODY}", encoding="utf-8")

    assert _run_gate(report, "--fix").returncode == 0
    assert "adversarial_review: exempt-machine-report" in report.read_text(encoding="utf-8")
    assert _r1_verdict(report).returncode == 0


def test_a_declaration_the_gate_rejects_is_REFUSED_not_laundered(tmp_path):
    """`adversarial_review: glm` is an attestation that a seat reviewed this file
    (2026-07-25 and 07-26 carry exactly that). Overwriting a broken one with a
    machine exemption would turn a failed review into a green one."""
    report = _report(tmp_path, "r.md")
    original = f"---\nadversarial_review: glm\n---\n\n{BODY}"
    report.write_text(original, encoding="utf-8")

    proc = _run_gate(report, "--fix")
    assert proc.returncode == REFUSED
    assert "Refusing to overwrite" in proc.stderr
    assert report.read_text(encoding="utf-8") == original, "must not touch an attestation"


def test_unclosed_frontmatter_is_refused_rather_than_guessed(tmp_path):
    report = _report(tmp_path, "r.md")
    original = f"---\ndate: 2026-07-27\n\n{BODY}"
    report.write_text(original, encoding="utf-8")

    proc = _run_gate(report, "--fix")
    assert proc.returncode == REFUSED
    assert "MALFORMED FRONTMATTER" in proc.stderr
    assert report.read_text(encoding="utf-8") == original


# ----------------------------------------------------------- INNOCENCE (unit)


def test_a_report_that_already_declares_is_left_byte_identical(tmp_path):
    report = _report(tmp_path, "r.md")
    original = f"{MANDATED}\n{BODY}"
    report.write_text(original, encoding="utf-8")

    proc = _run_gate(report, "--fix")
    assert proc.returncode == 0
    assert "already declares" in proc.stdout
    assert report.read_text(encoding="utf-8") == original


def test_a_real_seat_review_with_its_section_survives_untouched(tmp_path):
    """Innocence for the OTHER valid shape: a session did review it."""
    report = _report(tmp_path, "r.md")
    original = (
        f"---\nadversarial_review: glm\n---\n\n{BODY}\n"
        "## Adversarial review\n\nSeat: GLM, probed live before dispatch.\n"
    )
    report.write_text(original, encoding="utf-8")

    proc = _run_gate(report, "--fix")
    assert proc.returncode == 0
    assert report.read_text(encoding="utf-8") == original


def test_fix_is_idempotent(tmp_path):
    report = _report(tmp_path, "r.md")
    report.write_text(BODY, encoding="utf-8")

    assert _run_gate(report, "--fix").returncode == 0
    once = report.read_text(encoding="utf-8")
    assert _run_gate(report, "--fix").returncode == 0
    assert report.read_text(encoding="utf-8") == once


def test_check_mode_never_writes(tmp_path):
    report = _report(tmp_path, "r.md")
    report.write_text(BODY, encoding="utf-8")

    proc = _run_gate(report)  # no --fix
    assert proc.returncode == NEEDS_FIX
    assert report.read_text(encoding="utf-8") == BODY


# ------------------------------------------------------- FAKE WORLD (wrapper)

FAKE_AGY = """#!/usr/bin/env python3
# Fake brain. Reads the prompt from argv (the value following -p — agy's real
# -p/--print TAKES A VALUE, it does not read stdin), obeys FAKE_AGY_MODE, prints
# a SUMMARY.
import os, re, sys, pathlib

prompt = sys.argv[sys.argv.index("-p") + 1]
mode = os.environ.get("FAKE_AGY_MODE", "good")
if mode == "agyfail":
    # Mirrors the real production failure (measured 2026-09-26/27): agy exits
    # non-zero and prints no SUMMARY line, forcing the wrapper's fallback to
    # claude-cascade.sh.
    sys.exit(1)
m = re.search(r"Write report to: (\\S+)", prompt)
if m and mode == "symlinkfile":
    # Brain-controlled symlink at the staging path: a malicious/buggy brain
    # could stage a link to ANY file it can reach instead of a real report.
    victim = pathlib.Path(os.environ["FAKE_SYMLINK_VICTIM"])
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text("# NB Arsenal Health Report\\n\\n## Health Summary\\n- Total: 1 notebook\\n",
                       encoding="utf-8")
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.symlink_to(victim)
elif m and mode == "stub":
    # Heading-only, no section — the exact shape the gate review promoted.
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# NB Arsenal Health Report\\n", encoding="utf-8")
elif m and mode == "hardlink":
    # Hard link to an existing file: shares the same inode, so `mv` would
    # promote that SAME inode into the repo and the gate would write through
    # it into the victim too — same failure shape as a symlink, one level
    # indirect (measured live: the gate review's own probe hard-linked
    # .claude/agents/nb-curator.md into staging and it was promoted).
    victim = pathlib.Path(os.environ["FAKE_SYMLINK_VICTIM"])
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text("# NB Arsenal Health Report\\n\\n## Health Summary\\n- Total: 1 notebook\\n",
                       encoding="utf-8")
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    os.link(victim, p)
elif m and mode not in ("noreport", "emptyreport"):
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "# NB Arsenal Health Report\\n\\n## Health Summary\\n- Total: 58 notebooks\\n"
    if mode == "good":
        body = ("---\\nadversarial_review: exempt-machine-report # nb-curator daily "
                "health snapshot (generated artifact, not a research deliverable)\\n"
                "---\\n\\n") + body
    p.write_text(body, encoding="utf-8")
elif m and mode == "emptyreport":
    # The brain claims success and touches the staging path, but writes 0 bytes
    # — distinct from `noreport` (nothing at all), same required outcome: the
    # wrapper must not promote it.
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")

print("SUMMARY: broken=0 stale=0 proposals=0 press_new=0")
"""

# Fake claude-cascade.sh fallback: writes a compliant report to whatever path
# the prompt names (now $STAGING_PATH, outside the repo — see nb-curator-daily.sh),
# just like FAKE_AGY's "good" path, so the rest of the wrapper chain (promote,
# gate, digest, exit code) runs unchanged when the fallback tier is exercised.
FAKE_CASCADE = """#!/usr/bin/env python3
import re, sys, pathlib

prompt = sys.argv[1] if len(sys.argv) > 1 else ""
m = re.search(r"Write report to: (\\S+)", prompt)
if m:
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\\nadversarial_review: exempt-machine-report # nb-curator daily "
        "health snapshot (generated artifact, not a research deliverable)\\n"
        "---\\n\\n# NB Arsenal Health Report\\n\\n## Health Summary\\n- Total: 58 notebooks\\n",
        encoding="utf-8",
    )

print("SUMMARY: broken=0 stale=0 proposals=0 press_new=0")
"""


def _makassar_env() -> dict:
    return dict(os.environ, TZ="Asia/Makassar")


def _makassar_date_str() -> str:
    return subprocess.run(["date", "+%Y-%m-%d"], env=_makassar_env(),
                          capture_output=True, text=True, check=True).stdout.strip()


def _expected_report_filename() -> str:
    """Mirrors nb-curator-daily.sh's own REPORT_PATH branch, so a symlink test
    can pre-plant a path THE WRAPPER will actually compute today, whatever day
    it is run on."""
    env = _makassar_env()
    dow = int(subprocess.run(["date", "+%u"], env=env, capture_output=True, text=True, check=True).stdout.strip())
    day = int(subprocess.run(["date", "+%-d"], env=env, capture_output=True, text=True, check=True).stdout.strip())
    date_str = _makassar_date_str()
    month_str = subprocess.run(["date", "+%Y-%m"], env=env, capture_output=True, text=True, check=True).stdout.strip()
    if dow == 1 and day <= 7:
        return f"{month_str}-nb-intel-curation.md"
    if dow == 1:
        return f"{date_str}-curation.md"
    return f"{date_str}-health.md"


def _fake_world(tmp_path: Path, mode: str, *, wrapper: Path, extra_env: dict | None = None,
                setup_home=None) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (home / "scripts").mkdir(parents=True)
    (home / "logs").mkdir(parents=True)
    if setup_home is not None:
        setup_home(home)

    agy = home / ".local/bin/agy"
    agy.write_text(FAKE_AGY, encoding="utf-8")
    agy.chmod(0o755)

    cascade = home / "scripts/claude-cascade.sh"
    cascade.write_text(FAKE_CASCADE, encoding="utf-8")
    cascade.chmod(0o755)

    env = os.environ.copy()
    env.update(
        HOME=str(home),
        FAKE_AGY_MODE=mode,
        NB_CURATOR_LOCK_FILE=str(tmp_path / "nb-curator.lock"),
        TG_DRY_RUN="1",
        TG_SPOOL_DIR=str(tmp_path / "spool"),
        TELEGRAM_BOT_TOKEN="fake-token-never-sent",
        TELEGRAM_OWNER_CHAT_ID="0",
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run([shutil.which("zsh") or "/bin/zsh", str(wrapper)],
                          capture_output=True, text=True, env=env, timeout=180)


def _log(tmp_path: Path) -> str:
    p = tmp_path / "home/logs/nb-curator.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _spooled(tmp_path: Path) -> str:
    spool = tmp_path / "spool"
    if not spool.exists():
        return ""
    return "\n".join(f.read_text(encoding="utf-8") for f in spool.glob("*.jsonl"))


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_FAILS_when_the_brain_writes_no_report(tmp_path):
    """Innocence for a missing staged artifact: brain exit 0, SUMMARY printed,
    nothing at $STAGING_PATH. The wrapper must refuse to promote, name the
    reason, and the gate (which never sees a file at $REPORT_PATH) must fail
    closed: rc=2, a P0 in the spool, and the reason in the log."""
    proc = _fake_world(tmp_path, "noreport", wrapper=WRAPPER)
    log = _log(tmp_path)

    assert proc.returncode == 2, f"expected artifact-gate exit 2, got {proc.returncode}\n{log}"
    assert "STAGING FILE MISSING" in log
    assert "PROMOTE SKIPPED" in log
    assert "ARTIFACT GATE FAILED" in log
    assert "artifact gate rc=3" in log, "rc=3 is 'the report was never written'"
    assert "brain OK but the report failed the artifact gate" in _spooled(tmp_path)


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_FAILS_when_the_brain_writes_an_empty_report(tmp_path):
    """Innocence for a present-but-empty staged artifact: distinct failure mode
    from `noreport` above (the brain DID touch the path), same required
    outcome — never promoted, gate fails closed with the reason named."""
    proc = _fake_world(tmp_path, "emptyreport", wrapper=WRAPPER)
    log = _log(tmp_path)

    assert proc.returncode == 2, f"expected artifact-gate exit 2, got {proc.returncode}\n{log}"
    assert "STAGING FILE EMPTY" in log
    assert "PROMOTE SKIPPED" in log
    assert "artifact gate rc=3" in log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_refuses_a_symlinked_staged_report(tmp_path):
    """Guilt, re-gate blocker (a): a brain-controlled symlink at the staging
    path must never be promoted or followed. Before this fix `[ -e ]`/`[ -s ]`/
    `grep` all follow symlinks and `mv` would place the link itself inside the
    repo, where the artifact gate's --fix then writes THROUGH it into whatever
    the brain pointed at."""
    victim = tmp_path / "outside-victim.md"
    proc = _fake_world(tmp_path, "symlinkfile", wrapper=WRAPPER,
                       extra_env={"FAKE_SYMLINK_VICTIM": str(victim)})
    log = _log(tmp_path)
    report_path = tmp_path / "home/nuzantara/research/nb-health" / _expected_report_filename()

    assert "STAGING FILE NOT A REGULAR FILE" in log
    assert "PROMOTE SKIPPED" in log
    assert not report_path.exists(), "a symlinked staged file must never be promoted"
    assert victim.read_text(encoding="utf-8") == (
        "# NB Arsenal Health Report\n\n## Health Summary\n- Total: 1 notebook\n"
    ), "the victim file the brain pointed at must be untouched — nothing may write through the link"
    assert proc.returncode == 2, log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_refuses_a_hard_linked_staged_report(tmp_path):
    """Guilt, final re-gate item: a staged HARD LINK shares its inode with the
    victim it links — `mv` renames the inode in place, so promoting it would
    move the SAME inode into the repo and the gate would write through it into
    every other path that names it, one level indirect from the symlink case.
    Measured live in gate review: hard-linking .claude/agents/nb-curator.md
    into staging passed every prior check and was promoted."""
    victim = tmp_path / "outside-victim-hardlink.md"
    proc = _fake_world(tmp_path, "hardlink", wrapper=WRAPPER,
                       extra_env={"FAKE_SYMLINK_VICTIM": str(victim)})
    log = _log(tmp_path)
    report_path = tmp_path / "home/nuzantara/research/nb-health" / _expected_report_filename()

    assert "STAGING FILE NOT A REGULAR FILE" in log
    assert "PROMOTE SKIPPED" in log
    assert not report_path.exists(), "a hard-linked staged file must never be promoted"
    assert victim.read_text(encoding="utf-8") == (
        "# NB Arsenal Health Report\n\n## Health Summary\n- Total: 1 notebook\n"
    ), "the victim inode must be untouched — nothing may write through the shared link"
    assert proc.returncode == 2, log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_refuses_a_preplanted_symlinked_staging_dir(tmp_path):
    """Guilt, re-gate blocker (a): a symlink already sitting where the staging
    dir belongs (planted by anything with write access to $HOME/.agent before
    this run) must abort the whole run rather than be `chmod`'d — `chmod` on a
    symlink changes the TARGET's mode, not the link's."""
    date_str = _makassar_date_str()
    victim_dir = tmp_path / "victim-dir"
    victim_dir.mkdir(mode=0o755)

    def plant(home: Path) -> None:
        agent_dir = home / ".agent" / "nb-curator"
        agent_dir.mkdir(parents=True)
        (agent_dir / date_str).symlink_to(victim_dir)

    proc = _fake_world(tmp_path, "good", wrapper=WRAPPER, setup_home=plant)
    log = _log(tmp_path)

    assert proc.returncode == 1, log
    assert "FATAL" in log and "staging dir" in log
    assert "brain used:" not in log, "the brain must never run against an unsafe staging dir"
    assert oct(victim_dir.stat().st_mode)[-3:] == "755", "the symlink TARGET's mode must be untouched"


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_refuses_a_heading_only_stub(tmp_path):
    """Guilt, re-gate blocker (b): a one-line staged file carrying only the
    mandated heading (no section) must not be promoted — the artifact gate's
    own checks (non-empty, frontmatter) are not enough to reject a stub."""
    proc = _fake_world(tmp_path, "stub", wrapper=WRAPPER)
    log = _log(tmp_path)

    assert "STAGING FILE TOO THIN" in log
    assert "PROMOTE SKIPPED" in log
    assert proc.returncode == 2, log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_clears_a_symlink_squatting_report_path_before_promoting(tmp_path):
    """Innocence for the REPORT_PATH-side of blocker (a): a symlink already
    sitting at the FINAL tracked path (from before this fix existed, or from
    any other source) must be cleared before promotion, and the gate must
    never be given a chance to write through it into whatever it pointed at."""
    victim = tmp_path / "old-victim.md"
    victim.write_text("ORIGINAL VICTIM CONTENT\n", encoding="utf-8")
    filename = _expected_report_filename()

    def plant(home: Path) -> None:
        health_dir = home / "nuzantara/research/nb-health"
        health_dir.mkdir(parents=True)
        (health_dir / filename).symlink_to(victim)

    proc = _fake_world(tmp_path, "good", wrapper=WRAPPER, setup_home=plant)
    log = _log(tmp_path)
    report_path = tmp_path / "home/nuzantara/research/nb-health" / filename

    assert "removing symlink squatting REPORT_PATH" in log
    assert not report_path.is_symlink(), "REPORT_PATH must be a real promoted file, not the old symlink"
    assert victim.read_text(encoding="utf-8") == "ORIGINAL VICTIM CONTENT\n", (
        "the gate must never write through the cleared symlink's old target"
    )
    if not SYSTEM_PY_HAS_YAML:
        assert proc.returncode == 2 and "REDACTOR UNAVAILABLE" in log, log
        return
    assert proc.returncode == 0, log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_lands_the_report_even_when_worktree_enforcement_is_pinned_true(tmp_path):
    """Guilt case for the OLD (env-var-escape) wrapper, proven against the
    ACTUAL production condition measured 2026-09-27 on Pro: seat 1's own
    ~/.claude/settings.json pins AGENT_WORKTREE_ENFORCEMENT=true in its `env`
    block, which Claude Code applies on top of the invoking process's
    environment — so an inline `VAR=false cmd` prefix on the brain's own
    command line never reached the hook at all. This test forces that exact
    value into the whole subprocess environment (as if the seat's settings.json
    pinned it) and forces agy to fail so the claude-cascade fallback runs; the
    CURRENT design must still land the report, because the brain never writes
    inside the repo in the first place — the hook is never a factor."""
    proc = _fake_world(tmp_path, "agyfail", wrapper=WRAPPER,
                        extra_env={"AGENT_WORKTREE_ENFORCEMENT": "true"})
    log = _log(tmp_path)

    assert "brain used: claude-cascade" in log, f"cascade fallback was not exercised\n{log}"
    assert "promoted staged report" in log, f"the report was never promoted\n{log}"
    reports = list((tmp_path / "home/nuzantara/research/nb-health").glob("*.md"))
    assert len(reports) == 1, f"expected exactly one promoted report, got {reports}\n{log}"
    if not SYSTEM_PY_HAS_YAML:
        assert proc.returncode == 2 and "REDACTOR UNAVAILABLE" in log, log
        return
    assert proc.returncode == 0, f"a compliant, promoted report is not a failure\n{log}"
    assert "artifact gate rc=0" in log


def test_agy_model_string_is_not_stale():
    """Static guard for the second, independent root cause found alongside the
    write bug: agy's own error output (measured 2026-09-26/27 on Pro) lists no
    'Gemini 3.5' tier at all — every run was failing this tier instantly and
    burning Claude MAX quota on the fallback. Pins the fix so it can't silently
    regress back to the dead spelling."""
    text = WRAPPER.read_text(encoding="utf-8")
    assert '--model "Gemini 3.5' not in text, (
        "agy no longer recognizes the 3.5 Flash family (measured 2026-09-26/27)"
    )
    assert '--model "Gemini 3.8 Flash (Medium)"' in text


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_REPAIRS_a_report_written_without_the_mandated_frontmatter(tmp_path):
    proc = _fake_world(tmp_path, "nofrontmatter", wrapper=WRAPPER)
    log = _log(tmp_path)

    reports = list((tmp_path / "home/nuzantara/research/nb-health").glob("*.md"))
    assert len(reports) == 1, f"expected exactly one report, got {reports}"
    assert _r1_verdict(reports[0]).returncode == 0, "the wrapper must leave an R1-clean artifact"
    if not SYSTEM_PY_HAS_YAML:
        assert proc.returncode == 2 and "REDACTOR UNAVAILABLE" in log, log
        return
    assert proc.returncode == 0, f"a repairable report is not a failure\n{log}"
    assert "artifact gate rc=0" in log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_is_silent_and_green_on_a_compliant_run(tmp_path):
    """Innocence: the happy path must not start alarming."""
    proc = _fake_world(tmp_path, "good", wrapper=WRAPPER)
    log = _log(tmp_path)
    if not SYSTEM_PY_HAS_YAML:
        assert proc.returncode == 2 and "REDACTOR UNAVAILABLE" in log, log
        return
    assert proc.returncode == 0, log
    assert "no action/anomaly" in log
    assert "ARTIFACT GATE FAILED" not in log
    assert _spooled(tmp_path) == "", "a clean run must send nothing"


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_a_missing_gate_and_a_missing_gateway_both_leave_a_TRACE(tmp_path):
    """Copy the wrapper somewhere with no siblings: the artifact goes unverified
    and the alarm cannot be delivered. Neither may look like success — an alarm
    guarded by an `if` that merely does nothing is the failure mode this whole
    change exists to remove."""
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    copy = lonely / "nb-curator-daily.sh"
    shutil.copy2(WRAPPER, copy)

    proc = _fake_world(tmp_path, "good", wrapper=copy)
    log = _log(tmp_path)

    assert proc.returncode == 2, log
    assert "ARTIFACT GATE MISSING" in log
    assert "ALERT NOT SENT — gateway missing" in log


# ------------------------------------------------- REDACTION (gate + inventory)
# Invented names only. Shapes mirror the leaks measured 2026-09-26 in promoted reports.

LISTED_ID = "afd7fc4e-2568-4fff-861f-67b661842ece"
LEAKY_BODY = (
    "# NB Arsenal Health Report\n\n"
    "| id | title | sources |\n|---|---|---|\n"
    "| `11112222` | Piano di Ristrutturazione per PT Fakeco Nusantara | 3 |\n"
    "| `33334444` | NB-2: Immigration & Visa — Indonesia 2025 | 80 |\n\n"
    "Contact: someone@example.org\n"
)


def test_gate_redacts_client_identifiers_in_the_body_and_spares_the_frontmatter(tmp_path):
    report = _report(tmp_path, "2026-09-26-health.md")
    report.write_text(MANDATED + "\n" + LEAKY_BODY, encoding="utf-8")
    proc = _run_gate(report, "--fix")
    assert proc.returncode == 0, proc.stderr
    assert "REDACTED: 2 line(s)" in proc.stdout
    out = report.read_text(encoding="utf-8")
    assert "Fakeco" not in out and "someone@example.org" not in out
    assert "| Piano di Ristrutturazione per [COMPANY-NAME-REDACTED] | 3 |" in out
    assert "| NB-2: Immigration & Visa — Indonesia 2025 | 80 |" in out
    assert out.startswith(MANDATED), "the R1 declaration must survive byte for byte"
    assert _r1_verdict(report).returncode == 0


def test_gate_without_fix_reports_identifiers_and_leaves_the_file(tmp_path):
    report = _report(tmp_path, "2026-09-26-health.md")
    report.write_text(MANDATED + "\n" + LEAKY_BODY, encoding="utf-8")
    proc = _run_gate(report)
    assert proc.returncode == NEEDS_FIX
    assert report.read_text(encoding="utf-8") == MANDATED + "\n" + LEAKY_BODY


def _inventory_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("nb_inv_under_test", REPO / "scripts/nb_generate_inventory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raw_inventory(inv):
    notebooks = [
        {"id": "55556666-0000-0000-0000-000000000000", "title": "Meet 2026-05-13 Jane Placeholder — Villa", "source_count": 2},
        {"id": LISTED_ID, "title": "Harmless Looking Title", "source_count": 1},
        {"id": "77778888-0000-0000-0000-000000000000", "title": "NB-3: Company Setup — Indonesia 2025", "source_count": 9},
    ]
    sources = {k: [] for k in inv.NB_INTEL}
    sources["press"] = [{"title": "Reach us: someone@example.org"}]
    return inv.build_inventory(notebooks, sources)


def test_inventory_titles_are_redacted_before_the_brain_reads_them():
    inv = _inventory_module()
    out = inv.redact_inventory(_raw_inventory(inv), inv.load_title_redactor())
    assert [n["title"] for n in out["notebooks"]] == [
        "Meet 2026-05-13 [CLIENT-NAME-REDACTED] — Villa",
        "[CLIENT-NOTEBOOK-REDACTED]",
        "NB-3: Company Setup — Indonesia 2025",
    ]
    assert out["nb_intel"]["press"]["titles"] == ["Reach us: [CLIENT-EMAIL-REDACTED]"]
    assert out["redaction"] == "applied"


def test_inventory_withholds_every_title_when_the_redactor_cannot_load(tmp_path):
    inv = _inventory_module()
    redactor = inv.load_title_redactor(tmp_path / "missing_redactor.py")
    assert redactor is None
    out = inv.redact_inventory(_raw_inventory(inv), redactor)
    assert [n["title"] for n in out["notebooks"]][0] == "[NB-TITLE-WITHHELD:55556666]"
    assert out["nb_intel"]["press"]["titles"] == ["[SOURCE-TITLE-WITHHELD]"]
    assert out["redaction"] == "withheld"


def test_inventory_main_writes_only_redacted_titles(tmp_path, monkeypatch):
    """The wiring, not just the function: `--write` must never put a raw title on disk."""
    import json

    inv = _inventory_module()
    monkeypatch.setattr(inv, "fetch_notebooks", lambda: [
        {"id": "99990000-0000-0000-0000-000000000000", "title": "Kontrak untuk PT Fakeco Nusantara", "source_count": 1},
    ])
    monkeypatch.setattr(inv, "fetch_sources", lambda _uuid: [{"title": "Plain headline"}])
    monkeypatch.setattr(inv, "OUTPUT_PATH", tmp_path / "nb-inventory-live.json")
    monkeypatch.setattr(sys, "argv", ["nb_generate_inventory.py", "--write"])
    assert inv.main() == 0
    written = (tmp_path / "nb-inventory-live.json").read_text(encoding="utf-8")
    assert "Fakeco" not in written
    assert json.loads(written)["notebooks"][0]["title"] == "Kontrak untuk [COMPANY-NAME-REDACTED]"
