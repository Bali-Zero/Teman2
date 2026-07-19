from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from zantara_media.magazine.research_adapters import ResearchSourceUnavailableError
from zantara_media.magazine.research_runtime import (
    AsyncNlmClient,
    PollSettings,
    ResearchRuntimeConfigError,
    create_research_runtime,
    run_poll_loop,
)
from zantara_media.magazine.research_worker import ResearchWorkerError


VERSIONS = {
    "intel-lake": "intel-public.v1",
    "mata-garuda": "mata-garuda-public.v1",
    "notebooklm": "notebooklm-public.v1",
    "regulatory-watcher": "regulatory-public.v1",
}
NOTEBOOK_REF = "123e4567-e89b-42d3-a456-426614174000"


def _evidence(system_id: str, suffix: str, *, source_type: str = "official") -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "evidence_id": f"evidence-{system_id}-{suffix}",
        "root_source_id": f"root-{system_id}-{suffix}",
        "canonical_url": f"https://public.example.org/{system_id}/{suffix}",
        "publisher": f"{system_id} Public Authority",
        "document_citation": f"Public notice {suffix}",
        "published_at": "2026-07-18T08:00:00Z",
        "retrieved_at": "2026-07-18T09:00:00Z",
        "source_type": source_type,
        "primary_document_status": ("verified" if source_type == "official" else "not-primary"),
        "root_resolution_status": "resolved",
        "independence_verdict": "independent",
        "evidence_note": "Public issuing-authority notice.",
        "upstream_root_source_ids": [],
        "syndication_group_fingerprint": f"sg-{system_id}-{suffix}",
        "independence_ruleset_version": "independence.v1",
        "independence_reason": "issuing-authority-primary-document",
        "counts_toward_breaking": True,
    }
    return evidence


def _candidate(
    system_id: str,
    suffix: str,
    subject: str,
    *,
    numeric: bool = False,
    updated_at: str = "2026-07-18T09:00:00Z",
    domain: str = "immigration",
    language: str = "en",
    evidence_type: str = "official",
    confidence: str | None = "high",
    confidence_score: float | None = None,
    lifecycle_state: str | None = "verified",
) -> dict[str, Any]:
    claim = {
        "claim_id": f"claim-{system_id}-{suffix}",
        "claim_kind": "numeric" if numeric else "fact",
        "legal_effect": "none",
        "normalized_text": (
            f"{subject} has a 30 day public review period."
            if numeric
            else f"{subject} is covered by the public notice."
        ),
        "numeric_value": "30" if numeric else None,
        "numeric_unit": "days" if numeric else None,
        "as_of": "2026-07-18",
        "evidence_ids": [f"evidence-{system_id}-{suffix}"],
        "breaking_gate": "official-primary",
    }
    candidate: dict[str, Any] = {
        "public_id": f"public-{system_id}-{suffix}",
        "slug": f"{system_id}-{suffix}",
        "language": language,
        "domain": domain,
        "severity": "high",
        "first_seen_at": "2026-07-18T08:30:00Z",
        "event_occurred_at": "2026-07-18T08:00:00Z",
        "updated_at": updated_at,
        "title": f"{subject} public update",
        "deck": f"An official update about {subject}.",
        "summary": f"Sanitized public information about {subject}.",
        "why_it_matters": f"Operators following {subject} should review the notice.",
        "curiosity_text": None,
        "claims": [claim],
        "evidence_refs": [_evidence(system_id, suffix, source_type=evidence_type)],
        "legal_effect_claim_ids": [],
        "asset_digests": [],
        "novelty": 0.8,
        "recency": 0.9,
        "operational_impact": 0.8,
        "expected_current_version": 0,
        **({"record_kind": "insight"} if system_id == "notebooklm" else {}),
    }
    if confidence is not None:
        candidate["confidence"] = confidence
    if confidence_score is not None:
        candidate["confidence_score"] = confidence_score
    if lifecycle_state is not None:
        candidate["lifecycle_state"] = lifecycle_state
    return candidate


def _write_projection(directory: Path, system_id: str, candidates: list[dict[str, Any]]) -> Path:
    path = directory / f"{system_id}.public.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "magazine-public-projection.v1",
                "source_schema_version": VERSIONS[system_id],
                "system_id": system_id,
                "cutoff": "2026-07-19T00:00:00.000Z",
                "watermark": f"wm-{system_id}",
                "collector_run": {
                    "schema_version": "collector-run.v1",
                    "run_id": f"run-{system_id}",
                    "collector_id": "daily-public-projection",
                    "started_at": "2026-07-18T23:59:00Z",
                    "completed_at": "2026-07-19T00:00:00Z",
                    "status": "healthy",
                    "freshness": "fresh",
                    "items_seen": len(candidates),
                    "items_eligible": len(candidates),
                    "source_count": 1,
                    "unreachable_source_count": 0,
                    "watermark": f"wm-{system_id}",
                    "verified_at": "2026-07-19T00:00:00Z",
                },
                "candidates": candidates,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_registry(
    tmp_path: Path,
    *,
    overrides: Mapping[str, Any] | None = None,
    candidates_by_system: Mapping[str, list[dict[str, Any]]] | None = None,
) -> Path:
    selected = dict(candidates_by_system or {})
    projection_paths = {
        "intel-lake": str(
            _write_projection(
                tmp_path,
                "intel-lake",
                selected.get(
                    "intel-lake",
                    [_candidate("intel-lake", "golden", "Golden Visa", numeric=True)],
                ),
            )
        ),
        "mata-garuda": str(
            _write_projection(
                tmp_path,
                "mata-garuda",
                selected.get(
                    "mata-garuda",
                    [_candidate("mata-garuda", "investment", "Investment Permit")],
                ),
            )
        ),
        "notebooklm": str(
            _write_projection(
                tmp_path,
                "notebooklm",
                selected.get("notebooklm", [_candidate("notebooklm", "golden", "Golden Visa")]),
            )
        ),
        "regulatory-watcher": str(
            _write_projection(
                tmp_path,
                "regulatory-watcher",
                selected.get(
                    "regulatory-watcher",
                    [
                        _candidate("regulatory-watcher", "golden", "Golden Visa"),
                        _candidate(
                            "regulatory-watcher",
                            "future",
                            "Golden Visa",
                            updated_at="2026-07-20T00:00:00Z",
                        ),
                    ],
                ),
            )
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": "magazine-research-sources.v1",
        "projection_paths": projection_paths,
        "subjects": {
            "topic:golden-visa": {
                "label": "Golden Visa",
                "search_terms": ["golden visa"],
                "notebook_ref": NOTEBOOK_REF,
            },
            "entity:investment-permit": {
                "label": "Investment Permit",
                "search_terms": ["investment permit"],
                "notebook_ref": None,
            },
        },
    }
    if overrides:
        payload.update(overrides)
    path = tmp_path / "research-sources.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _request(mode: str) -> dict[str, Any]:
    topics = ["topic:golden-visa"]
    entities: list[str] = []
    template: str | None = None
    sources = ["intel-lake", "mata-garuda", "notebooklm", "regulatory-watcher"]
    if mode == "compare":
        entities = ["entity:investment-permit"]
        sources = ["mata-garuda", "intel-lake"]
    elif mode == "timeline":
        sources = ["regulatory-watcher"]
    elif mode == "notebook_insight":
        template = "explain"
        sources = ["notebooklm"]
    notebook_restricted = mode == "notebook_insight"
    return {
        "schema_version": "research-request.v1",
        "mode": mode,
        "topic_ids": topics,
        "entity_ids": entities,
        "index_tokens": [],
        "template": template,
        "facets": {
            "domains": [] if notebook_restricted else ["immigration"],
            "source_system_ids": sources,
            "evidence_types": ["official"],
            "confidence": [] if notebook_restricted else ["normal"],
            "lifecycle_states": [] if notebook_restricted else ["published"],
            "languages": [] if notebook_restricted else ["en"],
        },
    }


def _job(mode: str, sequence: int = 1) -> dict[str, Any]:
    return {
        "schema_version": "research-job.v1",
        "job_id": f"research-job-{sequence:016d}",
        "request_hash": f"{sequence:x}".rjust(64, "0"),
        "mode": mode,
        "request": _request(mode),
        "status": "claimed",
        "claim_token": f"claim-token-{sequence:016d}",
        "fencing_token": sequence,
        "lease_deadline": "2026-07-19T05:00:00.000Z",
    }


class QueueTransport:
    def __init__(self, jobs: list[Mapping[str, Any]]) -> None:
        self.jobs = list(jobs)
        self.results: list[Mapping[str, Any]] = []

    async def claim_research_job(
        self, *, worker_id: str, lease_seconds: int
    ) -> Mapping[str, Any] | None:
        return self.jobs.pop(0) if self.jobs else None

    async def heartbeat_research_job(self, **kwargs: Any) -> Mapping[str, Any]:
        return {"ok": True}

    async def submit_research_result(
        self, *, job_id: str, result: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.results.append(result)
        return {"ok": True}


class FakeNlmClient:
    def __init__(self, answer: str | None = None, error: Exception | None = None) -> None:
        self.answer = answer or json.dumps(
            {
                "schema_version": "magazine-notebook-result.v1",
                "summary": "The notebook confirms a public Golden Visa update.",
                "claims": [
                    {
                        "kind": "fact",
                        "text": "Golden Visa is covered by an official public notice.",
                        "numeric_value": None,
                        "numeric_unit": None,
                        "as_of": "2026-07-18",
                        "evidence": [
                            {
                                "publisher": "Immigration Authority",
                                "citation": "Official Golden Visa notice, 18 July 2026",
                                "canonical_url": "https://public.example.org/notices/golden-visa",
                                "source_type": "official",
                                "published_at": "2026-07-18T08:00:00Z",
                            }
                        ],
                    }
                ],
            }
        )
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def query(self, notebook_ref: str, prompt: str) -> str:
        self.calls.append((notebook_ref, prompt))
        if self.error is not None:
            raise self.error
        return self.answer


def _factory_env(registry_path: Path) -> dict[str, str]:
    return {"MAGAZINE_RESEARCH_SOURCE_CONFIG": str(registry_path)}


@pytest.mark.asyncio
async def test_production_factory_executes_all_four_modes_from_public_sources(
    tmp_path: Path,
) -> None:
    transport = QueueTransport(
        [_job("search", 1), _job("compare", 2), _job("timeline", 3), _job("notebook_insight", 4)]
    )
    nlm = FakeNlmClient()
    runtime = create_research_runtime(
        env=_factory_env(_write_registry(tmp_path)),
        transport=transport,
        nlm_client=nlm,
        dlp_gate=lambda _: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )

    for _ in range(4):
        assert await runtime.worker.run_once() is True

    assert [result["mode"] for result in transport.results] == [
        "search",
        "compare",
        "timeline",
        "notebook_insight",
    ]
    assert all(result["status"] == "completed" for result in transport.results)
    assert all(result["claims"] for result in transport.results)
    for result in transport.results:
        for claim in result["claims"]:
            assert claim["evidence"]
            if claim["kind"] == "numeric":
                assert (claim["numeric_value"], claim["numeric_unit"], claim["as_of"]) == (
                    "30",
                    "days",
                    "2026-07-18",
                )
    assert "future" not in str(transport.results[2])
    assert nlm.calls[0][0] == NOTEBOOK_REF
    assert NOTEBOOK_REF not in nlm.calls[0][1]
    assert NOTEBOOK_REF not in str(transport.results)
    await runtime.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "candidate_kwargs", "facet_overrides", "requested_sources"),
    [
        ("domain", {"domain": "tax"}, {}, ["regulatory-watcher"]),
        ("language", {"language": "id"}, {}, ["regulatory-watcher"]),
        ("evidence", {"evidence_type": "journalism"}, {}, ["regulatory-watcher"]),
        ("confidence", {"confidence": "medium"}, {}, ["regulatory-watcher"]),
        ("lifecycle", {"lifecycle_state": "amended"}, {}, ["regulatory-watcher"]),
        ("source", {}, {}, ["intel-lake"]),
        (
            "cutoff",
            {"updated_at": "2026-07-20T00:00:00Z"},
            {},
            ["regulatory-watcher"],
        ),
    ],
)
async def test_local_adapter_enforces_every_facet_and_projection_cutoff(
    tmp_path: Path,
    case_name: str,
    candidate_kwargs: Mapping[str, Any],
    facet_overrides: Mapping[str, list[str]],
    requested_sources: list[str],
) -> None:
    case_path = tmp_path / case_name
    case_path.mkdir()
    candidate = _candidate("regulatory-watcher", case_name, "Golden Visa", **candidate_kwargs)
    registry_path = _write_registry(
        case_path,
        candidates_by_system={
            "intel-lake": [],
            "mata-garuda": [],
            "notebooklm": [],
            "regulatory-watcher": [candidate],
        },
    )
    job = _job("search")
    job["request"] = {
        **job["request"],
        "facets": {
            **job["request"]["facets"],
            "source_system_ids": requested_sources,
            **facet_overrides,
        },
    }
    transport = QueueTransport([job])
    runtime = create_research_runtime(
        env=_factory_env(registry_path),
        transport=transport,
        nlm_client=FakeNlmClient(),
        dlp_gate=lambda _: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await runtime.worker.run_once() is True
    assert transport.results[0]["status"] == "completed"
    assert transport.results[0]["claims"] == []
    assert f"/{case_name}" not in str(transport.results[0])
    await runtime.aclose()


@pytest.mark.asyncio
async def test_local_adapter_combines_facets_maps_confidence_and_excludes_missing_metadata(
    tmp_path: Path,
) -> None:
    candidates = [
        _candidate("regulatory-watcher", "allowed", "Golden Visa"),
        _candidate("regulatory-watcher", "missing-confidence", "Golden Visa", confidence=None),
        _candidate("regulatory-watcher", "missing-lifecycle", "Golden Visa", lifecycle_state=None),
        _candidate(
            "regulatory-watcher",
            "cautious-threshold",
            "Golden Visa",
            confidence=None,
            confidence_score=0.60,
        ),
        _candidate(
            "regulatory-watcher",
            "abstain-threshold",
            "Golden Visa",
            confidence=None,
            confidence_score=0.14,
        ),
    ]
    registry_path = _write_registry(
        tmp_path,
        candidates_by_system={
            "intel-lake": [],
            "mata-garuda": [],
            "notebooklm": [],
            "regulatory-watcher": candidates,
        },
    )

    async def run(confidence: str, sequence: int) -> Mapping[str, Any]:
        job = _job("search", sequence)
        job["request"] = {
            **job["request"],
            "facets": {
                **job["request"]["facets"],
                "confidence": [confidence],
            },
        }
        transport = QueueTransport([job])
        runtime = create_research_runtime(
            env=_factory_env(registry_path),
            transport=transport,
            nlm_client=FakeNlmClient(),
            dlp_gate=lambda _: True,
            now=lambda: "2026-07-19T04:30:00.000Z",
        )
        assert await runtime.worker.run_once() is True
        await runtime.aclose()
        return transport.results[0]

    normal = await run("normal", 11)
    cautious = await run("cautious", 12)
    abstain = await run("abstain", 13)
    assert "allowed" in str(normal)
    assert "missing-confidence" not in str(normal)
    assert "missing-lifecycle" not in str(normal)
    assert "cautious-threshold" not in str(normal)
    assert "cautious-threshold" in str(cautious)
    assert "abstain-threshold" in str(abstain)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("facet", "selected"),
    [
        ("domains", ["immigration"]),
        ("confidence", ["normal"]),
        ("lifecycle_states", ["published"]),
        ("languages", ["en"]),
    ],
)
async def test_worker_rejects_unsupported_notebook_facets_before_nlm_call(
    tmp_path: Path, facet: str, selected: list[str]
) -> None:
    job = _job("notebook_insight")
    job["request"] = {
        **job["request"],
        "facets": {**job["request"]["facets"], facet: selected},
    }
    transport = QueueTransport([job])
    nlm = FakeNlmClient()
    runtime = create_research_runtime(
        env=_factory_env(_write_registry(tmp_path)),
        transport=transport,
        nlm_client=nlm,
        dlp_gate=lambda _: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    with pytest.raises(ResearchWorkerError, match="unsupported notebook insight facet"):
        await runtime.worker.run_once()
    assert nlm.calls == []
    assert transport.results == []
    await runtime.aclose()


@pytest.mark.asyncio
async def test_notebook_enforces_selected_evidence_type_and_fails_closed_without_match(
    tmp_path: Path,
) -> None:
    answer = json.dumps(
        {
            "schema_version": "magazine-notebook-result.v1",
            "summary": "Cited public synthesis.",
            "claims": [
                {
                    "kind": "fact",
                    "text": "Golden Visa has cited public coverage.",
                    "numeric_value": None,
                    "numeric_unit": None,
                    "as_of": "2026-07-18",
                    "evidence": [
                        {
                            "publisher": "Immigration Authority",
                            "citation": "Official notice",
                            "canonical_url": "https://public.example.org/official",
                            "source_type": "official",
                            "published_at": "2026-07-18T08:00:00Z",
                        },
                        {
                            "publisher": "Public Policy Journal",
                            "citation": "Research analysis",
                            "canonical_url": "https://public.example.org/research",
                            "source_type": "research",
                            "published_at": "2026-07-18T09:00:00Z",
                        },
                    ],
                }
            ],
        }
    )
    registry_path = _write_registry(tmp_path)
    matching = _job("notebook_insight", 21)
    matching["request"] = {
        **matching["request"],
        "facets": {**matching["request"]["facets"], "evidence_types": ["research"]},
    }
    nonmatching = _job("notebook_insight", 22)
    nonmatching["request"] = {
        **nonmatching["request"],
        "facets": {**nonmatching["request"]["facets"], "evidence_types": ["dataset"]},
    }
    transport = QueueTransport([matching, nonmatching])
    nlm = FakeNlmClient(answer=answer)
    runtime = create_research_runtime(
        env=_factory_env(registry_path),
        transport=transport,
        nlm_client=nlm,
        dlp_gate=lambda _: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await runtime.worker.run_once() is True
    matched = transport.results[0]
    assert matched["status"] == "completed"
    assert [item["source_type"] for item in matched["claims"][0]["evidence"]] == ["research"]
    assert "Allowed evidence types: research" in nlm.calls[0][1]

    assert await runtime.worker.run_once() is True
    assert transport.results[1]["status"] == "failed"
    assert transport.results[1]["failure"] == {"code": "source_unavailable"}
    await runtime.aclose()


@pytest.mark.asyncio
async def test_factory_constructs_persistent_signed_transport_when_not_injected(
    tmp_path: Path,
) -> None:
    env = {
        **_factory_env(_write_registry(tmp_path)),
        "MAGAZINE_BASE_URL": "https://sites.internal.example",
        "MAGAZINE_SIWC_BEARER_TOKEN": "siwc-test-token-0123456789",
        "MAGAZINE_HMAC_KEY_ID": "research-key-v1",
        "MAGAZINE_HMAC_SECRET": "hmac-test-secret-0123456789",
        "MAGAZINE_HMAC_AUDIENCE": "bali-zero-magazine",
        "MAGAZINE_RESEARCH_OUTCOME_JOURNAL": str(tmp_path / "outcomes.jsonl"),
    }
    runtime = create_research_runtime(env=env, nlm_client=FakeNlmClient())
    assert runtime._owned_transport is not None
    assert runtime.worker is not None
    await runtime.aclose()


@pytest.mark.asyncio
async def test_factory_jobs_reject_unknown_subject_paths_and_raw_query_keys(
    tmp_path: Path,
) -> None:
    unknown = _job("search")
    unknown["request"] = {**unknown["request"], "topic_ids": ["topic:unknown"]}
    transport = QueueTransport([unknown])
    runtime = create_research_runtime(
        env=_factory_env(_write_registry(tmp_path)),
        transport=transport,
        nlm_client=FakeNlmClient(),
        dlp_gate=lambda _: True,
        now=lambda: "2026-07-19T04:30:00.000Z",
    )
    assert await runtime.worker.run_once() is True
    assert transport.results[0]["failure"] == {"code": "invalid_result"}

    leaked = _job("search", 2)
    leaked["request"] = {
        **leaked["request"],
        "raw_query": "private lookup",
        "source_path": "/tmp/raw-osint.json",
    }
    transport.jobs.append(leaked)
    with pytest.raises(ResearchWorkerError, match="invalid research request"):
        await runtime.worker.run_once()
    await runtime.aclose()


def test_factory_config_rejects_missing_or_unknown_projection_paths(tmp_path: Path) -> None:
    with pytest.raises(ResearchRuntimeConfigError, match="missing research runtime configuration"):
        create_research_runtime(env={}, transport=QueueTransport([]), nlm_client=FakeNlmClient())

    path = _write_registry(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["projection_paths"]["raw-osint"] = str(tmp_path / "raw.json")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ResearchRuntimeConfigError, match="invalid research source configuration"):
        create_research_runtime(
            env=_factory_env(path), transport=QueueTransport([]), nlm_client=FakeNlmClient()
        )

    relative = _write_registry(tmp_path)
    payload = json.loads(relative.read_text(encoding="utf-8"))
    payload["projection_paths"]["intel-lake"] = "intel-lake.public.json"
    relative.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ResearchRuntimeConfigError, match="invalid research source configuration"):
        create_research_runtime(
            env=_factory_env(relative), transport=QueueTransport([]), nlm_client=FakeNlmClient()
        )


@pytest.mark.asyncio
async def test_notebook_failure_never_exposes_ref_raw_response_or_private_text(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    private = "passport A1234567 belonged to a private client"
    caplog.set_level(logging.DEBUG)
    unsafe_answers = (
        {
            "schema_version": "magazine-notebook-result.v1",
            "summary": private,
            "claims": [],
        },
        {
            "schema_version": "magazine-notebook-result.v1",
            "summary": "Public summary without evidence",
            "claims": [
                {
                    "claim_key": "claim-without-source",
                    "kind": "fact",
                    "text": "An uncited fact",
                    "evidence": [],
                    "numeric_value": None,
                    "numeric_unit": None,
                    "as_of": None,
                }
            ],
        },
    )
    for unsafe_answer in unsafe_answers:
        transport = QueueTransport([_job("notebook_insight")])
        runtime = create_research_runtime(
            env=_factory_env(_write_registry(tmp_path)),
            transport=transport,
            nlm_client=FakeNlmClient(answer=json.dumps(unsafe_answer)),
            dlp_gate=lambda _: True,
            now=lambda: "2026-07-19T04:30:00.000Z",
        )
        assert await runtime.worker.run_once() is True
        result = transport.results[0]
        assert result["status"] == "failed"
        assert result["failure"] == {"code": "source_unavailable"}
        combined = str(result) + caplog.text
        assert NOTEBOOK_REF not in combined
        assert private not in combined
        await runtime.aclose()


@pytest.mark.asyncio
async def test_async_nlm_client_uses_argv_without_shell_and_bounds_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "nlm"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    calls: list[tuple[str, ...]] = []

    response = json.dumps({"value": {"answer": '{"ok":true}'}}).encode()

    class Stream:
        def __init__(self) -> None:
            self.sent = False

        async def read(self, limit: int) -> bytes:
            if self.sent:
                return b""
            self.sent = True
            return response

    class Process:
        stdout = Stream()
        returncode = 0

        async def wait(self) -> int:
            return 0

        def kill(self) -> None:
            self.returncode = -9

    async def fake_exec(*argv: str, **kwargs: Any) -> Process:
        calls.append(argv)
        assert "shell" not in kwargs
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    client = AsyncNlmClient(binary=binary, timeout_seconds=5, max_output_bytes=1024)
    answer = await client.query(NOTEBOOK_REF, "closed public prompt")
    assert answer == '{"ok":true}'
    assert calls == [
        (
            str(binary),
            "query",
            "notebook",
            NOTEBOOK_REF,
            "closed public prompt",
            "--timeout",
            "5",
        )
    ]

    response = b"x" * 1025
    with pytest.raises(ResearchSourceUnavailableError, match="notebook source unavailable"):
        await client.query(NOTEBOOK_REF, "closed public prompt")


@pytest.mark.asyncio
async def test_poll_loop_has_bounded_backoff_and_graceful_stop() -> None:
    class Worker:
        def __init__(self) -> None:
            self.outcomes = iter([False, False, True, False])
            self.calls = 0

        async def run_once(self) -> bool:
            self.calls += 1
            return next(self.outcomes)

    worker = Worker()
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    await run_poll_loop(
        worker,
        settings=PollSettings(min_backoff_seconds=1, max_backoff_seconds=4),
        sleep=fake_sleep,
        max_cycles=4,
    )
    assert worker.calls == 4
    assert delays == [1, 2, 1, 1]

    stop = asyncio.Event()
    stop.set()
    worker = Worker()
    await run_poll_loop(worker, stop_event=stop, sleep=fake_sleep)
    assert worker.calls == 0
