#!/usr/bin/env python3
"""Deterministic, episode-local originality gate for WR3 creative locks.

The gate is intentionally small and mechanical.  It does not invent creative
work and it never opens a socket.  It canonicalizes a controlled set of
creative axes, derives a structural signature, and reserves that signature in
an append-only JSONL ledger while holding an exclusive ``fcntl.flock``.

Request schema::

    {
      "schema_version": "wr3.originality-request.v1",
      "episode_id": "s01e13-residency-permit",
      "seed_id": "optional for a child; required for a root",
      "parent_seed_id": "required for a child; null for a root",
      "description": "plain-language description used by the lexical gate",
      "signature_axes": {
        "narrative_engine_id": "...",
        "spatial_metaphor_id": "...",
        "opening_image_id": "...",
        "emotional_turn_id": "...",
        "final_image_id": "...",
        "camera_grammar_id": "...",
        "transition_motif_id": "...",
        "sound_motif_id": "...",
        "color_arc_id": "...",
        "blocking_id": "...",
        "hero_prop_id": "...",
        "wardrobe_arc_id": "..."
      }
    }

Root registration must be explicit.  For a child, ``seed_id`` is derived as
``UUID5(parent_seed_id, signature_sha256)``; a supplied value must match it.
An exact replay of a previously recorded seed and signature is idempotent.
The normalized description is part of that immutable binding.  Every other
collision fails closed and leaves the ledger unchanged.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUEST_SCHEMA = "wr3.originality-request.v1"
LEDGER_SCHEMA = "wr3.originality-ledger-record.v1"
RECEIPT_SCHEMA = "wr3.originality-receipt.v1"

CONCEPT_AXES = (
    "narrative_engine_id",
    "spatial_metaphor_id",
    "opening_image_id",
    "emotional_turn_id",
    "final_image_id",
)
CINEMATIC_AXES = (
    "camera_grammar_id",
    "transition_motif_id",
    "sound_motif_id",
    "color_arc_id",
    "blocking_id",
)
SURFACE_AXES = (
    "hero_prop_id",
    "wardrobe_arc_id",
)
SIGNATURE_AXES = CONCEPT_AXES + CINEMATIC_AXES + SURFACE_AXES

MIN_MATERIAL_DIFFERENCES = 4
MIN_CONCEPT_DIFFERENCES = 1
MIN_CINEMATIC_DIFFERENCES = 2
DESCRIPTION_JACCARD_LIMIT = 0.80
MIN_DESCRIPTION_TOKENS = 3

_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "episode_id",
        "seed_id",
        "parent_seed_id",
        "description",
        "signature_axes",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "episode_id",
        "seed_id",
        "parent_seed_id",
        "registration_kind",
        "signature_axes",
        "signature_sha256",
        "description_normalized",
        "description_tokens",
        "recorded_at",
    }
)
_EPISODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "con",
        "da",
        "dal",
        "dalla",
        "de",
        "degli",
        "dei",
        "del",
        "della",
        "di",
        "e",
        "for",
        "from",
        "gli",
        "i",
        "il",
        "in",
        "is",
        "it",
        "la",
        "le",
        "lo",
        "of",
        "on",
        "or",
        "per",
        "the",
        "to",
        "un",
        "una",
        "with",
    }
)


class OriginalityGateError(RuntimeError):
    """Base class for deterministic originality-gate failures."""

    error_code = "ORIGINALITY_GATE_ERROR"


class OriginalityValidationError(OriginalityGateError):
    """The request is incomplete, ambiguous, or otherwise malformed."""

    error_code = "INVALID_REQUEST"


class OriginalityLedgerError(OriginalityGateError):
    """The append-only ledger is malformed, torn, or internally inconsistent."""

    error_code = "MALFORMED_LEDGER"


class OriginalitySeedMutationError(OriginalityGateError):
    """An existing seed was presented with a different structural signature."""

    error_code = "SEED_MUTATION"


class OriginalityCollisionError(OriginalityGateError):
    """The candidate is not materially or lexically distinct enough."""

    error_code = "ORIGINALITY_COLLISION"


@dataclass(frozen=True)
class Candidate:
    """Validated, canonical candidate ready for a lock-held ledger decision."""

    episode_id: str
    supplied_seed_id: str | None
    parent_seed_id: str | None
    registration_kind: str
    signature_axes: dict[str, str]
    signature_sha256: str
    description_normalized: str
    description_tokens: tuple[str, ...]


@dataclass(frozen=True)
class DifferenceCount:
    """Structural distance between two canonical creative signatures."""

    concept: int
    cinematic: int
    surface: int

    @property
    def material(self) -> int:
        """Return differences on concept and cinematic axes only."""

        return self.concept + self.cinematic

    def as_dict(self) -> dict[str, int]:
        """Return a JSON-compatible representation."""

        return {
            "material": self.material,
            "concept": self.concept,
            "cinematic": self.cinematic,
            "surface_ignored": self.surface,
        }


def normalize_text(value: str) -> str:
    """NFKC/casefold text and collapse punctuation or whitespace to spaces."""

    if not isinstance(value, str):
        raise OriginalityValidationError("normalized values must be strings")
    normalized = unicodedata.normalize("NFKC", value).casefold()
    characters: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if character.isspace() or category.startswith("P") or category.startswith("Z"):
            characters.append(" ")
        else:
            characters.append(character)
    return " ".join("".join(characters).split())


def description_tokens(description_normalized: str) -> tuple[str, ...]:
    """Extract sorted unique, nontrivial tokens for lexical collision checks."""

    tokens = {
        token
        for token in description_normalized.split()
        if len(token) >= 3 and not token.isdecimal() and token not in _STOPWORDS
    }
    return tuple(sorted(tokens))


def description_sha256(description_normalized: str) -> str:
    """Return the SHA-256 of a canonical normalized description.

    Ledger v1 already persists the complete canonical description, so adding a
    required hash field would make the strict v1 schema incompatible with
    existing ledgers.  Receipts expose this digest as a compact immutable
    binding while ledger validation recomputes it from the persisted text.
    """

    if not isinstance(description_normalized, str) or not description_normalized:
        raise OriginalityValidationError(
            "description_normalized must be a non-empty string"
        )
    if normalize_text(description_normalized) != description_normalized:
        raise OriginalityValidationError("description_normalized must be canonical")
    return hashlib.sha256(description_normalized.encode("utf-8")).hexdigest()


def canonicalize_signature_axes(signature_axes: Mapping[str, Any]) -> dict[str, str]:
    """Validate the controlled signature schema and canonicalize every value."""

    if not isinstance(signature_axes, Mapping):
        raise OriginalityValidationError("signature_axes must be an object")
    if any(not isinstance(key, str) for key in signature_axes):
        raise OriginalityValidationError("signature_axes keys must be strings")
    actual = set(signature_axes)
    expected = set(SIGNATURE_AXES)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise OriginalityValidationError(
            f"signature_axes schema mismatch: missing={missing}, extra={extra}"
        )

    canonical: dict[str, str] = {}
    for axis in SIGNATURE_AXES:
        raw = signature_axes[axis]
        if not isinstance(raw, str):
            raise OriginalityValidationError(f"signature_axes.{axis} must be a string")
        value = normalize_text(raw)
        if not value:
            raise OriginalityValidationError(f"signature_axes.{axis} cannot be empty")
        canonical[axis] = value
    return canonical


def signature_sha256(signature_axes: Mapping[str, Any]) -> str:
    """Return the deterministic SHA-256 of canonical controlled axes."""

    canonical = canonicalize_signature_axes(signature_axes)
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def derive_child_seed(parent_seed_id: str, signature_digest: str) -> str:
    """Derive the canonical child UUID5 from its parent UUID and signature SHA."""

    parent = _canonical_uuid(parent_seed_id, field_name="parent_seed_id")
    if not isinstance(signature_digest, str) or not _SHA256_RE.fullmatch(
        signature_digest
    ):
        raise OriginalityValidationError(
            "signature_sha256 must be 64 lowercase hex chars"
        )
    return str(uuid.uuid5(uuid.UUID(parent), signature_digest))


def _canonical_uuid(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise OriginalityValidationError(f"{field_name} must be a UUID string")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise OriginalityValidationError(f"{field_name} must be a valid UUID") from exc
    if str(parsed) != value.casefold():
        raise OriginalityValidationError(f"{field_name} must use canonical UUID form")
    return str(parsed)


def _parse_candidate(request: Mapping[str, Any], *, register_root: bool) -> Candidate:
    if not isinstance(request, Mapping):
        raise OriginalityValidationError("request must be a JSON object")
    if any(not isinstance(key, str) for key in request):
        raise OriginalityValidationError("request keys must be strings")
    extra = sorted(set(request) - _REQUEST_FIELDS)
    missing = sorted(
        {"schema_version", "episode_id", "description", "signature_axes"} - set(request)
    )
    if missing or extra:
        raise OriginalityValidationError(
            f"request schema mismatch: missing={missing}, extra={extra}"
        )
    if request["schema_version"] != REQUEST_SCHEMA:
        raise OriginalityValidationError(f"schema_version must be {REQUEST_SCHEMA!r}")

    episode_id = request["episode_id"]
    if not isinstance(episode_id, str) or not _EPISODE_ID_RE.fullmatch(episode_id):
        raise OriginalityValidationError(
            "episode_id must be a lowercase ASCII episode identifier"
        )

    axes = canonicalize_signature_axes(request["signature_axes"])
    digest = signature_sha256(axes)
    description = request["description"]
    if not isinstance(description, str):
        raise OriginalityValidationError("description must be a string")
    description_normalized = normalize_text(description)
    tokens = description_tokens(description_normalized)
    if len(tokens) < MIN_DESCRIPTION_TOKENS:
        raise OriginalityValidationError(
            f"description must contain at least {MIN_DESCRIPTION_TOKENS} nontrivial tokens"
        )

    raw_seed = request.get("seed_id")
    supplied_seed = (
        _canonical_uuid(raw_seed, field_name="seed_id")
        if raw_seed is not None
        else None
    )
    raw_parent = request.get("parent_seed_id")

    if register_root:
        if raw_parent is not None:
            raise OriginalityValidationError(
                "explicit root registration requires parent_seed_id=null"
            )
        if supplied_seed is None:
            raise OriginalityValidationError(
                "explicit root registration requires seed_id"
            )
        parent_seed = None
        registration_kind = "root"
    else:
        if raw_parent is None:
            raise OriginalityValidationError(
                "child registration requires an existing parent_seed_id"
            )
        parent_seed = _canonical_uuid(raw_parent, field_name="parent_seed_id")
        registration_kind = "child"

    return Candidate(
        episode_id=episode_id,
        supplied_seed_id=supplied_seed,
        parent_seed_id=parent_seed,
        registration_kind=registration_kind,
        signature_axes=axes,
        signature_sha256=digest,
        description_normalized=description_normalized,
        description_tokens=tokens,
    )


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_ledger_bytes(payload: bytes) -> list[dict[str, Any]]:
    if not payload:
        return []
    if not payload.endswith(b"\n"):
        raise OriginalityLedgerError("ledger has a torn final record")

    records: list[dict[str, Any]] = []
    seen_seeds: set[str] = set()
    seen_signatures: set[str] = set()
    ledger_episode: str | None = None
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        if not raw_line:
            raise OriginalityLedgerError(f"ledger line {line_number} is blank")
        try:
            record = json.loads(raw_line, object_pairs_hook=_strict_object)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            raise OriginalityLedgerError(
                f"ledger line {line_number} is not strict JSON"
            ) from exc
        if not isinstance(record, dict):
            raise OriginalityLedgerError(f"ledger line {line_number} is not an object")
        _validate_ledger_record(
            record,
            line_number=line_number,
            seen_seeds=seen_seeds,
            seen_signatures=seen_signatures,
        )
        for prior_record in records:
            difference = _difference_count(
                record["signature_axes"], prior_record["signature_axes"]
            )
            if not _materially_novel(difference):
                raise OriginalityLedgerError(
                    f"ledger line {line_number} violates historical material "
                    f"novelty relative to seed_id {prior_record['seed_id']}: "
                    f"{difference.as_dict()}"
                )
            similarity = _jaccard(
                record["description_tokens"], prior_record["description_tokens"]
            )
            if similarity >= DESCRIPTION_JACCARD_LIMIT:
                raise OriginalityLedgerError(
                    f"ledger line {line_number} violates historical description "
                    f"Jaccard policy relative to seed_id {prior_record['seed_id']}: "
                    f"{similarity:.6f} >= {DESCRIPTION_JACCARD_LIMIT:.2f}"
                )
        if ledger_episode is None:
            ledger_episode = record["episode_id"]
        elif record["episode_id"] != ledger_episode:
            raise OriginalityLedgerError("ledger mixes multiple episode_id values")
        seen_seeds.add(record["seed_id"])
        seen_signatures.add(record["signature_sha256"])
        records.append(record)
    return records


def _validate_ledger_record(
    record: Mapping[str, Any],
    *,
    line_number: int,
    seen_seeds: set[str],
    seen_signatures: set[str],
) -> None:
    actual = set(record)
    if actual != _RECORD_FIELDS:
        raise OriginalityLedgerError(
            f"ledger line {line_number} schema mismatch: "
            f"missing={sorted(_RECORD_FIELDS - actual)}, "
            f"extra={sorted(actual - _RECORD_FIELDS)}"
        )
    if record["schema_version"] != LEDGER_SCHEMA:
        raise OriginalityLedgerError(f"ledger line {line_number} has unknown schema")
    if (
        not isinstance(record["sequence"], int)
        or isinstance(record["sequence"], bool)
        or record["sequence"] != line_number
    ):
        raise OriginalityLedgerError(f"ledger line {line_number} has invalid sequence")
    episode_id = record["episode_id"]
    if not isinstance(episode_id, str) or not _EPISODE_ID_RE.fullmatch(episode_id):
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid episode_id"
        )

    try:
        seed_id = _canonical_uuid(record["seed_id"], field_name="seed_id")
    except OriginalityValidationError as exc:
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid seed_id"
        ) from exc
    if seed_id in seen_seeds:
        raise OriginalityLedgerError(f"ledger line {line_number} repeats a seed_id")

    kind = record["registration_kind"]
    parent_seed = record["parent_seed_id"]
    if kind == "root":
        if parent_seed is not None:
            raise OriginalityLedgerError(
                f"ledger line {line_number} root has a parent_seed_id"
            )
    elif kind == "child":
        try:
            parent_seed = _canonical_uuid(parent_seed, field_name="parent_seed_id")
        except OriginalityValidationError as exc:
            raise OriginalityLedgerError(
                f"ledger line {line_number} child has invalid parent_seed_id"
            ) from exc
        if parent_seed not in seen_seeds:
            raise OriginalityLedgerError(
                f"ledger line {line_number} references a missing or future parent"
            )
    else:
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid registration_kind"
        )

    try:
        axes = canonicalize_signature_axes(record["signature_axes"])
    except OriginalityValidationError as exc:
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid signature_axes"
        ) from exc
    if axes != record["signature_axes"]:
        raise OriginalityLedgerError(
            f"ledger line {line_number} signature_axes are not canonical"
        )
    digest = signature_sha256(axes)
    if record["signature_sha256"] != digest:
        raise OriginalityLedgerError(
            f"ledger line {line_number} signature SHA does not match its axes"
        )
    if digest in seen_signatures:
        raise OriginalityLedgerError(
            f"ledger line {line_number} repeats a structural signature"
        )
    if kind == "child" and seed_id != derive_child_seed(parent_seed, digest):
        raise OriginalityLedgerError(
            f"ledger line {line_number} child seed violates UUID5 derivation"
        )

    normalized_description = record["description_normalized"]
    if not isinstance(normalized_description, str) or not normalized_description:
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid description_normalized"
        )
    if normalize_text(normalized_description) != normalized_description:
        raise OriginalityLedgerError(
            f"ledger line {line_number} description is not canonical"
        )
    expected_tokens = list(description_tokens(normalized_description))
    if len(expected_tokens) < MIN_DESCRIPTION_TOKENS:
        raise OriginalityLedgerError(
            f"ledger line {line_number} has too few nontrivial description tokens"
        )
    if record["description_tokens"] != expected_tokens:
        raise OriginalityLedgerError(
            f"ledger line {line_number} description_tokens do not match"
        )
    try:
        description_sha256(normalized_description)
    except OriginalityValidationError as exc:
        raise OriginalityLedgerError(
            f"ledger line {line_number} description cannot be hashed canonically"
        ) from exc

    recorded_at = record["recorded_at"]
    if not isinstance(recorded_at, str):
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid recorded_at"
        )
    try:
        timestamp = datetime.fromisoformat(recorded_at)
    except ValueError as exc:
        raise OriginalityLedgerError(
            f"ledger line {line_number} has invalid recorded_at"
        ) from exc
    if timestamp.tzinfo is None:
        raise OriginalityLedgerError(
            f"ledger line {line_number} recorded_at must be timezone-aware"
        )


def _difference_count(
    candidate_axes: Mapping[str, str], existing_axes: Mapping[str, str]
) -> DifferenceCount:
    return DifferenceCount(
        concept=sum(
            candidate_axes[axis] != existing_axes[axis] for axis in CONCEPT_AXES
        ),
        cinematic=sum(
            candidate_axes[axis] != existing_axes[axis] for axis in CINEMATIC_AXES
        ),
        surface=sum(
            candidate_axes[axis] != existing_axes[axis] for axis in SURFACE_AXES
        ),
    )


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def _materially_novel(difference: DifferenceCount) -> bool:
    return (
        difference.material >= MIN_MATERIAL_DIFFERENCES
        and difference.concept >= MIN_CONCEPT_DIFFERENCES
        and difference.cinematic >= MIN_CINEMATIC_DIFFERENCES
    )


def _receipt(
    *,
    status: str,
    candidate: Candidate,
    seed_id: str,
    sequence: int,
    record_count: int,
    recorded_at: str,
    closest_seed_id: str | None,
    closest_difference: DifferenceCount | None,
    max_jaccard_seed_id: str | None,
    max_jaccard: float,
) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "verdict": "PASS",
        "status": status,
        "episode_id": candidate.episode_id,
        "seed_id": seed_id,
        "parent_seed_id": candidate.parent_seed_id,
        "registration_kind": candidate.registration_kind,
        "signature_sha256": candidate.signature_sha256,
        "description_sha256": description_sha256(candidate.description_normalized),
        "sequence": sequence,
        "ledger_record_count": record_count,
        "recorded_at": recorded_at,
        "novelty_policy": {
            "material_differences_required": MIN_MATERIAL_DIFFERENCES,
            "concept_differences_required": MIN_CONCEPT_DIFFERENCES,
            "cinematic_differences_required": MIN_CINEMATIC_DIFFERENCES,
            "surface_axes_counted": False,
            "description_jaccard_fail_at_or_above": DESCRIPTION_JACCARD_LIMIT,
            "closest_structural_seed_id": closest_seed_id,
            "closest_structural_difference": (
                closest_difference.as_dict() if closest_difference else None
            ),
            "max_description_jaccard_seed_id": max_jaccard_seed_id,
            "max_description_jaccard": round(max_jaccard, 6),
        },
    }


def _now_iso(now: datetime | None) -> str:
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise OriginalityValidationError("now must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat()


def _write_all(file_descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(file_descriptor, view)
        if written <= 0:
            raise OSError("short write while appending originality ledger")
        view = view[written:]


def read_validated_ledger(ledger_path: Path) -> list[dict[str, Any]]:
    """Read and validate a ledger under a shared lock without modifying it."""

    ledger = Path(ledger_path)
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        file_descriptor = os.open(ledger, flags)
    except OSError as exc:
        raise OriginalityLedgerError(f"ledger is unreadable: {ledger}") from exc
    try:
        fcntl.flock(file_descriptor, fcntl.LOCK_SH)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return _load_ledger_bytes(b"".join(chunks))
    finally:
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_UN)
        finally:
            os.close(file_descriptor)


def validated_ledger_prefix_sha256(ledger_path: Path, record_count: int) -> str:
    """Hash the exact raw-byte prefix containing the first ``record_count`` rows.

    The complete ledger is first parsed and policy-validated while a shared
    lock prevents concurrent appends.  The returned digest covers the original
    JSONL bytes, including every newline, rather than a re-serialized object.
    This lets downstream consumers prove that a registration prefix remains
    unchanged even after valid records are appended to the ledger.
    """

    if (
        not isinstance(record_count, int)
        or isinstance(record_count, bool)
        or record_count < 0
    ):
        raise OriginalityLedgerError("record_count must be a non-negative integer")

    ledger = Path(ledger_path)
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        file_descriptor = os.open(ledger, flags)
    except OSError as exc:
        raise OriginalityLedgerError(f"ledger is unreadable: {ledger}") from exc
    try:
        fcntl.flock(file_descriptor, fcntl.LOCK_SH)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        records = _load_ledger_bytes(payload)
        if record_count > len(records):
            raise OriginalityLedgerError(
                f"record_count {record_count} exceeds ledger length {len(records)}"
            )
        raw_lines = payload.splitlines(keepends=True)
        prefix = b"".join(raw_lines[:record_count])
        return hashlib.sha256(prefix).hexdigest()
    finally:
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_UN)
        finally:
            os.close(file_descriptor)


def check_and_record(
    ledger_path: Path,
    request: Mapping[str, Any],
    *,
    register_root: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check and append one original signature, returning a receipt object.

    The full read/check/append cycle is serialized on the ledger file itself.
    Failed candidates and idempotent replays do not append a record.
    """

    candidate = _parse_candidate(request, register_root=register_root)
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    file_descriptor = os.open(ledger, flags, 0o600)
    try:
        fcntl.flock(file_descriptor, fcntl.LOCK_EX)
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        records = _load_ledger_bytes(b"".join(chunks))

        if records and records[0]["episode_id"] != candidate.episode_id:
            raise OriginalityLedgerError(
                "ledger episode_id does not match the candidate episode_id"
            )

        if candidate.registration_kind == "root":
            if candidate.supplied_seed_id is None:  # Defensive type narrowing.
                raise OriginalityValidationError("root registration requires seed_id")
            derived_seed = candidate.supplied_seed_id
        else:
            if candidate.parent_seed_id is None:  # Defensive type narrowing.
                raise OriginalityValidationError(
                    "child registration requires parent_seed_id"
                )
            derived_seed = derive_child_seed(
                candidate.parent_seed_id, candidate.signature_sha256
            )

        for record in records:
            if record["seed_id"] != derived_seed:
                continue
            if record["signature_sha256"] != candidate.signature_sha256:
                raise OriginalitySeedMutationError(
                    f"seed_id {derived_seed} is already bound to another signature"
                )
            if (
                record["registration_kind"] != candidate.registration_kind
                or record["parent_seed_id"] != candidate.parent_seed_id
            ):
                raise OriginalitySeedMutationError(
                    f"seed_id {derived_seed} replay changes its lineage"
                )
            if record["description_normalized"] != candidate.description_normalized:
                raise OriginalitySeedMutationError(
                    f"seed_id {derived_seed} replay changes its normalized description"
                )
            return _receipt(
                status="IDEMPOTENT_REPLAY",
                candidate=candidate,
                seed_id=derived_seed,
                sequence=record["sequence"],
                record_count=len(records),
                recorded_at=record["recorded_at"],
                closest_seed_id=None,
                closest_difference=None,
                max_jaccard_seed_id=None,
                max_jaccard=0.0,
            )

        if (
            candidate.supplied_seed_id is not None
            and candidate.supplied_seed_id != derived_seed
        ):
            for record in records:
                if record["seed_id"] == candidate.supplied_seed_id:
                    raise OriginalitySeedMutationError(
                        f"seed_id {candidate.supplied_seed_id} is already bound to another signature"
                    )
            raise OriginalityValidationError(
                "supplied child seed_id does not match UUID5(parent_seed_id, signature_sha256)"
            )

        if candidate.registration_kind == "child" and not any(
            record["seed_id"] == candidate.parent_seed_id for record in records
        ):
            raise OriginalityValidationError(
                f"parent_seed_id {candidate.parent_seed_id} does not exist in the ledger"
            )

        exact_collision = next(
            (
                record
                for record in records
                if record["signature_sha256"] == candidate.signature_sha256
            ),
            None,
        )
        if exact_collision is not None:
            raise OriginalityCollisionError(
                "structural signature already belongs to seed_id "
                f"{exact_collision['seed_id']}"
            )

        closest_seed_id: str | None = None
        closest_difference: DifferenceCount | None = None
        for record in records:
            difference = _difference_count(
                candidate.signature_axes, record["signature_axes"]
            )
            if closest_difference is None or (
                difference.material,
                difference.concept,
                difference.cinematic,
            ) < (
                closest_difference.material,
                closest_difference.concept,
                closest_difference.cinematic,
            ):
                closest_seed_id = record["seed_id"]
                closest_difference = difference
            if not _materially_novel(difference):
                raise OriginalityCollisionError(
                    "candidate is not materially novel relative to seed_id "
                    f"{record['seed_id']}: {difference.as_dict()}"
                )

        max_jaccard = 0.0
        max_jaccard_seed_id: str | None = None
        for record in records:
            similarity = _jaccard(
                candidate.description_tokens, record["description_tokens"]
            )
            if similarity > max_jaccard:
                max_jaccard = similarity
                max_jaccard_seed_id = record["seed_id"]
            if similarity >= DESCRIPTION_JACCARD_LIMIT:
                raise OriginalityCollisionError(
                    "description-token Jaccard collision with seed_id "
                    f"{record['seed_id']}: {similarity:.6f} >= "
                    f"{DESCRIPTION_JACCARD_LIMIT:.2f}"
                )

        recorded_at = _now_iso(now)
        sequence = len(records) + 1
        record = {
            "schema_version": LEDGER_SCHEMA,
            "sequence": sequence,
            "episode_id": candidate.episode_id,
            "seed_id": derived_seed,
            "parent_seed_id": candidate.parent_seed_id,
            "registration_kind": candidate.registration_kind,
            "signature_axes": candidate.signature_axes,
            "signature_sha256": candidate.signature_sha256,
            "description_normalized": candidate.description_normalized,
            "description_tokens": list(candidate.description_tokens),
            "recorded_at": recorded_at,
        }
        serialized = (
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        os.lseek(file_descriptor, 0, os.SEEK_END)
        _write_all(file_descriptor, serialized)
        os.fsync(file_descriptor)

        return _receipt(
            status="RECORDED",
            candidate=candidate,
            seed_id=derived_seed,
            sequence=sequence,
            record_count=sequence,
            recorded_at=recorded_at,
            closest_seed_id=closest_seed_id,
            closest_difference=closest_difference,
            max_jaccard_seed_id=max_jaccard_seed_id,
            max_jaccard=max_jaccard,
        )
    finally:
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_UN)
        finally:
            os.close(file_descriptor)


def _load_request(path: str) -> Mapping[str, Any]:
    if path == "-":
        raw = sys.stdin.buffer.read()
    else:
        raw = Path(path).read_bytes()
    try:
        request = json.loads(raw, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise OriginalityValidationError("request is not strict JSON") from exc
    if not isinstance(request, dict):
        raise OriginalityValidationError("request must be a JSON object")
    return request


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check-and-record", help="check and reserve one creative signature"
    )
    check.add_argument("--ledger", type=Path, required=True)
    check.add_argument("--request", required=True, help="JSON path, or - for stdin")
    check.add_argument(
        "--register-root",
        action="store_true",
        help="explicitly register a root seed instead of deriving a child",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the JSON-only CLI and return a process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        request = _load_request(args.request)
        receipt = check_and_record(
            args.ledger,
            request,
            register_root=args.register_root,
        )
        exit_code = 0
    except OriginalityGateError as exc:
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "verdict": "FAIL",
            "error_code": exc.error_code,
            "message": str(exc),
        }
        exit_code = 2
    except (OSError, TypeError, ValueError) as exc:
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "verdict": "FAIL",
            "error_code": "LOCAL_IO_ERROR",
            "message": str(exc),
        }
        exit_code = 2
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
