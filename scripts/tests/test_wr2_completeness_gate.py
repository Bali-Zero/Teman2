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
    """(i) slides.json/meta.json agree with disk at N-1; only the queue's
    own slide_count field is wrong -> queue_stale, carousel is genuinely
    complete at the smaller count."""
    car_dir = tmp_path / "carousel" / "topic-abcd1234"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8}))

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


def test_classify_genuinely_incomplete_when_expected_exceeds_disk(tmp_path):
    """(ii) meta.json/slides.json say N but disk only has N-1 -> genuinely
    incomplete: a real slide is missing from the durable artifact."""
    car_dir = tmp_path / "carousel" / "topic-deadbeef"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 9}))

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


def test_no_ground_truth_defaults_to_genuinely_incomplete_conservative(tmp_path):
    """When neither slides.json nor meta.json exist, the classifier must NOT
    silently trust disk as "complete" — conservative genuinely_incomplete,
    never a silent auto-lower of the declared count."""
    car_dir = tmp_path / "carousel" / "topic-noground"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)  # no meta.json, no slides.json

    qp = tmp_path / "queue" / "human-review-queue.json"
    _write_queue(qp, [{
        "id": "carousel_w", "draft_id": "d4", "state": "drafted",
        "slide_count": 9, "carousel_path": str(car_dir), "slides_dir": str(slides_dir),
    }])
    mismatches = reconciler.check_completeness(queue_path=qp)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.classification == "genuinely_incomplete"
    assert m.expected is None and m.expected_source == "none"


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
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8}))
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
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8}))
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
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 9}))
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


def test_backfill_apply_preserves_other_queue_entries(tmp_path):
    """INNOCENCE: entries with no mismatch (including published history) must
    be byte-for-byte preserved by the backfill write."""
    car_dir = tmp_path / "carousel" / "topic-abcd1234"
    slides_dir = car_dir / "slides"
    _make_pngs(slides_dir, 8)
    (car_dir / "meta.json").write_text(json.dumps({"slide_count": 8}))
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
