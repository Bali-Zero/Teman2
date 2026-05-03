"""Compute causal attribution for a pass->fail transition between two commits.

This module is the heart of the harness. Given a previous snapshot, a current
snapshot, and the replay results on both, it produces a `CausalDiff` per query
that classifies the change into one of seven `RootCause` categories using a
heuristic decision table (documented in the plan file). The classification is
intentionally conservative: when nothing in-scope has moved, we return
`UNKNOWN` rather than guess. The decision table is applied in a fixed order so
the classification is stable across runs.
"""

from __future__ import annotations

from ._types import (
    CausalDiff,
    CommitSnapshot,
    QueryResult,
    RetrievedChunk,
    RootCause,
)


def _retrieval_movement(
    prev: list[RetrievedChunk], curr: list[RetrievedChunk]
) -> list[dict]:
    """Return a sorted list of dicts describing how docs moved in/out of top-k."""
    prev_map = {c.doc_path: c for c in prev}
    curr_map = {c.doc_path: c for c in curr}
    all_paths = sorted(set(prev_map) | set(curr_map))
    out: list[dict] = []
    for p in all_paths:
        pc = prev_map.get(p)
        cc = curr_map.get(p)
        if pc and cc and pc.rank == cc.rank and abs(pc.score - cc.score) < 1e-6:
            continue  # no movement, skip
        out.append(
            {
                "doc_path": p,
                "prev_rank": pc.rank if pc else None,
                "curr_rank": cc.rank if cc else None,
                "prev_score": round(pc.score, 6) if pc else None,
                "curr_score": round(cc.score, 6) if cc else None,
            }
        )
    # Stable sort by doc_path for determinism.
    out.sort(key=lambda d: d["doc_path"])
    return out


def _claim_delta(prev: QueryResult, curr: QueryResult) -> dict:
    prev_set = set(prev.covered_keywords)
    curr_set = set(curr.covered_keywords)
    return {
        "prev_covered": sorted(prev_set),
        "curr_covered": sorted(curr_set),
        "missing_now": sorted(prev_set - curr_set),
        "regained": sorted(curr_set - prev_set),
    }


def _root_cause(
    prev_res: QueryResult,
    curr_res: QueryResult,
    curr_snapshot: CommitSnapshot,
    retrieval_delta: list[dict],
    claim_delta: dict,
) -> RootCause:
    """Apply the fixed decision table.

    The order matters and is documented in the plan. We only attribute a root
    cause to a true pass->fail transition; everything else returns UNKNOWN.
    """
    if not (prev_res.passed and not curr_res.passed):
        return RootCause.UNKNOWN

    missing_now = set(claim_delta.get("missing_now", []))
    removed_kb = set(curr_snapshot.removed_kb_files)
    changed_kb = set(curr_snapshot.changed_kb_files)
    added_kb = set(curr_snapshot.added_kb_files)

    # 1. KB_REMOVED — a supporting doc was deleted in this commit and a keyword
    # that used to be covered no longer is.
    if removed_kb and missing_now:
        for mv in retrieval_delta:
            if mv["curr_rank"] is None and mv["doc_path"] in removed_kb:
                return RootCause.KB_REMOVED

    # 2. KB_CONTENT_CHANGED — a doc still in top-k (or recently dropped) was
    # edited in this commit, and coverage fell.
    if changed_kb and missing_now:
        touched_paths = {
            mv["doc_path"] for mv in retrieval_delta if mv["doc_path"] in changed_kb
        }
        if touched_paths:
            return RootCause.KB_CONTENT_CHANGED
        # Even if no retrieval movement on this doc, a content edit that
        # removed a keyword still counts.
        for kw in missing_now:
            for f in changed_kb:
                if kw.lower() in f.lower():
                    return RootCause.KB_CONTENT_CHANGED

    # 3. KB_ADDED_NOISE — a new doc appeared in top-k this commit, pushing out
    # the previously-supporting chunk.
    if added_kb:
        for mv in retrieval_delta:
            if mv["prev_rank"] is None and mv["doc_path"] in added_kb:
                return RootCause.KB_ADDED_NOISE

    # 4. PROMPT_CHANGED
    if curr_snapshot.changed_prompts:
        return RootCause.PROMPT_CHANGED

    # 5. RETRIEVER_CONFIG_CHANGED
    if curr_snapshot.changed_retriever_cfg:
        return RootCause.RETRIEVER_CONFIG_CHANGED

    # 6. LLM_CONFIG_CHANGED
    if curr_snapshot.changed_llm_cfg:
        return RootCause.LLM_CONFIG_CHANGED

    return RootCause.UNKNOWN


def diff_snapshots(
    prev_snapshot: CommitSnapshot,
    curr_snapshot: CommitSnapshot,
    prev_results: list[QueryResult],
    curr_results: list[QueryResult],
) -> list[CausalDiff]:
    """Join the two result sets on query_id and produce a CausalDiff per query.

    Queries present in only one side are skipped (the eval set should be
    identical across commits by contract; any asymmetry indicates a bug
    upstream).
    """
    prev_by_id = {r.query_id: r for r in prev_results}
    curr_by_id = {r.query_id: r for r in curr_results}
    query_ids = sorted(set(prev_by_id.keys()) & set(curr_by_id.keys()))
    diffs: list[CausalDiff] = []
    for qid in query_ids:
        p = prev_by_id[qid]
        c = curr_by_id[qid]
        retrieval_delta = _retrieval_movement(p.top_k, c.top_k)
        claim_delta = _claim_delta(p, c)
        kb_summary = {
            "added": sorted(curr_snapshot.added_kb_files),
            "removed": sorted(curr_snapshot.removed_kb_files),
            "changed": sorted(curr_snapshot.changed_kb_files),
        }
        cause = _root_cause(p, c, curr_snapshot, retrieval_delta, claim_delta)
        diffs.append(
            CausalDiff(
                query_id=qid,
                prev_sha=prev_snapshot.sha,
                curr_sha=curr_snapshot.sha,
                prev_passed=p.passed,
                curr_passed=c.passed,
                retrieval_delta=retrieval_delta,
                prompt_delta=sorted(curr_snapshot.changed_prompts),
                retriever_cfg_delta=sorted(curr_snapshot.changed_retriever_cfg),
                llm_cfg_delta=sorted(curr_snapshot.changed_llm_cfg),
                kb_delta_summary=kb_summary,
                claim_delta=claim_delta,
                root_cause=cause,
            )
        )
    return diffs
