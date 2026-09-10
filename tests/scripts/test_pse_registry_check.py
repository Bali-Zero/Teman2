from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pse_registry_check", ROOT / "scripts" / "pse_registry_check.py")
assert SPEC is not None and SPEC.loader is not None
pse = importlib.util.module_from_spec(SPEC)
sys.modules["pse_registry_check"] = pse
SPEC.loader.exec_module(pse)

TOKOPEDIA_ROWS = [
    {
        "domain": "tokopedia.com",
        "is_domestik": True,
        "nama_se": "TOKOPEDIA",
        "nomor_tdpse": "000847.04/DJAI.PSE/09/2024",
        "pse_name": "TOKOPEDIA",
        "se_id": "a",
        "status": "Terdaftar",
        "tanggal_terdaftar": "2024-09-05",
    },
    {
        "domain": "gojek.com",
        "is_domestik": True,
        "nama_se": "GOJEK",
        "nomor_tdpse": "001758.01/DJAI.PSE/12/2021",
        "pse_name": "GOTO GOJEK TOKOPEDIA",
        "se_id": "b",
        "status": "Terdaftar",
        "tanggal_terdaftar": "2021-12-13",
    },
]


def ok_body(rows: list[dict], total: int | None = None) -> bytes:
    payload = {"data": {"data": rows, "total_rows": len(rows) if total is None else total}, "status": "success"}
    return json.dumps(payload).encode()


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds

    def wall(self) -> float:
        return 1_800_000_000.0 + self.t


class FakeTransport:
    def __init__(self, clock: FakeClock, responder, latency: float = 0.05) -> None:
        self.clock = clock
        self.responder = responder
        self.latency = latency
        self.calls: list[tuple[float, dict]] = []

    def __call__(self, url: str, body: bytes, headers: dict, timeout: float):
        payload = json.loads(body)
        self.calls.append((self.clock.t, payload))
        self.clock.t += self.latency
        return self.responder(payload)


def by_keyword(payload: dict):
    if "tokopedia" in payload["keyword"].lower():
        return 200, ok_body(TOKOPEDIA_ROWS)
    return 200, ok_body([])


def run(tmp_path: Path, text: str, responder, extra: list[str] | None = None):
    clock = FakeClock()
    transport = FakeTransport(clock, responder)
    src = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    src.write_text(text, encoding="utf-8")
    argv = [str(src), "-o", str(out), "--cache-dir", str(tmp_path / "cache")] + (extra or [])
    code = pse.main(argv, transport=transport, clock=clock.monotonic, sleep=clock.sleep, now=clock.wall)
    rows = list(csv.DictReader(out.open(encoding="utf-8"))) if out.exists() else []
    return code, rows, transport, clock


def test_keywords_raw_registrable_domain_and_legal_entity_deduplicated() -> None:
    assert pse.build_keywords("kita.balizero.com") == ["kita.balizero.com", "balizero.com"]
    assert pse.build_keywords("https://www.shop.example.co.id/path") == [
        "https://www.shop.example.co.id/path",
        "example.co.id",
    ]
    assert pse.build_keywords("tokopedia.com") == ["tokopedia.com"]
    assert pse.build_keywords("Bali Zero", "PT Bali Zero") == ["Bali Zero", "PT Bali Zero"]
    assert pse.build_keywords("Tokopedia", "tokopedia") == ["Tokopedia"]


def test_parse_input_accepts_csv_and_newline_list() -> None:
    entries = pse.parse_input("input,legal\nTokopedia\n\n# note\nkita.balizero.com,PT Bali Zero\n")
    assert [(e.raw, e.legal_entity) for e in entries] == [("Tokopedia", ""), ("kita.balizero.com", "PT Bali Zero")]
    assert entries[1].keywords == ["kita.balizero.com", "balizero.com", "PT Bali Zero"]


def test_tokopedia_located_and_bali_zero_not_located(tmp_path: Path) -> None:
    code, rows, _, _ = run(tmp_path, "Tokopedia\nBali Zero\n", by_keyword)
    assert code == 0
    assert tuple(rows[0].keys()) == pse.OUTPUT_COLUMNS
    toko = [r for r in rows if r["input"] == "Tokopedia"]
    bali = [r for r in rows if r["input"] == "Bali Zero"]
    assert {r["result"] for r in toko} == {"located"}
    assert {r["nomor_tdpse"] for r in toko} == {row["nomor_tdpse"] for row in TOKOPEDIA_ROWS}
    assert toko[0]["is_domestik"] == "true"
    assert [r["result"] for r in bali] == ["not_located"]
    assert "unregistered" not in (tmp_path / "out.csv").read_text()


def test_records_deduplicated_by_nomor_tdpse_across_keywords(tmp_path: Path) -> None:
    code, rows, transport, _ = run(tmp_path, "www.tokopedia.co.id,Tokopedia\n", lambda p: (200, ok_body(TOKOPEDIA_ROWS)))
    assert code == 0
    assert len(transport.calls) == 3
    assert len(rows) == 2
    assert all(r["keyword_used"] == "www.tokopedia.co.id" for r in rows)


def test_forced_http_error_exits_2_with_backoff_and_hard_stop(tmp_path: Path) -> None:
    code, rows, transport, clock = run(tmp_path, "Tokopedia\nBali Zero\n", lambda p: (500, b"oops"))
    assert code == 2
    assert len(transport.calls) == pse.MAX_CONSECUTIVE_FAILURES
    assert clock.sleeps[:2] == [1.0, 2.0]
    assert [r["result"] for r in rows] == ["error", "error"]
    assert "not_located" not in {r["result"] for r in rows}


def test_http_error_through_urllib_transport_exits_2(tmp_path: Path) -> None:
    error = urllib.error.HTTPError(pse.ENDPOINT, 503, "Service Unavailable", {}, io.BytesIO(b"down"))
    clock = FakeClock()
    src = tmp_path / "in.txt"
    src.write_text("Tokopedia\n", encoding="utf-8")
    with patch("pse_registry_check.urllib.request.urlopen", side_effect=error) as urlopen:
        code = pse.main([str(src), "-o", str(tmp_path / "o.csv"), "--no-cache"],
                        clock=clock.monotonic, sleep=clock.sleep, now=clock.wall)
    assert code == 2
    assert urlopen.call_count == pse.MAX_CONSECUTIVE_FAILURES
    request = urlopen.call_args[0][0]
    assert request.full_url == pse.ENDPOINT and request.get_method() == "POST"
    assert json.loads(request.data) == {"keyword": "Tokopedia", "length": 20, "start": 0}


def test_no_request_faster_than_one_per_second(tmp_path: Path) -> None:
    names = "\n".join(["Tokopedia", "Bali Zero", "kita.balizero.com", "Gojek", "Traveloka"]) + "\n"
    code, _, transport, clock = run(tmp_path, names, by_keyword)
    assert code == 0
    stamps = [t for t, _ in transport.calls]
    assert len(stamps) == 6
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert min(gaps) >= pse.MIN_INTERVAL_S - 1e-9
    assert clock.sleeps, "the limiter must actually wait, not rely on latency"


def test_429_backs_off_then_succeeds(tmp_path: Path) -> None:
    replies = iter([(429, b""), (200, ok_body(TOKOPEDIA_ROWS))])
    code, rows, transport, clock = run(tmp_path, "Tokopedia\n", lambda p: next(replies))
    assert code == 0
    assert len(transport.calls) == 2
    assert clock.sleeps[0] == pse.BACKOFF_BASE_S
    assert {r["result"] for r in rows} == {"located"}


@pytest.mark.parametrize(
    "body",
    [
        json.dumps({"status": "error", "message": "bad keyword"}).encode(),
        json.dumps({"status": "success", "data": {"data": []}}).encode(),
        b"<html>maintenance</html>",
    ],
)
def test_api_error_or_changed_shape_is_error_never_not_located(tmp_path: Path, body: bytes) -> None:
    code, rows, transport, _ = run(tmp_path, "Bali Zero\n", lambda p: (200, body))
    assert code == 2
    assert len(transport.calls) == 1
    assert [r["result"] for r in rows] == ["error"]


def test_cache_hit_within_24h_and_refetch_after_expiry(tmp_path: Path) -> None:
    clock = FakeClock()
    transport = FakeTransport(clock, by_keyword)
    kwargs = dict(transport=transport, clock=clock.monotonic, sleep=clock.sleep, now=clock.wall, cache_dir=tmp_path)
    pse.RegistryClient(**kwargs).search("Tokopedia")
    again = pse.RegistryClient(**kwargs).search("tokopedia ")
    assert again.from_cache and again.total_rows == 2 and len(transport.calls) == 1
    clock.t += pse.CACHE_TTL_S + 1
    fresh = pse.RegistryClient(**kwargs).search("Tokopedia")
    assert not fresh.from_cache and len(transport.calls) == 2


def test_probe_exit_codes(tmp_path: Path) -> None:
    def probe(responder):
        clock = FakeClock()
        transport = FakeTransport(clock, responder)
        code = pse.main(["--probe", "-o", str(tmp_path / "p.csv")], transport=transport,
                        clock=clock.monotonic, sleep=clock.sleep, now=clock.wall)
        return code, transport

    code, transport = probe(by_keyword)
    assert code == 0 and transport.calls[0][1]["keyword"] == "Tokopedia"
    assert probe(lambda p: (200, ok_body([])))[0] == 1
    assert probe(lambda p: (502, b""))[0] == 2


def test_empty_input_is_not_a_clean_run(tmp_path: Path) -> None:
    code, rows, transport, _ = run(tmp_path, "# nothing\n\n", by_keyword)
    assert code == 2 and rows == [] and transport.calls == []


def test_formula_like_cells_are_neutralised(tmp_path: Path) -> None:
    evil = [dict(TOKOPEDIA_ROWS[0], pse_name="=HYPERLINK(\"x\")", domain="-")]
    _, rows, _, _ = run(tmp_path, "Tokopedia\n", lambda p: (200, ok_body(evil)))
    assert rows[0]["pse_name"].startswith("'=")
    assert rows[0]["domain"] == "-"


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("PSE_REGISTRY_LIVE"), reason="network test: set PSE_REGISTRY_LIVE=1")
def test_live_probe_tokopedia_returns_rows() -> None:
    result = pse.RegistryClient().search(pse.PROBE_KEYWORD)
    assert result.total_rows > 0 and result.rows
