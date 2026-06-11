"""NLM Deep Research Pipeline — NB-5: Property & Real Estate Indonesia.

Daily execution: 02:35-03:00 WITA (Mon-Sat)
Schedule: 6-cluster rotation (Mon=A, Tue=B, Wed=C, Thu=D, Fri=E, Sat=F)
Output: ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb5.json

Run via:
    python -m apps.evaluator.nlm_deep_research.nb5_pipeline
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
from .source_snapshot import take_snapshot
from .source_management import (
    compute_nhs,
    classify_nhs,
    NotebookHealthInput,
)

logger = logging.getLogger(__name__)

# NB-5 configuration
NB5_NOTEBOOK_ID = "d9438180-5e63-4e2a-a473-6061101f6a8d"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb5_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb5_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb5_sources.json"
BRIEF_DIR = Path.home() / ".agent" / "decisions" / "nlm_briefs"
BRIEF_FILE = BRIEF_DIR / "daily_intelligence_brief_nb5.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 3
PIPELINE_DEADLINE_MINUTE = 0

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40

# 6-cluster rotation (Mon=0 → Sat=5), Sun=6 → OFF
CLUSTER_ROTATION = {
    0: ("A", "Foreign Ownership (PP 18/2021 + PP 28/2025)"),
    1: ("B", "Leasehold / Hak Sewa & HGU for Foreigners"),
    2: ("C", "Property Taxes (BPHTB, PBB-P2, PPh Final)"),
    3: ("D", "Strata Title / Apartemen & PPJB Process"),
    4: ("E", "Due Diligence & BPN Certification"),
    5: ("F", "Property Financing & KPR for Foreigners"),
}

# L1 query templates (Bahasa Indonesia primary, 60%)
L1_QUERIES: dict[str, str] = {
    "A": (
        "Peraturan terbaru kepemilikan properti oleh orang asing (WNA) di Indonesia 2025-2026. "
        "PP 18/2021 tentang Hak Pengelolaan, Hak Atas Tanah, Satuan Rumah Susun, dan "
        "PP 28/2025 tentang hak pakai dan rumah tinggal WNA. Batasan luas tanah, nilai minimum, "
        "syarat KITAS/KITAP, dan lokasi yang diizinkan. Sumber: ATR/BPN, Kemenkumham, BKPM."
    ),
    "B": (
        "Mekanisme sewa properti jangka panjang (leasehold) bagi WNA di Bali 2025-2026. "
        "Perbedaan Hak Sewa vs Hak Guna Bangunan (HGB) vs Hak Pakai. Durasi maksimum, "
        "perpanjangan, notaris persyaratan, dan risiko nominee arrangement. "
        "Putusan MA terbaru tentang sengketa properti WNA. Sumber: PPAT/ATR BPN, Hukumonline."
    ),
    "C": (
        "Pajak properti terbaru untuk transaksi di Bali 2025-2026: BPHTB (Bea Perolehan Hak "
        "Atas Tanah dan Bangunan) tarif Kabupaten Badung dan Kota Denpasar, PBB-P2 tarif daerah, "
        "PPh Final penjualan properti (tarif 2.5% PP terbaru), dan Bea Materai. "
        "Perda Badung dan Denpasar terbaru. Sumber: DJPK Kemenkeu, Dispenda Bali."
    ),
    "D": (
        "Prosedur pembelian apartemen/kondotel oleh WNA di Indonesia 2026: Strata title "
        "(SHMSRS), PPJB (Perjanjian Pengikatan Jual Beli) syarat dan risiko, AJB (Akta Jual Beli) "
        "di hadapan PPAT, dan batasan kepemilikan asing di rumah susun komersial. "
        "Peraturan terbaru Kemenpera. Sumber: BPN, PPAT Bali, Hukumonline."
    ),
    "E": (
        "Due diligence properti di Bali untuk investor asing 2026: verifikasi sertifikat HGB/SHM "
        "di BPN, cek APHT (Akta Pembebanan Hak Tanggungan) dan beban lain, validasi IMB/PBG "
        "(Persetujuan Bangunan Gedung), sengketa tanah adat (tanah desa adat Bali), "
        "dan zona rawan gempa. Sumber: ATR/BPN, DPMPTSP Bali, Bappeda Bali."
    ),
    "F": (
        "Pembiayaan properti untuk WNA di Indonesia 2026: apakah WNA bisa mengajukan KPR "
        "di bank Indonesia (BCA, Mandiri, BRI), persyaratan KITAS/KITAP untuk KPR, "
        "alternatif pembiayaan (developer financing, bridging loan), dan regulasi OJK tentang "
        "kredit properti untuk non-residen. Sumber: OJK, bank umum Indonesia, LPS."
    ),
}

# L2 query templates (English 30%, deeper analysis)
L2_QUERIES: dict[str, str] = {
    "A": (
        "Analyze PP 28/2025 (Indonesia's new foreign property ownership regulation): "
        "What changed from PP 18/2021? New minimum property values, eligible property types, "
        "required visa status (KITAS vs KITAP), provincial quotas or restrictions, "
        "and enforcement mechanisms. Impact on Bali villa market. "
        "Source: ATR/BPN official gazette, CBRE Indonesia, JLL Bali property report 2025."
    ),
    "B": (
        "Practical guide to long-term leasehold structures for foreigners in Bali 2026: "
        "25+25+30 year lease structures, nominee PT PMA as alternative, "
        "risks of lease agreements not registered at BPN, "
        "recent Supreme Court rulings on nominee arrangement invalidation, "
        "and legal alternatives post-PP 18/2021. Source: SSEK Legal, Makes & Partners, "
        "Indonesia Property Guide for Foreigners."
    ),
    "C": (
        "Complete tax calculation for a foreign buyer acquiring a villa in Badung regency Bali 2026: "
        "BPHTB rate and calculation (5% of (NJOP - NJOPTKP)), PPh Final seller side (2.5% of gross), "
        "notary/PPAT fees, property registration costs at BPN, annual PBB-P2. "
        "Total transaction cost as percentage of property value. "
        "Source: Kemenkeu DJPK, Badung Perda, EY Indonesia."
    ),
    "D": (
        "Foreign investor guide to buying condotel/strata title in Bali 2026: "
        "Maximum foreign ownership percentage in a building (satuan rumah susun asing), "
        "condotel vs private use strata title, developer trustworthiness checks (REI membership, "
        "SLF certificate), PPJB clauses to review, and common developer default scenarios. "
        "Source: REI Bali, PPAT Indonesia, Hukumonline."
    ),
    "E": (
        "Red flags and due diligence checklist for property acquisition in Bali 2026: "
        "How to verify land certificate authenticity via BPN online, "
        "identifying tanah adat (customary land) that cannot be sold to foreigners, "
        "checking building permit (PBG/IMB) validity, zone compliance (green belt, coastal setback), "
        "and title insurance availability in Indonesia. "
        "Source: ATR/BPN, Bali DPMPTSP, PPAT Association."
    ),
    "F": (
        "Property financing options for foreign nationals in Bali 2026: "
        "Which Indonesian banks offer mortgages to KITAS holders (BCA, Mandiri, BRI conditions), "
        "typical LTV ratios and interest rates for foreigners, "
        "alternative structures (offshore loan, developer installment, joint venture), "
        "OJK POJK regulations on foreign borrower eligibility, "
        "and currency risk for IDR-denominated mortgages. "
        "Source: OJK, bank official websites, Jakarta Globe property finance guide."
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


class NB5Pipeline:
    """NLM pipeline for NB-5: Property & Real Estate Indonesia.

    Architecture mirrors NB-4 pipeline exactly.
    Run slot: 02:35-03:00 WITA Mon-Sat.
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
            logger.info("Loaded NB-5 state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized NB-5 default state")

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
            "notebook_id": NB5_NOTEBOOK_ID,
            "notebook_name": "NB-5: Property & Real Estate Indonesia",
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
            "notebook": "NB-5: Property & Real Estate Indonesia",
            "notebook_id": NB5_NOTEBOOK_ID,
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
            # ARCH-8: snapshot before any mutation
            if not self.dry_run:
                try:
                    snap = take_snapshot(NB5_NOTEBOOK_ID, "nb5_property")
                    logger.info("ARCH-8 snapshot: %s", snap.name)
                except Exception as snap_err:
                    logger.warning("ARCH-8 snapshot failed (continuing): %s", snap_err)


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
                    nb_id=NB5_NOTEBOOK_ID,
                    nb_name="NB-5: Property & Real Estate Indonesia",
                    claims=all_claims,
                    dry_run=self.dry_run,
                )
                summary["phases"]["synthesis"] = synthesis_summary
                logger.info(
                    "NB-5 synthesis: daily=%s weekly=%s monthly=%s total_synth=%d",
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
            logger.error("NB-5 pipeline error: %s", e, exc_info=True)
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
        logger.info("=== NB-5 PRE-FLIGHT ===")
        checks = []

        now_wita = _now_wita()
        is_sunday = now_wita.weekday() == 6
        if is_sunday and not self.dry_run and not self.force:
            logger.info("Sunday — NB-5 pipeline skipped")
            return False
        checks.append(("not_sunday", not is_sunday or self.dry_run or self.force))

        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > 0)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past NB-5 deadline (03:00 WITA)")
        checks.append(("deadline", not past_deadline or self.dry_run or self.force))

        checks.append(("cb_nlm", not self.circuit_breakers.nlm.is_open))

        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        checks.append(("budget", weekly_calls < MAX_WEEKLY_CALLS))

        checks.append(("nlm_query_fn", self._nlm_query is not None or self.dry_run))
        checks.append(("notebook_id", bool(NB5_NOTEBOOK_ID)))

        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            logger.info("  %s %s", "✅" if ok else "❌", name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("NB-5 Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "Foreign Ownership"))

    def _run_query(
        self, level: str, cluster_key: str, conversation_id: Optional[str] = None
    ) -> dict:
        query_map = L1_QUERIES if level == "L1" else L2_QUERIES
        query_text = query_map.get(cluster_key, "")

        if not query_text:
            logger.warning("No %s query template for cluster %s", level, cluster_key)
            return {"success": False, "error": "no_query_template"}

        logger.info("Running NB-5 %s query (cluster %s)...", level, cluster_key)

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
            kwargs: dict = {"notebook_id": NB5_NOTEBOOK_ID, "query": query_text}
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            response = self._nlm_query(**kwargs)
            response_text = response if isinstance(response, str) else str(response)

            claims: list[ClaimRecord] = []
            try:
                claims = extract_claims_from_response(response_text, cluster_key, level)
                if claims:
                    append_claims_to_registry(claims, self.claims_file)
                    logger.info("Extracted %d claims from NB-5 %s", len(claims), level)
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
            logger.error("NB-5 %s query failed: %s", level, e)
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
            "NB-5 consolidation: cluster=%s claims=%d total=%d sources=%d NHS=%.3f (%s)",
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
                "notebook": "NB-5: Property & Real Estate Indonesia",
                "notebook_id": NB5_NOTEBOOK_ID,
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
            logger.info("NB-5 brief written to %s", BRIEF_FILE)
        except Exception as e:
            logger.warning("Failed to write NB-5 brief: %s", e)

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

    parser = argparse.ArgumentParser(description="NLM NB-5: Property & Real Estate Indonesia Pipeline")
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

    pipeline = NB5Pipeline(
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
