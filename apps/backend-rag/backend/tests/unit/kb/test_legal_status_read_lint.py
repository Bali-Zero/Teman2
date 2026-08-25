"""`legal_status` is measured untrustworthy — this refuses anyone who reads it.

Zero signed decision 5 (2026-08-25) as MARK, not REMOVE. The audit that followed
found the field is not repairable by patching rows: it is derived by two bare,
OVERLAPPING regexes over chunk text (`TIDAK BERLAKU` contains `BERLAKU`), so a
provision that does not apply to a class of person, a guarantor being replaced,
and a law's clause revoking its own predecessor all mark the current document
revoked. 9 document_ids hold BOTH named values across their own points.

The repair was refused for a reason that only a consumer map could give: nothing
reads the field. One reference exists in the whole backend and it is the write at
ingestion. Patching 1,484 points would have changed no observable behaviour while
making four documents look authoritative among ~590 on the same broken
derivation.

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


def test_the_guilt_matrix_is_not_empty():
    """A parametrised test over an empty list passes while proving nothing."""
    assert len(GUILTY) >= 8 and len(INNOCENT) >= 6


# ── the real tree ────────────────────────────────────────────────────────────

def test_the_backend_reads_the_field_nowhere_today(capsys):
    """The state the audit measured, locked in.

    If this goes red, someone has started reading a signal that is wrong on the two
    largest documents it marks revoked. That is the moment to read kb/topics/ instead.
    """
    rc = LINT.main([])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "clean — 0 reads" in out


def test_the_lint_refuses_to_pass_when_it_scanned_nothing(monkeypatch, tmp_path, capsys):
    """A lint that reads no files reports success on everything.

    This is the vacuity guard: 0 modules scanned must be BROKEN (exit 2), never
    clean (exit 0).
    """
    monkeypatch.setattr(LINT, "_roots", lambda repo: [tmp_path / "nowhere"])
    assert LINT.main([]) == 2
    assert "does not exist" in capsys.readouterr().err


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
