"""Contract tests for the shadow deterministic finalization spine."""

from __future__ import annotations

import ast
import asyncio
import inspect
import pickle
import time
from copy import copy, deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic import orchestrator_core as orchestrator_core_module
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.rag.agentic.orchestrator_finalization import (
    FinalizationContext,
    finalize_core_result,
    is_canonically_finalized,
)
from backend.services.rag.agentic.schema import (
    AnalyticsReceiptStatus,
    CoreResult,
    EvidenceProvenance,
    FinalizationStatus,
    ProducerOrigin,
    TrustedBypassReason,
)


def _producer_result(producer: str) -> CoreResult:
    source = {"type": "test", "source": "contract-source"}
    common: dict[str, Any] = {
        "answer": f"answer:{producer}",
        "sources": [source],
        "abstain": producer == "react",
        "abstain_reason": "contract-abstain" if producer == "react" else None,
    }
    if producer == "gate":
        return CoreResult(**(common | {"model_used": "greeting-gate", "sources": []}))
    if producer == "faq":
        return CoreResult(**common, model_used="faq_cache")
    if producer == "semantic_cache":
        return CoreResult(**common, model_used="cache", cache_hit=True)
    if producer == "multi_agent":
        return CoreResult(**(common | {"sources": []}), model_used="multi-agent-coordinator")
    if producer == "specialized_router":
        return CoreResult(
            **(common | {"sources": []}),
            model_used="specialized-router",
            tools_called=["autonomous_research"],
        )
    if producer == "kg":
        return CoreResult(**common, model_used="kg_langgraph")
    return CoreResult(
        **common,
        model_used="gemini-3.5-flash",
    )


def _producer_context(producer: str) -> FinalizationContext:
    origins = {
        "gate": ProducerOrigin.QUERY_GATE,
        "faq": ProducerOrigin.FAQ_CACHE,
        "semantic_cache": ProducerOrigin.SEMANTIC_CACHE,
        "multi_agent": ProducerOrigin.MULTI_AGENT_COORDINATOR,
        "specialized_router": ProducerOrigin.SPECIALIZED_SERVICE_ROUTER,
        "kg": ProducerOrigin.KNOWLEDGE_GRAPH,
        "react": ProducerOrigin.REACT_PIPELINE,
    }
    return FinalizationContext(
        result=_producer_result(producer),
        producer_origin=origins[producer],
        trusted_bypass_reason=(
            TrustedBypassReason.DETERMINISTIC_QUERY_GATE if producer == "gate" else None
        ),
        analytics_receipt=(AnalyticsReceiptStatus.WRITTEN if producer == "react" else None),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "producer",
        "expected_origin",
        "expected_provenance",
        "expected_trust",
        "expected_status",
    ),
    [
        (
            "gate",
            ProducerOrigin.QUERY_GATE,
            None,
            TrustedBypassReason.DETERMINISTIC_QUERY_GATE,
            FinalizationStatus.SHADOW_RECORDED,
        ),
        (
            "faq",
            ProducerOrigin.FAQ_CACHE,
            EvidenceProvenance.FAQ_CACHE,
            None,
            FinalizationStatus.SHADOW_RECORDED,
        ),
        (
            "semantic_cache",
            ProducerOrigin.SEMANTIC_CACHE,
            EvidenceProvenance.SEMANTIC_CACHE,
            None,
            FinalizationStatus.SHADOW_RECORDED,
        ),
        (
            "multi_agent",
            ProducerOrigin.MULTI_AGENT_COORDINATOR,
            None,
            None,
            FinalizationStatus.SHADOW_INCOMPLETE,
        ),
        (
            "specialized_router",
            ProducerOrigin.SPECIALIZED_SERVICE_ROUTER,
            None,
            None,
            FinalizationStatus.SHADOW_INCOMPLETE,
        ),
        (
            "kg",
            ProducerOrigin.KNOWLEDGE_GRAPH,
            EvidenceProvenance.KNOWLEDGE_GRAPH,
            None,
            FinalizationStatus.SHADOW_RECORDED,
        ),
        (
            "react",
            ProducerOrigin.REACT_PIPELINE,
            EvidenceProvenance.REACT_PIPELINE,
            None,
            FinalizationStatus.SHADOW_RECORDED,
        ),
    ],
)
async def test_public_sync_boundary_finalizes_each_producer_once_and_is_byte_idempotent(
    producer: str,
    expected_origin: ProducerOrigin,
    expected_provenance: EvidenceProvenance | None,
    expected_trust: TrustedBypassReason | None,
    expected_status: FinalizationStatus,
) -> None:
    context = _producer_context(producer)
    raw_result = context.result
    answer_before = raw_result.answer
    abstain_before = raw_result.abstain
    sources_before = deepcopy(raw_result.sources)

    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    core._process_query_core_unfinalized = AsyncMock(return_value=context)

    with patch.object(
        orchestrator_core_module,
        "finalize_core_result",
        wraps=finalize_core_result,
    ) as finalizer:
        result = await core.process_query_core(
            query="contract query",
            user_id="contract-user",
            conversation_history=None,
            start_time=0.0,
        )
        assert finalizer.call_count == 1
        serialized_once = result.model_dump_json().encode()

        finalized_again = await core.finalize_result(result)

        assert finalizer.call_count == 1
        assert finalized_again.model_dump_json().encode() == serialized_once

    assert result.answer == answer_before
    assert result.abstain is abstain_before
    assert result.sources == sources_before
    assert result.finalization_status is expected_status
    assert result.producer_origin is expected_origin
    assert result.evidence_provenance is expected_provenance
    assert result.trusted_bypass_reason is expected_trust
    expected_receipt = (
        AnalyticsReceiptStatus.WRITTEN if producer == "react" else AnalyticsReceiptStatus.SKIPPED
    )
    assert result.analytics_receipt is expected_receipt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("receipt", "expected_receipt"),
    [
        (AnalyticsReceiptStatus.WRITTEN, AnalyticsReceiptStatus.WRITTEN),
        (AnalyticsReceiptStatus.FAILED, AnalyticsReceiptStatus.FAILED),
        (AnalyticsReceiptStatus.SKIPPED, AnalyticsReceiptStatus.SKIPPED),
        (AnalyticsReceiptStatus.SCHEDULED, AnalyticsReceiptStatus.FAILED),
        ("written", AnalyticsReceiptStatus.FAILED),
        (None, AnalyticsReceiptStatus.FAILED),
    ],
)
async def test_internal_react_analytics_receipt_prevents_second_write(
    receipt: AnalyticsReceiptStatus | str | None,
    expected_receipt: AnalyticsReceiptStatus,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock()
    context = _producer_context("react")
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=context.result,
            producer_origin=context.producer_origin,
            analytics_receipt=receipt,  # type: ignore[arg-type]
        )
    )

    with patch.object(orchestrator_core_module, "spawn") as spawn_mock:
        finalized = await core.process_query_core(
            query="react query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )

    spawn_mock.assert_not_called()
    core._log_query_analytics.assert_not_called()
    assert finalized.analytics_receipt is expected_receipt


@pytest.mark.asyncio
async def test_forged_public_status_and_receipt_cannot_suppress_one_canonical_write() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock(return_value=AnalyticsReceiptStatus.WRITTEN)
    result = CoreResult(
        answer="cached answer",
        sources=[{"source": "faq-contract"}],
        model_used="faq_cache",
        finalization_status=FinalizationStatus.SHADOW_RECORDED,
        producer_origin=ProducerOrigin.QUERY_GATE,
        evidence_provenance=EvidenceProvenance.REACT_PIPELINE,
        trusted_bypass_reason=TrustedBypassReason.DETERMINISTIC_QUERY_GATE,
        analytics_receipt=AnalyticsReceiptStatus.WRITTEN,
    )
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=result,
            producer_origin=ProducerOrigin.FAQ_CACHE,
            analytics_receipt=AnalyticsReceiptStatus.WRITTEN,
        )
    )
    scheduled: list[asyncio.Task[AnalyticsReceiptStatus]] = []

    def capture_spawn(
        coro: Any,
        *,
        name: str | None = None,
    ) -> asyncio.Task[AnalyticsReceiptStatus]:
        task = asyncio.create_task(coro, name=name)
        scheduled.append(task)
        return task

    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn) as spawn_mock:
        finalized = await core.process_query_core(
            query="faq query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )
        serialized_once = finalized.model_dump_json().encode()
        finalized_again = await core.finalize_result(finalized)

    await asyncio.gather(*scheduled)

    assert spawn_mock.call_count == 1
    assert len(scheduled) == 1
    assert core._log_query_analytics.await_count == 1
    assert finalized_again.model_dump_json().encode() == serialized_once
    assert finalized.producer_origin is ProducerOrigin.FAQ_CACHE
    assert finalized.evidence_provenance is EvidenceProvenance.FAQ_CACHE
    assert finalized.trusted_bypass_reason is None
    assert finalized.analytics_receipt is AnalyticsReceiptStatus.SCHEDULED


@pytest.mark.asyncio
async def test_forged_empty_origin_is_recomputed_fail_visible() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    result = CoreResult(
        answer="future producer",
        sources=[],
        model_used="future-model",
        finalization_status=FinalizationStatus.SHADOW_RECORDED,
        producer_origin=ProducerOrigin.REACT_PIPELINE,
        evidence_provenance=EvidenceProvenance.REACT_PIPELINE,
        analytics_receipt=AnalyticsReceiptStatus.WRITTEN,
    )

    finalized = await core.finalize_result(result)

    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE
    assert finalized.producer_origin is ProducerOrigin.UNKNOWN
    assert finalized.evidence_provenance is None
    assert finalized.trusted_bypass_reason is None
    assert finalized.analytics_receipt is AnalyticsReceiptStatus.SKIPPED


@pytest.mark.asyncio
async def test_clones_and_json_roundtrip_are_pure_and_cannot_duplicate_analytics() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock(return_value=AnalyticsReceiptStatus.WRITTEN)
    context = FinalizationContext(
        result=CoreResult(
            answer="sourceful",
            sources=[{"source": "faq-contract"}],
            model_used="faq_cache",
        ),
        producer_origin=ProducerOrigin.FAQ_CACHE,
    )
    core._process_query_core_unfinalized = AsyncMock(return_value=context)
    scheduled: list[asyncio.Task[AnalyticsReceiptStatus]] = []

    def capture_spawn(
        coro: Any,
        *,
        name: str | None = None,
    ) -> asyncio.Task[AnalyticsReceiptStatus]:
        task = asyncio.create_task(coro, name=name)
        scheduled.append(task)
        return task

    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn) as spawn_mock:
        original = await core.process_query_core(
            query="faq query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )
        clones = [
            original.model_copy(),
            deepcopy(original),
            CoreResult.model_validate_json(original.model_dump_json()),
        ]
        for cloned in clones:
            assert not is_canonically_finalized(cloned)
            finalized_clone = await core.finalize_result(cloned)
            assert is_canonically_finalized(finalized_clone)
            assert finalized_clone.producer_origin is ProducerOrigin.FAQ_CACHE
            assert finalized_clone.finalization_status is FinalizationStatus.SHADOW_RECORDED
            assert finalized_clone.analytics_receipt is AnalyticsReceiptStatus.SKIPPED

    await asyncio.gather(*scheduled)

    assert is_canonically_finalized(original)
    assert spawn_mock.call_count == 1
    assert len(scheduled) == 1
    assert core._log_query_analytics.await_count == 1


@pytest.mark.asyncio
async def test_post_seal_metadata_tamper_is_restored_without_another_write() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock(return_value=AnalyticsReceiptStatus.WRITTEN)
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=CoreResult(
                answer="sourceful",
                sources=[{"source": "faq-contract"}],
                model_used="faq_cache",
            ),
            producer_origin=ProducerOrigin.FAQ_CACHE,
        )
    )
    scheduled: list[asyncio.Task[AnalyticsReceiptStatus]] = []

    def capture_spawn(
        coro: Any,
        *,
        name: str | None = None,
    ) -> asyncio.Task[AnalyticsReceiptStatus]:
        task = asyncio.create_task(coro, name=name)
        scheduled.append(task)
        return task

    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn) as spawn_mock:
        result = await core.process_query_core(
            query="faq query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )
        canonical_bytes = result.model_dump_json().encode()
        canonical_metadata = (
            result.finalization_status,
            result.producer_origin,
            result.evidence_provenance,
            result.trusted_bypass_reason,
            result.analytics_receipt,
        )
        result.finalization_status = FinalizationStatus.SHADOW_INCOMPLETE
        result.producer_origin = ProducerOrigin.REACT_PIPELINE
        result.evidence_provenance = EvidenceProvenance.REACT_PIPELINE
        result.trusted_bypass_reason = TrustedBypassReason.DETERMINISTIC_QUERY_GATE
        result.analytics_receipt = AnalyticsReceiptStatus.FAILED
        assert not is_canonically_finalized(result)

        restored = await core.finalize_result(result)

    await asyncio.gather(*scheduled)

    assert restored.model_dump_json().encode() == canonical_bytes
    assert restored.finalization_status is canonical_metadata[0]
    assert restored.producer_origin is canonical_metadata[1]
    assert restored.evidence_provenance is canonical_metadata[2]
    assert restored.trusted_bypass_reason is canonical_metadata[3]
    assert restored.analytics_receipt is canonical_metadata[4]
    assert is_canonically_finalized(restored)
    assert spawn_mock.call_count == 1
    assert core._log_query_analytics.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "producer"),
    [
        ("finalization_status", "faq"),
        ("producer_origin", "faq"),
        ("evidence_provenance", "faq"),
        ("trusted_bypass_reason", "gate"),
        ("analytics_receipt", "faq"),
    ],
)
async def test_post_seal_equal_string_tamper_restores_exact_enum_type(
    field_name: str,
    producer: str,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    result = await core.finalize_result(_producer_result(producer))
    canonical_value = getattr(result, field_name)
    assert canonical_value is not None
    canonical_bytes = result.model_dump_json().encode()

    setattr(result, field_name, canonical_value.value)

    assert not is_canonically_finalized(result)
    restored = await core.finalize_result(result)

    assert getattr(restored, field_name) is canonical_value
    assert restored.model_dump_json().encode() == canonical_bytes
    assert is_canonically_finalized(restored)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "producer"),
    [
        ("finalization_status", "faq"),
        ("producer_origin", "faq"),
        ("evidence_provenance", "faq"),
        ("trusted_bypass_reason", "gate"),
        ("analytics_receipt", "faq"),
    ],
)
async def test_post_seal_none_tamper_restores_exact_enum_type(
    field_name: str,
    producer: str,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    result = await core.finalize_result(_producer_result(producer))
    canonical_value = getattr(result, field_name)
    assert canonical_value is not None
    canonical_bytes = result.model_dump_json().encode()

    setattr(result, field_name, None)

    assert not is_canonically_finalized(result)
    restored = await core.finalize_result(result)

    assert getattr(restored, field_name) is canonical_value
    assert restored.model_dump_json().encode() == canonical_bytes
    assert is_canonically_finalized(restored)


@pytest.mark.asyncio
@pytest.mark.parametrize("tampered_model", ["security-gate", "future-gate"])
async def test_post_seal_attribution_drift_is_fail_closed_without_io(
    tampered_model: str,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock()
    result = await core.finalize_result(_producer_result("faq"))
    assert result.producer_origin is ProducerOrigin.FAQ_CACHE

    result.model_used = tampered_model
    with patch.object(orchestrator_core_module, "spawn") as spawn_mock:
        finalized = await core.finalize_result(result)

    spawn_mock.assert_not_called()
    core._log_query_analytics.assert_not_called()
    assert finalized.producer_origin is ProducerOrigin.UNKNOWN
    assert finalized.trusted_bypass_reason is None
    assert finalized.evidence_provenance is None
    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE
    assert finalized.analytics_receipt is AnalyticsReceiptStatus.SKIPPED
    assert is_canonically_finalized(finalized)


@pytest.mark.asyncio
async def test_execution_authority_cannot_be_cloned_into_a_second_analytics_write() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock(return_value=AnalyticsReceiptStatus.WRITTEN)
    first_context = FinalizationContext(
        result=CoreResult(
            answer="sourceful",
            sources=[{"source": "faq-contract"}],
            model_used="faq_cache",
        ),
        producer_origin=ProducerOrigin.FAQ_CACHE,
    )
    core._process_query_core_unfinalized = AsyncMock(return_value=first_context)
    scheduled: list[asyncio.Task[AnalyticsReceiptStatus]] = []
    captured_claims: list[Any] = []
    original_finalize = core._finalize_process_context

    def capture_spawn(
        coro: Any,
        *,
        name: str | None = None,
    ) -> asyncio.Task[AnalyticsReceiptStatus]:
        task = asyncio.create_task(coro, name=name)
        scheduled.append(task)
        return task

    def capture_authority(
        context: FinalizationContext,
        **kwargs: Any,
    ) -> CoreResult:
        claim = kwargs["claim_analytics"]
        captured_claims.extend([claim, copy(claim), deepcopy(claim)])
        with pytest.raises((AttributeError, pickle.PicklingError, TypeError)):
            pickle.dumps(claim)
        return original_finalize(context, **kwargs)

    core._finalize_process_context = MagicMock(side_effect=capture_authority)
    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn) as spawn_mock:
        await core.process_query_core(
            query="faq query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )
        original_claim, shallow_claim, deep_claim = captured_claims
        assert shallow_claim is original_claim
        assert deep_claim is original_claim

        second_context = FinalizationContext(
            result=first_context.result.model_copy(),
            producer_origin=ProducerOrigin.FAQ_CACHE,
        )
        for claim, context in (
            (original_claim, first_context),
            (shallow_claim, first_context),
            (deep_claim, second_context),
        ):
            with pytest.raises(RuntimeError, match="capability already consumed"):
                original_finalize(
                    context,
                    query="faq query",
                    user_id=None,
                    session_id=None,
                    claim_analytics=claim,
                )

    await asyncio.gather(*scheduled)

    assert spawn_mock.call_count == 1
    assert len(scheduled) == 1
    assert core._log_query_analytics.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sources",
    [
        [None],
        [{}],
        [{"source": ""}],
        [{"source": "unknown"}],
        [{"title": "placeholder"}],
        ["not-a-source"],
    ],
)
async def test_placeholder_sources_do_not_create_evidence_or_get_rewritten(
    sources: list[Any],
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    result = CoreResult(answer="cached answer", sources=deepcopy(sources), model_used="faq_cache")
    sources_before = deepcopy(result.sources)

    finalized = await core.finalize_result(result)

    assert finalized.sources == sources_before
    assert finalized.producer_origin is ProducerOrigin.FAQ_CACHE
    assert finalized.evidence_provenance is None
    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_used", "route_used"),
    [
        ("future-gate", None),
        ("model", "future-gate"),
        ("model", "invented-gate"),
    ],
)
async def test_gate_like_names_outside_closed_allowlist_are_incomplete(
    model_used: str,
    route_used: str | None,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None

    finalized = await core.finalize_result(
        CoreResult(answer="untrusted", model_used=model_used, route_used=route_used)
    )

    assert finalized.producer_origin is ProducerOrigin.UNKNOWN
    assert finalized.trusted_bypass_reason is None
    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE


def test_internal_context_cannot_extend_the_closed_gate_allowlist() -> None:
    finalized = finalize_core_result(
        CoreResult(answer="future gate", model_used="future-gate"),
        producer_origin=ProducerOrigin.QUERY_GATE,
        trusted_bypass_reason=TrustedBypassReason.DETERMINISTIC_QUERY_GATE,
        analytics_receipt=AnalyticsReceiptStatus.SKIPPED,
    )

    assert finalized.producer_origin is ProducerOrigin.UNKNOWN
    assert finalized.trusted_bypass_reason is None
    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE


@pytest.mark.asyncio
@pytest.mark.parametrize("background_error", [RuntimeError("db failed"), TimeoutError("db slow")])
async def test_fast_path_analytics_is_non_blocking_and_failure_cannot_mutate_response(
    background_error: Exception,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()

    async def fail_later(**_kwargs: Any) -> AnalyticsReceiptStatus:
        await asyncio.sleep(0)
        raise background_error

    core._log_query_analytics = fail_later
    tasks: list[asyncio.Task[AnalyticsReceiptStatus]] = []

    def capture_spawn(coro: Any, *, name: str | None = None) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro, name=name)
        tasks.append(task)
        return task

    raw_result = _producer_result("faq")
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=raw_result,
            producer_origin=ProducerOrigin.FAQ_CACHE,
        )
    )
    answer_before = raw_result.answer
    abstain_before = raw_result.abstain
    sources_before = deepcopy(raw_result.sources)
    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn):
        finalized = await asyncio.wait_for(
            core.process_query_core(
                query="cached query",
                user_id=None,
                conversation_history=None,
                start_time=0.0,
            ),
            timeout=0.05,
        )

    assert finalized.analytics_receipt is AnalyticsReceiptStatus.SCHEDULED
    assert finalized.answer == answer_before
    assert finalized.abstain is abstain_before
    assert finalized.sources == sources_before
    with pytest.raises(type(background_error)):
        await tasks[0]
    assert finalized.answer == answer_before
    assert finalized.abstain is abstain_before
    assert finalized.sources == sources_before


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["prepare", "spawn"])
async def test_synchronous_analytics_scheduling_failure_is_fail_visible(
    failure_point: str,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    raw_result = _producer_result("faq")
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=raw_result,
            producer_origin=ProducerOrigin.FAQ_CACHE,
        )
    )
    if failure_point == "prepare":
        core._log_query_analytics = MagicMock(side_effect=RuntimeError("prepare failed"))
        spawn_side_effect = None
    else:
        core._log_query_analytics = AsyncMock()
        spawn_side_effect = RuntimeError("spawn failed")

    with patch.object(
        orchestrator_core_module,
        "spawn",
        side_effect=spawn_side_effect,
    ) as spawn_mock:
        finalized = await core.process_query_core(
            query="cached query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )

    assert finalized.answer == raw_result.answer
    assert finalized.abstain is raw_result.abstain
    assert finalized.sources == raw_result.sources
    assert finalized.analytics_receipt is AnalyticsReceiptStatus.FAILED
    assert spawn_mock.call_count == (1 if failure_point == "spawn" else 0)


@pytest.mark.asyncio
async def test_scheduled_analytics_uses_return_time_source_and_timing_snapshots() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    raw_result = CoreResult(
        answer="cached answer",
        sources=[{"source": "faq-contract"}],
        model_used="faq_cache",
        timings={"total": 0.01},
    )
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=raw_result,
            producer_origin=ProducerOrigin.FAQ_CACHE,
        )
    )
    core._log_query_analytics = AsyncMock(return_value=AnalyticsReceiptStatus.WRITTEN)
    scheduled: list[Any] = []

    def capture_spawn(coro: Any, *, name: str | None = None) -> None:
        del name
        scheduled.append(coro)

    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn):
        finalized = await core.process_query_core(
            query="cached query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )

    raw_result.sources.append({"source": "post-return-mutation"})
    raw_result.timings["total"] = 99.0

    assert finalized.analytics_receipt is AnalyticsReceiptStatus.SCHEDULED
    assert core._log_query_analytics.call_args.kwargs["sources"] == [{"source": "faq-contract"}]
    assert core._log_query_analytics.call_args.kwargs["timings"] == {"total": 0.01}
    scheduled[0].close()


def test_finalizer_rejects_open_string_attribution_and_ambiguous_trust() -> None:
    result = CoreResult(answer="answer")
    with pytest.raises(TypeError, match="ProducerOrigin"):
        finalize_core_result(
            result,
            producer_origin="react_pipeline",  # type: ignore[arg-type]
            trusted_bypass_reason=None,
            analytics_receipt=AnalyticsReceiptStatus.SKIPPED,
        )
    with pytest.raises(ValueError, match="allowlisted query-gate"):
        finalize_core_result(
            result,
            producer_origin=ProducerOrigin.REACT_PIPELINE,
            trusted_bypass_reason=TrustedBypassReason.DETERMINISTIC_QUERY_GATE,
            analytics_receipt=AnalyticsReceiptStatus.SKIPPED,
        )
    with pytest.raises(TypeError, match="trusted_bypass_reason"):
        finalize_core_result(
            result,
            producer_origin=ProducerOrigin.QUERY_GATE,
            trusted_bypass_reason="deterministic_query_gate",  # type: ignore[arg-type]
            analytics_receipt=AnalyticsReceiptStatus.SKIPPED,
        )
    with pytest.raises(TypeError, match="analytics_receipt"):
        finalize_core_result(
            result,
            producer_origin=ProducerOrigin.REACT_PIPELINE,
            trusted_bypass_reason=None,
            analytics_receipt="written",  # type: ignore[arg-type]
        )


def test_finalization_enums_are_closed_to_the_reviewed_contract() -> None:
    assert set(ProducerOrigin) == {
        ProducerOrigin.QUERY_GATE,
        ProducerOrigin.FAQ_CACHE,
        ProducerOrigin.SEMANTIC_CACHE,
        ProducerOrigin.MULTI_AGENT_COORDINATOR,
        ProducerOrigin.SPECIALIZED_SERVICE_ROUTER,
        ProducerOrigin.KNOWLEDGE_GRAPH,
        ProducerOrigin.REACT_PIPELINE,
        ProducerOrigin.UNKNOWN,
    }
    assert set(EvidenceProvenance) == {
        EvidenceProvenance.FAQ_CACHE,
        EvidenceProvenance.SEMANTIC_CACHE,
        EvidenceProvenance.MULTI_AGENT_COORDINATOR,
        EvidenceProvenance.SPECIALIZED_SERVICE_ROUTER,
        EvidenceProvenance.KNOWLEDGE_GRAPH,
        EvidenceProvenance.REACT_PIPELINE,
    }
    assert set(TrustedBypassReason) == {
        TrustedBypassReason.DETERMINISTIC_QUERY_GATE,
    }
    assert set(AnalyticsReceiptStatus) == {
        AnalyticsReceiptStatus.SCHEDULED,
        AnalyticsReceiptStatus.WRITTEN,
        AnalyticsReceiptStatus.SKIPPED,
        AnalyticsReceiptStatus.FAILED,
    }
    assert set(FinalizationStatus) == {
        FinalizationStatus.SHADOW_RECORDED,
        FinalizationStatus.SHADOW_INCOMPLETE,
    }


@pytest.mark.asyncio
async def test_unknown_producer_is_fail_visible_instead_of_silent_react() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    result = CoreResult(
        answer="future producer",
        sources=[{"source": "unattributed-but-structured"}],
        model_used="future-model",
        route_used="aggregate_service",
    )
    sources_before = deepcopy(result.sources)

    finalized = await core.finalize_result(result)

    assert finalized.producer_origin is ProducerOrigin.UNKNOWN
    assert finalized.evidence_provenance is None
    assert finalized.trusted_bypass_reason is None
    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE
    assert finalized.sources == sources_before


@pytest.mark.asyncio
async def test_known_producer_without_transferred_evidence_is_incomplete() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None
    result = CoreResult(
        answer="coordinator answer",
        sources=[],
        model_used="multi-agent-coordinator",
    )

    finalized = await core.finalize_result(result)

    assert finalized.producer_origin is ProducerOrigin.MULTI_AGENT_COORDINATOR
    assert finalized.evidence_provenance is None
    assert finalized.trusted_bypass_reason is None
    assert finalized.finalization_status is FinalizationStatus.SHADOW_INCOMPLETE


@pytest.mark.asyncio
async def test_analytics_uses_answer_and_abstain_decision_not_source_count() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    core._log_query_analytics = AsyncMock()
    result = CoreResult(
        answer="I cannot answer safely.",
        sources=[{"source": "retrieved-source"}],
        model_used="faq_cache",
        abstain=True,
    )
    core._process_query_core_unfinalized = AsyncMock(
        return_value=FinalizationContext(
            result=result,
            producer_origin=ProducerOrigin.FAQ_CACHE,
        )
    )
    scheduled: list[asyncio.Task[AnalyticsReceiptStatus]] = []

    def capture_spawn(
        coro: Any,
        *,
        name: str | None = None,
    ) -> asyncio.Task[AnalyticsReceiptStatus]:
        task = asyncio.create_task(coro, name=name)
        scheduled.append(task)
        return task

    with patch.object(orchestrator_core_module, "spawn", side_effect=capture_spawn):
        finalized = await core.process_query_core(
            query="abstain query",
            user_id=None,
            conversation_history=None,
            start_time=0.0,
        )

    await asyncio.gather(*scheduled)

    assert finalized.analytics_receipt is AnalyticsReceiptStatus.SCHEDULED
    assert core._log_query_analytics.call_args.kwargs["response_generated"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repo_result", "repo_error", "expected_receipt"),
    [
        ("query-id", None, AnalyticsReceiptStatus.WRITTEN),
        (None, None, AnalyticsReceiptStatus.FAILED),
        (None, RuntimeError("repository failed"), AnalyticsReceiptStatus.FAILED),
        (None, TimeoutError("repository timeout"), AnalyticsReceiptStatus.FAILED),
    ],
)
async def test_canonical_analytics_receipt_reflects_repository_outcome(
    repo_result: str | None,
    repo_error: Exception | None,
    expected_receipt: AnalyticsReceiptStatus,
) -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = object()
    repository = MagicMock()
    repository.log_query = AsyncMock(return_value=repo_result, side_effect=repo_error)

    with patch.object(
        orchestrator_core_module,
        "QueryAnalyticsRepository",
        return_value=repository,
    ):
        receipt = await core._log_query_analytics(
            query="analytics contract",
            user_id=None,
            session_id=None,
            collections_used=set(),
            sources=[],
            model_used="contract-model",
            token_usage=orchestrator_core_module.TokenUsage(),
            timings={"total": 0.01},
            response_generated=True,
        )

    assert receipt is expected_receipt
    assert repository.log_query.call_args.kwargs["response_generated"] is True


@pytest.mark.asyncio
async def test_canonical_analytics_is_skipped_without_database_pool() -> None:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.db_pool = None

    receipt = await core._log_query_analytics(
        query="analytics contract",
        user_id=None,
        session_id=None,
        collections_used=set(),
        sources=[],
        model_used="contract-model",
        token_usage=orchestrator_core_module.TokenUsage(),
        timings={},
        response_generated=False,
    )

    assert receipt is AnalyticsReceiptStatus.SKIPPED


def test_pure_finalizer_p95_is_below_ten_milliseconds() -> None:
    durations_ns: list[int] = []
    for _ in range(500):
        result = CoreResult(answer="stable", sources=[{"source": "test"}])
        started_ns = time.perf_counter_ns()
        finalize_core_result(
            result,
            producer_origin=ProducerOrigin.REACT_PIPELINE,
            trusted_bypass_reason=None,
            analytics_receipt=AnalyticsReceiptStatus.SKIPPED,
        )
        durations_ns.append(time.perf_counter_ns() - started_ns)

    p95_ns = sorted(durations_ns)[int(len(durations_ns) * 0.95)]
    assert p95_ns < 10_000_000


def test_raw_early_returns_are_sealed_behind_one_public_wrapper() -> None:
    source = inspect.getsource(orchestrator_core_module)
    tree = ast.parse(source)
    core_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "OrchestratorCore"
    )
    methods = {
        node.name: node
        for node in core_class.body
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
    }
    public = methods["process_query_core"]
    implementation = methods["_process_query_core_unfinalized"]

    public_returns = [node for node in public.body if isinstance(node, ast.Return)]
    assert len(public_returns) == 1
    assert "_finalize_process_context" in ast.unparse(public_returns[0])

    authority_minters = [
        method_name
        for method_name, method in methods.items()
        for node in ast.walk(method)
        if isinstance(node, ast.FunctionDef) and node.name == "_claim_finalization_analytics_once"
    ]
    assert authority_minters == ["process_query_core"]

    raw_returns = [
        node
        for node in ast.walk(implementation)
        if isinstance(node, ast.Return) and node.value is not None
    ]
    assert raw_returns
    assert all(
        isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "FinalizationContext"
        for node in raw_returns
    ), "every user-visible early return must carry a closed internal producer context"

    callers: set[str] = set()
    for method_name, method in methods.items():
        for node in ast.walk(method):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "_process_query_core_unfinalized":
                    callers.add(method_name)
    assert callers == {"process_query_core"}
