"""WeeklyRoundupBuilder — aggregate content for the Monday newsletter.

Collects:
    - top 5 ResearchDossier (public_safe=true, last 7 days, by confidence)
    - latest approved WeeklyStrategicBrief (if any)
    - 3 most recent active CrossDossierThesis (L1 Connector output)

Produces a :class:`RoundupContent` that the NewsletterPublisher can hand to
the HTML template renderer.

Legge 2 OSINT blindato: ONLY public_safe dossiers are included. Private
dossiers (intelligence blindata) never reach the newsletter.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from backend.services.cognitive.models import (
    CrossDossierThesis,
    WeeklyStrategicBrief,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.intel.dossier_models import IntelItemSummary, ResearchDossier
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger(__name__)


DEFAULT_DOSSIERS_MAX = 5
DEFAULT_DOSSIERS_LOOKBACK = 7
DEFAULT_THESES_MAX = 3
DEFAULT_THESES_LOOKBACK = 14


@dataclass
class RoundupContent:
    week_of: date
    generated_at: datetime
    dossiers: list[ResearchDossier] = field(default_factory=list)
    theses: list[CrossDossierThesis] = field(default_factory=list)
    brief: WeeklyStrategicBrief | None = None

    @property
    def is_empty(self) -> bool:
        return not self.dossiers and not self.theses and self.brief is None


class WeeklyRoundupBuilder:
    """Read-only aggregator. OSINT-safe (public_safe only)."""

    def __init__(
        self,
        intel_repo: IntelRepository,
        cognitive_repo: CognitiveRepository,
        *,
        dossiers_max: int = DEFAULT_DOSSIERS_MAX,
        dossiers_lookback_days: int = DEFAULT_DOSSIERS_LOOKBACK,
        theses_max: int = DEFAULT_THESES_MAX,
        theses_lookback_days: int = DEFAULT_THESES_LOOKBACK,
    ) -> None:
        self.intel_repo = intel_repo
        self.cognitive_repo = cognitive_repo
        self.dossiers_max = dossiers_max
        self.dossiers_lookback = dossiers_lookback_days
        self.theses_max = theses_max
        self.theses_lookback = theses_lookback_days

    async def build(
        self,
        *,
        week_of: date | None = None,
        now: datetime | None = None,
    ) -> RoundupContent:
        now = now or datetime.now(timezone.utc)
        if week_of is None:
            week_of = _iso_monday(now)

        content = RoundupContent(week_of=week_of, generated_at=now)

        # 1. public_safe dossiers
        try:
            rows = await self.intel_repo.fetch_safe(
                """
                SELECT * FROM research_dossiers
                 WHERE archived_at IS NULL
                   AND public_safe = TRUE
                   AND freshness_expiry > NOW()
                   AND created_at > NOW() - make_interval(days => $1)
                 ORDER BY confidence_0_1 DESC, created_at DESC
                 LIMIT $2;
                """,
                self.dossiers_lookback,
                self.dossiers_max,
            )
            from backend.services.intel.dossier_repository import _row_to_dossier

            content.dossiers = [_row_to_dossier(row) for row in rows]
        except Exception as exc:
            logger.debug("newsletter dossiers fetch failed: %s", exc)

        # 2. theses (L1 Connector)
        try:
            theses = await self.cognitive_repo.recent_theses(
                days=self.theses_lookback,
                active_only=True,
            )
            content.theses = theses[: self.theses_max]
        except Exception as exc:
            logger.debug("newsletter theses fetch failed: %s", exc)

        # 3. Strategos brief (optional)
        try:
            content.brief = await self.cognitive_repo.latest_brief()
        except Exception as exc:
            logger.debug("newsletter brief fetch failed: %s", exc)

        return content


def _iso_monday(now: datetime) -> date:
    d = now.astimezone(timezone.utc).date()
    return d - timedelta(days=d.weekday())


# ── Daily digest (internal, 2026-07-14) ─────────────────────────────
#
# Distinct from WeeklyRoundupBuilder above: this is the INTERNAL daily
# digest (Zero mandate 2026-07-14 — "mai spedita finora, diventa interna
# daily"), not the public blog-subscriber newsletter. Sources are the raw
# internal Intel Lake (``intel_items``) and the WR2 strategic-synthesis
# layer (``cross_dossier_theses``) — both OSINT, both fine for an
# internal-only audience (no public_safe gate; Legge 2 boundary is about
# *audience*, and this artifact's audience is the Bali Zero team, never a
# public subscriber list).

DEFAULT_DAILY_LOOKBACK_HOURS = 48
DEFAULT_DAILY_THESES_MAX = 2
DEFAULT_DAILY_TOTAL_MAX = 3
DEFAULT_DAILY_SCARCE_FLOOR = 2  # fewer than this total items → "scarce day"

# Word-boundary keyword filter for intel_items relevance, grouped by
# editorial category. topic_tags on the raw lake rows are noisy (an
# unrelated cooperative-politics story was seen tagged "visa"/"immigration"
# in production data 2026-07-14, and a Bali property-market-trust article
# was tagged "visa" too) — filtering AND labeling off the title/summary
# text itself is more reliable than trusting the tag. Order matters: the
# first category whose keyword matches becomes the item's domain_tag.
_RELEVANCE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "VISA": ("visa", "kitas", "kitap", "imigrasi", "immigration", "overstay"),
    "TAX": ("pajak", "tax", "pph", "ppn", "djp", "npwp", "spt", "lkpm"),
    "KBLI": ("kbli", "pma", "pmdn", "oss", "nib", "izin"),
    "PROPERTY": ("property", "villa", "hak pakai", "sertifikat", "tanah"),
    "COMPLIANCE": (
        "kemenkumham",
        "permenkumham",
        "permenaker",
        "kemenaker",
        "compliance",
        "regulasi",
        "regulation",
        "akta",
        "notaris",
    ),
}
_RELEVANCE_RE = re.compile(
    r"\b("
    + "|".join(re.escape(k) for keywords in _RELEVANCE_CATEGORIES.values() for k in keywords)
    + r")\b",
    re.IGNORECASE,
)
_CATEGORY_RES: dict[str, re.Pattern[str]] = {
    tag: re.compile(r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE)
    for tag, keywords in _RELEVANCE_CATEGORIES.items()
}


@dataclass
class DailyDigestItem:
    kind: str  # "thesis" | "intel_item"
    title: str
    body: str  # the "why it matters" / summary text, plain (escaped at render time)
    source_label: str  # e.g. "Bali Zero Connector" or "en.tempo.co"
    source_url: str | None
    source_date: datetime | None
    domain_tag: str  # short kicker, e.g. "STRATEGOS", "TAX", "VISA"


@dataclass
class DailyDigestContent:
    day: date
    generated_at: datetime
    items: list[DailyDigestItem] = field(default_factory=list)
    scarce: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.items


def _thesis_to_item(t: CrossDossierThesis) -> DailyDigestItem:
    body = t.implication or t.narrative[:400]
    return DailyDigestItem(
        kind="thesis",
        title=t.title,
        body=body,
        source_label="Bali Zero Connector",
        source_url=None,
        source_date=t.generated_at,
        domain_tag="STRATEGOS",
    )


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WP_APPEARED_FIRST_RE = re.compile(
    r"\s*The post .*? appeared first on .*?\.?\s*$", re.IGNORECASE | re.DOTALL
)
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_summary(raw: str, *, max_len: int = 320) -> str:
    """Strip HTML markup, entities, and WordPress-RSS boilerplate.

    Found live 2026-07-14: some scraped intel_items.summary values are the
    raw RSS <description> — full HTML tags, `&#8217;`-style entities, and a
    trailing "The post X appeared first on Y." syndication footer. None of
    that is editorial content; the digest must show clean prose, not a raw
    feed dump.
    """
    text = _HTML_TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = _WP_APPEARED_FIRST_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _intel_item_to_item(i: IntelItemSummary) -> DailyDigestItem:
    return DailyDigestItem(
        kind="intel_item",
        title=i.title,
        body=_clean_summary(i.summary) if i.summary else "",
        source_label=i.source_domain or "source",
        source_url=i.canonical_url,
        source_date=i.published_at or i.first_seen_at,
        domain_tag=_domain_tag_for(i),
    )


def _domain_tag_for(i: IntelItemSummary) -> str:
    """Kicker badge derived from the matched relevance category, NOT the
    raw ``topic_tags`` (found noisy live 2026-07-14 — a Bali property-market
    article was tagged "visa"). Falls back to "INTEL" if, somehow, nothing
    in _RELEVANCE_CATEGORIES matches (should not happen post-_is_relevant)."""
    haystack = f"{i.title} {_clean_summary(i.summary) if i.summary else ''}"
    for tag, pattern in _CATEGORY_RES.items():
        if pattern.search(haystack):
            return tag
    return "INTEL"


def _is_relevant(i: IntelItemSummary) -> bool:
    haystack = f"{i.title} {_clean_summary(i.summary) if i.summary else ''}"
    return bool(_RELEVANCE_RE.search(haystack))


def _has_editorial_content(i: IntelItemSummary) -> bool:
    """Reject rows with no (or whitespace-only, post-cleaning) summary.

    Found live 2026-07-14: some scraped intel_items have title but empty
    summary — selecting them renders a blank body line in the card. Others
    have a summary that's ONLY WordPress-RSS boilerplate ("The post X
    appeared first on Y.") which _clean_summary strips to empty. Either
    way: an empty body is honest (no fabrication) but reads as broken;
    better to skip and let another fresh, relevant item (or the scarce-day
    note) take the slot.
    """
    return bool(_clean_summary(i.summary).strip()) if i.summary else False


class DailyDigestBuilder:
    """Read-only aggregator for the internal daily digest.

    Selection order (editorial priority, not just recency):
      1. up to ``theses_max`` fresh (<= lookback) active CrossDossierThesis
         — already-synthesized Bali Zero-specific implications.
      2. fresh, topically-relevant intel_items fill the remaining slots
         up to ``total_max``.

    Never fabricates: every item traces to a real DB row (kind + title +
    source). If fewer than ``DEFAULT_DAILY_SCARCE_FLOOR`` items are found,
    ``scarce=True`` is set — the caller must send an honest "quiet day"
    note rather than pad with stale content.
    """

    def __init__(
        self,
        intel_repo: IntelRepository,
        cognitive_repo: CognitiveRepository,
        *,
        lookback_hours: int = DEFAULT_DAILY_LOOKBACK_HOURS,
        theses_max: int = DEFAULT_DAILY_THESES_MAX,
        total_max: int = DEFAULT_DAILY_TOTAL_MAX,
    ) -> None:
        self.intel_repo = intel_repo
        self.cognitive_repo = cognitive_repo
        self.lookback_hours = lookback_hours
        self.theses_max = theses_max
        self.total_max = total_max

    async def build_daily(
        self,
        *,
        now: datetime | None = None,
    ) -> DailyDigestContent:
        now = now or datetime.now(timezone.utc)
        content = DailyDigestContent(day=now.date(), generated_at=now)

        theses: list[CrossDossierThesis] = []
        try:
            lookback_days = max(1, -(-self.lookback_hours // 24))  # ceil
            all_theses = await self.cognitive_repo.recent_theses(
                days=lookback_days,
                active_only=True,
            )
            cutoff = now - timedelta(hours=self.lookback_hours)
            theses = [t for t in all_theses if t.generated_at >= cutoff][: self.theses_max]
        except Exception as exc:
            logger.debug("daily digest theses fetch failed: %s", exc)

        items: list[DailyDigestItem] = [_thesis_to_item(t) for t in theses]

        remaining = self.total_max - len(items)
        if remaining > 0:
            try:
                candidates = await self.intel_repo.fetch_recent_intel_items(
                    lookback_hours=self.lookback_hours,
                    limit=max(remaining * 5, 10),  # over-fetch, then relevance-filter
                )
                relevant = [i for i in candidates if _is_relevant(i) and _has_editorial_content(i)]
                items.extend(_intel_item_to_item(i) for i in relevant[:remaining])
            except Exception as exc:
                logger.debug("daily digest intel_items fetch failed: %s", exc)

        content.items = items
        content.scarce = len(items) < DEFAULT_DAILY_SCARCE_FLOOR
        return content
