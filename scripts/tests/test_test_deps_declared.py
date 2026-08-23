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
import shlex
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"
MANIFEST = REPO_ROOT / "apps" / "backend-rag" / "requirements-test.txt"
# RE-ANCHORED 2026-08-23 (S11 backend-test sharding). This was a single job id,
# `backend-tests`. That job still exists — but it is now a FAN-IN, and the test
# runtime it used to install moved to `backend-shard`. A one-job anchor would
# still have resolved, still had run: steps, still parsed a package or two, and
# quietly stopped covering the install line it exists to police: `pytest
# pytest-cov pytest-asyncio pytest-mock fakeredis pytest-xdist`. That is exactly
# the silent-narrowing this checker's own docstring warns about, arriving through
# a job SPLIT rather than a rename, so the "job not found" assertion below could
# never have fired.
#
# The anchor is now the whole backend TEST LANE, and every named job must exist —
# a split or rename fails loudly instead of shrinking the scan. Scope discipline
# is unchanged and still load-bearing: `mcp-tests` is NOT in this list, so
# `fastmcp` cannot be laundered into the backend manifest (see the manifest's own
# DO-NOT-ADD note).
BACKEND_JOBS = ("backend-static", "backend-shard", "backend-tests")
BACKEND_JOB = "/".join(BACKEND_JOBS)  # for error messages only

# Flags that CONSUME the next token — its value is never a package name.
# `--target/-t`, `--prefix`, `--root` were added after an adversarial review
# showed `pip install --target vendor new-backend-dep` yielding {'vendor', ...}.
_ARG_TAKING_FLAGS = {
    "-r", "--requirement", "-c", "--constraint", "-e", "--editable",
    "-i", "--index-url", "--extra-index-url", "-f", "--find-links",
    "-t", "--target", "--prefix", "--root", "--python", "--cache-dir",
    "--log", "--proxy", "--platform", "--abi", "--implementation",
    "--python-version", "--only-binary", "--no-binary", "--report",
}
# Installing pip/uv/setuptools/wheel is bootstrapping, not a test dependency.
_INSTALLER_SELF = {"pip", "uv", "setuptools", "wheel"}
# Tokens that open a new command context — an installer AFTER one of these is
# still an install (`if pip install x; then`, `a && pip install x`).
_SEGMENT_BREAKS = {"&&", "||", ";", "|", "&", "(", ")", "{", "}",
                   "if", "then", "elif", "else", "do", "while", "until", "!"}
# Wrappers that may precede the installer without changing what it does.
_TRANSPARENT = {"sudo", "time", "nohup", "command", "exec", "xargs", "env"}


def _normalise(name: str) -> str:
    """PEP 503 comparison form: extras and version specifiers stripped."""
    base = re.split(r"[\[<>=!~;]", name, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", base).strip().lower()


def _backend_job_run_blocks() -> list[str]:
    """Every `run:` script belonging to the backend test lane — and nothing else."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = (doc or {}).get("jobs") or {}
    missing = [name for name in BACKEND_JOBS if jobs.get(name) is None]
    if missing:
        raise AssertionError(
            f"backend test-lane job(s) {missing} not found in {WORKFLOW} "
            f"(jobs: {sorted(jobs)}). They were renamed, split or removed — "
            "re-anchor this checker rather than letting it silently scan a "
            "subset of the lane."
        )
    blocks: list[str] = []
    for name in BACKEND_JOBS:
        blocks += [
            step["run"]
            for step in (jobs[name].get("steps") or [])
            if isinstance(step, dict) and step.get("run")
        ]
    return blocks


def _is_installer_at(tokens: list[str], i: int) -> int | None:
    """If an install command starts at tokens[i], return the index just past
    `install`; else None. Handles `pip`, `pip3`, `uv pip`, `python -m pip`."""
    t = tokens[i]
    if t == "uv" and i + 1 < len(tokens) and tokens[i + 1] in ("pip", "pip3"):
        i += 2
    elif re.fullmatch(r"python[0-9.]*", t) and tokens[i + 1:i + 3] == ["-m", "pip"]:
        i += 3
    elif re.fullmatch(r"pip[0-9]*", t):
        i += 1
    else:
        return None
    # allow global options between the installer and the subcommand
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] in _ARG_TAKING_FLAGS:
            i += 1
        i += 1
    return i + 1 if i < len(tokens) and tokens[i] == "install" else None


def _packages_in(script: str) -> set[str]:
    """Packages an install command in `script` would install.

    shlex, not `.split()` — the round-2 review found five shapes the naive
    tokenizer got WRONG, and every one of them was a FALSE NEGATIVE, which is
    the dangerous direction here: a dep installed in CI that this checker cannot
    see is a dep nobody has to declare.

        pip install "new-backend-dep>=1"                 -> [] (quote char rejected)
        if pip install new-backend-dep; then :; fi       -> [] (not at line start)
        env X=1 pip install new-backend-dep              -> [] (same)
        pip install a && pip install "new-dep>=1"        -> ['a', 'install']
        pip install --target vendor new-backend-dep      -> [..., 'vendor']
    """
    found: set[str] = set()
    script = re.sub(r"\\\s*\n\s*", " ", script)  # join `\`-continued lines
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            # unbalanced quotes (a YAML fragment, an expression): fail LOUD by
            # skipping only this line, never by pretending the file is clean —
            # the non-empty assertion in the test below is what catches a
            # wholesale parse failure.
            continue
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            # Step over anything that can legitimately precede an installer:
            # a segment break, a transparent wrapper, or a `VAR=value` prefix.
            if (tok in _SEGMENT_BREAKS or tok in _TRANSPARENT
                    or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok)):
                i += 1
                continue
            after = _is_installer_at(tokens, i)
            if after is None:
                i += 1
                continue
            j, skip_next = after, False
            while j < len(tokens) and tokens[j] not in _SEGMENT_BREAKS:
                a = tokens[j]
                if skip_next:
                    skip_next = False
                elif a in _ARG_TAKING_FLAGS:
                    skip_next = True
                elif a.startswith("-") or "/" in a or a.endswith(".txt") or a.startswith("$"):
                    pass
                else:
                    n = _normalise(a)
                    if n and n not in _INSTALLER_SELF:
                        found.add(n)
                j += 1
            i = j
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


def test_the_anchor_still_covers_the_job_that_installs_the_test_runtime() -> None:
    """GUILT for a re-narrowed anchor (S11, 2026-08-23).

    `pytest-xdist` is installed by `backend-shard` and by NO other job in the
    lane. Before this checker was re-anchored it read only `backend-tests`, and
    after the sharding split that job installs `coverage` alone — so the scan
    stayed non-empty, every assertion stayed green, and the install line this
    file exists to police had quietly left its field of view.

    A non-empty scan is not the same as a complete one (superscar #2 / W97).
    This pins the difference: narrow the anchor back to one job and this fails.
    """
    seen = inline_installed_packages()
    assert "pytest-xdist" in seen, (
        "the scan no longer reaches the job that installs the test runtime — "
        f"saw {sorted(seen)}. `pytest-xdist` comes only from `backend-shard`; "
        "if it is gone, BACKEND_JOBS has been narrowed or the shard job was "
        "renamed, and this checker is now policing a job that installs almost "
        "nothing."
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

    The five marked ROUND 2 are the ones an adversarial review found the naive
    `.split()` tokenizer getting wrong — every one a FALSE NEGATIVE, i.e. a
    package CI installs that the checker could not see and nobody would have to
    declare. That is the dangerous direction: a false positive annoys someone,
    a false negative is the bug this file exists to prevent, silently.
    """
    cases = {
        # shapes already present in this repo's workflows
        "uv pip install --system pytest pytest-cov fakeredis": {"pytest", "pytest-cov", "fakeredis"},
        "run: pip install pytest pytest-cov httpx": {"pytest", "pytest-cov", "httpx"},
        "python -m pip install module-package": {"module-package"},
        "pip install alpha-package # human note": {"alpha-package"},
        "uv pip install --system -r requirements.lock.txt": set(),
        "uv pip install --system -e ../../packages/cell-core": set(),
        "pip install --upgrade pip uv": set(),
        "# pip install commented-out-package": set(),
        "pip install \\\n  first-package \\\n  second-package": {"first-package", "second-package"},
        # ROUND 2 — each of these returned the wrong answer before shlex
        'pip install "quoted-dep>=1"': {"quoted-dep"},                       # quote char rejected the token
        "if pip install conditional-dep; then :; fi": {"conditional-dep"},   # installer not at line start
        "env FOO=1 pip install env-prefixed-dep": {"env-prefixed-dep"},      # same
        'pip install alpha && pip install "beta>=1"': {"alpha", "beta"},     # second install lost, 'install' harvested
        "pip install --target vendor targeted-dep": {"targeted-dep"},        # flag VALUE read as a package
    }
    for script, expected in cases.items():
        assert _packages_in(script) == expected, (
            f"parser mis-read {script!r}: got {_packages_in(script)}, want {expected}"
        )


def test_the_parser_fails_loud_rather_than_quiet_on_a_broken_line() -> None:
    """An unparseable line is skipped, never treated as 'no installs here' for
    the whole file: test_inputs_are_readable_and_non_empty above is what turns a
    wholesale parse failure into a red. Pinned so the two stay a pair."""
    assert _packages_in('pip install "unterminated') == set()
    assert inline_installed_packages(), (
        "the real workflow still parses to a non-empty set — if this ever goes "
        "empty, the coverage assertion below becomes vacuously true"
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
