"""Phase-0 safety rail (FATAL 4, MAJOR 6): delta quarantine trigger.

Guilt: a matched citation quarantines the row SAME DAY (FAQ copy deleted,
Qdrant flagged, never left serving until "next batch"). An unmapped
service_line or a `partial: true` run is NEVER a silent no-op.
Innocence: `new_today_count == 0 AND partial == false` is a TRUE no-op
(zero LLM calls — nothing beyond loading the delta JSON even runs). A
legitimate mapped delta with zero citation matches is also a no-op result
(nothing quarantined) but is NOT the same code path as the true no-op.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.services.caching.notebooklm_cache_service import (
    NotebookLMCacheService,
    domain_scope_id,
)
from scripts import curated_qa_regen_trigger as trigger
from scripts.curated_qa_harvest import _stable_point_id

# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted

    async def scan_iter(self, match: str | None = None):
        prefix = (match or "*").rstrip("*")
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key


class FakeQdrantClient:
    """In-memory stand-in supporting the subset used by quarantine_row():
    get() (fetch existing embedding+payload) and upsert_documents()
    (re-upsert with the flagged payload, same embedding)."""

    def __init__(self) -> None:
        self.points: dict[str, dict[str, Any]] = {}

    def seed(self, point_id: str, *, text: str, embedding: list[float], metadata: dict) -> None:
        self.points[point_id] = {"text": text, "embedding": embedding, "metadata": metadata}

    async def get(self, ids: list[str], include: list[str] | None = None) -> dict[str, Any]:
        formatted: dict[str, Any] = {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        for point_id in ids:
            point = self.points.get(point_id)
            if point is None:
                continue
            formatted["ids"].append(point_id)
            formatted["embeddings"].append(point["embedding"])
            formatted["documents"].append(point["text"])
            formatted["metadatas"].append(point["metadata"])
        return formatted

    async def upsert_documents(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
        flatten_payload: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        ids = ids or [str(i) for i in range(len(chunks))]
        for i, point_id in enumerate(ids):
            self.points[point_id] = {
                "text": chunks[i],
                "embedding": embeddings[i],
                "metadata": metadatas[i],
            }
        return {"success": True, "documents_added": len(chunks)}


@pytest.fixture
def faq_cache() -> NotebookLMCacheService:
    svc = NotebookLMCacheService()
    svc.redis_client = FakeAsyncRedis()
    return svc


@pytest.fixture
def qdrant_client() -> FakeQdrantClient:
    return FakeQdrantClient()


def _row(**overrides: Any) -> dict:
    base = {
        "question": "What deposit is required for E33?",
        "answer": "A qualifying deposit is required.",
        "domain": "visa",
        "lang": "en",
        "source_ref": "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1",
        "source_date": "2026-07-15",
        "confidence_class": "JELAS",
        "law_refs": ["Permenkumham 22/2023"],
        "source_priority": 80,
        "verbatim_eligible": True,
        "client_specific": False,
    }
    base.update(overrides)
    return base


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _delta(**overrides: Any) -> dict:
    base = {
        "run_at": "2026-07-19T07:00:00+08:00",
        "today": "2026-07-19",
        "new_today_count": 1,
        "partial": False,
        "deltas": [
            {
                "citation": "Permenkumham 22/2023",
                "title_id": "x",
                "title_en": "x",
                "service_line": ["visa"],
                "summary": "x",
                "source": "x",
                "verbatim_excerpt": "x",
            },
        ],
        "seen_citations": [],
    }
    base.update(overrides)
    return base


# ── SERVICE_LINE_TO_DOMAIN mapping ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("service_line", "expected_domain"),
    [
        ("visa", "visa"),
        ("immigration", "visa"),
        ("tax", "tax"),
        ("company", "kbli"),
        ("business", "kbli"),
        ("oss", "kbli"),
        ("property", "property"),
        ("land", "property"),
    ],
)
def test_service_line_mapping_table(service_line: str, expected_domain: str) -> None:
    assert trigger.SERVICE_LINE_TO_DOMAIN[service_line] == expected_domain


def test_unmapped_service_line_not_in_table() -> None:
    assert "hr" not in trigger.SERVICE_LINE_TO_DOMAIN
    assert "regulatory" not in trigger.SERVICE_LINE_TO_DOMAIN


# ── match_citation_against_law_refs ─────────────────────────────────────────


def test_match_citation_guilt_substring_case_insensitive() -> None:
    assert trigger.match_citation_against_law_refs(
        "permenkumham 22/2023",
        ["Permenkumham 22/2023, Pasal 56"],
    )


def test_match_citation_innocence_no_match() -> None:
    assert not trigger.match_citation_against_law_refs("PP 45/2024", ["Permenkumham 22/2023"])


def test_match_citation_innocence_empty_inputs() -> None:
    assert not trigger.match_citation_against_law_refs("", ["ref"])
    assert not trigger.match_citation_against_law_refs("citation", [])


# ── find_quarantine_candidates ──────────────────────────────────────────────


def test_find_quarantine_candidates_matches_same_domain_row() -> None:
    rows_by_domain = {"visa": [(Path("x.jsonl"), _row())]}
    deltas = [
        {"citation": "Permenkumham 22/2023", "service_line": ["visa"]},
    ]

    candidates, unmapped = trigger.find_quarantine_candidates(deltas, rows_by_domain)

    assert len(candidates) == 1
    assert candidates[0]["domain"] == "visa"
    assert unmapped == []


def test_find_quarantine_candidates_no_match_is_empty() -> None:
    rows_by_domain = {"visa": [(Path("x.jsonl"), _row())]}
    deltas = [{"citation": "PP 45/2024", "service_line": ["visa"]}]

    candidates, unmapped = trigger.find_quarantine_candidates(deltas, rows_by_domain)

    assert candidates == []
    assert unmapped == []


def test_find_quarantine_candidates_unmapped_service_line_is_never_silent() -> None:
    rows_by_domain: dict = {}
    deltas = [{"citation": "SE-8/PJ/2026", "service_line": ["hr", "regulatory"]}]

    candidates, unmapped = trigger.find_quarantine_candidates(deltas, rows_by_domain)

    assert candidates == []
    assert len(unmapped) == 2
    assert {u["service_line"] for u in unmapped} == {"hr", "regulatory"}


def test_find_quarantine_candidates_mixed_mapped_and_unmapped_still_matches() -> None:
    rows_by_domain = {"tax": [(Path("x.jsonl"), _row(domain="tax", law_refs=["SE-8/PJ/2026"]))]}
    deltas = [{"citation": "SE-8/PJ/2026", "service_line": ["tax", "regulatory"]}]

    candidates, unmapped = trigger.find_quarantine_candidates(deltas, rows_by_domain)

    assert len(candidates) == 1
    assert candidates[0]["domain"] == "tax"
    assert len(unmapped) == 1
    assert unmapped[0]["service_line"] == "regulatory"


def test_find_quarantine_candidates_cross_domain_row_not_matched() -> None:
    """INNOCENCE — a tax delta must never match a visa-domain row even if
    the citation string happens to appear in its law_refs."""
    rows_by_domain = {
        "visa": [(Path("x.jsonl"), _row(domain="visa", law_refs=["SE-8/PJ/2026"]))],
    }
    deltas = [{"citation": "SE-8/PJ/2026", "service_line": ["tax"]}]

    candidates, unmapped = trigger.find_quarantine_candidates(deltas, rows_by_domain)

    assert candidates == []


# ── quarantine_row ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quarantine_row_deletes_faq_and_flags_qdrant(
    faq_cache: NotebookLMCacheService,
    qdrant_client: FakeQdrantClient,
) -> None:
    question = "What deposit is required for E33?"
    domain = "visa"
    await faq_cache.set(
        question,
        "A qualifying deposit is required.",
        metadata={
            "source_ref": "x",
            "source_date": "2026-07-15",
            "domain": domain,
            "confidence_class": "JELAS",
            "source_priority": 80,
        },
        notebook_id=domain_scope_id(domain),
    )
    point_id = _stable_point_id(question, domain)
    qdrant_client.seed(
        point_id,
        text=question,
        embedding=[0.1] * 1536,
        metadata={"answer": "A qualifying deposit is required.", "domain": domain},
    )

    await trigger.quarantine_row(
        {"domain": domain, "question": question},
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
        citation="Permenkumham 22/2023",
    )

    assert await faq_cache.get(question, notebook_id=domain_scope_id(domain)) is None
    flagged = qdrant_client.points[point_id]["metadata"]
    assert flagged["regulatory_flagged"] is True
    assert flagged["regulatory_flagged_citation"] == "Permenkumham 22/2023"
    # Staleness rail (MAJOR 7/8): quarantine also flips the SAME `active`
    # field the class-based-TTL rail writes, so the grounding-injection
    # filter excludes this point without a second regulatory_flagged
    # special-case.
    assert flagged["active"] is False
    assert flagged["invalidated_at"] is not None
    # Qdrant point still EXISTS — flagged, not deleted.
    assert point_id in qdrant_client.points


@pytest.mark.asyncio
async def test_quarantine_row_missing_qdrant_point_still_deletes_faq(
    faq_cache: NotebookLMCacheService,
    qdrant_client: FakeQdrantClient,
) -> None:
    """INNOCENCE-ish robustness: if the Qdrant point somehow doesn't exist,
    the FAQ deletion must still have happened (fail-safe on the
    higher-risk sink) rather than raising."""
    question = "Some question"
    domain = "visa"
    await faq_cache.set(
        question,
        "answer",
        metadata={
            "source_ref": "x",
            "source_date": "2026-07-15",
            "domain": domain,
            "confidence_class": "JELAS",
            "source_priority": 80,
        },
        notebook_id=domain_scope_id(domain),
    )

    await trigger.quarantine_row(
        {"domain": domain, "question": question},
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
        citation="some citation",
    )

    assert await faq_cache.get(question, notebook_id=domain_scope_id(domain)) is None


# ── compute_regen_candidate_backlog (MAJOR 11) ──────────────────────────────


def test_compute_regen_candidate_backlog_empty_when_dir_missing(tmp_path: Path) -> None:
    assert trigger.compute_regen_candidate_backlog(tmp_path / "does-not-exist") == {}


def test_compute_regen_candidate_backlog_counts_per_domain(tmp_path: Path) -> None:
    regen_dir = tmp_path / "_regen-candidates"
    regen_dir.mkdir()
    (regen_dir / "2026-07-18.jsonl").write_text(
        "\n".join(
            json.dumps(c)
            for c in [
                {"citation": "x", "domain": "visa", "question": "q1"},
                {"citation": "x", "domain": "tax", "question": "q2"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (regen_dir / "2026-07-19.jsonl").write_text(
        json.dumps({"citation": "y", "domain": "visa", "question": "q3"}) + "\n",
        encoding="utf-8",
    )

    backlog = trigger.compute_regen_candidate_backlog(regen_dir)

    assert backlog == {"visa": 2, "tax": 1}


def test_compute_regen_candidate_backlog_ignores_malformed_lines(tmp_path: Path) -> None:
    """INNOCENCE — one corrupt line in a candidates file must not crash the
    scan or drop the other valid rows in the same file."""
    regen_dir = tmp_path / "_regen-candidates"
    regen_dir.mkdir()
    (regen_dir / "2026-07-18.jsonl").write_text(
        "not json\n" + json.dumps({"citation": "x", "domain": "visa", "question": "q1"}) + "\n",
        encoding="utf-8",
    )

    backlog = trigger.compute_regen_candidate_backlog(regen_dir)

    assert backlog == {"visa": 1}


# ── run() orchestration ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_true_no_op_zero_new_and_not_partial(tmp_path: Path) -> None:
    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(json.dumps(_delta(new_today_count=0, partial=False)), encoding="utf-8")

    summary = await trigger.run("2026-07-19", delta_path=delta_path)

    assert summary["no_op"] is True
    assert summary["alerts"] == []
    assert summary["quarantined"] == []


@pytest.mark.asyncio
async def test_run_refreshes_backlog_gauge_even_on_no_op_day(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Staleness rail (MAJOR 11): a PRIOR day's un-triaged candidates must
    still be reflected in the gauge on a QUIET (no_op=True) day — the
    backlog computation is a pure read of directory state, not derived
    from today's delta, so it must run unconditionally, before the
    no-op early return."""
    regen_dir = tmp_path / "curated_qa" / "_regen-candidates"
    monkeypatch.setattr(trigger, "_CURATED_QA_DATA_DIR", tmp_path / "curated_qa")
    monkeypatch.setattr(trigger, "_REGEN_CANDIDATES_DIR", regen_dir)
    regen_dir.mkdir(parents=True)
    (regen_dir / "2026-07-10.jsonl").write_text(
        json.dumps({"citation": "old", "domain": "visa", "question": "stale one"}) + "\n",
        encoding="utf-8",
    )

    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(json.dumps(_delta(new_today_count=0, partial=False)), encoding="utf-8")

    summary = await trigger.run("2026-07-19", delta_path=delta_path)

    assert summary["no_op"] is True  # confirm we DID take the no-op path

    from backend.app.metrics import curated_qa_regen_candidate_backlog_size

    assert curated_qa_regen_candidate_backlog_size.labels(domain="visa")._value.get() == 1


@pytest.mark.asyncio
async def test_run_partial_true_is_never_silent_even_with_zero_new(tmp_path: Path) -> None:
    """GUILT — partial=true must alert even when new_today_count==0 (a
    partial scan finding 'nothing new' is not trustworthy)."""
    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(json.dumps(_delta(new_today_count=0, partial=True)), encoding="utf-8")

    summary = await trigger.run("2026-07-19", delta_path=delta_path)

    assert summary["no_op"] is False
    assert any("PARTIAL" in a for a in summary["alerts"])


@pytest.mark.asyncio
async def test_run_mapped_delta_zero_matches_is_not_true_no_op(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A legitimate mapped delta with zero citation matches produces an
    empty quarantine list, but is NOT the same code path as the true
    no_op=True case (it scanned the corpus, just found nothing)."""
    monkeypatch.setattr(trigger, "_CURATED_QA_DATA_DIR", tmp_path / "curated_qa")
    monkeypatch.setattr(
        trigger, "_REGEN_CANDIDATES_DIR", tmp_path / "curated_qa" / "_regen-candidates"
    )
    (tmp_path / "curated_qa").mkdir()
    _write_jsonl((tmp_path / "curated_qa" / "visa.jsonl"), [_row()])

    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(
        json.dumps(_delta(deltas=[{"citation": "PP 45/2024", "service_line": ["visa"]}])),
        encoding="utf-8",
    )

    summary = await trigger.run("2026-07-19", delta_path=delta_path)

    assert summary["no_op"] is False
    assert summary["quarantined"] == []


@pytest.mark.asyncio
async def test_run_unmapped_service_line_alerts_and_never_silent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(trigger, "_CURATED_QA_DATA_DIR", tmp_path / "curated_qa")
    monkeypatch.setattr(
        trigger, "_REGEN_CANDIDATES_DIR", tmp_path / "curated_qa" / "_regen-candidates"
    )
    (tmp_path / "curated_qa").mkdir()

    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(
        json.dumps(
            _delta(deltas=[{"citation": "SE-8/PJ/2026", "service_line": ["hr"]}]),
        ),
        encoding="utf-8",
    )

    summary = await trigger.run("2026-07-19", delta_path=delta_path)

    assert len(summary["unmapped_service_lines"]) == 1
    assert any("unmapped service_line" in a for a in summary["alerts"])


@pytest.mark.asyncio
async def test_run_same_day_quarantine_end_to_end(
    tmp_path: Path,
    monkeypatch,
    faq_cache: NotebookLMCacheService,
    qdrant_client: FakeQdrantClient,
) -> None:
    """GUILT — the full loop: a simulated delta whose citation matches a
    row's law_refs quarantines it THE SAME invocation — FAQ copy gone,
    Qdrant flagged, regen-candidates file written. Never left serving
    until 'next batch'."""
    curated_qa_dir = tmp_path / "curated_qa"
    curated_qa_dir.mkdir()
    monkeypatch.setattr(trigger, "_CURATED_QA_DATA_DIR", curated_qa_dir)
    monkeypatch.setattr(trigger, "_REGEN_CANDIDATES_DIR", curated_qa_dir / "_regen-candidates")
    _write_jsonl(curated_qa_dir / "visa.jsonl", [_row()])

    question = "What deposit is required for E33?"
    domain = "visa"
    await faq_cache.set(
        question,
        "A qualifying deposit is required.",
        metadata={
            "source_ref": "x",
            "source_date": "2026-07-15",
            "domain": domain,
            "confidence_class": "JELAS",
            "source_priority": 80,
        },
        notebook_id=domain_scope_id(domain),
    )
    point_id = _stable_point_id(question, domain)
    qdrant_client.seed(
        point_id,
        text=question,
        embedding=[0.1] * 1536,
        metadata={"answer": "A qualifying deposit is required.", "domain": domain},
    )

    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(json.dumps(_delta()), encoding="utf-8")

    summary = await trigger.run(
        "2026-07-19",
        delta_path=delta_path,
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
    )

    assert len(summary["quarantined"]) == 1
    assert await faq_cache.get(question, notebook_id=domain_scope_id(domain)) is None
    assert qdrant_client.points[point_id]["metadata"]["regulatory_flagged"] is True
    assert qdrant_client.points[point_id]["metadata"]["active"] is False
    assert point_id in qdrant_client.points  # still there, just flagged

    candidates_file = curated_qa_dir / "_regen-candidates" / "2026-07-19.jsonl"
    assert candidates_file.exists()
    written = [json.loads(line) for line in candidates_file.read_text().splitlines()]
    assert len(written) == 1
    assert written[0]["citation"] == "Permenkumham 22/2023"


@pytest.mark.asyncio
async def test_run_dry_run_never_writes_or_quarantines(
    tmp_path: Path,
    monkeypatch,
    faq_cache: NotebookLMCacheService,
    qdrant_client: FakeQdrantClient,
) -> None:
    curated_qa_dir = tmp_path / "curated_qa"
    curated_qa_dir.mkdir()
    monkeypatch.setattr(trigger, "_CURATED_QA_DATA_DIR", curated_qa_dir)
    monkeypatch.setattr(trigger, "_REGEN_CANDIDATES_DIR", curated_qa_dir / "_regen-candidates")
    _write_jsonl(curated_qa_dir / "visa.jsonl", [_row()])

    question = "What deposit is required for E33?"
    domain = "visa"
    await faq_cache.set(
        question,
        "A qualifying deposit is required.",
        metadata={
            "source_ref": "x",
            "source_date": "2026-07-15",
            "domain": domain,
            "confidence_class": "JELAS",
            "source_priority": 80,
        },
        notebook_id=domain_scope_id(domain),
    )

    delta_path = tmp_path / "2026-07-19-delta.json"
    delta_path.write_text(json.dumps(_delta()), encoding="utf-8")

    summary = await trigger.run(
        "2026-07-19",
        delta_path=delta_path,
        dry_run=True,
        faq_cache=faq_cache,
        qdrant_client=qdrant_client,
    )

    assert len(summary["quarantined"]) == 1  # reported...
    assert not (
        curated_qa_dir / "_regen-candidates" / "2026-07-19.jsonl"
    ).exists()  # ...but not written
    # ...and the FAQ entry is untouched.
    assert await faq_cache.get(question, notebook_id=domain_scope_id(domain)) is not None
