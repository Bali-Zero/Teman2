#!/usr/bin/env python3
"""Stop hook — SEAM-VERIFY (P4 §3.5): map changed files to known seams, advise.

ADVISORY ONLY. This hook NEVER blocks (always exit 0) and NEVER crashes the
session: every failure path degrades to a clean exit. It is the post-session
"did you verify the seams you touched?" reminder — the deterministic part of
SEAM-VERIFY that does NOT require the agent to infer what it broke.

Design (P4 spec, calibrated to disk-state 2026-06-09):
  - The spec's §3.5 testmon path is DEFERRED: pytest-testmon is NOT installed in
    the backend venv. Installing it touches the backend venv (multi-day, out of
    scope) and a hook that silently no-ops when testmon is missing would be just
    another disarmed guardian (cicatrix W64: "esiste ma non gira"). So this Tier-1
    hook does the deterministic part WITHOUT testmon: it maps the git diff to the
    declared seams (the SEAM_MAP below, every seam-test path verified on disk in
    this turn) and tells the operator exactly which pytest command to run.
  - It is advisory (stderr + exit 0), mirroring stop_verify.py's contract but one
    notch softer: stop_verify can BLOCK (exit 2); seam_verify only ADVISES, because
    it cannot know the agent didn't already run the test, and a false block on
    every dirty session would be worse than the gap it closes.

Cron-aware: skipped in non-interactive (cron / `claude --print`) contexts, like
stop_verify.py — those sessions end dirty by design and have no human to read the
advice.

Reference: research/operations/specs/P4-seam-verify.md (§3.5, §4 seam map).
Family: stop_verify.py (Stop-hook contract), W64 (esiste != armato), the
2026-05-02 router/middleware 3-hotfix cicatrix this seam map neutralizes.
"""
import json
import os
import subprocess
import sys


# ---------------------------------------------------------------------------
# SEAM_MAP — declared seams. Each entry: a path-prefix or path-substring that,
# when present in the git diff, implies a known seam, plus the seam-test that
# covers it. Every seam-test path below was `[ -f ]`-verified on disk on
# 2026-06-09 (anti-hallucination: no phantom file:line). Order matters — first
# match wins per file, most-specific prefixes first.
# ---------------------------------------------------------------------------
SEAM_MAP = [
    # (match_substring, seam_name, seam_test_path_relative_to_repo_root)
    (
        "backend/app/setup/router_manifest.py",
        "router<->registration (manifest SSOT)",
        "apps/backend-rag/backend/tests/setup/test_router_manifest.py",
    ),
    (
        "backend/app/middleware/public_endpoints",
        "route<->auth-middleware (PUBLIC_ENDPOINTS)",
        "apps/backend-rag/backend/tests/unit/middleware/test_public_endpoints_registry.py",
    ),
    (
        "backend/app/routers/",
        "route<->mounting (404 / manifest parity)",
        "apps/backend-rag/backend/tests/integration/test_endpoints_reachable.py "
        "apps/backend-rag/backend/tests/setup/test_router_manifest.py",
    ),
    (
        "backend/app/dependencies.py",
        "import-chain SPOF (dependencies.py)",
        "apps/backend-rag/tests/test_import_time.py",
    ),
    (
        "backend/app/router_registration",
        "route<->registration (include_router)",
        "apps/backend-rag/backend/tests/setup/test_router_manifest.py "
        "apps/backend-rag/backend/tests/integration/test_endpoints_reachable.py",
    ),
]

# Files that touch the HTTP/middleware surface but are NOT in a declared seam
# above → undeclared-seam warning (mitigation of P4 §5 residual: implicit seams).
UNDECLARED_WATCH = (
    "backend/app/routers",
    "backend/app/middleware",
    "backend/app/setup",
    "backend/channels/",
)

REPO_MARKER = "Desktop/nuzantara"  # only advise inside the nuzantara checkout


def _is_interactive() -> bool:
    """True only for an interactive (human) session (mirror stop_verify.py)."""
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
        os.close(fd)
        return True
    except Exception:
        pass
    return os.isatty(2)


def _changed_files(cwd: str) -> list[str]:
    """Tracked-modified + staged + untracked files, relative to repo root."""
    files: set[str] = set()
    for args in (
        ["git", "-C", cwd, "diff", "--name-only", "HEAD"],
        ["git", "-C", cwd, "diff", "--name-only", "--cached"],
        ["git", "-C", cwd, "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                files.update(x for x in r.stdout.splitlines() if x.strip())
        except Exception:
            continue
    return sorted(files)


def main() -> None:
    # Never block / advise in cron context.
    if not _is_interactive():
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = payload.get("cwd", os.getcwd())
    if REPO_MARKER not in cwd:
        sys.exit(0)

    try:
        changed = _changed_files(cwd)
    except Exception:
        sys.exit(0)
    if not changed:
        sys.exit(0)

    # Map files -> seams (dedupe by seam name, preserve a representative file).
    hit_seams: dict[str, tuple[str, str]] = {}  # seam -> (seam_test, example_file)
    undeclared: list[str] = []
    for f in changed:
        matched = False
        for sub, seam, test in SEAM_MAP:
            if sub in f:
                hit_seams.setdefault(seam, (test, f))
                matched = True
                break
        if not matched and any(w in f for w in UNDECLARED_WATCH):
            undeclared.append(f)

    if not hit_seams and not undeclared:
        sys.exit(0)

    lines = ["", "SEAM-VERIFY (advisory — P4): you touched declared seams.", ""]
    if hit_seams:
        for seam, (test, example) in hit_seams.items():
            # Test paths are stored repo-root-relative; the suggested command cds
            # into apps/backend-rag, so strip that prefix to keep paths valid.
            rel = " ".join(t.replace("apps/backend-rag/", "", 1) for t in test.split())
            lines.append(f"  · {seam}")
            lines.append(f"      (e.g. {example})")
            lines.append(f"      run:  cd apps/backend-rag && PYTHONPATH=. "
                         f".venv/bin/pytest {rel} -q")
            lines.append("")
    if undeclared:
        lines.append("  ⚠ undeclared seam (HTTP/middleware surface, no seam-test mapped):")
        for f in undeclared[:8]:
            lines.append(f"      {f}")
        lines.append("    → verify manually; consider adding it to SEAM_MAP "
                     "in scripts/hooks/seam_verify.py (the versioned source — "
                     "editing the installed ~/.claude/hooks copy is overwritten "
                     "by install_fase0_governance.sh)")
        lines.append("")
    lines.append("(advisory only — does NOT block. testmon path deferred: "
                 "pytest-testmon not installed.)")
    sys.stderr.write("\n".join(lines) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
