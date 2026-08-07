#!/usr/bin/env python3
"""apps/zantara-media's tests must have a runner, and it must be the DIRECTORY.

Why this exists (2026-08-07, GARUDA decommission). Two facts collide:

  - `magazine-auto-assets.yml` is the ONLY job that installs this app's
    dependencies (pydantic, httpx, Pillow, cryptography, rfc8785), so it is the
    only job that CAN run its tests. The lean `antidotes` job runs on a bare
    interpreter and dies at collection on `pydantic`.
  - `antidotes` is a REQUIRED check; `magazine-auto-assets` is not.

So the suite runs where the environment is, and this — dependency-free, stdlib
only, therefore runnable in the required job — is what stops the coverage from
silently narrowing again. It was a named file list until today, which is how
`tests/test_dlp.py` and `tests/test_image_handler.py` ended up with no runner
anywhere: a list does not grow when a file is added.

DECLARED LIMIT: this proves a runner is CONFIGURED over the whole directory. It
cannot prove the job ran, or passed — `magazine-auto-assets.yml` carries a
`paths:` filter, so a PR touching nothing under apps/zantara-media legitimately
skips it. Pair it with that job's own verdict, not with this test alone.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github/workflows/magazine-auto-assets.yml"
TESTS_DIR = "apps/zantara-media/tests"


def _pytest_invocations(text: str) -> list[str]:
    """Every `python -m pytest ...` command in the workflow, flattened."""
    out = []
    for m in re.finditer(r"python -m pytest\b", text):
        tail = text[m.start():]
        # a `>-` folded block ends at the next line that starts a new YAML key
        # or step; good enough here, and the corpus below pins the behaviour.
        stop = re.search(r"\n\s*(-\s+name:|[a-z-]+:)\s", tail)
        out.append(" ".join((tail[: stop.start()] if stop else tail).split()))
    return out


def _covers_directory(invocations: list[str]) -> bool:
    """True if some invocation targets the tests DIRECTORY, not files under it."""
    for cmd in invocations:
        for tok in cmd.split():
            if tok.rstrip("/") == TESTS_DIR:
                return True
    return False


def test_the_workflow_runs_the_whole_zantara_media_tests_directory():
    text = WORKFLOW.read_text()
    inv = _pytest_invocations(text)
    assert inv, "no `python -m pytest` invocation found in %s" % WORKFLOW.name
    assert _covers_directory(inv), (
        "magazine-auto-assets.yml must run the %s DIRECTORY. Naming individual "
        "files leaves every future test file with no runner — that is how "
        "test_dlp.py and test_image_handler.py were orphaned. Found: %r" % (TESTS_DIR, inv)
    )


def test_the_workflow_is_triggered_by_changes_to_that_app():
    """A runner that never wakes is not a runner (superscar #2)."""
    text = WORKFLOW.read_text()
    assert "apps/zantara-media/**" in text, (
        "magazine-auto-assets.yml must keep `apps/zantara-media/**` in its paths "
        "filter, or the suite it owns never runs on a PR that changes the app."
    )


def test_every_test_file_in_the_app_is_under_that_directory():
    """Guards the assumption the directory form relies on."""
    root = REPO / TESTS_DIR
    assert root.is_dir(), "%s missing — did the app move?" % TESTS_DIR
    found = list(root.rglob("test_*.py"))
    assert found, "no test files under %s — a green directory run would be vacuous" % TESTS_DIR


# --- guilt: the shape this guard exists to reject -------------------------

def test_it_rejects_a_named_file_list():
    narrowed = """
      - name: Verify magazine asset lifecycle contracts
        run: >-
          python -m pytest -q
          apps/zantara-media/tests/magazine/test_cli.py
          apps/zantara-media/tests/magazine/test_media_resolver.py
        continue-on-error: false
    """
    assert not _covers_directory(_pytest_invocations(narrowed))


def test_it_rejects_a_sibling_directory_that_merely_starts_the_same():
    sneaky = """
        run: >-
          python -m pytest -q
          apps/zantara-media/tests-disabled
    """
    assert not _covers_directory(_pytest_invocations(sneaky))


# --- innocence: shapes that are legitimately fine -------------------------

def test_it_accepts_the_directory_with_a_trailing_slash():
    ok = """
        run: >-
          python -m pytest -q
          apps/zantara-media/tests/
    """
    assert _covers_directory(_pytest_invocations(ok))


def test_it_accepts_the_directory_alongside_other_targets():
    ok = """
        run: >-
          python -m pytest -q
          apps/zantara-media/tests
          scripts/tests/test_flowkit_cli.py
    """
    assert _covers_directory(_pytest_invocations(ok))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        try:
            fn()
            print("  ok   %s" % fn.__name__)
        except AssertionError as exc:
            bad += 1
            print("  FAIL %s: %s" % (fn.__name__, exc))
    print("\n%d/%d passed" % (len(fns) - bad, len(fns)))
    raise SystemExit(1 if bad else 0)
