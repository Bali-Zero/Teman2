"""NLM Deep Research Pipeline — NB-4: Tax & Fiscal Indonesia.

Daily execution: 02:20-03:00 WITA (Mon-Sat)
Schedule: 7-cluster rotation (Mon=A, Tue=B, Wed=F, Thu=D, Fri=G, Sat=C+E)
Output: ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb4.json

Run via:
    python -m apps.evaluator.nlm_deep_research.nb4_pipeline
"""

import json
import logging
import os
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

# NB-4 configuration
NB4_NOTEBOOK_ID = "d4b2eedb-9863-4a1a-81ff-a11b0b45d853"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb4_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb4_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb4_sources.json"
BRIEF_DIR = Path.home() / ".agent" / "decisions" / "nlm_briefs"
BRIEF_FILE = BRIEF_DIR / "daily_intelligence_brief_nb4.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 3
PIPELINE_DEADLINE_MINUTE = 0

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40  # 2/day * 6 days + 4 buffer

# 7-cluster rotation (Mon=0 → Sat=5)
# Sun=6 → OFF
CLUSTER_ROTATION = {
    0: ("A", "Corporate Tax (PPh Badan)"),
    1: ("B", "Personal Income Tax (PPh OP)"),
    2: ("F", "Tax Admin & Coretax"),
    3: ("D", "Withholding Taxes (PPh 21/23/26)"),
    4: ("G", "International Tax (DTA/GloBE)"),
    5: ("CE", "VAT/PPN + Property Tax"),  # combined
}

# L1 query templates per cluster (Bahasa Indonesia primary, 60%)
L1_QUERIES: dict[str, str] = {
    "A": (
        "Peraturan terbaru tarif Pajak Penghasilan Badan (PPh Badan) untuk perusahaan PMA "
        "di Indonesia tahun 2025-2026. Termasuk tarif umum 22%, fasilitas pengurangan 50% "
        "untuk omzet di bawah Rp 50 miliar (Pasal 31E), tax holiday industri pionir "
        "(PMK terbaru), dan super deduction R&D 300%. Sumber resmi DJP, Kemenkeu, atau DDTC. "
        "Bukan iklan konsultan pajak."
    ),
    "B": (
        "Aturan terbaru Pajak Penghasilan Orang Pribadi (PPh OP) bagi ekspatriat dan "
        "warga negara asing di Indonesia 2025-2026. Aturan residensi pajak 183 hari, "
        "tarif progresif, sistem TER (PP 58/2023), NPWP berbasis NIK. "
        "Sumber: DJP, Kemenkeu, DDTC. Bukan panduan umum."
    ),
    "F": (
        "Update terbaru sistem Coretax DJP Indonesia tahun 2026. Masalah teknis, "
        "perbaikan sistem, panduan penggunaan resmi, perubahan prosedur SPT Tahunan "
        "dan eFaktur pasca-implementasi. SE DJP terbaru, PMK 81/2024 (KUP Coretax). "
        "Sumber: pajak.go.id, DDTC. Bukan tutorial pihak ketiga."
    ),
    "D": (
        "Peraturan terbaru pemotongan dan pemungutan pajak PPh Pasal 21 sistem TER 2026, "
        "PPh Pasal 23 jasa dan royalti, PPh Pasal 26 pembayaran ke luar negeri, "
        "PPh Pasal 4 ayat 2 final. Tarif terbaru, pengecualian, dan kewajiban pelaporan. "
        "PMK dan SE DJP 2025-2026. Sumber: perpajakan.ddtc.co.id, pajak.go.id."
    ),
    "G": (
        "Tax treaty Indonesia terbaru 2025-2026: perkembangan P3B (Persetujuan Penghindaran "
        "Pajak Berganda), implementasi Global Minimum Tax GloBE/Pilar 2 di Indonesia "
        "(PMK 136/2024), aturan substance requirements PMK 112/2025, CRS pelaporan aset luar "
        "negeri. Sumber: Kemenkeu, DDTC, Baker McKenzie Indonesia."
    ),
    "CE": (
        "Update terbaru PPN (Pajak Pertambahan Nilai) Indonesia 2026: tarif 12% barang mewah "
        "PPnBM, e-faktur sistem terbaru, ketentuan PKP baru. DAN: BPHTB tarif terbaru "
        "Bali/Kabupaten Badung untuk transaksi properti, PBB-P2 tarif daerah, "
        "capital gains properti ekspatriat. Sumber: DJP, Perda Bali/Badung terbaru, DDTC."
    ),
}

# L2 query templates per cluster (English 30%, deeper analysis)
L2_QUERIES: dict[str, str] = {
    "A": (
        "Analyze the practical tax incentive landscape for PT PMA companies in Indonesia 2026: "
        "tax holiday eligibility criteria (pioneer industry criteria per current PMK), "
        "investment allowance vs tax holiday trade-offs, special economic zone tax rates, "
        "and impact of UU Cipta Kerja (Job Creation Law) on corporate tax incentives. "
        "Focus on Bali-based investors. Source: PwC Indonesia tax summaries, DDTC analysis."
    ),
    "B": (
        "How does Indonesian personal income tax apply to foreign nationals working in Bali "
        "under KITAS/KITAP in 2026? Tax residency determination (183-day rule), "
        "domestic vs worldwide income taxation, tax treaty benefit claims (US, Australia, UK, "
        "EU countries), and exit tax implications. DDTC, EY, PwC expat tax guides Indonesia."
    ),
    "F": (
        "Coretax DJP Indonesia 2026: practical assessment of the new unified tax portal. "
        "What changed for PT PMA companies vs individual taxpayers? Registration migration "
        "from DJP Online to Coretax, common technical issues and workarounds, compliance "
        "deadlines changed post-PMK 81/2024. Source: DDTC News, DJP official circulars."
    ),
    "D": (
        "Withholding tax compliance guide for PT PMA companies in Indonesia 2026: "
        "PPh 21 TER monthly calculation for expat employees, PPh 23 on management fees "
        "and technical services, PPh 26 reduced rates under tax treaties, PPh 4(2) final "
        "on rental and construction. Practical monthly reporting schedule and Coretax e-filing. "
        "Source: PwC, DDTC withholding tax Indonesia."
    ),
    "G": (
        "Indonesia Global Minimum Tax implementation status 2026: PMK 136/2024 Pillar 2 "
        "GloBE rules, qualifying domestic minimum top-up tax (QDMTT), in-scope MNEs "
        "(turnover >EUR 750M), substance-based income exclusion (SBIE), "
        "transitional safe harbors. Impact on Bali-based holding structures. "
        "Source: Baker McKenzie, KPMG Indonesia GloBE tracker."
    ),
    "CE": (
        "VAT and property tax practical guide for foreign investors in Bali 2026: "
        "PPN on property transactions (commercial vs residential), when PKP registration "
        "is required for PT PMA, BPHTB calculation on land/building acquisition in Badung "
        "and Denpasar regencies, PBB-P2 annual rates, capital gains treatment on property "
        "sale by foreigners. Source: DDTC, ASEAN Briefing Bali property tax guide."
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


class NB4Pipeline:
    """NLM pipeline for NB-4: Tax & Fiscal Indonesia.

    Architecture mirrors NB-2 pipeline exactly.
    Run slot: 02:20-03:00 WITA Mon-Sat.
    """

    def __init__(
        self,
        state_file: str = STATE_FILE,
        claims_file: str = CLAIMS_FILE,
        registry_file: str = REGISTRY_FILE,
        nlm_query_fn=None,
        dry_run: bool = False,
        force: bool = False,
    ):
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
            logger.info("Loaded NB-4 state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized NB-4 default state")

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
            "notebook_id": NB4_NOTEBOOK_ID,
            "notebook_name": "NB-4: Tax & Fiscal Indonesia",
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
            "notebook": "NB-4: Tax & Fiscal Indonesia",
            "notebook_id": NB4_NOTEBOOK_ID,
            "started_at": _now_iso(),
            "dry_run": self.dry_run,
            "phases": {},
        }

        try:
            # Phase 1: Pre-flight
            self._phase = PipelinePhase.PREFLIGHT
            preflight_ok = self._preflight()
            summary["phases"]["preflight"] = {"passed": preflight_ok}
            if not preflight_ok:
                self._phase = PipelinePhase.HALTED
                summary["halted_at"] = "preflight"
                return summary

            # Determine today's cluster
            cluster_key, cluster_name = self._today_cluster()
            summary["cluster"] = cluster_key
            summary["cluster_name"] = cluster_name

            # Phase 2: L1 Query
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

            # Phase 3: Assessment
            self._phase = PipelinePhase.ASSESSING
            l1_claims = l1_result.get("claims", [])
            summary["phases"]["assess"] = {"claims_extracted": len(l1_claims)}

            # Phase 4: L2 Query
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

            # Phase 5: Consolidation
            self._phase = PipelinePhase.CONSOLIDATING
            all_claims = l1_claims + l2_result.get("claims", [])
            consolidation = self._consolidate(all_claims, cluster_key, cluster_name, summary)
            summary["phases"]["consolidation"] = consolidation

            # Phase 6: Complete
            self._phase = PipelinePhase.COMPLETE
            if l1_result.get("success"):
                self.circuit_breakers.nlm.record_success()

            queries_used = (1 if l1_result.get("success") else 0) + (
                1 if l2_result.get("success") else 0
            )
            self._increment_budget(queries_used)
            self._update_cluster_history(cluster_key)

            # Write brief
            self._write_brief(summary)

        except Exception as e:
            logger.error("NB-4 pipeline error: %s", e, exc_info=True)
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
        logger.info("=== NB-4 PRE-FLIGHT ===")
        checks = []

        # 1. Sunday OFF (Sat=5 is OK for combined C+E cluster)
        now_wita = _now_wita()
        is_sunday = now_wita.weekday() == 6
        if is_sunday and not self.dry_run and not self.force:
            logger.info("Sunday — NB-4 pipeline skipped")
            return False
        checks.append(("not_sunday", not is_sunday or self.dry_run or self.force))

        # 2. Deadline check (must complete before 03:00 WITA, intel scraper at 03:00)
        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > 0)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past NB-4 deadline (03:00 WITA — intel scraper window)")
        checks.append(("deadline", not past_deadline or self.dry_run))

        # 3. Circuit breakers
        checks.append(("cb_nlm", not self.circuit_breakers.nlm.is_open))

        # 4. Budget
        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        checks.append(("budget", weekly_calls < MAX_WEEKLY_CALLS))

        # 5. NLM query function
        checks.append(("nlm_query_fn", self._nlm_query is not None or self.dry_run))

        # 6. Notebook ID configured
        checks.append(("notebook_id", bool(NB4_NOTEBOOK_ID)))

        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            logger.info("  %s %s", "✅" if ok else "❌", name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("NB-4 Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "Corporate Tax (PPh Badan)"))

    def _run_query(
        self, level: str, cluster_key: str, conversation_id: Optional[str] = None
    ) -> dict:
        query_map = L1_QUERIES if level == "L1" else L2_QUERIES
        query_text = query_map.get(cluster_key, query_map.get(cluster_key.split("+")[0], ""))

        if not query_text:
            logger.warning("No %s query template for cluster %s", level, cluster_key)
            return {"success": False, "error": "no_query_template"}

        logger.info("Running NB-4 %s query (cluster %s)...", level, cluster_key)

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
            kwargs: dict = {
                "notebook_id": NB4_NOTEBOOK_ID,
                "query": query_text,
            }
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            response = self._nlm_query(**kwargs)
            response_text = response if isinstance(response, str) else str(response)

            # Extract claims
            claims: list[ClaimRecord] = []
            try:
                claims = extract_claims_from_response(response_text, cluster_key, level)
                if claims:
                    append_claims_to_registry(claims, self.claims_file)
                    logger.info("Extracted %d claims from NB-4 %s", len(claims), level)
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
            logger.error("NB-4 %s query failed: %s", level, e)
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

        # Compute NHS for health tracking
        # NotebookHealthInput requires: active_count, sources (List[Source]),
        # clusters_with_claims, categories_with_claims,
        # duplicates_found_this_week, sources_evaluated_this_week
        try:
            from .pipeline import _dict_to_source  # reuse NB-2 converter

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
                clusters_with_claims=min(1, len(claims)),  # approximate
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
            "NB-4 consolidation: cluster=%s claims=%d total=%d sources=%d NHS=%.3f (%s)",
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
        """Write daily intelligence brief to output dir."""
        try:
            BRIEF_DIR.mkdir(parents=True, exist_ok=True)
            brief = {
                "generated_at": _now_iso(),
                "notebook": "NB-4: Tax & Fiscal Indonesia",
                "notebook_id": NB4_NOTEBOOK_ID,
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
            logger.info("NB-4 brief written to %s", BRIEF_FILE)
        except Exception as e:
            logger.warning("Failed to write NB-4 brief: %s", e)

    def _increment_budget(self, queries_used: int) -> None:
        budget = self._state.setdefault("budget", {})
        # Reset weekly counter if new week
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
        # Keep last 30 entries
        if len(history) > 30:
            self._state["cluster_history"] = history[-30:]


# --- CLI Entry Point ---

def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NLM NB-4: Tax & Fiscal Indonesia Pipeline")
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

    pipeline = NB4Pipeline(
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
