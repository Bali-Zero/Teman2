"""NLM Deep Research Pipeline — NB-7: Editorial & Content Strategy.

Daily execution: 02:40-03:00 WITA (Mon-Sat)
Schedule: 5-cluster rotation (Mon=A, Tue=B, Wed=C, Thu=D, Fri=E, Sat=A)
Output: ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb7.json

Run via:
    python -m apps.evaluator.nlm_deep_research.nb7_pipeline
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from .circuit_breaker import CircuitBreakerRegistry
from .claim_extractor import (
    ClaimRecord,
    append_claims_to_registry,
    extract_claims_from_response,
    load_claims_count,
)
from .registry import SourceRegistry
from .source_management import (
    compute_nhs,
    classify_nhs,
    NotebookHealthInput,
)

logger = logging.getLogger(__name__)

# NB-7 configuration
NB7_NOTEBOOK_ID = "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb7_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb7_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb7_sources.json"
BRIEF_DIR = Path.home() / ".agent" / "decisions" / "nlm_briefs"
BRIEF_FILE = BRIEF_DIR / "daily_intelligence_brief_nb7.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 3
PIPELINE_DEADLINE_MINUTE = 0

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40

# 5-cluster rotation (Mon=0 → Fri=4, Sat=5 → recycles A)
CLUSTER_ROTATION = {
    0: ("A", "SEO & GEO Content Strategy"),
    1: ("B", "Audience & Persona Research"),
    2: ("C", "Content Formats & Distribution"),
    3: ("D", "Competitor Content Analysis"),
    4: ("E", "AI-Assisted Content Workflows"),
    5: ("A", "SEO & GEO Content Strategy"),  # Saturday = repeat A
}

# L1 query templates (English primary for editorial content, 60%)
L1_QUERIES: dict[str, str] = {
    "A": (
        "Latest SEO and GEO (Generative Engine Optimization) strategies for B2B legal/business "
        "services content in 2026. How AI search engines (ChatGPT, Perplexity, Gemini) cite "
        "authoritative legal content differently from Google. E-E-A-T signals for YMYL legal "
        "content, structured data for FAQ/HowTo schema, llms.txt strategy, and answer snippet "
        "optimization for 'how to set up a company in Bali' type queries. "
        "Source: Search Engine Journal, Ahrefs Blog, Clearscope 2025-2026."
    ),
    "B": (
        "Content audience research for Indonesian business services targeting expats in Bali 2026: "
        "Digital nomad visa applicant journey stages, pain points by nationality (Australian, "
        "European, American), search intent patterns for 'Bali company setup', 'KITAS application', "
        "'tax Indonesia foreigner' keywords. Seasonal trends (high season Jan-Mar, Jul-Aug). "
        "Source: Ahrefs keyword data, SparkToro audience research, Google Trends Indonesia."
    ),
    "C": (
        "Best performing content formats for B2B legal services in Southeast Asia 2026: "
        "Long-form guides (3000+ words) vs quick-reference tables, video content performance "
        "for visa/company topics, podcast/audio content for expat communities, "
        "interactive calculators (tax, BPJS, cost of living), newsletter open rates for "
        "regulatory update content. Source: HubSpot State of Marketing 2026, "
        "Content Marketing Institute, Ahrefs SEO study."
    ),
    "D": (
        "Competitor content strategy analysis for Indonesian business services market 2026: "
        "How do Emerhub, InCorp, Cekindo, and Seven Stones structure their content? "
        "Topic gaps not covered by competitors, keyword opportunities with low competition, "
        "backlink profiles of top-ranking Bali business guides. What content earns the most "
        "inbound links in the Indonesian expat legal niche? "
        "Source: Ahrefs, Semrush, Moz competitor analysis."
    ),
    "E": (
        "AI-assisted content creation workflows for legal/regulatory content 2026: "
        "How to use LLMs (Claude, GPT, Gemini) for drafting regulatory explainers while "
        "maintaining accuracy (fact-check protocols, human review gates), "
        "AI for multilingual content (Bahasa Indonesia + English), "
        "automated regulatory change detection for content refresh triggers, "
        "and disclosure requirements for AI-generated legal content. "
        "Source: Reuters Institute AI Content Report 2026, Nieman Lab, Content Science Review."
    ),
}

# L2 query templates (Bahasa Indonesia 30%, tactical depth)
L2_QUERIES: dict[str, str] = {
    "A": (
        "Practical GEO optimization tactics for Bali Zero / Zantara content portfolio 2026: "
        "Specific schema markup for legal service FAQs, how to structure 'definitive guide' "
        "articles to maximize AI citation probability, entity optimization for 'PT PMA Bali', "
        "'KITAS Bali', 'digital nomad visa Indonesia' entities in knowledge graphs, "
        "and measuring GEO impact via brand mentions in AI responses. "
        "Source: Wordtune GEO study, Semrush AI Visibility report, Clearscope case studies."
    ),
    "B": (
        "Strategi konten untuk menjangkau ekspatriat dan investor asing di Bali 2026: "
        "Keyword cluster 'setup bisnis di Bali', 'visa kerja Indonesia', 'pajak ekspatriat Bali', "
        "volume pencarian dan kesulitan, konten dalam Bahasa Inggris vs Indonesia, "
        "dan platform media sosial yang paling efektif (LinkedIn vs Instagram vs Facebook Groups "
        "expat). Sumber: Ahrefs, Google Search Console data Bali Zero, Semrush."
    ),
    "C": (
        "Content distribution strategy for Indonesian legal content targeting global expats 2026: "
        "Reddit communities (r/indonesia, r/digitalnomad, r/expats), Facebook Groups "
        "(Bali Expats, Digital Nomads Bali, Foreigners in Indonesia), LinkedIn for B2B, "
        "WhatsApp broadcast lists for regulatory updates, email newsletter segmentation "
        "by client stage (prospect/new client/active/alumni). Engagement benchmarks per channel. "
        "Source: Sprout Social, Buffer, Mailchimp benchmark reports 2026."
    ),
    "D": (
        "Gap analysis: what content topics are underserved in the Bali/Indonesia business "
        "services market that Bali Zero could own in 2026? "
        "Topics with search volume >500/month, difficulty <40, currently no authoritative "
        "English-language source: examples might include Coretax DJP for foreigners, "
        "PP 28/2025 property law, JKP unemployment insurance for expats, "
        "KBLI 2025 classification guide. Prioritize by business impact. "
        "Source: Ahrefs keyword explorer, Google Search Console, NLM NB-2/3/4/5 gap findings."
    ),
    "E": (
        "Quality assurance framework for AI-generated regulatory content at scale 2026: "
        "Multi-layer review process (AI draft → legal expert check → compliance officer sign-off), "
        "version control for regulatory articles (date-stamped, changelog), "
        "automated alerts when source regulation changes (webhook from JDIH?), "
        "and reader trust signals (author bio, last verified date, source citations). "
        "Source: Reuters Institute, LexBlog legal content standards, ABA Tech Report."
    ),
}


class PipelinePhase(Enum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    RUNNING_L1 = "RUNNING_L1"
    ASSESSING = "ASSESSING"
    RUNNING_L2 = "RUNNING_L2"
    CONSOLIDATING = "CONSOLIDATING"
    COMPLETE = "COMPLETE"
    HALTED = "HALTED"


class DegradationLevel(Enum):
    NOMINAL = "NOMINAL"
    DEGRADED_L1 = "DEGRADED_L1"
    DEGRADED_L2 = "DEGRADED_L2"
    HALTED = "HALTED"


def _now_wita() -> datetime:
    return datetime.now(timezone.utc) + WITA_OFFSET


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NB7Pipeline:
    """NLM pipeline for NB-7: Editorial & Content Strategy.

    Architecture mirrors NB-4 pipeline exactly.
    Run slot: 02:40-03:00 WITA Mon-Sat.
    """

    def __init__(
        self,
        state_file: str = STATE_FILE,
        claims_file: str = CLAIMS_FILE,
        registry_file: str = REGISTRY_FILE,
        nlm_query_fn=None,
        dry_run: bool = False,
        force: bool = False,
    ) -> None:
        self.state_file = Path(state_file)
        self.claims_file = Path(claims_file)
        self.registry = SourceRegistry(registry_file)
        self.circuit_breakers: Optional[CircuitBreakerRegistry] = None
        self.dry_run = dry_run
        self.force = force
        self._nlm_query = nlm_query_fn
        self._state: dict = {}
        self._run_id: str = ""
        self._phase = PipelinePhase.IDLE
        self._degradation = DegradationLevel.NOMINAL
        self._claims_before: int = 0

    def load_state(self) -> None:
        if self.state_file.exists():
            with open(self.state_file) as f:
                self._state = json.load(f)
            logger.info("Loaded NB-7 state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized NB-7 default state")

        self.registry.load()
        self._claims_before = load_claims_count(self.claims_file)
        self.circuit_breakers = CircuitBreakerRegistry.load(Path(self.state_file))

    def save_state(self) -> None:
        self._state["current_state"] = self._phase.value
        self._state["degradation_level"] = self._degradation.value
        self._state["last_updated"] = _now_iso()
        from .circuit_breaker import CBName
        self._state["circuit_breakers"] = {
            CBName.CB_NLM.value: self.circuit_breakers.nlm.to_dict(),
            CBName.CB_SOURCE.value: self.circuit_breakers.source.to_dict(),
            CBName.CB_INTEGRATION.value: self.circuit_breakers.integration.to_dict(),
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)
        self.registry.save()

    def _default_state(self) -> dict:
        return {
            "schema_version": 1,
            "notebook_id": NB7_NOTEBOOK_ID,
            "notebook_name": "NB-7: Editorial & Content Strategy",
            "current_state": "IDLE",
            "degradation_level": "NOMINAL",
            "last_updated": _now_iso(),
            "budget": {
                "daily_queries": 0,
                "weekly_calls": 0,
                "week_start": _now_wita().strftime("%Y-W%W"),
            },
            "circuit_breakers": {},
            "last_run": None,
            "cluster_history": [],
        }

    def run(self) -> dict:
        self._run_id = str(uuid.uuid4())
        start_time = time.time()
        summary: dict = {
            "run_id": self._run_id,
            "notebook": "NB-7: Editorial & Content Strategy",
            "notebook_id": NB7_NOTEBOOK_ID,
            "started_at": _now_iso(),
            "dry_run": self.dry_run,
            "phases": {},
        }

        try:
            self._phase = PipelinePhase.PREFLIGHT
            preflight_ok = self._preflight()
            summary["phases"]["preflight"] = {"passed": preflight_ok}
            if not preflight_ok:
                self._phase = PipelinePhase.HALTED
                summary["halted_at"] = "preflight"
                return summary

            cluster_key, cluster_name = self._today_cluster()
            summary["cluster"] = cluster_key
            summary["cluster_name"] = cluster_name

            self._phase = PipelinePhase.RUNNING_L1
            l1_result = self._run_query("L1", cluster_key)
            summary["phases"]["l1"] = l1_result

            if not l1_result.get("success"):
                self.circuit_breakers.nlm.record_failure()
                if self.circuit_breakers.nlm.is_open:
                    self._degradation = DegradationLevel.DEGRADED_L1
                    summary["halted_at"] = "l1_circuit_open"
                    self._phase = PipelinePhase.HALTED
                    return summary

            self._phase = PipelinePhase.ASSESSING
            l1_claims = l1_result.get("claims", [])
            summary["phases"]["assess"] = {"claims_extracted": len(l1_claims)}

            self._phase = PipelinePhase.RUNNING_L2
            l2_result = self._run_query(
                "L2",
                cluster_key,
                conversation_id=l1_result.get("conversation_id"),
            )
            summary["phases"]["l2"] = l2_result

            if not l2_result.get("success") and l1_result.get("success"):
                self.circuit_breakers.nlm.record_failure()
                self._degradation = DegradationLevel.DEGRADED_L1

            self._phase = PipelinePhase.CONSOLIDATING
            all_claims = l1_claims + l2_result.get("claims", [])
            consolidation = self._consolidate(all_claims, cluster_key, cluster_name, summary)
            summary["phases"]["consolidation"] = consolidation

            # Rolling synthesis: generate daily synthetic source (+ weekly/monthly roll-up if due)
            try:
                from .synthesis_roller import run_daily_synthesis  # noqa: PLC0415

                synthesis_summary = run_daily_synthesis(
                    nb_id=NB7_NOTEBOOK_ID,
                    nb_name="NB-7: Editorial & Content Strategy",
                    claims=all_claims,
                    dry_run=self.dry_run,
                )
                summary["phases"]["synthesis"] = synthesis_summary
                logger.info(
                    "NB-7 synthesis: daily=%s weekly=%s monthly=%s total_synth=%d",
                    synthesis_summary.get("daily", {}).get("status", "?"),
                    synthesis_summary.get("weekly", {}).get("status", "skipped") if synthesis_summary.get("weekly") else "skipped",
                    synthesis_summary.get("monthly", {}).get("status", "skipped") if synthesis_summary.get("monthly") else "skipped",
                    synthesis_summary.get("total_synthetic", 0),
                )
            except Exception as se:
                logger.warning("Synthesis roller failed (non-blocking): %s", se)
                summary["phases"]["synthesis"] = {"status": "error", "error": str(se)}

            self._phase = PipelinePhase.COMPLETE
            if l1_result.get("success"):
                self.circuit_breakers.nlm.record_success()

            queries_used = (1 if l1_result.get("success") else 0) + (
                1 if l2_result.get("success") else 0
            )
            self._increment_budget(queries_used)
            self._update_cluster_history(cluster_key)
            self._write_brief(summary)

        except Exception as e:
            logger.error("NB-7 pipeline error: %s", e, exc_info=True)
            self._phase = PipelinePhase.HALTED
            self._degradation = DegradationLevel.DEGRADED_L2
            summary["error"] = str(e)
        finally:
            elapsed = time.time() - start_time
            summary["completed_at"] = _now_iso()
            summary["elapsed_seconds"] = round(elapsed, 1)
            summary["degradation"] = self._degradation.value
            summary["claims_total"] = load_claims_count(self.claims_file)
            self.save_state()

        return summary

    def _preflight(self) -> bool:
        logger.info("=== NB-7 PRE-FLIGHT ===")
        checks = []

        now_wita = _now_wita()
        is_sunday = now_wita.weekday() == 6
        if is_sunday and not self.dry_run and not self.force:
            logger.info("Sunday — NB-7 pipeline skipped")
            return False
        checks.append(("not_sunday", not is_sunday or self.dry_run or self.force))

        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > 0)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past NB-7 deadline (03:00 WITA)")
        checks.append(("deadline", not past_deadline or self.dry_run or self.force))

        checks.append(("cb_nlm", not self.circuit_breakers.nlm.is_open))

        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        checks.append(("budget", weekly_calls < MAX_WEEKLY_CALLS))

        checks.append(("nlm_query_fn", self._nlm_query is not None or self.dry_run))
        checks.append(("notebook_id", bool(NB7_NOTEBOOK_ID)))

        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            logger.info("  %s %s", "✅" if ok else "❌", name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("NB-7 Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "SEO & GEO Content Strategy"))

    def _run_query(
        self, level: str, cluster_key: str, conversation_id: Optional[str] = None
    ) -> dict:
        query_map = L1_QUERIES if level == "L1" else L2_QUERIES
        query_text = query_map.get(cluster_key, "")

        if not query_text:
            logger.warning("No %s query template for cluster %s", level, cluster_key)
            return {"success": False, "error": "no_query_template"}

        logger.info("Running NB-7 %s query (cluster %s)...", level, cluster_key)

        if self.dry_run:
            logger.info("[DRY-RUN] Query: %s", query_text[:80])
            return {
                "success": True,
                "level": level,
                "cluster": cluster_key,
                "query": query_text,
                "response": "[DRY-RUN] Simulated response",
                "claims": [],
                "conversation_id": "dry-run-conv-id",
            }

        try:
            kwargs: dict = {"notebook_id": NB7_NOTEBOOK_ID, "query": query_text}
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            response = self._nlm_query(**kwargs)
            response_text = response if isinstance(response, str) else str(response)

            claims: list[ClaimRecord] = []
            try:
                claims = extract_claims_from_response(response_text, cluster_key, level)
                if claims:
                    append_claims_to_registry(claims, self.claims_file)
                    logger.info("Extracted %d claims from NB-7 %s", len(claims), level)
            except Exception as ce:
                logger.warning("Claim extraction failed: %s", ce)

            return {
                "success": True,
                "level": level,
                "cluster": cluster_key,
                "query": query_text[:100] + "...",
                "response_length": len(response_text),
                "claims": [c.__dict__ if hasattr(c, "__dict__") else c for c in claims],
            }

        except Exception as e:
            logger.error("NB-7 %s query failed: %s", level, e)
            return {"success": False, "level": level, "error": str(e)}

    def _consolidate(
        self,
        claims: list,
        cluster_key: str,
        cluster_name: str,
        summary: dict,
    ) -> dict:
        new_claims = len(claims)
        total_claims = load_claims_count(self.claims_file)
        source_count = self.registry.total_count

        try:
            from .pipeline import _dict_to_source

            source_objs = []
            for sid, sd in self.registry.sources.items():
                try:
                    source_objs.append(_dict_to_source(sid, sd))
                except Exception:
                    pass

            categories_seen = len({
                c.get("category", "") for c in claims if c.get("category")
            })
            nhs_input = NotebookHealthInput(
                active_count=self.registry.active_count,
                sources=source_objs,
                clusters_with_claims=min(1, len(claims)),
                categories_with_claims=categories_seen,
                duplicates_found_this_week=0,
                sources_evaluated_this_week=max(1, len(claims)),
            )
            nhs_result = compute_nhs(nhs_input)
            nhs = nhs_result.nhs_total
            nhs_label = classify_nhs(nhs).value
        except Exception:
            nhs = 0.0
            nhs_label = "UNKNOWN"

        logger.info(
            "NB-7 consolidation: cluster=%s claims=%d total=%d sources=%d NHS=%.3f (%s)",
            cluster_key, new_claims, total_claims, source_count, nhs, nhs_label,
        )

        return {
            "cluster": cluster_key,
            "cluster_name": cluster_name,
            "new_claims": new_claims,
            "total_claims": total_claims,
            "source_count": source_count,
            "nhs": nhs,
            "nhs_label": nhs_label,
        }

    def _write_brief(self, summary: dict) -> None:
        try:
            BRIEF_DIR.mkdir(parents=True, exist_ok=True)
            brief = {
                "generated_at": _now_iso(),
                "notebook": "NB-7: Editorial & Content Strategy",
                "notebook_id": NB7_NOTEBOOK_ID,
                "run_id": summary.get("run_id"),
                "cluster": summary.get("cluster"),
                "cluster_name": summary.get("cluster_name"),
                "status": "COMPLETE" if self._phase == PipelinePhase.COMPLETE else "PARTIAL",
                "phases": summary.get("phases", {}),
                "claims_total": summary.get("claims_total", 0),
                "degradation": summary.get("degradation", "NOMINAL"),
                "elapsed_seconds": summary.get("elapsed_seconds"),
            }
            with open(BRIEF_FILE, "w") as f:
                json.dump(brief, f, indent=2, ensure_ascii=False)
            logger.info("NB-7 brief written to %s", BRIEF_FILE)
        except Exception as e:
            logger.warning("Failed to write NB-7 brief: %s", e)

    def _increment_budget(self, queries_used: int) -> None:
        budget = self._state.setdefault("budget", {})
        current_week = _now_wita().strftime("%Y-W%W")
        if budget.get("week_start") != current_week:
            budget["weekly_calls"] = 0
            budget["week_start"] = current_week
        budget["daily_queries"] = queries_used
        budget["weekly_calls"] = budget.get("weekly_calls", 0) + queries_used

    def _update_cluster_history(self, cluster_key: str) -> None:
        history = self._state.setdefault("cluster_history", [])
        history.append({
            "date": _now_wita().strftime("%Y-%m-%d"),
            "cluster": cluster_key,
            "run_id": self._run_id,
        })
        if len(history) > 30:
            self._state["cluster_history"] = history[-30:]


# --- CLI Entry Point ---

def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NLM NB-7: Editorial & Content Strategy Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without NLM calls")
    parser.add_argument("--force", action="store_true", help="Force run (ignore Sunday/deadline check)")
    parser.add_argument("--state-file", default=STATE_FILE, help="Path to state file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    nlm_query_fn = None
    if not args.dry_run:
        try:
            from apps.evaluator.nlm_deep_research.nlm_bridge import nlm_query, check_nlm_available
            if check_nlm_available():
                nlm_query_fn = nlm_query
            else:
                logger.warning("nlm CLI not available — pipeline will fail preflight")
        except ImportError:
            logger.warning("nlm_bridge import failed")

    pipeline = NB7Pipeline(
        state_file=args.state_file,
        dry_run=args.dry_run,
        force=args.force,
        nlm_query_fn=nlm_query_fn,
    )
    pipeline.load_state()
    result = pipeline.run()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result.get("phases", {}).get("preflight", {}).get("passed") else 1)


if __name__ == "__main__":
    main()
