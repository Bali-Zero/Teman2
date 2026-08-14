#!/usr/bin/env python3
"""Classify a PR's changed files for path-aware CI job selection.

The caller owns changed-file enumeration. In GitHub Actions that caller must
be ``hotzone_changed_files.sh`` so the input is anchored to the merge-base.
This module is deliberately pure: known paths map to one or more domains,
while an empty, malformed, or unclassified input recommends every test job.

Promoted to enforcing 2026-08-14 (.github/workflows/tests.yml gates its six
heavy test jobs on ``suggested_jobs``/``run_all`` below) after a 57-run
shadow-measurement audit that found and closed one real false-skip (see
EXACT_RULES' PricingTool-canonical entry below) — see that workflow's
``changes`` job for the fail-open contract every consumer of this module's
output must honor.
"""

from __future__ import annotations

import json
import posixpath
import re
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
    # a directory/prefix rule.
    #
    # CORRECTION (red-team HIGH-8, 2026-08-14): this comment previously
    # claimed "no rulepack path feeds the frontend snapshot" after checking
    # only PricingService. That was wrong, not merely incomplete — Codex's
    # red-team re-read apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/
    # engine-adapter.test.ts and found it DOES read
    # apps/backend-rag/backend/services/visa_engine/contracts/packs/
    # rulepack-prod-*.source.json directly (globs every file matching
    # rulepack-prod-\d+.source.json under that dir and asserts every SUPPORT
    # reason code in them has frontend copy — see productionPackFiles() /
    # supportReasonCodesInPack() in that test). Same suite's
    # fact-mapper.test.ts also reads
    # apps/backend-rag/backend/services/visa_engine/models.py directly,
    # extracting every dotted `alias="a.b"` on ApplicantFactsData as the
    # backend contract. Both couplings are now below (models.py as an exact
    # path; the rulepack family as a filename-pattern rule, since the exact
    # active pack filename changes as new packs are authored ahead of
    # activation — see that test's own comment on why it globs).
    "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json": {
        "backend_python",
        "mouth",
    },
    "apps/backend-rag/backend/services/visa_engine/models.py": {
        "backend_python",
        "mouth",
    },
    # Cross-domain coupling found in the 57-run shadow audit (2026-08-14):
    # apps/mouth/src/lib/kbli-canonical-pins.test.ts (a REQUIRED
    # frontend-tests suite, no path filter) reads these two repo-root `data/`
    # files directly and fails on a stale/mismatched pin — see that test's
    # own header for why the check has to live in mouth rather than in the
    # filiera compilers. The "data/" PREFIX_RULES entry below already routes
    # these to backend_python + docs_content_data; these EXACT entries widen
    # ONLY these two files to also reach mouth (most of data/ — analysis/,
    # competitor/, kb_sources/, etc. — has no such frontend reader, so this
    # is deliberately not a directory/prefix rule).
    "data/source_documents/KBLI_2025_FINAL_CLEAN.json": {
        "backend_python",
        "docs_content_data",
        "mouth",
    },
    "data/kbli-filiera/membership/batch-a-members.json": {
        "backend_python",
        "docs_content_data",
        "mouth",
    },
    # Cross-domain coupling found in the 57-run shadow audit (2026-08-14):
    # apps/backend-rag/backend/tests/app/routers/test_analytics_funnel_parity.py
    # reads these two exact packages/core files directly (regex-extracts the
    # FUNNEL_EVENTS / APP_EVENTS `as const` arrays) and pins backend
    # ALLOWED_EVENTS/FUNNEL_PAGE_EVENTS/FUNNEL_APP_EVENTS as the exact union —
    # a mismatch either direction fails a backend-tests test. The
    # "packages/core/" PREFIX_RULES entry below already routes these to
    # packages_core + mouth; these EXACT entries additionally widen ONLY
    # these two files to backend_python (every other file under
    # packages/core/analytics/ — index.ts, useFunnelApp.ts, the *.test.ts
    # siblings — has no such backend reader, so this is deliberately not a
    # directory/prefix rule).
    "packages/core/analytics/funnel-view.ts": {
        "packages_core",
        "mouth",
        "backend_python",
    },
    "packages/core/analytics/funnel-app.ts": {
        "packages_core",
        "mouth",
        "backend_python",
    },
}

# Filename-pattern coupling (red-team HIGH-8, 2026-08-14): the visa-engine
# rulepack family is authored under a numbered filename
# (rulepack-prod-<N>.source.json) and a NEW pack is written and merged
# BEFORE it is the active one — engine-adapter.test.ts globs every file
# matching this exact pattern under this exact directory (never a directory
# it doesn't also enumerate), so the CI coupling has to match the same
# family, not one pinned filename. Deliberately a narrow regex scoped to
# both the exact directory AND the test's own basename pattern — mirrors
# `/^rulepack-prod-\d+\.source\.json$/` in that test file, not invented.
REGEX_RULES: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (
        re.compile(
            r"^apps/backend-rag/backend/services/visa_engine/contracts/packs/"
            r"rulepack-prod-\d+\.source\.json$"
        ),
        frozenset({"backend_python", "mouth"}),
    ),
)

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

    for pattern, domains in REGEX_RULES:
        if pattern.match(path):
            return set(domains)

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
