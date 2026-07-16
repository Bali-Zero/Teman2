"""Tests for wr2_queue_pull_merge (split-brain cure, 2026-07-13).

Guilt: a local publish transition survives the pull and lands in push_back.
Innocence: remote (Pro SSOT) wins everywhere else; junk/garbage never rides
the push-back channel into an ssh command line.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

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


merge = _load("wr2_queue_pull_merge")


def _remote_drafted(eid: str = "carousel_1") -> dict:
    return {"id": eid, "topic": "ITAS vs KITAS", "state": "drafted",
            "slide_count": 9, "instagram_post_url": None}


def _local_published(eid: str = "carousel_1", url: str = "https://www.instagram.com/p/AbC123/") -> dict:
    return {"id": eid, "topic": "ITAS vs KITAS", "state": "published",
            "slide_count": 9, "instagram_post_url": url,
            "instagram_published_at": "2026-07-13T02:00:00Z",
            "state_history": [{"state": "published", "by": "wr2-control-app"}]}


# ── guilt: publish transitions survive the pull ──────────────────────────────

def test_local_publish_survives_remote_drafted():
    merged, report = merge.merge_queues([_remote_drafted()], [_local_published()])
    assert merged[0]["state"] == "published"
    assert merged[0]["instagram_post_url"] == "https://www.instagram.com/p/AbC123/"
    assert report["protected"] == ["carousel_1"]
    assert report["push_back"][0]["ref_code"].startswith("WR2-")
    assert report["push_back"][0]["ig_url"] == "https://www.instagram.com/p/AbC123/"


def test_local_only_entry_is_kept_but_never_pushed_back():
    extra = _local_published("app_upload_1")
    merged, report = merge.merge_queues([_remote_drafted()], [_local_published(), extra])
    assert [e["id"] for e in merged] == ["carousel_1", "app_upload_1"]
    assert report["local_only"] == ["app_upload_1"]
    assert [e["id"] for e in report["push_back"]] == ["carousel_1"]


# ── innocence: remote wins everywhere else ───────────────────────────────────

def test_remote_wins_when_local_not_published():
    loc = _remote_drafted()
    loc["state"] = "reviewed"
    rem = _remote_drafted()
    rem["state"] = "drafted_needs_human_edit"
    merged, report = merge.merge_queues([rem], [loc])
    assert merged[0]["state"] == "drafted_needs_human_edit"
    assert report["protected"] == [] and report["push_back"] == []


def test_remote_published_stays_remote_verbatim():
    rem = _local_published()  # remote already published
    loc = _local_published(url="https://www.instagram.com/p/OTHER/")
    merged, report = merge.merge_queues([rem], [loc])
    assert merged[0]["instagram_post_url"] == "https://www.instagram.com/p/AbC123/"
    assert report["protected"] == []


def test_bogus_ig_url_never_rides_push_back():
    loc = _local_published(url="https://evil'; rm -rf /'")
    merged, report = merge.merge_queues([_remote_drafted()], [loc])
    # entry is still protected locally (merge), but excluded from the ssh channel
    assert merged[0]["state"] == "published"
    assert report["protected"] == ["carousel_1"]
    assert report["push_back"] == []


def test_old_schema_item_id_matching():
    rem = {"item_id": "old_1", "topic": "X", "state": "applied_ready_for_damar"}
    loc = {"item_id": "old_1", "topic": "X", "state": "published",
           "instagram_post_url": "https://www.instagram.com/reel/Zz9/"}
    merged, report = merge.merge_queues([rem], [loc])
    assert merged[0]["state"] == "published"
    assert report["push_back"][0]["ig_url"].endswith("/Zz9/")


def test_cli_writes_merged_and_prints_report(tmp_path):
    r = tmp_path / "r.json"; r.write_text(json.dumps([_remote_drafted()]))
    l = tmp_path / "l.json"; l.write_text(json.dumps([_local_published()]))
    out = tmp_path / "m.json"
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = merge.main(["--remote", str(r), "--local", str(l), "--out", str(out)])
    assert rc == 0
    assert json.loads(out.read_text())[0]["state"] == "published"
    rep = json.loads(buf.getvalue())
    assert rep["protected"] == ["carousel_1"]


def test_cli_corrupt_local_falls_back_to_remote(tmp_path):
    r = tmp_path / "r.json"; r.write_text(json.dumps([_remote_drafted()]))
    l = tmp_path / "l.json"; l.write_text("{not json")
    out = tmp_path / "m.json"
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        rc = merge.main(["--remote", str(r), "--local", str(l), "--out", str(out)])
    assert rc == 0
    assert json.loads(out.read_text())[0]["state"] == "drafted"


# ── archive-blind resurrect fix (2026-07-17) ─────────────────────────────────
# WHY: Pro moves an entry from its live queue to queue-archive.json (archiving
# it). The next pull's remote queue no longer contains that id, so — without
# an archive cross-check — the OLD code classified it as local_only ("new
# local entry") and kept re-adding it to the merged output forever. Live case:
# a golden-visa entry archived on Pro at 17:4x kept reappearing on M5 every
# tick.

def test_archived_local_only_entry_is_dropped_not_resurrected():
    """GUILT: a local entry whose id is present in the freshly-pulled remote
    archive must disappear from the merge output — Pro's archive decision
    wins, it is not resurrected as a "new" local-only entry."""
    archived = _remote_drafted("golden_visa_1")
    merged, report = merge.merge_queues(
        [_remote_drafted("carousel_1")],
        [_remote_drafted("carousel_1"), archived],
        remote_archive=[archived],
    )
    assert [e["id"] for e in merged] == ["carousel_1"]
    assert report["local_only"] == []
    assert report["archived_dropped"] == ["golden_visa_1"]
    assert report["published_local_kept_despite_archive"] == []


def test_published_local_only_entry_survives_archive_on_pro():
    """CRITICAL GUILT (Codex red-team, 2026-07-17): a local entry that is
    ITSELF published* must survive even when its id is in the remote
    archive and absent from the remote queue — push_back only fires from
    the remote loop (for entries still present in the remote queue), so an
    id Pro has already archived can never push_back; dropping it here would
    permanently lose the published state + instagram_post_url with no
    recovery path (live race: M5 publishes A, Pro archives A before the
    next tick's push_back lands)."""
    archived_and_published = _local_published("golden_visa_1")
    merged, report = merge.merge_queues(
        [_remote_drafted("carousel_1")],
        [_remote_drafted("carousel_1"), archived_and_published],
        remote_archive=[_remote_drafted("golden_visa_1")],
    )
    assert [e["id"] for e in merged] == ["carousel_1", "golden_visa_1"]
    assert merged[1]["state"] == "published"
    assert merged[1]["instagram_post_url"] == "https://www.instagram.com/p/AbC123/"
    assert report["local_only"] == ["golden_visa_1"]
    assert report["archived_dropped"] == []
    assert report["published_local_kept_despite_archive"] == ["golden_visa_1"]


def test_genuinely_local_entry_not_in_archive_still_protected():
    """INNOCENCE: a local-only entry whose id is NOT in the remote archive
    must still be kept and reported as local_only — the archive cross-check
    must not become a new way to lose real local-only entries."""
    extra = _local_published("app_upload_1")
    other_archived = _remote_drafted("some_other_archived_id")
    merged, report = merge.merge_queues(
        [_remote_drafted()],
        [_local_published(), extra],
        remote_archive=[other_archived],
    )
    assert [e["id"] for e in merged] == ["carousel_1", "app_upload_1"]
    assert report["local_only"] == ["app_upload_1"]
    assert report["archived_dropped"] == []


def test_entry_in_both_remote_queue_and_archive_queue_wins():
    """INNOCENCE (pathological case): an id present in BOTH the live remote
    queue AND the remote archive is NOT dropped and NOT local_only — the
    live queue wins (kept as a normal remote entry), with a warning flag."""
    rem = _remote_drafted("carousel_1")
    merged, report = merge.merge_queues(
        [rem],
        [],
        remote_archive=[_remote_drafted("carousel_1")],
    )
    assert [e["id"] for e in merged] == ["carousel_1"]
    assert merged[0]["state"] == "drafted"
    assert report["local_only"] == []
    assert report["archived_dropped"] == []
    assert report["queue_and_archive_conflict"] == ["carousel_1"]


def test_no_remote_archive_arg_behaves_as_before():
    """Backward compatibility: remote_archive=None (or omitted) must not
    change any existing behavior — callers that never pass it are unaffected."""
    merged, report = merge.merge_queues([_remote_drafted()], [_local_published()])
    assert merged[0]["state"] == "published"
    assert report["archived_dropped"] == []
    assert report["queue_and_archive_conflict"] == []


def test_cli_remote_archive_flag_drops_archived_entry(tmp_path):
    r = tmp_path / "r.json"; r.write_text(json.dumps([_remote_drafted("carousel_1")]))
    archived = _remote_drafted("golden_visa_1")
    l = tmp_path / "l.json"; l.write_text(json.dumps([_remote_drafted("carousel_1"), archived]))
    a = tmp_path / "a.json"; a.write_text(json.dumps([archived]))
    out = tmp_path / "m.json"
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = merge.main(["--remote", str(r), "--local", str(l), "--out", str(out),
                          "--remote-archive", str(a)])
    assert rc == 0
    assert [e["id"] for e in json.loads(out.read_text())] == ["carousel_1"]
    rep = json.loads(buf.getvalue())
    assert rep["archived_dropped"] == ["golden_visa_1"]


def test_cli_missing_remote_archive_file_degrades_gracefully(tmp_path):
    """A --remote-archive path that doesn't exist (e.g. Pro's archive pull
    failed this tick) must never crash the CLI — degrade to no cross-check."""
    r = tmp_path / "r.json"; r.write_text(json.dumps([_remote_drafted()]))
    l = tmp_path / "l.json"; l.write_text(json.dumps([_local_published()]))
    out = tmp_path / "m.json"
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        rc = merge.main(["--remote", str(r), "--local", str(l), "--out", str(out),
                          "--remote-archive", str(tmp_path / "does-not-exist.json")])
    assert rc == 0
    assert json.loads(out.read_text())[0]["state"] == "published"


# ── external_push_candidates / mark_synced_to_pro — M5->Pro propagation (§B) ─


def _external_manual_entry(**overrides) -> dict:
    entry = {
        "item_id": "external_2026-07-17T090000_my-manual-post",
        "state": "published",
        "instagram_post_url": "https://www.instagram.com/p/ManualPost1/",
        "source": "external_manual",
        "published_at": "2026-07-17T09:00:00+00:00",
        "instagram_published_at": "2026-07-17T09:00:00+00:00",
        "topic": "My manual post",
        "topic_slug": "my-manual-post",
        "slide_count": 0,
        "created_at": "2026-07-17T09:00:00+00:00",
    }
    entry.update(overrides)
    return entry


def test_external_push_candidates_picks_up_unsynced_external_manual_entry():
    local = [_remote_drafted(), _external_manual_entry()]
    candidates = merge.external_push_candidates(local)
    assert [c["item_id"] for c in candidates] == ["external_2026-07-17T090000_my-manual-post"]


def test_external_push_candidates_excludes_already_synced():
    local = [_external_manual_entry(synced_to_pro=True)]
    assert merge.external_push_candidates(local) == []


def test_external_push_candidates_excludes_pipeline_entries():
    # a normal published WR2-pipeline entry (no source=="external_manual") must NEVER
    # be offered for push-back on this channel — that's the OTHER push_back list.
    local = [_local_published()]
    assert merge.external_push_candidates(local) == []


def test_external_push_candidates_excludes_manual_external_source_confusion():
    # "manual_external" (ingest_external_post's convention) is a DIFFERENT origin —
    # must not be conflated with "external_manual" (this feature's exact marker).
    local = [_external_manual_entry(source="manual_external")]
    assert merge.external_push_candidates(local) == []


def test_external_push_candidates_excludes_invalid_payload():
    # a malformed local entry (missing topic_slug here) must never be shipped over
    # ssh as a broken CLI argument.
    entry = _external_manual_entry()
    del entry["topic_slug"]
    assert merge.external_push_candidates([entry]) == []


def test_merge_queues_report_includes_push_back_external():
    _, report = merge.merge_queues([_remote_drafted()], [_external_manual_entry()])
    assert [c["item_id"] for c in report["push_back_external"]] == ["external_2026-07-17T090000_my-manual-post"]


def test_mark_synced_to_pro_marks_matching_entry_only():
    items = [_external_manual_entry(item_id="a"), _external_manual_entry(item_id="b")]
    updated = merge.mark_synced_to_pro(items, "a")
    a = next(i for i in updated if i["item_id"] == "a")
    b = next(i for i in updated if i["item_id"] == "b")
    assert a["synced_to_pro"] is True
    assert "synced_to_pro" not in b
    # pure — input list's dicts not mutated
    assert "synced_to_pro" not in items[0]


def test_mark_synced_to_pro_noop_on_unknown_id():
    items = [_external_manual_entry(item_id="a")]
    updated = merge.mark_synced_to_pro(items, "does-not-exist")
    assert updated == items


def test_mark_synced_then_excluded_from_next_push_candidates():
    entry = _external_manual_entry()
    synced = merge.mark_synced_to_pro([entry], entry["item_id"])
    assert merge.external_push_candidates(synced) == []


def test_cli_mark_synced_item_id_writes_atomically(tmp_path):
    f = tmp_path / "local.json"
    f.write_text(json.dumps([_external_manual_entry(item_id="x")]))
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = merge.main(["--mark-synced-item-id", "x", "--mark-synced-file", str(f)])
    assert rc == 0
    resp = json.loads(buf.getvalue())
    assert resp == {"ok": True, "marked": "x"}
    updated = json.loads(f.read_text())
    assert updated[0]["synced_to_pro"] is True


def test_cli_mark_synced_requires_file_arg():
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = merge.main(["--mark-synced-item-id", "x"])
    assert rc == 2
