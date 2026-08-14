#!/usr/bin/env python3
"""Classify a PR's changed files for path-aware CI job selection.

The caller owns changed-file enumeration. In GitHub Actions that caller must
be ``hotzone_changed_files.sh`` so the input is anchored to the merge-base.
This module is deliberately pure: known paths map to one or more domains,
while an empty, malformed, or unclassified input recommends every test job.

Promoted to enforcing 2026-08-14 (.github/workflows/tests.yml gates its six
heavy test jobs on ``suggested_jobs``/``run_all`` below) after a ~250-PR
shadow-measurement window — see that workflow's ``changes`` job for the
fail-open contract every consumer of this module's output must honor.
"""

from __future__ import annotations

import json
import posixpath
import sys
from collections.abc import Iterable

ENUMERATION_ERROR = "__CHANGE_MAP_ENUMERATION_ERROR__"

DOMAIN_NAMES = (
    "backend_python",
    "mouth",
    "admin_dashboard",
    "wa_mirror",
    "mcp",
    "evaluator",
    "packages_core",
    "infra_workflows",
    "docs_content_data",
    "security_sensitive",
)

TEST_JOBS = (
    "backend-tests",
    "mcp-tests",
    "evaluator-critical-tests",
    "frontend-tests",
    "packages-core-tests",
    "e2e-tests",
)

PRODUCT_DOMAINS = frozenset(
    {
        "backend_python",
        "mouth",
        "admin_dashboard",
        "wa_mirror",
        "mcp",
        "evaluator",
        "packages_core",
    }
)

EXACT_RULES: dict[str, set[str] | frozenset[str]] = {
    # This workflow defines every job being measured. Editing it must never
    # produce a self-approved selective recommendation.
    ".github/workflows/tests.yml": PRODUCT_DOMAINS
    | {"infra_workflows", "security_sensitive"},
    "scripts/ci/change_map.py": {"infra_workflows", "security_sensitive"},
    "scripts/ci/test_change_map.py": {"infra_workflows", "security_sensitive"},
    "package.json": {
        "mouth",
        "admin_dashboard",
        "wa_mirror",
        "packages_core",
        "security_sensitive",
    },
    "package-lock.json": {
        "mouth",
        "admin_dashboard",
        "wa_mirror",
        "packages_core",
        "security_sensitive",
    },
    "pyproject.toml": {
        "backend_python",
        "mcp",
        "evaluator",
        "security_sensitive",
    },
    # Cross-domain coupling found in the 57-run shadow audit (2026-08-14,
    # run 31648287902): this single backend file is PricingTool's canonical
    # source (PricingService._load_prices() reads it, and
    # scripts/sync_frontend_prices.py regenerates the mouth-side copy from
    # it). Two mouth vitest suites read this exact path directly and fail on
    # drift — apps/mouth/src/lib/pricing-snapshot.test.ts ("keeps every
    # exact PricingTool row in parity") and
    # apps/mouth/src/lib/bali-zero-prices.test.ts ("PricingTool
    # source-of-truth") — so a PR that edits only this backend file, without
    # having regenerated apps/mouth/data/bali-zero-prices.json yet, needs
    # frontend-tests to catch the mismatch before merge. The "apps/backend-rag/"
    # prefix rule below already puts this path in backend_python; this exact
    # entry additionally routes it to mouth. Deliberately an EXACT path, not
    # a directory/prefix rule: investigated apps/backend-rag/backend/services/
    # visa_engine/ (the sibling file that landed in the same real-world PR,
    # rulepack-prod-008.source.json) and PricingService only ever reads this
    # one file — no rulepack path feeds the frontend snapshot, so widening
    # the coupling there would be an unearned guess, not a verified edge.
    "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json": {
        "backend_python",
        "mouth",
    },
}

PREFIX_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("apps/backend-rag/", frozenset({"backend_python"})),
    ("apps/crm-cell/", frozenset({"backend_python"})),
    ("packages/cell-core/", frozenset({"backend_python", "mcp"})),
    ("apps/mouth/", frozenset({"mouth"})),
    ("apps/admin-dashboard/", frozenset({"admin_dashboard"})),
    ("apps/wa-mirror/", frozenset({"wa_mirror"})),
    ("apps/nuzantara-mcp/", frozenset({"mcp"})),
    ("apps/nuzantara-mcp-advanced/", frozenset({"mcp"})),
    ("apps/nuzantara-mcp-browser/", frozenset({"mcp"})),
    ("apps/evaluator/", frozenset({"evaluator"})),
    # packages/core is both its own suite and a direct frontend dependency.
    ("packages/core/", frozenset({"packages_core", "mouth"})),
    (
        "packages/ts-schemas/",
        frozenset({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}),
    ),
    (
        "packages/shared-schemas/",
        frozenset({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}),
    ),
    (".github/", frozenset({"infra_workflows", "security_sensitive"})),
    (".husky/", frozenset({"infra_workflows", "security_sensitive"})),
    (".security/", frozenset({"infra_workflows", "security_sensitive"})),
    ("scripts/ci/", frozenset({"infra_workflows", "security_sensitive"})),
    ("infra/", frozenset({"infra_workflows", "security_sensitive"})),
    ("config/", frozenset({"infra_workflows", "security_sensitive"})),
    ("data/", frozenset({"backend_python", "docs_content_data"})),
    ("public/", frozenset({"mouth", "docs_content_data"})),
)

DOC_PREFIXES = (
    "docs/",
    "research/",
    ".agents/skills/",
    ".claude/skills/",
    ".claude/rules/",
    ".claude/commands/",
    ".claude/agents/",
)
DOC_SUFFIXES = (
    ".md",
    ".mdx",
    ".txt",
    ".csv",
    ".json",
    ".jsonl",
    ".yml",
    ".yaml",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".pdf",
)

PYTHON_MANIFEST_NAMES = frozenset(
    {
        "requirements.txt",
        "requirements.lock.txt",
        "requirements-test.txt",
        "requirements-dev.txt",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
        "uv.lock",
    }
)


def _normalize(raw: str) -> str | None:
    """Return a safe repo-relative POSIX path or ``None``."""

    # ``git diff --name-only`` does not add padding. Treat edge whitespace as
    # malformed instead of silently turning it into a different repository
    # path (Git filenames may legally contain spaces).
    if raw != raw.strip():
        return None
    path = raw
    while path.startswith("./"):
        path = path[2:]
    if not path or "\x00" in path or "\n" in path or "\r" in path:
        return None
    if path.startswith("/") or any(part == ".." for part in path.split("/")):
        return None
    normalized = posixpath.normpath(path)
    if normalized in {"", "."} or normalized.startswith("../"):
        return None
    return normalized


def _domains_for_path(path: str) -> set[str]:
    exact = EXACT_RULES.get(path)
    if exact is not None:
        return set(exact)

    basename = path.rsplit("/", 1)[-1]
    if basename in PYTHON_MANIFEST_NAMES or basename.startswith("requirements-"):
        return {"backend_python", "mcp", "evaluator", "security_sensitive"}

    for prefix, domains in PREFIX_RULES:
        if path.startswith(prefix):
            matched = set(domains)
            if any(part in {"auth", "security", "migrations", "deploy"} for part in path.split("/")):
                matched.add("security_sensitive")
            if basename in {"Dockerfile", "fly.toml"}:
                matched.add("security_sensitive")
            # MDX is served by mouth and also consumed by backend indexing code.
            if path.startswith("apps/mouth/") and path.endswith(".mdx"):
                matched.update({"backend_python", "docs_content_data"})
            return matched

    if path.startswith(DOC_PREFIXES) and path.lower().endswith(DOC_SUFFIXES):
        return {"docs_content_data"}
    if "/" not in path and path.lower().endswith((".md", ".mdx", ".txt")):
        return {"docs_content_data"}
    return set()


def _suggested_jobs(domains: set[str], run_all: bool) -> list[str]:
    # CI infrastructure and security-sensitive surfaces can affect any suite
    # indirectly. They are known paths, but never candidates for selective
    # execution.
    if run_all or domains.intersection({"infra_workflows", "security_sensitive"}):
        return list(TEST_JOBS)

    jobs: list[str] = []
    if "backend_python" in domains:
        jobs.append("backend-tests")
    if "mcp" in domains:
        jobs.append("mcp-tests")
    if "evaluator" in domains:
        jobs.append("evaluator-critical-tests")
    if domains.intersection({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}):
        jobs.append("frontend-tests")
    if "packages_core" in domains:
        jobs.append("packages-core-tests")
    if domains.intersection({"backend_python", "mouth", "packages_core"}):
        jobs.append("e2e-tests")
    return jobs


def classify(paths: Iterable[str]) -> dict[str, object]:
    """Build the deterministic change-map recommendation for ``paths``."""

    raw_paths = list(paths)
    enumeration_failed = ENUMERATION_ERROR in raw_paths
    normalized: list[str] = []
    malformed: list[str] = []
    for raw in raw_paths:
        if not raw.strip() or raw == ENUMERATION_ERROR:
            continue
        path = _normalize(raw)
        if path is None:
            malformed.append(raw)
        else:
            normalized.append(path)

    changed = sorted(set(normalized))
    domains: set[str] = set()
    unknown: list[str] = []
    for path in changed:
        matched = _domains_for_path(path)
        if matched:
            domains.update(matched)
        else:
            unknown.append(path)

    unknown.extend(malformed)
    unknown = sorted(set(unknown))
    empty = not changed and not malformed and not enumeration_failed
    run_all = enumeration_failed or empty or bool(unknown)
    if enumeration_failed:
        reason = "enumeration_failed"
    elif empty:
        reason = "empty_changed_set"
    elif unknown:
        reason = "unclassified_paths"
    else:
        reason = "classified"

    suggested = _suggested_jobs(domains, run_all)
    return {
        "schema_version": 1,
        # Promoted 2026-08-14 (cicatrix superscar #2, "esiste ≠ armato": a
        # status field that keeps saying "shadow" after the caller starts
        # enforcing it is exactly the false-green this family warns about —
        # the next person to debug a skipped job would read this and assume
        # nothing gates on it). Literal, not derived: this module has exactly
        # one caller (.github/workflows/tests.yml's `changes` job) and it is
        # enforcing; there is no second "shadow" consumer to parametrize for.
        "mode": "enforcing",
        "reason": reason,
        "changed_file_count": len(changed),
        "domains": {name: name in domains for name in DOMAIN_NAMES},
        "unknown_paths": unknown,
        "run_all": run_all,
        "suggested_jobs": suggested,
        "would_skip": [job for job in TEST_JOBS if job not in suggested],
    }


def _read_paths(argv: list[str]) -> list[str]:
    if argv:
        return [line for arg in argv for line in arg.splitlines()]
    return sys.stdin.read().splitlines()


def main(argv: list[str] | None = None) -> int:
    result = classify(_read_paths(list(argv if argv is not None else sys.argv[1:])))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
