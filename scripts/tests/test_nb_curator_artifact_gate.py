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
m = re.search(r"Write report to: (\\S+)", prompt)
if m and mode != "noreport":
    p = pathlib.Path(m.group(1))
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "# NB Arsenal Health Report\\n\\n## Health Summary\\n- Total: 58 notebooks\\n"
    if mode == "good":
        body = ("---\\nadversarial_review: exempt-machine-report # nb-curator daily "
                "health snapshot (generated artifact, not a research deliverable)\\n"
                "---\\n\\n") + body
    p.write_text(body, encoding="utf-8")

print("SUMMARY: broken=0 stale=0 proposals=0 press_new=0")
"""


def _fake_world(tmp_path: Path, mode: str, *, wrapper: Path) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (home / "scripts").mkdir(parents=True)
    (home / "logs").mkdir(parents=True)

    agy = home / ".local/bin/agy"
    agy.write_text(FAKE_AGY, encoding="utf-8")
    agy.chmod(0o755)

    cascade = home / "scripts/claude-cascade.sh"
    cascade.write_text("#!/bin/sh\necho 'SUMMARY: broken=0 stale=0 proposals=0 press_new=0'\n")
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
    """The exact run the old wrapper called OK: brain exit 0, SUMMARY printed,
    no artifact. Now: rc=2, a P0 in the spool, and the reason in the log."""
    proc = _fake_world(tmp_path, "noreport", wrapper=WRAPPER)
    log = _log(tmp_path)

    assert proc.returncode == 2, f"expected artifact-gate exit 2, got {proc.returncode}\n{log}"
    assert "ARTIFACT GATE FAILED" in log
    assert "artifact gate rc=3" in log, "rc=3 is 'the report was never written'"
    assert "brain OK but the report failed the artifact gate" in _spooled(tmp_path)


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_REPAIRS_a_report_written_without_the_mandated_frontmatter(tmp_path):
    proc = _fake_world(tmp_path, "nofrontmatter", wrapper=WRAPPER)
    log = _log(tmp_path)
    assert proc.returncode == 0, f"a repairable report is not a failure\n{log}"

    reports = list((tmp_path / "home/nuzantara/research/nb-health").glob("*.md"))
    assert len(reports) == 1, f"expected exactly one report, got {reports}"
    assert _r1_verdict(reports[0]).returncode == 0, "the wrapper must leave an R1-clean artifact"
    assert "artifact gate rc=0" in log


@pytest.mark.skipif(shutil.which("zsh") is None, reason="wrapper is a zsh script")
def test_wrapper_is_silent_and_green_on_a_compliant_run(tmp_path):
    """Innocence: the happy path must not start alarming."""
    proc = _fake_world(tmp_path, "good", wrapper=WRAPPER)
    log = _log(tmp_path)
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
