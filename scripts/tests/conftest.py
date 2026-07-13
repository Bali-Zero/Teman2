from __future__ import annotations

import pytest

MIN_TEST_NOFILE_LIMIT = 4096


@pytest.fixture(autouse=True)
def _wr2_runtime_isolation(tmp_path, monkeypatch):
    """Tests must NEVER touch the real WR2 runtime state (W96, 2026-07-13).

    Same fixture as apps/backend-rag/backend/tests/conftest.py: any test that
    reaches a WR2 writer honoring WR2_OUTPUT_ROOT without mocking it would land
    fixture entries in the PRODUCTION human-review-queue.json and spool real
    Telegram notifications. Redirect both to tmp_path unconditionally.
    """
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "wr2-output"))
    monkeypatch.setenv("TG_DRY_RUN", "1")
    monkeypatch.setenv("TG_SPOOL_DIR", str(tmp_path / "tg-spool"))


def pytest_configure(config: object) -> None:
    _ = config
    try:
        import resource
    except ImportError:
        return

    try:
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (OSError, ValueError):
        return

    if soft_limit == resource.RLIM_INFINITY:
        return

    target_limit = max(soft_limit, MIN_TEST_NOFILE_LIMIT)
    if hard_limit != resource.RLIM_INFINITY:
        target_limit = min(target_limit, hard_limit)
    if target_limit <= soft_limit:
        return

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard_limit))
    except (OSError, ValueError):
        return
