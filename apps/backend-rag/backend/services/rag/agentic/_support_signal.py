"""B2.1 §1 — the support signal (ruling I26, staff room 2026-09-12).

Answers one question a retrieval score cannot: does the retrieved CONTEXT
explicitly state the specific fact the QUERY asks for? Contract:
`evidence/2026-09/agent-nuzantara-backend-rag-b2-engine-63f75705/B2-1-build-spec.md`
§1, decided by the B1.4 measurement
(`research/operations/2026-09-11-bot-staff-room/B1-4-support-signal.md`).

**Chosen method (ruling I26):** candidate (iii), the Codex seat reached ONLY
through the UNCHANGED `backend.llm.codex_exec_client.CodexExecClient.generate`
adapter — never a hand-typed `codex exec` line, never a paid per-token
endpoint (the seat is the flat ChatGPT subscription the WA leg's daemon
already uses). Three binding conditions from the ruling:

1. **Determinism defence (K6).** Three repetitions, `majority()` takes the
   STRICT majority; a split vote fails closed to `NOT_SUPPORTED`.
2. **Fallback.** The local Ollama judge (candidate (ii), `qwen3.8:27b-mlx`,
   127.0.0.1, $0) is the RECORDED runner-up and designated fallback when the
   Codex seat is unavailable — the switch is always visible on the decision
   (`fallback_used`), never silent.
3. **The benchmark stays separate.** This module carries no manifest, no
   label, no benchmark logic — see `manifest_supplement_b2.json` and the B2.1
   harness for that side.

Pure and importable: NO import-time I/O, NO import-time seat probe.
Constructing `CodexSupportJudge`/`OllamaSupportJudge` and calling
`evaluate_support()` are the only operations that touch a filesystem stat,
a subprocess or the network — all at CALL time.

**PII boundary.** This module receives whatever `query`/`context` strings its
caller passes and never widens their exposure: it does not redact, cap or
inspect them for PII itself (`wa_package_builder.build_context_package` is
the caller responsible for handing this module the ALREADY-redacted,
ALREADY-capped text — see B2.1 build spec §3). It never logs, returns or
re-derives either judge's raw response text; on `UNAVAILABLE` it records only
the failing exception's TYPE NAME (`type(exc).__name__`), never the message,
never stdout/stderr.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from backend.llm.codex_exec_client import MODEL_TERRA, CodexExecClient

__all__ = [
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_OPTIONS",
    "OLLAMA_TIMEOUT_S",
    "RUBRIC",
    "CodexSupportJudge",
    "OllamaSupportJudge",
    "SupportDecision",
    "SupportVerdict",
    "evaluate_support",
    "majority",
]


class SupportVerdict(StrEnum):
    """The four decision values a support-signal repetition (or the overall
    decision) can carry. `UNAVAILABLE` is a fourth, distinct value — never
    folded into SUPPORTED/NOT_SUPPORTED/UNKNOWN (B1.4 §2 candidate (iii))."""

    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


# Shared rubric, byte-identical to B1.4's `RUBRIC_TEMPLATE`
# (evidence/2026-09/agent-nuzantara-backend-rag-b1-4-support-signal-0956ceb5/
# support_probe.py:102-106) — used by BOTH judges so the fallback answers the
# SAME question, not a different one.
RUBRIC = (
    "You judge evidence sufficiency. Question: {query}. Context: {context}. "
    "Does the context explicitly state the specific fact the question asks "
    "for? Reply with exactly one word: SUPPORTED, NOT_SUPPORTED or UNKNOWN."
)

_DECISION_TOKENS = {"SUPPORTED", "NOT_SUPPORTED", "UNKNOWN"}


def _strict_parse(text: str | None) -> SupportVerdict:
    """Shared strict parse (identical rule to B1.4's `_parse_decision`):
    first whitespace-delimited token, punctuation stripped, upper-cased,
    compared against the three answerable names. Anything else — empty text,
    a sentence, an unrecognised word — is `UNKNOWN`."""
    if not text:
        return SupportVerdict.UNKNOWN
    tokens = text.strip().split()
    if not tokens:
        return SupportVerdict.UNKNOWN
    cleaned = re.sub(r"[^A-Za-z_]", "", tokens[0]).upper()
    if cleaned in _DECISION_TOKENS:
        return SupportVerdict(cleaned)
    return SupportVerdict.UNKNOWN


_REPETITIONS = 3


def majority(votes: tuple[SupportVerdict, ...]) -> SupportVerdict:
    """Ruling I26 condition 1. A verdict wins only with a STRICT majority
    (>= 2 of the `_REPETITIONS` votes) of identical values. No strict
    majority (every vote distinct) fails CLOSED to `NOT_SUPPORTED`.
    `UNKNOWN` and `UNAVAILABLE` are ordinary values here, counted the same as
    `SUPPORTED`/`NOT_SUPPORTED` — they can win a majority in their own right,
    but they never COMBINE with each other or with anything else to manufacture
    a `SUPPORTED` majority that wasn't actually voted."""
    if len(votes) != _REPETITIONS:
        raise ValueError(f"majority() requires exactly {_REPETITIONS} votes, got {len(votes)}")
    counts: dict[SupportVerdict, int] = {}
    for vote in votes:
        counts[vote] = counts.get(vote, 0) + 1
    for value, count in counts.items():
        if count >= 2:
            return value
    return SupportVerdict.NOT_SUPPORTED


@dataclass(frozen=True)
class SupportDecision:
    """The result `evaluate_support()` hands its caller."""

    verdict: SupportVerdict
    votes: tuple[SupportVerdict, ...]
    judge: str  # "codex:gpt-5.6-terra" | "ollama:qwen3.8:27b-mlx" | "absent"
    fallback_used: bool
    latency_s: float
    detail: str  # exception TYPE NAME only on UNAVAILABLE; never raw stdout/stderr


def _dominant_detail(votes: tuple[SupportVerdict, ...], details: tuple[str, ...]) -> str:
    """Among the repetitions that voted UNAVAILABLE, the most common recorded
    exception type name (ties broken by first occurrence). Empty string when
    no repetition voted UNAVAILABLE."""
    counts: dict[str, int] = {}
    order: list[str] = []
    for vote, detail in zip(votes, details, strict=False):
        if vote is SupportVerdict.UNAVAILABLE and detail:
            if detail not in counts:
                order.append(detail)
            counts[detail] = counts.get(detail, 0) + 1
    if not counts:
        return ""
    return max(order, key=lambda d: counts[d])


# ---------------------------------------------------------------------------
# Codex judge — the chosen candidate (iii), through the unchanged adapter.
# ---------------------------------------------------------------------------
_CODEX_TIMEOUT_S = 90.0
_CODEX_MAX_CONCURRENCY = 4


class CodexSupportJudge:
    """The Codex seat, reached ONLY through `CodexExecClient.generate` — the
    adapter is UNCHANGED, this class never hand-types a `codex exec` argv.
    Model pinned to `MODEL_TERRA` (`gpt-5.6-terra`), the same constant
    `wa_codex_daemon.py` falls back to when `WA_CODEX_MODEL` is unset."""

    def __init__(self, *, model: str = MODEL_TERRA, timeout_s: float = _CODEX_TIMEOUT_S) -> None:
        self._model = model
        self._timeout_s = timeout_s
        self._client = CodexExecClient(model=model, timeout_s=timeout_s)
        self.last_run_details: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return f"codex:{self._model}"

    @property
    def available(self) -> bool:
        return self._client.available

    async def _vote_once(self, query: str, context: str) -> tuple[SupportVerdict, str]:
        prompt = RUBRIC.format(query=query, context=context)
        try:
            result = await self._client.generate(prompt, model=self._model, timeout_s=self._timeout_s)
        except Exception as exc:
            # repetition closed; the type name is recorded, the exception's
            # message and any stdout/stderr the adapter itself never exposes
            # are not re-derived here either.
            return SupportVerdict.UNAVAILABLE, type(exc).__name__
        return _strict_parse(result.text), ""

    async def vote_repetitions(
        self, query: str, context: str, *, reps: int = _REPETITIONS
    ) -> tuple[SupportVerdict, ...]:
        semaphore = asyncio.Semaphore(_CODEX_MAX_CONCURRENCY)

        async def _one() -> tuple[SupportVerdict, str]:
            async with semaphore:
                return await self._vote_once(query, context)

        results = await asyncio.gather(*(_one() for _ in range(reps)))
        votes = tuple(v for v, _ in results)
        self.last_run_details = tuple(d for _, d in results)
        return votes


# ---------------------------------------------------------------------------
# Ollama judge — the recorded runner-up and designated fallback (candidate ii).
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3.8:27b-mlx"
OLLAMA_TIMEOUT_S = 120.0
OLLAMA_OPTIONS = {"temperature": 0, "seed": 42}
_OLLAMA_PROBE_TIMEOUT_S = 5.0


def _ollama_generate_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/generate"


def _ollama_tags_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/tags"


def _check_ollama_reachable(url: str, timeout: float) -> None:
    """Blocking reachability probe — `GET /api/tags`, never a generate call.
    Not part of the shared candidate-ii shape (B1.4 has none): added so
    `evaluate_support` can tell "the seat is down" (this probe fails) apart
    from "the seat answered but the reply didn't parse" (which stays
    UNKNOWN, unchanged from B1.4's `call_candidate_ii`) — the two judges'
    `judge="absent"` / both-unavailable path depends on the distinction."""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout):
        return None


def _ollama_generate_once(
    prompt: str, base_url: str, model: str, timeout_s: float, *, include_think: bool
) -> tuple[SupportVerdict, bool, bool, str]:
    """One `POST /api/generate` call. Returns
    `(verdict, sent_think, accepted_think, outcome)`. Mirrors B1.4's
    `_ollama_call` shape exactly (same payload, same failure->UNKNOWN rule)."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "options": dict(OLLAMA_OPTIONS),
        "stream": False,
    }
    if include_think:
        payload["think"] = False
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _ollama_generate_url(base_url),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return SupportVerdict.UNKNOWN, include_think, False, f"http_error_{exc.code}"
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        return SupportVerdict.UNKNOWN, include_think, False, f"connection_error:{type(exc).__name__}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return SupportVerdict.UNKNOWN, include_think, include_think, "response_not_json"
    return _strict_parse(data.get("response", "")), include_think, include_think, "ok"


def _ollama_generate_with_retry(
    prompt: str, base_url: str, model: str, timeout_s: float
) -> tuple[SupportVerdict, bool, bool, str]:
    """`think: false` is attempted first; on HTTP 400 (server rejects the
    field) retry ONCE without it. Which attempt succeeded is carried in the
    returned `sent_think`/`accepted_think` flags — never re-derived from the
    model's raw text."""
    verdict, sent_think, accepted_think, outcome = _ollama_generate_once(
        prompt, base_url, model, timeout_s, include_think=True
    )
    if outcome == "http_error_400":
        verdict, sent_think, accepted_think, outcome = _ollama_generate_once(
            prompt, base_url, model, timeout_s, include_think=False
        )
    return verdict, sent_think, accepted_think, outcome


class OllamaSupportJudge:
    """The local, $0, no-egress fallback judge (candidate ii)."""

    def __init__(
        self,
        *,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout_s: float = OLLAMA_TIMEOUT_S,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._timeout_s = timeout_s
        self.last_run_details: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    async def is_available(self) -> tuple[bool, str]:
        try:
            await asyncio.to_thread(
                _check_ollama_reachable, _ollama_tags_url(self._base_url), _OLLAMA_PROBE_TIMEOUT_S
            )
        except Exception as exc:
            return False, type(exc).__name__
        return True, ""

    async def _vote_once(self, query: str, context: str) -> tuple[SupportVerdict, bool, bool, str]:
        prompt = RUBRIC.format(query=query, context=context)
        return await asyncio.to_thread(
            _ollama_generate_with_retry, prompt, self._base_url, self._model, self._timeout_s
        )

    async def vote_repetitions(
        self, query: str, context: str, *, reps: int = _REPETITIONS
    ) -> tuple[SupportVerdict, ...]:
        votes: list[SupportVerdict] = []
        for _ in range(reps):
            verdict, _sent_think, _accepted_think, _outcome = await self._vote_once(query, context)
            votes.append(verdict)
        self.last_run_details = ("",) * len(votes)
        return tuple(votes)


# ---------------------------------------------------------------------------
# The consumer-facing entry point.
# ---------------------------------------------------------------------------
_ABSENT_JUDGE = "absent"


async def evaluate_support(
    query: str,
    context: str,
    *,
    judge: CodexSupportJudge | OllamaSupportJudge | None = None,
) -> SupportDecision:
    """Ruling I26. Resolves the judge once: Codex when its adapter reports
    `available`, else Ollama with `fallback_used=True`. If the Codex judge's
    three repetitions come back a MAJORITY `UNAVAILABLE`, retry ONCE on the
    Ollama judge and set `fallback_used=True`. If Ollama is unreachable too
    the verdict is `UNAVAILABLE` (`judge="absent"`) — fail-closed, per the
    build spec's named residual (a dead Codex seat AND a dead local Ollama
    mutes the bot into blanket abstention; that risk is recorded in
    `pack.yml`, not engineered around here).

    `judge=` is an injection point for callers/tests that already hold a
    concrete judge instance: when given, it is used directly (its three
    repetitions, its own `majority()`), bypassing the Codex-then-Ollama
    resolution and reporting `fallback_used=False` — no fallback occurred
    because no resolution ran.
    """
    t0 = time.monotonic()

    if judge is not None:
        votes = await judge.vote_repetitions(query, context)
        verdict = majority(votes)
        details = getattr(judge, "last_run_details", ())
        detail = _dominant_detail(votes, details) if verdict is SupportVerdict.UNAVAILABLE else ""
        return SupportDecision(
            verdict=verdict,
            votes=votes,
            judge=judge.name,
            fallback_used=False,
            latency_s=time.monotonic() - t0,
            detail=detail,
        )

    codex_judge = CodexSupportJudge()
    if codex_judge.available:
        codex_votes = await codex_judge.vote_repetitions(query, context)
        codex_verdict = majority(codex_votes)
        if codex_verdict is not SupportVerdict.UNAVAILABLE:
            return SupportDecision(
                verdict=codex_verdict,
                votes=codex_votes,
                judge=codex_judge.name,
                fallback_used=False,
                latency_s=time.monotonic() - t0,
                detail="",
            )
        # Majority of the Codex repetitions were UNAVAILABLE — fall through
        # to the recorded fallback rather than reporting a dead seat's
        # majority directly.

    ollama_judge = OllamaSupportJudge()
    reachable, reach_detail = await ollama_judge.is_available()
    if not reachable:
        return SupportDecision(
            verdict=SupportVerdict.UNAVAILABLE,
            votes=(SupportVerdict.UNAVAILABLE,) * _REPETITIONS,
            judge=_ABSENT_JUDGE,
            fallback_used=True,
            latency_s=time.monotonic() - t0,
            detail=reach_detail,
        )
    ollama_votes = await ollama_judge.vote_repetitions(query, context)
    return SupportDecision(
        verdict=majority(ollama_votes),
        votes=ollama_votes,
        judge=ollama_judge.name,
        fallback_used=True,
        latency_s=time.monotonic() - t0,
        detail="",
    )
