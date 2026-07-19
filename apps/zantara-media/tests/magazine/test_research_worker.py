from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from zantara_media.magazine.research_worker import (
    ResearchClaim,
    ResearchEvidence,
    ResearchLeaseLostError,
    ResearchWorker,
    ResearchWorkerError,
)


CLAIMED_JOB: dict[str, Any] = {
    "schema_version": "research-job.v1",
    "job_id": "research-job-0123456789abcdef",
    "request_hash": "a" * 64,
    "mode": "notebook_insight",
    "request": {
        "schema_version": "research-request.v1",
        "mode": "notebook_insight",
        "topic_ids": ["topic:visa-policy"],
        "entity_ids": [],
        "index_tokens": [],
        "template": "explain",
        "facets": {
            "domains": ["immigration"],
            "source_system_ids": ["notebooklm"],
            "evidence_types": ["official"],
            "confidence": ["normal"],
            "lifecycle_states": ["published"],
            "languages": ["en"],
        },
    },
    "status": "claimed",
    "claim_token": "claim-token-0123456789abcdef",
    "fencing_token": 1,
    "lease_deadline": "2026-07-19T05:00:00.000Z",
}


class FakeTransport:
    def __init__(
        self,
        job: Mapping[str, Any] | None = CLAIMED_JOB,
        *,
        fail_heartbeat_at: int | None = None,
    ) -> None:
        self.job = job
        self.results: list[Mapping[str, Any]] = []
        self.heartbeats: list[tuple[str, str, int]] = []
        self.fail_heartbeat_at = fail_heartbeat_at

    async def claim_research_job(
        self, *, worker_id: str, lease_seconds: int
    ) -> Mapping[str, Any] | None:
        assert worker_id == "worker:pro-magazine"
        assert lease_seconds == 120
        return self.job

    async def heartbeat_research_job(
        self, *, job_id: str, claim_token: str, fencing_token: int, lease_seconds: int
    ) -> Mapping[str, Any]:
        self.heartbeats.append((job_id, claim_token, fencing_token))
        if self.fail_heartbeat_at == len(self.heartbeats):
            raise RuntimeError("CAS conflict")
        return {"ok": True}

    async def submit_research_result(
        self, *, job_id: str, result: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.results.append(result)
        return {"ok": True, "status": "created"}


class NotebookAdapter:
    notebook_uuid = "local-notebook-uuid-must-never-cross-boundary"

    async def execute(self, request: Mapping[str, Any]) -> tuple[str, list[ResearchClaim]]:
        assert "question" not in request
        return (
            "The official source records a material visa policy change.",
            [
                ResearchClaim(
                    claim_id="claim:visa-change-1",
                    kind="fact",
                    text="The issuing authority records the policy change.",
                    as_of="2026-07-19",
                    evidence=(
                        ResearchEvidence(
                            evidence_id="evidence:official-visa-change",
                            publisher="Directorate General of Immigration",
                            citation="Official policy notice, 19 July 2026",
                            canonical_url="https://www.imigrasi.go.id/",
                            source_type="official",
                            published_at="2026-07-19",
                        ),
                    ),
                )
            ],
        )


@pytest.mark.asyncio
async def test_worker_claims_executes_dlp_binds_evidence_and_posts_closed_result() -> None:
    transport = FakeTransport()

    async def dlp_gate(text: str) -> bool:
        assert "local-notebook-uuid" not in text
        return True

    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": NotebookAdapter()},
        dlp_gate=dlp_gate,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await worker.run_once() is True
    result = transport.results[0]
    assert result["schema_version"] == "research-result.v1"
    assert result["status"] == "completed"
    assert result["claims"][0]["evidence"]
    serialized = str(result)
    assert "notebook_uuid" not in serialized
    assert "local-notebook-uuid" not in serialized
    assert set(result) == {
        "schema_version",
        "job_id",
        "request_hash",
        "mode",
        "status",
        "completed_at",
        "summary",
        "claims",
        "failure",
        "claim_token",
        "fencing_token",
    }


@pytest.mark.asyncio
async def test_worker_posts_safe_failure_receipt_without_raw_adapter_error() -> None:
    class BrokenAdapter:
        async def execute(self, request: Mapping[str, Any]) -> tuple[str, list[ResearchClaim]]:
            raise RuntimeError("passport A1234567 belonged to a private client")

    transport = FakeTransport()
    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": BrokenAdapter()},
        dlp_gate=lambda text: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await worker.run_once() is True
    result = transport.results[0]
    assert result["status"] == "failed"
    assert result["failure"] == {"code": "source_unavailable"}
    assert "passport" not in str(result)
    assert result["summary"] is None
    assert result["claims"] == []


@pytest.mark.asyncio
async def test_worker_rejects_unbound_claim_and_dlp_failure_with_safe_codes() -> None:
    class UnboundAdapter:
        async def execute(self, request: Mapping[str, Any]) -> tuple[str, list[ResearchClaim]]:
            return (
                "Unsupported assertion.",
                [
                    ResearchClaim(
                        claim_id="claim:unsupported",
                        kind="fact",
                        text="Unsupported assertion.",
                        evidence=(),
                    )
                ],
            )

    transport = FakeTransport()
    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": UnboundAdapter()},
        dlp_gate=lambda text: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    await worker.run_once()
    assert transport.results[0]["failure"] == {"code": "evidence_missing"}

    transport = FakeTransport()

    async def reject_dlp(text: str) -> bool:
        return False

    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": NotebookAdapter()},
        dlp_gate=reject_dlp,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    await worker.run_once()
    assert transport.results[0]["failure"] == {"code": "dlp_rejected"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Private client Jane Doe lives at 17 Sunset Lane, Canggu.",
        "The government announced a public tourism regulation.",
    ],
)
@pytest.mark.parametrize("failure_mode", ["unavailable", "malformed"])
async def test_default_dlp_classifier_uncertainty_posts_only_sanitized_failure(
    text: str, failure_mode: str
) -> None:
    class TextAdapter:
        async def execute(self, request: Mapping[str, Any]) -> tuple[str, list[ResearchClaim]]:
            return (
                text,
                [
                    ResearchClaim(
                        claim_id="claim:classifier-uncertainty",
                        kind="fact",
                        text=text,
                        evidence=(
                            ResearchEvidence(
                                evidence_id="evidence:classifier-uncertainty",
                                publisher="Public Authority",
                                citation="Public notice",
                                canonical_url="https://example.org/notice",
                                source_type="official",
                            ),
                        ),
                    )
                ],
            )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    if failure_mode == "unavailable":
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("PRIVATE_CLASSIFIER_DETAIL"))
    else:
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"response": "PRIVATE_CLASSIFIER_DETAIL"}
        mock_client.post = AsyncMock(return_value=response)

    transport = FakeTransport()
    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": TextAdapter()},
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    with patch("zantara_media.security.dlp.httpx.AsyncClient", return_value=mock_client):
        assert await worker.run_once() is True

    result = transport.results[0]
    assert result["status"] == "failed"
    assert result["failure"] == {"code": "dlp_rejected"}
    assert result["summary"] is None
    assert result["claims"] == []
    assert text not in str(result)
    assert "PRIVATE_CLASSIFIER_DETAIL" not in str(result)


def test_worker_model_rejects_unknown_modes_and_private_identifiers() -> None:
    with pytest.raises(ResearchWorkerError):
        ResearchWorker.validate_job({**CLAIMED_JOB, "mode": "freeform"})
    leaked = {
        **CLAIMED_JOB,
        "request": {**CLAIMED_JOB["request"], "notebook_uuid": "private"},
    }
    with pytest.raises(ResearchWorkerError):
        ResearchWorker.validate_job(leaked)
    wrong_notebook_source = {
        **CLAIMED_JOB,
        "request": {
            **CLAIMED_JOB["request"],
            "facets": {
                **CLAIMED_JOB["request"]["facets"],
                "source_system_ids": ["regulatory-watcher", "notebooklm"],
            },
        },
    }
    with pytest.raises(ResearchWorkerError, match="NotebookLM only"):
        ResearchWorker.validate_job(wrong_notebook_source)


def test_numeric_claim_requires_unit_value_as_of_and_evidence() -> None:
    evidence = (
        ResearchEvidence(
            evidence_id="evidence:official-number",
            publisher="BKPM",
            citation="Official statistics",
            canonical_url="https://www.bkpm.go.id/",
            source_type="official",
        ),
    )
    with pytest.raises(ResearchWorkerError, match="as-of"):
        ResearchClaim(
            claim_id="claim:investment-share",
            kind="numeric",
            text="The share is 25 percent.",
            numeric_value="25",
            numeric_unit="percent",
            evidence=evidence,
        ).projection()
    assert (
        ResearchClaim(
            claim_id="claim:investment-share",
            kind="numeric",
            text="The share is 25 percent.",
            numeric_value="25",
            numeric_unit="percent",
            as_of="2026-07-19",
            evidence=evidence,
        ).projection()["as_of"]
        == "2026-07-19"
    )


@pytest.mark.asyncio
async def test_immediate_adapter_keeps_heartbeat_through_projection_dlp_and_submission() -> None:
    phase = {"name": "claimed"}
    heartbeat_phases: list[str] = []

    class SlowProjectionClaim:
        def __init__(self, claim: ResearchClaim) -> None:
            self._claim = claim

        def projection(self) -> dict[str, Any]:
            phase["name"] = "projection"
            time.sleep(0.025)
            return self._claim.projection()

    class ImmediateAdapter(NotebookAdapter):
        async def execute(self, request: Mapping[str, Any]) -> tuple[str, list[Any]]:
            summary, claims = await super().execute(request)
            return summary, [SlowProjectionClaim(claims[0])]

    class SlowSubmitTransport(FakeTransport):
        async def heartbeat_research_job(
            self,
            *,
            job_id: str,
            claim_token: str,
            fencing_token: int,
            lease_seconds: int,
        ) -> Mapping[str, Any]:
            heartbeat_phases.append(phase["name"])
            return await super().heartbeat_research_job(
                job_id=job_id,
                claim_token=claim_token,
                fencing_token=fencing_token,
                lease_seconds=lease_seconds,
            )

        async def submit_research_result(
            self, *, job_id: str, result: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            phase["name"] = "submission"
            await asyncio.sleep(0.025)
            response = await super().submit_research_result(job_id=job_id, result=result)
            phase["name"] = "acknowledged"
            return response

    async def slow_reject_dlp(text: str) -> bool:
        phase["name"] = "dlp"
        await asyncio.sleep(0.025)
        return False

    transport = SlowSubmitTransport()
    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": ImmediateAdapter()},
        dlp_gate=slow_reject_dlp,
        now=lambda: "2026-07-19T04:30:00.000Z",
        heartbeat_interval_seconds=0.003,
    )
    assert await worker.run_once() is True
    assert heartbeat_phases.count("projection") >= 2
    assert heartbeat_phases.count("dlp") >= 2
    assert heartbeat_phases.count("submission") >= 2
    assert len(transport.results) == 1
    assert transport.results[0]["failure"] == {"code": "dlp_rejected"}
    heartbeat_count = len(transport.heartbeats)
    await asyncio.sleep(0.015)
    assert len(transport.heartbeats) == heartbeat_count


@pytest.mark.asyncio
async def test_cancelled_or_stale_lease_stops_adapter_and_never_submits() -> None:
    adapter_cancelled = asyncio.Event()

    class BlockingAdapter:
        async def execute(self, request: Mapping[str, Any]) -> tuple[str, list[ResearchClaim]]:
            try:
                await asyncio.sleep(10)
            finally:
                adapter_cancelled.set()
            raise AssertionError("unreachable")

    transport = FakeTransport(fail_heartbeat_at=2)
    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": BlockingAdapter()},
        dlp_gate=lambda text: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
        heartbeat_interval_seconds=0.005,
    )
    with pytest.raises(ResearchLeaseLostError):
        await worker.run_once()
    assert adapter_cancelled.is_set()
    assert transport.results == []


@pytest.mark.asyncio
async def test_lease_loss_cancels_inflight_result_submission_without_stale_submit() -> None:
    submission_started = asyncio.Event()
    submission_cancelled = asyncio.Event()

    class BlockingSubmitTransport(FakeTransport):
        async def submit_research_result(
            self, *, job_id: str, result: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            submission_started.set()
            try:
                await asyncio.sleep(10)
            finally:
                submission_cancelled.set()
            raise AssertionError("unreachable")

    transport = BlockingSubmitTransport(fail_heartbeat_at=2)
    worker = ResearchWorker(
        transport=transport,
        adapters={"notebook_insight": NotebookAdapter()},
        dlp_gate=lambda text: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
        heartbeat_interval_seconds=0.005,
    )
    with pytest.raises(ResearchLeaseLostError):
        await asyncio.wait_for(worker.run_once(), timeout=0.2)
    assert submission_started.is_set()
    assert submission_cancelled.is_set()
    assert transport.results == []
