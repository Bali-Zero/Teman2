"""Unit tests for the WR2 HTML render apply-worker + the engine vision fail-closed gate.

Pytest-collectable (mock-based, no real DB / Drive / chromium). The full DB-level
behavior of the _pg HTML-lane is covered in
tests/unit/services/canva_renderer_v2/test_pg.py.
"""

from __future__ import annotations

import tempfile
import urllib.request
from pathlib import Path

import pytest
from scripts.wr2_html_render_apply import _HeroServer, _normalize_heroes

# ── hero normalizer (#13) ────────────────────────────────────────────────────


def test_normalizer_serves_present_hero_and_rewrites_url():
    work = Path(tempfile.mkdtemp(prefix="wr2-norm-"))
    hero_dir = work / "heroes"
    hero_dir.mkdir(parents=True)
    src = work / "src.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0HEROBYTES")
    slides = [{"is_hero_image": True, "hero_image_path": str(src), "headline": "A"}]
    with _HeroServer(hero_dir) as server:
        norm = _normalize_heroes(slides, hero_dir, server)
        assert norm[0]["image_url"].startswith(f"http://127.0.0.1:{server.port}/")
        # the localhost URL serves exactly the source bytes
        got = urllib.request.urlopen(norm[0]["image_url"], timeout=5).read()
        assert got == src.read_bytes()
        assert list(hero_dir.glob("hero-01*"))


def test_normalizer_passes_through_non_hero_slide():
    work = Path(tempfile.mkdtemp(prefix="wr2-norm-"))
    hero_dir = work / "heroes"
    hero_dir.mkdir(parents=True)
    slides = [{"headline": "no hero here"}]
    with _HeroServer(hero_dir) as server:
        norm = _normalize_heroes(slides, hero_dir, server)
        assert "image_url" not in norm[0]


def test_normalizer_no_fake_url_for_missing_hero():
    """A hero slide whose hero_image_path is missing on disk must NOT get a URL — the
    renderer's hero gate then correctly fails it (we never ship a hero slide without
    its image)."""
    work = Path(tempfile.mkdtemp(prefix="wr2-norm-"))
    hero_dir = work / "heroes"
    hero_dir.mkdir(parents=True)
    slides = [{"is_hero_image": True, "hero_image_path": str(work / "does-not-exist.jpg")}]
    with _HeroServer(hero_dir) as server:
        norm = _normalize_heroes(slides, hero_dir, server)
        assert "image_url" not in norm[0]


# ── vision fail-closed (v4 condition E / GO#3 c1/c5) ─────────────────────────


def test_vision_critic_soft_pass_by_default(monkeypatch):
    from wr2_html_renderer import claude_vision

    monkeypatch.setattr(claude_vision, "_run_claude_json", lambda *a, **k: None)
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)
    png = Path(tempfile.mkdtemp()) / "x.png"
    png.write_bytes(b"PNG")
    c = claude_vision.claude_design_critic(png, {}, {})
    assert c.passed is True  # historical soft-pass when vision unavailable + env unset


def test_vision_critic_fail_closed_when_required(monkeypatch):
    from wr2_html_renderer import claude_vision

    monkeypatch.setattr(claude_vision, "_run_claude_json", lambda *a, **k: None)
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")
    png = Path(tempfile.mkdtemp()) / "x.png"
    png.write_bytes(b"PNG")
    c = claude_vision.claude_design_critic(png, {}, {})
    assert c.passed is False
    assert any("vision" in i.lower() for i in c.issues)


# ── 429 rate-limit resilience (2026-06-12: a transient quota window masqueraded
#    as "vision unavailable" and burned 3 attempts → render_failed on a healthy
#    draft) ──────────────────────────────────────────────────────────────────


def _fake_proc(returncode=0, stdout="", stderr=""):
    from types import SimpleNamespace
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_claude_json_raises_on_429_envelope(monkeypatch):
    """A CLI error envelope with api_error_status==429 (even rc!=0) is a transient
    rate-limit, distinct from a real outage — must raise VisionRateLimited."""
    import json as _json

    from wr2_html_renderer import claude_vision

    envelope = _json.dumps({"is_error": True, "api_error_status": 429,
                            "result": "You've hit your session limit · resets 2:40am"})
    monkeypatch.setattr(claude_vision.subprocess, "run",
                        lambda *a, **k: _fake_proc(returncode=1, stdout=envelope))
    with pytest.raises(claude_vision.VisionRateLimited):
        claude_vision._run_claude_json("p", {"type": "object"})


def test_run_claude_json_raises_on_session_limit_text(monkeypatch):
    from wr2_html_renderer import claude_vision

    monkeypatch.setattr(claude_vision.subprocess, "run",
                        lambda *a, **k: _fake_proc(returncode=1, stderr="Error: session limit reached"))
    with pytest.raises(claude_vision.VisionRateLimited):
        claude_vision._run_claude_json("p", {"type": "object"})


def test_run_claude_json_genuine_failure_returns_none_not_raise(monkeypatch):
    """A real non-429 failure (rc!=0, no limit text) stays the None/unavailable
    path — must NOT be reclassified as rate-limit."""
    from wr2_html_renderer import claude_vision

    monkeypatch.setattr(claude_vision.subprocess, "run",
                        lambda *a, **k: _fake_proc(returncode=1, stderr="boom: chromium crashed"))
    assert claude_vision._run_claude_json("p", {"type": "object"}) is None


def test_run_claude_json_promotes_numbered_oauth_slot_to_bare(monkeypatch):
    """BUGFIX 2026-06-30: the fleet ships the MAX OAuth token in numbered slots
    (CLAUDE_CODE_OAUTH_TOKEN_1/_2/_3); the `claude` CLI authenticates from the
    BARE CLAUDE_CODE_OAUTH_TOKEN. If the bare var is unset, the vision call must
    promote the first available numbered slot, else the CLI fails `Not logged in`
    and (under WR2_VISION_REQUIRED=1) sinks the whole carousel. Verify the env
    passed to subprocess.run carries the promoted bare token."""
    from wr2_html_renderer import claude_vision

    captured = {}

    def _capture(*a, **k):
        captured["env"] = k.get("env", {})
        return _fake_proc(returncode=0, stdout='{"structured_output": {}}')

    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN_1", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "slot-two-token")
    monkeypatch.setattr(claude_vision.subprocess, "run", _capture)

    claude_vision._run_claude_json("p", {"type": "object"})
    assert captured["env"].get("CLAUDE_CODE_OAUTH_TOKEN") == "slot-two-token", (
        "first available numbered slot must be promoted to the bare token"
    )


def test_run_claude_json_keeps_existing_bare_oauth_token(monkeypatch):
    """If the bare CLAUDE_CODE_OAUTH_TOKEN is already set, it must be respected —
    the numbered-slot promotion only fills an UNSET bare var, never overrides."""
    from wr2_html_renderer import claude_vision

    captured = {}

    def _capture(*a, **k):
        captured["env"] = k.get("env", {})
        return _fake_proc(returncode=0, stdout='{"structured_output": {}}')

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "bare-token")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "slot-one-token")
    monkeypatch.setattr(claude_vision.subprocess, "run", _capture)

    claude_vision._run_claude_json("p", {"type": "object"})
    assert captured["env"].get("CLAUDE_CODE_OAUTH_TOKEN") == "bare-token"


def test_run_claude_json_timeout_raises_transient(monkeypatch):
    """A subprocess timeout is endpoint latency, not a defect — must raise the
    transient VisionTimeout (no burned attempt), NOT return None (which would
    fail-closed crash a healthy draft)."""
    import subprocess as _sp

    from wr2_html_renderer import claude_vision

    def _boom(*a, **k):
        raise _sp.TimeoutExpired(cmd="claude", timeout=180)

    monkeypatch.setattr(claude_vision.subprocess, "run", _boom)
    with pytest.raises(claude_vision.VisionTimeout):
        claude_vision._run_claude_json("p", {"type": "object"})


def test_vision_timeout_is_a_transient(monkeypatch):
    """VisionTimeout and VisionRateLimited share the VisionTransient base so the
    worker's single handler covers both."""
    from wr2_html_renderer import claude_vision

    assert issubclass(claude_vision.VisionTimeout, claude_vision.VisionTransient)
    assert issubclass(claude_vision.VisionRateLimited, claude_vision.VisionTransient)


def test_run_claude_json_timeout_budget_from_env(monkeypatch):
    """The wall-clock budget defaults to 180s and is overridable via
    WR2_VISION_TIMEOUT_S (raised from the old hardcoded 120s)."""
    import subprocess as _sp

    from wr2_html_renderer import claude_vision

    captured = {}

    def _capture(cmd, *a, **k):
        captured["timeout"] = k.get("timeout")
        raise _sp.TimeoutExpired(cmd="claude", timeout=k.get("timeout"))

    monkeypatch.setattr(claude_vision.subprocess, "run", _capture)
    monkeypatch.delenv("WR2_VISION_TIMEOUT_S", raising=False)
    with pytest.raises(claude_vision.VisionTimeout):
        claude_vision._run_claude_json("p", {"type": "object"})
    assert captured["timeout"] == 180

    monkeypatch.setenv("WR2_VISION_TIMEOUT_S", "300")
    with pytest.raises(claude_vision.VisionTimeout):
        claude_vision._run_claude_json("p", {"type": "object"})
    assert captured["timeout"] == 300


def test_run_claude_json_pins_vision_model(monkeypatch):
    """Default pins claude-sonnet-4-6; WR2_VISION_MODEL overrides. (No --model
    before = CLI default, heavier → 120s timeouts + quota burn.)"""
    import json as _json

    from wr2_html_renderer import claude_vision

    captured = {}

    def _capture(cmd, *a, **k):
        captured["cmd"] = cmd
        return _fake_proc(returncode=0, stdout=_json.dumps({"structured_output": {"ok": True}}))

    monkeypatch.setattr(claude_vision.subprocess, "run", _capture)
    monkeypatch.delenv("WR2_VISION_MODEL", raising=False)
    claude_vision._run_claude_json("p", {"type": "object"})
    assert "--model" in captured["cmd"]
    assert "claude-sonnet-4-6" in captured["cmd"]

    monkeypatch.setenv("WR2_VISION_MODEL", "claude-opus-4-8")
    claude_vision._run_claude_json("p", {"type": "object"})
    assert "claude-opus-4-8" in captured["cmd"]


def test_design_critic_propagates_rate_limit_not_fail_closed(monkeypatch):
    """When the runner signals rate-limit, the critic must propagate it (the
    apply-worker treats it as transient), NOT collapse to the fail-closed
    'unavailable' Critique that the circuit breaker would burn an attempt on."""
    from wr2_html_renderer import claude_vision

    def _raise(*a, **k):
        raise claude_vision.VisionRateLimited("429")

    monkeypatch.setattr(claude_vision, "_run_claude_json", _raise)
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")
    png = Path(tempfile.mkdtemp()) / "x.png"
    png.write_bytes(b"PNG")
    with pytest.raises(claude_vision.VisionRateLimited):
        claude_vision.claude_design_critic(png, {}, {})


@pytest.mark.asyncio
async def test_apply_one_rate_limit_does_not_burn_attempt(monkeypatch):
    """INVARIANT: a 429 during render releases the lease back to
    drafts_imaged_checked WITHOUT writing _html_attempts and WITHOUT
    render_failed — the draft is retried next tick, no attempt consumed."""
    from unittest.mock import AsyncMock, MagicMock

    import scripts.wr2_html_render_apply as html

    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.close = AsyncMock()
    monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(
        html._pg, "acquire_html_lease_and_fetch",
        AsyncMock(return_value={"slides_json": {"slides": [{"headline": "H"}]}}),
    )
    monkeypatch.setattr(html, "_heartbeat_loop", AsyncMock())
    monkeypatch.setattr(html, "_normalize_heroes", lambda slides, *a, **k: slides)

    class _Srv:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(html, "_HeroServer", lambda *a, **k: _Srv())
    from wr2_html_renderer.claude_vision import VisionRateLimited, VisionTimeout
    # parametrize-free: prove BOTH transient kinds (429 + timeout) take the
    # no-burn path via the shared VisionTransient base.
    monkeypatch.setattr(
        html, "_render_carousel",
        AsyncMock(side_effect=VisionTimeout("vision call timed out after 180s")),
    )
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")
    assert issubclass(VisionRateLimited, html.VisionTransient)
    assert issubclass(VisionTimeout, html.VisionTransient)

    import uuid as _uuid
    did = _uuid.uuid4()
    result = await html._apply_one("postgres://x", did, "owner-1")

    assert result.startswith("rate_limited")
    # the release UPDATE must NOT touch the attempt counter and must NOT fail it
    sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "_html_attempts" not in sqls
    assert "render_failed" not in sqls
    assert "drafts_imaged_checked" in sqls


# ── render-failure circuit breaker: the attempt counter must INCREMENT and
#    eventually reach render_failed (2026-06-13 SCAR: the counter was stored in
#    slides_json — a JSONB ARRAY — so the read silently returned 0 and the
#    jsonb_set WRITE raised InvalidTextRepresentationError, crashing the
#    retry-release before the draft could be parked → reconciliation re-kicked it
#    forever. Fixed by a dedicated INTEGER column html_render_attempts, mig 228) ─


class _InvalidTextRepresentationError(Exception):
    """Stand-in for asyncpg.exceptions.InvalidTextRepresentationError — raised by
    the fake conn to reproduce the exact Postgres error the OLD jsonb_set-on-array
    write triggered (`path element at position 1 is not an integer`)."""


class _FakeRenderFailDB:
    """A minimal fake DB connection that emulates JUST enough Postgres semantics
    to make the BUGGY form crash and the FIXED form work:

      * a row with slides_json as a JSONB ARRAY (the real shape) + an integer
        html_render_attempts column (migration 228).
      * fetchval on the OLD read (slides_json->>'_html_attempts') would return
        NULL on an array; on the NEW read it returns the integer column.
      * execute on the OLD write (jsonb_set(slides_json, '{_html_attempts}', ...))
        RAISES (array path element is not an integer); on the NEW write it sets
        the integer column. A render_failed UPDATE flips the status.

    This is a true regression guard: revert _apply_one to the jsonb_set/array
    form and the retry-path execute raises here exactly as it did in prod.
    """

    def __init__(self, attempts: int = 0):
        self.attempts = attempts          # the html_render_attempts column value
        self.status = "rendering"
        self.executed: list[str] = []

    def is_closed(self):
        return False

    async def close(self):
        return None

    async def fetchval(self, sql, *args):
        s = " ".join(sql.split())
        if "html_render_attempts" in s:
            return self.attempts          # the fixed read
        if "_html_attempts" in s:
            # the OLD read against a JSONB ARRAY: ->> 'text-key' yields NULL
            return None
        return 0

    async def execute(self, sql, *args):
        s = " ".join(sql.split())
        self.executed.append(s)
        if "jsonb_set" in s and "_html_attempts" in s:
            # the OLD buggy write — Postgres rejects a non-integer array path
            raise _InvalidTextRepresentationError(
                'path element at position 1 is not an integer: "_html_attempts"'
            )
        if "html_render_attempts" in s:
            # the fixed write: SET html_render_attempts = $3
            self.attempts = args[2]
            self.status = "drafts_imaged_checked"
            return "UPDATE 1"
        if "render_failed" in s:
            self.status = "render_failed"
            return "UPDATE 1"
        return "UPDATE 1"


async def _run_apply_one_with_render_failure(monkeypatch, fake_conn, max_attempts="3"):
    """Drive _apply_one so the render raises a RuntimeError (the designer-loop
    convergence-failure path), using the supplied fake_conn for main_conn."""
    from unittest.mock import AsyncMock

    import scripts.wr2_html_render_apply as html

    # main_conn = fake_conn; hb_conn = throwaway mock (heartbeat is stubbed out)
    hb = AsyncMock()
    hb.close = AsyncMock()
    monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(side_effect=[fake_conn, hb]))
    monkeypatch.setattr(
        html._pg, "acquire_html_lease_and_fetch",
        AsyncMock(return_value={"slides_json": [{"headline": "H"}]}),  # ARRAY, the real shape
    )
    monkeypatch.setattr(html, "_heartbeat_loop", AsyncMock())
    monkeypatch.setattr(html, "_normalize_heroes", lambda slides, *a, **k: slides)

    class _Srv:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(html, "_HeroServer", lambda *a, **k: _Srv())
    # the render fails the convergence gate -> RuntimeError (transient render path)
    monkeypatch.setattr(
        html, "_render_carousel",
        AsyncMock(side_effect=RuntimeError("designer loop did not converge")),
    )
    monkeypatch.setattr(html, "_ops_alert", AsyncMock())
    monkeypatch.setenv("WR2_HTML_MAX_ATTEMPTS", max_attempts)
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)
    monkeypatch.delenv("WR2_HTML_SHADOW", raising=False)

    import uuid as _uuid
    return await html._apply_one("postgres://x", _uuid.uuid4(), "owner-1")


@pytest.mark.asyncio
async def test_apply_one_render_failure_increments_attempt_without_jsonb_crash(monkeypatch):
    """REGRESSION (2026-06-13): the retry-release UPDATE must execute WITHOUT
    raising InvalidTextRepresentationError, and must increment the dedicated
    INTEGER counter (not jsonb_set the slides_json array). The bug crashed this
    path and left the draft looping forever."""
    fake = _FakeRenderFailDB(attempts=0)
    result = await _run_apply_one_with_render_failure(monkeypatch, fake)

    # first failure of 3 → back to the queue for retry (NOT render_failed yet)
    assert result.startswith("retry:1:")
    assert fake.status == "drafts_imaged_checked"
    assert fake.attempts == 1  # counter actually incremented + persisted

    sqls = " ".join(fake.executed)
    # the fixed write uses the integer column; the buggy array form is gone
    assert "html_render_attempts" in sqls
    assert "jsonb_set" not in sqls
    assert "_html_attempts" not in sqls


@pytest.mark.asyncio
async def test_apply_one_attempt_counter_accumulates_to_render_failed(monkeypatch):
    """REGRESSION: across successive failures the counter accumulates (1→2→3) and
    at max_attempts the draft transitions to render_failed instead of looping
    forever. Pre-fix the read always returned 0 (array ->> text-key = NULL) so
    the draft NEVER reached the breaker."""
    # attempt 1: counter 0 → 1, retry
    f1 = _FakeRenderFailDB(attempts=0)
    r1 = await _run_apply_one_with_render_failure(monkeypatch, f1)
    assert r1.startswith("retry:1:") and f1.attempts == 1 and f1.status == "drafts_imaged_checked"

    # attempt 2: counter 1 → 2, still retry (max=3)
    f2 = _FakeRenderFailDB(attempts=1)
    r2 = await _run_apply_one_with_render_failure(monkeypatch, f2)
    assert r2.startswith("retry:2:") and f2.attempts == 2 and f2.status == "drafts_imaged_checked"

    # attempt 3: counter 1→... reaches max=3 → render_failed (terminal)
    f3 = _FakeRenderFailDB(attempts=2)
    r3 = await _run_apply_one_with_render_failure(monkeypatch, f3)
    assert r3.startswith("render_failed:")
    assert f3.status == "render_failed"
    # the terminal path does NOT touch the integer counter (just flips status)
    sqls = " ".join(f3.executed)
    assert "render_failed" in sqls
    assert "jsonb_set" not in sqls


# ── connection-resilience: the ~15 min render kills the idle main_conn; the
#    terminal write must reconnect (2026-06-12 SCAR: drafts stuck 'rendering'
#    forever because the post-render write crashed on a closed connection) ──────


@pytest.mark.asyncio
async def test_ensure_live_reconnects_when_closed(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import scripts.wr2_html_render_apply as html

    dead = MagicMock()
    dead.is_closed = MagicMock(return_value=True)
    fresh = MagicMock()
    connect = AsyncMock(return_value=fresh)
    monkeypatch.setattr(html.asyncpg, "connect", connect)

    out = await html._ensure_live(dead, "postgres://x")

    assert out is fresh
    connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_live_keeps_open_connection(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import scripts.wr2_html_render_apply as html

    live = MagicMock()
    live.is_closed = MagicMock(return_value=False)
    connect = AsyncMock()
    monkeypatch.setattr(html.asyncpg, "connect", connect)

    out = await html._ensure_live(live, "postgres://x")

    assert out is live
    connect.assert_not_awaited()  # no needless reconnect on a healthy conn


@pytest.mark.asyncio
async def test_apply_one_reconnects_before_terminal_write(monkeypatch):
    """INVARIANT: if main_conn died during the long render, the success path
    reconnects so the carousel reaches status='rendered' instead of crashing on
    a closed connection (which left it stuck in 'rendering')."""
    from unittest.mock import AsyncMock, MagicMock

    import scripts.wr2_html_render_apply as html

    dead = MagicMock(name="dead")
    dead.is_closed = MagicMock(return_value=True)   # closed by the proxy mid-render
    dead.execute = AsyncMock()
    dead.fetchval = AsyncMock(return_value=0)
    dead.close = AsyncMock()
    fresh = MagicMock(name="fresh")
    fresh.is_closed = MagicMock(return_value=False)
    fresh.execute = AsyncMock()
    fresh.fetchval = AsyncMock(return_value=0)
    fresh.close = AsyncMock()

    # first two connects (main_conn, hb_conn) → dead; any reconnect → fresh
    conns = [dead, dead, fresh, fresh]
    monkeypatch.setattr(html.asyncpg, "connect", AsyncMock(side_effect=conns))
    monkeypatch.setattr(
        html._pg, "acquire_html_lease_and_fetch",
        AsyncMock(return_value={"slides_json": {"slides": [{"headline": "H"}]}}),
    )
    monkeypatch.setattr(html, "_heartbeat_loop", AsyncMock())
    monkeypatch.setattr(html, "_normalize_heroes", lambda slides, *a, **k: slides)

    class _Srv:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(html, "_HeroServer", lambda *a, **k: _Srv())

    # render "succeeds": produce a PNG path the worker will glob
    async def _fake_render(draft_id, slides, work, vision_required):
        d = work / "carousel" / "slides"
        d.mkdir(parents=True, exist_ok=True)
        (d / "01.png").write_bytes(b"PNG")
        return d
    monkeypatch.setattr(html, "_render_carousel", _fake_render)
    monkeypatch.setattr(html, "_drive_upload_carousel", AsyncMock(return_value="https://drive/x"))
    monkeypatch.setattr(
        html._pg, "persist_html_result_and_enqueue_notifications",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(html, "_log_ledger_best_effort", AsyncMock())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)
    monkeypatch.delenv("WR2_HTML_SHADOW", raising=False)

    import uuid as _uuid
    persist = html._pg.persist_html_result_and_enqueue_notifications
    result = await html._apply_one("postgres://x", _uuid.uuid4(), "owner-1")

    assert result.startswith("rendered")
    # the persist (terminal write) ran on the RECONNECTED conn, not the dead one
    assert persist.await_args.args[0] is fresh


@pytest.mark.asyncio
async def test_designer_loop_converges_default_no_vision(monkeypatch):
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _P:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _P())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=None,
        use_vision=True,
        max_iters=2,
    )
    assert res.converged is True


def _tiny_png_writer():
    """A render_fn that writes a 1x1 PNG (the tests only need a file to exist)."""
    import base64

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    return render_fn


class _GeoFailInkAtEdge:
    """Geometry NEVER passes and ALWAYS proposes the same ineffective lever —
    exactly the slide-8 signature (ink at bottom edge, body shrink no-op)."""
    passed = False
    issues = ["ink at bottom edge (ratio=0.50) — possible text overflow"]
    levers = [{"lever": "shrink_font", "target": "body", "reason": "bottom overflow"}]
    score = 0.0
    tier = "geometry"


class _CheapPass:
    passed = True
    levers: list = []
    score = 1.0
    issues: list = []
    tier = "mock"


@pytest.mark.asyncio
async def test_designer_loop_cheap_noop_escalates_to_vision_not_failed(monkeypatch):
    """BUGFIX 2026-06-29 (Bug B): a cheap geometry lever that NEVER moves the
    verdict (shrink_font body for `ink at bottom edge` when the bottom ink is the
    LOGO, not the body) must NOT spin to max_iters → render_failed. It must defer
    the verdict to the WHOLE-SLIDE vision critic (which can see body/footer
    overflow), NOT blind-accept on legibility+headline-OCR (codex refuter
    REFUTED that variant: OCR only checks the headline, body could be clipped).

    Here the vision critic PASSES → the slide converges (vision saw the whole
    slide and approved). Repro of the killer: drafts 8e582ce0 / d2d308bf /
    9b923976 all died on slide 8 with ink-at-edge 0.50 constant, shrink_body
    1→2→3, legibility PASS + OCR 1.0, then render_failed (critiques=[]). ~5 days
    zero WR2 output — the cheap path never reached vision at all.
    """
    from wr2_html_renderer import designer_loop as dl

    class _VisionPass:
        passed = True
        issues: list = []
        levers: list = []
        readable = True
        tier = "vision"

    vision_calls = {"n": 0}

    def _vision(*a, **k):
        vision_calls["n"] += 1
        return _VisionPass()

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _GeoFailInkAtEdge())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _CheapPass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _CheapPass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=_tiny_png_writer(),
        out_dir=out,
        vision_critic=_vision,
        brand_verifier=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is True, "cheap no-op must escalate to vision, which here passes"
    assert vision_calls["n"] >= 1, "the vision critic MUST be consulted on a cheap no-op"
    # history must not double-append the escalated iter record
    escalated = [h for h in res.history if h.get("cheap_noop_escalated_to_vision")]
    assert len(escalated) == 1


@pytest.mark.asyncio
async def test_designer_loop_cheap_noop_no_vision_does_not_publish(monkeypatch):
    """Counterpart: if the cheap lever is a no-op AND there is NO vision critic to
    adjudicate the whole slide, the loop must NOT blind-accept — it escalates and
    does NOT converge (a residual we cannot verify is never published)."""
    from wr2_html_renderer import designer_loop as dl

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _GeoFailInkAtEdge())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _CheapPass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _CheapPass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=_tiny_png_writer(),
        out_dir=out,
        vision_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is False, "cheap no-op + no vision to adjudicate must NOT publish"


@pytest.mark.asyncio
async def test_designer_loop_fail_closed_when_vision_required(monkeypatch):
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _P:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _P())
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=None,
        use_vision=True,
        max_iters=2,
    )
    assert res.converged is False
    assert res.reason == "vision_required_but_unavailable"


# ── designer-loop deadlock + real rebalance_wrap lever (2026-06-09) ──────────


def test_apply_levers_folds_rebalance_wrap():
    """FIX#2b: rebalance_wrap is now a real, applicable lever (not excluded)."""
    from wr2_html_renderer.designer_loop import _apply_levers

    acc: dict = {}
    applied = _apply_levers(acc, [{"lever": "rebalance_wrap", "reason": "orphan"}])
    names = [lev.get("lever") for lev in applied]
    assert "rebalance_wrap" in names
    assert acc.get("_rebalance_wrap") is True


def test_apply_levers_rerender_still_not_folded():
    """Pure structural signals (rerender) remain NON-applied escalation signals."""
    from wr2_html_renderer.designer_loop import _apply_levers

    acc: dict = {}
    applied = _apply_levers(acc, [{"lever": "rerender", "reason": "near-empty"}])
    assert applied == []


def test_balance_headline_inserts_br_no_orphan():
    """_balance_headline wraps a long headline into lines via <br>, each within
    the RENDERED PIXEL-WIDTH budget (not char count) and with no orphan word."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    out = _balance_headline("KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT")
    assert "<br>" in out
    lines = out.split("<br>")
    assert len(lines) >= 2  # actually wrapped
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line too wide: {ln!r}"
        assert len(ln.split()) >= 2, f"orphan line: {ln!r}"
    # round-trips the words (only <br>s inserted, nothing dropped/reordered)
    assert out.replace("<br>", " ").split() == "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT".split()


def test_balance_headline_short_title_unchanged():
    """≤3 words: leave the headline alone (nothing to balance)."""
    from wr2_html_renderer.composer import _balance_headline

    assert _balance_headline("Clock Is Ticking") == "Clock Is Ticking"
    assert "<br>" not in _balance_headline("Two Words")


def test_balance_headline_idempotent_if_prewrapped():
    """A headline that already carries a <br> is left as-is."""
    from wr2_html_renderer.composer import _balance_headline

    pre = "KPK ARRESTS<br>A TOP MINISTER"
    assert _balance_headline(pre) == pre


def test_rebalance_wrap_only_applies_when_lever_set():
    """FIX#2c: _fill_placeholders only re-wraps the headline when the
    _rebalance_wrap lever is active in slide['_levers']."""
    from wr2_html_renderer.composer import _fill_placeholders

    html = "<h1>{{heading}}</h1>"
    slide = {"headline": "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT"}
    # no lever → no <br>
    out_off = _fill_placeholders(html, slide, hero_filename=None)
    assert "<br>" not in out_off
    # lever on → <br> present, rendered as a tag (not escaped)
    slide_on = {**slide, "_levers": {"_rebalance_wrap": True}}
    out_on = _fill_placeholders(html, slide_on, hero_filename=None)
    assert "<br>" in out_on
    assert "&lt;br&gt;" not in out_on  # not HTML-escaped


def test_text_anchor_removed_from_allowed_levers():
    """FIX#2a: text_anchor is a zombie (no CSS side) — gone from the vocabulary."""
    from wr2_html_renderer.claude_vision import _ALLOWED_LEVERS

    assert "text_anchor" not in _ALLOWED_LEVERS
    assert "rebalance_wrap" in _ALLOWED_LEVERS  # still a real lever


def test_legibility_levers_constant():
    """The pure-legibility lever set: scrim/stroke/shrink + grow (the symmetric
    grow_font partner added 2026-06-10)."""
    from wr2_html_renderer.designer_loop import _LEGIBILITY_LEVERS

    assert _LEGIBILITY_LEVERS == {"scrim_opacity", "text_stroke", "shrink_font", "grow_font"}


# ── saliency-placement is SOFT when contrast passes (2026-06-12 SCAR: a busy
#    background band blocked a legible slide forever — busyness measured on the
#    raw hero ignores the scrim, and the reposition remedy is disabled) ─────────


def _mk_png(tmp):
    p = Path(tmp) / "iter.png"
    p.write_bytes(b"PNG")
    return p


def test_legibility_busy_band_is_soft_when_contrast_passes(monkeypatch, tmp_path):
    """Hero text on a busier-than-calmest band but with PASSING contrast must NOT
    fail the gate — the text is legible, scrim mitigates the busy bg, and the
    only real remedy (reposition) is disabled. The note is still surfaced."""
    from wr2_html_renderer import designer_loop as dl

    monkeypatch.setattr(dl, "text_region_contrast", lambda *a, **k: 12.6)  # ≫ AAA 7.0
    monkeypatch.setattr(dl, "calmest_band", lambda *a, **k: (0, [0.00, 0.02, 0.05]))
    hero = tmp_path / "hero.jpg"
    hero.write_bytes(b"JPG")

    c = dl.critic_legibility(_mk_png(tmp_path), {"headline": "H"}, is_hero=True, hero_path=hero)

    assert c.passed is True
    assert any("busier than calmest" in i for i in c.issues)  # note still visible
    assert not c.levers  # nothing to pull — contrast is fine, reposition disabled


def test_legibility_busy_band_is_hard_when_contrast_fails(monkeypatch, tmp_path):
    """If contrast ALSO fails, the busy-band note is part of the hard problem and
    the in-place remedy ladder (scrim+stroke) is proposed; gate fails."""
    from wr2_html_renderer import designer_loop as dl

    monkeypatch.setattr(dl, "text_region_contrast", lambda *a, **k: 3.0)  # < AAA 7.0
    monkeypatch.setattr(dl, "calmest_band", lambda *a, **k: (0, [0.00, 0.02, 0.05]))
    hero = tmp_path / "hero.jpg"
    hero.write_bytes(b"JPG")

    c = dl.critic_legibility(_mk_png(tmp_path), {"headline": "H"}, is_hero=True, hero_path=hero)

    assert c.passed is False
    assert any("contrast" in i for i in c.issues)
    assert any(lev["lever"] == "scrim_opacity" for lev in c.levers)


def test_legibility_calm_band_passes_clean(monkeypatch, tmp_path):
    """Calm bottom band + good contrast → pass, no issues, no levers."""
    from wr2_html_renderer import designer_loop as dl

    monkeypatch.setattr(dl, "text_region_contrast", lambda *a, **k: 13.0)
    monkeypatch.setattr(dl, "calmest_band", lambda *a, **k: (2, [0.05, 0.04, 0.01]))
    hero = tmp_path / "hero.jpg"
    hero.write_bytes(b"JPG")

    c = dl.critic_legibility(_mk_png(tmp_path), {"headline": "H"}, is_hero=True, hero_path=hero)

    assert c.passed is True
    assert c.issues == []
    assert c.levers == []


@pytest.mark.asyncio
async def test_designer_loop_legibility_lever_not_killed_by_brand_reject(monkeypatch):
    """FIX#3: when the brand verifier rejects for a NON-legibility reason but the
    only applied lever is pure-legibility (scrim/stroke/shrink), the loop must
    NOT break — it commits the legibility change and keeps iterating."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    # cheap tiers always pass → we reach the vision tier every iteration
    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0, "brand": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            # iter 1: wants a pure-legibility lever (scrim) — applicable
            return dl.Critique(
                tier="vision",
                passed=False,
                issues=["text a touch low-contrast"],
                levers=[{"lever": "scrim_opacity", "delta": 0.15, "reason": "low contrast"}],
                score=0.5,
            )
        # iter 2+: now happy
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    def brand_verifier(png, slide, ctx):
        # rejects for a NON-text-legibility reason (palette) — OCR can't override
        # this, but the legibility-only override (FIX#3) must.
        calls["brand"] += 1
        return dl.Critique(tier="brand", passed=False, issues=["palette looks off to me"])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=brand_verifier,
        ocr_critic=None,  # disable OCR adjudication so only FIX#3 decides
        use_vision=True,
        max_iters=3,
    )
    # the legibility change was committed despite the brand reject, and the loop
    # went on to a second iteration where vision passed → converged.
    assert res.converged is True
    assert calls["vision"] >= 2  # did NOT break after the first reject
    # the committed scrim lever is reflected in the history (renamed override key)
    assert any(rec.get("brand_verify_inert_override") for rec in res.history)


@pytest.mark.asyncio
async def test_designer_loop_rebalance_wrap_not_killed_by_brand_reject(monkeypatch):
    """Brand-inert override (fire-test residual): when the verifier rejects for a
    NON-inert reason (hierarchy/logo) but the only applied levers are
    {rebalance_wrap, shrink_font} — both brand-inert (text re-wrap + font
    down-step) — the loop must NOT break. rebalance_wrap is now covered by
    _BRAND_INERT_LEVERS, not just _LEGIBILITY_LEVERS."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0, "brand": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            # iter 1: proposes the exact pair the fire-test hit (rebalance + shrink)
            return dl.Critique(
                tier="vision",
                passed=False,
                issues=["title leaves an orphan word"],
                levers=[
                    {"lever": "rebalance_wrap", "reason": "orphan word on last line"},
                    {"lever": "shrink_font", "target": "heading", "reason": "a touch dense"},
                ],
                score=0.5,
            )
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    def brand_verifier(png, slide, ctx):
        # rejects for a NON-inert reason (hierarchy/logo) — the brand-inert
        # override must still commit the rebalance+shrink change.
        calls["brand"] += 1
        return dl.Critique(tier="brand", passed=False, issues=["hierarchy unclear; logo too small"])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Top"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=brand_verifier,
        ocr_critic=None,  # disable OCR adjudication so only the inert override decides
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is True
    assert calls["vision"] >= 2  # did NOT break after the first reject
    assert any(rec.get("brand_verify_inert_override") for rec in res.history)


def test_brand_inert_levers_includes_rebalance_wrap():
    """_BRAND_INERT_LEVERS = legibility levers + rebalance_wrap (text re-wrap)."""
    from wr2_html_renderer.designer_loop import _BRAND_INERT_LEVERS, _LEGIBILITY_LEVERS

    assert _BRAND_INERT_LEVERS == _LEGIBILITY_LEVERS | {"rebalance_wrap"}
    assert "rebalance_wrap" in _BRAND_INERT_LEVERS


# ── FIX#2b robust multi-line wrap + FIX#4 composition-debt accept (2026-06-10) ─


def test_balance_headline_real_title_pixel_width_no_orphan():
    """The real fire-test title wraps so EVERY line fits the cover box by RENDERED
    PIXEL WIDTH (84px uppercase) and NO line is a single-word orphan. At 84px the
    char-count model wrongly produced a 2-line split that overflowed the 960px
    box (→ the browser re-split → the "TOP" orphan); the pixel model yields a
    clean wrap (here 3 lines, all within box)."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    out = _balance_headline("The KITAS Bribe Trail Reaches the Top")
    lines = out.split("<br>")
    assert len(lines) >= 2  # actually wrapped
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan: {ln!r}"
    assert out.replace("<br>", " ").split() == "The KITAS Bribe Trail Reaches the Top".split()


def test_balance_headline_indonesia_visa_fee_no_orphan():
    """The 'Indonesia Visa Fee Jumps to IDR 3.5M' title (the FEE-orphan case):
    each line fits the box by pixel width, no orphan. The char model put
    'Indonesia Visa Fee' (968px) on one line — overflowing the box — and the
    browser re-split it into a FEE orphan."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    out = _balance_headline("Indonesia Visa Fee Jumps to IDR 3.5M")
    lines = out.split("<br>")
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan: {ln!r}"


def test_balance_headline_never_splits_a_word():
    """FIX#2b(a): a <br> is only ever inserted BETWEEN whole words, never inside
    one — every wrapped segment's tokens are intact words from the input."""
    from wr2_html_renderer.composer import _balance_headline

    title = "Supercalifragilistic Enforcement Crackdown Begins Now Across Bali"
    out = _balance_headline(title)
    in_words = set(title.split())
    out_words = out.replace("<br>", " ").split()
    # every emitted token is an original word (nothing was cut at a <br>)
    for w in out_words:
        assert w in in_words, f"word fragment produced: {w!r}"
    assert out_words == title.split()  # order + completeness


def test_balance_headline_parametrizable_box_width():
    """The pixel budget is parametrizable via box_width_px (e.g. a wider box or a
    smaller font). A very generous box fits the whole title on one line → no
    <br>; a tiny box forces more lines."""
    from wr2_html_renderer.composer import _balance_headline

    title = "The KITAS Bribe Trail Reaches the Top"
    assert "<br>" not in _balance_headline(title, box_width_px=100000)
    assert _balance_headline(title, box_width_px=300).count("<br>") >= 2


def test_estimate_text_width_px_calibrated():
    """The em-width estimate reproduces the real rendered width of
    'INDONESIA VISA FEE' (measured 937.3px at 84px uppercase) within ±10%."""
    from wr2_html_renderer.composer import _estimate_text_width_px

    est = _estimate_text_width_px("INDONESIA VISA FEE", font_px=84)
    assert 937.3 * 0.90 <= est <= 937.3 * 1.10, f"estimate {est:.1f}px off real 937.3px"
    # lowercase input is normalized to uppercase (the .heading transform) → same
    assert _estimate_text_width_px("indonesia visa fee", 84) == est


@pytest.mark.asyncio
async def test_designer_loop_accepts_best_render_on_composition_debt(monkeypatch):
    """FIX#4: vision rejects for a PURELY editorial reason (weak/generic hero) and
    proposes only 'rerender' (no CSS lever). The slide is legible + brand-clean,
    so the loop must ACCEPT the best render (converged=True) and flag the debt."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    # cheap tiers (geometry/legibility/ocr) pass → we reach vision
    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # rejects, but only for editorial composition + a rerender-only lever
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=[
                "hero photo is a generic dark interior, editorially weak for this story",
                "could breathe more — spacing feels tight",
            ],
            levers=[{"lever": "rerender", "reason": "swap the hero for a stronger image"}],
            score=0.6,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Top"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is True
    assert res.accepted_with_composition_debt is True
    assert res.reason == "accepted_with_composition_debt"
    # the editorial debt is recorded (visible, not silently dropped)
    assert any("editorially weak" in d for d in res.composition_debt)
    assert res.final_png is not None


@pytest.mark.asyncio
async def test_designer_loop_does_not_accept_on_real_legibility_residual(monkeypatch):
    """FIX#4 counter-proof: a HARD residual (a single-word orphan / unreadable
    title) is NOT composition debt — the loop must NOT converge (gate strict)."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # legibility defect (orphan word) + only a rerender lever → must NOT be
        # accepted as debt.
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=["single-word orphan 'TOP' on line 3 — the title is hard to read"],
            levers=[{"lever": "rerender", "reason": "structural"}],
            score=0.4,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=2,
    )
    assert res.converged is False
    assert res.accepted_with_composition_debt is False
    assert res.composition_debt == []


@pytest.mark.asyncio
async def test_designer_loop_idempotent_rebalance_falls_through_to_debt(monkeypatch):
    """NO-OP LEVER FIX: the vision keeps proposing rebalance_wrap, but the
    headline is already at its balanced pixel-optimum, so re-applying the lever
    yields the IDENTICAL render (proposed == levers_acc on iter 2). That no-op
    must NOT count as progress: with a SOFT (editorial) residual it falls through
    to accepted_with_composition_debt instead of spinning to max_iters."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"n": 0}

    def vision_critic(png, slide, ctx):
        # Every iteration: reject for a SOFT editorial reason AND re-propose the
        # SAME rebalance_wrap lever. After iter 1 commits _rebalance_wrap, iter 2
        # re-proposes it → proposed == levers_acc → no-op.
        calls["n"] += 1
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=[
                "hero photo is a generic dark interior, editorially weak for this story",
            ],
            levers=[{"lever": "rebalance_wrap", "reason": "balance the headline lines"}],
            score=0.6,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Very Top of It"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    # Iter 1 commits rebalance (progress), iter 2 is a no-op → SOFT residual →
    # accept as composition debt. Must NOT have spun all 3 iterations.
    assert res.converged is True
    assert res.accepted_with_composition_debt is True
    assert res.reason == "accepted_with_composition_debt"
    assert any("editorially weak" in d for d in res.composition_debt)
    # the no-op short-circuit fired before exhausting max_iters
    assert res.iterations <= 2
    assert calls["n"] <= 2


@pytest.mark.asyncio
async def test_designer_loop_progressive_rebalance_is_not_premature_debt(monkeypatch):
    """CAUTION: a rebalance_wrap on a NOT-yet-balanced title is REAL progress
    (proposed != levers_acc on iter 1) and must NOT be downgraded to no-op. Here
    the lever lands on iter 1 and the next vision pass converges via PASS — the
    loop must NOT short-circuit into composition-debt on the very first
    (progressive) application."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    seq = {"n": 0}

    def vision_critic(png, slide, ctx):
        seq["n"] += 1
        if seq["n"] == 1:
            # first look: title needs a re-wrap → propose the lever (PROGRESS)
            return dl.Critique(
                tier="vision",
                passed=False,
                issues=["title leaves an awkward two-word tail"],
                levers=[{"lever": "rebalance_wrap", "reason": "balance the lines"}],
                score=0.7,
            )
        # after the re-wrap applied, the render now passes vision → converge
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "A Title That Needs A Rebalance To Read Well"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    # converged via a real vision PASS after the progressive rebalance — NOT via
    # the composition-debt fallback.
    assert res.converged is True
    assert res.accepted_with_composition_debt is False
    assert res.reason != "accepted_with_composition_debt"


@pytest.mark.asyncio
async def test_designer_loop_noop_lever_with_hard_residual_does_not_accept(monkeypatch):
    """CAUTION: a no-op (idempotent) rebalance does NOT excuse a HARD residual.
    If the lever is a no-op AND the residual is a real legibility defect (a
    single-word orphan), the loop must NOT converge — the gate stays strict."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # always re-propose the SAME rebalance_wrap (becomes a no-op on iter 2)
        # AND flag a HARD single-word orphan → must NOT be accepted as debt.
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=["single-word orphan 'TOP' stranded alone on the last line — unreadable"],
            levers=[{"lever": "rebalance_wrap", "reason": "balance the lines"}],
            score=0.4,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The Whole KITAS Bribe Trail Reaches The Top"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is False
    assert res.accepted_with_composition_debt is False
    assert res.composition_debt == []


@pytest.mark.asyncio
async def test_designer_loop_scrim_lever_is_always_progress_not_noop(monkeypatch):
    """SANITY: an accumulating lever (scrim_opacity, +delta each step) ALWAYS
    changes the lever state (proposed != levers_acc), so it must NEVER be
    misread as a no-op. With a HARD residual and a still-progressing scrim, the
    loop keeps iterating (and ultimately does not accept-as-debt) — proving the
    no-op signal isolates only truly-idempotent levers."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    seen_levers_before: list = []

    def vision_critic(png, slide, ctx):
        # always reject + propose scrim_opacity (accumulates delta → never a no-op);
        # the residual is HARD (categorical illegibility) so the loop stays strict
        # at max_iters and does NOT accept-as-debt (matches the docstring).
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=["text is unreadable / illegible over the photo"],
            levers=[{"lever": "scrim_opacity", "delta": 0.1, "reason": "low contrast"}],
            score=0.5,
        )

    async def render_fn(slide, png_path):
        # record the accumulated scrim each render — it must keep climbing
        seen_levers_before.append(slide.get("_levers", {}).get("scrim_opacity"))
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    # scrim never folds to a no-op → the loop iterated (made_progress stayed True),
    # so it did NOT short-circuit into composition-debt on iteration 2; and the
    # HARD residual keeps the strict gate at max_iters → no accept-as-debt either.
    assert res.accepted_with_composition_debt is False
    # the scrim actually accumulated across renders (distinct, climbing values)
    scrims = [v for v in seen_levers_before if v is not None]
    assert scrims == sorted(scrims)
    assert len(set(scrims)) >= 2


def test_classify_residual_issues():
    """Unit: the residual-issue classifier separates editorial debt from hard
    legibility/brand defects."""
    from wr2_html_renderer.designer_loop import (
        _classify_residual_issues,
        _is_composition_only_lever,
    )

    # pure composition
    has_hard, all_comp = _classify_residual_issues(["hero photo is generic / editorially weak"])
    assert has_hard is False and all_comp is True
    # hard legibility wins even when mixed with composition
    has_hard, all_comp = _classify_residual_issues(
        ["hero is weak", "the headline has an orphan word and is hard to read"]
    )
    assert has_hard is True and all_comp is False
    # brand drift is hard
    has_hard, _ = _classify_residual_issues(["the palette uses an off-brand blue"])
    assert has_hard is True
    # empty → all_composition=True (BUGFIX 2026-06-29 / Bug A): a critic returning
    # ZERO atomic defects is a CLEAN slide, the most acceptable case — not a
    # reject-without-reason. The old `(False, False)` seed (bool(issues)) sank
    # whole carousels whenever the residual list was empty. has_hard stays False.
    assert _classify_residual_issues([]) == (False, True)
    # a list of ONLY synthetic 'vision: …' summary markers (skipped, no atomic
    # claim) is likewise clean → all_composition=True.
    assert _classify_residual_issues(["vision: balanced/clean"]) == (False, True)
    # lever classifier
    assert _is_composition_only_lever({"rerender"}) is True
    assert _is_composition_only_lever({"rerender", "scrim_opacity"}) is False
    assert _is_composition_only_lever(set()) is False


def test_balance_headline_template_max_title_no_orphan():
    """A title at the template's upper word bound (≤12 words) still wraps with
    NO single-word orphan line and every line fits the box by pixel width."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    # a clean-pairing 10-word title (consecutive words pair within the box)
    title = "KPK Arrests Top Deputy Minister in a Major Graft Case"
    out = _balance_headline(title)
    lines = out.split("<br>")
    assert len(lines) >= 3  # genuinely long → several lines
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan line: {ln!r}"
    assert out.replace("<br>", " ").split() == title.split()


def test_balance_headline_never_overflows_box_even_if_orphan_unavoidable():
    """Invariant guarantee: regardless of input, NO line ever exceeds the pixel
    budget (the browser never re-wraps). A pathological over-long title may leave
    an orphan, but it must NEVER overflow — overflow is the bug we are killing."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    title = (
        "Indonesia Tightens Investor KITAS Rules After A Major Graft Scandal "
        "Rocks The Immigration Directorate Today"
    )
    out = _balance_headline(title)
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in out.split("<br>"):
        # a single word longer than the box is the only allowed exception (it
        # cannot be split); here no single word is that wide.
        assert _estimate_text_width_px(ln) <= budget, f"OVERFLOW: {ln!r}"  # nothing lost


def test_orphan_grading_two_word_tail_soft_one_word_hard():
    """FIX B: orphan grading is fine-grained.

    - a ≥2-word short tail on an ALREADY-balanced wrap (rebalance committed) is
      editorial rhythm → NOT hard (acceptable composition debt);
    - the SAME claim without a re-wrap attempt → HARD (fail-safe);
    - a genuine 1-word orphan → HARD even with rebalance committed."""
    from wr2_html_renderer.designer_loop import (
        _classify_residual_issues,
        _orphan_is_hard,
    )

    two_word_tail = "THE TOP sits alone on line 3 — 2 words vs 3 on lines above"
    one_word = "single-word orphan 'TOP' alone on its own line"

    # 2-word tail + rebalance applied → soft (composition, not hard)
    has_hard, all_comp = _classify_residual_issues([two_word_tail], rebalance_applied=True)
    assert has_hard is False, "a 2-word balanced tail must NOT be a hard reject"
    assert all_comp is True, "it should classify as editorial composition"

    # same claim WITHOUT a re-wrap → fail-safe HARD
    has_hard_norewrap, _ = _classify_residual_issues([two_word_tail], rebalance_applied=False)
    assert has_hard_norewrap is True, "without re-wrap any orphan claim stays HARD"

    # 1-word orphan stays HARD even with rebalance applied
    has_hard_one, _ = _classify_residual_issues([one_word], rebalance_applied=True)
    assert has_hard_one is True, "a 1-word orphan is illegibility — must stay HARD"

    # _orphan_is_hard direct contract
    assert _orphan_is_hard(two_word_tail.lower(), rebalance_applied=True) == (True, False)
    assert _orphan_is_hard(two_word_tail.lower(), rebalance_applied=False) == (True, True)
    assert _orphan_is_hard(one_word.lower(), rebalance_applied=True) == (True, True)
    # a non-orphan claim is not graded as an orphan at all
    assert _orphan_is_hard("hero photo feels generic", rebalance_applied=True) == (False, False)


@pytest.mark.asyncio
async def test_designer_loop_accepts_two_word_tail_after_rewrap(monkeypatch):
    """FIX A+B end-to-end: after _rebalance_wrap is committed, a residual vision
    reject whose only complaint is a ≥2-word short tail (editorial rhythm) +
    rerender-only lever is ACCEPTED as composition debt → converged=True."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            # iter 1: propose rebalance_wrap (brand-inert → committed via override)
            return dl.Critique(
                tier="vision",
                passed=False,
                issues=["title leaves an orphan word"],
                levers=[{"lever": "rebalance_wrap", "reason": "orphan"}],
                score=0.5,
            )
        # iter 2: only complaint left is a 2-word short tail (editorial rhythm)
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=[
                "'Reaches the Top' sits alone on line 2 — 2 words vs 4 on the line above, uneven visual rhythm"
            ],
            levers=[{"lever": "rerender", "reason": "could be tighter"}],
            score=0.7,
        )

    def brand_verifier(png, slide, ctx):
        # brand always clean; the inert override commits the rebalance regardless
        return dl.Critique(tier="brand", passed=True, issues=[])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Top"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=brand_verifier,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is True
    assert res.accepted_with_composition_debt is True
    assert any("rhythm" in d for d in res.composition_debt)


# ── grow_font lever: thumbnail-legible sub-headline min-size (2026-06-10) ──────


def test_apply_levers_folds_grow_font():
    """grow_font is a real, applicable lever, symmetric to shrink_font."""
    from wr2_html_renderer.designer_loop import _apply_levers

    acc: dict = {}
    applied = _apply_levers(acc, [{"lever": "grow_font", "target": "subhead", "reason": "tiny"}])
    assert "grow_font" in [lev.get("lever") for lev in applied]
    assert acc.get("grow_subhead") == 1
    # default target is subhead
    acc2: dict = {}
    _apply_levers(acc2, [{"lever": "grow_font"}])
    assert acc2.get("grow_subhead") == 1
    # accumulates per step
    _apply_levers(acc2, [{"lever": "grow_font"}])
    assert acc2.get("grow_subhead") == 2


def test_grow_font_in_lever_sets():
    """grow_font is in the allowed vocabulary AND the brand-inert/legibility sets
    (growing a too-small text toward legibility cannot drift the brand)."""
    from wr2_html_renderer.claude_vision import _ALLOWED_LEVERS
    from wr2_html_renderer.designer_loop import (
        _BRAND_INERT_LEVERS,
        _LEGIBILITY_LEVERS,
    )

    assert "grow_font" in _ALLOWED_LEVERS
    assert "grow_font" in _LEGIBILITY_LEVERS
    assert "grow_font" in _BRAND_INERT_LEVERS


def _grow_subhead_px(css: str) -> int | None:
    """Pull the absolute .subheading font-size (px) out of a lever CSS block."""
    import re

    m = re.search(r"\.subhead,\.subheading\{font-size:(\d+)px", css)
    return int(m.group(1)) if m else None


def _grow_heading_px(css: str) -> int | None:
    """Pull the absolute .heading font-size (px) out of a lever CSS block."""
    import re

    m = re.search(r"\.headline,\.heading,h1\{font-size:(\d+)px", css)
    return int(m.group(1)) if m else None


def test_levers_to_css_grow_font_floor_and_cap():
    """grow_font targets the sub-headline with an ABSOLUTE px size: step 1 lands
    on the floor and a high step is clamped to the cap, never above."""
    from wr2_html_renderer.composer import _GROW_CLAMP_PX, _levers_to_css

    min_px, cap_px = _GROW_CLAMP_PX["subhead"]
    css1 = _levers_to_css({"grow_subhead": 1})
    assert ".subhead" in css1  # targets the sub-headline element
    assert _grow_subhead_px(css1) == min_px  # step 1 == floor
    # a high step is clamped to the cap, never above
    assert _grow_subhead_px(_levers_to_css({"grow_subhead": 9})) == cap_px
    # no grow lever → no grow CSS at all
    assert _grow_subhead_px(_levers_to_css({"text_stroke": True})) is None


def test_grow_subhead_never_exceeds_title_no_hierarchy_inversion():
    """BUG #2 (hierarchy inversion): the sub-headline (kicker) grow must NEVER
    reach or exceed the cover title font-size — at ANY step. The kicker is an
    accessory tag; the title must stay the largest element. Measured at the CSS
    level here; pixel-verified in the E2E probe."""
    from wr2_html_renderer.composer import (
        _GROW_CLAMP_PX,
        _HEADING_BASE_PX,
        _levers_to_css,
    )

    sub_min, sub_cap = _GROW_CLAMP_PX["subhead"]
    # the cap itself is strictly below the cover title base
    assert sub_cap < _HEADING_BASE_PX, (
        f"subhead grow cap {sub_cap}px must stay below title {_HEADING_BASE_PX}px"
    )
    assert sub_min <= sub_cap
    # every grow step keeps the subhead below the title
    for n in (1, 2, 3, 5, 10, 20):
        px = _grow_subhead_px(_levers_to_css({"grow_subhead": n}))
        assert px < _HEADING_BASE_PX, f"grow_subhead={n} → {px}px ≥ title (inversion)"


def test_grow_heading_grows_title_and_stays_largest():
    """grow_font target=heading enlarges the TITLE above its base, and even when
    BOTH grow, the title stays larger than the kicker (hierarchy preserved)."""
    from wr2_html_renderer.composer import _HEADING_BASE_PX, _levers_to_css

    css = _levers_to_css({"grow_heading": 1})
    head_px = _grow_heading_px(css)
    assert head_px is not None and head_px >= _HEADING_BASE_PX
    # both grown at once: title still dominates the kicker
    both = _levers_to_css({"grow_heading": 1, "grow_subhead": 9})
    assert _grow_heading_px(both) > _grow_subhead_px(both)


def test_levers_to_css_grow_font_progresses_each_step():
    """REGRESSION (the (52,64)/calc(1em*) no-op bug): grow steps must RISE
    (non-decreasing, strictly rising at least once before the cap), never a flat
    constant. The subhead cap range is small, so it rises then plateaus at cap."""
    from wr2_html_renderer.composer import _GROW_CLAMP_PX, _levers_to_css

    min_px, cap_px = _GROW_CLAMP_PX["subhead"]
    sizes = [_grow_subhead_px(_levers_to_css({"grow_subhead": n})) for n in (1, 2, 3, 4)]
    assert sizes[0] == min_px  # step 1 is the floor
    assert sizes == sorted(sizes)  # non-decreasing
    assert sizes[-1] > sizes[0], f"never grew: {sizes}"  # rose at least once
    assert all(px <= cap_px for px in sizes)  # never above cap
    # a very high step is exactly the cap
    assert _grow_subhead_px(_levers_to_css({"grow_subhead": 20})) == cap_px
    # body grow (larger range) rises across consecutive steps too
    body_sizes = []
    for n in (1, 2, 3):
        import re

        css = _levers_to_css({"grow_body": n})
        m = re.search(r"font-size:(\d+)px", css)
        body_sizes.append(int(m.group(1)))
    assert body_sizes[1] > body_sizes[0] and body_sizes[2] > body_sizes[1]


@pytest.mark.asyncio
async def test_designer_loop_grow_font_repairs_small_subhead(monkeypatch):
    """The repair flow: vision flags an illegible (too-small) sub-headline and
    proposes grow_font; the loop APPLIES it (brand-clean), re-renders, and on the
    next pass the text is legible → converges. Illegibility is REPAIRED, not
    accepted as debt."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            return dl.Critique(
                tier="vision",
                passed=False,
                issues=["sub-headline is illegible at Instagram thumbnail scale"],
                levers=[{"lever": "grow_font", "target": "subhead", "reason": "too small to read"}],
                score=0.5,
            )
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    def brand_verifier(png, slide, ctx):
        return dl.Critique(tier="brand", passed=True, issues=[])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X", "subhead": "tiny sub"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=brand_verifier,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is True
    # grow_font was applied, NOT accepted as composition debt
    assert res.accepted_with_composition_debt is False
    assert any(rec.get("vision_levers_pulled") for rec in res.history)


@pytest.mark.asyncio
async def test_designer_loop_never_accepts_illegible_subhead_as_debt(monkeypatch):
    """Counter-proof: an illegible sub-headline with ONLY a rerender lever (no
    grow available to pull) must NEVER be accepted as composition debt — the gate
    stays strict (converged=False)."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # legibility defect but only a structural lever proposed → not CSS-fixable
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=["sub-headline is unreadable / illegible at thumbnail scale"],
            levers=[{"lever": "rerender", "reason": "structural"}],
            score=0.3,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X", "subhead": "tiny"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=2,
    )
    assert res.converged is False
    assert res.accepted_with_composition_debt is False


def test_fill_placeholders_schema_fallback_old_and_new():
    """BUG #3: _fill_placeholders reads BOTH schema variants — old Canva drafts
    (heading/subheading) and new drafts (headline/subhead) — so an old-schema
    cover is never rendered blank."""
    from wr2_html_renderer.composer import _fill_placeholders

    html = "<h1>{{heading}}</h1><div class='subheading'>{{subheading}}</div><p>{{body}}</p>"
    # OLD schema: heading/subheading/body present, headline/subhead absent
    out_old = _fill_placeholders(
        html,
        {"heading": "OLD TITLE", "subheading": "OLD KICKER", "body": "old body"},
        hero_filename=None,
    )
    assert "OLD TITLE" in out_old and "OLD KICKER" in out_old and "old body" in out_old
    assert "{{heading}}" not in out_old and "{{subheading}}" not in out_old
    # NEW schema still works
    out_new = _fill_placeholders(
        html,
        {"headline": "NEW TITLE", "subhead": "NEW KICKER", "body": "new body"},
        hero_filename=None,
    )
    assert "NEW TITLE" in out_new and "NEW KICKER" in out_new and "new body" in out_new


# ── classifier word-boundary + soft-exclusion (W68/W72/W73 class) 2026-06-10 ──


def test_classifier_editorial_conditional_claims_not_false_hard():
    """The 4 real verdict claims that the bare-substring classifier false-HARD'd
    must now classify as SOFT (editorial/conditional) so a correctly-rendered
    draft can converge. W68/W72/W73 discipline: don't clobber a correct output."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    # "wrap" inside an already-rebalanced 3-line stub complaint → editorial rhythm
    hh, ac = _classify_residual_issues(
        ["Title wrap produces a 3-line stub"], rebalance_applied=True
    )
    assert hh is False and ac is True
    # "color" as an accent SUGGESTION → not palette drift
    hh, ac = _classify_residual_issues(["Consider popping the datum in a brand accent color"])
    assert hh is False and ac is True
    # "legibility" in a CONDITIONAL claim ("may drop below") → hypothetical
    hh, ac = _classify_residual_issues(["Logo may drop below legibility on a busy hero"])
    assert hh is False and ac is True
    # critic AFFIRMS correct + "may be illegible" hedge → not an actual defect
    hh, ac = _classify_residual_issues(
        ["The eyebrow is the correct brand treatment but may be an illegible smear"]
    )
    assert hh is False and ac is True


def test_classifier_real_defects_stay_hard():
    """COUNTER-PROOFS: actual, categorical, blocking defects MUST stay HARD — the
    gate must not go soft. We never publish illegible/clipped/off-palette."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    # categorical illegibility (no may/might) → HARD
    assert _classify_residual_issues(["subhead is illegible at thumbnail scale"])[0] is True
    # actual clipping → HARD
    assert _classify_residual_issues(["the title is clipped at the right edge, cut off"])[0] is True
    # genuine 1-word orphan → HARD (even after a re-wrap)
    assert (
        _classify_residual_issues(
            ["single-word orphan TOP alone on line 3"], rebalance_applied=True
        )[0]
        is True
    )
    # real palette drift → HARD
    assert _classify_residual_issues(["off-brand color, not in palette"])[0] is True


def test_classifier_word_boundary_not_bare_substring():
    """The markers match on WORD BOUNDARY, so they do NOT fire inside longer
    words (the W73 bare-substring trap): "rewrap"/"discolor"/"legible" must not
    trip "wrap"/"color"/"illegible"-style HARD matches."""
    from wr2_html_renderer.designer_loop import _claim_is_hard, _contains_any_word

    # word-boundary helper basics
    assert _contains_any_word("the title is clipped", ("clipped",)) is True
    assert _contains_any_word("a rewrap of the line", ("wrap",)) is False
    assert _contains_any_word("off the edge of frame", ("off the edge",)) is True
    # _claim_is_hard: "legible" (positive) is NOT illegible → not hard
    assert _claim_is_hard("the headline is legible and crisp") is False
    # "discoloration" must not trip a bare "color" hard match
    assert _claim_is_hard("a faint discoloration in the photo background") is False
    # but a real categorical defect is hard
    assert _claim_is_hard("the text is unreadable") is True


def test_classifier_conditional_marker_downgrades_legibility():
    """A 'may/might/could' hedge in front of a legibility word downgrades it from
    HARD to editorial — but the SAME claim without the hedge stays HARD."""
    from wr2_html_renderer.designer_loop import _claim_is_hard

    assert _claim_is_hard("the subhead might be illegible at small sizes") is False
    assert _claim_is_hard("the subhead is illegible at small sizes") is True


def test_classifier_synthetic_vision_marker_does_not_block_soft_accept():
    """UNDER-MATCH FIX (W68/W72/W73 class, 3rd face): the Claude critic appends
    categorical summary markers ('vision: unbalanced/crammed', 'vision: text not
    easily readable') derived from its OWN boolean flags. They are meta-labels,
    not atomic defects. A single such marker must NOT veto an otherwise-SOFT
    residual: all_composition must stay True so the composition-debt accept can
    fire (the root cause of the 0/5 convergence rate)."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    soft_atomic = [
        "hero photo is a generic dark interior, editorially weak for this story",
        "could breathe more — spacing feels a touch tight",
    ]
    # the two synthetic markers that previously fell into the else branch
    for marker in ("vision: unbalanced/crammed", "vision: text not easily readable"):
        has_hard, all_comp = _classify_residual_issues(
            soft_atomic + [marker], rebalance_applied=True
        )
        assert has_hard is False, f"{marker!r} must not set has_hard"
        assert all_comp is True, f"{marker!r} must not block all_composition"
    # a residual whose ONLY signal is a synthetic 'vision: …' summary is itself
    # SOFT (the render already passed the cheap legibility tier) → accept as debt
    only_summary, only_comp = _classify_residual_issues(
        ["vision: text not easily readable"], rebalance_applied=True
    )
    assert only_summary is False
    assert only_comp is True


def test_classifier_synthetic_vision_marker_does_not_save_real_hard_defect():
    """COUNTER-PROOF: the 'vision: …' neutrality must NOT weaken has_hard. A REAL
    atomic legibility defect coexisting with a synthetic summary still blocks —
    the marker is neutral, the atomic claim carries the severity."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    has_hard, all_comp = _classify_residual_issues(
        ["the subhead is illegible at thumbnail size", "vision: text not easily readable"],
        rebalance_applied=True,
    )
    assert has_hard is True
    assert all_comp is False


def test_classifier_vision_required_failclosed_is_not_skipped():
    """COUNTER-PROOF: the fail-closed 'vision REQUIRED but unavailable…' string
    starts with 'vision ' (NO colon) — it is a genuine block, NOT a synthetic
    summary. It must NOT be skipped: it leaves all_composition=False so the loop
    does not accept an unverified render as debt."""
    from wr2_html_renderer.designer_loop import (
        _classify_residual_issues,
        _is_vision_summary_marker,
    )

    failclosed = "vision REQUIRED but unavailable — fail-closed (WR2_VISION_REQUIRED=1)"
    assert _is_vision_summary_marker(failclosed.lower()) is False
    has_hard, all_comp = _classify_residual_issues([failclosed], rebalance_applied=True)
    # not a composition marker, not an orphan, not conditional → falls to else →
    # all_composition stays False (the render is NOT safe to accept as debt).
    assert all_comp is False


def test_classifier_weak_hierarchy_marker_still_soft():
    """REGRESSION GUARD: 'vision: weak hierarchy' previously passed by ACCIDENT
    (it contains 'weak', a composition marker). After the fix it is skipped as a
    synthetic summary, so it must STILL be SOFT (all_composition True) — the
    behavior is preserved, now for the right reason."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    has_hard, all_comp = _classify_residual_issues(
        ["vision: weak hierarchy"], rebalance_applied=True
    )
    assert has_hard is False
    assert all_comp is True


@pytest.mark.asyncio
async def test_designer_loop_accepts_best_at_max_iters_on_soft_residual(monkeypatch):
    """ACCEPT-BEST AT MAX_ITERS: the (non-deterministic) vision keeps proposing
    INCREMENTAL editorial levers every iteration (scrim_opacity +delta →
    made_progress=True each iter), so the loop never reaches the
    made_progress=False accept branch and previously exhausted max_iters with a
    'max_iters reached' REJECT — even though the render is legible + brand-clean
    and the only residuals are editorial. This is the structural cause of the
    ~23% coin-flip convergence. After the fix, the loop accepts the best render
    as composition debt at the iteration-budget exit."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"n": 0}

    def vision_critic(png, slide, ctx):
        # reject EVERY iteration with a SOFT editorial residual + an INCREMENTAL
        # scrim_opacity lever (accumulates delta → proposed != levers_acc each
        # time → made_progress=True → commit+continue, never the accept branch).
        calls["n"] += 1
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=[
                "hero photo is a generic dark interior, editorially weak for this story",
                "vision: unbalanced/crammed",
            ],
            levers=[{"lever": "scrim_opacity", "delta": 0.1, "reason": "nudge contrast"}],
            score=0.6,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Very Top of It"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    # the loop ran the full budget (incremental lever every iter) but accepted at
    # the max_iters exit instead of a 'max_iters reached' reject.
    assert calls["n"] == 3
    assert res.converged is True
    assert res.accepted_with_composition_debt is True
    assert "max_iters" in res.reason
    assert any("editorially weak" in d for d in res.composition_debt)
    assert res.final_png is not None


@pytest.mark.asyncio
async def test_designer_loop_does_not_accept_at_max_iters_on_hard_residual(monkeypatch):
    """COUNTER-PROOF (HARD): if the LAST reject before max_iters carries a REAL
    HARD residual (categorical illegibility), the strict gate must hold — no
    accept-as-debt at max_iters, converged stays False. The accept-best is for
    SOFT residuals only."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # every reject carries a REAL HARD legibility defect (categorical) AND an
        # incremental lever → made_progress=True each iter → reaches max_iters
        # with a HARD residual → must NOT accept.
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=["the subhead is illegible at thumbnail size"],
            levers=[{"lever": "scrim_opacity", "delta": 0.1, "reason": "nudge contrast"}],
            score=0.4,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is False
    assert res.accepted_with_composition_debt is False
    assert res.composition_debt == []
    assert "max_iters" in res.reason


@pytest.mark.asyncio
async def test_designer_loop_early_converge_unchanged_by_max_iters_accept(monkeypatch):
    """COUNTER-PROOF (early converge): a vision PASS at iteration 1 still converges
    normally — the max_iters accept-best must not perturb the pre-budget paths."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.97)

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"},
        render_fn=render_fn,
        out_dir=out,
        vision_critic=vision_critic,
        brand_verifier=None,
        ocr_critic=None,
        use_vision=True,
        max_iters=3,
    )
    assert res.converged is True
    assert res.iterations == 1
    assert res.accepted_with_composition_debt is False
    assert "max_iters" not in (res.reason or "")


# ── F10-A2 Defect 1: headline number-orphan wrap ─────────────────────────────


def test_balance_headline_number_not_orphaned_at_end_of_line():
    """F10-A2 Defect 1: _balance_headline must NOT end a line on a bare numeral
    when there is a following line.  The load-bearing phrase "3 RULES CHANGED"
    must stay on one line -- splitting as "...VALID. 3" / "RULES CHANGED" breaks
    the editorial claim and was the concrete failure observed on the shadow cover."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    headline = "YOUR KITAP IS VALID. 3 RULES CHANGED."
    out = _balance_headline(headline)
    lines = out.split("<br>")
    # must have wrapped (headline is long enough)
    assert len(lines) >= 2, f"expected wrap, got single line: {out!r}"
    # no line may END on a bare numeral when there is a successor line
    import re

    bare_num = re.compile(r"^\d+\.?$")
    for i, ln in enumerate(lines[:-1]):  # all except the last
        last_word = ln.split()[-1] if ln.split() else ""
        assert not bare_num.match(last_word), (
            f"line {i} ends on bare numeral {last_word!r}: full wrap={out!r}"
        )
    # the phrase "3 RULES CHANGED" must appear together on one line
    found_together = any("3 RULES CHANGED" in ln.upper() for ln in lines)
    assert found_together, f'"3 RULES CHANGED" split across lines: {lines!r}'
    # pixel-budget and no-overflow invariant preserved
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
    # words round-trip
    assert out.replace("<br>", " ").split() == headline.split()


def test_balance_headline_number_orphan_not_created_for_other_titles():
    """Regression guard: existing well-formed titles that happen to contain a
    digit word elsewhere must NOT be broken by the new numeral-orphan pass."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    titles = [
        "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT",  # no numeral at all
        "Indonesia Visa Fee Jumps to IDR 3.5M",  # decimal -> not bare int
        "THE KITAS BRIBE TRAIL REACHES THE TOP",  # no numeral
        "BALI ZERO GUIDE 2026 KITAS RULES EXPLAINED FULLY",  # year in mid-title
    ]
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for title in titles:
        out = _balance_headline(title)
        for ln in out.split("<br>"):
            assert _estimate_text_width_px(ln) <= budget, f"title {title!r}: line overflows: {ln!r}"
        assert out.replace("<br>", " ").split() == title.split(), (
            f"words changed for {title!r}: {out!r}"
        )


# ── F10-A2 Defect 2: duplicate regulation citation (corner badge) ─────────────


def test_cover_materialize_regulation_rendered_once_not_twice():
    """F10-A2 Defect 2: materialize_slide_html for the cover-photo family must
    render regulation_code EXACTLY once (in the yellow subheading kicker slot),
    NOT also in the top-right corner badge.  The badge is a redundant, thumbnail-
    illegible duplication of the kicker content."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    # Minimal skeleton that reproduces the dual-citation structure
    COVER_SKELETON = """<!doctype html>
<html><head><link rel="stylesheet" href="../_base.css"></head>
<body>
  {{#if regulation_code}}<div class="regulation-badge">{{regulation_code}}</div>{{/if}}
  <div class="content">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
  </div>
</body></html>"""

    # subhead and regulation_code carry the SAME textual value (as happens on
    # the real KITAP cover: both refer to "Permenkumham 22/2023 + 11/2024").
    reg_value = "Permenkumham 22/2023 + 11/2024"
    slide = {
        "index": 1,
        "slide_type": "cover",
        "is_cover": True,
        "is_hero_image": True,
        "headline": "YOUR KITAP IS VALID. 3 RULES CHANGED.",
        "subhead": reg_value,  # yellow kicker shows the regulation
        "regulation_code": reg_value,  # badge MUST be suppressed on cover
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        slides_dir = Path(tmpdir) / "slides"
        slides_dir.mkdir()

        with (
            patch("wr2_html_renderer.composer._extract_skeleton", return_value=COVER_SKELETON),
        ):
            from wr2_html_renderer.composer import materialize_slide_html

            html_path, expect_hero = asyncio.run(
                materialize_slide_html(slide, slides_dir, index=1, total=9)
            )

        html = html_path.read_text()
        # 1. The badge div must be absent (it was the redundant duplicate)
        assert "regulation-badge" not in html, (
            f"regulation-badge div still present in cover HTML: {html[:600]}"
        )
        # 2. The {{#if}} template syntax must be fully resolved (no leftover)
        assert "{{#if" not in html and "{{/if}}" not in html, (
            "template conditional not fully resolved"
        )
        # 3. The regulation value must appear EXACTLY ONCE — via the subheading
        #    kicker, not duplicated in the now-stripped badge.
        count = html.count(reg_value)
        assert count == 1, (
            f"regulation_code rendered {count} times (expected 1 via kicker only). "
            f"HTML snippet: {html[:600]}"
        )
        # 4. The subheading (kicker) must be present and contain the regulation
        assert reg_value in html, "subheading kicker missing from cover HTML"


def test_cover_materialize_no_regulation_renders_cleanly():
    """F10-A2 Defect 2 edge case: a cover slide with NO regulation_code must
    render cleanly (no leftover empty badge element, no template placeholder
    visible in the output HTML)."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    COVER_SKELETON = """<!doctype html>
<html><head><link rel="stylesheet" href="../_base.css"></head>
<body>
  {{#if regulation_code}}<div class="regulation-badge">{{regulation_code}}</div>{{/if}}
  <div class="content">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
  </div>
</body></html>"""

    slide = {
        "index": 1,
        "is_cover": True,
        "is_hero_image": True,
        "headline": "BALI ZERO GUIDE 2026",
        "subhead": "WHAT YOU NEED TO KNOW",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        slides_dir = Path(tmpdir) / "slides"
        slides_dir.mkdir()

        with (
            patch("wr2_html_renderer.composer._extract_skeleton", return_value=COVER_SKELETON),
        ):
            from wr2_html_renderer.composer import materialize_slide_html

            html_path, _ = asyncio.run(materialize_slide_html(slide, slides_dir, index=1, total=9))

        html = html_path.read_text()
        assert "regulation-badge" not in html
        assert "{{regulation_code}}" not in html
        assert "{{#if" not in html
        assert "{{/if}}" not in html


# ── F10-A2 Option A: ALWAYS-ON deterministic number de-orphan (pixel-independent) ──

def test_deorphan_numbers_glues_bare_numeral_to_following_word():
    """The always-on de-orphan glues a bare numeral to its following word with a
    non-breaking space so the browser can NEVER strand it at a line end. This is
    pixel-independent (the F10 re-shadow proved a pixel-based de-orphan misses the
    orphan because the real browser wrap disagrees with our estimate)."""
    from wr2_html_renderer.composer import _deorphan_numbers_in_headline

    out = _deorphan_numbers_in_headline("YOUR KITAP IS VALID. 3 RULES CHANGED.")
    # "3" must be glued to "RULES" via &nbsp; — un-splittable by the browser
    assert "3&nbsp;RULES" in out, out
    # nothing else changed: same words, only the one space became &nbsp;
    assert out.replace("&nbsp;", " ").split() == "YOUR KITAP IS VALID. 3 RULES CHANGED.".split()
    # the load-bearing phrase is intact
    assert "3&nbsp;RULES CHANGED." in out


def test_deorphan_numbers_noop_when_no_bare_numeral():
    """A headline with no bare-numeral-before-word pattern is returned verbatim
    (no brand drift on the common case)."""
    from wr2_html_renderer.composer import _deorphan_numbers_in_headline

    for h in [
        "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT",   # no digits
        "Indonesia Visa Fee Jumps to IDR 3.5M",        # 3.5M is not a bare integer word
        "THE YEAR 2026",                               # trailing numeral, nothing after to glue
    ]:
        assert _deorphan_numbers_in_headline(h) == h, h


def test_deorphan_numbers_handles_leading_and_mid_numerals():
    """Leading ("10 NEW...") and mid-headline ("...2026 KITAS...") numerals are
    glued to their following word."""
    from wr2_html_renderer.composer import _deorphan_numbers_in_headline

    assert "10&nbsp;NEW" in _deorphan_numbers_in_headline("10 NEW RULES TAKE EFFECT")
    assert "11&nbsp;PERCENT" in _deorphan_numbers_in_headline("PROPERTY TAX IS 11 PERCENT NOW")


def test_deorphan_numbers_does_not_glue_across_a_br():
    """A numeral immediately followed by a <br> (not a space+word) is left alone —
    gluing across an explicit line break would be wrong."""
    from wr2_html_renderer.composer import _deorphan_numbers_in_headline

    out = _deorphan_numbers_in_headline("SOMETHING 3<br>RULES CHANGED")
    assert "&nbsp;" not in out
    assert out == "SOMETHING 3<br>RULES CHANGED"


def test_deorphan_numbers_composes_with_balance_headline():
    """When the lever ran first (full pixel rebalance with <br>s), the always-on
    de-orphan still glues the numeral to its noun on whatever line it landed."""
    from wr2_html_renderer.composer import _balance_headline, _deorphan_numbers_in_headline

    levered = _balance_headline("YOUR KITAP IS VALID. 3 RULES CHANGED.")
    out = _deorphan_numbers_in_headline(levered)
    assert "3&nbsp;RULES" in out
    # the <br> structure from the rebalance is preserved
    assert "<br>" in out


def test_cover_compose_always_deorphans_number_without_lever():
    """F10-A2 ROOT FIX: materialize_slide_html must apply the number de-orphan to
    a cover headline UNCONDITIONALLY — even when NO _rebalance_wrap lever is set
    (the re-shadow converged at iter 1, so the critic never asked for the lever,
    and the orphan survived). The rendered HTML must glue "3" to "RULES"."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    COVER_SKELETON = """<!doctype html>
<html><head><link rel="stylesheet" href="../_base.css"></head>
<body>
  <div class="content">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
  </div>
</body></html>"""

    # NOTE: no "_levers" key at all -> the lever path is NOT taken.
    slide = {
        "index": 1,
        "is_cover": True,
        "is_hero_image": True,
        "headline": "YOUR KITAP IS VALID. 3 RULES CHANGED.",
        "subhead": "PERMENKUMHAM 22/2023 + 11/2024",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        slides_dir = Path(tmpdir) / "slides"
        slides_dir.mkdir()
        with patch(
            "wr2_html_renderer.composer._extract_skeleton", return_value=COVER_SKELETON
        ):
            from wr2_html_renderer.composer import materialize_slide_html

            html_path, _ = asyncio.run(
                materialize_slide_html(slide, slides_dir, index=1, total=9)
            )
        html = html_path.read_text()
        # the orphan-killer ran even without the lever
        assert "3&nbsp;RULES" in html, (
            f"number de-orphan did NOT run at compose time: {html[:600]}"
        )


# ── F10-A2 Option B: SENTENCE-AWARE cover-headline wrap (measured, multi-title) ──

def _heading_lines(out: str) -> list[str]:
    """Split a wrapped headline into its rendered lines (strip &nbsp; back to a
    space so we compare on visible text)."""
    return [ln.replace("&nbsp;", " ") for ln in out.split("<br>")]


def test_sentence_wrap_kitap_keeps_load_bearing_sentence_on_one_line():
    """THE case: "YOUR KITAP IS VALID. 3 RULES CHANGED." must break at the
    sentence boundary so "3 RULES CHANGED." sits on ONE line, with a bounded
    shrink (not below the 60px floor)."""
    from wr2_html_renderer.composer import (
        _HEADLINE_FIT_FLOOR_PX,
        _wrap_headline_sentence_aware,
    )

    out, font = _wrap_headline_sentence_aware("YOUR KITAP IS VALID. 3 RULES CHANGED.")
    lines = _heading_lines(out)
    assert lines == ["YOUR KITAP IS VALID.", "3 RULES CHANGED."], lines
    assert font is not None and font >= _HEADLINE_FIT_FLOOR_PX, font
    assert font < 84, f"expected a bounded shrink, got base font {font}"


def test_sentence_wrap_single_short_sentence_fits_or_wraps_no_split_above_floor():
    """A single short sentence that does not fit at base on one line falls back to
    pixel-wrap at the floor (graceful degradation) — never a sub-floor font."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _HEADLINE_FIT_FLOOR_PX,
        _WRAP_SAFETY,
        _estimate_text_width_px,
        _wrap_headline_sentence_aware,
    )

    out, font = _wrap_headline_sentence_aware("INDONESIA VISA FEE GOES UP.")
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    measure_font = font if font is not None else 84
    assert measure_font >= _HEADLINE_FIT_FLOOR_PX, measure_font
    for ln in _heading_lines(out):
        assert _estimate_text_width_px(ln, measure_font) <= budget, (ln, measure_font)


def test_sentence_wrap_three_short_sentences_one_per_line_at_base():
    """Three short sentences each fit at base font → one sentence per line, no
    shrink (font None)."""
    from wr2_html_renderer.composer import _wrap_headline_sentence_aware

    out, font = _wrap_headline_sentence_aware("PT PMA SETUP. 5 STEPS. 1 MONTH.")
    lines = _heading_lines(out)
    assert lines == ["PT PMA SETUP.", "5 STEPS.", "1 MONTH."], lines
    assert font is None, f"three short sentences should fit at base, got font {font}"


def test_sentence_wrap_one_long_sentence_bounded_shrink_or_wrap_never_mid_split_above_floor():
    """A single long sentence with no internal boundary must NOT be split into
    fake sentences; it bounded-shrinks then pixel-wraps at the floor — never
    overflows, never sub-floor."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _HEADLINE_FIT_FLOOR_PX,
        _WRAP_SAFETY,
        _estimate_text_width_px,
        _wrap_headline_sentence_aware,
    )

    title = "NEW TAX RULE FOR FOREIGN PROPERTY OWNERS IN BALI."
    out, font = _wrap_headline_sentence_aware(title)
    measure_font = font if font is not None else 84
    assert measure_font >= _HEADLINE_FIT_FLOOR_PX, measure_font
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in _heading_lines(out):
        assert _estimate_text_width_px(ln, measure_font) <= budget, (ln, measure_font)
    # words round-trip (nothing dropped/reordered)
    assert " ".join(_heading_lines(out)).split() == title.split()


def test_sentence_wrap_short_title_that_fits_is_unchanged():
    """A short headline with no sentence boundary that ALREADY FITS at base is
    returned verbatim with no font override (zero brand drift)."""
    from wr2_html_renderer.composer import _wrap_headline_sentence_aware

    # genuinely short + narrow → fits at 84 → untouched
    for t in ("TWO WORDS", "VISA RULE", "NEW KITAS"):
        out, font = _wrap_headline_sentence_aware(t)
        assert out == t, (t, out)
        assert font is None, (t, font)


def test_sentence_wrap_short_but_wide_title_bounded_shrinks_not_overflow():
    """A short (<=3-word) headline that OVERFLOWS at base is NOT left to overflow
    just because it is short — it bounded-shrinks to fit (>= floor), staying on
    one line (the "KBLI 55130 EXPLAINED" 1020px-at-84 case)."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _HEADLINE_FIT_FLOOR_PX,
        _WRAP_SAFETY,
        _estimate_text_width_px,
        _wrap_headline_sentence_aware,
    )

    out, font = _wrap_headline_sentence_aware("KBLI 55130 EXPLAINED")
    assert font is not None and _HEADLINE_FIT_FLOOR_PX <= font < 84, font
    assert "<br>" not in out  # still one line, just smaller
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    assert _estimate_text_width_px(out, font) <= budget


def test_sentence_wrap_very_long_single_sentence_hits_floor_and_pixel_wraps():
    """Graceful-degradation proof: a very long single sentence cannot fit at the
    floor on one line → it pixel-wraps at the floor font across multiple lines,
    every line within budget, font pinned at the floor (never below)."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _HEADLINE_FIT_FLOOR_PX,
        _WRAP_SAFETY,
        _estimate_text_width_px,
        _wrap_headline_sentence_aware,
    )

    title = (
        "INDONESIA TIGHTENS INVESTOR KITAS RULES AFTER A MAJOR GRAFT SCANDAL "
        "ROCKS THE IMMIGRATION DIRECTORATE TODAY."
    )
    out, font = _wrap_headline_sentence_aware(title)
    assert font == _HEADLINE_FIT_FLOOR_PX, f"expected floor pin, got {font}"
    lines = _heading_lines(out)
    assert len(lines) >= 3, lines  # genuinely multi-line
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln, _HEADLINE_FIT_FLOOR_PX) <= budget, ln
    assert " ".join(lines).split() == title.split()


def test_sentence_wrap_battery_no_overflow_no_subfloor():
    """Battery invariant across all shapes: NO line overflows the box budget at
    the chosen font, and the chosen font is NEVER below the floor."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _HEADLINE_FIT_FLOOR_PX,
        _WRAP_SAFETY,
        _estimate_text_width_px,
        _wrap_headline_sentence_aware,
    )

    titles = [
        "YOUR KITAP IS VALID. 3 RULES CHANGED.",
        "INDONESIA VISA FEE GOES UP.",
        "PT PMA SETUP. 5 STEPS. 1 MONTH.",
        "NEW TAX RULE FOR FOREIGN PROPERTY OWNERS IN BALI.",
        "KBLI 55130 EXPLAINED",
        "INDONESIA TIGHTENS INVESTOR KITAS RULES AFTER A MAJOR GRAFT SCANDAL "
        "ROCKS THE IMMIGRATION DIRECTORATE TODAY.",
    ]
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for t in titles:
        out, font = _wrap_headline_sentence_aware(t)
        mf = font if font is not None else 84
        assert mf >= _HEADLINE_FIT_FLOOR_PX, (t, mf)
        # The no-overflow-at-font invariant holds for every line the wrap
        # PRODUCED (i.e. once it inserted at least one <br> OR chose a shrink
        # font). A title returned verbatim-and-flat (no <br>, font None) is the
        # "unchanged short title" case: the wrap deliberately defers its wrapping
        # to the browser (same as the legacy <=3-word _balance_headline no-op), so
        # the whole-string width is not a single-line constraint here.
        if "<br>" in out or font is not None:
            for ln in _heading_lines(out):
                assert _estimate_text_width_px(ln, mf) <= budget, (t, ln, mf)
        # never drop/reorder words (always holds)
        assert " ".join(_heading_lines(out)).split() == t.split(), t


def test_cover_compose_injects_headline_font_when_shrunk():
    """End-to-end through materialize_slide_html: a cover whose sentence-wrap
    needs a shrink injects a `.heading{font-size:<px>}` override, and the
    load-bearing sentence sits on its own line."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    COVER_SKELETON = """<!doctype html>
<html><head><link rel="stylesheet" href="../_base.css"></head>
<body>
  <div class="content">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
  </div>
</body></html>"""

    slide = {
        "index": 1, "is_cover": True, "is_hero_image": True,
        "headline": "YOUR KITAP IS VALID. 3 RULES CHANGED.",
        "subhead": "PERMENKUMHAM 22/2023 + 11/2024",
    }
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp) / "slides"
        sd.mkdir()
        with patch(
            "wr2_html_renderer.composer._extract_skeleton", return_value=COVER_SKELETON
        ):
            from wr2_html_renderer.composer import materialize_slide_html

            hp, _ = asyncio.run(materialize_slide_html(slide, sd, index=1, total=9))
        html = hp.read_text()
        import re

        # the heading carries the sentence break
        m = re.search(r'<div class="heading">(.*?)</div>', html, re.DOTALL)
        assert m is not None
        lines = [ln.replace("&nbsp;", " ") for ln in m.group(1).split("<br>")]
        assert lines == ["YOUR KITAP IS VALID.", "3 RULES CHANGED."], lines
        # a font-fit override was injected, in [floor, 84)
        fm = re.search(r'data-headline-fit.*?font-size:(\d+)px', html, re.DOTALL)
        assert fm is not None, "no headline-fit font override injected"
        assert 60 <= int(fm.group(1)) < 84, fm.group(1)


def test_non_cover_slide_no_sentence_wrap():
    """A non-cover family must NOT get the sentence-aware wrap / font override
    (the feature is cover-scoped)."""
    from wr2_html_renderer.composer import _fill_placeholders

    html = '<html><head></head><body><div class="heading">{{heading}}</div></body></html>'
    slide = {"headline": "SOME BODY SLIDE TITLE. SECOND SENTENCE HERE."}
    out = _fill_placeholders(html, slide, hero_filename=None, cover_family=False)
    # no font-fit override, no sentence <br> inserted by the cover-only path
    assert "data-headline-fit" not in out


# ── HARD-reject observability (post-mortem of 2026-06-11: 3 drafts render_failed
#    with zero trace of WHICH critiques rejected them) ────────────────────────────


@pytest.mark.asyncio
async def test_designer_loop_hard_residual_logs_the_critiques(monkeypatch, caplog):
    """When the loop keeps best but does NOT converge because of a HARD residual,
    the critiques MUST reach the WARNING log — symmetric to the composition-debt
    accept branch which already logs. Without this, a render_failed leaves zero
    trace of WHY the gate rejected."""
    import base64
    import logging

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        return dl.Critique(
            tier="vision",
            passed=False,
            issues=["single-word orphan 'TOP' on line 3 — the title is hard to read"],
            levers=[{"lever": "rerender", "reason": "structural"}],
            score=0.4,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
        )

    out = Path(tempfile.mkdtemp())
    with caplog.at_level(logging.WARNING):
        res = await dl.run_designer_loop(
            slide={"headline": "X"},
            render_fn=render_fn,
            out_dir=out,
            vision_critic=vision_critic,
            brand_verifier=None,
            ocr_critic=None,
            use_vision=True,
            max_iters=2,
        )
    assert res.converged is False
    assert any("single-word orphan" in r.message for r in caplog.records), (
        "HARD residual critiques never reached the log"
    )


@pytest.mark.asyncio
async def test_render_carousel_reject_cites_critiques_and_dumps_history(monkeypatch, tmp_path):
    """On a non-converged slide, _render_carousel must (a) include the last vision
    critiques in the raised RuntimeError (they reach the apply-log + DB
    rejection_reason) and (b) persist the full designer history as JSON under
    WR2_HTML_DEBUG_DIR for post-mortem (the render tmp dir is deleted on exit)."""
    import json as _json

    import scripts.wr2_html_render_apply as html
    from wr2_html_renderer import composer as comp
    from wr2_html_renderer import designer_loop as dl

    hist = [
        {
            "iter": 1,
            "vision": {"passed": False, "issues": ["title clipped at right edge"]},
            "verdict": "vision flagged hard residual ['rerender'] / ['title clipped at right edge'] (not auto-fixable) — keeping best, not converged",
        }
    ]

    async def fake_loop(**kwargs):
        return dl.DesignerResult(
            final_png=None, iterations=2, converged=False, history=hist, reason="max_iters"
        )

    monkeypatch.setattr(dl, "run_designer_loop", fake_loop)
    monkeypatch.setattr(comp, "_stage_assets", lambda *a, **k: None)
    monkeypatch.setattr(comp, "make_slide_render_fn", lambda **k: None)
    debug_dir = tmp_path / "debug"
    monkeypatch.setenv("WR2_HTML_DEBUG_DIR", str(debug_dir))

    with pytest.raises(RuntimeError) as ei:
        await html._render_carousel(
            "draft-test", [{"headline": "T"}], tmp_path / "work", vision_required=True
        )
    assert "title clipped at right edge" in str(ei.value)

    dumps = list(debug_dir.glob("*.json"))
    assert dumps, "designer history JSON was not persisted"
    payload = _json.loads(dumps[0].read_text())
    assert payload["draft_id"] == "draft-test"
    assert payload["history"] == hist


# ── facts-block body structurer (designer-loop convergence, 2026-06-12) ──────
# Diagnosis: draft 3e2c2923 slide 2 HARD-rejected every iteration because the
# body renders as ONE monolithic uppercase-bold paragraph; the vision critic's
# only lever is `rerender` (structural) which no CSS lever can perform → the
# loop can never converge. The fix is a deterministic body structurer in the
# COMPOSER: label/value stack + separated subordinate source line + yellow
# accent on the lead value. Conservative: non-parsing bodies render
# byte-identical to the legacy paragraph path; cover slides untouched.

_FACTS_BODY = (
    "NEW FEE: IDR 3,500,000. OLD FEE: IDR 2,000,000. REGULATION: PMK 47/2026. "
    "EFFECTIVE: 1 JUNE 2026. [SOURCE: KEMENKEU, 24 APR 2026]"
)
_FACTS_BODY_NO_SOURCE = (
    "NEW FEE: IDR 3,500,000. OLD FEE: IDR 2,000,000. REGULATION: PMK 47/2026. "
    "EFFECTIVE: 1 JUNE 2026."
)


def test_split_source_line_extracts_trailing_source():
    """_split_source_line extracts a trailing [SOURCE: …] verbatim (brackets
    stripped) and returns the body without it."""
    from wr2_html_renderer.composer import _split_source_line

    body, src = _split_source_line(_FACTS_BODY)
    assert body == _FACTS_BODY_NO_SOURCE
    assert src == "SOURCE: KEMENKEU, 24 APR 2026"


def test_split_source_line_fonte_and_case_insensitive():
    from wr2_html_renderer.composer import _split_source_line

    body, src = _split_source_line("BODY TEXT. [Fonte: Kemenkeu, 24 Apr 2026]")
    assert body == "BODY TEXT."
    assert src == "Fonte: Kemenkeu, 24 Apr 2026"
    body, src = _split_source_line("BODY TEXT. [source: imigrasi]")
    assert body == "BODY TEXT."
    assert src == "source: imigrasi"


def test_split_source_line_no_source_returns_none():
    from wr2_html_renderer.composer import _split_source_line

    plain = "A NORMAL BODY WITH NO ATTRIBUTION AT ALL."
    assert _split_source_line(plain) == (plain, None)
    # a NON-trailing bracket segment is content, not attribution — untouched
    mid = "[SOURCE: X] FOLLOWED BY MORE TEXT."
    assert _split_source_line(mid) == (mid, None)


def test_parse_fact_pairs_parses_facts_body():
    """The exact 3e2c2923 slide-2 style body (source-stripped) parses into
    ordered label/value pairs."""
    from wr2_html_renderer.composer import _parse_fact_pairs

    pairs = _parse_fact_pairs(_FACTS_BODY_NO_SOURCE)
    assert pairs == [
        ("NEW FEE", "IDR 3,500,000"),
        ("OLD FEE", "IDR 2,000,000"),
        ("REGULATION", "PMK 47/2026"),
        ("EFFECTIVE", "1 JUNE 2026"),
    ]


def test_parse_fact_pairs_none_for_prose():
    """Conservative fallback: anything that is not a clean ≥2-pair chain of
    `LABEL: value. ` segments returns None (legacy paragraph rendering)."""
    from wr2_html_renderer.composer import _parse_fact_pairs

    # narrative sentence with one colon → single segment → None
    assert _parse_fact_pairs(
        "THE MINISTRY CONFIRMED: FEES WILL RISE SHARPLY IN JUNE 2026."
    ) is None
    # plain prose, no colon at all
    assert _parse_fact_pairs(
        "YOUR KITAP STAYS VALID. THE RENEWAL WINDOW MOVED TO MARCH."
    ) is None
    # mixed: one fact segment + one narrative segment → whole-or-nothing → None
    assert _parse_fact_pairs(
        "NEW FEE: IDR 3,500,000. THIS IS WHY IT MATTERS FOR YOUR VISA."
    ) is None
    # label longer than 4 words → None
    assert _parse_fact_pairs(
        "WHAT YOU NEED TO KNOW NOW: EVERYTHING. ALSO THIS OTHER THING HERE: MORE."
    ) is None
    # empty / whitespace
    assert _parse_fact_pairs("") is None
    assert _parse_fact_pairs("   ") is None


_BODY_SLIDE_HTML = (
    "<html><head></head><body>"
    '<div class="text-panel" data-zone-type="text">'
    '<div class="heading">{{heading}}</div>'
    '<div class="body">{{body}}</div>'
    "</div></body></html>"
)


def test_fill_placeholders_facts_body_renders_label_value_stack():
    """A facts body renders as a label/value stack: one row per pair, the
    source line present OUTSIDE the rows, yellow accent on the FIRST value
    only (the lead fact), facts CSS injected."""
    from wr2_html_renderer.composer import _fill_placeholders

    out = _fill_placeholders(
        _BODY_SLIDE_HTML,
        {"headline": "VISA FEE UPDATE", "body": _FACTS_BODY},
        hero_filename=None,
        cover_family=False,
    )
    # 4 label/value rows
    assert out.count('class="fact-row"') == 4
    assert '<div class="fact-label">NEW FEE</div>' in out
    assert '<div class="fact-label">EFFECTIVE</div>' in out
    # yellow accent on the FIRST value only
    assert out.count("fact-value-lead") >= 1
    assert '<div class="fact-value fact-value-lead">IDR 3,500,000</div>' in out
    assert '<div class="fact-value">IDR 2,000,000</div>' in out
    assert '<div class="fact-value">PMK 47/2026</div>' in out
    assert 'fact-value-lead">IDR 2,000,000' not in out
    # source line present, OUTSIDE the rows, brackets stripped
    assert '<div class="fact-source">SOURCE: KEMENKEU, 24 APR 2026</div>' in out
    assert "[SOURCE" not in out
    last_row = out.rfind('class="fact-row"')
    assert out.find('class="fact-source"') > last_row
    # facts CSS injected, accent from the existing brand token (no invented hex)
    assert 'data-facts-block="1"' in out
    assert "var(--color-accent-yellow)" in out
    # the dead-void fix: the text stack centers vertically in its zone
    assert "justify-content:center" in out
    assert "{{body}}" not in out


def test_fill_placeholders_facts_body_without_source_still_stacks():
    from wr2_html_renderer.composer import _fill_placeholders

    out = _fill_placeholders(
        _BODY_SLIDE_HTML,
        {"headline": "VISA FEE UPDATE", "body": _FACTS_BODY_NO_SOURCE},
        hero_filename=None,
        cover_family=False,
    )
    assert out.count('class="fact-row"') == 4
    assert 'class="fact-source"' not in out


def test_fill_placeholders_non_parsing_body_byte_identical():
    """Regression: a body that does NOT parse as fact pairs renders EXACTLY as
    before the change — placeholder substituted verbatim, no facts markup, no
    injected facts CSS."""
    from wr2_html_renderer.composer import _fill_placeholders

    prose = "YOUR KITAP STAYS VALID. THE RENEWAL WINDOW MOVED TO MARCH."
    out = _fill_placeholders(
        _BODY_SLIDE_HTML,
        {"headline": "SHORT TITLE", "body": prose},
        hero_filename=None,
        cover_family=False,
    )
    # pre-change snapshot semantics: plain placeholder substitution only
    expected = _BODY_SLIDE_HTML.replace("{{heading}}", "SHORT TITLE").replace(
        "{{body}}", prose
    )
    assert out == expected
    assert "fact-row" not in out
    assert "data-facts-block" not in out


def test_fill_placeholders_cover_family_facts_body_untouched():
    """Cover slides are COMPLETELY untouched by the facts structurer — even a
    body that would parse as pairs renders as the legacy paragraph."""
    from wr2_html_renderer.composer import _fill_placeholders

    out = _fill_placeholders(
        _BODY_SLIDE_HTML,
        {"headline": "FEE", "body": _FACTS_BODY},
        hero_filename=None,
        cover_family=True,
    )
    assert "fact-row" not in out
    assert "data-facts-block" not in out
    expected = _BODY_SLIDE_HTML.replace("{{heading}}", "FEE").replace(
        "{{body}}", _FACTS_BODY
    )
    assert out == expected


def test_materialize_body_slide_facts_stack_and_centering():
    """materialize_slide_html on a NON-cover body slide with a facts body emits
    the stack + the vertical-centering CSS (dead-void critique) into the HTML
    file the renderer consumes."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    BODY_SKELETON = """<!doctype html>
<html><head><link rel="stylesheet" href="../_base.css"></head>
<body>
  <div class="text-panel" data-zone-type="text">
    <div class="subheading">{{subheading}}</div>
    <div class="heading">{{heading}}</div>
    <div class="body">{{body}}</div>
  </div>
</body></html>"""

    slide = {
        "slide_number": 2,
        "slide_type": "facts",
        "headline": "THE NUMBERS",
        "subhead": "PMK 47/2026",
        "body": _FACTS_BODY,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        slides_dir = Path(tmpdir) / "slides"
        slides_dir.mkdir()
        with patch(
            "wr2_html_renderer.composer._extract_skeleton", return_value=BODY_SKELETON
        ):
            from wr2_html_renderer.composer import materialize_slide_html

            html_path, expect_hero = asyncio.run(
                materialize_slide_html(slide, slides_dir, index=2, total=6)
            )
        html = html_path.read_text()
        assert html.count('class="fact-row"') == 4
        assert '<div class="fact-source">SOURCE: KEMENKEU, 24 APR 2026</div>' in html
        assert "justify-content:center" in html
        assert "var(--color-accent-yellow)" in html
        assert "[SOURCE" not in html
