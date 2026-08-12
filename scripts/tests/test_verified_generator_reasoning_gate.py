"""Regression tests for the verified-generator reasoning fail-closed gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SPEC = importlib.util.spec_from_file_location(
    "verified_generator",
    REPO / "apps" / "backend-rag" / "scripts" / "verified_generator.py",
)
assert SPEC and SPEC.loader
vg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vg
SPEC.loader.exec_module(vg)


def test_unarmed_required_reasoning_aborts_before_dispatch(
    monkeypatch: Any, caplog: Any
) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("unarmed reasoning gate must not invoke a retired route")

    monkeypatch.setattr(vg, "run_dispatch", unexpected)
    with pytest.raises(SystemExit) as exc_info:
        vg.step_reasoning_gate(skip=False)

    assert exc_info.value.code == 2
    assert "--skip-reasoning" in caplog.text


def test_explicit_reasoning_skip_never_calls_dispatch(monkeypatch: Any) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("explicit skip must not invoke the retired route")

    monkeypatch.setattr(vg, "run_dispatch", unexpected)

    assert vg.step_reasoning_gate(skip=True) == ""


def test_main_enforces_reasoning_gate_before_any_provider_call(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("main reached a provider before the reasoning gate")

    monkeypatch.setattr(vg, "run_dispatch", unexpected)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verified_generator.py",
            "--domain",
            "immigration",
            "--topic",
            "KITAS renewal",
            "--output",
            str(tmp_path / "guide.txt"),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        vg.main()

    assert exc_info.value.code == 2
