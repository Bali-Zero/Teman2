"""Unit tests for scripts/_entailment_check.py.

Covers:
    - Evidence snippet extraction from a SKILL.md (file:line + commit + URL)
    - Redaction wrapper invocation (subprocess mock)
    - Gemini CLI verdict parsing (YES / NO / UNKNOWN / quota exhaust)
    - Quota detection regex
    - Per-proposal evaluation: pass / reject paths
    - Partition: passed/ vs rejected/ + audit log written
    - CLI smoke

Run:
    cd ~/Desktop/nuzantara-wt-evoskill-phase1
    python3 -m pytest scripts/test_entailment_check.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import _entailment_check as ec  # noqa: E402


# ─── Snippet extraction ──────────────────────────────────────────────


def test_extract_file_line_snippet(tmp_path, monkeypatch):
    f = tmp_path / "code.py"
    f.write_text("\n".join(f"L{i}" for i in range(1, 30)) + "\n")
    monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
    text = "Cite `code.py:10-12` here."
    snippets = ec.extract_evidence_snippets(text)
    assert len(snippets) == 1
    assert "[file:line]" in snippets[0]
    assert "code.py:10-12" in snippets[0]
    assert "L10" in snippets[0]
    assert "L12" in snippets[0]


def test_extract_commit_snippet(monkeypatch):
    def fake_subprocess_run(cmd, **kw):
        return SimpleNamespace(
            returncode=0,
            stdout="commit subject line\n\ncommit body description here\n",
            stderr="",
        )
    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    text = "Fix in commit `abc12345` resolved the bug."
    snippets = ec.extract_evidence_snippets(text)
    assert len(snippets) == 1
    assert "[commit] abc12345" in snippets[0]
    assert "commit subject line" in snippets[0]


def test_extract_url_snippet():
    text = "See https://example.com/foo/bar for context."
    snippets = ec.extract_evidence_snippets(text)
    assert len(snippets) == 1
    assert "[external_url] https://example.com/foo/bar" in snippets[0]


def test_extract_no_citations():
    text = "Plain prose with no citations whatsoever."
    snippets = ec.extract_evidence_snippets(text)
    assert snippets == []


def test_extract_bounded_to_max_8(tmp_path, monkeypatch):
    """If a proposal cites 20 URLs, only first 8 should make it into prompt."""
    text = " ".join(f"https://example.com/{i}" for i in range(20))
    snippets = ec.extract_evidence_snippets(text)
    assert len(snippets) == 8


# ─── Redaction wrapper ───────────────────────────────────────────────


def test_redact_invokes_redactor_script(monkeypatch):
    captured: dict = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["input"] = kw.get("input")
        return SimpleNamespace(returncode=0, stdout="redacted text output", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = ec.redact("input with PII zero@balizero.com")
    assert out == "redacted text output"
    assert "_redact_pii.py" in " ".join(captured["cmd"])
    assert captured["input"] == "input with PII zero@balizero.com"


def test_redact_empty_output_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ec.EntailmentError, match="empty"):
        ec.redact("some input")


def test_redact_non_zero_exit_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=1, stdout="", stderr="redaction failed")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ec.EntailmentError, match="exited 1"):
        ec.redact("some input")


def test_redact_script_missing_raises(monkeypatch):
    monkeypatch.setattr(ec, "REDACTOR_SCRIPT", Path("/nonexistent/_redact_pii.py"))
    with pytest.raises(ec.EntailmentError, match="redactor missing"):
        ec.redact("input")


# ─── Gemini CLI mock + verdict parsing ───────────────────────────────


def test_gemini_verdict_yes(monkeypatch):
    monkeypatch.setattr(
        "shutil.which", lambda _: "/opt/homebrew/bin/gemini"
    )
    def fake_run(cmd, **kw):
        return SimpleNamespace(
            returncode=0,
            stdout="VERDICT: YES — claim aligns with cited diff line 42",
            stderr="",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    v = ec.call_gemini_verdict("prompt body")
    assert v.verdict == "YES"
    assert "claim aligns" in v.rationale
    assert v.quota_exhausted is False


def test_gemini_verdict_no(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    def fake_run(cmd, **kw):
        return SimpleNamespace(
            returncode=0,
            stdout="VERDICT: NO — cited file does not mention the claim",
            stderr="",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    v = ec.call_gemini_verdict("prompt")
    assert v.verdict == "NO"
    assert v.quota_exhausted is False


def test_gemini_verdict_unknown_format(monkeypatch):
    """Gemini returned text without VERDICT line → UNKNOWN."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    def fake_run(cmd, **kw):
        return SimpleNamespace(
            returncode=0,
            stdout="Yeah, looks fine I guess. The claim seems plausible.",
            stderr="",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    v = ec.call_gemini_verdict("prompt")
    assert v.verdict == "UNKNOWN"


def test_gemini_verdict_quota_exhaust_429(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    def fake_run(cmd, **kw):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="429 RESOURCE_EXHAUSTED: quota exceeded for daily Gemini OAuth tier",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    v = ec.call_gemini_verdict("prompt")
    assert v.verdict == "UNKNOWN"
    assert v.quota_exhausted is True


def test_gemini_cli_missing_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(ec.EntailmentError, match="gemini CLI not found"):
        ec.call_gemini_verdict("prompt")


def test_gemini_timeout(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))
    monkeypatch.setattr(subprocess, "run", fake_run)
    v = ec.call_gemini_verdict("prompt")
    assert v.verdict == "UNKNOWN"
    assert v.quota_exhausted is False
    assert "timed out" in v.rationale.lower()


# ─── Quota detection regex ───────────────────────────────────────────


def test_quota_detection_patterns():
    assert ec._detect_quota_exhaust("Error 429: rate limit exceeded")
    assert ec._detect_quota_exhaust("RESOURCE_EXHAUSTED for project")
    assert ec._detect_quota_exhaust("daily quota exceeded")
    assert ec._detect_quota_exhaust("out of usage for this tier")
    assert not ec._detect_quota_exhaust("normal success response")
    assert not ec._detect_quota_exhaust("HTTP 200 OK")


# ─── End-to-end per-proposal evaluation (mocked) ─────────────────────


def _mock_redactor_pass(monkeypatch):
    """Mock redactor to return input verbatim (no PII in fixtures)."""
    def fake_run(cmd, **kw):
        # Distinguish git invocations from redactor invocations
        if cmd and "_redact_pii.py" in " ".join(str(c) for c in cmd):
            return SimpleNamespace(
                returncode=0,
                stdout=kw.get("input", "") or "redacted",
                stderr="",
            )
        # Default for git etc.
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)


def test_evaluate_proposal_passes(tmp_path, monkeypatch):
    skill = tmp_path / "good" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# Skill\n\nFix in `code.py:1`.\n" + "padding " * 30)
    code = tmp_path / "code.py"
    code.write_text("\n".join(["L1", "L2", "L3"]))
    monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    # Mock the redactor + gemini together
    def fake_run(cmd, **kw):
        cmd_str = " ".join(str(c) for c in cmd)
        if "_redact_pii.py" in cmd_str:
            return SimpleNamespace(
                returncode=0, stdout=kw.get("input") or "x", stderr=""
            )
        if "gemini" in cmd_str:
            return SimpleNamespace(
                returncode=0,
                stdout="VERDICT: YES — file content supports the claim",
                stderr="",
            )
        # git etc — return non-zero so commit_snippet isn't appended
        return SimpleNamespace(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    report = ec.evaluate_proposal(skill)
    assert report.passed is True
    assert report.verdict == "YES"


def test_evaluate_proposal_rejected_by_gemini_no(tmp_path, monkeypatch):
    skill = tmp_path / "bad" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# Skill\n\nFix in `code.py:1`.\n" + "padding " * 30)
    code = tmp_path / "code.py"
    code.write_text("L1")
    monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    def fake_run(cmd, **kw):
        cmd_str = " ".join(str(c) for c in cmd)
        if "_redact_pii.py" in cmd_str:
            return SimpleNamespace(returncode=0, stdout=kw.get("input") or "x", stderr="")
        if "gemini" in cmd_str:
            return SimpleNamespace(
                returncode=0,
                stdout="VERDICT: NO — cited line does not support claim",
                stderr="",
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    report = ec.evaluate_proposal(skill)
    assert report.passed is False
    assert "entailment NO" in report.reject_reason


def test_evaluate_proposal_quota_exhaust(tmp_path, monkeypatch):
    skill = tmp_path / "quota" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# Skill\n\nFix in `code.py:1`.\n" + "padding " * 30)
    code = tmp_path / "code.py"
    code.write_text("L1")
    monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gemini")
    def fake_run(cmd, **kw):
        cmd_str = " ".join(str(c) for c in cmd)
        if "_redact_pii.py" in cmd_str:
            return SimpleNamespace(returncode=0, stdout=kw.get("input") or "x", stderr="")
        if "gemini" in cmd_str:
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="429 RESOURCE_EXHAUSTED",
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    report = ec.evaluate_proposal(skill)
    assert report.passed is False
    assert "quota exhausted" in report.reject_reason


def test_evaluate_proposal_no_snippets(tmp_path, monkeypatch):
    """Defensive: SKILL.md without citations should never reach entailment
    (evidence_lint rejects first) but guard anyway."""
    skill = tmp_path / "nocite" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# Skill\n\nNo citations.\n")
    monkeypatch.setattr(ec, "REPO_ROOT", tmp_path)
    report = ec.evaluate_proposal(skill)
    assert report.passed is False
    assert "no extractable evidence" in report.reject_reason


# ─── Partition ───────────────────────────────────────────────────────


def test_partition_moves_dirs_and_writes_audit(tmp_path):
    proposals = tmp_path / "proposals"
    pe = proposals / "passed-existence"
    pe.mkdir(parents=True)
    p1 = pe / "skill-x"
    p1.mkdir()
    (p1 / "SKILL.md").write_text("x")
    p2 = pe / "skill-y"
    p2.mkdir()
    (p2 / "SKILL.md").write_text("y")
    r1 = ec.EntailmentReport(
        skill_md=p1 / "SKILL.md", passed=True, verdict="YES", rationale="ok"
    )
    r2 = ec.EntailmentReport(
        skill_md=p2 / "SKILL.md",
        passed=False,
        verdict="NO",
        rationale="not aligned",
        reject_reason="entailment NO: not aligned",
    )
    passed, rejected = ec.partition_proposals(pe, [r1, r2])
    assert passed == 1
    assert rejected == 1
    assert (proposals / "passed" / "skill-x" / "SKILL.md").is_file()
    assert (proposals / "rejected" / "skill-y" / "SKILL.md").is_file()
    audit = json.loads((proposals / "_entailment_check_audit.json").read_text())
    assert len(audit) == 2


# ─── CLI ─────────────────────────────────────────────────────────────


def test_cli_missing_dir():
    assert ec.main(["/nonexistent/xyz"]) == 1


def test_cli_bad_arg_count():
    assert ec.main([]) == 1
    assert ec.main(["a", "b"]) == 1
