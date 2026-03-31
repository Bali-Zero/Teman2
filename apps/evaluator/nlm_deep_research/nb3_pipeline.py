"""NLM Deep Research Pipeline — NB-3: Company Setup Indonesia.

Daily execution: 02:45-03:00 WITA (Mon-Sat)
Schedule: 6-cluster rotation (Mon=A, Tue=B, Wed=C, Thu=D, Fri=E, Sat=F)
Output: ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb3.json

Run via:
    python -m apps.evaluator.nlm_deep_research.nb3_pipeline
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

# NB-3 configuration
NB3_NOTEBOOK_ID = "933509f9-1561-403d-bd44-4a7a67a36df2"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb3_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb3_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb3_sources.json"
BRIEF_DIR = Path.home() / ".agent" / "decisions" / "nlm_briefs"
BRIEF_FILE = BRIEF_DIR / "daily_intelligence_brief_nb3.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 3
PIPELINE_DEADLINE_MINUTE = 0

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40

# 6-cluster rotation (Mon=0 → Sat=5), Sun=6 → OFF
CLUSTER_ROTATION = {
    0: ("A", "PT PMA Setup & BKPM/OSS Licensing"),
    1: ("B", "Director / Commissioner Structure & Notarial Deed"),
    2: ("C", "KBLI 2025 Classification & Sector Restrictions"),
    3: ("D", "Virtual Office & Domicile Letter (SKDP)"),
    4: ("E", "Post-Establishment Compliance (BPJS, NPWP, NIB)"),
    5: ("F", "PT PMA Capital Requirements & Share Structure"),
}

# L1 query templates (Bahasa Indonesia primary, 60%)
L1_QUERIES: dict[str, str] = {
    "A": (
        "Prosedur terbaru pendirian PT PMA (Penanaman Modal Asing) di Indonesia 2025-2026. "
        "Langkah-langkah di OSS (Online Single Submission) RBA, persyaratan BKPM/DPMPTSP, "
        "dokumen yang diperlukan (akta notaris, anggaran dasar, KTP/paspor direktur), "
        "modal dasar minimum, dan timeline rata-rata dari pengajuan hingga NIB terbit. "
        "Peraturan BKPM terbaru 2025. Sumber: oss.go.id, BKPM, DPMPTSP."
    ),
    "B": (
        "Persyaratan direktur dan komisaris PT PMA di Indonesia 2026: bolehkah WNA menjadi "
        "direktur utama? Persyaratan KITAS/KITAP untuk direktur asing, minimal berapa direktur "
        "WNI diperlukan, kewajiban RPTKA untuk direksi asing, perbedaan direktur aktif vs "
        "komisaris pasif. Akta notaris dan perubahan akta jika ada pergantian direksi. "
        "Sumber: UU PT 40/2007, Kemenkumham, notaris terdaftar."
    ),
    "C": (
        "Panduan KBLI 2025 untuk perusahaan PMA di Bali: perubahan dari KBLI 2020, "
        "sektor-sektor yang tertutup untuk asing (Daftar Negatif Investasi terbaru), "
        "KBLI yang memerlukan izin khusus (TDUP, IUJK, dll), dan cara memilih KBLI yang tepat "
        "untuk bisnis digital nomad/remote worker services, konsultansi, dan jasa ekspat. "
        "Perpres 10/2021 DNI terbaru. Sumber: BKPM, oss.go.id, KBLI 2025 resmi BPS."
    ),
    "D": (
        "Domisili usaha dan virtual office untuk PT PMA di Bali 2026: apakah virtual office "
        "masih diterima sebagai domisili perusahaan PMA? Persyaratan SKDP (Surat Keterangan "
        "Domisili Perusahaan) dari kelurahan/kecamatan, perbedaan zona komersial vs residensial, "
        "masalah domisili di Bali untuk perusahaan non-Badung, dan syarat perjanjian sewa "
        "untuk alamat usaha. Sumber: DPMPTSP Bali/Badung, Kemendagri."
    ),
    "E": (
        "Kewajiban pasca-pendirian PT PMA di Indonesia 2026: pendaftaran BPJS Ketenagakerjaan "
        "dan BPJS Kesehatan untuk karyawan asing dan lokal, perolehan NPWP badan, aktivasi "
        "PKP (Pengusaha Kena Pajak) jika omzet >Rp 4,8 miliar, laporan LKPM triwulanan ke BKPM, "
        "dan kewajiban pembukuan/audit. Sanksi jika tidak patuh. Sumber: BPJS, DJP, BKPM."
    ),
    "F": (
        "Persyaratan modal PT PMA di Indonesia 2026: modal dasar minimum Rp 10 miliar "
        "untuk PMA (sesuai Perpres 10/2021), modal disetor minimum 25%, struktur saham "
        "untuk joint venture WNA-WNI, larangan nominee saham, perbedaan modal dasar vs "
        "modal ditempatkan vs modal disetor. Verifikasi modal oleh notaris. "
        "Sumber: BKPM, UU PT 40/2007, PP 29/2016."
    ),
}

# L2 query templates (English 30%, deeper analysis)
L2_QUERIES: dict[str, str] = {
    "A": (
        "Step-by-step PT PMA incorporation guide for foreigners in Bali 2026: "
        "Realistic timeline (OSS registration to NIB to bank account opening), "
        "notary selection criteria, common delays and how to avoid them, "
        "cost breakdown (notary fees, PNBP, government charges, service agent fees), "
        "and differences between incorporating directly vs using a local incorporation agent. "
        "Source: Hukumonline, SSEK Legal, Makes & Partners Indonesia."
    ),
    "B": (
        "Foreign director requirements for PT PMA in Indonesia 2026: "
        "Can a foreigner be sole director? KITAS TKA requirement for active foreign directors, "
        "minimum local director/commissioner ratio, RPTKA quota application process, "
        "practical implications of having a nominee local director (risks and alternatives), "
        "and notarial deed amendment process when changing directors. "
        "Source: UU PT 40/2007, Kemenkumham, SSEK Indonesia."
    ),
    "C": (
        "KBLI 2025 selection guide for digital nomad and expat service businesses in Bali: "
        "Best KBLI codes for business consulting (70209), immigration consulting (69200), "
        "online services (62010-62090), education/training (85499), property management (68200). "
        "Which codes are open vs restricted for foreign ownership post-Perpres 10/2021, "
        "and how the KBLI 2025 update changed eligibility for common PMA business types. "
        "Source: BKPM DNI list, KBLI 2025 BPS, Hukumonline."
    ),
    "D": (
        "Virtual office viability for PT PMA in Bali 2026: "
        "Which regencies (Badung, Denpasar, Gianyar) still accept virtual office addresses "
        "for NIB applications, minimum lease duration required for SKDP, "
        "risk of OSS rejection for virtual office addresses, "
        "and recommended virtual office providers in Seminyak/Canggu/Ubud area. "
        "Source: DPMPTSP Badung, Bali Chamber of Commerce, recent client case studies."
    ),
    "E": (
        "PT PMA post-incorporation compliance calendar for Bali 2026: "
        "Month-by-month obligations — BPJS Ketenagakerjaan registration (30 days), "
        "NPWP badan (30 days), LKPM quarterly report deadlines (April 15, July 15, Oct 15, Jan 15), "
        "annual financial statement audit requirement (if capital >Rp 50B or employees >300), "
        "SPT Tahunan Badan deadline (April 30), and dividend reporting to BKPM. "
        "Penalties for non-compliance. Source: BKPM, DJP, BPJS official guidelines."
    ),
    "F": (
        "PT PMA capital structure practical guide for Bali investors 2026: "
        "Rp 10 billion minimum — is this realistic for small businesses? "
        "Exceptions for micro/small PMA (UMK), paid-up capital verification by notary, "
        "foreign exchange inflow documentation (LKPM capital reporting), "
        "share structure options for 51% foreign / 49% local joint venture, "
        "and nominee shareholder risks post-Supreme Court ruling. "
        "Source: BKPM, OJK, Baker McKenzie Indonesia capital requirements guide."
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


class NB3Pipeline:
    """NLM pipeline for NB-3: Company Setup Indonesia.

    Architecture mirrors NB-4 pipeline exactly.
    Run slot: 02:45-03:00 WITA Mon-Sat.
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
            logger.info("Loaded NB-3 state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized NB-3 default state")

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
            "notebook_id": NB3_NOTEBOOK_ID,
            "notebook_name": "NB-3: Company Setup Indonesia",
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
            "notebook": "NB-3: Company Setup Indonesia",
            "notebook_id": NB3_NOTEBOOK_ID,
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
            logger.error("NB-3 pipeline error: %s", e, exc_info=True)
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
        logger.info("=== NB-3 PRE-FLIGHT ===")
        checks = []

        now_wita = _now_wita()
        is_sunday = now_wita.weekday() == 6
        if is_sunday and not self.dry_run and not self.force:
            logger.info("Sunday — NB-3 pipeline skipped")
            return False
        checks.append(("not_sunday", not is_sunday or self.dry_run or self.force))

        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > 0)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past NB-3 deadline (03:00 WITA)")
        checks.append(("deadline", not past_deadline or self.dry_run))

        checks.append(("cb_nlm", not self.circuit_breakers.nlm.is_open))

        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        checks.append(("budget", weekly_calls < MAX_WEEKLY_CALLS))

        checks.append(("nlm_query_fn", self._nlm_query is not None or self.dry_run))
        checks.append(("notebook_id", bool(NB3_NOTEBOOK_ID)))

        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            logger.info("  %s %s", "✅" if ok else "❌", name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("NB-3 Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "PT PMA Setup & BKPM/OSS Licensing"))

    def _run_query(
        self, level: str, cluster_key: str, conversation_id: Optional[str] = None
    ) -> dict:
        query_map = L1_QUERIES if level == "L1" else L2_QUERIES
        query_text = query_map.get(cluster_key, "")

        if not query_text:
            logger.warning("No %s query template for cluster %s", level, cluster_key)
            return {"success": False, "error": "no_query_template"}

        logger.info("Running NB-3 %s query (cluster %s)...", level, cluster_key)

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
            kwargs: dict = {"notebook_id": NB3_NOTEBOOK_ID, "query": query_text}
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            response = self._nlm_query(**kwargs)
            response_text = response if isinstance(response, str) else str(response)

            claims: list[ClaimRecord] = []
            try:
                claims = extract_claims_from_response(response_text, cluster_key, level)
                if claims:
                    append_claims_to_registry(claims, self.claims_file)
                    logger.info("Extracted %d claims from NB-3 %s", len(claims), level)
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
            logger.error("NB-3 %s query failed: %s", level, e)
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

            categories_seen = len({c.get("category", "") for c in claims if c.get("category")})
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
            "NB-3 consolidation: cluster=%s claims=%d total=%d sources=%d NHS=%.3f (%s)",
            cluster_key,
            new_claims,
            total_claims,
            source_count,
            nhs,
            nhs_label,
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
                "notebook": "NB-3: Company Setup Indonesia",
                "notebook_id": NB3_NOTEBOOK_ID,
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
            logger.info("NB-3 brief written to %s", BRIEF_FILE)
        except Exception as e:
            logger.warning("Failed to write NB-3 brief: %s", e)

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
        history.append(
            {
                "date": _now_wita().strftime("%Y-%m-%d"),
                "cluster": cluster_key,
                "run_id": self._run_id,
            }
        )
        if len(history) > 30:
            self._state["cluster_history"] = history[-30:]


# --- CLI Entry Point ---


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NLM NB-3: Company Setup Indonesia Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without NLM calls")
    parser.add_argument(
        "--force", action="store_true", help="Force run (ignore Sunday/deadline check)"
    )
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
            from apps.evaluator.nlm_deep_research.nlm_bridge import (
                check_nlm_available,
                nlm_query,
            )

            if check_nlm_available():
                nlm_query_fn = nlm_query
            else:
                logger.warning("nlm CLI not available — pipeline will fail preflight")
        except ImportError:
            logger.warning("nlm_bridge import failed")

    pipeline = NB3Pipeline(
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
