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

So the runner was not merely writing into a drawer: it could not run at all. Two
sibling scripts named it too. `apps/backend-rag/scripts/ingest_2026_laws.py` had
already been cured this way, with the reasoning written in a comment. A comment
does not fail. This does.

Why the AST and not a regex
---------------------------
The first cut of this module matched collection literals with regexes, and a
cross-family refuter took it apart on 2026-08-25. Two of its findings produced a
GREEN gate over a LIVE defect, which is worse than no gate at all:

    LegalIngestionService(collection_name="legal_unified" + "_2026")
    LegalIngestionService(collection_name="legal_unified" "_2026")

Both extracted `legal_unified` — a mapped name — and passed clean while writing to
the dead collection. Four more forms simply vanished: an f-string, a positional
argument, a dict value, and a module constant.

The cure is not more patterns. It is a different rule:

    **A collection target a static reader cannot resolve is a VIOLATION.**

Because the whole purpose is that a reader — human or CI — can see where an ingest
writes. If the target is assembled at runtime, nobody can, and saying so is the
honest answer. Constant folding is deliberately modest: literals, implicit
adjacency, `+` of resolvable strings, and module-level `NAME = "..."`. Everything
else is reported, never guessed.

Modes
-----
  check     declared entrypoints resolve to registry-mapped collections
  discover  no UNDECLARED ingest entrypoint exists — found BY CONTENT, not by
            filename, because `ingest.py` / `load_regulations.py` /
            `upsert_laws.py` all dodged the old name globs.

Exit: 0 clean · 1 unresolved or unmapped target · 2 undeclared entrypoint.
"""
from __future__ import annotations

import argparse
import ast
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
    # Write entrypoints `discover` surfaced on 2026-08-25 once it looked at
    # CONTENT instead of filenames. These name registry-mapped collections, so
    # declaring them costs nothing and widens what the gate watches.
    "apps/backend-rag/backend/migrations/migration_021b_add_bm25_sparse_vectors.py",
    "apps/backend-rag/backend/scripts/migrate_skills_to_qdrant_cloud.py",
    "apps/backend-rag/scripts/add_visa_aliases.py",
    "apps/backend-rag/scripts/curated_qa_harvest.py",
    "apps/backend-rag/scripts/enrich_immigration_circulars.py",
)

# Modules that look like ingest entrypoints to `discover` but are not. Each needs
# a reason: an allowlist without one grows until it is the whole tree.
DISCOVERY_ALLOWLIST: dict[str, str] = {
    "apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py":
        "the service itself — it RESOLVES a caller's name, it does not choose one",
    "apps/backend-rag/backend/app/routers/oracle_ingest.py":
        "HTTP router — the collection arrives from the service layer",
    "apps/backend-rag/scripts/ingest_kbli_notebook_expert.py":
        "OPEN FINDING, deliberately NOT cured here (kb/inventory/"
        "legal_unified_2026.yaml -> open_findings, WIZ-4). It names "
        "'kbli_notebook_expert', absent from BOTH the registry and live Qdrant "
        "(14 collections measured 2026-08-25), and its first act is "
        "delete_collection(). Repointing it at a live KBLI collection would arm a "
        "destructive rebuild of 1,873 real points, so the safe cure is not a "
        "rename — it is a decision, and it belongs to lane B, not to this one.",

    # ── OPEN FINDINGS: the same defect class as Work Item Zero, on other topics.
    # Held here rather than cured, because each cure is a decision with real blast
    # radius and MANDATE §8 says a lane that finds a defect outside its topic
    # writes it down and does not chase it. Every entry below has a matching row in
    # kb/inventory/legal_unified_2026.yaml -> open_findings, and a test asserts
    # that correspondence so this list cannot quietly become a graveyard.
    "apps/backend-rag/backend/scripts/generate_tka_embeddings.py":
        "OPEN FINDING WIZ-5 (lane E): writes to `kbli_tka`, which is a LIVE alias "
        "(-> kbli_tka_hybrid, 246 points measured 2026-08-25) that the registry "
        "does not map. The cure is a registry addition, not a script edit.",
    "apps/bali-intel-scraper/scripts/load_intel_sources.py":
        "OPEN FINDING WIZ-6 (lane F): writes to `intel_authoritative_sources` "
        "(525 live points). It IS in CANONICAL_COLLECTION_ALIASES — mapped to "
        "`balizero_news` — but absent from LOGICAL_TO_PHYSICAL_COLLECTIONS, so "
        "is_known_collection() is False. Adding it changes how an existing alias "
        "resolves; that is not a drive-by.",
    "apps/bali-intel-scraper/scripts/load_intel_sources_streaming.py":
        "OPEN FINDING WIZ-6 (lane F): the streaming twin of the above, same "
        "collection, same cure.",
    "scripts/nlm_shadow_extractor.py":
        "OPEN FINDING WIZ-7 (lane B): writes to `nlm_shadow_hybrid`, which IS in "
        "the registry but does NOT exist among the 14 live collections measured "
        "2026-08-25 — the mirror image of every other finding here.",
    "apps/backend-rag/backend/migrations/migration_020.py":
        "OPEN FINDING WIZ-8 (lane P): creates `collective_memories`, absent from "
        "both the registry and live Qdrant. A migration for a collection nobody "
        "has; retire it or explain it.",
    "apps/backend-rag/backend/migrations/migration_031b_hybrid_collections.py":
        "OPEN FINDING WIZ-8 (lane P): names a collection literally called `test`.",
    "apps/bali-intel-scraper/scripts/init_news_collection.py":
        "OPEN FINDING WIZ-8 (lane P): creates `balizero_news_history`, absent from "
        "both the registry and live Qdrant.",
    "apps/backend-rag/scripts/run_hier_eval.py":
        "OPEN FINDING WIZ-8 (lane P): an evaluation harness writing "
        "`kb_politics_hier_v1`, absent from both.",
}

# Calls whose collection argument IS an ingest target.
INGEST_CALLS: frozenset[str] = frozenset({
    "LegalIngestionService",
    "CollectionManager",
    "QdrantClient",
})
# ...but only these take the collection POSITIONALLY. `QdrantClient`'s first
# positional argument is the URL/location: reading it as a collection produced a
# phantom target `:memory:` on first run. A rule that invents a target is as bad
# as one that misses it.
POSITIONAL_COLLECTION_CALLS: frozenset[str] = frozenset({
    "LegalIngestionService",
    "CollectionManager",
})
# Qdrant write operations — presence of any of these makes a module an ingest
# entrypoint for `discover`, whatever it is called.
QDRANT_WRITE_CALLS: frozenset[str] = frozenset({
    "upsert", "create_collection", "recreate_collection", "delete_collection",
    "upload_points", "upload_collection", "set_payload", "overwrite_payload",
})
# Keyword / assignment targets that name a collection.
COLLECTION_KEYWORDS: frozenset[str] = frozenset({"collection_name", "collection"})
COLLECTION_ASSIGN_NAMES: frozenset[str] = frozenset({
    "COLLECTION_NAME", "COLLECTION", "collection_name", "TARGET_COLLECTION",
})

SKIP_DIR_PARTS = frozenset({
    ".git", ".worktrees", "node_modules", ".venv", "venv", "__pycache__",
    "site-packages", ".mypy_cache", ".pytest_cache", "dist", "build", ".ruff_cache",
})

UNRESOLVED = "\0UNRESOLVED\0"  # sentinel: a value no source file can contain


def _is_test_module(rel: str) -> bool:
    """A test module's collection literal is a FIXTURE, not a chosen target
    (`test_legal_ingestion_service.py` names 'custom_collection' precisely to
    prove the preflight rejects it)."""
    name = rel.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in rel


def repo_root(start: Path | None = None) -> Path:
    """Repo root, found by marker — never by the caller's cwd.

    The CI shards run pytest from `apps/backend-rag`; a cwd-relative root would
    make this module report ABSENT for every path it is meant to guard.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise RuntimeError(f"ingest_target_lint: repo root not found from {here}")


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """`NAME = "literal"` anywhere in the module, so a target held in a constant
    resolves — including inside a function, which is where three of this repo's
    real entrypoints put it.

    A name assigned more than once is dropped rather than guessed at: two
    assignments mean the reader cannot tell which one reaches the call either, and
    reporting that honestly is the whole design.
    """
    values: dict[str, str] = {}
    assigned: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            assigned[target.id] = assigned.get(target.id, 0) + 1
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[target.id] = node.value.value
    return {name: value for name, value in values.items() if assigned[name] == 1}


def _resolve(node: ast.AST, constants: dict[str, str]) -> str:
    """Fold a value to a string, or return UNRESOLVED. Never guess.

    Implicit adjacency ("a" "b") is already one Constant by the time the parser
    is done, so it is covered by the first branch.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else UNRESOLVED
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve(node.left, constants)
        right = _resolve(node.right, constants)
        if left is not UNRESOLVED and right is not UNRESOLVED:
            return left + right
        return UNRESOLVED
    if isinstance(node, ast.Name):
        return constants.get(node.id, UNRESOLVED)
    return UNRESOLVED


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def performs_qdrant_write(source: str) -> bool:
    """Does this module actually WRITE to Qdrant?

    Constructing a client with a collection name is not enough: a read-only
    service does that too, and requiring only the name listed 40 modules — most of
    them retrieval paths. An ingest entrypoint is a module that chooses a
    destination AND writes to it.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(
        isinstance(node, ast.Call) and _call_name(node) in QDRANT_WRITE_CALLS
        for node in ast.walk(tree)
    )


def collection_targets(source: str) -> list[tuple[str, int, str]]:
    """Every collection target a module names: (value_or_UNRESOLVED, lineno, how).

    Covers, because a refuter proved each one escaped the regex version:
      * `LegalIngestionService(collection_name=...)`, keyword AND positional
      * any `*.upsert(collection_name=...)` / `create_collection(...)` etc.
      * `COLLECTION_NAME = ...` at module level
      * `{"collection": ...}` in a dict literal
      * `["--collection", ...]` in an argv list
    """
    tree = ast.parse(source)
    constants = _string_constants(tree)
    found: list[tuple[str, int, str]] = []

    def record(node: ast.AST, lineno: int, how: str) -> None:
        found.append((_resolve(node, constants), lineno, how))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in INGEST_CALLS or name in QDRANT_WRITE_CALLS:
                for kw in node.keywords:
                    if kw.arg in COLLECTION_KEYWORDS:
                        record(kw.value, node.lineno, f"{name}({kw.arg}=)")
                if name in POSITIONAL_COLLECTION_CALLS and node.args:
                    record(node.args[0], node.lineno, f"{name}(positional)")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in COLLECTION_ASSIGN_NAMES:
                    record(node.value, node.lineno, f"{target.id} =")
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in COLLECTION_KEYWORDS:
                    record(value, node.lineno, f'{{"{key.value}": }}')
        elif isinstance(node, (ast.List, ast.Tuple)):
            elts = node.elts
            for i, elt in enumerate(elts[:-1]):
                if isinstance(elt, ast.Constant) and elt.value == "--collection":
                    record(elts[i + 1], node.lineno, '["--collection", ]')

    # stable, de-duplicated by (value, how) so one target reported twice by two
    # rules does not read as two problems
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, int, str]] = []
    for value, lineno, how in found:
        key = (value, how)
        if key not in seen:
            seen.add(key)
            unique.append((value, lineno, how))
    return unique


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
    """Violations: a target that is unmapped, or that cannot be resolved at all.

    `entrypoints` / `source_root` exist so the guilt tests can point the SAME code
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
            violations.append(f"{rel}: declared entrypoint does not exist")
            continue
        try:
            targets = collection_targets(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            violations.append(f"{rel}: cannot be parsed, so its target is unknown: {exc}")
            continue
        if not targets:
            # A silent zero here is how this gate would become decorative.
            violations.append(
                f"{rel}: declared as an ingest entrypoint but names NO collection "
                "target — either the rule set is stale or the file is no longer an "
                "entrypoint; do not leave it silently green"
            )
            continue
        for value, lineno, how in targets:
            if value is UNRESOLVED:
                violations.append(
                    f"{rel}:{lineno}: {how} target is assembled at runtime, so no "
                    "reader can tell which collection this writes to. Name it with a "
                    "plain string literal, or resolve it through "
                    "collection_registry.resolve_collection_name() at the call site."
                )
            elif not is_known(value):
                violations.append(
                    f"{rel}:{lineno}: {how} collection {value!r} is NOT in "
                    "collection_registry.py — nothing reads it, and "
                    "LegalIngestionService's preflight refuses it (canonicalizes to "
                    f"{canonicalize(value)!r})"
                )
    return violations


def discover(root: Path | None = None) -> list[str]:
    """Undeclared modules that HARDCODE a Qdrant collection they write to.

    Found BY CONTENT, not by filename. The first cut globbed names, and a refuter
    listed five real ones that dodged it in a breath: `ingest.py`,
    `load_regulations.py`, `regulatory_delta_ingest.py`, `embed_regulations.py`,
    `upsert_laws.py`.

    DECLARED LIMIT, so nobody mistakes this for more than it is: only a RESOLVED
    literal counts. A module that takes its collection from a caller, a CLI flag or
    an env var is a pass-through, not a choice — flagging those would list every
    router and migration in the tree (66 of them, measured) and train the reader to
    ignore this output. The consequence is real and stated rather than hidden: a
    NEW ingest script that assembles its target dynamically is invisible here. It
    is still caught the moment it is declared, because `check` treats an
    unresolvable target as a violation.
    """
    root = root or repo_root()
    declared = set(DECLARED_ENTRYPOINTS) | set(DISCOVERY_ALLOWLIST)
    found: set[str] = set()
    for path in root.rglob("*.py"):
        rel_parts = path.relative_to(root).parts
        if SKIP_DIR_PARTS & set(rel_parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in declared or _is_test_module(rel):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "collection" not in source:      # cheap prefilter before ast.parse
            continue
        try:
            targets = collection_targets(source)
        except SyntaxError:
            continue
        if not performs_qdrant_write(source):
            continue
        if any(value is not UNRESOLVED for value, _, _ in targets):
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
        print(f"[check] {len(DECLARED_ENTRYPOINTS)} declared ingest entrypoint(s)")
        for v in violations:
            print(f"  VIOLATION: {v}")
        if violations:
            rc = 1
        else:
            print("  clean — every target resolves, and resolves through the registry")
    if args.mode in ("discover", "all"):
        undeclared = discover(root)
        print(f"[discover] undeclared ingest entrypoints: {len(undeclared)}")
        for u in undeclared:
            print(f"  UNDECLARED: {u}")
        if undeclared:
            rc = rc or 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
