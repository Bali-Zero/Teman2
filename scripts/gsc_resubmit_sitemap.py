#!/usr/bin/env python3
"""GSC Sitemap Re-submit — Plan A SEO Cell pre-natal Sprint 0.

Pings Google Search Console API to re-submit balizero.com sitemap so
newly-indexed pages (4 commercial-intent articles + 4 funnel pages with
fresh Schema.org JSON-LD) get re-discovered faster.

Auth: Service Account at .secrets/google-credentials.json
Usage: python3 scripts/gsc_resubmit_sitemap.py
Exit: 0 on success, 1 on failure.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
Plan: docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md Task 9
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[GSC ReSubmit] %(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"

SITE_URL = "https://balizero.com"
SITEMAP_URLS = [
    "https://balizero.com/sitemap.xml",
]


def main() -> int:
    if not CREDENTIALS_PATH.exists():
        logger.error("Credentials missing: %s", CREDENTIALS_PATH)
        return 1

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        logger.error(
            "Missing deps. Install: pip install google-auth google-api-python-client"
        )
        return 1

    creds = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/webmasters"],
    )
    service = build("webmasters", "v3", credentials=creds)

    failures = 0
    for sitemap_url in SITEMAP_URLS:
        try:
            service.sitemaps().submit(
                siteUrl=SITE_URL, feedpath=sitemap_url
            ).execute()
            logger.info("Submitted %s for site %s", sitemap_url, SITE_URL)
        except HttpError as e:
            logger.error("Failed to submit %s: %s", sitemap_url, e)
            failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
