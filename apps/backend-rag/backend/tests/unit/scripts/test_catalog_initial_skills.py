"""Unit tests for backend/scripts/catalog_initial_skills.py.

Focus: the pure extraction function (``extract_candidates_from_source``) that
turns a Python source file into a list of skill candidate dicts. The CLI glue
(argparse, filesystem walk, dry-run report) is exercised via an integration
smoke test that points at a small temp tree.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.scripts.catalog_initial_skills import (
    SkillCandidate,
    extract_candidates_from_source,
    is_eligible_function,
    scan_tree,
)


# ─── Function eligibility ────────────────────────────────────────


@pytest.mark.parametrize("name,expected", [
    ("extract_kbli_codes", True),
    ("parse_akta_founders", True),
    ("retry_with_backoff", True),
    ("_private_helper", False),
    ("__init__", False),
    ("test_something", False),
    ("get", False),          # too short / trivial CRUD
    ("list_items", False),   # CRUD
    ("create_user", False),  # CRUD
    ("delete_record", False),
    # Verbs that carry domain-specific procedure are kept
    ("detect_proxy_signatures", True),
    ("normalize_outcome", True),
    ("chunk_text", True),
    ("classify_intent", True),
])
def test_is_eligible_function_name(name: str, expected: bool):
    assert is_eligible_function(name) is expected


# ─── Source extraction ───────────────────────────────────────────


def _source(body: str) -> str:
    """Dedent helper so tests can use triple-quoted source with natural indent."""
    return textwrap.dedent(body).lstrip("\n")


def test_extract_candidates_ignores_test_files():
    src = _source("""
        def extract_kbli_codes(text):
            '''Pull KBLI codes from free text.'''
            return []
    """)
    # Files whose path segments mark them as tests must return zero candidates.
    out = extract_candidates_from_source(
        source=src, relpath="backend/tests/unit/test_foo.py", cell_hint="foo",
    )
    assert out == []


def test_extract_candidates_skips_private_and_dunder():
    src = _source("""
        def _helper():
            pass

        def __dunder__():
            pass
    """)
    out = extract_candidates_from_source(
        source=src, relpath="backend/services/foo/bar.py", cell_hint="foo",
    )
    assert out == []


def test_extract_candidates_captures_docstring_as_procedure():
    src = _source('''
        def detect_proxy_signatures(text):
            """Use regex for 'bertindak berdasarkan' before LLM parsing."""
            return []
    ''')
    out = extract_candidates_from_source(
        source=src, relpath="backend/services/akta/parser.py", cell_hint="akta",
    )
    assert len(out) == 1
    cand = out[0]
    assert isinstance(cand, SkillCandidate)
    assert cand.skill_id.startswith("akta:")
    assert "detect_proxy_signatures" in cand.skill_id
    assert "bertindak berdasarkan" in cand.procedure
    assert cand.source_file == "backend/services/akta/parser.py"
    assert cand.cell == "akta"
    assert cand.confidence == 0.5
    assert cand.scope == "Project"


def test_extract_candidates_fallback_procedure_when_no_docstring():
    src = _source("""
        def normalize_outcome(raw):
            return raw.strip().lower()
    """)
    out = extract_candidates_from_source(
        source=src, relpath="backend/services/experience/util.py", cell_hint="experience",
    )
    assert len(out) == 1
    # Fallback shape: "<name> in <file>" — never empty (required by genome schema).
    assert out[0].procedure
    assert "normalize_outcome" in out[0].procedure


def test_extract_candidates_methods_of_classes_included():
    src = _source('''
        class ChunkingStrategy:
            def chunk_text(self, text, size=10_000):
                """Split text into overlapping windows."""
                return []

            def _private(self):
                pass
    ''')
    out = extract_candidates_from_source(
        source=src, relpath="backend/services/rag/chunker.py", cell_hint="rag",
    )
    ids = [c.skill_id for c in out]
    assert any("chunk_text" in i for i in ids)
    assert not any("_private" in i for i in ids)


def test_extract_candidates_crud_excluded():
    src = _source('''
        def get_user(uid):
            """Fetch a user by id."""
            return {}

        def list_orders():
            """List all orders."""
            return []

        def create_invoice(data):
            """Create an invoice."""
            return {}
    ''')
    out = extract_candidates_from_source(
        source=src, relpath="backend/services/crm/repo.py", cell_hint="crm",
    )
    assert out == []


def test_extract_candidates_cell_hint_fallback_when_missing():
    """When cell_hint is empty, the skill_id must still be unique and valid."""
    src = _source('''
        def parse_bali_visa_timeline(text):
            """Extract visa timeline events from unstructured text."""
            return []
    ''')
    out = extract_candidates_from_source(
        source=src, relpath="backend/services/misc/parser.py", cell_hint="",
    )
    assert len(out) == 1
    # Must not start with 'colon' (i.e., empty prefix).
    assert not out[0].skill_id.startswith(":")


# ─── Tree scan (integration of extractor + filesystem walk) ──────


def test_scan_tree_walks_python_files(tmp_path: Path):
    root = tmp_path / "backend-rag"
    services = root / "backend" / "services" / "foo"
    services.mkdir(parents=True)
    (services / "parser.py").write_text(_source('''
        def parse_something(text):
            """Do something to text."""
            return text
    '''))
    (services / "__init__.py").write_text("")
    # Test file should be skipped
    tests = root / "backend" / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_parser.py").write_text(_source('''
        def test_parse_something():
            pass
    '''))

    cands = scan_tree(root)
    ids = [c.skill_id for c in cands]
    assert any("parse_something" in i for i in ids)
    assert not any("test_" in i for i in ids)


def test_scan_tree_caps_at_explicit_limit(tmp_path: Path):
    """When scan yields >limit candidates the function truncates and warns."""
    root = tmp_path / "root"
    pkg = root / "backend" / "services" / "many"
    pkg.mkdir(parents=True)
    body = "\n\n".join(
        f"def extract_thing_{i}(x):\n    \"\"\"Do {i}.\"\"\"\n    return x"
        for i in range(20)
    )
    (pkg / "module.py").write_text(body)

    cands = scan_tree(root, limit=5)
    assert len(cands) == 5
