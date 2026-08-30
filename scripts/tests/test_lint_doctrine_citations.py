"""Guilt + innocence for the doctrine citation-integrity lint.

The defect this exists for: `.claude/skills/sota-architecture-loop/SKILL.md`
cited `research/operations/2026-05-30-sota-ai-architecture-methodology.md` and
said its three axioms were "verificate, vedi research file". That file has never
existed in this repository. A reader — human or agent — extends a cited claim the
trust it would extend to a real source, so a phantom citation is worse than none.

The innocence cases carry as much weight as the guilt ones, and the reason is
measured rather than theoretical: the first version of this lint reported 47
findings on a clean corpus, of which 4 were on SYMBIOSIS.md — this repo's most
load-bearing document — because it matched `docs/` in the MIDDLE of
`apps/mata-garuda/docs/X.md`, a path that exists. A lint that reddens correct
doctrine is a lint someone switches off.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_LINT = Path(__file__).resolve().parents[1] / "lint_doctrine_citations.py"
_SPEC = importlib.util.spec_from_file_location("lint_doctrine_citations", _LINT)
assert _SPEC and _SPEC.loader
lint = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lint)

REPO = Path(__file__).resolve().parents[2]


def _run(subject: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_LINT), "--subject", str(subject.relative_to(REPO))],
        cwd=REPO, capture_output=True, text=True,
    )


def _write(tmp_path: Path, body: str) -> Path:
    # Inside the repo, because the lint resolves citations against the repo it
    # runs in; a fixture outside it would test a different question.
    d = REPO / "scripts" / "tests" / "_fixtures_doctrine"
    d.mkdir(exist_ok=True)
    f = d / f"{tmp_path.name}.md"
    f.write_text(body, encoding="utf-8")
    return f


def test_guilt_a_cited_file_that_does_not_exist_is_red(tmp_path: Path) -> None:
    f = _write(tmp_path, "See `research/operations/2026-05-30-sota-ai-architecture-methodology.md`.\n")
    try:
        r = _run(f)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "does not exist" in r.stdout
        assert "2026-05-30-sota-ai-architecture-methodology.md" in r.stdout
    finally:
        f.unlink()


def test_innocence_a_cited_file_that_exists_is_green(tmp_path: Path) -> None:
    # A path that exists on THIS branch — the resolver reads the checkout it runs
    # in, so a fixture citing a file that only lands on another branch tests the
    # branch, not the lint.
    f = _write(tmp_path, "See `docs/plans/2026-08-29-beyond-sota-craft-wave/L03-architecture-decision-making.md`.\n")
    try:
        assert _run(f).returncode == 0
    finally:
        f.unlink()


def test_innocence_a_path_inside_a_fenced_code_block_is_not_a_citation(tmp_path: Path) -> None:
    """The spec's named innocence requirement, and the mechanism the cured skill
    file relies on to quote its own retracted citation as a LITERAL."""
    f = _write(tmp_path, "Retracted:\n\n```text\nresearch/operations/2026-05-30-does-not-exist.md\n```\n")
    try:
        r = _run(f)
        assert r.returncode == 0, f"a fenced literal was treated as a citation:\n{r.stdout}"
    finally:
        f.unlink()


def test_innocence_a_shell_example_is_not_a_citation(tmp_path: Path) -> None:
    f = _write(tmp_path, "Run `grep -n foo research/operations/nope-does-not-exist.md` to check.\n")
    try:
        assert _run(f).returncode == 0
    finally:
        f.unlink()


def test_innocence_docs_in_the_middle_of_a_longer_path(tmp_path: Path) -> None:
    """The over-match that reddened SYMBIOSIS.md. `apps/mata-garuda/docs/X.md`
    is not a citation to `docs/X.md`, and `~/Desktop/OTHER-PROJECT/docs/Y.md` is
    not a citation to this repo at all."""
    f = _write(
        tmp_path,
        # Backticked — the span recogniser's path.
        "- `apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md`\n"
        "- `~/Desktop/OSINT-Nexus/docs/RESEARCH_LANDSCAPE_2026.md`\n"
        # And BARE in prose — the regex recogniser's path, which is the one that
        # carried the defect. Without this line a mutation restoring `\b` (which
        # matches immediately after a slash) survives every case here: the span
        # recogniser anchors independently, so the two must both be exercised.
        "See apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md for the patterns.\n"
        "Older notes live in ~/Desktop/OSINT-Nexus/docs/RESEARCH_LANDSCAPE_2026.md there.\n",
    )
    try:
        r = _run(f)
        assert r.returncode == 0, f"matched a path fragment mid-path:\n{r.stdout}"
    finally:
        f.unlink()


def test_innocence_a_bare_directory_is_not_a_citation(tmp_path: Path) -> None:
    """`research/operations/` names a place, not a source. Requiring a file
    extension is what separates the two; without it the lint cried 47 times to
    be right 12."""
    f = _write(tmp_path, "Captures live in `research/operations/` and plans in `docs/plans/`.\n")
    try:
        assert _run(f).returncode == 0
    finally:
        f.unlink()


def test_innocence_a_template_path_is_not_a_citation(tmp_path: Path) -> None:
    f = _write(tmp_path, "Write to `research/<domain>/YYYY-MM-DD-slug.md` and `docs/plans/*.md`.\n")
    try:
        assert _run(f).returncode == 0
    finally:
        f.unlink()


def test_one_finding_is_reported_once(tmp_path: Path) -> None:
    """Three recognisers run over the same line, so a backticked markdown link is
    legitimately seen by two of them. Reporting it twice does not make it truer."""
    f = _write(tmp_path, "See [`research/operations/nope-does-not-exist.md`](research/operations/nope-does-not-exist.md).\n")
    try:
        r = _run(f)
        assert r.returncode == 1
        assert r.stdout.count("nope-does-not-exist.md") == 1, r.stdout
    finally:
        f.unlink()


def test_an_empty_extraction_is_an_error_not_a_clean_bill(tmp_path: Path) -> None:
    """A lint that silently scans nothing reports clean forever — the exact
    failure class it exists to catch."""
    r = subprocess.run(
        [sys.executable, str(_LINT), "--subject", "scripts/tests/_fixtures_doctrine/__none__.md"],
        cwd=REPO, capture_output=True, text=True,
    )
    # An explicit --subject that matches nothing is a usage error, not a clean run.
    assert r.returncode == 2, f"{r.stdout}{r.stderr}"

    # And the load-bearing half: on the DEFAULT corpus, an extractor that finds
    # nothing must be an error rather than a clean bill.
    broken = REPO / "scripts" / "lint_doctrine_citations.py"
    original = broken.read_text()
    try:
        broken.write_text(original.replace(
            'DEFAULT_SUBJECTS: tuple[str, ...] = (',
            'DEFAULT_SUBJECTS: tuple[str, ...] = ("__no_such_subject__.md",) if True else (', 1))
        r2 = subprocess.run([sys.executable, str(_LINT)], cwd=REPO, capture_output=True, text=True)
        assert r2.returncode == 2, (
            "a corpus run that extracted zero citations reported clean — the exact "
            f"failure this guard exists for:\n{r2.stdout}{r2.stderr}"
        )
    finally:
        broken.write_text(original)


def test_the_live_corpus_is_green() -> None:
    """The arming assertion: the real doctrine surface passes on this branch."""
    r = subprocess.run([sys.executable, str(_LINT)], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"live doctrine has an unresolved citation:\n{r.stdout}"


def test_the_cured_skill_no_longer_cites_the_phantom() -> None:
    text = (REPO / ".claude" / "skills" / "sota-architecture-loop" / "SKILL.md").read_text()
    assert "pratica istituzionale" in text, "the honest provenance statement is gone"
    # The retracted path may still appear as a quoted LITERAL, but only inside a fence.
    for i, line in enumerate(text.splitlines()):
        if "2026-05-30-sota-ai-architecture-methodology" in line:
            fenced = text.splitlines()[:i].count("```text") > text.splitlines()[:i].count("```") - text.splitlines()[:i].count("```text")
            assert line.lstrip().startswith("research/"), (
                "the retracted path reappeared outside its code fence — it would be "
                "a citation again, and the lint would be red on the file that cures it"
            )


def test_the_workflow_filter_covers_every_file_the_lint_scans() -> None:
    """Trigger symmetry, the way `test_tg_gateway_trigger_symmetry.py` does it.

    A guard whose CI job does not start on the only diff that could violate it
    has been armed at nothing. Measured 2026-08-31: the lint's subject globs
    reached `.claude/skills/modus/AMENDMENTS.md` while the workflow's path filter
    listed only `*/SKILL.md`, so a phantom citation added there would have been a
    finding on a PR that never ran the finder. Asserting the relation rather than
    the list means the next subject added to the lint fails HERE, loudly, instead
    of silently escaping the job.
    """
    import fnmatch

    wf = (REPO / ".github" / "workflows" / "immune-enforcement.yml").read_text()
    block = wf.split("while IFS= read -r f; do", 1)[1].split('done <<< "$CHANGED"', 1)[0]
    patterns = [
        ln.strip().rstrip("|\\").strip()
        for ln in block.splitlines()
        if ln.strip().rstrip("|\\").strip() and not ln.strip().startswith(("#", "case", "esac", "*)", ";;", "RELEVANT"))
    ]

    subjects = lint._collect_subjects(REPO, None)
    uncovered = []
    for s in subjects:
        rel = s.relative_to(REPO).as_posix()
        if not any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            uncovered.append(rel)

    assert not uncovered, (
        "these files are scanned by the lint but would NOT start the job that runs it — "
        "add them to immune-enforcement.yml's path filter, or drop them from "
        f"DEFAULT_SUBJECTS: {uncovered}"
    )
