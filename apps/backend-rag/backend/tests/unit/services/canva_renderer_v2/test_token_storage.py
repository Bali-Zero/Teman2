"""OrchestratorTokenStorage: HMAC + flock + proactive refresh + atomic write."""

import json
import os
import subprocess
import sys
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


# Worker source for the concurrency test below, run via `python -c` in a
# fresh subprocess rather than `multiprocessing.Process`. This suite runs
# under pytest.ini's `--import-mode=importlib`, which imports this module
# under a synthetic dotted name (`unit.services.canva_renderer_v2....`) that
# is never inserted into sys.path. On macOS, multiprocessing's default
# "spawn" start method re-imports the target's module by that name in the
# child to unpickle it, and fails with `ModuleNotFoundError: No module named
# 'unit'` (exitcode 1) — reproducible 100% locally, invisible on Linux CI
# where the default "fork" start method never re-imports. Counterfactual
# check: switching pytest.ini to `--import-mode=prepend` makes the original
# multiprocessing.Process version pass. A subprocess that imports the
# production module fresh (via PYTHONPATH=.) sidesteps pickling/import-mode
# entirely and is portable to both start methods and both platforms.
#
# Each worker touches its own ready-file before waiting on the shared
# barrier (R1 finding: the original barrier was touch()-ed *before* the
# workers were even started, so both simply found it already present and
# never actually raced each other — a pre-existing gap the spawn-fix
# preserved verbatim). The test below now only touches the barrier once
# both ready-files exist, so the flock is genuinely contended.
_WORKER_SNIPPET = """
import os
import sys
import time
from pathlib import Path

token_file, hmac_key, barrier_path, ready_path = sys.argv[1:5]
os.environ["WR2_CANVA_TOKEN_FILE"] = token_file
os.environ["WR2_CANVA_HMAC_KEY"] = hmac_key

# Signal readiness, then wait for the shared start signal so both workers
# hit the flock as close to simultaneously as possible.
Path(ready_path).touch()
while not Path(barrier_path).exists():
    time.sleep(0.02)

from backend.services.canva_renderer_v2._token_storage import OrchestratorTokenStorage

s = OrchestratorTokenStorage()
tok = s.load_sync()
s.save_sync(
    {
        **tok,
        "access_token": f"by_pid_{os.getpid()}",
        "expires_in": 3600,
        "refresh_token": tok["refresh_token"],
    }
)
"""


def test_flock_serializes_concurrent_writes(tmp_path, monkeypatch):
    """Two processes saving concurrently → final file is consistent (HMAC valid)."""
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    barrier = tmp_path / "go"
    ready_paths = [tmp_path / f"ready-{i}" for i in range(2)]

    repo_root = Path(__file__).resolve().parents[5]  # apps/backend-rag
    env = dict(os.environ)
    # Prepend, don't overwrite: preserve any pre-existing PYTHONPATH (CI/
    # monorepo tooling may rely on it) while still making `backend` importable.
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [".", existing_pythonpath]))

    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _WORKER_SNIPPET, str(p), HMAC_KEY, str(barrier), str(ready)],
            env=env,
            cwd=str(repo_root),
        )
        for ready in ready_paths
    ]
    try:
        deadline = time.monotonic() + 10
        while not all(rp.exists() for rp in ready_paths):
            if time.monotonic() > deadline:
                raise AssertionError("workers did not signal ready in time")
            time.sleep(0.02)
        barrier.touch()

        for proc in procs:
            rc = proc.wait(timeout=10)
            assert rc == 0
    finally:
        # Never leak a worker process on assertion failure / timeout.
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

    # File must still be valid (HMAC intact)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    final = OrchestratorTokenStorage().load_sync()
    assert final["access_token"].startswith("by_pid_")
