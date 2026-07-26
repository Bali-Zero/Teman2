"""Unit tests for generate_automations_reference.py — registry + sentinel enrichment."""
from __future__ import annotations

import json
import plistlib
import sys
import tempfile
import unittest
import unittest.mock
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


class TestHumanizePlistSchedule(unittest.TestCase):
    def test_start_interval_hours(self):
        self.assertEqual(gen._humanize_plist_schedule({"StartInterval": 3600}), "every 1h")

    def test_start_interval_minutes(self):
        self.assertEqual(gen._humanize_plist_schedule({"StartInterval": 600}), "every 10m")

    def test_start_interval_odd_seconds(self):
        self.assertEqual(gen._humanize_plist_schedule({"StartInterval": 90}), "every 90s")

    def test_start_calendar_interval_daily(self):
        parsed = {"StartCalendarInterval": {"Hour": 8, "Minute": 15}}
        self.assertEqual(gen._humanize_plist_schedule(parsed), "daily 08:15 WITA")

    def test_run_at_load(self):
        self.assertEqual(gen._humanize_plist_schedule({"RunAtLoad": True}), "RunAtLoad")

    def test_unknown_falls_back_to_dash(self):
        self.assertEqual(gen._humanize_plist_schedule({}), "—")


class TestExtractPlistPurpose(unittest.TestCase):
    def test_strips_repo_canon_prefix(self):
        raw = "<!-- Repo canon. Does the thing daily. -->\n<plist></plist>"
        self.assertEqual(gen._extract_plist_purpose(raw), "Does the thing daily.")

    def test_no_comment_returns_empty(self):
        self.assertEqual(gen._extract_plist_purpose("<plist></plist>"), "")

    def test_multiline_comment_collapsed(self):
        raw = "<!--\n  Repo canon.\n  Multi\n  line\n-->\n<plist></plist>"
        self.assertEqual(gen._extract_plist_purpose(raw), "Multi line")


class TestFindPendingLiveSnapshot(unittest.TestCase):
    """Task #10 regression: generate_automations_reference.py used to have ZERO logic
    for the 'Repo-canon additions pending live snapshot' section — a human hand-added
    it to docs/AUTOMATIONS_REFERENCE.md and every regen (full-file overwrite) silently
    deleted it. This asserts the section is now RE-DERIVED from repo state (option c),
    using the two real magazine LaunchAgents committed under infra/launchagents/."""

    MAGAZINE_LABELS = {"com.balizero.magazine.morning", "com.balizero.magazine.breaking"}

    def _all_repo_labels(self) -> set[str]:
        labels = set()
        for p in gen.REPO_LAUNCHAGENTS_DIR.glob("*.plist"):
            try:
                with p.open("rb") as f:
                    parsed = plistlib.load(f)
            except Exception:
                continue
            labels.add(parsed.get("Label", p.stem))
        return labels

    def test_magazine_labels_pending_when_not_installed(self):
        installed = self._all_repo_labels() - self.MAGAZINE_LABELS
        rows = gen._find_pending_live_snapshot(installed)
        found = {r["label"] for r in rows}
        self.assertTrue(self.MAGAZINE_LABELS.issubset(found))

    def test_magazine_labels_absent_once_installed(self):
        installed = self._all_repo_labels()  # everything, including the magazine pair
        rows = gen._find_pending_live_snapshot(installed)
        found = {r["label"] for r in rows}
        self.assertFalse(self.MAGAZINE_LABELS & found)

    def test_pending_rows_carry_derived_schedule_and_purpose(self):
        installed = self._all_repo_labels() - self.MAGAZINE_LABELS
        rows = {r["label"]: r for r in gen._find_pending_live_snapshot(installed)}
        morning = rows["com.balizero.magazine.morning"]
        self.assertEqual(morning["host"], "Pro")
        self.assertEqual(morning["schedule"], "daily 08:15 WITA")
        self.assertIn("morning magazine compose", morning["purpose"])
        breaking = rows["com.balizero.magazine.breaking"]
        self.assertEqual(breaking["schedule"], "every 10m")

    def test_missing_repo_dir_returns_empty_not_crash(self):
        original = gen.REPO_LAUNCHAGENTS_DIR
        gen.REPO_LAUNCHAGENTS_DIR = Path("/nonexistent/launchagents")
        try:
            self.assertEqual(gen._find_pending_live_snapshot(set()), [])
        finally:
            gen.REPO_LAUNCHAGENTS_DIR = original


class TestRenderPendingSnapshotSection(unittest.TestCase):
    def test_empty_rows_render_nothing(self):
        self.assertEqual(gen._render_pending_snapshot_section([]), [])

    def test_renders_table_row_per_entry(self):
        rows = [{"label": "com.example.foo", "host": "Pro", "schedule": "daily 08:00 WITA", "purpose": "does foo"}]
        lines = gen._render_pending_snapshot_section(rows)
        joined = "\n".join(lines)
        self.assertIn("## Repo-canon additions pending live snapshot", joined)
        self.assertIn("`com.example.foo`", joined)
        self.assertIn("does foo", joined)


class TestGenerateSurvivesRegen(unittest.TestCase):
    """End-to-end regression for task #10: generate() must re-derive the pending-
    snapshot section on every run, not depend on a human re-adding it after the
    previous full-file-overwrite regen deleted it."""

    def test_generate_includes_pending_snapshot_when_not_live(self):
        installed_job = gen.Job(
            name="com_balizero_other_thing", machine="Pro", kind="launchagent",
            schedule="RunAtLoad", command="com.balizero.other-thing",
            plist_label="com.balizero.other-thing",
        )

        def fake_parse_launchagents(machine: str):
            return [installed_job] if machine == "Pro" else []

        with unittest.mock.patch.object(gen, "_run", return_value=""), \
             unittest.mock.patch.object(gen, "_ssh_mini", return_value=""), \
             unittest.mock.patch.object(gen, "_parse_launchagents", side_effect=fake_parse_launchagents):
            content = gen.generate(dry_run=True)

        self.assertIn("## Repo-canon additions pending live snapshot", content)
        self.assertIn("com.balizero.magazine.morning", content)
        self.assertIn("com.balizero.magazine.breaking", content)


if __name__ == "__main__":
    unittest.main()
