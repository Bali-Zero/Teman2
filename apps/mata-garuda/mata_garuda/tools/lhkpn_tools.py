"""
Mata Garuda — LHKPN scraping tools.

Targets antv.kpk.go.id/elhkpn/ — Indonesian state officials' wealth
declarations. Tools are pure functions where possible; HTTP calls are
isolated for testability.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5
GENOME constraints: max 10 req/min, User-Agent rotation, fallback on 403.

No httpx — uses subprocess + curl (Mata Garuda only allows pydantic + pytest).
"""
from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Any
from urllib.parse import quote_plus

logger = logging.getLogger("mata_garuda.tools.lhkpn")


LHKPN_BASE_URL = "https://antv.kpk.go.id/elhkpn"
LHKPN_RATE_LIMIT_S = 6  # 10 req/min = 6s between requests

LHKPN_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


# ── Pure parsers (no I/O, easy to test) ────────────────────────────────


def parse_lhkpn_search_html(html: str) -> list[dict[str, Any]]:
    """Extract search results from antv.kpk.go.id search page.

    Returns list of dicts with: nama, nip, jabatan, report_year.
    """
    table_match = re.search(
        r'<table[^>]*id="resultsTable"[^>]*>(.*?)</table>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not table_match:
        return []

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.DOTALL | re.IGNORECASE,
    )
    results: list[dict[str, Any]] = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) >= 4:
            results.append({
                "nama": _strip_html(cells[0]),
                "nip": _strip_html(cells[1]),
                "jabatan": _strip_html(cells[2]),
                "report_year": _strip_html(cells[3]),
            })
    return results


def parse_lhkpn_profile_html(html: str) -> dict[str, Any]:
    """Extract profile fields from antv.kpk.go.id detail page."""

    def get_span(span_id: str) -> str:
        m = re.search(
            rf'<span[^>]*id="{span_id}"[^>]*>(.*?)</span>',
            html, re.DOTALL | re.IGNORECASE,
        )
        return _strip_html(m.group(1)) if m else ""

    def count_table_rows(table_id: str) -> int:
        m = re.search(
            rf'<table[^>]*id="{table_id}"[^>]*>(.*?)</table>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if not m:
            return 0
        return len(re.findall(r"<tr[^>]*>", m.group(1), re.IGNORECASE))

    return {
        "nama": get_span("nama"),
        "nip": get_span("nip"),
        "jabatan": get_span("jabatan"),
        "angkatan": get_span("angkatan"),
        "total_harta_idr": _parse_idr(get_span("totalHarta")),
        "properties_count": count_table_rows("properties"),
        "vehicles_count": count_table_rows("vehicles"),
        "accounts_count": count_table_rows("accounts"),
    }


def _strip_html(s: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def _parse_idr(s: str) -> int:
    """Parse 'Rp 12.500.000.000' or 'Rp 5,000,000' → 12500000000.

    Indonesian Rupiah uses dots as thousand separators. We strip ALL non-digit
    characters since the unit is always IDR.
    """
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0


# ── HTTP wrappers (effectful — invoked by the agent) ───────────────────


def _http_get_with_rotation(
    url: str,
    timeout: int = 15,
    user_agent_index: int = 0,
) -> tuple[int, str]:
    """GET via curl with User-Agent rotation. Returns (status_code, body).

    Returns (0, "") on transport failure.
    """
    ua = LHKPN_USER_AGENTS[user_agent_index % len(LHKPN_USER_AGENTS)]
    cmd = [
        "curl", "-sS", "-L",  # follow redirects
        "--max-time", str(timeout),
        "-w", "\\n%{http_code}",
        "-H", f"User-Agent: {ua}",
        "-H", "Accept-Language: id-ID,id;q=0.9,en;q=0.7",
        "-H", "Accept: text/html,application/xhtml+xml",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        logger.warning("LHKPN curl timeout %s", url)
        return 0, ""
    except Exception as e:
        logger.warning("LHKPN curl exception %s: %s", url, e)
        return 0, ""

    if result.returncode != 0:
        logger.warning("LHKPN curl exit %d: %s", result.returncode, result.stderr.strip())
        return 0, ""

    output = result.stdout
    nl = output.rfind("\n")
    if nl == -1:
        return 0, ""

    body = output[:nl]
    try:
        status = int(output[nl + 1:].strip())
    except ValueError:
        return 0, ""

    return status, body


def scrape_lhkpn_search(query: str) -> list[dict[str, Any]]:
    """Search LHKPN by name. Honors rate limit + UA rotation on 403."""
    url = (
        f"{LHKPN_BASE_URL}/index.php/searchpenyelenggara/searchpencarian"
        f"?q={quote_plus(query)}"
    )

    for attempt in range(len(LHKPN_USER_AGENTS)):
        time.sleep(LHKPN_RATE_LIMIT_S)
        status, body = _http_get_with_rotation(url, user_agent_index=attempt)
        if status == 200:
            return parse_lhkpn_search_html(body)
        if status == 403:
            logger.warning("LHKPN search 403 attempt %d — rotating UA", attempt + 1)
            continue
        logger.error("LHKPN search non-200/403: status=%d", status)
        return []

    logger.error("LHKPN search exhausted UA rotation for query=%s", query)
    return []


def scrape_lhkpn_profile(nip: str) -> dict[str, Any]:
    """Fetch detail page for a NIP. Honors rate limit + UA rotation on 403."""
    url = (
        f"{LHKPN_BASE_URL}/index.php/searchpenyelenggara/profilelhkpn/{nip}"
    )

    for attempt in range(len(LHKPN_USER_AGENTS)):
        time.sleep(LHKPN_RATE_LIMIT_S)
        status, body = _http_get_with_rotation(url, user_agent_index=attempt)
        if status == 200:
            return parse_lhkpn_profile_html(body)
        if status == 403:
            logger.warning("LHKPN profile 403 attempt %d — rotating UA", attempt + 1)
            continue
        logger.error("LHKPN profile non-200/403: status=%d", status)
        return {}

    logger.error("LHKPN profile exhausted UA rotation for nip=%s", nip)
    return {}
