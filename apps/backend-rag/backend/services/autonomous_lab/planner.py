"""Source-agnostic planning scaffold for the Nuzantara autonomous lab."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

PIPELINE_VERSION = "autonomous-lab-v0"
SAFE_COMMAND_ARG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
RAW_MARKER_PATTERN = re.compile(
    r"\b(?:RAW(?:_[A-Z0-9]+){1,}|[A-Z0-9]+_(?:MUST_NOT_LEAK|SHOULD_NOT_APPEAR))\b"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"<>,;]{12,}"
)
SECRET_QUERY_KEY_PATTERN = re.compile(
    r"(?i)(?:^|[?&])(?:access[_-]?token|api[_-]?key|key|password|secret|signature|sig|token)="
)


class MaterialSourceType(str, Enum):
    """Supported source classes for lab material envelopes."""

    WEB = "web"
    REPO = "repo"
    DATASET = "dataset"
    DRIVE_METADATA = "drive_metadata"
    CHAT_METADATA = "chat_metadata"
    OPERATOR_NOTE = "operator_note"
    OTHER = "other"


PRIVATE_RECEIPT_SOURCE_TYPES = frozenset(
    {
        MaterialSourceType.CHAT_METADATA,
        MaterialSourceType.DRIVE_METADATA,
        MaterialSourceType.OPERATOR_NOTE,
        MaterialSourceType.OTHER,
    }
)


class GateSeverity(str, Enum):
    """Gate severity used by lab receipts."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class PipelineStep:
    """One pipeline stage in the autonomous lab."""

    order: int
    stage: str
    component: str
    output: str
    gate: str

    def to_receipt(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "order": self.order,
            "stage": self.stage,
            "component": self.component,
            "output": self.output,
            "gate": self.gate,
        }


@dataclass(frozen=True)
class ResearchMaterial:
    """Raw research envelope accepted by the lab.

    The raw text is intentionally not serialized by LabRun receipts.
    """

    material_id: str
    source_type: MaterialSourceType
    source_uri: str
    title: str
    text: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, str] = field(default_factory=dict)

    def content_fingerprint(self) -> str:
        """Return a stable, receipt-safe fingerprint for the raw text."""
        return _safe_sha256_fingerprint(self.text)


@dataclass(frozen=True)
class NormalizedMaterial:
    """Derived, receipt-safe representation of research material."""

    material_id: str
    source_type: MaterialSourceType
    source_uri: str
    title: str
    captured_at: datetime
    content_fingerprint: str
    summary: str
    tags: list[str]
    claims: list[str]
    risk_flags: list[str]

    def to_receipt(self) -> dict[str, Any]:
        """Return a JSON-safe representation without raw text."""
        return {
            "material_id": self.material_id,
            "source_type": self.source_type.value,
            "source_uri": self.source_uri,
            "title": self.title,
            "captured_at": self.captured_at.isoformat(),
            "content_fingerprint": self.content_fingerprint,
            "summary": self.summary,
            "tags": self.tags,
            "claims": self.claims,
            "risk_flags": self.risk_flags,
        }


@dataclass(frozen=True)
class LabSafetyGate:
    """Safety gate result for a lab run draft."""

    name: str
    passed: bool
    severity: GateSeverity
    detail: str

    def to_receipt(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SimulationPlan:
    """Prod-like simulation plan emitted before any experiment runs."""

    target_paths: list[str]
    worktree_lane: str
    worktree_command: str
    context_reconstruction: list[str]
    verification_commands: list[str]
    failure_analysis_required: bool = True

    def to_receipt(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "target_paths": self.target_paths,
            "worktree_lane": self.worktree_lane,
            "worktree_command": self.worktree_command,
            "context_reconstruction": self.context_reconstruction,
            "verification_commands": self.verification_commands,
            "failure_analysis_required": self.failure_analysis_required,
        }


@dataclass(frozen=True)
class LabRun:
    """Decision-grade draft produced by the autonomous lab planner."""

    run_id: str
    objective: str
    created_at: datetime
    pipeline_version: str
    pipeline: list[PipelineStep]
    materials: list[NormalizedMaterial]
    hypotheses: list[str]
    simulation_plan: SimulationPlan
    safety_gates: list[LabSafetyGate]
    decision_grade_outputs: list[str]
    promotion_policy: str

    def has_blockers(self) -> bool:
        """Return True when a blocker gate failed."""
        return any(
            gate.severity == GateSeverity.BLOCKER and not gate.passed for gate in self.safety_gates
        )

    def to_receipt(self) -> dict[str, Any]:
        """Return a JSON-safe receipt with no raw material text."""
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "created_at": self.created_at.isoformat(),
            "pipeline_version": self.pipeline_version,
            "pipeline": [step.to_receipt() for step in self.pipeline],
            "materials": [material.to_receipt() for material in self.materials],
            "hypotheses": self.hypotheses,
            "simulation_plan": self.simulation_plan.to_receipt(),
            "safety_gates": [gate.to_receipt() for gate in self.safety_gates],
            "decision_grade_outputs": self.decision_grade_outputs,
            "promotion_policy": self.promotion_policy,
            "blocked": self.has_blockers(),
        }


def default_pipeline() -> list[PipelineStep]:
    """Return the canonical v0 lab pipeline."""
    return [
        PipelineStep(1, "intake", "source_adapters", "ResearchMaterial[]", "provenance"),
        PipelineStep(2, "normalize", "normalizer", "NormalizedMaterial[]", "no_raw_receipt"),
        PipelineStep(3, "compose", "composer", "hypotheses_and_spec", "evidence_quorum"),
        PipelineStep(4, "reconstruct", "context_builder", "SimulationPlan", "no_secrets"),
        PipelineStep(5, "experiment", "worktree_runner", "patch_and_artifacts", "worktree"),
        PipelineStep(
            6, "verify", "verification_runner", "test_metrics_failure_report", "empirical"
        ),
        PipelineStep(7, "promote", "decision_gate", "operator_proposal", "manual_only"),
    ]


class AutonomousLabPlanner:
    """Build source-agnostic autonomous lab run drafts and receipts."""

    def __init__(self, worktree_lane: str = "ops") -> None:
        self.worktree_lane = worktree_lane

    def normalize_material(self, material: ResearchMaterial) -> NormalizedMaterial:
        """Normalize one material envelope without retaining raw text."""
        return NormalizedMaterial(
            material_id=_receipt_safe_material_id(material.material_id),
            source_type=material.source_type,
            source_uri=_safe_source_uri(material.source_uri, material.source_type),
            title=_receipt_safe_title(material.title),
            captured_at=material.captured_at,
            content_fingerprint=material.content_fingerprint(),
            summary=_summarize(material.text),
            tags=_extract_tags(material.text, material.metadata),
            claims=_extract_claims(material.text),
            risk_flags=_risk_flags(material),
        )

    def draft_run(
        self,
        *,
        objective: str,
        materials: list[ResearchMaterial],
        target_paths: list[str],
        task_id: str,
        created_at: datetime | None = None,
    ) -> LabRun:
        """Build a lab run draft from arbitrary research materials."""
        safe_objective = _receipt_safe_objective(objective)
        normalized = [self.normalize_material(material) for material in materials]
        simulation_plan = self._build_simulation_plan(target_paths=target_paths, task_id=task_id)
        gates = self._evaluate_gates(materials=materials, simulation_plan=simulation_plan)
        return LabRun(
            run_id=task_id,
            objective=safe_objective,
            created_at=created_at or datetime.now(tz=timezone.utc),
            pipeline_version=PIPELINE_VERSION,
            pipeline=default_pipeline(),
            materials=normalized,
            hypotheses=_hypotheses(safe_objective, normalized),
            simulation_plan=simulation_plan,
            safety_gates=gates,
            decision_grade_outputs=[
                "technical proposal",
                "patch diff",
                "test report",
                "metric delta",
                "failure analysis",
                "manual promotion recommendation",
            ],
            promotion_policy="manual_operator_decision_only",
        )

    def write_receipt(self, run: LabRun, receipt_dir: Path) -> Path:
        """Persist a lab run receipt atomically and return the final path."""
        receipt_dir.mkdir(parents=True, exist_ok=True)
        final_path = receipt_dir / f"{run.run_id}.json"
        tmp_path = final_path.with_suffix(".json.tmp")
        payload = run.to_receipt()
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(final_path)
        return final_path

    def _build_simulation_plan(self, *, target_paths: list[str], task_id: str) -> SimulationPlan:
        safe_paths = [
            _require_safe_repo_path(path, f"target_paths[{index}]")
            for index, path in enumerate(target_paths)
            if path.strip()
        ]
        safe_lane = _require_safe_command_arg(self.worktree_lane, "worktree_lane")
        safe_task_id = _require_safe_command_arg(task_id, "task_id")
        worktree_command = (
            f"python scripts/agent_start.py --lane {safe_lane} --task-id {safe_task_id}"
        )
        return SimulationPlan(
            target_paths=safe_paths,
            worktree_lane=safe_lane,
            worktree_command=worktree_command,
            context_reconstruction=[
                "git head and dirty-state snapshot",
                "target service import graph",
                "environment key allowlist without secret values",
                "fixture or sanitized data shape matching production contracts",
                "exact runtime command path used by production or cron",
            ],
            verification_commands=_verification_commands(safe_paths),
        )

    def _evaluate_gates(
        self,
        *,
        materials: list[ResearchMaterial],
        simulation_plan: SimulationPlan,
    ) -> list[LabSafetyGate]:
        workspace_write_requested = any(
            material.metadata.get("requires_google_workspace_write", "").lower() == "true"
            for material in materials
        )
        return [
            LabSafetyGate(
                name="materials_present",
                passed=len(materials) > 0,
                severity=GateSeverity.BLOCKER,
                detail="at least one research material is required",
            ),
            LabSafetyGate(
                name="raw_material_not_persisted",
                passed=True,
                severity=GateSeverity.BLOCKER,
                detail="receipts store grouped content fingerprint and derived fields only",
            ),
            LabSafetyGate(
                name="worktree_isolation",
                passed=simulation_plan.worktree_command.startswith("python scripts/agent_start.py"),
                severity=GateSeverity.BLOCKER,
                detail=simulation_plan.worktree_command,
            ),
            LabSafetyGate(
                name="google_workspace_write_block",
                passed=not workspace_write_requested,
                severity=GateSeverity.BLOCKER,
                detail="workspace write flow requires explicit operator request",
            ),
            LabSafetyGate(
                name="production_deploy_block",
                passed=True,
                severity=GateSeverity.BLOCKER,
                detail="lab drafts never emit deploy or origin-main promotion commands",
            ),
            LabSafetyGate(
                name="manual_promotion_only",
                passed=True,
                severity=GateSeverity.BLOCKER,
                detail="operator must approve any promotion after verification",
            ),
        ]


def _summarize(text: str, max_chars: int = 360) -> str:
    words = re.findall(r"\w+", text)
    line_count = len([line for line in text.splitlines() if line.strip()])
    sentence_count = len([part for part in re.split(r"[.!?]+", text) if part.strip()])
    summary = (
        f"Derived non-verbatim summary: {len(words)} words, "
        f"{line_count} non-empty lines, {sentence_count} sentence-like segments."
    )
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3].rstrip() + "..."


def _safe_sha256_fingerprint(value: str, hex_chars: int = 16) -> str:
    """Return a grouped SHA-256 prefix that remains useful without tripping secret scans."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:hex_chars]
    grouped = "-".join(digest[index : index + 4] for index in range(0, len(digest), 4))
    return f"sha256:{grouped}"


def _receipt_safe_objective(objective: str) -> str:
    words = re.findall(r"\w+", objective)
    return f"objective_fingerprint:{_safe_sha256_fingerprint(objective)}; words:{len(words)}"


def _receipt_safe_material_id(material_id: str) -> str:
    candidate = material_id.strip()
    if SAFE_COMMAND_ARG_PATTERN.match(candidate) and not _contains_receipt_sensitive_value(candidate):
        return candidate
    return f"material_fingerprint:{_safe_sha256_fingerprint(material_id)}"


def _receipt_safe_title(title: str) -> str:
    words = re.findall(r"\w+", title)
    return f"title_fingerprint:{_safe_sha256_fingerprint(title)}; words:{len(words)}"


def _safe_source_uri(source_uri: str, source_type: MaterialSourceType) -> str:
    candidate = source_uri.strip()
    if source_type in PRIVATE_RECEIPT_SOURCE_TYPES:
        return f"{source_type.value}:source_fingerprint:{_safe_sha256_fingerprint(candidate)}"
    if _contains_receipt_sensitive_value(candidate):
        return f"{source_type.value}:source_fingerprint:{_safe_sha256_fingerprint(candidate)}"

    parsed = urlsplit(candidate)
    if parsed.query or parsed.fragment or len(candidate) > 240:
        scheme = parsed.scheme or source_type.value
        host = parsed.netloc or "local"
        return f"{scheme}://{host}/source_fingerprint:{_safe_sha256_fingerprint(candidate)}"
    return candidate


def _contains_receipt_sensitive_value(value: str) -> bool:
    return bool(
        RAW_MARKER_PATTERN.search(value)
        or SECRET_ASSIGNMENT_PATTERN.search(value)
        or SECRET_QUERY_KEY_PATTERN.search(value)
    )


def _require_safe_command_arg(value: str, field_name: str) -> str:
    candidate = value.strip()
    if not SAFE_COMMAND_ARG_PATTERN.match(candidate):
        raise ValueError(f"{field_name} must be a safe slug for planned command receipts")
    return candidate


def _require_safe_repo_path(value: str, field_name: str) -> str:
    candidate = value.strip()
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate or candidate == ".":
        raise ValueError(f"{field_name} must be a non-empty repository-relative path")
    if "\x00" in candidate:
        raise ValueError(f"{field_name} must not contain null bytes")
    if "\\" in candidate:
        raise ValueError(f"{field_name} must use POSIX separators")
    if "://" in candidate:
        raise ValueError(f"{field_name} must not be a URI")
    if candidate.startswith("~"):
        raise ValueError(f"{field_name} must not be home-relative")
    if _contains_receipt_sensitive_value(candidate):
        raise ValueError(f"{field_name} must not contain receipt-sensitive values")

    path = PurePosixPath(candidate)
    if path.is_absolute():
        raise ValueError(f"{field_name} must be repository-relative")
    if ".." in path.parts:
        raise ValueError(f"{field_name} must not contain path traversal")
    return path.as_posix()


def _extract_tags(text: str, metadata: dict[str, str]) -> list[str]:
    haystack = " ".join([text, " ".join(metadata.values())]).lower()
    tag_map = {
        "research": ("research", "paper", "study", "source"),
        "repo": ("code", "repo", "diff", "test", "pytest"),
        "simulation": ("simulate", "prod-like", "fixture", "runtime"),
        "crm": ("crm", "client", "whatsapp"),
        "workspace": ("drive", "docs", "sheets", "workspace"),
        "safety": ("secret", "token", "privacy", "approval", "gate"),
    }
    tags = [
        tag for tag, needles in tag_map.items() if any(needle in haystack for needle in needles)
    ]
    return tags or ["general"]


def _extract_claims(text: str, limit: int = 5) -> list[str]:
    lines = [line.strip(" -\t") for line in text.splitlines()]
    candidates = [line for line in lines if len(line) >= 24]
    if not candidates:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        candidates = [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 24]
    return [
        f"claim_fingerprint:{_safe_sha256_fingerprint(candidate)}"
        for candidate in candidates[:limit]
    ]


def _risk_flags(material: ResearchMaterial) -> list[str]:
    flags: list[str] = []
    text = material.text.lower()
    if material.source_type in {
        MaterialSourceType.CHAT_METADATA,
        MaterialSourceType.DRIVE_METADATA,
    }:
        flags.append("private_metadata_source")
    if "api_key" in text or "secret" in text or "token" in text:
        flags.append("possible_secret_reference")
    if material.metadata.get("requires_google_workspace_write", "").lower() == "true":
        flags.append("workspace_write_requested")
    return flags


def _hypotheses(objective: str, materials: list[NormalizedMaterial]) -> list[str]:
    tags = sorted({tag for material in materials for tag in material.tags})
    if not tags:
        return [f"Investigate whether '{objective}' is productive enough for an experiment."]
    return [
        f"Use {', '.join(tags[:4])} evidence to test whether '{objective}' can produce a decision-grade Nuzantara change.",
        "Prefer a reversible worktree experiment with explicit tests before any promotion.",
    ]


def _verification_commands(target_paths: list[str]) -> list[str]:
    commands: list[str] = []
    if any(path.startswith("apps/backend-rag/") for path in target_paths):
        commands.append(
            "cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/autonomous_lab -q"
        )
    if any(path.startswith("apps/mouth/") for path in target_paths):
        commands.append("cd apps/mouth && npm run lint")
    if any(path.startswith("research/") for path in target_paths):
        commands.append("git diff --check -- research/operations/autonomous-lab")
    return commands or ["git diff --check"]
