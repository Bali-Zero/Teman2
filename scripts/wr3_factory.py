#!/usr/bin/env python3
"""Thin, deterministic control plane for Zantara Video Factory V3.

The module owns episode state, evidence hashes, reconciliation, dry-run, and
packaging metadata.  It deliberately does not replace the WR3 supervisor,
FlowKit client, spend authority, identity verifier, or assembler.

All commands are local and zero-network except ``canary``.  The canary command
is fail-closed until the existing Flow executor is explicitly bound; merely
reaching ``READY_FOR_SPEND`` can never submit a job.
"""

from __future__ import annotations

import argparse
import copy
import errno
import fcntl
import hashlib
import json
import os
import re
import socket
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence


EPISODE_STATES: tuple[str, ...] = (
    "PROPOSED",
    "TOPIC_APPROVED",
    "GROUNDED",
    "SCRIPT_LOCKED",
    "STORY_LOCKED",
    "WARDROBE_LOCKED",
    "SHOTPACK_LOCKED",
    "PRE_RENDER_PASS",
    "READY_FOR_SPEND",
    "CANARY_SUBMITTED",
    "CANARY_RENDERED",
    "CANARY_QA_PASS",
    "RENDER_AUTHORIZED",
    "RENDERING",
    "RENDERED",
    "ASSEMBLED",
    "FINAL_QA_PASS",
    "YOUTUBE_PACKAGE_READY",
    "HUMAN_APPROVED",
)

FACTORY_MANIFEST_NAME = "factory-manifest.json"
FACTORY_MANIFEST_SCHEMA = "1.0"
LANGUAGE_MANIFEST_SCHEMA = "1.0"
EXPECTED_SEASON_TOPICS = 20
EXPECTED_SEASON_RESERVES = 10
SAFETY_SWITCHES = (
    "ALLOW_FLOW_SPEND",
    "ALLOW_REAL_RENDER",
    "ALLOW_YOUTUBE_UPLOAD",
    "ALLOW_EXTERNAL_PUBLISH",
    "ALLOW_DEPLOY",
)
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_EPISODE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_BCP47 = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
_SUBTITLE_TIMESTAMP = re.compile(
    r"^(?:(?P<hours>\d{2,}):)?(?P<minutes>[0-5]\d):"
    r"(?P<seconds>[0-5]\d)[,.](?P<milliseconds>\d{3})$"
)


class FactoryError(RuntimeError):
    """A Factory command cannot safely complete."""


class FactoryBusyError(FactoryError):
    """Another process owns the episode transition lock."""


@dataclass(frozen=True)
class GateResult:
    passed: bool
    evidence: tuple[dict[str, Any], ...] = ()
    blockers: tuple[str, ...] = ()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FactoryError(f"required file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise FactoryError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FactoryError(f"expected a JSON object in {path}")
    return payload


def _encoded_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Durably replace one JSON object without exposing a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _encoded_json(payload)
    if path.exists() and path.read_bytes() == encoded:
        return

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _episode_lock(episode_dir: Path) -> Iterator[None]:
    episode_dir.mkdir(parents=True, exist_ok=True)
    lock_path = episode_dir / ".factory.lock"
    handle = lock_path.open("a+b")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise FactoryBusyError(
                    f"episode transition already in progress: {episode_dir.name}"
                ) from exc
            raise
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _factory_root(repo_root: Path) -> Path:
    root = repo_root.resolve() / "docs" / "wr3" / "factory"
    state = root / "FACTORY_STATE.md"
    season = root / "editorial" / "season-01.json"
    if not state.is_file():
        raise FactoryError(f"FACTORY_STATE.md is missing: {state}")
    if not season.is_file():
        raise FactoryError(f"Season 01 manifest is missing: {season}")
    return root


def _validate_episode_id(episode_id: str) -> None:
    if not _EPISODE_ID.fullmatch(episode_id):
        raise FactoryError(f"invalid episode id: {episode_id!r}")


def _episode_dir(repo_root: Path, episode_id: str) -> Path:
    _validate_episode_id(episode_id)
    root = _factory_root(repo_root)
    matches: list[Path] = []
    for context_path in sorted((root / "episodes").glob("*/context-snapshot.json")):
        try:
            context = _load_json(context_path)
        except FactoryError:
            continue
        if context.get("episode_id") == episode_id:
            matches.append(context_path.parent)
    if not matches:
        raise FactoryError(f"no context snapshot found for episode {episode_id}")
    if len(matches) > 1:
        raise FactoryError(
            f"multiple episode directories claim {episode_id}: "
            + ", ".join(str(path) for path in matches)
        )
    return matches[0]


def _season(repo_root: Path) -> dict[str, Any]:
    return _load_json(_factory_root(repo_root) / "editorial" / "season-01.json")


def _validate_season_shape(season: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    recommendations = season.get("recommended_topics")
    reserves = season.get("reserve_topics")
    if not isinstance(recommendations, list) or len(recommendations) != EXPECTED_SEASON_TOPICS:
        blockers.append(
            f"season must contain exactly {EXPECTED_SEASON_TOPICS} recommended topics"
        )
    if not isinstance(reserves, list) or len(reserves) != EXPECTED_SEASON_RESERVES:
        blockers.append(
            f"season must contain exactly {EXPECTED_SEASON_RESERVES} reserve topics"
        )
    switches = season.get("safety_switch_values")
    if not isinstance(switches, dict):
        blockers.append("season safety_switch_values must be an object")
    else:
        for name in SAFETY_SWITCHES:
            if switches.get(name) != 0:
                blockers.append(f"season safety switch {name} must default to zero")
    return blockers


def _resolve_beneath(root: Path, path: Path, *, kind: str) -> Path:
    """Resolve ``path`` while rejecting traversal and escaping symlinks."""
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise FactoryError(f"{kind} escapes its allowed directory: {path}") from exc
    return resolved_path


def _episode_evidence(episode_dir: Path, path: Path) -> dict[str, Any]:
    resolved = _resolve_beneath(
        episode_dir,
        path,
        kind="episode evidence",
    )
    relative = resolved.relative_to(episode_dir.resolve())
    if not resolved.is_file():
        raise FactoryError(f"evidence file is missing: {path}")
    return {
        "path": relative.as_posix(),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _initial_manifest(repo_root: Path, episode_dir: Path) -> dict[str, Any]:
    context_path = episode_dir / "context-snapshot.json"
    context = _load_json(context_path)
    episode_id = context.get("episode_id")
    candidate_id = context.get("candidate_id")
    title = context.get("title")
    if not all(isinstance(value, str) and value for value in (episode_id, candidate_id, title)):
        raise FactoryError("context snapshot must contain episode_id, candidate_id, and title")

    root = _factory_root(repo_root)
    season_path = root / "editorial" / "season-01.json"
    state_path = root / "FACTORY_STATE.md"
    season = _load_json(season_path)
    blockers = _validate_season_shape(season)
    if blockers:
        raise FactoryError("; ".join(blockers))

    now = _utc_now()
    proposed_evidence = [_episode_evidence(episode_dir, context_path)]
    return {
        "schema_version": FACTORY_MANIFEST_SCHEMA,
        "episode_id": episode_id,
        "candidate_id": candidate_id,
        "title": title,
        "state": "PROPOSED",
        "created_at_utc": now,
        "updated_at_utc": now,
        "revision": 1,
        "publication_allowed": False,
        "native_audio_canonical": True,
        "safety_switches": dict(season["safety_switch_values"]),
        "lineage": {
            "factory_state": {
                "path": state_path.relative_to(repo_root.resolve()).as_posix(),
                "sha256": _sha256(state_path),
            },
            "season_01": {
                "path": season_path.relative_to(repo_root.resolve()).as_posix(),
                "sha256": _sha256(season_path),
            },
        },
        "evidence": {"PROPOSED": proposed_evidence},
        "transitions": [],
    }


def _state_index(state: str) -> int:
    try:
        return EPISODE_STATES.index(state)
    except ValueError as exc:
        raise FactoryError(f"unknown episode state: {state!r}") from exc


def advance_state(
    manifest: dict[str, Any],
    target_state: str,
    *,
    evidence: Sequence[dict[str, Any]],
) -> bool:
    """Advance exactly one predecessor edge; return False for an idempotent replay."""
    current = manifest.get("state")
    if not isinstance(current, str):
        raise FactoryError("manifest state is missing or invalid")
    current_index = _state_index(current)
    target_index = _state_index(target_state)
    if target_index == current_index:
        return False
    if target_index != current_index + 1:
        raise FactoryError(
            f"cannot skip episode state predecessor: {current} -> {target_state}"
        )
    now = _utc_now()
    manifest["state"] = target_state
    manifest["updated_at_utc"] = now
    manifest["revision"] = int(manifest.get("revision", 0)) + 1
    manifest.setdefault("evidence", {})[target_state] = [dict(item) for item in evidence]
    manifest.setdefault("transitions", []).append(
        {
            "from": current,
            "to": target_state,
            "at_utc": now,
            "evidence": [dict(item) for item in evidence],
        }
    )
    return True


def _claim_ids(brief: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    direct = brief.get("claim_ids")
    if isinstance(direct, list):
        ids.extend(str(value) for value in direct if isinstance(value, str) and value)
    for key in ("regulatory_citations", "key_numbers", "key_facts"):
        values = brief.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict) and isinstance(value.get("claim_id"), str):
                ids.append(value["claim_id"])
    return list(dict.fromkeys(ids))


def _json_gate(
    episode_dir: Path,
    names: Sequence[str],
    predicate: Any,
    blocker: str,
) -> GateResult:
    for name in names:
        path = episode_dir / name
        if not path.is_file():
            continue
        try:
            payload = _load_json(path)
        except FactoryError as exc:
            return GateResult(False, blockers=(str(exc),))
        try:
            accepted = bool(predicate(payload))
        except (KeyError, TypeError, ValueError):
            accepted = False
        if not accepted:
            return GateResult(False, blockers=(blocker,))
        return GateResult(True, evidence=(_episode_evidence(episode_dir, path),))
    return GateResult(False, blockers=(blocker,))


def _topic_approval_gate(episode_dir: Path, manifest: dict[str, Any]) -> GateResult:
    path = episode_dir / "topic-approval.json"
    if not path.is_file():
        return GateResult(False, blockers=("explicit topic-approval.json is missing",))
    approval = _load_json(path)
    valid = (
        approval.get("decision") == "APPROVED"
        and approval.get("episode_id") == manifest.get("episode_id")
        and approval.get("candidate_id") == manifest.get("candidate_id")
        and approval.get("approved_by") == "human"
        and approval.get("publication_allowed") is False
    )
    if not valid:
        return GateResult(
            False,
            blockers=("topic approval is not exact, human, episode-bound, and no-publish",),
        )
    return GateResult(True, evidence=(_episode_evidence(episode_dir, path),))


def _grounded_gate(episode_dir: Path) -> GateResult:
    path = episode_dir / "brief.json"
    if not path.is_file():
        return GateResult(False, blockers=("grounded brief.json is missing",))
    brief = _load_json(path)
    if not _claim_ids(brief):
        return GateResult(False, blockers=("grounded brief has no claim IDs",))
    if brief.get("grounding_status") not in {"GROUNDED", "PASS", "LOCKED"}:
        return GateResult(False, blockers=("grounded brief has no passing grounding_status",))
    return GateResult(True, evidence=(_episode_evidence(episode_dir, path),))


def _script_gate(episode_dir: Path) -> GateResult:
    path = episode_dir / "script.json"
    if not path.is_file():
        return GateResult(False, blockers=("frozen script.json is missing",))
    script = _load_json(path)
    if script.get("status") not in {"FROZEN", "LOCKED"}:
        return GateResult(False, blockers=("script status is not FROZEN or LOCKED",))
    if not _claim_ids(script):
        return GateResult(False, blockers=("script has no claim bindings",))
    return GateResult(True, evidence=(_episode_evidence(episode_dir, path),))


def _story_gate(episode_dir: Path) -> GateResult:
    return _json_gate(
        episode_dir,
        ("story-lock.json", "beat-sheet.json"),
        lambda value: value.get("status") in {"LOCKED", "PASS"}
        and isinstance(value.get("beats"), list)
        and bool(value["beats"]),
        "locked story/beat sheet is missing or incomplete",
    )


def _wardrobe_gate(episode_dir: Path) -> GateResult:
    required_views = {"front", "three_quarter", "full_body", "fabric_detail"}
    return _json_gate(
        episode_dir,
        ("wardrobe-reference-spec.json",),
        lambda value: value.get("status") in {"LOCKED", "PASS"}
        and required_views.issubset(set(value.get("views") or []))
        and value.get("identity_continuity") is True,
        "wardrobe reference specification is missing or incomplete",
    )


def _shotpack_gate(episode_dir: Path) -> GateResult:
    path = episode_dir / "shot-pack.json"
    if not path.is_file():
        return GateResult(False, blockers=("locked shot-pack.json is missing",))
    shot_pack = _load_json(path)
    shots = shot_pack.get("shots")
    if shot_pack.get("status") not in {"LOCKED", "PASS"} or not isinstance(shots, list) or not shots:
        return GateResult(False, blockers=("shot pack is not locked or has no shots",))
    identifiers: list[Any] = []
    for shot in shots:
        if not isinstance(shot, dict):
            return GateResult(False, blockers=("shot pack contains a non-object shot",))
        identifier = shot.get("shot_id", shot.get("index"))
        if identifier is None:
            return GateResult(False, blockers=("shot pack contains a shot without an ID",))
        if shot.get("shot_class") not in {"SYNC_FOREGROUND", "PURE_BROLL", "TRANSITION"}:
            return GateResult(False, blockers=("shot pack contains an invalid shot_class",))
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        return GateResult(False, blockers=("shot pack contains duplicate shot IDs",))
    return GateResult(True, evidence=(_episode_evidence(episode_dir, path),))


def _pre_render_gate(episode_dir: Path) -> GateResult:
    shot_pack = episode_dir / "shot-pack.json"
    expected = _sha256(shot_pack) if shot_pack.is_file() else None

    def accepted(value: dict[str, Any]) -> bool:
        bound = value.get("shot_pack_sha256")
        return value.get("verdict") == "PASS" and bound == expected

    return _json_gate(
        episode_dir,
        ("pre-render-gate.json", "pre-render-verdict.json"),
        accepted,
        "pre-render PASS bound to the current shot-pack hash is missing",
    )


def _readiness_gate(manifest: dict[str, Any]) -> GateResult:
    switches = manifest.get("safety_switches")
    if not isinstance(switches, dict):
        return GateResult(False, blockers=("safety switches are missing",))
    nonzero = [name for name in SAFETY_SWITCHES if switches.get(name) != 0]
    if nonzero:
        return GateResult(
            False,
            blockers=("non-spending readiness requires zero switches: " + ", ".join(nonzero),),
        )
    return GateResult(
        True,
        evidence=(
            {
                "kind": "deterministic_readiness",
                "flow_jobs_submitted": 0,
                "flow_credits_consumed": 0,
                "publication_allowed": False,
            },
        ),
    )


def _canary_submitted_gate(episode_dir: Path, manifest: dict[str, Any]) -> GateResult:
    return _json_gate(
        episode_dir,
        ("canary-submission-receipt.json",),
        lambda value: value.get("status") == "SUBMITTED"
        and value.get("episode_id") == manifest.get("episode_id")
        and isinstance(value.get("workflow_id"), str),
        "exact canary submission receipt is missing",
    )


def _canary_rendered_gate(episode_dir: Path) -> GateResult:
    result_path = episode_dir / "canary-result.json"
    if not result_path.is_file():
        return GateResult(False, blockers=("canary result is missing",))
    result = _load_json(result_path)
    relative = result.get("clip_path")
    expected_hash = result.get("clip_sha256")
    if not isinstance(relative, str) or not isinstance(expected_hash, str):
        return GateResult(False, blockers=("canary result has no clip path/hash",))
    clip = _resolve_beneath(
        episode_dir,
        episode_dir / relative,
        kind="canary clip",
    )
    if not clip.is_file() or _sha256(clip) != expected_hash:
        return GateResult(False, blockers=("canary clip is missing or hash-mismatched",))
    return GateResult(
        True,
        evidence=(
            _episode_evidence(episode_dir, result_path),
            _episode_evidence(episode_dir, clip),
        ),
    )


def _gate_for_state(
    episode_dir: Path,
    manifest: dict[str, Any],
    target_state: str,
) -> GateResult:
    if target_state == "TOPIC_APPROVED":
        return _topic_approval_gate(episode_dir, manifest)
    if target_state == "GROUNDED":
        return _grounded_gate(episode_dir)
    if target_state == "SCRIPT_LOCKED":
        return _script_gate(episode_dir)
    if target_state == "STORY_LOCKED":
        return _story_gate(episode_dir)
    if target_state == "WARDROBE_LOCKED":
        return _wardrobe_gate(episode_dir)
    if target_state == "SHOTPACK_LOCKED":
        return _shotpack_gate(episode_dir)
    if target_state == "PRE_RENDER_PASS":
        return _pre_render_gate(episode_dir)
    if target_state == "READY_FOR_SPEND":
        return _readiness_gate(manifest)
    if target_state == "CANARY_SUBMITTED":
        return _canary_submitted_gate(episode_dir, manifest)
    if target_state == "CANARY_RENDERED":
        return _canary_rendered_gate(episode_dir)
    if target_state == "CANARY_QA_PASS":
        return _json_gate(
            episode_dir,
            ("canary-qa.json",),
            lambda value: value.get("verdict") == "PASS"
            and value.get("identity_status") == "PASS"
            and value.get("audio_status") == "PASS"
            and value.get("technical_status") == "PASS",
            "canary identity/audio/technical QA PASS is missing",
        )
    if target_state == "RENDER_AUTHORIZED":
        return _json_gate(
            episode_dir,
            ("render-authorization.json",),
            lambda value: value.get("type") == "EPISODE_RENDER"
            and value.get("episode_id") == manifest.get("episode_id")
            and isinstance(value.get("max_credits"), int)
            and value["max_credits"] > 0,
            "separate full-render authorization is missing",
        )
    if target_state == "RENDERING":
        return _json_gate(
            episode_dir,
            ("render-report.json",),
            # A completed report is also proof that RENDERING happened.  This
            # lets an interrupted supervisor resume through both consecutive
            # edges without inventing or skipping a state.
            lambda value: value.get("status")
            in {"incomplete", "PARTIAL", "RENDERING", "OK"},
            "render-in-progress evidence is missing",
        )
    if target_state == "RENDERED":
        return _json_gate(
            episode_dir,
            ("render-report.json",),
            lambda value: value.get("status") == "OK"
            and isinstance(value.get("rendered"), list)
            and bool(value["rendered"])
            and not value.get("failed"),
            "complete render report is missing",
        )
    if target_state == "ASSEMBLED":
        master = episode_dir / "master.mp4"
        assembled = episode_dir / "episode_manifest.json"
        if not master.is_file() or not assembled.is_file():
            return GateResult(False, blockers=("master.mp4 and episode_manifest.json are required",))
        return GateResult(
            True,
            evidence=(
                _episode_evidence(episode_dir, master),
                _episode_evidence(episode_dir, assembled),
            ),
        )
    if target_state == "FINAL_QA_PASS":
        return _json_gate(
            episode_dir,
            ("final-qa.json",),
            lambda value: value.get("verdict") in {"PASS", "PASS-WITH-NOTES"},
            "final critic PASS is missing",
        )
    if target_state == "YOUTUBE_PACKAGE_READY":
        return _json_gate(
            episode_dir,
            ("metadata/language_manifest.json",),
            lambda value: value.get("status") == "READY"
            and value.get("youtube_upload_status") == "DISABLED",
            "validated no-upload language package is missing",
        )
    if target_state == "HUMAN_APPROVED":
        return _json_gate(
            episode_dir,
            ("human-approval.json",),
            lambda value: value.get("decision") == "APPROVED"
            and value.get("episode_id") == manifest.get("episode_id")
            and value.get("approved_by") == "human",
            "explicit human approval is missing",
        )
    raise FactoryError(f"no gate is defined for state {target_state}")


def _next_state(state: str) -> str | None:
    index = _state_index(state)
    if index + 1 >= len(EPISODE_STATES):
        return None
    return EPISODE_STATES[index + 1]


def _reconcile(episode_dir: Path, manifest: dict[str, Any]) -> tuple[bool, GateResult | None]:
    changed = False
    blocking_gate: GateResult | None = None
    while True:
        target = _next_state(str(manifest["state"]))
        if target is None:
            break
        gate = _gate_for_state(episode_dir, manifest, target)
        if not gate.passed:
            blocking_gate = gate
            break
        changed = advance_state(manifest, target, evidence=gate.evidence) or changed
    return changed, blocking_gate


def _load_or_build_manifest(repo_root: Path, episode_dir: Path) -> tuple[dict[str, Any], bool]:
    path = episode_dir / FACTORY_MANIFEST_NAME
    if not path.is_file():
        return _initial_manifest(repo_root, episode_dir), True
    manifest = _load_json(path)
    if manifest.get("schema_version") != FACTORY_MANIFEST_SCHEMA:
        raise FactoryError(
            f"factory manifest schema mismatch: {manifest.get('schema_version')!r}"
        )
    if manifest.get("episode_id") != _load_json(episode_dir / "context-snapshot.json").get("episode_id"):
        raise FactoryError("factory manifest episode_id does not match context snapshot")
    _state_index(str(manifest.get("state")))
    drift = _manifest_drift(repo_root, episode_dir, manifest)
    if drift:
        paths = ", ".join(str(item["path"]) for item in drift)
        raise FactoryError(f"evidence drift blocks reconciliation: {paths}")
    return manifest, False


def prepare_episode(repo_root: Path, episode_id: str) -> dict[str, Any]:
    """Persist the highest consecutive state supported by current evidence."""
    repo_root = repo_root.resolve()
    episode_dir = _episode_dir(repo_root, episode_id)
    manifest_path = episode_dir / FACTORY_MANIFEST_NAME
    with _episode_lock(episode_dir):
        manifest, created = _load_or_build_manifest(repo_root, episode_dir)
        changed, blocker = _reconcile(episode_dir, manifest)
        if created or changed:
            _atomic_write_json(manifest_path, manifest)
    return {
        "command": "prepare",
        "episode_id": episode_id,
        "state": manifest["state"],
        "next_state": _next_state(str(manifest["state"])),
        "changed": created or changed,
        "manifest_path": str(manifest_path),
        "blockers": list(blocker.blockers) if blocker is not None else [],
        "flow_jobs_submitted": 0,
        "flow_credits_consumed": 0,
    }


def dry_run_episode(repo_root: Path, episode_id: str) -> dict[str, Any]:
    """Simulate reconciliation without writes, sockets, or spend authority calls."""
    repo_root = repo_root.resolve()
    episode_dir = _episode_dir(repo_root, episode_id)
    manifest, _ = _load_or_build_manifest(repo_root, episode_dir)
    simulated = copy.deepcopy(manifest)
    changed, blocker = _reconcile(episode_dir, simulated)
    blockers = list(blocker.blockers) if blocker is not None else []
    state = str(simulated["state"])
    return {
        "command": "dry-run",
        "episode_id": episode_id,
        "status": "PASS" if not blockers else "BLOCKED",
        "current_state": manifest["state"],
        "would_advance": changed,
        "would_advance_to": state,
        "next_state": _next_state(state),
        "blockers": blockers,
        "flow_jobs_submitted": 0,
        "flow_credits_consumed": 0,
        "writes_performed": 0,
        "network_calls": 0,
    }


def _tracked_episode_evidence(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    tracked: list[dict[str, Any]] = []
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        return tracked
    for state in EPISODE_STATES:
        entries = evidence.get(state)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                tracked.append(entry)
    return tracked


def _manifest_drift(
    repo_root: Path,
    episode_dir: Path,
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    drift: list[dict[str, str]] = []
    for evidence in _tracked_episode_evidence(manifest):
        relative = str(evidence["path"])
        path = _resolve_beneath(
            episode_dir,
            episode_dir / relative,
            kind="episode evidence",
        )
        expected = evidence.get("sha256")
        if not path.is_file():
            drift.append({"path": relative, "reason": "missing"})
        elif _sha256(path) != expected:
            drift.append({"path": relative, "reason": "sha256_mismatch"})

    lineage = manifest.get("lineage")
    if isinstance(lineage, dict):
        for label, entry in lineage.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                drift.append({"path": str(label), "reason": "invalid_lineage"})
                continue
            relative = str(entry["path"])
            path = _resolve_beneath(
                repo_root,
                repo_root / relative,
                kind="lineage evidence",
            )
            if not path.is_file():
                drift.append({"path": relative, "reason": "missing"})
            elif _sha256(path) != entry.get("sha256"):
                drift.append({"path": relative, "reason": "sha256_mismatch"})
    return drift


def validate_episode(repo_root: Path, episode_id: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    episode_dir = _episode_dir(repo_root, episode_id)
    manifest_path = episode_dir / FACTORY_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FactoryError(f"episode has not been prepared: {episode_id}")
    manifest = _load_json(manifest_path)
    _state_index(str(manifest.get("state")))
    drift = _manifest_drift(repo_root, episode_dir, manifest)
    tracked_paths: set[str] = set()
    for evidence in _tracked_episode_evidence(manifest):
        relative = str(evidence["path"])
        tracked_paths.add(relative)

    untracked = [
        path.relative_to(episode_dir).as_posix()
        for path in sorted((episode_dir / "clips").glob("*.mp4"))
        if path.relative_to(episode_dir).as_posix() not in tracked_paths
    ]
    next_state = _next_state(str(manifest["state"]))
    next_gate = _gate_for_state(episode_dir, manifest, next_state) if next_state else None
    return {
        "command": "validate",
        "episode_id": episode_id,
        "state": manifest["state"],
        "next_state": next_state,
        "valid": not drift and not untracked,
        "drift": drift,
        "untracked_artifacts": untracked,
        "next_gate_blockers": list(next_gate.blockers) if next_gate and not next_gate.passed else [],
        "flow_jobs_submitted": 0,
        "flow_credits_consumed": 0,
    }


def validate_canary_authorization(
    manifest: dict[str, Any],
    authorization: dict[str, Any],
    *,
    requested_max_credits: int,
    current_shot_pack_sha256: str,
) -> dict[str, Any]:
    if manifest.get("state") != "READY_FOR_SPEND":
        raise FactoryError("canary requires the exact READY_FOR_SPEND state")
    if authorization.get("type") != "FLOW_CANARY":
        raise FactoryError("authorization type must be FLOW_CANARY")
    if authorization.get("episode_id") != manifest.get("episode_id"):
        raise FactoryError("canary authorization episode_id mismatch")
    if authorization.get("authorized_by") != "human":
        raise FactoryError("canary authorization must be human")
    maximum = authorization.get("max_credits")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise FactoryError("canary authorization max_credits must be a positive integer")
    if maximum != requested_max_credits:
        raise FactoryError("requested credit cap differs from the exact authorization cap")
    if authorization.get("clip_count") != 1:
        raise FactoryError("canary authorization must be limited to exactly one clip")
    shot_id = authorization.get("shot_id")
    if not isinstance(shot_id, str) or not shot_id:
        raise FactoryError("canary authorization must name exactly one shot_id")
    exact_text = (
        f"AUTHORIZE FLOW CANARY: {manifest['episode_id']} "
        f"MAX_CREDITS: {maximum}"
    )
    if authorization.get("authorization_text") != exact_text:
        raise FactoryError(f"canary authorization text must be exactly: {exact_text}")
    if authorization.get("shot_pack_sha256") != current_shot_pack_sha256:
        raise FactoryError("canary authorization is stale for the current shot pack")
    return {
        "authorized": True,
        "episode_id": manifest["episode_id"],
        "max_credits": maximum,
        "clip_count": 1,
        "shot_id": shot_id,
        "shot_pack_sha256": current_shot_pack_sha256,
    }


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def canary_episode(repo_root: Path, episode_id: str) -> dict[str, Any]:
    """Validate the canary gate and stop before an unbound executor can spend."""
    repo_root = repo_root.resolve()
    episode_dir = _episode_dir(repo_root, episode_id)
    manifest_path = episode_dir / FACTORY_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FactoryError(f"episode has not been prepared: {episode_id}")
    manifest = _load_json(manifest_path)
    authorization_path = episode_dir / "canary-authorization.json"
    authorization = _load_json(authorization_path)
    shot_pack = episode_dir / "shot-pack.json"
    if not shot_pack.is_file():
        raise FactoryError("canary requires shot-pack.json")
    shot_pack_payload = _load_json(shot_pack)
    maximum = authorization.get("max_credits")
    if isinstance(maximum, bool) or not isinstance(maximum, int):
        raise FactoryError("canary authorization max_credits is invalid")
    validated = validate_canary_authorization(
        manifest,
        authorization,
        requested_max_credits=maximum,
        current_shot_pack_sha256=_sha256(shot_pack),
    )
    shot_ids = {
        shot.get("shot_id", shot.get("index"))
        for shot in shot_pack_payload.get("shots", [])
        if isinstance(shot, dict)
    }
    if validated["shot_id"] not in shot_ids:
        raise FactoryError("authorized canary shot_id is absent from the current shot pack")
    if not _env_enabled("ALLOW_FLOW_SPEND") or not _env_enabled("ALLOW_REAL_RENDER"):
        raise FactoryError(
            "canary is authorized on paper but ALLOW_FLOW_SPEND=1 and "
            "ALLOW_REAL_RENDER=1 are both required"
        )
    if socket.gethostname() == "Air-M5":
        raise FactoryError("real Flow canary execution must run on Pro, not Air-M5")

    # No production adapter is bound yet.  Stop before importing or calling the
    # spend authority: a rejected command must not consume an authorization or
    # append a misleading spend-decision record.
    return {
        **validated,
        "status": "BLOCKED",
        "reason": "CANARY_EXECUTOR_NOT_BOUND",
        "flow_jobs_submitted": 0,
        "flow_credits_consumed": 0,
        "message": (
            "The control-plane gates passed, but no one-shot production adapter "
            "is bound. Refusing to call the whole-episode renderer."
        ),
    }


def _subtitle_milliseconds(value: str) -> int | None:
    match = _SUBTITLE_TIMESTAMP.fullmatch(value.strip())
    if match is None:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    milliseconds = int(match.group("milliseconds"))
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + milliseconds


def _subtitle_timing_errors(path: Path) -> list[str]:
    """Validate SRT/VTT cue order without rendering or changing the sidecar."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        return [f"{path.name}: cannot read subtitle sidecar: {exc}"]

    spans: list[tuple[int, int]] = []
    errors: list[str] = []
    for line in lines:
        if "-->" not in line:
            continue
        start_text, end_with_settings = line.split("-->", 1)
        end_parts = end_with_settings.strip().split()
        start = _subtitle_milliseconds(start_text.strip())
        end = _subtitle_milliseconds(end_parts[0]) if end_parts else None
        cue_number = len(spans) + 1
        if start is None or end is None:
            errors.append(f"{path.name}: cue {cue_number} has an invalid timestamp")
            continue
        if start >= end:
            errors.append(f"{path.name}: cue {cue_number} must end after it starts")
        if spans and start < spans[-1][1]:
            errors.append(
                f"{path.name}: cue {cue_number} overlaps cue {cue_number - 1}"
            )
        spans.append((start, end))
    if not spans:
        errors.append(f"{path.name}: no valid subtitle cues found")
    return errors


def _canonical_script_contract(
    script_path: Path,
) -> tuple[str, dict[str, Any] | None, list[str], list[str]]:
    if not script_path.is_file():
        return "MISSING", None, [], ["frozen English script.json is missing"]
    source_script_sha256 = _sha256(script_path)
    try:
        source_script = _load_json(script_path)
    except FactoryError as exc:
        return source_script_sha256, None, [], [str(exc)]

    errors: list[str] = []
    if source_script.get("status") not in {"FROZEN", "LOCKED"}:
        errors.append("English script status is not FROZEN or LOCKED")
    if source_script.get("language") != "en":
        errors.append("English script language must be en")
    claim_ids = _claim_ids(source_script)
    if not claim_ids:
        errors.append("English script has no claim bindings")
    return source_script_sha256, source_script, claim_ids, errors


def _language_entry(
    episode_dir: Path,
    language: str,
    source_script_sha256: str,
    source_claim_ids: Sequence[str],
    source_script_errors: Sequence[str],
) -> dict[str, Any]:
    if language == "en":
        script = episode_dir / "script.json"
        srt = episode_dir / "captions_en.srt"
        vtt = episode_dir / "captions_en.vtt"
        master = episode_dir / "master.mp4"
        required = (script, srt, vtt, master)
        errors = list(source_script_errors)
        errors.extend(
            f"required English package asset is missing: {path.name}"
            for path in required
            if not path.is_file()
        )
        for captions in (srt, vtt):
            if captions.is_file():
                errors.extend(_subtitle_timing_errors(captions))
        ready = not errors
        return {
            "language": "en",
            "multilingual_level": "CANONICAL",
            "status": "READY" if ready else "BLOCKED",
            "source_script_sha256": source_script_sha256,
            "source_script_hash": source_script_sha256,
            "translation_hash": source_script_sha256,
            "claim_ids": list(source_claim_ids),
            "validation_errors": errors,
            "artifact_sha256": {
                path.name: _sha256(path) for path in required if path.is_file()
            },
            "glossary_version": None,
            "voice_asset": "master.mp4" if master.is_file() else None,
            "voice_approval_status": "CANONICAL_NATIVE" if ready else "BLOCKED",
            "full_mix_asset": "master.mp4" if master.is_file() else None,
            "captions_srt": "captions_en.srt" if srt.is_file() else None,
            "captions_vtt": "captions_en.vtt" if vtt.is_file() else None,
            "localized_title": None,
            "localized_description": None,
            "localized_thumbnail": None,
            "duration": None,
            "duration_drift": 0 if ready else None,
            "duration_qa_status": "SOURCE" if ready else "BLOCKED",
            "lip_sync_claim": "NATIVE_CANONICAL" if ready else "BLOCKED",
            "semantic_qa_status": "SOURCE" if ready else "BLOCKED",
            "terminology_qa_status": "SOURCE" if ready else "BLOCKED",
            "human_review_status": "REQUIRED",
            "youtube_upload_status": "DISABLED",
        }

    language_dir = episode_dir / "languages" / language
    preferred_translation = language_dir / f"script_{language}.json"
    alternate_translation = language_dir / "translated_script.json"
    translation = (
        preferred_translation
        if preferred_translation.is_file() or not alternate_translation.is_file()
        else alternate_translation
    )
    srt = language_dir / f"captions_{language}.srt"
    vtt = language_dir / f"captions_{language}.vtt"
    metadata = language_dir / f"metadata_{language}.json"
    required = (translation, srt, vtt, metadata)
    errors = list(source_script_errors)
    errors.extend(
        f"required {language} package asset is missing: {path.name}"
        for path in required
        if not path.is_file()
    )
    translation_payload: dict[str, Any] = {}
    metadata_payload: dict[str, Any] = {}
    if translation.is_file():
        try:
            translation_payload = _load_json(translation)
        except FactoryError as exc:
            errors.append(str(exc))
        else:
            if translation_payload.get("status") not in {"FROZEN", "LOCKED"}:
                errors.append("translation status is not FROZEN or LOCKED")
            if translation_payload.get("language") != language:
                errors.append(f"translation language must be {language}")
            if translation_payload.get("source_script_sha256") != source_script_sha256:
                errors.append("translation is not bound to the frozen English script hash")
            translated_claim_ids = _claim_ids(translation_payload)
            if set(translated_claim_ids) != set(source_claim_ids):
                errors.append(
                    "translation claim IDs do not exactly match the frozen English script"
                )
    if metadata.is_file():
        try:
            metadata_payload = _load_json(metadata)
        except FactoryError as exc:
            errors.append(str(exc))
        else:
            for key in ("localized_title", "localized_description"):
                if not isinstance(metadata_payload.get(key), str) or not metadata_payload[key]:
                    errors.append(f"localized metadata is missing {key}")
            for key in ("semantic_qa_status", "terminology_qa_status"):
                if metadata_payload.get(key) != "PASS":
                    errors.append(f"localized metadata {key} is not PASS")

    multilingual_level = metadata_payload.get("multilingual_level", 1)
    if (
        isinstance(multilingual_level, bool)
        or not isinstance(multilingual_level, int)
        or multilingual_level not in {1, 2, 3}
    ):
        raise FactoryError(
            f"{language} multilingual_level must be exactly 1, 2, or 3"
        )

    voice_asset: Path | None = None
    full_mix_asset: Path | None = None
    voice_approval_status = "YOUTUBE_AUTODUB_NOT_GENERATED"
    human_review_status = "REQUIRED"
    duration = metadata_payload.get("duration")
    duration_drift = metadata_payload.get("duration_drift")
    duration_qa_status = metadata_payload.get("duration_qa_status", "NOT_RUN")
    lip_sync_claim = metadata_payload.get("lip_sync_claim", "NOT_APPLICABLE")
    extra_artifacts: list[Path] = []

    if multilingual_level == 2:
        voice_asset = language_dir / f"dialogue_{language}.wav"
        full_mix_asset = language_dir / f"mix_{language}.wav"
        extra_artifacts.extend((voice_asset, full_mix_asset))
        for path in (voice_asset, full_mix_asset):
            if not path.is_file():
                errors.append(f"Level 2 required audio asset is missing: {path.name}")
        voice_approval_status = str(
            metadata_payload.get("voice_approval_status", "BLOCKED")
        )
        human_review_status = str(
            metadata_payload.get("human_review_status", "REQUIRED")
        )
        if voice_approval_status != "APPROVED":
            errors.append("Level 2 voice_approval_status is not APPROVED")
        if human_review_status != "APPROVED":
            errors.append("Level 2 human_review_status is not APPROVED")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or duration <= 0
        ):
            errors.append("Level 2 duration must be a positive number")
        if isinstance(duration_drift, bool) or not isinstance(
            duration_drift, (int, float)
        ):
            errors.append("Level 2 duration_drift must be numeric")
        if duration_qa_status != "PASS":
            errors.append("Level 2 duration_qa_status is not PASS")
        if lip_sync_claim == "PERFECT":
            errors.append("Level 2 must not claim perfect lip sync")

    if multilingual_level == 3:
        render_manifest_path = language_dir / "level3-render-manifest.json"
        extra_artifacts.append(render_manifest_path)
        render_manifest: dict[str, Any] = {}
        if not render_manifest_path.is_file():
            errors.append("Level 3 render manifest is missing")
        else:
            try:
                render_manifest = _load_json(render_manifest_path)
            except FactoryError as exc:
                errors.append(str(exc))

        localized_video_value = render_manifest.get("localized_video")
        localized_video: Path | None = None
        if isinstance(localized_video_value, str):
            try:
                localized_video = _resolve_beneath(
                    episode_dir,
                    episode_dir / localized_video_value,
                    kind="Level 3 localized video",
                )
            except FactoryError as exc:
                errors.append(str(exc))
        else:
            errors.append("Level 3 localized_video is missing")
        if localized_video is not None:
            full_mix_asset = localized_video
            extra_artifacts.append(localized_video)
            if not localized_video.is_file():
                errors.append("Level 3 localized video is missing")
            elif _sha256(localized_video) != render_manifest.get(
                "localized_video_sha256"
            ):
                errors.append("Level 3 localized video hash does not match")

        if render_manifest.get("status") != "PASS":
            errors.append("Level 3 render status is not PASS")
        if render_manifest.get("language") != language:
            errors.append(f"Level 3 render language must be {language}")
        if render_manifest.get("source_script_sha256") != source_script_sha256:
            errors.append("Level 3 render is not bound to the frozen English script hash")
        flow_authorization_sha256 = render_manifest.get("flow_authorization_sha256")
        if not isinstance(flow_authorization_sha256, str) or not re.fullmatch(
            r"[a-f0-9]{64}", flow_authorization_sha256
        ):
            errors.append("Level 3 Flow authorization hash is invalid")
        regenerated = render_manifest.get("regenerated_shot_classes")
        if not isinstance(regenerated, list) or set(regenerated) != {
            "SYNC_FOREGROUND"
        }:
            errors.append("Level 3 may regenerate only SYNC_FOREGROUND shots")
        reused = render_manifest.get("reused_shot_classes")
        if (
            not isinstance(reused, list)
            or not reused
            or not set(reused).issubset({"PURE_BROLL", "TRANSITION"})
        ):
            errors.append("Level 3 may reuse only PURE_BROLL and TRANSITION shots")
        for qa_field in (
            "canary_qa_status",
            "identity_qa_status",
            "voice_qa_status",
            "pronunciation_qa_status",
            "audio_qa_status",
            "lip_sync_qa_status",
            "native_speaker_review_status",
        ):
            if render_manifest.get(qa_field) != "PASS":
                errors.append(f"Level 3 {qa_field} is not PASS")
        voice_approval_status = "NATIVE_FLOW_QA_PASS"
        human_review_status = (
            "APPROVED"
            if render_manifest.get("native_speaker_review_status") == "PASS"
            else "REQUIRED"
        )
        duration_qa_status = str(
            render_manifest.get("duration_qa_status", "NOT_APPLICABLE")
        )
        lip_sync_claim = "NATIVE_LANGUAGE_QA_PASS"

    for captions in (srt, vtt):
        if captions.is_file():
            errors.extend(_subtitle_timing_errors(captions))

    ready = not errors
    translation_hash = _sha256(translation) if translation.is_file() else None
    artifacts = (*required, *extra_artifacts)
    return {
        "language": language,
        "multilingual_level": multilingual_level,
        "status": "READY" if ready else "BLOCKED",
        "source_script_sha256": source_script_sha256,
        "source_script_hash": source_script_sha256,
        "translation_hash": translation_hash,
        "claim_ids": _claim_ids(translation_payload),
        "validation_errors": errors,
        "artifact_sha256": {
            path.relative_to(episode_dir).as_posix(): _sha256(path)
            for path in artifacts
            if path.is_file()
        },
        "glossary_version": metadata_payload.get("glossary_version"),
        "voice_asset": (
            voice_asset.relative_to(episode_dir).as_posix()
            if voice_asset is not None and voice_asset.is_file()
            else None
        ),
        "voice_approval_status": voice_approval_status,
        "full_mix_asset": (
            full_mix_asset.relative_to(episode_dir).as_posix()
            if full_mix_asset is not None and full_mix_asset.is_file()
            else None
        ),
        "captions_srt": str(srt.relative_to(episode_dir)) if srt.is_file() else None,
        "captions_vtt": str(vtt.relative_to(episode_dir)) if vtt.is_file() else None,
        "localized_title": metadata_payload.get("localized_title"),
        "localized_description": metadata_payload.get("localized_description"),
        "localized_thumbnail": metadata_payload.get("localized_thumbnail"),
        "duration": duration,
        "duration_drift": duration_drift,
        "duration_qa_status": duration_qa_status,
        "lip_sync_claim": lip_sync_claim,
        "semantic_qa_status": metadata_payload.get("semantic_qa_status", "BLOCKED"),
        "terminology_qa_status": metadata_payload.get(
            "terminology_qa_status", "BLOCKED"
        ),
        "human_review_status": human_review_status,
        "youtube_upload_status": "DISABLED",
    }


def package_episode(
    repo_root: Path,
    episode_id: str,
    *,
    languages: Sequence[str],
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    episode_dir = _episode_dir(repo_root, episode_id)
    manifest_path = episode_dir / FACTORY_MANIFEST_NAME
    normalized_languages = tuple(dict.fromkeys(language.strip() for language in languages))
    if not normalized_languages or "en" not in normalized_languages:
        raise FactoryError("package languages must include canonical English (en)")
    invalid = [language for language in normalized_languages if not _BCP47.fullmatch(language)]
    if invalid:
        raise FactoryError("invalid BCP 47 language tag(s): " + ", ".join(invalid))

    language_manifest_path = episode_dir / "metadata" / "language_manifest.json"
    master_path = episode_dir / "master.mp4"
    with _episode_lock(episode_dir):
        manifest, _created = _load_or_build_manifest(repo_root, episode_dir)
        if _state_index(str(manifest.get("state"))) < _state_index("FINAL_QA_PASS"):
            raise FactoryError("package requires FINAL_QA_PASS or a later state")
        master_before = _sha256(master_path) if master_path.is_file() else None
        script = episode_dir / "script.json"
        (
            source_script_sha256,
            _source_script,
            source_claim_ids,
            source_script_errors,
        ) = _canonical_script_contract(script)
        entries = {
            language: _language_entry(
                episode_dir,
                language,
                source_script_sha256,
                source_claim_ids,
                source_script_errors,
            )
            for language in normalized_languages
        }
        ready = all(entry["status"] == "READY" for entry in entries.values())
        payload: dict[str, Any] = {
            "schema_version": LANGUAGE_MANIFEST_SCHEMA,
            "episode_id": episode_id,
            "status": "READY" if ready else "BLOCKED",
            "canonical_language": "en",
            "source_script_sha256": source_script_sha256,
            "source_script_hash": source_script_sha256,
            "claim_ids": source_claim_ids,
            "youtube_upload_status": "DISABLED",
            "languages": entries,
        }
        encoded = _encoded_json(payload)
        package_is_locked = _state_index(str(manifest["state"])) >= _state_index(
            "YOUTUBE_PACKAGE_READY"
        )
        if package_is_locked and (
            not language_manifest_path.is_file()
            or language_manifest_path.read_bytes() != encoded
        ):
            raise FactoryError(
                "cannot replace a locked language package; create an approved revision"
            )
        _atomic_write_json(language_manifest_path, payload)

        if ready and manifest.get("state") == "FINAL_QA_PASS":
            advance_state(
                manifest,
                "YOUTUBE_PACKAGE_READY",
                evidence=(_episode_evidence(episode_dir, language_manifest_path),),
            )
            _atomic_write_json(manifest_path, manifest)
        master_after = _sha256(master_path) if master_path.is_file() else None
        if master_after != master_before:
            raise FactoryError("canonical English master changed during packaging")
    return {
        "command": "package",
        "episode_id": episode_id,
        "status": payload["status"],
        "state": manifest["state"],
        "languages": entries,
        "language_manifest_path": str(language_manifest_path),
        "youtube_upload_status": "DISABLED",
        "english_master_modified": False,
    }


def factory_plan(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    root = _factory_root(repo_root)
    season = _season(repo_root)
    blockers = _validate_season_shape(season)
    episodes: list[dict[str, Any]] = []
    for context_path in sorted((root / "episodes").glob("*/context-snapshot.json")):
        context = _load_json(context_path)
        manifest_path = context_path.parent / FACTORY_MANIFEST_NAME
        state = _load_json(manifest_path).get("state") if manifest_path.is_file() else "UNPREPARED"
        episodes.append(
            {
                "episode_id": context.get("episode_id"),
                "candidate_id": context.get("candidate_id"),
                "title": context.get("title"),
                "state": state,
            }
        )
    return {
        "command": "plan",
        "status": str(season.get("status") or "UNSPECIFIED") if not blockers else "BLOCKED",
        "season_status": season.get("status"),
        "recommended_topics": len(season.get("recommended_topics") or []),
        "reserve_topics": len(season.get("reserve_topics") or []),
        "approved_topic_ids": list(season.get("approved_topic_ids") or []),
        "episodes": episodes,
        "blockers": blockers,
        "safety_switches": season.get("safety_switch_values"),
    }


def factory_status(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    root = _factory_root(repo_root)
    state_path = root / "FACTORY_STATE.md"
    episodes: list[dict[str, Any]] = []
    for manifest_path in sorted((root / "episodes").glob(f"*/{FACTORY_MANIFEST_NAME}")):
        manifest = _load_json(manifest_path)
        episodes.append(
            {
                "episode_id": manifest.get("episode_id"),
                "state": manifest.get("state"),
                "next_state": _next_state(str(manifest.get("state"))),
                "manifest_path": str(manifest_path),
            }
        )
    return {
        "command": "status",
        "factory_state_path": str(state_path),
        "factory_state_sha256": _sha256(state_path),
        "episodes": episodes,
        "publication_allowed": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factory",
        description="Thin deterministic control plane for Zantara Video Factory V3",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan", help="show Season and episode plan")
    subparsers.add_parser("status", help="show persisted Factory status")
    for command in ("prepare", "dry-run", "canary", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("episode_id")
    package = subparsers.add_parser("package")
    package.add_argument("episode_id")
    package.add_argument("--languages", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = factory_plan(args.repo_root)
        elif args.command == "status":
            result = factory_status(args.repo_root)
        elif args.command == "prepare":
            result = prepare_episode(args.repo_root, args.episode_id)
        elif args.command == "dry-run":
            result = dry_run_episode(args.repo_root, args.episode_id)
        elif args.command == "canary":
            result = canary_episode(args.repo_root, args.episode_id)
        elif args.command == "validate":
            result = validate_episode(args.repo_root, args.episode_id)
        elif args.command == "package":
            result = package_episode(
                args.repo_root,
                args.episode_id,
                languages=tuple(part.strip() for part in args.languages.split(",")),
            )
        else:  # pragma: no cover - argparse closes the set
            raise FactoryError(f"unknown command: {args.command}")
    except FactoryError as exc:
        sys.stdout.write(
            json.dumps(
                {"status": "HALT", "command": args.command, "error": str(exc)},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return 2
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if result.get("valid") is False or result.get("status") in {"BLOCKED", "HALT"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
