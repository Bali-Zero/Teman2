"""Dataclasses and enums for the causal regression harness.

Kept in a dedicated module to avoid circular imports between the walker, the
replay engine, the diff engine, and the report generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RootCause(str, Enum):
    """The seven root-cause categories a pass->fail transition can fall into."""

    KB_CONTENT_CHANGED = "KB_CONTENT_CHANGED"
    KB_REMOVED = "KB_REMOVED"
    KB_ADDED_NOISE = "KB_ADDED_NOISE"
    PROMPT_CHANGED = "PROMPT_CHANGED"
    RETRIEVER_CONFIG_CHANGED = "RETRIEVER_CONFIG_CHANGED"
    LLM_CONFIG_CHANGED = "LLM_CONFIG_CHANGED"
    UNKNOWN = "UNKNOWN"


ROOT_CAUSE_COLORS: dict[str, str] = {
    # Deterministic, web-safe, enough contrast for a flamegraph cell.
    RootCause.KB_CONTENT_CHANGED.value: "#e67e22",
    RootCause.KB_REMOVED.value: "#c0392b",
    RootCause.KB_ADDED_NOISE.value: "#d35400",
    RootCause.PROMPT_CHANGED.value: "#8e44ad",
    RootCause.RETRIEVER_CONFIG_CHANGED.value: "#2980b9",
    RootCause.LLM_CONFIG_CHANGED.value: "#16a085",
    RootCause.UNKNOWN.value: "#7f8c8d",
}


@dataclass
class CommitSnapshot:
    """A single commit view: SHA plus categorized file deltas vs its parent."""

    sha: str
    short_sha: str
    parent_sha: str | None
    subject: str
    order_index: int  # position within the walked range, oldest-first
    changed_kb_files: list[str] = field(default_factory=list)
    added_kb_files: list[str] = field(default_factory=list)
    removed_kb_files: list[str] = field(default_factory=list)
    changed_prompts: list[str] = field(default_factory=list)
    changed_llm_cfg: list[str] = field(default_factory=list)
    changed_retriever_cfg: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "parent_sha": self.parent_sha,
            "subject": self.subject,
            "order_index": self.order_index,
            "changed_kb_files": sorted(self.changed_kb_files),
            "added_kb_files": sorted(self.added_kb_files),
            "removed_kb_files": sorted(self.removed_kb_files),
            "changed_prompts": sorted(self.changed_prompts),
            "changed_llm_cfg": sorted(self.changed_llm_cfg),
            "changed_retriever_cfg": sorted(self.changed_retriever_cfg),
            "warnings": sorted(self.warnings),
        }


@dataclass
class RetrievedChunk:
    """One hit from the deterministic mock retriever."""

    doc_path: str
    score: float
    rank: int
    snippet: str

    def to_dict(self) -> dict:
        return {
            "doc_path": self.doc_path,
            "score": round(self.score, 6),
            "rank": self.rank,
            "snippet": self.snippet,
        }


@dataclass
class QueryResult:
    """Replay outcome for one (commit, query) cell in the flamegraph."""

    commit_sha: str
    query_id: str
    query: str
    expected_keywords: list[str]
    top_k: list[RetrievedChunk]
    covered_keywords: list[str]
    coverage: float
    passed: bool

    def to_dict(self) -> dict:
        return {
            "commit_sha": self.commit_sha,
            "query_id": self.query_id,
            "query": self.query,
            "expected_keywords": sorted(self.expected_keywords),
            "top_k": [c.to_dict() for c in self.top_k],
            "covered_keywords": sorted(self.covered_keywords),
            "coverage": round(self.coverage, 6),
            "passed": self.passed,
        }


@dataclass
class CausalDiff:
    """Attribution output for a single (query, adjacent-commit-pair) transition."""

    query_id: str
    prev_sha: str
    curr_sha: str
    prev_passed: bool
    curr_passed: bool
    retrieval_delta: list[dict]  # pre-sorted list of doc movement dicts
    prompt_delta: list[str]
    retriever_cfg_delta: list[str]
    llm_cfg_delta: list[str]
    kb_delta_summary: dict
    claim_delta: dict
    root_cause: RootCause

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "prev_sha": self.prev_sha,
            "curr_sha": self.curr_sha,
            "prev_passed": self.prev_passed,
            "curr_passed": self.curr_passed,
            "retrieval_delta": self.retrieval_delta,
            "prompt_delta": sorted(self.prompt_delta),
            "retriever_cfg_delta": sorted(self.retriever_cfg_delta),
            "llm_cfg_delta": sorted(self.llm_cfg_delta),
            "kb_delta_summary": self.kb_delta_summary,
            "claim_delta": self.claim_delta,
            "root_cause": self.root_cause.value,
        }
