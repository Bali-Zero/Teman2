"""Evidence linter (Step 3a) — deterministic existence gate for proposals.

Reads `agent-library/config/evidence-rules.yaml` and applies each rule
to every `SKILL.md` in a proposals directory. A proposal is PASSED
only if at least one verifiable citation is found AND no citation
fails verification. Failed proposals are moved to `rejected/`,
passed ones to `passed-existence/` (further reviewed by
`_entailment_check.py` Step 3b).

This is the FIRST gate in the anti-hallucination pipeline (Step 3a per
spec). It's pure-Python deterministic — no LLM calls — so it runs in
seconds and cannot be gamed by a proposer.

Five citation types supported (see `evidence-rules.yaml`):
    file_line_ref         file:line resolves on disk
    commit_hash           git rev-parse returns 0
    external_url          HTTP HEAD 2xx/3xx in 2s
    memory_file_ref       ~/.claude/projects/.../memory/<name>.md exists
    cicatrix_scar_ref     section header found in cicatrix-scars.md

CLI:
    python3 scripts/_evidence_lint.py <proposals_dir>

Exit codes:
    0  All present proposals were processed (some may have been rejected;
       partition is on disk under passed-existence/ and rejected/)
    1  Fatal error (config missing, IO error, etc.)

Phase 1 — addresses L10 (extensionless files) from .known-limitations-v1.md.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = REPO_ROOT / "agent-library" / "config" / "evidence-rules.yaml"
CICATRIX_FILE = REPO_ROOT / ".claude" / "rules" / "cicatrix-scars.md"


# ─── Config dataclasses ──────────────────────────────────────────────


@dataclass
class Rule:
    id: str
    description: str
    pattern: re.Pattern[str]
    verify: str
    timeout_sec: float = 2.0


@dataclass
class GateConfig:
    min_verified_refs: int = 1
    dedup_min_score: float = 1.5
    reject_no_citation: bool = True


@dataclass
class EvidenceConfig:
    rules: list[Rule]
    gate: GateConfig


def load_config(path: Path | str = DEFAULT_RULES) -> EvidenceConfig:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"evidence-rules.yaml not found at {path}")
    raw = yaml.safe_load(path.read_text())
    rules = []
    for r in raw.get("rules", []):
        rules.append(
            Rule(
                id=r["id"],
                description=r.get("description", ""),
                pattern=re.compile(r["pattern"]),
                verify=r["verify"],
                timeout_sec=float(r.get("timeout_sec", 2.0)),
            )
        )
    g = raw.get("gate", {}) or {}
    gate = GateConfig(
        min_verified_refs=int(g.get("min_verified_refs", 1)),
        dedup_min_score=float(g.get("dedup_min_score", 1.5)),
        reject_no_citation=bool(g.get("reject_no_citation", True)),
    )
    return EvidenceConfig(rules=rules, gate=gate)


# ─── Per-rule verifiers ──────────────────────────────────────────────


def _verify_file_exists_and_line_in_range(match: re.Match[str]) -> bool:
    """`<path>:<start>(-<end>)?` — file exists + line numbers in range."""
    path_raw = match.group(1)
    line_start = int(match.group(2))
    line_end_str = match.group(3) if match.lastindex and match.lastindex >= 3 else None
    line_end = int(line_end_str) if line_end_str else line_start

    p = Path(os.path.expanduser(path_raw))
    if not p.is_absolute():
        p = REPO_ROOT / path_raw
    if not p.is_file():
        return False
    try:
        # wc -l equivalent
        with p.open("rb") as fh:
            line_count = sum(1 for _ in fh)
    except OSError:
        return False
    return 1 <= line_start <= line_count and line_start <= line_end <= line_count


def _verify_git_rev_parse(match: re.Match[str]) -> bool:
    sha = match.group(1)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return result.returncode == 0


def _verify_http_head(match: re.Match[str], timeout_sec: float) -> bool:
    url = match.group(0)
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
    except ValueError:
        return False
    try:
        # Use httpx via subprocess-less import to avoid network in test
        # environments unless explicitly enabled. Test fixture monkeypatches
        # this function entirely; production uses httpx HEAD.
        import httpx

        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            r = client.head(url)
        return 200 <= r.status_code < 400
    except Exception as e:  # network error, DNS, TLS, etc.
        logger.debug("HEAD failed for %s: %s", url, e)
        return False


def _verify_memory_file_exists(match: re.Match[str]) -> bool:
    path_raw = match.group(0).strip("`")
    p = Path(os.path.expanduser(path_raw))
    return p.is_file()


def _verify_cicatrix_scar_grep(match: re.Match[str]) -> bool:
    header = match.group(0)
    if not CICATRIX_FILE.is_file():
        return False
    try:
        content = CICATRIX_FILE.read_text(errors="replace")
    except OSError:
        return False
    # Header is a fuzzy match — strip emoji / whitespace differences.
    # Compare normalised forms (collapse whitespace).
    norm_header = re.sub(r"\s+", " ", header).strip()
    for line in content.splitlines():
        norm_line = re.sub(r"\s+", " ", line).strip()
        if norm_header in norm_line or norm_line.startswith(norm_header):
            return True
    return False


_VERIFIERS = {
    "file_exists_and_line_in_range": _verify_file_exists_and_line_in_range,
    "git_rev_parse": _verify_git_rev_parse,
    "http_head_2xx_or_3xx": _verify_http_head,  # special-cased (needs timeout)
    "file_exists": _verify_memory_file_exists,
    "section_header_grep_in_cicatrix": _verify_cicatrix_scar_grep,
}


# ─── Per-proposal evaluation ─────────────────────────────────────────


@dataclass
class ProposalReport:
    skill_md: Path
    matches_by_rule: dict[str, int] = field(default_factory=dict)
    verified_refs: int = 0
    failed_refs: list[tuple[str, str]] = field(default_factory=list)
    passed: bool = False
    reject_reason: str = ""


def evaluate_proposal(skill_md: Path, config: EvidenceConfig) -> ProposalReport:
    report = ProposalReport(skill_md=skill_md)
    if not skill_md.is_file():
        report.reject_reason = f"SKILL.md not found: {skill_md}"
        return report
    try:
        text = skill_md.read_text(errors="replace")
    except OSError as e:
        report.reject_reason = f"unreadable SKILL.md: {e}"
        return report

    for rule in config.rules:
        matches = list(rule.pattern.finditer(text))
        if not matches:
            continue
        report.matches_by_rule[rule.id] = len(matches)
        for m in matches:
            verifier = _VERIFIERS.get(rule.verify)
            if verifier is None:
                report.failed_refs.append(
                    (rule.id, f"unknown verifier {rule.verify!r}")
                )
                continue
            try:
                if rule.verify == "http_head_2xx_or_3xx":
                    ok = verifier(m, rule.timeout_sec)  # type: ignore[arg-type]
                else:
                    ok = verifier(m)  # type: ignore[arg-type]
            except Exception as e:
                ok = False
                report.failed_refs.append(
                    (rule.id, f"{type(e).__name__}: {e}: {m.group(0)[:80]}")
                )
            if ok:
                report.verified_refs += 1
            else:
                report.failed_refs.append(
                    (rule.id, f"verification failed: {m.group(0)[:80]}")
                )

    # Gate decision
    if config.gate.reject_no_citation and report.verified_refs == 0:
        if not report.matches_by_rule:
            report.reject_reason = "no citation patterns matched"
        else:
            report.reject_reason = (
                f"citations present but {len(report.failed_refs)} failed verification, "
                f"0 verified (min {config.gate.min_verified_refs})"
            )
        return report
    if report.verified_refs < config.gate.min_verified_refs:
        report.reject_reason = (
            f"only {report.verified_refs} verified refs "
            f"(need ≥{config.gate.min_verified_refs})"
        )
        return report

    # Codex panel R5 BLOCKING #5: strict gate — if ANY matched citation
    # failed verification, reject the whole proposal. Mixing valid +
    # invalid citations weakens the deterministic anti-hallucination
    # gate (the proposer could pad a real citation with bogus ones to
    # ride through). Fail-closed default.
    if report.failed_refs:
        report.reject_reason = (
            f"{report.verified_refs} verified refs PASS but "
            f"{len(report.failed_refs)} other citations failed verification — "
            f"strict gate rejects mixed valid+invalid citation sets "
            f"(first failure: {report.failed_refs[0][1][:120]})"
        )
        return report

    report.passed = True
    return report


# ─── Partition: move SKILL.md folders to passed-existence/ or rejected/ ──


def _proposal_dir_for(skill_md: Path) -> Path:
    """Each SKILL.md lives at proposals/YYYY-MM-DD/<slug>/SKILL.md.
    We move the whole <slug>/ directory so helper files travel with it."""
    return skill_md.parent


def partition_proposals(
    proposals_dir: Path, reports: list[ProposalReport]
) -> tuple[int, int]:
    passed_dir = proposals_dir / "passed-existence"
    rejected_dir = proposals_dir / "rejected"
    passed_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)

    passed_count = 0
    rejected_count = 0
    audit: list[dict[str, Any]] = []

    for report in reports:
        proposal_dir = _proposal_dir_for(report.skill_md)
        target_parent = passed_dir if report.passed else rejected_dir
        target = target_parent / proposal_dir.name
        try:
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(proposal_dir), str(target))
        except (OSError, shutil.Error) as e:
            logger.error(
                "failed to move %s → %s: %s", proposal_dir, target, e
            )
            continue
        audit.append(
            {
                "skill_dir": proposal_dir.name,
                "passed": report.passed,
                "verified_refs": report.verified_refs,
                "failed_refs": [
                    {"rule": r, "reason": reason}
                    for r, reason in report.failed_refs
                ],
                "matches_by_rule": report.matches_by_rule,
                "reject_reason": report.reject_reason if not report.passed else "",
                "moved_to": str(target.relative_to(proposals_dir)),
            }
        )
        if report.passed:
            passed_count += 1
        else:
            rejected_count += 1

    audit_path = proposals_dir / "_evidence_lint_audit.json"
    try:
        audit_path.write_text(json.dumps(audit, indent=2))
    except OSError as e:
        logger.warning("could not write audit log: %s", e)

    return passed_count, rejected_count


# ─── CLI entrypoint ──────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("EVIDENCE_LINT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s _evidence_lint: %(message)s",
    )
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        sys.stderr.write("Usage: _evidence_lint.py <proposals_dir>\n")
        return 1
    proposals_dir = Path(argv[0])
    if not proposals_dir.is_dir():
        sys.stderr.write(f"proposals_dir not found: {proposals_dir}\n")
        return 1
    try:
        config = load_config()
    except FileNotFoundError as e:
        sys.stderr.write(f"{e}\n")
        return 1
    # Find SKILL.md files (skip nested passed-existence/rejected directories
    # in case of re-run on already-partitioned tree)
    skill_md_files: list[Path] = []
    for child in proposals_dir.iterdir():
        if child.is_dir() and child.name not in ("passed-existence", "rejected", "passed"):
            candidate = child / "SKILL.md"
            if candidate.is_file():
                skill_md_files.append(candidate)
    logger.info("evaluating %d SKILL.md files in %s", len(skill_md_files), proposals_dir)
    reports = [evaluate_proposal(p, config) for p in skill_md_files]
    passed, rejected = partition_proposals(proposals_dir, reports)
    logger.info("evidence-lint result: %d passed, %d rejected", passed, rejected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
