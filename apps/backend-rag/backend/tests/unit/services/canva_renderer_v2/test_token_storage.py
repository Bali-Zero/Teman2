"""OrchestratorTokenStorage: HMAC + flock + proactive refresh + atomic write."""
import hmac
import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from backend.services.canva_renderer_v2._token_storage import (
    OrchestratorTokenStorage,
    TokenStorageError,
    sign_payload,
)


HMAC_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _seed_valid(path: Path, expires_in_s: int = 3600) -> dict:
    payload = {
        "client_id": "cid",
        "client_secret": "",
        "access_token": "tok",
        "refresh_token": "ref",
        "scope": "user:read teams:read",
        "token_type": "bearer",
        "expires_at_epoch": time.time() + expires_in_s,
        "issued_at": "2026-05-13T18:30:00Z",
        "last_refreshed_iso": "2026-05-13T18:30:00Z",
    }
    signed = sign_payload(payload, key=bytes.fromhex(HMAC_KEY))
    path.write_text(json.dumps(signed))
    return signed


def test_token_load_valid(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    tokens = storage.load_sync()
    assert tokens["access_token"] == "tok"


def test_token_hmac_mismatch_raises(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    # Corrupt the file
    data = json.loads(p.read_text())
    data["access_token"] = "TAMPERED"
    p.write_text(json.dumps(data))

    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    with pytest.raises(TokenStorageError, match="HMAC"):
        storage.load_sync()


def test_token_missing_file_raises(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    with pytest.raises(TokenStorageError, match="not found"):
        storage.load_sync()


def test_proactive_refresh_signals_expiry(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p, expires_in_s=60)  # 1min < 300s margin
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    assert storage.needs_refresh() is True


def test_proactive_refresh_not_needed(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p, expires_in_s=3600)  # 1h > 300s margin
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    assert storage.needs_refresh() is False


def test_set_tokens_preserves_refresh_token_on_omission(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()

    # Canva omits refresh_token in refresh response (common pattern)
    new_tokens = {
        "access_token": "new_tok",
        "refresh_token": None,  # omitted
        "expires_in": 3600,
        "token_type": "bearer",
        "scope": "user:read teams:read",
    }
    storage.save_sync(new_tokens)
    saved = json.loads(p.read_text())
    assert saved["refresh_token"] == "ref"  # preserved from existing
    assert saved["access_token"] == "new_tok"


def _worker_lock_test(token_file: str, hmac_key: str, barrier_path: str):
    """Worker that loads + immediately saves under flock. Used in concurrency test."""
    os.environ["WR2_CANVA_TOKEN_FILE"] = token_file
    os.environ["WR2_CANVA_HMAC_KEY"] = hmac_key
    # Wait for sibling
    while not Path(barrier_path).exists():
        time.sleep(0.05)
    s = OrchestratorTokenStorage()
    tok = s.load_sync()
    s.save_sync({**tok, "access_token": f"by_pid_{os.getpid()}",
                 "expires_in": 3600, "refresh_token": tok["refresh_token"]})


def test_flock_serializes_concurrent_writes(tmp_path, monkeypatch):
    """Two processes saving concurrently → final file is consistent (HMAC valid)."""
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    barrier = tmp_path / "go"
    barrier.touch()

    procs = [
        multiprocessing.Process(target=_worker_lock_test, args=(str(p), HMAC_KEY, str(barrier)))
        for _ in range(2)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=10)
        assert proc.exitcode == 0

    # File must still be valid (HMAC intact)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    final = OrchestratorTokenStorage().load_sync()
    assert final["access_token"].startswith("by_pid_")
