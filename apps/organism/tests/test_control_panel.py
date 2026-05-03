import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from organism.control_panel import create_app
from organism.blackout import BlackoutManager


def test_health_endpoint_returns_ok(tmp_path):
    import time as _time
    before = _time.time()
    app = create_app(blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"))
    client = TestClient(app)
    resp = client.get("/health")
    after = _time.time()
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["paused"] is False
    # `ts` field powers the W1.5 organism heartbeat bridge — must be
    # present, numeric, and within the request window.
    assert isinstance(body["ts"], (int, float))
    assert before <= body["ts"] <= after


def test_pause_requires_token(tmp_path):
    app = create_app(blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"))
    client = TestClient(app)
    resp = client.post("/pause?minutes=30")
    # Without token, either 401 or 503 (if token file not configured)
    assert resp.status_code in (401, 503)


def test_pause_with_token_creates_flag(tmp_path, monkeypatch):
    token_path = tmp_path / "token"
    token_path.write_text("secret-token")
    monkeypatch.setenv("ORGANISM_TOKEN_PATH", str(token_path))
    flag_path = tmp_path / "pause.flag"
    app = create_app(blackout=BlackoutManager(flag_path=flag_path))
    client = TestClient(app)
    resp = client.post("/pause?minutes=30", headers={"X-Organism-Token": "secret-token"})
    assert resp.status_code == 200
    assert resp.json()["paused_for_minutes"] == 30
    assert flag_path.exists()


def test_pause_max_120_minutes(tmp_path, monkeypatch):
    token_path = tmp_path / "token"
    token_path.write_text("t")
    monkeypatch.setenv("ORGANISM_TOKEN_PATH", str(token_path))
    app = create_app(blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"))
    client = TestClient(app)
    resp = client.post("/pause?minutes=999", headers={"X-Organism-Token": "t"})
    assert resp.status_code == 400
    assert "max 120" in resp.json()["detail"]


def test_resume_clears_flag(tmp_path, monkeypatch):
    token_path = tmp_path / "token"
    token_path.write_text("t")
    monkeypatch.setenv("ORGANISM_TOKEN_PATH", str(token_path))
    flag_path = tmp_path / "pause.flag"
    app = create_app(blackout=BlackoutManager(flag_path=flag_path))
    client = TestClient(app)
    # First pause
    client.post("/pause?minutes=30", headers={"X-Organism-Token": "t"})
    assert flag_path.exists()
    # Then resume
    resp = client.post("/resume", headers={"X-Organism-Token": "t"})
    assert resp.status_code == 200
    assert not flag_path.exists()


def test_health_reflects_pause_state(tmp_path, monkeypatch):
    token_path = tmp_path / "token"
    token_path.write_text("t")
    monkeypatch.setenv("ORGANISM_TOKEN_PATH", str(token_path))
    bm = BlackoutManager(flag_path=tmp_path / "pause.flag")
    app = create_app(blackout=bm)
    client = TestClient(app)
    bm.pause(minutes=5)
    resp = client.get("/health")
    assert resp.json()["paused"] is True


def test_blackout_manager_expires():
    """Flag auto-expires when expiry time passes."""
    import time
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as td:
        bm = BlackoutManager(flag_path=_P(td) / "pause.flag")
        bm.pause(minutes=1)
        assert bm.is_paused() is True
        # Force expiry by rewriting flag to past timestamp
        (_P(td) / "pause.flag").write_text(str(time.time() - 10))
        assert bm.is_paused() is False
        # File should be auto-deleted by is_paused()
        assert not (_P(td) / "pause.flag").exists()


def test_blackout_manager_rejects_out_of_range():
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as td:
        bm = BlackoutManager(flag_path=_P(td) / "pause.flag")
        with pytest.raises(ValueError):
            bm.pause(minutes=0)
        with pytest.raises(ValueError):
            bm.pause(minutes=121)


def test_stats_requires_token(tmp_path):
    """W2 will populate /stats — must require auth even before content."""
    app = create_app(blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"))
    client = TestClient(app)
    resp = client.get("/stats")
    assert resp.status_code in (401, 503)


def test_stats_with_token_returns_stub(tmp_path, monkeypatch):
    token_path = tmp_path / "token"
    token_path.write_text("t")
    monkeypatch.setenv("ORGANISM_TOKEN_PATH", str(token_path))
    app = create_app(blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"))
    client = TestClient(app)
    resp = client.get("/stats", headers={"X-Organism-Token": "t"})
    assert resp.status_code == 200
    assert "events_processed" in resp.json()
