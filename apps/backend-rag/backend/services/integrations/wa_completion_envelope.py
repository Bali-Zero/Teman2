"""B2.4 — authenticated completion envelope (design `B2-4-design.md` §1.2).

Why a MAC and not a plain parsed JSON reply: before the daemon carrying this
module is provisioned, an OLD daemon still returns raw model text over the
same transport field, and a prompt-injected client message could make the
model print a look-alike JSON claiming a SUPPORTED verdict. Binding the
reply to `package_hash` alone is not enough either — Codex runs with
read-only shell access and could compute and print its own prompt's hash
itself. A MAC under a key derived from `WA_BROKER_KEY` closes both holes:
the codex child process never sees this key (only Fly and the daemon
process do), so it cannot forge one. Decoding is strict and NEVER raises —
any violation returns `None` — so a caller fails closed on a corrupt or
forged wire without needing to special-case an exception.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from backend.services.rag.agentic._support_signal import SupportVerdict, majority

ENVELOPE_VERSION = 1
_KEY_CONTEXT = b"wa-completion-envelope/v1"
_FIELDS = frozenset({"v", "package_hash", "verdict", "votes", "judge", "answer", "mac"})
_JUDGE_RE = re.compile(r"^(codex|ollama):[A-Za-z0-9._:-]{1,60}$")
_ANSWERABLE = frozenset(
    {SupportVerdict.SUPPORTED, SupportVerdict.NOT_SUPPORTED, SupportVerdict.UNKNOWN}
)
_ANSWERABLE_VALUES = frozenset(verdict.value for verdict in _ANSWERABLE)
_VOTE_VALUES = frozenset(verdict.value for verdict in SupportVerdict)


@dataclass(frozen=True)
class SupportCompletion:
    """The verified content of a decoded envelope."""

    verdict: SupportVerdict
    votes: tuple[SupportVerdict, ...]
    judge: str
    answer: str | None


def _canonical(obj: dict[str, object]) -> str:
    """Same serializer discipline as `wa_package_builder._canonical_wire`:
    `sort_keys` makes it independent of dict insertion order, compact
    `separators` plus `ensure_ascii=False` keep it deterministic."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _derive_key(key: str) -> bytes:
    """Domain-separated from the HTTP `X-API-Key` use of the same secret —
    a MAC computed under this key can never be replayed as an auth header,
    or vice versa."""
    return hmac.new(key.encode("utf-8"), _KEY_CONTEXT, hashlib.sha256).digest()


def encode_completion(
    *,
    key: str,
    package_hash: str,
    verdict: SupportVerdict,
    votes: tuple[SupportVerdict, ...],
    judge: str,
    answer: str | None,
) -> str:
    """Seal a support verdict (and, on SUPPORTED, the generated answer) into
    the wire envelope. Raises `ValueError` on any input that could not have
    come from an honest daemon run — never silently coerces one."""
    if not key:
        raise ValueError("encode_completion: key must not be empty")
    if not package_hash:
        raise ValueError("encode_completion: package_hash must not be empty")
    if verdict not in _ANSWERABLE:
        raise ValueError(
            "encode_completion: verdict must be one of the three answerable values "
            "(UNAVAILABLE is never enveloped)"
        )
    if len(votes) != 3 or not all(isinstance(vote, SupportVerdict) for vote in votes):
        raise ValueError("encode_completion: votes must be exactly 3 SupportVerdict values")
    if majority(votes) is not verdict:
        raise ValueError("encode_completion: verdict does not match majority(votes)")
    if not _JUDGE_RE.match(judge):
        raise ValueError("encode_completion: judge does not match the expected shape")
    if verdict is SupportVerdict.SUPPORTED:
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("encode_completion: SUPPORTED requires a non-empty answer")
    elif answer is not None:
        raise ValueError("encode_completion: a non-SUPPORTED verdict must carry answer=None")

    body: dict[str, object] = {
        "v": ENVELOPE_VERSION,
        "package_hash": package_hash,
        "verdict": verdict.value,
        "votes": [vote.value for vote in votes],
        "judge": judge,
        "answer": answer,
    }
    mac = hmac.new(_derive_key(key), _canonical(body).encode("utf-8"), hashlib.sha256).hexdigest()
    return _canonical({**body, "mac": mac})


def _decode(text: str | None, *, key: str | None, package_hash: str) -> SupportCompletion | None:
    """The real decode logic — every explicit structural/MAC/semantic check
    lives here, unchanged. Kept private: `decode_completion` is the public
    NEVER-raises boundary, this function is not guaranteed to be exception-
    free on its own (see its caller's docstring)."""
    if not key or text is None:
        return None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or set(obj.keys()) != _FIELDS:
        return None

    version = obj.get("v")
    if isinstance(version, bool) or version != ENVELOPE_VERSION:
        return None

    mac = obj.get("mac")
    stored_hash = obj.get("package_hash")
    judge = obj.get("judge")
    if not isinstance(mac, str) or not isinstance(stored_hash, str) or not isinstance(judge, str):
        return None

    # Authenticate the raw bytes BEFORE trusting any other field's value.
    # Compared as BYTES, not str: `hmac.compare_digest` raises `TypeError`
    # for `str` arguments containing non-ASCII characters, and `mac`/
    # `stored_hash` are attacker-controlled (an old, un-provisioned daemon
    # forwards raw model text here, which a prompt injection can shape) —
    # a comparison that can raise on a forged input is not a comparison,
    # it is a crash oracle. `expected_mac`/`package_hash` are always our
    # own ASCII hex, so encoding them `ascii` is safe by construction.
    body = {field: value for field, value in obj.items() if field != "mac"}
    expected_mac = hmac.new(
        _derive_key(key), _canonical(body).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(mac.encode("utf-8"), expected_mac.encode("ascii")):
        return None
    if not hmac.compare_digest(stored_hash.encode("utf-8"), package_hash.encode("ascii")):
        return None

    verdict_raw = obj.get("verdict")
    if not isinstance(verdict_raw, str) or verdict_raw not in _ANSWERABLE_VALUES:
        return None
    verdict = SupportVerdict(verdict_raw)

    votes_raw = obj.get("votes")
    if (
        not isinstance(votes_raw, list)
        or len(votes_raw) != 3
        or not all(isinstance(item, str) and item in _VOTE_VALUES for item in votes_raw)
    ):
        return None
    votes = tuple(SupportVerdict(item) for item in votes_raw)
    if majority(votes) is not verdict:
        return None

    if not _JUDGE_RE.match(judge):
        return None

    answer = obj.get("answer")
    if verdict is SupportVerdict.SUPPORTED:
        if not isinstance(answer, str) or not answer.strip():
            return None
    elif answer is not None:
        return None

    return SupportCompletion(verdict=verdict, votes=votes, judge=judge, answer=answer)


def decode_completion(
    text: str | None, *, key: str | None, package_hash: str
) -> SupportCompletion | None:
    """Verify and parse an envelope. NEVER raises: any structural, MAC or
    semantic violation returns `None` — fail closed, silently, so callers
    never need a try/except around an untrusted wire.

    The explicit checks in `_decode` catch every violation this module's
    author anticipated; this wrapper is the BACKSTOP for the ones an
    attacker can still reach through a legacy, un-provisioned daemon that
    forwards raw (prompt-injectable) model text over the same field —
    e.g. deeply nested JSON exhausting the parser's recursion limit, or a
    lone UTF-16 surrogate that `_canonical(...).encode("utf-8")` cannot
    encode. Never let `_decode` raise past this line."""
    try:
        return _decode(text, key=key, package_hash=package_hash)
    except Exception:
        return None
