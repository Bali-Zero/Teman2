"""
Behavioral tests for pajak_monitor.py's enrichment time budget (R1) and monitor wiring
(M6, M7) — gate REWORK-BUILD on PR #7084 (2026-09-21).

`pajak_monitor.py` imports `agent_job`/`browser_job`. `browser_job` lives only on Pro;
`agent_job.py` is in this repo but imports httpx and structlog. Like the gate's own re-run, both
are STUBBED in `sys.modules` before
`pajak_monitor.py` is loaded via `importlib.util` — the same isolation trick
`test_pajak_parse.py` uses for `pajak_parse.py`. `intel_lake_outbox` (also Pro-only) is stubbed
per-test to CAPTURE what `_write_intel_feed` would have enqueued, since that dict is the only
place `published_at` and `raw_payload` are observable from outside the function.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import time
import types
import zoneinfo
from pathlib import Path

MODULE_DIR = Path(__file__).parent.parent / "cron-agent-python"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pajak"


class _DummyLogger:
    def warning(self, event, **kw):
        pass

    def error(self, event, **kw):
        pass

    def info(self, event, **kw):
        pass


def _install_stub_agent_modules() -> None:
    if "agent_job" not in sys.modules:
        agent_job = types.ModuleType("agent_job")

        class AgentJob:
            pass

        class RunResult:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        async def web_search(*a, **kw):
            return []

        def main(cls):
            pass

        agent_job.AgentJob = AgentJob
        agent_job.RunResult = RunResult
        agent_job.WITA = zoneinfo.ZoneInfo("Asia/Makassar")
        agent_job.main = main
        agent_job.web_search = web_search
        sys.modules["agent_job"] = agent_job

    if "browser_job" not in sys.modules:
        browser_job = types.ModuleType("browser_job")

        class BrowserJob:
            def __init__(self, *a, **kw):
                self.started_at = time.time()
                self._side_effects = []
                self.logger = _DummyLogger()

            async def _check_robots(self, url):
                return True

            async def random_delay(self, a, b):
                return None

            async def fetch_page(self, url):
                return {"html": ""}

            async def send_telegram(self, msg, tier="p0", dedup_key=""):
                return True

            def log_step(self, *a, **kw):
                pass

            def _record_success(self):
                pass

        browser_job.BrowserJob = BrowserJob
        sys.modules["browser_job"] = browser_job


_install_stub_agent_modules()

spec = importlib.util.spec_from_file_location("pajak_monitor", MODULE_DIR / "pajak_monitor.py")
pajak_monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pajak_monitor)


def _install_capturing_outbox() -> list[dict]:
    calls: list[dict] = []
    module = types.ModuleType("intel_lake_outbox")

    def enqueue(producer_name, payload):
        calls.append(payload)

    module.enqueue = enqueue
    sys.modules["intel_lake_outbox"] = module
    return calls


def _make_job(timeout_s=240):
    job = pajak_monitor.PajakMonitorJob()
    job.timeout_s = timeout_s
    return job


class _CapturingLogger:
    """Records `.warning(event, **kw)` calls; `.info`/`.error` are no-ops like `_DummyLogger`."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict]] = []

    def warning(self, event, **kw):
        self.warnings.append((event, kw))

    def error(self, event, **kw):
        pass

    def info(self, event, **kw):
        pass


def _install_capturing_logger(job) -> "_CapturingLogger":
    logger = _CapturingLogger()
    job.logger = logger
    return logger


def _install_capturing_telegram(job) -> list[dict]:
    calls: list[dict] = []

    async def send_telegram(msg, tier="p0", dedup_key=""):
        calls.append({"msg": msg, "tier": tier, "dedup_key": dedup_key})
        return True

    job.send_telegram = send_telegram
    return calls


def _peraturan_item(slug: str, scraped_at: str = "2026-01-01T00:00:00+08:00") -> dict:
    return {
        "url": f"{pajak_monitor.PAJAK_PERATURAN_DETAIL_PREFIX}{slug}",
        "title": f"Peraturan {slug}",
        "source": "pajak_peraturan",
        "scraped_at": scraped_at,
        "type": "tax_regulation",
        "nomor": "1/PMK.02/2026",
        "jenis": "Peraturan Menteri Keuangan",
        "regulation_date": None,
    }


# ─── R1 — enrichment must never blow the job's own time budget ────────────


def test_r1_enrichment_stops_within_budget_when_fetch_page_hangs(tmp_path, monkeypatch):
    """A `fetch_page` that hangs forever must not prevent `_enrich_peraturan_details` from
    returning well within the job's timeout, and `_write_intel_feed` must still write every
    item afterward — enriched or not. Before R1, nothing bounded the per-fetch time or the
    total enrichment time, so this scenario used to let the OUTER `asyncio.wait_for(run(),
    timeout_s)` (browser_job.py) cancel the whole job mid-enrichment: no row written, no URL
    marked seen, no Telegram alert."""
    monkeypatch.setattr(pajak_monitor, "DETAIL_FETCH_TIMEOUT_S", 0.05)
    monkeypatch.setattr(pajak_monitor, "DETAIL_ENRICH_BUDGET_MARGIN_S", 0.0)
    monkeypatch.setattr(pajak_monitor, "INTEL_INCOMING_DIR", tmp_path)

    job = _make_job(timeout_s=0.3)

    async def hanging_fetch_page(url):
        await asyncio.sleep(1_000_000)

    job.fetch_page = hanging_fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    items = [_peraturan_item(f"reg-{i}") for i in range(10)]

    async def scenario():
        # Outer bound is a TEST safety net (fail loud instead of hanging the suite), not the
        # behavior under test — the real bound is R1's own deadline/per-fetch timeout, expected
        # to finish in well under a second.
        await asyncio.wait_for(job._enrich_peraturan_details(items), timeout=5.0)

    asyncio.run(scenario())

    # Every fetch hung and was cut off by the per-fetch timeout — nothing could be enriched.
    assert all("_detail" not in item for item in items)

    outbox_calls = _install_capturing_outbox()
    written = job._write_intel_feed(items)

    assert written == len(items)
    assert len(outbox_calls) == len(items)
    for call, item in zip(outbox_calls, items):
        assert call["published_at"] == item["scraped_at"]
        assert "citation" not in call["raw_payload"]


# ─── M6 — published_at must become the regulation's own date on success ───


def test_m6_published_at_becomes_regulation_date_when_extraction_succeeds(tmp_path, monkeypatch):
    """Kills a monitor mutation that keeps `published_at` as scrape time even when `_detail`
    is present — the entire point of the enrichment is that `published_at` becomes the
    regulation's OWN date, not the day the cron happened to run."""
    monkeypatch.setattr(pajak_monitor, "INTEL_INCOMING_DIR", tmp_path)
    job = _make_job()
    outbox_calls = _install_capturing_outbox()

    item = _peraturan_item("reg-1", scraped_at="2026-06-01T00:00:00+08:00")
    item["_detail"] = {
        "citation": "PERATURAN MENTERI KEUANGAN NOMOR 1/PMK.02/2026",
        "verbatim_excerpt": "PERATURAN MENTERI KEUANGAN NOMOR 1/PMK.02/2026 TENTANG SESUATU.",
        "regulation_date": "2026-01-15T12:00:00Z",
        "jenis": "Peraturan Menteri Keuangan",
        "nomor": "1/PMK.02/2026",
    }

    job._write_intel_feed([item])

    assert len(outbox_calls) == 1
    call = outbox_calls[0]
    assert call["published_at"] == "2026-01-15T12:00:00Z"
    assert call["published_at"] != item["scraped_at"]
    assert call["raw_payload"]["citation"] == item["_detail"]["citation"]
    assert call["raw_payload"]["verbatim_excerpt"] == item["_detail"]["verbatim_excerpt"]
    assert call["raw_payload"]["extractor"] == pajak_monitor.EXTRACTOR_NAME


# ─── M7 — a missing regulation_date must never enrich the item ────────────


def test_m7_missing_regulation_date_never_touches_raw_payload_or_published_at(tmp_path, monkeypatch):
    """Kills a monitor mutation that drops the `regulation_date` requirement before setting
    `item['_detail']`. The synthetic page below has a real, matchable jenis+nomor heading (so
    citation/excerpt WOULD be found) but no `tanggal` field at all — `_enrich_peraturan_details`
    must still leave the item untouched, because a `_detail` without a date would make
    `published_at` become `None` in `_write_intel_feed`."""
    monkeypatch.setattr(pajak_monitor, "INTEL_INCOMING_DIR", tmp_path)
    job = _make_job()

    html_without_date = (
        '<div class="field field--name-field-jenis-dokumen">Peraturan Menteri Keuangan</div>'
        '<div class="field field--name-field-nomor-dokumen">1/PMK.02/2026</div>'
        '<div class="field field--name-field-body-dalam-html">'
        "PERATURAN MENTERI KEUANGAN NOMOR 1/PMK.02/2026 TENTANG SESUATU. Menimbang: a. bahwa."
        "</div>"
    )

    async def fetch_page(url):
        return {"html": html_without_date}

    job.fetch_page = fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    item = _peraturan_item("reg-1", scraped_at="2026-06-01T00:00:00+08:00")

    asyncio.run(job._enrich_peraturan_details([item]))
    assert "_detail" not in item

    outbox_calls = _install_capturing_outbox()
    job._write_intel_feed([item])

    assert len(outbox_calls) == 1
    call = outbox_calls[0]
    assert call["published_at"] == item["scraped_at"]
    assert "citation" not in call["raw_payload"]
    assert "verbatim_excerpt" not in call["raw_payload"]


def test_r1_a_hanging_robots_check_is_bounded_by_the_same_per_page_timeout(tmp_path, monkeypatch):
    """robots.txt is fetched before the detail page; if it hangs (uncached, slow host) it must be
    cut off by the same per-page timeout, not left outside it where it can blow the job."""
    monkeypatch.setattr(pajak_monitor, "DETAIL_FETCH_TIMEOUT_S", 0.05)
    monkeypatch.setattr(pajak_monitor, "DETAIL_ENRICH_BUDGET_MARGIN_S", 0.0)
    monkeypatch.setattr(pajak_monitor, "INTEL_INCOMING_DIR", tmp_path)

    job = _make_job(timeout_s=0.3)

    async def hanging_robots(url):
        await asyncio.sleep(1_000_000)

    async def never_called_fetch_page(url):
        raise AssertionError("fetch_page must not run while robots is unanswered")

    job._check_robots = hanging_robots
    job.fetch_page = never_called_fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    items = [_peraturan_item(f"reg-{i}") for i in range(10)]

    async def scenario():
        await asyncio.wait_for(job._enrich_peraturan_details(items), timeout=5.0)

    asyncio.run(scenario())

    assert all("_detail" not in item for item in items)


# ─── #7087 C1 — pin the deadline arm itself, independent of timing ────────


def test_c1_deadline_is_checked_before_every_fetch_not_after(monkeypatch):
    """Gate PWC-7087 C1: kills G1 (deadline check removed entirely) and G2 (deadline check
    moved to AFTER the fetch instead of before it) by asserting on `fetch_page` CALL COUNT and
    the returned `skipped_for_budget`, not on wall-clock timing (the prior R1 tests' 5 s safety
    net was looser than 10x the per-page timeout, so G1/G2 silently survived them).

    `timeout_s=-1.0` with margin 0 makes the deadline `-1.0` — `self._elapsed()` is always >= 0,
    so the VERY FIRST check (before candidate 0) is already over budget. A correctly-ordered
    check must therefore skip ALL candidates without ever calling `fetch_page`:
    - G1 (check removed): would call `fetch_page` for every candidate → `fetch_calls` non-empty.
    - G2 (check moved after the fetch): would call `fetch_page` exactly ONCE (candidate 0) before
      the first post-fetch check catches it and breaks → `fetch_calls` has exactly 1 entry.
    - Correct: `fetch_calls` stays empty, `skipped_for_budget == len(candidates)`.
    """
    monkeypatch.setattr(pajak_monitor, "DETAIL_FETCH_TIMEOUT_S", 5.0)
    monkeypatch.setattr(pajak_monitor, "DETAIL_ENRICH_BUDGET_MARGIN_S", 0.0)

    job = _make_job(timeout_s=-1.0)

    fetch_calls: list[str] = []

    async def fetch_page(url):
        fetch_calls.append(url)
        return {"html": ""}

    job.fetch_page = fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    items = [_peraturan_item(f"reg-{i}") for i in range(5)]

    skipped = asyncio.run(job._enrich_peraturan_details(items))

    assert fetch_calls == []
    assert skipped == len(items)


# ─── #7074 C1 — _write_intel_feed's per-item host guard, behaviorally ─────


def test_c1_write_intel_feed_labels_by_real_host_skips_hostless_and_continues(tmp_path, monkeypatch):
    """Gate PWC-7074 C1: kills three survived mutations at once with one behavioral run over
    FOUR items, a hostless one placed in the MIDDLE:
    - M2 (`source_host(url) or "pajak.go.id"` fallback): would give the hostless item the
      `pajak.go.id` label and enqueue it anyway — checked by asserting no call carries the
      hostless item's URL.
    - M3 (`continue` → `break` on no-host): would abort the WHOLE loop at the hostless item,
      losing both `count` and the enqueue calls for every item AFTER it — checked by asserting
      the items placed after the hostless one still get written and enqueued.
    - M5 (label re-hardcoded as `"pajak.go." + "id"`): would label EVERY item `pajak.go.id`
      regardless of its real host — checked by asserting the non-pajak item's own real host.
    """
    monkeypatch.setattr(pajak_monitor, "INTEL_INCOMING_DIR", tmp_path)
    job = _make_job()
    outbox_calls = _install_capturing_outbox()

    item_pajak = _peraturan_item("reg-1")
    item_hostless = {**_peraturan_item("reg-2"), "url": "nb: NB-INTEL-Tax"}
    item_other_host = {**_peraturan_item("reg-3"), "url": "https://cnbcindonesia.com/news/x"}
    item_after = {**_peraturan_item("reg-4"), "url": "https://ortax.org/some-article"}
    items = [item_pajak, item_hostless, item_other_host, item_after]

    written = job._write_intel_feed(items)

    # M3 guard: the local JSON write happens for every item regardless of the host guard.
    assert written == len(items)

    # M2/M3 guard: exactly the 3 items WITH a real host got enqueued — the hostless one never
    # reached _lake_enqueue, and the two items AFTER it were not skipped.
    enqueued_urls = [call["canonical_url"] for call in outbox_calls]
    assert enqueued_urls == [item_pajak["url"], item_other_host["url"], item_after["url"]]

    by_url = {call["canonical_url"]: call for call in outbox_calls}
    # M5 guard: each item's label is ITS OWN real host, never a hardcoded "pajak.go.id".
    assert by_url[item_pajak["url"]]["source_domain"] == "pajak.go.id"
    assert by_url[item_other_host["url"]]["source_domain"] == "cnbcindonesia.com"
    assert by_url[item_after["url"]]["source_domain"] == "ortax.org"


# ─── lake row content_hash and title — gate-7125 survivors G11/G12 ────────


def test_lake_row_content_hash_reads_title_and_url_and_title_is_not_cut_short(tmp_path, monkeypatch):
    """Gate-7125 survivors, one behavioral run:
    - G11 (`content_hash` from the title alone): two items with the SAME title on different
      URLs would get the same hash — checked by asserting their hashes differ. The symmetric
      case (same URL, different title) is checked too, so a url-only hash reds as well.
    - G12 (lake `title` cut to 50 chars): a 200-char title must reach the lake whole; only
      the 500-char cap applies.
    """
    monkeypatch.setattr(pajak_monitor, "INTEL_INCOMING_DIR", tmp_path)
    job = _make_job()
    outbox_calls = _install_capturing_outbox()

    shared_title = "Peraturan Menteri Keuangan Nomor 1 Tahun 2026"
    item_a = {**_peraturan_item("reg-a"), "title": shared_title}
    item_b = {**_peraturan_item("reg-b"), "title": shared_title}
    item_a_retitled = {**item_a, "title": shared_title + " (perubahan)"}
    long_title = ("Tata Cara Pelaksanaan Hak dan Pemenuhan Kewajiban Perpajakan " * 4)[:200]
    item_long = {**_peraturan_item("reg-long"), "title": long_title}
    item_over_cap = {**_peraturan_item("reg-over-cap"), "title": "x" * 600}

    job._write_intel_feed([item_a, item_b, item_a_retitled, item_long, item_over_cap])

    hashes = [call["content_hash"] for call in outbox_calls]
    assert len(hashes) == 5
    assert hashes[0] != hashes[1]
    assert hashes[0] != hashes[2]
    assert outbox_calls[3]["title"] == long_title
    assert outbox_calls[4]["title"] == "x" * 500


# ─── zero-yield signal — ledger `pajak-direct-sources-have-no-zero-yield-alarm` ────
#
# Both direct pajak.go.id sources (index-peraturan, siaran-pers-page) once died silently:
# 0 parsed rows, job still exited `ok`, because `log_step` only records `duration_s`.
# `_fetch_direct_sources`/`_signal_zero_yield` are tested directly (like `_enrich_peraturan_
# details`/`_write_intel_feed` above), not through the whole `run()`, since `run()` also
# shells out to `redis-cli` (via `_get_seen_urls`/`_mark_seen`), which this test file has no
# reason to depend on.

INDEX_HTML = (FIXTURES_DIR / "index.html").read_text()
SIARAN_HTML = (FIXTURES_DIR / "siaran.html").read_text()

_ZERO_ROWS_HTML = "<html><body><div class=\"view-content\"></div></body></html>"


def test_zero_yield_signal_fires_when_both_direct_sources_parse_zero_rows():
    """Guilt: a fixture page with zero rows (Drupal `view-content` with no `views-row`
    children — same shape a DJP markup change produces) drives the signal for BOTH direct
    sources, via the structured warning log and a `digest`-tier (never `p0`, never `log` —
    `log` spools to disk only and is never sent) Telegram heartbeat."""
    job = _make_job()
    logger = _install_capturing_logger(job)
    tg_calls = _install_capturing_telegram(job)

    async def fetch_page(url):
        return {"html": _ZERO_ROWS_HTML}

    job.fetch_page = fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    async def scenario():
        items, zero_yield = await job._fetch_direct_sources()
        if zero_yield:
            await job._signal_zero_yield(zero_yield)
        return items, zero_yield

    items, zero_yield = asyncio.run(scenario())

    assert items == []
    assert zero_yield == ["index-peraturan", "siaran-pers-page"]

    warned_sources = sorted(
        kw["source"] for event, kw in logger.warnings if event == "pajak_direct_source_zero_yield"
    )
    assert warned_sources == ["index-peraturan", "siaran-pers-page"]

    assert len(tg_calls) == 1
    assert tg_calls[0]["tier"] == "digest"
    assert "index-peraturan" in tg_calls[0]["msg"]
    assert "siaran-pers-page" in tg_calls[0]["msg"]


def test_zero_yield_signal_does_not_fire_when_direct_sources_parse_rows():
    """Innocence: the real fixtures (index.html, siaran.html — nonzero rows) must not trip
    the signal. Also kills an inverted-condition mutation (`if items_peraturan:` instead of
    `if not items_peraturan:`), which would flag every healthy run as zero-yield."""
    job = _make_job()
    logger = _install_capturing_logger(job)
    tg_calls = _install_capturing_telegram(job)

    async def fetch_page(url):
        return {"html": INDEX_HTML if "peraturan" in url else SIARAN_HTML}

    job.fetch_page = fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    items, zero_yield = asyncio.run(job._fetch_direct_sources())

    assert len(items) > 0
    assert zero_yield == []
    assert not any(event == "pajak_direct_source_zero_yield" for event, _ in logger.warnings)
    assert tg_calls == []


def test_zero_yield_signal_fires_for_only_the_dead_source_when_one_is_healthy():
    """One source healthy (siaran.html), one dead (zero rows) — only the dead one is named,
    the healthy one's items are still returned."""
    job = _make_job()
    logger = _install_capturing_logger(job)
    tg_calls = _install_capturing_telegram(job)

    async def fetch_page(url):
        return {"html": _ZERO_ROWS_HTML if "peraturan" in url else SIARAN_HTML}

    job.fetch_page = fetch_page
    job.random_delay = lambda a, b: asyncio.sleep(0)

    async def scenario():
        items, zero_yield = await job._fetch_direct_sources()
        if zero_yield:
            await job._signal_zero_yield(zero_yield)
        return items, zero_yield

    items, zero_yield = asyncio.run(scenario())

    assert zero_yield == ["index-peraturan"]
    assert len(items) == 5  # siaran-pers-page's 5 rows, index-peraturan's 0
    warned_sources = [
        kw["source"] for event, kw in logger.warnings if event == "pajak_direct_source_zero_yield"
    ]
    assert warned_sources == ["index-peraturan"]
    assert len(tg_calls) == 1
    assert "index-peraturan" in tg_calls[0]["msg"]
    assert "siaran-pers-page" not in tg_calls[0]["msg"]


def test_zero_yield_signal_never_pages_p0():
    """The signal must use the job's `digest` tier, never `p0` — `run_job()` (agent_job.py)
    pages tier="p0" on any RunResult.status != "ok", and this row explicitly does not want
    zero-yield turned into a P0 page. Also never `log`: tg_notify.py spools a `log`-tier
    message to disk only (`log-only.jsonl`) and never sends it — that would recreate the
    exact green≠working silence this row exists to cure."""
    job = _make_job()
    _install_capturing_logger(job)
    tg_calls = _install_capturing_telegram(job)

    asyncio.run(job._signal_zero_yield(["index-peraturan"]))

    assert len(tg_calls) == 1
    assert tg_calls[0]["tier"] != "p0"
    assert tg_calls[0]["tier"] != "log"
    assert tg_calls[0]["tier"] == "digest"
