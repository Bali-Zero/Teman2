"""Behavioral tests for the NB-INTEL-Press full-notebook alert added to
`intel-lake-nb-pusher-a2/intel-lake-nb-pusher-standalone.py`.

Ledger row `nb-intel-press-is-full-and-the-pusher-calls-it-an-unknown-error` (2026-09-22):
NB-INTEL-Press hit its ~500-source cap on 2026-07-18 and every push since came back from
Google as `API error (code 3): INVALID_ARGUMENT Hint: File paths must be accessible…` —
`_classify_nlm_error` only recognised the literal word "quota", so this fell through to
"unknown" → 3 retries → `failed_permanent`, and the pusher's only health signal
(`oldest_pending_age_seconds`) watches PENDING rows, so a `failed_permanent` row (no longer
pending) never raised anything. 96 rows died silently this way.

Module has a hyphenated path (`intel-lake-nb-pusher-a2/`), loaded via `importlib` — same
isolation trick as `test_pajak_monitor.py` / `test_wr2_image_generator_lease.py`. The module
imports `asyncpg` (installed in this env) at load time but never connects at import.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).parent.parent / "intel-lake-nb-pusher-a2"
MODULE_PATH = MODULE_DIR / "intel-lake-nb-pusher-standalone.py"


@pytest.fixture
def pusher():
    sys.modules.pop("intel_lake_nb_pusher_standalone", None)
    spec = importlib.util.spec_from_file_location(
        "intel_lake_nb_pusher_standalone", MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["intel_lake_nb_pusher_standalone"] = mod
    spec.loader.exec_module(mod)
    return mod


# ─── classifier: the real Google response is `notebook_full`, not `unknown` ────

# Measured shape (ledger row above). The hint sentence ("File paths must be accessible…") is
# Google's own misleading wording — the classifier matches on the gRPC status ENTITY (code 3 /
# INVALID_ARGUMENT on a source-add call), not that sentence, so a reworded hint still matches.
REAL_FULL_NOTEBOOK_STDERR = (
    "Uploading nlm_push_a1b2c3d4.txt... Error: Could not add file source: "
    "API error (code 3): INVALID_ARGUMENT Hint: File paths must be accessible…"
)


def test_full_notebook_error_classified_notebook_full_not_unknown(pusher):
    """Guilt: revert the `code 3`/`INVALID_ARGUMENT` branch in `_classify_nlm_error` and this
    reds — the real string falls through every other class to `unknown`."""
    assert pusher._classify_nlm_error(REAL_FULL_NOTEBOOK_STDERR, "", 1) == "notebook_full"


def test_unrelated_invalid_argument_without_code_3_stays_unknown(pusher):
    """Innocence: an INVALID_ARGUMENT with no code-3 marker is NOT reclassified — the match
    requires both tokens together, not either alone (over-match guard, scar family #3)."""
    assert pusher._classify_nlm_error("INVALID_ARGUMENT: malformed title", "", 1) == "unknown"


# ─── retry decision: notebook_full fails fast, exactly like quota ──────────────
#
# A full notebook will not empty itself between attempts, so it is fail-fast like `quota`
# rather than retried up to MAX_ATTEMPTS_PERMANENT like a transient class.


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple]] = []

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))


class _FakeAcquireCtx:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


@pytest.mark.asyncio
async def test_notebook_full_goes_straight_to_failed_permanent_on_first_attempt(pusher):
    """Pins the retry decision: `notebook_full`, like `quota`, is fail-fast — the very FIRST
    failure lands `failed_permanent`, no `failed_transient` detour. Guilt: drop
    `"notebook_full"` from the `("quota", "notebook_full")` tuple in `update_push_result` and
    this reds (the error class would fall to the `failed_transient` else-branch instead)."""
    conn = _FakeConn()
    pool = _FakePool(conn)
    await pusher.update_push_result(
        pool, 42,
        success=False, push_method=None,
        error_class="notebook_full", error_text=REAL_FULL_NOTEBOOK_STDERR,
    )
    update_calls = [c for c in conn.execute_calls if "UPDATE intel_item_nb_pushes" in c[0]]
    assert len(update_calls) == 1
    _query, args = update_calls[0]
    # args = (push_id, error_text, error_class, MAX_ATTEMPTS_PERMANENT, new_status)
    assert args[-1] == "failed_permanent"


# ─── per-notebook failure-streak alert ──────────────────────────────────────

PRESS_NB_UUID = "9d262101-abeb-4e15-af9c-c38e028c62fe"


def test_streak_of_terminal_failures_raises_exactly_one_alert_naming_the_notebook(pusher):
    """Guilt: remove the streak-length/dedup check in `_maybe_alert_notebook_streak` (e.g. drop
    the `if nb_uuid in state: return False` guard) and the SECOND tick re-sends — this reds on
    `len(sent) == 1`."""
    sent: list[str] = []
    state: dict = {}
    recent = ["failed_permanent"] * pusher.NOTEBOOK_FAILURE_STREAK_N

    fired_1 = pusher._maybe_alert_notebook_streak(
        PRESS_NB_UUID, "notebook_full", recent, state, send=sent.append
    )
    fired_2 = pusher._maybe_alert_notebook_streak(
        PRESS_NB_UUID, "notebook_full", recent, state, send=sent.append
    )

    assert fired_1 is True
    assert fired_2 is False
    assert len(sent) == 1
    assert PRESS_NB_UUID in sent[0]
    assert "notebook_full" in sent[0]


def test_fewer_than_n_terminal_failures_does_not_alert(pusher):
    """Guilt: remove the `len(recent_statuses) < n` gate in `_notebook_failure_streak` and a
    single failure would already read as a streak — this reds."""
    sent: list[str] = []
    state: dict = {}
    short = ["failed_permanent"] * (pusher.NOTEBOOK_FAILURE_STREAK_N - 1)

    fired = pusher._maybe_alert_notebook_streak(
        PRESS_NB_UUID, "notebook_full", short, state, send=sent.append
    )

    assert fired is False
    assert sent == []


def test_healthy_notebook_in_the_same_run_does_not_alert(pusher):
    """Innocence: a notebook whose most recent attempts include a real `pushed` success (a
    genuinely healthy notebook mixed into the same batch as the broken one) never fires,
    even though it had ONE failure earlier in its history."""
    sent: list[str] = []
    state: dict = {}
    recent = ["pushed", "failed_transient", "failed_permanent"]

    fired = pusher._maybe_alert_notebook_streak(
        "healthy-nb-uuid", "network", recent, state, send=sent.append
    )

    assert fired is False
    assert sent == []


def test_recovery_then_a_new_streak_alerts_again(pusher):
    """Guilt: drop the `state.pop(nb_uuid, None)` recovery-clear in `_maybe_alert_notebook_streak`
    (keep only the `if not streak: return False` half) and this reds — the SECOND streak
    would stay silent forever, since the notebook's dedup entry from the first alert is never
    removed. Asserted on the observable (a second alert actually sent, naming the notebook),
    not on the internal state dict alone, so the test survives a refactor of where dedup state
    lives."""
    sent: list[str] = []
    state: dict = {}
    broken_streak = ["failed_permanent"] * pusher.NOTEBOOK_FAILURE_STREAK_N
    recovered = ["pushed", "pushed", "pushed"]

    # First streak: alerts once.
    assert pusher._maybe_alert_notebook_streak(
        PRESS_NB_UUID, "notebook_full", broken_streak, state, send=sent.append
    ) is True
    assert len(sent) == 1

    # Recovery run: streak broken, no alert — this is the run that must clear dedup state.
    assert pusher._maybe_alert_notebook_streak(
        PRESS_NB_UUID, "notebook_full", recovered, state, send=sent.append
    ) is False
    assert len(sent) == 1

    # A NEW streak after recovery must alert again — the observable proof of the clear.
    assert pusher._maybe_alert_notebook_streak(
        PRESS_NB_UUID, "notebook_full", broken_streak, state, send=sent.append
    ) is True
    assert len(sent) == 2
    assert PRESS_NB_UUID in sent[1]
