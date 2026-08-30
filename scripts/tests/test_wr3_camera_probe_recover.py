"""Recovery-only invariants for an already-charged WR3 camera probe."""

from __future__ import annotations

import ast
import copy
import fcntl
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wr3_camera_probe_recover as recovery  # noqa: E402


PROJECT_ID = "08c2c96a-7983-4f8b-a41e-b3afe3a68e3b"
VIDEO_ID = "648a1e43-fae8-4d2a-a825-f6a2c31225b0"
WORKFLOW_ID = "806283d2-a2f8-477d-a327-2a29d313d331"
MEDIA_ID = "b8f6f600-5093-4edf-bcb3-e5383df76c3e"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 96
ORIGINAL_ERROR = {
    "type": "FlowkitError",
    "message": "legacy media endpoint rejected workflow-backed media",
}


def _receipt_payload(episode_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": "wr3-camera-probe-run-receipt/1.1",
        "runner_version": "1.1",
        "created_at": "2026-08-30T20:20:08+00:00",
        "updated_at": "2026-08-30T20:20:15+00:00",
        "generation_status": "successful",
        "retrieval_status": "failed",
        "source": {
            "episode_id": "s01e13-residency-permit-probes-f01-fluid-approach",
            "family_id": "f01-fluid-approach",
            "variant_id": "v05",
            "shot_index": 105,
        },
        "flow": {
            "endpoint": "http://127.0.0.1:8100",
            "paygate": "PAYGATE_TIER_TIER1P5",
            "project_id": PROJECT_ID,
            "video_id": VIDEO_ID,
            "workflow_id": WORKFLOW_ID,
            "media_id": MEDIA_ID,
            "generate_call_count": 1,
            "download_call_count": 1,
        },
        "credits": {
            "live_before": 12530,
            "live_after": None,
            "live_delta": None,
        },
        "artifact": {
            "mp4_path": str((episode_dir / "clips" / "105.mp4").resolve()),
            "bytes": None,
            "sha256": None,
        },
        "error": copy.deepcopy(ORIGINAL_ERROR),
    }


def _write_receipt(
    tmp_path: Path,
    *,
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Path, dict[str, Any]]:
    episode_dir = tmp_path / "episode"
    episode_dir.mkdir(parents=True)
    receipt = _receipt_payload(episode_dir)
    if mutate is not None:
        mutate(receipt)
    receipt_path = episode_dir / "probe-run-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt_path, receipt


def _mp4_path(receipt: dict[str, Any]) -> Path:
    return Path(receipt["artifact"]["mp4_path"])


def _receipt_sha256(receipt_path: Path) -> str:
    return hashlib.sha256(receipt_path.read_bytes()).hexdigest()


def _config(
    receipt_path: Path,
    *,
    expected_initial_receipt_sha256: str | None = None,
    timeout_s: int = recovery.DEFAULT_TIMEOUT_S,
    poll_interval_s: int = recovery.DEFAULT_POLL_INTERVAL_S,
) -> recovery.RecoveryConfig:
    return recovery.RecoveryConfig(
        receipt=receipt_path,
        expected_initial_receipt_sha256=(
            expected_initial_receipt_sha256 or _receipt_sha256(receipt_path)
        ),
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )


def _make_successful(receipt: dict[str, Any], mp4_bytes: bytes = MP4_BYTES) -> None:
    receipt["retrieval_status"] = "successful"
    receipt["artifact"]["bytes"] = len(mp4_bytes)
    receipt["artifact"]["sha256"] = hashlib.sha256(mp4_bytes).hexdigest()
    receipt["credits"]["live_after"] = 12520
    receipt["credits"]["live_delta"] = 10
    receipt["credits"]["live_balance_delta_observed"] = 10
    receipt["credits"]["live_delta_scope"] = recovery.LIVE_DELTA_SCOPE
    receipt["credits"]["live_delta_is_exact_workflow_cost"] = False
    receipt["error"] = None


def test_module_imports_only_recovery_primitives_from_flow_client() -> None:
    source = Path(recovery.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    forbidden_calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "wr3_flowkit_client":
            imported.update(alias.name for alias in node.names)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name in {"_generate_video", "submit_clip", "setup_episode_context"}:
                forbidden_calls.add(name)

    assert imported == {"EpisodeContext", "_download_video_media", "_http_get_json"}
    assert forbidden_calls == set()
    parser_actions = {action.dest for action in recovery._build_parser()._actions}
    assert "expected_initial_receipt_sha256" in parser_actions
    assert not parser_actions.intersection(
        {"project_id", "workflow_id", "media_id", "retry", "resubmit"}
    )


@pytest.mark.asyncio
async def test_one_recovery_call_uses_exact_receipt_ids_and_updates_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    calls: list[dict[str, Any]] = []

    async def fake_download(context: recovery.EpisodeContext, **kwargs: Any) -> None:
        calls.append({"context": context, **kwargs})
        kwargs["dest"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["dest"].write_bytes(MP4_BYTES)

    async def fake_get(url: str, timeout_s: int) -> dict[str, int]:
        assert url == "http://127.0.0.1:8100/api/flow/credits"
        assert timeout_s == 30
        return {"credits": 12520}

    atomic_snapshots: list[dict[str, Any]] = []
    atomic_replacements: list[tuple[Path, Path]] = []
    synced_directories: list[Path] = []
    durability_events: list[str] = []
    real_atomic_write = recovery._write_json_atomic
    real_file_fsync = recovery._fsync_file
    real_replace = recovery.os.replace

    def tracking_replace(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        atomic_replacements.append((source_path, destination_path))
        real_replace(source, destination)

    def tracking_directory_fsync(path: Path) -> None:
        synced_directories.append(path)
        durability_events.append(f"directory:{path}")

    def tracking_file_fsync(path: Path) -> None:
        real_file_fsync(path)
        durability_events.append(f"file:{path}")

    def tracking_atomic_write(path: Path, payload: dict[str, Any]) -> None:
        real_atomic_write(path, payload)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        atomic_snapshots.append(snapshot)
        durability_events.append(
            f"receipt:{snapshot['recovery']['attempts'][-1]['status']}"
        )

    monkeypatch.setattr(recovery, "_download_video_media", fake_download)
    monkeypatch.setattr(recovery, "_http_get_json", fake_get)
    monkeypatch.setattr(recovery.os, "replace", tracking_replace)
    monkeypatch.setattr(recovery, "_fsync_directory", tracking_directory_fsync)
    monkeypatch.setattr(recovery, "_fsync_file", tracking_file_fsync)
    monkeypatch.setattr(recovery, "_write_json_atomic", tracking_atomic_write)

    result = await recovery.recover_one(
        _config(
            receipt_path,
            timeout_s=17,
            poll_interval_s=0,
        )
    )

    assert len(calls) == 1
    call = calls[0]
    context = call.pop("context")
    assert context.project_id == PROJECT_ID
    assert context.video_id == VIDEO_ID
    assert context.project_name == result["source"]["episode_id"]
    staging_path = Path(result["recovery"]["staging"]["path"])
    assert call == {
        "workflow_id": WORKFLOW_ID,
        "media_id": MEDIA_ID,
        "dest": staging_path,
        "timeout_s": 17,
        "poll_interval_s": 0,
    }
    assert [item["retrieval_status"] for item in atomic_snapshots] == [
        "pending",
        "pending",
        "pending",
        "successful",
    ]
    assert [
        item["recovery"]["attempts"][-1]["status"] for item in atomic_snapshots
    ] == ["downloading", "staged", "artifact_recovered", "successful"]
    receipt_replacements = [
        pair for pair in atomic_replacements if pair[1] == receipt_path
    ]
    media_replacements = [
        pair for pair in atomic_replacements if pair[1] == _mp4_path(result)
    ]
    assert len(receipt_replacements) == 4
    assert len(media_replacements) == 1
    assert media_replacements[0][0] == staging_path
    assert synced_directories.count(receipt_path.parent) == 4
    assert synced_directories.count(_mp4_path(result).parent) == 2
    assert (
        durability_events.index(f"file:{staging_path}")
        < durability_events.index(f"directory:{staging_path.parent}")
        < durability_events.index("receipt:staged")
    )
    assert result["generation_status"] == "successful"
    assert result["retrieval_status"] == "successful"
    assert result["flow"]["download_call_count"] == 2
    assert result["flow"]["project_id"] == PROJECT_ID
    assert result["flow"]["workflow_id"] == WORKFLOW_ID
    assert result["flow"]["media_id"] == MEDIA_ID
    assert result["artifact"]["bytes"] == len(MP4_BYTES)
    assert result["artifact"]["sha256"] == hashlib.sha256(MP4_BYTES).hexdigest()
    assert result["credits"]["live_after"] == 12520
    assert result["credits"]["live_delta"] == 10
    assert result["credits"]["live_balance_delta_observed"] == 10
    assert result["credits"]["live_delta_scope"] == (
        "global_account_balance_observation_not_per_workflow"
    )
    assert result["credits"]["live_delta_is_exact_workflow_cost"] is False
    assert result["recovery"]["original_error"] == ORIGINAL_ERROR
    assert list(receipt_path.parent.glob(".probe-run-receipt.json.*.tmp")) == []
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == result


def test_publish_refuses_to_replace_a_preexisting_final_artifact(
    tmp_path: Path,
) -> None:
    staging_path = tmp_path / "clips" / ".105.bound.recovery-stage.mp4"
    final_path = tmp_path / "clips" / "105.mp4"
    staging_path.parent.mkdir(parents=True)
    staging_path.write_bytes(MP4_BYTES)
    final_bytes = b"already-published-final"
    final_path.write_bytes(final_bytes)

    with pytest.raises(recovery.ReceiptValidationError, match="refusing to overwrite"):
        recovery._publish_staged_artifact(staging_path, final_path)

    assert staging_path.read_bytes() == MP4_BYTES
    assert final_path.read_bytes() == final_bytes


def _set_nested(receipt: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node: dict[str, Any] = receipt
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("generation_status",), "failed", "generation_status"),
        (("flow", "project_id"), "", "project_id"),
        (("flow", "workflow_id"), None, "workflow_id"),
        (("flow", "media_id"), f" {MEDIA_ID}", "media_id"),
        (("flow", "generate_call_count"), 2, "generate_call_count"),
        (
            ("credits", "live_balance_delta_observed"),
            10,
            "final live credit values",
        ),
    ],
)
@pytest.mark.asyncio
async def test_invalid_receipt_fails_before_any_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    value: Any,
    match: str,
) -> None:
    receipt_path, _ = _write_receipt(
        tmp_path,
        mutate=lambda receipt: _set_nested(receipt, path, value),
    )

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("invalid receipt must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    with pytest.raises(recovery.ReceiptValidationError, match=match):
        await recovery.recover_one(_config(receipt_path))


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8100",
        "http://flowkit.test:8100",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8100/api/flow",
        "http://user@127.0.0.1:8100",
    ],
)
@pytest.mark.asyncio
async def test_noncanonical_gateway_endpoint_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    receipt_path, _ = _write_receipt(
        tmp_path,
        mutate=lambda receipt: _set_nested(receipt, ("flow", "endpoint"), endpoint),
    )

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("unsafe endpoint must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    with pytest.raises(recovery.ReceiptValidationError, match="loopback FlowKit"):
        await recovery.recover_one(_config(receipt_path))


@pytest.mark.asyncio
async def test_concurrent_recovery_lock_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    lock_path = recovery._recovery_lock_path(receipt_path.resolve())

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("locked recovery must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(
            recovery.ReceiptValidationError, match="already in progress"
        ):
            await recovery.recover_one(_config(receipt_path))


@pytest.mark.asyncio
async def test_trusted_initial_receipt_sha_mismatch_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("authorization mismatch must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    with pytest.raises(
        recovery.ReceiptValidationError,
        match="trusted initial receipt SHA-256",
    ):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256="0" * 64,
            )
        )


@pytest.mark.asyncio
async def test_coordinated_id_tuple_tamper_fails_against_embedded_initial_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    expected_initial_sha = _receipt_sha256(receipt_path)

    class SimulatedCrash(BaseException):
        pass

    async def crash_after_staging(
        _context: recovery.EpisodeContext,
        **kwargs: Any,
    ) -> None:
        kwargs["dest"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["dest"].write_bytes(MP4_BYTES)
        raise SimulatedCrash("process exited after client published staging")

    monkeypatch.setattr(recovery, "_download_video_media", crash_after_staging)
    with pytest.raises(SimulatedCrash):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )

    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered_media_id = "00000000-0000-0000-0000-000000000000"
    tampered["flow"]["media_id"] = tampered_media_id
    # Simulate coordinated editing of every clear-text binding. The embedded
    # exact initial receipt bytes remain immutable under the trusted SHA.
    tampered["recovery"]["authorization"]["authorization_tuple"]["flow"]["media_id"] = (
        tampered_media_id
    )
    tampered["recovery"]["staging"]["ids"]["media_id"] = tampered_media_id
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("coordinated tuple tamper must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)
    with pytest.raises(
        recovery.ReceiptValidationError,
        match="authorization tuple differs from initial receipt",
    ):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )


@pytest.mark.parametrize(
    ("credit_key", "tampered_value", "match"),
    [
        ("live_before", 99999, "immutable authorization tuple differs"),
        ("declared_clip_cost", 99, "immutable authorization tuple differs"),
        ("clip_cost_source", "tampered", "immutable authorization tuple differs"),
        (
            "live_delta_is_exact_workflow_cost",
            True,
            "live_delta_is_exact_workflow_cost must be false",
        ),
    ],
)
@pytest.mark.asyncio
async def test_credit_truth_tamper_after_crash_fails_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    credit_key: str,
    tampered_value: Any,
    match: str,
) -> None:
    def add_credit_truth(receipt: dict[str, Any]) -> None:
        receipt["credits"].update(
            {
                "declared_clip_cost": 10,
                "clip_cost_source": "operator_supplied_paygate_parameter",
                "live_delta_scope": recovery.LIVE_DELTA_SCOPE,
                "live_delta_is_exact_workflow_cost": False,
            }
        )

    receipt_path, _ = _write_receipt(tmp_path, mutate=add_credit_truth)
    expected_initial_sha = _receipt_sha256(receipt_path)

    class SimulatedCrash(BaseException):
        pass

    async def crash_after_staging(
        _context: recovery.EpisodeContext,
        **kwargs: Any,
    ) -> None:
        kwargs["dest"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["dest"].write_bytes(MP4_BYTES)
        raise SimulatedCrash("process exited after client published staging")

    monkeypatch.setattr(recovery, "_download_video_media", crash_after_staging)
    with pytest.raises(SimulatedCrash):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )

    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered["credits"][credit_key] = tampered_value
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("credit truth tamper must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)
    with pytest.raises(recovery.ReceiptValidationError, match=match):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )


@pytest.mark.asyncio
async def test_crash_after_staging_publish_resumes_without_redownload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    expected_initial_sha = _receipt_sha256(receipt_path)
    downloads = 0

    class SimulatedCrash(BaseException):
        pass

    async def crash_after_staging(
        _context: recovery.EpisodeContext,
        **kwargs: Any,
    ) -> None:
        nonlocal downloads
        downloads += 1
        kwargs["dest"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["dest"].write_bytes(MP4_BYTES)
        raise SimulatedCrash("process exited after client published staging")

    monkeypatch.setattr(recovery, "_download_video_media", crash_after_staging)
    with pytest.raises(SimulatedCrash):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )

    crashed = json.loads(receipt_path.read_text(encoding="utf-8"))
    staging_path = Path(crashed["recovery"]["staging"]["path"])
    assert crashed["recovery"]["staging"]["status"] == "bound"
    assert crashed["recovery"]["attempts"][-1]["status"] == "downloading"
    assert crashed["flow"]["media_id"] == MEDIA_ID
    assert staging_path.read_bytes() == MP4_BYTES
    assert not _mp4_path(crashed).exists()

    async def forbidden_download(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("valid bound staging must not be downloaded again")

    async def good_credit_read(_url: str, timeout_s: int) -> dict[str, int]:
        assert timeout_s == 30
        return {"credits": 12520}

    monkeypatch.setattr(recovery, "_download_video_media", forbidden_download)
    monkeypatch.setattr(recovery, "_http_get_json", good_credit_read)
    completed = await recovery.recover_one(
        _config(
            receipt_path,
            expected_initial_receipt_sha256=expected_initial_sha,
        )
    )

    assert downloads == 1
    assert completed["retrieval_status"] == "successful"
    assert completed["flow"]["project_id"] == PROJECT_ID
    assert completed["flow"]["video_id"] == VIDEO_ID
    assert completed["flow"]["workflow_id"] == WORKFLOW_ID
    assert completed["flow"]["media_id"] == MEDIA_ID
    assert completed["flow"]["download_call_count"] == 2
    assert completed["recovery"]["attempts"][-1]["mode"] == (
        "resume_unrecorded_staging"
    )
    assert not staging_path.exists()
    assert _mp4_path(completed).read_bytes() == MP4_BYTES


@pytest.mark.asyncio
async def test_crash_after_staging_to_final_replace_resumes_without_redownload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    expected_initial_sha = _receipt_sha256(receipt_path)
    downloads = 0

    async def fake_download(
        _context: recovery.EpisodeContext,
        **kwargs: Any,
    ) -> None:
        nonlocal downloads
        downloads += 1
        kwargs["dest"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["dest"].write_bytes(MP4_BYTES)

    class SimulatedCrash(BaseException):
        pass

    real_publish = recovery._publish_staged_artifact

    def crash_after_replace(staging_path: Path, mp4_path: Path) -> None:
        real_publish(staging_path, mp4_path)
        raise SimulatedCrash("process exited immediately after os.replace")

    monkeypatch.setattr(recovery, "_download_video_media", fake_download)
    monkeypatch.setattr(recovery, "_publish_staged_artifact", crash_after_replace)
    with pytest.raises(SimulatedCrash):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )

    crashed = json.loads(receipt_path.read_text(encoding="utf-8"))
    staging_path = Path(crashed["recovery"]["staging"]["path"])
    assert crashed["recovery"]["staging"]["status"] == "staged"
    assert crashed["recovery"]["attempts"][-1]["status"] == "staged"
    assert not staging_path.exists()
    assert _mp4_path(crashed).read_bytes() == MP4_BYTES

    async def forbidden_download(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("published final artifact must not be downloaded again")

    async def good_credit_read(_url: str, timeout_s: int) -> dict[str, int]:
        assert timeout_s == 30
        return {"credits": 12520}

    monkeypatch.setattr(recovery, "_download_video_media", forbidden_download)
    monkeypatch.setattr(recovery, "_publish_staged_artifact", real_publish)
    monkeypatch.setattr(recovery, "_http_get_json", good_credit_read)
    completed = await recovery.recover_one(
        _config(
            receipt_path,
            expected_initial_receipt_sha256=expected_initial_sha,
        )
    )

    assert downloads == 1
    assert completed["retrieval_status"] == "successful"
    assert completed["flow"]["project_id"] == PROJECT_ID
    assert completed["flow"]["video_id"] == VIDEO_ID
    assert completed["flow"]["workflow_id"] == WORKFLOW_ID
    assert completed["flow"]["media_id"] == MEDIA_ID
    assert completed["flow"]["download_call_count"] == 2
    assert completed["recovery"]["attempts"][-1]["mode"] == "resume_published"
    assert _mp4_path(completed).read_bytes() == MP4_BYTES


@pytest.mark.asyncio
async def test_existing_successful_mp4_is_idempotent_without_network_or_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, receipt = _write_receipt(tmp_path, mutate=_make_successful)
    mp4_path = _mp4_path(receipt)
    mp4_path.parent.mkdir(parents=True)
    mp4_path.write_bytes(MP4_BYTES)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    original_receipt_bytes = receipt_path.read_bytes()

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("completed recovery must be an idempotent local no-op")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    result = await recovery.recover_one(_config(receipt_path))

    assert result == receipt
    assert receipt_path.read_bytes() == original_receipt_bytes
    assert mp4_path.read_bytes() == MP4_BYTES


@pytest.mark.asyncio
async def test_unbound_existing_mp4_is_inconsistent_and_refused_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, receipt = _write_receipt(tmp_path)
    mp4_path = _mp4_path(receipt)
    mp4_path.parent.mkdir(parents=True)
    mp4_path.write_bytes(MP4_BYTES)

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("inconsistent local state must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    with pytest.raises(recovery.ReceiptValidationError, match="authorization binding"):
        await recovery.recover_one(_config(receipt_path))


@pytest.mark.asyncio
async def test_unbound_deterministic_staging_mp4_is_refused_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    config = _config(receipt_path)
    validated = recovery.validate_recovery(config)
    validated.staging_path.parent.mkdir(parents=True, exist_ok=True)
    validated.staging_path.write_bytes(MP4_BYTES)

    async def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("unbound staging must fail before network")

    monkeypatch.setattr(recovery, "_download_video_media", forbidden)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden)

    with pytest.raises(recovery.ReceiptValidationError, match="authorization binding"):
        await recovery.recover_one(config)

    assert validated.staging_path.read_bytes() == MP4_BYTES


@pytest.mark.asyncio
async def test_failed_recovery_preserves_exact_ids_and_original_error_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, original = _write_receipt(tmp_path)
    calls = 0

    async def failing_download(
        context: recovery.EpisodeContext,
        **kwargs: Any,
    ) -> None:
        nonlocal calls
        calls += 1
        assert context.project_id == PROJECT_ID
        assert kwargs["workflow_id"] == WORKFLOW_ID
        assert kwargs["media_id"] == MEDIA_ID
        raise RuntimeError("signed URL still unavailable")

    async def forbidden_credit_read(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("credits are not read after a failed download")

    monkeypatch.setattr(recovery, "_download_video_media", failing_download)
    monkeypatch.setattr(recovery, "_http_get_json", forbidden_credit_read)

    with pytest.raises(
        recovery.ProbeDownloadRecoveryError, match="no render was resubmitted"
    ):
        await recovery.recover_one(_config(receipt_path))

    assert calls == 1
    failed = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert failed["generation_status"] == "successful"
    assert failed["retrieval_status"] == "failed"
    assert failed["flow"]["project_id"] == original["flow"]["project_id"]
    assert failed["flow"]["video_id"] == original["flow"]["video_id"]
    assert failed["flow"]["workflow_id"] == original["flow"]["workflow_id"]
    assert failed["flow"]["media_id"] == original["flow"]["media_id"]
    assert failed["flow"]["generate_call_count"] == 1
    assert failed["flow"]["download_call_count"] == 2
    assert failed["artifact"]["bytes"] is None
    assert failed["artifact"]["sha256"] is None
    assert failed["error"] == {
        "type": "RuntimeError",
        "message": "signed URL still unavailable",
    }
    assert failed["recovery"]["original_error"] == ORIGINAL_ERROR
    assert failed["recovery"]["attempts"][-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_credit_failure_preserves_pinned_mp4_and_next_run_skips_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path, _ = _write_receipt(tmp_path)
    expected_initial_sha = _receipt_sha256(receipt_path)
    downloads = 0

    async def fake_download(context: recovery.EpisodeContext, **kwargs: Any) -> None:
        nonlocal downloads
        downloads += 1
        kwargs["dest"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["dest"].write_bytes(MP4_BYTES)

    async def broken_credit_read(url: str, timeout_s: int) -> dict[str, Any]:
        return {"detail": {"error": "temporarily unavailable"}}

    monkeypatch.setattr(recovery, "_download_video_media", fake_download)
    monkeypatch.setattr(recovery, "_http_get_json", broken_credit_read)

    with pytest.raises(recovery.ProbeCreditReadError, match="SHA-pinned"):
        await recovery.recover_one(
            _config(
                receipt_path,
                expected_initial_receipt_sha256=expected_initial_sha,
            )
        )

    partial = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert downloads == 1
    assert partial["generation_status"] == "successful"
    assert partial["retrieval_status"] == "failed"
    assert partial["artifact"]["bytes"] == len(MP4_BYTES)
    assert partial["artifact"]["sha256"] == hashlib.sha256(MP4_BYTES).hexdigest()
    assert partial["credits"]["live_after"] is None
    assert partial["credits"]["live_delta"] is None
    assert partial["recovery"]["attempts"][-1]["status"] == "artifact_recovered"

    async def forbidden_download(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a SHA-pinned recovered MP4 must not be downloaded again")

    async def good_credit_read(url: str, timeout_s: int) -> dict[str, int]:
        return {"data": {"credits": 12520}}

    monkeypatch.setattr(recovery, "_download_video_media", forbidden_download)
    monkeypatch.setattr(recovery, "_http_get_json", good_credit_read)

    completed = await recovery.recover_one(
        _config(
            receipt_path,
            expected_initial_receipt_sha256=expected_initial_sha,
        )
    )

    assert downloads == 1
    assert completed["retrieval_status"] == "successful"
    assert completed["flow"]["download_call_count"] == 2
    assert completed["credits"]["live_after"] == 12520
    assert completed["credits"]["live_delta"] == 10
    assert completed["recovery"]["attempts"][-1]["mode"] == "resume_artifact"
    assert completed["recovery"]["attempts"][-1]["status"] == "successful"
    assert completed["recovery"]["original_error"] == ORIGINAL_ERROR
