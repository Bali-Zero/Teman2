#!/usr/bin/env python3
"""Derive immutable-source E13 camera-probe packs for WR3 render execution.

This is deliberately a *probe-specific* pre-render adapter/gate.  The normal
``wr3_gatekeeper_check.py`` is the final-episode spend gate and caps its
``prompt_positive`` dialect at 25 words.  E13's authorised camera tests use
long, camera-first Veo prompts; pretending those are final-episode shots would
either destroy the experiment or bypass a real gate.  Instead this module:

* reads the six approved source packs without modifying them;
* strips prompt-transport markers that Veo can render as fake camera UI;
* splits their trailing negative clauses from the positive render prompt;
* emits a schema accepted by both WR3 render entry points;
* assigns globally unique episode, shot, probe, and child-seed identifiers;
* normalises the renderer identity token to the exact ``A007`` contract;
* removes every voiced/legal claim from the f06 static-verdict probes; and
* writes SHA-256 lineage receipts plus one fail-closed probe verdict.

It never calls Flow, spends credits, publishes, or authorises a final episode.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from wr3_originality_gate import (
    OriginalityGateError,
    canonicalize_signature_axes,
    description_sha256 as originality_description_sha256,
    normalize_text as originality_normalize_text,
    read_validated_ledger,
    signature_sha256 as originality_signature_sha256,
    validated_ledger_prefix_sha256,
)

ADAPTER_VERSION = "1.2"
RUNTIME_SCHEMA_VERSION = "wr3-camera-probe-runtime/1.0"
RECEIPT_SCHEMA_VERSION = "wr3-camera-probe-lineage/1.0"
VERDICT_SCHEMA_VERSION = "wr3-camera-probe-gate/1.0"
OUTPUT_LOCK_NAME = ".probe-adapter.lock"
EXPECTED_PLAN_EPISODE_ID = "s01e13-residency-permit-probes"
EXPECTED_CONTEXT_EPISODE_ID = "S01E13"
EXPECTED_CANDIDATE_ID = "C07"
EXPECTED_ORIGINALITY_EPISODE_ID = "s01e13-residency-permit"
EXPECTED_FAMILY_COUNT = 6
EXPECTED_VARIANTS_PER_FAMILY = 4
EXPECTED_GENERATION_COUNT = 24

FAMILY_RE = re.compile(r"^f(?P<number>\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_EPISODE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STYLE_RE = re.compile(
    r"\b(editorial\s+documentary|documentary|cinematic|journalistic|"
    r"press\s+photography|magazine\s+cover|National\s+Geographic|"
    r"award-winning)\b",
    re.IGNORECASE,
)
SENSITIVE_RE = re.compile(
    r"\b(passport|visa\s+stamp|visa\s+document|stamp\s+page)\b",
    re.IGNORECASE,
)
CITY_RE = re.compile(r"\b(Jakarta|Bali|Surabaya|Denpasar|Medan)\b")
SAFETY_RE = re.compile(
    r"\b(prison|prisons|punishes|punish|violence|violent|shooting|shoot|"
    r"kill|killed|dead|death|handcuff|handcuffs|weapon|weapons|officer|"
    r"officers|uniform|arrest|deport|deportation|gun|blood)\b",
    re.IGNORECASE,
)
CLICHE_RE = re.compile(
    r"\b(beach|palm\s+tree|palm\s+trees|infinity\s+pool|sunset|sunrise|"
    r"rice\s+paddy|rice\s+terrace|temple|laptop\s+on\s+beach|coffee\s+cup|"
    r"coconut|boho|influencer|handshake|smiling\s+team|stock\s+photo|"
    r"drone\s+over\s+ocean)\b",
    re.IGNORECASE,
)
F06_VOICE_RE = re.compile(
    r"[\u201c\u201d\"]|\b(says?|speaks?|spoken|voice|dialogue|lip[ -]?sync|"
    r"addresses?)\b",
    re.IGNORECASE,
)
F06_LEGAL_RE = re.compile(
    r"\b(residen(?:ce|cy)|permit|permission|status|right|rights|all-access|"
    r"work|property|bank|banking|tax|citizenship|visa)\b",
    re.IGNORECASE,
)

# The source camera/lens/identity prefix is preserved verbatim.  Only the
# legally ungrounded speaking performance is replaced with this visual action.
F06_VISUAL_ONLY_SUFFIX = (
    "One action only: Zantara meets the lens, takes one controlled breath "
    "with naturally closed lips, and holds calm, precise eye contact without "
    "smiling or dramatizing. Her chosen stillness reverses the preceding "
    "movement and leaves a clean edit handle. Soft neutral architectural "
    "daylight, quiet negative space, and realistic skin texture. Native audio "
    "contains subtle room tone, fabric movement, breathing, and one faint "
    "architectural click after the hold."
)
F06_EXTRA_NEGATIVE = (
    "speech, dialogue, vocalization, lip sync, moving lips, subtitles, captions"
)
GLOBAL_TRANSPORT_NEGATIVE = (
    "on-screen camera user interface, technical overlays, aspect-ratio labels, "
    "frame-rate labels, fps labels, lens labels, framing guides, contact sheet, "
    "split screen, reference-image display, letterbox bars, pillarbox bars, "
    "any visible text"
)
TRANSPORT_PREFIX_RE = re.compile(r"^\s*CAMERA\s+FIRST\s*:\s*", re.IGNORECASE)
DELIVERY_ASPECT_RE = re.compile(
    r"\b(?:vertical\s+)?(?:9\s*:\s*16|720\s*[x\u00d7]\s*1280)"
    r"(?:\s+(?:portrait|format|aspect(?:\s+ratio)?))?\b",
    re.IGNORECASE,
)


class ProbeAdapterError(ValueError):
    """A fail-closed probe contract violation."""


@dataclass(frozen=True)
class Inputs:
    repo_root: Path
    plan_path: Path
    authorization_path: Path
    context_path: Path
    creative_lock_path: Path
    output_root: Path


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """Durably replace one authorization artifact without a torn-write window."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _exclusive_output_lock(output_root: Path) -> Iterator[None]:
    """Serialize derivations while retaining a stable lock inode on disk."""

    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / OUTPUT_LOCK_NAME
    try:
        handle = lock_path.open("a+b")
    except OSError as exc:
        raise ProbeAdapterError(
            f"probe adapter lock cannot be opened: {lock_path}: {exc}"
        ) from exc

    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise ProbeAdapterError(
                    f"probe adapter already running for output root: {output_root}"
                ) from exc
            raise ProbeAdapterError(
                f"probe adapter lock failed: {lock_path}: {exc}"
            ) from exc
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProbeAdapterError(f"{label} unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProbeAdapterError(f"{label} must be a JSON object: {path}")
    return value


def _required_str(obj: dict[str, Any], key: str, label: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProbeAdapterError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _validate_uuid(value: str, label: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ProbeAdapterError(f"{label} is not a UUID: {value!r}") from exc


def _resolve_repo_source(repo_root: Path, source_ref: str) -> Path:
    source_path = (repo_root / source_ref).resolve()
    try:
        source_path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ProbeAdapterError(f"source pack escapes repo root: {source_ref}") from exc
    if not source_path.is_file():
        raise ProbeAdapterError(f"source pack does not exist: {source_ref}")
    return source_path


def _validate_originality_binding(
    repo_root: Path,
    creative_lock: dict[str, Any],
) -> dict[str, Any]:
    """Validate the registered creative signature without mutating its ledger."""

    seed_id = _required_str(creative_lock, "seed_id", "creative lock")
    parent_seed_id = creative_lock.get("parent_seed_id")
    description = _required_str(
        creative_lock,
        "originality_description",
        "creative lock",
    )
    raw_axes = creative_lock.get("signature_axes")
    try:
        axes = canonicalize_signature_axes(raw_axes)
        signature_digest = originality_signature_sha256(axes)
    except OriginalityGateError as exc:
        raise ProbeAdapterError(
            f"creative-lock originality axes invalid: {exc}"
        ) from exc

    gate = creative_lock.get("originality_gate")
    if not isinstance(gate, dict):
        raise ProbeAdapterError("creative_lock.originality_gate must be an object")
    if gate.get("verdict") != "PASS":
        raise ProbeAdapterError("creative-lock originality gate must be PASS")
    expected_kind = "root" if parent_seed_id is None else "child"
    if gate.get("registration_kind") != expected_kind:
        raise ProbeAdapterError(
            "creative-lock originality registration kind is inconsistent"
        )
    if gate.get("signature_sha256") != signature_digest:
        raise ProbeAdapterError("creative-lock originality signature SHA mismatch")
    expected_description_sha = originality_description_sha256(
        originality_normalize_text(description)
    )
    if gate.get("description_sha256") != expected_description_sha:
        raise ProbeAdapterError("creative-lock originality description SHA mismatch")

    resolved: dict[str, Path] = {}
    for name in ("request", "receipt", "ledger"):
        path_ref = _required_str(gate, f"{name}_path", "creative lock originality gate")
        resolved[name] = _resolve_repo_source(repo_root, path_ref)

    request_sha = _sha256_path(resolved["request"])
    receipt_sha = _sha256_path(resolved["receipt"])
    if request_sha != gate.get("request_sha256"):
        raise ProbeAdapterError("originality request SHA mismatch")
    if receipt_sha != gate.get("receipt_sha256"):
        raise ProbeAdapterError("originality receipt SHA mismatch")

    request = _read_json(resolved["request"], "originality request")
    receipt = _read_json(resolved["receipt"], "originality receipt")
    expected_request = {
        "schema_version": "wr3.originality-request.v1",
        "episode_id": EXPECTED_ORIGINALITY_EPISODE_ID,
        "seed_id": seed_id,
        "parent_seed_id": parent_seed_id,
        "description": description,
        "signature_axes": raw_axes,
    }
    if request != expected_request:
        raise ProbeAdapterError(
            "originality request is not the exact creative-lock projection"
        )

    expected_receipt_fields = {
        "schema_version": "wr3.originality-receipt.v1",
        "verdict": "PASS",
        "episode_id": EXPECTED_ORIGINALITY_EPISODE_ID,
        "seed_id": seed_id,
        "parent_seed_id": parent_seed_id,
        "registration_kind": expected_kind,
        "signature_sha256": signature_digest,
        "description_sha256": expected_description_sha,
    }
    for key, expected in expected_receipt_fields.items():
        if receipt.get(key) != expected:
            raise ProbeAdapterError(f"originality receipt {key} mismatch")
    if receipt.get("status") not in {"RECORDED", "IDEMPOTENT_REPLAY"}:
        raise ProbeAdapterError("originality receipt status is not durable")

    try:
        records = read_validated_ledger(resolved["ledger"])
    except OriginalityGateError as exc:
        raise ProbeAdapterError(f"originality ledger invalid: {exc}") from exc
    matching = [
        record
        for record in records
        if record["seed_id"] == seed_id
        and record["signature_sha256"] == signature_digest
        and record["parent_seed_id"] == parent_seed_id
        and record["registration_kind"] == expected_kind
    ]
    if len(matching) != 1:
        raise ProbeAdapterError(
            "originality ledger does not contain one exact lock record"
        )
    if matching[0]["description_normalized"] != originality_normalize_text(description):
        raise ProbeAdapterError(
            "originality ledger description does not match creative lock"
        )
    if matching[0]["sequence"] != receipt.get("sequence"):
        raise ProbeAdapterError("originality receipt sequence does not match ledger")
    receipt_record_count = receipt.get("ledger_record_count")
    if (
        isinstance(receipt_record_count, bool)
        or not isinstance(receipt_record_count, int)
        or receipt_record_count < matching[0]["sequence"]
        or len(records) < receipt_record_count
    ):
        raise ProbeAdapterError("originality receipt ledger count is inconsistent")
    registration_sha = _required_str(
        gate,
        "ledger_sha256_at_registration",
        "creative lock originality gate",
    )
    try:
        prefix_sha = validated_ledger_prefix_sha256(
            resolved["ledger"],
            receipt_record_count,
        )
    except OriginalityGateError as exc:
        raise ProbeAdapterError(
            f"originality ledger registration prefix invalid: {exc}"
        ) from exc
    if prefix_sha != registration_sha:
        raise ProbeAdapterError("originality ledger registration SHA mismatch")

    return {
        "verdict": "PASS",
        "registration_kind": expected_kind,
        "signature_sha256": signature_digest,
        "description_sha256": receipt["description_sha256"],
        "request_path": gate["request_path"],
        "request_sha256": request_sha,
        "receipt_path": gate["receipt_path"],
        "receipt_sha256": receipt_sha,
        "ledger_path": gate["ledger_path"],
        "ledger_sha256_at_registration": gate["ledger_sha256_at_registration"],
        "ledger_record_count_at_registration": receipt_record_count,
    }


def _split_negative_clause(prompt: str) -> tuple[str, str]:
    """Split the final ``No ...`` sentence into the renderer negative field."""
    match = re.search(r"\s+No\s+([^\n]+?)\.?$", prompt.strip())
    if match is None:
        raise ProbeAdapterError(
            "source prompt must end with an explicit 'No ...' clause"
        )
    positive = prompt[: match.start()].strip()
    negative = match.group(1).strip().rstrip(".")
    if not positive or not negative:
        raise ProbeAdapterError(
            "source prompt produced an empty positive or negative clause"
        )
    return positive, negative


def _without_duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip().strip(",")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


def _add_negative(base: str, extra: str) -> str:
    return ", ".join(_without_duplicates([*base.split(","), *extra.split(",")]))


def _strip_prompt_transport(prompt: str) -> str:
    """Remove delivery metadata while preserving camera/lens direction.

    The aspect ratio and output resolution are already typed fields in the
    runtime pack.  Repeating them in prose caused Veo to draw fake technical
    overlays, framing guides, and letterbox bars in the canary.  Lens and
    movement declarations are intentionally untouched because they are the
    creative variable under test.
    """
    cleaned = TRANSPORT_PREFIX_RE.sub("", prompt)
    cleaned = DELIVERY_ASPECT_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"([,;:])\s*([,;:])(?:\s*[,;:])*", r"\1", cleaned)
    cleaned = re.sub(r",\s*([.;])", r"\1", cleaned)
    return cleaned.strip(" ,;")


def _make_f06_visual_only(positive: str, negative: str) -> tuple[str, str]:
    marker = "One action only:"
    if marker not in positive:
        raise ProbeAdapterError("f06 prompt is missing its action marker")
    camera_and_identity = positive.split(marker, 1)[0].strip()
    visual_positive = f"{camera_and_identity} {F06_VISUAL_ONLY_SUFFIX}"
    return visual_positive, _add_negative(negative, F06_EXTRA_NEGATIVE)


def _variant_seed(root_seed: str, global_probe_id: str) -> str:
    return str(uuid.uuid5(uuid.UUID(root_seed), global_probe_id))


def _word_count(value: str) -> int:
    return len(value.split())


def _validate_positive_prompt(
    prompt: str,
    *,
    family_id: str,
    shot_id: str,
) -> list[str]:
    issues: list[str] = []
    word_count = _word_count(prompt)
    # This bounded camera-probe dialect is intentionally distinct from the
    # final-episode 25-word gate.  Rich source prompts were approved at 100-150
    # words; after moving the negative clause out, 60-135 words is the explicit
    # renderer contract.
    if not 60 <= word_count <= 135:
        issues.append(f"positive wordcount {word_count} outside 60..135")
    for label, pattern in (
        ("style modifier", STYLE_RE),
        ("sensitive object", SENSITIVE_RE),
        ("city name", CITY_RE),
        ("safety word", SAFETY_RE),
        ("cliche", CLICHE_RE),
    ):
        matches = sorted({str(value).lower() for value in pattern.findall(prompt)})
        if matches:
            issues.append(f"{label}: {matches}")
    if family_id == "f06-static-verdict":
        if F06_VOICE_RE.search(prompt):
            issues.append("f06 contains voiced-performance language")
        if F06_LEGAL_RE.search(prompt):
            issues.append("f06 contains an ungrounded legal claim token")
    return [f"{shot_id}: {issue}" for issue in issues]


def _source_prompt_issues(prompt: str, shot_label: str) -> list[str]:
    issues: list[str] = []
    word_count = _word_count(prompt)
    if not 100 <= word_count <= 150:
        issues.append(f"{shot_label}: source wordcount {word_count} outside 100..150")
    return issues


def _derive_family(
    *,
    repo_root: Path,
    plan: dict[str, Any],
    context: dict[str, Any],
    originality_binding: dict[str, Any],
    family: dict[str, Any],
    variants_per_family: int,
) -> tuple[dict[str, Any], dict[str, Any], Path, str, list[str]]:
    family_id = _required_str(family, "id", "family")
    family_match = FAMILY_RE.fullmatch(family_id)
    if family_match is None:
        raise ProbeAdapterError(f"invalid family id: {family_id!r}")
    family_number = int(family_match.group("number"))
    source_ref = _required_str(family, "source_pack", family_id)
    source_path = _resolve_repo_source(repo_root, source_ref)
    source_sha = _sha256_path(source_path)
    source = _read_json(source_path, f"source pack {family_id}")

    source_episode_id = _required_str(source, "episode_id", family_id)
    if SOURCE_EPISODE_RE.fullmatch(source_episode_id) is None:
        raise ProbeAdapterError(
            f"{family_id}: invalid source episode id {source_episode_id!r}"
        )
    shots = source.get("shots")
    if not isinstance(shots, list) or len(shots) != variants_per_family:
        raise ProbeAdapterError(
            f"{family_id}: expected {variants_per_family} source shots, got "
            f"{len(shots) if isinstance(shots, list) else 'non-list'}"
        )

    identity = context.get("identity")
    if not isinstance(identity, dict):
        raise ProbeAdapterError("context.identity must be an object")
    anchor_id = _required_str(identity, "anchor_id", "context.identity")
    if anchor_id != "A007":
        raise ProbeAdapterError(
            f"context identity must be exact A007, got {anchor_id!r}"
        )
    anchor_path = _required_str(identity, "anchor_path_on_pro", "context.identity")
    anchor_sha = _required_str(identity, "anchor_sha256", "context.identity")
    if source.get("anchor_image_path") != anchor_path:
        raise ProbeAdapterError(
            f"{family_id}: source anchor path does not match context"
        )

    creative_seed_id = _required_str(plan, "creative_seed_id", "probe plan")
    source_topic = _required_str(source, "topic", family_id)
    runtime_episode_id = f"{source_episode_id}-{family_id}"
    runtime_shots: list[dict[str, Any]] = []
    transition_entries: list[dict[str, Any]] = []
    variant_receipts: list[dict[str, Any]] = []
    issues: list[str] = []

    source_indices: set[int] = set()
    for expected_variant, source_shot in enumerate(shots, start=1):
        if not isinstance(source_shot, dict):
            raise ProbeAdapterError(
                f"{family_id}: source shot {expected_variant} is not an object"
            )
        source_index = source_shot.get("index")
        if not isinstance(source_index, int) or isinstance(source_index, bool):
            raise ProbeAdapterError(
                f"{family_id}: source shot index must be an integer"
            )
        if source_index != expected_variant:
            raise ProbeAdapterError(
                f"{family_id}: expected source index {expected_variant}, got {source_index}"
            )
        if source_index in source_indices:
            raise ProbeAdapterError(
                f"{family_id}: duplicate source index {source_index}"
            )
        source_indices.add(source_index)

        source_prompt = _required_str(
            source_shot,
            "positive_prompt",
            f"{family_id}[{source_index}]",
        )
        issues.extend(
            _source_prompt_issues(source_prompt, f"{family_id}[{source_index}]")
        )
        source_tokens = source_shot.get("identity_tokens")
        if not isinstance(source_tokens, list) or not any(
            isinstance(token, str) and "A007" in token for token in source_tokens
        ):
            raise ProbeAdapterError(
                f"{family_id}[{source_index}]: source has no A007 lineage token"
            )

        positive, negative = _split_negative_clause(source_prompt)
        positive = _strip_prompt_transport(positive)
        negative = _add_negative(negative, GLOBAL_TRANSPORT_NEGATIVE)
        if family_id == "f06-static-verdict":
            positive, negative = _make_f06_visual_only(positive, negative)

        shot_number = family_number * 100 + source_index
        shot_id = f"s{shot_number:04d}"
        variant_id = f"v{source_index:02d}"
        global_probe_id = f"{plan['episode_id']}:{family_id}:{variant_id}"
        child_seed = _variant_seed(creative_seed_id, global_probe_id)
        issues.extend(
            _validate_positive_prompt(positive, family_id=family_id, shot_id=shot_id)
        )

        duration_s = source_shot.get("duration_s")
        if duration_s != 8:
            issues.append(f"{shot_id}: duration must be exactly 8 seconds")
        resolution = source_shot.get("resolution")
        aspect = source_shot.get("aspect")
        if resolution != "720x1280" or aspect != "9:16":
            issues.append(f"{shot_id}: expected 720x1280 at 9:16")

        runtime_shot = {
            "index": shot_number,
            "shot_id": shot_id,
            "global_probe_id": global_probe_id,
            "variant_id": variant_id,
            "variant_seed_id": child_seed,
            "family_id": family_id,
            "creative_seed_id": creative_seed_id,
            "shot_type": "zantara-camera-probe",
            "prompt_positive": positive,
            "positive_prompt": positive,
            "prompt_negative": negative,
            "negative_prompt": negative,
            "identity_tokens": ["A007"],
            "duration_s": 8,
            "resolution": "720x1280",
            "aspect": "9:16",
            "transition_to_next": None,
            "audio_mode": (
                "native-ambient-only"
                if family_id == "f06-static-verdict"
                else "native-dub-safe-ambient"
            ),
        }
        runtime_shots.append(runtime_shot)
        transition_entries.append(
            {
                "shot_id": shot_id,
                "from": None,
                "to": None,
                "transition": "standalone-camera-probe",
            }
        )
        variant_receipts.append(
            {
                "source_index": source_index,
                "source_prompt_sha256": _sha256_bytes(source_prompt.encode("utf-8")),
                "shot_id": shot_id,
                "global_probe_id": global_probe_id,
                "variant_id": variant_id,
                "variant_seed_id": child_seed,
                "runtime_positive_prompt_sha256": _sha256_bytes(
                    positive.encode("utf-8")
                ),
                "runtime_negative_prompt_sha256": _sha256_bytes(
                    negative.encode("utf-8")
                ),
            }
        )

    runtime_pack = {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "episode_id": runtime_episode_id,
        "source_episode_id": source_episode_id,
        "candidate_id": context.get("candidate_id"),
        "creative_seed_id": creative_seed_id,
        "originality_gate": originality_binding,
        "family_id": family_id,
        "source_pack": source_ref,
        "source_pack_sha256": source_sha,
        "topic": source_topic,
        "purpose": "authorised standalone cinematic camera probes; not a final episode",
        "anchor_image_path": anchor_path,
        "anchor_sha256": anchor_sha,
        "identity_token": "A007",
        "aspect_ratio": "9:16",
        "resolution": "720x1280",
        "total_duration_s": 8 * len(runtime_shots),
        "transition_map": {
            "mode": "standalone-camera-probes",
            "entries": transition_entries,
        },
        "shots": runtime_shots,
    }
    runtime_bytes = _json_bytes(runtime_pack)
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "family_id": family_id,
        "creative_seed_id": creative_seed_id,
        "originality_gate": originality_binding,
        "source_pack": source_ref,
        "source_pack_sha256": source_sha,
        "runtime_episode_id": runtime_episode_id,
        "runtime_pack": f"{family_id}/shot-pack.json",
        "runtime_pack_sha256": _sha256_bytes(runtime_bytes),
        "transformations": [
            "globally unique family and shot identifiers",
            "prompt transport and aspect markers removed from positive prose",
            "source negative clause split into renderer negative fields",
            "global camera-UI and visible-text protections added to negative prompt",
            "identity token normalized to exact A007",
            (
                "voiced and legal performance replaced by visual-only native ambience"
                if family_id == "f06-static-verdict"
                else "source visual performance preserved"
            ),
        ],
        "variants": variant_receipts,
    }
    return runtime_pack, receipt, source_path, source_sha, issues


def _derive_probe_runtime_locked(inputs: Inputs) -> dict[str, Any]:
    """Validate inputs and publish a fail-closed runtime authorization set.

    The canonical verdict is durably changed to FAIL before validation or any
    family write. Family files may therefore remain after an interrupted or
    failed re-derivation, but they are not spend-authorized until the final
    PASS verdict binds their exact SHA-256 values.
    """
    try:
        plan_sha = (
            _sha256_path(inputs.plan_path) if inputs.plan_path.is_file() else None
        )
    except OSError:
        # _read_json below will turn the same fault into the named FAIL reason.
        plan_sha = None
    verdict: dict[str, Any] = {
        "schema_version": VERDICT_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "verdict": "FAIL",
        "scope": "E13 authorised camera probes only; no Flow call and no final-episode approval",
        "plan_sha256": plan_sha,
        "checks": {},
        "errors": [],
        "families": [],
    }
    verdict_path = inputs.output_root / "probe-gate-verdict.json"
    # Invalidate any earlier PASS before touching runtime family files. The
    # charged runner requires this current verdict and its exact family hash.
    _write_bytes_atomic(verdict_path, _json_bytes(verdict))

    try:
        plan = _read_json(inputs.plan_path, "probe plan")
        authorization = _read_json(inputs.authorization_path, "probe authorization")
        context = _read_json(inputs.context_path, "context snapshot")
        creative_lock = _read_json(inputs.creative_lock_path, "creative lock")
        originality_binding = _validate_originality_binding(
            inputs.repo_root,
            creative_lock,
        )

        plan_episode_id = _required_str(plan, "episode_id", "probe plan")
        if plan_episode_id != EXPECTED_PLAN_EPISODE_ID:
            raise ProbeAdapterError(
                f"expected E13 probe episode {EXPECTED_PLAN_EPISODE_ID!r}, "
                f"got {plan_episode_id!r}"
            )
        if context.get("episode_id") != EXPECTED_CONTEXT_EPISODE_ID:
            raise ProbeAdapterError(
                f"context must identify {EXPECTED_CONTEXT_EPISODE_ID}"
            )
        if context.get("candidate_id") != EXPECTED_CANDIDATE_ID:
            raise ProbeAdapterError(
                f"context must identify candidate {EXPECTED_CANDIDATE_ID}"
            )
        creative_seed_id = _required_str(plan, "creative_seed_id", "probe plan")
        _validate_uuid(creative_seed_id, "probe plan creative_seed_id")
        if creative_lock.get("seed_id") != creative_seed_id:
            raise ProbeAdapterError("creative-lock seed does not match probe plan")
        if authorization.get("episode_id") != plan_episode_id:
            raise ProbeAdapterError("authorization episode does not match probe plan")
        if authorization.get("candidate_id") != context.get("candidate_id"):
            raise ProbeAdapterError("authorization candidate does not match context")
        authorised = authorization.get("authorized")
        if (
            not isinstance(authorised, dict)
            or authorised.get("topic_pilot") is not True
        ):
            raise ProbeAdapterError("topic pilot is not authorised")
        if authorised.get("creative_lock") is not True:
            raise ProbeAdapterError("creative lock is not authorised")
        if authorised.get("native_audio") is not True:
            raise ProbeAdapterError("native audio is not authorised")

        legal_scope = context.get("legal_scope")
        if not isinstance(legal_scope, dict):
            raise ProbeAdapterError("context.legal_scope must be an object")
        if legal_scope.get("camera_probes_only") is not True:
            raise ProbeAdapterError(
                "context does not restrict execution to camera probes"
            )
        if legal_scope.get("implementation_specific_claims_allowed") is not False:
            raise ProbeAdapterError(
                "context does not prohibit ungrounded implementation claims"
            )
        lock_scope = creative_lock.get("probe_scope")
        if (
            not isinstance(lock_scope, dict)
            or lock_scope.get("publication_allowed") is not False
        ):
            raise ProbeAdapterError(
                "creative lock does not explicitly prohibit publication"
            )

        family_count = plan.get("family_count")
        variants_per_family = plan.get("variants_per_family")
        authorised_generation_count = plan.get("authorized_generation_count")
        if not all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in (
                family_count,
                variants_per_family,
                authorised_generation_count,
            )
        ):
            raise ProbeAdapterError("probe counts must be positive integers")
        expected_matrix = (
            EXPECTED_FAMILY_COUNT,
            EXPECTED_VARIANTS_PER_FAMILY,
            EXPECTED_GENERATION_COUNT,
        )
        if (
            family_count,
            variants_per_family,
            authorised_generation_count,
        ) != expected_matrix:
            raise ProbeAdapterError(
                "E13 probe matrix must be exactly "
                f"{EXPECTED_FAMILY_COUNT}x{EXPECTED_VARIANTS_PER_FAMILY}="
                f"{EXPECTED_GENERATION_COUNT}"
            )
        if family_count * variants_per_family != authorised_generation_count:
            raise ProbeAdapterError(
                "probe count matrix does not equal authorised generation count"
            )
        if authorised.get("flow_veo_probe_generations") != authorised_generation_count:
            raise ProbeAdapterError(
                "authorization generation count does not match probe plan"
            )
        if lock_scope.get("families") != family_count:
            raise ProbeAdapterError(
                "creative-lock family count does not match probe plan"
            )
        if lock_scope.get("variants_per_family") != variants_per_family:
            raise ProbeAdapterError(
                "creative-lock variant count does not match probe plan"
            )
        if lock_scope.get("authorized_generations") != authorised_generation_count:
            raise ProbeAdapterError(
                "creative-lock generation count does not match probe plan"
            )

        families = plan.get("families")
        if not isinstance(families, list) or len(families) != family_count:
            raise ProbeAdapterError(
                "probe-plan family list does not match family_count"
            )

        derived: list[tuple[dict[str, Any], dict[str, Any], Path, str]] = []
        all_issues: list[str] = []
        for family in families:
            if not isinstance(family, dict):
                raise ProbeAdapterError("every probe family must be an object")
            runtime_pack, receipt, source_path, source_sha, issues = _derive_family(
                repo_root=inputs.repo_root,
                plan=plan,
                context=context,
                originality_binding=originality_binding,
                family=family,
                variants_per_family=variants_per_family,
            )
            derived.append((runtime_pack, receipt, source_path, source_sha))
            all_issues.extend(issues)

        family_ids = [pack["family_id"] for pack, _, _, _ in derived]
        episode_ids = [pack["episode_id"] for pack, _, _, _ in derived]
        shots = [shot for pack, _, _, _ in derived for shot in pack["shots"]]
        shot_ids = [shot["shot_id"] for shot in shots]
        probe_ids = [shot["global_probe_id"] for shot in shots]
        child_seeds = [shot["variant_seed_id"] for shot in shots]
        uniqueness = {
            "family_ids": len(set(family_ids)) == len(family_ids),
            "episode_ids": len(set(episode_ids)) == len(episode_ids),
            "shot_ids": len(set(shot_ids)) == len(shot_ids),
            "global_probe_ids": len(set(probe_ids)) == len(probe_ids),
            "variant_seed_ids": len(set(child_seeds)) == len(child_seeds),
        }
        failed_uniqueness = [name for name, passed in uniqueness.items() if not passed]
        if failed_uniqueness:
            all_issues.append(f"non-unique runtime identifiers: {failed_uniqueness}")
        if len(shots) != authorised_generation_count:
            all_issues.append(
                f"derived {len(shots)} shots, expected {authorised_generation_count}"
            )
        if all_issues:
            raise ProbeAdapterError("; ".join(all_issues))

        # Verify source immutability immediately before the first runtime write.
        for _, _, source_path, source_sha in derived:
            if _sha256_path(source_path) != source_sha:
                raise ProbeAdapterError(
                    f"source changed during adaptation: {source_path}"
                )

        brief_template = {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "candidate_id": context.get("candidate_id"),
            "creative_seed_id": creative_seed_id,
            "originality_gate": originality_binding,
            "purpose": "camera probe only",
            "target_duration_s": 8 * variants_per_family,
            "legal_claims_allowed": False,
            "publication_allowed": False,
        }
        family_summaries: list[dict[str, Any]] = []
        for runtime_pack, receipt, source_path, source_sha in derived:
            family_id = runtime_pack["family_id"]
            family_dir = inputs.output_root / family_id
            family_dir.mkdir(parents=True, exist_ok=True)
            pack_bytes = _json_bytes(runtime_pack)
            brief = {
                **brief_template,
                "episode_id": runtime_pack["episode_id"],
                "family_id": family_id,
            }
            _write_bytes_atomic(family_dir / "shot-pack.json", pack_bytes)
            _write_bytes_atomic(family_dir / "brief.json", _json_bytes(brief))
            _write_bytes_atomic(
                family_dir / "lineage-receipt.json",
                _json_bytes(receipt),
            )
            # Belt after write: receipts must describe the exact bytes on disk,
            # and source files must still be the exact inputs that were hashed.
            if (
                _sha256_path(family_dir / "shot-pack.json")
                != receipt["runtime_pack_sha256"]
            ):
                raise ProbeAdapterError(
                    f"runtime SHA mismatch after write: {family_id}"
                )
            if _sha256_path(source_path) != source_sha:
                raise ProbeAdapterError(
                    f"source changed during runtime write: {source_path}"
                )
            family_summaries.append(
                {
                    "family_id": family_id,
                    "episode_id": runtime_pack["episode_id"],
                    "source_pack_sha256": source_sha,
                    "runtime_pack_sha256": receipt["runtime_pack_sha256"],
                    "shot_count": len(runtime_pack["shots"]),
                }
            )

        verdict.update(
            {
                "verdict": "PASS",
                "checks": {
                    "authorization": {"passed": True, "generation_count": len(shots)},
                    "originality": {
                        "passed": True,
                        "signature_sha256": originality_binding["signature_sha256"],
                        "surface_axes_counted": False,
                    },
                    "source_immutability": {
                        "passed": True,
                        "source_count": len(derived),
                    },
                    "runtime_schema": {"passed": True},
                    "global_uniqueness": {"passed": True, **uniqueness},
                    "identity": {"passed": True, "required_token": "A007"},
                    "f06_visual_only": {"passed": True},
                    "flow_or_publish_side_effects": {"passed": True, "count": 0},
                },
                "errors": [],
                "families": family_summaries,
            }
        )
    except (ProbeAdapterError, OSError) as exc:
        verdict["errors"] = [str(exc)]

    _write_bytes_atomic(verdict_path, _json_bytes(verdict))
    return verdict


def derive_probe_runtime(inputs: Inputs) -> dict[str, Any]:
    """Serialize one fail-closed adapter derivation for an output root."""

    with _exclusive_output_lock(inputs.output_root):
        return _derive_probe_runtime_locked(inputs)


def _default_inputs(args: argparse.Namespace) -> Inputs:
    repo_root = args.repo_root.resolve()
    plan_path = args.plan.resolve()
    episode_root = plan_path.parent.parent
    return Inputs(
        repo_root=repo_root,
        plan_path=plan_path,
        authorization_path=(
            args.authorization or plan_path.parent / "probe-authorization.json"
        ).resolve(),
        context_path=(args.context or episode_root / "context-snapshot.json").resolve(),
        creative_lock_path=(
            args.creative_lock or episode_root / "creative-lock.json"
        ).resolve(),
        output_root=args.output_root.resolve(),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan", required=True, type=Path, help="approved probe-plan.json"
    )
    parser.add_argument(
        "--output-root", required=True, type=Path, help="new runtime pack root"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root used to resolve source_pack references",
    )
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--creative-lock", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    verdict = derive_probe_runtime(_default_inputs(args))
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if verdict["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
