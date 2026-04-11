"""Replay a frozen eval set against each commit using git-blob-reconstructed KB.

Given a `CommitSnapshot`, we (a) materialize all text files under the configured
KB root at that commit into a cache directory, (b) build a deterministic
`MockRetriever` over them, and (c) run every eval row through the retriever,
producing a `QueryResult` per (commit, query) cell. Binary files are skipped
with a warning. No LLM is invoked by default; an `--with-ollama` flag in the
CLI can extend this later, but the causal categorization never depends on LLM
output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ._gitblob import is_binary, ls_tree, show_blob
from ._retriever import MockRetriever, _tokenize
from ._types import CommitSnapshot, QueryResult, RetrievedChunk


DEFAULT_CACHE_ROOT = Path("/tmp/causal-kb-cache")
MAX_BLOB_BYTES = 256 * 1024  # 256 KiB — skip huge artifacts, they're never prose chunks


@dataclass
class EvalRow:
    query_id: str
    query: str
    expected_keywords: list[str]


def load_eval_set(path: str | Path) -> list[EvalRow]:
    """Read a JSONL file of `{query_id, query, expected_keywords}` rows."""
    p = Path(path)
    rows: list[EvalRow] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rows.append(
                EvalRow(
                    query_id=str(obj["query_id"]),
                    query=str(obj["query"]),
                    expected_keywords=[str(k) for k in obj.get("expected_keywords", [])],
                )
            )
    # Sort by query_id so replay order is deterministic regardless of file order.
    rows.sort(key=lambda r: r.query_id)
    return rows


def reconstruct_kb(
    sha: str,
    repo: str,
    kb_root: str,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> tuple[dict[str, str], list[str]]:
    """Return `{relative_path: text}` for all text files under `kb_root` at `sha`.

    Side effect: each text blob is written to
    `/tmp/causal-kb-cache/{sha}/{relative_path}` so callers can inspect raw state
    after the fact. Binary files are counted into the `warnings` list as
    `"binary_skipped:<path>"`, matching what the final JSON report emits.
    """
    cache_root = Path(cache_root)
    sha_dir = cache_root / sha
    sha_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    docs: dict[str, str] = {}

    entries = ls_tree(sha, repo, kb_root)
    for e in entries:
        path = e["path"]
        size = e["size_bytes"]
        if size > MAX_BLOB_BYTES:
            warnings.append(f"oversize_skipped:{path}")
            continue
        blob = show_blob(sha, path, repo)
        if blob is None:
            warnings.append(f"missing_blob:{path}")
            continue
        if is_binary(blob):
            warnings.append(f"binary_skipped:{path}")
            continue
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            warnings.append(f"undecodable:{path}")
            continue
        rel = path
        docs[rel] = text
        # Write to cache (best-effort — don't fail the run on a disk error).
        try:
            target = sha_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except OSError:
            warnings.append(f"cache_write_failed:{path}")
    return docs, sorted(warnings)


def run_eval_set(
    snapshot: CommitSnapshot,
    eval_rows: list[EvalRow],
    repo: str,
    kb_root: str,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    top_k: int = 5,
    coverage_pass_threshold: float = 0.5,
) -> tuple[list[QueryResult], list[str]]:
    """Replay every `eval_row` against the KB reconstructed for `snapshot`.

    Returns `(results, warnings)`. `warnings` is empty for a clean run.
    """
    docs, warnings = reconstruct_kb(snapshot.sha, repo, kb_root, cache_root)
    retriever = MockRetriever(docs)
    results: list[QueryResult] = []
    for row in eval_rows:
        hits = retriever.retrieve(row.query, top_k=top_k)
        covered = _covered_keywords(row.expected_keywords, hits)
        coverage = (len(covered) / len(row.expected_keywords)) if row.expected_keywords else 0.0
        passed = coverage >= coverage_pass_threshold
        results.append(
            QueryResult(
                commit_sha=snapshot.sha,
                query_id=row.query_id,
                query=row.query,
                expected_keywords=row.expected_keywords,
                top_k=hits,
                covered_keywords=covered,
                coverage=coverage,
                passed=passed,
            )
        )
    return results, warnings


def _covered_keywords(
    expected: list[str], hits: list[RetrievedChunk]
) -> list[str]:
    """Return the subset of `expected` keywords present in any retrieved snippet.

    Matching is done on the tokenized bag of words to avoid punctuation and
    casing noise.
    """
    if not expected or not hits:
        return []
    bag: set[str] = set()
    for h in hits:
        bag.update(_tokenize(h.snippet))
    covered: list[str] = []
    for kw in expected:
        kw_tokens = _tokenize(kw)
        if kw_tokens and all(t in bag for t in kw_tokens):
            covered.append(kw)
    return sorted(covered)
