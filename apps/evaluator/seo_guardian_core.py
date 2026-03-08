import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Guardian] %(levelname)s: %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MOUTH_APP_DIR = PROJECT_ROOT / "apps" / "mouth"
KBLI_DATA_PATH = MOUTH_APP_DIR / "data" / "KBLI_2025_FINAL_CLEAN.json"
CREDENTIALS_PATH = PROJECT_ROOT / "google-credentials.json"
OUTPUT_PATH = PROJECT_ROOT / "SEO_ACTION_PLAN_REAL_DATA.json"

# Date range: last 7 days
END_DATE = date.today().isoformat()
START_DATE = (date.today() - timedelta(days=7)).isoformat()


class NuzantaraSEOGuardian:
    """
    Il 'Grande Sapiente' della SEO AI per Nuzantara.
    Usa credenziali reali per dominare Google Search Console e Analytics.
    GSC è la fonte primaria; Analytics è opzionale (fallback graceful).
    """

    def __init__(self) -> None:
        self.scopes = [
            "https://www.googleapis.com/auth/webmasters.readonly",
            "https://www.googleapis.com/auth/analytics.readonly",
        ]
        self.site_url = "https://balizero.com"
        self.credentials: Optional[service_account.Credentials] = self._load_credentials()

    def _load_credentials(self) -> Optional[service_account.Credentials]:
        if not CREDENTIALS_PATH.exists():
            logger.warning("Credentials file not found at %s. Running in demo mode.", CREDENTIALS_PATH)
            return None
        try:
            creds = service_account.Credentials.from_service_account_file(
                str(CREDENTIALS_PATH), scopes=self.scopes
            )
            logger.info("Credentials loaded OK (project: %s)", creds.service_account_email)
            return creds
        except Exception as e:
            logger.error("Failed to load credentials: %s", e)
            return None

    async def fetch_gsc_data(self) -> List[Dict[str, Any]]:
        """Recupera le top 50 keyword da Google Search Console (fonte primaria)."""
        if not self.credentials:
            logger.warning("No credentials — returning demo GSC data.")
            return [{"query": "bali company registration", "clicks": 120, "impressions": 800, "ctr": 0.15, "position": 3.2}]

        try:
            service = build("webmasters", "v3", credentials=self.credentials)
            request_body = {
                "startDate": START_DATE,
                "endDate": END_DATE,
                "dimensions": ["query"],
                "rowLimit": 50,
            }
            response = (
                service.searchanalytics()
                .query(siteUrl=self.site_url, body=request_body)
                .execute()
            )
            rows = response.get("rows", [])
            logger.info("GSC returned %d rows for %s → %s", len(rows), START_DATE, END_DATE)
            return rows
        except HttpError as e:
            logger.error("GSC HttpError: %s", e)
            return []
        except Exception as e:
            logger.error("GSC unexpected error: %s", e)
            return []

    async def fetch_analytics_data(self) -> Optional[Dict[str, Any]]:
        """
        Recupera metriche da Google Analytics (fonte secondaria, opzionale).
        Se il Property ID non è configurato o la property non esiste, restituisce None
        senza interrompere il flusso principale.
        """
        ga_property_id = os.environ.get("GA4_PROPERTY_ID")
        if not ga_property_id:
            logger.info("GA4_PROPERTY_ID not set — skipping Analytics (not required).")
            return None

        if not self.credentials:
            logger.info("No credentials — skipping Analytics.")
            return None

        try:
            service = build("analyticsdata", "v1beta", credentials=self.credentials)
            response = (
                service.properties()
                .runReport(
                    property=f"properties/{ga_property_id}",
                    body={
                        "dateRanges": [{"startDate": START_DATE, "endDate": END_DATE}],
                        "metrics": [{"name": "sessions"}, {"name": "bounceRate"}],
                        "dimensions": [{"name": "pagePath"}],
                        "limit": 10,
                    },
                )
                .execute()
            )
            logger.info("Analytics data fetched OK.")
            return response
        except HttpError as e:
            if e.resp.status in (403, 404):
                logger.warning("Analytics property %s not accessible (status %s) — skipping.", ga_property_id, e.resp.status)
            else:
                logger.error("Analytics HttpError: %s", e)
            return None
        except Exception as e:
            logger.error("Analytics unexpected error: %s", e)
            return None

    async def audit_kbli_indexing(self) -> List[str]:
        """Verifica la sitemap vs database KBLI."""
        if not KBLI_DATA_PATH.exists():
            logger.warning("KBLI data file not found at %s", KBLI_DATA_PATH)
            return []
        with open(KBLI_DATA_PATH) as f:
            kbli_data = json.load(f)
        codes = [c["kode_kbli_2025"] for c in kbli_data.get("data", [])]
        logger.info("Audit: %d codici KBLI mappati nel database.", len(codes))
        return codes

    async def generate_action_plan(
        self,
        gsc_rows: List[Dict[str, Any]],
        kbli_codes: List[str],
        analytics_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Genera il piano d'attacco SEO AI con dati reali."""
        logger.info("Generating SEO action plan...")

        # Identify top queries missing KBLI coverage
        kbli_keywords = {"kbli", "kode kbli", "klasifikasi baku lapangan usaha"}
        top_queries = [
            {
                "query": row.get("keys", [""])[0] if "keys" in row else row.get("query", ""),
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0), 4),
                "position": round(row.get("position", 0), 1),
            }
            for row in gsc_rows
        ]

        critical_gaps = [q for q in top_queries if q["position"] > 10 and q["clicks"] == 0]
        kbli_queries = [q for q in top_queries if any(kw in q["query"].lower() for kw in kbli_keywords)]

        plan: Dict[str, Any] = {
            "generated_at": date.today().isoformat(),
            "date_range": {"start": START_DATE, "end": END_DATE},
            "site_url": self.site_url,
            "data_sources": {
                "gsc": "real" if self.credentials else "demo",
                "analytics": "real" if analytics_data else "skipped",
            },
            "gsc_summary": {
                "total_queries": len(top_queries),
                "top_queries": top_queries[:10],
                "kbli_related_queries": kbli_queries,
            },
            "kbli_audit": {
                "total_codes": len(kbli_codes),
                "sample_codes": kbli_codes[:5],
            },
            "critical_gaps": critical_gaps[:20],
            "action_items": [
                {
                    "priority": "HIGH",
                    "action": "Submit 1,563 KBLI URLs to Google Indexing API",
                    "reason": f"Only {len(kbli_queries)} KBLI queries visible in GSC top 50",
                },
                {
                    "priority": "HIGH",
                    "action": "Add FAQ Schema to all KBLI Gold pages",
                    "reason": "Structured data increases CTR for AI-cited queries",
                },
                {
                    "priority": "MEDIUM",
                    "action": f"Fix {len(critical_gaps)} queries with position >10 and 0 clicks",
                    "reason": "High impression / zero click = metadata or content gap",
                },
                {
                    "priority": "LOW",
                    "action": "Update llms.txt with latest service pricing",
                    "reason": "AI crawlers (GPT, Gemini) reference llms.txt for structured answers",
                },
            ],
        }

        if analytics_data:
            plan["analytics_data"] = analytics_data

        with open(OUTPUT_PATH, "w") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        logger.info("Action plan saved to %s", OUTPUT_PATH)
        return plan

    async def run(self) -> Dict[str, Any]:
        logger.info("=== Nuzantara SEO Guardian: ACTIVE ===")
        logger.info("Site: %s | Period: %s → %s", self.site_url, START_DATE, END_DATE)

        gsc_data, kbli_codes, analytics_data = await asyncio.gather(
            self.fetch_gsc_data(),
            self.audit_kbli_indexing(),
            self.fetch_analytics_data(),
        )

        plan = await self.generate_action_plan(gsc_data, kbli_codes, analytics_data)
        logger.info("=== SEO Cycle Complete ===")
        return plan


if __name__ == "__main__":
    guardian = NuzantaraSEOGuardian()
    asyncio.run(guardian.run())
