"""Base scraper with retry, rate-limiting, and normalized output."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from osint_nexus.config import RAW_DIR, SCRAPE_MAX_RETRIES
from osint_nexus.utils.logging import get_logger

logger = get_logger("scraper")


class ScrapedRecord(BaseModel):
    """Normalized output from any scraper."""

    source: str
    entity_type: str
    url: str
    raw_data: dict[str, Any]
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            blob = orjson.dumps(self.raw_data, option=orjson.OPT_SORT_KEYS)
            self.content_hash = hashlib.sha256(blob).hexdigest()[:16]


class BaseScraper(ABC):
    """All scrapers inherit from this."""

    name: str = "base"

    def __init__(self) -> None:
        self.logger = get_logger(f"scraper.{self.name}")
        self._output_dir = RAW_DIR / self.name
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Run the scraper. Returns normalized records."""

    def save_records(self, records: list[ScrapedRecord]) -> Path:
        """Persist records to JSON. Returns file path."""
        if not records:
            return self._output_dir
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self._output_dir / f"{self.name}_{ts}.json"
        data = [r.model_dump(mode="json") for r in records]
        path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
        self.logger.info("Saved %d records → %s", len(records), path.name)
        return path

    @staticmethod
    def retry_scrape(func):
        """Decorator for retryable scrape operations."""
        return retry(
            stop=stop_after_attempt(SCRAPE_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((Exception,)),
            before_sleep=lambda s: logger.warning(
                "Retry %d/%d after %s",
                s.attempt_number,
                SCRAPE_MAX_RETRIES,
                s.outcome.exception() if s.outcome else "unknown",
            ),
        )(func)
