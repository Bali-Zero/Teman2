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

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from backend.services.cognitive.models import (
    CrossDossierThesis,
    WeeklyStrategicBrief,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.intel.dossier_models import ResearchDossier
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
        except Exception as exc:  # noqa: BLE001
            logger.debug("newsletter dossiers fetch failed: %s", exc)

        # 2. theses (L1 Connector)
        try:
            theses = await self.cognitive_repo.recent_theses(
                days=self.theses_lookback, active_only=True,
            )
            content.theses = theses[: self.theses_max]
        except Exception as exc:  # noqa: BLE001
            logger.debug("newsletter theses fetch failed: %s", exc)

        # 3. Strategos brief (optional)
        try:
            content.brief = await self.cognitive_repo.latest_brief()
        except Exception as exc:  # noqa: BLE001
            logger.debug("newsletter brief fetch failed: %s", exc)

        return content


def _iso_monday(now: datetime) -> date:
    d = now.astimezone(timezone.utc).date()
    return d - timedelta(days=d.weekday())
