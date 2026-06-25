from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_doctor_module() -> ModuleType:
    backend_root = Path(__file__).resolve().parents[4]
    script_path = backend_root / "scripts" / "local_audio_doctor.py"
    spec = importlib.util.spec_from_file_location("local_audio_doctor_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cli_bootstraps_backend_root(monkeypatch: pytest.MonkeyPatch) -> None:
    backend_root = Path(__file__).resolve().parents[4]
    monkeypatch.setattr(
        sys,
        "path",
        [entry for entry in sys.path if entry != str(backend_root)],
    )

    _load_doctor_module()

    assert sys.path[0] == str(backend_root)


class FakeReport:
    def __init__(self, *, ok: bool) -> None:
        self.ok = ok

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "checks": []}

    def format_text(self) -> str:
        return f"ok={self.ok}"


def test_cli_returns_nonzero_and_json_for_failed_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_doctor_module()
    monkeypatch.setattr(
        module,
        "build_local_audio_readiness_report",
        lambda **_kwargs: FakeReport(ok=False),
    )

    exit_code = module.main(["--mode", "static", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_cli_passes_deep_mode_to_builder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_doctor_module()
    calls: list[str] = []

    def fake_build(**kwargs: object) -> FakeReport:
        calls.append(str(kwargs["mode"]))
        return FakeReport(ok=True)

    monkeypatch.setattr(module, "build_local_audio_readiness_report", fake_build)

    exit_code = module.main(["--mode", "deep"])

    assert exit_code == 0
    assert calls == ["deep"]
    assert capsys.readouterr().out.strip() == "ok=True"
