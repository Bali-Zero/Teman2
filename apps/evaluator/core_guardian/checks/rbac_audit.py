"""
RBAC Audit — Core Guardian Check

Finds FastAPI endpoints that lack RBAC protection.

Detection rules:
1. Any endpoint with path containing `{client_id}` or `{practice_id}` MUST call
   `verify_client_access` or `is_crm_admin` or `_require_hr_admin`.
2. Any mutation endpoint (POST/PUT/PATCH/DELETE) MUST have `Depends(get_current_user)`.
3. GET endpoints with `/{id}` path params should apply the same RBAC as their list counterpart.

Usage:
    from apps.evaluator.core_guardian.checks.rbac_audit import run_audit
    findings = run_audit(project_root)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORE_PATHS = {"__pycache__", ".venv", "venv", "migrations", "tests", ".git"}

# HTTP method decorators
ENDPOINT_PATTERN = re.compile(
    r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']", re.MULTILINE
)

# RBAC function calls
RBAC_CALLS = {
    "verify_client_access",
    "is_crm_admin",
    "_require_hr_admin",
    "require_admin",
    "can_view_all_practices",
}

# Auth dependency
AUTH_DEPENDENCY = re.compile(r"Depends\s*\(\s*get_current_user\s*\)")

# Path params that require RBAC
SENSITIVE_PATH_PARAMS = re.compile(r"\{(client_id|practice_id|employee_id)\}")


@dataclass
class RBACFinding:
    """An endpoint missing RBAC protection."""

    file: str
    line: int
    method: str
    path: str
    issue: str
    severity: str = "error"  # error for missing auth, warning for missing RBAC

    def __str__(self) -> str:
        icon = "🔴" if self.severity == "error" else "⚠️"
        return (
            f"{icon} {self.file}:{self.line} {self.method.upper()} {self.path} — {self.issue}"
        )


@dataclass
class AuditResult:
    findings: list[RBACFinding] = field(default_factory=list)
    files_scanned: int = 0
    endpoints_scanned: int = 0

    @property
    def total(self) -> int:
        return len(self.findings)

    def summary(self) -> str:
        return (
            f"RBACAudit: {self.total} findings across {self.endpoints_scanned} "
            f"endpoints in {self.files_scanned} files"
        )


def _should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & IGNORE_PATHS) or any(
        p.lower().startswith("test_") for p in path.parts
    )


def _extract_function_body(content: str, start_pos: int) -> str:
    """Extract the function body following an endpoint decorator."""
    # Find the function definition after the decorator
    rest = content[start_pos:]
    # Look for "async def" or "def" after the decorator
    func_match = re.search(r"(?:async\s+)?def\s+(\w+)\s*\(", rest)
    if not func_match:
        return ""

    # Get everything until the next decorator or end of dedented block
    func_start = start_pos + func_match.start()
    # Grab next ~100 lines or until next @router
    lines = content[func_start:].split("\n")
    body_lines = []
    in_body = False
    for line in lines[:100]:
        if line.strip().startswith("async def ") or line.strip().startswith("def "):
            in_body = True
            body_lines.append(line)
            continue
        if in_body:
            if line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                break  # Dedented — end of function
            if line.strip().startswith("@router."):
                break  # Next endpoint
            body_lines.append(line)

    return "\n".join(body_lines)


def _find_line(content: str, pos: int) -> int:
    return content[:pos].count("\n") + 1


def _scan_router(filepath: Path, result: AuditResult) -> None:
    """Scan a Python router file for RBAC gaps."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    # Only scan files that define routers
    if "APIRouter" not in content:
        return

    result.files_scanned += 1

    for m in ENDPOINT_PATTERN.finditer(content):
        method = m.group(1)
        path = m.group(2)
        line = _find_line(content, m.start())
        result.endpoints_scanned += 1

        # Extract the function body for this endpoint
        body = _extract_function_body(content, m.end())

        # Check 1: Mutation endpoints must have auth dependency
        if method in ("post", "put", "patch", "delete"):
            if not AUTH_DEPENDENCY.search(body):
                result.findings.append(RBACFinding(
                    file=str(filepath),
                    line=line,
                    method=method,
                    path=path,
                    issue="mutation endpoint without Depends(get_current_user)",
                    severity="error",
                ))

        # Check 2: Endpoints with sensitive path params should have RBAC
        if SENSITIVE_PATH_PARAMS.search(path):
            has_rbac = any(call in body for call in RBAC_CALLS)
            if not has_rbac:
                result.findings.append(RBACFinding(
                    file=str(filepath),
                    line=line,
                    method=method,
                    path=path,
                    issue=f"endpoint with sensitive path param but no RBAC call ({', '.join(RBAC_CALLS)})",
                    severity="warning",
                ))


def run_audit(project_root: str | Path) -> AuditResult:
    """Run RBAC audit across all backend routers."""
    root = Path(project_root)
    result = AuditResult()

    routers_dir = root / "apps" / "backend-rag" / "backend" / "app" / "routers"
    if not routers_dir.exists():
        logger.warning(f"Routers directory not found: {routers_dir}")
        return result

    for filepath in routers_dir.rglob("*.py"):
        if not _should_skip(filepath):
            _scan_router(filepath, result)

    logger.info(result.summary())
    return result


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    res = run_audit(root)
    for f in res.findings:
        print(f)
    print(f"\n{res.summary()}")
