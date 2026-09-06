"""Offline evidence consumers fail closed and never infer during catalog reads."""

from contextlib import asynccontextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tomllib
from typing import Any, AsyncIterator

import pytest

from scripts.conductor import codex_shadow_probe as consumer
from scripts.conductor.codex_shadow_launch import PROFILE


def model_entry(model: str, *, hidden: bool = False) -> dict[str, Any]:
    return {
        "id": model,
        "model": model,
        "hidden": hidden,
        "isDefault": False,
        "defaultReasoningEffort": "medium",
        "description": "EXCLUDED_PROVIDER_DESCRIPTION",
        "supportedReasoningEfforts": [
            {"reasoningEffort": "medium", "description": "EXCLUDED_EFFORT_COPY"}
        ],
    }


class CatalogRPC:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = deepcopy(pages)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.config = tomllib.loads(PROFILE)
        self.config["unknown_metadata"] = "EXCLUDED_CONFIG"
        self.account = {"type": "chatgpt", "email": "EXCLUDED_ACCOUNT"}
        self.local_stopped = False

    async def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, params))
        if method == "config/read":
            return {"config": self.config}
        if method == "account/read":
            return {"account": self.account}
        assert method == "model/list", "Catalog must never invoke inference"
        return self.pages.pop(0)


@pytest.fixture
def source_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "producer"
    directory = root / "scripts/conductor"
    directory.mkdir(parents=True)
    for name in consumer.SOURCE_MODULES:
        (directory / name).write_text("# synthetic producer " + name + "\n")
    monkeypatch.setattr(consumer, "SOURCE_ROOT", root)
    return root


def install_launcher(
    monkeypatch: pytest.MonkeyPatch,
    rpc: CatalogRPC,
    root: Path,
    *,
    drift: bool = False,
    stopped: bool = True,
) -> None:
    @asynccontextmanager
    async def launch(auth_home: Path) -> AsyncIterator[tuple]:
        try:
            yield (
                rpc,
                root,
                {
                    "runtime_version": "synthetic-runtime",
                    "binary_hash": "synthetic-binary-digest",
                    "profile_hash": "synthetic-profile-digest",
                },
                lambda: "synthetic-credential-fingerprint",
            )
        finally:
            rpc.local_stopped = stopped
            if drift:
                (root / "scripts/conductor/contracts.py").write_text("changed")

    monkeypatch.setattr(consumer, "launch_shadow", launch)


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", ["hidden-model", "absent-model"])
async def test_catalog_unavailable_model_paginates_without_admission_or_inference(
    source_tree: Path, monkeypatch: pytest.MonkeyPatch, requested: str
) -> None:
    rpc = CatalogRPC(
        [
            {"data": [model_entry("visible-model")], "nextCursor": "EXCLUDED_CURSOR"},
            {
                "data": [model_entry("hidden-model", hidden=True)],
                "unknown": "EXCLUDED_RAW",
            },
        ]
    )
    install_launcher(monkeypatch, rpc, source_tree)

    def no_adapter(*args: object, **kwargs: object) -> None:
        raise AssertionError("Catalog must not try admission")

    monkeypatch.setattr(consumer, "CodexShadow", no_adapter)
    result = await consumer.probe(source_tree, requested, "catalog")
    assert [name for name, _ in rpc.calls] == [
        "config/read",
        "account/read",
        "model/list",
        "model/list",
    ]
    assert all(
        params["includeHidden"] is True
        for name, params in rpc.calls
        if name == "model/list"
    )
    assert rpc.calls[-1][1]["cursor"] == "EXCLUDED_CURSOR"
    assert result["catalog"]["requested_model_available"] is (
        requested == "hidden-model"
    )
    assert result["catalog"]["complete"] is True
    assert len(result["catalog"]["pages"]) == 2
    assert result["catalog"]["pages"][-1]["models"][0]["hidden"] is True
    assert result["inference_calls"] == 0
    assert result["effect_authority"] == "none" and result["fleet_activation"] is False
    assert result["local_process_group_stopped"] is True
    assert result["runtime"]["profile_hash"] and result["host"]
    assert result["auth_context_hash"] == consumer.digest(
        {"account": rpc.account, "credential": "synthetic-credential-fingerprint"}
    )
    assert rpc.calls[1] == ("account/read", {"refreshToken": False})
    assert result["source_producer"] == consumer.source_producer()
    assert result["source_verification"] == "unchanged"
    assert "EXCLUDED" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["cycle", "limit", "profile", "account", "drift", "cleanup"]
)
async def test_catalog_failure_never_emits_success(
    source_tree: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    pages = (
        [{"data": [], "nextCursor": "cursor"}] * 2
        if failure == "cycle"
        else [{"data": [], "nextCursor": str(index)} for index in range(21)]
        if failure == "limit"
        else [{"data": []}]
    )
    rpc = CatalogRPC(pages)
    if failure == "profile":
        rpc.config["web_search"] = "enabled"
    if failure == "account":
        rpc.account["type"] = "apikey"
    install_launcher(
        monkeypatch,
        rpc,
        source_tree,
        drift=failure == "drift",
        stopped=failure != "cleanup",
    )
    expected = {
        "cycle": "catalog_cursor_cycle",
        "limit": "catalog_page_limit",
        "profile": "shadow_approval_or_web",
        "account": "chatgpt_subscription_required",
        "drift": "source_producer_changed",
        "cleanup": "local_process_group_not_stopped",
    }
    with pytest.raises((PermissionError, RuntimeError), match=expected[failure]):
        await consumer.probe(source_tree, "absent-model", "catalog")
    calls = [name for name, _ in rpc.calls]
    assert calls.count("model/list") == {
        "cycle": 2,
        "limit": 20,
        "profile": 0,
        "account": 0,
    }.get(failure, 1)
    assert set(calls) <= {"config/read", "account/read", "model/list"}


@pytest.mark.asyncio
async def test_default_discovery_still_admits_model_and_binds_producer(
    source_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rpc = CatalogRPC([{"data": [model_entry("available-model")]}])
    install_launcher(monkeypatch, rpc, source_tree)
    result = await consumer.probe(source_tree, "available-model", "discovery")
    assert [name for name, _ in rpc.calls] == [
        "config/read",
        "account/read",
        "model/list",
    ]
    assert "includeHidden" not in rpc.calls[-1][1]
    assert result["results"] == [] and result["authorization_checks"] == []
    assert result["source_producer"] == consumer.source_producer()
    assert "EXCLUDED" not in json.dumps(result)


def test_manifest_binds_exact_six_source_bytes(source_tree: Path) -> None:
    binding = consumer.source_producer()
    assert len(binding["files"]) == 6
    for relative, value in binding["files"].items():
        assert sha256((source_tree / relative).read_bytes()).hexdigest() == value
    canonical = json.dumps(
        binding["files"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert binding["manifest_sha256"] == sha256(canonical.encode()).hexdigest()


def test_cli_keyerror_is_receipt_safe_and_keeps_initial_producer_binding(
    source_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rpc = CatalogRPC([{}])
    install_launcher(monkeypatch, rpc, source_tree)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe",
            "--auth-home",
            str(source_tree),
            "--model",
            "absent-model",
            "--catalog",
        ],
    )
    assert consumer.main() == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["error_type"] == "KeyError"
    assert result["source_producer"] == consumer.source_producer()
    assert result["source_verification"] == "not_completed"
    assert result["status"] == "qualification_failed"
    assert "EXCLUDED" not in output.out and not output.err
