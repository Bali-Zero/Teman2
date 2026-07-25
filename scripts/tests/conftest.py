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


_ISOLATED_MODULE_PREFIXES = ("wr2_", "warroom_")


@pytest.fixture(autouse=True)
def _wr2_module_identity_isolation():
    """Restore swapped wr2_*/warroom_* modules after each test (W96 class-cure,
    module-identity dimension, 2026-07-25).

    12 WR2 test fixtures do `sys.modules.pop("wr2_X"); import wr2_X; return mod`
    to get a "fresh" module WITHOUT restoring the original (e.g. `wdg` in
    test_wr2_draft_generator_cover_codex_detection.py). That leaks a NEW module
    instance into sys.modules, so a LATER test's `patch("wr2_X.attr", ...)`
    patches the fresh instance while the test still holds a reference (imported at
    its own collection) to the OLD one — the patch silently misses and the real
    code path runs. Observed: test_compose_slides_forwards_tier_into_prompt fell
    through to a live `claude` CLI subprocess after cover_codex_detection had run,
    but ONLY mid-batch — it passed alone and in CI's canonical order, a latent
    order-dependent flake.

    Snapshot the fresh-import-prone module keys BEFORE each test (autouse fixtures
    set up before the test-requested pop/reimport fixture) and restore them AFTER,
    so no test can leak a swapped module identity to the next.
    """
    import sys
    saved = {k: v for k, v in sys.modules.items() if k.startswith(_ISOLATED_MODULE_PREFIXES)}
    try:
        yield
    finally:
        for k in [k for k in sys.modules if k.startswith(_ISOLATED_MODULE_PREFIXES)]:
            if k not in saved:
                del sys.modules[k]  # a module first-imported during the test → drop it
        sys.modules.update(saved)   # restore any that were swapped to their originals


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
