"""
Mata Garuda — LHKPN scraping tools.

Targets the KPK e-Announcement portal for Indonesian state officials'
wealth declarations. As of 2026-04-26 KPK decommissioned
``antv.kpk.go.id`` (NXDOMAIN) and migrated to ``elhkpn.kpk.go.id`` with
reCAPTCHA v3 gating + a SPA UI. Programmatic access via ``curl`` is no
longer possible.

To stay within the Mata Garuda stack ceiling (only ``pydantic`` and
``pytest`` are allowed runtime deps — see ``apps/mata-garuda/CLAUDE.md``
§1 "Stack minimale"), this module no longer talks to the portal
directly. Instead it shells out to the OSINT-Nexus scraper which already
implements the new flow (browser-core + reCAPTCHA token injection + PDF
auto-download). This preserves Symbiosis Law 2 ("OSINT data stays on
Pro, no cloud egress") because OSINT-Nexus is a separate Pro-local
package and the subprocess is a localhost-only ``python -m`` invocation.

Reference: ``research/2026-05-16-lhkpn-flow-triage.md`` (FIX-1).
GENOME constraints (max 10 req/min, UA rotation, fallback on 403) are
now enforced inside the OSINT-Nexus scraper.

The module deliberately keeps the legacy pure parsers
(``parse_lhkpn_search_html``, ``parse_lhkpn_profile_html``,
``LHKPN_USER_AGENTS``) intact so the existing unit-test suite
(``tests/test_lhkpn_tools.py``) continues to pass. They are dead code
for the new flow but cheap insurance if the portal ever exposes
HTML-renderable views again.
"""
from __future__ import annotations

import json as _json
import logging
import os
import re
import subprocess
from typing import Any

logger = logging.getLogger("mata_garuda.tools.lhkpn")


# ── New portal config ──────────────────────────────────────────────────

LHKPN_BASE_URL = "https://elhkpn.kpk.go.id"  # post-2026-04-26 migration
LHKPN_RATE_LIMIT_S = 6  # 10 req/min — kept for parity, enforced by OSINT-Nexus

# OSINT-Nexus subprocess wiring. The defaults assume a standard Pro
# layout; both can be overridden via environment to keep the path out of
# source for prod packaging or to point at a worktree during dev.
OSINT_NEXUS_PYTHON = os.environ.get(
    "OSINT_NEXUS_PYTHON",
    "/Users/nuzantara/Desktop/OSINT-Nexus/.venv/bin/python",
)
OSINT_NEXUS_MODULE = os.environ.get(
    "OSINT_NEXUS_MODULE", "osint_nexus.cli.lhkpn_scrape"
)
# Hard cap. The scraper boots a Chromium context (~3s) and the portal
# adds ~10s for reCAPTCHA + ~30s for the PDF auto-download timer; allow
# headroom for slow runs but cap to prevent gap_consumer from hanging.
OSINT_NEXUS_TIMEOUT_S = int(os.environ.get("OSINT_NEXUS_TIMEOUT_S", "180"))

LHKPN_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


# ── Pure parsers (no I/O, easy to test) ────────────────────────────────
# Kept verbatim from the curl-based implementation so the existing
# pytest suite remains green and we retain a fallback path if KPK ever
# re-exposes server-rendered HTML.


def parse_lhkpn_search_html(html: str) -> list[dict[str, Any]]:
    """Extract search results from a legacy server-rendered search page.

    Returns list of dicts with: nama, nip, jabatan, report_year.
    Used by the test suite; not invoked by the live shellout path.
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
    """Extract profile fields from a legacy server-rendered detail page."""

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


# ── Shellout to OSINT-Nexus (effectful — invoked by the agent) ─────────


def _invoke_osint_nexus(
    *,
    mode: str,
    query: str | None = None,
    nip: str | None = None,
    download_pdf: bool = True,
) -> dict[str, Any]:
    """Run the OSINT-Nexus LHKPN scraper as a subprocess.

    Returns a dict with the same shape as the CLI emits. On any error
    (timeout, missing CLI, non-zero exit) returns a dict with
    ``ok=False`` and a non-empty ``error`` string — never raises.

    Exit-code mapping (see ``osint_nexus/cli/lhkpn_scrape.py``):
        0 ok          → returned as-is
        1 transient   → ok=False, error="recaptcha_failed_retry_later"
        2 not_found   → ok=False, error="no_results"
        3 fatal       → ok=False, error="subprocess_fatal:..."
    """
    cmd: list[str] = [OSINT_NEXUS_PYTHON, "-m", OSINT_NEXUS_MODULE, "--mode", mode]
    if nip is not None:
        cmd.extend(["--nip", nip])
    elif query is not None:
        cmd.extend(["--query", query])
    else:
        return {
            "ok": False,
            "error": "neither query nor nip provided",
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }
    if not download_pdf:
        cmd.append("--no-download-pdf")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OSINT_NEXUS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "OSINT-Nexus LHKPN scraper timed out after %ds (mode=%s, query=%r, nip=%r)",
            OSINT_NEXUS_TIMEOUT_S, mode, query, nip,
        )
        return {
            "ok": False,
            "error": f"scraper_timeout_{OSINT_NEXUS_TIMEOUT_S}s",
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }
    except FileNotFoundError:
        logger.error(
            "OSINT-Nexus CLI not found at %s (set OSINT_NEXUS_PYTHON env var)",
            OSINT_NEXUS_PYTHON,
        )
        return {
            "ok": False,
            "error": f"osint_nexus_cli_not_found:{OSINT_NEXUS_PYTHON}",
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("OSINT-Nexus shellout raised unexpectedly")
        return {
            "ok": False,
            "error": f"shellout_exception:{type(exc).__name__}:{exc}",
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }

    # The CLI always emits valid JSON on stdout, even on non-zero exit.
    # Parse defensively: if stdout is corrupt we still want to surface
    # the exit code rather than crash the caller.
    stdout = (result.stdout or "").strip()
    if not stdout:
        return {
            "ok": False,
            "error": (
                f"empty_stdout exit={result.returncode} "
                f"stderr={result.stderr.strip()[:200]}"
            ),
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }
    try:
        payload: dict[str, Any] = _json.loads(stdout)
    except _json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": (
                f"invalid_json_from_cli:{exc} exit={result.returncode} "
                f"stdout_head={stdout[:200]}"
            ),
            "records": [],
            "profile": None,
            "pdf_paths": [],
        }

    # Trust the CLI's `ok` flag for the success path. If the CLI exited
    # non-zero AND the payload is missing `ok`, synthesise a failure so
    # callers don't see a half-populated dict.
    if "ok" not in payload:
        payload["ok"] = result.returncode == 0
        payload.setdefault("error", f"missing_ok_flag exit={result.returncode}")

    return payload


def scrape_lhkpn_search(query: str) -> list[dict[str, Any]]:
    """Search LHKPN by free-text name.

    Returns list[dict] with keys ``nama, nip, jabatan, report_year`` to
    preserve the legacy contract consumed by ``lhkpn_harvester``. The
    new portal does NOT expose NIP in the search-row payload (see the
    cell layout in ``osint_nexus/scrapers/lhkpn.py``). For backward
    compatibility we set ``nip=""`` and surface the additional 2026
    fields under ``_raw`` for callers that want them.

    Returns ``[]`` on any failure path (no_results, transient, fatal).
    """
    payload = _invoke_osint_nexus(mode="search", query=query)
    if not payload.get("ok"):
        # Logged at the appropriate level inside _invoke_osint_nexus.
        return []

    records = payload.get("records") or []
    out: list[dict[str, Any]] = []
    for r in records:
        out.append({
            "nama": r.get("nama", ""),
            # Portal no longer returns NIP in the row — caller may need
            # to derive it from another source (CSV, KG, prior reflection).
            "nip": "",
            "jabatan": r.get("jabatan", ""),
            "report_year": str(r.get("tahun_data", "")),
            "_raw": r,
        })
    return out


def scrape_lhkpn_profile(nip: str) -> dict[str, Any]:
    """Fetch the LHKPN profile keyed by NIP.

    Returns a dict with the legacy-shape keys
    ``nama, nip, jabatan, angkatan, total_harta_idr, properties_count,
    vehicles_count, accounts_count`` consumed by ``lhkpn_harvester``.
    The new portal does not expose ``angkatan`` or per-asset row counts
    in the search index (counts require parsing the downloaded PDF
    via ``osint_nexus.parsers.lhkpn_parser`` — out of scope here), so
    those fields are returned as the empty string / ``0`` rather than
    fabricated.

    Returns ``{}`` on any failure path so that the caller's
    ``if not profile`` check still works.

    Caveat (post-2026-04-26 portal migration)
    -----------------------------------------
    The new SPA only accepts free-text NAMES in its search field; NIK
    queries return zero rows because the portal does not index NIPs in
    the visible search index. Calling this function with a NIP that has
    no corresponding name lookup will return ``{}`` (empty profile).
    The healthy path is now ``scrape_lhkpn_search(name)`` followed by
    selecting a hit; the lhkpn_harvester agent already prefers
    ``harvest_lhkpn_by_name`` when a name is available. See
    ``research/2026-05-16-lhkpn-flow-triage.md`` AIL-1/AIL-2 for the
    longer-term remedy (CSV→name resolver upstream of this call).
    """
    # We forward the NIP as both the search query AND the canonical NIP
    # echoed back in `profile.nip`. The CLI's `profile` mode then
    # normalises the first hit to the legacy profile shape; if the
    # portal returns no rows the CLI exits 2 → we surface {}.
    payload = _invoke_osint_nexus(mode="profile", nip=nip)
    if not payload.get("ok"):
        return {}

    profile = payload.get("profile") or {}
    if not profile:
        return {}
    # Defensive copy — strip the OSINT-Nexus-specific `_raw` blob so
    # callers and tests that snapshot the legacy keys don't accidentally
    # depend on it.
    legacy = {k: profile.get(k) for k in (
        "nama", "nip", "jabatan", "angkatan",
        "total_harta_idr", "properties_count",
        "vehicles_count", "accounts_count",
    )}
    if "_raw" in profile:
        legacy["_raw"] = profile["_raw"]
    return legacy
