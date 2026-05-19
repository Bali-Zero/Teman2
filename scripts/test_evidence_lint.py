"""Unit tests for scripts/_evidence_lint.py.

Covers:
    - Config load (rules + gate parsing)
    - Each citation type verifier: file:line (with + without ext),
      commit hash (resolves + doesn't), URL (mocked httpx), memory
      file path, cicatrix scar header
    - Per-proposal evaluation: pass / reject paths
    - Partition: passed-existence/ vs rejected/ + audit log written
    - Gate: reject_no_citation + min_verified_refs

Run:
    cd ~/Desktop/nuzantara-wt-evoskill-phase1
    python3 -m pytest scripts/test_evidence_lint.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import _evidence_lint as ev  # noqa: E402


# ─── Config load ─────────────────────────────────────────────────────


def test_load_config_defaults():
    config = ev.load_config()
    assert config.gate.min_verified_refs == 1
    assert config.gate.reject_no_citation is True
    rule_ids = [r.id for r in config.rules]
    assert "file_line_ref" in rule_ids
    assert "commit_hash" in rule_ids
    assert "external_url" in rule_ids
    assert "memory_file_ref" in rule_ids
    assert "cicatrix_scar_ref" in rule_ids


def test_load_config_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ev.load_config(tmp_path / "nonexistent.yaml")


# ─── file:line verifier ──────────────────────────────────────────────


def test_file_line_verifier_extension(tmp_path, monkeypatch):
    """file:line with extension that resolves on disk."""
    f = tmp_path / "test.py"
    f.write_text("line1\nline2\nline3\nline4\nline5\n")
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    text = f"Cite `test.py:2-3` here."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "file_line_ref")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_file_exists_and_line_in_range(m) is True


def test_file_line_verifier_extensionless(tmp_path, monkeypatch):
    """L10 fix: Makefile / Dockerfile without extension also valid."""
    f = tmp_path / "Makefile"
    f.write_text("\n".join(f"line{i}" for i in range(1, 20)) + "\n")
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    text = "See `Makefile:5` for the install target."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "file_line_ref")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_file_exists_and_line_in_range(m) is True


def test_file_line_verifier_line_out_of_range(tmp_path, monkeypatch):
    f = tmp_path / "small.txt"
    f.write_text("only_3\nlines\nhere\n")
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    text = "Cite `small.txt:100`"
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "file_line_ref")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_file_exists_and_line_in_range(m) is False


def test_file_line_verifier_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "REPO_ROOT", tmp_path)
    text = "Cite `nonexistent.py:1`"
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "file_line_ref")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_file_exists_and_line_in_range(m) is False


# ─── commit hash verifier ────────────────────────────────────────────


def test_commit_hash_resolves_to_real_commit():
    """Use HEAD of the actual repo — must always resolve."""
    import subprocess
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ev.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    text = f"See commit `{head}` for the fix."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "commit_hash")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_git_rev_parse(m) is True


def test_commit_hash_does_not_resolve():
    text = "See commit `deadbeef0000` which doesn't exist."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "commit_hash")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_git_rev_parse(m) is False


# ─── URL verifier (mocked httpx) ─────────────────────────────────────


def test_url_verifier_mocked_200(monkeypatch):
    """Mock httpx.Client to return 200 — patch BEFORE first import call."""
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def head(self, url):
            return httpx.Response(200, request=httpx.Request("HEAD", url))
    monkeypatch.setattr(httpx, "Client", FakeClient)
    text = "Cite https://github.com/foo/bar source."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "external_url")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_http_head(m, 2.0) is True


def test_url_verifier_mocked_500(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def head(self, url):
            return httpx.Response(500, request=httpx.Request("HEAD", url))
    monkeypatch.setattr(httpx, "Client", FakeClient)
    text = "Cite https://example.com/broken source."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "external_url")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_http_head(m, 2.0) is False


def test_url_verifier_network_error(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def head(self, url):
            raise httpx.ConnectError("no DNS")
    monkeypatch.setattr(httpx, "Client", FakeClient)
    text = "Cite https://no-such-domain-xyz.invalid/ source."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "external_url")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_http_head(m, 2.0) is False


# ─── memory file ref ─────────────────────────────────────────────────


def test_memory_file_ref_exists(tmp_path, monkeypatch):
    """Memory ref pattern requires ~/.claude/projects/.../memory/<name>.md path."""
    # Build a fake home with a memory file
    mem_dir = tmp_path / ".claude" / "projects" / "test-proj" / "memory"
    mem_dir.mkdir(parents=True)
    mem_file = mem_dir / "test_memory.md"
    mem_file.write_text("dummy")
    # Make ~ expand to our tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))
    text = "See `~/.claude/projects/test-proj/memory/test_memory.md` for context."
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "memory_file_ref")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_memory_file_exists(m) is True


def test_memory_file_ref_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    text = "See `~/.claude/projects/test-proj/memory/never_made.md`"
    config = ev.load_config()
    rule = next(r for r in config.rules if r.id == "memory_file_ref")
    m = rule.pattern.search(text)
    assert m is not None
    assert ev._verify_memory_file_exists(m) is False


# ─── per-proposal evaluation ─────────────────────────────────────────


def test_evaluate_proposal_passes_with_real_commit(tmp_path, monkeypatch):
    import subprocess
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ev.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    skill = tmp_path / "good-skill" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text(
        f"# Good Skill\n\nCites the fix in commit `{head}` of the repo.\n"
    )
    config = ev.load_config()
    report = ev.evaluate_proposal(skill, config)
    assert report.passed is True
    assert report.verified_refs >= 1


def test_evaluate_proposal_rejects_no_citation(tmp_path):
    skill = tmp_path / "no-cite" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# Skill\n\nNo evidence cited here, just claims.\n")
    config = ev.load_config()
    report = ev.evaluate_proposal(skill, config)
    assert report.passed is False
    assert "no citation patterns matched" in report.reject_reason


def test_evaluate_proposal_rejects_failed_verification(tmp_path):
    skill = tmp_path / "bad-cite" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("# Skill\n\nCites `deadbeef9999` non-existent commit.\n")
    config = ev.load_config()
    report = ev.evaluate_proposal(skill, config)
    assert report.passed is False
    assert "verified refs" in report.reject_reason.lower() or "failed verification" in report.reject_reason.lower()
    assert report.matches_by_rule.get("commit_hash", 0) == 1


# ─── Partition test ──────────────────────────────────────────────────


def test_partition_moves_dirs_and_writes_audit(tmp_path):
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    p1 = proposals / "skill-a"
    p1.mkdir()
    (p1 / "SKILL.md").write_text("a")
    p2 = proposals / "skill-b"
    p2.mkdir()
    (p2 / "SKILL.md").write_text("b")
    r1 = ev.ProposalReport(skill_md=p1 / "SKILL.md", passed=True, verified_refs=1)
    r2 = ev.ProposalReport(
        skill_md=p2 / "SKILL.md", passed=False, reject_reason="test reject"
    )
    passed, rejected = ev.partition_proposals(proposals, [r1, r2])
    assert passed == 1
    assert rejected == 1
    assert (proposals / "passed-existence" / "skill-a" / "SKILL.md").is_file()
    assert (proposals / "rejected" / "skill-b" / "SKILL.md").is_file()
    audit_path = proposals / "_evidence_lint_audit.json"
    assert audit_path.is_file()
    audit = json.loads(audit_path.read_text())
    assert len(audit) == 2
    skill_dirs = {e["skill_dir"] for e in audit}
    assert skill_dirs == {"skill-a", "skill-b"}


# ─── CLI smoke ───────────────────────────────────────────────────────


def test_cli_main_smoke(tmp_path, capsys):
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    p = proposals / "fake-skill"
    p.mkdir()
    (p / "SKILL.md").write_text("# No evidence at all.\n")
    exit_code = ev.main([str(proposals)])
    assert exit_code == 0
    # Rejected because no citation
    assert (proposals / "rejected" / "fake-skill" / "SKILL.md").is_file()


def test_cli_missing_dir():
    assert ev.main(["/nonexistent/path/xyz"]) == 1


def test_cli_bad_arg_count():
    assert ev.main([]) == 1
    assert ev.main(["a", "b"]) == 1
