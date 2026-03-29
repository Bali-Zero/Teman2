"""NLM Deep Research Pipeline orchestrator.

Daily execution: 01:10-02:20 WITA (Mon-Fri)
Phases: pre-flight → L1 query → assess → L2 query → consolidate → handoff

This is the main entry point. Run via:
    python -m apps.evaluator.nlm_deep_research.pipeline
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
from .handoff import generate_handoff, save_handoff, validate_handoff_schema
from .invariants import check_all_invariants, InvariantSeverity
from .registry import SourceRegistry
from .source_management import (
    compute_svs,
    compute_nhs,
    classify_nhs,
    Source,
    SourceDates,
    SourceScores,
    SourceFlags,
    SourceDedup,
    SourceType,
    LifecycleStage,
    NotebookHealthInput,
)

logger = logging.getLogger(__name__)

# NB-2 configuration
NB2_NOTEBOOK_ID = "cff93ab0-813a-42f2-a8de-36987e724271"

# File paths
STATE_FILE = "apps/evaluator/nlm_nb2_pipeline_state.json"
CLAIMS_FILE = "apps/evaluator/nlm_nb2_claims.jsonl"
REGISTRY_FILE = "apps/evaluator/nlm_nb2_sources.json"

# Timing (WITA = UTC+8)
WITA_OFFSET = timedelta(hours=8)
PIPELINE_DEADLINE_HOUR = 2
PIPELINE_DEADLINE_MINUTE = 30
MAX_QUERY_TIMEOUT_SECONDS = 120

# Budget
MAX_DAILY_QUERIES = 2
MAX_WEEKLY_CALLS = 40

# Cluster rotation (Mon=0 → Fri=4)
CLUSTER_ROTATION = {
    0: ("A", "Work Permits"),
    1: ("B", "Stay Permits"),
    2: ("C", "Visit Visas"),
    3: ("D", "Special Visas"),
    4: ("E", "Compliance"),
}

# Query levels
QUERY_LEVELS = {
    "L1": "Monitoring — What changed?",
    "L2": "Comparative — How did it change?",
    "L3": "Deep analysis — Why? Implications?",
    "L4": "Cross-domain — Connections?",
}


class PipelinePhase(Enum):
    """Pipeline execution phases."""
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    RUNNING_L1 = "RUNNING_L1"
    ASSESSING = "ASSESSING"
    RUNNING_L2 = "RUNNING_L2"
    CONSOLIDATING = "CONSOLIDATING"
    COMPLETE = "COMPLETE"
    HALTED = "HALTED"


class DegradationLevel(Enum):
    """Pipeline health degradation levels."""
    NOMINAL = "NOMINAL"
    DEGRADED_L1 = "DEGRADED_L1"
    DEGRADED_L2 = "DEGRADED_L2"
    HALTED = "HALTED"


class NLMPipeline:
    """Main pipeline orchestrator for NLM Deep Research.

    Usage:
        pipeline = NLMPipeline()
        pipeline.load_state()
        result = pipeline.run()
        pipeline.save_state()
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
        # CB loaded from state file in load_state(), not independently
        self.circuit_breakers: Optional[CircuitBreakerRegistry] = None
        self.dry_run = dry_run
        self.force = force

        # NLM query function — injected for testability
        # In production, this wraps mcp__notebooklm-mcp__notebook_query
        self._nlm_query = nlm_query_fn

        # Pipeline state
        self._state: dict = {}
        self._run_id: str = ""
        self._phase = PipelinePhase.IDLE
        self._degradation = DegradationLevel.NOMINAL
        self._claims_before: int = 0

    def load_state(self) -> None:
        """Load pipeline state from disk."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                self._state = json.load(f)
            logger.info("Loaded pipeline state: %s", self._state.get("current_state"))
        else:
            self._state = self._default_state()
            logger.info("Initialized default pipeline state")

        self.registry.load()
        self._claims_before = load_claims_count(self.claims_file)

        # Load circuit breakers from state file CB section
        self.circuit_breakers = CircuitBreakerRegistry.load(Path(self.state_file))

    def save_state(self) -> None:
        """Save pipeline state to disk."""
        self._state["current_state"] = self._phase.value
        self._state["degradation_level"] = self._degradation.value
        self._state["last_updated"] = _now_iso()
        # Save CB state into our state dict
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
        logger.info("Saved pipeline state: %s", self._phase.value)

    def run(self) -> dict:
        """Execute full pipeline run.

        Returns:
            Run summary dict with phase results and metrics
        """
        self._run_id = str(uuid.uuid4())
        start_time = time.time()
        summary = {
            "run_id": self._run_id,
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
            cluster_letter, cluster_name = self._today_cluster()
            summary["cluster"] = cluster_letter
            summary["cluster_name"] = cluster_name

            # Phase 2: L1 Query
            self._phase = PipelinePhase.RUNNING_L1
            l1_result = self._run_query("L1", cluster_letter)
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
            summary["phases"]["assess"] = {
                "claims_extracted": len(l1_claims),
            }

            # Phase 4: L2 Query (with L1 context)
            self._phase = PipelinePhase.RUNNING_L2
            l2_result = self._run_query(
                "L2",
                cluster_letter,
                conversation_id=l1_result.get("conversation_id"),
            )
            summary["phases"]["l2"] = l2_result

            if not l2_result.get("success") and l1_result.get("success"):
                # L2 failed but L1 worked — degrade but continue
                self.circuit_breakers.nlm.record_failure()
                self._degradation = DegradationLevel.DEGRADED_L1

            # Phase 5: Consolidation
            self._phase = PipelinePhase.CONSOLIDATING
            all_claims = l1_claims + l2_result.get("claims", [])
            consolidation = self._consolidate(all_claims, cluster_letter)
            summary["phases"]["consolidation"] = consolidation

            # Phase 6: Complete
            self._phase = PipelinePhase.COMPLETE
            if l1_result.get("success"):
                self.circuit_breakers.nlm.record_success()

            # Update budget tracking
            queries_used = (1 if l1_result.get("success") else 0) + (
                1 if l2_result.get("success") else 0
            )
            self._increment_budget(queries_used)

        except Exception as e:
            logger.error("Pipeline error: %s", e, exc_info=True)
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
        """Run 12-point pre-flight checklist.

        Returns True if all critical checks pass.
        """
        logger.info("=== PRE-FLIGHT CHECKLIST ===")
        checks = []

        # 1. Weekend check
        now_wita = _now_wita()
        is_weekend = now_wita.weekday() >= 5
        if is_weekend and not self.dry_run and not self.force:
            logger.info("Weekend — pipeline skipped (use --force to override)")
            return False
        checks.append(("weekend", not is_weekend or self.dry_run or self.force))

        # 2. Deadline check
        past_deadline = (
            now_wita.hour > PIPELINE_DEADLINE_HOUR
            or (now_wita.hour == PIPELINE_DEADLINE_HOUR and now_wita.minute > PIPELINE_DEADLINE_MINUTE)
        )
        if past_deadline and not self.dry_run:
            logger.warning("Past deadline (02:30 WITA)")
        checks.append(("deadline", not past_deadline or self.dry_run))

        # 3. Circuit breakers
        nlm_ok = not self.circuit_breakers.nlm.is_open
        checks.append(("cb_nlm", nlm_ok))

        # 4. Budget check
        weekly_calls = self._state.get("budget", {}).get("weekly_calls", 0)
        budget_ok = weekly_calls < MAX_WEEKLY_CALLS
        checks.append(("budget", budget_ok))

        # 5. State file version
        version_ok = self._state.get("schema_version", 1) == 1
        checks.append(("state_version", version_ok))

        # 6. Registry loaded
        registry_ok = self.registry.total_count > 0
        checks.append(("registry", registry_ok))

        # 7. Claims file accessible
        claims_ok = self.claims_file.parent.exists()
        checks.append(("claims_file", claims_ok))

        # 8. Invariant check
        inv_results = check_all_invariants(
            sources=self.registry.to_invariant_dict(),
            pipeline_state=self._state,
            claims_count=self._claims_before,
        )
        critical_fails = [r for r in inv_results if not r.passed and r.severity == InvariantSeverity.CRITICAL]
        invariants_ok = len(critical_fails) == 0
        checks.append(("invariants", invariants_ok))

        # 9. NLM query function available
        query_fn_ok = self._nlm_query is not None or self.dry_run
        checks.append(("nlm_query_fn", query_fn_ok))

        # Log results
        all_passed = all(ok for _, ok in checks)
        for name, ok in checks:
            status = "✅" if ok else "❌"
            logger.info("  %s %s", status, name)

        if not all_passed:
            failed = [name for name, ok in checks if not ok]
            logger.error("Pre-flight FAILED: %s", failed)

        return all_passed

    def _today_cluster(self) -> tuple[str, str]:
        """Get today's cluster based on weekday rotation."""
        weekday = _now_wita().weekday()
        return CLUSTER_ROTATION.get(weekday, ("A", "Work Permits"))

    def _run_query(
        self,
        level: str,
        cluster: str,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Execute a single NLM query.

        Args:
            level: L1, L2, L3, or L4
            cluster: Cluster letter A-E
            conversation_id: For context injection from previous query

        Returns:
            Dict with success, answer, claims, conversation_id
        """
        query_text = self._build_query(level, cluster)
        logger.info("Running %s query for Cluster %s...", level, cluster)

        if self.dry_run:
            logger.info("[DRY RUN] Would query: %s", query_text[:100])
            return {
                "success": True,
                "answer": "[DRY RUN] No actual query executed",
                "claims": [],
                "conversation_id": conversation_id or "dry-run",
                "sources_used": [],
            }

        if not self._nlm_query:
            logger.error("No NLM query function configured")
            return {"success": False, "error": "No query function"}

        try:
            result = self._nlm_query(
                notebook_id=NB2_NOTEBOOK_ID,
                query=query_text,
                conversation_id=conversation_id,
            )

            if result.get("status") != "success":
                logger.warning("NLM query returned non-success: %s", result.get("error"))
                return {"success": False, "error": result.get("error", "Unknown")}

            answer = result.get("answer", "")
            source_ids = result.get("sources_used", [])
            conv_id = result.get("conversation_id", conversation_id)

            # Extract claims
            claims = extract_claims_from_response(
                response_text=answer,
                source_ids=source_ids,
                query_cluster=cluster,
                sources_metadata=self.registry.to_invariant_dict(),
            )

            return {
                "success": True,
                "answer": answer,
                "claims": [c.to_dict() for c in claims],
                "conversation_id": conv_id,
                "sources_used": source_ids,
            }

        except Exception as e:
            logger.error("NLM query failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    def _build_query(self, level: str, cluster: str) -> str:
        """Build query text for given level and cluster.

        In production, this selects from 20 template queries based on
        cluster and level. For MVP, uses simplified templates.
        """
        # L1: monitoring query in Bahasa Indonesia
        if level == "L1":
            templates = {
                "A": "Berikan update terbaru tentang peraturan RPTKA, DKP-TKA, dan izin kerja TKA di Indonesia tahun 2025-2026. Apakah ada perubahan prosedur, tarif, atau persyaratan baru? Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
                "B": "Berikan update terbaru tentang konversi KITAS ke KITAP, perpanjangan izin tinggal terbatas, dan penyatuan keluarga WNA di Indonesia tahun 2025-2026. Apakah ada perubahan persyaratan? Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
                "C": "Berikan update terbaru tentang Visa Kunjungan (VOA, e-VOA, C1, C2), perpanjangan izin tinggal kunjungan, dan aturan visa run di Indonesia tahun 2025-2026. Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
                "D": "Berikan update terbaru tentang visa Second Home, Golden Visa E28, visa pensiun E33E/E33F, dan visa Digital Nomad E33G di Indonesia tahun 2025-2026. Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
                "E": "Berikan update terbaru tentang sanksi overstay, deportasi, Tim Pora, dan penegakan hukum keimigrasian di Bali tahun 2025-2026. Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
            }
            return templates.get(cluster, templates["A"])

        # L2: comparative query in mixed language
        if level == "L2":
            templates = {
                "A": "Bandingkan prosedur RPTKA dan DKP-TKA sebelum dan sesudah PP 34/2021. Apa yang berubah untuk perusahaan PT PMA yang ingin mempekerjakan TKA di Bali? Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
                "B": "Bandingkan persyaratan konversi KITAS ke KITAP untuk kategori pekerja (E23), investor (E28), dan keluarga (E31). Apa perbedaan utama dalam durasi, dokumen, dan biaya? Jawab hanya berdasarkan dokumen sumber.",
                "C": "Bandingkan hak dan pembatasan pemegang VOA, C1, dan C2 di Indonesia. Aktivitas apa yang legal dan ilegal untuk masing-masing? Jawab hanya berdasarkan dokumen sumber.",
                "D": "Bandingkan syarat investasi antara Golden Visa E28B 5 tahun dan 10 tahun, serta Second Home E33B. Berapa minimum investasi dan deposit untuk masing-masing? Jawab hanya berdasarkan dokumen sumber.",
                "E": "Jelaskan perbedaan antara pencegahan (cekal), penangkalan, dan deportasi dalam hukum keimigrasian Indonesia. Kapan masing-masing diterapkan? Jawab hanya berdasarkan dokumen sumber.",
            }
            return templates.get(cluster, templates["A"])

        # L3/L4: deep analysis
        return f"Analisis mendalam tentang Cluster {cluster} — dampak perubahan regulasi keimigrasian 2024-2026 terhadap operasi di Bali. Jawab hanya berdasarkan dokumen sumber."

    def _consolidate(self, claims: list[dict], cluster: str) -> dict:
        """Consolidation phase: save claims, recalculate SVS/NHS, generate handoff."""
        # 1. Save new claims
        claim_records = [
            ClaimRecord(**{k: v for k, v in c.items() if k in ClaimRecord.__dataclass_fields__})
            for c in claims
            if claims  # skip if empty
        ]
        new_count = 0
        if claim_records:
            new_count = append_claims_to_registry(claim_records, self.claims_file)

        # 2. Recalculate SVS for all sources
        svs_updates = 0
        for sid, source_dict in self.registry.sources.items():
            try:
                source_obj = _dict_to_source(sid, source_dict)
                scores = compute_svs(source_obj)
                old_svs = source_dict.get("scores", {}).get("svs_total", 0)
                if abs(scores.svs_total - old_svs) > 0.001:
                    self.registry.update_source(sid, {
                        "scores": {
                            "svs_total": round(scores.svs_total, 3),
                            "svs_classification": scores.svs_classification.value,
                        }
                    })
                    svs_updates += 1
            except Exception as e:
                logger.debug("SVS skip for %s: %s", sid, e)

        # 3. Calculate NHS
        source_objs = []
        for sid, sd in self.registry.sources.items():
            try:
                source_objs.append(_dict_to_source(sid, sd))
            except Exception:
                pass

        nhs_input = NotebookHealthInput(
            active_count=self.registry.active_count,
            sources=source_objs,
            clusters_with_claims=len(self.registry.get_clusters_with_claims()),
            categories_with_claims=len(set(
                c.get("category", "")
                for c in claims
                if c.get("category")
            )),
            duplicates_found_this_week=0,
            sources_evaluated_this_week=max(1, len(claims)),
        )
        nhs_result = compute_nhs(nhs_input)
        nhs = nhs_result.nhs_total
        nhs_class = nhs_result.nhs_classification.value

        # 4. Generate handoff
        handoff = generate_handoff(
            claims=claims,
            pipeline_run_id=self._run_id,
            notebook_id=NB2_NOTEBOOK_ID,
            query_cluster=cluster,
            queries_executed=2,
            domain_denylist=self.registry.domain_denylist,
        )

        is_valid, errors = validate_handoff_schema(handoff)
        if is_valid:
            save_handoff(handoff)
        else:
            logger.warning("Handoff validation failed: %s", errors)

        # 5. Run post-consolidation invariant check
        inv_results = check_all_invariants(
            sources=self.registry.to_invariant_dict(),
            pipeline_state=self._state,
            claims_count=new_count if new_count > 0 else self._claims_before,
        )
        failures = [r for r in inv_results if not r.passed]

        return {
            "claims_saved": len(claim_records),
            "claims_total": new_count,
            "svs_updates": svs_updates,
            "nhs": round(nhs, 3),
            "nhs_class": nhs_class,
            "handoff_valid": is_valid,
            "invariant_failures": len(failures),
        }

    def _increment_budget(self, queries: int) -> None:
        """Increment budget counters."""
        budget = self._state.setdefault("budget", {
            "daily_queries": 0,
            "weekly_calls": 0,
            "last_reset_date": "",
        })

        today = _now_wita().strftime("%Y-%m-%d")
        week_start = (_now_wita() - timedelta(days=_now_wita().weekday())).strftime("%Y-%m-%d")

        # Reset daily if new day
        if budget.get("last_reset_date") != today:
            budget["daily_queries"] = 0
            budget["last_reset_date"] = today

        # Reset weekly if new week
        if budget.get("week_start") != week_start:
            budget["weekly_calls"] = 0
            budget["week_start"] = week_start

        budget["daily_queries"] += queries
        budget["weekly_calls"] += queries

    def _default_state(self) -> dict:
        """Create default pipeline state."""
        return {
            "schema_version": 1,
            "pipeline_version": "1.0.0",
            "current_state": "IDLE",
            "degradation_level": "NOMINAL",
            "last_updated": _now_iso(),
            "last_run": None,
            "budget": {
                "daily_queries": 0,
                "weekly_calls": 0,
                "last_reset_date": "",
                "week_start": "",
            },
            "circuit_breakers": {},
            "previous_claims_count": 0,
        }


def _now_iso() -> str:
    """Current time in ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def _now_wita() -> datetime:
    """Current time in WITA (UTC+8)."""
    return datetime.now(timezone(WITA_OFFSET))


def _dict_to_source(source_id: str, d: dict) -> Source:
    """Convert a registry dict entry to a Source dataclass."""
    from datetime import datetime as dt

    dates_raw = d.get("dates", {})
    dates = SourceDates(
        published=_parse_date(dates_raw.get("published")),
        ingested=_parse_date(dates_raw.get("ingested")),
        promoted=_parse_date(dates_raw.get("promoted")),
        last_reviewed=_parse_date(dates_raw.get("last_reviewed")),
        last_confirmed_valid=_parse_date(dates_raw.get("last_confirmed_valid")),
    )

    scores_raw = d.get("scores", {})
    scores = SourceScores(
        svs_total=scores_raw.get("svs_total", 0),
        times_cited=scores_raw.get("times_cited", 0),
    )

    flags_raw = d.get("flags", {})
    flags = SourceFlags(
        pinned=flags_raw.get("pinned", False),
        enforcement_divergence=flags_raw.get("enforcement_divergence", False),
        manual_review_needed=flags_raw.get("manual_review_needed", False),
    )

    dedup_raw = d.get("dedup", {})
    dedup = SourceDedup(
        url_hash=dedup_raw.get("url_hash"),
        title_normalized=dedup_raw.get("title_normalized", ""),
        known_duplicates=dedup_raw.get("known_duplicates", []),
    )

    # Map source_type string to enum
    st_str = d.get("source_type", "KNOWLEDGE_DOC")
    try:
        source_type = SourceType(st_str)
    except ValueError:
        source_type = SourceType.KNOWLEDGE_DOC

    # Map stage string to enum
    stage_str = d.get("stage", "ACTIVE")
    try:
        stage = LifecycleStage(stage_str)
    except ValueError:
        stage = LifecycleStage.ACTIVE

    return Source(
        nlm_source_id=source_id,
        stage=stage,
        category=d.get("category", "canonical"),
        source_type=source_type,
        title=d.get("title", ""),
        url=d.get("url"),
        language=d.get("language", "id"),
        tier=d.get("tier", 2),
        tier_label=d.get("tier_label", "T2_REGIONAL"),
        dates=dates,
        scores=scores,
        claims=d.get("claims", scores_raw.get("claims_backed", [])),
        dedup=dedup,
        flags=flags,
    )


def _parse_date(val) -> Optional[datetime]:
    """Parse a date string to datetime, or return None."""
    if not val:
        return None
    try:
        if "T" in str(val):
            return datetime.fromisoformat(str(val))
        return datetime.strptime(str(val), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# --- CLI Entry Point ---

def main():
    """Run the pipeline from command line."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NLM Deep Research Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without NLM calls")
    parser.add_argument("--force", action="store_true", help="Force run (ignore weekend check)")
    parser.add_argument("--state-file", default=STATE_FILE, help="Path to state file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Import NLM query function for production runs
    nlm_query_fn = None
    if not args.dry_run:
        try:
            from apps.evaluator.nlm_deep_research.nlm_bridge import nlm_query, check_nlm_available
            if check_nlm_available():
                nlm_query_fn = nlm_query
            else:
                logger.warning("nlm CLI not available — pipeline will fail preflight")
        except ImportError:
            logger.warning("nlm_bridge import failed — pipeline will fail preflight")

    pipeline = NLMPipeline(
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
