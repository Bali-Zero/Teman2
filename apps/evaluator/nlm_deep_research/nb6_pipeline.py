"""NLM Deep Research Pipeline — NB-6: Operations & Compliance Indonesia.

Daily execution: 02:30-03:00 WITA (Mon-Sat)
Schedule: 6-cluster rotation (Mon=A, Tue=B, Wed=C, Thu=D, Fri=E, Sat=F)
Output: ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb6.json

Run via:
    python -m apps.evaluator.nlm_deep_research.nb6_pipeline
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

# NB-6 configuration
NB6_NOTEBOOK_ID = "85207af3-352f-4554-8d2a-18f42cc541ba"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb6_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb6_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb6_sources.json"
BRIEF_DIR = Path.home() / ".agent" / "decisions" / "nlm_briefs"
BRIEF_FILE = BRIEF_DIR / "daily_intelligence_brief_nb6.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 3
PIPELINE_DEADLINE_MINUTE = 0

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40

# 6-cluster rotation (Mon=0 → Sat=5), Sun=6 → OFF
CLUSTER_ROTATION = {
    0: ("A", "PT PMA Setup & Capital Requirements"),
    1: ("B", "RPTKA/IMTA & Foreign Worker Compliance"),
    2: ("C", "OSS-RBA Licensing & KBLI 2025"),
    3: ("D", "BPJS & Payroll Compliance"),
    4: ("E", "Corporate Governance & AHU Online"),
    5: ("F", "UU PDP & Data Protection Compliance"),
}

# L1 query templates (Bahasa Indonesia primary ~60%)
L1_QUERIES: dict[str, str] = {
    "A": (
        "Persyaratan terbaru pendirian PT PMA di Indonesia tahun 2025-2026. "
        "Modal minimum BKPM Reg. 5/2025 (IDR 2.5 miliar vs IDR 10 miliar per KBLI), "
        "rencana investasi, lock-up period modal, dan deadline realisasi. "
        "Perbedaan antara modal disetor dan total rencana investasi. "
        "Sumber: BKPM, OSS, Hukumonline. Bukan panduan umum konsultan."
    ),
    "B": (
        "Prosedur terbaru RPTKA (Rencana Penggunaan Tenaga Kerja Asing) dan IMTA tahun 2026. "
        "Sinkronisasi 'Satu Data Ketenagakerjaan' antara Kemnaker, DG Imigrasi, DG Pajak. "
        "Persyaratan pendamping TKA, knowledge transfer plan, alur digital SIAPkerja. "
        "Threshold KITAS investor (IDR 10 miliar vs IDR 15 miliar untuk KITAP). "
        "Sumber: Kemnaker, kemnaker.go.id, SIAPkerja."
    ),
    "C": (
        "Update terbaru sistem OSS-RBA dan KBLI 2025 untuk PT PMA di Indonesia. "
        "Deadline migrasi KBLI 2025 tanggal 18 Juni 2026. Peraturan Pemerintah 28/2025 "
        "menggantikan PP 5/2021 — perubahan kategori risiko, PB-UMKU sektoral. "
        "Lisensi sekunder untuk sektor properti (68111), hospitality (55900), konstruksi (41011). "
        "Sumber: oss.go.id, BKPM, Kemenko Perekonomian."
    ),
    "D": (
        "Kewajiban BPJS terbaru tahun 2026 untuk perusahaan PMA dengan karyawan lokal dan ekspatriat. "
        "Aliquota BPJS Kesehatan (4%+1%), BPJS Ketenagakerjaan (JHT 3.7%+2%, JP 2%+1%, JKK, JKM). "
        "Cap gaji terbaru untuk JP (IDR 11.086.300), perubahan usia pensiun JP 59→65 tahun. "
        "Deadline kontribusi Desember (dipercepat ke 31 Desember). "
        "Sumber: BPJS Kesehatan resmi, BPJS Ketenagakerjaan, Kemnaker."
    ),
    "E": (
        "Tata kelola perusahaan PT PMA via AHU Online tahun 2026. "
        "Kewajiban laporan tahunan SABH, batas waktu 30 hari setelah notarisasi RUPS. "
        "RUPS wajib dalam 6 bulan setelah tutup buku. Akibat keterlambatan: blokir AHU → "
        "tidak bisa ubah direksi, pemegang saham, modal. "
        "Verifikasi UBO (Ultimate Beneficial Owner) setiap tahun per FATF requirements. "
        "Sumber: AHU Online, Kemenkumham, MOLHR Reg. 49/2025."
    ),
    "F": (
        "Implementasi UU PDP (UU No. 27/2022) untuk perusahaan konsultasi berbasis AI di Indonesia. "
        "Putusan MK No. 151/PUU-XXII/2024: test DPO dari kumulatif menjadi alternatif. "
        "Kewajiban notifikasi pelanggaran 72 jam (otoritas + subjek data). "
        "DPIA wajib untuk pemrosesan profiling otomatis. "
        "Sanksi: 2% dari omzet tahunan + IDR 60 miliar. "
        "Sumber: Kominfo, OJK, hukumonline.com, DDTC."
    ),
}

# L2 query templates (English ~30%, deeper analysis)
L2_QUERIES: dict[str, str] = {
    "A": (
        "Practical analysis of PT PMA capital requirements under BKPM Regulation 5/2025: "
        "the dual-track system (IDR 2.5B paid-up vs IDR 10B per KBLI investment plan), "
        "12-month capital lock-up implications, realization timeline enforcement, "
        "and the 'honeymoon period' trap where LKPM shows no progress toward IDR 10B. "
        "Consequences: AHU system block, NIB suspension, inability to renew RPTKA. "
        "Source: BKPM official, Seven Stones Indonesia, HBT Law 2025-2026."
    ),
    "B": (
        "How does the 'Satu Data Ketenagakerjaan' integration affect PT PMA compliance in 2026? "
        "Explain the invisible audit mechanism: automatic cross-check of RPTKA data against "
        "KITAS records and PPh 21 declarations. What triggers an automatic audit flag? "
        "OJK Reg. 1/2026 requiring 2 Indonesian counterparts per TKA in executive roles. "
        "Knowledge transfer documentation requirements and practical SOP for Bali-based companies. "
        "Source: Kemnaker, OJK Indonesia, Permitindo, ASEAN Briefing."
    ),
    "C": (
        "Deep analysis of GR 28/2025 (PP 28/2025) replacing GR 5/2021 for OSS-RBA in Indonesia. "
        "What changed for PT PMA in KBLI risk classification, PB-UMKU secondary licenses, "
        "and sector-specific compliance requirements? "
        "KBLI 2025 migration deadline June 18, 2026: what happens to NIB if migration missed? "
        "Practical checklist for PT PMA with multiple KBLI codes in Bali. "
        "Source: oss.go.id, PwC Legal Alert GR 28/2025, ASEAN Briefing OSS guide."
    ),
    "D": (
        "BPJS compliance practical guide for PT PMA companies with mixed Indonesian and expat workforce 2026. "
        "Expat BPJS enrollment requirements (mandatory for KITAS holders), "
        "salary cap changes for JP program, December deadline acceleration, "
        "integration with SIPP and EDABU portals for electronic reporting. "
        "Penalties for late or incorrect reporting. "
        "Source: BPJS official portals, Acclime Indonesia, PwC Indonesia HR guide."
    ),
    "E": (
        "PT PMA corporate governance compliance calendar 2026: "
        "AGMS timing (within 6 months of fiscal year close), AHU Online SABH annual report "
        "(30-day window after notarized minutes), UBO verification annual cycle, "
        "NIB renewal triggers and conditions. "
        "What is the AHU system block and how to recover from it? "
        "Practical timeline for Bali-based PT PMA with fiscal year ending December 31. "
        "Source: Kemenkumham AHU Online, Hukumonline, Baker McKenzie Indonesia."
    ),
    "F": (
        "UU PDP implementation for AI-first consulting companies in Indonesia 2026: "
        "DPO obligation under Constitutional Court ruling (alternative not cumulative test), "
        "72-hour breach notification workflow for companies using Fly.io/cloud infrastructure, "
        "DPIA requirements for automated client profiling in CRM systems, "
        "right to object against algorithmic decisions (human-on-the-loop requirement), "
        "IP ownership in custom AI model development (MOCDA Circular 9/2023). "
        "Source: Kominfo, Baker McKenzie PDP guide, OneTrust Indonesia."
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


class NB6Pipeline:
    """NLM pipeline for NB-6: Operations & Compliance Indonesia.

    Architecture mirrors NB-4 pipeline exactly.
    Run slot: 02:30-03:00 WITA Mon-Sat.
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
            logger.info("Loaded NB-6 state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized NB-6 default state")

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
            "notebook_id": NB6_NOTEBOOK_ID,
            "notebook_name": "NB-6: Operations & Compliance Indonesia",
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
            "notebook": "NB-6: Operations & Compliance Indonesia",
            "notebook_id": NB6_NOTEBOOK_ID,
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
                    nb_id=NB6_NOTEBOOK_ID,
                    nb_name="NB-6: Operations & Compliance Indonesia",
                    claims=all_claims,
                    dry_run=self.dry_run,
                )
                summary["phases"]["synthesis"] = synthesis_summary
                logger.info(
                    "NB-6 synthesis: daily=%s weekly=%s monthly=%s total_synth=%d",
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
            logger.error("NB-6 pipeline error: %s", e, exc_info=True)
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
        logger.info("=== NB-6 PRE-FLIGHT ===")
        checks = []

        now_wita = _now_wita()
        is_sunday = now_wita.weekday() == 6
        if is_sunday and not self.dry_run and not self.force:
            logger.info("Sunday — NB-6 pipeline skipped")
            return False
        checks.append(("not_sunday", not is_sunday or self.dry_run or self.force))

        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > 0)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past NB-6 deadline (03:00 WITA)")
        checks.append(("deadline", not past_deadline or self.dry_run or self.force))

        checks.append(("cb_nlm", not self.circuit_breakers.nlm.is_open))

        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        checks.append(("budget", weekly_calls < MAX_WEEKLY_CALLS))

        checks.append(("nlm_query_fn", self._nlm_query is not None or self.dry_run))
        checks.append(("notebook_id", bool(NB6_NOTEBOOK_ID)))

        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            logger.info("  %s %s", "✅" if ok else "❌", name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("NB-6 Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "PT PMA Setup & Capital Requirements"))

    def _run_query(
        self, level: str, cluster_key: str, conversation_id: Optional[str] = None
    ) -> dict:
        query_map = L1_QUERIES if level == "L1" else L2_QUERIES
        query_text = query_map.get(cluster_key, "")

        if not query_text:
            logger.warning("No %s query template for cluster %s", level, cluster_key)
            return {"success": False, "error": "no_query_template"}

        logger.info("Running NB-6 %s query (cluster %s)...", level, cluster_key)

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
                "notebook_id": NB6_NOTEBOOK_ID,
                "query": query_text,
            }
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            response = self._nlm_query(**kwargs)
            response_text = response if isinstance(response, str) else str(response)

            claims: list[ClaimRecord] = []
            try:
                claims = extract_claims_from_response(response_text, cluster_key, level)
                if claims:
                    append_claims_to_registry(claims, self.claims_file)
                    logger.info("Extracted %d claims from NB-6 %s", len(claims), level)
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
            logger.error("NB-6 %s query failed: %s", level, e)
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
            nhs_input = NotebookHealthInput(
                source_count=source_count,
                active_count=self.registry.active_count,
                verified_claims_count=total_claims,
                target_sources=120,
            )
            nhs = compute_nhs(nhs_input)
            nhs_label = classify_nhs(nhs)
        except Exception:
            nhs = 0.0
            nhs_label = "UNKNOWN"

        logger.info(
            "NB-6 consolidation: cluster=%s claims=%d total=%d sources=%d NHS=%.3f (%s)",
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
                "notebook": "NB-6: Operations & Compliance Indonesia",
                "notebook_id": NB6_NOTEBOOK_ID,
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
            logger.info("NB-6 brief written to %s", BRIEF_FILE)
        except Exception as e:
            logger.warning("Failed to write NB-6 brief: %s", e)

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

def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NLM NB-6: Operations & Compliance Indonesia")
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

    pipeline = NB6Pipeline(
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
