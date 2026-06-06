"""Pre-score deterministico per item dell'Intel Lake (`intel_items`).

Estratto/adattato da `scripts/wr2_topic_selector.py:score_item` (pesi BZ identici).
Differenza-chiave (panel 3-LLM 2026-06-06): qui il pre-score è **ordinamento/tie-break**,
NON un gate a monte dell'LLM. Lo Step 1 della War Room giudica TUTTI i freschi con l'LLM;
il pre-score serve solo a ordinare i candidati e — solo in caso di volume anomalo
(>MAX_ITEMS) — a tagliare per freshness+tier, MAI per keyword (i titoli regolatori
asciutti, es. "PMK 131/2024", hanno poche keyword ma sono core-BZ).

Schema di input: dict da `intel_items` con almeno
    title, summary, source_domain, published_at, first_seen_at, topic_tags
(i campi mancanti degradano a default, mai eccezione).

PROVENANCE: pesi e logica freshness derivati da wr2_topic_selector.py:score_item
(stesso repo, licenza nostra). Fork intenzionale — vedi §5 del design doc
research/marketing/2026-06-06-warroom-step1-intel-lake-reader.md. Quando Step1+2
rimpiazzano wr2_topic_selector.py, unificare qui. Owner: 2026-06-06.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

# --- Pesi BZ (identici a wr2_topic_selector.BZ_KEYWORDS) ---------------------
BZ_KEYWORDS: dict[str, int] = {
    # visa / immigration (highest priority)
    "investor kitas": 30, "golden visa": 25, "kitas": 25, "kitap": 25,
    "visa": 20, "imigrasi": 20, "immigration": 20, "overstay": 20, "nomad": 18,
    # tax / company
    "kbli": 25, "npwp": 20, "pma": 20, "nik": 15, "pajak": 15, "tax": 12, "bpjs": 10,
    # property
    "property": 15, "investor": 12, "real estate": 12, "villa": 10,
    # generic (low weight)
    "bali": 8, "indonesia": 5, "jakarta": 3,
}

FRESHNESS_MAX_POINTS: int = 30
FRESHNESS_HALF_LIFE_HOURS: float = 72.0

# Tier derivato dal source_domain (lo Step 1 non ha il campo `tier` della staging area).
# T1 = fonte primaria/istituzionale o major news; T2 = news/consultancy nota; T3 = resto.
TIER_WEIGHT: dict[str, int] = {"T1": 30, "T2": 15, "T3": 5}
_T1_DOMAIN_HINTS = (
    "antaranews", "liputan6", "kompas", "detik", "cnnindonesia", "thejakartapost",
    "tempo.co", "bisnis.com", "kontan.co", "go.id",  # *.go.id = governo
)
_T2_DOMAIN_HINTS = (
    "consultancy", "consulting", "lawfirm", "law.co", "emerhub", "letsmoveindonesia",
    "imigrasi", "pajak", "oss.go", "investindonesia",
)

# Titoli "routine/evergreen": penalizzati (stesso pattern del selettore).
ROUTINE_TITLE_PENALTY: float = 20.0
ROUTINE_TITLE_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*(?:how\s+to|guide\s+to|the\s+complete\s+guide|.+\s+explained|.+\s+decoded|"
    r"step[-\s]by[-\s]step|everything\s+you\s+need)\b",
    re.IGNORECASE,
)


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _derive_tier(source_domain: str) -> str:
    d = (source_domain or "").lower()
    if any(h in d for h in _T1_DOMAIN_HINTS):
        return "T1"
    if any(h in d for h in _T2_DOMAIN_HINTS):
        return "T2"
    return "T3"


def prescore_item(item: dict[str, Any], *, now: Optional[datetime] = None) -> tuple[float, dict[str, Any]]:
    """(score, breakdown) per un item di intel_items. NON è un gate — solo ordinamento.

    `now` iniettabile per determinismo (il chiamante congela run_ts una volta sola).
    `freshness_points` e `tier_points` sono i SOLI campi usati per l'eventuale
    circuit-breaker di volume; `keywords_points` NON va mai usato per tagliare.
    """
    now = now or datetime.now(timezone.utc)
    detail: dict[str, Any] = {"rules": {}}

    # freshness: fallback published_at -> first_seen_at (i 4 yt_monitor reali senza data)
    pub = _parse_dt(item.get("published_at")) or _parse_dt(item.get("first_seen_at"))
    age_h = max(0.0, (now - pub).total_seconds() / 3600.0) if pub else 24.0
    fresh_score = max(0.0, 1 - age_h / FRESHNESS_HALF_LIFE_HOURS) * FRESHNESS_MAX_POINTS
    detail["rules"]["freshness_points"] = round(fresh_score, 1)
    detail["rules"]["age_hours"] = round(age_h, 1)
    detail["rules"]["date_source"] = (
        "published_at" if _parse_dt(item.get("published_at")) else
        ("first_seen_at" if _parse_dt(item.get("first_seen_at")) else "none")
    )

    title = str(item.get("title") or "").lower()
    summary = str(item.get("summary") or "")[:1500].lower()
    tags = " ".join(item.get("topic_tags") or []).lower()
    text = f"{title} {summary} {tags}"

    kw_hits: list[str] = []
    kw_score = 0
    for kw, w in BZ_KEYWORDS.items():
        if kw in text:
            kw_hits.append(kw)
            kw_score += w
    detail["rules"]["keywords_matched"] = kw_hits
    detail["rules"]["keywords_points"] = kw_score

    tier = _derive_tier(str(item.get("source_domain") or ""))
    tier_score = TIER_WEIGHT.get(tier, 5)
    detail["rules"]["tier"] = tier
    detail["rules"]["tier_points"] = tier_score

    routine_penalty = ROUTINE_TITLE_PENALTY if (title and ROUTINE_TITLE_PATTERN.search(title)) else 0.0
    detail["rules"]["routine_penalty"] = routine_penalty

    total = fresh_score + kw_score + tier_score - routine_penalty
    detail["score"] = round(total, 1)
    return total, detail


def order_candidates(
    items: list[dict[str, Any]], *, now: Optional[datetime] = None
) -> list[tuple[dict[str, Any], float, dict[str, Any]]]:
    """Ordina (desc) i candidati per pre-score. NON taglia. Restituisce (item, score, detail)."""
    scored = [(it, *prescore_item(it, now=now)) for it in items]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


def circuit_break_by_volume(
    scored: list[tuple[dict[str, Any], float, dict[str, Any]]],
    *,
    max_items: int,
) -> list[tuple[dict[str, Any], float, dict[str, Any]]]:
    """SOLO se il volume supera max_items: tieni i top per freshness+tier (MAI keyword).

    Panel 3-LLM: il taglio per volume anomalo non deve mai usare le keyword
    (penalizzerebbe i titoli regolatori asciutti = i gioielli core-BZ).
    """
    if len(scored) <= max_items:
        return scored
    by_fresh_tier = sorted(
        scored,
        key=lambda t: (t[2]["rules"]["freshness_points"] + t[2]["rules"]["tier_points"]),
        reverse=True,
    )
    return by_fresh_tier[:max_items]
