"""B1.4 support-signal probe harness.

Measures four candidate "does the retrieved text contain the requested fact"
methods against the counterfactual pairs of the B1.3 mandatory manifest
(`apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json`).
Contract: `research/operations/2026-09-11-bot-staff-room/B1-design.md` §4 B1.4,
`evidence/2026-09/agent-nuzantara-backend-rag-b1-4-support-signal-0956ceb5/B1-4-build-spec.md`.

Candidates:
  (i)   deterministic span check on slot rules derived from the QUERY (no imports).
  (ii)  local Ollama judge (`qwen3.8:27b-mlx`, 127.0.0.1:11434, no egress, $0).
  (iii) the Codex seat, ONLY through the unchanged
        `backend.llm.codex_exec_client.CodexExecClient.generate` adapter, model
        pinned to the WA leg's production model (`MODEL_TERRA`, see
        `wa_codex_daemon.py:159`). Inputs are the REDACTED query and the capped
        REDACTED context, built with the SAME `wa_dlp.redact_package_fields`
        call and the SAME chunk cap `wa_package_builder.py` uses at its own
        DLP gate (`wa_package_builder.py:585`).
  (iv)  control — no support signal, the scorer as it exists today
        (`reasoning_utils.calculate_evidence_score` +
        `_abstain_policy.build_abstain_policy(...).label_abstains`).

At DECISION time every candidate reads only a case's `query`, `context` (list
of chunk strings) and `provenance_fixture.sources` — never a label field
(`stratum`, `expected_*`, `supporting_span`, `missing_fact_explanation`,
`requested_fact`, `case_id`). Those are read only in the SCORING pass, after
every decision already exists.

Network: 127.0.0.1:11434 (candidate ii) and the Codex adapter's own fixed
subprocess (candidate iii, `codex exec ...` per its documented argv prefix).
Nothing else — no embedding call, no other LLM, no paid per-token API.

CLI: `--manifest PATH` (default: `<backend-root>/backend/tests/benchmarks/
evidence_sufficiency/manifest_mandatory.json`), `--backend-root PATH` (the
`apps/backend-rag` directory added to `sys.path` so `backend.llm
.codex_exec_client`, `backend.services.rag.agentic.wa_dlp`,
`.reasoning_utils` and `._abstain_policy` import from THAT tree, never an
ambient `PYTHONPATH`), `--ollama-url` (base URL, default
`http://127.0.0.1:11434`; `/api/generate` and `/api/tags` are appended by
the harness), `--reps`, `--candidates`, `--out`, `--limit-pairs N` (smoke
only — limits to the first N pair_ids, sorted).

The receipts additionally pin, at `meta`: host, UTC start/end, manifest
sha256, the backend-root's own git HEAD sha (read from the tree actually
imported, distinct from `base_sha` which is the harness FILE's own git
tree), the imported adapter file's sha256, `codex --version`, the resolved
`CODEX_HOME`'s basename ONLY (never its contents — the adapter's own
`_resolve_codex_home()` order is explicit-arg -> env `CODEX_HOME` -> `~/
.codex`; this harness never passes an explicit `codex_home=`, so it always
resolves from the env var when set, matching the adapter unchanged), the
Ollama model id and its digest from `GET /api/tags`, and the exact request
options sent per call.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure Sentry (and anything else gated the same way) never initializes from
# a bare import of backend modules — this harness's fence is "no network
# other than 127.0.0.1:11434 and the Codex adapter subprocess" and a stray
# Sentry init on import would violate it silently.
os.environ.setdefault("SKIP_SENTRY_INIT", "1")

# `backend.app.core.config.Settings` (pydantic-settings) is instantiated at
# IMPORT TIME of `backend.services.rag.__init__` — reached transitively by
# every candidate (iii)/(iv) lazy import (`wa_dlp`, `wa_package_builder`,
# `reasoning_utils`, `_abstain_policy` all sit under `backend.services.rag`)
# — and raises `pydantic.ValidationError` (`jwt_secret_key`, `api_keys`)
# without these set, exactly as `backend/tests/conftest.py:16-23` documents
# ("must be set FIRST, before any import") and sets for the test suite. Same
# fixed, clearly-fake placeholders as that file — never a real credential;
# `setdefault` never overrides a value already present in the environment.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only-nuzantara")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")

# The Codex CLI is a Node shebang script commonly installed under
# /opt/homebrew/bin; the caller is expected to already have it on PATH, but
# the harness makes that a guarantee rather than a hope (CodexExecClient's
# own `_build_env` forwards this process's PATH verbatim to the child).
if "/opt/homebrew/bin" not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + "/opt/homebrew/bin"

# ---------------------------------------------------------------------------
# Shared rubric (candidates ii and iii — identical text per the build spec).
# ---------------------------------------------------------------------------
RUBRIC_TEMPLATE = (
    "You judge evidence sufficiency. Question: {query}. Context: {context}. "
    "Does the context explicitly state the specific fact the question asks "
    "for? Reply with exactly one word: SUPPORTED, NOT_SUPPORTED or UNKNOWN."
)

_DECISION_TOKENS = {"SUPPORTED", "NOT_SUPPORTED", "UNKNOWN"}


def _parse_decision(text: str | None) -> str:
    """Strict parse: first token, case-insensitive, punctuation stripped;
    anything else (including empty text) -> UNKNOWN."""
    if not text:
        return "UNKNOWN"
    tokens = text.strip().split()
    if not tokens:
        return "UNKNOWN"
    cleaned = re.sub(r"[^A-Za-z_]", "", tokens[0]).upper()
    return cleaned if cleaned in _DECISION_TOKENS else "UNKNOWN"


# ---------------------------------------------------------------------------
# Candidate (i) — deterministic span check. No repo imports: the method is
# entirely self-contained regex on the QUERY (slot selection) and the
# CONTEXT (pattern search). Requested-fact extraction is part of the method
# (query -> slot), never read from the manifest's `requested_fact` field.
# ---------------------------------------------------------------------------
_PRICE_QUERY_RE = re.compile(r"\b(?:price|cost|harga|mahal)\b|all[- ]in", re.IGNORECASE)
_CAPITAL_QUERY_RE = re.compile(r"\b(?:capital|modal)\b", re.IGNORECASE)
_DURATION_QUERY_RE = re.compile(
    r"\b(?:duration|how long|processing time)\b|berapa\s+lama|lama\s+proses",
    re.IGNORECASE,
)
_REQUIREMENTS_QUERY_RE = re.compile(r"\b(?:requirement|requirements|syarat)\b", re.IGNORECASE)

_AMOUNT_RE = re.compile(r"\b(?:IDR|Rp)\.?\s*[\d][\d.,]*\b", re.IGNORECASE)
_CAPITAL_WORD_RE = re.compile(r"\b(?:capital|modal)\b", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"\b\d+(?:\s*(?:-|–|to|sampai|hingga)\s*\d+)?\s*"
    r"(?:weeks?|days?|months?|minggu|hari|bulan)\b",
    re.IGNORECASE,
)
_REQUIREMENT_LEXICON: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:deed|akta)\b", re.IGNORECASE),
    re.compile(r"\bNPWP\b", re.IGNORECASE),
    re.compile(r"\bKBLI\b", re.IGNORECASE),
    re.compile(r"\b(?:address|alamat)\b", re.IGNORECASE),
    re.compile(r"\b(?:approval|SK|pengesahan)\b", re.IGNORECASE),
)


def _slot_for_query(query: str) -> str | None:
    if _PRICE_QUERY_RE.search(query):
        return "price"
    if _CAPITAL_QUERY_RE.search(query):
        return "capital"
    if _DURATION_QUERY_RE.search(query):
        return "duration"
    if _REQUIREMENTS_QUERY_RE.search(query):
        return "requirements"
    return None


def decide_i(query: str, context_text: str) -> dict[str, Any]:
    slot = _slot_for_query(query)
    if slot is None:
        return {"decision": "UNKNOWN", "outcome": "no_slot_matched", "slot": None}
    if slot == "price":
        matched = bool(_AMOUNT_RE.search(context_text))
    elif slot == "capital":
        matched = bool(_AMOUNT_RE.search(context_text) and _CAPITAL_WORD_RE.search(context_text))
    elif slot == "duration":
        matched = bool(_DURATION_RE.search(context_text))
    else:  # requirements
        hits = sum(1 for pattern in _REQUIREMENT_LEXICON if pattern.search(context_text))
        matched = hits >= 2
    decision = "SUPPORTED" if matched else "NOT_SUPPORTED"
    return {"decision": decision, "outcome": "ok", "slot": slot}


# ---------------------------------------------------------------------------
# Candidate (ii) — local Ollama judge.
# ---------------------------------------------------------------------------
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3.8:27b-mlx"
OLLAMA_TIMEOUT_S = 120.0
OLLAMA_OPTIONS = {"temperature": 0, "seed": 42}


def _ollama_generate_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/generate"


def _ollama_tags_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/tags"


def fetch_ollama_model_digest(base_url: str, model: str) -> dict[str, Any]:
    """`GET /api/tags` and return the digest of `model`, or an error record.
    Read-only, no generation call — used only to pin the receipts' model
    identity."""
    req = urllib.request.Request(_ollama_tags_url(base_url), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 - report, never raise into the run
        return {"model": model, "digest": None, "error": f"{type(exc).__name__}: {exc}"}
    for entry in data.get("models", []):
        if entry.get("name") == model or entry.get("model") == model:
            return {"model": model, "digest": entry.get("digest"), "error": None}
    return {"model": model, "digest": None, "error": "model_not_in_tags"}


def _ollama_call(prompt: str, ollama_base_url: str, *, include_think: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "options": dict(OLLAMA_OPTIONS),
        "stream": False,
    }
    if include_think:
        payload["think"] = False
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _ollama_generate_url(ollama_base_url),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request_options = {
        "options": dict(OLLAMA_OPTIONS),
        "stream": False,
        "think_sent": include_think,
    }
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        latency = time.monotonic() - t0
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            detail = ""
        return {
            "decision": "UNKNOWN",
            "outcome": f"http_error_{exc.code}",
            "latency_s": latency,
            "raw_first_token": None,
            "sent_think": include_think,
            "accepted_think": False,
            "error_detail": detail,
            "request_options": request_options,
        }
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        latency = time.monotonic() - t0
        return {
            "decision": "UNKNOWN",
            "outcome": f"connection_error:{type(exc).__name__}",
            "latency_s": latency,
            "raw_first_token": None,
            "sent_think": include_think,
            "accepted_think": False,
            "request_options": request_options,
        }
    latency = time.monotonic() - t0
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "decision": "UNKNOWN",
            "outcome": "response_not_json",
            "latency_s": latency,
            "raw_first_token": raw[:64] if raw else None,
            "sent_think": include_think,
            "accepted_think": include_think,
            "request_options": request_options,
        }
    text = data.get("response", "")
    decision = _parse_decision(text)
    first_token = text.strip().split()[0] if text and text.strip() else None
    return {
        "decision": decision,
        "outcome": "ok",
        "latency_s": latency,
        "raw_first_token": first_token,
        "sent_think": include_think,
        "accepted_think": include_think,
        "request_options": request_options,
    }


def call_candidate_ii(query: str, context_text: str, ollama_base_url: str) -> dict[str, Any]:
    prompt = RUBRIC_TEMPLATE.format(query=query, context=context_text)
    result = _ollama_call(prompt, ollama_base_url, include_think=True)
    if result["outcome"] == "http_error_400":
        # Server rejected an unrecognised field — retry without `think`.
        result = _ollama_call(prompt, ollama_base_url, include_think=False)
    return result


# ---------------------------------------------------------------------------
# Candidate (iii) — Codex seat via the unchanged CodexExecClient adapter.
# ---------------------------------------------------------------------------
def _load_codex_adapter() -> tuple[Any, str | None]:
    """Import the adapter module and hash its file. Returns (module, sha256
    or None if the file could not be hashed)."""
    import backend.llm.codex_exec_client as codex_exec_client

    try:
        sha = hashlib.sha256(Path(codex_exec_client.__file__).read_bytes()).hexdigest()
    except OSError:
        sha = None
    return codex_exec_client, sha


def _git_head_sha(cwd: Path) -> str | None:
    """`git rev-parse HEAD` at `cwd`, or None — never an empty string — when
    `cwd` is not inside a git repo (e.g. a standalone-copied harness) or the
    command otherwise fails. A bare `.stdout.strip()` on a non-zero exit
    silently returns `""`, which is indistinguishable from "the repo's HEAD
    really is an empty string" in the receipts; this makes the two cases
    distinct."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def fetch_codex_version() -> str | None:
    """`codex --version`, read-only, never a hand-typed `codex exec` call —
    used only to pin the receipts' binary identity, distinct from the
    adapter's own subprocess invocation in `generate()`."""
    try:
        result = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, timeout=15, check=False
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    return (result.stdout or result.stderr or "").strip() or None


def codex_home_basename() -> str | None:
    """Basename ONLY of the `CODEX_HOME` this process would resolve to —
    NEVER its contents, never the full path (which would reveal `$HOME`).
    Mirrors `CodexExecClient._resolve_codex_home()`'s documented order
    (`backend/llm/codex_exec_client.py:928-953`, read-only, confirmed):
    explicit constructor arg -> env `CODEX_HOME` -> `~/.codex`. This
    harness never passes an explicit `codex_home=` (§ call_candidate_iii),
    so it always follows the env var when set, letting the adapter's own
    resolution run unchanged, per the mandate's exception (1)."""
    env_home = os.environ.get("CODEX_HOME", "").strip()
    if env_home:
        return Path(env_home).resolve().name
    return (Path.home() / ".codex").resolve().name


def _redact_and_cap(query: str, context_chunks: list[str]) -> tuple[str, str]:
    """Mirror `wa_package_builder.py`'s own DLP gate exactly: cap the chunks
    the same way (`_cap_chunks`, the same `_MAX_CHUNKS`/`_MAX_CHUNK_CHARS`
    constants), then redact history+chunks through the SAME
    `wa_dlp.redact_package_fields` call site (`wa_package_builder.py:585`).
    Returns (redacted_query, redacted_context_text). Raises whatever
    `redact_package_fields` raises (e.g. `DlpOverflow`) — the caller decides
    how to turn that into an UNAVAILABLE candidate result."""
    from backend.services.rag.agentic.wa_dlp import redact_package_fields
    from backend.services.rag.agentic.wa_package_builder import _cap_chunks

    history = [{"role": "user", "content": query}]
    raw_chunks = [{"text": chunk} for chunk in context_chunks]
    capped_chunks = _cap_chunks(raw_chunks)
    dlp_result = redact_package_fields(history, capped_chunks, None)
    redacted_query = dlp_result.history[0]["content"]
    redacted_context = "\n".join(chunk["text"] for chunk in dlp_result.chunks)
    return redacted_query, redacted_context


async def call_candidate_iii(
    query: str,
    context_chunks: list[str],
    *,
    model: str,
    timeout_s: float = 90.0,
) -> dict[str, Any]:
    try:
        codex_exec_client, _ = _load_codex_adapter()
    except Exception as exc:  # ImportError or anything else at import time
        return {
            "decision": "UNAVAILABLE",
            "outcome": f"import_error:{type(exc).__name__}",
            "latency_s": 0.0,
            "raw_first_token": None,
        }

    try:
        redacted_query, redacted_context = _redact_and_cap(query, context_chunks)
    except Exception as exc:  # DlpOverflow or any detector failure — fail closed
        return {
            "decision": "UNAVAILABLE",
            "outcome": f"dlp_error:{type(exc).__name__}",
            "latency_s": 0.0,
            "raw_first_token": None,
        }

    prompt = RUBRIC_TEMPLATE.format(query=redacted_query, context=redacted_context)

    try:
        client = codex_exec_client.CodexExecClient(model=model, timeout_s=timeout_s)
    except Exception as exc:  # CodexExecModelNotAllowedError / ValueError
        return {
            "decision": "UNAVAILABLE",
            "outcome": f"construction_error:{type(exc).__name__}",
            "latency_s": 0.0,
            "raw_first_token": None,
        }

    if not client.available:
        return {
            "decision": "UNAVAILABLE",
            "outcome": "adapter_unavailable",
            "latency_s": 0.0,
            "raw_first_token": None,
        }

    t0 = time.monotonic()
    try:
        result = await client.generate(prompt, model=model, timeout_s=timeout_s)
    except Exception as exc:
        # CodexExecUnavailableError / CodexExecAuthError / CodexExecQuotaError /
        # CodexExecProcessError / CodexExecOutputShapeError /
        # CodexExecTimeoutError / CodexExecCommunicationError — any of the
        # adapter's typed failures fail this candidate closed, never a
        # hand-typed fallback invocation.
        latency = time.monotonic() - t0
        return {
            "decision": "UNAVAILABLE",
            "outcome": f"adapter_error:{type(exc).__name__}",
            "latency_s": latency,
            "raw_first_token": None,
        }
    latency = time.monotonic() - t0
    decision = _parse_decision(result.text)
    first_token = result.text.strip().split()[0] if result.text and result.text.strip() else None
    return {
        "decision": decision,
        "outcome": "ok",
        "latency_s": latency,
        "raw_first_token": first_token,
        "model": result.model,
        "adapter_latency_ms": result.latency_ms,
        # `codex exec` exposes no temperature/seed control (build spec,
        # candidate iii) — recorded literally rather than omitted, so the
        # receipts never imply a control that was never sent.
        "request_options": "not_controllable_by_codex_exec",
    }


async def run_candidate_iii_batch(
    items: list[tuple[str, str, list[str]]],
    *,
    model: str,
    timeout_s: float = 90.0,
    max_concurrency: int = 4,
) -> dict[str, dict[str, Any]]:
    """`items` is a list of (call_key, query, context_chunks). At most
    `max_concurrency` calls in flight at once."""
    semaphore = asyncio.Semaphore(max_concurrency)
    results: dict[str, dict[str, Any]] = {}

    async def _one(key: str, query: str, context_chunks: list[str]) -> None:
        async with semaphore:
            results[key] = await call_candidate_iii(
                query, context_chunks, model=model, timeout_s=timeout_s
            )

    await asyncio.gather(*(_one(key, query, chunks) for key, query, chunks in items))
    return results


# ---------------------------------------------------------------------------
# Candidate (iv) — control. No support signal: the scorer as it exists today.
# ---------------------------------------------------------------------------
def decide_iv(
    query: str, context_chunks: list[str], sources: list[dict[str, Any]]
) -> dict[str, Any]:
    from backend.services.rag.agentic._abstain_policy import build_abstain_policy
    from backend.services.rag.agentic.reasoning_utils import (
        calculate_evidence_score,
    )

    score = calculate_evidence_score(
        sources=sources,
        context_gathered=context_chunks,
        query=query,
    )
    policy = build_abstain_policy(query)
    abstains = policy.label_abstains(score)
    decision = "NOT_SUPPORTED" if abstains else "SUPPORTED"
    return {
        "decision": decision,
        "outcome": "ok",
        "evidence_score": score,
        "label_abstains": abstains,
    }


# ---------------------------------------------------------------------------
# Manifest / pairing.
# ---------------------------------------------------------------------------
def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    return json.loads(raw), sha


def group_pairs(cases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group cases by `pair_id`, keeping only pairs with exactly one
    `sufficient` and one `relevant_insufficient` member (the B1.3 manifest's
    counterfactual-pair contract)."""
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        pair_id = case.get("pair_id")
        if not pair_id:
            continue
        by_pair.setdefault(pair_id, []).append(case)

    valid: dict[str, list[dict[str, Any]]] = {}
    for pair_id, members in by_pair.items():
        if len(members) != 2:
            continue
        strata = {m.get("stratum") for m in members}
        if strata != {"sufficient", "relevant_insufficient"}:
            continue
        valid[pair_id] = sorted(members, key=lambda m: m.get("stratum", ""))
    return valid


def _context_text(case: dict[str, Any]) -> str:
    context = case.get("context", [])
    if isinstance(context, str):
        return context
    return "\n".join(context)


def _sources(case: dict[str, Any]) -> list[dict[str, Any]]:
    return case.get("provenance_fixture", {}).get("sources", [])


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------
_ALL_CANDIDATES = ("i", "ii", "iii", "iv")
_COST_BY_CANDIDATE = {
    "i": "none",
    "ii": "$0 local",
    "iii": "flat subscription",
    "iv": "none",
}
DEFAULT_BACKEND_ROOT = "apps/backend-rag"
DEFAULT_MANIFEST_RELATIVE = Path(
    "backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json"
)


def _iter_pair_cases(
    pairs: dict[str, list[dict[str, Any]]], limit: int | None
) -> list[tuple[str, dict[str, Any]]]:
    pair_ids = sorted(pairs.keys())
    if limit is not None:
        pair_ids = pair_ids[:limit]
    out: list[tuple[str, dict[str, Any]]] = []
    for pair_id in pair_ids:
        for case in pairs[pair_id]:
            out.append((pair_id, case))
    return out


async def run(args: argparse.Namespace) -> dict[str, Any]:
    utc_start = datetime.now(timezone.utc).isoformat()

    # `--backend-root` goes on sys.path BEFORE any lazy `import backend...`
    # runs (decide_iv, _load_codex_adapter, _redact_and_cap) so the product
    # modules (CodexExecClient, wa_dlp, reasoning_utils, _abstain_policy)
    # import from THIS tree, never an ambient PYTHONPATH.
    backend_root = Path(args.backend_root).resolve()
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    manifest_path = (
        Path(args.manifest) if args.manifest else backend_root / DEFAULT_MANIFEST_RELATIVE
    )
    manifest, manifest_sha256 = load_manifest(manifest_path)
    cases = manifest.get("cases", [])
    pairs = group_pairs(cases)
    pair_cases = _iter_pair_cases(pairs, args.limit_pairs)

    candidates = [c.strip() for c in args.candidates.split(",") if c.strip()]
    for c in candidates:
        if c not in _ALL_CANDIDATES:
            raise SystemExit(f"unknown candidate: {c!r} (allowed: {_ALL_CANDIDATES})")

    # cwd is the HARNESS FILE's own location, never the manifest's and never
    # --backend-root: the manifest/backend-root may live outside this
    # checkout entirely (e.g. copied standalone to /tmp on Mini, which is
    # NOT a git repo — `_git_head_sha` returns None rather than an empty
    # string in that case), and base_sha names the code's base commit, not
    # wherever the manifest or the imported tree sits.
    base_sha = _git_head_sha(Path(__file__).resolve().parent)
    # cwd IS --backend-root: this pins the tree the harness actually imports
    # product modules from (distinct from base_sha above).
    backend_root_git_sha = _git_head_sha(backend_root)

    adapter_file_sha256: str | None = None
    if "iii" in candidates:
        try:
            _, adapter_file_sha256 = _load_codex_adapter()
        except Exception:
            adapter_file_sha256 = None

    codex_version = fetch_codex_version() if "iii" in candidates else None
    codex_home = codex_home_basename() if "iii" in candidates else None
    ollama_digest_record = (
        fetch_ollama_model_digest(args.ollama_url, OLLAMA_MODEL) if "ii" in candidates else None
    )

    codex_model = args.codex_model

    calls: list[dict[str, Any]] = []

    # --- candidate i (deterministic, no network) ---
    if "i" in candidates:
        for pair_id, case in pair_cases:
            context_text = _context_text(case)
            for rep in range(args.reps):
                t0 = time.monotonic()
                result = decide_i(case["query"], context_text)
                latency = time.monotonic() - t0
                calls.append(
                    {
                        "candidate": "i",
                        "pair_id": pair_id,
                        "case_id": case.get("case_id"),
                        "rep": rep,
                        "decision": result["decision"],
                        "outcome": result["outcome"],
                        "latency_s": latency,
                        "raw_first_token": None,
                        "cost": _COST_BY_CANDIDATE["i"],
                        "detail": {"slot": result.get("slot")},
                    }
                )

    # --- candidate iv (deterministic given the fixture, no network) ---
    if "iv" in candidates:
        for pair_id, case in pair_cases:
            context_chunks = case.get("context", [])
            if isinstance(context_chunks, str):
                context_chunks = [context_chunks]
            sources = _sources(case)
            for rep in range(args.reps):
                t0 = time.monotonic()
                try:
                    result = decide_iv(case["query"], context_chunks, sources)
                except Exception as exc:
                    latency = time.monotonic() - t0
                    calls.append(
                        {
                            "candidate": "iv",
                            "pair_id": pair_id,
                            "case_id": case.get("case_id"),
                            "rep": rep,
                            "decision": "UNKNOWN",
                            "outcome": f"error:{type(exc).__name__}",
                            "latency_s": latency,
                            "raw_first_token": None,
                            "cost": _COST_BY_CANDIDATE["iv"],
                        }
                    )
                    continue
                latency = time.monotonic() - t0
                calls.append(
                    {
                        "candidate": "iv",
                        "pair_id": pair_id,
                        "case_id": case.get("case_id"),
                        "rep": rep,
                        "decision": result["decision"],
                        "outcome": result["outcome"],
                        "latency_s": latency,
                        "raw_first_token": None,
                        "cost": _COST_BY_CANDIDATE["iv"],
                        "detail": {
                            "evidence_score": result.get("evidence_score"),
                            "label_abstains": result.get("label_abstains"),
                        },
                    }
                )

    # --- candidate ii (sequential, local Ollama) ---
    if "ii" in candidates:
        for pair_id, case in pair_cases:
            context_text = _context_text(case)
            for rep in range(args.reps):
                result = call_candidate_ii(case["query"], context_text, args.ollama_url)
                calls.append(
                    {
                        "candidate": "ii",
                        "pair_id": pair_id,
                        "case_id": case.get("case_id"),
                        "rep": rep,
                        "decision": result["decision"],
                        "outcome": result["outcome"],
                        "latency_s": result.get("latency_s"),
                        "raw_first_token": result.get("raw_first_token"),
                        "cost": _COST_BY_CANDIDATE["ii"],
                        "detail": {
                            "model": OLLAMA_MODEL,
                            "sent_think": result.get("sent_think"),
                            "accepted_think": result.get("accepted_think"),
                            "request_options": result.get("request_options"),
                        },
                    }
                )

    # --- candidate iii (Codex adapter, up to 4 concurrent) ---
    if "iii" in candidates:
        batch_items: list[tuple[str, str, list[str], str, str | None]] = []
        for pair_id, case in pair_cases:
            context_chunks = case.get("context", [])
            if isinstance(context_chunks, str):
                context_chunks = [context_chunks]
            for rep in range(args.reps):
                key = f"{pair_id}|{case.get('case_id')}|{rep}"
                batch_items.append(
                    (key, case["query"], context_chunks, pair_id, case.get("case_id"))
                )

        results = await run_candidate_iii_batch(
            [(key, query, chunks) for key, query, chunks, _, _ in batch_items],
            model=codex_model,
            timeout_s=90.0,
            max_concurrency=4,
        )
        for key, _, _, pair_id, case_id in batch_items:
            rep = int(key.rsplit("|", 1)[1])
            result = results[key]
            calls.append(
                {
                    "candidate": "iii",
                    "pair_id": pair_id,
                    "case_id": case_id,
                    "rep": rep,
                    "decision": result["decision"],
                    "outcome": result["outcome"],
                    "latency_s": result.get("latency_s"),
                    "raw_first_token": result.get("raw_first_token"),
                    "cost": _COST_BY_CANDIDATE["iii"],
                    "detail": {
                        "model": result.get("model", codex_model),
                        "adapter_latency_ms": result.get("adapter_latency_ms"),
                    },
                }
            )

    utc_end = datetime.now(timezone.utc).isoformat()

    measured_pair_ids = (
        sorted(pairs.keys())[: args.limit_pairs]
        if args.limit_pairs is not None
        else sorted(pairs.keys())
    )
    pairs_summary, candidate_summary = _score(calls, candidates, measured_pair_ids, pairs)

    receipts = {
        "meta": {
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_sha256,
            "base_sha": base_sha,
            "backend_root": str(backend_root),
            "backend_root_git_sha": backend_root_git_sha,
            "host": platform.node(),
            "utc_start": utc_start,
            "utc_end": utc_end,
            "candidates_run": candidates,
            "reps": args.reps,
            "limit_pairs": args.limit_pairs,
            "pairs_measured": measured_pair_ids,
            "model_ids": {"ii": OLLAMA_MODEL, "iii": codex_model},
            "adapter_file_sha256": adapter_file_sha256,
            "codex_version": codex_version,
            "codex_home_basename": codex_home,
            "ollama_url": args.ollama_url,
            "ollama_model_digest": ollama_digest_record,
        },
        "calls": calls,
        "pairs": pairs_summary,
        "summary": candidate_summary,
    }
    return receipts


def _score(
    calls: list[dict[str, Any]],
    candidates: list[str],
    pair_ids: list[str],
    pairs: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Post-hoc scoring pass. Reads `pair_id`/`case_id`/`decision` from the
    already-produced calls, and `stratum` from `pairs` (the ORIGINAL case
    objects) ONLY here — never at decision time. Every decision already
    exists before this function is called; `stratum` is read only to know
    which pair member is expected SUPPORTED (sufficient) vs NOT_SUPPORTED
    (relevant_insufficient) — it never selects an input to a candidate."""
    # index: (candidate, pair_id, case_id) -> [decisions per rep]
    by_key: dict[tuple[str, str, str | None], list[str]] = {}
    for call in calls:
        key = (call["candidate"], call["pair_id"], call["case_id"])
        by_key.setdefault(key, []).append(call["decision"])

    # case_id -> stratum, from the manifest's own pair members (scoring-time
    # read only).
    stratum_by_case: dict[str | None, str] = {}
    for members in pairs.values():
        for case in members:
            stratum_by_case[case.get("case_id")] = case.get("stratum")

    pairs_summary: list[dict[str, Any]] = []
    candidate_summary: list[dict[str, Any]] = []

    for candidate in candidates:
        cand_calls = [c for c in calls if c["candidate"] == candidate]
        cand_pair_ids = sorted({c["pair_id"] for c in cand_calls if c["pair_id"] in pair_ids})
        distinguished_count = 0
        unstable_count = 0
        for pair_id in cand_pair_ids:
            case_ids = sorted({c["case_id"] for c in cand_calls if c["pair_id"] == pair_id})
            member_stable: dict[str, bool] = {}
            member_decisions: dict[str, list[str]] = {}
            for case_id in case_ids:
                decisions = by_key.get((candidate, pair_id, case_id), [])
                member_decisions[case_id] = decisions
                member_stable[case_id] = len(set(decisions)) <= 1
            unstable = any(not stable for stable in member_stable.values())
            distinguished = False
            if not unstable and len(case_ids) == 2:
                sufficient_ids = [
                    cid for cid in case_ids if stratum_by_case.get(cid) == "sufficient"
                ]
                insufficient_ids = [
                    cid for cid in case_ids if stratum_by_case.get(cid) == "relevant_insufficient"
                ]
                if len(sufficient_ids) == 1 and len(insufficient_ids) == 1:
                    sufficient_decision = next(iter(set(member_decisions[sufficient_ids[0]])))
                    insufficient_decision = next(iter(set(member_decisions[insufficient_ids[0]])))
                    distinguished = (
                        sufficient_decision == "SUPPORTED"
                        and insufficient_decision == "NOT_SUPPORTED"
                    )
            if unstable:
                unstable_count += 1
            if distinguished:
                distinguished_count += 1
            pairs_summary.append(
                {
                    "candidate": candidate,
                    "pair_id": pair_id,
                    "unstable": unstable,
                    "distinguished": distinguished,
                    "decisions": {
                        cid: {
                            "stratum": stratum_by_case.get(cid),
                            "decisions": member_decisions[cid],
                        }
                        for cid in case_ids
                    },
                }
            )
        total_pairs = len(cand_pair_ids)
        qualifies = total_pairs > 0 and distinguished_count == total_pairs
        candidate_summary.append(
            {
                "candidate": candidate,
                "total_pairs": total_pairs,
                "distinguished_pairs": distinguished_count,
                "unstable_pairs": unstable_count,
                "qualifies": qualifies,
            }
        )

    return pairs_summary, candidate_summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=None,
        help="path to the manifest JSON (default: "
        f"<backend-root>/{DEFAULT_MANIFEST_RELATIVE})",
    )
    parser.add_argument(
        "--backend-root",
        default=DEFAULT_BACKEND_ROOT,
        help="apps/backend-rag directory added to sys.path, so the adapter/wa_dlp/"
        "reasoning_utils/_abstain_policy import from THIS tree "
        f"(default: {DEFAULT_BACKEND_ROOT!r}, relative to cwd)",
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_BASE_URL,
        help=f"Ollama base URL, /api/generate and /api/tags appended (default: {DEFAULT_OLLAMA_BASE_URL})",
    )
    parser.add_argument(
        "--candidates", default="i,ii,iii,iv", help="comma-separated subset of i,ii,iii,iv"
    )
    parser.add_argument("--reps", type=int, default=3, help="repetitions per case")
    parser.add_argument(
        "--limit-pairs",
        dest="limit_pairs",
        type=int,
        default=None,
        help="SMOKE ONLY: limit to the first N pairs (sorted by pair_id)",
    )
    parser.add_argument(
        "--out", default="support_probe_receipts.json", help="output receipts JSON path"
    )
    parser.add_argument(
        "--codex-model",
        default="gpt-5.6-terra",
        help="model slug passed to CodexExecClient for candidate (iii); "
        "pinned to the WA leg's production model (MODEL_TERRA, "
        "backend/llm/codex_exec_client.py:362, constructed at "
        "wa_codex_daemon.py:159,230 — wa_codex_leg.py itself never calls "
        "CodexExecClient or references MODEL_TERRA, confirmed read-only)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    receipts = asyncio.run(run(args))
    out_path = Path(args.out)
    out_path.write_text(json.dumps(receipts, indent=2, default=str))
    print(json.dumps(receipts["summary"], indent=2))  # noqa: T201 - CLI report output, by design


if __name__ == "__main__":
    main()
