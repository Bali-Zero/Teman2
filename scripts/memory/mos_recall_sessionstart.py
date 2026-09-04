#!/usr/bin/env python3
"""LAYER 2 — mos_recall_sessionstart.py (production, wired to SessionStart).

Generative-Agents-style ("Park et al. 2023") retrieval: score = recency x
importance x relevance, print the top-k as one-line claims, print NOTHING
when nothing is pertinent. stdlib only; well under 2s cold over ~1800 files.

MEMDIR is derived, not hardcoded: ``~/.claude/projects/<slug>/memory`` where
``<slug>`` is the absolute project path with every ``/`` -> ``-`` (e.g.
``/Users/balizero/nuzantara`` -> ``-Users-balizero-nuzantara``), from
``$CLAUDE_PROJECT_DIR`` (fallback: `git rev-parse --show-toplevel`) +
``Path.home()`` — never assumed, since Pro/Mini check out at a different
absolute path. Missing dir -> exit 0 silently (unwired machine, not a break).

Index cache: ``<memdir>/.recall_cache.json``, keyed by path, entries rebuilt
only on mtime change. Lives INSIDE memdir on purpose — `mem save` already
writes there constantly, so a derived index next to its corpus can't drift.

PII boundary: the printed line is built ONLY from frontmatter `description`
(truncated 120 chars) and passed through `redact()` before stdout. Body text
feeds the relevance index only and is NEVER printed.

Fail-open: any exception in `main()` -> quiet exit 0, nothing printed.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CACHE_FILENAME = ".recall_cache.json"
BODY_PREVIEW_CHARS = 400
CLAIM_MAX_CHARS = 120
OUTPUT_CAP_BYTES = 1500
HALF_LIFE_DAYS = 30.0
RECENCY_LAMBDA = math.log(2) / HALF_LIFE_DAYS
DEFAULT_TOPK = 6
DEFAULT_RELEVANCE_THRESHOLD = 0.35  # BM25-like score; tuned against the 12-scenario eval set
BM25_K1 = 1.5
BM25_B = 0.75
GIT_TIMEOUT_SECONDS = 1.5
RUNTIME_BUDGET_SECONDS = 2.0  # advisory only — nothing here hard-aborts mid-run
MEMORY_MD_WARN_BYTES = 2560
HEADER_LINE = "🧠 memoria pertinente (top-6, mem recall per altro):"
MEMORY_MD_WARN_TEMPLATE = (
    "⚠️ MEMORY.md {bytes}B > 2560B — è un nucleo, non un indice (catalogo: MEMORY_INDEX.md)"
)

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DATE_IN_NAME_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})(?:\.md)?$")
TOKEN_RE = re.compile(r"[a-z0-9]+")

KNOWN_PREFIXES = {
    "discovery", "decision", "lesson", "lessons", "fact", "project",
    "unresolved", "reference", "ops", "feedback",
}

IMPORTANCE_BY_TYPE = {
    "feedback": 1.0,
    "decision": 1.0,
    "lesson": 1.0,
    "lessons": 1.0,
    "project": 0.9,
    "discovery": 0.8,
    "fact": 0.6,
    "reference": 0.6,
}
IMPORTANCE_DEFAULT = 0.5

STOPWORDS_EN = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "been", "with", "at", "by", "from", "as",
    "that", "this", "it", "its", "into", "than", "then", "not", "no",
    "so", "do", "does", "did", "has", "have", "had", "but", "if", "when",
    "which", "who", "what", "how", "never", "always", "only", "one",
}
STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a",
    "da", "in", "con", "su", "per", "tra", "fra", "e", "o", "che", "chi",
    "cui", "non", "mai", "sempre", "solo", "come", "quando", "dove",
    "questo", "questa", "questi", "queste", "del", "della", "dei",
    "delle", "al", "alla", "ai", "alle", "dal", "dalla", "dai", "dalle",
    "nel", "nella", "nei", "nelle", "sul", "sulla", "sui", "sulle",
    "è", "sono", "era", "erano", "essere", "stato", "stata",
}
STOPWORDS = STOPWORDS_EN | STOPWORDS_IT

# PII redaction (transformation). Duplicated (not imported) from the sibling
# Layer-3 script memory_index_build.py — separate PRs, keep in sync by hand.
REDACT_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REDACT_PHONE_RE = re.compile(r"\+(?:62|39)[\s.-]?\d[\d\s.-]{6,}\d")
REDACT_ID_RE = re.compile(r"\b(?:passport|KTP)\b\D{0,10}\d[\d\s-]*", re.IGNORECASE)
REDACT_DIGITRUN_RE = re.compile(r"(?<!\d)\d{10,15}(?!\d)")


def redact(text: str) -> str:
    """Replace PII shapes with placeholders (email/id/phone before the
    generic digit-run so the specific patterns consume their digits first)."""
    if not text:
        return text
    text = REDACT_EMAIL_RE.sub("<email>", text)
    text = REDACT_ID_RE.sub("<id>", text)
    text = REDACT_PHONE_RE.sub("<num>", text)
    text = REDACT_DIGITRUN_RE.sub("<num>", text)
    return text


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = text.replace("_", " ").replace("-", " ")
    toks = TOKEN_RE.findall(text)
    return [t for t in toks if t not in STOPWORDS and len(t) >= 2]


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    out: dict = {}
    metadata: dict = {}
    in_metadata = False
    for line in block.split("\n"):
        if not line.strip():
            continue
        if line.startswith("metadata:"):
            in_metadata = True
            continue
        if in_metadata:
            if line.startswith((" ", "\t")):
                kv = line.strip()
                if ":" in kv:
                    k, _, v = kv.partition(":")
                    metadata[k.strip()] = _unquote(v.strip())
                continue
            else:
                in_metadata = False
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = _unquote(v.strip())
    out["metadata"] = metadata
    return out


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] in ('"', "'"):
        return v[1:-1]
    return v


def date_key_from_name(filename: str) -> str | None:
    m = DATE_IN_NAME_RE.search(filename.rsplit(".md", 1)[0] + ".md")
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def classify_type(filename: str, fm_type: str | None) -> str:
    prefix = filename.split("_", 1)[0]
    if prefix in KNOWN_PREFIXES:
        return prefix
    if fm_type:
        return fm_type
    return "misc"


def load_cache(cache_path: str) -> dict:
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_cache(cache_path: str, cache: dict) -> None:
    tmp = cache_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, cache_path)
    except OSError:
        pass  # cache is a pure speed optimization; a write failure is not fatal


def build_or_refresh_index(memdir: str, cache_path: str, use_cache: bool = True) -> tuple[dict, dict]:
    """Returns (index, stats). index: {path: entry}."""
    files = sorted(glob.glob(os.path.join(memdir, "*.md")))
    cache = load_cache(cache_path) if use_cache else {}
    index: dict = {}
    rebuilt = 0
    reused = 0

    for path in files:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        cached = cache.get(path)
        if cached and cached.get("mtime") == mtime:
            index[path] = cached
            reused += 1
            continue

        rebuilt += 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read(4096)  # frontmatter + preview only, never the whole file
        except (OSError, UnicodeDecodeError):
            continue
        fm = parse_frontmatter(text)
        name = fm.get("name") or os.path.basename(path)[:-3]
        description = (fm.get("description") or "").strip()
        fm_type = (fm.get("metadata") or {}).get("type")
        fn = os.path.basename(path)
        typ = classify_type(fn, fm_type)
        dkey = date_key_from_name(fn)

        body = FRONTMATTER_RE.sub("", text, count=1)[:BODY_PREVIEW_CHARS]
        indexed_text = f"{name} {description} {body}"

        entry = {
            "mtime": mtime,
            "path": path,
            "filename": fn,
            "name": name,
            "description": description,
            "type": typ,
            "date_key": dkey,
            "indexed_text": indexed_text,
        }
        index[path] = entry

    if use_cache and rebuilt > 0:
        save_cache(cache_path, index)

    stats = {"file_count": len(index), "rebuilt": rebuilt, "reused": reused}
    return index, stats


def recency_score(entry: dict, now_ts: float) -> float:
    dkey = entry.get("date_key")
    if dkey:
        try:
            t = time.mktime(time.strptime(dkey, "%Y-%m-%d"))
        except ValueError:
            t = entry["mtime"]
    else:
        t = entry["mtime"]
    age_days = max(0.0, (now_ts - t) / 86400.0)
    return math.exp(-RECENCY_LAMBDA * age_days)


def importance_score(entry: dict) -> float:
    return IMPORTANCE_BY_TYPE.get(entry.get("type"), IMPORTANCE_DEFAULT)


def compute_doc_freq(index: dict) -> tuple[dict, dict, float]:
    """Returns (doc_tokens_cache, df, avgdl) computed once per query."""
    doc_tokens: dict = {}
    df: dict = {}
    total_len = 0
    for path, entry in index.items():
        toks = tokenize(entry["indexed_text"])
        doc_tokens[path] = toks
        total_len += len(toks)
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    avgdl = (total_len / len(index)) if index else 1.0
    return doc_tokens, df, avgdl


def bm25_relevance(query_tokens: list[str], doc_tokens: list[str], df: dict, n_docs: int, avgdl: float) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    tf: dict = {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    for qt in set(query_tokens):
        f = tf.get(qt, 0)
        if f == 0:
            continue
        n_qt = df.get(qt, 0)
        idf = math.log((n_docs - n_qt + 0.5) / (n_qt + 0.5) + 1)
        denom = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl)
        score += idf * (f * (BM25_K1 + 1)) / denom
    return score


# ---------------------------------------------------------------------------
# Context derivation: memdir slug, git branch/commits/status.
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def git_toplevel(cwd: str) -> str | None:
    out = _git(["rev-parse", "--show-toplevel"], cwd)
    return out or None


def resolve_memdir(cwd: str | None = None, home: str | None = None) -> str | None:
    """~/.claude/projects/<slug>/memory, <slug> = abs project dir, '/' -> '-'.
    `cwd` defaults to $CLAUDE_PROJECT_DIR (fallback: git toplevel of cwd);
    `home` overrides Path.home() (test-only)."""
    project_dir = cwd or os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        project_dir = git_toplevel(os.getcwd())
    if not project_dir:
        return None
    abs_dir = os.path.abspath(project_dir)
    slug = abs_dir.replace(os.sep, "-")
    home_path = Path(home) if home else Path.home()
    return str(home_path / ".claude" / "projects" / slug / "memory")


def build_context_query(cwd: str) -> str:
    """cwd basename + branch + last 8 commit subjects + changed file names.
    Every git call is best-effort, silently empty on failure."""
    parts = [os.path.basename(cwd.rstrip("/"))] if cwd else []

    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if branch:
        parts.append(branch)

    commits = _git(["log", "-8", "--format=%s"], cwd)
    if commits:
        parts.append(commits)

    status = _git(["status", "--porcelain"], cwd)
    if status:
        names = []
        for line in status.splitlines():
            if len(line) > 3:
                path = line[3:].split(" -> ")[-1].strip()
                names.append(os.path.basename(path))
        if names:
            parts.append(" ".join(names))

    return " ".join(parts)


def recall(
    memdir: str,
    cache_path: str,
    query: str,
    topk: int = DEFAULT_TOPK,
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    use_cache: bool = True,
) -> tuple[list[dict], dict]:
    t0 = time.time()
    index, idx_stats = build_or_refresh_index(memdir, cache_path, use_cache=use_cache)
    doc_tokens, df, avgdl = compute_doc_freq(index)
    n_docs = len(index)
    now_ts = time.time()
    q_tokens = tokenize(query)

    scored = []
    for path, entry in index.items():
        rel = bm25_relevance(q_tokens, doc_tokens[path], df, n_docs, avgdl)
        rec = recency_score(entry, now_ts)
        imp = importance_score(entry)
        combined = rec * imp * rel
        scored.append((combined, rel, rec, imp, entry))

    scored.sort(key=lambda t: t[0], reverse=True)
    best_rel = scored[0][1] if scored else 0.0

    elapsed = time.time() - t0
    stats = {
        **idx_stats,
        "elapsed_seconds": round(elapsed, 4),
        "best_relevance": round(best_rel, 4),
        "threshold": threshold,
        "query": query,
        "query_tokens": q_tokens,
    }

    if best_rel < threshold:
        return [], stats

    top = scored[:topk]
    results = [
        {
            "combined": round(c, 4),
            "relevance": round(r, 4),
            "recency": round(rec, 4),
            "importance": imp,
            "filename": e["filename"],
            "description": e["description"],
        }
        for c, r, rec, imp, e in top
    ]
    return results, stats


def memory_md_warning(memdir: str) -> str | None:
    path = os.path.join(memdir, "MEMORY.md")
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size > MEMORY_MD_WARN_BYTES:
        return MEMORY_MD_WARN_TEMPLATE.format(bytes=size)
    return None


def format_output(results: list[dict], warning: str | None = None, cap_bytes: int = OUTPUT_CAP_BYTES) -> str:
    """Header + redacted top-k claims + optional MEMORY.md-oversize warning,
    all within cap_bytes total (UTF-8 bytes, newline-joined)."""
    reserve = len(warning.encode("utf-8")) + 1 if warning else 0
    budget = max(cap_bytes - reserve, 0)

    lines: list[str] = []
    total_bytes = 0
    if results:
        header_bytes = len(HEADER_LINE.encode("utf-8")) + 1
        if header_bytes <= budget:
            lines.append(HEADER_LINE)
            total_bytes += header_bytes
        for r in results:
            claim = redact(r["description"] or r["filename"])
            if len(claim) > CLAIM_MAX_CHARS:
                claim = claim[: CLAIM_MAX_CHARS - 1].rstrip() + "…"
            line = f"- {claim} → {r['filename']}"
            line_bytes = len(line.encode("utf-8")) + 1
            if total_bytes + line_bytes > budget:
                break
            lines.append(line)
            total_bytes += line_bytes

    if warning:
        lines.append(warning)

    return "\n".join(lines)


def main() -> int:
    try:
        ap = argparse.ArgumentParser()
        ap.add_argument("--memdir", default=None)
        ap.add_argument("--cache-path", default=None)
        ap.add_argument("--no-cache", action="store_true")
        ap.add_argument("--query", default=None)
        ap.add_argument("--cwd", default=None)
        ap.add_argument("--topk", type=int, default=DEFAULT_TOPK)
        ap.add_argument("--threshold", type=float, default=DEFAULT_RELEVANCE_THRESHOLD)
        args = ap.parse_args()

        cwd = args.cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        memdir = args.memdir or resolve_memdir(cwd=cwd)
        if not memdir or not os.path.isdir(memdir):
            return 0  # not wired on this machine — silent, never the reason a session breaks

        cache_path = args.cache_path or os.path.join(memdir, CACHE_FILENAME)
        query = args.query if args.query else build_context_query(cwd)

        results, _stats = recall(
            memdir, cache_path, query,
            topk=args.topk, threshold=args.threshold, use_cache=not args.no_cache,
        )
        warning = memory_md_warning(memdir)
        out = format_output(results, warning=warning)
        if out:
            print(out)
        return 0
    except Exception:
        # Fail-open contract: a receptor must never break a session.
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
