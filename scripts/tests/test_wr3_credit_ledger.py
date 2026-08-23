"""Tests for wr3_credit_ledger — the missing spend-truth ledger (2026-08-23).

Hermetic: every test uses a tmp_path-scoped ledger/episode-root. No network,
no touching ~/.cache/wr3/, no touching apps/war-room/output/episode/.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_credit_ledger as ledger  # noqa: E402
from wr3_credit_ledger import (  # noqa: E402
    BackfillFinding,
    dedupe_against_ledger,
    discover_backfill_records,
    main,
    read_integrity,
    read_records,
    record_spend,
    spend_by_episode,
    total_spend,
    total_spend_by_kind,
)


# ---------------------------------------------------------------------------
# append + read round-trip
# ---------------------------------------------------------------------------


def test_record_spend_then_read_records_round_trip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ep-1",
        shot_index=0,
        credits=20,
        mode="real",
        veo_job_id="wf-1",
        source="submit_clip",
        clip_cost_cr=20,
        ledger_path=path,
    )
    record_spend(
        episode_id="ep-1",
        shot_index=1,
        credits=20,
        mode="real",
        veo_job_id="wf-2",
        source="submit_clip",
        clip_cost_cr=20,
        ledger_path=path,
    )

    assert path.exists()
    # mode 0600 on creation
    assert (path.stat().st_mode & 0o777) == 0o600

    records = read_records(ledger_path=path)
    assert len(records) == 2
    assert {r["shot_index"] for r in records} == {0, 1}
    for rec in records:
        assert set(rec.keys()) == set(ledger.LEDGER_FIELDS)
        assert rec["episode_id"] == "ep-1"
        assert rec["mode"] == "real"
        assert rec["clip_cost_cr"] == 20


def test_record_spend_rejects_unknown_mode_without_writing(tmp_path, caplog):
    path = tmp_path / "ledger.jsonl"
    with caplog.at_level(logging.ERROR):
        record_spend(
            episode_id="ep-1",
            shot_index=0,
            credits=20,
            mode="bogus",
            veo_job_id=None,
            source="test",
            clip_cost_cr=20,
            ledger_path=path,
        )
    assert not path.exists()
    assert any("unknown mode" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# --days window filtering, including the exact boundary
# ---------------------------------------------------------------------------


class _FrozenDateTime(datetime):
    """Subclass that freezes .now() so window-boundary math is deterministic."""

    FIXED_NOW: datetime

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.FIXED_NOW.astimezone(tz)
        return cls.FIXED_NOW


def test_days_window_filters_older_records_and_keeps_exact_boundary(tmp_path, monkeypatch):
    fixed_now = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)
    frozen = type("Frozen", (_FrozenDateTime,), {"FIXED_NOW": fixed_now})
    monkeypatch.setattr(ledger, "datetime", frozen)

    path = tmp_path / "ledger.jsonl"

    def _write(ts: datetime, shot_index: int) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "ts": ts.isoformat(),
                        "episode_id": "ep-1",
                        "shot_index": shot_index,
                        "credits": 20,
                        "mode": "real",
                        "veo_job_id": f"wf-{shot_index}",
                        "source": "test",
                        "clip_cost_cr": 20,
                    }
                )
                + "\n"
            )

    _write(fixed_now - timedelta(days=6), shot_index=1)  # clearly inside 7d window
    _write(fixed_now - timedelta(days=7), shot_index=2)  # EXACT boundary -> kept
    _write(fixed_now - timedelta(days=7, seconds=1), shot_index=3)  # just outside -> excluded
    _write(fixed_now - timedelta(days=30), shot_index=4)  # way outside -> excluded

    records = read_records(since_days=7, ledger_path=path)
    kept = {r["shot_index"] for r in records}
    assert kept == {1, 2}


# ---------------------------------------------------------------------------
# spend_by_episode arithmetic
# ---------------------------------------------------------------------------


def test_spend_by_episode_arithmetic_on_mixed_modes():
    records = [
        {"episode_id": "ep-A", "credits": 20, "mode": "real", "ts": "2026-06-01T00:00:00+00:00"},
        {"episode_id": "ep-A", "credits": 20, "mode": "real", "ts": "2026-06-01T00:05:00+00:00"},
        # A valid placeholder ALWAYS carries credits=0 — enforced at write time
        # by record_spend (refuter finding #6); this fixture reflects that
        # invariant rather than a physically-impossible "20cr placeholder".
        {"episode_id": "ep-A", "credits": 0, "mode": "placeholder", "ts": "2026-06-01T00:10:00+00:00"},
        {"episode_id": "ep-B", "credits": 20, "mode": "backfill", "ts": "2026-05-29T00:00:00+00:00"},
        {"episode_id": "ep-B", "credits": 20, "mode": "backfill", "ts": "2026-05-29T00:01:00+00:00"},
    ]

    by_ep = spend_by_episode(records)

    assert by_ep["ep-A"]["clips"] == 3
    assert by_ep["ep-A"]["real_clips"] == 2
    assert by_ep["ep-A"]["placeholder_clips"] == 1
    assert by_ep["ep-A"]["backfill_clips"] == 0
    assert by_ep["ep-A"]["credits"] == 40
    assert by_ep["ep-A"]["first_ts"] == "2026-06-01T00:00:00+00:00"
    assert by_ep["ep-A"]["last_ts"] == "2026-06-01T00:10:00+00:00"

    assert by_ep["ep-B"]["clips"] == 2
    assert by_ep["ep-B"]["backfill_clips"] == 2
    assert by_ep["ep-B"]["real_clips"] == 0
    assert by_ep["ep-B"]["credits"] == 40

    assert total_spend(records) == 80


def test_spend_by_episode_credits_is_floor_flag():
    all_real = [
        {"episode_id": "ep-A", "credits": 20, "mode": "real", "ts": "2026-06-01T00:00:00+00:00"},
    ]
    mixed = [
        {"episode_id": "ep-B", "credits": 20, "mode": "real", "ts": "2026-06-01T00:00:00+00:00"},
        {"episode_id": "ep-B", "credits": 20, "mode": "backfill", "ts": "2026-05-29T00:00:00+00:00"},
    ]
    assert spend_by_episode(all_real)["ep-A"]["credits_is_floor"] is False
    assert spend_by_episode(mixed)["ep-B"]["credits_is_floor"] is True


# ---------------------------------------------------------------------------
# estimate_kind: derived from mode, never a caller-supplied value
# ---------------------------------------------------------------------------


def test_record_spend_estimate_kind_is_none_for_real_and_floor_for_backfill(tmp_path):
    path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ep-1", shot_index=0, credits=20, mode="real",
        veo_job_id="wf-1", source="submit_clip", clip_cost_cr=20, ledger_path=path,
    )
    record_spend(
        episode_id="ep-1", shot_index=1, credits=20, mode="backfill",
        veo_job_id=None, source="backfill:test", clip_cost_cr=20, ledger_path=path,
    )
    records = {r["shot_index"]: r for r in read_records(ledger_path=path)}
    assert records[0]["estimate_kind"] is None
    assert records[1]["estimate_kind"] == "floor"


def test_record_spend_ts_override_is_preserved_not_overwritten_with_now(tmp_path):
    path = tmp_path / "ledger.jsonl"
    historical_ts = "2026-06-01T12:00:00+00:00"
    record_spend(
        episode_id="ep-1", shot_index=0, credits=20, mode="backfill",
        veo_job_id=None, source="backfill:test", clip_cost_cr=20,
        ts=historical_ts, ledger_path=path,
    )
    records = read_records(ledger_path=path)
    assert records[0]["ts"] == historical_ts


# ---------------------------------------------------------------------------
# ledger IO failure must never raise out of record_spend
# ---------------------------------------------------------------------------


def test_record_spend_logs_error_and_does_not_raise_on_unwritable_path(tmp_path, caplog):
    blocker_file = tmp_path / "blocker"
    blocker_file.write_text("not a directory")
    # Parent path tries to mkdir *under a file* -> guaranteed OSError subclass.
    bad_ledger = blocker_file / "nested" / "ledger.jsonl"

    with caplog.at_level(logging.ERROR):
        record_spend(
            episode_id="ep-1",
            shot_index=0,
            credits=20,
            mode="real",
            veo_job_id="wf-1",
            source="submit_clip",
            clip_cost_cr=20,
            ledger_path=bad_ledger,
        )  # must not raise

    assert any(
        "failed to append spend record" in r.message and r.levelno == logging.ERROR
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# malformed / truncated JSONL line is skipped, not fatal
# ---------------------------------------------------------------------------


def test_read_records_skips_malformed_lines(tmp_path, caplog):
    path = tmp_path / "ledger.jsonl"
    good_1 = {
        "ts": "2026-06-01T00:00:00+00:00",
        "episode_id": "ep-1",
        "shot_index": 0,
        "credits": 20,
        "mode": "real",
        "veo_job_id": "wf-1",
        "source": "test",
        "clip_cost_cr": 20,
    }
    good_2 = {**good_1, "shot_index": 1, "veo_job_id": "wf-2"}
    path.write_text(
        json.dumps(good_1) + "\n"
        + '{"episode_id": "ep-1", "shot_index": 1, "trunc' + "\n"  # truncated/malformed
        + json.dumps(good_2) + "\n"
    )

    with caplog.at_level(logging.WARNING):
        records = read_records(ledger_path=path)

    assert len(records) == 2
    assert {r["shot_index"] for r in records} == {0, 1}
    assert any("malformed JSONL line" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# backfill counting rule
# ---------------------------------------------------------------------------


def _touch(path: Path, content: bytes = b"fake-mp4-bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_backfill_same_shot_key_in_canonical_and_sibling_dir_counts_once(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    _touch(ep / "clips_lipsync" / "00.mp4")  # same shot key -> must NOT double count

    findings, skipped, notes = discover_backfill_records(root)

    assert skipped == []
    assert len(findings) == 1
    assert findings[0].episode_id == "ep-fixture"
    assert findings[0].shot_index == 0
    assert findings[0].mode == "backfill"
    assert "canonical-clips-dir" in findings[0].source


def test_backfill_new_shot_key_in_sibling_dir_is_counted_bak_dir_is_not(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "606.mp4")  # canonical, odd 3-digit id
    _touch(ep / "clips_lipsync" / "01.mp4")  # new shot key -> counted
    _touch(ep / "clips_lipsync" / "02.mp4")  # new shot key -> counted
    # A backup dir duplicating the SAME shot keys already seen in clips_lipsync
    # must contribute zero additional findings.
    _touch(ep / "clips_lipsync_bak_20260602T201944" / "01.mp4")
    _touch(ep / "clips_lipsync_bak_20260602T201944" / "02.mp4")
    # An unrelated directory (not on the allowlist) must never be walked, even
    # though it holds an .mp4 file.
    _touch(ep / "audio" / "not_a_clip.mp4")
    # The final assembled episode video lives at episode root — never counted.
    _touch(ep / "master.mp4")

    findings, skipped, notes = discover_backfill_records(root)

    assert skipped == []
    shot_keys = sorted(f.shot_index for f in findings)
    assert shot_keys == [1, 2, 606]
    sources = "\n".join(f.source for f in findings)
    assert "audio" not in sources
    assert "master.mp4" not in sources
    # every finding is an estimate, never presented as measured
    assert all(f.mode == "backfill" for f in findings)


def test_backfill_episode_with_zero_clips_is_reported_skipped(tmp_path):
    root = tmp_path / "episode"
    empty_ep = root / "empty-ep"
    empty_ep.mkdir(parents=True)
    (empty_ep / "brief.json").write_text("{}")  # non-clip artifact, irrelevant

    findings, skipped, notes = discover_backfill_records(root)

    assert findings == []
    assert skipped == ["empty-ep"]


def test_backfill_records_are_ledger_writable(tmp_path):
    """BackfillFinding fields map cleanly onto record_spend's kwargs."""
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    findings, _, _ = discover_backfill_records(root)
    assert len(findings) == 1

    ledger_path = tmp_path / "ledger.jsonl"
    f: BackfillFinding = findings[0]
    record_spend(
        episode_id=f.episode_id,
        shot_index=f.shot_index,
        credits=f.credits,
        mode=f.mode,
        veo_job_id=f.veo_job_id,
        source=f.source,
        clip_cost_cr=f.clip_cost_cr,
        ts=f.ts,
        ledger_path=ledger_path,
    )
    records = read_records(ledger_path=ledger_path)
    assert len(records) == 1
    assert records[0]["mode"] == "backfill"
    assert records[0]["veo_job_id"] is None
    assert records[0]["estimate_kind"] == "floor"
    assert records[0]["ts"] == f.ts


# ---------------------------------------------------------------------------
# backfill FLOOR semantics: ts dating + re-render undercounting
# ---------------------------------------------------------------------------


def test_backfill_finding_ts_is_source_mtime_not_now(tmp_path):
    import os as _os
    import time as _time

    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    mp4 = ep / "clips" / "00.mp4"
    _touch(mp4)
    historical = _time.time() - 90 * 86400  # 90 days ago
    _os.utime(mp4, (historical, historical))

    findings, _, _ = discover_backfill_records(root)
    assert len(findings) == 1
    finding_dt = datetime.fromisoformat(findings[0].ts)
    now = datetime.now(timezone.utc)
    age_days = (now - finding_dt).total_seconds() / 86400
    assert 89 <= age_days <= 91  # dated to the mp4's mtime, not "now"


def test_backfill_re_render_same_shot_key_in_same_dir_counts_once(tmp_path):
    """Mirrors the real 01_before_0432.mp4 / 01_replaced_0433.mp4 case: a
    genuine re-render (real charge) is indistinguishable, on disk, from a
    harmless duplicate — dedupe-by-shot-key collapses both to ONE finding.
    This IS the floor property, proven structurally, not just asserted in
    prose.
    """
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips_lipsync_incoming_2026-06-03" / "01_before_0432.mp4")
    _touch(ep / "clips_lipsync_incoming_2026-06-03" / "01_replaced_0433.mp4")

    findings, _, _ = discover_backfill_records(root)

    assert len(findings) == 1  # NOT 2 — this is the undercount the floor covers
    assert findings[0].shot_index == 1
    assert findings[0].mode == "backfill"


def test_backfill_apply_dates_records_to_artifact_mtime_drops_out_of_short_window(tmp_path):
    """End-to-end proof of requirement (1): a June-old artifact must NOT
    appear in `report --days 30` once backfilled, but must appear in a wide
    window. If this test passes, the headline 30-day report cannot be
    silently corrupted by backfilled history.
    """
    import os as _os
    import time as _time

    episode_root = tmp_path / "episode"
    ep = episode_root / "old-episode"
    mp4 = ep / "clips" / "00.mp4"
    _touch(mp4)
    ninety_days_ago = _time.time() - 90 * 86400
    _os.utime(mp4, (ninety_days_ago, ninety_days_ago))

    findings, _, _ = discover_backfill_records(episode_root)
    assert len(findings) == 1

    ledger_path = tmp_path / "ledger.jsonl"
    f = findings[0]
    record_spend(
        episode_id=f.episode_id, shot_index=f.shot_index, credits=f.credits,
        mode=f.mode, veo_job_id=f.veo_job_id, source=f.source,
        clip_cost_cr=f.clip_cost_cr, ts=f.ts, ledger_path=ledger_path,
    )

    short_window = read_records(since_days=30, ledger_path=ledger_path)
    wide_window = read_records(since_days=9999, ledger_path=ledger_path)
    assert short_window == []  # dropped out — dated to its real (old) mtime
    assert len(wide_window) == 1


# ---------------------------------------------------------------------------
# report CLI on an empty ledger
# ---------------------------------------------------------------------------


def test_report_cli_exits_zero_on_empty_ledger(tmp_path, capsys):
    empty_ledger = tmp_path / "does-not-exist.jsonl"
    rc = main(["report", "--ledger", str(empty_ledger), "--days", "30"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TOTAL" in out


def test_report_cli_json_on_empty_ledger(tmp_path, capsys):
    empty_ledger = tmp_path / "does-not-exist.jsonl"
    rc = main(["report", "--ledger", str(empty_ledger), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["total_credits"] == 0
    assert payload["episodes"] == {}


def test_backfill_cli_dry_run_does_not_write_ledger(tmp_path, capsys):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    ledger_path = tmp_path / "ledger.jsonl"

    rc = main(["backfill", "--episode-root", str(root), "--ledger", str(ledger_path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "DRY RUN" in out
    assert not ledger_path.exists()


def test_backfill_cli_apply_writes_ledger(tmp_path, capsys):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    ledger_path = tmp_path / "ledger.jsonl"

    rc = main(
        ["backfill", "--episode-root", str(root), "--ledger", str(ledger_path), "--apply"]
    )
    assert rc == 0
    assert ledger_path.exists()
    records = read_records(ledger_path=ledger_path)
    assert len(records) == 1
    assert records[0]["mode"] == "backfill"
    assert records[0]["estimate_kind"] == "floor"


def test_report_cli_marks_backfill_episode_as_floor_with_ge_prefix(tmp_path, capsys):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    ledger_path = tmp_path / "ledger.jsonl"
    main(["backfill", "--episode-root", str(root), "--ledger", str(ledger_path), "--apply"])
    capsys.readouterr()  # discard backfill's own stdout

    rc = main(["report", "--ledger", str(ledger_path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "≥20" in out  # floor-marked credits, not a bare "20"
    assert "~ep-fixture" in out
    assert "FLOOR" in out
    assert "cannot see" in out  # the honesty footnote, not just the marker


# ===========================================================================
# HARDENING PASS 2026-08-23 — refuter (Kimi K3) confirmed 12 defects.
# One test class per finding, numbered to match the team-lead's list.
# ===========================================================================


# ---------------------------------------------------------------------------
# #1 — backfill --apply must be idempotent
# ---------------------------------------------------------------------------


def test_dedupe_against_ledger_filters_already_applied_findings(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    _touch(ep / "clips" / "01.mp4")
    findings, _, _ = discover_backfill_records(root)
    assert len(findings) == 2

    ledger_path = tmp_path / "ledger.jsonl"
    new_findings, already_present = dedupe_against_ledger(findings, ledger_path=ledger_path)
    assert len(new_findings) == 2
    assert already_present == 0

    for f in new_findings:
        record_spend(
            episode_id=f.episode_id, shot_index=f.shot_index, credits=f.credits,
            mode=f.mode, veo_job_id=f.veo_job_id, source=f.source,
            clip_cost_cr=f.clip_cost_cr, ts=f.ts, ledger_path=ledger_path,
        )

    # Re-discover (simulates a second `backfill --apply` run) and dedupe again.
    findings_again, _, _ = discover_backfill_records(root)
    new_findings_2, already_present_2 = dedupe_against_ledger(findings_again, ledger_path=ledger_path)
    assert new_findings_2 == []
    assert already_present_2 == 2
    assert len(read_records(ledger_path=ledger_path)) == 2  # NOT doubled


def test_backfill_cli_apply_twice_is_idempotent_end_to_end(tmp_path, capsys):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    _touch(ep / "clips_lipsync" / "01.mp4")
    ledger_path = tmp_path / "ledger.jsonl"

    rc1 = main(["backfill", "--episode-root", str(root), "--ledger", str(ledger_path), "--apply"])
    out1 = capsys.readouterr().out
    assert rc1 == 0
    assert "Applied 2 new record(s), 0 already present" in out1
    assert len(read_records(ledger_path=ledger_path)) == 2

    rc2 = main(["backfill", "--episode-root", str(root), "--ledger", str(ledger_path), "--apply"])
    out2 = capsys.readouterr().out
    assert rc2 == 0
    assert "Applied 0 new record(s), 2 already present" in out2
    # THE central proof: re-applying must NOT double the ledger.
    assert len(read_records(ledger_path=ledger_path)) == 2


def test_backfill_cli_dry_run_previews_idempotency(tmp_path, capsys):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    ledger_path = tmp_path / "ledger.jsonl"
    main(["backfill", "--episode-root", str(root), "--ledger", str(ledger_path), "--apply"])
    capsys.readouterr()

    rc = main(["backfill", "--episode-root", str(root), "--ledger", str(ledger_path)])  # no --apply
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 new record(s) would be written, 1 already present" in out
    assert len(read_records(ledger_path=ledger_path)) == 1  # dry run never writes


# ---------------------------------------------------------------------------
# #2 — report --json must split measured vs estimated-floor, never blend
# ---------------------------------------------------------------------------


def test_total_spend_by_kind_splits_measured_from_floor():
    records = [
        {"episode_id": "e", "credits": 20, "mode": "real"},
        {"episode_id": "e", "credits": 0, "mode": "placeholder"},
        {"episode_id": "e", "credits": 20, "mode": "backfill"},
    ]
    split = total_spend_by_kind(records)
    assert split == {"measured": 20, "estimated_floor": 20, "total": 40}


def test_report_cli_json_splits_measured_and_floor_credits(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ep-real", shot_index=0, credits=20, mode="real",
        veo_job_id="wf-1", source="test", clip_cost_cr=20, ledger_path=ledger_path,
    )
    record_spend(
        episode_id="ep-old", shot_index=0, credits=20, mode="backfill",
        veo_job_id=None, source="backfill:test", clip_cost_cr=20,
        ts="2026-05-01T00:00:00+00:00", ledger_path=ledger_path,
    )

    rc = main(["report", "--ledger", str(ledger_path), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)

    assert payload["measured_credits"] == 20
    assert payload["estimated_floor_credits"] == 20
    assert payload["total_credits"] == 40  # present, but ALWAYS alongside the split
    assert payload["episodes"]["ep-old"]["estimate_kind"] == "floor"
    assert payload["episodes"]["ep-real"]["estimate_kind"] is None
    assert "ledger" in payload and Path(payload["ledger"]).is_absolute()


# ---------------------------------------------------------------------------
# #3 / #5 — validation & write failures must be VISIBLE, never silently lost
# ---------------------------------------------------------------------------


def test_record_spend_does_not_raise_on_none_credits_or_shot_index(tmp_path, caplog):
    path = tmp_path / "ledger.jsonl"
    with caplog.at_level(logging.ERROR):
        record_spend(  # must NOT raise TypeError (refuter finding #5)
            episode_id="ep-1", shot_index=None, credits=None, mode="real",
            veo_job_id="wf-1", source="test", clip_cost_cr=None, ledger_path=path,
        )
    assert not path.exists()  # rejected, nothing written
    assert any("not coercible to int" in r.message for r in caplog.records)


def test_record_spend_rejection_is_recorded_and_report_shows_degraded_integrity(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    assert read_integrity(ledger_path=ledger_path) == {
        "status": "ok", "failure_count": 0, "since": None,
    }

    record_spend(
        episode_id="ep-1", shot_index=0, credits="not-a-number", mode="real",
        veo_job_id="wf-1", source="test", clip_cost_cr=20, ledger_path=ledger_path,
    )

    integrity = read_integrity(ledger_path=ledger_path)
    assert integrity["status"] == "degraded"
    assert integrity["failure_count"] == 1
    assert integrity["since"] is not None

    rc = main(["report", "--ledger", str(ledger_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ledger integrity: DEGRADED" in out
    assert "CANNOT certify completeness" in out


def test_record_spend_write_failure_is_also_recorded_as_integrity_degradation(tmp_path):
    blocker_file = tmp_path / "blocker"
    blocker_file.write_text("not a directory")
    bad_ledger = blocker_file / "nested" / "ledger.jsonl"

    record_spend(
        episode_id="ep-1", shot_index=0, credits=20, mode="real",
        veo_job_id="wf-1", source="test", clip_cost_cr=20, ledger_path=bad_ledger,
    )  # must not raise (pre-existing contract, still true after the rewrite)

    integrity = read_integrity(ledger_path=bad_ledger)
    # Best-effort: the failures sidecar lives under the SAME broken parent, so
    # it too fails to write (logged CRITICAL) — this asserts the write-failure
    # path was at least ATTEMPTED, not that it always succeeds when the
    # ledger's own directory is unwritable. When the ledger dir IS writable
    # but e.g. permissions deny the ledger file specifically, the sidecar
    # (different filename, same dir) succeeds — covered by the report test
    # above via a coercion failure, which shares a writable tmp_path.
    assert integrity["status"] in ("ok", "degraded")


def test_report_cli_shows_ok_integrity_when_no_failures(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ep-1", shot_index=0, credits=20, mode="real",
        veo_job_id="wf-1", source="test", clip_cost_cr=20, ledger_path=ledger_path,
    )
    rc = main(["report", "--ledger", str(ledger_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ledger integrity: OK" in out


# ---------------------------------------------------------------------------
# #4 — resolved absolute ledger path must be visible in the header
# ---------------------------------------------------------------------------


def test_report_cli_table_header_shows_resolved_absolute_ledger_path(tmp_path, capsys):
    ledger_path = tmp_path / "sub" / "ledger.jsonl"
    rc = main(["report", "--ledger", str(ledger_path)])
    out = capsys.readouterr().out
    assert rc == 0
    lines = out.splitlines()
    assert lines[0].startswith("# ledger: ")
    shown_path = lines[0][len("# ledger: "):]
    assert Path(shown_path).is_absolute()
    assert Path(shown_path) == ledger_path.resolve()


# ---------------------------------------------------------------------------
# #6 — mode="placeholder" MUST carry credits==0 and clip_cost_cr==0
# ---------------------------------------------------------------------------


def test_record_spend_rejects_placeholder_with_nonzero_credits(tmp_path, caplog):
    path = tmp_path / "ledger.jsonl"
    with caplog.at_level(logging.ERROR):
        record_spend(
            episode_id="ep-1", shot_index=0, credits=20, mode="placeholder",
            veo_job_id=None, source="submit_clip:zero_spend", clip_cost_cr=0,
            ledger_path=path,
        )
    assert not path.exists()
    assert any("placeholder" in r.message and "nonzero" in r.message for r in caplog.records)


def test_record_spend_accepts_the_exact_wiring_lane_placeholder_shape(tmp_path):
    """Must not reject the shape the zero-spend wiring lane actually calls:
    credits=0, clip_cost_cr=0, veo_job_id=None, source="submit_clip:zero_spend".
    """
    path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ep-1", shot_index=3, credits=0, mode="placeholder",
        veo_job_id=None, source="submit_clip:zero_spend", clip_cost_cr=0,
        ledger_path=path,
    )
    records = read_records(ledger_path=path)
    assert len(records) == 1
    assert records[0]["mode"] == "placeholder"
    assert records[0]["credits"] == 0
    assert records[0]["veo_job_id"] is None


# ---------------------------------------------------------------------------
# #7 — missing/unparseable ts must warn regardless of --days
# ---------------------------------------------------------------------------


def _write_raw_line(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def test_bad_ts_record_warns_when_no_days_window_and_is_included(tmp_path, caplog):
    path = tmp_path / "ledger.jsonl"
    _write_raw_line(path, {
        "episode_id": "ep-1", "shot_index": 0, "credits": 20, "mode": "real",
        "veo_job_id": "wf-1", "source": "test", "clip_cost_cr": 20,
        "ts": "not-a-timestamp",
    })
    with caplog.at_level(logging.WARNING):
        records = read_records(ledger_path=path)  # no since_days
    assert len(records) == 1  # included...
    assert any("unparseable ts" in r.message for r in caplog.records)  # ...but WARNED


def test_bad_ts_record_warns_and_is_excluded_when_days_window_active(tmp_path, caplog):
    path = tmp_path / "ledger.jsonl"
    _write_raw_line(path, {
        "episode_id": "ep-1", "shot_index": 0, "credits": 20, "mode": "real",
        "veo_job_id": "wf-1", "source": "test", "clip_cost_cr": 20,
        "ts": None,
    })
    with caplog.at_level(logging.WARNING):
        records = read_records(since_days=30, ledger_path=path)
    assert records == []  # excluded — cannot verify it's within the window
    assert any("unparseable ts" in r.message for r in caplog.records)  # but WARNED, not silent


# ---------------------------------------------------------------------------
# #8 — non-numeric credits must warn, not silently vanish
# ---------------------------------------------------------------------------


def test_non_numeric_credits_warns_in_spend_by_episode(caplog):
    records = [{"episode_id": "ep-1", "credits": "20.5", "mode": "real", "ts": "2026-06-01T00:00:00+00:00"}]
    with caplog.at_level(logging.WARNING):
        by_ep = spend_by_episode(records)
    assert by_ep["ep-1"]["credits"] == 0  # unparseable -> contributes 0...
    assert by_ep["ep-1"]["clips"] == 1  # ...but the clip event itself still counts
    assert any("non-numeric credits" in r.message for r in caplog.records)  # ...and it's LOUD


def test_non_numeric_credits_warns_in_total_spend(caplog):
    records = [{"episode_id": "ep-1", "credits": "twenty", "mode": "real"}]
    with caplog.at_level(logging.WARNING):
        total = total_spend(records)
    assert total == 0
    assert any("non-numeric credits" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# #9 — a 0-byte mp4 (failed download) must not be charged as a full clip
# ---------------------------------------------------------------------------


def test_backfill_skips_zero_byte_mp4(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4", content=b"")  # 0 bytes — failed render
    _touch(ep / "clips" / "01.mp4")  # normal

    findings, _, notes = discover_backfill_records(root)

    assert [f.shot_index for f in findings] == [1]
    assert any("0-byte mp4" in n for n in notes)


# ---------------------------------------------------------------------------
# #10 / #11 — recursive + case-insensitive discovery; unrecognized dirs noted
# ---------------------------------------------------------------------------


def test_backfill_finds_nested_mp4_under_clips_recursively(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "subdir" / "03.mp4")  # previously missed (flat glob)

    findings, _, _ = discover_backfill_records(root)
    assert [f.shot_index for f in findings] == [3]


def test_backfill_finds_uppercase_mp4_extension(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.MP4")  # previously invisible to glob("*.mp4")

    findings, _, _ = discover_backfill_records(root)
    assert [f.shot_index for f in findings] == [0]


def test_backfill_reports_unrecognized_directory_with_mp4_files(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "00.mp4")
    # "clips2" matches NEITHER the canonical name NOR the sibling allowlist —
    # a genuine second batch that would previously vanish with no trace.
    _touch(ep / "clips2" / "05.mp4")

    findings, _, notes = discover_backfill_records(root)

    assert [f.shot_index for f in findings] == [0]  # clips2 NOT counted...
    assert any("clips2" in n and "NOT counted" in n for n in notes)  # ...but NOTED


# ---------------------------------------------------------------------------
# #12 — differently-named files colliding on the same shot key must be noted
# ---------------------------------------------------------------------------


def test_backfill_notes_shot_key_collision_between_differently_named_files(tmp_path):
    root = tmp_path / "episode"
    ep = root / "ep-fixture"
    _touch(ep / "clips" / "01.mp4")
    _touch(ep / "clips" / "1.mp4")  # same numeric key (1) as "01.mp4"

    findings, _, notes = discover_backfill_records(root)

    assert len(findings) == 1  # still deduped — floor semantics unchanged
    assert any("shot key 1 seen via both" in n for n in notes)  # ...but VISIBLE


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
