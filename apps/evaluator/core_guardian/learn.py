"""
Core Guardian V5 — Self-Evolving Code Intelligence (learn.py)

The brain that closes the feedback loop. Analyzes accumulated data from
guardian_decisions and guardian_risk_scores to:

1. PatternMiner: Identify recurring findings (5+ occurrences)
2. WeightCalibrator: Auto-tune risk_scorer weights from rollback correlation
3. FragilityScorer: Predict which files will break next (git + ruff + decisions)
4. RuleGenerator: Propose new deterministic checks from mined patterns

Architecture:
  - LEARN PROPOSES, CRON VALIDATES (extending "MODEL PROPOSES, PYTHON VALIDATES")
  - All proposals go to proposals.json for review before activation
  - Weight adjustments capped at ±10% per cycle
  - New rules must pass validation before entering the check pipeline
  - Everything logged to guardian_decisions with component='learn'

Budget: $0 base cycle (pure Python). Optional LLM-assisted cycle: $0.50/week max.
Schedule: Runs after each cron_guardian fix cycle.

Dependencies: stdlib + asyncpg (via decision_logger)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

logger = logging.getLogger("guardian.learn")

# --- Paths ---
_GUARDIAN_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _GUARDIAN_DIR.parent.parent.parent
_AGENT_DIR = _PROJECT_ROOT / ".agent" / "decisions"
_PROPOSALS_FILE = _AGENT_DIR / "learn_proposals.json"
_LEARN_STATE_FILE = _AGENT_DIR / "learn_state.json"
_LEARNED_RULES_DIR = _AGENT_DIR / "learned_rules"

# --- Config ---
MIN_PATTERN_OCCURRENCES = 5
SIMILARITY_THRESHOLD = 0.75
MAX_WEIGHT_DELTA = 0.10  # ±10% per calibration cycle
MAX_PROPOSALS_PER_CYCLE = 5
FRAGILITY_LOOKBACK_DAYS = 30
CALIBRATION_LOOKBACK_DAYS = 30


# ============================================================================
# PatternMiner — Find recurring findings in guardian_decisions
# ============================================================================


class PatternMiner:
    """Mines guardian_decisions for recurring patterns.

    Groups similar findings using SequenceMatcher (no ML deps).
    A pattern = cluster of 5+ findings with text similarity > 0.75.
    """

    def __init__(self, decisions: list[dict]) -> None:
        self.decisions = decisions
        self.patterns: list[dict] = []

    def mine(self) -> list[dict]:
        """Extract recurring patterns from decisions.

        Returns list of {
            pattern_id: str,
            canonical: str (most common finding text),
            count: int,
            check_types: list[str],
            severities: Counter,
            files: list[str],
            first_seen: str,
            last_seen: str,
            action_outcomes: Counter,
        }
        """
        if not self.decisions:
            return []

        # Step 1: Group decisions by check_type for efficiency
        by_check_type: dict[str, list[dict]] = defaultdict(list)
        for d in self.decisions:
            by_check_type[d.get("check_type", "unknown")].append(d)

        # Step 2: Within each check_type, cluster similar findings
        all_clusters: list[list[dict]] = []

        for check_type, decisions in by_check_type.items():
            clusters = self._cluster_findings(decisions)
            all_clusters.extend(clusters)

        # Step 3: Also cluster across check_types for cross-cutting patterns
        cross_clusters = self._cluster_findings(self.decisions)
        for cc in cross_clusters:
            # Only add if it's genuinely cross-check-type
            check_types = {d.get("check_type") for d in cc}
            if len(check_types) > 1 and len(cc) >= MIN_PATTERN_OCCURRENCES:
                all_clusters.append(cc)

        # Step 4: Convert clusters to pattern records
        self.patterns = []
        seen_canonicals: set[str] = set()

        for cluster in all_clusters:
            if len(cluster) < MIN_PATTERN_OCCURRENCES:
                continue

            canonical = self._pick_canonical(cluster)
            if not canonical:
                continue
            # Dedup by canonical similarity
            if any(SequenceMatcher(None, canonical, s).ratio() > 0.9 for s in seen_canonicals):
                continue
            seen_canonicals.add(canonical)

            timestamps = [d.get("timestamp", "") for d in cluster if d.get("timestamp")]
            files = self._extract_files(cluster)

            pattern = {
                "pattern_id": self._make_id(canonical),
                "canonical": canonical,
                "count": len(cluster),
                "check_types": sorted({d.get("check_type", "unknown") for d in cluster}),
                "severities": dict(Counter(d.get("severity", "info") for d in cluster)),
                "files": files[:20],  # Cap file list
                "first_seen": min(timestamps) if timestamps else "",
                "last_seen": max(timestamps) if timestamps else "",
                "action_outcomes": dict(Counter(d.get("action_taken", "none") for d in cluster)),
            }
            self.patterns.append(pattern)

        # Sort by count descending
        self.patterns.sort(key=lambda p: p["count"], reverse=True)
        return self.patterns

    def _cluster_findings(self, decisions: list[dict]) -> list[list[dict]]:
        """Cluster decisions by finding text similarity.

        Simple greedy clustering: iterate findings, assign to first matching
        cluster or create new one. O(n*k) where k = number of clusters.
        """
        clusters: list[list[dict]] = []
        cluster_canonicals: list[str] = []

        for d in decisions:
            finding = d.get("finding", "")
            if not finding or len(finding) < 10:
                continue

            # Normalize: lowercase, strip paths, collapse whitespace
            normalized = self._normalize_finding(finding)

            matched = False
            for i, canonical in enumerate(cluster_canonicals):
                if SequenceMatcher(None, normalized, canonical).ratio() > SIMILARITY_THRESHOLD:
                    clusters[i].append(d)
                    matched = True
                    break

            if not matched:
                clusters.append([d])
                cluster_canonicals.append(normalized)

        return clusters

    @staticmethod
    def _normalize_finding(text: str) -> str:
        """Normalize finding text for comparison."""
        text = text.lower()
        # Strip file paths (common noise)
        text = re.sub(r"[\w/\\]+\.py", "<file>", text)
        text = re.sub(r"line \d+", "line N", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:200]  # Cap length for comparison

    @staticmethod
    def _pick_canonical(cluster: list[dict]) -> str:
        """Pick the most representative finding text from a cluster."""
        findings = [d.get("finding", "") for d in cluster]
        counts = Counter(findings)
        return counts.most_common(1)[0][0] if counts else ""

    @staticmethod
    def _extract_files(cluster: list[dict]) -> list[str]:
        """Extract unique file paths from cluster findings and metadata."""
        files: set[str] = set()
        for d in cluster:
            finding = d.get("finding", "")
            # Extract .py paths from finding text
            for m in re.finditer(r"[\w/\\]+\.py", finding):
                files.add(m.group(0))
            # Check metadata for file info
            meta = d.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            if meta.get("file"):
                files.add(meta["file"])
        return sorted(files)

    @staticmethod
    def _make_id(text: str) -> str:
        """Generate stable pattern ID from canonical text."""
        return hashlib.sha256(text.encode()).hexdigest()[:12]


# ============================================================================
# WeightCalibrator — Auto-tune risk_scorer weights from rollback history
# ============================================================================


class WeightCalibrator:
    """Calibrates risk_scorer weights based on historical rollback correlation.

    Logic: If a sub-score (e.g., cache) was high before rollbacks but the
    overall score didn't trigger auto-fix, the weight for that sub-score
    should increase. Conversely, if a sub-score is always high but never
    correlates with actual regressions, its weight should decrease.

    Safety: Max ±10% adjustment per cycle. Weights must sum to 1.0.
    """

    SCORE_FIELDS = ["rbac_score", "api_contract_score", "cache_score", "dead_code_score"]
    WEIGHT_KEYS = ["rbac", "api_contract", "cache", "dead_code"]

    def __init__(
        self,
        risk_scores: list[dict],
        decisions: list[dict],
        current_weights: dict[str, float],
    ) -> None:
        self.risk_scores = risk_scores
        self.decisions = decisions
        self.current_weights = current_weights.copy()

    def calibrate(self) -> dict:
        """Propose weight adjustments.

        Returns {
            current_weights: {rbac: 0.40, ...},
            proposed_weights: {rbac: 0.42, ...},
            deltas: {rbac: +0.02, ...},
            rationale: str,
            confidence: float (0-1),
        }
        """
        if len(self.risk_scores) < 10:
            return {
                "current_weights": self.current_weights,
                "proposed_weights": self.current_weights,
                "deltas": {k: 0.0 for k in self.WEIGHT_KEYS},
                "rationale": f"Insufficient data ({len(self.risk_scores)} samples, need 10+)",
                "confidence": 0.0,
            }

        # Step 1: Find risk score snapshots that preceded rollbacks
        rollback_timestamps = self._find_rollback_timestamps()

        if not rollback_timestamps:
            return {
                "current_weights": self.current_weights,
                "proposed_weights": self.current_weights,
                "deltas": {k: 0.0 for k in self.WEIGHT_KEYS},
                "rationale": "No rollbacks in history — weights are adequate",
                "confidence": 0.5,
            }

        # Step 2: Get pre-rollback scores (nearest snapshot before each rollback)
        pre_rollback_scores = self._get_pre_rollback_scores(rollback_timestamps)

        if not pre_rollback_scores:
            return {
                "current_weights": self.current_weights,
                "proposed_weights": self.current_weights,
                "deltas": {k: 0.0 for k in self.WEIGHT_KEYS},
                "rationale": "No risk score snapshots found near rollback events",
                "confidence": 0.1,
            }

        # Step 3: Compute average sub-scores before rollbacks vs overall average
        avg_pre_rollback = self._compute_avg(pre_rollback_scores)
        avg_overall = self._compute_avg(self.risk_scores)

        # Step 4: Calculate adjustment direction
        # If a sub-score was disproportionately high before rollbacks,
        # its weight should increase (it's a better predictor of problems)
        deltas: dict[str, float] = {}
        for score_field, weight_key in zip(self.SCORE_FIELDS, self.WEIGHT_KEYS):
            pre_rb = avg_pre_rollback.get(score_field, 0)
            overall = avg_overall.get(score_field, 0)

            if overall == 0:
                deltas[weight_key] = 0.0
                continue

            # Ratio > 1 means this score was elevated before rollbacks
            ratio = pre_rb / max(overall, 1)
            # Convert to adjustment: ratio 1.5 → +5%, ratio 0.5 → -5%
            raw_delta = (ratio - 1.0) * 0.10
            # Clamp to MAX_WEIGHT_DELTA
            deltas[weight_key] = max(-MAX_WEIGHT_DELTA, min(MAX_WEIGHT_DELTA, raw_delta))

        # Step 5: Normalize so weights still sum to 1.0
        proposed = {}
        for k in self.WEIGHT_KEYS:
            proposed[k] = max(0.05, self.current_weights[k] + deltas[k])

        # Re-normalize to sum=1.0
        total = sum(proposed.values())
        proposed = {k: round(v / total, 4) for k, v in proposed.items()}

        # Recalculate actual deltas after normalization
        actual_deltas = {k: round(proposed[k] - self.current_weights[k], 4) for k in self.WEIGHT_KEYS}

        confidence = min(1.0, len(pre_rollback_scores) / 10)

        return {
            "current_weights": self.current_weights,
            "proposed_weights": proposed,
            "deltas": actual_deltas,
            "rationale": (
                f"Based on {len(pre_rollback_scores)} pre-rollback snapshots vs "
                f"{len(self.risk_scores)} total. "
                f"Rollback-correlated sub-scores: "
                + ", ".join(
                    f"{k}={avg_pre_rollback.get(sf, 0):.0f}"
                    for sf, k in zip(self.SCORE_FIELDS, self.WEIGHT_KEYS)
                )
            ),
            "confidence": round(confidence, 2),
        }

    def _find_rollback_timestamps(self) -> list[str]:
        """Find timestamps where rollback actions occurred."""
        timestamps = []
        for d in self.decisions:
            action = d.get("action_taken", "")
            if "rollback" in action.lower():
                ts = d.get("timestamp", "")
                if ts:
                    timestamps.append(ts)
        return sorted(timestamps)

    def _get_pre_rollback_scores(self, rollback_timestamps: list[str]) -> list[dict]:
        """Get the nearest risk score snapshot before each rollback."""
        if not self.risk_scores:
            return []

        # Sort risk scores by timestamp
        sorted_scores = sorted(self.risk_scores, key=lambda s: s.get("timestamp", ""))
        pre_rollback: list[dict] = []

        for rb_ts in rollback_timestamps:
            best: dict | None = None
            for score in sorted_scores:
                score_ts = str(score.get("timestamp", ""))
                if score_ts <= rb_ts:
                    best = score
                else:
                    break
            if best is not None:
                pre_rollback.append(best)

        return pre_rollback

    @staticmethod
    def _compute_avg(scores: list[dict]) -> dict[str, float]:
        """Compute average of score fields."""
        if not scores:
            return {}

        sums: dict[str, float] = defaultdict(float)
        for s in scores:
            for field in WeightCalibrator.SCORE_FIELDS:
                val = s.get(field, 0)
                if isinstance(val, (int, float)):
                    sums[field] += val

        return {k: v / len(scores) for k, v in sums.items()}


# ============================================================================
# FragilityScorer — Predict which files will break next
# ============================================================================


class FragilityScorer:
    """Calculates file fragility scores from git history + violations + decisions + scars.

    Score = weighted combination of:
      - Modification frequency (35%): files changed often are more fragile
      - Violation density (25%): files with many ruff violations
      - Decision history (15%): files that appear in fix/rollback decisions
      - Churn rate (10%): lines added+deleted relative to file size
      - Cicatrix scars (15%): files with historical bug patterns from cicatrix-scars.md

    No ML — just arithmetic on observable signals.
    """

    WEIGHT_MOD_FREQ = 0.35
    WEIGHT_VIOLATIONS = 0.25
    WEIGHT_DECISIONS = 0.15
    WEIGHT_CHURN = 0.10
    WEIGHT_CICATRIX = 0.15

    _CICATRIX_FILE = _PROJECT_ROOT / ".claude" / "rules" / "cicatrix-scars.md"

    def __init__(
        self,
        project_root: Path,
        backend_dir: Path,
        decisions: list[dict] | None = None,
    ) -> None:
        self.project_root = project_root
        self.backend_dir = backend_dir
        self.decisions = decisions or []

    def score_files(self) -> list[dict]:
        """Compute fragility scores for all backend Python files.

        Returns sorted list of {
            file: str,
            fragility: int (0-100),
            mod_count: int,
            violation_count: int,
            decision_count: int,
            churn: int,
            cicatrix_score: int,
        }
        """
        # Step 1: Git modification frequency
        mod_counts = self._git_mod_frequency()

        # Step 2: Ruff violation counts
        violation_counts = self._ruff_violations()

        # Step 3: Decision mention counts
        decision_counts = self._decision_file_mentions()

        # Step 4: Git churn (lines added+deleted)
        churn_counts = self._git_churn()

        # Step 5: Cicatrix scar scores
        cicatrix_scores = self._cicatrix_scores()

        # Step 6: Combine all files
        all_files = (
            set(mod_counts) | set(violation_counts) | set(decision_counts)
            | set(churn_counts) | set(cicatrix_scores)
        )

        # Filter to Python files in backend, excluding tests
        all_files = {
            f for f in all_files
            if f.endswith(".py") and "/tests/" not in f and "test_" not in f.split("/")[-1]
        }

        if not all_files:
            return []

        # Step 7: Normalize each dimension to 0-100
        max_mod = max(mod_counts.values()) if mod_counts else 1
        max_viol = max(violation_counts.values()) if violation_counts else 1
        max_dec = max(decision_counts.values()) if decision_counts else 1
        max_churn = max(churn_counts.values()) if churn_counts else 1
        max_cicatrix = max(cicatrix_scores.values()) if cicatrix_scores else 1

        results: list[dict] = []
        for f in all_files:
            mod_norm = (mod_counts.get(f, 0) / max_mod) * 100
            viol_norm = (violation_counts.get(f, 0) / max_viol) * 100
            dec_norm = (decision_counts.get(f, 0) / max_dec) * 100
            churn_norm = (churn_counts.get(f, 0) / max_churn) * 100
            cicatrix_norm = (cicatrix_scores.get(f, 0) / max_cicatrix) * 100

            fragility = (
                self.WEIGHT_MOD_FREQ * mod_norm
                + self.WEIGHT_VIOLATIONS * viol_norm
                + self.WEIGHT_DECISIONS * dec_norm
                + self.WEIGHT_CHURN * churn_norm
                + self.WEIGHT_CICATRIX * cicatrix_norm
            )

            results.append({
                "file": f,
                "fragility": min(100, round(fragility)),
                "mod_count": mod_counts.get(f, 0),
                "violation_count": violation_counts.get(f, 0),
                "decision_count": decision_counts.get(f, 0),
                "churn": churn_counts.get(f, 0),
                "cicatrix_score": cicatrix_scores.get(f, 0),
            })

        results.sort(key=lambda r: r["fragility"], reverse=True)
        return results

    def _git_mod_frequency(self) -> dict[str, int]:
        """Count how many commits touched each file in lookback period."""
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"--since={FRAGILITY_LOOKBACK_DAYS} days ago",
                    "--name-only", "--pretty=format:",
                    "--", "apps/backend-rag/backend/",
                ],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=30,
            )
            counts: dict[str, int] = Counter()
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line.endswith(".py"):
                    # Normalize path relative to backend-rag
                    if "apps/backend-rag/" in line:
                        line = line.split("apps/backend-rag/")[1]
                    counts[line] += 1
            return dict(counts)
        except Exception as e:
            logger.warning(f"git mod frequency failed: {e}")
            return {}

    def _ruff_violations(self) -> dict[str, int]:
        """Count ruff violations per file."""
        try:
            venv_python = self.backend_dir / ".venv" / "bin" / "python"
            if not venv_python.exists():
                venv_python = self.backend_dir / "venv" / "bin" / "python"

            result = subprocess.run(
                [str(venv_python), "-m", "ruff", "check", "--output-format", "json", "backend/"],
                cwd=str(self.backend_dir),
                capture_output=True, text=True, timeout=60,
            )
            counts: dict[str, int] = Counter()
            try:
                violations = json.loads(result.stdout) if result.stdout else []
            except json.JSONDecodeError:
                logger.warning("Ruff output is not valid JSON — violation count will be 0")
                violations = []

            for v in violations:
                filename = v.get("filename", "")
                if "apps/backend-rag/" in filename:
                    filename = filename.split("apps/backend-rag/")[1]
                counts[filename] += 1
            return dict(counts)
        except Exception as e:
            logger.warning(f"ruff violations scan failed: {e}")
            return {}

    def _decision_file_mentions(self) -> dict[str, int]:
        """Count how many guardian decisions mention each file."""
        counts: dict[str, int] = Counter()
        for d in self.decisions:
            finding = d.get("finding", "")
            meta = d.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}

            # Extract files from finding text
            for m in re.finditer(r"[\w/]+\.py", finding):
                counts[m.group(0)] += 1

            # Extract from metadata
            if meta.get("file"):
                counts[meta["file"]] += 1

        return dict(counts)

    def _git_churn(self) -> dict[str, int]:
        """Count lines added+deleted per file in lookback period."""
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"--since={FRAGILITY_LOOKBACK_DAYS} days ago",
                    "--numstat", "--pretty=format:",
                    "--", "apps/backend-rag/backend/",
                ],
                cwd=str(self.project_root),
                capture_output=True, text=True, timeout=30,
            )
            counts: dict[str, int] = Counter()
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    added, deleted, filepath = parts
                    try:
                        churn = int(added) + int(deleted)
                    except ValueError:
                        continue
                    if filepath.endswith(".py"):
                        if "apps/backend-rag/" in filepath:
                            filepath = filepath.split("apps/backend-rag/")[1]
                        counts[filepath] += churn
            return dict(counts)
        except Exception as e:
            logger.warning(f"git churn analysis failed: {e}")
            return {}

    def _cicatrix_scores(self) -> dict[str, int]:
        """Parse cicatrix-scars.md and assign scores based on recurrence count.

        Files with more historical bug recurrences get higher scores.
        Score = recurrence count (raw), normalized later in score_files().
        """
        cicatrix_file = self.project_root / ".claude" / "rules" / "cicatrix-scars.md"
        if not cicatrix_file.exists():
            return {}

        try:
            content = cicatrix_file.read_text()
        except OSError:
            return {}

        scores: dict[str, int] = {}
        scar_pattern = re.compile(
            r'### [^\n]*SCAR:\s*(.+?)\n_Recurrence:\s*(\d+)\s*observations_',
        )

        for match in scar_pattern.finditer(content):
            file_path = match.group(1).strip()
            recurrence = int(match.group(2))

            # Normalize path: strip leading / or /app/ prefix
            file_path = re.sub(r'^/app/', '', file_path)
            file_path = file_path.lstrip('/')
            # Map to backend-relative paths
            if file_path.startswith("apps/backend-rag/"):
                file_path = file_path.split("apps/backend-rag/")[1]

            scores[file_path] = recurrence

        return scores


# ============================================================================
# RuleGenerator — Propose new deterministic checks from patterns
# ============================================================================


class RuleGenerator:
    """Generates proposals for new deterministic checks from mined patterns.

    When the same type of finding recurs 5+ times across different files,
    it's a candidate for a deterministic check (regex or AST-based).

    Does NOT auto-deploy rules — writes proposals to learn_proposals.json
    for human or cron_guardian review.
    """

    # Templates for common pattern types that can become regex checks
    REGEX_TEMPLATES: dict[str, dict[str, str]] = {
        "hardcoded_email": {
            "pattern": r'["\'][\w.+-]+@[\w-]+\.[\w.]+["\']',
            "description": "Hardcoded email address found",
            "severity": "warning",
        },
        "hardcoded_url": {
            "pattern": r'https?://(?!localhost|127\.0\.0\.1|example\.com)[\w./:-]+',
            "description": "Hardcoded URL (not localhost) found",
            "severity": "info",
        },
        "print_statement": {
            "pattern": r"^\s*print\s*\(",
            "description": "print() statement (use logger instead)",
            "severity": "warning",
        },
        "bare_except": {
            "pattern": r"except\s*:",
            "description": "Bare except clause (catch specific exceptions)",
            "severity": "warning",
        },
        "todo_fixme": {
            "pattern": r"#\s*(TODO|FIXME|HACK|XXX)\b",
            "description": "TODO/FIXME comment (track in issue tracker)",
            "severity": "info",
        },
    }

    def __init__(self, patterns: list[dict], existing_checks: set[str]) -> None:
        """
        Args:
            patterns: Output from PatternMiner.mine()
            existing_checks: Names of already-active checks (to avoid duplicates)
        """
        self.patterns = patterns
        self.existing_checks = existing_checks

    def generate_proposals(self) -> list[dict]:
        """Generate rule proposals from patterns.

        Returns list of {
            rule_id: str,
            name: str,
            type: "regex" | "ast" | "manual_review",
            pattern: str (regex) or description,
            description: str,
            severity: str,
            source_pattern: str (pattern_id from PatternMiner),
            confidence: float,
            occurrences: int,
            sample_files: list[str],
        }
        """
        proposals: list[dict] = []

        for pattern in self.patterns:
            if pattern["count"] < MIN_PATTERN_OCCURRENCES:
                continue

            # Try to match against known templates
            proposal = self._match_template(pattern)
            if proposal is None:
                # Generate a manual review proposal for unrecognized patterns
                proposal = self._create_manual_proposal(pattern)

            if proposal and proposal["name"] not in self.existing_checks:
                proposals.append(proposal)

            if len(proposals) >= MAX_PROPOSALS_PER_CYCLE:
                break

        return proposals

    def _match_template(self, pattern: dict) -> dict | None:
        """Try to match a mined pattern against known regex templates."""
        canonical = pattern.get("canonical", "").lower()

        for template_name, template in self.REGEX_TEMPLATES.items():
            # Check if canonical finding mentions the template concept
            keywords = template_name.replace("_", " ").split()
            if any(kw in canonical for kw in keywords):
                return {
                    "rule_id": f"learned_{template_name}_{pattern['pattern_id'][:6]}",
                    "name": f"learned_{template_name}",
                    "type": "regex",
                    "pattern": template["pattern"],
                    "description": template["description"],
                    "severity": template["severity"],
                    "source_pattern": pattern["pattern_id"],
                    "confidence": min(1.0, pattern["count"] / 20),
                    "occurrences": pattern["count"],
                    "sample_files": pattern.get("files", [])[:5],
                }

        return None

    @staticmethod
    def _create_manual_proposal(pattern: dict) -> dict:
        """Create a manual review proposal for patterns that don't match templates."""
        return {
            "rule_id": f"review_{pattern['pattern_id'][:8]}",
            "name": f"review_{pattern['pattern_id'][:8]}",
            "type": "manual_review",
            "pattern": pattern["canonical"][:200],
            "description": f"Recurring pattern ({pattern['count']}x): {pattern['canonical'][:100]}",
            "severity": "info",
            "source_pattern": pattern["pattern_id"],
            "confidence": min(1.0, pattern["count"] / 30),
            "occurrences": pattern["count"],
            "sample_files": pattern.get("files", [])[:5],
        }


# ============================================================================
# Learning Cycle Orchestrator
# ============================================================================


def _load_state() -> dict:
    """Load learn state from disk."""
    try:
        if _LEARN_STATE_FILE.exists():
            return json.loads(_LEARN_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {
        "last_run": "",
        "cycles_completed": 0,
        "total_patterns_found": 0,
        "total_proposals_generated": 0,
        "weight_adjustments_proposed": 0,
        "active_learned_rules": [],
    }


def _save_state(state: dict) -> None:
    """Persist learn state to disk."""
    _LEARN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp = _LEARN_STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str))
        tmp.replace(_LEARN_STATE_FILE)
    except OSError as e:
        logger.error(f"Failed to save learn state: {e}")


def _save_proposals(proposals: list[dict]) -> None:
    """Save proposals to disk for review."""
    _PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = []
        if _PROPOSALS_FILE.exists():
            try:
                existing = json.loads(_PROPOSALS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                existing = []

        # Merge: update existing proposals by rule_id, append new ones
        existing_ids = {p.get("rule_id") for p in existing}
        for proposal in proposals:
            if proposal["rule_id"] in existing_ids:
                # Update existing
                for i, ep in enumerate(existing):
                    if ep.get("rule_id") == proposal["rule_id"]:
                        existing[i] = proposal
                        break
            else:
                existing.append(proposal)

        tmp = _PROPOSALS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, indent=2, default=str))
        tmp.replace(_PROPOSALS_FILE)
    except OSError as e:
        logger.error(f"Failed to save proposals: {e}")


async def run_learning_cycle(
    decisions: list[dict] | None = None,
    risk_scores: list[dict] | None = None,
) -> dict:
    """Run a complete learning cycle.

    Can be called with pre-loaded data (for testing) or will query
    the database via decision_logger.

    Returns summary dict with all findings and proposals.
    """
    from decision_logger import (
        get_recent_decisions,
        get_risk_trend,
        log_decision,
    )
    from risk_scorer import WEIGHTS

    run_id = f"learn-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    t0 = time.monotonic()
    state = _load_state()

    logger.info(f"Learning cycle {run_id} starting (cycle #{state['cycles_completed'] + 1})")

    # --- Step 1: Gather data ---
    if decisions is None:
        decisions = await get_recent_decisions(hours=CALIBRATION_LOOKBACK_DAYS * 24, limit=5000)
    if risk_scores is None:
        risk_scores_raw = await get_risk_trend(days=CALIBRATION_LOOKBACK_DAYS)
        # get_risk_trend returns daily averages, we need raw scores for calibration
        # Fall back to decisions-extracted scores if needed
        risk_scores = risk_scores_raw if risk_scores_raw else []

    logger.info(f"Data loaded: {len(decisions)} decisions, {len(risk_scores)} risk score snapshots")

    summary: dict[str, Any] = {
        "run_id": run_id,
        "decisions_analyzed": len(decisions),
        "risk_scores_analyzed": len(risk_scores),
    }

    # --- Step 2: Pattern Mining ---
    miner = PatternMiner(decisions)
    patterns = miner.mine()
    summary["patterns_found"] = len(patterns)
    summary["top_patterns"] = [
        {"canonical": p["canonical"][:80], "count": p["count"]}
        for p in patterns[:5]
    ]

    if patterns:
        await log_decision(
            run_id, "learn", "pattern_mining",
            f"Found {len(patterns)} recurring patterns from {len(decisions)} decisions",
            "info", "analysis_complete",
            metadata={"top_3": [p["pattern_id"] for p in patterns[:3]]},
        )

    # --- Step 3: Weight Calibration ---
    calibrator = WeightCalibrator(risk_scores, decisions, WEIGHTS)
    calibration = calibrator.calibrate()
    summary["weight_calibration"] = calibration

    if calibration["confidence"] > 0.3 and any(abs(d) > 0.005 for d in calibration["deltas"].values()):
        await log_decision(
            run_id, "learn", "weight_calibration",
            f"Proposed weight adjustments (confidence={calibration['confidence']:.0%}): "
            + ", ".join(f"{k}:{d:+.2%}" for k, d in calibration["deltas"].items() if abs(d) > 0.001),
            "info", "proposal_generated",
            rationale=calibration["rationale"],
            metadata={"proposed_weights": calibration["proposed_weights"]},
        )
        state["weight_adjustments_proposed"] += 1

    # --- Step 4: Fragility Scoring ---
    scorer = FragilityScorer(
        project_root=_PROJECT_ROOT,
        backend_dir=_PROJECT_ROOT / "apps" / "backend-rag",
        decisions=decisions,
    )
    fragile_files = scorer.score_files()
    summary["fragile_files_top10"] = fragile_files[:10]

    if fragile_files:
        top_fragile = fragile_files[0]
        await log_decision(
            run_id, "learn", "fragility_analysis",
            f"Top fragile file: {top_fragile['file']} (score={top_fragile['fragility']}). "
            f"Analyzed {len(fragile_files)} files.",
            "info", "analysis_complete",
            metadata={"top_5": [f["file"] for f in fragile_files[:5]]},
        )

    # --- Step 5: Rule Generation ---
    existing_checks = {
        "cache_invalidation", "empty_catch", "rbac", "dead_code", "api_contract",
    }
    generator = RuleGenerator(patterns, existing_checks)
    proposals = generator.generate_proposals()
    summary["rule_proposals"] = len(proposals)
    summary["proposals_detail"] = proposals

    if proposals:
        _save_proposals(proposals)
        await log_decision(
            run_id, "learn", "rule_generation",
            f"Generated {len(proposals)} rule proposals: "
            + ", ".join(p["name"] for p in proposals),
            "info", "proposal_generated",
            metadata={"rule_ids": [p["rule_id"] for p in proposals]},
        )

    # --- Step 6: Update state ---
    duration_s = round(time.monotonic() - t0, 2)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["cycles_completed"] += 1
    state["total_patterns_found"] += len(patterns)
    state["total_proposals_generated"] += len(proposals)
    _save_state(state)

    summary["duration_s"] = duration_s
    summary["cycle_number"] = state["cycles_completed"]

    logger.info(
        f"Learning cycle {run_id} complete in {duration_s}s: "
        f"{len(patterns)} patterns, {len(proposals)} proposals, "
        f"calibration confidence={calibration['confidence']:.0%}"
    )

    return summary


# ============================================================================
# Sync wrapper for non-async callers (cron_guardian)
# ============================================================================


def run_learning_cycle_sync(
    decisions: list[dict] | None = None,
    risk_scores: list[dict] | None = None,
) -> dict:
    """Sync wrapper for run_learning_cycle."""
    import asyncio

    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(
                asyncio.run, run_learning_cycle(decisions, risk_scores)
            ).result(timeout=120)
    except RuntimeError:
        pass

    return asyncio.run(run_learning_cycle(decisions, risk_scores))


# ============================================================================
# CLI entry point
# ============================================================================


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="[Learn %(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    if verbose:
        logging.getLogger("guardian").setLevel(logging.DEBUG)

    result = run_learning_cycle_sync()
    print(json.dumps(result, indent=2, default=str))
