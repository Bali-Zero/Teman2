"""vault_common — shared utilities for the GARUDA-FILIERA Batch-0 vault compilers.

Pure-stdlib on purpose (Mini runs these; avoid exotic deps per the batch-0
mandate). Everything network-facing goes through `http_get`, which bypasses
the system proxy explicitly (memory trap: urllib honors it silently —
scripts/fetch_oss_risk.py hit this first) and never retries a 404 (a 404 is
a signal, not a transient failure — P3 corroborated-absence discipline,
research/operations/2026-07-16-kbli-filiera-methodology.md).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

DEFAULT_VAULT_ROOT = Path("~/nuzantara-vault").expanduser()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger(name: str) -> logging.Logger:
    """logger, never print() (CLAUDE.md golden rule #8) — idempotent, safe
    to call more than once for the same name (won't double-attach handlers)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """UTC, second precision, explicit Z suffix — matches the fetched_at
    shape used across every fetch-log/absence record in this package."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# JSONL append/read log
# ---------------------------------------------------------------------------

def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def read_jsonl(path: Path) -> list[dict]:
    """Never raises on a missing file or a corrupt line (a torn last line
    from a killed process is recoverable — the log is append-only evidence,
    not a transaction log; a bad line is just skipped, not fatal)."""
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Idempotent resume (shared decision logic — pp28 and oss fetchers both use
# this so "existing-file-with-matching-sha skipped, mismatched-sha
# refetched" is ONE tested code path, not two copies that can drift apart)
# ---------------------------------------------------------------------------

def decide_resume(prior: dict | None, file_path: Path) -> str:
    """Returns "skip" (file verified on disk, matches the prior record's
    recorded bytes+sha256) or "refetch" (no prior, prior wasn't a clean
    200, file missing, size drifted, or sha256 drifted — re-verified on
    every call, never trusted blindly per the batch-0 spec)."""
    if prior is None:
        return "refetch"
    if prior.get("http_status") != 200:
        return "refetch"
    if not file_path.exists():
        return "refetch"
    try:
        if file_path.stat().st_size != prior.get("bytes"):
            return "refetch"
    except OSError:
        return "refetch"
    if sha256_file(file_path) != prior.get("sha256"):
        return "refetch"
    return "skip"


# ---------------------------------------------------------------------------
# HTTP (stdlib urllib — proxy-bypassed, 404-is-terminal, polite retry)
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    error: str | None = None


def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 25.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> FetchResult:
    """GET with an explicit proxy bypass (ProxyHandler({})) and a 404 that
    returns IMMEDIATELY without entering the retry loop — a 404 is a
    LEGIT no-scope/absence signal, never a transient failure to hammer
    (P3; "never retry-storm it"). Any other non-2xx or network exception
    retries up to `retries` times with linear backoff, then returns a
    FetchResult with `error` set (never raises — callers decide fail-visible
    handling, e.g. exit-1-after-full-sweep)."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_status = 0
    last_error = "exhausted"
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with opener.open(req, timeout=timeout) as resp:
                return FetchResult(status=resp.status, headers=dict(resp.headers), body=resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp else b""
            if exc.code == 404:
                return FetchResult(status=404, headers=dict(exc.headers or {}), body=body)
            last_status = exc.code
            last_error = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 — network layer, deliberately broad
            last_error = str(exc)
        if attempt < retries - 1:
            time.sleep(backoff * (attempt + 1))
    return FetchResult(status=last_status, headers={}, body=b"", error=last_error)


# ---------------------------------------------------------------------------
# Content-Disposition filename parsing
# ---------------------------------------------------------------------------

_CD_STAR_RE = re.compile(r"filename\*\s*=\s*[^']*''([^;]+)", re.IGNORECASE)
_CD_QUOTED_RE = re.compile(r'filename\s*=\s*"([^"]+)"', re.IGNORECASE)
_CD_BARE_RE = re.compile(r"filename\s*=\s*([^;]+)", re.IGNORECASE)


def parse_content_disposition_filename(header_value: str | None) -> str | None:
    """RFC 6266/5987-tolerant filename extraction: filename*=UTF-8''...
    (percent-encoded) takes priority over plain quoted/bare filename=...
    Returns None if the header is absent or carries no filename param."""
    if not header_value:
        return None
    m = _CD_STAR_RE.search(header_value)
    if m:
        return unquote(m.group(1)).strip()
    m = _CD_QUOTED_RE.search(header_value)
    if m:
        return m.group(1).strip()
    m = _CD_BARE_RE.search(header_value)
    if m:
        return m.group(1).strip().strip('"')
    return None


# ---------------------------------------------------------------------------
# PP28 lampiran filename structure (a lampiran LETTER can span multiple
# sequential BPK download ids — this parser is what lets the fetch-log
# double as the id->lampiran map, no separate file needed: grounded fact
# 2026-07-16, e.g. id 394941 = "2.6g Lampiran I.F ... (I.F.4501-5248).pdf")
# ---------------------------------------------------------------------------

_LAMPIRAN_HEAD_RE = re.compile(
    r"^(?P<fragment>\d+\.\d+[a-zA-Z]?)\s+Lampiran\s+(?P<letter>[IVXLCDM]+(?:\.[A-Z])?)\b"
)
_LAMPIRAN_RANGE_RE = re.compile(
    r"\((?:[IVXLCDM]+(?:\.[A-Z])?\.)?(?P<range>\d+-\d+)[^)]*\)"
)


def parse_pp28_lampiran_filename(filename: str) -> dict:
    """Best-effort structural parse of a PP28 lampiran Content-Disposition
    filename into {fragment, letter, range}. Any field is None when not
    present — never raises, an unparseable filename still gets recorded
    verbatim in the fetch-log (`filename` field), just without the
    structural breakdown."""
    head = _LAMPIRAN_HEAD_RE.match(filename)
    range_m = _LAMPIRAN_RANGE_RE.search(filename)
    return {
        "fragment": head.group("fragment") if head else None,
        "letter": head.group("letter") if head else None,
        "range": range_m.group("range") if range_m else None,
    }


# ---------------------------------------------------------------------------
# Filename sanitizing (vault blob names must be safe on POSIX + S3 keys)
# ---------------------------------------------------------------------------

_UNSAFE_RE = re.compile(r"[\x00-\x1f/\\]")


def sanitize_filename(name: str, *, max_len: int = 180) -> str:
    """Replaces control chars and path separators, collapses whitespace,
    and caps length (preserving the extension where recognizable) — keeps
    the human-readable source filename (parentheses/dots survive) while
    making it a safe single path component on any filesystem the vault
    might live on."""
    name = _UNSAFE_RE.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > max_len:
        stem, dot, ext = name.rpartition(".")
        if dot and stem and len(ext) <= 8:
            keep = max_len - len(ext) - 1
            name = f"{stem[:keep]}.{ext}"
        else:
            name = name[:max_len]
    return name
