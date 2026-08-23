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

    IT DOES NOT MAKE EVERY WRITE SAFE. It redirects the two env vars; a caller
    that passes an explicit `ledger_path=` still writes wherever it is told.
    Only the tripwire covers that, and only after the fact.

    TO TEST THE DEFAULT-PATH FALLBACK, redirect HOME as well — never `delenv`
    alone. This fixture makes the dangerous version look safe, so the pattern
    is written out here rather than left to be rediscovered:

        def test_default_path(tmp_path, monkeypatch):
            monkeypatch.setenv("HOME", str(tmp_path))      # <- NOT optional
            monkeypatch.delenv("WR3_CREDIT_LEDGER", raising=False)
            record_spend(...)                              # lands in tmp_path

    Without the HOME line, that test writes the production ledger under a
    fixture whose whole promise is that it cannot.
    """
    monkeypatch.setenv("WR3_CREDIT_LEDGER", str(tmp_path / "wr3-credit-ledger.jsonl"))
    monkeypatch.setenv("WR3_SPEND_DECISION_LOG", str(tmp_path / "wr3-spend-decisions.jsonl"))


_WR3_STATE_DIR = Path(".cache") / "wr3"


def _wr3_real_state_fingerprint() -> dict[str, str]:
    """(path -> sha256) for EVERY file in the real `~/.cache/wr3` directory.

    The whole directory, not a named pair. `wr3_credit_ledger._record_failure`
    writes a `<ledger>.failures` sidecar beside the ledger, so a guard listing
    only `credit-ledger.jsonl` and `spend-decisions.jsonl` misses part of the
    module's own write surface — a validation rejection against the real path
    would mutate real state with the session green (cross-family refuter,
    Kimi K3). Enumerating the directory also covers `flow-quota.json` and any
    file a future writer adds, which a hardcoded list never would.

    Read via the process's own HOME so the guard resolves the path exactly as
    the code under test does. A missing directory is `{}`, not an error: on CI
    runners and fresh machines it simply does not exist.
    """
    root = Path(os.path.expanduser("~")) / _WR3_STATE_DIR
    out: dict[str, str] = {}
    try:
        entries = sorted(path for path in root.iterdir() if path.is_file())
    except OSError:
        return out
    for path in entries:
        try:
            out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            out[str(path)] = "unreadable"
    return out


def _wr3_state_delta(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Human-legible description of what moved, newest evidence first.

    The tripwire cannot ATTRIBUTE a write — a real render, a cron job or a
    concurrent pytest run on Pro/Mini would trip it just as a leaking test
    does. So it does not merely say "something changed": it prints the lines
    that appeared, and whoever reads the failure can see in one glance whether
    they are `test_*` fixtures or a genuine render. An alarm that cannot be
    diagnosed is an alarm that gets disarmed.
    """
    notes: list[str] = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        if old is None:
            notes.append(f"CREATED {path}")
        elif new is None:
            notes.append(f"DELETED {path}")
        else:
            notes.append(f"CHANGED {path}")
        if new is not None and path.endswith((".jsonl", ".failures")):
            try:
                lines = Path(path).read_text().splitlines()
            except OSError:
                continue
            for line in lines[-5:]:
                notes.append(f"    tail: {line[:200]}")
    return notes


@pytest.fixture()
def wr3_real_state_fingerprint():
    """Expose the tripwire's detector so it can be tested for guilt.

    A detector nobody probes is the same as no detector — importing `conftest`
    by name is not reliable across rootdirs, so it is handed over as a fixture.
    """
    return _wr3_real_state_fingerprint


@pytest.fixture(scope="session", autouse=True)
def _wr3_real_state_tripwire():
    """Fail the session loudly if the run mutated real WR3 spend state.

    The isolation fixture above is the cure; this is what proves the cure is
    still armed. Without it, deleting one `monkeypatch.setenv` line silently
    restores the exact defect it was written for — the suite would go green
    while writing fiction into the production ledger, which is precisely how
    the defect survived unnoticed in the first place.

    KNOWN LIMITS, stated rather than papered over:

    * It cannot attribute the write. Any writer trips it — a real render, a
      manual `backfill --apply`, a second pytest running concurrently. That is
      why the failure prints the appended lines instead of only a verdict.
    * A test that appends and then restores the original bytes is invisible to
      a content hash. Content hashing is still right: it is what stops a
      touched-but-unchanged file from failing every clean session.
    * It is session-scoped, so it never runs when zero tests are selected
      (`-k` matching nothing exits 5 with the fixture uninstantiated), and a
      SIGKILL or `os._exit` skips teardown entirely.
    * It covers `scripts/tests/` only. A test living in another rootdir that
      imports the wr3 modules gets neither the redirection nor this guard.
    """
    before = _wr3_real_state_fingerprint()
    yield
    after = _wr3_real_state_fingerprint()
    if before != after:
        raise AssertionError(
            "the test suite mutated REAL WR3 spend state (W96):\n  "
            + "\n  ".join(_wr3_state_delta(before, after))
            + "\n\nIf those lines look like test fixtures, a test reached "
            "record_spend()/log_decision() without the isolation fixture's env "
            "redirection — find it, do not clean the file by hand. If they look "
            "like a genuine render, a real writer ran concurrently with this "
            "session and the suite is innocent."
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
