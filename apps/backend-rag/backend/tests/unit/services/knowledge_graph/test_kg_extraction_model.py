"""
Regression guard for the KG extractor's Gemini model (2026-07-14).

The §10f feeder was armed live and every chunk 404'd because the extractor
hardcoded `gemini-2.0-flash-lite`, a model Google retired. This guards the
class: the generateContent call sites must reference the env-driven constant,
not a hardcoded model literal, and the default must be a survivable alias.
"""

import re
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[5]
    / "apps"
    / "backend-rag"
    / "scripts"
    / "kg_incremental_extraction.py"
)


def _source() -> str:
    # The test file lives under apps/backend-rag/backend/tests/... so a
    # repo-relative resolve is fragile across worktrees; fall back to walking
    # up for the scripts dir.
    if _SCRIPT.exists():
        return _SCRIPT.read_text()
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "scripts" / "kg_incremental_extraction.py"
        if cand.exists():
            return cand.read_text()
    raise AssertionError("kg_incremental_extraction.py not found")


def test_no_hardcoded_model_at_call_sites() -> None:
    src = _source()
    # A model="literal-string" at any generate_content call site is the bug.
    hardcoded = re.findall(r'model=["\']gemini-[\w.\-]+["\']', src)
    assert not hardcoded, f"hardcoded Gemini model at call site: {hardcoded}"


def test_default_model_is_survivable_alias() -> None:
    src = _source()
    assert '_KG_GEMINI_MODEL = os.environ.get("KG_GEMINI_MODEL"' in src
    # The default must be a "-latest" alias so a future model retirement does
    # not silently zero out extraction again.
    m = re.search(r'os\.environ\.get\("KG_GEMINI_MODEL",\s*"([^"]+)"\)', src)
    assert m, "KG_GEMINI_MODEL default not found"
    assert m.group(1).endswith("-latest"), f"default {m.group(1)!r} is not a -latest alias"
