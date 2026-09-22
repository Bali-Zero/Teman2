"""Unit tests for scripts/wr2_ig_dashboard_import.py.

Builds a minimal dashboard .xlsx in tmp_path (same 3-sheet layout as the real
90-day export) plus a fake queue, then runs the importer: shortcode matching,
dashboard_-prefixed merge without clobbering scraper keys, atomic write +
backup, dry-run purity, unmatched-shortcode accounting.
"""
from __future__ import annotations

import importlib.util
import fcntl
import json
import sys
import threading
from pathlib import Path
from types import ModuleType

import openpyxl
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


imp = _load("wr2_ig_dashboard_import")

HEADERS = ["Data", "Carosello", "Link", "Views", "Viewers", "Interactions",
           "Accounts engaged", "Shares", "Likes", "Comments", "Saves",
           "% Views da follower", "Views da Home", "Views da Profilo",
           "Views da Altro", "Profile activity", "Profile visits", "Follows",
           "Engagement rate (Interactions/Viewers)", "Share rate (Shares/Viewers)", "Note"]


def _make_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Caroselli"
    ws.append(["Content insights"])
    ws.append([None] * len(HEADERS))
    ws.append(HEADERS)
    ws.append(["2026-09-09", "Supervising a Bali project. Deported.",
               "https://www.instagram.com/p/DdEAXq/", 6573, 3297, 112, 82,
               38, 33, 21, 17, 0.617, 6251, 46, 276, 22, 20, 2, 0.017, 0.0058, ""])
    ws.append(["2026-09-22", "One screen. Different roles",
               "https://www.instagram.com/p/DdlbuM/", 610, 224, 2, 3,
               0, 2, 0, 0, 0.998, 610, 0, 0, 1, 1, 0, 0.003, 0, ""])
    ws.append(["", "TOTALE", "", 371429, 30064, 10015, 8131, 3916, 3383, 329,
               2241, "", 285001, 20185, 16596, 5763, 4696, 981, 0.027, 0.0105, ""])
    acc = wb.create_sheet("Account")
    acc.append(["Instagram Account insights"])
    acc.append(["Metrica", "Valore"])
    acc.append(["Views", 70409])
    acc.append(["Total followers", 10776])
    ore = wb.create_sheet("Orari attivi follower")
    ore.append(["Most active times"])
    ore.append([None] * 8)
    ore.append(["Fascia", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"])
    ore.append(["18:00", 4010, 3977, 3964, 3947, 3933, 3864, 3867])
    ore.append(["Picco", "18:00", "18:00", "18:00", "18:00", "18:00", "18:00", "18:00"])
    wb.save(path)


def _make_queue(path: Path) -> None:
    queue = [
        {"id": "a1", "state": "published",
         "instagram_post_url": "https://www.instagram.com/p/DdEAXq/",
         "ig_media_id": "17895695668004550",
         "engagement_metrics": {"likes": 30, "source": "ig_metrics_scraper",
                                "scraped_at": "2026-09-10T00:00:00+00:00"}},
        {"id": "a2", "state": "published",
         "instagram_post_url": "https://www.instagram.com/p/NOPE12/"},
    ]
    path.write_text(json.dumps(queue))


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["wr2_ig_dashboard_import.py", *argv])
    return imp.main()


def test_merge_matches_shortcode_and_preserves_scraper_keys(tmp_path, monkeypatch):
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    queue = json.loads(q.read_text())
    m = queue[0]["engagement_metrics"]
    assert m["dashboard_views"] == 6573
    assert m["dashboard_follower_share"] == 0.617
    assert m["dashboard_follows"] == 2
    assert m["dashboard_engagement_rate"] == 0.017
    assert m["dashboard_share_rate"] == 0.0058
    assert m["dashboard_export"] == "rep.xlsx"
    assert m["dashboard_source"] == "dashboard_xlsx"
    assert m["dashboard_post_date"] == "2026-09-09"
    # scraper keys untouched
    assert m["likes"] == 30
    assert m["source"] == "ig_metrics_scraper"
    assert m["scraped_at"] == "2026-09-10T00:00:00+00:00"


def test_unmatched_dashboard_post_leaves_queue_item_alone(tmp_path, monkeypatch, capsys):
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    out = capsys.readouterr().out
    assert "matched=1" in out
    assert "DdlbuM" in out  # reported as unmatched shortcode
    queue = json.loads(q.read_text())
    assert "engagement_metrics" not in queue[1]


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    before = q.read_text()
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q), "--dry-run") == 0
    assert q.read_text() == before
    assert list(tmp_path.glob("queue.json.bak-dashimport-*")) == []


def test_summary_saved_with_account_and_best_hours(tmp_path, monkeypatch):
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    summ = tmp_path / "summary.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q),
                "--save-summary", str(summ)) == 0
    s = json.loads(summ.read_text())
    assert s["posts_parsed"] == 2
    assert s["account_total_followers"] == 10776
    assert s["best_hours"]["Lun"] == "18:00"


def test_row_without_link_column_never_matches_note_text(tmp_path, monkeypatch, capsys):
    # regression: a sheet WITHOUT a Link column must not read shortcodes
    # out of the last (Note) column.
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Caroselli"
    ws.append(["Content insights"])
    ws.append([None] * 3)
    ws.append(["Data", "Carosello", "Note"])
    ws.append(["2026-09-09", "Some post",
               "see https://www.instagram.com/p/DdEAXq/ for ref"])
    xlsx = tmp_path / "nolink.xlsx"
    wb.save(xlsx)
    q = tmp_path / "queue.json"
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    out = capsys.readouterr().out
    assert "dropped_no_shortcode=1" in out
    assert "WARNING missing_columns: Views," in out
    queue = json.loads(q.read_text())
    assert "engagement_metrics" not in queue[0] or \
        queue[0]["engagement_metrics"].get("dashboard_source") != "dashboard_xlsx"


@pytest.mark.parametrize("kind", ["p", "reel", "reels", "tv", "balizero.id/p"])
def test_every_url_variant_matches(tmp_path, monkeypatch, kind):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Caroselli"
    ws.append(["Content insights"])
    ws.append([None] * 3)
    ws.append(["Data", "Carosello", "Link"])
    ws.append(["2026-09-09", "Reel post", f"https://www.instagram.com/{kind}/DdEAXq/"])
    xlsx = tmp_path / "reels.xlsx"
    wb.save(xlsx)
    q = tmp_path / "queue.json"
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    queue = json.loads(q.read_text())
    assert queue[0]["engagement_metrics"].get("dashboard_source") == "dashboard_xlsx"


def test_missing_xlsx_returns_2(tmp_path, monkeypatch):
    q = tmp_path / "queue.json"
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(tmp_path / "nope.xlsx"),
                "--queue", str(q)) == 2


def test_xlsx_without_header_row_returns_2_and_writes_nothing(tmp_path, monkeypatch):
    wb = openpyxl.Workbook()
    wb.active.title = "Caroselli"
    xlsx = tmp_path / "noheader.xlsx"
    wb.save(xlsx)
    q = tmp_path / "queue.json"
    _make_queue(q)
    before = q.read_text()
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 2
    assert q.read_text() == before


def test_backup_is_the_pre_import_queue(tmp_path, monkeypatch):
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    before = q.read_text()
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    baks = list(tmp_path.glob("queue.json.bak-dashimport-*"))
    assert len(baks) == 1
    assert baks[0].read_text() == before
    assert "dashboard_views" in q.read_text()


def test_scraper_refresh_keeps_dashboard_keys(tmp_path, monkeypatch):
    # the Graph API cannot re-supply dashboard_* — a scraper refresh after an
    # import must carry them over, not replace engagement_metrics wholesale.
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    scraper = _load("wr2_ig_metrics_scraper")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(scraper, "fetch_metrics", lambda media_id, token: {
        "likes": 41, "reach": 900, "source": "ig_metrics_scraper",
        "scraped_at": "2026-09-23T00:00:00+00:00"})
    monkeypatch.setattr(sys, "argv", ["wr2_ig_metrics_scraper.py", "--queue", str(q),
                                      "--max-age-days", "0"])
    assert scraper.main() == 0
    m = json.loads(q.read_text())[0]["engagement_metrics"]
    assert m["likes"] == 41  # the scraper's own keys are refreshed
    assert m["dashboard_views"] == 6573  # the dashboard's survive
    assert m["dashboard_follower_share"] == 0.617


def test_reimport_replaces_the_previous_dashboard_snapshot(tmp_path, monkeypatch):
    # a column absent from the new export must not leave the old value behind
    # under a fresh timestamp; scraper keys stay.
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Caroselli"
    ws.append(["Data", "Carosello", "Link", "Views"])
    ws.append(["2026-09-09", "Same post", "https://www.instagram.com/p/DdEAXq/", 7000])
    second = tmp_path / "rep30.xlsx"
    wb.save(second)
    assert _run(monkeypatch, "--xlsx", str(second), "--queue", str(q)) == 0
    m = json.loads(q.read_text())[0]["engagement_metrics"]
    assert m["dashboard_views"] == 7000
    assert "dashboard_follows" not in m
    assert m["dashboard_export"] == "rep30.xlsx"
    assert m["likes"] == 30


def test_import_reads_and_writes_under_the_queue_lock(tmp_path, monkeypatch):
    # another writer holds the queue lock and appends an item; the import must
    # wait for it and build on that write, not erase it with a stale baseline.
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    monkeypatch.setattr(sys, "argv", ["wr2_ig_dashboard_import.py", "--xlsx", str(xlsx),
                                      "--queue", str(q)])
    rc: list[int] = []
    with open(q.with_suffix(".lock"), "w") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        t = threading.Thread(target=lambda: rc.append(imp.main()))
        t.start()
        t.join(0.5)
        assert t.is_alive()  # blocked on the lock
        queue = json.loads(q.read_text())
        queue.append({"id": "a3", "state": "drafted"})
        q.write_text(json.dumps(queue))
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
    t.join(10)
    assert rc == [0]
    queue = json.loads(q.read_text())
    assert [i["id"] for i in queue] == ["a1", "a2", "a3"]
    assert queue[0]["engagement_metrics"]["dashboard_views"] == 6573


def test_import_during_a_scraper_fetch_survives_its_write(tmp_path, monkeypatch):
    # the scraper fetches for minutes before writing; an import landing in that
    # window must survive the scraper's write.
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    scraper = _load("wr2_ig_metrics_scraper")
    imp_argv = ["wr2_ig_dashboard_import.py", "--xlsx", str(xlsx), "--queue", str(q)]
    scr_argv = ["wr2_ig_metrics_scraper.py", "--queue", str(q), "--max-age-days", "0"]

    def fetch_while_importing(media_id, token):
        sys.argv = imp_argv
        assert imp.main() == 0
        sys.argv = scr_argv
        return {"likes": 41, "source": "ig_metrics_scraper",
                "scraped_at": "2026-09-23T00:00:00+00:00"}

    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(scraper, "fetch_metrics", fetch_while_importing)
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", scr_argv)
    assert scraper.main() == 0
    m = json.loads(q.read_text())[0]["engagement_metrics"]
    assert m["likes"] == 41
    assert m["dashboard_views"] == 6573


def _mirror_queue(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home"
    q = home / imp.QUEUE_REL
    q.parent.mkdir(parents=True)
    _make_queue(q)
    monkeypatch.setattr(imp.Path, "home", classmethod(lambda cls: home))
    return q


def test_refuses_to_write_the_pull_mirror(tmp_path, monkeypatch):
    # off Pro, this path is wr2-queue-pull.sh's remote-wins mirror: a write
    # there is erased by the next pull, so the import must not pretend it landed.
    xlsx = tmp_path / "rep.xlsx"
    _make_xlsx(xlsx)
    q = _mirror_queue(tmp_path, monkeypatch)
    before = q.read_text()
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 2
    assert q.read_text() == before
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q), "--dry-run") == 0


def test_writes_the_same_path_when_it_is_the_ssot(tmp_path, monkeypatch):
    xlsx = tmp_path / "rep.xlsx"
    _make_xlsx(xlsx)
    q = _mirror_queue(tmp_path, monkeypatch)
    monkeypatch.setattr(imp, "SSOT_HOME", tmp_path / "home")
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    assert "dashboard_views" in json.loads(q.read_text())[0]["engagement_metrics"]


def test_duplicate_queue_items_all_get_the_snapshot(tmp_path, monkeypatch):
    xlsx = tmp_path / "rep.xlsx"
    q = tmp_path / "queue.json"
    _make_xlsx(xlsx)
    _make_queue(q)
    queue = json.loads(q.read_text())
    queue.append({"id": "a1-dup", "state": "published",
                  "instagram_post_url": "https://www.instagram.com/p/DdEAXq/"})
    q.write_text(json.dumps(queue))
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 0
    queue = json.loads(q.read_text())
    assert queue[0]["engagement_metrics"]["dashboard_views"] == 6573
    assert queue[2]["engagement_metrics"]["dashboard_views"] == 6573


def test_corrupt_xlsx_returns_2(tmp_path, monkeypatch):
    xlsx = tmp_path / "corrupt.xlsx"
    xlsx.write_bytes(b"not a zip archive")
    q = tmp_path / "queue.json"
    _make_queue(q)
    assert _run(monkeypatch, "--xlsx", str(xlsx), "--queue", str(q)) == 2
