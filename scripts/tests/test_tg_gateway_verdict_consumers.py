"""Runtime regressions for Python callers of the Telegram gateway verdict.

The gateway intentionally exits zero for delivery, dedupe, and durable-spool
outcomes.  Callers that use only ``returncode`` therefore turn a refusal into a
delivery acknowledgement.  These tests exercise the real caller boundaries so
the static class guard is not the only thing protecting the contract.
"""
from __future__ import annotations

import asyncio
import builtins
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    module_name = f"gateway_verdict_test_{name}"
    spec = importlib.util.spec_from_file_location(module_name, REPO / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


drive = _load("drive_token_watchdog")
bridge = _load("wa_mirror_bridge_liveness_alarm")
daily = _load("wr2_daily_reconciler")
html = _load("wr2_html_render_apply")
wa_session = _load("wa_session_liveness")

from scripts.tg_gateway_verdict import extract_gateway_verdict  # noqa: E402


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("tg_notify: sent\n", "sent"),
        ("tg_notify: logged\n", "logged"),
        ("tg_notify: spooled\n", "spooled"),
        ("tg_notify: deduped\n", "deduped"),
        ("tg_notify: p0_overflow_spooled\n", "p0_overflow_spooled"),
        ("tg_notify: p0_unsent_spooled\n", "p0_unsent_spooled"),
        (
            "tg_notify: P0 unsendable: telegram internal error\n"
            "tg_notify: p0_unsent_spooled\n",
            "p0_unsent_spooled",
        ),
        ("tg_notify: deduped\ntg_notify: sent\n", "sent"),
        ("tg_notify: telegram internal error\n", None),
        ("tg_notify: sent with trailing words\n", None),
        ("", None),
    ],
)
def test_extracts_last_exact_canonical_verdict(stderr: str, expected: str | None) -> None:
    assert extract_gateway_verdict(stderr) == expected


class _Result:
    def __init__(self, stderr: str, returncode: int = 0) -> None:
        self.stderr = stderr
        self.stdout = ""
        self.returncode = returncode


def _gateway_file(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "tg_notify.py").write_text("")


def _call_consumer(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    result: _Result,
) -> bool | None:
    _gateway_file(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: result)

    if name == "drive":
        monkeypatch.setattr(drive, "DRY_RUN", False)
        monkeypatch.setattr(drive, "PROJECT_ROOT", tmp_path)
        return drive._send_telegram("body", "token")

    if name == "bridge":
        monkeypatch.setattr(bridge, "_DRY_RUN", False)
        monkeypatch.setattr(bridge, "_bot_token", lambda: "token")
        return bridge._send_telegram("body")

    if name == "daily":
        monkeypatch.setattr(daily, "_REPO", tmp_path)
        return daily._tg_notify("p0", "key", "body")

    if name == "html":
        monkeypatch.setattr(html, "_REPO", tmp_path)
        return html._tg_notify("p0", "key", "body")

    if name == "wa_session":
        monkeypatch.setattr(wa_session, "REPO", tmp_path)
        # The production fallback prepends REPO/scripts for launchd. Keep that
        # mutation inside this test so a later ``import tg_notify`` cannot load
        # our empty fake gateway from tmp_path.
        monkeypatch.setattr(sys, "path", list(sys.path))
        real_import = builtins.__import__

        def fail_sentinel_import(
            module_name: str,
            globals_: dict | None = None,
            locals_: dict | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if module_name == "sentinel_lib":
                raise ImportError("force direct gateway fallback")
            return real_import(module_name, globals_, locals_, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fail_sentinel_import)
        return wa_session.send_to_gateway("body", "host")

    raise AssertionError(f"unknown consumer {name}")


@pytest.mark.parametrize("consumer", ["drive", "bridge", "daily", "html", "wa_session"])
@pytest.mark.parametrize(
    ("stderr", "returncode", "delivered"),
    [
        ("tg_notify: sent\n", 0, True),
        ("tg_notify: deduped\n", 0, False),
        ("tg_notify: p0_overflow_spooled\n", 0, False),
        (
            "tg_notify: P0 unsendable: telegram internal error\n"
            "tg_notify: p0_unsent_spooled\n",
            0,
            False,
        ),
        ("tg_notify: telegram internal error\n", 0, False),
        ("tg_notify: sent\n", 1, False),
    ],
)
def test_consumers_fail_closed_unless_gateway_delivered(
    consumer: str,
    stderr: str,
    returncode: int,
    delivered: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    actual = _call_consumer(consumer, monkeypatch, tmp_path, _Result(stderr, returncode))
    if consumer == "html" and (returncode != 0 or extract_gateway_verdict(stderr) is None):
        assert actual is None
    else:
        assert actual is delivered


@pytest.mark.parametrize(
    ("stderr", "returncode", "accepted"),
    [
        ("tg_notify: spooled\n", 0, True),
        ("tg_notify: deduped\n", 0, True),
        ("tg_notify: sent\n", 0, False),
        ("tg_notify: logged\n", 0, False),
        ("tg_notify: p0_overflow_spooled\n", 0, False),
        ("tg_notify: p0_unsent_spooled\n", 0, False),
        ("tg_notify: internal error (disk full) — best-effort spooled\n", 0, False),
        ("tg_notify: spooled\n", 1, False),
    ],
)
def test_drive_digest_accepts_only_durable_queue_verdicts(
    stderr: str,
    returncode: int,
    accepted: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _gateway_file(tmp_path)
    monkeypatch.setattr(drive, "DRY_RUN", False)
    monkeypatch.setattr(drive, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _Result(stderr, returncode),
    )

    assert drive._send_telegram("body", "token", tier="digest") is accepted


class _FakeAsyncClient:
    calls: list[tuple[str, dict[str, object]]]

    def __init__(self, calls: list[tuple[str, dict[str, object]]], **_: object) -> None:
        self.calls = calls

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, object]) -> None:
        self.calls.append((url, json))


@pytest.mark.parametrize(("gateway_result", "fallback_calls"), [(True, 0), (False, 0), (None, 1)])
def test_html_direct_fallback_only_when_gateway_result_is_unknown(
    gateway_result: bool | None,
    fallback_calls: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(html, "_tg_notify", lambda *args, **kwargs: gateway_result)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(calls, **kwargs))
    asyncio.run(html._ops_alert("body"))

    assert len(calls) == fallback_calls
