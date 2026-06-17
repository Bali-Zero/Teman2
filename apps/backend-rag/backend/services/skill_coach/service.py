"""Skill Coach dry-run evaluator.

This service closes the safe half of the learning loop: it evaluates
trajectory-derived skill proposals and emits redacted evidence cards. It does
not write active skills to the Genome and does not publish HGT events.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from backend.services.skill_coach.models import SkillCoachEvidence

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.environ.get(
    "EXPERIENCE_DB_PATH",
    os.path.expanduser("~/.nuzantara/experience.db"),
)

SKILL_CREATION_PROPOSALS_PATH = os.environ.get(
    "SKILL_CREATION_PROPOSALS_PATH",
    os.path.expanduser("~/.nuzantara/skill_creation_proposals.jsonl"),
)

SKILL_COACH_EVIDENCE_PATH = os.environ.get(
    "SKILL_COACH_EVIDENCE_PATH",
    os.path.expanduser("~/.nuzantara/skill_coach_evidence.jsonl"),
)

_REDACTED_TEXT = "[redacted: customer-data scan failed]"
_MAX_SOURCE_TRAJECTORY_IDS = 20

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "phone",
        re.compile(r"(?<!\d)(?:\+?62|0)[\s.-]?\d{2,4}(?:[\s.-]?\d){5,10}(?!\d)"),
    ),
    ("nik", re.compile(r"(?<!\d)\d{16}(?!\d)")),
    (
        "npwp",
        re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}\.?\d[-.]?\d{3}\.?\d{3}(?!\d)"),
    ),
    (
        "passport",
        re.compile(
            r"\b(?:passport|paspor)\s*[:#-]?\s*[A-Z0-9]{6,12}\b|\b[A-Z][0-9]{7,8}\b",
            re.I,
        ),
    ),
    (
        "customer_id",
        re.compile(r"\b(?:ktp|nik|npwp)\s*[:#-]?\s*[A-Z0-9.\-]{6,24}\b", re.I),
    ),
)


def scan_clear_customer_data(*texts: object) -> list[str]:
    """Return customer-data category labels found in text, never matched values."""
    findings: list[str] = []
    haystack = "\n".join(str(t) for t in texts if t is not None)
    for label, pattern in _PII_PATTERNS:
        if pattern.search(haystack) and label not in findings:
            findings.append(label)

    normalized_digits = re.sub(r"[\s.-]+", "", haystack)
    if re.search(r"(?<!\d)\d{16}(?!\d)", normalized_digits) and "nik" not in findings:
        findings.append("nik")
    if (
        re.search(r"(?<!\d)\d{15}(?!\d)", normalized_digits)
        and "npwp" not in findings
    ):
        findings.append("npwp")
    return findings


class SkillCoachService:
    """Evaluate skill proposals against historical trajectory evidence."""

    def __init__(
        self,
        db_path: str | None = None,
        proposals_path: str | None = None,
        evidence_path: str | None = None,
        min_support: int = 3,
    ) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._proposals_path = proposals_path or SKILL_CREATION_PROPOSALS_PATH
        self._evidence_path = evidence_path or SKILL_COACH_EVIDENCE_PATH
        self._min_support = min_support

    def evaluate_proposal(
        self,
        proposal: dict[str, Any],
        trajectories: list[dict[str, Any]],
    ) -> SkillCoachEvidence:
        """Build one redacted evidence card from a proposal and trajectories."""
        cell = str(proposal.get("cell") or "")
        skill_id = str(proposal.get("skill_id") or proposal.get("proposal_id") or "")
        proposal_id = str(proposal.get("proposal_id") or skill_id)
        tags = _parse_tags(proposal.get("tags"))
        scope = str(proposal.get("scope") or "Project")
        preconditions = str(proposal.get("precondition") or proposal.get("preconditions") or "")
        procedure = str(proposal.get("procedure") or "")
        success_criteria = str(
            proposal.get("success_criterion") or proposal.get("success_criteria") or ""
        )

        matching = [
            t
            for t in trajectories
            if str(t.get("cell_origin") or t.get("cell") or "") == cell
            and _tags_apply(tags, _parse_tags(t.get("tags")))
        ]
        support_count = sum(1 for t in matching if t.get("outcome") == "success")
        hurt_count = sum(1 for t in matching if t.get("outcome") in {"failure", "partial"})
        neutral_count = max(len(matching) - support_count - hurt_count, 0)
        false_apply_count = sum(1 for t in matching if t.get("outcome") == "failure")
        source_trajectory_ids = _source_trajectory_ids(proposal, matching)
        findings = scan_clear_customer_data(
            proposal_id,
            skill_id,
            cell,
            scope,
            *tags,
            *source_trajectory_ids,
            preconditions,
            procedure,
            success_criteria,
        )
        redaction_status = "failed" if findings else "passed"

        if findings:
            status = "rejected"
            decision_reason = "rejected: proposal text contains clear customer-data markers"
            proposal_id = _stable_id("redacted-proposal", proposal_id, skill_id, cell)
            skill_id = _stable_id("redacted-skill", skill_id, proposal_id, cell)
            cell = _stable_id("redacted-cell", cell)
            tags = []
            scope = "Project"
            source_trajectory_ids = []
            preconditions = _REDACTED_TEXT
            procedure = _REDACTED_TEXT
            success_criteria = _REDACTED_TEXT
        elif hurt_count > 0 or false_apply_count > 0:
            status = "rejected"
            decision_reason = "rejected: historical matching trajectories include harm"
        elif support_count >= self._min_support:
            status = "shadow_eligible"
            decision_reason = "eligible for shadow mode: enough clean historical support"
        else:
            status = "proposed"
            decision_reason = "proposed: clean but below support threshold"

        card = SkillCoachEvidence(
            proposal_id=_bounded_text(proposal_id, "unknown-proposal", 128),
            skill_id=_bounded_text(skill_id, "unknown-skill", 128),
            cell=_bounded_text(cell, "unknown-cell", 64),
            tags=tags,
            scope=_bounded_text(scope, "Project", 128),
            status=status,
            source_trajectory_ids=source_trajectory_ids,
            preconditions=_bounded_text(preconditions, "unspecified precondition", 1000),
            procedure=_bounded_text(procedure, "unspecified procedure", 4000),
            success_criteria=_bounded_text(
                success_criteria,
                "unspecified success criteria",
                1000,
            ),
            confidence=_bounded_confidence(proposal.get("confidence")),
            redaction_status=redaction_status,
            redaction_findings=sorted(set(findings)),
            support_count=support_count,
            hurt_count=hurt_count,
            false_apply_count=false_apply_count,
            neutral_count=neutral_count,
            history_sample_size=len(matching),
            decision_reason=decision_reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        leaked_findings = scan_clear_customer_data(card.model_dump_json())
        if leaked_findings:
            all_findings = sorted(set(findings + leaked_findings))
            return _fully_redacted_card(
                card=card,
                findings=all_findings,
                reason="rejected: serialized evidence card contains customer-data markers",
            )
        return card

    def evaluate_proposals(
        self,
        proposals: list[dict[str, Any]],
        trajectories: list[dict[str, Any]] | None = None,
    ) -> list[SkillCoachEvidence]:
        """Evaluate many proposals with one trajectory scan."""
        trajectory_rows = trajectories if trajectories is not None else self.fetch_trajectories()
        cards: list[SkillCoachEvidence] = []
        for index, proposal in enumerate(proposals, start=1):
            try:
                cards.append(self.evaluate_proposal(proposal, trajectory_rows))
            except (TypeError, ValueError, ValidationError):
                logger.warning("skip invalid skill-creation proposal at index=%d", index)
        return cards

    def read_proposals(self) -> list[dict[str, Any]]:
        """Read proposal JSONL emitted by the trajectory aggregator."""
        return _read_jsonl(self._proposals_path, "skill-creation proposal")

    def fetch_trajectories(self) -> list[dict[str, Any]]:
        """Read active trajectory rows from the shared Genome SQLite database."""
        if not os.path.exists(self._db_path):
            return []
        today = datetime.now(timezone.utc).date().isoformat()
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT id, cell_origin, type, outcome, procedure, tags,
                          valid_from, valid_to, confidence
                   FROM genome
                   WHERE type='trajectory' AND (valid_to IS NULL OR valid_to > ?)""",
                (today,),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def write_evidence(self, cards: list[SkillCoachEvidence]) -> None:
        """Write evidence cards as JSONL outside the repo."""
        os.makedirs(os.path.dirname(self._evidence_path) or ".", exist_ok=True)
        with open(self._evidence_path, "w", encoding="utf-8") as fh:
            for card in cards:
                fh.write(json.dumps(card.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def creation_proposals(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read redacted Skill Coach evidence cards."""
        rows = _read_jsonl(self._evidence_path, "skill-coach evidence")
        cards: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            try:
                card = SkillCoachEvidence.model_validate(row)
            except ValidationError:
                logger.warning("skip invalid skill-coach evidence row at index=%d", index)
                continue
            if scan_clear_customer_data(card.model_dump_json()):
                logger.warning("skip unsafe skill-coach evidence row at index=%d", index)
                continue
            payload = card.model_dump(mode="json")
            if status and payload.get("status") != status:
                continue
            cards.append(payload)
            if len(cards) >= limit:
                break
        return cards


def _read_jsonl(path: str, label: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skip malformed %s line at line=%d", label, line_number)
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def _parse_tags(tags_field: Any) -> list[str]:
    if isinstance(tags_field, list):
        return sorted({str(t) for t in tags_field if str(t)})
    if isinstance(tags_field, str) and tags_field:
        try:
            parsed = json.loads(tags_field)
        except json.JSONDecodeError:
            return [tags_field]
        if isinstance(parsed, list):
            return sorted({str(t) for t in parsed if str(t)})
    return []


def _tags_apply(proposal_tags: list[str], trajectory_tags: list[str]) -> bool:
    if not proposal_tags:
        return True
    return set(proposal_tags).issubset(set(trajectory_tags))


def _source_trajectory_ids(
    proposal: dict[str, Any],
    matching: list[dict[str, Any]],
) -> list[str]:
    matching_ids: list[str] = []
    matching_id_set: set[str] = set()
    for row in matching:
        raw_id = row.get("id") or row.get("trajectory_id")
        if raw_id:
            trajectory_id = str(raw_id)
            matching_ids.append(trajectory_id)
            matching_id_set.add(trajectory_id)

    explicit = proposal.get("source_trajectory_ids") or proposal.get("example_trajectory_ids")
    if isinstance(explicit, list):
        candidates = [str(i) for i in explicit if str(i) in matching_id_set]
    else:
        candidates = matching_ids

    ids: list[str] = []
    seen: set[str] = set()
    for trajectory_id in candidates:
        if trajectory_id in seen or scan_clear_customer_data(trajectory_id):
            continue
        seen.add(trajectory_id)
        ids.append(trajectory_id)
        if len(ids) >= _MAX_SOURCE_TRAJECTORY_IDS:
            break
    return ids


def _bounded_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.5
    return max(0.0, min(confidence, 0.5))


def _bounded_text(value: str, fallback: str, max_length: int) -> str:
    text = str(value or "").strip() or fallback
    return text[:max_length]


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\n".join(str(p) for p in parts if p is not None)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _fully_redacted_card(
    card: SkillCoachEvidence,
    findings: list[str],
    reason: str,
) -> SkillCoachEvidence:
    digest_source = f"{card.proposal_id}\n{card.skill_id}\n{card.cell}"
    return SkillCoachEvidence(
        proposal_id=_stable_id("redacted-proposal", digest_source),
        skill_id=_stable_id("redacted-skill", digest_source),
        cell=_stable_id("redacted-cell", digest_source),
        tags=[],
        scope="Project",
        status="rejected",
        source_trajectory_ids=[],
        preconditions=_REDACTED_TEXT,
        procedure=_REDACTED_TEXT,
        success_criteria=_REDACTED_TEXT,
        confidence=min(card.confidence, 0.5),
        redaction_status="failed",
        redaction_findings=sorted(set(findings)),
        support_count=0,
        hurt_count=0,
        false_apply_count=0,
        neutral_count=0,
        history_sample_size=0,
        decision_reason=reason,
        created_at=card.created_at,
    )
