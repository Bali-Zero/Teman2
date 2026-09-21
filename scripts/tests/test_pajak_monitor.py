"""
Behavioral tests for pajak_monitor.py's enrichment time budget (R1) and monitor wiring
(M6, M7) — gate REWORK-BUILD on PR #7084 (2026-09-21).

`pajak_monitor.py` imports `agent_job`/`browser_job`, which live only on Pro and are not in
this repo. Like the gate's own re-run, both are STUBBED in `sys.modules` before
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

            async def send_telegram(self, msg):
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
