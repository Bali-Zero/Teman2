"""P03 finding F11 — the zero-spend path must be reachable from the DRIVER.

These tests exercise `scripts/wr3_render_episode.py` as a subprocess, i.e. the
exact command an operator types, rather than importing
`wr3_flowkit_client.submit_clip` directly. That distinction is the point of the
finding: before the patch `submit_clip` honoured `WR3_ZERO_SPEND` perfectly and
the driver still could not reach it, because `_health()` and
`setup_episode_context()` both dial the gateway first. A library-level test
would have stayed green through the entire defect.

Two gateway shapes are used, deliberately:

* a **refused port**, proven refused by the fixture itself, for "nothing is
  running at all";
* a **stub /health server** that answers `extension_connected: false` and
  COUNTS the requests it receives, for the two things a refused port cannot
  distinguish — that the health gate specifically fires (exit 2, not merely
  "some network call died"), and that a zero-spend run performs *zero* gateway
  requests rather than dialling and swallowing the error.

No Flow/Veo job is submitted by any test here and no credit can be spent: the
placeholder renderer is local ffmpeg only, and the stub serves `/health` alone.

Hermeticity (W96 — tests must never write production state): the child process
gets a WHITELISTED environment, not a copy of the parent's. That kills three
things at once — the real `~/.cache/wr3/*` (HOME is redirected), a developer's
stray `WR3_*` toggles, and `HTTP_PROXY`/`ALL_PROXY`, which `urllib` honours and
which would otherwise route the "verified refused" loopback endpoint through a
proxy and quietly void the fixture's central guarantee.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_SCRIPTS = Path(__file__).resolve().parents[1]
DRIVER = REPO_SCRIPTS / "wr3_render_episode.py"

sys.path.insert(0, str(REPO_SCRIPTS))

from wr3_credit_ledger import read_records, total_spend  # noqa: E402

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
requires_ffmpeg = pytest.mark.skipif(
    not FFMPEG_AVAILABLE,
    reason="ffmpeg not on PATH — the placeholder renderer needs the local binary",
)

# Inherited only because the child genuinely needs them: PATH to find ffmpeg,
# the locale vars for text decoding, TMPDIR for ffmpeg scratch. Everything else
# — proxies, WR3_* toggles, tokens — is deliberately absent.
_ENV_WHITELIST = ("PATH", "TMPDIR", "LANG", "LC_ALL")


def _refused_endpoint() -> str:
    """A loopback endpoint verified to refuse connections right now."""

    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    probe = socket.socket()
    probe.settimeout(1.0)
    try:
        probe.connect(("127.0.0.1", port))
    except (ConnectionRefusedError, OSError):
        return f"http://127.0.0.1:{port}"
    finally:
        probe.close()
    pytest.skip(f"port {port} became occupied — cannot prove the refused-gateway case")


class _StubGateway:
    """Counts every request it receives. `paths` is the audit trail."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.paths: list[str] = []
        self._lock = threading.Lock()

    def record(self, path: str) -> None:
        with self._lock:
            self.paths.append(path)


@contextmanager
def _stub_gateway(payload: dict):
    state = _StubGateway(payload)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            state.record(self.path)
            body = json.dumps(state.payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            state.record(self.path)
            self.send_response(500)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", state
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _episode(tmp_path: Path, *, name: str = "EP-F11", n_shots: int = 3) -> Path:
    ep = tmp_path / name
    ep.mkdir(parents=True)
    (ep / "shot-pack.json").write_text(
        json.dumps(
            {
                "resolution": "720x1280",
                "aspect_ratio": "9:16",
                "shots": [
                    {
                        "shot_id": f"s{i:03d}",
                        "prompt_positive": f"placeholder shot {i}",
                        "prompt_negative": "",
                        "duration_s": 8,
                    }
                    for i in range(1, n_shots + 1)
                ],
            },
            indent=2,
        )
    )
    return ep


def _run(
    ep: Path,
    tmp_path: Path,
    *,
    zero_spend: bool,
    endpoint: str | None = None,
    ledger: Path | None = None,
) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {k: os.environ[k] for k in _ENV_WHITELIST if k in os.environ}
    env["HOME"] = str(home)
    env["WR3_CREDIT_LEDGER"] = str(ledger or (tmp_path / "ledger.jsonl"))
    env["WR3_SPEND_DECISION_LOG"] = str(tmp_path / "decisions.jsonl")
    env["WR3_FLOWKIT_ENDPOINT"] = endpoint or _refused_endpoint()
    # urllib honours these; an inherited proxy would route the loopback
    # endpoint somewhere real and void the whole premise.
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    if zero_spend:
        env["WR3_ZERO_SPEND"] = "1"
    return subprocess.run(
        [sys.executable, str(DRIVER), str(ep)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )


# --------------------------------------------------------------------------
# The health gate is real — proven against a LIVE gateway, not a dead port
# --------------------------------------------------------------------------


def test_real_mode_rejects_noncanonical_gateway_before_health(
    tmp_path: Path,
) -> None:
    """A local service on a non-FlowKit port is not an allowed network target."""
    ep = _episode(tmp_path, n_shots=2)
    with _stub_gateway({"extension_connected": False, "status": "degraded"}) as (
        url,
        stub,
    ):
        res = _run(ep, tmp_path, zero_spend=False, endpoint=url)
    assert res.returncode == 6, f"stdout={res.stdout!r} stderr={res.stderr[-1500:]!r}"
    assert json.loads(res.stdout.strip())["reason"] == "episode_run_guard"
    assert stub.paths == [], stub.paths
    assert not (ep / "clips").exists()


@requires_ffmpeg
def test_zero_spend_bypasses_a_health_gate_that_is_demonstrably_firing(
    tmp_path: Path,
) -> None:
    """Same live gateway, same `extension_connected: false`, zero-spend ON.

    The previous test proves that gateway HALTS a real run. This one proves
    zero-spend renders anyway — and that it made ZERO requests, so the bypass
    is a genuine skip and not a dial whose error is swallowed.
    """
    ep = _episode(tmp_path, n_shots=2)
    with _stub_gateway({"extension_connected": False, "status": "degraded"}) as (
        url,
        stub,
    ):
        res = _run(ep, tmp_path, zero_spend=True, endpoint=url)
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr[-1500:]!r}"
    assert stub.paths == [], f"zero-spend run contacted the gateway: {stub.paths}"
    assert sorted(p.name for p in (ep / "clips").glob("*.mp4")) == ["01.mp4", "02.mp4"]


# --------------------------------------------------------------------------
# Nothing running at all
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_zero_spend_renders_every_shot_against_a_refused_gateway(
    tmp_path: Path,
) -> None:
    ep = _episode(tmp_path, n_shots=3)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr[-1500:]!r}"
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["status"] == "OK"
    assert out["rendered"] == 3
    assert out["failed"] == 0
    clips = sorted((ep / "clips").glob("*.mp4"))
    assert [c.name for c in clips] == ["01.mp4", "02.mp4", "03.mp4"]
    assert all(c.stat().st_size > 0 for c in clips)


def test_without_zero_spend_a_refused_gateway_stops_the_run(tmp_path: Path) -> None:
    ep = _episode(tmp_path, n_shots=3)
    res = _run(ep, tmp_path, zero_spend=False)
    assert res.returncode != 0
    assert not (ep / "clips").exists()
    combined = res.stdout + res.stderr
    assert "FlowKit endpoint must be exactly loopback port 8100" in combined


# --------------------------------------------------------------------------
# Credits, labelling, and what must NOT appear on disk
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_zero_spend_spends_zero_credits_in_the_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    before = total_spend(read_records(ledger_path=ledger))
    ep = _episode(tmp_path, n_shots=2)
    res = _run(ep, tmp_path, zero_spend=True, ledger=ledger)
    assert res.returncode == 0, res.stderr[-1500:]
    records = read_records(ledger_path=ledger)
    after = total_spend(records)
    assert before == 0 and after == 0, f"before={before} after={after}"
    assert len(records) == 2
    assert {r["mode"] for r in records} == {"placeholder"}
    assert all(r["credits"] == 0 for r in records)


@requires_ffmpeg
def test_zero_spend_labels_the_render_report_placeholder(tmp_path: Path) -> None:
    """A placeholder report must not be mistakable for a real one on disk."""
    ep = _episode(tmp_path, n_shots=1)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, res.stderr[-1500:]
    report = json.loads((ep / "render-report.json").read_text())
    assert report["mode"] == "placeholder"
    assert report["status"] == "OK"
    assert report["total_cost_cr"] == 0
    assert report["rendered"][0]["veo_job_id"].startswith("placeholder:")
    assert json.loads(res.stdout.strip().splitlines()[-1])["mode"] == "placeholder"


@requires_ffmpeg
def test_a_new_run_never_leaves_a_previous_runs_report_in_place(tmp_path: Path) -> None:
    """Stale-report poisoning (cross-family refuter, Kimi K3).

    A shot whose id does not match `s<digits>` used to raise ValueError from
    OUTSIDE the retry loop's handler and kill the process before any report was
    written — leaving a previous run's `render-report.json` describing the new
    run's clips. Here the previous report claims a real 380-credit render; after
    the placeholder run it must claim neither.
    """
    ep = _episode(tmp_path, n_shots=2)
    stale = {
        "mode": "real",
        "total_cost_cr": 380,
        "status": "OK",
        "rendered": [{"shot_id": "s001", "veo_job_id": "veo-real-deadbeef"}],
        "failed": [],
        "extension_drop": False,
    }
    (ep / "render-report.json").write_text(json.dumps(stale))

    pack = json.loads((ep / "shot-pack.json").read_text())
    pack["shots"][1]["shot_id"] = "shot-2"  # "shot-2".lstrip("s") == "hot-2"
    (ep / "shot-pack.json").write_text(json.dumps(pack))

    res = _run(ep, tmp_path, zero_spend=True)
    report = json.loads((ep / "render-report.json").read_text())
    assert report["mode"] == "placeholder", "stale report survived the run"
    assert report["total_cost_cr"] == 0
    assert "veo-real-deadbeef" not in json.dumps(report)
    assert [f["shot_id"] for f in report["failed"]] == ["shot-2"]
    assert res.returncode == 1  # PARTIAL, not a traceback


@requires_ffmpeg
def test_the_stale_report_is_gone_before_the_run_finishes(tmp_path: Path) -> None:
    """The startup stamp, probed WHILE the run is in flight.

    The test above proves the malformed-shot crash is gone, so it exercises the
    fix and never the belt: the run ends normally and the FINAL write overwrites
    the stale report anyway. Removing the startup stamp leaves that test green.

    This one watches the file during the run. If a previous run's
    `"mode": "real"` report is still readable after the first clip lands, the
    belt is not there — that is the window in which an unenumerated crash (OOM,
    SIGKILL, full disk) would leave clips described by the wrong run.
    """
    ep = _episode(tmp_path, n_shots=4)
    stale = {
        "mode": "real",
        "total_cost_cr": 380,
        "status": "OK",
        "rendered": [{"shot_id": "s001", "veo_job_id": "veo-real-deadbeef"}],
        "failed": [],
        "extension_drop": False,
    }
    report_path = ep / "render-report.json"
    report_path.write_text(json.dumps(stale))

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {k: os.environ[k] for k in _ENV_WHITELIST if k in os.environ}
    env.update(
        {
            "HOME": str(home),
            "WR3_CREDIT_LEDGER": str(tmp_path / "ledger.jsonl"),
            "WR3_SPEND_DECISION_LOG": str(tmp_path / "decisions.jsonl"),
            "WR3_FLOWKIT_ENDPOINT": _refused_endpoint(),
            "NO_PROXY": "*",
            "no_proxy": "*",
            "WR3_ZERO_SPEND": "1",
        }
    )
    proc = subprocess.Popen(
        [sys.executable, str(DRIVER), str(ep)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    seen_incomplete = False
    try:
        deadline = time.monotonic() + 120
        while proc.poll() is None and time.monotonic() < deadline:
            try:
                mid = json.loads(report_path.read_text())
            except (OSError, json.JSONDecodeError):
                time.sleep(0.02)
                continue
            if mid.get("status") == "incomplete":
                assert mid["mode"] == "placeholder"
                assert "veo-real-deadbeef" not in json.dumps(mid)
                seen_incomplete = True
                break
            time.sleep(0.02)
    finally:
        proc.wait(timeout=120)
    assert seen_incomplete, (
        "the stale report was never replaced while the run was in flight — "
        "a crash before the final write would leave it describing the new clips"
    )


@requires_ffmpeg
def test_zero_spend_never_creates_a_flowkit_context(tmp_path: Path) -> None:
    """`_flowkit_context.json` is written by the DRIVER right after
    `setup_episode_context()` returns. Its absence is the on-disk proof that the
    second preflight branch was skipped too — not just the health probe.
    """
    ep = _episode(tmp_path, n_shots=1)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, res.stderr[-1500:]
    assert not (ep / "_flowkit_context.json").exists()
