"""Audit silent `except` handlers in apps/backend-rag/backend/.

Silent = handler body does not re-raise, does not call a logger/logging,
and does not call any name containing 'log'/'audit'/'trace'/'report'.

Severity heuristic:
  critical: path touches auth | security | consent | pii | gdpr | crm/write
  high:     path touches crm | client | kg | llm | middleware | channels
  medium:   everything else

Emits JSON: {generated_at, total, by_module, by_severity, entries:[...]}
"""
from __future__ import annotations
import ast
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

BACKEND = Path("apps/backend-rag/backend")

LOG_PATTERN = re.compile(r"\b(logger|logging|log|audit|trace|report|capture_exception|sentry)\b", re.I)

CRITICAL_HINTS = (
    "/auth", "/security", "/consent", "/pii", "/gdpr",
    "crm_client", "crm/clients", "crm/write", "hybrid_auth",
    "jwt", "password", "token", "secret",
)
HIGH_HINTS = (
    "/crm", "/client", "/kg", "/llm", "/middleware", "/channels",
    "/ocr", "/drive", "/payments", "/billing", "/hr",
)


@dataclass
class Finding:
    path: str
    line: int
    end_line: int
    module: str
    handler_type: str          # "bare", "Exception", "BaseException", "<other>"
    body_kind: str             # "pass", "continue", "break", "return_none", "return_literal", "ellipsis"
    severity: str
    snippet: str


def classify_severity(rel_path: str) -> str:
    p = rel_path.lower()
    if any(h in p for h in CRITICAL_HINTS):
        return "critical"
    if any(h in p for h in HIGH_HINTS):
        return "high"
    return "medium"


def module_of(rel_path: str) -> str:
    parts = rel_path.split("/")
    try:
        i = parts.index("backend")
    except ValueError:
        return parts[0] if parts else "unknown"
    tail = parts[i + 1 : i + 4]
    return "/".join(tail) if tail else "backend"


def handler_name(handler: ast.ExceptHandler) -> str:
    if handler.type is None:
        return "bare"
    try:
        return ast.unparse(handler.type)
    except Exception:
        return "<unknown>"


def body_is_silent(body: list[ast.stmt]) -> tuple[bool, str]:
    """Return (silent, body_kind). Silent = no raise, no logging call, no side effect worth auditing."""
    if len(body) != 1:
        return False, ""
    stmt = body[0]
    # Pass
    if isinstance(stmt, ast.Pass):
        return True, "pass"
    # Continue / break
    if isinstance(stmt, ast.Continue):
        return True, "continue"
    if isinstance(stmt, ast.Break):
        return True, "break"
    # Bare ellipsis
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
        return True, "ellipsis"
    # Return None / return constant
    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return True, "return_none"
        if isinstance(stmt.value, ast.Constant):
            return True, "return_literal"
        # return [] or return {} or return ()
        if isinstance(stmt.value, (ast.List, ast.Dict, ast.Tuple, ast.Set)):
            return True, "return_empty_container"
    return False, ""


def contains_raise_or_log(body: list[ast.stmt]) -> bool:
    """Check whether any statement in body re-raises or logs."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            try:
                src = ast.unparse(node.func)
            except Exception:
                continue
            if LOG_PATTERN.search(src):
                return True
    return False


def walk_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        # Skip tests, migrations, virtualenvs, vendored
        parts = set(p.parts)
        if any(s in parts for s in {"tests", "migrations", ".venv", "venv", "__pycache__", "alembic"}):
            continue
        yield p


def scan_file(path: Path, repo_root: Path) -> list[Finding]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    findings: list[Finding] = []
    source_lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if contains_raise_or_log(node.body):
            continue
        silent, kind = body_is_silent(node.body)
        if not silent:
            continue
        rel = path.relative_to(repo_root).as_posix()
        snippet_start = max(node.lineno - 1, 0)
        snippet_end = min(snippet_start + 3, len(source_lines))
        snippet = "\n".join(source_lines[snippet_start:snippet_end])
        findings.append(Finding(
            path=rel,
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            module=module_of(rel),
            handler_type=handler_name(node),
            body_kind=kind,
            severity=classify_severity(rel),
            snippet=snippet,
        ))
    return findings


def main(out_path: Path) -> int:
    repo_root = Path.cwd()
    target = repo_root / BACKEND
    if not target.exists():
        print(f"Target not found: {target}", file=sys.stderr)
        return 2
    findings: list[Finding] = []
    for p in walk_py_files(target):
        findings.extend(scan_file(p, repo_root))
    findings.sort(key=lambda f: (f.severity != "critical", f.severity != "high", f.path, f.line))

    by_module: dict[str, int] = {}
    by_severity: dict[str, int] = {"critical": 0, "high": 0, "medium": 0}
    by_kind: dict[str, int] = {}
    for f in findings:
        by_module[f.module] = by_module.get(f.module, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        by_kind[f.body_kind] = by_kind.get(f.body_kind, 0) + 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": BACKEND.as_posix(),
        "total": len(findings),
        "by_severity": by_severity,
        "by_module": dict(sorted(by_module.items(), key=lambda x: -x[1])),
        "by_kind": by_kind,
        "entries": [asdict(f) for f in findings],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} — total={report['total']} severity={by_severity}")
    top = list(by_module.items())[:8]
    print("Top modules:")
    for m, n in top:
        print(f"  {n:4d}  {m}")
    return 0


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-1-pdp-audit.json")
    sys.exit(main(out))
