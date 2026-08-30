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
    #
    # Exercised through a COPY, never by editing the production lint in place.
    # The earlier version wrote a mutated `scripts/lint_doctrine_citations.py` and
    # restored it in a `finally` — so a SIGKILL between the two left the repo's
    # real lint mutated, and a parallel test run could read the temporary version
    # and pass or fail for reasons that had nothing to do with it (Codex sol,
    # 2026-08-31). A test that can corrupt the thing it tests is not a test.
    import tempfile

    src = (REPO / "scripts" / "lint_doctrine_citations.py").read_text()
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / "lint_copy.py"
        copy.write_text(src.replace(
            'DEFAULT_SUBJECTS: tuple[str, ...] = (',
            'DEFAULT_SUBJECTS: tuple[str, ...] = ("__no_such_subject__.md",) if True else (', 1))
        r2 = subprocess.run([sys.executable, str(copy)], cwd=REPO, capture_output=True, text=True)
    assert r2.returncode == 2, (
        "a corpus run that extracted zero citations reported clean — the exact "
        f"failure this guard exists for:\n{r2.stdout}{r2.stderr}"
    )


def test_the_live_corpus_is_green() -> None:
    """The arming assertion: the real doctrine surface passes on this branch."""
    r = subprocess.run([sys.executable, str(_LINT)], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"live doctrine has an unresolved citation:\n{r.stdout}"


def test_the_cured_skill_is_green_and_says_why() -> None:
    """The cure is checked by the property that matters, not by its formatting.

    The earlier version asserted the retracted path sat inside a code fence, and
    computed a `fenced` flag it then never asserted (Codex sol, 2026-08-31 —
    finding 11: a test that measures something and throws the measurement away).
    Both are now replaced by the two things that are actually true and load-bearing:
    the file is green under the lint, and it carries a RETRACTION MARKER, which is
    what makes it survive a reformat that a fence would not.
    """
    skill = REPO / ".claude" / "skills" / "sota-architecture-loop" / "SKILL.md"
    text = skill.read_text()
    assert "pratica istituzionale" in text, "the honest provenance statement is gone"
    assert lint._RETRACTION_RE.search(text), (
        "the retraction marker is gone — without it the quoted dead path is a "
        "citation again, and the file that cures the phantom becomes one"
    )
    r = _run(skill)
    assert r.returncode == 0, f"the cured file is not green:\n{r.stdout}"


def test_every_retraction_in_the_repo_is_green_under_the_lint() -> None:
    """All three cures, by the same property. Naming them individually would let
    a fourth retraction land unchecked."""
    for rel in (
        ".claude/skills/sota-architecture-loop/SKILL.md",
        ".claude/skills/skill-catalog/SKILL.md",
        "AUTONOMOUS_OPS.md",
    ):
        f = REPO / rel
        assert lint._RETRACTION_RE.search(f.read_text()), f"{rel} lost its retraction marker"
        assert _run(f).returncode == 0, f"{rel} is red under the lint"


def test_a_retraction_marker_excuses_its_own_line_and_nothing_else(tmp_path: Path) -> None:
    """The marker is LINE-scoped, and this case is why.

    It was block-scoped first — "the paragraph after RETRACTED is exempt" — which
    excused every OTHER citation sharing that paragraph, live ones included, and
    the test written for it pinned only the blank-line boundary so the hole was
    locked in by its own guard (Kimi K3, 2026-08-31). The narrow rule costs one
    thing: a retraction must NAME its dead path on the marker's own line."""
    f = _write(
        tmp_path,
        "RETRACTED — `research/operations/dead-one.md` never existed. "
        "The live source is `research/operations/also-missing.md` today.\n"
        "\n"
        "And a plain claim: `research/operations/third-missing.md`.\n",
    )
    try:
        r = _run(f)
        assert r.returncode == 1
        assert "third-missing.md" in r.stdout, "a citation outside the marked line was excused"
        assert "dead-one.md" not in r.stdout, "the retracted path was reported anyway"
        # The load-bearing half: a live citation SHARING the marker's line is
        # excused too, and that is the accepted cost of the narrow rule — it is
        # named here rather than left for someone to discover.
        assert "also-missing.md" not in r.stdout
    finally:
        f.unlink()


def test_every_retraction_names_its_path_on_the_marker_line() -> None:
    """The rule above only works if the cures obey it. Asserted, because a
    retraction whose path drifts to the next line silently becomes a finding."""
    for rel in (
        ".claude/skills/sota-architecture-loop/SKILL.md",
        ".claude/skills/skill-catalog/SKILL.md",
        "AUTONOMOUS_OPS.md",
    ):
        text = (REPO / rel).read_text()
        marked = [ln for ln in text.splitlines() if lint._RETRACTION_RE.search(ln)]
        assert marked, f"{rel} has no retraction marker"
        assert any(("research/" in ln or "docs/" in ln) for ln in marked), (
            f"{rel} marks a retraction but names no path on the marker's own line — "
            "the marker is line-scoped, so the path would be a finding"
        )


def test_a_citation_reaching_through_a_tracked_symlink_resolves(tmp_path: Path) -> None:
    """`docs/design-palettes/kbli-images` is a tracked symlink to a directory
    under `apps/`. `git ls-tree` lists the LINK, and `rglob` does not descend into
    directory symlinks, so a real file behind it was reported missing by BOTH
    resolvers — a false positive on correct doctrine (Kimi K3, 2026-08-31)."""
    link = REPO / "docs" / "design-palettes" / "kbli-images"
    if not link.is_symlink():
        import pytest as _pytest

        _pytest.skip("the tracked symlink this case exists for is gone; the rule may be removable")
    target = next((p for p in link.resolve().iterdir() if p.is_file()), None)
    assert target is not None, "premise: the symlinked dir must contain a file"
    cited = f"docs/design-palettes/kbli-images/{target.name}"
    f = _write(tmp_path, f"See `{cited}`.\n")
    try:
        r = _run(f)
        assert r.returncode == 0, f"a real file behind a symlink read as missing:\n{r.stdout}"
    finally:
        f.unlink()


def test_a_titled_link_is_still_a_citation(tmp_path: Path) -> None:
    """Markdown allows `[x](path "title")`; leaving the title attached made the
    extension test fail and the citation invisible."""
    f = _write(tmp_path, 'See [x](research/operations/nope-titled.md "The Title").\n')
    try:
        r = _run(f)
        assert r.returncode == 1, f"a titled link was invisible:\n{r.stdout}"
        assert "nope-titled.md" in r.stdout
    finally:
        f.unlink()


def test_a_relative_prefix_is_normalised_in_prose_and_backticks_too(tmp_path: Path) -> None:
    """The `./` fix landed on links only, so the three recognisers disagreed —
    the same path was seen as a link and invisible as prose or in a span."""
    f = _write(
        tmp_path,
        "Backtick: `./research/operations/nope-tick.md`\n"
        "\n"
        "Prose: see ./research/operations/nope-prose.md for detail.\n",
    )
    try:
        r = _run(f)
        assert r.returncode == 1
        assert "nope-tick.md" in r.stdout, "./ in a backtick span was invisible"
        assert "nope-prose.md" in r.stdout, "./ in prose was invisible"
    finally:
        f.unlink()


def test_the_placeholder_token_set_is_actually_reachable(tmp_path: Path) -> None:
    """Its fixtures were all caught by the bracket/glob test first, so emptying
    the token set survived the whole suite — a branch that read as protection
    while nothing could tell it from dead code."""
    f = _write(tmp_path, "Write to `research/YYYY/nope-token.md`.\n")
    try:
        assert _run(f).returncode == 0, "a YYYY placeholder was treated as a citation"
    finally:
        f.unlink()


def test_tilde_fences_are_recognised_as_code(tmp_path: Path) -> None:
    """Codex sol finding 12: every fence fixture used backticks, so deleting the
    `~~~` branch survived. Markdown permits both."""
    f = _write(tmp_path, "Example:\n\n~~~text\nresearch/operations/nope-tilde.md\n~~~\n")
    try:
        assert _run(f).returncode == 0, "a ~~~ fence was scanned as prose"
    finally:
        f.unlink()


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


def test_a_relative_prefixed_link_is_still_a_citation(tmp_path: Path) -> None:
    """Codex sol finding 1: markdown links are routinely written `[x](./docs/y.md)`,
    and accepting only tokens beginning exactly `docs/` made every one of them
    invisible — an under-match in the one syntax a doc author is most likely to
    use. Kept as its own case because a mutation dropping the `./` strip survived
    the whole suite without it."""
    f = _write(tmp_path, "See [the thing](./research/operations/nope-relative.md).\n")
    try:
        r = _run(f)
        assert r.returncode == 1, f"a ./-prefixed citation was not seen:\n{r.stdout}"
        assert "nope-relative.md" in r.stdout
    finally:
        f.unlink()


def test_a_percent_encoded_link_resolves_to_the_real_file(tmp_path: Path) -> None:
    """Codex sol finding 4: a markdown link target is URL-encoded, so a real file
    whose name contains a space arrives as `%20` and was reported missing."""
    real = REPO / "docs" / "plans" / "2026-08-29-beyond-sota-craft-wave" / "L03-architecture-decision-making.md"
    assert real.is_file(), "premise: the fixture must cite a file that exists"
    encoded = "docs/plans/2026-08-29-beyond-sota-craft-wave/L03%2Darchitecture%2Ddecision%2Dmaking.md"
    f = _write(tmp_path, f"See [spec]({encoded}).\n")
    try:
        r = _run(f)
        assert r.returncode == 0, f"a percent-encoded path to a real file read as missing:\n{r.stdout}"
    finally:
        f.unlink()


def test_a_long_extension_is_still_a_citation(tmp_path: Path) -> None:
    """Codex sol finding 3: the extension pattern capped at six characters, so
    `.markdown` — eight, and real — slipped through unscanned."""
    f = _write(tmp_path, "See `docs/nope-long-extension.markdown`.\n")
    try:
        assert _run(f).returncode == 1
    finally:
        f.unlink()


def test_an_uppercase_directory_is_not_a_template(tmp_path: Path) -> None:
    """Codex sol finding 2: any capitalised segment was read as a placeholder, so
    `docs/API/x.md` — and `docs/RESEARCH_LANDSCAPE_2026.md`, a real filename shape
    in this repo — became unscannable. That is an under-match that hides exactly
    the phantoms this lint exists to find."""
    f = _write(tmp_path, "See `docs/API/nope-uppercase.md` and `docs/NOPE_LANDSCAPE_2026.md`.\n")
    try:
        r = _run(f)
        assert r.returncode == 1
        assert "nope-uppercase.md" in r.stdout and "NOPE_LANDSCAPE_2026.md" in r.stdout
    finally:
        f.unlink()


def test_an_indented_list_continuation_is_still_scanned(tmp_path: Path) -> None:
    """Why this lint does NOT exclude 4-space-indented blocks.

    An attempt to (Codex sol finding 5) made THIS case fail: markdown gives a
    list continuation the same indentation as a code block, and no heuristic
    separated them, so the rule hid a citation inside a nested bullet. That is an
    under-match, and this guard's posture is that an under-match hides a phantom
    while an over-match costs a finding nobody needed. The rule was removed and
    its absence documented at `_RETRACTION_RE`; the reformat worry it was meant
    to answer is covered semantically by the retraction marker instead."""
    f = _write(tmp_path, "- a bullet\n\n    and its continuation cites `research/operations/nope-in-list.md`\n")
    try:
        r = _run(f)
        assert r.returncode == 1, "a citation in a list continuation was skipped as code"
        assert "nope-in-list.md" in r.stdout
    finally:
        f.unlink()
