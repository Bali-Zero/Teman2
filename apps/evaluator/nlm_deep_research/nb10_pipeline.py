"""NLM Deep Research Pipeline — NB-10: Team Guides.

Daily execution: 02:50-03:00 WITA (Mon-Sat)
Schedule: 6-cluster rotation (Mon=A, Tue=B, Wed=C, Thu=D, Fri=E, Sat=F)
Output: ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb10.json

Run via:
    python -m apps.evaluator.nlm_deep_research.nb10_pipeline
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

# NB-10 configuration
NB10_NOTEBOOK_ID = "f0307c2c-9220-4160-93c8-f4a6ef4a3b65"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb10_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb10_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb10_sources.json"
BRIEF_DIR = Path.home() / ".agent" / "decisions" / "nlm_briefs"
BRIEF_FILE = BRIEF_DIR / "daily_intelligence_brief_nb10.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 3
PIPELINE_DEADLINE_MINUTE = 0

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40

# 6-cluster rotation (Mon=0 → Sat=5), Sun=6 → OFF
CLUSTER_ROTATION = {
    0: ("A", "Hukum Ketenagakerjaan & PKWT/PKWTT"),
    1: ("B", "Payroll Compliance: PPh 21 TER + BPJS Mixed Team"),
    2: ("C", "UU PDP & Data Protection for AI Tools"),
    3: ("D", "Remote & Async Work: Indonesian Context"),
    4: ("E", "EOR & Hiring Foreigners in Bali"),
    5: ("F", "AI Tools, Legal Liability & IP Ownership"),
}

# L1 query templates (Bahasa Indonesia primary ~60%)
L1_QUERIES: dict[str, str] = {
    "A": (
        "Aturan terbaru hukum ketenagakerjaan Indonesia untuk perusahaan konsultasi kecil tahun 2026. "
        "PKWT (kontrak kerja waktu tertentu) vs PKWTT (tetap): cap total 5 tahun termasuk perpanjangan. "
        "PKWT tidak tertulis = otomatis PKWTT. PKWT tidak boleh ada masa percobaan. "
        "THR (Tunjangan Hari Raya): 1 bulan gaji untuk karyawan ≥12 bulan, pro-rata <12 bulan. "
        "Cuti tahunan: 12 hari setelah 1 tahun. Cuti melahirkan: 3 bulan. "
        "Pengecualian overtime untuk 'thinker/planner/controller' (Art. 78 UU 13/2003). "
        "Sumber: Kemnaker, Hukumonline, JAMSOSTEK, UU Cipta Kerja."
    ),
    "B": (
        "Panduan payroll compliance untuk tim campuran (karyawan lokal + ekspatriat) di Indonesia 2026. "
        "PPh 21 sistem TER (PP 58/2023): tarif bulanan berdasarkan golongan. "
        "BPJS Kesehatan wajib untuk pemegang KITAS (4%+1% capped IDR 12 juta). "
        "BPJS Ketenagakerjaan untuk TKA: JHT 3.7%+2%, JP 2%+1%, JKK, JKM. "
        "Pelaporan: Sistem TER via Coretax/e-Bupot, BPJS via EDABU + SIPP. "
        "Deadline kontribusi Desember (31 Desember, tidak ada grace period ke Januari). "
        "Sumber: DJP, Kemnaker, BPJS resmi."
    ),
    "C": (
        "Implementasi UU PDP (UU No. 27/2022) untuk perusahaan yang menggunakan AI tools tahun 2026. "
        "Klasifikasi data: data umum (NIK, nama) vs data spesifik/sensitif (biometri, kesehatan, finansial). "
        "DPIA wajib untuk profiling otomatis karyawan atau klien. "
        "Hak subjek data menolak keputusan algoritmik (human-on-the-loop wajib). "
        "Breach notification: 72 jam ke otoritas DAN ke subjek data. "
        "Test DPO alternatif (MK No. 151/PUU-XXII/2024): cukup 1 kondisi dari 3. "
        "Sanksi: 2% omzet + IDR 60 miliar + potensi pencabutan izin. "
        "Sumber: Kominfo, OJK, Baker McKenzie PDP Indonesia."
    ),
    "D": (
        "Panduan kerja remote dan komunikasi async untuk tim Indonesia tahun 2025-2026. "
        "Friction budaya: 'iya' dalam konteks profesional Indonesia sering berarti 'mengerti' bukan 'setuju'. "
        "Response anxiety: tekanan hierarki mendorong respons segera ke atasan walau di luar jam kerja. "
        "Nilai Kekeluargaan dan Gotong Royong dalam konteks kerja digital. "
        "SLA komunikasi async: standar respons, dokumentasi keputusan, meeting minimal. "
        "Tools populer di perusahaan Indonesia: Slack, WhatsApp Business, Notion, Jira. "
        "Sumber: Gadjian Indonesia, SHRM Asia, HR magazine Indonesia."
    ),
    "E": (
        "Employer of Record (EOR) dan rekrutmen TKA di Bali Indonesia tahun 2026. "
        "Model EOR vs mendirikan PT PMA sendiri: perbandingan biaya, risiko, waktu setup. "
        "Persyaratan RPTKA untuk TKA: pendamping lokal, knowledge transfer plan. "
        "OJK Reg. 1/2026: 2 counterpart Indonesian untuk setiap TKA di peran eksekutif. "
        "KITAS Working vs KITAS Investor: threshold dan proses. "
        "Sumber: Remote.com Indonesia, Deel Indonesia, Acclime EOR guide."
    ),
    "F": (
        "Kerangka hukum penggunaan AI tools di tempat kerja Indonesia tahun 2025-2026. "
        "MOCDA Circular 9/2023 AI Ethics: transparansi, akuntabilitas, anti-bias. "
        "Kepemilikan IP output AI: siapa pemilik konten yang dihasilkan AI dalam kontrak kerja? "
        "Data Processing Agreement untuk vendor AI (ChatGPT, Claude, Gemini) per UU PDP. "
        "Perlindungan data klien saat menggunakan AI tools: zero-data-retention agreements. "
        "Tanggung jawab hukum atas kesalahan AI dalam konteks consulting (AI legal liability). "
        "Sumber: MOCDA, Kominfo, Baker McKenzie AI Indonesia, OneTrust."
    ),
}

# L2 query templates (English ~30%)
L2_QUERIES: dict[str, str] = {
    "A": (
        "Indonesian employment law practical guide for small AI-first consulting firm in Bali 2026: "
        "PKWT contract drafting best practices (must be in writing, registered at Kemnaker, "
        "specific task/time bounded), conversion triggers to PKWTT, "
        "'thinker/planner/controller' overtime exemption for consultant roles, "
        "THR calculation for part-time and pro-rated employees, "
        "severance pay (pesangon) formula under Omnibus Law GR 35/2021. "
        "Source: Kemnaker, L&E Global Indonesia, Hukumonline labor law guide 2026."
    ),
    "B": (
        "Practical payroll guide for PT PMA with mixed Indonesian and expat staff 2026: "
        "PPh 21 TER monthly calculation for expat employees (using TER table Category C), "
        "annual reconciliation SPT 1721 in Coretax, "
        "BPJS enrollment for new expat employees (KITAS registration timeline), "
        "December payroll deadline acceleration (contributions by Dec 31, not Jan 10), "
        "e-Bupot 21/26 filing in Coretax — step-by-step guide. "
        "Source: DJP Coretax, DDTC payroll guide, BPJS official 2026."
    ),
    "C": (
        "UU PDP compliance checklist for AI-first consulting companies using cloud AI tools: "
        "vendor DPA requirements (OpenAI, Anthropic, Google — zero data retention options), "
        "client data handling policies when AI processes personal data for CRM/analysis, "
        "DPIA template for automated client profiling system, "
        "breach response workflow: detection → 72-hour notification → remediation. "
        "UU PDP extraterritorial application: does it apply to Fly.io Singapore servers? "
        "Source: Baker McKenzie PDP practical guide, OneTrust Indonesia, Kominfo."
    ),
    "D": (
        "Building an async-first remote work culture in Indonesian company context 2026: "
        "how to set communication SLAs that respect Indonesian cultural norms "
        "(hierarchical respect, indirect communication, relationship-building), "
        "which async tools work best in Indonesian teams (Slack vs WhatsApp Business vs Notion), "
        "managing 'response anxiety' — setting explicit norms around off-hours messaging, "
        "documentation culture: how to get Indonesian teams to write decisions in Notion/Confluence "
        "when oral tradition is strong. "
        "Source: Workmate Indonesia, IARAS cross-cultural management, HBR Asia 2025."
    ),
    "E": (
        "EOR vs PT PMA for hiring in Bali 2026: comprehensive comparison. "
        "EOR (e.g., Remote.com, Deel, Velocity Global): setup time 1-2 weeks, "
        "cost 15-20% of salary, no RPTKA needed for Indonesian employees, "
        "risk: EOR is legal employer (affects control). "
        "PT PMA: setup 4-8 weeks, full control, RPTKA required for expats, "
        "BPJS + PPh 21 direct liability. "
        "When to use EOR vs PT PMA for Bali consulting operations. "
        "Source: Remote.com Indonesia pricing, Acclime EOR guide, BKPM PT PMA setup."
    ),
    "F": (
        "AI tools legal framework for consulting companies in Indonesia 2026: "
        "IP ownership of AI-generated work product (MOCDA Circular 9/2023 — "
        "DPA must define ownership of trained model weights and outputs), "
        "liability for AI advice errors in professional consulting context, "
        "client consent requirements for AI-assisted analysis of personal data, "
        "zero-data-retention options for enterprise AI tools (Claude Enterprise, "
        "OpenAI Enterprise, Gemini Business), "
        "practical DPA template clauses for Indonesian law compliance. "
        "Source: MOCDA, Baker McKenzie AI Indonesia, Dentons HPRP AI law guide."
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


class NB10Pipeline:
    """NLM pipeline for NB-10: Team Guides.

    Architecture mirrors NB-4 pipeline exactly.
    Run slot: 02:50-03:00 WITA Mon-Sat.
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
            logger.info("Loaded NB-10 state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized NB-10 default state")

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
            "notebook_id": NB10_NOTEBOOK_ID,
            "notebook_name": "NB-10: Team Guides",
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
            "notebook": "NB-10: Team Guides",
            "notebook_id": NB10_NOTEBOOK_ID,
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
            logger.error("NB-10 pipeline error: %s", e, exc_info=True)
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
        logger.info("=== NB-10 PRE-FLIGHT ===")
        checks = []

        now_wita = _now_wita()
        is_sunday = now_wita.weekday() == 6
        if is_sunday and not self.dry_run and not self.force:
            logger.info("Sunday — NB-10 pipeline skipped")
            return False
        checks.append(("not_sunday", not is_sunday or self.dry_run or self.force))

        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > 0)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past NB-10 deadline (03:00 WITA)")
        checks.append(("deadline", not past_deadline or self.dry_run))

        checks.append(("cb_nlm", not self.circuit_breakers.nlm.is_open))

        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        checks.append(("budget", weekly_calls < MAX_WEEKLY_CALLS))

        checks.append(("nlm_query_fn", self._nlm_query is not None or self.dry_run))
        checks.append(("notebook_id", bool(NB10_NOTEBOOK_ID)))

        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            logger.info("  %s %s", "✅" if ok else "❌", name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("NB-10 Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "Hukum Ketenagakerjaan"))

    def _run_query(
        self, level: str, cluster_key: str, conversation_id: Optional[str] = None
    ) -> dict:
        query_map = L1_QUERIES if level == "L1" else L2_QUERIES
        query_text = query_map.get(cluster_key, "")

        if not query_text:
            logger.warning("No %s query template for cluster %s", level, cluster_key)
            return {"success": False, "error": "no_query_template"}

        logger.info("Running NB-10 %s query (cluster %s)...", level, cluster_key)

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
                "notebook_id": NB10_NOTEBOOK_ID,
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
                    logger.info("Extracted %d claims from NB-10 %s", len(claims), level)
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
            logger.error("NB-10 %s query failed: %s", level, e)
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
            "NB-10 consolidation: cluster=%s claims=%d total=%d sources=%d NHS=%.3f (%s)",
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
                "notebook": "NB-10: Team Guides",
                "notebook_id": NB10_NOTEBOOK_ID,
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
            logger.info("NB-10 brief written to %s", BRIEF_FILE)
        except Exception as e:
            logger.warning("Failed to write NB-10 brief: %s", e)

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

    parser = argparse.ArgumentParser(description="NLM NB-10: Team Guides Pipeline")
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

    pipeline = NB10Pipeline(
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
