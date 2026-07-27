#!/usr/bin/env python3
"""Every test dependency the BACKEND CI job installs inline must be declared in
apps/backend-rag/requirements-test.txt.

WHY (measured 2026-07-27, cicatrix-superscar.md family #2 "esiste ≠ armato"):
the `backend-tests` job in `.github/workflows/tests.yml` installs its
test-runtime deps as a bare inline list —

    uv pip install --system pytest pytest-cov pytest-asyncio pytest-mock fakeredis

— while `requirements-test.txt` knew about one of them. An inline workflow list
is not a manifest: nothing in the tree stated that the suite needs `fakeredis`,
so a fleet machine provisioned from the repo could not reproduce CI's
environment. Mini's venv duly lacked it; two test files ERRORed at COLLECTION
(module-level `import fakeredis.aioredis`, no importorskip); and the pre-push
gate rejected two branches that do not touch those files at all — a red owned
by the machine, reported as a verdict on the diff.

SCOPE IS LOAD-BEARING, NOT A DETAIL. This checker reads ONLY the backend job.
The first draft scanned the whole file and swept up `fastmcp` from the separate
`mcp-tests` job, which led to `fastmcp` being added to the BACKEND manifest —
a package that lives in apps/nuzantara-mcp/ with its own venv and that
requirements.txt deliberately removed on 2026-05-03 to close 8 Dependabot
alerts (1 critical + 4 high + 3 medium). Adversarial review caught it before
merge. One job owns one manifest: a whole-file scan is manifest-ownership
laundering, not thoroughness.

Direction is also deliberate: the manifest must COVER the installer, never the
reverse. `mypy` and `testcontainers` are dev/pre-commit tooling the backend job
does not install; a check written the other way would fail on them and teach
people to delete real declarations.

Run:  python3 scripts/tests/test_test_deps_declared.py
      pytest scripts/tests/test_test_deps_declared.py -q
Wired into CI by .github/workflows/prepush-guards.yml (a test that no gate runs
is the very disease this file exists to prevent).
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
MANIFEST = REPO_ROOT / "apps" / "backend-rag" / "requirements-test.txt"
BACKEND_JOB = "backend-tests"

# Tokens that are flags, shell/expression syntax, or paths — never package names.
_NOT_A_PACKAGE_PREFIX = ("-", "$", "{", '"', "'", "#", "\\", "|", "&", ">", "<")
_ARG_TAKING_FLAGS = {"-r", "-e", "-c", "--requirement", "--editable", "--constraint",
                     "--index-url", "-i", "--extra-index-url", "--find-links", "-f"}
# `pip`/`uv` bootstrapping themselves is not a test dependency.
_INSTALLER_SELF = {"pip", "uv", "setuptools", "wheel"}

_INSTALL_RE = re.compile(
    r"""(?:^|[;&|]\s*|\brun:\s*)      # command position: line start, after a
                                      # separator, or right after a YAML `run:`
        (?:python[0-9.]*\s+-m\s+)?    # optional `python -m` form
        (?:uv\s+pip|pip[0-9]*)        # the installer
        \s+install\b(?P<args>.*)$""",
    re.VERBOSE,
)


def _normalise(name: str) -> str:
    """PEP 503 comparison form: extras and version specifiers stripped."""
    base = re.split(r"[\[<>=!~;]", name, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", base).strip().lower()


def _backend_job_run_blocks() -> list[str]:
    """Every `run:` script belonging to the backend job — and nothing else."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = (doc or {}).get("jobs") or {}
    job = jobs.get(BACKEND_JOB)
    if job is None:
        raise AssertionError(
            f"job '{BACKEND_JOB}' not found in {WORKFLOW} (jobs: {sorted(jobs)}). "
            "It was renamed or removed — re-anchor this checker rather than "
            "letting it silently scan nothing."
        )
    return [s["run"] for s in (job.get("steps") or []) if isinstance(s, dict) and s.get("run")]


def _packages_in(script: str) -> set[str]:
    found: set[str] = set()
    # Join `\`-continued lines first: a package on the second line of a
    # continuation is still installed by the same command.
    script = re.sub(r"\\\s*\n\s*", " ", script)
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            continue
        line = line.split(" #", 1)[0]  # drop trailing shell comment
        m = _INSTALL_RE.search(line)
        if not m:
            continue
        skip_next = False
        for tok in m.group("args").split():
            if skip_next:
                skip_next = False
                continue
            if tok in _ARG_TAKING_FLAGS:
                skip_next = True
                continue
            if tok.startswith(_NOT_A_PACKAGE_PREFIX) or "/" in tok or tok.endswith(".txt"):
                continue
            n = _normalise(tok)
            if n and n not in _INSTALLER_SELF:
                found.add(n)
    return found


def inline_installed_packages() -> set[str]:
    out: set[str] = set()
    for block in _backend_job_run_blocks():
        out |= _packages_in(block)
    return out


def declared_packages() -> set[str]:
    out: set[str] = set()
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        out.add(_normalise(line))
    return out


# --------------------------------------------------------------------------
# Fail LOUD rather than vacuously: an empty parse would make the coverage
# assertion trivially true (blind-scan, superscar #2 / W84 — zero items
# traversed is not the same as nothing to find).
# --------------------------------------------------------------------------


def test_inputs_are_readable_and_non_empty() -> None:
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    assert MANIFEST.is_file(), f"missing {MANIFEST}"
    assert _backend_job_run_blocks(), f"job '{BACKEND_JOB}' has no run: steps"
    assert inline_installed_packages(), (
        f"no inline-installed packages parsed out of the '{BACKEND_JOB}' job — "
        "the install step was reformatted and this test would silently pass "
        "against an empty set. Re-anchor the parser."
    )


def test_every_inline_installed_dep_is_declared() -> None:
    """GUILT: a package the backend job installs but nothing declares."""
    missing = sorted(inline_installed_packages() - declared_packages())
    assert not missing, (
        f"installed by the '{BACKEND_JOB}' job in {WORKFLOW.name} but declared "
        f"in no manifest: {missing}. Add them to requirements-test.txt — "
        "otherwise no machine can rebuild CI's test env from the repo, and the "
        "local suite fails with collection ERRORs that look like a defect in "
        "whatever diff is being pushed (measured on Mini, 2026-07-27)."
    )


def test_manifest_may_declare_extras() -> None:
    """INNOCENCE: manifest-only entries are legitimate, not a violation."""
    extras = declared_packages() - inline_installed_packages()
    assert "mypy" in extras and "testcontainers" in extras, (
        "expected dev-only tooling (mypy, testcontainers) to be declared and NOT "
        "installed by the backend job. If that changed, re-read this test's "
        "premise — do not delete the declarations to make it green."
    )


def test_scope_excludes_other_jobs() -> None:
    """SCOPE GUARD: the checker must not drag another job's deps in here.

    `fastmcp` is installed by the `mcp-tests` job and belongs to
    apps/nuzantara-mcp. If it ever appears in this checker's view again, the
    scoping regressed and the backend manifest is about to re-acquire 8
    Dependabot alerts' worth of dependency.
    """
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    other_jobs = [j for j in ((doc or {}).get("jobs") or {}) if j != BACKEND_JOB]
    assert other_jobs, "expected tests.yml to define jobs besides the backend one"
    assert "fastmcp" not in inline_installed_packages()
    assert "fastmcp" not in declared_packages(), (
        "fastmcp must NOT be declared in the backend manifest — it lives in "
        "apps/nuzantara-mcp/ and requirements.txt removed it on 2026-05-03 to "
        "close 8 Dependabot alerts."
    )


def test_parser_handles_the_forms_this_repo_actually_uses() -> None:
    """The tokenizer is the weak point; pin its behaviour on real shapes.

    Every string below appears in, or is one edit away from, this repo's
    workflows. The first draft of this parser missed three of them.
    """
    cases = {
        "uv pip install --system pytest pytest-cov fakeredis": {"pytest", "pytest-cov", "fakeredis"},
        "run: pip install pytest pytest-cov httpx": {"pytest", "pytest-cov", "httpx"},
        "python -m pip install module-package": {"module-package"},
        "pip install alpha-package # human note": {"alpha-package"},
        "uv pip install --system -r requirements.lock.txt": set(),
        "uv pip install --system -e ../../packages/cell-core": set(),
        "pip install --upgrade pip uv": set(),
        "# pip install commented-out-package": set(),
        "pip install \\\n  first-package \\\n  second-package": {"first-package", "second-package"},
    }
    for script, expected in cases.items():
        assert _packages_in(script) == expected, (
            f"parser mis-read {script!r}: got {_packages_in(script)}, want {expected}"
        )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
