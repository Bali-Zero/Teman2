"""Walk a git range and produce a `CommitSnapshot` per commit, oldest-first.

The walker is the source of truth for "what changed at this commit". It bins
each changed file into one of four buckets (KB, prompts, LLM cfg, retriever
cfg) using regexes scoped to `apps/backend-rag/`. The downstream replay and
diff engines consume these lists but never re-read the git index themselves,
which keeps causal attribution deterministic.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._gitblob import changed_paths, commit_meta, resolve_range
from ._types import CommitSnapshot

# Path classification regexes. Compiled once for determinism and speed.
# Order matters only for human-readable reporting; categorization is independent.
_KB_RE = re.compile(r"(^|/)(apps/backend-rag/)?(backend/)?kb/|/kb/|packages/kb/")
_PROMPT_RE = re.compile(r"backend/prompts/|prompts/zantara_core|/zantara_core\.py$")
_LLM_CFG_RE = re.compile(
    r"backend/llm/|ollama_client\.py|/llm_config|\.yaml$.*llm|backend/core/config\.py"
)
_RETRIEVER_CFG_RE = re.compile(
    r"backend/services/rag/|hybrid_search|retriever_config|chunking|qdrant_service"
    r"|rrf|cross_encoder|reranker"
)

DEFAULT_PATH_FILTER = "apps/backend-rag/"


def _classify(path: str, status: str, snap: CommitSnapshot) -> None:
    """Drop `path` into the right bucket on `snap`."""
    is_added = status == "A"
    is_removed = status == "D"

    # KB bucket
    if _KB_RE.search(path):
        if is_added:
            snap.added_kb_files.append(path)
        elif is_removed:
            snap.removed_kb_files.append(path)
        else:
            snap.changed_kb_files.append(path)
        # A KB file can still ALSO touch retriever cfg via its name, so continue
        # checking the other buckets below.

    if _PROMPT_RE.search(path):
        snap.changed_prompts.append(path)

    if _LLM_CFG_RE.search(path):
        snap.changed_llm_cfg.append(path)

    if _RETRIEVER_CFG_RE.search(path):
        snap.changed_retriever_cfg.append(path)


def walk_range(
    range_expr: str,
    repo: str | Path,
    path_filter: str = DEFAULT_PATH_FILTER,
) -> list[CommitSnapshot]:
    """Return ordered `CommitSnapshot` objects for every commit in the range.

    Args:
        range_expr: any git rev range, e.g. `HEAD~30..HEAD`, `v1..v2`, a single SHA.
        repo: path to a git repo (worktree or bare is fine).
        path_filter: restrict to commits that touch this prefix. Empty string
            disables the filter (useful for synthetic test repos).

    The returned list is sorted oldest-first. Empty if no commits match.
    """
    repo_str = str(repo)
    pf = path_filter if path_filter else None
    shas = resolve_range(range_expr, repo_str, pf)
    snaps: list[CommitSnapshot] = []
    for idx, sha in enumerate(shas):
        meta = commit_meta(sha, repo_str)
        snap = CommitSnapshot(
            sha=meta["sha"],
            short_sha=meta["short_sha"],
            parent_sha=meta["parent_sha"],
            subject=meta["subject"],
            order_index=idx,
        )
        # Scope the name-status to the same path filter so we don't pollute
        # the snapshot with unrelated file moves.
        entries = changed_paths(sha, repo_str, pf)
        for e in entries:
            _classify(e["path"], e["status"], snap)
        # Deduplicate lists to keep the snapshot minimal and ordered.
        snap.changed_kb_files = sorted(set(snap.changed_kb_files))
        snap.added_kb_files = sorted(set(snap.added_kb_files))
        snap.removed_kb_files = sorted(set(snap.removed_kb_files))
        snap.changed_prompts = sorted(set(snap.changed_prompts))
        snap.changed_llm_cfg = sorted(set(snap.changed_llm_cfg))
        snap.changed_retriever_cfg = sorted(set(snap.changed_retriever_cfg))
        snaps.append(snap)
    return snaps
