"""Tests for scripts/profile-monitor/wrapper.py — the tailnet-only bind.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package, and `profile-monitor` additionally has a hyphen a normal `import`
statement cannot spell (mirrors scripts/tests/test_adversarial_review_gate.py
convention).

Guilt/innocence pair (superscar #3): _resolve_listen_host must refuse an
all-interfaces bind (guilt: default env, "0.0.0.0", "") and accept everything
else (innocence: the real default, an explicit tailnet override, the open-bind
opt-in). Separately, _serve_with_bind_retry must retry EADDRNOTAVAIL with
capped backoff instead of propagating it (cicatrix #7/#8: KeepAlive=true on a
process that exits at boot before tailscaled is up becomes a crash loop) and
must NOT swallow any other OSError.

Importing the module has one real side effect: it creates ~/logs/ and opens
profile-monitor-wrapper.log via logging.basicConfig at import time — that is
existing wrapper.py behavior, unrelated to this change, and left as-is.
"""

from __future__ import annotations

import errno
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "profile-monitor" / "wrapper.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("profile_monitor_wrapper", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wrapper = _load_module()


# ---------------------------------------------------------------------------
# _resolve_listen_host
# ---------------------------------------------------------------------------


def test_default_host_is_pro_tailscale_ip_not_all_interfaces():
    assert wrapper._resolve_listen_host({}) == "100.107.22.111"
    assert wrapper.DEFAULT_LISTEN_HOST != "0.0.0.0"


def test_env_override_is_honored():
    assert wrapper._resolve_listen_host(
        {"PROFILE_MONITOR_LISTEN_HOST": "100.99.1.2"}
    ) == "100.99.1.2"


@pytest.mark.parametrize("host", ["0.0.0.0", ""])
def test_all_interfaces_default_is_refused(host):
    """GUILT: an explicit 0.0.0.0/"" must exit non-zero, not silently bind."""
    with pytest.raises(SystemExit) as exc_info:
        wrapper._resolve_listen_host({"PROFILE_MONITOR_LISTEN_HOST": host})
    assert exc_info.value.code != 0


def test_all_interfaces_with_explicit_optin_is_allowed():
    """INNOCENCE: the one-line opt-in must actually open the gate."""
    host = wrapper._resolve_listen_host(
        {
            "PROFILE_MONITOR_LISTEN_HOST": "0.0.0.0",
            "PROFILE_MONITOR_ALLOW_OPEN_BIND": "1",
        }
    )
    assert host == "0.0.0.0"


def test_optin_flag_alone_without_open_host_changes_nothing():
    """INNOCENCE: the opt-in flag must not affect a normal tailnet host."""
    host = wrapper._resolve_listen_host(
        {
            "PROFILE_MONITOR_LISTEN_HOST": "100.107.22.111",
            "PROFILE_MONITOR_ALLOW_OPEN_BIND": "1",
        }
    )
    assert host == "100.107.22.111"


# ---------------------------------------------------------------------------
# _serve_with_bind_retry
# ---------------------------------------------------------------------------


class _FakeServer:
    def __init__(self, addr, handler_cls):
        self.addr = addr
        self.handler_cls = handler_cls


def _addrnotavail() -> OSError:
    return OSError(errno.EADDRNOTAVAIL, "Can't assign requested address")


def test_bind_retry_succeeds_after_n_failures():
    calls = {"n": 0}
    sleeps: list[float] = []

    def flaky_server_cls(addr, handler_cls):
        calls["n"] += 1
        if calls["n"] < 4:
            raise _addrnotavail()
        return _FakeServer(addr, handler_cls)

    server = wrapper._serve_with_bind_retry(
        "100.107.22.111",
        9099,
        object,
        server_cls=flaky_server_cls,
        sleep=sleeps.append,
    )

    assert isinstance(server, _FakeServer)
    assert calls["n"] == 4
    # 3 failures before the success → 3 sleeps, capped exponential backoff.
    assert sleeps == [1, 2, 4]


def test_bind_retry_caps_backoff_at_max_seconds():
    calls = {"n": 0}
    sleeps: list[float] = []
    failures_before_success = 8

    def flaky_server_cls(addr, handler_cls):
        calls["n"] += 1
        if calls["n"] <= failures_before_success:
            raise _addrnotavail()
        return _FakeServer(addr, handler_cls)

    wrapper._serve_with_bind_retry(
        "100.107.22.111",
        9099,
        object,
        server_cls=flaky_server_cls,
        sleep=sleeps.append,
    )

    assert max(sleeps) <= wrapper.BIND_RETRY_MAX_SECONDS
    assert sleeps[-1] == wrapper.BIND_RETRY_MAX_SECONDS


def test_bind_retry_does_not_swallow_other_oserrors():
    """A non-EADDRNOTAVAIL OSError (e.g. EADDRINUSE) must propagate, never retry."""

    def server_cls(addr, handler_cls):
        raise OSError(errno.EADDRINUSE, "Address already in use")

    with pytest.raises(OSError) as exc_info:
        wrapper._serve_with_bind_retry(
            "100.107.22.111",
            9099,
            object,
            server_cls=server_cls,
            sleep=lambda _: None,
        )
    assert exc_info.value.errno == errno.EADDRINUSE


def test_bind_retry_succeeds_immediately_with_no_failures():
    sleeps: list[float] = []

    server = wrapper._serve_with_bind_retry(
        "100.107.22.111",
        9099,
        object,
        server_cls=_FakeServer,
        sleep=sleeps.append,
    )

    assert isinstance(server, _FakeServer)
    assert sleeps == []
