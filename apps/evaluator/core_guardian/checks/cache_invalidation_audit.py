"""
Cache Invalidation Audit — Core Guardian Check

Trova endpoint mutation (POST/PUT/PATCH/DELETE) senza chiamata a invalidate_cache().
Integrato nel Core Guardian watchdog ogni 3h.

Usage:
    from apps.evaluator.core_guardian.checks.cache_invalidation_audit import run_audit
    findings = run_audit(project_root)
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Decorator patterns che indicano una mutation HTTP
MUTATION_DECORATORS = {".post(", ".put(", ".patch(", ".delete("}

# Nome della funzione di invalidation cache nel progetto
INVALIDATE_CACHE_PATTERN = "invalidate_cache"

# File/directory da ignorare
IGNORE_PATHS = {
    "__pycache__",
    ".venv",
    "venv",
    "migrations",
    "tests",
    "test_",
}


@dataclass
class CacheFinding:
    """Singolo finding: endpoint mutation senza invalidate_cache."""

    file: str
    line: int
    function_name: str
    decorator: str
    severity: str = "warning"  # warning | info

    def __str__(self) -> str:
        return (
            f"⚠️ {self.file}:{self.line} `{self.function_name}` "
            f"[{self.decorator}] — mutation senza invalidate_cache()"
        )


def _should_skip(path: Path) -> bool:
    """Ritorna True se il path va ignorato."""
    parts = {p.lower() for p in path.parts}
    return bool(parts & IGNORE_PATHS) or any(
        p.lower().startswith("test_") for p in path.parts
    )


def _has_cache_invalidation(node: ast.AsyncFunctionDef | ast.FunctionDef, source: str) -> bool:
    """
    Controlla se la funzione (o i suoi sotto-nodi) chiama invalidate_cache.
    Usa sia AST walk che stringa (fallback per pattern dinamici).
    """
    # AST walk per chiamate esplicite
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            # invalidate_cache(...) diretto
            if isinstance(func, ast.Name) and INVALIDATE_CACHE_PATTERN in func.id:
                return True
            # await obj.invalidate_cache(...) o self.cache.invalidate(...)
            if isinstance(func, ast.Attribute) and INVALIDATE_CACHE_PATTERN in func.attr:
                return True

    # Fallback: stringa unparsed (per casi complessi come await cache.delete_pattern(...))
    try:
        fn_source = ast.unparse(node)
        if INVALIDATE_CACHE_PATTERN in fn_source or "cache.delete" in fn_source:
            return True
    except Exception:
        pass

    return False


def _get_mutation_decorator(node: ast.AsyncFunctionDef | ast.FunctionDef) -> str | None:
    """Ritorna il decorator di mutation se presente, altrimenti None."""
    try:
        deco_str = " ".join(ast.unparse(d) for d in node.decorator_list)
        for pattern in MUTATION_DECORATORS:
            if pattern in deco_str:
                return pattern.strip(".(")
        return None
    except Exception:
        return None


def audit_file(filepath: Path) -> list[CacheFinding]:
    """
    Analizza un singolo file Python per mutation senza invalidate_cache.
    Ritorna lista di CacheFinding.
    """
    findings: list[CacheFinding] = []

    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.debug(f"Impossibile leggere {filepath}: {e}")
        return findings

    # Fast path: se non ci sono decorator mutation, skip parse
    has_mutation_syntax = any(p in source for p in MUTATION_DECORATORS)
    if not has_mutation_syntax:
        return findings

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    file_has_any_invalidation = INVALIDATE_CACHE_PATTERN in source

    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue

        mutation_decorator = _get_mutation_decorator(node)
        if not mutation_decorator:
            continue

        # Se il file non ha NESSUNA invalidazione → tutti i mutation endpoint sono findings
        if not file_has_any_invalidation:
            findings.append(
                CacheFinding(
                    file=str(filepath),
                    line=node.lineno,
                    function_name=node.name,
                    decorator=mutation_decorator,
                )
            )
            continue

        # File con alcune invalidazioni → controlla questa specifica funzione
        if not _has_cache_invalidation(node, source):
            findings.append(
                CacheFinding(
                    file=str(filepath),
                    line=node.lineno,
                    function_name=node.name,
                    decorator=mutation_decorator,
                )
            )

    return findings


def run_audit(project_root: Path) -> list[CacheFinding]:
    """
    Esegue l'audit su tutti i router del backend.
    Ritorna lista di CacheFinding (vuota = tutto OK).
    """
    routers_dir = project_root / "apps" / "backend-rag" / "backend" / "app" / "routers"
    if not routers_dir.exists():
        logger.warning(f"Routers dir non trovata: {routers_dir}")
        return []

    all_findings: list[CacheFinding] = []
    scanned = 0

    for filepath in sorted(routers_dir.glob("**/*.py")):
        if _should_skip(filepath):
            continue
        findings = audit_file(filepath)
        all_findings.extend(findings)
        scanned += 1

    logger.info(
        f"Cache invalidation audit: {scanned} file scansionati, "
        f"{len(all_findings)} finding{'s' if len(all_findings) != 1 else ''}"
    )

    return all_findings


def format_report(findings: list[CacheFinding], verbose: bool = False) -> str:
    """Formatta i finding per Telegram/log."""
    if not findings:
        return "✅ Cache invalidation audit: nessun problema trovato"

    lines = [f"⚠️ Cache Invalidation Audit: {len(findings)} endpoint senza invalidate_cache\n"]

    # Raggruppa per file
    by_file: dict[str, list[CacheFinding]] = {}
    for f in findings:
        key = Path(f.file).name
        by_file.setdefault(key, []).append(f)

    for filename, file_findings in sorted(by_file.items()):
        lines.append(f"📄 {filename} ({len(file_findings)} mutation):")
        if verbose:
            for finding in file_findings[:5]:  # max 5 per file in report
                lines.append(f"  • L{finding.line} `{finding.function_name}` [{finding.decorator}]")
            if len(file_findings) > 5:
                lines.append(f"  ... e altri {len(file_findings) - 5}")

    lines.append("\nFix: aggiungere `await invalidate_cache(\"zantara:namespace:*\")` dopo ogni mutation")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    from pathlib import Path as P

    # Trova project root
    root = P(__file__).resolve()
    for _ in range(8):
        if (root / ".git").exists():
            break
        root = root.parent

    findings = run_audit(root)
    print(format_report(findings, verbose=True))
    sys.exit(1 if findings else 0)
