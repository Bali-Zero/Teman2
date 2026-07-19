"""Pro-side worker for closed, public-intelligence Magazine research jobs.

The worker resolves local source and NotebookLM registries behind the Pro boundary.
Sites receives only a DLP-passed projection or a content-free failure receipt.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from zantara_media.security.dlp import dlp_check

ResearchMode = Literal["search", "compare", "timeline", "notebook_insight"]
ClaimKind = Literal["fact", "numeric", "analysis"]
SourceType = Literal["official", "journalism", "research", "dataset"]
FailureCode = Literal[
    "source_unavailable",
    "dlp_rejected",
    "evidence_missing",
    "invalid_result",
    "internal_error",
]

_MODES: frozenset[str] = frozenset({"search", "compare", "timeline", "notebook_insight"})
_TEMPLATES: frozenset[str] = frozenset({"explain", "compare", "timeline"})
_STABLE_ID = re.compile(r"^(?:topic|entity|token):[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{15,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ResearchWorkerError(ValueError):
    """Closed-contract or worker-boundary violation."""


class EvidenceMissingError(ResearchWorkerError):
    """A factual, numeric, or analytical claim has no evidence binding."""


class ResearchLeaseLostError(RuntimeError):
    """The Sites lease was cancelled, expired, or fenced by another worker."""


@dataclass(frozen=True, slots=True)
class ResearchEvidence:
    evidence_id: str
    publisher: str
    citation: str
    canonical_url: str | None
    source_type: SourceType
    published_at: str | None = None

    def projection(self) -> dict[str, Any]:
        if not self.evidence_id.startswith("evidence:"):
            raise ResearchWorkerError("invalid evidence identifier")
        if not self.publisher.strip() or not self.citation.strip():
            raise ResearchWorkerError("invalid evidence projection")
        if self.source_type not in {"official", "journalism", "research", "dataset"}:
            raise ResearchWorkerError("invalid evidence source type")
        if self.canonical_url is not None and not self.canonical_url.startswith("https://"):
            raise ResearchWorkerError("evidence URL must use HTTPS")
        return {
            "evidence_id": self.evidence_id,
            "publisher": self.publisher,
            "citation": self.citation,
            "canonical_url": self.canonical_url,
            "source_type": self.source_type,
            "published_at": self.published_at,
        }


@dataclass(frozen=True, slots=True)
class ResearchClaim:
    claim_id: str
    kind: ClaimKind
    text: str
    evidence: tuple[ResearchEvidence, ...]
    numeric_value: str | None = None
    numeric_unit: str | None = None
    as_of: str | None = None

    def projection(self) -> dict[str, Any]:
        if not self.claim_id.startswith("claim:") or not self.text.strip():
            raise ResearchWorkerError("invalid research claim")
        if self.kind not in {"fact", "numeric", "analysis"}:
            raise ResearchWorkerError("invalid research claim kind")
        if not self.evidence or len(self.evidence) > 12:
            raise EvidenceMissingError("research claim has no evidence")
        if self.kind == "numeric" and (
            self.numeric_value is None or self.numeric_unit is None or self.as_of is None
        ):
            raise EvidenceMissingError("numeric claim lacks value, unit, or as-of date")
        return {
            "claim_id": self.claim_id,
            "kind": self.kind,
            "text": self.text,
            "numeric_value": self.numeric_value,
            "numeric_unit": self.numeric_unit,
            "as_of": self.as_of,
            "evidence": [item.projection() for item in self.evidence],
        }


class ResearchAdapter(Protocol):
    async def execute(self, request: Mapping[str, Any]) -> tuple[str, Sequence[ResearchClaim]]: ...


class ResearchTransport(Protocol):
    async def claim_research_job(
        self, *, worker_id: str, lease_seconds: int
    ) -> Mapping[str, Any] | None: ...

    async def heartbeat_research_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        fencing_token: int,
        lease_seconds: int,
    ) -> Mapping[str, Any]: ...

    async def submit_research_result(
        self, *, job_id: str, result: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


DlpGate = Callable[[str], bool | Awaitable[bool]]
Clock = Callable[[], str]


async def _default_dlp_gate(text: str) -> bool:
    result = await dlp_check(text, "magazine-research-projection.json")
    return not result.has_pii and not result.indeterminate


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ResearchWorkerError(f"invalid {label}")


def _stable_id_list(value: Any, prefixes: frozenset[str]) -> list[str]:
    if not isinstance(value, list) or len(value) > 8:
        raise ResearchWorkerError("invalid stable identifier list")
    if any(
        not isinstance(item, str)
        or _STABLE_ID.fullmatch(item) is None
        or item.split(":", 1)[0] not in prefixes
        for item in value
    ):
        raise ResearchWorkerError("invalid stable identifier")
    if len(set(value)) != len(value):
        raise ResearchWorkerError("duplicate stable identifier")
    return cast(list[str], value)


class ResearchWorker:
    """Claims Sites jobs, executes local adapters, and emits sanitized receipts."""

    def __init__(
        self,
        *,
        transport: ResearchTransport,
        adapters: Mapping[ResearchMode, ResearchAdapter],
        dlp_gate: DlpGate = _default_dlp_gate,
        now: Clock,
        worker_id: str = "worker:pro-magazine",
        lease_seconds: int = 120,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self._transport = transport
        self._adapters = dict(adapters)
        self._dlp_gate = dlp_gate
        self._now = now
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        interval = heartbeat_interval_seconds or max(1.0, lease_seconds / 3)
        if interval <= 0:
            raise ResearchWorkerError("invalid heartbeat interval")
        self._heartbeat_interval_seconds = interval

    @staticmethod
    def validate_job(value: Mapping[str, Any]) -> Mapping[str, Any]:
        _exact_keys(
            value,
            {
                "schema_version",
                "job_id",
                "request_hash",
                "mode",
                "request",
                "status",
                "claim_token",
                "fencing_token",
                "lease_deadline",
            },
            "research job",
        )
        mode = value.get("mode")
        request = value.get("request")
        if (
            value.get("schema_version") != "research-job.v1"
            or not isinstance(value.get("job_id"), str)
            or not isinstance(value.get("request_hash"), str)
            or _SHA256.fullmatch(cast(str, value["request_hash"])) is None
            or mode not in _MODES
            or value.get("status") != "claimed"
            or not isinstance(value.get("claim_token"), str)
            or _TOKEN.fullmatch(cast(str, value["claim_token"])) is None
            or not isinstance(value.get("fencing_token"), int)
            or cast(int, value["fencing_token"]) < 1
            or not isinstance(request, Mapping)
        ):
            raise ResearchWorkerError("invalid research job")
        _exact_keys(
            request,
            {
                "schema_version",
                "mode",
                "topic_ids",
                "entity_ids",
                "index_tokens",
                "template",
                "facets",
            },
            "research request",
        )
        if request.get("schema_version") != "research-request.v1" or request.get("mode") != mode:
            raise ResearchWorkerError("invalid research request")
        topics = _stable_id_list(request.get("topic_ids"), frozenset({"topic"}))
        entities = _stable_id_list(request.get("entity_ids"), frozenset({"entity"}))
        tokens = _stable_id_list(request.get("index_tokens"), frozenset({"token"}))
        if not topics and not entities and not tokens:
            raise ResearchWorkerError("research request has no selected subject")
        if mode == "notebook_insight":
            if (
                request.get("template") not in _TEMPLATES
                or len(topics) + len(entities) != 1
                or tokens
            ):
                raise ResearchWorkerError("invalid notebook insight request")
        elif request.get("template") is not None:
            raise ResearchWorkerError("unexpected notebook template")
        if mode == "compare" and len(topics) + len(entities) != 2:
            raise ResearchWorkerError("compare requires exactly two public subjects")
        if mode == "timeline" and len(topics) + len(entities) != 1:
            raise ResearchWorkerError("timeline requires exactly one public subject")
        facets = request.get("facets")
        if not isinstance(facets, Mapping):
            raise ResearchWorkerError("invalid research facets")
        _exact_keys(
            facets,
            {
                "domains",
                "source_system_ids",
                "evidence_types",
                "confidence",
                "lifecycle_states",
                "languages",
            },
            "research facets",
        )
        allowed_facets: dict[str, set[str]] = {
            "domains": {"immigration", "company", "tax", "property", "compliance"},
            "source_system_ids": {
                "intel-lake",
                "mata-garuda",
                "regulatory-watcher",
                "notebooklm",
            },
            "evidence_types": {"official", "journalism", "research", "dataset"},
            "confidence": {"normal", "cautious", "abstain"},
            "lifecycle_states": {"published", "amended", "superseded"},
            "languages": {"en", "id"},
        }
        for key, allowed in allowed_facets.items():
            selected = facets.get(key)
            if (
                not isinstance(selected, list)
                or len(selected) > 8
                or any(not isinstance(item, str) or item not in allowed for item in selected)
                or len(set(selected)) != len(selected)
            ):
                raise ResearchWorkerError("invalid research facets")
        source_system_ids = facets.get("source_system_ids")
        if not source_system_ids:
            raise ResearchWorkerError("research request requires a source system")
        if mode == "notebook_insight" and source_system_ids != ["notebooklm"]:
            raise ResearchWorkerError("notebook insight requires NotebookLM only")
        return value

    async def _passes_dlp(self, projection: Mapping[str, Any]) -> bool:
        # Local serialization is ephemeral and never logged or transmitted before the gate.
        candidate = json.dumps(projection, ensure_ascii=False, sort_keys=True)
        outcome = self._dlp_gate(candidate)
        return bool(await outcome) if inspect.isawaitable(outcome) else bool(outcome)

    def _failure(self, job: Mapping[str, Any], code: FailureCode) -> dict[str, Any]:
        return {
            "schema_version": "research-result.v1",
            "job_id": job["job_id"],
            "request_hash": job["request_hash"],
            "mode": job["mode"],
            "status": "failed",
            "completed_at": self._now(),
            "summary": None,
            "claims": [],
            "failure": {"code": code},
            "claim_token": job["claim_token"],
            "fencing_token": job["fencing_token"],
        }

    async def _heartbeat_loop(self, job: Mapping[str, Any]) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval_seconds)
            await self._renew_lease(job)

    async def _renew_lease(self, job: Mapping[str, Any]) -> None:
        await self._transport.heartbeat_research_job(
            job_id=cast(str, job["job_id"]),
            claim_token=cast(str, job["claim_token"]),
            fencing_token=cast(int, job["fencing_token"]),
            lease_seconds=self._lease_seconds,
        )

    async def _run_with_heartbeat(
        self, job: Mapping[str, Any], operation: Callable[[], Awaitable[None]]
    ) -> None:
        try:
            await self._renew_lease(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ResearchLeaseLostError("research lease lost") from exc

        heartbeat_task = asyncio.create_task(self._heartbeat_loop(job))
        operation_task = asyncio.create_task(operation())
        try:
            done, _ = await asyncio.wait(
                {operation_task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if operation_task in done:
                await operation_task
                return
            try:
                lease_error = heartbeat_task.exception()
            except asyncio.CancelledError as exc:
                lease_error = exc
            operation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await operation_task
            raise ResearchLeaseLostError("research lease lost") from lease_error
        finally:
            for task in (operation_task, heartbeat_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation_task, heartbeat_task, return_exceptions=True)

    async def _process_and_submit(self, job: Mapping[str, Any]) -> None:
        adapter = self._adapters.get(cast(ResearchMode, job["mode"]))
        if adapter is None:
            result = self._failure(job, "invalid_result")
        else:
            try:
                summary, claims = await adapter.execute(cast(Mapping[str, Any], job["request"]))
                if not isinstance(summary, str) or not summary.strip() or len(summary) > 2000:
                    raise ResearchWorkerError("invalid research summary")
                if len(claims) > 50:
                    raise ResearchWorkerError("too many research claims")
                projections = await asyncio.to_thread(
                    lambda: [claim.projection() for claim in claims]
                )
                candidate: dict[str, Any] = {
                    "schema_version": "research-result.v1",
                    "job_id": job["job_id"],
                    "request_hash": job["request_hash"],
                    "mode": job["mode"],
                    "status": "completed",
                    "completed_at": self._now(),
                    "summary": summary,
                    "claims": projections,
                    "failure": None,
                    "claim_token": job["claim_token"],
                    "fencing_token": job["fencing_token"],
                }
                if len(json.dumps(candidate, ensure_ascii=False).encode("utf-8")) > 128_000:
                    raise ResearchWorkerError("research result exceeds size limit")
                result = (
                    candidate
                    if await self._passes_dlp(candidate)
                    else self._failure(job, "dlp_rejected")
                )
            except ResearchLeaseLostError:
                raise
            except EvidenceMissingError:
                result = self._failure(job, "evidence_missing")
            except ResearchWorkerError:
                result = self._failure(job, "invalid_result")
            except Exception:
                # Raw adapter or DLP errors can contain private source fragments.
                result = self._failure(job, "source_unavailable")
        await self._transport.submit_research_result(job_id=cast(str, job["job_id"]), result=result)

    async def run_once(self) -> bool:
        raw_job = await self._transport.claim_research_job(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
        )
        if raw_job is None:
            return False
        job = self.validate_job(raw_job)
        await self._run_with_heartbeat(
            job,
            lambda: self._process_and_submit(job),
        )
        return True
