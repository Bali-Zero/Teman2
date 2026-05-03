"""SEO Cell configuration — paths, thresholds, pre_natal unlock rules."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "seo_cell"

# NOTE: DATA_DIR is NOT created at import time. Importing this module must be
# a pure, side-effect-free operation so that pytest collection, tooling, and
# test fixtures (tmp_path-style) can reason about the filesystem without the
# real cell polluting the workspace. Call ensure_data_dir() at the writer
# site instead (cell_birth_date() and create_seo_cell() do this today).

DNA_PATH = Path(__file__).resolve().parent / "dna.json"
DB_PATH = DATA_DIR / "seo_cell.db"

# Same SA has GSC owner role for balizero.com
GOOGLE_CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"

# Brief path — Task 1 output (owner Antonello), consumed here as lightweight
# signal once present. Missing file = no-op, never blocks.
SEO_BRIEF_PATH = PROJECT_ROOT / "data" / "seo_kw_targets" / "2026-04-21-prenatal.json"

# ── Site + funnels ─────────────────────────────────────────────────────────
SITE_URL = "https://balizero.com"
FUNNELS = ("visa", "kbli", "tax", "property")

# ── Pre-natal unlock thresholds (decision memo, AND gate) ──────────────────
PRE_NATAL_MIN_GSC_QUERIES = 80       # distinct query strings seen in 28d
PRE_NATAL_MIN_WEBSITE_ORGANIC_LEADS = 3  # from CRM referrer_url attribution
PRE_NATAL_MIN_AGE_DAYS = 28

# ── Cell timing ────────────────────────────────────────────────────────────
PULSE_INTERVAL_SECONDS = 86400  # daily
SLEEP_HOURS = (2, 6)             # 02:00-06:00 WITA

# Birth date — first pulse. Persist to avoid re-birth confusion.
# If the file doesn't exist yet, we stamp it on first successful factory call.
_BIRTH_DATE_MARKER = DATA_DIR / "birth_date.txt"


def ensure_data_dir() -> Path:
    """Create ``DATA_DIR`` on demand and return it.

    Importing this module must stay side-effect-free (see note next to
    the DATA_DIR declaration). Writers that actually need the directory
    on disk — currently :func:`cell_birth_date` (writes the birth-date
    marker) and :func:`apps.evaluator.seo_cell.cell.create_seo_cell`
    (opens the SQLite memory stack) — must call this first.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def cell_birth_date() -> datetime:
    """Returns the cell's immutable birth date.

    Stamped on first call, then read from disk thereafter. This is the
    reference point for `age_days` in the pre_natal unlock check.
    """
    if _BIRTH_DATE_MARKER.exists():
        return datetime.fromisoformat(_BIRTH_DATE_MARKER.read_text().strip())
    ensure_data_dir()
    now = datetime.now(timezone.utc)
    _BIRTH_DATE_MARKER.write_text(now.isoformat())
    return now


# ── Competitor SERP (decision memo: max 2 vendors, 7gg cache) ──────────────
COMPETITOR_DOMAINS = ("cekindo.com", "emerhub.com")
COMPETITOR_CACHE_TTL_SECONDS = 7 * 86400
COMPETITOR_CACHE_DB = DATA_DIR / "competitor_serp_cache.db"

# ── EventBus channel consumed by war_room_event_sensor ─────────────────────
WAR_ROOM_EVENT_CHANNEL = "war_room.event"  # already active (migration 112)
