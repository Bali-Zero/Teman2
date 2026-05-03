"""Unit tests for generate_automations_reference.py — registry + sentinel enrichment."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Aggiungi la root al path per importare lo script
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import generate_automations_reference as gen

REGISTRY_FIXTURE = {
    "jobs": {
        "fly_health_check": {
            "host": "Nuzantara",
            "type": "cron",
            "schedule_seconds": 1800,
            "staleness_threshold_s": 28800,
            "restart_cmd": "bash /Users/nuzantara/scripts/fly-health-check.sh",
            "is_idempotent": True,
            "repair_scope": "LOCAL",
            "critical": True,
            "max_attempts": 10,
        },
        "nlm_bridge": {
            "host": "Nuzantara",
            "type": "launchagent",
            "schedule_seconds": 60,
            "is_idempotent": True,
            "repair_scope": "LOCAL",
            "critical": False,
            "max_attempts": 5,
        },
    }
}

SENTINEL_STATUS_FIXTURE = {
    "ts": 1776001369.9,
    "generated_at": "2026-04-12T13:42:49Z",
    "jobs_total": 56,
    "jobs_checked": 56,
    "jobs_healthy": 15,
    "jobs_circuit_open": 12,
    "jobs_circuit_terminal": 16,
    "dlq_entries": 59,
    "dlq_terminal": 16,
    "dlq_phase_distribution": {"T0": 4, "T1": 0, "T2": 0, "T3": 20, "T4": 19, "TERMINAL": 16},
}

CIRCUIT_BREAKERS_FIXTURE = {
    "fly_health_check": {
        "state": "CLOSED",
        "failures": 0,
        "phase": "T0",
        "phase_updated_at": 1776001369.0,
    },
    "nlm_bridge": {
        "state": "OPEN",
        "failures": 3,
        "phase": "T3",
        "phase_updated_at": 1775000000.0,
    },
}


class TestLoadRegistry(unittest.TestCase):
    def test_returns_empty_dict_when_file_missing(self):
        result = gen._load_registry(Path("/nonexistent/job_registry.json"))
        self.assertEqual(result, {})

    def test_parses_jobs_correctly(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(REGISTRY_FIXTURE, f)
            p = Path(f.name)
        try:
            result = gen._load_registry(p)
            self.assertIn("fly_health_check", result)
            self.assertTrue(result["fly_health_check"]["is_idempotent"])
            self.assertEqual(result["fly_health_check"]["repair_scope"], "LOCAL")
            self.assertEqual(result["fly_health_check"]["max_attempts"], 10)
        finally:
            p.unlink()

    def test_returns_empty_dict_on_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            p = Path(f.name)
        try:
            result = gen._load_registry(p)
            self.assertEqual(result, {})
        finally:
            p.unlink()


class TestLoadSentinelState(unittest.TestCase):
    def test_returns_empty_tuple_when_files_missing(self):
        status, cb = gen._load_sentinel_state(
            Path("/nonexistent/sentinel_status.json"),
            Path("/nonexistent/circuit_breakers.json"),
        )
        self.assertEqual(status, {})
        self.assertEqual(cb, {})

    def test_parses_both_files(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SENTINEL_STATUS_FIXTURE, f)
            status_path = Path(f.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(CIRCUIT_BREAKERS_FIXTURE, f)
            cb_path = Path(f.name)
        try:
            status, cb = gen._load_sentinel_state(status_path, cb_path)
            self.assertEqual(status["jobs_healthy"], 15)
            self.assertEqual(cb["fly_health_check"]["state"], "CLOSED")
            self.assertEqual(cb["nlm_bridge"]["phase"], "T3")
        finally:
            status_path.unlink()
            cb_path.unlink()

    def test_returns_status_only_when_cb_missing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SENTINEL_STATUS_FIXTURE, f)
            status_path = Path(f.name)
        try:
            status, cb = gen._load_sentinel_state(status_path, Path("/nonexistent/cb.json"))
            self.assertEqual(status["jobs_healthy"], 15)
            self.assertEqual(cb, {})
        finally:
            status_path.unlink()


class TestEnrichJobFromRegistry(unittest.TestCase):
    def _make_job(self, name: str) -> gen.Job:
        return gen.Job(
            name=name, machine="Pro", kind="cron",
            schedule="1800", command="bash test.sh",
        )

    def test_enriches_known_job(self):
        job = self._make_job("fly_health_check")
        registry = {
            "fly_health_check": {
                "is_idempotent": True,
                "repair_scope": "LOCAL",
                "critical": True,
                "max_attempts": 10,
            }
        }
        gen._enrich_job_from_registry(job, registry)
        self.assertTrue(job.is_idempotent)
        self.assertEqual(job.repair_scope, "LOCAL")
        self.assertTrue(job.critical)
        self.assertEqual(job.max_attempts, 10)

    def test_unknown_job_leaves_defaults(self):
        job = self._make_job("unknown_job")
        gen._enrich_job_from_registry(job, {})
        self.assertIsNone(job.is_idempotent)
        self.assertIsNone(job.repair_scope)
        self.assertFalse(job.critical)
        self.assertIsNone(job.max_attempts)

    def test_partial_registry_entry(self):
        job = self._make_job("partial_job")
        registry = {"partial_job": {"repair_scope": "EXTERNAL"}}
        gen._enrich_job_from_registry(job, registry)
        self.assertIsNone(job.is_idempotent)
        self.assertEqual(job.repair_scope, "EXTERNAL")
        self.assertFalse(job.critical)
        self.assertIsNone(job.max_attempts)


class TestEnrichJobFromCircuitBreaker(unittest.TestCase):
    def _make_job(self, name: str) -> gen.Job:
        return gen.Job(
            name=name, machine="Pro", kind="cron",
            schedule="1800", command="bash test.sh",
        )

    def test_enriches_open_circuit(self):
        job = self._make_job("nlm_bridge")
        cb = {"nlm_bridge": {"state": "OPEN", "failures": 3, "phase": "T3", "phase_updated_at": 0.0}}
        gen._enrich_job_from_circuit_breaker(job, cb)
        self.assertEqual(job.circuit_state, "OPEN")
        self.assertEqual(job.dlq_phase, "T3")

    def test_enriches_closed_circuit(self):
        job = self._make_job("fly_health_check")
        cb = {"fly_health_check": {"state": "CLOSED", "failures": 0, "phase": "T0", "phase_updated_at": 0.0}}
        gen._enrich_job_from_circuit_breaker(job, cb)
        self.assertEqual(job.circuit_state, "CLOSED")
        self.assertEqual(job.dlq_phase, "T0")

    def test_unknown_job_leaves_none(self):
        job = self._make_job("no_such_job")
        gen._enrich_job_from_circuit_breaker(job, {})
        self.assertIsNone(job.circuit_state)
        self.assertIsNone(job.dlq_phase)

    def test_enriches_terminal_phase(self):
        job = self._make_job("broken_job")
        cb = {"broken_job": {"state": "OPEN", "failures": 10, "phase": "TERMINAL", "phase_updated_at": 0.0}}
        gen._enrich_job_from_circuit_breaker(job, cb)
        self.assertEqual(job.circuit_state, "OPEN")
        self.assertEqual(job.dlq_phase, "TERMINAL")


class TestFormatCircuitBadge(unittest.TestCase):
    def test_closed_t0(self):
        result = gen._format_circuit_badge("CLOSED", "T0")
        self.assertEqual(result, "✅ CLOSED/T0")

    def test_open_t3(self):
        result = gen._format_circuit_badge("OPEN", "T3")
        self.assertEqual(result, "🔴 OPEN/T3")

    def test_terminal(self):
        result = gen._format_circuit_badge("OPEN", "TERMINAL")
        self.assertEqual(result, "💀 OPEN/TERMINAL")

    def test_none_values(self):
        result = gen._format_circuit_badge(None, None)
        self.assertEqual(result, "—")

    def test_open_t4(self):
        result = gen._format_circuit_badge("OPEN", "T4")
        self.assertEqual(result, "🔴 OPEN/T4")

    def test_closed_t0_is_not_red(self):
        result = gen._format_circuit_badge("CLOSED", "T0")
        self.assertNotIn("🔴", result)
        self.assertNotIn("💀", result)


if __name__ == "__main__":
    unittest.main()
