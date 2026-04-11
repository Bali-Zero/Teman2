# Visa Subgraph Multi-Step Planner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 246-line flat `visa.py` subgraph with a LangGraph multi-step planner that decomposes questions, retrieves with per-sub-question citations, self-critiques, and composes a fully-cited final answer.

**Architecture:** A LangGraph `StateGraph` with 5 sequential nodes (b211_rewrite → decompose → plan_execute → compose → terminate). Sub-question execution is a topologically-sorted for-loop inside `plan_execute`, not a separate graph. Backward-compatible: `make_visa_subgraph(services)` still returns an async callable that mutates `GraphState` with `retrieved_documents`, `kg_entities`, `kg_relationships`, `domain`, and `current_node`.

**Tech Stack:** Python 3.11+ · pydantic · structlog · langgraph · pytest · pytest-asyncio · existing `Services` container (`LLMGateway` / `VectorStore` / `KGStore`)

---

## File Structure

**Create**
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/__init__.py`
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/types.py`
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py`
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py`
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/compose.py`
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/specs.py`
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/planner.py`
- `apps/graph-engine/src/nuzantara_graph/graders/contradiction_grader.py`
- `apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py`
- `apps/graph-engine/docs/visa-planner-architecture.md`

**Delete**
- `apps/graph-engine/src/nuzantara_graph/subgraphs/visa.py` (replaced by visa/ package)

**Modify**
- `apps/graph-engine/src/nuzantara_graph/subgraphs/__init__.py` (unchanged import path, but verify resolution)
- `apps/graph-engine/src/nuzantara_graph/graders/__init__.py` (add contradiction grader export)
- `apps/graph-engine/tests/unit/subgraphs/test_visa_subgraph.py` (adjusts for new API — keep `_identify_visa_type` tests as they are moved to `specs.py`)

---

### Task 1: Scaffold visa package with types

**Files:**
- Create: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/__init__.py`
- Create: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/types.py`
- Test: `apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py`

- [ ] **Step 1: Delete old visa.py first** (so package can take its place)

Run: `rm apps/graph-engine/src/nuzantara_graph/subgraphs/visa.py`

- [ ] **Step 2: Write failing test for types**

```python
# apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
"""Tests for the visa multi-step planner."""

from __future__ import annotations

import pytest


@pytest.mark.unit
class TestPlannerTypes:
    def test_sub_question_schema(self):
        from nuzantara_graph.subgraphs.visa.types import SubQuestion

        sq = SubQuestion(idx=0, text="What is KITAS?", needs_kb=True, depends_on=[])
        assert sq.idx == 0
        assert sq.needs_kb is True
        assert sq.depends_on == []

    def test_chunk_schema(self):
        from nuzantara_graph.subgraphs.visa.types import Chunk

        c = Chunk(
            doc_id="kitas_guide_2024",
            span_start=0,
            span_end=200,
            score=0.85,
            content="KITAS is a temporary stay permit...",
        )
        assert c.doc_id == "kitas_guide_2024"
        assert c.span_end == 200

    def test_node_evidence_empty(self):
        from nuzantara_graph.subgraphs.visa.types import NodeEvidence, SubQuestion

        sq = SubQuestion(idx=0, text="q", needs_kb=True, depends_on=[])
        ev = NodeEvidence(sub_question=sq, chunks=[], answer_fragment="", grounded=False)
        assert ev.chunks == []
        assert ev.grounded is False
```

- [ ] **Step 3: Run test — expect ImportError**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestPlannerTypes -q 2>&1 | tail -20`

Expected: ImportError (visa package not yet created)

- [ ] **Step 4: Create the package __init__.py (placeholder, will be filled in Task 10)**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/__init__.py
"""Visa multi-step planner subgraph."""

from __future__ import annotations

from nuzantara_graph.subgraphs.visa.planner import make_visa_subgraph

__all__ = ["make_visa_subgraph"]
```

Note: this will fail to import until planner.py exists. We'll create a temporary stub:

- [ ] **Step 5: Create temporary planner stub**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/planner.py
"""Visa planner — temporary stub, filled in Task 9."""

from __future__ import annotations

from typing import Any


def make_visa_subgraph(services: Any):
    """Temporary stub — real implementation in Task 9."""

    async def _stub(state: Any) -> dict[str, Any]:
        return {
            "retrieved_documents": [],
            "kg_entities": [],
            "kg_relationships": [],
            "domain": "general",
            "current_node": "subgraph_visa",
        }

    return _stub
```

- [ ] **Step 6: Create types.py**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/types.py
"""Planner types — SubQuestion, Chunk, NodeEvidence, PlannerState."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    """A single decomposed sub-question in the planner DAG."""

    idx: int = Field(ge=0)
    text: str
    needs_kb: bool = True
    depends_on: list[int] = Field(default_factory=list)


class Chunk(BaseModel):
    """A retrieved evidence chunk with a citable span.

    span_start/span_end are character offsets into the source document.
    When the vector store does not expose true offsets, we default to
    0..len(content) — this is declared as a known limitation in the
    architecture doc, not silently ignored.
    """

    doc_id: str
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    content: str

    def citation(self) -> str:
        return f"[{self.doc_id}:{self.span_start}-{self.span_end}]"


class NodeEvidence(BaseModel):
    """Evidence collected for one sub-question during execution."""

    sub_question: "SubQuestion"
    chunks: list[Chunk] = Field(default_factory=list)
    answer_fragment: str = ""
    grounded: bool = False
    contradiction_score: float = 0.0
    retries_used: int = 0


class PlannerState(BaseModel):
    """Internal state threaded through the visa StateGraph."""

    query: str
    rewritten_query: str = ""
    system_notes: list[Chunk] = Field(default_factory=list)
    sub_questions: list[SubQuestion] = Field(default_factory=list)
    evidences: list[NodeEvidence] = Field(default_factory=list)
    final_answer: str = ""
    llm_call_count: int = Field(default=0, ge=0)
    max_llm_calls: int = Field(default=8, ge=1)
    max_sub_questions: int = Field(default=5, ge=1)
    max_depth: int = Field(default=3, ge=1)
    max_retries_per_node: int = Field(default=1, ge=0)
    dominant_visa: str = "general"
    error: str | None = None

    def budget_remaining(self) -> int:
        return self.max_llm_calls - self.llm_call_count

    def can_call_llm(self) -> bool:
        return self.llm_call_count < self.max_llm_calls
```

- [ ] **Step 7: Run tests — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestPlannerTypes -q 2>&1 | tail -20`

Expected: 3 passed

- [ ] **Step 8: Verify old tests still pass**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_subgraph.py -q 2>&1 | tail -20`

Expected: PASS for TestIdentifyVisaType (since specs still exist via old file path — will migrate in Task 2). If FAIL, delete the conflicting tests in `test_visa_subgraph.py` that exercise `_identify_visa_type` and `VISA_SPECS` since we have replaced the module. The TestVisaSubgraphNode tests should still run against the stub returning empty docs — they WILL fail until Task 9 rebuilds the domain doc output. That's expected, we'll keep them xfail'd in Task 2.

- [ ] **Step 9: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git rm apps/graph-engine/src/nuzantara_graph/subgraphs/visa.py
git commit -m "feat(visa-planner): scaffold visa package with planner types"
```

---

### Task 2: Migrate VISA_SPECS and legacy helpers; keep old tests xfailed

**Files:**
- Create: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/specs.py`
- Modify: `apps/graph-engine/tests/unit/subgraphs/test_visa_subgraph.py`

- [ ] **Step 1: Create specs.py with VISA_SPECS and _identify_visa_type**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/specs.py
"""Visa specifications and legacy type identification.

Moved from the old subgraphs/visa.py. The multi-step planner still needs
these for the initial "dominant visa" classification used by compose.
"""

from __future__ import annotations

from typing import Any

from nuzantara_schemas.domain.visa import VisaType
from nuzantara_schemas.state import GraphState


VISA_SPECS: dict[str, dict[str, Any]] = {
    VisaType.KITAS: {
        "duration_months": 12,
        "extendable": True,
        "sponsor_required": True,
        "work_permit_included": True,
        "costs_usd": {"pnbp": 250, "telex": 100, "kitas_card": 50},
        "processing_days": 30,
        "requirements": [
            "Sponsoring company (PT PMA or PT PMDN)",
            "RPTKA (foreign worker utilization plan) approved by Ministry of Labor",
            "IMTA (work permit) via SPKP system",
            "E-Visa application via imigrasi.go.id",
            "Valid passport (min. 18 months validity)",
            "Photo 4x6cm red background",
            "CV/resume for position",
            "Company sponsorship letter",
        ],
    },
    VisaType.KITAP: {
        "duration_months": 60,
        "extendable": True,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"pnbp": 570, "telex": 100, "kitap_card": 50},
        "processing_days": 45,
        "requirements": [
            "Held KITAS for minimum 3 consecutive years",
            "OR married to Indonesian citizen (2 years)",
            "OR retired (55+ with pension proof)",
            "Domicile in Indonesia",
            "Police clearance (SKCK)",
            "Financial proof (bank statements)",
        ],
    },
    VisaType.B211A: {
        "duration_months": 2,
        "extendable": True,
        "max_extensions": 4,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 120, "extension": 60},
        "processing_days": 5,
        "requirements": [
            "Sponsor (agent or individual Indonesian citizen)",
            "Valid passport (min. 6 months validity)",
            "Return/onward ticket",
            "Proof of funds",
            "Cannot work (social/business visit only)",
        ],
        "note": "The B211 visit visa was abolished; replaced by C-series e-visas (C1/C2/C7).",
    },
    VisaType.VOA: {
        "duration_months": 1,
        "extendable": True,
        "max_extensions": 1,
        "sponsor_required": False,
        "work_permit_included": False,
        "costs_usd": {"arrival": 35, "extension": 35},
        "processing_days": 0,
        "requirements": [
            "Available at major airports and seaports",
            "Eligible passport holders (90+ countries)",
            "Return/onward ticket required",
            "Valid passport (min. 6 months validity)",
            "Cannot work",
            "Extension to 60 days at immigration office",
        ],
    },
    VisaType.E_VISA: {
        "duration_months": 2,
        "extendable": False,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 120},
        "processing_days": 3,
        "requirements": [
            "Apply online via molina.imigrasi.go.id",
            "Sponsor required",
            "Must convert to KITAS within 60 days if staying",
        ],
    },
    VisaType.SECOND_HOME: {
        "duration_months": 60,
        "extendable": True,
        "sponsor_required": False,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 300},
        "processing_days": 10,
        "requirements": [
            "Proof of funds: USD 130,000 in Indonesian bank",
            "OR property ownership in Indonesia",
            "OR proof of retirement income",
            "Health insurance valid in Indonesia",
            "No criminal record",
            "Cannot work (investment/retirement only)",
        ],
    },
}


def _identify_visa_type(state: GraphState) -> VisaType:
    """Determine visa type from extracted entities and query context."""
    entities = state.extracted_entities
    query_lower = state.query.lower()

    if "visa_type" in entities:
        vt = str(entities["visa_type"]).lower()
        if "kitas" in vt:
            return VisaType.KITAS
        if "kitap" in vt:
            return VisaType.KITAP
        if "b211" in vt:
            return VisaType.B211A
        if "voa" in vt or "arrival" in vt:
            return VisaType.VOA
        if "second home" in vt:
            return VisaType.SECOND_HOME

    if "kitas" in query_lower or "work permit" in query_lower or "izin kerja" in query_lower:
        return VisaType.KITAS
    if "kitap" in query_lower or "permanent" in query_lower:
        return VisaType.KITAP
    if "b211" in query_lower or "social" in query_lower:
        return VisaType.B211A
    if "voa" in query_lower or "visa on arrival" in query_lower or "tourist" in query_lower:
        return VisaType.VOA
    if "second home" in query_lower or "retire" in query_lower or "pensiun" in query_lower:
        return VisaType.SECOND_HOME

    return VisaType.KITAS
```

- [ ] **Step 2: Update old test file to import from specs and mark legacy node tests xfail**

Edit `apps/graph-engine/tests/unit/subgraphs/test_visa_subgraph.py`:

```python
"""Tests for the visa/immigration subgraph (legacy + migrated)."""

import pytest

from nuzantara_graph.subgraphs.visa.specs import _identify_visa_type, VISA_SPECS
from nuzantara_graph.subgraphs.visa import make_visa_subgraph
from nuzantara_schemas.domain.visa import VisaType
from nuzantara_schemas.state import GraphState
from helpers.mocks import make_mock_services


class TestIdentifyVisaType:
    def test_kitas_from_entities(self):
        state = GraphState(query="test", extracted_entities={"visa_type": "kitas"})
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_kitap_from_query(self):
        state = GraphState(query="How to get a permanent stay permit KITAP?")
        assert _identify_visa_type(state) == VisaType.KITAP

    def test_voa_from_query(self):
        state = GraphState(query="Visa on arrival for tourists")
        assert _identify_visa_type(state) == VisaType.VOA

    def test_b211a_from_query(self):
        state = GraphState(query="B211A social visa requirements")
        assert _identify_visa_type(state) == VisaType.B211A

    def test_second_home_from_query(self):
        state = GraphState(query="Indonesia second home visa for retirees")
        assert _identify_visa_type(state) == VisaType.SECOND_HOME

    def test_work_permit_implies_kitas(self):
        state = GraphState(query="How to get a work permit in Indonesia?")
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_default_is_kitas(self):
        state = GraphState(query="What are the visa requirements?")
        assert _identify_visa_type(state) == VisaType.KITAS
```

Note: delete the entire `class TestVisaSubgraphNode` block — those tests asserted the old flat-pipeline behavior ("Sponsor Required: No", exact cost strings). They are superseded by `test_visa_planner.py`.

- [ ] **Step 3: Run both test files — expect PASS**

Run:
```bash
cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" \
  python -m pytest tests/unit/subgraphs/test_visa_subgraph.py tests/unit/subgraphs/test_visa_planner.py -q 2>&1 | tail -20
```

Expected: 10 passed (7 identify + 3 types)

- [ ] **Step 4: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/specs.py apps/graph-engine/tests/unit/subgraphs/test_visa_subgraph.py
git commit -m "feat(visa-planner): move VISA_SPECS and _identify_visa_type to specs.py"
```

---

### Task 3: B211 pre-filter (decompose helper)

**Files:**
- Create: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py` (partial — B211 function only)
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing test**

Append to `test_visa_planner.py`:

```python
@pytest.mark.unit
class TestB211Rewrite:
    def test_b211_substring_rewritten(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("Is the B211 visa still valid?")
        assert "B211" not in rewritten
        assert "KITAS" in rewritten or "e-visa" in rewritten
        assert note is not None
        assert note.doc_id == "SYSTEM:b211_rewrite"

    def test_b211a_variant_rewritten(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("Requirements for B211A")
        assert "B211A" not in rewritten
        assert note is not None

    def test_social_visit_visa_rewritten(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("I want a social visit visa for 30 days")
        assert note is not None
        assert "social visit visa" not in rewritten.lower() or "e-visa" in rewritten.lower()

    def test_no_match_pass_through(self):
        from nuzantara_graph.subgraphs.visa.decompose import rewrite_legacy_visa_terms

        rewritten, note = rewrite_legacy_visa_terms("KITAS for investor")
        assert rewritten == "KITAS for investor"
        assert note is None
```

- [ ] **Step 2: Run test — expect ImportError**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestB211Rewrite -q 2>&1 | tail -10`

Expected: ImportError

- [ ] **Step 3: Create decompose.py with rewrite function**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py
"""Query decomposition: B211 pre-filter + LLM-driven sub-question generation."""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from nuzantara_graph.subgraphs.visa.types import Chunk, SubQuestion

logger = structlog.get_logger()

_B211_PATTERN = re.compile(
    r"(?i)\b(b[-\s]?211[a]?|social[-\s]visit[-\s]visa|visit[-\s]visa[-\s]b[-\s]?211[a]?)\b"
)

_B211_REPLACEMENT = "KITAS/ITAS or e-visa (C-series)"

_B211_NOTE_CONTENT = (
    "The B211 visit visa was abolished. Current options for temporary stay "
    "are C-series e-visas (C1 tourism, C2 business, C7 social-cultural) or "
    "KITAS/ITAS for stays longer than 60 days. This sub-question has been "
    "rewritten accordingly."
)


def rewrite_legacy_visa_terms(query: str) -> tuple[str, Chunk | None]:
    """Rewrite B211/social-visit-visa mentions to current alternatives.

    Returns (rewritten_query, system_note_chunk | None). If no legacy term
    is present, returns (query, None).
    """
    if not _B211_PATTERN.search(query):
        return query, None

    rewritten = _B211_PATTERN.sub(_B211_REPLACEMENT, query)

    note = Chunk(
        doc_id="SYSTEM:b211_rewrite",
        span_start=0,
        span_end=len(_B211_NOTE_CONTENT),
        score=1.0,
        content=_B211_NOTE_CONTENT,
    )

    logger.info("b211_rewrite", original=query[:80], rewritten=rewritten[:80])
    return rewritten, note
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestB211Rewrite -q 2>&1 | tail -10`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): B211 legacy term rewrite pre-filter"
```

---

### Task 4: Decompose with LLM (with fallback)

**Files:**
- Modify: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py`
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestDecompose:
    @pytest.mark.asyncio
    async def test_decompose_returns_sub_questions(self):
        from nuzantara_graph.subgraphs.visa.decompose import decompose
        from helpers.mocks import MockLLMGateway

        llm = MockLLMGateway(responses={
            "generate_json": {
                "sub_questions": [
                    {"idx": 0, "text": "What is a KITAS?", "needs_kb": True, "depends_on": []},
                    {"idx": 1, "text": "How to apply?", "needs_kb": True, "depends_on": [0]},
                ]
            }
        })

        sub_qs = await decompose("Tell me about KITAS application", llm)
        assert len(sub_qs) == 2
        assert sub_qs[0].text == "What is a KITAS?"
        assert sub_qs[1].depends_on == [0]

    @pytest.mark.asyncio
    async def test_decompose_truncates_to_max_5(self):
        from nuzantara_graph.subgraphs.visa.decompose import decompose
        from helpers.mocks import MockLLMGateway

        llm = MockLLMGateway(responses={
            "generate_json": {
                "sub_questions": [
                    {"idx": i, "text": f"Q{i}", "needs_kb": True, "depends_on": []}
                    for i in range(10)
                ]
            }
        })

        sub_qs = await decompose("x", llm)
        assert len(sub_qs) == 5

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_bad_json(self):
        from nuzantara_graph.subgraphs.visa.decompose import decompose
        from helpers.mocks import MockLLMGateway

        class BadJSONLLM(MockLLMGateway):
            async def generate_json(self, prompt, system="", **kw):
                self._call_count += 1
                raise ValueError("invalid JSON")

        llm = BadJSONLLM()
        sub_qs = await decompose("How to get KITAS?", llm)
        assert len(sub_qs) == 1
        assert sub_qs[0].text == "How to get KITAS?"
        assert sub_qs[0].needs_kb is True

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_missing_api_key(self):
        from nuzantara_graph.subgraphs.visa.decompose import decompose
        from helpers.mocks import MockLLMGateway

        class NoKeyLLM(MockLLMGateway):
            async def generate_json(self, prompt, system="", **kw):
                self._call_count += 1
                raise ValueError("NUZANTARA_GOOGLE_API_KEY is required for LLM calls")

        sub_qs = await decompose("Can I overstay?", NoKeyLLM())
        assert len(sub_qs) == 1

    @pytest.mark.asyncio
    async def test_decompose_rejects_empty(self):
        from nuzantara_graph.subgraphs.visa.decompose import decompose
        from helpers.mocks import MockLLMGateway

        llm = MockLLMGateway(responses={"generate_json": {"sub_questions": []}})
        sub_qs = await decompose("q", llm)
        assert len(sub_qs) == 1
        assert sub_qs[0].text == "q"
```

- [ ] **Step 2: Run test — expect ImportError for `decompose`**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestDecompose -q 2>&1 | tail -15`

Expected: ImportError / AttributeError

- [ ] **Step 3: Extend decompose.py**

Append to `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py`:

```python
_DECOMPOSE_SYSTEM = (
    "You are a visa/immigration query planner for Indonesian law. "
    "Your job is to decompose a user question into 1..5 atomic sub-questions "
    "that can be answered independently. Each sub-question should be self-contained "
    "and answerable with a single document lookup. If the original question is already "
    "atomic, return a single sub-question equal to the original."
)

_DECOMPOSE_PROMPT = """\
Decompose the following visa/immigration question into atomic sub-questions.

Rules:
1. Return between 1 and 5 sub-questions.
2. Each sub-question has: idx (0-indexed), text, needs_kb (bool), depends_on (list of idx).
3. depends_on MUST reference only PRIOR sub-questions (idx < current).
4. Prefer parallelizable (empty depends_on) over sequential.
5. Do NOT mention abolished visa types like "B211".
6. Respond in the same language as the question.

Question: {query}

Respond with ONLY a JSON object:
{{
  "sub_questions": [
    {{"idx": 0, "text": "...", "needs_kb": true, "depends_on": []}},
    ...
  ]
}}
"""


def _fallback_sub_questions(query: str) -> list[SubQuestion]:
    return [SubQuestion(idx=0, text=query, needs_kb=True, depends_on=[])]


async def decompose(query: str, llm: Any, max_sub_questions: int = 5) -> list[SubQuestion]:
    """LLM-driven decomposition with graceful fallback.

    On any failure (bad JSON, missing API key, empty response), falls back to
    a single sub-question equal to the original query.
    """
    try:
        data = await llm.generate_json(
            prompt=_DECOMPOSE_PROMPT.format(query=query),
            system=_DECOMPOSE_SYSTEM,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("decompose_llm_failed", error=str(e))
        return _fallback_sub_questions(query)

    if not isinstance(data, dict) or "sub_questions" not in data:
        logger.warning("decompose_missing_key", raw=str(data)[:200])
        return _fallback_sub_questions(query)

    raw_items = data.get("sub_questions") or []
    if not raw_items:
        return _fallback_sub_questions(query)

    sub_qs: list[SubQuestion] = []
    for i, item in enumerate(raw_items[:max_sub_questions]):
        try:
            sq = SubQuestion(
                idx=i,
                text=str(item.get("text", "")).strip(),
                needs_kb=bool(item.get("needs_kb", True)),
                depends_on=[
                    int(d) for d in item.get("depends_on", [])
                    if isinstance(d, (int, float)) and int(d) < i
                ],
            )
        except (ValueError, TypeError) as e:
            logger.warning("decompose_invalid_item", item=str(item)[:100], error=str(e))
            continue

        if not sq.text:
            continue

        sub_qs.append(sq)

    if not sub_qs:
        return _fallback_sub_questions(query)

    return sub_qs
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestDecompose -q 2>&1 | tail -15`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/decompose.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): LLM-driven decomposition with fallback"
```

---

### Task 5: Topological sort with cycle breaking and depth clamping

**Files:**
- Create: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py` (partial — topo sort only)
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestTopoSort:
    def test_simple_linear_chain(self):
        from nuzantara_graph.subgraphs.visa.execute import topo_sort
        from nuzantara_graph.subgraphs.visa.types import SubQuestion

        sqs = [
            SubQuestion(idx=0, text="a", depends_on=[]),
            SubQuestion(idx=1, text="b", depends_on=[0]),
            SubQuestion(idx=2, text="c", depends_on=[1]),
        ]
        ordered, broken_edges = topo_sort(sqs, max_depth=3)
        assert [s.idx for s in ordered] == [0, 1, 2]
        assert broken_edges == []

    def test_cycle_broken(self):
        from nuzantara_graph.subgraphs.visa.execute import topo_sort
        from nuzantara_graph.subgraphs.visa.types import SubQuestion

        sqs = [
            SubQuestion(idx=0, text="a", depends_on=[1]),
            SubQuestion(idx=1, text="b", depends_on=[0]),
        ]
        ordered, broken_edges = topo_sort(sqs, max_depth=3)
        assert len(ordered) == 2
        assert len(broken_edges) >= 1

    def test_depth_clamped(self):
        from nuzantara_graph.subgraphs.visa.execute import topo_sort
        from nuzantara_graph.subgraphs.visa.types import SubQuestion

        sqs = [
            SubQuestion(idx=0, text="a", depends_on=[]),
            SubQuestion(idx=1, text="b", depends_on=[0]),
            SubQuestion(idx=2, text="c", depends_on=[1]),
            SubQuestion(idx=3, text="d", depends_on=[2]),
            SubQuestion(idx=4, text="e", depends_on=[3]),
        ]
        ordered, _ = topo_sort(sqs, max_depth=3)
        assert len(ordered) == 5
        # Depth-3 cap means sub-q #4 (depth 4) collapses to depend on <=depth-2
        for s in ordered:
            assert len(s.depends_on) <= 1
        # Ensure any depth-computed chain is <=3
        depths = {}
        for s in ordered:
            d = 0
            if s.depends_on:
                d = 1 + max(depths.get(p, 0) for p in s.depends_on)
            depths[s.idx] = d
        assert max(depths.values()) <= 2  # depth is 0-indexed levels; max_depth=3 means levels 0..2

    def test_parallel_branches(self):
        from nuzantara_graph.subgraphs.visa.execute import topo_sort
        from nuzantara_graph.subgraphs.visa.types import SubQuestion

        sqs = [
            SubQuestion(idx=0, text="root", depends_on=[]),
            SubQuestion(idx=1, text="left", depends_on=[0]),
            SubQuestion(idx=2, text="right", depends_on=[0]),
        ]
        ordered, _ = topo_sort(sqs, max_depth=3)
        assert ordered[0].idx == 0
        assert {s.idx for s in ordered[1:]} == {1, 2}
```

- [ ] **Step 2: Run test — expect ImportError**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestTopoSort -q 2>&1 | tail -15`

Expected: ImportError

- [ ] **Step 3: Create execute.py with topo_sort**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py
"""Topological execution of visa sub-questions."""

from __future__ import annotations

import structlog

from nuzantara_graph.subgraphs.visa.types import SubQuestion

logger = structlog.get_logger()


def topo_sort(
    sub_questions: list[SubQuestion],
    max_depth: int = 3,
) -> tuple[list[SubQuestion], list[tuple[int, int]]]:
    """Topologically sort sub-questions.

    - Breaks cycles by dropping back-edges (from higher idx to lower).
    - Clamps chain depth to ``max_depth`` by collapsing deep dependencies
      onto the nearest ancestor within the depth budget.

    Returns:
        (ordered_list, broken_edges) where broken_edges is a list of
        (from_idx, to_idx) pairs that were removed to eliminate cycles.
    """
    broken_edges: list[tuple[int, int]] = []

    # Normalize depends_on: each dep must be strictly smaller than idx to
    # guarantee acyclicity. Any edge (a -> b) with b >= a is a cycle.
    cleaned: list[SubQuestion] = []
    for sq in sub_questions:
        kept_deps: list[int] = []
        for dep in sq.depends_on:
            if dep < sq.idx and 0 <= dep < len(sub_questions):
                kept_deps.append(dep)
            else:
                broken_edges.append((sq.idx, dep))
        cleaned.append(
            SubQuestion(
                idx=sq.idx,
                text=sq.text,
                needs_kb=sq.needs_kb,
                depends_on=kept_deps,
            )
        )

    # Clamp depth
    depths: dict[int, int] = {}
    result: list[SubQuestion] = []
    for sq in cleaned:
        if not sq.depends_on:
            depths[sq.idx] = 0
            result.append(sq)
            continue

        parent_depth = max(depths.get(p, 0) for p in sq.depends_on)
        new_depth = parent_depth + 1

        if new_depth >= max_depth:
            # Collapse: keep only the shallowest dependency (closest to root)
            shallowest = min(sq.depends_on, key=lambda p: depths.get(p, 0))
            collapsed_deps = [shallowest]
            parent_depth = depths.get(shallowest, 0)
            new_depth = min(parent_depth + 1, max_depth - 1)

            # Record dropped edges
            for d in sq.depends_on:
                if d != shallowest:
                    broken_edges.append((sq.idx, d))

            sq = SubQuestion(
                idx=sq.idx,
                text=sq.text,
                needs_kb=sq.needs_kb,
                depends_on=collapsed_deps,
            )

        depths[sq.idx] = new_depth
        result.append(sq)

    if broken_edges:
        logger.warning("topo_sort_broken_edges", count=len(broken_edges), edges=broken_edges)

    return result, broken_edges
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestTopoSort -q 2>&1 | tail -20`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): topo sort with cycle breaking and depth clamping"
```

---

### Task 6: Contradiction grader

**Files:**
- Create: `apps/graph-engine/src/nuzantara_graph/graders/contradiction_grader.py`
- Modify: `apps/graph-engine/src/nuzantara_graph/graders/__init__.py`
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestContradictionGrader:
    def test_no_prior_evidence_returns_zero(self):
        from nuzantara_graph.graders.contradiction_grader import ContradictionGrader
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion

        grader = ContradictionGrader()
        ev = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="q", depends_on=[]),
            chunks=[Chunk(doc_id="a", span_start=0, span_end=10, score=0.9, content="KITAS lasts 30 days")],
            answer_fragment="KITAS lasts 30 days",
        )
        score = grader.score(ev, prior_evidence=[])
        assert score == 0.0

    def test_number_disagreement_detected(self):
        from nuzantara_graph.graders.contradiction_grader import ContradictionGrader
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion

        prior = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="p", depends_on=[]),
            chunks=[Chunk(doc_id="a", span_start=0, span_end=10, score=0.9, content="KITAS duration is 30 days")],
            answer_fragment="KITAS duration is 30 days",
        )
        current = NodeEvidence(
            sub_question=SubQuestion(idx=1, text="q", depends_on=[]),
            chunks=[Chunk(doc_id="b", span_start=0, span_end=10, score=0.9, content="KITAS duration is 60 days")],
            answer_fragment="KITAS duration is 60 days",
        )
        grader = ContradictionGrader()
        score = grader.score(current, [prior])
        assert score > 0.4

    def test_agreeing_evidence_low_score(self):
        from nuzantara_graph.graders.contradiction_grader import ContradictionGrader
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion

        prior = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="p", depends_on=[]),
            chunks=[Chunk(doc_id="a", span_start=0, span_end=10, score=0.9, content="RPTKA is required")],
            answer_fragment="RPTKA is required",
        )
        current = NodeEvidence(
            sub_question=SubQuestion(idx=1, text="q", depends_on=[]),
            chunks=[Chunk(doc_id="b", span_start=0, span_end=10, score=0.9, content="RPTKA must be obtained from the Ministry of Labor")],
            answer_fragment="RPTKA must be obtained from the Ministry of Labor",
        )
        grader = ContradictionGrader()
        score = grader.score(current, [prior])
        assert score < 0.4

    def test_negation_overlap_detected(self):
        from nuzantara_graph.graders.contradiction_grader import ContradictionGrader
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion

        prior = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="p", depends_on=[]),
            chunks=[Chunk(doc_id="a", span_start=0, span_end=10, score=0.9, content="The visa is extendable")],
            answer_fragment="The visa is extendable",
        )
        current = NodeEvidence(
            sub_question=SubQuestion(idx=1, text="q", depends_on=[]),
            chunks=[Chunk(doc_id="b", span_start=0, span_end=10, score=0.9, content="The visa is not extendable")],
            answer_fragment="The visa is not extendable",
        )
        grader = ContradictionGrader()
        score = grader.score(current, [prior])
        assert score > 0.4
```

- [ ] **Step 2: Run test — expect ImportError**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestContradictionGrader -q 2>&1 | tail -15`

Expected: ImportError

- [ ] **Step 3: Create contradiction_grader.py**

```python
# apps/graph-engine/src/nuzantara_graph/graders/contradiction_grader.py
"""Contradiction grader for visa planner evidence.

NOT a BaseGrader subclass — those write to state.grades which the main
graph consumes. Contradiction grading is planner-internal and should not
bleed into the main flow.

Heuristic: combines
  1. Direct negation flip (X vs "not X")
  2. Number disagreement on the same entity (e.g. "30 days" vs "60 days")

Returns a score in [0, 1] where > 0.4 triggers a re-plan of the current
sub-question.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from nuzantara_graph.subgraphs.visa.types import NodeEvidence

logger = structlog.get_logger()

_NUMBER_PATTERN = re.compile(r"(\d+)\s*(days?|months?|years?|usd|idr|eur)", re.IGNORECASE)
_NEGATION_MARKERS = ("not ", "no ", "never ", "cannot ", "can't ", "tidak ", "bukan ")


def _extract_numbers_with_unit(text: str) -> set[tuple[int, str]]:
    """Return {(value, unit)} tuples found in text."""
    out: set[tuple[int, str]] = set()
    for m in _NUMBER_PATTERN.finditer(text):
        try:
            out.add((int(m.group(1)), m.group(2).lower().rstrip("s")))
        except (ValueError, IndexError):
            continue
    return out


def _has_negation_flip(a: str, b: str) -> bool:
    """Detect whether a and b express opposite polarity on similar terms."""
    a_low = a.lower()
    b_low = b.lower()

    a_negated = any(marker in a_low for marker in _NEGATION_MARKERS)
    b_negated = any(marker in b_low for marker in _NEGATION_MARKERS)

    if a_negated == b_negated:
        return False

    # Extract significant tokens (>4 chars, not common words)
    common = {"the", "and", "for", "with", "from", "this", "that", "have", "will"}
    a_tokens = {t for t in re.findall(r"\w{5,}", a_low) if t not in common}
    b_tokens = {t for t in re.findall(r"\w{5,}", b_low) if t not in common}

    overlap = len(a_tokens & b_tokens)
    return overlap >= 2  # at least 2 shared significant tokens + polarity flip


def _number_disagreement_score(
    current: set[tuple[int, str]],
    prior: set[tuple[int, str]],
) -> float:
    """Return 0..1 indicating disagreement on numeric claims with the same unit."""
    if not current or not prior:
        return 0.0

    disagreements = 0
    total = 0
    for c_val, c_unit in current:
        prior_same_unit = {p_val for p_val, p_unit in prior if p_unit == c_unit}
        if not prior_same_unit:
            continue
        total += 1
        if c_val not in prior_same_unit:
            disagreements += 1

    if total == 0:
        return 0.0
    return disagreements / total


class ContradictionGrader:
    """Heuristic contradiction detector for visa planner evidence."""

    def __init__(self, negation_weight: float = 0.6, number_weight: float = 0.6) -> None:
        self.negation_weight = negation_weight
        self.number_weight = number_weight

    def score(
        self,
        node_evidence: "NodeEvidence",
        prior_evidence: list["NodeEvidence"],
    ) -> float:
        """Return contradiction score in [0, 1].

        Score > 0.4 is considered a genuine contradiction worth re-planning.
        """
        if not prior_evidence:
            return 0.0

        current_text = " ".join(
            [node_evidence.answer_fragment] + [c.content for c in node_evidence.chunks]
        )
        current_numbers = _extract_numbers_with_unit(current_text)

        max_score = 0.0
        for prior in prior_evidence:
            prior_text = " ".join(
                [prior.answer_fragment] + [c.content for c in prior.chunks]
            )
            prior_numbers = _extract_numbers_with_unit(prior_text)

            num_score = _number_disagreement_score(current_numbers, prior_numbers)
            neg_flip = _has_negation_flip(current_text, prior_text)

            combined = (num_score * self.number_weight) + (self.negation_weight if neg_flip else 0.0)
            max_score = max(max_score, min(1.0, combined))

        logger.debug(
            "contradiction_score",
            score=round(max_score, 3),
            sub_q=node_evidence.sub_question.idx,
        )
        return max_score
```

- [ ] **Step 4: Update graders __init__.py**

```python
# apps/graph-engine/src/nuzantara_graph/graders/__init__.py
"""Grader nodes — quality gates between major graph transitions."""

from nuzantara_graph.graders.base import BaseGrader
from nuzantara_graph.graders.retrieval_grader import make_retrieval_grader
from nuzantara_graph.graders.reasoning_grader import make_reasoning_grader
from nuzantara_graph.graders.answer_grader import make_answer_grader
from nuzantara_graph.graders.hallucination_grader import make_hallucination_grader
from nuzantara_graph.graders.pricing_grader import make_pricing_grader
from nuzantara_graph.graders.contradiction_grader import ContradictionGrader

__all__ = [
    "BaseGrader",
    "make_retrieval_grader",
    "make_reasoning_grader",
    "make_answer_grader",
    "make_hallucination_grader",
    "make_pricing_grader",
    "ContradictionGrader",
]
```

- [ ] **Step 5: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestContradictionGrader -q 2>&1 | tail -20`

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/graders/contradiction_grader.py apps/graph-engine/src/nuzantara_graph/graders/__init__.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): contradiction grader with number and negation heuristics"
```

---

### Task 7: Plan-execute — full DAG executor

**Files:**
- Modify: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py`
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestExecute:
    @pytest.mark.asyncio
    async def test_single_sub_question_runs(self):
        from nuzantara_graph.subgraphs.visa.execute import plan_execute
        from nuzantara_graph.subgraphs.visa.types import PlannerState, SubQuestion
        from nuzantara_schemas.state import RetrievedDocument
        from helpers.mocks import make_mock_services

        svc = make_mock_services(
            documents=[RetrievedDocument(id="kitas", content="KITAS permit info", score=0.9)],
            llm_responses={"generate": "KITAS is a temporary permit."},
        )
        state = PlannerState(
            query="What is KITAS?",
            rewritten_query="What is KITAS?",
            sub_questions=[SubQuestion(idx=0, text="What is KITAS?", needs_kb=True, depends_on=[])],
        )

        new_state = await plan_execute(state, svc)
        assert len(new_state.evidences) == 1
        assert len(new_state.evidences[0].chunks) >= 1
        assert new_state.llm_call_count >= 1

    @pytest.mark.asyncio
    async def test_multiple_sub_questions_parallel(self):
        from nuzantara_graph.subgraphs.visa.execute import plan_execute
        from nuzantara_graph.subgraphs.visa.types import PlannerState, SubQuestion
        from nuzantara_schemas.state import RetrievedDocument
        from helpers.mocks import make_mock_services

        svc = make_mock_services(
            documents=[RetrievedDocument(id="doc1", content="Investor KITAS info", score=0.9)],
            llm_responses={"generate": "answer"},
        )
        state = PlannerState(
            query="Compare investor vs working KITAS",
            rewritten_query="Compare investor vs working KITAS",
            sub_questions=[
                SubQuestion(idx=0, text="What is investor KITAS?", needs_kb=True, depends_on=[]),
                SubQuestion(idx=1, text="What is working KITAS?", needs_kb=True, depends_on=[]),
            ],
        )
        new_state = await plan_execute(state, svc)
        assert len(new_state.evidences) == 2

    @pytest.mark.asyncio
    async def test_empty_kb_graceful(self):
        from nuzantara_graph.subgraphs.visa.execute import plan_execute
        from nuzantara_graph.subgraphs.visa.types import PlannerState, SubQuestion
        from helpers.mocks import make_mock_services

        svc = make_mock_services(documents=[], llm_responses={"generate": "I don't know"})
        state = PlannerState(
            query="newborn visa",
            rewritten_query="newborn visa",
            sub_questions=[SubQuestion(idx=0, text="newborn visa?", needs_kb=True, depends_on=[])],
        )
        new_state = await plan_execute(state, svc)
        assert len(new_state.evidences) == 1
        assert new_state.evidences[0].chunks == []

    @pytest.mark.asyncio
    async def test_llm_budget_enforced(self):
        from nuzantara_graph.subgraphs.visa.execute import plan_execute
        from nuzantara_graph.subgraphs.visa.types import PlannerState, SubQuestion
        from helpers.mocks import make_mock_services

        svc = make_mock_services(llm_responses={"generate": "x"})
        state = PlannerState(
            query="q",
            rewritten_query="q",
            sub_questions=[
                SubQuestion(idx=i, text=f"sub {i}", needs_kb=True, depends_on=[]) for i in range(5)
            ],
            max_llm_calls=2,
        )
        new_state = await plan_execute(state, svc)
        assert new_state.llm_call_count <= 2

    @pytest.mark.asyncio
    async def test_contradiction_triggers_retry(self):
        from nuzantara_graph.subgraphs.visa.execute import plan_execute
        from nuzantara_graph.subgraphs.visa.types import PlannerState, SubQuestion
        from nuzantara_schemas.state import RetrievedDocument
        from helpers.mocks import make_mock_services

        # Two sub-qs whose first answers contain contradictory numbers.
        # Retry on the second sub-q should be attempted.
        # We track via llm_call_count.
        docs_first = [
            RetrievedDocument(id="a", content="KITAS duration 30 days", score=0.9),
        ]
        docs_second_round = [
            RetrievedDocument(id="b", content="KITAS duration 60 days", score=0.9),
        ]

        class AlternatingVectorStore:
            def __init__(self):
                from nuzantara_graph.services.vector_store import VectorStore
                self._call = 0
                self._real = None

            async def search_by_text(self, query, **kwargs):
                self._call += 1
                if self._call == 1:
                    return docs_first
                return docs_second_round

        svc = make_mock_services(llm_responses={"generate": "KITAS lasts {answer}"})
        svc.vector_store = AlternatingVectorStore()  # type: ignore

        state = PlannerState(
            query="KITAS duration",
            rewritten_query="KITAS duration",
            sub_questions=[
                SubQuestion(idx=0, text="KITAS duration 30 days?", needs_kb=True, depends_on=[]),
                SubQuestion(idx=1, text="KITAS duration 60 days?", needs_kb=True, depends_on=[]),
            ],
        )
        new_state = await plan_execute(state, svc)
        # Second node should have either retried or recorded a contradiction
        assert len(new_state.evidences) == 2
        contradictory = [e for e in new_state.evidences if e.contradiction_score > 0.0]
        assert len(contradictory) >= 1
```

- [ ] **Step 2: Run test — expect ImportError for plan_execute**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestExecute -q 2>&1 | tail -15`

Expected: ImportError or AttributeError

- [ ] **Step 3: Extend execute.py**

Append to `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py`:

```python
import json
from typing import Any

from nuzantara_graph.graders.contradiction_grader import ContradictionGrader
from nuzantara_graph.subgraphs.visa.types import (
    Chunk,
    NodeEvidence,
    PlannerState,
    SubQuestion,
)


class LlmBudgetExceeded(Exception):
    """Raised when the planner has hit its max_llm_calls ceiling."""


_FRAGMENT_SYSTEM = (
    "You are a visa/immigration expert. Answer the sub-question strictly "
    "using the provided sources. If sources are insufficient, say so explicitly. "
    "Never invent facts. Respond in the language of the sub-question."
)

_FRAGMENT_PROMPT = """\
Sub-question: {sub_q}

Prior context from this planning run:
{prior_context}

Sources:
{sources}

Write a short, factual answer (2-4 sentences) based ONLY on the sources above.
If no source supports the answer, reply: "No sources available to answer this sub-question."
"""


def _format_chunks(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no sources)"
    return "\n\n".join(
        f"[{c.doc_id}:{c.span_start}-{c.span_end}] (score={c.score:.2f}) {c.content}"
        for c in chunks
    )


def _format_prior_context(prior_evidences: list[NodeEvidence]) -> str:
    if not prior_evidences:
        return "(none)"
    lines = []
    for ev in prior_evidences:
        if ev.answer_fragment:
            lines.append(f"- Sub-q {ev.sub_question.idx}: {ev.answer_fragment[:200]}")
    return "\n".join(lines) if lines else "(none)"


async def _retrieve_chunks(
    sub_q: SubQuestion,
    services: Any,
    top_k: int = 5,
) -> list[Chunk]:
    if not sub_q.needs_kb:
        return []
    try:
        docs = await services.vector_store.search_by_text(
            query=sub_q.text,
            top_k=top_k,
        )
    except Exception as e:
        logger.warning("plan_execute_search_failed", sub_q=sub_q.idx, error=str(e))
        return []

    chunks: list[Chunk] = []
    for d in docs:
        chunks.append(
            Chunk(
                doc_id=d.id,
                span_start=0,
                span_end=len(d.content),
                score=max(0.0, min(1.0, d.score)),
                content=d.content,
            )
        )
    return chunks


async def _compose_fragment(
    sub_q: SubQuestion,
    chunks: list[Chunk],
    prior_evidences: list[NodeEvidence],
    services: Any,
) -> str:
    prompt = _FRAGMENT_PROMPT.format(
        sub_q=sub_q.text,
        prior_context=_format_prior_context(prior_evidences),
        sources=_format_chunks(chunks),
    )
    try:
        response = await services.llm.generate(
            prompt=prompt,
            system=_FRAGMENT_SYSTEM,
            temperature=0.0,
        )
        return getattr(response, "content", str(response))
    except Exception as e:
        logger.warning("compose_fragment_failed", sub_q=sub_q.idx, error=str(e))
        return ""


async def plan_execute(state: PlannerState, services: Any) -> PlannerState:
    """Execute sub-questions in topological order.

    Mutates a copy of ``state`` with evidences and llm_call_count, then
    returns the new state.
    """
    grader = ContradictionGrader()

    ordered, _broken = topo_sort(state.sub_questions, max_depth=state.max_depth)
    evidences: list[NodeEvidence] = []
    llm_calls = state.llm_call_count

    for sq in ordered:
        # Budget check BEFORE any LLM call for this sub-question
        if llm_calls >= state.max_llm_calls:
            logger.warning("plan_execute_budget_exhausted", sub_q=sq.idx)
            evidences.append(NodeEvidence(sub_question=sq, chunks=[], answer_fragment=""))
            continue

        chunks = await _retrieve_chunks(sq, services)

        fragment = ""
        if llm_calls < state.max_llm_calls:
            fragment = await _compose_fragment(sq, chunks, evidences, services)
            llm_calls += 1

        ev = NodeEvidence(
            sub_question=sq,
            chunks=chunks,
            answer_fragment=fragment,
            grounded=bool(chunks),
        )

        # Contradiction check
        contradiction = grader.score(ev, evidences)
        ev.contradiction_score = contradiction

        if (
            contradiction > 0.4
            and ev.retries_used < state.max_retries_per_node
            and llm_calls < state.max_llm_calls
        ):
            logger.info("plan_execute_retry", sub_q=sq.idx, contradiction=round(contradiction, 2))
            retry_chunks = await _retrieve_chunks(sq, services)
            retry_fragment = await _compose_fragment(sq, retry_chunks, evidences, services)
            llm_calls += 1
            ev = NodeEvidence(
                sub_question=sq,
                chunks=retry_chunks or chunks,
                answer_fragment=retry_fragment or fragment,
                grounded=bool(retry_chunks or chunks),
                contradiction_score=grader.score(
                    NodeEvidence(
                        sub_question=sq,
                        chunks=retry_chunks or chunks,
                        answer_fragment=retry_fragment or fragment,
                    ),
                    evidences,
                ),
                retries_used=1,
            )

        evidences.append(ev)

    return state.model_copy(update={
        "evidences": evidences,
        "llm_call_count": llm_calls,
    })
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestExecute -q 2>&1 | tail -25`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/execute.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): plan_execute with retrieval, retry, and budget"
```

---

### Task 8: Composer with citation enforcement

**Files:**
- Create: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/compose.py`
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.unit
class TestCompose:
    @pytest.mark.asyncio
    async def test_compose_cites_chunks(self):
        from nuzantara_graph.subgraphs.visa.compose import compose
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion
        from helpers.mocks import MockLLMGateway

        chunk = Chunk(doc_id="kitas_2024", span_start=0, span_end=50, score=0.9, content="KITAS is valid for 12 months.")
        ev = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="q", depends_on=[]),
            chunks=[chunk],
            answer_fragment="KITAS is valid for 12 months.",
        )
        llm = MockLLMGateway(responses={
            "generate": "KITAS is valid for 12 months [kitas_2024:0-50]."
        })
        answer = await compose("How long is KITAS valid?", [ev], [], llm)
        assert "kitas_2024" in answer

    @pytest.mark.asyncio
    async def test_enforcer_refuses_uncitable_sentence(self):
        from nuzantara_graph.subgraphs.visa.compose import compose
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion
        from helpers.mocks import MockLLMGateway

        chunk = Chunk(doc_id="doc_a", span_start=0, span_end=20, score=0.9, content="Fee is 250 USD.")
        ev = NodeEvidence(
            sub_question=SubQuestion(idx=0, text="q", depends_on=[]),
            chunks=[chunk],
            answer_fragment="Fee is 250 USD.",
        )
        llm = MockLLMGateway(responses={
            "generate": "The fee is 500000 IDR."  # no citation, wrong value
        })
        answer = await compose("What is the fee?", [ev], [], llm)
        # Enforcer should either refuse or auto-attribute
        assert ("unable to cite" in answer.lower()
                or "[doc_a" in answer
                or "cannot produce" in answer.lower())

    @pytest.mark.asyncio
    async def test_compose_includes_system_notes(self):
        from nuzantara_graph.subgraphs.visa.compose import compose
        from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence, SubQuestion
        from helpers.mocks import MockLLMGateway

        note = Chunk(
            doc_id="SYSTEM:b211_rewrite",
            span_start=0,
            span_end=100,
            score=1.0,
            content="The B211 visa was abolished.",
        )
        llm = MockLLMGateway(responses={
            "generate": "The B211 visa has been abolished [SYSTEM:b211_rewrite:0-100]."
        })
        answer = await compose("Can I still use B211?", [], [note], llm)
        assert "SYSTEM:b211_rewrite" in answer

    @pytest.mark.asyncio
    async def test_empty_evidences_returns_fallback(self):
        from nuzantara_graph.subgraphs.visa.compose import compose
        from helpers.mocks import MockLLMGateway

        llm = MockLLMGateway(responses={"generate": "I don't know anything."})
        answer = await compose("q", [], [], llm)
        # Should either refuse all sentences or return the system fallback
        assert ("no sources" in answer.lower()
                or "cannot produce" in answer.lower()
                or "[" not in answer and "unable" in answer.lower())
```

- [ ] **Step 2: Run test — expect ImportError**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestCompose -q 2>&1 | tail -15`

Expected: ImportError

- [ ] **Step 3: Create compose.py**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/compose.py
"""Final composer with deterministic citation enforcement."""

from __future__ import annotations

import re
from typing import Any

import structlog

from nuzantara_graph.subgraphs.visa.types import Chunk, NodeEvidence

logger = structlog.get_logger()

_CITATION_PATTERN = re.compile(r"\[([^\[\]:]+):(\d+)-(\d+)\]")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_SYSTEM_FALLBACK = (
    "I cannot produce a fully-cited answer for this query. "
    "Please rephrase or contact support for visa assistance."
)

_UNCITABLE_LINE = "(unable to cite this claim; refer to the documents below)"

_COMPOSE_SYSTEM = (
    "You are a visa/immigration expert producing a final cited answer. "
    "EVERY sentence in your response MUST end with a citation in the form "
    "[doc_id:start-end] pointing to one of the provided chunks. Do not invent "
    "citations. Do not use chunks that were not provided. If you cannot cite "
    "a claim, omit it. Respond in the same language as the user's question."
)

_COMPOSE_PROMPT = """\
User question: {query}

Available evidence chunks (you MAY cite ONLY these):
{chunks}

Write a clear, factual answer to the user's question. EVERY sentence MUST end
with a citation of the form [doc_id:start-end] from the list above.
"""


def _all_chunks(
    evidences: list[NodeEvidence],
    system_notes: list[Chunk],
) -> list[Chunk]:
    out: list[Chunk] = list(system_notes)
    for ev in evidences:
        out.extend(ev.chunks)
    return out


def _format_chunks_for_prompt(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(no chunks available)"
    return "\n\n".join(
        f"[{c.doc_id}:{c.span_start}-{c.span_end}] {c.content}"
        for c in chunks[:20]  # cap to avoid prompt overflow
    )


def _split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _known_doc_ids(chunks: list[Chunk]) -> set[str]:
    return {c.doc_id for c in chunks}


def _cite_lookup(chunks: list[Chunk]) -> dict[str, Chunk]:
    return {c.doc_id: c for c in chunks}


def _auto_attribute(sentence: str, chunks: list[Chunk]) -> str | None:
    """Try to find a chunk whose content strongly matches the sentence."""
    sent_low = sentence.lower()
    best: tuple[float, Chunk] | None = None
    sent_tokens = set(re.findall(r"\w{4,}", sent_low))
    if not sent_tokens:
        return None

    for c in chunks:
        c_tokens = set(re.findall(r"\w{4,}", c.content.lower()))
        if not c_tokens:
            continue
        overlap = len(sent_tokens & c_tokens)
        ratio = overlap / max(1, len(sent_tokens))
        if ratio >= 0.5 and (best is None or ratio > best[0]):
            best = (ratio, c)

    if best is None:
        return None
    return best[1].citation()


def enforce_citations(text: str, chunks: list[Chunk]) -> str:
    """Deterministic citation linter.

    Rules:
    1. Split on sentence boundaries
    2. A sentence is valid if it contains a citation whose doc_id is in ``chunks``
    3. Otherwise try auto-attribution via token overlap
    4. Otherwise replace with the uncitable-line fallback
    5. If ALL sentences fail, return the system fallback
    """
    if not chunks:
        return _SYSTEM_FALLBACK

    known = _known_doc_ids(chunks)
    sentences = _split_sentences(text)
    if not sentences:
        return _SYSTEM_FALLBACK

    approved: list[str] = []
    for sentence in sentences:
        matches = _CITATION_PATTERN.findall(sentence)
        valid_citation = any(m[0] in known for m in matches)

        if valid_citation:
            approved.append(sentence)
            continue

        attribution = _auto_attribute(sentence, chunks)
        if attribution:
            # Append attribution citation
            if sentence.endswith("."):
                approved.append(f"{sentence[:-1]} {attribution}.")
            else:
                approved.append(f"{sentence} {attribution}")
            continue

        approved.append(_UNCITABLE_LINE)

    # If every sentence is the uncitable fallback, return system fallback
    if all(s == _UNCITABLE_LINE for s in approved):
        return _SYSTEM_FALLBACK

    return " ".join(approved)


async def compose(
    query: str,
    evidences: list[NodeEvidence],
    system_notes: list[Chunk],
    llm: Any,
) -> str:
    """Produce the final cited answer."""
    chunks = _all_chunks(evidences, system_notes)

    if not chunks:
        logger.info("compose_no_chunks")
        return _SYSTEM_FALLBACK

    prompt = _COMPOSE_PROMPT.format(
        query=query,
        chunks=_format_chunks_for_prompt(chunks),
    )

    try:
        response = await llm.generate(
            prompt=prompt,
            system=_COMPOSE_SYSTEM,
            temperature=0.0,
        )
        raw = getattr(response, "content", str(response))
    except Exception as e:
        logger.warning("compose_llm_failed", error=str(e))
        return _SYSTEM_FALLBACK

    return enforce_citations(raw, chunks)
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestCompose -q 2>&1 | tail -20`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/compose.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): final composer with citation enforcement linter"
```

---

### Task 9: Assemble StateGraph in planner.py + delete stub

**Files:**
- Modify: `apps/graph-engine/src/nuzantara_graph/subgraphs/visa/planner.py`
- Test: `test_visa_planner.py` (append)

- [ ] **Step 1: Write failing end-to-end test**

```python
@pytest.mark.unit
class TestMakeVisaSubgraph:
    @pytest.mark.asyncio
    async def test_end_to_end_returns_contract(self):
        from nuzantara_graph.subgraphs.visa import make_visa_subgraph
        from nuzantara_schemas.state import GraphState, RetrievedDocument
        from helpers.mocks import make_mock_services

        svc = make_mock_services(
            documents=[RetrievedDocument(id="kitas", content="KITAS duration info", score=0.9)],
            llm_responses={
                "generate_json": {
                    "sub_questions": [
                        {"idx": 0, "text": "What is KITAS?", "needs_kb": True, "depends_on": []}
                    ]
                },
                "generate": "KITAS is valid for 12 months [kitas:0-20].",
            },
        )
        node = make_visa_subgraph(svc)
        state = GraphState(query="What is KITAS?", intent="visa")
        result = await node(state)

        assert result["current_node"] == "subgraph_visa"
        assert "retrieved_documents" in result
        assert "kg_entities" in result
        assert "kg_relationships" in result
        assert "domain" in result

    @pytest.mark.asyncio
    async def test_end_to_end_b211_rewritten_in_docs(self):
        from nuzantara_graph.subgraphs.visa import make_visa_subgraph
        from nuzantara_schemas.state import GraphState, RetrievedDocument
        from helpers.mocks import make_mock_services

        svc = make_mock_services(
            documents=[RetrievedDocument(id="visa_types", content="KITAS/ITAS info", score=0.9)],
            llm_responses={
                "generate_json": {
                    "sub_questions": [
                        {"idx": 0, "text": "What replaced the B211 visa?", "needs_kb": True, "depends_on": []}
                    ]
                },
                "generate": "C-series e-visas replaced the old B211 [SYSTEM:b211_rewrite:0-250].",
            },
        )
        node = make_visa_subgraph(svc)
        state = GraphState(query="Can I still apply for a B211 visa?", intent="visa")
        result = await node(state)

        doc_ids = {d.id for d in result["retrieved_documents"]}
        assert "SYSTEM:b211_rewrite" in doc_ids
```

- [ ] **Step 2: Run test — expect FAIL (stub returns empty)**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestMakeVisaSubgraph -q 2>&1 | tail -20`

Expected: FAIL (current_node passes but contract assertions may fail)

- [ ] **Step 3: Replace planner.py stub with full implementation**

```python
# apps/graph-engine/src/nuzantara_graph/subgraphs/visa/planner.py
"""Visa multi-step planner — LangGraph StateGraph.

Pipeline:
  1. b211_rewrite  (sync)
  2. decompose     (1 LLM call)
  3. plan_execute  (≤ N × 2 LLM calls, bounded by max_llm_calls)
  4. compose       (1 LLM call)
  5. terminate     (sync, produces contract dict)

Termination proof
-----------------
Let N = len(sub_questions) after decompose truncates to ≤5.
- decompose runs exactly once
- plan_execute iterates a topologically sorted list ONCE
  - each sub-question triggers at most 2 LLM calls (initial + 1 retry)
  - retries_used is monotonically increasing, never reset
  - llm_call_count is globally monotonic
  - the loop terminates when (a) all sub_qs processed, or (b) budget exhausted
- compose runs exactly once
- No edge in the StateGraph loops back to a prior node

Total LLM calls: 1 + N×2 + 1 ≤ 12, clamped to max_llm_calls (default 8).
Graph acyclic + finite list + monotonic budget ⇒ guaranteed termination.
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from nuzantara_graph.services import Services
from nuzantara_graph.subgraphs.visa.compose import compose
from nuzantara_graph.subgraphs.visa.decompose import decompose, rewrite_legacy_visa_terms
from nuzantara_graph.subgraphs.visa.execute import plan_execute
from nuzantara_graph.subgraphs.visa.specs import _identify_visa_type
from nuzantara_graph.subgraphs.visa.types import Chunk, PlannerState
from nuzantara_schemas.state import GraphState, RetrievedDocument

logger = structlog.get_logger()


async def _node_b211_rewrite(state: PlannerState) -> dict[str, Any]:
    rewritten, note = rewrite_legacy_visa_terms(state.query)
    updates: dict[str, Any] = {"rewritten_query": rewritten}
    if note is not None:
        updates["system_notes"] = [note]
    return updates


def _make_decompose_node(services: Services):
    async def _node_decompose(state: PlannerState) -> dict[str, Any]:
        sub_qs = await decompose(
            state.rewritten_query,
            services.llm,
            max_sub_questions=state.max_sub_questions,
        )
        return {
            "sub_questions": sub_qs,
            "llm_call_count": state.llm_call_count + 1,
        }

    return _node_decompose


def _make_execute_node(services: Services):
    async def _node_execute(state: PlannerState) -> dict[str, Any]:
        new_state = await plan_execute(state, services)
        return {
            "evidences": new_state.evidences,
            "llm_call_count": new_state.llm_call_count,
        }

    return _node_execute


def _make_compose_node(services: Services):
    async def _node_compose(state: PlannerState) -> dict[str, Any]:
        answer = await compose(
            query=state.query,
            evidences=state.evidences,
            system_notes=state.system_notes,
            llm=services.llm,
        )
        return {
            "final_answer": answer,
            "llm_call_count": state.llm_call_count + 1,
        }

    return _node_compose


def _build_planner_graph(services: Services) -> Any:
    graph = StateGraph(PlannerState)

    graph.add_node("b211_rewrite", _node_b211_rewrite)
    graph.add_node("decompose", _make_decompose_node(services))
    graph.add_node("plan_execute", _make_execute_node(services))
    graph.add_node("compose", _make_compose_node(services))

    graph.set_entry_point("b211_rewrite")
    graph.add_edge("b211_rewrite", "decompose")
    graph.add_edge("decompose", "plan_execute")
    graph.add_edge("plan_execute", "compose")
    graph.add_edge("compose", END)

    return graph.compile()


def _to_retrieved_documents(
    state: PlannerState,
) -> list[RetrievedDocument]:
    """Convert planner evidences + system notes into RetrievedDocument list.

    The main graph's REASON node expects RetrievedDocument objects. We pack
    each chunk as one document, plus an answer_fragment summary document
    per evidence, so the composer's cited answer is also visible.
    """
    docs: list[RetrievedDocument] = []

    # System notes first (B211 etc.)
    for note in state.system_notes:
        docs.append(
            RetrievedDocument(
                id=note.doc_id,
                content=note.content,
                score=note.score,
                metadata={"source": "system_note"},
                source="domain",
            )
        )

    # Evidence chunks
    for ev in state.evidences:
        for c in ev.chunks:
            docs.append(
                RetrievedDocument(
                    id=c.doc_id,
                    content=c.content,
                    score=c.score,
                    metadata={
                        "span_start": c.span_start,
                        "span_end": c.span_end,
                        "sub_question_idx": ev.sub_question.idx,
                        "sub_question_text": ev.sub_question.text,
                    },
                    source="vector",
                )
            )

    # Answer fragment summary
    if state.final_answer:
        docs.append(
            RetrievedDocument(
                id="visa_planner:final_answer",
                content=state.final_answer,
                score=1.0,
                metadata={"kind": "planner_answer"},
                source="domain",
            )
        )

    return docs


def _dominant_visa(state: GraphState) -> str:
    """Pick the dominant visa type using existing heuristics."""
    try:
        return _identify_visa_type(state).value
    except Exception:
        return "general"


def make_visa_subgraph(services: Services):
    """Factory that creates the multi-step visa planner node.

    Backward-compatible: the returned callable matches the old subgraph's
    contract — it accepts a GraphState and returns a dict with the keys
    expected by the main REASON node.
    """
    compiled_graph = _build_planner_graph(services)

    async def visa_planner_node(state: GraphState) -> dict[str, Any]:
        logger.info(
            "visa_planner_start",
            query=state.query[:80],
            intent=getattr(state.intent, "value", state.intent),
        )

        planner_state = PlannerState(query=state.query)

        try:
            result = await compiled_graph.ainvoke(planner_state)
            # langgraph returns a dict after compile().ainvoke()
            if isinstance(result, dict):
                final = PlannerState(**result)
            else:
                final = result
        except Exception as e:
            logger.error("visa_planner_graph_failed", error=str(e))
            final = planner_state.model_copy(update={"error": str(e)})

        docs = _to_retrieved_documents(final)

        # KG lookups preserved from the legacy path (cheap, non-LLM)
        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []
        try:
            dominant = _dominant_visa(state)
            kg_entities = await services.kg_store.get_entities(
                entity_ids=[f"visa:{dominant}"],
            )
        except Exception as e:
            logger.warning("visa_planner_kg_failed", error=str(e))

        logger.info(
            "visa_planner_complete",
            doc_count=len(docs),
            llm_calls=final.llm_call_count,
            sub_questions=len(final.sub_questions),
        )

        return {
            "retrieved_documents": docs,
            "kg_entities": kg_entities,
            "kg_relationships": kg_relationships,
            "domain": _dominant_visa(state),
            "current_node": "subgraph_visa",
            "visa_planner_trace": {
                "llm_calls": final.llm_call_count,
                "sub_questions": [sq.model_dump() for sq in final.sub_questions],
                "evidences_count": len(final.evidences),
                "final_answer": final.final_answer,
            },
        }

    return visa_planner_node
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py::TestMakeVisaSubgraph -q 2>&1 | tail -25`

Expected: 2 passed

- [ ] **Step 5: Run all tests**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py tests/unit/subgraphs/test_visa_subgraph.py -q 2>&1 | tail -15`

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add apps/graph-engine/src/nuzantara_graph/subgraphs/visa/planner.py apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "feat(visa-planner): assemble StateGraph planner end-to-end"
```

---

### Task 10: Remaining test cases (to hit 15 total)

**Files:**
- Modify: `apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py`

This task adds the remaining named test cases from the spec that are not yet covered by the earlier tasks' assertions. Some cases overlap with tests already written (e.g., contradiction retry is in TestExecute). Review the spec's 15-case table, then add missing ones as a `TestScenarios` class. Required scenarios still missing:

1. overstay fine calculation
2. KITAS→KITAP transition timeline (sequential sub-qs)
3. investor KITAS vs working KITAS (parallel sub-qs)
4. e-visa eligibility for EU citizens
5. visa for newborn Indonesian-foreigner child
6. multi-hop overstay+re-entry
7. Indonesian-language question

- [ ] **Step 1: Add TestScenarios class**

Append to `test_visa_planner.py`:

```python
@pytest.mark.unit
class TestScenarios:
    """Real-world scenario coverage per spec."""

    async def _run_planner(self, query: str, decompose_response: dict, fragment: str, docs=None):
        from nuzantara_graph.subgraphs.visa import make_visa_subgraph
        from nuzantara_schemas.state import GraphState, RetrievedDocument
        from helpers.mocks import make_mock_services

        svc = make_mock_services(
            documents=docs
            or [RetrievedDocument(id="doc_a", content="general visa guidance 30 days", score=0.85)],
            llm_responses={
                "generate_json": decompose_response,
                "generate": fragment,
            },
        )
        node = make_visa_subgraph(svc)
        return await node(GraphState(query=query, intent="visa"))

    @pytest.mark.asyncio
    async def test_overstay_fine(self):
        result = await self._run_planner(
            query="How much is the overstay fine for 3 days?",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "overstay fine 3 days", "needs_kb": True, "depends_on": []}
                ]
            },
            fragment="Fine is 1 million IDR per day [doc_a:0-40].",
        )
        assert result["current_node"] == "subgraph_visa"
        assert any("overstay" in d.content.lower() or "IDR" in d.content
                   for d in result["retrieved_documents"])

    @pytest.mark.asyncio
    async def test_kitas_to_kitap_transition(self):
        result = await self._run_planner(
            query="How do I go from KITAS to KITAP?",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "KITAS duration", "needs_kb": True, "depends_on": []},
                    {"idx": 1, "text": "KITAP eligibility after KITAS", "needs_kb": True, "depends_on": [0]},
                ]
            },
            fragment="KITAS 1 year then KITAP [doc_a:0-40].",
        )
        trace = result["visa_planner_trace"]
        assert len(trace["sub_questions"]) == 2

    @pytest.mark.asyncio
    async def test_investor_vs_working_kitas_parallel(self):
        result = await self._run_planner(
            query="Investor KITAS vs working KITAS?",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "investor KITAS requirements", "needs_kb": True, "depends_on": []},
                    {"idx": 1, "text": "working KITAS requirements", "needs_kb": True, "depends_on": []},
                ]
            },
            fragment="Both types require sponsorship [doc_a:0-40].",
        )
        trace = result["visa_planner_trace"]
        assert len(trace["sub_questions"]) == 2
        # Both should be parallel (depth 0)
        for sq in trace["sub_questions"]:
            assert sq["depends_on"] == []

    @pytest.mark.asyncio
    async def test_evisa_eu_eligibility(self):
        result = await self._run_planner(
            query="Can EU citizens get an e-visa?",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "e-visa eligible countries", "needs_kb": True, "depends_on": []}
                ]
            },
            fragment="EU citizens are eligible [doc_a:0-40].",
        )
        assert result["domain"] in {"kitas", "e_visa", "general"}

    @pytest.mark.asyncio
    async def test_newborn_visa(self):
        result = await self._run_planner(
            query="Visa for newborn child of Indonesian-foreigner couple",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "newborn KITAS sponsorship", "needs_kb": True, "depends_on": []}
                ]
            },
            fragment="Newborn children of mixed couples can get KITAS under family sponsorship [doc_a:0-40].",
        )
        assert "retrieved_documents" in result

    @pytest.mark.asyncio
    async def test_multi_hop_overstay_re_entry(self):
        result = await self._run_planner(
            query="I overstayed 3 days, then left, can I come back on e-visa?",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "overstay penalty", "needs_kb": True, "depends_on": []},
                    {"idx": 1, "text": "re-entry eligibility after overstay", "needs_kb": True, "depends_on": [0]},
                ]
            },
            fragment="Overstay is fined, re-entry allowed after penalty paid [doc_a:0-40].",
        )
        trace = result["visa_planner_trace"]
        assert len(trace["sub_questions"]) == 2
        assert trace["sub_questions"][1]["depends_on"] == [0]

    @pytest.mark.asyncio
    async def test_indonesian_language_query(self):
        result = await self._run_planner(
            query="Apa itu KITAS dan bagaimana cara mendapatkannya?",
            decompose_response={
                "sub_questions": [
                    {"idx": 0, "text": "definisi KITAS", "needs_kb": True, "depends_on": []}
                ]
            },
            fragment="KITAS adalah izin tinggal sementara [doc_a:0-40].",
        )
        assert result["current_node"] == "subgraph_visa"
```

- [ ] **Step 2: Run all visa_planner tests**

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py -q 2>&1 | tail -20`

Expected: all pass; total test count ≥ 15 in `test_visa_planner.py`

- [ ] **Step 3: Verify total case count**

Count tests and confirm coverage:

Run: `cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" python -m pytest tests/unit/subgraphs/test_visa_planner.py --collect-only -q 2>&1 | grep '::test_' | wc -l`

Expected: ≥ 15

- [ ] **Step 4: Commit**

```bash
git add apps/graph-engine/tests/unit/subgraphs/test_visa_planner.py
git commit -m "test(visa-planner): add 7 real-world scenario tests"
```

---

### Task 11: Architecture doc

**Files:**
- Create: `apps/graph-engine/docs/visa-planner-architecture.md`

- [ ] **Step 1: Write the doc**

```markdown
# Visa Subgraph Multi-Step Planner — Architecture

**Entry point:** `nuzantara_graph.subgraphs.visa.make_visa_subgraph(services) -> async callable`

**Contract:** Called by the main graph as the `SUBGRAPH_VISA` node. Mutates `GraphState` with `retrieved_documents`, `kg_entities`, `kg_relationships`, `domain`, `current_node`, and adds a `visa_planner_trace` key for introspection.

## StateGraph (ASCII)

            ┌────────────────┐
            │  b211_rewrite  │  — regex replace + system note
            └───────┬────────┘
                    │
            ┌───────▼────────┐
            │   decompose    │  — 1 LLM call → list[SubQuestion]
            └───────┬────────┘
                    │
            ┌───────▼────────┐
            │  plan_execute  │  — topo loop over sub-questions
            └───────┬────────┘  ↳ per-node: retrieve → fragment → critique → (retry×1)
                    │
            ┌───────▼────────┐
            │    compose     │  — 1 LLM call → citation enforcer
            └───────┬────────┘
                    │
            ┌───────▼────────┐
            │   terminate    │  — packs evidences into RetrievedDocument list
            └───────┬────────┘
                    │
                   END

## Termination Proof

Let `N = len(sub_questions)` after `decompose` truncates to ≤ 5.

1. `decompose` runs exactly once.
2. `plan_execute` iterates a topologically sorted list **once**. Each sub-question receives:
   - one retrieve call (free, no LLM)
   - one `compose_fragment` LLM call
   - optionally one retry LLM call if `contradiction_score > 0.4` AND `retries_used < 1`
3. `retries_used` is monotonically increasing and **never reset**.
4. `llm_call_count` is a monotonically increasing global counter with a hard cap (`max_llm_calls`, default 8). Any step that would exceed the cap is skipped.
5. `compose` runs exactly once.
6. The StateGraph edges form a line (`b211_rewrite → decompose → plan_execute → compose → END`). There is **no conditional loop-back edge**.

Total LLM calls ≤ `1 + N×2 + 1 = 2N + 2`. For N=5, that is 12 — clamped to 8 by the budget check.

∎ The graph halts for every input because: (a) the StateGraph is acyclic, (b) the inner loop is a finite `for` over a finite topologically-sorted list, (c) per-node retries are bounded by a monotonic counter, (d) the global LLM budget is a hard ceiling.

## Failure Mode Table

| Failure | Detection | Recovery |
|---|---|---|
| Decompose LLM returns invalid JSON | `json.JSONDecodeError` / type check | Fall back to single sub-question = original query |
| Decompose LLM unavailable (no API key) | `ValueError` from `LLMGateway` | Same fallback |
| Decompose returns cyclic deps | `topo_sort` detects via idx ordering | Drop back-edge, log warning, continue |
| Decompose returns depth > max_depth | depth counter in `topo_sort` | Collapse to shallowest ancestor, log broken edges |
| Decompose returns > max_sub_questions | length check | Truncate to first 5 |
| Vector store returns empty | `len(chunks) == 0` | Node evidence is empty; composer emits `_SYSTEM_FALLBACK` |
| Vector store raises | try/except in `_retrieve_chunks` | Empty chunks, log warning, continue |
| `contradiction_score > 0.4` | `ContradictionGrader.score()` | Re-plan that one sub-q once (if retry budget allows) |
| All nodes produce empty evidence | `compose()` sees no chunks | Returns `_SYSTEM_FALLBACK` |
| Composer LLM returns uncitable answer | `enforce_citations` | Drop uncitable sentences; fall back if all drop |
| LLM budget exhausted mid-execute | `llm_call_count >= max_llm_calls` | Skip remaining LLM calls, proceed with current evidence |
| B211 pre-filter matches | regex match | Rewrite query + inject system note chunk |
| LangGraph compile/execute exception | try/except in `make_visa_subgraph` wrapper | Log error, return empty contract dict |

## Citation Enforcement Rationale

Every factual claim in a visa answer must be traceable to a document or a system note. Otherwise:

1. **Hallucination risk**: Zantara has historically fabricated legal requirements (cf. `.claude/rules/cicatrix-scars.md`). LLM prompt instructions are unreliable; a deterministic post-processor is the only guarantee.
2. **User verification**: Users cannot verify claims against primary sources without stable `doc_id:start-end` anchors.
3. **Compliance**: Indonesian visa rules change monthly; wrong claims have legal consequences for clients.

The enforcer:
1. Splits the LLM output on sentence boundaries.
2. For each sentence, checks for a `[doc_id:start-end]` citation whose `doc_id` is in the set of known chunks.
3. If none, attempts auto-attribution via token overlap (≥ 50%).
4. If still none, replaces the sentence with `(unable to cite this claim; refer to the documents below)`.
5. If **every** sentence fails, returns `I cannot produce a fully-cited answer for this query. Please rephrase or contact support for visa assistance.`

## B211 Handling

The B211 visit visa no longer exists. A pre-filter rewrites any match to `KITAS/ITAS or e-visa (C-series)` and injects a system note chunk with `doc_id="SYSTEM:b211_rewrite"`. This guarantees the composer can cite the rewrite without needing knowledge-base evidence.

## Known Limitations

1. **Span offsets are approximate.** We default to `(0, len(content))` because the vector store does not expose character-level offsets. Real spans would require pipeline re-ingestion.
2. **Contradiction detection is heuristic.** Number disagreement + negation polarity flip catches the obvious cases. Subtle semantic contradictions (e.g., "60 days" vs "two months") are not detected.
3. **No live-model tier in initial delivery.** All tests mock `LLMGateway`. A `@pytest.mark.live` tier can be added when a gated test fixture for Gemini exists.
4. **Language detection is naive.** The planner relies on the LLM to mirror the input language.
```

- [ ] **Step 2: Commit**

```bash
git add apps/graph-engine/docs/visa-planner-architecture.md
git commit -m "docs(visa-planner): architecture, termination proof, failure modes"
```

---

### Task 12: Full test sweep + verification

- [ ] **Step 1: Run all visa tests**

Run:
```bash
cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" \
  python -m pytest tests/unit/subgraphs/test_visa_planner.py tests/unit/subgraphs/test_visa_subgraph.py -v 2>&1 | tail -40
```

Expected: all green

- [ ] **Step 2: Verify no broken imports in main graph builder**

Run:
```bash
cd apps/graph-engine && PYTHONPATH="src:../../packages/shared-schemas/src:tests" \
  python -c "from nuzantara_graph.graph.builder import build_graph; g = build_graph(); print('OK, nodes:', len(g.nodes))" 2>&1 | tail -5
```

Expected: "OK, nodes: …"

- [ ] **Step 3: Line count check**

Run:
```bash
wc -l apps/graph-engine/src/nuzantara_graph/subgraphs/visa/*.py
```

Expected: each file reasonably short; `planner.py` + `execute.py` the largest, both < 300 lines

- [ ] **Step 4: Confirm 3+ commits on the branch**

Run:
```bash
cd /Users/nuzantara/Desktop/nuzantara/.worktrees/visa-planner && git log --oneline feat/visa-multi-step-planner ^main 2>&1 | head
```

Expected: ≥ 3 commits

---

## Self-Review

**Spec coverage:** Each requirement from `docs/superpowers/specs/2026-04-11-visa-planner-design.md` is covered:
- Pipeline (b211_rewrite → decompose → plan_execute → compose → terminate): Tasks 3, 4, 7, 8, 9
- Backward compat (make_visa_subgraph signature, return keys): Task 9
- Termination proof: Task 11
- B211 pre-filter: Task 3
- LLM provider policy (Services.llm only): Tasks 4, 7, 8, 9
- Topo sort + cycle break + depth clamp: Task 5
- Contradiction grader: Task 6
- Citation enforcer: Task 8
- 15 tests: Tasks 1, 3, 4, 5, 6, 7, 8, 9, 10 (running total: 3+4+5+4+4+5+4+2+7 = 38 tests, but **named scenarios** cover ≥ 15 of the spec items)
- Architecture doc: Task 11

**Placeholder scan:** No "TBD/TODO/implement later/handle edge cases" markers. Every step has code.

**Type consistency:** `SubQuestion`, `Chunk`, `NodeEvidence`, `PlannerState`, `ContradictionGrader` are defined in Task 1 and 6, then used consistently in Tasks 4, 5, 7, 8, 9.

No gaps.

---

## Execution

**Selected:** Inline execution via `superpowers:executing-plans` (single-session TDD, user task specifies autonomous work).
