"""The internal `source_ref` must never reach the model (2026-08-11).

`_inject_curated_qa_grounding` used to label every block
``[CURATED {source_ref} {source_date}]``. `zantara_core.py` orders the model to
cite its source — ``📜 Sumber: [Nama Peraturan], Pasal [X]`` — so the model
cited what it had been given. Measured on the live worker that day, four of
eight probed answers printed a line ending in ``CURATED FINAL-v2.md#Q7`` to the
client: an internal repo artifact presented as a legal source, on a surface
whose entire value is being a credible consultant.

Two of those four carried no other defect — the citation leak is independent of
the internal-monologue leak found in the same sweep, and would have survived a
cure for it.

Sizing, because "is this a corner case?" decides the shape of the cure:
scrolling the whole live collection gave **808 of 808** points with an
internal-looking `source_ref` (`FINAL.md#Q1` … `#Q14`, 456 distinct values) and
**zero** with a citable regulation name. There is therefore nothing in this
field a client may ever see, and removing it costs no citation — the regulation
an answer rests on is named inside the answer text, which is what the model
should be citing.

Guilt and innocence are both load-bearing here in an unusual way: the naive
cure ("drop the whole label") would also drop `source_date`, which is real
vetting metadata that names no artifact and tells the model how fresh the
pre-vetted answer is. The date must survive.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

INTERNAL_REF = "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1"
VISA_ENTITIES = {"domain": "visa"}


def make_core() -> OrchestratorCore:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.semantic_cache = None
    core.faq_cache = None
    core.retriever = None
    core.entity_extractor = None
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None
    core.db_pool = None
    core.reasoning_engine = None
    core.llm_gateway = object()
    core.context_manager = None
    core.query_gates = None
    core.prompt_builder = None
    core.routing_manager = None
    core._surface_router = None
    core._specialized_router = None
    core._multi_agent_coordinator = None
    core._kg_auto_expansion = None
    return core


def _hit(score: float = 0.95, answer: str = "The E33 deposit is USD 130,000.", **meta) -> dict:
    metadata = {
        "answer": answer,
        "domain": "visa",
        "source_ref": INTERNAL_REF,
        "source_date": "2026-07-15",
        "confidence_class": "BERSYARAT",
        "source_priority": 80,
        **meta,
    }
    return {"id": "abc", "text": "curated question", "metadata": metadata, "score": score}


def _core_with(hits: list[dict]) -> OrchestratorCore:
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value={"query": "q", "results": hits, "collection": "curated_qa"},
        ),
    )
    return core


@pytest.mark.asyncio
async def test_guilt_the_internal_source_ref_never_reaches_the_prompt() -> None:
    """GUILT: the exact string the live bot printed to clients is absent.

    Asserted on the raw value AND on its bare filename half: an intermediate
    cure that shortened `…/FINAL-v2.md#Q7` to `FINAL-v2.md` would pass a
    whole-string check while leaking the same thing.
    """
    core = _core_with([_hit()])

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("E33 deposit?", VISA_ENTITIES)

    assert result, "precondition: the hit must be injected at all"
    assert INTERNAL_REF not in result
    assert "E33-DEFINITIVE-CHATKB-2026-07-15" not in result
    assert ".md" not in result


@pytest.mark.asyncio
async def test_guilt_holds_for_every_injected_block_not_just_the_first() -> None:
    """GUILT, second block: top_k is 2, so a cure applied to one label and not
    the loop would leak on any query that matches twice."""
    core = _core_with(
        [
            _hit(0.95, answer="Answer one.", source_ref="ALPHA.md#Q1"),
            _hit(0.93, answer="Answer two.", source_ref="BETA.md#Q9"),
        ],
    )

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("E33 deposit?", VISA_ENTITIES)

    assert "Answer one." in result and "Answer two." in result
    assert "ALPHA.md#Q1" not in result
    assert "BETA.md#Q9" not in result


@pytest.mark.asyncio
async def test_innocence_the_vetting_date_and_the_answer_survive() -> None:
    """INNOCENCE: the cure must remove the artifact, not the metadata.

    `source_date` names nothing internal and tells the model how fresh the
    pre-vetted answer is; the answer text is the whole point of the block. A
    cure that deleted the label wholesale would pass the guilt tests above and
    silently drop both.
    """
    core = _core_with([_hit()])

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("E33 deposit?", VISA_ENTITIES)

    assert "The E33 deposit is USD 130,000." in result
    assert "2026-07-15" in result
    assert "CURATED" in result


@pytest.mark.asyncio
async def test_innocence_the_model_is_told_the_section_is_not_citable() -> None:
    """INNOCENCE / belt-and-braces: with the identifier gone, the only thing
    left to mistake for a source is the `[CURATED …]` marker itself, so the
    header says so explicitly. Asserted once, on the header — not per block."""
    core = _core_with([_hit()])

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("E33 deposit?", VISA_ENTITIES)

    assert "Never cite this section" in result
    assert "cite only the regulation named inside the text" in result


@pytest.mark.asyncio
async def test_provenance_is_kept_in_the_log_not_lost(caplog) -> None:
    """The reference is not deleted, it is RELOCATED.

    Provenance is genuinely used — "which vetted row produced this answer" is
    the first question when a curated answer turns out wrong. Moving it to the
    log keeps that answerable while removing it from everything a client can
    see. Without this test the cure would read as "we dropped provenance".
    """
    core = _core_with([_hit()])

    with (
        patch("backend.app.metrics.curated_qa_injections_total"),
        caplog.at_level(logging.INFO),
    ):
        await core._inject_curated_qa_grounding("E33 deposit?", VISA_ENTITIES)

    assert any(INTERNAL_REF in record.getMessage() for record in caplog.records), (
        "the internal ref must still be recoverable from the logs"
    )
