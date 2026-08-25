#!/usr/bin/env python3
"""ingest_target_lint — every ingest entrypoint must name a REGISTRY-MAPPED collection.

Why this exists, measured 2026-08-25
------------------------------------
`infra/eventbus/regulatory_ingest_runner.py` named `legal_unified_2026`. That
string is absent from `backend/core/collection_registry.py`, so:

  * no retrieval path can ever read what it writes — every legal alias in the
    registry resolves to `legal_unified` (physically `legal_unified_hybrid_hybrid`);
  * `LegalIngestionService`'s own preflight REFUSES it — a canonical target
    outside `ALLOWED_CANONICAL_COLLECTIONS` raises `LegalIngestIntegrityError`.

So the runner was not merely writing into a drawer: it could not run at all.
The live `legal_unified_2026` collection (15,410 points / 18 documents) is a
frozen artifact of 2026-05-16 — byte-identical counts in
`research/nb-lifecycle/2026-05-16-r5-phase2-indexing-parity.md:202` — and nothing
has been added to it since.

`apps/backend-rag/scripts/ingest_2026_laws.py` had already been cured the same
way, with the reasoning written in a comment. A comment does not fail. This does.

Modes
-----
  check     declared entrypoints only name registry-mapped collections
  discover  no UNDECLARED ingest entrypoint exists (a new one cannot slip in
            unlinted just by not being added to the list)

Exit: 0 clean · 1 unmapped collection literal · 2 undeclared entrypoint.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Ingest entrypoints: modules that WRITE into a Qdrant collection. Adding one
# without listing it here is caught by `discover`, not by good intentions.
DECLARED_ENTRYPOINTS: tuple[str, ...] = (
    "infra/eventbus/regulatory_ingest_runner.py",
    "apps/backend-rag/scripts/ingest_2026_laws.py",
    "apps/backend-rag/scripts/ingest_desktop_laws.py",
    "apps/backend-rag/scripts/ingest_t0_regulations.py",
    "apps/backend-rag/scripts/ingest_komdigi_social.py",
    "apps/backend-rag/scripts/ingest_tier1_gaps.py",
    "apps/backend-rag/scripts/ingest_tax_genius.py",
    "apps/backend-rag/scripts/ingest_license_procedures.py",
    "apps/backend-rag/scripts/ingest_single_file.py",
    "apps/backend-rag/scripts/ingest_research_g_batch1.py",
    "apps/backend-rag/backend/scripts/ingest_pwc_pocket_tax_book_2026.py",
)

# Paths that look like ingest entrypoints but are not: `discover` would otherwise
# flag them forever. Each needs a reason, because an allowlist without one grows
# until it is the whole tree.
DISCOVERY_ALLOWLIST: dict[str, str] = {
    "apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py":
        "the service itself — it RESOLVES a caller's name, it does not choose one",
    "apps/backend-rag/backend/app/routers/oracle_ingest.py":
        "HTTP router — the collection arrives from the service layer, no literal",
    "apps/backend-rag/scripts/ingest_kbli_notebook_expert.py":
        "OPEN FINDING, deliberately NOT cured here (see kb/inventory/"
        "legal_unified_2026.yaml -> open_findings). It names 'kbli_notebook_expert', "
        "which is absent from BOTH the registry and live Qdrant (14 collections "
        "measured 2026-08-25), and its first act is delete_collection(). Repointing "
        "it at a live KBLI collection would arm a destructive rebuild of 1,873 real "
        "points, so the safe cure is not a rename — it is a decision, and it belongs "
        "to the KBLI squad, not to this one.",
}

DISCOVERY_GLOBS: tuple[str, ...] = (
    "**/*ingest*runner*.py",
    "**/ingest_*.py",
    "**/*_ingestion_service.py",
)

# A test module's collection literal is a FIXTURE, not a chosen production target
# (`test_legal_ingestion_service.py` names 'custom_collection' precisely to prove
# the preflight rejects it). Flagging those would train the reader to ignore this
# gate's output, which is how a gate stops being read.
def _is_test_module(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in rel


SKIP_DIR_PARTS = frozenset({
    ".git", ".worktrees", "node_modules", ".venv", "venv", "__pycache__",
    "site-packages", ".mypy_cache", ".pytest_cache", "dist", "build",
})

# Collection literals as they are actually written at the call sites.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"""collection_name\s*=\s*["']([A-Za-z0-9_.\-]+)["']"""),
    re.compile(r"""COLLECTION_NAME\s*=\s*["']([A-Za-z0-9_.\-]+)["']"""),
    re.compile(r"""["']--collection["']\s*,\s*["']([A-Za-z0-9_.\-]+)["']"""),
    re.compile(r"""\bcollection\s*=\s*["']([A-Za-z0-9_.\-]+)["']"""),
)

# Literals that are a parameter DEFAULT or a documented placeholder rather than a
# chosen target. Kept empty on purpose: today every declared entrypoint names a
# real target, and an exemption list is where this kind of gate goes to die.
LITERAL_EXEMPTIONS: frozenset[str] = frozenset()


def repo_root(start: Path | None = None) -> Path:
    """Repo root, found by marker — never by the caller's cwd.

    The shards run pytest from `apps/backend-rag`; a cwd-relative root would make
    this module report ABSENT for every path it is meant to guard.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise RuntimeError("ingest_target_lint: repo root not found from %s" % here)


def extract_collection_literals(source: str) -> list[str]:
    """Every collection-name literal a module names, in first-seen order."""
    seen: list[str] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(source):
            value = match.group(1)
            if value not in seen:
                seen.append(value)
    return seen


def _load_registry(root: Path):
    sys.path.insert(0, str(root / "apps" / "backend-rag"))
    from backend.core.collection_registry import (  # noqa: E402
        canonicalize_collection_name,
        is_known_collection,
    )
    return is_known_collection, canonicalize_collection_name


def check(
    root: Path | None = None,
    entrypoints: tuple[str, ...] | None = None,
    source_root: Path | None = None,
) -> list[str]:
    """Violations: an entrypoint naming a collection the registry does not map.

    `entrypoints` / `source_root` exist so the guilt test can point the SAME code
    at a synthetic tree. A checker whose failure path is never executed is a
    checker nobody has seen fail.
    """
    root = root or repo_root()
    source_root = source_root or root
    is_known, canonicalize = _load_registry(root)
    violations: list[str] = []
    for rel in (entrypoints if entrypoints is not None else DECLARED_ENTRYPOINTS):
        path = source_root / rel
        if not path.is_file():
            violations.append("%s: declared entrypoint does not exist" % rel)
            continue
        literals = extract_collection_literals(path.read_text(encoding="utf-8"))
        if not literals:
            # A silent zero here is how this gate would become decorative.
            violations.append(
                "%s: declared as an ingest entrypoint but names NO collection "
                "literal — either the pattern set is stale or the file is no "
                "longer an entrypoint; do not leave it silently green" % rel
            )
            continue
        for literal in literals:
            if literal in LITERAL_EXEMPTIONS:
                continue
            if not is_known(literal):
                violations.append(
                    "%s: collection %r is NOT in collection_registry.py — nothing "
                    "reads it, and LegalIngestionService's preflight refuses it "
                    "(canonicalizes to %r)" % (rel, literal, canonicalize(literal))
                )
    return violations


def discover(root: Path | None = None) -> list[str]:
    """Undeclared modules that look like ingest entrypoints."""
    root = root or repo_root()
    declared = set(DECLARED_ENTRYPOINTS) | set(DISCOVERY_ALLOWLIST)
    found: set[str] = set()
    for glob in DISCOVERY_GLOBS:
        for path in root.glob(glob):
            if not path.is_file():
                continue
            if SKIP_DIR_PARTS & set(path.relative_to(root).parts):
                continue
            rel = path.relative_to(root).as_posix()
            if rel in declared or _is_test_module(rel):
                continue
            if extract_collection_literals(path.read_text(encoding="utf-8", errors="replace")):
                found.add(rel)
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="all",
                        choices=("check", "discover", "all"))
    args = parser.parse_args(argv)
    root = repo_root()
    rc = 0
    if args.mode in ("check", "all"):
        violations = check(root)
        print("[check] %d declared ingest entrypoint(s)" % len(DECLARED_ENTRYPOINTS))
        for v in violations:
            print("  UNMAPPED: %s" % v)
        if violations:
            rc = 1
        else:
            print("  clean — every named collection resolves through the registry")
    if args.mode in ("discover", "all"):
        undeclared = discover(root)
        print("[discover] undeclared ingest entrypoints: %d" % len(undeclared))
        for u in undeclared:
            print("  UNDECLARED: %s" % u)
        if undeclared:
            rc = rc or 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
