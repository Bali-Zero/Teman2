#!/usr/bin/env python3
"""Derive per-scanner run/skip flags for security.yml from a change_map.py map.

Companion to change_map.py (2026-08-20 path-aware gating of
.github/workflows/security.yml). This module does NOT re-classify paths — it
consumes the map `classify()` already produced (same domain vocabulary,
same run_all fallback) and answers one narrower question per scanner:
"given these domains, does THIS security job need to run?"

Kept as its own file, extracted from BASE_SHA alongside change_map.py /
test_change_map.py / hotzone_changed_files.sh in security.yml's `changes`
job (root-of-trust: a PR could otherwise bypass gating by editing THIS
file's flag math directly, leaving change_map.py's domain classification
untouched — a distinct attack surface from gaming the classifier itself).
Also CODEOWNERS-TIER1 alongside the other three (see .github/CODEOWNERS).

Fail-open by construction: every flag is `run_all OR <domain match>` — never
a bare domain match — so a run_all=True map (classifier failure, enumeration
failure, unclassified path, or genuinely broad diff) forces every flag True
regardless of what follows.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable

# Each entry: which change_map.py domains make this scanner necessary.
# Rationale for each mapping lives in security.yml's per-job `if:` comments,
# not duplicated here — this table is the single place the actual policy
# is expressed; test_security_gate_flags.py pins it with named cases.
FLAG_DOMAINS: dict[str, tuple[str, ...]] = {
    # Source-code analyzers: gated on the domains whose PREFIX_RULES trees
    # are that language (apps/evaluator, packages/cell-core,
    # apps/nuzantara-mcp are Python; packages/core is TSX/TS — verified live
    # by extension count 2026-08-20).
    "run_codeql_python": ("backend_python", "mcp", "evaluator", "security_sensitive"),
    "run_codeql_js": ("mouth", "admin_dashboard", "wa_mirror", "packages_core", "security_sensitive"),
    # Bandit's scan target is fixed to apps/backend-rag/backend/ only.
    "run_bandit": ("backend_python", "security_sensitive"),
    # Snyk-python / Safety scan apps/backend-rag/requirements.txt ONLY. A
    # backend_python-only change (no manifest edit) cannot alter the
    # declared dependency set these two evaluate — change_map.py's
    # PYTHON_MANIFEST_NAMES rule already tags any requirements*.txt /
    # pyproject.toml / uv.lock change as security_sensitive, globally,
    # regardless of directory, so security_sensitive alone is sufficient.
    "run_snyk_python": ("security_sensitive",),
    "run_safety": ("security_sensitive",),
    # Snyk-docker also validates the production Dockerfile still BUILDS
    # (fly deploy builds this same file) — backend_python is included here,
    # unlike snyk-python/safety, because application code can break that
    # build even with the Dockerfile/manifest untouched.
    "run_snyk_docker": ("backend_python", "security_sensitive"),
}

# run_snyk_node is handled separately below: it needs the JS-manifest
# predicate (see js_manifest_touched), not just a domain lookup, because
# change_map.py's own JS-manifest rule has a verified gap (nested lockfiles
# like apps/wa-mirror/package-lock.json fall through to PREFIX_RULES and are
# never tagged security_sensitive — see security.yml's `changes` job
# comment for the full writeup).


def js_manifest_touched(paths: Iterable[str]) -> bool:
    """True if any changed path's basename is a JS dependency manifest.

    Deliberately basename-only, anywhere in the tree — not routed through
    change_map.py's domain model. Closes the exact gap change_map.py has
    today: EXACT_RULES only matches the literal root-level "package.json" /
    "package-lock.json" paths, so a nested manifest is tagged only its app
    domain (e.g. "wa_mirror"), never "security_sensitive".
    """
    for raw in paths:
        if not raw or not raw.strip():
            continue
        base = raw.rsplit("/", 1)[-1]
        if base in ("package.json", "package-lock.json"):
            return True
    return False


def compute_flags(map_result: dict, js_manifest: bool) -> dict[str, bool]:
    """Return {flag_name: bool} for every gated security.yml job.

    `map_result` is change_map.py's classify() output (or an
    equivalent dict — schema_version/domains/run_all keys). Fail-open: a
    malformed or missing "domains"/"run_all" key raises, which the caller
    (security.yml's classify step) treats the same as any other classifier
    failure — force every flag True — never silently defaults to False.
    """
    run_all = bool(map_result["run_all"])
    domains = map_result["domains"]

    flags: dict[str, bool] = {}
    for name, needed_domains in FLAG_DOMAINS.items():
        flags[name] = run_all or any(domains.get(d, False) for d in needed_domains)

    flags["run_snyk_node"] = (
        run_all or domains.get("security_sensitive", False) or js_manifest
    )
    return flags


def main(argv: list[str] | None = None) -> int:
    """CLI: MAP_JSON=<json> security_gate_flags.py < <changed-files-list>

    Mirrors change_map.py's own CLI conventions in this same caller
    (security.yml): the JSON blob travels through an env var (as the
    caller already does for MAP_JSON, avoiding argv-length/quoting
    concerns for a payload whose size — unknown_paths can be long — isn't
    bounded), and the changed-file list travels over stdin (exactly how
    change_map.py itself reads paths). No positional args.

    Prints `name=true`/`name=false` lines, one per flag, suitable for
    `>> "$GITHUB_OUTPUT"`. Any error here is a caller-visible non-zero exit —
    security.yml's classify step treats a non-zero exit as classifier
    failure and forces the conservative fallback, never swallows it.
    """
    del argv  # no positional args; kept for test-call symmetry with change_map.main()
    map_json = os.environ.get("MAP_JSON", "")
    if not map_json:
        print("security_gate_flags: MAP_JSON env var is required and was empty", file=sys.stderr)
        return 2

    map_result = json.loads(map_json)
    paths = [line.rstrip("\n") for line in sys.stdin]

    js_manifest = js_manifest_touched(paths)
    flags = compute_flags(map_result, js_manifest)

    print(f"js_manifest_touched={'true' if js_manifest else 'false'}")
    for name, value in flags.items():
        print(f"{name}={'true' if value else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
