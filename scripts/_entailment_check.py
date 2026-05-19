"""Entailment checker (Step 3b) — semantic claim-vs-evidence gate.

After `_evidence_lint.py` Step 3a verifies that citations EXIST, this
Step 3b verifies that the cited content actually SUPPORTS the claim
made in the SKILL.md. Existence ≠ entailment: a SKILL.md can cite a
real file but quote it wrongly, or cite a real commit but misrepresent
its diff.

Architecture: cross-vendor isolation (CoEvoSkills paper anti-pattern
fix per panel R1 finding). DeepSeek wrote the proposal (Task #23),
Gemini 3.1 Pro free OAuth verifies it. Different provider, different
bias profile.

Fallback chain when Gemini quota-exhausts:
    1. `gemini --print` CLI (free OAuth, ~30 calls/run typical)
    2. NotebookLM NB-1 General Bali Zero via mcp__notebooklm-mcp
       (when MCP available — Phase 2 hooks; Phase 1 logs warning
       and rejects on quota exhaust as fail-closed default)

Privacy: EVERY evidence snippet sent to Gemini MUST first pass
`_redact_pii.py` (Symbiosis Law 2 + UU PDP — panel R3 BLOCKING
defense in depth).

CLI:
    python3 scripts/_entailment_check.py <passed-existence_dir>

Proposals that pass go to `passed/` (sibling of `passed-existence/`),
those that fail go to `rejected/` with a JSON audit log.

Exit codes:
    0  Pipeline completed (proposals partitioned on disk)
    1  Fatal error (config / IO / gemini CLI missing)
    2  Gemini quota exhausted AND no fallback available — fail-closed

Phase 1 — Step 3b per spec §"Architecture".
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

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
REDACTOR_SCRIPT = REPO_ROOT / "scripts" / "_redact_pii.py"

# Gemini CLI invocation. Free OAuth tier — no API key in env, OAuth
# flow handled by the gemini binary at first use.
GEMINI_CLI = os.environ.get("GEMINI_CLI", "gemini")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")
GEMINI_TIMEOUT_SEC = int(os.environ.get("GEMINI_TIMEOUT_SEC", "120"))

# Prompt template — terse, structured output, fail-closed framing.
# Gemini returns either "YES" or "NO" plus a one-line rationale.
# Any other output → treat as quota-exhausted / parse error → reject.
ENTAILMENT_PROMPT = """You are a strict logical entailment verifier for an auto-evolving
agent library. The proposed entry below cites evidence to support a
claim. Your single job: decide whether the cited content ACTUALLY
SUPPORTS the claim, or whether the citation is misrepresented.

Output format (single line):
    VERDICT: YES — <≤80 char rationale>
    VERDICT: NO — <≤80 char rationale>

VERDICT YES only if the cited content DIRECTLY supports the claim.
VERDICT NO if: cited content contradicts the claim, cited content
doesn't address the claim, cited content is generic boilerplate that
the proposal misrepresents as evidence, OR the cited content is
ambiguous and the proposal overstates its certainty.

When in doubt, default to NO — this is a fail-closed pipeline. The
human reviewer prefers a false-rejection (lose a good proposal) over
a false-acceptance (a hallucinated pattern enters the library).

═══ PROPOSAL ═══════════════════════════════════════════════════════
{proposal}

═══ CITED EVIDENCE (already redacted for privacy) ══════════════════
{evidence}
═══════════════════════════════════════════════════════════════════
"""

# Regex extracting citations from a SKILL.md — same patterns as
# evidence-rules.yaml. Kept inline (NOT loaded from yaml) because
# this module needs the actual content of the citation to feed to
# Gemini, not just verify it exists.
_FILE_LINE_RE = re.compile(r"`([a-zA-Z0-9_./~\-]+(?:\.[a-zA-Z0-9]+)?):(\d+)(?:-(\d+))?`")
_COMMIT_RE = re.compile(r"\b([0-9a-f]{8,40})\b")
_URL_RE = re.compile(r"https?://[^\s)>\]`]+")


class EntailmentError(RuntimeError):
    """Raised on fatal entailment failures (CLI missing, quota exhaust)."""


# ─── Evidence snippet extraction ─────────────────────────────────────


def extract_evidence_snippets(proposal_text: str) -> list[str]:
    """Pull the actual cited content (file slice, commit message, URL
    title) so Gemini can compare it to the claim. Limits to first 8
    citations to bound the prompt size.
    """
    snippets: list[str] = []
    MAX = 8

    for m in _FILE_LINE_RE.finditer(proposal_text):
        if len(snippets) >= MAX:
            break
        path_raw = m.group(1)
        line_start = int(m.group(2))
        line_end_str = m.group(3) if m.lastindex and m.lastindex >= 3 else None
        line_end = int(line_end_str) if line_end_str else line_start
        p = Path(os.path.expanduser(path_raw))
        if not p.is_absolute():
            p = REPO_ROOT / path_raw
        if not p.is_file():
            continue
        try:
            with p.open(errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        # Take ±5 lines around the cited range for context
        ctx_start = max(0, line_start - 5)
        ctx_end = min(len(lines), line_end + 5)
        slice_text = "".join(lines[ctx_start:ctx_end])
        snippets.append(
            f"[file:line] {path_raw}:{line_start}-{line_end}\n"
            f"```\n{slice_text}```"
        )

    for m in _COMMIT_RE.finditer(proposal_text):
        if len(snippets) >= MAX:
            break
        sha = m.group(1)
        try:
            r = subprocess.run(
                ["git", "show", "--no-patch", "--format=%s%n%b", sha],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        if r.returncode != 0:
            continue
        snippets.append(f"[commit] {sha}\n```\n{r.stdout.strip()[:2000]}\n```")

    for m in _URL_RE.finditer(proposal_text):
        if len(snippets) >= MAX:
            break
        url = m.group(0)
        # We don't actually fetch URLs here — too expensive and
        # asymmetric (Gemini may have its own knowledge of the URL).
        # Just list the URL as evidence pointer.
        snippets.append(f"[external_url] {url}")

    return snippets


# ─── Redaction wrapper ───────────────────────────────────────────────


def redact(text: str) -> str:
    """Pipe text through scripts/_redact_pii.py.

    Fail-closed: if redactor exits non-zero or returns empty, raise
    EntailmentError to abort the entire proposal (Symbiosis Law 2
    hard rule — panel R3 BLOCKING #2 + R4 BLOCKING #1).
    """
    if not REDACTOR_SCRIPT.is_file():
        raise EntailmentError(
            f"redactor missing at {REDACTOR_SCRIPT} — fail-closed per "
            f"Symbiosis Law 2 (OSINT data MUST NOT leave Pro)"
        )
    try:
        r = subprocess.run(
            ["python3", str(REDACTOR_SCRIPT)],
            input=text,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise EntailmentError(
            f"redactor invocation failed: {type(e).__name__}: {e}"
        ) from e
    if r.returncode != 0:
        raise EntailmentError(
            f"redactor exited {r.returncode}: {r.stderr[:300]}"
        )
    out = r.stdout
    if not out or not out.strip():
        raise EntailmentError("redactor returned empty output — fail-closed")
    return out


# ─── Gemini invocation ───────────────────────────────────────────────


_QUOTA_PATTERNS = [
    re.compile(r"\bquota\b", re.IGNORECASE),
    re.compile(r"\brate.?limit", re.IGNORECASE),
    re.compile(r"\b429\b"),
    re.compile(r"\bRESOURCE_EXHAUSTED\b"),
    re.compile(r"out of (extra )?usage", re.IGNORECASE),
]


def _detect_quota_exhaust(text: str) -> bool:
    return any(p.search(text) for p in _QUOTA_PATTERNS)


@dataclass
class GeminiVerdict:
    raw_output: str
    verdict: str  # "YES" | "NO" | "UNKNOWN"
    rationale: str
    quota_exhausted: bool


def call_gemini_verdict(prompt: str) -> GeminiVerdict:
    """Invoke `gemini --print` CLI, parse VERDICT line, detect quota.

    Returns GeminiVerdict; never raises on transient errors — only
    raises EntailmentError if the gemini CLI is missing entirely.
    """
    if not shutil.which(GEMINI_CLI):
        raise EntailmentError(
            f"gemini CLI not found on PATH (looked for {GEMINI_CLI!r}). "
            f"Install via npm i -g @google/gemini-cli + run `gemini` once "
            f"to complete OAuth flow."
        )
    try:
        r = subprocess.run(
            [GEMINI_CLI, "-m", GEMINI_MODEL, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=GEMINI_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GeminiVerdict(
            raw_output="(timeout)",
            verdict="UNKNOWN",
            rationale=f"gemini CLI timed out after {GEMINI_TIMEOUT_SEC}s",
            quota_exhausted=False,
        )

    out = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
    if r.returncode != 0 and _detect_quota_exhaust(out):
        return GeminiVerdict(
            raw_output=out[:500],
            verdict="UNKNOWN",
            rationale="quota exhausted",
            quota_exhausted=True,
        )
    if r.returncode != 0:
        return GeminiVerdict(
            raw_output=out[:500],
            verdict="UNKNOWN",
            rationale=f"gemini exited {r.returncode}: {out[:200]}",
            quota_exhausted=False,
        )

    # Parse the VERDICT line. Be tolerant to leading whitespace and
    # markdown emphasis.
    verdict = "UNKNOWN"
    rationale = ""
    for line in r.stdout.splitlines():
        line = line.strip().lstrip("*").lstrip("#").strip()
        m = re.match(
            r"VERDICT\s*[:=]\s*(YES|NO|UNKNOWN)\b\s*(?:[—\-:]\s*(.*))?",
            line,
            re.IGNORECASE,
        )
        if m:
            verdict = m.group(1).upper()
            rationale = (m.group(2) or "").strip()[:200]
            break

    return GeminiVerdict(
        raw_output=r.stdout[:1000],
        verdict=verdict,
        rationale=rationale,
        quota_exhausted=False,
    )


# ─── Per-proposal entailment evaluation ──────────────────────────────


@dataclass
class EntailmentReport:
    skill_md: Path
    passed: bool = False
    verdict: str = "UNKNOWN"
    rationale: str = ""
    snippet_count: int = 0
    reject_reason: str = ""


def evaluate_proposal(skill_md: Path) -> EntailmentReport:
    report = EntailmentReport(skill_md=skill_md)
    try:
        proposal_text = skill_md.read_text(errors="replace")
    except OSError as e:
        report.reject_reason = f"unreadable SKILL.md: {e}"
        return report

    snippets = extract_evidence_snippets(proposal_text)
    report.snippet_count = len(snippets)
    if not snippets:
        # Should never happen after _evidence_lint.py gate — defensive
        report.reject_reason = "no extractable evidence snippets"
        return report

    evidence_text = "\n\n".join(snippets)[:8000]  # bound prompt size
    try:
        redacted_proposal = redact(proposal_text[:4000])
        redacted_evidence = redact(evidence_text)
    except EntailmentError as e:
        report.reject_reason = f"redaction failed: {e}"
        return report

    prompt = ENTAILMENT_PROMPT.format(
        proposal=redacted_proposal[:4000],
        evidence=redacted_evidence[:6000],
    )
    verdict = call_gemini_verdict(prompt)
    report.verdict = verdict.verdict
    report.rationale = verdict.rationale
    if verdict.quota_exhausted:
        report.reject_reason = (
            "Gemini quota exhausted — fail-closed (Phase 1 has no "
            "NotebookLM fallback wired yet; Phase 2 adds NB-1 path)"
        )
        return report
    if verdict.verdict == "YES":
        report.passed = True
    elif verdict.verdict == "NO":
        report.reject_reason = f"entailment NO: {verdict.rationale}"
    else:
        report.reject_reason = f"verdict UNKNOWN: {verdict.rationale}"
    return report


# ─── Partition: move SKILL.md folders to passed/ or rejected/ ────────


def partition_proposals(
    passed_existence_dir: Path, reports: list[EntailmentReport]
) -> tuple[int, int]:
    proposals_root = passed_existence_dir.parent
    passed_dir = proposals_root / "passed"
    rejected_dir = proposals_root / "rejected"
    passed_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)

    passed_count = 0
    rejected_count = 0
    audit: list[dict[str, Any]] = []

    for report in reports:
        proposal_dir = report.skill_md.parent
        target = (passed_dir if report.passed else rejected_dir) / proposal_dir.name
        try:
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(proposal_dir), str(target))
        except (OSError, shutil.Error) as e:
            logger.error("move %s → %s failed: %s", proposal_dir, target, e)
            continue
        audit.append(
            {
                "skill_dir": proposal_dir.name,
                "passed": report.passed,
                "verdict": report.verdict,
                "rationale": report.rationale,
                "snippet_count": report.snippet_count,
                "reject_reason": report.reject_reason if not report.passed else "",
                "moved_to": str(target.relative_to(proposals_root)),
            }
        )
        if report.passed:
            passed_count += 1
        else:
            rejected_count += 1

    audit_path = proposals_root / "_entailment_check_audit.json"
    try:
        audit_path.write_text(json.dumps(audit, indent=2))
    except OSError as e:
        logger.warning("could not write audit log: %s", e)

    return passed_count, rejected_count


# ─── CLI entrypoint ──────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("ENTAILMENT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s _entailment_check: %(message)s",
    )
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        sys.stderr.write("Usage: _entailment_check.py <passed-existence_dir>\n")
        return 1
    passed_existence_dir = Path(argv[0])
    if not passed_existence_dir.is_dir():
        sys.stderr.write(f"passed-existence dir not found: {passed_existence_dir}\n")
        return 1

    skill_md_files = [
        c / "SKILL.md"
        for c in passed_existence_dir.iterdir()
        if c.is_dir() and (c / "SKILL.md").is_file()
    ]
    logger.info(
        "entailment-checking %d proposals in %s",
        len(skill_md_files),
        passed_existence_dir,
    )

    reports: list[EntailmentReport] = []
    quota_hit = False
    for skill_md in skill_md_files:
        try:
            report = evaluate_proposal(skill_md)
        except EntailmentError as e:
            logger.error("fatal entailment error on %s: %s", skill_md, e)
            return 1
        if "quota exhausted" in report.reject_reason:
            quota_hit = True
        reports.append(report)

    passed, rejected = partition_proposals(passed_existence_dir, reports)
    logger.info("entailment result: %d passed, %d rejected", passed, rejected)

    # If quota hit on ANY proposal, surface to caller via exit 2 so the
    # wrapper can flag a Telegram alert (operator may want to retry
    # the run tomorrow).
    if quota_hit:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
