"""P03 finding F11 — the zero-spend path must be reachable from the DRIVER.

These tests deliberately exercise `scripts/wr3_render_episode.py` as a
subprocess, i.e. the exact command an operator types, rather than importing
`wr3_flowkit_client.submit_clip` directly. That distinction is the whole point
of the finding: before this patch `submit_clip` honoured `WR3_ZERO_SPEND`
perfectly and the driver still could not reach it, because `_health()` and
`setup_episode_context()` both dial the gateway first. A library-level test
would have stayed green through the entire defect.

Every test points the driver at a *refused* TCP port, so a green result cannot
be explained by a live FlowKit gateway on the machine running the suite. No
Flow/Veo job is submitted by any test here, and no credit can be spent: the
placeholder renderer is local ffmpeg only.

Hermeticity (W96 — tests must never write production state): HOME, the credit
ledger and the spend-decision log are all redirected into tmp_path, so the real
`~/.cache/wr3/credit-ledger.jsonl` is untouched even if an env var were dropped.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
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


def _refused_endpoint() -> str:
    """A loopback endpoint that is verified to REFUSE connections right now.

    Binding port 0 and closing hands back a port the kernel just confirmed
    free; we then prove it is refused rather than assuming it. If some other
    process grabs it in the gap, the probe says so and the test skips instead
    of silently testing nothing.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    probe = socket.socket()
    probe.settimeout(1.0)
    try:
        probe.connect(("127.0.0.1", port))
    except (ConnectionRefusedError, OSError):
        return f"http://127.0.0.1:{port}"
    finally:
        probe.close()
    pytest.skip(f"port {port} became occupied between bind and probe — cannot prove refusal")


def _episode(tmp_path: Path, *, name: str = "EP-F11", n_shots: int = 3) -> Path:
    ep = tmp_path / name
    ep.mkdir(parents=True)
    (ep / "shot-pack.json").write_text(json.dumps({
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
    }, indent=2))
    return ep


def _run(ep: Path, tmp_path: Path, *, zero_spend: bool) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["WR3_CREDIT_LEDGER"] = str(tmp_path / "ledger.jsonl")
    env["WR3_SPEND_DECISION_LOG"] = str(tmp_path / "decisions.jsonl")
    env["WR3_FLOWKIT_ENDPOINT"] = _refused_endpoint()
    env.pop("WR3_SPEND_DECISION", None)
    if zero_spend:
        env["WR3_ZERO_SPEND"] = "1"
    else:
        env.pop("WR3_ZERO_SPEND", None)
    return subprocess.run(
        [sys.executable, str(DRIVER), str(ep)],
        capture_output=True, text=True, env=env, timeout=300,
    )


@requires_ffmpeg
def test_driver_zero_spend_renders_every_shot_against_a_refused_gateway(tmp_path: Path) -> None:
    ep = _episode(tmp_path, n_shots=3)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr[-2000:]!r}"
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["status"] == "OK"
    assert out["rendered"] == 3
    assert out["failed"] == 0
    clips = sorted((ep / "clips").glob("*.mp4"))
    assert [c.name for c in clips] == ["01.mp4", "02.mp4", "03.mp4"]
    assert all(c.stat().st_size > 0 for c in clips)


def test_driver_without_zero_spend_cannot_reach_the_render_loop(tmp_path: Path) -> None:
    """Falsification for the test above.

    Same episode, same refused port, zero-spend OFF. If this passed too, the
    green above would prove nothing about the guard — it would just mean the
    driver never needed the gateway. It must fail at the health preflight.
    """
    ep = _episode(tmp_path, n_shots=3)
    res = _run(ep, tmp_path, zero_spend=False)
    assert res.returncode != 0
    assert not (ep / "clips").exists()
    combined = res.stdout + res.stderr
    assert "URLError" in combined or "Connection refused" in combined, combined[-2000:]


@requires_ffmpeg
def test_driver_zero_spend_spends_zero_credits_in_the_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    before = total_spend(read_records(ledger_path=ledger))
    ep = _episode(tmp_path, n_shots=2)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, res.stderr[-2000:]
    records = read_records(ledger_path=ledger)
    after = total_spend(records)
    assert before == 0 and after == 0, f"before={before} after={after}"
    assert len(records) == 2
    assert {r["mode"] for r in records} == {"placeholder"}
    assert all(r["credits"] == 0 for r in records)


@requires_ffmpeg
def test_driver_zero_spend_labels_the_render_report_placeholder(tmp_path: Path) -> None:
    """A placeholder report must not be mistakable for a real one on disk."""
    ep = _episode(tmp_path, n_shots=1)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, res.stderr[-2000:]
    report = json.loads((ep / "render-report.json").read_text())
    assert report["mode"] == "placeholder"
    assert report["total_cost_cr"] == 0
    assert report["rendered"][0]["veo_job_id"].startswith("placeholder:")
    assert json.loads(res.stdout.strip().splitlines()[-1])["mode"] == "placeholder"


@requires_ffmpeg
def test_driver_zero_spend_never_creates_a_flowkit_context(tmp_path: Path) -> None:
    """`setup_episode_context` writes `_flowkit_context.json` as its side effect.

    Its absence is the on-disk proof that the second network preflight was
    skipped too — not just the health probe.
    """
    ep = _episode(tmp_path, n_shots=1)
    res = _run(ep, tmp_path, zero_spend=True)
    assert res.returncode == 0, res.stderr[-2000:]
    assert not (ep / "_flowkit_context.json").exists()
