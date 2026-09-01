"""`legal_status` is measured untrustworthy — this refuses anyone who reads it.

Zero signed decision 5 (2026-08-25) as MARK, not REMOVE. The audit that followed
found the field is not repairable by patching rows: it is derived by two bare,
OVERLAPPING regexes over chunk text (`TIDAK BERLAKU` contains `BERLAKU`), so a
provision that does not apply to a class of person, a guarantor being replaced,
and a law's clause revoking its own predecessor all mark the current document
revoked. 9 document_ids hold BOTH named values across their own points.

The repair was refused for a reason that only a consumer map could give: nothing
reads the field. At the time of the audit, one reference existed in the whole
backend and it was the write at ingestion (since retired, PR #4948 — the field
now has no write site at all; `test_the_summary_reports_a_measured_count_not_a_remembered_fact`
below locks that in as a MEASURED count, not a remembered one, per the lesson this
same file's docstring caught the module on an hour after it was written).
Patching 1,484 points would have changed no observable behaviour while making
four documents look authoritative among ~590 on the same broken derivation.

So the declaration "untrustworthy" is enforced here rather than written down
somewhere. It is a one-way ratchet: writing the field stays legal, reading it does
not, until it is re-derived at document level.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _lint():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "ci" / "legal_status_read_lint.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("_ls_lint", candidate)
            mod = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("_ls_lint", mod)
            spec.loader.exec_module(mod)
            return mod
    pytest.fail(f"scripts/ci/legal_status_read_lint.py not found from {here}")


LINT = _lint()


# ── innocence: the write, and everything unrelated, must pass ────────────────

INNOCENT = [
    ("the ingestion write, a dict-literal key",
     'payload = {"document_id": doc_id, "legal_status": metadata.get("status")}'),
    ("the same write spread over lines",
     'payload = {\n    "text": t,\n    "legal_status": status,\n}'),
    ("a nested write",
     'point = {"metadata": {"legal_status": st, "book_title": bt}}'),
    ("an unrelated field with a similar name",
     'x = payload.get("legal_status_reviewed_at")'),
    ("a variable that merely sounds like it",
     'legal_status = compute()  # a local name, not the payload field'),
    ("no mention at all", 'def f():\n    return 1'),
    ("an attribute WRITE — symmetric with the dict-literal write",
     'point.legal_status = derived'),
    ("a dict-literal write whose key is built by concatenation",
     'payload = {"legal_" + "status": derived}'),
    ("concatenation that does not fold to the field name",
     'k = "legal_" + "statuses"'),
    ("an attribute that merely shares a prefix",
     'x = record.legal_status_reviewed_at'),
    ("addition of two non-string constants — must not crash the folder",
     'total = 1 + 2'),
    ("a BinOp add where one side is not a literal — cannot fold, must not crash",
     'k = prefix + "status"'),
    # ── Round 2 / Guard 7: what a completeness reviewer named as accepted gaps —
    # each MUST stay innocent, and each is innocent for a DIFFERENT reason, not
    # one blanket "dynamic" excuse (see module docstring's "NOT caught" list).
    ("a keyword ARGUMENT whose name happens to be the field — a value being "
     "PASSED under that name, not a read of it",
     'consume(legal_status=value)'),
    ("a **kwargs spread of a dict that might hold the field — no literal string "
     "in the source for this shape to match, catching it soundly needs type info "
     "this lint does not have",
     'consume(**payload)'),
    ("a dict-unpacking spread, the literal-write-shaped sibling of **kwargs",
     'copy = {**payload}'),
    ("an aliased import of a constant defined in ANOTHER module — the value is "
     "static but resolving it needs cross-file analysis, out of scope for a "
     "single-file AST fold",
     'from external_contract import LEGAL_STATUS as KEY\nstatus_a = payload[KEY]'),
    (".format() with a non-literal argument — cannot fold, must not guess",
     'status_b = payload["legal_{}".format(suffix)]'),
    ("%-format with a non-literal operand — cannot fold, must not guess",
     'status_c = payload["legal_%s" % suffix]'),
    ('"".join() of non-literal parts — cannot fold, must not guess',
     'status_d = payload["".join(parts)]'),
    ("a .format() call that folds to something else entirely — proves the "
     "folder is checked against FIELD/NESTED, not just 'did it fold at all'",
     '"report_{}.txt".format("legal_status_summary")'),
    ("getattr with a computed name — the one gap the module docstring always "
     "named, unaffected by any of the Round 2 additions",
     'name = config.FIELD_NAME\nstatus_e = getattr(point, name)'),
]


@pytest.mark.parametrize("name,src", INNOCENT, ids=[c[0] for c in INNOCENT])
def test_innocence(name, src):
    assert LINT.scan_source(src) == [], f"{name}: refused a legitimate construct"


# ── guilt: every shape of a read ─────────────────────────────────────────────

GUILTY = [
    ("a .get() read", 'st = payload.get("legal_status")'),
    ("a subscript read", 'st = payload["legal_status"]'),
    ("the nested key", 'st = payload.get("metadata.legal_status")'),
    ("a Qdrant filter key",
     'flt = FieldCondition(key="metadata.legal_status", match=MatchValue(value="berlaku"))'),
    ("an exclusion filter — the exact thing decision 5 forbids",
     'must_not = [FieldCondition(key="legal_status", match=MatchValue(value="dicabut"))]'),
    ("a comparison", 'if payload.get("legal_status") == "dicabut": skip()'),
    ("hidden in a list of projected keys", 'KEYS = ["document_id", "legal_status"]'),
    ("a keyword argument", 'q = search(field="legal_status")'),
    ("an attribute read — the reviewer's exact evasion #2",
     'if point.legal_status == "dicabut": drop()'),
    ("two-part concatenation — the reviewer's exact evasion #1",
     'field = "legal_" + "status"'),
    ("three-part concatenation, proving the fold recurses",
     'field = "le" + "gal_" + "status"'),
    ("concatenation of the nested key, split so neither half alone matches "
     "anything (a genuine BinOp-fold proof, not an accidental plain-Constant hit)",
     'k = "metadata.legal_" + "status"'),
    ("concatenation used directly as a read, not via an intermediate name",
     'st = payload.get("legal_" + "status")'),
    # ── Round 2 / Guard 7: fully-literal string-building shapes the module
    # docstring used to (wrongly) claim no AST lint could catch.
    (".format() with a single literal positional argument",
     'st = payload["legal_{}".format("status")]'),
    (".format() with a literal keyword argument",
     'st = payload["{x}".format(x="legal_status")]'),
    ("%-format with a single literal operand",
     'st = payload["legal_%s" % "status"]'),
    ("%-format with a literal tuple operand",
     'st = payload["%s_%s" % ("legal", "status")]'),
    ('"".join() of a literal tuple',
     'st = payload["".join(("legal", "_status"))]'),
    ('"".join() of a literal list',
     'st = payload["".join(["legal", "_status"])]'),
    # ── Round 2 / Guard 7: the class-pattern match keyword the reviewer named
    # explicitly — kwd_attrs are raw strings, not Constant nodes, so this is
    # the one shape visit_Constant structurally cannot see on its own.
    ("a match/case class-pattern keyword — the reviewer's exact evasion",
     'match point:\n    case Point(legal_status=status_h):\n        consume(status_h)'),
    # ── Round 2 / Guard 7 regression guard: the reviewer explicitly confirmed
    # this ALREADY worked before Round 2 (MatchMapping keys are ordinary
    # Constant nodes) — it must keep working after the visit_Assign exemption
    # and the visit_MatchClass addition, not regress as a side effect of either.
    ("a match/case dict-pattern key — already caught before Round 2, must not "
     "regress",
     'match point:\n    case {"legal_status": status}:\n        consume(status)'),
    # ── Round 2 regression guard: the NEW visit_Assign exemption is scoped to
    # a SINGLE `ast.Name` target only — it must not overreach onto multi-target
    # or destructuring assigns, where the underlying Constant is still visited
    # independently and must still be caught.
    ("a multi-target assign — the single-Name exemption must not extend to it",
     'a = b = "legal_status"'),
    ("a tuple-destructuring assign — the target is not a bare Name either",
     'x, y = "legal_status", 2'),
]


@pytest.mark.parametrize("name,src", GUILTY, ids=[c[0] for c in GUILTY])
def test_guilt(name, src):
    assert LINT.scan_source(src), f"{name}: the lint accepted a read"


def test_a_read_and_a_write_in_one_module_reports_only_the_read():
    src = (
        'payload = {"legal_status": derived}\n'
        'if other.get("legal_status") == "dicabut":\n'
        '    drop()\n'
    )
    hits = LINT.scan_source(src)
    assert len(hits) == 1, hits
    assert hits[0][0] == 2, "reported the wrong line — the write, not the read"


def test_a_concatenated_read_and_a_concatenated_write_report_only_the_read():
    """Same shape as the plain-string case above, proven for the BinOp path too —
    the write exemption and the read detection must agree on the SAME node, not
    two independent guesses that happen to coincide today."""
    src = (
        'payload = {"legal_" + "status": derived}\n'
        'if other.get("legal_" + "status") == "dicabut":\n'
        '    drop()\n'
    )
    hits = LINT.scan_source(src)
    assert len(hits) == 1, hits
    assert hits[0][0] == 2, "reported the wrong line — the write, not the read"


def test_count_writes_also_counts_an_attribute_store_and_a_concatenated_key():
    """`count_writes` (the "clean — 0 reads, N write site(s)" measurement) must
    not undercount just because a write happens to use a shape newer than the
    plain dict-literal key it was first written against."""
    assert LINT.count_writes('point.legal_status = derived') == 1
    assert LINT.count_writes('payload = {"legal_" + "status": derived}') == 1
    assert LINT.count_writes(
        'point.legal_status = a\npayload = {"legal_" + "status": b}'
    ) == 2


def test_the_guilt_matrix_is_not_empty():
    """A parametrised test over an empty list passes while proving nothing."""
    assert len(GUILTY) >= 20 and len(INNOCENT) >= 18


def test_folded_write_exemptions_cover_the_new_literal_shapes_too():
    """Round 2: `.format()`/`%`/`.join()` fold in `_folded_str` now, which
    `visit_Dict`'s key check reuses automatically — a write built with any of
    them must stay exempt, symmetric with the pre-existing `+`-concatenation
    write exemption proven above."""
    for key_src in (
        '"legal_{}".format("status")',
        '"legal_%s" % "status"',
        '"".join(("legal", "_status"))',
    ):
        src = f"payload = {{{key_src}: derived}}"
        assert LINT.scan_source(src) == [], f"{key_src}: a folded-literal write was refused"
        assert LINT.count_writes(src) == 1, f"{key_src}: not counted as a write site"


def test_match_class_keyword_reports_the_pattern_line_not_the_match_line():
    src = (
        "match point:\n"
        "    case Point(\n"
        "        legal_status=status_h,\n"
        "    ):\n"
        "        consume(status_h)\n"
    )
    hits = LINT.scan_source(src)
    assert len(hits) == 1, hits
    assert hits[0][0] == 3, "reported the wrong line — should be the kwd pattern's own line"


def test_match_class_only_flags_the_named_keyword_not_every_keyword():
    """A class pattern with an unrelated keyword alongside must not spuriously
    hit — only the one literally named `legal_status`."""
    src = (
        "match point:\n"
        "    case Point(document_id=d, legal_status=s):\n"
        "        consume(d, s)\n"
    )
    hits = LINT.scan_source(src)
    assert len(hits) == 1, hits
    assert hits[0][1] == "legal_status"


# ── the real tree ────────────────────────────────────────────────────────────

def test_the_backend_reads_the_field_nowhere_today(capsys):
    """The state the audit measured, locked in.

    If this goes red, someone has started reading a signal that is wrong on the two
    largest documents it marks revoked. That is the moment to read kb/topics/ instead.
    """
    rc = LINT.main([])
    out = capsys.readouterr().out
    assert rc == 0, out
    # Round 2: the wording changed from "clean — 0 reads" to name its own
    # boundary ("statically resolvable") rather than imply completeness — see
    # module docstring's promise-reformulation. A substring check that still
    # matched the OLD wording would prove nothing about the NEW claim.
    assert "clean — 0 statically resolvable reads" in out


def test_the_lint_refuses_to_pass_when_it_scanned_nothing(monkeypatch, tmp_path, capsys):
    """A lint that reads no files reports success on everything.

    This is the vacuity guard: 0 modules scanned must be BROKEN (exit 2), never
    clean (exit 0).
    """
    monkeypatch.setattr(LINT, "_roots", lambda repo: [tmp_path / "nowhere"])
    assert LINT.main([]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_roots_cover_apps_scripts_and_kb_not_backend_rag_alone():
    """Round 2 / Guard 7(a): the reviewer's concrete example was a consumer
    under `scripts/` (`scripts/legal_consumer.py`) that the old
    `apps/backend-rag/backend`-only scope could never see. Lock in that the
    scan now actually covers scripts/, not just assert the summary LOOKS wider."""
    repo = Path(__file__).resolve()
    for parent in repo.parents:
        if (parent / ".git").exists():
            repo = parent
            break
    roots = {r.name for r in LINT._roots(repo)}
    assert roots == {"apps", "scripts", "kb"}, roots


def test_a_read_under_scripts_is_now_caught_by_a_real_scan(tmp_path, monkeypatch):
    """The reviewer's exact example: `scripts/legal_consumer.py` reading
    `payload["legal_status"]` used to score 0 reads because the old
    `apps/backend-rag/backend`-only scope never walked `scripts/` at all —
    never because the shape itself was invisible to scan_source(). This
    writes a real file to disk and drives the SAME per-file loop main() runs
    (read → scan_source → count_writes) over a `_roots()` pointed at it, so a
    regression that only re-narrows `_roots()` — the exact Guard 7(a) finding
    — would leave this scan silently empty, not just an in-memory string
    proven guilty in isolation, which was never the disputed claim."""
    fake_root = tmp_path / "scripts"
    fake_root.mkdir()
    (fake_root / "legal_consumer.py").write_text(
        'status = payload["legal_status"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(LINT, "_roots", lambda repo: [fake_root])
    repo = Path(__file__).resolve()  # unused by the loop below, just a stand-in `repo` arg
    found = []
    for root in LINT._roots(repo):
        for path in sorted(root.rglob("*.py")):
            if LINT._skip(path):
                continue
            found.extend(LINT.scan_source(path.read_text(encoding="utf-8")))
    assert found, "a real on-disk read under a scripts/-shaped root was not caught"


def test_allow_marker_suppresses_the_finding_but_stays_visible_not_silent():
    """Round 2 / Guard 7: the ALLOW_MARKER mechanism exists so this lint's own
    scan of its own diagnostic tooling (scripts/kb/audit_*.py and friends,
    once _roots() covers scripts/) doesn't need a directory-wide exemption —
    see _is_marked_allow's docstring. An unmarked read on the SAME shape must
    still be refused: the marker is a per-site opt-in, never a blanket one."""
    marked_lines = LINT._is_marked_allow(
        ['x = payload.get("legal_status")  # legal-status-lint: allow — audit tool'], 1
    )
    unmarked = LINT._is_marked_allow(['x = payload.get("legal_status")'], 1)
    assert marked_lines is True
    assert unmarked is False


def test_allow_marker_is_line_scoped_not_file_scoped():
    """A marker on line 1 must not silently allow an unmarked read on line 2 —
    it is a per-SITE opt-in, checked against the exact line the hit is on."""
    lines = [
        'x = payload.get("legal_status")  # legal-status-lint: allow — reason',
        'y = payload.get("legal_status")',
    ]
    assert LINT._is_marked_allow(lines, 1) is True
    assert LINT._is_marked_allow(lines, 2) is False


def test_a_plain_assignment_of_the_field_name_stays_guilty_everywhere_else():
    """`field = "legal_status"` — no concatenation, just a bare literal — must
    stay guilty: an earlier draft of the Round 2 fix for the self-flagging
    problem below (a general "NAME = literal is exempt" rule) accidentally
    un-caught this AND the pre-existing "assign the field to a variable"
    evasion (`field = "legal_" + "status"`, already in GUILTY above) along
    with it. The two shapes are structurally identical — the fix had to be
    file-scoped instead, see the next test."""
    assert LINT.scan_source('field = "legal_status"')


def test_the_lint_excludes_only_its_own_file_by_identity_not_by_pattern():
    """Round 2 regression proof for the exact bug this file's own widened scan
    hit first: `FIELD = "legal_status"` / `NESTED = "metadata.legal_status"`
    are this lint's own comparison vocabulary, not a payload read — but
    exempting them cannot be a general AST rule (see the test above for why
    that broke a real guilty case). The fix is `_skip()` excluding this exact
    file by resolved path identity — proven here directly against `_skip`,
    and by the full real-tree scan in `test_the_backend_reads_the_field_nowhere_today`
    which would otherwise refuse this file's own two constant lines the
    moment _roots() covers scripts/ci/."""
    lint_path = Path(LINT.__file__).resolve()
    assert LINT._skip(lint_path) is True
    # And the exclusion is by IDENTITY, not by directory name — a sibling
    # file in the same scripts/ci/ directory must NOT be swept in for free.
    sibling = lint_path.with_name("some_other_ci_script.py")
    assert LINT._skip(sibling) is False


def test_the_summary_reports_a_measured_count_not_a_remembered_fact():
    """The clean message used to read "The only reference is the ingestion write."

    That was true when it was written and became FALSE the moment the ingestion
    write was itself retired — a gate stating a fact it had not measured, which is
    the small version of what this campaign exists to correct. It now counts the
    write sites it actually saw.
    """
    assert LINT.count_writes('p = {"legal_status": x}') == 1
    assert LINT.count_writes('p = {"metadata": {"legal_status": x}}') == 1
    assert LINT.count_writes('p = {"legal_status": a, "other": b}\nq = {"legal_status": c}') == 2
    assert LINT.count_writes('st = payload.get("legal_status")') == 0, (
        "a READ was counted as a write site"
    )
    assert LINT.count_writes('def f():\n    return 1') == 0
