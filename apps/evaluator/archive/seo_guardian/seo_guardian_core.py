import os
import json
import argparse
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import date, datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[SEO Guardian] %(levelname)s: %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MOUTH_APP_DIR = PROJECT_ROOT / "apps" / "mouth"
KBLI_DATA_PATH = MOUTH_APP_DIR / "data" / "KBLI_2025_FINAL_CLEAN.json"
CREDENTIALS_PATH = PROJECT_ROOT / ".secrets" / "google-credentials.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "analysis" / "SEO_ACTION_PLAN_REAL_DATA.json"

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

    async def analyze_ai_seo(self) -> Dict[str, Any]:
        """
        Monitora l'integrità e la freschezza dei file di ingestione AI (llms.txt, etc.).
        Verifica la presenza di istruzioni di citazione e master data KBLI.
        """
        public_dir = PROJECT_ROOT / "apps" / "mouth" / "public"
        files_to_check = [
            "llms.txt",
            "llms-full.txt",
            "llms-id.txt",
            "llms-kbli.txt",
            "sitemap-ai.xml"
        ]
        
        results = {}
        for filename in files_to_check:
            file_path = public_dir / filename
            if not file_path.exists():
                results[filename] = {"status": "MISSING", "error": "File not found"}
                continue
            
            stats = file_path.stat()
            content = file_path.read_text(errors='ignore')
            
            results[filename] = {
                "status": "OK",
                "size": stats.st_size,
                "last_modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "has_citation_guard": "AI-CITATION-INSTRUCTION" in content,
                "is_empty": stats.st_size < 100
            }

        return results

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

        gsc_data, kbli_codes, analytics_data, geo_audit, ai_ingestion = await asyncio.gather(
            self.fetch_gsc_data(),
            self.audit_kbli_indexing(),
            self.fetch_analytics_data(),
            self.audit_geo_aeo(),
            self.analyze_ai_seo(),
        )

        plan = await self.generate_action_plan(gsc_data, kbli_codes, analytics_data)
        plan["geo_aeo_audit"] = geo_audit
        plan["ai_ingestion_audit"] = ai_ingestion

        # Add GEO-specific action items
        if geo_audit["coverage_percent"] < 80:
            plan["action_items"].insert(0, {
                "priority": "HIGH",
                "action": f"Add AI SEO metadata to {geo_audit['missing_ai_seo_count']} articles missing aiOptimization",
                "reason": f"Only {geo_audit['coverage_percent']}% of articles have AI-citable answerSnippet + entityMentions",
            })
        
        # Add AI Ingestion-specific action items
        missing_ai_files = [f for f, res in ai_ingestion.items() if res["status"] == "MISSING"]
        if missing_ai_files:
            plan["action_items"].insert(0, {
                "priority": "CRITICAL",
                "action": f"Restore missing AI ingestion files: {', '.join(missing_ai_files)}",
                "reason": "AI Bots (GPT, Perplexity) cannot ingest Bali Zero intelligence without these files",
            })
        
        missing_citation = [f for f, res in ai_ingestion.items() if res["status"] == "OK" and not res["has_citation_guard"]]
        if missing_citation:
            plan["action_items"].append({
                "priority": "HIGH",
                "action": f"Add Citation Guard to: {', '.join(missing_citation)}",
                "reason": "Ensure LLMs attribute Bali Zero when summarizing these intelligence assets",
            })

        if not geo_audit["llms_txt"]["fresh"]:
            plan["action_items"].append({
                "priority": "HIGH",
                "action": "Update llms.txt — file is stale (>30 days old)",
                "reason": "AI crawlers (GPTBot, ClaudeBot, PerplexityBot) rely on fresh llms.txt for citations",
            })
        logger.info("=== SEO Cycle Complete ===")
        return plan

    async def run_report(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the guardian and output structured JSON report.
        Used by the autonomous agent system.
        """
        logger.info("=== SEO Guardian: REPORT MODE ===")
        plan = await self.run()

        # Enrich with indexing state
        indexing_state_path = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
        indexing_state = {}
        if indexing_state_path.exists():
            with open(indexing_state_path) as f:
                raw = json.load(f)
                indexing_state = {
                    "total_submitted": raw.get("total_submitted", 0),
                    "failed_count": len(raw.get("failed", [])),
                    "last_run": raw.get("last_run"),
                }

        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "report",
            "seo_plan": plan,
            "geo_aeo_audit": plan.get("geo_aeo_audit", {}),
            "ai_ingestion_audit": plan.get("ai_ingestion_audit", {}),
            "indexing_state": indexing_state,
            "opportunities": self._extract_opportunities(plan, indexing_state),
        }

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Report saved to %s", out)

        return report

    async def audit_geo_aeo(self) -> Dict[str, Any]:
        """
        Audit GEO/AEO readiness: check AI SEO metadata on published articles.
        Verifies: answerSnippet, entityMentions, faqSchema, aiConfidenceScore,
        llms.txt freshness, and AI citation meta tags.
        """
        logger.info("Running GEO/AEO audit...")
        articles_dir = MOUTH_APP_DIR / "src" / "content" / "articles"
        llms_path = MOUTH_APP_DIR / "public" / "llms.txt"

        total_articles = 0
        with_ai_optimization = 0
        with_answer_snippet = 0
        with_entity_mentions = 0
        with_faq = 0
        missing_ai_seo: List[str] = []

        if articles_dir.exists():
            for mdx_file in articles_dir.rglob("*.mdx"):
                # Count all languages in GEO/AEO audit (multilingual coverage matters)
                pass  # No language filtering — audit all translations
                total_articles += 1
                try:
                    content = mdx_file.read_text(encoding="utf-8", errors="ignore")
                    # Check frontmatter for AI SEO fields
                    has_ai_opt = "aiOptimization:" in content
                    has_snippet = "answerSnippet:" in content
                    has_entities = "entityMentions:" in content
                    has_confidence = "aiConfidenceScore:" in content

                    if has_ai_opt:
                        with_ai_optimization += 1
                    if has_snippet:
                        with_answer_snippet += 1
                    if has_entities:
                        with_entity_mentions += 1
                    if not has_ai_opt and not has_confidence:
                        missing_ai_seo.append(mdx_file.stem)
                except Exception:
                    pass

        # Check llms.txt freshness
        llms_fresh = False
        llms_version = "unknown"
        if llms_path.exists():
            llms_content = llms_path.read_text(encoding="utf-8", errors="ignore")
            if "Version:" in llms_content:
                for line in llms_content.split("\n"):
                    if "Version:" in line:
                        llms_version = line.split("Version:")[-1].strip()
                        break
            # Fresh if modified in last 30 days
            from os import stat
            mtime = datetime.fromtimestamp(stat(llms_path).st_mtime)
            llms_fresh = (datetime.now() - mtime).days < 30

        coverage_pct = round((with_ai_optimization / max(total_articles, 1)) * 100, 1)

        audit = {
            "total_articles": total_articles,
            "with_ai_optimization": with_ai_optimization,
            "with_answer_snippet": with_answer_snippet,
            "with_entity_mentions": with_entity_mentions,
            "coverage_percent": coverage_pct,
            "missing_ai_seo_count": len(missing_ai_seo),
            "missing_ai_seo_sample": missing_ai_seo[:10],
            "llms_txt": {
                "exists": llms_path.exists(),
                "version": llms_version,
                "fresh": llms_fresh,
            },
        }

        logger.info(
            "GEO/AEO audit: %d/%d articles have AI optimization (%.1f%%), llms.txt v%s (%s)",
            with_ai_optimization, total_articles, coverage_pct,
            llms_version, "fresh" if llms_fresh else "STALE",
        )
        return audit

    def _extract_opportunities(self, plan: Dict[str, Any], indexing_state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract actionable opportunities from the SEO plan."""
        opportunities = []

        # High-impression zero-click pages
        for gap in plan.get("critical_gaps", []):
            opportunities.append({
                "type": "ctr_optimization",
                "risk": "LOW",
                "query": gap.get("query", ""),
                "impressions": gap.get("impressions", 0),
                "current_ctr": gap.get("ctr", 0),
                "current_position": gap.get("position", 0),
                "suggested_action": "update_meta_description",
            })

        # Indexing gaps — use pre-loaded state to avoid double file read
        total_submitted = (indexing_state or {}).get("total_submitted", 0)
        if not indexing_state:
            indexing_state_path = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"
            if indexing_state_path.exists():
                with open(indexing_state_path) as f:
                    total_submitted = json.load(f).get("total_submitted", 0)

        pending = 1563 - total_submitted
        if pending > 0:
            opportunities.append({
                "type": "indexing_submission",
                "risk": "LOW",
                "pending_urls": pending,
                "suggested_action": "submit_indexing_batch",
                "batch_size": min(pending, 50),
            })

        # AI Ingestion Gaps
        ai_ingestion = plan.get("ai_ingestion_audit", {})
        for filename, res in ai_ingestion.items():
            if res.get("status") == "MISSING":
                opportunities.append({
                    "type": "ai_visibility",
                    "risk": "MEDIUM",
                    "file": filename,
                    "suggested_action": "generate_ai_ingestion_files",
                    "reason": f"Critical AI ingestion file {filename} is missing",
                })
            elif not res.get("has_citation_guard"):
                opportunities.append({
                    "type": "ai_branding",
                    "risk": "LOW",
                    "file": filename,
                    "suggested_action": "add_citation_guard",
                    "reason": f"File {filename} is missing AI-CITATION-INSTRUCTION",
                })

        return opportunities


def main() -> None:
    parser = argparse.ArgumentParser(description="Nuzantara SEO Guardian")
    parser.add_argument(
        "--mode",
        choices=["run", "report"],
        default="run",
        help="run: standard execution. report: structured JSON output for agent system.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for report mode (default: stdout as JSON)",
    )
    args = parser.parse_args()

    guardian = NuzantaraSEOGuardian()

    if args.mode == "report":
        report = asyncio.run(guardian.run_report(output_path=args.output))
        if not args.output:
            print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        asyncio.run(guardian.run())


if __name__ == "__main__":
    main()
