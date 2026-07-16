"""Tests for the WR2 A1/A3 complete-or-nothing gate (2026-07-16).

Mandate (Zero, verbatim): the app must NEVER receive drafted carousels with a
single/partial slide — complete or nothing. This file covers:

  - derive_slide_count(): the ONE helper every writer routes through.
  - A1: _render_carousel's explicit completeness gate, both the non-vision
    (compose_carousel) and vision-required (per-slide designer loop) paths —
    including the "RenderResult.ok landmine" (ok only requires
    `slides_rendered > 0`, not `== total`; a partial-but-nonempty render with
    zero recorded failures must still be caught).
  - _persist_local_artifacts / _publish_visibility re-deriving slide_count
    from the DURABLE artifact, never the in-memory png_paths list.
  - A3: wr2_daily_reconciler's check_completeness() 3-way classification
    (queue_stale / genuinely_incomplete / dirless) and
    apply_completeness_backfill()'s honest-state mutation.

No DB, no Playwright, no Drive — tmp_path + monkeypatch only (W96 discipline;
the autouse conftest fixture already redirects WR2_OUTPUT_ROOT/TG to tmp_path).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


html = _load("wr2_html_render_apply")
reconciler = _load("wr2_daily_reconciler")


def _make_pngs(slides_dir: Path, n: int, *, with_logo: bool = False, with_placeholder: bool = False) -> None:
    slides_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        (slides_dir / f"{i:02d}.png").write_bytes(b"\x89PNG-fake-" + bytes([i]))
    if with_logo:
        (slides_dir / "logo.png").write_bytes(b"\x89PNG-logo")
    if with_placeholder:
        (slides_dir / "placeholder-hero.png").write_bytes(b"\x89PNG-ph")


# ── derive_slide_count ───────────────────────────────────────────────────────


def test_derive_slide_count_numeric_stem_only(tmp_path):
    d = tmp_path / "slides"
    _make_pngs(d, 5, with_logo=True, with_placeholder=True)
    assert html.derive_slide_count(d) == 5  # logo.png + placeholder-hero.png excluded


def test_derive_slide_count_missing_dir_is_zero(tmp_path):
    assert html.derive_slide_count(tmp_path / "does-not-exist") == 0


def test_derive_slide_count_ignores_non_png_and_non_numeric(tmp_path):
    d = tmp_path / "slides"
    d.mkdir()
    (d / "01.png").write_bytes(b"x")
    (d / "01.html").write_bytes(b"<html>")
    (d / "01-hero.jpg").write_bytes(b"x")
    (d / "cover.png").write_bytes(b"x")  # non-numeric stem, excluded
    assert html.derive_slide_count(d) == 1


# ── A1: _render_carousel completeness gate (non-vision / default path) ─────


def _fake_compose_carousel_factory(rendered_indices: list[int]):
    """Build a fake compose_carousel that writes PNGs for `rendered_indices`
    into out_dir/slides and reports ok=True with zero failures — simulating
    the RenderResult.ok landmine (ok only checks `slides_rendered > 0`, not
    `== total`) regardless of what actually landed on disk."""

    async def _fake(slides, out_dir, *, topic="", timeout_ms=30000):
        slides_dir = Path(out_dir) / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        for i in rendered_indices:
            (slides_dir / f"{i:02d}.png").write_bytes(b"\x89PNG-fake")
        return SimpleNamespace(
            ok=True,
            slides_rendered=len(rendered_indices),
            heroes_placed=1,
            heroes_expected=1,
            failures=[],
        )

    return _fake


def test_guilt_partial_render_never_reaches_promotion(tmp_path, monkeypatch):
    """GUILT: compose_carousel reports ok=True (zero failures, slides_rendered>0)
    but only 8 of 9 slides actually landed on disk. The A1 gate must still
    raise — this is exactly the RenderResult.ok landmine + the 2026-07-08
    1-August case pattern (queue said 9/9, disk had 8)."""
    import wr2_html_renderer.composer as composer_mod

    monkeypatch.setattr(composer_mod, "compose_carousel", _fake_compose_carousel_factory(list(range(1, 9))))

    slides = [{"headline": f"slide {i}"} for i in range(1, 10)]  # 9 slides
    with pytest.raises(RuntimeError, match="completeness gate failed"):
        asyncio.run(html._render_carousel("draft-guilt", slides, tmp_path / "work", vision_required=False))


def test_innocence_full_render_flows_unchanged(tmp_path, monkeypatch):
    """INNOCENCE: a full N-of-N render (9/9, ok=True) must pass through exactly
    as before — the new gate must not clobber the happy path."""
    import wr2_html_renderer.composer as composer_mod

    monkeypatch.setattr(composer_mod, "compose_carousel", _fake_compose_carousel_factory(list(range(1, 10))))

    slides = [{"headline": f"slide {i}"} for i in range(1, 10)]
    slides_dir, weak = asyncio.run(
        html._render_carousel("draft-innocent", slides, tmp_path / "work", vision_required=False)
    )
    assert weak == []
    assert html.derive_slide_count(slides_dir) == 9


def test_guilt_compose_carousel_not_ok_still_raises_as_before(tmp_path, monkeypatch):
    """GUILT (regression guard): the pre-existing `.ok` gate still raises when
    compose_carousel reports real failures — the new explicit check is
    additive, not a replacement."""
    import wr2_html_renderer.composer as composer_mod

    async def _fake_not_ok(slides, out_dir, *, topic="", timeout_ms=30000):
        return SimpleNamespace(ok=False, slides_rendered=3, heroes_placed=0, heroes_expected=1, failures=["boom"])

    monkeypatch.setattr(composer_mod, "compose_carousel", _fake_not_ok)
    slides = [{"headline": "x"}] * 3
    with pytest.raises(RuntimeError, match="carousel render gate failed"):
        asyncio.run(html._render_carousel("draft-notok", slides, tmp_path / "work", vision_required=False))


# ── _persist_local_artifacts / _publish_visibility re-derive from disk ──────


def test_persist_local_artifacts_slide_count_is_disk_derived(tmp_path):
    """slide_count in meta.json must equal what derive_slide_count() sees on
    the durable slides_dir, not just len(png_paths)."""
    src = tmp_path / "render-tmp"
    src.mkdir()
    pngs = []
    for i in range(1, 4):
        p = src / f"{i:02d}.png"
        p.write_bytes(b"\x89PNG-fake")
        pngs.append(p)
    car_dir = html._persist_local_artifacts(
        draft_id="abcd", topic="Topic", png_paths=pngs, drive_url="https://drive/x",
        weak_count=0, fact_check_status="pass", out_root=tmp_path / "output",
        rendered_at="2026-07-16T00:00:00Z",
    )
    meta = json.loads((car_dir / "meta.json").read_text())
    assert meta["slide_count"] == html.derive_slide_count(car_dir / "slides") == 3


def test_persist_local_artifacts_raises_on_copy_mismatch(tmp_path, monkeypatch):
    """GUILT: if the durable copy silently produced fewer files than
    png_paths (simulated by monkeypatching shutil.copy2 to skip one file),
    _persist_local_artifacts must raise rather than write a lying meta.json."""
    import shutil

    src = tmp_path / "render-tmp"
    src.mkdir()
    pngs = []
    for i in range(1, 4):
        p = src / f"{i:02d}.png"
        p.write_bytes(b"\x89PNG-fake")
        pngs.append(p)

    real_copy2 = shutil.copy2

    def _flaky_copy2(s, d, *a, **kw):
        if Path(s).name == "02.png":
            return  # silently drop this one
        return real_copy2(s, d, *a, **kw)

    monkeypatch.setattr(shutil, "copy2", _flaky_copy2)
    with pytest.raises(RuntimeError, match="completeness mismatch"):
        html._persist_local_artifacts(
            draft_id="abcd", topic="Topic", png_paths=pngs, drive_url="https://drive/x",
            weak_count=0, fact_check_status="pass", out_root=tmp_path / "output",
            rendered_at="2026-07-16T00:00:00Z",
        )


# ── A3: check_completeness() 3-way classification ───────────────────────────


def _write_queue(qp: Path, entries: list[dict]) -> None:
    qp.parent.mkdir(parents=True, exist_ok=True)
    qp.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def test_classify_queue_stale_when_expected_matches_disk(tmp_path):
    """(i) meta.json's intended_slide_count (DB-sourced, HIGH #4) agrees with
    disk at N-1; only the queue's own slide_count field is wrong ->
    queue_stale, carousel is genuinely complete at the smaller count."""
    car_dir = tmp_path / "carousel" / "topic-abcd1234"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8, "intended_slide_count": 8}))

    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_x", "draft_id": "d1", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.classification == "queue_stale"
    assert m.disk == 8 and m.declared == 9 and m.expected == 8


def test_classify_queue_stale_when_entry_carries_intended_slide_count(tmp_path):
    """Same as above but the QUEUE ENTRY itself carries intended_slide_count
    (the field this PR adds to _make_queue_entry) — the highest-priority
    source, checked before meta.json."""
    car_dir = tmp_path / "carousel" / "topic-entry-src"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    # no meta.json at all — the entry's own field must be sufficient

    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_e", "draft_id": "d1e", "state": "drafted",
        "slide_count": 9, "intended_slide_count": 8,
        "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.classification == "queue_stale"
    assert m.expected == 8 and m.expected_source == "intended_slide_count"


def test_classify_genuinely_incomplete_when_expected_exceeds_disk(tmp_path):
    """(ii) meta.json's intended_slide_count says N but disk only has N-1 ->
    genuinely incomplete: a real slide is missing from the durable artifact."""
    car_dir = tmp_path / "carousel" / "topic-deadbeef"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8, "intended_slide_count": 9}))

    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_y", "draft_id": "d2", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.classification == "genuinely_incomplete"
    assert m.disk == 8 and m.expected == 9


def test_classify_genuinely_incomplete_even_when_queue_matches_disk(tmp_path):
    """HIGH #3 regression: queue's declared count matches disk (8==8) but an
    independent slides.json says the TRUE intent was 9 — the old code's
    `if disk == declared: continue` shortcut made this class of loss
    completely invisible to the sweep. Must now be reported as
    genuinely_incomplete, not silently skipped."""
    car_dir = tmp_path / "carousel" / "topic-queue-disk-agree-both-wrong"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "slides.json").write_text(json.dumps({"slides": [{}] * 9}))

    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_qd", "draft_id": "d_qd", "state": "drafted",
        "slide_count": 8, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.classification == "genuinely_incomplete"
    assert m.declared == 8 and m.disk == 8 and m.expected == 9
    assert m.expected_source == "slides.json"


def test_classify_dirless(tmp_path):
    """(iii) slides_dir missing/not a directory -> dirless."""
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_z", "draft_id": "d3", "state": "drafted",
        "slide_count": 9, "carousel_path": str(tmp_path / "gone"),
        "slides_dir": str(tmp_path / "gone" / "slides"),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1 and mismatches[0].classification == "dirless"


def test_no_ground_truth_classifies_unknown_intent_never_mutates(tmp_path):
    """HIGH #4 (2026-07-16): when NO independent source exists (no entry/
    meta.json intended_slide_count, no slides.json), the classifier must NOT
    guess either way — not "complete" (queue_stale) and not "incomplete"
    (genuinely_incomplete). unknown_intent is report-only; apply_backfill
    must never mutate this entry (see test_backfill_unknown_intent_never_mutates)."""
    car_dir = tmp_path / "carousel" / "topic-noground"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)  # no meta.json, no slides.json, no entry field

    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_w", "draft_id": "d4", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.classification == "unknown_intent"
    assert m.expected is None and m.expected_source == "none"


def test_backfill_unknown_intent_never_mutates(tmp_path):
    """HIGH #4: apply_completeness_backfill must NOT touch an unknown_intent
    entry even with --apply — report only, regardless of dry_run."""
    car_dir = tmp_path / "carousel" / "topic-noground2"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [{
        "id": "carousel_w2", "draft_id": "d4b", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }]
    _write_queue(qp, before)

    reports = reconciler.apply_completeness_backfill(queue_path=qp, dry_run=False)
    assert len(reports) == 1
    assert reports[0]["classification"] == "unknown_intent"
    assert reports[0]["action"].startswith("report_only")
    # queue file byte-for-byte untouched despite dry_run=False
    assert json.loads(qp.read_text()) == before


def test_innocence_matching_entries_are_never_flagged(tmp_path):
    """INNOCENCE: an entry whose declared slide_count matches disk exactly
    must never appear in the mismatch report."""
    car_dir = tmp_path / "carousel" / "topic-fine"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 9)
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_fine", "draft_id": "d5", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    assert reconciler.check_completeness(queue_path=qp) == []


def test_innocence_terminal_states_are_never_touched(tmp_path):
    """INNOCENCE: published/archived history is immutable — even a mismatched
    published entry must never be flagged or mutated."""
    car_dir = tmp_path / "carousel" / "topic-published"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 5)  # disk disagrees with declared 9, but published
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_pub", "draft_id": "d6", "state": "published",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    assert reconciler.check_completeness(queue_path=qp) == []


# ── A3: apply_completeness_backfill() honest-state mutation ─────────────────


def test_backfill_dry_run_never_mutates(tmp_path):
    car_dir = tmp_path / "carousel" / "topic-abcd1234"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8, "intended_slide_count": 8}))
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [{
        "id": "carousel_x", "draft_id": "d1", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }]
    _write_queue(qp, before)

    reports = reconciler.apply_completeness_backfill(queue_path=qp, dry_run=True)
    assert len(reports) == 1 and reports[0]["classification"] == "queue_stale"
    # queue file untouched
    assert json.loads(qp.read_text()) == before


def test_backfill_apply_fixes_queue_stale_slide_count_in_place(tmp_path):
    """Case (i): carousel is genuinely complete at 8 — fix the number, keep state."""
    car_dir = tmp_path / "carousel" / "topic-abcd1234"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8, "intended_slide_count": 8}))
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_x", "draft_id": "d1", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
        "state_history": [{"state": "drafted", "at": "t0"}],
    }])

    reports = reconciler.apply_completeness_backfill(queue_path=qp, dry_run=False)
    assert len(reports) == 1 and reports[0]["action"].startswith("fix slide_count")

    queue = json.loads(qp.read_text())
    entry = queue[0]
    assert entry["slide_count"] == 8
    assert entry["state"] == "drafted"  # unchanged — carousel really is complete
    assert entry["state_history"][-1]["by"] == "wr2-daily-reconciler-backfill"


def test_backfill_apply_marks_genuinely_incomplete_render_incomplete(tmp_path):
    """Case (ii): a real slide is missing — mark render_incomplete, never
    silently renumber down to disk as if that were the design."""
    car_dir = tmp_path / "carousel" / "topic-deadbeef"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 9, "intended_slide_count": 9}))
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_y", "draft_id": "d2", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])

    reports = reconciler.apply_completeness_backfill(queue_path=qp, dry_run=False)
    assert len(reports) == 1 and reports[0]["classification"] == "genuinely_incomplete"

    queue = json.loads(qp.read_text())
    entry = queue[0]
    assert entry["state"] == reconciler.RENDER_INCOMPLETE_STATE
    assert entry["slide_count"] == 8  # honest — reflects physical reality, not the lie
    assert entry["state_history"][-1]["reason"].startswith("genuinely incomplete")


def test_backfill_apply_marks_dirless_render_incomplete(tmp_path):
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_z", "draft_id": "d3", "state": "reviewed",
        "slide_count": 9, "carousel_path": str(tmp_path / "gone"),
        "slides_dir": str(tmp_path / "gone" / "slides"),
    }])
    reports = reconciler.apply_completeness_backfill(queue_path=qp, dry_run=False)
    assert len(reports) == 1 and reports[0]["classification"] == "dirless"
    entry = json.loads(qp.read_text())[0]
    assert entry["state"] == reconciler.RENDER_INCOMPLETE_STATE


# ── old-schema carousel_path-only resolution fix (2026-07-17) ──────────────
# WHY: OLD-style queue entries (pre-`slides_dir` field, still live in the
# queue) carry only `carousel_path` and NO `slides_dir` key at all. The old
# code treated the missing key as "no dir" and misclassified a real,
# fully-rendered carousel as dirless (live case: indonesia-visafree-myth-
# reality, 8 real PNGs, mis-marked tonight).


def test_guilt_old_schema_carousel_path_only_entry_is_not_dirless(tmp_path):
    """GUILT: an entry with ONLY carousel_path (no slides_dir key at all) and
    real PNGs under carousel_path/slides must resolve correctly — not dirless,
    and (with a correct declared count) not flagged as any mismatch at all."""
    car_dir = tmp_path / "carousel" / "indonesia-visafree-myth-reality"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_old", "draft_id": "d-old", "state": "drafted",
        "slide_count": 8, "carousel_path": str(car_dir),
        # deliberately NO "slides_dir" key — old-schema shape
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert mismatches == []


def test_innocence_genuinely_dirless_entry_without_slides_dir_key_stays_dirless(tmp_path):
    """INNOCENCE: an entry with only carousel_path, where NEITHER
    carousel_path/slides NOR any carousel_root suffix-match exists, must
    still classify as dirless — the fix must not make everything resolve."""
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_gone", "draft_id": "d-gone", "state": "drafted",
        "slide_count": 8, "carousel_path": str(tmp_path / "carousel" / "gone-topic"),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1 and mismatches[0].classification == "dirless"


def test_backfill_apply_never_mutates_old_schema_entry_with_real_pngs(tmp_path):
    """GUILT (backfill path): the same old-schema entry must not be mutated to
    render_incomplete by apply_completeness_backfill either."""
    car_dir = tmp_path / "carousel" / "indonesia-visafree-myth-reality"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [{
        "id": "carousel_old", "draft_id": "d-old", "state": "drafted",
        "slide_count": 8, "carousel_path": str(car_dir),
    }]
    _write_queue(qp, before)
    reports = reconciler.apply_completeness_backfill(queue_path=qp, dry_run=False)
    assert reports == []
    assert json.loads(qp.read_text()) == before


def test_suffix_match_resolves_when_both_recorded_paths_are_stale(tmp_path, monkeypatch):
    """Resolution step 3: neither slides_dir nor carousel_path point at a real
    directory anymore (the carousel dir was renamed/re-persisted), but a
    directory under carousel_root (check_completeness resolves this from
    WR2_OUTPUT_ROOT, same as _verify_visibility_or_backfill) matches by
    topic_slug — the entry must still resolve, not be classified dirless."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "wr2-output"))
    carousel_root = tmp_path / "wr2-output" / "carousel"
    real_dir = carousel_root / "2026-07-01-indonesia-visafree-myth-reality-abcd1234"
    slides_dir = real_dir / "slides"
    _make_pngs(slides_dir, 8)
    stale = tmp_path / "carousel" / "stale-dir-no-longer-exists"
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_drifted", "draft_id": "d-drift", "state": "drafted",
        "slide_count": 8,
        "carousel_path": str(stale),
        "slides_dir": str(stale / "slides"),
        "topic_slug": "indonesia-visafree-myth-reality",
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert mismatches == []


def test_resolve_slides_dir_pure_unit_all_three_paths():
    """Direct unit coverage of _resolve_slides_dir()'s 3-step priority,
    independent of check_completeness()'s queue/env plumbing."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        carousel_root = root / "carousel"

        # step 1: slides_dir present and real
        sd = root / "direct-slides"
        sd.mkdir()
        assert reconciler._resolve_slides_dir({"slides_dir": str(sd)}, carousel_root) == sd

        # step 1 fallback -> step 2: slides_dir stale, carousel_path resolves
        cp = root / "carousel-dir"
        (cp / "slides").mkdir(parents=True)
        entry = {"slides_dir": str(root / "nope"), "carousel_path": str(cp)}
        assert reconciler._resolve_slides_dir(entry, carousel_root) == cp / "slides"

        # step 2b: carousel_path itself IS the slides dir already
        direct_slides_as_cp = root / "already-slides"
        direct_slides_as_cp.mkdir()
        entry2 = {"carousel_path": str(direct_slides_as_cp / "slides")}
        (direct_slides_as_cp / "slides").mkdir()
        assert reconciler._resolve_slides_dir(entry2, carousel_root) == direct_slides_as_cp / "slides"

        # step 3: both stale, suffix-match under carousel_root by topic_slug
        carousel_root.mkdir()
        matched = carousel_root / "2026-01-01-my-topic-slug-deadbeef"
        (matched / "slides").mkdir(parents=True)
        entry3 = {
            "slides_dir": str(root / "gone" / "slides"),
            "carousel_path": str(root / "gone"),
            "topic_slug": "my-topic-slug",
        }
        assert reconciler._resolve_slides_dir(entry3, carousel_root) == matched / "slides"

        # all three fail -> None
        entry4 = {
            "slides_dir": str(root / "gone2" / "slides"),
            "carousel_path": str(root / "gone2"),
            "topic_slug": "no-such-topic-anywhere",
        }
        assert reconciler._resolve_slides_dir(entry4, carousel_root) is None


def test_resolve_slides_dir_suffix_match_prefers_newest_dir():
    """GUILT (gate finding, 2026-07-17): when step 3's suffix-match has MULTIPLE
    candidates (a topic re-rendered into a second dir), the resolver must
    return the NEWEST (later-dated) one, never the oldest. Carousel dirs are
    date-prefixed (2026-07-08-..., 2026-07-14-...); a naive ascending sort
    picks the OLDEST match — reproduced live before this fix: two dirs
    2026-07-08-visa-myth-aaa and 2026-07-14-visa-myth-bbb, both with valid
    slides, resolved to 2026-07-08 (stale)."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        carousel_root = root / "carousel"
        old_dir = carousel_root / "2026-07-08-visa-myth-aaa"
        new_dir = carousel_root / "2026-07-14-visa-myth-bbb"
        (old_dir / "slides").mkdir(parents=True)
        (old_dir / "slides" / "01.png").write_bytes(b"\x89PNG-old")
        (new_dir / "slides").mkdir(parents=True)
        (new_dir / "slides" / "01.png").write_bytes(b"\x89PNG-new")

        entry = {
            "slides_dir": str(root / "gone" / "slides"),
            "carousel_path": str(root / "gone"),
            "topic_slug": "visa-myth",
        }
        resolved = reconciler._resolve_slides_dir(entry, carousel_root)
        assert resolved == new_dir / "slides"
        assert resolved != old_dir / "slides"


def test_backfill_apply_preserves_other_queue_entries(tmp_path):
    """INNOCENCE: entries with no mismatch (including published history) must
    be byte-for-byte preserved by the backfill write."""
    car_dir = tmp_path / "carousel" / "topic-abcd1234"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8, "intended_slide_count": 8}))
    qp = tmp_path / "queue" / "human-review-queue.json"
    published = {"id": "carousel_old", "draft_id": "d0", "state": "published", "slide_count": 9999}
    _write_queue(qp, [
        published,
        {
            "id": "carousel_x", "draft_id": "d1", "state": "drafted",
            "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
        },
    ])
    reconciler.apply_completeness_backfill(queue_path=qp, dry_run=False)
    queue = json.loads(qp.read_text())
    assert queue[0] == published
    assert queue[1]["slide_count"] == 8


# ── repair_false_incomplete() one-shot repair (2026-07-17) ─────────────────
# WHY: the pre-fix dirless bug (see _resolve_slides_dir section above) had
# already mutated some render_incomplete entries in the live queue before the
# fix merged. This one-shot CLI restores the false positives it produced,
# without touching genuinely dirless entries or any other state.


def test_repair_guilt_false_incomplete_restored_to_drafted_under_apply(tmp_path):
    """GUILT: a render_incomplete entry whose resolved slides dir (using the
    FIXED resolution) has real PNGs is restored to drafted, with the correct
    disk-derived slide_count, under --apply."""
    car_dir = tmp_path / "carousel" / "indonesia-visafree-myth-reality"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_old", "draft_id": "d-old", "state": reconciler.RENDER_INCOMPLETE_STATE,
        "slide_count": 8, "carousel_path": str(car_dir),
        "state_history": [{"state": reconciler.RENDER_INCOMPLETE_STATE, "at": "t0",
                            "reason": "dirless: slides_dir missing/not a directory"}],
    }])
    reports = reconciler.repair_false_incomplete(queue_path=qp, dry_run=False)
    assert len(reports) == 1
    assert reports[0]["action"] == "restore_to_drafted"
    assert reports[0]["disk"] == 8

    entry = json.loads(qp.read_text())[0]
    assert entry["state"] == "drafted"
    assert entry["slide_count"] == 8
    assert entry["slides_dir"] == str(slides_dir)
    assert entry["state_history"][-1]["by"] == "wr2-daily-reconciler-repair-false-incomplete"


def test_repair_dry_run_never_mutates(tmp_path):
    car_dir = tmp_path / "carousel" / "indonesia-visafree-myth-reality"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [{
        "id": "carousel_old", "draft_id": "d-old", "state": reconciler.RENDER_INCOMPLETE_STATE,
        "slide_count": 8, "carousel_path": str(car_dir),
    }]
    _write_queue(qp, before)
    reports = reconciler.repair_false_incomplete(queue_path=qp, dry_run=True)
    assert len(reports) == 1 and reports[0]["action"] == "restore_to_drafted"
    assert json.loads(qp.read_text()) == before


def test_repair_innocence_genuinely_dirless_entry_untouched(tmp_path):
    """INNOCENCE: an entry genuinely dirless even under the fixed resolution
    (no slides_dir/carousel_path/suffix-match resolves) must stay
    render_incomplete — the repair must not resurrect a real false negative."""
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [{
        "id": "carousel_gone", "draft_id": "d-gone", "state": reconciler.RENDER_INCOMPLETE_STATE,
        "slide_count": 8, "carousel_path": str(tmp_path / "carousel" / "truly-gone"),
    }]
    _write_queue(qp, before)
    reports = reconciler.repair_false_incomplete(queue_path=qp, dry_run=False)
    assert reports == []
    assert json.loads(qp.read_text()) == before


def test_repair_innocence_published_and_other_states_never_touched(tmp_path):
    """INNOCENCE: entries in ANY state other than render_incomplete —
    including a published entry whose disk mismatches its declared count —
    must never be considered by the repair, even if their resolved dir would
    have real PNGs."""
    car_dir = tmp_path / "carousel" / "some-published-topic"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 5)
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [
        {"id": "carousel_pub", "draft_id": "d-pub", "state": "published",
         "slide_count": 9999, "carousel_path": str(car_dir)},
        {"id": "carousel_drafted", "draft_id": "d-draft", "state": "drafted",
         "slide_count": 5, "carousel_path": str(car_dir)},
    ]
    _write_queue(qp, before)
    reports = reconciler.repair_false_incomplete(queue_path=qp, dry_run=False)
    assert reports == []
    assert json.loads(qp.read_text()) == before


def test_repair_exclude_id_hard_excludes_entry(tmp_path):
    """--exclude-id: an operator override that skips a specific entry even
    though it would otherwise resolve cleanly (e.g. a genuinely-bad carousel
    that happens to share the render_incomplete state)."""
    car_dir = tmp_path / "carousel" / "excluded-topic"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    before = [{
        "id": "carousel_excluded", "draft_id": "d-excl", "state": reconciler.RENDER_INCOMPLETE_STATE,
        "slide_count": 8, "carousel_path": str(car_dir),
    }]
    _write_queue(qp, before)
    reports = reconciler.repair_false_incomplete(
        queue_path=qp, dry_run=False, exclude_ids={"carousel_excluded"},
    )
    assert reports == []
    assert json.loads(qp.read_text()) == before


def test_repair_preserves_other_queue_entries_byte_for_byte(tmp_path):
    car_dir = tmp_path / "carousel" / "indonesia-visafree-myth-reality"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    qp = tmp_path / "queue" / "human-review-queue.json"
    published = {"id": "carousel_pub", "draft_id": "d0", "state": "published", "slide_count": 9999}
    _write_queue(qp, [
        published,
        {"id": "carousel_old", "draft_id": "d-old", "state": reconciler.RENDER_INCOMPLETE_STATE,
         "slide_count": 8, "carousel_path": str(car_dir)},
    ])
    reconciler.repair_false_incomplete(queue_path=qp, dry_run=False)
    queue = json.loads(qp.read_text())
    assert queue[0] == published
    assert queue[1]["state"] == "drafted"


# ── HIGH #5: staging + atomic swap in _persist_local_artifacts ─────────────


def test_persist_local_artifacts_rerender_replaces_stale_pngs_atomically(tmp_path):
    """A shorter re-render (9 -> 8 slides) must fully replace the old
    slides_dir contents via the staging+swap — no ghost 09.png survives, and
    content is genuinely swapped, not just counted (Codex red-team HIGH #5:
    the old in-place clear+copy left a window where a partial dir was
    observable to a concurrent reader; the new staging+swap must still fully
    replace content end to end)."""
    out_root = tmp_path / "output"
    src = tmp_path / "render-tmp-1"
    src.mkdir()
    first_pngs = []
    for i in range(1, 10):  # 9 slides
        p = src / f"{i:02d}.png"
        p.write_bytes(b"\x89PNG-v1")
        first_pngs.append(p)
    car_dir = html._persist_local_artifacts(
        draft_id="rerender1", topic="Topic", png_paths=first_pngs,
        drive_url="https://drive/x", weak_count=0, fact_check_status="pass",
        intended_slide_count=9, out_root=out_root, rendered_at="2026-07-16T00:00:00Z",
    )
    assert html.derive_slide_count(car_dir / "slides") == 9
    assert (car_dir / "slides" / "09.png").is_file()

    src2 = tmp_path / "render-tmp-2"
    src2.mkdir()
    second_pngs = []
    for i in range(1, 9):  # 8 slides — a shorter re-render
        p = src2 / f"{i:02d}.png"
        p.write_bytes(b"\x89PNG-v2")
        second_pngs.append(p)
    car_dir2 = html._persist_local_artifacts(
        draft_id="rerender1", topic="Topic", png_paths=second_pngs,
        drive_url="https://drive/y", weak_count=0, fact_check_status="pass",
        intended_slide_count=8, out_root=out_root, rendered_at="2026-07-16T01:00:00Z",
    )
    assert car_dir2 == car_dir  # same draft/day -> same carousel dir
    assert html.derive_slide_count(car_dir / "slides") == 8
    assert not (car_dir / "slides" / "09.png").exists()  # ghost must be gone
    assert (car_dir / "slides" / "01.png").read_bytes() == b"\x89PNG-v2"  # content actually swapped
    # no leftover staging/old dirs
    assert not list(car_dir.glob(".slides.new.*"))
    assert not list(car_dir.glob(".slides.old.*"))


def test_persist_local_artifacts_failed_copy_leaves_old_slides_untouched(tmp_path, monkeypatch):
    """Rollback safety of the staging+swap (HIGH #5): if the NEW copy fails
    verification, the OLD slides_dir (from a prior successful persist) must
    be left completely intact — never partially clobbered."""
    import shutil

    out_root = tmp_path / "output"
    src = tmp_path / "render-tmp-1"
    src.mkdir()
    first_pngs = [src / "01.png", src / "02.png"]
    for p in first_pngs:
        p.write_bytes(b"\x89PNG-good")
    car_dir = html._persist_local_artifacts(
        draft_id="rollback1", topic="Topic", png_paths=first_pngs,
        drive_url="https://drive/x", weak_count=0, fact_check_status="pass",
        intended_slide_count=2, out_root=out_root, rendered_at="2026-07-16T00:00:00Z",
    )
    assert html.derive_slide_count(car_dir / "slides") == 2

    src2 = tmp_path / "render-tmp-2"
    src2.mkdir()
    second_pngs = [src2 / "01.png", src2 / "02.png", src2 / "03.png"]
    for p in second_pngs:
        p.write_bytes(b"\x89PNG-bad")

    real_copy2 = shutil.copy2

    def _flaky_copy2(s, d, *a, **kw):
        if Path(s).name == "03.png":
            return  # silently drop -> staging verification will raise
        return real_copy2(s, d, *a, **kw)

    monkeypatch.setattr(shutil, "copy2", _flaky_copy2)
    with pytest.raises(RuntimeError, match="completeness mismatch"):
        html._persist_local_artifacts(
            draft_id="rollback1", topic="Topic", png_paths=second_pngs,
            drive_url="https://drive/y", weak_count=0, fact_check_status="pass",
            intended_slide_count=3, out_root=out_root, rendered_at="2026-07-16T01:00:00Z",
        )
    # OLD content must survive untouched — the swap never happened
    assert html.derive_slide_count(car_dir / "slides") == 2
    assert (car_dir / "slides" / "01.png").read_bytes() == b"\x89PNG-good"
    assert not list(car_dir.glob(".slides.new.*"))  # staging cleaned up


# ── HIGH #5b: render_incomplete is repointable by a complete re-render ─────


def test_render_incomplete_entry_is_repointed_by_a_complete_rerender(tmp_path):
    """A re-render that reaches _append_review_queue has ALREADY passed the
    A1 gate (verified complete) — repoint FROM render_incomplete must succeed
    so a fixed carousel flows back into review instead of staying stuck
    pointing at the old incomplete artifact forever (Codex red-team HIGH #5)."""
    entry_old = {
        "id": "carousel_old_id", "draft_id": "d-stuck", "state": "render_incomplete",
        "carousel_path": "/old", "slides_dir": "/old/slides", "slide_count": 0,
        "state_history": [{"state": "render_incomplete", "at": "t0"}],
    }
    entry_new = {
        "id": "carousel_new_id", "draft_id": "d-stuck", "topic_slug": "x", "topic": "X",
        "drafted_at": "t1", "carousel_path": "/new", "slides_dir": "/new/slides",
        "drive_url": "https://drive/y", "media_type": "carousel", "slide_count": 8,
        "intended_slide_count": 8, "critic_overall_verdict": "legibility_only_pass",
        "critic_summary": "all slides converged", "fact_check_status": None,
        "state": "drafted", "state_history": [{"state": "drafted", "at": "t1"}],
        "instagram_post_url": None, "instagram_published_at": None, "engagement_metrics": None,
    }
    qp = tmp_path / "queue.json"
    qp.write_text(json.dumps([entry_old]), encoding="utf-8")
    appended = html._append_review_queue(entry_new, queue_path=qp)
    assert appended is True
    queue = json.loads(qp.read_text())
    assert len(queue) == 1  # repointed, not appended as a second entry
    item = queue[0]
    assert item["id"] == "carousel_old_id"  # identity/ref_code survives repoint
    assert item["state"] == "drafted"  # un-stuck
    assert item["slides_dir"] == "/new/slides"
    assert item["slide_count"] == 8
    assert item["intended_slide_count"] == 8


# ── HIGH #2: _verify_visibility_or_backfill never lies "drafted" ───────────


def test_backfill_visibility_never_appends_drafted_when_disk_mismatches_intent(tmp_path, monkeypatch):
    """HIGH #2 (2026-07-16): DB row already status='rendered' but
    _publish_visibility failed AFTER wiping/never-populating slides_dir
    (disk=0) — a real, reproduced scenario. The old code appended a normal
    'drafted' entry with slide_count=0 anyway. Must now land as
    render_incomplete, never a lying 'drafted'."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "wr2-output"))
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "topic": "Some Topic", "drive_url": "https://drive/z",
        "slides_json": json.dumps({"slides": [{}] * 9}),  # DB says 9 intended
    }
    result = reconciler._verify_visibility_or_backfill(row, dry_run=False)
    assert result == "backfilled_incomplete"

    qp = tmp_path / "wr2-output" / "queue" / "human-review-queue.json"
    queue = json.loads(qp.read_text())
    assert len(queue) == 1
    entry = queue[0]
    assert entry["state"] == reconciler.RENDER_INCOMPLETE_STATE
    assert entry["slide_count"] == 0
    assert entry["intended_slide_count"] == 9


def test_backfill_visibility_appends_drafted_only_when_disk_matches_intent(tmp_path, monkeypatch):
    """INNOCENCE: a genuinely complete backfill (disk == DB-declared intent,
    both > 0) must still land as a normal reviewable 'drafted' entry."""
    monkeypatch.setenv("WR2_OUTPUT_ROOT", str(tmp_path / "wr2-output"))
    draft_id = "22222222-2222-2222-2222-222222222222"
    car_dir = tmp_path / "wr2-output" / "carousel" / f"missing-{draft_id[:8]}"
    _make_pngs(car_dir / "slides", 3)
    row = {
        "id": draft_id, "topic": "Some Topic", "drive_url": "https://drive/z",
        "slides_json": json.dumps({"slides": [{}] * 3}),
    }
    result = reconciler._verify_visibility_or_backfill(row, dry_run=False)
    assert result == "backfilled"

    qp = tmp_path / "wr2-output" / "queue" / "human-review-queue.json"
    entry = json.loads(qp.read_text())[0]
    assert entry["state"] == "drafted"
    assert entry["slide_count"] == 3
    assert entry["intended_slide_count"] == 3
