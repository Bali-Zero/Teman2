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
