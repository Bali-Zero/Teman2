#!/usr/bin/env python3
"""pse_registry_check.py — is a TD-PSE record LOCATED in the Komdigi registry?

Read-only lookup tool for a manual list of company names or domains. For each
input it searches the public registry behind pse.komdigi.go.id and reports
"located" (with the records found) or "not_located". It never says
"unregistered": absence from a keyword search is not proof of non-registration
(the legal entity may be spelled differently, the search is fuzzy). A located
record is a keyword hit — a human still reads pse_name/domain before using it.

API (verified 2026-09-11 from the site's Next.js bundle, re-probed live):
    POST https://pse.komdigi.go.id/api/v1/tdpse/tdpse-list
    body {"keyword": str, "length": 20, "start": 0}
    -> {"status": "success", "data": {"total_rows": N, "data": [record, ...]}}

Behaviour (spec: pse-scanner.spec.md, compliance-stack build Lane B):
  * keywords per input: the raw input, the registrable part of a domain
    (kita.example.co.id -> example.co.id), and the optional second-column legal
    entity; records deduplicated by nomor_tdpse.
  * at most one request per second; exponential backoff on HTTP 429/5xx and
    network errors; the run HARD-STOPS after 3 consecutive failed requests.
  * successful responses cached on disk for 24 h, keyed by keyword.
  * a malformed or {"status": "error"} response is an ERROR, never a
    "not_located" — a silent API change must not read as "nobody registered".

Exit codes: 0 every input checked · 2 any input errored (or no input at all)
            · 1 --probe returned zero rows for "Tokopedia".

Boundaries: company names and domains only (no personal data), no outreach, no
email generation, not scheduled (manual use only until a human has run the list
for two weeks).

Usage:
    python3 scripts/pse_registry_check.py companies.csv -o result.csv
    printf 'Tokopedia\\nBali Zero\\n' | python3 scripts/pse_registry_check.py -
    python3 scripts/pse_registry_check.py --probe
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

ENDPOINT = "https://pse.komdigi.go.id/api/v1/tdpse/tdpse-list"
REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Origin": "https://pse.komdigi.go.id",
    "Referer": "https://pse.komdigi.go.id/",
}
PAGE_LENGTH = 20
MIN_INTERVAL_S = 1.0
BACKOFF_BASE_S = 1.0
MAX_CONSECUTIVE_FAILURES = 3
CACHE_TTL_S = 24 * 3600
REQUEST_TIMEOUT_S = 30.0
PROBE_KEYWORD = "Tokopedia"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "nuzantara" / "pse_registry_check"

OUTPUT_COLUMNS = (
    "input",
    "keyword_used",
    "result",
    "pse_name",
    "domain",
    "nomor_tdpse",
    "is_domestik",
    "tanggal_terdaftar",
    "status",
    "checked_at",
)
RECORD_FIELDS = ("pse_name", "domain", "nomor_tdpse", "is_domestik", "tanggal_terdaftar", "status")
HEADER_CELLS = {"input", "name", "company", "company_name", "domain"}
SECOND_LEVEL_SUFFIXES = {
    "co.id", "ac.id", "go.id", "or.id", "web.id", "my.id", "biz.id", "sch.id",
    "net.id", "mil.id", "desa.id", "ponpes.id",
    "co.uk", "org.uk", "com.au", "com.sg", "com.my", "co.jp", "com.cn", "com.hk",
    "co.nz", "co.za", "com.br",
}
_HOST_RE = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")

Transport = Callable[[str, bytes, dict, float], "tuple[int, bytes]"]


class QueryError(Exception):
    """One keyword could not be checked."""


class HardStop(QueryError):
    """MAX_CONSECUTIVE_FAILURES failed requests in a row: stop the whole run."""


@dataclass
class Entry:
    raw: str
    legal_entity: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    total_rows: int
    rows: list[dict]
    fetched_at: float
    from_cache: bool = False


def urllib_transport(url: str, body: bytes, headers: dict, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""


def _host_of(text: str) -> str:
    value = text.strip().lower()
    if "://" in value:
        value = urllib.parse.urlsplit(value).hostname or ""
    else:
        value = value.split("/", 1)[0]
    value = value.split(":", 1)[0].rstrip(".")
    return value[4:] if value.startswith("www.") else value


def registrable_domain(text: str) -> Optional[str]:
    if " " in text.strip():
        return None
    host = _host_of(text)
    if not _HOST_RE.fullmatch(host):
        return None
    labels = host.split(".")
    keep = 3 if len(labels) >= 3 and ".".join(labels[-2:]) in SECOND_LEVEL_SUFFIXES else 2
    return ".".join(labels[-keep:])


def build_keywords(raw: str, legal_entity: str = "") -> list[str]:
    candidates = [raw.strip(), registrable_domain(raw) or "", legal_entity.strip()]
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate.lower() not in seen:
            seen.add(candidate.lower())
            keywords.append(candidate)
    return keywords


def parse_input(text: str) -> list[Entry]:
    entries: list[Entry] = []
    for index, row in enumerate(csv.reader(io.StringIO(text))):
        cells = [cell.strip() for cell in row]
        if not cells or not cells[0] or cells[0].startswith("#"):
            continue
        if index == 0 and cells[0].lower() in HEADER_CELLS:
            continue
        legal = cells[1] if len(cells) > 1 else ""
        entries.append(Entry(raw=cells[0], legal_entity=legal, keywords=build_keywords(cells[0], legal)))
    return entries


def parse_response(raw: bytes) -> tuple[int, list[dict]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise QueryError(f"response is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise QueryError("response is not a JSON object")
    if payload.get("status") == "error":
        raise QueryError(f"API error: {payload.get('message') or payload.get('error') or 'unspecified'}")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise QueryError("unexpected response shape: data.data is not a list")
    total = data.get("total_rows")
    if not isinstance(total, int) or isinstance(total, bool):
        raise QueryError("unexpected response shape: data.total_rows is not an integer")
    return total, [row for row in data["data"] if isinstance(row, dict)]


class RegistryClient:
    def __init__(
        self,
        transport: Optional[Transport] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
        cache_dir: Optional[Path] = None,
        min_interval: float = MIN_INTERVAL_S,
    ) -> None:
        self._transport = transport or urllib_transport
        self._clock = clock
        self._sleep = sleep
        self._now = now
        self._cache_dir = cache_dir
        self._min_interval = max(MIN_INTERVAL_S, min_interval)
        self._last_request: Optional[float] = None
        self.consecutive_failures = 0
        self.requests_made = 0

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self._last_request + self._min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _cache_path(self, keyword: str) -> Optional[Path]:
        if self._cache_dir is None:
            return None
        digest = hashlib.sha256(keyword.strip().lower().encode("utf-8")).hexdigest()[:32]
        return self._cache_dir / f"{digest}.json"

    def _cache_get(self, keyword: str) -> Optional[SearchResult]:
        path = self._cache_path(keyword)
        if path is None or not path.is_file():
            return None
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = float(cached["fetched_at"])
            total, rows = int(cached["total_rows"]), list(cached["rows"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not 0 <= self._now() - fetched_at < CACHE_TTL_S:
            return None
        return SearchResult(total, rows, fetched_at, from_cache=True)

    def _cache_put(self, keyword: str, result: SearchResult) -> None:
        path = self._cache_path(keyword)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = {"keyword": keyword, "fetched_at": result.fetched_at, "total_rows": result.total_rows, "rows": result.rows}
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(blob, handle, ensure_ascii=False)
        os.replace(tmp, path)

    def search(self, keyword: str) -> SearchResult:
        cached = self._cache_get(keyword)
        if cached is not None:
            return cached
        body = json.dumps({"keyword": keyword, "length": PAGE_LENGTH, "start": 0}).encode("utf-8")
        attempt = 0
        while True:
            self._throttle()
            self.requests_made += 1
            retryable = True
            try:
                status, raw = self._transport(ENDPOINT, body, dict(REQUEST_HEADERS), REQUEST_TIMEOUT_S)
            except OSError as exc:
                error = f"network error: {exc}"
            else:
                if status == 200:
                    try:
                        total, rows = parse_response(raw)
                    except QueryError as exc:
                        error, retryable = str(exc), False
                    else:
                        self.consecutive_failures = 0
                        result = SearchResult(total, rows, self._now())
                        self._cache_put(keyword, result)
                        return result
                else:
                    error = f"HTTP {status}"
                    retryable = status == 429 or 500 <= status < 600
            self.consecutive_failures += 1
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                raise HardStop(f"{error} ({self.consecutive_failures} consecutive failures, run stopped)")
            if not retryable:
                raise QueryError(error)
            self._sleep(BACKOFF_BASE_S * 2**attempt)
            attempt += 1


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def _row(entry: Entry, keyword: str, result: str, checked_at: str, record: Optional[dict] = None) -> dict:
    row = dict.fromkeys(OUTPUT_COLUMNS, "")
    row.update(input=entry.raw, keyword_used=keyword, result=result, checked_at=checked_at)
    for name in RECORD_FIELDS:
        value = (record or {}).get(name, "")
        row[name] = str(value).lower() if isinstance(value, bool) else ("" if value is None else str(value))
    return row


def check_entries(entries: Iterable[Entry], client: RegistryClient, now: Callable[[], float] = time.time,
                  log: Callable[[str], None] = lambda msg: None) -> tuple[list[dict], int]:
    rows: list[dict] = []
    errored = 0
    stopped: Optional[str] = None
    for entry in entries:
        if stopped:
            rows.append(_row(entry, " | ".join(entry.keywords), "error", _iso(now())))
            log(f"error: {entry.raw!r} not checked, {stopped}")
            errored += 1
            continue
        found: dict[str, tuple[str, dict, float]] = {}
        errors: list[str] = []
        fetched: list[float] = []
        for keyword in entry.keywords:
            try:
                result = client.search(keyword)
            except HardStop as exc:
                errors.append(keyword)
                stopped = str(exc)
                log(f"error: {entry.raw!r} keyword {keyword!r}: {exc}")
                break
            except QueryError as exc:
                errors.append(keyword)
                log(f"error: {entry.raw!r} keyword {keyword!r}: {exc}")
                continue
            fetched.append(result.fetched_at)
            for record in result.rows:
                key = str(record.get("nomor_tdpse") or record.get("se_id") or json.dumps(record, sort_keys=True))
                found.setdefault(key, (keyword, record, result.fetched_at))
        for keyword, record, fetched_at in found.values():
            rows.append(_row(entry, keyword, "located", _iso(fetched_at), record))
        if errors:
            rows.append(_row(entry, " | ".join(errors), "error", _iso(now())))
            errored += 1
        elif not found:
            rows.append(_row(entry, " | ".join(entry.keywords), "not_located", _iso(max(fetched))))
    return rows, errored


def _csv_safe(value: str) -> str:
    formula = value[:1] in ("=", "+", "@") or (value[:1] == "-" and len(value) > 1)
    return "'" + value if formula else value


def write_csv(rows: list[dict], handle) -> None:
    writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_safe(value) for key, value in row.items()})


def main(
    argv: Optional[list[str]] = None,
    *,
    transport: Optional[Transport] = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> int:
    parser = argparse.ArgumentParser(description="Check company names/domains against the Komdigi TD-PSE registry.")
    parser.add_argument("input", nargs="?", help="CSV or newline list (name or domain[, legal entity]); '-' = stdin")
    parser.add_argument("-o", "--output", help="output CSV path (default: stdout)")
    parser.add_argument("--probe", action="store_true", help=f"live self-test: {PROBE_KEYWORD!r} must return rows")
    parser.add_argument("--no-cache", action="store_true", help="bypass the 24 h on-disk cache")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args(argv)

    def log(message: str) -> None:
        print(message, file=sys.stderr)

    if args.probe:
        entries = parse_input(PROBE_KEYWORD)
    elif not args.input:
        parser.error("an input file (or '-') is required unless --probe is given")
    else:
        try:
            text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        except OSError as exc:
            log(f"error: cannot read {args.input}: {exc}")
            return 2
        entries = parse_input(text)
    if not entries:
        log("error: no inputs found — an empty run is not a clean run")
        return 2

    cache_dir = None if (args.no_cache or args.probe) else args.cache_dir
    client = RegistryClient(transport=transport, clock=clock, sleep=sleep, now=now, cache_dir=cache_dir)
    rows, errored = check_entries(entries, client, now=now, log=log)

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as handle:
            write_csv(rows, handle)
    else:
        write_csv(rows, sys.stdout)

    located = sum(1 for e in entries if any(r["input"] == e.raw and r["result"] == "located" for r in rows))
    log(f"checked {len(entries)} input(s): {located} located, {errored} errored, {client.requests_made} request(s)")
    if errored:
        return 2
    if args.probe and not any(r["result"] == "located" for r in rows):
        log(f"PROBE FAILED: {PROBE_KEYWORD!r} returned 0 rows — treat as an API change, not as 'nobody registered'")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
