"""Tests for the B2.2 residual cosine re-measurement harness
(``backend/tests/benchmarks/evidence_sufficiency/measure_residual_cosines.py``,
RULING I15).

No network call anywhere in this file. Every provider call in a test goes
through a fake ``generate_query_embedding`` — never a real embedder or
OpenAI client, and no test invokes the real ``_build_zero_retry_generator``.
Tests that need a mutated manifest or artifact copy the three real files
into ``tmp_path`` first; tests that only read are pointed at the real
``evidence_sufficiency`` directory.
"""

from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path
from typing import Any

import pytest

from backend.tests.benchmarks.evidence_sufficiency import measure_residual_cosines as mrc

REAL_BENCH_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "evidence_sufficiency"


def _real_plan() -> dict[str, Any]:
    artifact_data = mrc.load_verified_artifact(REAL_BENCH_DIR / mrc.ARTIFACT_FILENAME)
    return mrc.plan_batch(REAL_BENCH_DIR, artifact_data)


def _write_valid_precall_env(tmp_path: Path) -> tuple[Path, Path]:
    """A fresh evidence_dir carrying one valid, uncompleted b2-2-precall.json
    (built from the REAL bench dir's plan) plus a fresh, empty b1_5_dir (0
    consumed) — the common starting point for the `execute()` tests."""
    evidence_dir = tmp_path / "evidence"
    b1_5_dir = tmp_path / "b1_5"
    b1_5_dir.mkdir()
    (b1_5_dir / "b1-5-precall.json").write_text(
        json.dumps({"completion": {"attempts": 0}}),
        encoding="utf-8",
    )
    plan = _real_plan()
    mrc.write_precall(
        evidence_dir,
        plan,
        consumed_before=0,
        base_sha="0" * 40,
        artifact_sha256=mrc.ARTIFACT_EXPECTED_SHA256,
    )
    return evidence_dir, b1_5_dir


def _bench_copy(tmp_path: Path) -> Path:
    """A tmp_path copy of the two manifests + the real (byte-identical, so
    still sha256-pin-valid) B1.5 artifact, for tests that mutate a manifest."""
    bench_dir = tmp_path / "bench"
    bench_dir.mkdir()
    for name in ("manifest_mandatory.json", "manifest_supplement_b2.json", mrc.ARTIFACT_FILENAME):
        shutil.copy(REAL_BENCH_DIR / name, bench_dir / name)
    return bench_dir


class FakeGenerator:
    """A fake `EmbeddingsGenerator` substitute: async
    `generate_query_embedding`, no network, records every call. When
    `precall_path` is given, its FIRST call asserts the on-disk record
    already carries an `ack_envelope` — proving `execute()` flushed it
    before making any provider call."""

    def __init__(
        self,
        *,
        vectors_by_text: dict[str, list[float]] | None = None,
        precall_path: Path | None = None,
        dim: int = mrc.DIMENSION,
    ) -> None:
        self.calls: list[str] = []
        self._vectors_by_text = vectors_by_text or {}
        self._precall_path = precall_path
        self._checked_ack = False
        self._dim = dim

    async def generate_query_embedding(self, text: str) -> list[float]:
        self.calls.append(text)
        if self._precall_path is not None and not self._checked_ack:
            self._checked_ack = True
            record = json.loads(self._precall_path.read_text(encoding="utf-8"))
            assert record.get("ack_envelope"), (
                "ack_envelope must already be on disk before the first provider call"
            )
        if text in self._vectors_by_text:
            return self._vectors_by_text[text]
        return [0.1 * (i + 1) for i in range(self._dim)]


class BoomGenerator:
    """Raises on every call, with a message that would leak a credential if
    the harness ever recorded more than the exception type + status_code."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate_query_embedding(self, text: str) -> list[float]:
        self.calls.append(text)
        exc = RuntimeError("Bearer sk-test-SECRET leaked in this message")
        exc.status_code = 401  # type: ignore[attr-defined]
        raise exc


# ---------------------------------------------------------------------------
# plan_batch — on the real, frozen files
# ---------------------------------------------------------------------------
def test_plan_on_real_files_is_five_provider_attempts_and_v1_reuses_artifact() -> None:
    plan = _real_plan()
    assert plan["planned_provider_attempts"] == 5
    assert len(plan["items"]) == 6

    v1_query_items = [
        item
        for item in plan["items"]
        if item["case_id"] == "bs-17806bb4" and item["role"] == "query"
    ]
    assert len(v1_query_items) == 1
    assert v1_query_items[0]["source"] == "artifact"
    assert v1_query_items[0]["residual"] == "V1"

    v2_case_ids = {item["case_id"] for item in plan["items"] if item["residual"] == "V2"}
    assert v2_case_ids == {"sup-d-4984a0c2", "sup-d-4d058bdc"}
    for item in plan["items"]:
        if item["case_id"] in v2_case_ids:
            assert item["source"] == "provider"


def test_plan_items_never_carry_the_manifest_text_itself() -> None:
    plan = _real_plan()
    manifest = json.loads((REAL_BENCH_DIR / "manifest_mandatory.json").read_text(encoding="utf-8"))
    supplement = json.loads(
        (REAL_BENCH_DIR / "manifest_supplement_b2.json").read_text(encoding="utf-8"),
    )
    manifest_texts: set[str] = set()
    for case in [*manifest["cases"], *supplement["cases"]]:
        manifest_texts.add(case.get("query", ""))
        for chunk in case.get("context") or []:
            manifest_texts.add(chunk)

    for item in plan["items"]:
        assert set(item.keys()) == {"case_id", "residual", "role", "source", "text_sha256"}
        for value in item.values():
            assert value not in manifest_texts


# ---------------------------------------------------------------------------
# write_precall — one run only, and budget-aware
# ---------------------------------------------------------------------------
def test_write_precall_refuses_a_second_write_under_any_name(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "b2-2-precall-anything.json").write_text("{}", encoding="utf-8")

    plan = _real_plan()
    with pytest.raises(mrc.RefusalError, match="already present"):
        mrc.write_precall(
            evidence_dir,
            plan,
            consumed_before=0,
            base_sha="0" * 40,
            artifact_sha256=mrc.ARTIFACT_EXPECTED_SHA256,
        )


def test_compute_budget_sums_a_fake_b1_5_receipt_of_38(tmp_path: Path) -> None:
    b1_5_dir = tmp_path / "b1_5"
    b1_5_dir.mkdir()
    (b1_5_dir / "b1-5-precall.json").write_text(
        json.dumps({"completion": {"attempts": 38}}),
        encoding="utf-8",
    )
    budget = mrc.compute_budget(b1_5_dir, None)
    assert budget["b1_5_consumed"] == 38
    assert budget["consumed"] == 38
    assert budget["remaining"] == 2
    assert budget["own_consumed_checked"] is False


def test_write_precall_refuses_when_38_of_40_already_consumed(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    plan = {"items": [], "planned_provider_attempts": 5}
    with pytest.raises(mrc.RefusalError, match="exceeds"):
        mrc.write_precall(
            evidence_dir,
            plan,
            consumed_before=38,
            base_sha="0" * 40,
            artifact_sha256="deadbeef",
        )
    assert not evidence_dir.exists() or not list(evidence_dir.glob("b2-2-precall*.json"))


def test_own_consumed_unknown_receipt_costs_the_full_ceiling(tmp_path: Path) -> None:
    (tmp_path / "b2-2-precall-mystery.json").write_text(
        json.dumps({"list_sha256": "abc"}),
        encoding="utf-8",
    )
    consumed, receipts = mrc.own_consumed(tmp_path)
    assert consumed == mrc.CEILING
    assert "full ceiling" in receipts[0]


def test_write_precall_records_the_expected_hard_stop_and_remaining(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    plan = _real_plan()
    record = mrc.write_precall(
        evidence_dir,
        plan,
        consumed_before=23,
        base_sha="0" * 40,
        artifact_sha256=mrc.ARTIFACT_EXPECTED_SHA256,
    )
    assert record["planned_provider_attempts"] == 5
    assert record["hard_stop"] == 5
    assert record["remaining_after"] == 12
    assert record["ack_envelope"] is None
    assert record["ceiling"] == 40


# ---------------------------------------------------------------------------
# execute — refusals
# ---------------------------------------------------------------------------
def test_execute_refuses_without_a_precall_record(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    with pytest.raises(mrc.RefusalError, match="no pre-call record"):
        mrc.execute(
            evidence_dir, REAL_BENCH_DIR, tmp_path / "b1_5", "ack-1", lambda: FakeGenerator()
        )


def test_execute_refuses_when_completion_already_present(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / mrc.PRECALL_FILENAME).write_text(
        json.dumps({"completion": {"attempts": 1}}),
        encoding="utf-8",
    )
    with pytest.raises(mrc.RefusalError, match="already has a completion"):
        mrc.execute(
            evidence_dir, REAL_BENCH_DIR, tmp_path / "b1_5", "ack-1", lambda: FakeGenerator()
        )


def test_execute_refuses_with_an_empty_ack_envelope(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    with pytest.raises(mrc.RefusalError, match="ack_envelope"):
        mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "", lambda: FakeGenerator())


def test_execute_refuses_when_a_case_text_changed_since_the_precall(tmp_path: Path) -> None:
    bench_dir = _bench_copy(tmp_path)
    plan = mrc.plan_batch(bench_dir, mrc.load_verified_artifact(bench_dir / mrc.ARTIFACT_FILENAME))

    evidence_dir = tmp_path / "evidence"
    b1_5_dir = tmp_path / "b1_5"
    b1_5_dir.mkdir()
    mrc.write_precall(
        evidence_dir,
        plan,
        consumed_before=0,
        base_sha="0" * 40,
        artifact_sha256=mrc.ARTIFACT_EXPECTED_SHA256,
    )

    supplement_path = bench_dir / "manifest_supplement_b2.json"
    data = json.loads(supplement_path.read_text(encoding="utf-8"))
    for case in data["cases"]:
        if case["case_id"] == "sup-d-4984a0c2":
            case["context"] = ["a completely different chunk of text, never in the frozen manifest"]
    supplement_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(mrc.RefusalError, match="text_sha256"):
        mrc.execute(evidence_dir, bench_dir, b1_5_dir, "ack-1", lambda: FakeGenerator())


# ---------------------------------------------------------------------------
# execute — the real run, with a fake generator
# ---------------------------------------------------------------------------
def test_execute_writes_ack_envelope_before_the_first_provider_call(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    precall_path = evidence_dir / mrc.PRECALL_FILENAME
    fake = FakeGenerator(precall_path=precall_path)

    completion = mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "env-ack-123", lambda: fake)

    assert completion["attempts"] == 5
    record = json.loads(precall_path.read_text(encoding="utf-8"))
    assert record["ack_envelope"] == "env-ack-123"
    assert "execution_start_utc" in record
    assert "completion" in record


def test_hard_stop_is_honoured_even_when_recorded_lower_than_planned(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    precall_path = evidence_dir / mrc.PRECALL_FILENAME
    record = json.loads(precall_path.read_text(encoding="utf-8"))
    assert record["planned_provider_attempts"] == 5
    record["hard_stop"] = 3
    precall_path.write_text(json.dumps(record), encoding="utf-8")

    fake = FakeGenerator()
    completion = mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-hardstop", lambda: fake)

    assert completion["attempts"] == 3
    assert len(fake.calls) == 3


def test_failures_record_only_type_and_status_code_never_the_message(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    precall_path = evidence_dir / mrc.PRECALL_FILENAME

    completion = mrc.execute(
        evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-boom", lambda: BoomGenerator()
    )

    assert completion["attempts"] == 5
    assert len(completion["failures"]) == 5
    for failure in completion["failures"]:
        assert failure["error"] == "RuntimeError"
        assert failure["status_code"] == "401"
        assert set(failure.keys()) == {"case_id", "role", "error", "status_code"}

    raw = precall_path.read_text(encoding="utf-8")
    assert "Bearer sk-test-SECRET" not in raw
    assert "SECRET" not in raw
    assert json.dumps(completion) and "SECRET" not in json.dumps(completion)


def test_socket_guard_execute_never_touches_a_real_socket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a real socket call was attempted")

    monkeypatch.setattr(socket.socket, "connect", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)

    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    completion = mrc.execute(
        evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-socket", lambda: FakeGenerator()
    )

    assert completion["attempts"] == 5
    assert completion["v1_verdict"] in {"HOLDS", "INCOMPATIBLE", "BROKEN", "UNMEASURED"}


# ---------------------------------------------------------------------------
# Cosine math + V1 verdict classification
# ---------------------------------------------------------------------------
def test_cosine_on_known_vectors() -> None:
    assert mrc.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert mrc.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert mrc.cosine([1.0, 1.0], [1.0, 1.0]) == pytest.approx(1.0)
    assert mrc.cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_v1_verdict_classification_at_the_named_thresholds() -> None:
    assert mrc.v1_verdict(0.373) == "HOLDS"
    assert mrc.v1_verdict(0.3736) == "INCOMPATIBLE"
    assert mrc.v1_verdict(0.31) == "BROKEN"
    assert mrc.v1_verdict(None) == "UNMEASURED"


# ---------------------------------------------------------------------------
# G1 — "runs once" must hold even across a kill / a mid-batch raise
# ---------------------------------------------------------------------------
def test_execute_refuses_when_execution_already_started_without_completion(
    tmp_path: Path,
) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    precall_path = evidence_dir / mrc.PRECALL_FILENAME
    record = json.loads(precall_path.read_text(encoding="utf-8"))
    record["execution_start_utc"] = "2026-01-01T00:00:00+00:00"
    record["ack_envelope"] = "some-prior-ack-that-never-completed"
    precall_path.write_text(json.dumps(record), encoding="utf-8")

    fake = FakeGenerator()
    with pytest.raises(mrc.RefusalError, match="execution_start_utc"):
        mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-2", lambda: fake)
    assert fake.calls == []


class MismatchGenerator:
    """Returns a 3-float vector for one named text (simulating a chunk
    embedding of the wrong dimension) and a real-dimension vector for
    everything else."""

    def __init__(self, mismatched_text: str) -> None:
        self.calls: list[str] = []
        self._mismatched_text = mismatched_text

    async def generate_query_embedding(self, text: str) -> list[float]:
        self.calls.append(text)
        if text == self._mismatched_text:
            return [0.1, 0.2, 0.3]
        return [0.1] * mrc.DIMENSION


def test_vector_length_mismatch_is_recorded_not_raised(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    v1_chunk_text = mrc.load_cases(REAL_BENCH_DIR)["bs-17806bb4"]["chunk"]
    fake = MismatchGenerator(v1_chunk_text)

    completion = mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-mismatch", lambda: fake)

    assert completion["attempts"] == 5
    assert completion["cosines"]["bs-17806bb4"]["measured"] is False
    mismatch_failures = [f for f in completion["failures"] if f["error"] == "VectorLengthMismatch"]
    assert len(mismatch_failures) == 1
    assert mismatch_failures[0]["case_id"] == "bs-17806bb4"


class _FakeInterrupt(BaseException):
    """A `BaseException` that is NOT an `Exception` — stands in for a real
    `KeyboardInterrupt`/kill signal, which `_run_batch`'s per-item
    `except Exception` must never swallow."""


class InterruptingGenerator:
    def __init__(self, boom_after: int) -> None:
        self.calls: list[str] = []
        self._boom_after = boom_after

    async def generate_query_embedding(self, text: str) -> list[float]:
        self.calls.append(text)
        if len(self.calls) > self._boom_after:
            raise _FakeInterrupt("simulated kill mid-batch")
        return [0.1] * mrc.DIMENSION


def test_a_mid_batch_base_exception_still_persists_a_completion(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    precall_path = evidence_dir / mrc.PRECALL_FILENAME
    fake = InterruptingGenerator(boom_after=2)

    with pytest.raises(_FakeInterrupt):
        mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-interrupt", lambda: fake)

    record = json.loads(precall_path.read_text(encoding="utf-8"))
    assert "completion" in record
    assert record["completion"]["attempts"] == 3
    assert record["completion"]["aborted_by"] == "_FakeInterrupt"
    assert len(fake.calls) == 3


# ---------------------------------------------------------------------------
# G2 — the manifest/artifact pin and the B1.5 ledger get no CLI override
# ---------------------------------------------------------------------------
def test_argparse_rejects_bench_dir_and_b1_5_dir_overrides() -> None:
    with pytest.raises(SystemExit) as exc_info:
        mrc.main(["--b1-5-dir", "/tmp/whatever-b1-5"])
    assert exc_info.value.code == 2

    with pytest.raises(SystemExit) as exc_info2:
        mrc.main(["--bench-dir", "/tmp/whatever-bench"])
    assert exc_info2.value.code == 2


def test_compute_budget_refuses_on_a_missing_or_empty_b1_5_ledger(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does-not-exist"
    with pytest.raises(mrc.RefusalError, match="does not exist or holds no"):
        mrc.compute_budget(missing_dir, None, require_ledger=True)

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(mrc.RefusalError, match="does not exist or holds no"):
        mrc.compute_budget(empty_dir, None, require_ledger=True)

    # the write path: compute_budget(require_ledger=True) is exactly what
    # _cmd_write_precall calls before write_precall.
    with pytest.raises(mrc.RefusalError, match="does not exist or holds no"):
        mrc.compute_budget(empty_dir, tmp_path / "evidence", require_ledger=True)

    # plan mode stays permissive: require_ledger defaults to False.
    budget = mrc.compute_budget(empty_dir, None)
    assert budget["b1_5_consumed"] == 0


# ---------------------------------------------------------------------------
# G3 — the completion names the exact call it made, and only the scalar
# max_retries off the client, never the client object itself
# ---------------------------------------------------------------------------
class ClientCarryingGenerator(FakeGenerator):
    """A fake generator whose `.client` carries `max_retries` alongside a
    value that must NEVER be recorded — proving `_generator_max_retries`
    reads only the one scalar attribute it is documented to read."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        class _Client:
            max_retries = 0
            api_key = "sk-should-never-be-recorded"  # noqa: S105

        self.client = _Client()


def test_completion_records_embedding_call_and_max_retries(tmp_path: Path) -> None:
    evidence_dir, b1_5_dir = _write_valid_precall_env(tmp_path)
    fake = ClientCarryingGenerator()

    completion = mrc.execute(evidence_dir, REAL_BENCH_DIR, b1_5_dir, "ack-g3", lambda: fake)

    assert completion["embedding_call"] == "EmbeddingsGenerator.generate_query_embedding"
    assert completion["max_retries"] == 0
    assert "sk-should-never-be-recorded" not in json.dumps(completion)

    record = json.loads((evidence_dir / mrc.PRECALL_FILENAME).read_text(encoding="utf-8"))
    assert "sk-should-never-be-recorded" not in json.dumps(record)
