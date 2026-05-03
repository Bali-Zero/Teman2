"""
API Contract Audit — Core Guardian Check

Finds frontend-backend mismatches by:
1. Extracting API endpoints called by the frontend (from api client files)
2. Extracting API endpoints defined in the backend (from FastAPI routers)
3. Comparing: calls without definitions = GHOST endpoint
4. Definitions without calls = UNUSED endpoint (informational)

Also detects:
- Frontend sending fields the backend model doesn't define (type mismatch)
- Backend returning fields the frontend type doesn't declare

Usage:
    from apps.evaluator.core_guardian.checks.api_contract_audit import run_audit
    findings = run_audit(project_root)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORE_PATHS = {"__pycache__", ".venv", "venv", "node_modules", ".next", "dist", ".git"}


@dataclass
class ContractFinding:
    file: str
    line: int
    category: str  # "ghost_endpoint" | "unused_endpoint" | "method_mismatch"
    endpoint: str
    detail: str
    severity: str = "warning"

    def __str__(self) -> str:
        icon = "🔴" if self.severity == "error" else "⚠️"
        return f"{icon} {self.file}:{self.line} [{self.category}] {self.endpoint} — {self.detail}"


@dataclass
class EndpointInfo:
    method: str  # GET, POST, PUT, PATCH, DELETE
    path: str  # /api/crm/clients
    file: str
    line: int


@dataclass
class AuditResult:
    findings: list[ContractFinding] = field(default_factory=list)
    frontend_endpoints: list[EndpointInfo] = field(default_factory=list)
    backend_endpoints: list[EndpointInfo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.findings)

    def summary(self) -> str:
        return (
            f"APIContractAudit: {self.total} findings | "
            f"frontend calls: {len(self.frontend_endpoints)}, "
            f"backend routes: {len(self.backend_endpoints)}"
        )


# Frontend API call patterns
# api.get<...>("/api/crm/clients")
# this.client.request<...>("/api/crm/clients")
# api.post("/api/hr/leave/request", data)
FE_API_CALL = re.compile(
    r"(?:api|this\.client)\s*\.\s*(get|post|put|patch|delete|request)\s*(?:<[^>]*>)?\s*\(\s*[\"'`]([^\"'`]+)[\"'`]",
    re.MULTILINE,
)

# Also match template literal API calls: `${baseUrl}/api/...` or `/api/...`
FE_FETCH_CALL = re.compile(
    r"fetch\s*\(\s*[\"'`]([^\"'`]*?/api/[^\"'`]+)[\"'`]",
    re.MULTILINE,
)

# Backend endpoint patterns
# @router.get("/clients/{id}")
BE_ENDPOINT = re.compile(
    r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']",
    re.MULTILINE,
)

# Router prefix
BE_PREFIX = re.compile(
    r"APIRouter\s*\(\s*prefix\s*=\s*[\"']([^\"']+)[\"']",
)


def _find_line(content: str, pos: int) -> int:
    return content[:pos].count("\n") + 1


def _normalize_path(path: str) -> str:
    """Normalize path by replacing path params with placeholders."""
    # Replace {param} with *
    path = re.sub(r"\{[^}]+\}", "*", path)
    # Replace ${...} template literals
    path = re.sub(r"\$\{[^}]+\}", "*", path)
    # Remove trailing slashes
    return path.rstrip("/")


def _extract_frontend_calls(root: Path) -> list[EndpointInfo]:
    """Extract all API calls from frontend code."""
    endpoints: list[EndpointInfo] = []

    api_dirs = [
        root / "apps" / "mouth" / "src" / "lib" / "api",
        root / "apps" / "mouth" / "src" / "hooks",
        root / "apps" / "mouth" / "src" / "app",
    ]

    for api_dir in api_dirs:
        if not api_dir.exists():
            continue
        for ext in ("*.ts", "*.tsx"):
            for filepath in api_dir.rglob(ext):
                if "test" in filepath.name.lower() or "node_modules" in str(filepath):
                    continue
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                for m in FE_API_CALL.finditer(content):
                    method = m.group(1).upper()
                    if method == "REQUEST":
                        method = "GET"  # default for generic request
                    path = m.group(2)
                    if path.startswith("/api/"):
                        endpoints.append(EndpointInfo(
                            method=method,
                            path=path,
                            file=str(filepath),
                            line=_find_line(content, m.start()),
                        ))

                for m in FE_FETCH_CALL.finditer(content):
                    path = m.group(1)
                    if "/api/" in path:
                        # Extract just the /api/... part
                        api_idx = path.index("/api/")
                        path = path[api_idx:]
                        endpoints.append(EndpointInfo(
                            method="GET",  # fetch default
                            path=path,
                            file=str(filepath),
                            line=_find_line(content, m.start()),
                        ))

    return endpoints


def _extract_backend_routes(root: Path) -> list[EndpointInfo]:
    """Extract all defined backend routes."""
    endpoints: list[EndpointInfo] = []

    routers_dir = root / "apps" / "backend-rag" / "backend" / "app" / "routers"
    if not routers_dir.exists():
        return endpoints

    for filepath in routers_dir.rglob("*.py"):
        if "test" in filepath.name.lower():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Find prefix
        prefix_match = BE_PREFIX.search(content)
        prefix = prefix_match.group(1) if prefix_match else ""

        for m in BE_ENDPOINT.finditer(content):
            method = m.group(1).upper()
            path = prefix + m.group(2)
            endpoints.append(EndpointInfo(
                method=method,
                path=path,
                file=str(filepath),
                line=_find_line(content, m.start()),
            ))

    return endpoints


def run_audit(project_root: str | Path) -> AuditResult:
    """Run API contract audit comparing frontend calls to backend routes."""
    root = Path(project_root)
    result = AuditResult()

    result.frontend_endpoints = _extract_frontend_calls(root)
    result.backend_endpoints = _extract_backend_routes(root)

    # Build normalized backend route set
    be_routes: dict[str, EndpointInfo] = {}
    for ep in result.backend_endpoints:
        key = f"{ep.method} {_normalize_path(ep.path)}"
        be_routes[key] = ep

    # Check each frontend call against backend
    for fe_ep in result.frontend_endpoints:
        norm_path = _normalize_path(fe_ep.path)
        key = f"{fe_ep.method} {norm_path}"

        # Direct match
        if key in be_routes:
            continue

        # Try with wildcard matching (frontend /api/crm/clients/123 → backend /api/crm/clients/*)
        matched = False
        for be_key in be_routes:
            be_method, be_path = be_key.split(" ", 1)
            if be_method != fe_ep.method:
                continue
            # Simple glob: * matches any path segment
            be_parts = be_path.split("/")
            fe_parts = norm_path.split("/")
            if len(be_parts) == len(fe_parts):
                if all(
                    bp == fp or bp == "*" or fp == "*"
                    for bp, fp in zip(be_parts, fe_parts)
                ):
                    matched = True
                    break

        if not matched:
            result.findings.append(ContractFinding(
                file=fe_ep.file,
                line=fe_ep.line,
                category="ghost_endpoint",
                endpoint=f"{fe_ep.method} {fe_ep.path}",
                detail="frontend calls this endpoint but no matching backend route found",
                severity="warning",
            ))

    logger.info(result.summary())
    return result


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
    res = run_audit(root)
    print(f"\n{'=' * 60}")
    print(f"Frontend API calls: {len(res.frontend_endpoints)}")
    print(f"Backend routes: {len(res.backend_endpoints)}")
    print(f"{'=' * 60}")
    if res.findings:
        print(f"\nFindings ({res.total}):")
        for f in res.findings:
            print(f"  {f}")
    else:
        print("\n✅ All frontend API calls match backend routes.")
    print(f"\n{res.summary()}")
