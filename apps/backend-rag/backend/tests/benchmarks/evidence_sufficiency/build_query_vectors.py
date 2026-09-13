#!/usr/bin/env python3
"""B1.5 — the one bounded embedding batch for B2.2 (research/operations/
2026-09-11-bot-staff-room/B1-design.md §4 B1.5, §2 exception (2)).

Authorization: README queue item 7 — RULED 2026-09-11 ~15:00 WITA: YES
("ok procediamo"), recorded at
research/operations/2026-09-11-bot-staff-room/README.md:89. Nothing in this
file executes that authorization by itself: `--execute` still refuses to run
twice (a pre-call record with or without a completion already present STOPS
it) and this module makes no network call merely by being imported — every
OpenAI/backend import lives inside the `--execute` code path, never at
module scope, so `--dry-run` and the unit tests that import this module for
its pure functions never touch the network or a credential.

Ceiling: 40 TOTAL provider attempts INCLUDING retries. This harness reaches
that ceiling by construction rather than by counting sub-HTTP retries: the
product's own `AsyncOpenAI` client (`backend/core/embeddings.py:271`,
`self.client = AsyncOpenAI(api_key=self.api_key)`, no `max_retries`
override, so the installed SDK's default of 2 applies) is replaced, AFTER
construction, with one built at `max_retries=0` — `self.client` is a plain
public instance attribute assigned inside `EmbeddingsGenerator._init_openai`,
not encapsulated, so this needs no edit to `embeddings.py`. With retries
disabled, one call to `generate_query_embedding()` is exactly one provider
attempt: no failure is silently retried by the SDK, so the harness's own
per-query attempt counter equals the true attempt count Astra's round-3
finding 24 asked for ("max_retries=0 is sufficient", round-4 delta check).
The one thing left unreused from the product path is the retry policy
itself — everything else (model, dimensions, batching, truncation, caching,
error handling) is the exact code `generate_query_embedding` already runs.

Selection is deterministic and label-free: the distinct (query_lang, query)
pairs of the B1.3 mandatory manifest's cases, sorted by (query_lang, query).
If that count exceeds the ceiling, this harness STOPS and reports — it never
chooses a subset itself (that judgment belongs to the staff room).

Canary reuse: `scripts/.rag_canary/embedding_baseline.json` holds REFERENCE
TEXT embeddings, never queries; this harness only ever reads it (read-only)
to report whether any selected query happens to be byte-identical to one of
those reference texts. It never calls `rag_canary.py`'s `save_baseline`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Product defaults, mirrored (not imported) so --dry-run never imports the
# backend app / triggers Settings() / risks an implicit .env load.
# Source: apps/backend-rag/backend/core/embeddings.py:254-256
#   self.model = ... or "text-embedding-3-small"
#   self.dimensions = 1536  # OpenAI text-embedding-3-small is always 1536
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536

# The env var the product's Settings object binds `openai_api_key` from
# (apps/backend-rag/backend/app/core/config.py:58-61).
CREDENTIAL_ENV_VAR = "OPENAI_API_KEY"

CEILING = 40

CANARY_BASELINE_PATH = Path(
    "/Users/nuzantara/nuzantara/scripts/.rag_canary/embedding_baseline.json",
)

APPROVAL_REFERENCE = (
    "research/operations/2026-09-11-bot-staff-room/README.md queue item 7 "
    '— RULED 2026-09-11 ~15:00 WITA: YES ("ok procediamo")'
)

PRECALL_FILENAME = "b1-5-precall.json"

HANDOFF_LOCATION = "B2.2 retrieval harness"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Selection (pure, no I/O beyond reading the manifest file given to it)
# ---------------------------------------------------------------------------
def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def select_queries(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Distinct (query_lang, query) pairs, sorted by (query_lang, query).

    Label-free: only `query_lang` and `query` are read from each case.
    """
    cases = manifest.get("cases", [])
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for case in cases:
        lang = case["query_lang"]
        query = case["query"]
        seen[(lang, query)] = {"query_lang": lang, "query": query}
    return [seen[key] for key in sorted(seen.keys())]


def mapping_key(entry: dict[str, str]) -> str:
    return f"{entry['query_lang']}::{entry['query']}"


def canonical_bytes(selected: list[dict[str, str]]) -> bytes:
    return json.dumps(
        selected,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def list_sha256(selected: list[dict[str, str]]) -> str:
    return hashlib.sha256(canonical_bytes(selected)).hexdigest()


# ---------------------------------------------------------------------------
# Credential presence (never loads a .env file; reports the product's
# implicit-load risk as a fact instead of triggering it)
# ---------------------------------------------------------------------------
def credential_status() -> dict[str, str]:
    value = os.environ.get(CREDENTIAL_ENV_VAR)
    return {
        "variable": CREDENTIAL_ENV_VAR,
        "status": "SET" if value else "UNSET",
        "note": (
            "Read directly from os.environ; no .env file opened by this harness. "
            "The product's settings loader "
            "(backend.app.core.config.Settings, "
            "SettingsConfigDict(env_file='.env')) would load a .env file "
            "implicitly the moment it is imported/instantiated — that import "
            "happens only in --execute's code path, never in --dry-run."
        ),
    }


# ---------------------------------------------------------------------------
# Canary baseline (read-only)
# ---------------------------------------------------------------------------
def canary_overlap(
    selected: list[dict[str, str]],
    canary_path: Path = CANARY_BASELINE_PATH,
) -> dict[str, Any]:
    if not canary_path.exists():
        return {
            "canary_path": str(canary_path),
            "exists": False,
            "overlap_count": None,
            "overlap_queries": [],
        }
    with canary_path.open("r", encoding="utf-8") as fh:
        baseline = json.load(fh)
    texts = set(baseline.get("texts", []))
    overlap = [entry["query"] for entry in selected if entry["query"] in texts]
    return {
        "canary_path": str(canary_path),
        "exists": True,
        "canary_model": baseline.get("model"),
        "canary_dimensions": baseline.get("dimensions"),
        "canary_num_texts": baseline.get("num_texts"),
        "overlap_count": len(overlap),
        "overlap_queries": overlap,
    }


# ---------------------------------------------------------------------------
# Artifact verification (shared by the real-artifact test and the tiny
# synthetic guilt/innocence fixture test — see
# backend/tests/unit/services/rag/test_query_vectors_b1_5.py)
# ---------------------------------------------------------------------------
def verify_artifact(data: dict[str, Any], ceiling: int = CEILING) -> list[str]:
    """Return a list of problem strings; an empty list means the artifact
    is internally consistent. Never raises on a malformed artifact — it
    reports problems instead, so a test can assert on the exact reason.
    """
    problems: list[str] = []
    required = {"query_list", "list_sha256", "vectors", "dimension", "attempts_made"}
    missing = required - data.keys()
    if missing:
        problems.append(f"missing required keys: {sorted(missing)}")
        return problems

    query_list = data["query_list"]
    recomputed_list_sha256 = list_sha256(query_list)
    if recomputed_list_sha256 != data["list_sha256"]:
        problems.append(
            f"list_sha256 mismatch: recorded={data['list_sha256']} "
            f"recomputed={recomputed_list_sha256}",
        )

    expected_keys = {mapping_key(e) for e in query_list}
    actual_keys = set(data["vectors"].keys())
    # A query whose provider call FAILED is recorded in `failures` and carries
    # no vector — by design, since the batch is never retried. Such an artifact
    # is incomplete but not inconsistent, so the mapping check subtracts the
    # recorded failures instead of rejecting it outright. Any other gap, and
    # any extra key, is still a mismatch.
    failed_keys = {
        mapping_key(f) for f in data.get("failures", []) if "query_lang" in f and "query" in f
    }
    missing = expected_keys - actual_keys - failed_keys
    extra = actual_keys - expected_keys
    if missing or extra:
        problems.append(
            "mapping keys mismatch: "
            f"missing={sorted(missing)} extra={sorted(extra)}",
        )

    dimension = data["dimension"]
    for key, vector in data["vectors"].items():
        if len(vector) != dimension:
            problems.append(
                f"vector '{key}' has dimension {len(vector)}, expected {dimension}",
            )

    attempts = data["attempts_made"]
    if attempts > ceiling:
        problems.append(f"attempts_made {attempts} exceeds ceiling {ceiling}")

    return problems


def build_artifact(
    *,
    query_list: list[dict[str, str]],
    vectors_by_key: dict[str, list[float]],
    model: str,
    dimension: int,
    attempts: int,
    failures: list[dict[str, str]],
    base_sha: str,
) -> dict[str, Any]:
    languages = sorted({e["query_lang"] for e in query_list})
    return {
        "schema_version": 1,
        "synthetic": True,
        "query_list": query_list,
        "list_sha256": list_sha256(query_list),
        "vectors": vectors_by_key,
        "model": model,
        "dimension": dimension,
        "language_coverage": languages,
        "approval_reference": APPROVAL_REFERENCE,
        "attempts_made": attempts,
        "failures": failures,
        "handoff": HANDOFF_LOCATION,
        "base_sha": base_sha,
        "generated_at_utc": _utc_now_iso(),
    }


# ---------------------------------------------------------------------------
# git / host helpers
# ---------------------------------------------------------------------------
def git_head_sha(repo_dir: Path | None = None) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir) if repo_dir else None,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Pre-call record
# ---------------------------------------------------------------------------
def precall_path(evidence_dir: Path) -> Path:
    return evidence_dir / PRECALL_FILENAME


def attempts_already_consumed(evidence_dir: Path) -> tuple[int, list[str]]:
    """Sum the provider attempts recorded by EVERY receipt in `evidence_dir`,
    not just the canonical one.

    The ceiling of 40 is a TOTAL across this mandate's batch, not a per-run
    allowance. `cmd_execute`'s refusal to start when `b1-5-precall.json`
    exists protects the common case, but it keys on one filename: a receipt
    preserved under any other name (as ruling I24a required for the aborted
    attempt) would otherwise reset the budget to zero. This reads them all —
    `completion.attempts` for a run that finished, `resolution.provider_attempts`
    for one that was resolved without finishing — and returns (attempts, the
    receipt names read), so the caller subtracts them from the ceiling.

    A receipt that records NEITHER field is counted as the full ceiling: an
    unreadable prior attempt is never assumed to be free.
    """
    consumed = 0
    seen: list[str] = []
    for path in sorted(evidence_dir.glob("b1-5-precall*.json")):
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


def write_precall_record(
    evidence_dir: Path,
    *,
    list_hash: str,
    base_sha: str,
    ceiling: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "authorization_reference": APPROVAL_REFERENCE,
        "list_sha256": list_hash,
        "timestamp_utc": _utc_now_iso(),
        "host": socket.gethostname(),
        "base_sha": base_sha,
        "ceiling": ceiling,
    }
    if extra:
        record.update(extra)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = precall_path(evidence_dir)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return record


def append_precall_completion(
    evidence_dir: Path,
    *,
    attempts: int,
    failures: list[dict[str, str]],
    artifact_sha256: str,
) -> None:
    path = precall_path(evidence_dir)
    with path.open("r", encoding="utf-8") as fh:
        record = json.load(fh)
    record["completion"] = {
        "attempts": attempts,
        "failures": len(failures),
        "failure_details": failures,
        "artifact_sha256": artifact_sha256,
        "end_timestamp_utc": _utc_now_iso(),
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ---------------------------------------------------------------------------
# The product embedding path, reused with retries disabled
# ---------------------------------------------------------------------------
def _build_zero_retry_generator() -> Any:
    """Construct the product's own EmbeddingsGenerator (openai provider),
    then swap its OpenAI client for one built with `max_retries=0`.

    Only called from `cmd_execute` — never at module import time, so
    `--dry-run` and any test that imports this module never trigger this
    (and never trigger the backend app's Settings()/`.env` load either).
    """
    from openai import AsyncOpenAI

    from backend.core.embeddings import EmbeddingsGenerator

    generator = EmbeddingsGenerator(provider="openai")
    # embeddings.py:271 — self.client is a plain public attribute assigned
    # inside _init_openai(); reassigning it here needs no production edit.
    generator.client = AsyncOpenAI(api_key=generator.api_key, max_retries=0)
    return generator


async def _run_batch(
    generator: Any,
    selected: list[dict[str, str]],
    ceiling: int,
) -> tuple[dict[str, list[float]], list[dict[str, str]], int]:
    vectors: dict[str, list[float]] = {}
    failures: list[dict[str, str]] = []
    attempts = 0
    for entry in selected:
        if attempts >= ceiling:
            break
        attempts += 1
        try:
            vector = await generator.generate_query_embedding(entry["query"])
            vectors[mapping_key(entry)] = vector
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
            # The exception TYPE only. `repr(exc)` on an OpenAI transport error
            # can carry request headers — i.e. the Authorization value — and
            # this record is checked into the repository.
            failures.append(
                {
                    "query_lang": entry["query_lang"],
                    "query": entry["query"],
                    "error": type(exc).__name__,
                    "status_code": str(getattr(exc, "status_code", "") or ""),
                },
            )
    return vectors, failures, attempts


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_dry_run(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    selected = select_queries(manifest)
    languages = sorted({e["query_lang"] for e in selected})
    list_hash = list_sha256(selected)

    print("=== B1.5 build_query_vectors.py --dry-run ===")
    print(f"manifest: {args.manifest}")
    print(f"evidence dir: {args.evidence_dir}")
    print(f"selected query count: {len(selected)}")
    print(f"languages: {languages}")
    print(f"query list sha256: {list_hash}")

    if len(selected) > CEILING:
        print(
            f"STOP: selected query count {len(selected)} exceeds ceiling "
            f"{CEILING} — refusing to choose a subset. Escalate to the "
            "staff room; this harness will not pick which queries to drop.",
        )
        return 1

    print(f"model (product default, embeddings.py:254-256): {DEFAULT_MODEL}")
    print(f"dimension (product default, embeddings.py:256): {DEFAULT_DIMENSION}")

    cred = credential_status()
    print(f"credential variable: {cred['variable']} = {cred['status']}")
    print(f"credential note: {cred['note']}")

    canary = canary_overlap(selected)
    print(f"canary baseline path: {canary['canary_path']}")
    print(f"canary baseline exists: {canary['exists']}")
    if canary["exists"]:
        print(
            "canary model/dimensions/num_texts: "
            f"{canary['canary_model']} / {canary['canary_dimensions']} / "
            f"{canary['canary_num_texts']}",
        )
        print(f"canary byte-identical overlap count: {canary['overlap_count']}")
        if canary["overlap_queries"]:
            print(f"canary overlap queries: {canary['overlap_queries']}")
    else:
        print(
            "canary baseline NOT FOUND at the expected path — cannot verify "
            "overlap from here; --execute must re-check this before running "
            "(B1-design.md §4 B1.5).",
        )

    print(f"ceiling: {CEILING} total provider attempts including retries")
    print(f"authorization reference: {APPROVAL_REFERENCE}")
    print("no network call made by --dry-run")
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    """NOT run by the B1.5 builder. Written for the Dux to run later, under
    the recorded README queue item 7 authorization, after re-checking the
    canary baseline exists on Pro's main checkout.
    """
    import asyncio

    evidence_dir = Path(args.evidence_dir)
    manifest_path = Path(args.manifest)

    manifest = load_manifest(manifest_path)
    selected = select_queries(manifest)

    if len(selected) > CEILING:
        print(
            f"STOP: selected query count {len(selected)} exceeds ceiling "
            f"{CEILING} — refusing to choose a subset. Escalate to the "
            "staff room.",
        )
        return 1

    p_path = precall_path(evidence_dir)
    if p_path.exists():
        with p_path.open("r", encoding="utf-8") as fh:
            existing = json.load(fh)
        if "completion" not in existing:
            print(
                f"STOP: pre-call record {p_path} exists without a "
                "completion — a prior run is incomplete or ambiguous. "
                "Escalate to the staff room; never start a second batch "
                "silently.",
            )
        else:
            print(
                f"STOP: pre-call record {p_path} already has a completion "
                "— a batch already ran. A second batch is never started "
                "silently. Escalate to the staff room.",
            )
        return 1

    # The budget is a TOTAL across every receipt in this directory, not a
    # fresh 40 per invocation (see `attempts_already_consumed`).
    consumed, receipts_read = attempts_already_consumed(evidence_dir)
    remaining = CEILING - consumed
    if remaining <= 0:
        print(
            f"STOP: prior receipts in {evidence_dir} already account for "
            f"{consumed} of the {CEILING} attempt ceiling "
            f"({'; '.join(receipts_read)}) — nothing left to spend. "
            "Escalate to the staff room.",
        )
        return 1
    if len(selected) > remaining:
        print(
            f"STOP: {len(selected)} queries selected but only {remaining} of "
            f"the {CEILING} attempts remain after prior receipts "
            f"({'; '.join(receipts_read) or 'none'}) — refusing to run a "
            "partial batch. Escalate to the staff room.",
        )
        return 1

    # §4 B1.5 asks B1.5 to VERIFY the canary baseline's presence before
    # deciding whether any canary vector is reusable, and --dry-run's output
    # promises --execute re-checks it. Do it here, and record the read in the
    # pre-call receipt, so the promise and the code agree.
    canary = canary_overlap(selected)

    list_hash = list_sha256(selected)
    base_sha = git_head_sha()
    write_precall_record(
        evidence_dir,
        list_hash=list_hash,
        base_sha=base_sha,
        ceiling=CEILING,
        extra={
            "manifest_path": str(manifest_path),
            # Council finding (Codex, B1.5 round 1): without this the receipt
            # cannot prove the queries came from the FROZEN manifest — the
            # list hash is self-referential, computed over whatever --manifest
            # was handed. The shipped artifact predates this field; the test
            # proves the same property for it directly, by re-deriving the
            # selection from the frozen manifest on disk.
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "attempts_already_consumed": consumed,
            "receipts_read": receipts_read,
            "remaining_budget": remaining,
            "canary_check": canary,
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    )

    generator = _build_zero_retry_generator()
    vectors, failures, attempts = asyncio.run(
        _run_batch(generator, selected, CEILING),
    )

    artifact = build_artifact(
        query_list=selected,
        vectors_by_key=vectors,
        model=generator.model,
        dimension=generator.dimensions,
        attempts=attempts,
        failures=failures,
        base_sha=base_sha,
    )

    out_path = Path(args.out) if args.out else manifest_path.parent / "query_vectors_b1_5.json"
    out_bytes = json.dumps(
        artifact,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    out_path.write_bytes(out_bytes)
    artifact_sha256 = hashlib.sha256(out_bytes).hexdigest()

    append_precall_completion(
        evidence_dir,
        attempts=attempts,
        failures=failures,
        artifact_sha256=artifact_sha256,
    )

    print(f"Wrote artifact: {out_path} (sha256={artifact_sha256})")
    print(f"Attempts: {attempts}, failures: {len(failures)}")
    if failures:
        print("Failures were recorded, not retried; batch not repeated.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "B1.5 — one bounded embedding batch harness (B1-design.md §4 "
            "B1.5). --dry-run reports selection/credential/canary state "
            "with no network call. --execute runs the batch once, under "
            "README queue item 7's authorization, and refuses to run twice."
        ),
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the B1.3 mandatory manifest JSON",
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        help="Evidence directory for the pre-call record",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Artifact output path (default: query_vectors_b1_5.json beside the manifest)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Report selection/credential/canary state; no network call",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Run the one bounded batch; requires recorded authorization",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        return cmd_dry_run(args)
    return cmd_execute(args)


if __name__ == "__main__":
    sys.exit(main())
