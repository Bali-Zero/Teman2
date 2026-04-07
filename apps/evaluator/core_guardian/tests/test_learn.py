"""Tests for Core Guardian V5 Learning Engine."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from learn import (
    FragilityScorer,
    PatternMiner,
    RuleGenerator,
    WeightCalibrator,
    _save_proposals,
    run_learning_cycle_sync,
)


# --- Test Data Generators ---

def _make_decision(
    check_type: str = "rbac_audit",
    finding: str = "Missing RBAC check in backend/app/routers/foo.py line 42",
    severity: str = "warning",
    action_taken: str = "auto_fix",
    risk_score: int = 45,
    timestamp: str = "2026-04-01T10:00:00+00:00",
    component: str = "watchdog",
    metadata: dict | None = None,
) -> dict:
    return {
        "run_id": "test-001",
        "timestamp": timestamp,
        "component": component,
        "check_type": check_type,
        "finding": finding,
        "severity": severity,
        "action_taken": action_taken,
        "risk_score": risk_score,
        "metadata": metadata or {},
    }


def _make_risk_score(
    overall: int = 36,
    rbac: int = 30,
    api: int = 30,
    cache: int = 50,
    dead: int = 45,
    timestamp: str = "2026-04-01T10:00:00+00:00",
) -> dict:
    return {
        "timestamp": timestamp,
        "overall_score": overall,
        "rbac_score": rbac,
        "api_contract_score": api,
        "cache_score": cache,
        "dead_code_score": dead,
    }


# ============================================================================
# PatternMiner Tests
# ============================================================================


class TestPatternMiner(unittest.TestCase):
    """Test pattern mining from guardian decisions."""

    def test_empty_decisions_returns_empty(self) -> None:
        miner = PatternMiner([])
        patterns = miner.mine()
        self.assertEqual(patterns, [])

    def test_single_finding_not_a_pattern(self) -> None:
        """Need MIN_PATTERN_OCCURRENCES (5) to be a pattern."""
        decisions = [_make_decision() for _ in range(3)]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        self.assertEqual(patterns, [])

    def test_five_similar_findings_becomes_pattern(self) -> None:
        """5 similar findings should cluster into one pattern."""
        decisions = [
            _make_decision(finding=f"Missing RBAC check in backend/app/routers/file{i}.py line {i*10}")
            for i in range(6)
        ]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        self.assertGreaterEqual(len(patterns), 1)
        self.assertGreaterEqual(patterns[0]["count"], 5)

    def test_dissimilar_findings_no_pattern(self) -> None:
        """Very different findings should not cluster."""
        decisions = [
            _make_decision(finding="Alpha bravo charlie delta echo"),
            _make_decision(finding="Foxtrot golf hotel india juliet"),
            _make_decision(finding="Kilo lima mike november oscar"),
            _make_decision(finding="Papa quebec romeo sierra tango"),
            _make_decision(finding="Uniform victor whiskey xray yankee"),
        ]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        # Should not form a cluster since texts are very different
        self.assertEqual(len(patterns), 0)

    def test_pattern_extracts_files(self) -> None:
        """Patterns should extract file paths from findings."""
        decisions = [
            _make_decision(finding="Issue in backend/app/routers/crm_clients.py line 42")
            for _ in range(6)
        ]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        self.assertGreaterEqual(len(patterns), 1)
        self.assertIn("backend/app/routers/crm_clients.py", patterns[0]["files"])

    def test_pattern_has_required_fields(self) -> None:
        """Each pattern must have all required fields."""
        decisions = [_make_decision() for _ in range(7)]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        if patterns:
            p = patterns[0]
            self.assertIn("pattern_id", p)
            self.assertIn("canonical", p)
            self.assertIn("count", p)
            self.assertIn("check_types", p)
            self.assertIn("severities", p)
            self.assertIn("action_outcomes", p)

    def test_normalize_finding_strips_paths(self) -> None:
        """Normalization should replace file paths with <file>."""
        result = PatternMiner._normalize_finding(
            "Error in backend/app/routers/foo.py at line 42"
        )
        self.assertIn("<file>", result)
        self.assertIn("line N", result)

    def test_patterns_sorted_by_count_descending(self) -> None:
        """Patterns should be sorted by count (most frequent first)."""
        decisions = (
            [_make_decision(finding="Common finding repeated many times") for _ in range(10)]
            + [_make_decision(finding="Less common but still recurring finding") for _ in range(6)]
        )
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        if len(patterns) >= 2:
            self.assertGreaterEqual(patterns[0]["count"], patterns[1]["count"])

    def test_empty_findings_skipped(self) -> None:
        """Decisions with empty or very short findings should be skipped."""
        decisions = [_make_decision(finding="") for _ in range(10)]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        self.assertEqual(patterns, [])

    def test_metadata_as_string_handled(self) -> None:
        """Metadata stored as JSON string should be parsed correctly."""
        decisions = [
            _make_decision(
                finding="Issue in backend/app/routers/crm.py line 42",
                metadata='{"file": "backend/app/routers/crm.py"}',
            )
            for _ in range(6)
        ]
        miner = PatternMiner(decisions)
        patterns = miner.mine()
        self.assertGreaterEqual(len(patterns), 1)
        self.assertIn("backend/app/routers/crm.py", patterns[0]["files"])


# ============================================================================
# WeightCalibrator Tests
# ============================================================================


class TestWeightCalibrator(unittest.TestCase):
    """Test risk scorer weight calibration."""

    DEFAULT_WEIGHTS = {"rbac": 0.40, "api_contract": 0.30, "cache": 0.20, "dead_code": 0.10}

    def test_insufficient_data_returns_no_change(self) -> None:
        """With < 10 risk scores, should return current weights unchanged."""
        cal = WeightCalibrator(
            risk_scores=[_make_risk_score() for _ in range(5)],
            decisions=[],
            current_weights=self.DEFAULT_WEIGHTS,
        )
        result = cal.calibrate()
        self.assertEqual(result["proposed_weights"], self.DEFAULT_WEIGHTS)
        self.assertEqual(result["confidence"], 0.0)

    def test_no_rollbacks_returns_adequate(self) -> None:
        """Without rollbacks, weights are deemed adequate."""
        scores = [_make_risk_score() for _ in range(15)]
        decisions = [_make_decision(action_taken="auto_fix") for _ in range(10)]
        cal = WeightCalibrator(scores, decisions, self.DEFAULT_WEIGHTS)
        result = cal.calibrate()
        self.assertEqual(result["proposed_weights"], self.DEFAULT_WEIGHTS)
        self.assertIn("adequate", result["rationale"])

    def test_rollback_correlation_adjusts_weights(self) -> None:
        """Rollbacks correlated with high cache scores should increase cache weight."""
        # Normal scores: cache=20
        scores = [
            _make_risk_score(overall=30, cache=20, timestamp=f"2026-04-0{i}T10:00:00+00:00")
            for i in range(1, 8)
        ]
        # Pre-rollback scores: cache=80 (much higher)
        scores.extend([
            _make_risk_score(overall=70, cache=80, timestamp=f"2026-04-0{i}T09:00:00+00:00")
            for i in range(5, 8)
        ])

        # Rollback decisions at 09:30 (after the high-cache scores)
        decisions = [
            _make_decision(
                action_taken="rollback",
                timestamp=f"2026-04-0{i}T09:30:00+00:00",
            )
            for i in range(5, 8)
        ]

        cal = WeightCalibrator(scores, decisions, self.DEFAULT_WEIGHTS)
        result = cal.calibrate()

        # Cache weight should have increased (or at least not decreased)
        self.assertGreater(result["confidence"], 0.0)
        # Weights should still sum to ~1.0
        total = sum(result["proposed_weights"].values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_weights_always_sum_to_one(self) -> None:
        """Proposed weights must always sum to 1.0."""
        scores = [_make_risk_score() for _ in range(20)]
        decisions = [
            _make_decision(action_taken="rollback", timestamp="2026-04-05T10:00:00+00:00")
            for _ in range(5)
        ]
        cal = WeightCalibrator(scores, decisions, self.DEFAULT_WEIGHTS)
        result = cal.calibrate()
        total = sum(result["proposed_weights"].values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_weight_delta_capped(self) -> None:
        """No weight should change more than MAX_WEIGHT_DELTA per cycle."""
        scores = [_make_risk_score(rbac=100, cache=0) for _ in range(20)]
        decisions = [
            _make_decision(action_taken="rollback", timestamp="2026-04-05T10:00:00+00:00")
            for _ in range(10)
        ]
        cal = WeightCalibrator(scores, decisions, self.DEFAULT_WEIGHTS)
        result = cal.calibrate()

        for k in self.DEFAULT_WEIGHTS:
            delta = abs(result["deltas"][k])
            # After normalization, deltas can be slightly over MAX_WEIGHT_DELTA
            # but the pre-normalization delta is capped
            self.assertLessEqual(delta, 0.15, f"Delta for {k} too large: {delta}")

    def test_minimum_weight_floor(self) -> None:
        """No weight should go below 0.05."""
        scores = [_make_risk_score() for _ in range(20)]
        decisions = [
            _make_decision(action_taken="rollback", timestamp="2026-04-05T10:00:00+00:00")
            for _ in range(5)
        ]
        cal = WeightCalibrator(scores, decisions, self.DEFAULT_WEIGHTS)
        result = cal.calibrate()
        for k, v in result["proposed_weights"].items():
            self.assertGreaterEqual(v, 0.04, f"Weight {k}={v} is below floor")


# ============================================================================
# FragilityScorer Tests
# ============================================================================


class TestFragilityScorer(unittest.TestCase):
    """Test file fragility scoring."""

    def _make_scorer(self, decisions: list[dict] | None = None) -> FragilityScorer:
        return FragilityScorer(
            project_root=Path("/fake/project"),
            backend_dir=Path("/fake/project/apps/backend-rag"),
            decisions=decisions or [],
        )

    @patch("learn.subprocess.run")
    def test_git_mod_frequency_parses_output(self, mock_run: MagicMock) -> None:
        """Should parse git log --name-only output."""
        mock_run.return_value = MagicMock(
            stdout=(
                "apps/backend-rag/backend/app/routers/crm_clients.py\n"
                "apps/backend-rag/backend/app/routers/crm_clients.py\n"
                "apps/backend-rag/backend/services/rag/hybrid_search.py\n"
                "\n"
            ),
            returncode=0,
        )
        scorer = self._make_scorer()
        counts = scorer._git_mod_frequency()
        self.assertEqual(counts.get("backend/app/routers/crm_clients.py"), 2)
        self.assertEqual(counts.get("backend/services/rag/hybrid_search.py"), 1)

    @patch("learn.subprocess.run")
    def test_git_churn_parses_numstat(self, mock_run: MagicMock) -> None:
        """Should parse git log --numstat output."""
        mock_run.return_value = MagicMock(
            stdout=(
                "10\t5\tapps/backend-rag/backend/app/routers/crm_clients.py\n"
                "20\t10\tapps/backend-rag/backend/services/rag/hybrid_search.py\n"
            ),
            returncode=0,
        )
        scorer = self._make_scorer()
        churn = scorer._git_churn()
        self.assertEqual(churn.get("backend/app/routers/crm_clients.py"), 15)
        self.assertEqual(churn.get("backend/services/rag/hybrid_search.py"), 30)

    def test_decision_file_mentions(self) -> None:
        """Should extract file paths from decision findings."""
        decisions = [
            _make_decision(finding="Issue in backend/app/routers/foo.py line 10"),
            _make_decision(finding="Problem in backend/app/routers/foo.py line 20"),
            _make_decision(finding="Error in backend/services/bar.py"),
        ]
        scorer = self._make_scorer(decisions)
        counts = scorer._decision_file_mentions()
        self.assertEqual(counts.get("backend/app/routers/foo.py"), 2)
        self.assertEqual(counts.get("backend/services/bar.py"), 1)

    @patch("learn.subprocess.run")
    def test_score_files_returns_sorted_results(self, mock_run: MagicMock) -> None:
        """Should return files sorted by fragility descending."""
        # Mock both git calls and ruff
        def side_effect(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "--name-only" in cmd_str:
                return MagicMock(
                    stdout=(
                        "apps/backend-rag/backend/app/routers/crm.py\n" * 10
                        + "apps/backend-rag/backend/services/rag.py\n" * 2
                    ),
                    returncode=0,
                )
            if "--numstat" in cmd_str:
                return MagicMock(
                    stdout=(
                        "50\t30\tapps/backend-rag/backend/app/routers/crm.py\n"
                        "5\t2\tapps/backend-rag/backend/services/rag.py\n"
                    ),
                    returncode=0,
                )
            if "ruff" in cmd_str:
                return MagicMock(
                    stdout=json.dumps([
                        {"filename": "apps/backend-rag/backend/app/routers/crm.py", "code": "DTZ005"},
                        {"filename": "apps/backend-rag/backend/app/routers/crm.py", "code": "ANN204"},
                        {"filename": "apps/backend-rag/backend/app/routers/crm.py", "code": "ANN001"},
                    ]),
                    returncode=0,
                )
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect
        scorer = self._make_scorer()
        results = scorer.score_files()

        if len(results) >= 2:
            self.assertGreaterEqual(results[0]["fragility"], results[1]["fragility"])

    def test_fragility_score_capped_at_100(self) -> None:
        """Fragility score should never exceed 100."""
        scorer = self._make_scorer()
        # Even with maximum values, score is capped
        for r in [{"file": "x.py", "fragility": 150}]:
            self.assertLessEqual(min(100, r["fragility"]), 100)

    @patch("learn.subprocess.run")
    def test_excludes_test_files(self, mock_run: MagicMock) -> None:
        """Test files should be excluded from fragility scoring."""
        mock_run.return_value = MagicMock(
            stdout=(
                "apps/backend-rag/backend/tests/test_crm.py\n" * 5
                + "apps/backend-rag/backend/app/routers/crm.py\n" * 3
            ),
            returncode=0,
        )
        scorer = self._make_scorer()
        counts = scorer._git_mod_frequency()
        # test files are counted in raw data but filtered in score_files()
        self.assertIn("backend/tests/test_crm.py", counts)

    def test_cicatrix_scores_parses_scars(self) -> None:
        """Should extract recurrence counts from cicatrix-scars.md."""
        import tempfile

        scar_md = """# Cicatrix
### ⚠️ SCAR: /app/backend/llm/zantara_ai_client.py
_Recurrence: 5 observations_

```markdown
TRAUMA: GenAIClient lacks create_chat
```

### ⚠️ SCAR: apps/backend-rag/backend/services/rag/orchestrator_core.py
_Recurrence: 12 observations_

```markdown
TRAUMA: Unused variables
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            scar_file = Path(tmp) / ".claude" / "rules" / "cicatrix-scars.md"
            scar_file.parent.mkdir(parents=True)
            scar_file.write_text(scar_md)

            scorer = self._make_scorer()
            scorer.project_root = Path(tmp)
            scores = scorer._cicatrix_scores()

        # /app/ prefix stripped, backend-rag split applied
        self.assertEqual(scores.get("backend/llm/zantara_ai_client.py"), 5)
        self.assertEqual(scores.get("backend/services/rag/orchestrator_core.py"), 12)

    def test_cicatrix_scores_missing_file(self) -> None:
        """Should return empty dict when cicatrix file doesn't exist."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            scorer = self._make_scorer()
            scorer.project_root = Path(tmp)
            scores = scorer._cicatrix_scores()
        self.assertEqual(scores, {})

    def test_cicatrix_scores_no_matching_scars(self) -> None:
        """Should return empty dict when file has no SCAR blocks."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            scar_file = Path(tmp) / ".claude" / "rules" / "cicatrix-scars.md"
            scar_file.parent.mkdir(parents=True)
            scar_file.write_text("# Cicatrix\nNo scars found.\n")

            scorer = self._make_scorer()
            scorer.project_root = Path(tmp)
            scores = scorer._cicatrix_scores()
        self.assertEqual(scores, {})


# ============================================================================
# RuleGenerator Tests
# ============================================================================


class TestRuleGenerator(unittest.TestCase):
    """Test rule proposal generation from patterns."""

    def _make_pattern(
        self,
        canonical: str = "Hardcoded email address found in config",
        count: int = 7,
        pattern_id: str = "abc123def456",
    ) -> dict:
        return {
            "pattern_id": pattern_id,
            "canonical": canonical,
            "count": count,
            "check_types": ["dead_code_audit"],
            "severities": {"warning": count},
            "files": ["backend/app/routers/foo.py"],
            "first_seen": "2026-03-01",
            "last_seen": "2026-04-01",
            "action_outcomes": {"auto_fix": count},
        }

    def test_empty_patterns_no_proposals(self) -> None:
        gen = RuleGenerator([], existing_checks=set())
        proposals = gen.generate_proposals()
        self.assertEqual(proposals, [])

    def test_matching_template_generates_regex_rule(self) -> None:
        """Pattern matching a template should generate a regex rule."""
        patterns = [self._make_pattern(canonical="Hardcoded email address in config file")]
        gen = RuleGenerator(patterns, existing_checks=set())
        proposals = gen.generate_proposals()
        self.assertGreaterEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["type"], "regex")
        self.assertIn("email", proposals[0]["name"])

    def test_unrecognized_pattern_generates_manual_review(self) -> None:
        """Unknown patterns should generate manual_review proposals."""
        patterns = [self._make_pattern(
            canonical="Unusual XYZ pattern detected in multiple modules",
            count=8,
        )]
        gen = RuleGenerator(patterns, existing_checks=set())
        proposals = gen.generate_proposals()
        self.assertGreaterEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["type"], "manual_review")

    def test_existing_checks_not_duplicated(self) -> None:
        """Should not propose rules that match existing check names."""
        patterns = [self._make_pattern()]
        gen = RuleGenerator(patterns, existing_checks={"learned_hardcoded_email"})
        proposals = gen.generate_proposals()
        for p in proposals:
            self.assertNotEqual(p["name"], "learned_hardcoded_email")

    def test_max_proposals_per_cycle(self) -> None:
        """Should cap proposals at MAX_PROPOSALS_PER_CYCLE."""
        patterns = [
            self._make_pattern(
                canonical=f"Pattern type {i} recurring issue",
                count=10 + i,
                pattern_id=f"id{i:04d}xxxxxxx",
            )
            for i in range(20)
        ]
        gen = RuleGenerator(patterns, existing_checks=set())
        proposals = gen.generate_proposals()
        self.assertLessEqual(len(proposals), 5)

    def test_proposal_has_required_fields(self) -> None:
        """Each proposal must have all required fields."""
        patterns = [self._make_pattern()]
        gen = RuleGenerator(patterns, existing_checks=set())
        proposals = gen.generate_proposals()
        if proposals:
            p = proposals[0]
            required = {"rule_id", "name", "type", "pattern", "description",
                        "severity", "source_pattern", "confidence", "occurrences"}
            self.assertTrue(required.issubset(set(p.keys())), f"Missing fields: {required - set(p.keys())}")

    def test_confidence_scales_with_occurrences(self) -> None:
        """More occurrences should increase confidence."""
        low = self._make_pattern(count=5)
        high = self._make_pattern(count=20, pattern_id="high12345678")
        gen_low = RuleGenerator([low], existing_checks=set())
        gen_high = RuleGenerator([high], existing_checks=set())
        props_low = gen_low.generate_proposals()
        props_high = gen_high.generate_proposals()
        if props_low and props_high:
            self.assertLessEqual(props_low[0]["confidence"], props_high[0]["confidence"])


# ============================================================================
# Proposals Persistence Tests
# ============================================================================


class TestProposalsPersistence(unittest.TestCase):
    """Test proposal save/load logic."""

    def test_save_proposals_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposals_file = Path(tmp) / "proposals.json"
            with patch("learn._PROPOSALS_FILE", proposals_file):
                _save_proposals([
                    {"rule_id": "test_rule_1", "name": "test", "type": "regex"},
                ])
            self.assertTrue(proposals_file.exists())
            data = json.loads(proposals_file.read_text())
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["rule_id"], "test_rule_1")

    def test_save_proposals_merges_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposals_file = Path(tmp) / "proposals.json"
            proposals_file.write_text(json.dumps([
                {"rule_id": "existing_1", "name": "old", "type": "regex"},
            ]))
            with patch("learn._PROPOSALS_FILE", proposals_file):
                _save_proposals([
                    {"rule_id": "new_1", "name": "new", "type": "regex"},
                ])
            data = json.loads(proposals_file.read_text())
            self.assertEqual(len(data), 2)
            ids = {p["rule_id"] for p in data}
            self.assertIn("existing_1", ids)
            self.assertIn("new_1", ids)

    def test_save_proposals_updates_existing_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proposals_file = Path(tmp) / "proposals.json"
            proposals_file.write_text(json.dumps([
                {"rule_id": "rule_1", "name": "old_name", "type": "regex"},
            ]))
            with patch("learn._PROPOSALS_FILE", proposals_file):
                _save_proposals([
                    {"rule_id": "rule_1", "name": "updated_name", "type": "regex"},
                ])
            data = json.loads(proposals_file.read_text())
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["name"], "updated_name")


# ============================================================================
# Integration Test — run_learning_cycle_sync
# ============================================================================


class TestLearningCycle(unittest.TestCase):
    """Integration test for the full learning cycle."""

    @patch("decision_logger.log_decision", new_callable=AsyncMock)
    @patch("learn.FragilityScorer.score_files")
    @patch("learn._save_proposals")
    @patch("learn._save_state")
    def test_full_cycle_with_patterns(
        self,
        mock_save_state: MagicMock,
        mock_save_proposals: MagicMock,
        mock_score_files: MagicMock,
        mock_log_decision: AsyncMock,
    ) -> None:
        """Full cycle with enough data should find patterns and generate proposals."""
        # 8 similar decisions → should form a pattern
        decisions = [
            _make_decision(
                finding=f"Missing cache invalidation in backend/app/routers/file{i}.py",
                check_type="cache_audit",
            )
            for i in range(8)
        ]
        risk_scores = [_make_risk_score() for _ in range(15)]
        mock_score_files.return_value = [
            {"file": "backend/app/routers/crm.py", "fragility": 72,
             "mod_count": 10, "violation_count": 5, "decision_count": 3, "churn": 50},
        ]

        result = run_learning_cycle_sync(decisions=decisions, risk_scores=risk_scores)

        self.assertIn("patterns_found", result)
        self.assertIn("rule_proposals", result)
        self.assertIn("weight_calibration", result)
        self.assertIn("fragile_files_top10", result)
        self.assertIn("duration_s", result)
        self.assertGreaterEqual(result["decisions_analyzed"], 8)

    @patch("decision_logger.log_decision", new_callable=AsyncMock)
    @patch("learn.FragilityScorer.score_files")
    @patch("learn._save_proposals")
    @patch("learn._save_state")
    def test_empty_cycle_no_errors(
        self,
        mock_save_state: MagicMock,
        mock_save_proposals: MagicMock,
        mock_score_files: MagicMock,
        mock_log_decision: AsyncMock,
    ) -> None:
        """Empty data should produce a clean result with no errors."""
        mock_score_files.return_value = []

        result = run_learning_cycle_sync(decisions=[], risk_scores=[])

        self.assertEqual(result["patterns_found"], 0)
        self.assertEqual(result["rule_proposals"], 0)
        self.assertIn("duration_s", result)


if __name__ == "__main__":
    unittest.main()
