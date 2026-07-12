from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_worker_module() -> ModuleType:
    backend_root = Path(__file__).resolve().parents[4]
    script_path = backend_root / "scripts" / "local_livekit_voice_worker.py"
    spec = importlib.util.spec_from_file_location("local_livekit_voice_worker_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_health_endpoint_defaults_to_loopback_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_worker_module()
    monkeypatch.delenv("VOICE_CONCIERGE_LIVEKIT_WORKER_HEALTH_URL", raising=False)

    endpoint = module.health_endpoint_from_env()

    assert endpoint.host == "127.0.0.1"
    assert endpoint.port == 7889
    assert endpoint.path == "/healthz"
    assert endpoint.url == "http://127.0.0.1:7889/healthz"


def test_native_health_endpoint_rejects_healthz_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_worker_module()
    monkeypatch.setenv(
        "VOICE_CONCIERGE_LIVEKIT_WORKER_NATIVE_HEALTH_URL",
        "http://127.0.0.1:7889/healthz",
    )

    with pytest.raises(module.PreflightError, match="native health"):
        module.native_health_endpoint_from_env()


def test_livekit_server_url_rejects_public_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_worker_module()
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")

    with pytest.raises(module.PreflightError, match="localhost"):
        module.livekit_server_url_from_env()


def test_livekit_server_url_accepts_tailscale_lan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_worker_module()
    monkeypatch.setenv("LIVEKIT_URL", "ws://100.107.22.111:7880")

    assert module.livekit_server_url_from_env() == "ws://100.107.22.111:7880"


def test_sidecar_health_requires_livekit_server_and_native_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_worker_module()
    config = module.SidecarConfig(
        health_endpoint=module.HealthEndpoint(
            host="127.0.0.1",
            port=7889,
            path="/healthz",
            url="http://127.0.0.1:7889/healthz",
        ),
        native_endpoint=module.HealthEndpoint(
            host="127.0.0.1",
            port=7888,
            path="/",
            url="http://127.0.0.1:7888/",
        ),
        livekit_url="ws://127.0.0.1:7880",
        agent_name="voice-concierge-local",
    )
    monkeypatch.setattr(module, "_tcp_reachable", lambda _url: False)
    monkeypatch.setattr(module, "_native_worker_root_ok", lambda _url: True)
    monkeypatch.setattr(
        module,
        "_native_worker_metadata",
        lambda _url: {"agent_name": "voice-concierge-local"},
    )

    status_code, payload = module.build_sidecar_health_payload(config)

    assert status_code == 503
    assert payload["healthy"] is False
    assert payload["native_worker_ready"] is True
