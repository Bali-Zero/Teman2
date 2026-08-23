from __future__ import annotations

import hashlib
import os
from pathlib import Path

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


@pytest.fixture(autouse=True)
def _wr3_runtime_isolation(tmp_path, monkeypatch):
    """Tests must NEVER write the real WR3 credit ledger (W96, 2026-08-23).

    `wr3_flowkit_client.submit_clip()` calls `record_spend()` on every charge,
    and `record_spend()` falls back to `~/.cache/wr3/credit-ledger.jsonl` when
    `WR3_CREDIT_LEDGER` is unset. Several existing tests drive `submit_clip`
    with a mocked gateway and never set that variable, so the suite has been
    appending `mode: "real"`, `credits: 20` rows for episodes that never
    existed — measured 2026-08-23: 28 such rows, 560 fictitious credits, in the
    one file whose entire purpose is to be the truth about spend. A ledger a
    test run can write is not a ledger.

    Same shape as `_wr2_runtime_isolation` above, and the same reason: the cure
    belongs in a fixture no future test can forget, not in a rule each test
    must remember. `_wr3_real_state_tripwire` proves it stayed armed.
    """
    monkeypatch.setenv("WR3_CREDIT_LEDGER", str(tmp_path / "wr3-credit-ledger.jsonl"))
    monkeypatch.setenv("WR3_SPEND_DECISION_LOG", str(tmp_path / "wr3-spend-decisions.jsonl"))


def _wr3_real_state_fingerprint() -> dict[str, str]:
    """(path -> sha256 | "absent") for the real WR3 state files.

    Read via the process's own HOME so the tripwire follows the same resolution
    the code under test would use.
    """
    home = Path(os.path.expanduser("~"))
    out: dict[str, str] = {}
    for name in ("credit-ledger.jsonl", "spend-decisions.jsonl"):
        target = home / ".cache" / "wr3" / name
        try:
            out[str(target)] = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError:
            out[str(target)] = "absent"
    return out


@pytest.fixture()
def wr3_real_state_fingerprint():
    """Expose the tripwire's detector so it can be tested for guilt.

    A detector nobody probes is the same as no detector — importing `conftest`
    by name is not reliable across rootdirs, so it is handed over as a fixture.
    """
    return _wr3_real_state_fingerprint


@pytest.fixture(scope="session", autouse=True)
def _wr3_real_state_tripwire():
    """Fail the session loudly if the suite mutated real WR3 spend state.

    The isolation fixture above is the cure; this is what proves the cure is
    still armed. Without it, deleting one `monkeypatch.setenv` line silently
    restores the exact defect it was written for — the suite would go green
    while writing fiction into the production ledger, which is precisely how
    the defect survived unnoticed in the first place.
    """
    before = _wr3_real_state_fingerprint()
    yield
    after = _wr3_real_state_fingerprint()
    changed = [path for path, digest in after.items() if before.get(path) != digest]
    if changed:
        raise AssertionError(
            "the test suite mutated REAL WR3 spend state (W96): "
            + ", ".join(changed)
            + " — a test reached record_spend()/log_decision() without the "
            "isolation fixture's env redirection. Do not clean the file by "
            "hand; find the test that escaped."
        )


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
