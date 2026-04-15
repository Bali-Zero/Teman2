"""Scan backend-rag + mata-garuda for candidate reusable skills.

Philosophy (Sprint 5.2 Week 3-4): seed the Skill Registry with a controlled
dry-run. We extract top-level functions and public class methods whose names
and docstrings suggest they carry a reusable *procedure* (not CRUD). Tests,
private helpers, and dunder methods are excluded. The output is a list of
``SkillCandidate`` dicts (one per eligible function) that a human must
approve before we write any row into the Genome.

Usage:

    # Show what would be ingested, grouped by cell.
    PYTHONPATH=. python backend/scripts/catalog_initial_skills.py --dry-run

    # Actually write (only after reviewing the dry-run).
    PYTHONPATH=. python backend/scripts/catalog_initial_skills.py --apply

    # Point at a custom monorepo root (default: 3 levels up from this file).
    PYTHONPATH=. python backend/scripts/catalog_initial_skills.py --dry-run \\
        --repo-root /path/to/nuzantara

Safety:
- ``--apply`` is off by default; calling without it is a no-op write.
- All candidates start with ``confidence=0.5`` and ``scope='Project'``.
- Idempotent via ``skill_id = "{cell}:{func_name}@{source_file}"``.
- Cap per run: ``--limit`` (default 50) — we want 30–50 solid seeds, not 200.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ─── Eligibility rules ────────────────────────────────────────────

# Substring rejects — if a function name starts with any of these, skip.
_CRUD_PREFIXES = (
    "get_", "list_", "fetch_", "load_", "read_",
    "create_", "insert_", "add_",
    "update_", "set_", "put_",
    "delete_", "remove_", "drop_",
    "save_",  # generic persistence
)

# Minimum length so we don't catch 1-letter or 2-letter names like ``get``.
_MIN_NAME_LEN = 4

# Directory / path fragments that indicate test or migration files. Candidates
# from these files are never emitted.
_EXCLUDED_PATH_FRAGMENTS = (
    "/tests/", "/test/", "/migrations/", "/__pycache__/", "/.venv/",
    "/node_modules/",
)


def is_eligible_function(name: str) -> bool:
    """Return True when a function name is a plausible skill candidate.

    Reject:
    - dunder (``__init__``, ``__str__`` …)
    - private (leading underscore)
    - test_* or *_test_ patterns
    - too short
    - CRUD verbs (get/list/create/update/delete/save)

    Accept everything else.
    """
    if not name or name.startswith("_"):
        return False
    if name.startswith("test_") or "_test_" in name or name.endswith("_test"):
        return False
    if len(name) < _MIN_NAME_LEN:
        return False
    if any(name.startswith(prefix) for prefix in _CRUD_PREFIXES):
        return False
    return True


def _is_excluded_path(relpath: str) -> bool:
    norm = "/" + relpath.replace("\\", "/").lstrip("/")
    return any(frag in norm for frag in _EXCLUDED_PATH_FRAGMENTS)


# ─── Candidate dataclass ──────────────────────────────────────────


@dataclass
class SkillCandidate:
    """One proposed Skill Registry entry.

    Flat shape (mirrors Genome row): ready to serialise as JSON and — after
    approval — to pass into ``Genome.record_skill`` / ``SkillService.record``.
    """

    cell: str
    skill_id: str
    procedure: str
    precondition: str = ""
    success_criterion: str = ""
    confidence: float = 0.5
    scope: str = "Project"
    source_file: str = ""
    source_line: int = 0
    # Free-form context (e.g. "method of ClassX") — does NOT flow into Genome;
    # kept in the dry-run report for humans.
    context: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Pure extraction from source ──────────────────────────────────


def _make_skill_id(cell_hint: str, func_name: str, relpath: str) -> str:
    """Stable, idempotent id combining cell + function name + short file suffix.

    Short suffix keeps the id readable while avoiding collisions across cells
    that expose the same verb (two ``chunk_text`` in different modules).
    """
    prefix = cell_hint or Path(relpath).parts[0] if relpath else "misc"
    stem = Path(relpath).stem if relpath else "unknown"
    return f"{prefix}:{func_name}@{stem}"


def _docstring_or_fallback(node: ast.AST, func_name: str, relpath: str) -> str:
    """Pull the docstring; fallback to a minimal non-empty procedure string.

    ``Genome.record_skill`` requires a non-empty ``procedure`` (NOT NULL +
    CHECK upstream). Never return empty.
    """
    doc = ast.get_docstring(node)
    if doc and doc.strip():
        # Keep it to one paragraph — first line(s) up to double newline.
        first_para = doc.strip().split("\n\n", 1)[0].strip()
        return first_para
    return f"{func_name} in {relpath}"


def extract_candidates_from_source(
    source: str,
    relpath: str,
    cell_hint: str,
) -> list[SkillCandidate]:
    """Parse *source* and return eligible skill candidates.

    Pure function: no filesystem, no network. Tests drive it with inline
    Python source strings.
    """
    if _is_excluded_path(relpath):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        logger.warning("skip %s: syntax error at line %s", relpath, exc.lineno)
        return []

    candidates: list[SkillCandidate] = []

    # Top-level functions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not is_eligible_function(node.name):
                continue
            candidates.append(SkillCandidate(
                cell=cell_hint,
                skill_id=_make_skill_id(cell_hint, node.name, relpath),
                procedure=_docstring_or_fallback(node, node.name, relpath),
                source_file=relpath,
                source_line=node.lineno,
                context="module-level function",
            ))
        elif isinstance(node, ast.ClassDef):
            # Public methods of classes
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not is_eligible_function(item.name):
                        continue
                    candidates.append(SkillCandidate(
                        cell=cell_hint,
                        skill_id=_make_skill_id(
                            cell_hint, f"{node.name}.{item.name}", relpath,
                        ),
                        procedure=_docstring_or_fallback(item, item.name, relpath),
                        source_file=relpath,
                        source_line=item.lineno,
                        context=f"method of {node.name}",
                    ))
    return candidates


# ─── Tree scan ────────────────────────────────────────────────────


def _infer_cell_hint(relpath: str) -> str:
    """Best-effort: the first segment after ``backend/services/`` or ``mata_garuda``
    becomes the cell name. Falls back to the top-level app name."""
    parts = Path(relpath).parts
    if "services" in parts:
        idx = parts.index("services")
        if idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if not candidate.endswith(".py"):
                return candidate
    if "mata_garuda" in parts:
        idx = parts.index("mata_garuda")
        if idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if not candidate.endswith(".py"):
                return candidate
        return "mata_garuda"
    # Fallback: first directory under the repo root
    if len(parts) >= 2:
        return parts[0]
    return "misc"


def scan_tree(root: Path, limit: int = 50) -> list[SkillCandidate]:
    """Walk *root* for .py files and return candidates up to *limit*.

    Deterministic order (sorted paths) so dry-run output is stable across
    machines / runs.
    """
    root = Path(root)
    candidates: list[SkillCandidate] = []
    for path in sorted(root.rglob("*.py")):
        relpath = str(path.relative_to(root))
        if _is_excluded_path(relpath):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("skip %s: %s", relpath, exc)
            continue
        cell_hint = _infer_cell_hint(relpath)
        cands = extract_candidates_from_source(source, relpath, cell_hint)
        for c in cands:
            candidates.append(c)
            if len(candidates) >= limit:
                logger.warning(
                    "hit limit=%d before finishing tree; truncating. Re-run "
                    "with a higher --limit to see the rest.", limit,
                )
                return candidates
    return candidates


# ─── CLI ──────────────────────────────────────────────────────────


def _dry_run_report(candidates: list[SkillCandidate]) -> dict:
    by_cell = Counter(c.cell for c in candidates)
    by_context = Counter(c.context for c in candidates)
    return {
        "total": len(candidates),
        "by_cell": dict(by_cell.most_common()),
        "by_context": dict(by_context),
        "sample": [c.to_dict() for c in candidates[:10]],
    }


def _apply(candidates: list[SkillCandidate]) -> dict[str, int]:
    """Record each candidate via SkillService. Imported lazily so the dry-run
    path works even without a configured backend."""
    from backend.services.skill.models import SkillRecord  # noqa: E402
    from backend.services.skill.service import SkillService  # noqa: E402

    service = SkillService()
    if not service.is_available:
        logger.error("SkillService not available (cell_core import failed); abort apply.")
        return {"inserted": 0, "updated": 0, "skipped": len(candidates)}
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for c in candidates:
        try:
            record = SkillRecord(
                cell=c.cell or "misc",
                skill_id=c.skill_id,
                procedure=c.procedure,
                precondition=c.precondition,
                success_criterion=c.success_criterion,
                confidence=c.confidence,
                scope=c.scope,
            )
        except Exception as exc:
            logger.warning("skip %s: validation failed (%s)", c.skill_id, exc)
            counts["skipped"] += 1
            continue
        result = service.record(record)
        action = result.get("action", "skipped")
        if action in counts:
            counts[action] += 1
        else:
            counts["skipped"] += 1
    return counts


def _default_repo_root() -> Path:
    # .../apps/backend-rag/backend/scripts/catalog_initial_skills.py
    # parents: [0]scripts, [1]backend, [2]backend-rag, [3]apps, [4]<repo_root>
    return Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root", type=Path, default=_default_repo_root(),
        help="Monorepo root to scan (default: inferred from script location).",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Hard cap on candidates emitted (default: 50).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Only print the report; do not write to the Genome.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually record the candidates (turns off dry-run).",
    )
    parser.add_argument(
        "--subtree", action="append", default=[],
        help=(
            "Restrict scan to this sub-path, relative to repo-root. May be "
            "given multiple times. Defaults to apps/backend-rag and apps/mata-garuda."
        ),
    )
    args = parser.parse_args(argv)

    subtrees = args.subtree or ["apps/backend-rag", "apps/mata-garuda"]
    all_candidates: list[SkillCandidate] = []
    for sub in subtrees:
        target = (args.repo_root / sub).resolve()
        if not target.exists():
            logger.warning("subtree missing, skipping: %s", target)
            continue
        logger.info("scanning %s …", target)
        all_candidates.extend(scan_tree(target, limit=args.limit))
        if len(all_candidates) >= args.limit:
            all_candidates = all_candidates[: args.limit]
            break

    report = _dry_run_report(all_candidates)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.apply:
        logger.info("applying %d candidates …", len(all_candidates))
        counts = _apply(all_candidates)
        print(json.dumps({"apply": counts}, indent=2))
    else:
        logger.info(
            "dry-run complete (%d candidates). Re-run with --apply to write.",
            len(all_candidates),
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
