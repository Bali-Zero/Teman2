"""B2.2 — the residual cosine re-measurement batch (RULING I15 under B2
generation authority 20260912T091907Z-435d; imperator orders b2-resume2
item (3)).

This is the ONE further provider batch this authorization covers. It
re-measures V1 — the embedding cosine of manifest case ``bs-17806bb4``
(``manifest_mandatory.json``), whose only recorded cosine (0.373) is a
historical attestation with no measurement receipt on disk (see that case's
``provenance_fixture.note``) — and measures V2 for the first time: the
(query, chunk) cosines of ``sup-d-4984a0c2`` and ``sup-d-4d058bdc``
(``manifest_supplement_b2.json``), which carry no measured cosine anywhere.

Ceiling discipline mirrors B1.5
(``build_query_vectors.py``, reused here via import, never reimplemented):
40 TOTAL provider attempts across the whole mandate, ``max_retries=0`` on
the product's own ``EmbeddingsGenerator``, one pre-call record written
BEFORE the first provider call, and the batch refuses to run twice. The
budget this module checks is CUMULATIVE with B1.5's own consumption (23 of
40 already spent there) — see ``compute_budget``.

V1 is falsifiable, not merely descriptive: a re-measurement more than
0.0005 away from the declared 0.373 (its stated 3-decimal precision) is
INCOMPATIBLE with the attestation, and a measurement below 0.32 (the
MODERATE-band floor ``reasoning_utils.py`` uses) means the cure this case
relies on is BROKEN. V2 carries no such prior claim, so this module only
ever records what it measured — it never declares a verdict for V2.

Importing this module (and running its default plan mode) DOES load backend
modules transitively, via ``harness.source_sha256`` and
``build_query_vectors`` — that is ordinary Python import cost, not a
provider call: no network request and no credential use happen merely from
that import. The actual OpenAI client is constructed only inside
``--execute``'s code path, via ``_build_zero_retry_generator``.
``--write-precall`` and ``--execute`` are separate, deliberate steps;
``--execute`` refuses unless a pre-call record already exists, carries no
completion, and its own recomputed plan and budget still agree with what
was recorded.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import socket
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.tests.benchmarks.evidence_sufficiency.build_query_vectors import (
    CEILING,
    _build_zero_retry_generator,
    attempts_already_consumed,
    git_head_sha,
    mapping_key,
)
from backend.tests.benchmarks.evidence_sufficiency.harness import source_sha256

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "text-embedding-3-small"
DIMENSION = 1536

AUTHORIZATION_REFERENCE = (
    "RULING I15 (envelope 20260912T013527Z-13d6) under B2 generation authority "
    "20260912T091907Z-435d; imperator orders b2-resume2 item (3)"
)

ARTIFACT_FILENAME = "query_vectors_b1_5.json"
#: Pin for `query_vectors_b1_5.json`, verified via `harness.source_sha256`
#: (raw file bytes, never a re-serialized `json.dumps`) before this module
#: trusts a single vector from it.
ARTIFACT_EXPECTED_SHA256 = "0021c3275b7bd9f812f0ce52fc06da1330e89a9d1c40a4c105ca932720083012"

PRECALL_FILENAME = "b2-2-precall.json"
PRECALL_GLOB = "b2-2-precall*.json"
#: B1.5's own receipt glob (`build_query_vectors.py`'s `PRECALL_FILENAME` pattern,
#: duplicated here as a literal since that module does not export it) — used to
#: refuse reading an ABSENT B1.5 ledger as zero consumption (G2).
B1_5_PRECALL_GLOB = "b1-5-precall*.json"

#: (case_id, manifest filename, residual label). Order is the plan/execution
#: order: V1 first, then V2's two cases.
CASES: tuple[tuple[str, str, str], ...] = (
    ("bs-17806bb4", "manifest_mandatory.json", "V1"),
    ("sup-d-4984a0c2", "manifest_supplement_b2.json", "V2"),
    ("sup-d-4d058bdc", "manifest_supplement_b2.json", "V2"),
)

DECLARED_RAW_V1 = 0.373
V1_INCOMPATIBLE_DELTA = 0.0005
V1_BROKEN_CEILING = 0.32

#: Repo-root-relative path to the B1.5 receipts directory (23 provider
#: attempts already consumed there — see `attempts_already_consumed`).
DEFAULT_B1_5_RELATIVE = Path(
    "evidence/2026-09/agent-nuzantara-backend-rag-b1-5-query-vectors-7057dd74",
)


class RefusalError(RuntimeError):
    """Raised whenever this harness refuses to proceed. Always a single-line
    message — the CLI prints it verbatim and returns 1."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Repo / path helpers
# ---------------------------------------------------------------------------
def find_repo_root(start: Path) -> Path:
    """Walk up from `start` to the nearest ancestor holding a `.git` entry
    (file or directory — a worktree's `.git` is a file). Raises if none is
    found, rather than silently falling back to some other directory."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RefusalError(f"no repo root (.git) found walking up from {start}")


def default_bench_dir() -> Path:
    return Path(__file__).resolve().parent


def default_b1_5_dir() -> Path:
    repo_root = find_repo_root(Path(__file__).parent)
    return repo_root / DEFAULT_B1_5_RELATIVE


# ---------------------------------------------------------------------------
# Manifest case lookup (pure, reads only the two manifests it is given)
# ---------------------------------------------------------------------------
def _load_case(bench_dir: Path, manifest_name: str, case_id: str) -> dict[str, Any]:
    path = Path(bench_dir) / manifest_name
    with path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    for case in manifest.get("cases", []):
        if case.get("case_id") == case_id:
            context = case.get("context")
            if not isinstance(context, list) or len(context) != 1:
                count = 0 if context is None else len(context)
                raise RefusalError(
                    f"{case_id} in {manifest_name}: expected exactly one context chunk, got {count}",
                )
            return case
    raise RefusalError(f"case_id {case_id!r} not found in {manifest_name}")


def load_cases(bench_dir: Path) -> dict[str, dict[str, Any]]:
    """`case_id` -> `{"manifest", "residual", "query", "query_lang", "chunk"}`
    for every case in `CASES`. The only I/O here is reading the two frozen
    manifests named in `CASES`."""
    bench_dir = Path(bench_dir)
    result: dict[str, dict[str, Any]] = {}
    for case_id, manifest_name, residual in CASES:
        case = _load_case(bench_dir, manifest_name, case_id)
        result[case_id] = {
            "manifest": manifest_name,
            "residual": residual,
            "query": case["query"],
            "query_lang": case["query_lang"],
            "chunk": case["context"][0],
        }
    return result


# ---------------------------------------------------------------------------
# Artifact verification (pin check before ANY vector from it is trusted)
# ---------------------------------------------------------------------------
def load_verified_artifact(path: Path) -> dict[str, Any]:
    path = Path(path)
    actual = source_sha256(path)
    if actual != ARTIFACT_EXPECTED_SHA256:
        raise RefusalError(
            f"{path} has sha256 {actual}, expected {ARTIFACT_EXPECTED_SHA256} — "
            "refusing to trust an artifact that does not match the pinned hash",
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Plan (pure — no I/O beyond reading the two manifests + the verified artifact)
# ---------------------------------------------------------------------------
def plan_batch(bench_dir: Path, artifact_data: dict[str, Any]) -> dict[str, Any]:
    """For each case in `CASES`, two items: a "query" item (source
    "artifact" when its mapping key is already in the artifact's vectors,
    else "provider") and a "chunk" item (always "provider" — the artifact
    never carries chunk vectors). Every item carries only a sha256 of its
    text, never the text itself.

    `planned_provider_attempts` is the count of "provider" items. With the
    manifests and artifact on disk today this is 5: V1's query is reused
    from the artifact (1 provider call, its chunk); V2's two cases have
    neither vector in the artifact (2 provider calls each).
    """
    cases = load_cases(bench_dir)
    artifact_vectors = artifact_data.get("vectors", {})

    items: list[dict[str, Any]] = []
    for case_id, _manifest_name, residual in CASES:
        info = cases[case_id]
        q_key = mapping_key({"query_lang": info["query_lang"], "query": info["query"]})
        q_source = "artifact" if q_key in artifact_vectors else "provider"
        items.append(
            {
                "case_id": case_id,
                "residual": residual,
                "role": "query",
                "source": q_source,
                "text_sha256": _sha256_text(info["query"]),
            },
        )
        items.append(
            {
                "case_id": case_id,
                "residual": residual,
                "role": "chunk",
                "source": "provider",
                "text_sha256": _sha256_text(info["chunk"]),
            },
        )

    planned_provider_attempts = sum(1 for item in items if item["source"] == "provider")
    return {"items": items, "planned_provider_attempts": planned_provider_attempts}


# ---------------------------------------------------------------------------
# Budget — cumulative across B1.5's own receipts dir AND this batch's own
# ---------------------------------------------------------------------------
def own_consumed(
    evidence_dir: Path,
    *,
    exclude: str | None = None,
) -> tuple[int, list[str]]:
    """Sum the provider attempts recorded by every `b2-2-precall*.json`
    receipt in `evidence_dir`, under the same rules as B1.5's
    `attempts_already_consumed` (completion.attempts, else
    resolution.provider_attempts, else unreadable/unknown = the full
    ceiling — an unresolved prior receipt is never assumed free).

    `exclude`, when given (a filename), skips that one file. This is used
    by `execute()` to recompute the budget without double-counting the
    canonical `b2-2-precall.json` record against itself: that record has,
    by construction, no completion yet at that point in its own lifecycle,
    and the "no attempt count" rule would otherwise price its own
    not-yet-run reservation as the full ceiling. Its already-recorded
    `consumed_before`/`hard_stop` fields are the authoritative account of
    what preceded it; this function accounts for every OTHER receipt.
    """
    evidence_dir = Path(evidence_dir)
    consumed = 0
    seen: list[str] = []
    for path in sorted(evidence_dir.glob(PRECALL_GLOB)):
        if exclude is not None and path.name == exclude:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, json.JSONDecodeError):
            consumed += CEILING
            seen.append(f"{path.name} (unreadable — counted as the full ceiling)")
            continue
        completion = record.get("completion")
        resolution = record.get("resolution")
        if isinstance(completion, dict) and "attempts" in completion:
            consumed += int(completion["attempts"])
            seen.append(f"{path.name} (completion.attempts={completion['attempts']})")
        elif isinstance(resolution, dict) and "provider_attempts" in resolution:
            consumed += int(resolution["provider_attempts"])
            seen.append(
                f"{path.name} (resolution.provider_attempts={resolution['provider_attempts']})",
            )
        else:
            consumed += CEILING
            seen.append(f"{path.name} (no attempt count — counted as the full ceiling)")
    return consumed, seen


def compute_budget(
    b1_5_dir: Path,
    evidence_dir: Path | None,
    *,
    exclude: str | None = None,
    require_ledger: bool = False,
) -> dict[str, Any]:
    """`consumed = attempts_already_consumed(b1_5_dir)[0] + own_consumed(evidence_dir)[0]`;
    `remaining = CEILING - consumed`.

    `evidence_dir=None` is accepted for plan-mode reporting before any
    evidence directory has been chosen — it contributes 0 (nothing has been
    written there yet) and is reported as `own_consumed_checked: False`.

    `require_ledger=True` (used by the write and execute paths, never by
    plan mode) refuses when `b1_5_dir` does not exist or holds no
    `b1-5-precall*.json` — an ABSENT B1.5 ledger is never silently read as
    zero prior consumption, which would defeat the 40-attempt ceiling."""
    b1_5_dir = Path(b1_5_dir)
    if require_ledger and (not b1_5_dir.exists() or not any(b1_5_dir.glob(B1_5_PRECALL_GLOB))):
        raise RefusalError(
            f"{b1_5_dir} does not exist or holds no {B1_5_PRECALL_GLOB} — an absent "
            "B1.5 ledger is never read as zero consumption",
        )
    b1_5_consumed, b1_5_receipts = attempts_already_consumed(b1_5_dir)
    if evidence_dir is None:
        own = 0
        own_receipts: list[str] = []
        checked = False
    else:
        own, own_receipts = own_consumed(Path(evidence_dir), exclude=exclude)
        checked = True
    consumed = b1_5_consumed + own
    return {
        "ceiling": CEILING,
        "b1_5_consumed": b1_5_consumed,
        "b1_5_receipts": b1_5_receipts,
        "own_consumed": own,
        "own_receipts": own_receipts,
        "own_consumed_checked": checked,
        "consumed": consumed,
        "remaining": CEILING - consumed,
    }


# ---------------------------------------------------------------------------
# Pre-call record
# ---------------------------------------------------------------------------
def _falsification_v1() -> dict[str, str]:
    return {
        "declared_raw": DECLARED_RAW_V1,
        "incompatible_if": (
            f"abs(measured - {DECLARED_RAW_V1}) >= {V1_INCOMPATIBLE_DELTA} "
            "(stated 3-decimal precision)"
        ),
        "cure_broken_if": f"measured < {V1_BROKEN_CEILING}",
    }


def write_precall(
    evidence_dir: Path,
    plan: dict[str, Any],
    consumed_before: int,
    base_sha: str,
    *,
    artifact_sha256: str,
) -> dict[str, Any]:
    """Writes `b2-2-precall.json`. Refuses if ANY `b2-2-precall*.json`
    already exists in `evidence_dir` (this batch runs exactly once) or if
    the plan's `planned_provider_attempts` would exceed what remains of the
    ceiling given `consumed_before`."""
    evidence_dir = Path(evidence_dir)
    existing = sorted(evidence_dir.glob(PRECALL_GLOB)) if evidence_dir.exists() else []
    if existing:
        names = [p.name for p in existing]
        raise RefusalError(
            f"refusing to write a pre-call record: {names} already present in "
            f"{evidence_dir} — this batch runs once",
        )

    planned = plan["planned_provider_attempts"]
    remaining_before_plan = CEILING - consumed_before
    if planned > remaining_before_plan:
        raise RefusalError(
            f"planned_provider_attempts {planned} exceeds the {remaining_before_plan} "
            f"remaining of the {CEILING} ceiling ({consumed_before} already consumed)",
        )

    hard_stop = min(planned, remaining_before_plan)
    remaining_after = CEILING - consumed_before - planned

    record = {
        "authorization_reference": AUTHORIZATION_REFERENCE,
        "ceiling": CEILING,
        "consumed_before": consumed_before,
        "planned_provider_attempts": planned,
        "remaining_after": remaining_after,
        "hard_stop": hard_stop,
        "items": plan["items"],
        "artifact_sha256": artifact_sha256,
        "model": MODEL,
        "dimension": DIMENSION,
        "max_retries": 0,
        "host": socket.gethostname(),
        "base_sha": base_sha,
        "timestamp_utc": _utc_now_iso(),
        "falsification_v1": _falsification_v1(),
        "v2_note": "measured values are recorded, no verdict is declared by this tool",
        "ack_envelope": None,
    }

    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / PRECALL_FILENAME
    with path.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return record


# ---------------------------------------------------------------------------
# Cosine math (pure Python — no numpy requirement)
# ---------------------------------------------------------------------------
def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise RefusalError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def v1_verdict(raw: float | None) -> str:
    if raw is None:
        return "UNMEASURED"
    if raw < V1_BROKEN_CEILING:
        return "BROKEN"
    if abs(raw - DECLARED_RAW_V1) >= V1_INCOMPATIBLE_DELTA:
        return "INCOMPATIBLE"
    return "HOLDS"


# ---------------------------------------------------------------------------
# Execute — the one authorized provider batch
# ---------------------------------------------------------------------------
class _BatchProgress:
    """Mutated IN PLACE by `_run_batch`, never replaced — so if a
    `BaseException` (a kill, a `KeyboardInterrupt`-like signal) propagates
    out of the batch loop, whatever this object already holds (attempts
    counted, vectors obtained, failures recorded so far) survives for
    `execute()`'s `finally` to persist. `attempts` is incremented BEFORE the
    provider call it accounts for, so an attempt that itself raises is still
    counted (G1)."""

    def __init__(self) -> None:
        self.vectors: dict[tuple[str, str], list[float]] = {}
        self.failures: list[dict[str, str]] = []
        self.attempts: int = 0


def _generator_max_retries(generator: Any) -> int:
    """Reads only the scalar `max_retries` int off `generator.client`, if
    present — never the client object itself, and never any other
    attribute (G3: the completion must never carry a credential or any
    other client internal)."""
    client = getattr(generator, "client", None)
    value = getattr(client, "max_retries", None)
    return value if isinstance(value, int) else 0


async def _run_batch(
    generator: Any,
    plan_items: list[dict[str, Any]],
    cases: dict[str, dict[str, Any]],
    artifact_vectors: dict[str, list[float]],
    hard_stop: int,
    progress: _BatchProgress,
) -> None:
    """Runs `plan_items` in order, mutating `progress` in place. Artifact-sourced
    items cost no attempt. Provider items call `generator.generate_query_embedding`
    once each (the same call for a chunk's text as for a query's) and stop
    entirely once `hard_stop` provider attempts have been made — a true hard
    stop, not a selective skip. A per-item `Exception` is recorded as a
    failure and does not abort the batch; a `BaseException` that is not an
    `Exception` propagates out of this function (and out of the `asyncio.run`
    that drives it) with `progress` left holding everything counted so far."""
    for item in plan_items:
        case_id = item["case_id"]
        role = item["role"]
        info = cases[case_id]
        key = (case_id, role)

        if item["source"] == "artifact":
            q_key = mapping_key({"query_lang": info["query_lang"], "query": info["query"]})
            progress.vectors[key] = artifact_vectors[q_key]
            continue

        if progress.attempts >= hard_stop:
            break

        progress.attempts += 1
        text = info["query"] if role == "query" else info["chunk"]
        try:
            vector = await generator.generate_query_embedding(text)
            progress.vectors[key] = vector
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
            # Exception TYPE + status_code only. `repr(exc)`/`str(exc)` on a
            # transport error can carry request headers (Authorization) —
            # this record is checked into the repository.
            progress.failures.append(
                {
                    "case_id": case_id,
                    "role": role,
                    "error": type(exc).__name__,
                    "status_code": str(getattr(exc, "status_code", "") or ""),
                },
            )


def _compute_cosines(
    cases: dict[str, dict[str, Any]],
    vectors: dict[tuple[str, str], list[float]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """Never raises: a vector-length mismatch (e.g. a chunk vector the wrong
    dimension) is recorded as a per-case failure entry
    (`error: "VectorLengthMismatch"`) alongside an unmeasured cosine, never
    an unrecorded raise that would abort the batch after attempts were
    already spent (G1)."""
    cosines: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for case_id in cases:
        q = vectors.get((case_id, "query"))
        c = vectors.get((case_id, "chunk"))
        if q is None or c is None:
            cosines[case_id] = {"measured": False, "raw": None, "raw_3dp": None}
            continue
        try:
            raw = cosine(q, c)
        except RefusalError:
            cosines[case_id] = {"measured": False, "raw": None, "raw_3dp": None}
            failures.append(
                {
                    "case_id": case_id,
                    "role": "cosine",
                    "error": "VectorLengthMismatch",
                    "status_code": "",
                },
            )
            continue
        cosines[case_id] = {"measured": True, "raw": round(raw, 6), "raw_3dp": round(raw, 3)}
    return cosines, failures


def execute(
    evidence_dir: Path,
    bench_dir: Path,
    b1_5_dir: Path,
    ack_envelope: str,
    generator_factory: Callable[[], Any],
) -> dict[str, Any]:
    """Runs the one authorized batch. Refuses unless a pre-call record
    exists with no completion AND no `execution_start_utc`/`ack_envelope`
    already recorded (G1 — a record that already started, whether or not it
    finished, is never re-run: a prior process could have been killed after
    spending attempts but before writing a completion, and re-running would
    spend them again), `ack_envelope` is non-empty, the recomputed plan
    still matches the record's `planned_provider_attempts` and every item's
    `text_sha256`, and the recomputed budget still covers the plan.

    Writes `ack_envelope` and `execution_start_utc` into the record BEFORE
    the first provider call (flushed to disk). From that point on, a
    `completion` is ALWAYS written — in a `finally` — even if the batch or
    the cosine step raises: attempts/failures/whatever vectors were
    obtained are persisted, an aborting exception's TYPE is recorded as
    `aborted_by`, and the exception is then re-raised. Vectors themselves
    are never persisted."""
    evidence_dir = Path(evidence_dir)
    bench_dir = Path(bench_dir)
    b1_5_dir = Path(b1_5_dir)

    if not ack_envelope:
        raise RefusalError("ack_envelope must be a non-empty string")

    precall_path = evidence_dir / PRECALL_FILENAME
    if not precall_path.exists():
        raise RefusalError(f"no pre-call record at {precall_path} — run --write-precall first")
    with precall_path.open("r", encoding="utf-8") as fh:
        record = json.load(fh)
    if "completion" in record:
        raise RefusalError(f"{precall_path} already has a completion — this batch runs once")
    if record.get("execution_start_utc") is not None or record.get("ack_envelope") is not None:
        raise RefusalError(
            f"{precall_path} already has an execution_start_utc or ack_envelope recorded "
            "with no completion — an execution already started; resolve by hand, never re-run",
        )

    artifact_path = bench_dir / ARTIFACT_FILENAME
    artifact_data = load_verified_artifact(artifact_path)
    plan = plan_batch(bench_dir, artifact_data)

    if plan["planned_provider_attempts"] != record["planned_provider_attempts"]:
        raise RefusalError(
            "recomputed planned_provider_attempts "
            f"{plan['planned_provider_attempts']} != recorded "
            f"{record['planned_provider_attempts']}",
        )

    recorded_text_sha = {(i["case_id"], i["role"]): i["text_sha256"] for i in record["items"]}
    for item in plan["items"]:
        key = (item["case_id"], item["role"])
        if recorded_text_sha.get(key) != item["text_sha256"]:
            raise RefusalError(
                f"text_sha256 for {key} differs from the pre-call record — refusing to "
                "run against changed text",
            )

    budget = compute_budget(
        b1_5_dir,
        evidence_dir,
        exclude=PRECALL_FILENAME,
        require_ledger=True,
    )
    remaining = budget["remaining"] - plan["planned_provider_attempts"]
    if remaining < 0:
        raise RefusalError(
            f"recomputed budget no longer covers planned_provider_attempts "
            f"{plan['planned_provider_attempts']} (remaining {budget['remaining']})",
        )

    # BEFORE the first provider call: ack + start time, flushed to disk.
    record["ack_envelope"] = ack_envelope
    record["execution_start_utc"] = _utc_now_iso()
    with precall_path.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")

    generator = generator_factory()
    cases = load_cases(bench_dir)
    artifact_vectors = artifact_data.get("vectors", {})

    progress = _BatchProgress()
    aborted_by: str | None = None
    completion: dict[str, Any] = {}
    try:
        try:
            asyncio.run(
                _run_batch(
                    generator,
                    plan["items"],
                    cases,
                    artifact_vectors,
                    record["hard_stop"],
                    progress,
                ),
            )
        except BaseException as exc:  # noqa: BLE001 - recorded as aborted_by, always re-raised
            aborted_by = type(exc).__name__
            raise
    finally:
        cosines, cosine_failures = _compute_cosines(cases, progress.vectors)
        v1_case_id = next(cid for cid, _m, residual in CASES if residual == "V1")
        v1_entry = cosines.get(v1_case_id, {})
        verdict = v1_verdict(v1_entry["raw"]) if v1_entry.get("measured") else v1_verdict(None)

        vector_sha256 = {
            f"{case_id}/{role}": hashlib.sha256(
                json.dumps(vector).encode("utf-8"),
            ).hexdigest()
            for (case_id, role), vector in progress.vectors.items()
        }

        completion = {
            "attempts": progress.attempts,
            "failures": [*progress.failures, *cosine_failures],
            "cosines": cosines,
            "v1_verdict": verdict,
            "vector_sha256": vector_sha256,
            "embedding_call": "EmbeddingsGenerator.generate_query_embedding",
            "max_retries": _generator_max_retries(generator),
            "end_timestamp_utc": _utc_now_iso(),
        }
        if aborted_by is not None:
            completion["aborted_by"] = aborted_by
        record["completion"] = completion
        with precall_path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, sort_keys=True)
            fh.write("\n")

    return completion


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_refusal(exc: RefusalError) -> None:
    print(f"REFUSED: {exc}")


def _cmd_plan(bench_dir: Path, b1_5_dir: Path, evidence_dir: Path | None) -> int:
    try:
        artifact_data = load_verified_artifact(bench_dir / ARTIFACT_FILENAME)
        plan = plan_batch(bench_dir, artifact_data)
        budget = compute_budget(b1_5_dir, evidence_dir)
    except RefusalError as exc:
        _print_refusal(exc)
        return 1
    print(
        json.dumps(
            {"plan": plan, "budget": budget},
            indent=2,
            sort_keys=True,
        ),
    )
    return 0


def _cmd_write_precall(
    bench_dir: Path,
    b1_5_dir: Path,
    evidence_dir: Path,
    expect_attempts: int | None,
) -> int:
    try:
        artifact_path = bench_dir / ARTIFACT_FILENAME
        artifact_data = load_verified_artifact(artifact_path)
        plan = plan_batch(bench_dir, artifact_data)
        if expect_attempts is None:
            raise RefusalError("--expect-attempts is required with --write-precall")
        if expect_attempts != plan["planned_provider_attempts"]:
            raise RefusalError(
                f"--expect-attempts {expect_attempts} != planned "
                f"{plan['planned_provider_attempts']}",
            )
        budget = compute_budget(b1_5_dir, evidence_dir, require_ledger=True)
        base_sha = git_head_sha(find_repo_root(bench_dir))
        record = write_precall(
            evidence_dir,
            plan,
            budget["consumed"],
            base_sha,
            artifact_sha256=ARTIFACT_EXPECTED_SHA256,
        )
    except RefusalError as exc:
        _print_refusal(exc)
        return 1
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def _cmd_execute(
    bench_dir: Path,
    b1_5_dir: Path,
    evidence_dir: Path,
    ack_envelope: str | None,
) -> int:
    try:
        if not ack_envelope:
            raise RefusalError("--ack-envelope is required with --execute")
        completion = execute(
            evidence_dir=evidence_dir,
            bench_dir=bench_dir,
            b1_5_dir=b1_5_dir,
            ack_envelope=ack_envelope,
            generator_factory=_build_zero_retry_generator,
        )
    except RefusalError as exc:
        _print_refusal(exc)
        return 1
    print(json.dumps(completion, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "B2.2 — residual cosine re-measurement (RULING I15). Default (no flag) is "
            "plan mode: prints the plan + budget, no network call. --write-precall records "
            "the one authorized batch's plan. --execute runs it, once, under a named ack."
        ),
    )
    parser.add_argument(
        "--evidence-dir",
        default=None,
        help="this batch's evidence directory (required for --write-precall/--execute)",
    )
    parser.add_argument("--write-precall", action="store_true")
    parser.add_argument("--expect-attempts", type=int, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack-envelope", default=None)
    args = parser.parse_args(argv)

    # Neither the bench dir (manifests + B1.5 artifact) nor the B1.5 receipts
    # dir is overridable from the CLI (G2 / RULING I48 F1 on the sibling
    # harness): a pin gets no override flag, and pointing --b1-5-dir at an
    # empty directory would silently defeat the 40-attempt ceiling.
    bench_dir = default_bench_dir()
    b1_5_dir = default_b1_5_dir()

    if args.write_precall and args.execute:
        print("REFUSED: --write-precall and --execute are mutually exclusive")
        return 1

    if args.execute:
        if not args.evidence_dir:
            print("REFUSED: --evidence-dir is required with --execute")
            return 1
        return _cmd_execute(bench_dir, b1_5_dir, Path(args.evidence_dir), args.ack_envelope)

    if args.write_precall:
        if not args.evidence_dir:
            print("REFUSED: --evidence-dir is required with --write-precall")
            return 1
        return _cmd_write_precall(
            bench_dir,
            b1_5_dir,
            Path(args.evidence_dir),
            args.expect_attempts,
        )

    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
    return _cmd_plan(bench_dir, b1_5_dir, evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
