"""
Jurnal.id Integration Service for LKPM data collection.

Pulls journal entries and chart of accounts from Jurnal.id API.
Uses httpx.AsyncClient, follows zoho_oauth_service.py pattern.
"""

import logging
from datetime import date
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants

logger = logging.getLogger(__name__)


class JurnalService:
    """Client for Jurnal.id accounting API."""

    def __init__(self, api_key: str | None = None, api_url: str | None = None) -> None:
        self.api_key = api_key or settings.jurnal_api_key
        self.api_url = (api_url or settings.jurnal_api_url).rstrip("/")

    def _headers(self, client_api_key: str | None = None) -> dict[str, str]:
        """Build request headers with API key."""
        key = client_api_key or self.api_key
        if not key:
            raise ValueError("Jurnal API key not configured")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_journal_entries(
        self,
        start_date: date,
        end_date: date,
        api_key: str | None = None,
        company_id: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Pull journal entries for a date range.

        Returns dict with 'entries' list and 'pagination' info.
        """
        logger.info(f"Fetching Jurnal entries: {start_date} to {end_date}, page={page}")

        params: dict[str, Any] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": page,
            "page_size": page_size,
        }
        if company_id:
            params["company_id"] = company_id

        try:
            async with httpx.AsyncClient(timeout=HttpTimeoutConstants.JURNAL_TIMEOUT) as client:
                response = await client.get(
                    f"{self.api_url}/journal_entries",
                    headers=self._headers(api_key),
                    params=params,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Jurnal API error: {response.status_code} — {response.text[:200]}"
                    )
                    raise ValueError(f"Jurnal API returned {response.status_code}")

                data = response.json()
                entries = data.get("journal_entries", data.get("data", []))
                pagination = data.get("pagination", {})

                logger.info(f"Fetched {len(entries)} journal entries (page {page})")
                return {"entries": entries, "pagination": pagination}

        except httpx.RequestError as e:
            logger.error(f"Jurnal API network error: {type(e).__name__}: {e}")
            raise ValueError(f"Network error connecting to Jurnal: {e}") from e

    async def get_all_journal_entries(
        self,
        start_date: date,
        end_date: date,
        api_key: str | None = None,
        company_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all journal entries across pages."""
        all_entries: list[dict[str, Any]] = []
        page = 1
        max_pages = 50  # Safety limit

        while page <= max_pages:
            result = await self.get_journal_entries(
                start_date=start_date,
                end_date=end_date,
                api_key=api_key,
                company_id=company_id,
                page=page,
            )
            entries = result["entries"]
            all_entries.extend(entries)

            pagination = result.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            if page >= total_pages:
                break
            page += 1

        logger.info(f"Total Jurnal entries fetched: {len(all_entries)}")
        return all_entries

    async def get_chart_of_accounts(
        self,
        api_key: str | None = None,
        company_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch chart of accounts for transaction categorization mapping.

        Returns list of account dicts with 'number', 'name', 'category'.
        """
        logger.info("Fetching Jurnal chart of accounts")

        params: dict[str, Any] = {}
        if company_id:
            params["company_id"] = company_id

        try:
            async with httpx.AsyncClient(timeout=HttpTimeoutConstants.JURNAL_TIMEOUT) as client:
                response = await client.get(
                    f"{self.api_url}/chart_of_accounts",
                    headers=self._headers(api_key),
                    params=params,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Jurnal CoA error: {response.status_code} — {response.text[:200]}"
                    )
                    raise ValueError(f"Jurnal API returned {response.status_code}")

                data = response.json()
                accounts = data.get("chart_of_accounts", data.get("data", []))
                logger.info(f"Fetched {len(accounts)} chart of accounts")
                return accounts

        except httpx.RequestError as e:
            logger.error(f"Jurnal CoA network error: {type(e).__name__}: {e}")
            raise ValueError(f"Network error connecting to Jurnal: {e}") from e
