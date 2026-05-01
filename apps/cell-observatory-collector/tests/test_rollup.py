import pytest
from cell_observatory.rollup import compute_daily_rollup
from cell_observatory.storage import Storage


@pytest.mark.asyncio
async def test_compute_rollup(tmp_path):
    s = Storage(db_path=tmp_path / "x.db")
    await s.init()
    # seed 3 events for cell 'organism', 2 green 1 yellow
    for i, label in enumerate(["green", "green", "yellow"]):
        await s.insert_pulse_event({
            "outbox_id": i, "event_version": "v1", "cell_id": "organism",
            "cell_kind": "x", "pulse_id": f"01{i}",
            "pulse_timestamp": "2026-05-01T00:00:00.000Z",
            "phase": "x", "sensors": [],
            "pulse_result": {"classifier_self": label},
            "homeostatic_state": {}, "scar_signals": [], "metadata": {},
        })

    await compute_daily_rollup(s, "2026-05-01")
    rows = await s._fetchall(
        "SELECT * FROM pulse_daily_rollup WHERE day='2026-05-01' AND cell_id='organism'"
    )
    assert len(rows) == 1
    assert rows[0]["n_pulse"] == 3
    assert rows[0]["n_self_green"] == 2
    assert rows[0]["n_self_yellow"] == 1
    await s.close()
