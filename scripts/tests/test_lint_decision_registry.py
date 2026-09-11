"""Guilt + innocence for `scripts/lint_decision_registry.py`.

THE RULE THIS EXISTS FOR is R1: a reused `D-NNN` is a HARD FAIL.

A reservation that lives only in a document nobody re-reads decays monotonically
with the number of concurrent writers, and this fleet has paid for that lesson
twice in two other counters:

  - W40: two migrations both claimed number 194, five minutes apart. The next
    deploy would have hard-failed before applying ANY migration.
  - W128: two PRs both claimed scar W126, three minutes apart, while
    `origin/main` still read W125 — so "is this number free?" answered TRUE for
    both of them, correctly, at the moment each asked.

Decision numbers are the same counter with the same writers. This corpus is what
makes the third instance impossible rather than merely unlikely.

Everything here is offline: the evidence resolver is injected, so no git, no
network, no clock.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_LINT = _SCRIPTS / "lint_decision_registry.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_decision_registry", _LINT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load()

_OK = """decisions:
  - id: D-001
    title: "a decision"
    date: 2026-01-01
    status: accepted
    door: two-way
    evidence: CLAUDE.md
"""


def _entries(text: str):
    return mod.parse_registry(text)


def _run(text: str, resolver=lambda _p: True):
    return mod.run_lint(_entries(text), resolver)


def _rules(violations: list[str]) -> set[str]:
    return {v.split()[0] for v in violations}


# ------------------------------------------------------------------- innocence


def test_the_real_shipped_registry_is_clean() -> None:
    """The registry this PR ships must pass its own lint.

    Not a tautology: it is 18 hand-written records and the lint has six rules,
    and the first run of the pair found a real defect (an evidence path that
    resolved nowhere).
    """
    text = (_SCRIPTS.parent / "docs" / "decisions" / "registry.yaml").read_text(encoding="utf-8")
    entries = _entries(text)
    assert len(entries) == 18, f"expected the 18 backfilled records, parsed {len(entries)}"
    code, violations = mod.run_lint(entries, lambda _p: True)
    assert code == 0 and violations == [], violations


def test_a_well_formed_minimal_entry_passes() -> None:
    code, violations = _run(_OK)
    assert code == 0 and violations == [], violations


# ----------------------------------------------------------------------- guilt


def test_R1_a_reused_id_is_a_hard_fail_and_names_both_lines() -> None:
    """W40 and W128, applied to decision numbers before they happen a third time."""
    text = _OK + _OK.split("decisions:\n")[1]
    code, violations = _run(text)
    assert code == 1
    assert "R1" in _rules(violations), violations
    dup = [v for v in violations if v.startswith("R1")][0]
    assert "D-001" in dup and "," in dup, f"the report must name every line: {dup}"


@pytest.mark.parametrize("bad_id", ["D-1", "D-0001", "X-001", "D001", "d-001"])
def test_R2_a_malformed_id_is_a_violation(bad_id: str) -> None:
    """A malformed id cannot be checked for collision, so it is not a lesser
    problem than a collision — it is the same problem, unmeasurable."""
    code, violations = _run(_OK.replace("D-001", bad_id))
    assert code == 1 and "R2" in _rules(violations), violations


def test_R3_superseded_by_is_required_exactly_when_the_status_says_so() -> None:
    superseded_without_target = _OK.replace("status: accepted", "status: superseded-by")
    assert "R3" in _rules(_run(superseded_without_target)[1])

    target_without_status = _OK.replace(
        "    door: two-way", "    superseded_by: D-002\n    door: two-way"
    )
    assert "R3" in _rules(_run(target_without_status)[1])


def test_R3_a_supersession_pointing_nowhere_is_a_violation() -> None:
    """The whole value of the field is that it RESOLVES. A dangling
    `superseded_by` is the registry claiming a link it cannot follow."""
    text = _OK.replace("status: accepted", "status: superseded-by").replace(
        "    door: two-way", "    superseded_by: D-999\n    door: two-way"
    )
    assert "R3" in _rules(_run(text)[1])


def test_R3_a_record_cannot_supersede_itself() -> None:
    text = _OK.replace("status: accepted", "status: superseded-by").replace(
        "    door: two-way", "    superseded_by: D-001\n    door: two-way"
    )
    assert "R3" in _rules(_run(text)[1])


def test_R3_postponed_requires_a_revisit_date_and_nothing_else_may_carry_one() -> None:
    postponed_no_date = _OK.replace("status: accepted", "status: postponed")
    assert "R3" in _rules(_run(postponed_no_date)[1])

    accepted_with_date = _OK.replace(
        "    door: two-way", "    revisit_by: 2026-12-01\n    door: two-way"
    )
    assert "R3" in _rules(_run(accepted_with_date)[1])


def test_R4_the_door_must_be_declared_and_must_be_one_of_the_two() -> None:
    assert "R4" in _rules(_run(_OK.replace("    door: two-way\n", ""))[1])
    assert "R4" in _rules(_run(_OK.replace("door: two-way", "door: revolving"))[1])


def test_R5_a_decision_with_no_resolvable_evidence_is_prose() -> None:
    """The resolver is injected, so this is about the RULE, not about git."""
    assert "R5" in _rules(_run(_OK, resolver=lambda _p: False)[1])
    assert "R5" in _rules(_run(_OK.replace("    evidence: CLAUDE.md\n", ""))[1])


def test_R5_a_line_anchor_is_stripped_before_the_path_is_resolved() -> None:
    """`CLAUDE.md#L130` must be resolved as `CLAUDE.md`.

    The anchor is a convenience for a human and drifts as the file changes; the
    PATH is the contract. Resolving the two together would make every record go
    red the first time somebody inserted a paragraph.
    """
    seen: list[str] = []

    def spy(path: str) -> bool:
        seen.append(path)
        return True

    _run(_OK.replace("evidence: CLAUDE.md", "evidence: CLAUDE.md#L130"), resolver=spy)
    assert seen == ["CLAUDE.md"], seen


def test_R6_contradicting_a_record_that_does_not_exist_is_a_violation() -> None:
    text = _OK.replace("    door: two-way", "    contradicts: [D-404]\n    door: two-way")
    assert "R6" in _rules(_run(text)[1])


def test_R6_contradicting_a_record_that_does_exist_is_fine() -> None:
    text = _OK + """  - id: D-002
    title: "second"
    date: 2026-01-02
    status: accepted
    door: two-way
    evidence: CLAUDE.md
    contradicts: [D-001]
"""
    code, violations = _run(text)
    assert code == 0 and violations == [], violations


def test_an_unparseable_line_is_a_violation_and_never_a_silent_skip(tmp_path: Path) -> None:
    """A parser that shrugs at what it does not understand reports a clean
    registry for a file it only half read.

    It RAISES rather than returning a violation, which is the stronger contract —
    a half-parsed registry cannot be rule-checked at all, so producing a partial
    verdict over it would be worse than producing none. What matters is that the
    CLI turns that into a VERDICT with a line number, not a traceback: this
    asserts both halves.
    """
    with pytest.raises(mod.ParseError):
        _entries(_OK + "  this is not a record\n")

    reg = tmp_path / "registry.yaml"
    reg.write_text(_OK + "  this is not a record\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-B", str(_LINT), "--fixture", str(reg)], capture_output=True, text=True
    )
    assert r.returncode == 1, f"rc={r.returncode}"
    out = r.stdout + r.stderr
    assert "PARSE ERROR" in out and "line 8" in out, out
    assert "Traceback" not in out, "a traceback is not a verdict"


# ------------------------------------------ findings from the cross-family round


def test_a_duplicate_KEY_inside_one_entry_is_a_parse_error() -> None:
    """The hole that hollowed out R1, and it is the likeliest hand-edit accident.

    A repeated key used to overwrite silently. Paste a record, add a new `id:` at
    the top, leave the old one below — the first id VANISHES, so two entries can
    claim one number and the hard-fail never sees it. The rule that exists to stop
    number collisions was blind to the way number collisions actually get made.
    """
    with pytest.raises(mod.ParseError) as e:
        _entries(
            "decisions:\n  - id: D-001\n    title: \"a\"\n    id: D-002\n"
            "    date: 2026-01-01\n    status: accepted\n    door: two-way\n    evidence: CLAUDE.md\n"
        )
    assert "duplicate key" in str(e.value) and "id" in str(e.value)


def test_a_HYPHENATED_key_is_accepted_and_normalised() -> None:
    """`superseded-by:` is the natural spelling because the STATUS is literally
    `superseded-by`. Rejecting it made the schema's own inconsistency the
    writer's problem, on the single most confusable field it has."""
    text = """decisions:
  - id: D-001
    title: "a"
    date: 2026-01-01
    status: superseded-by
    superseded-by: D-002
    door: two-way
    evidence: CLAUDE.md
  - id: D-002
    title: "b"
    date: 2026-01-02
    status: accepted
    door: two-way
    evidence: CLAUDE.md
"""
    code, violations = _run(text)
    assert code == 0 and violations == [], violations
    assert _entries(text)[0]["superseded_by"] == "D-002"


def test_a_hyphen_and_underscore_spelling_of_the_same_key_still_collide() -> None:
    """Normalising must not open a way to write the same field twice."""
    with pytest.raises(mod.ParseError):
        _entries(
            "decisions:\n  - id: D-001\n    superseded_by: D-002\n    superseded-by: D-003\n"
            "    title: \"a\"\n    date: 2026-01-01\n    status: superseded-by\n"
            "    door: two-way\n    evidence: CLAUDE.md\n"
        )


def test_a_SCALAR_contradicts_is_a_violation_not_a_silent_skip() -> None:
    """`contradicts: D-404` used to be skipped by an isinstance guard, so a
    malformed field read as "no contradictions" — the field says something and
    the lint hears nothing."""
    text = _OK.replace("    door: two-way", "    contradicts: D-404\n    door: two-way")
    assert "R6" in _rules(_run(text)[1])


def test_an_EMPTY_superseded_by_on_an_accepted_record_is_a_violation() -> None:
    """A vacuous field is worse than an absent one: absence is honest, while a
    present-but-empty `superseded_by` reads to a human as "somebody looked"."""
    bare = _OK.replace("    door: two-way", "    superseded_by:\n    door: two-way")
    assert "R3" in _rules(_run(bare)[1]), "a bare `superseded_by:` passed"

    quoted = _OK.replace("    door: two-way", '    superseded_by: ""\n    door: two-way')
    assert "R3" in _rules(_run(quoted)[1]), "an explicit empty-string superseded_by passed"


def test_the_resolver_works_when_origin_main_IS_ABSENT(tmp_path: Path) -> None:
    """The CI landmine this nearly shipped.

    The immune workflow's ONLY `git fetch origin main` sits ~750 lines AFTER the
    unit-test battery that runs this lint, and the workflow's own comment says
    checkout's fetch-depth:0 does not reliably leave refs/remotes/origin/main on
    a pull_request event. Gating the resolver on origin/main alone would have
    raised on every innocent PR and turned a REQUIRED job red for a ref nobody
    fetched.

    A repo with a commit but no `origin/main` must still answer — HEAD plus the
    working tree is weaker than origin/main, not blind: a typo resolves nowhere.
    """
    import subprocess as sp

    repo = tmp_path / "repo"
    (repo / "docs" / "decisions").mkdir(parents=True)
    for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        sp.run(["git", *cmd], cwd=repo, check=True, capture_output=True)
    (repo / "REAL.md").write_text("x", encoding="utf-8")
    (repo / "docs" / "decisions" / "registry.yaml").write_text(
        _OK.replace("evidence: CLAUDE.md", "evidence: REAL.md"), encoding="utf-8"
    )
    sp.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    sp.run(["git", "commit", "-qm", "x"], cwd=repo, check=True, capture_output=True)

    assert (
        sp.run(["git", "rev-parse", "--verify", "--quiet", "origin/main"], cwd=repo,
               capture_output=True).returncode != 0
    ), "premise: this repo must genuinely have no origin/main"

    lint = repo / "scripts"
    lint.mkdir()
    (lint / "lint_decision_registry.py").write_text(_LINT.read_text(encoding="utf-8"), encoding="utf-8")
    r = sp.run([sys.executable, "-B", str(lint / "lint_decision_registry.py")],
               cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "Traceback" not in (r.stdout + r.stderr)

    # HEAD must actually be CONSULTED, not merely listed. A path committed and
    # then DELETED from the working tree resolves through exactly one branch, so
    # a mutation that drops HEAD from the usable refs cannot hide behind the
    # working-tree fallback — which is precisely what it did in the first
    # version of this test.
    sp.run(["git", "rm", "-q", "REAL.md"], cwd=repo, check=True, capture_output=True)
    assert not (repo / "REAL.md").exists(), "premise: the file must be gone from the tree"
    r_head = sp.run([sys.executable, "-B", str(lint / "lint_decision_registry.py")],
                    cwd=repo, capture_output=True, text=True)
    assert r_head.returncode == 0, (
        f"HEAD was not consulted, so a committed-then-deleted path resolved nowhere: "
        f"rc={r_head.returncode}\n{r_head.stdout}"
    )

    # …and a typo still resolves NOWHERE, so the weaker check is not a blind one.
    (repo / "docs" / "decisions" / "registry.yaml").write_text(
        _OK.replace("evidence: CLAUDE.md", "evidence: NOPE.md"), encoding="utf-8"
    )
    r2 = sp.run([sys.executable, "-B", str(lint / "lint_decision_registry.py")],
                cwd=repo, capture_output=True, text=True)
    assert r2.returncode == 1 and "R5" in r2.stdout, f"{r2.returncode}\n{r2.stdout}"


def test_evidence_must_be_a_BLOB_inside_the_repo() -> None:
    """`-e` says "an object exists", which was true for a DIRECTORY.

    `evidence: docs` resolved. So did `/etc/passwd`, through the working-tree
    fallback, leaving the repository entirely. A registry records decisions about
    THIS repo, and evidence must be a readable document — not a tree, not a
    submodule gitlink, not a file somewhere else on the machine.

    This exercises the REAL resolver, which is the point: the R5 rule tests
    inject their own, so a resolver that returned `bool(path)` passed the entire
    suite. That mutation is the reason this test exists.
    """
    _, resolver = mod.gather_live_registry_data(mod.REPO_ROOT / "docs" / "decisions" / "registry.yaml")

    assert resolver("CLAUDE.md") is True, "a real tracked document must resolve"
    assert resolver("docs") is False, "a directory is not evidence"
    assert resolver("/etc/passwd") is False, "evidence must not escape the repo"
    assert resolver("../secrets") is False, "evidence must not escape the repo"
    assert resolver("docs/definitely-not-a-real-file.md") is False, "a typo must resolve nowhere"
    assert resolver("") is False


def test_every_evidence_path_in_the_SHIPPED_registry_really_resolves() -> None:
    """End-to-end through the REAL resolver, over the REAL registry.

    The previous version of this pair asserted only that the live CLI exited 0,
    which a resolver returning `bool(path)` also satisfies — every shipped
    evidence value is non-empty, so the whole suite accepted evidence that
    resolves nowhere. Found by a cross-family reviewer as a surviving mutation.
    """
    entries, resolver = mod.gather_live_registry_data(
        mod.REPO_ROOT / "docs" / "decisions" / "registry.yaml"
    )
    unresolved = [
        e["evidence"] for e in entries if not resolver(str(e.get("evidence", "")).split("#")[0])
    ]
    assert unresolved == [], unresolved


# ------------------------------------------------------------------ the CLI


def test_the_next_free_id_is_the_successor_of_the_highest() -> None:
    assert mod.next_free_id(_entries(_OK)) == "D-002"
    assert mod.next_free_id([]) == "D-001"


def test_a_missing_registry_exits_3_and_says_which_file() -> None:
    """A lint that cannot find its subject must not report clean."""
    r = subprocess.run(
        [sys.executable, "-B", str(_LINT), "--registry", "/nonexistent/registry.yaml"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 3, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "/nonexistent/registry.yaml" in (r.stdout + r.stderr)


def test_the_live_run_against_the_shipped_registry_is_clean(tmp_path: Path) -> None:
    """End-to-end through the REAL resolver — origin/main, then HEAD, then the
    working tree. This is what catches an evidence path that resolves nowhere,
    which is exactly what the first run of this pair found."""
    r = subprocess.run([sys.executable, "-B", str(_LINT)], capture_output=True, text=True, cwd=str(_SCRIPTS.parent))
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "No violations" in r.stdout, r.stdout
