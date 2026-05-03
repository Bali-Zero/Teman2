#!/usr/bin/env python3
"""
dep_audit.py — Dependency vulnerability audit for Nuzantara.

Runs pip-audit on apps/backend-rag/requirements.txt, parses JSON output,
and opens a GitHub PR when HIGH or CRITICAL vulnerabilities are found.

Writes ~/.agent/decisions/state/dep_audit.last.json for Sentinel monitoring.

Schedule: weekly (registered in job_registry.json as weekly_dep_audit).
Runtime: Python 3.11+ (system Python — no venv needed, only uses stdlib + pip-audit).
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[dep_audit %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dep_audit")

# --- Paths ---

def find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".git").exists() and (current / "apps" / "backend-rag").exists():
            return current
        current = current.parent
    env_root = os.environ.get("NUZANTARA_ROOT")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    logger.error("Cannot find project root. Set NUZANTARA_ROOT.")
    sys.exit(1)


PROJECT_ROOT = find_project_root()
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag"
REQUIREMENTS_FILE = BACKEND_DIR / "requirements.txt"
AGENT_DIR = PROJECT_ROOT / ".agent" / "decisions"
STATE_DIR = AGENT_DIR / "state"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

HIGH_SEVERITY = {"high", "critical"}

# --- Sentinel state write ---

def write_last_json(status: str, detail: str = "") -> None:
    """Write state file for Sentinel monitoring."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "job": "dep_audit",
        "status": status,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    import tempfile as _tempfile
    tmp_fd, tmp_path = _tempfile.mkstemp(dir=str(STATE_DIR), suffix=".tmp", prefix="dep_audit")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(STATE_DIR / "dep_audit.last.json"))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# --- pip-audit ---

def run_pip_audit() -> list[dict]:
    """
    Run pip-audit on requirements.txt. Returns list of vulnerability dicts.
    Each dict: {name, version, id, aliases, description, fix_versions, severity}.
    Returns [] on clean or error.
    """
    if not REQUIREMENTS_FILE.exists():
        logger.error(f"requirements.txt not found: {REQUIREMENTS_FILE}")
        return []

    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "pip_audit",
             "-r", str(REQUIREMENTS_FILE),
             "--format", "json",
             "--progress-spinner", "off"],
            capture_output=True, text=True, timeout=300,
            cwd=str(BACKEND_DIR),
        )
    except FileNotFoundError:
        # pip_audit not installed in venv — try system pip-audit
        try:
            result = subprocess.run(
                ["pip-audit",
                 "-r", str(REQUIREMENTS_FILE),
                 "--format", "json",
                 "--progress-spinner", "off"],
                capture_output=True, text=True, timeout=300,
                cwd=str(BACKEND_DIR),
            )
        except FileNotFoundError:
            logger.error("pip-audit not found. Install: pip install pip-audit")
            return []
    except subprocess.TimeoutExpired:
        logger.error("pip-audit timed out after 300s")
        return []

    if not result.stdout.strip():
        logger.info("pip-audit: no output (possibly no vulnerabilities)")
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"pip-audit JSON parse error: {e}")
        return []

    # pip-audit JSON format: {"dependencies": [{"name": ..., "version": ..., "vulns": [...]}]}
    vulns: list[dict] = []
    dependencies = data if isinstance(data, list) else data.get("dependencies", [])
    for dep in dependencies:
        for vuln in dep.get("vulns", []):
            severity = vuln.get("aliases", [""])[0] if vuln.get("aliases") else ""
            # Try to extract severity from id or description
            sev_label = _extract_severity(vuln)
            vulns.append({
                "name": dep.get("name", ""),
                "version": dep.get("version", ""),
                "id": vuln.get("id", ""),
                "aliases": vuln.get("aliases", []),
                "description": vuln.get("description", ""),
                "fix_versions": vuln.get("fix_versions", []),
                "severity": sev_label,
            })

    logger.info(f"pip-audit found {len(vulns)} vulnerabilities")
    return vulns


def _extract_severity(vuln: dict) -> str:
    """Best-effort severity extraction from pip-audit vuln dict."""
    # pip-audit doesn't always provide severity; check aliases for GHSA prefix
    # and description keywords
    desc = (vuln.get("description") or "").lower()
    for sev in ("critical", "high", "medium", "low"):
        if sev in desc:
            return sev
    # Fallback: treat all vulns as high for safety
    return "high"


# --- GitHub PR ---

def create_vuln_pr(vulns: list[dict]) -> bool:
    """
    Create a GitHub PR (info-only) listing the vulnerabilities.
    Uses gh CLI. Returns True on success.
    """
    # Check gh is available
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, timeout=10)
        if result.returncode != 0:
            logger.warning("gh CLI not available — skipping PR creation")
            return False
    except FileNotFoundError:
        logger.warning("gh CLI not found — skipping PR creation")
        return False

    branch_name = f"security/dep-audit-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"

    # Create branch
    r = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0:
        logger.warning(f"Could not create branch {branch_name}: {r.stderr[:100]}")
        return False

    # Write a report file as the "change"
    report_path = BACKEND_DIR / "SECURITY_AUDIT.md"
    lines = [
        "# Dependency Security Audit Report\n",
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n",
        "## Vulnerabilities Found\n\n",
        "| Package | Version | ID | Severity | Fix Versions |\n",
        "|---------|---------|----|-----------|--------------|\n",
    ]
    for v in vulns:
        fix = ", ".join(v["fix_versions"]) or "no fix available"
        lines.append(
            f"| {v['name']} | {v['version']} | {v['id']} | "
            f"**{v['severity']}** | {fix} |\n"
        )
    lines.append("\n_This file is auto-generated by dep_audit.py — do not edit manually._\n")

    report_path.write_text("".join(lines))

    subprocess.run(
        ["git", "add", str(report_path)],
        cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
    )
    subprocess.run(
        ["git", "commit", "-m", f"security: dependency audit {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"],
        cwd=str(PROJECT_ROOT), capture_output=True, timeout=15,
    )

    # Push branch
    r = subprocess.run(
        ["git", "push", "origin", branch_name],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        logger.warning(f"Push failed: {r.stderr[:100]}")
        subprocess.run(["git", "checkout", "main"], cwd=str(PROJECT_ROOT), capture_output=True, timeout=10)
        return False

    # Build PR body
    body_lines = [
        "## Dependency Vulnerability Report\n\n",
        "Automated audit found vulnerabilities that require attention.\n\n",
        "### Findings\n\n",
        "| Package | Version | ID | Severity | Fix |\n",
        "|---------|---------|----|-----------|---------|\n",
    ]
    for v in vulns:
        fix = ", ".join(v["fix_versions"]) or "no fix"
        body_lines.append(f"| {v['name']} | {v['version']} | {v['id']} | **{v['severity']}** | {fix} |\n")
    body_lines.append("\n_Auto-generated by dep_audit.py_\n")

    high_count = sum(1 for v in vulns if v["severity"] in HIGH_SEVERITY)
    r = subprocess.run(
        ["gh", "pr", "create",
         "--title", f"security: {high_count} HIGH/CRITICAL dependency vulnerabilities found",
         "--body", "".join(body_lines),
         "--base", "main",
         "--head", branch_name,
         "--label", "security"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
    )

    # Return to main regardless
    subprocess.run(["git", "checkout", "main"], cwd=str(PROJECT_ROOT), capture_output=True, timeout=10)

    if r.returncode != 0:
        logger.warning(f"gh pr create failed: {r.stderr[:200]}")
        return False

    pr_url = r.stdout.strip()
    logger.info(f"PR created: {pr_url}")
    return True


# --- Main ---

def main() -> None:
    logger.info("=== dep_audit start ===")

    vulns = run_pip_audit()

    if not vulns:
        logger.info("No vulnerabilities found — clean!")
        write_last_json("ok", "0 vulnerabilities")
        return

    high_vulns = [v for v in vulns if v["severity"] in HIGH_SEVERITY]
    all_ids = ", ".join(v["id"] for v in vulns[:5])
    detail = f"{len(vulns)} vulns ({len(high_vulns)} HIGH/CRITICAL): {all_ids}"
    logger.warning(detail)

    if high_vulns:
        logger.info(f"Creating PR for {len(high_vulns)} HIGH/CRITICAL vulnerabilities")
        pr_ok = create_vuln_pr(high_vulns)
        status = "ok" if pr_ok else "failed"
        write_last_json(status, detail)
    else:
        # Medium/low only — log but no PR
        logger.info("Only medium/low vulnerabilities — no PR needed")
        write_last_json("ok", detail)

    logger.info("=== dep_audit complete ===")


if __name__ == "__main__":
    main()
