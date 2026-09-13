"""B2.1 §1 — tests for `_support_signal.py` (ruling I26).

Contract: `evidence/2026-09/agent-nuzantara-backend-rag-b2-engine-63f75705/
B2-1-build-spec.md` §1. Reuses B1.4's measured shapes (rubric text, strict
parse, Ollama request body, adapter invocation) — this suite never calls a
live seat: the adapter and the HTTP call are always mocked. The real seat
measurement is the Dux's own run, never CI's.

Covers:
  - `majority()`'s full truth table (every 3-vote combination over the four
    `SupportVerdict` values), plus named documentation cases.
  - the shared strict-parse table.
  - every typed `CodexExecClient.generate` exception voting UNAVAILABLE with
    its type name, never its message.
  - the Ollama HTTP-400 `think` retry, recording which attempt succeeded.
  - `evaluate_support`'s resolution: Codex-decisive (no fallback), Codex
    majority-UNAVAILABLE (fallback), Codex adapter absent (fallback), both
    judges unavailable (`UNAVAILABLE`, `judge="absent"`), and the `judge=`
    injection override.
  - importing the module performs no network I/O.
"""

from __future__ import annotations

import importlib
import itertools
import json
import socket
import sys
import urllib.error
import urllib.request
from collections import Counter
from unittest.mock import AsyncMock, patch

import pytest

import backend.services.rag.agentic._support_signal as support_signal_module
from backend.llm.codex_exec_client import (
    MODEL_TERRA,
    CodexExecAuthError,
    CodexExecCommunicationError,
    CodexExecOutputShapeError,
    CodexExecProcessError,
    CodexExecQuotaError,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
)
from backend.services.rag.agentic._support_signal import (
    OLLAMA_MODEL,
    RUBRIC,
    CodexSupportJudge,
    OllamaSupportJudge,
    SupportVerdict,
    _ollama_generate_with_retry,
    _strict_parse,
    evaluate_support,
    majority,
)

ALL_VERDICTS = (
    SupportVerdict.SUPPORTED,
    SupportVerdict.NOT_SUPPORTED,
    SupportVerdict.UNKNOWN,
    SupportVerdict.UNAVAILABLE,
)


def _reference_majority(votes: tuple[SupportVerdict, ...]) -> SupportVerdict:
    """Independent restatement of ruling I26 condition 1, used as the test
    oracle: a value wins with >= 2 of 3 identical votes; no such value ->
    fail-closed NOT_SUPPORTED."""
    counts = Counter(votes)
    for value, count in counts.items():
        if count >= 2:
            return value
    return SupportVerdict.NOT_SUPPORTED


class TestRubric:
    def test_rubric_is_byte_identical_to_b1_4(self) -> None:
        expected = (
            "You judge evidence sufficiency. Question: {query}. Context: {context}. "
            "Does the context explicitly state the specific fact the question asks "
            "for? Reply with exactly one word: SUPPORTED, NOT_SUPPORTED or UNKNOWN."
        )
        assert RUBRIC == expected


class TestMajorityTruthTable:
    @pytest.mark.parametrize("votes", list(itertools.product(ALL_VERDICTS, repeat=3)))
    def test_every_three_vote_combination(self, votes: tuple[SupportVerdict, ...]) -> None:
        assert majority(votes) == _reference_majority(votes)

    def test_unanimous_supported(self) -> None:
        assert majority((SupportVerdict.SUPPORTED,) * 3) == SupportVerdict.SUPPORTED

    def test_unanimous_not_supported(self) -> None:
        assert majority((SupportVerdict.NOT_SUPPORTED,) * 3) == SupportVerdict.NOT_SUPPORTED

    def test_two_of_three_supported_wins(self) -> None:
        votes = (SupportVerdict.SUPPORTED, SupportVerdict.SUPPORTED, SupportVerdict.NOT_SUPPORTED)
        assert majority(votes) == SupportVerdict.SUPPORTED

    def test_two_of_three_unavailable_wins_unavailable(self) -> None:
        votes = (SupportVerdict.UNAVAILABLE, SupportVerdict.UNAVAILABLE, SupportVerdict.SUPPORTED)
        assert majority(votes) == SupportVerdict.UNAVAILABLE

    def test_full_three_way_split_fails_closed(self) -> None:
        votes = (SupportVerdict.SUPPORTED, SupportVerdict.NOT_SUPPORTED, SupportVerdict.UNKNOWN)
        assert majority(votes) == SupportVerdict.NOT_SUPPORTED

    def test_unknown_and_unavailable_never_combine_into_supported(self) -> None:
        votes = (SupportVerdict.UNKNOWN, SupportVerdict.UNAVAILABLE, SupportVerdict.SUPPORTED)
        assert majority(votes) == SupportVerdict.NOT_SUPPORTED

    def test_rejects_wrong_length(self) -> None:
        with pytest.raises(ValueError):
            majority((SupportVerdict.SUPPORTED, SupportVerdict.SUPPORTED))


class TestStrictParse:
    @pytest.mark.parametrize(
        ("raw_text", "expected"),
        [
            ("SUPPORTED", SupportVerdict.SUPPORTED),
            ("supported", SupportVerdict.SUPPORTED),
            ("NOT_SUPPORTED", SupportVerdict.NOT_SUPPORTED),
            ("not_supported", SupportVerdict.NOT_SUPPORTED),
            ("UNKNOWN", SupportVerdict.UNKNOWN),
            ("unknown", SupportVerdict.UNKNOWN),
            ("SUPPORTED.", SupportVerdict.SUPPORTED),
            ("SUPPORTED!", SupportVerdict.SUPPORTED),
            ("  SUPPORTED  ", SupportVerdict.SUPPORTED),
            ("I think it is supported by the text.", SupportVerdict.UNKNOWN),
            ("", SupportVerdict.UNKNOWN),
            (None, SupportVerdict.UNKNOWN),
            ("MAYBE", SupportVerdict.UNKNOWN),
            ("NOTSUPPORTED", SupportVerdict.UNKNOWN),
        ],
    )
    def test_strict_parse_table(self, raw_text: str | None, expected: SupportVerdict) -> None:
        assert _strict_parse(raw_text) == expected


class TestCodexSupportJudgeTypedExceptions:
    @pytest.mark.parametrize(
        "exc_instance",
        [
            CodexExecUnavailableError("adapter unavailable"),
            CodexExecAuthError("auth failed"),
            CodexExecQuotaError("quota exhausted"),
            CodexExecProcessError(1),
            CodexExecOutputShapeError("empty stdout"),
            CodexExecTimeoutError("timed out"),
            CodexExecCommunicationError("pipe broke"),
        ],
        ids=lambda exc: type(exc).__name__,
    )
    async def test_typed_exception_votes_unavailable_with_type_name(self, exc_instance: Exception) -> None:
        judge = CodexSupportJudge()
        judge._client.generate = AsyncMock(side_effect=exc_instance)  # noqa: SLF001

        verdict, detail = await judge._vote_once("query", "context")  # noqa: SLF001

        assert verdict == SupportVerdict.UNAVAILABLE
        assert detail == type(exc_instance).__name__
        assert str(exc_instance) not in detail

    async def test_a_supported_reply_parses_through_unmodified(self) -> None:
        judge = CodexSupportJudge()
        fake_result = type("FakeResult", (), {"text": "SUPPORTED"})()
        judge._client.generate = AsyncMock(return_value=fake_result)  # noqa: SLF001

        verdict, detail = await judge._vote_once("query", "context")  # noqa: SLF001

        assert verdict == SupportVerdict.SUPPORTED
        assert detail == ""

    def test_name_carries_the_pinned_model(self) -> None:
        assert CodexSupportJudge().name == f"codex:{MODEL_TERRA}"

    async def test_vote_repetitions_runs_three_and_records_details(self) -> None:
        judge = CodexSupportJudge()
        judge._client.generate = AsyncMock(  # noqa: SLF001
            side_effect=CodexExecTimeoutError("timed out"),
        )

        votes = await judge.vote_repetitions("query", "context")

        assert votes == (SupportVerdict.UNAVAILABLE,) * 3
        assert judge.last_run_details == ("CodexExecTimeoutError",) * 3


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


class TestOllamaThinkRetry:
    def test_http_400_retries_without_think_and_records_which_attempt_succeeded(self) -> None:
        calls: list[dict] = []

        def _fake_urlopen(req, timeout=None):  # noqa: ANN001
            payload = json.loads(req.data.decode("utf-8"))
            calls.append(payload)
            if "think" in payload:
                raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", None, None)
            return _FakeHTTPResponse(json.dumps({"response": "SUPPORTED"}).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            verdict, sent_think, accepted_think, outcome = _ollama_generate_with_retry(
                "prompt", "http://127.0.0.1:11434", OLLAMA_MODEL, 5.0
            )

        assert len(calls) == 2
        assert "think" in calls[0]
        assert "think" not in calls[1]
        assert verdict == SupportVerdict.SUPPORTED
        assert sent_think is False
        assert accepted_think is False
        assert outcome == "ok"

    def test_first_attempt_success_never_retries(self) -> None:
        def _fake_urlopen(req, timeout=None):  # noqa: ANN001
            return _FakeHTTPResponse(json.dumps({"response": "NOT_SUPPORTED"}).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen) as mocked:
            verdict, sent_think, accepted_think, outcome = _ollama_generate_with_retry(
                "prompt", "http://127.0.0.1:11434", OLLAMA_MODEL, 5.0
            )

        assert mocked.call_count == 1
        assert verdict == SupportVerdict.NOT_SUPPORTED
        assert sent_think is True
        assert accepted_think is True
        assert outcome == "ok"

    def test_connection_failure_votes_unknown_not_unavailable(self) -> None:
        def _fake_urlopen(req, timeout=None):  # noqa: ANN001
            raise ConnectionRefusedError("no daemon")

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            verdict, _sent, _accepted, outcome = _ollama_generate_with_retry(
                "prompt", "http://127.0.0.1:11434", OLLAMA_MODEL, 5.0
            )

        assert verdict == SupportVerdict.UNKNOWN
        assert outcome.startswith("connection_error:")

    async def test_is_available_true_on_reachable_daemon(self) -> None:
        with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(b"{}")):
            reachable, detail = await OllamaSupportJudge().is_available()
        assert reachable is True
        assert detail == ""

    async def test_is_available_false_records_type_name(self) -> None:
        def _fake_urlopen(req, timeout=None):  # noqa: ANN001
            raise ConnectionRefusedError("no daemon")

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            reachable, detail = await OllamaSupportJudge().is_available()

        assert reachable is False
        assert detail == "ConnectionRefusedError"


class _FakeJudge:
    """Minimal duck-typed stand-in for CodexSupportJudge/OllamaSupportJudge,
    used only to drive `evaluate_support`'s resolution logic in isolation."""

    def __init__(
        self,
        name: str,
        votes: tuple[SupportVerdict, ...],
        *,
        available: bool = True,
        reachable: bool = True,
        reach_detail: str = "",
    ) -> None:
        self._name = name
        self._votes = votes
        self.available = available
        self._reachable = reachable
        self._reach_detail = reach_detail
        self.last_run_details: tuple[str, ...] = ("",) * len(votes)

    @property
    def name(self) -> str:
        return self._name

    async def vote_repetitions(self, query: str, context: str, *, reps: int = 3) -> tuple[SupportVerdict, ...]:
        return self._votes

    async def is_available(self) -> tuple[bool, str]:
        return self._reachable, self._reach_detail


def _forbid_construction(label: str):
    def _raise() -> None:
        raise AssertionError(f"{label} must not be constructed on this path")

    return _raise


class TestEvaluateSupportResolution:
    async def test_codex_decisive_skips_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_codex = _FakeJudge(
            "codex:gpt-5.6-terra",
            (SupportVerdict.SUPPORTED, SupportVerdict.SUPPORTED, SupportVerdict.NOT_SUPPORTED),
            available=True,
        )
        monkeypatch.setattr(support_signal_module, "CodexSupportJudge", lambda: fake_codex)
        monkeypatch.setattr(
            support_signal_module, "OllamaSupportJudge", _forbid_construction("OllamaSupportJudge")
        )

        decision = await evaluate_support("q", "c")

        assert decision.fallback_used is False
        assert decision.judge == "codex:gpt-5.6-terra"
        assert decision.verdict == SupportVerdict.SUPPORTED
        assert decision.votes == fake_codex._votes  # noqa: SLF001

    async def test_codex_adapter_absent_falls_back_to_ollama(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_codex = _FakeJudge("codex:gpt-5.6-terra", (), available=False)
        fake_ollama = _FakeJudge(
            "ollama:qwen3.8:27b-mlx",
            (SupportVerdict.SUPPORTED, SupportVerdict.SUPPORTED, SupportVerdict.NOT_SUPPORTED),
        )
        monkeypatch.setattr(support_signal_module, "CodexSupportJudge", lambda: fake_codex)
        monkeypatch.setattr(support_signal_module, "OllamaSupportJudge", lambda: fake_ollama)

        decision = await evaluate_support("q", "c")

        assert decision.fallback_used is True
        assert decision.judge == "ollama:qwen3.8:27b-mlx"
        assert decision.verdict == SupportVerdict.SUPPORTED

    async def test_codex_majority_unavailable_falls_back_to_ollama(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_codex = _FakeJudge(
            "codex:gpt-5.6-terra",
            (SupportVerdict.UNAVAILABLE, SupportVerdict.UNAVAILABLE, SupportVerdict.SUPPORTED),
            available=True,
        )
        fake_ollama = _FakeJudge("ollama:qwen3.8:27b-mlx", (SupportVerdict.NOT_SUPPORTED,) * 3)
        monkeypatch.setattr(support_signal_module, "CodexSupportJudge", lambda: fake_codex)
        monkeypatch.setattr(support_signal_module, "OllamaSupportJudge", lambda: fake_ollama)

        decision = await evaluate_support("q", "c")

        assert decision.fallback_used is True
        assert decision.judge == "ollama:qwen3.8:27b-mlx"
        assert decision.verdict == SupportVerdict.NOT_SUPPORTED

    async def test_both_judges_unavailable_produces_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_codex = _FakeJudge("codex:gpt-5.6-terra", (), available=False)
        fake_ollama = _FakeJudge(
            "ollama:qwen3.8:27b-mlx", (), reachable=False, reach_detail="ConnectionRefusedError"
        )
        monkeypatch.setattr(support_signal_module, "CodexSupportJudge", lambda: fake_codex)
        monkeypatch.setattr(support_signal_module, "OllamaSupportJudge", lambda: fake_ollama)

        decision = await evaluate_support("q", "c")

        assert decision.verdict == SupportVerdict.UNAVAILABLE
        assert decision.judge == "absent"
        assert decision.fallback_used is True
        assert decision.detail == "ConnectionRefusedError"
        assert decision.votes == (SupportVerdict.UNAVAILABLE,) * 3

    async def test_judge_override_bypasses_resolution_entirely(self, monkeypatch: pytest.MonkeyPatch) -> None:
        forced = _FakeJudge("codex:gpt-5.6-terra", (SupportVerdict.SUPPORTED,) * 3)
        monkeypatch.setattr(
            support_signal_module, "CodexSupportJudge", _forbid_construction("CodexSupportJudge")
        )
        monkeypatch.setattr(
            support_signal_module, "OllamaSupportJudge", _forbid_construction("OllamaSupportJudge")
        )

        decision = await evaluate_support("q", "c", judge=forced)

        assert decision.judge == "codex:gpt-5.6-terra"
        assert decision.fallback_used is False
        assert decision.verdict == SupportVerdict.SUPPORTED

    async def test_judge_override_surfaces_unavailable_detail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        forced = _FakeJudge("codex:gpt-5.6-terra", (SupportVerdict.UNAVAILABLE,) * 3)
        forced.last_run_details = ("CodexExecTimeoutError",) * 3

        decision = await evaluate_support("q", "c", judge=forced)

        assert decision.verdict == SupportVerdict.UNAVAILABLE
        assert decision.detail == "CodexExecTimeoutError"
        assert decision.fallback_used is False


class TestImportIsFree:
    def test_import_performs_no_network_io(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _blocked_connect(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("importing _support_signal must not touch the network")

        monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
        module_name = "backend.services.rag.agentic._support_signal"
        assert module_name in sys.modules
        importlib.reload(sys.modules[module_name])
