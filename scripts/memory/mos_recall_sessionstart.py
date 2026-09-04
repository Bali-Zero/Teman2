#!/usr/bin/env python3
"""LAYER 2 — mos_recall_sessionstart.py (SessionStart recall hook).

score = recency x importance x BM25 relevance; prints top-k claims, silent
when nothing pertinent. MEMDIR = ~/.claude/projects/<slug>/memory (slug =
abs project dir, '/' -> '-'); missing in a worktree, so we retry against the
MAIN worktree via `git rev-parse --git-common-dir`. Only frontmatter
`description` is printed, through redact(). Fail-open: quiet exit 0.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

BODY_PREVIEW_CHARS, CLAIM_MAX_CHARS, OUTPUT_CAP_BYTES = 400, 120, 1500
CACHE_FILENAME, HALF_LIFE_DAYS, DEFAULT_TOPK = ".recall_cache.json", 30.0, 6
RECENCY_LAMBDA = math.log(2) / HALF_LIFE_DAYS
DEFAULT_RELEVANCE_THRESHOLD = 0.35  # BM25-like score, tuned against the 12-scenario eval set
BM25_K1, BM25_B = 1.5, 0.75
GIT_TIMEOUT_SECONDS, MEMORY_MD_WARN_BYTES = 1.5, 2560
HEADER_LINE = "🧠 memoria pertinente (top-6, mem recall per altro):"
MEMORY_MD_WARN_TEMPLATE = "⚠️ MEMORY.md {bytes}B > 2560B — è un nucleo, non un indice (catalogo: MEMORY_INDEX.md)"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DATE_IN_NAME_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})(?:\.md)?$")
TOKEN_RE = re.compile(r"[a-z0-9]+")
TOPLEVEL_KV_RE = re.compile(r"^(\w[\w]*):[ \t]*(.*)$", re.MULTILINE)
INDENTED_KV_RE = re.compile(r"^[ \t]+(\w[\w-]*):[ \t]*(.*)$", re.MULTILINE)
KNOWN_PREFIXES = {"discovery", "decision", "lesson", "lessons", "fact", "project", "unresolved", "reference", "ops", "feedback"}
IMPORTANCE_BY_TYPE = {"feedback": 1.0, "decision": 1.0, "lesson": 1.0, "lessons": 1.0, "project": 0.9, "discovery": 0.8, "fact": 0.6, "reference": 0.6}
IMPORTANCE_DEFAULT = 0.5

# EN + IT stopwords, kept as one whitespace-split string for density.
STOPWORDS = frozenset((
    "a an the and or of to in on for is are was were be been with at by from as that this it its "
    "into than then not no so do does did has have had but if when which who what how never always only one "
    "il lo la i gli le un uno una di a da in con su per tra fra e o che chi cui non mai sempre solo "
    "come quando dove questo questa questi queste del della dei delle al alla ai alle dal dalla dai dalle "
    "nel nella nei nelle sul sulla sui sulle è sono era erano essere stato stata"
).split())

# PII redaction (duplicated, not imported, from the sibling Layer-3 script).
REDACT_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REDACT_PHONE_RE = re.compile(r"\+(?:62|39)[\s.-]?\d[\d\s.-]{6,}\d")
REDACT_ID_RE = re.compile(r"\b(?:passport|KTP)\b\D{0,10}\d[\d\s-]*", re.IGNORECASE)
REDACT_DIGITRUN_RE = re.compile(r"(?<!\d)\d{10,15}(?!\d)")

def redact(text: str) -> str:
    if not text: return text
    text = REDACT_EMAIL_RE.sub("<email>", text)
    text = REDACT_ID_RE.sub("<id>", text)
    text = REDACT_PHONE_RE.sub("<num>", text)
    return REDACT_DIGITRUN_RE.sub("<num>", text)

def tokenize(text: str) -> list[str]:
    text = text.lower().replace("_", " ").replace("-", " ")
    return [t for t in TOKEN_RE.findall(text) if t not in STOPWORDS and len(t) >= 2]

def _unquote(v: str) -> str:
    v = v.strip()
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] in ('"', "'") else v

def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m: return {}
    out = {k: _unquote(v.strip()) for k, v in TOPLEVEL_KV_RE.findall(m.group(1))}
    out["metadata"] = {k: _unquote(v.strip()) for k, v in INDENTED_KV_RE.findall(m.group(1))}
    return out

def load_cache(cache_path: str) -> dict:
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
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
    cache = load_cache(cache_path) if use_cache else {}
    index, rebuilt = {}, 0
    for path in sorted(glob.glob(os.path.join(memdir, "*.md"))):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        cached = cache.get(path)
        if cached and cached.get("mtime") == mtime:
            index[path] = cached
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read(4096)  # frontmatter + preview only, never the whole file
        except (OSError, UnicodeDecodeError):
            continue
        rebuilt += 1
        fm = parse_frontmatter(text)
        fn = os.path.basename(path)
        prefix = fn.split("_", 1)[0]
        typ = prefix if prefix in KNOWN_PREFIXES else ((fm.get("metadata") or {}).get("type") or "misc")
        dm = DATE_IN_NAME_RE.search(fn.rsplit(".md", 1)[0] + ".md")
        name, description = fm.get("name") or fn[:-3], (fm.get("description") or "").strip()
        body = FRONTMATTER_RE.sub("", text, count=1)[:BODY_PREVIEW_CHARS]
        index[path] = {"mtime": mtime, "filename": fn, "name": name, "description": description, "type": typ,
                        "date_key": f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}" if dm else None,
                        "indexed_text": f"{name} {description} {body}"}
    if use_cache and rebuilt > 0:
        save_cache(cache_path, index)
    return index, {"file_count": len(index), "rebuilt": rebuilt}

def recency_score(entry: dict, now_ts: float) -> float:
    dkey = entry.get("date_key")
    try:
        t = time.mktime(time.strptime(dkey, "%Y-%m-%d")) if dkey else entry["mtime"]
    except ValueError:
        t = entry["mtime"]
    return math.exp(-RECENCY_LAMBDA * max(0.0, (now_ts - t) / 86400.0))

def importance_score(entry: dict) -> float:
    return IMPORTANCE_BY_TYPE.get(entry.get("type"), IMPORTANCE_DEFAULT)

def compute_doc_freq(index: dict) -> tuple[dict, dict, float]:
    doc_tokens, df, total_len = {}, {}, 0
    for path, entry in index.items():
        toks = tokenize(entry["indexed_text"])
        doc_tokens[path] = toks
        total_len += len(toks)
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    return doc_tokens, df, (total_len / len(index)) if index else 1.0

def bm25_relevance(query_tokens: list[str], doc_tokens: list[str], df: dict, n_docs: int, avgdl: float) -> float:
    if not query_tokens or not doc_tokens: return 0.0
    dl, tf = len(doc_tokens), {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    for qt in set(query_tokens) & tf.keys():
        f, n_qt = tf[qt], df.get(qt, 0)
        idf = math.log((n_docs - n_qt + 0.5) / (n_qt + 0.5) + 1)
        score += idf * (f * (BM25_K1 + 1)) / (f + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl))
    return score

def _git(args: list[str], cwd: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""

def git_main_worktree(cwd: str) -> str | None:
    common = _git(["rev-parse", "--git-common-dir"], cwd)
    if common and not os.path.isabs(common):
        common = os.path.abspath(os.path.join(cwd, common))
    return common[: -len(os.sep + ".git")] if common and common.endswith(os.sep + ".git") else None

def _slug_memdir(project_dir: str, home_path: Path) -> str:
    slug = os.path.abspath(project_dir).replace(os.sep, "-")
    return str(home_path / ".claude" / "projects" / slug / "memory")

def resolve_memdir(cwd: str | None = None, home: str | None = None) -> str | None:
    project_dir = cwd or os.environ.get("CLAUDE_PROJECT_DIR") or _git(["rev-parse", "--show-toplevel"], os.getcwd())
    if not project_dir: return None
    home_path = Path(home) if home else Path.home()
    primary = _slug_memdir(project_dir, home_path)
    if os.path.isdir(primary):
        return primary
    main_root = git_main_worktree(os.path.abspath(project_dir))
    fallback = _slug_memdir(main_root, home_path) if main_root else None
    return fallback if fallback and os.path.isdir(fallback) else primary  # still missing — main() exits 0 quietly

def build_context_query(cwd: str) -> str:
    parts = [os.path.basename(cwd.rstrip("/"))] if cwd else []
    parts += [o for o in (_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd), _git(["log", "-8", "--format=%s"], cwd)) if o]
    status = _git(["status", "--porcelain"], cwd)
    names = [os.path.basename(ln[3:].split(" -> ")[-1].strip()) for ln in status.splitlines() if len(ln) > 3] if status else []
    return " ".join(parts + ([" ".join(names)] if names else []))

def recall(memdir: str, cache_path: str, query: str, topk: int = DEFAULT_TOPK,
           threshold: float = DEFAULT_RELEVANCE_THRESHOLD, use_cache: bool = True) -> tuple[list[dict], dict]:
    index, idx_stats = build_or_refresh_index(memdir, cache_path, use_cache=use_cache)
    doc_tokens, df, avgdl = compute_doc_freq(index)
    n_docs, now_ts, q_tokens = len(index), time.time(), tokenize(query)
    scored = []
    for path, entry in index.items():
        rel = bm25_relevance(q_tokens, doc_tokens[path], df, n_docs, avgdl)
        scored.append((recency_score(entry, now_ts) * importance_score(entry) * rel, rel, entry))
    scored.sort(key=lambda t: t[0], reverse=True)
    best_rel = scored[0][1] if scored else 0.0
    stats = {**idx_stats, "best_relevance": round(best_rel, 4), "threshold": threshold, "query": query}
    if best_rel < threshold:
        return [], stats
    results = [{"filename": e["filename"], "description": e["description"]} for _, _, e in scored[:topk]]
    return results, stats

def memory_md_warning(memdir: str) -> str | None:
    try:
        size = os.path.getsize(os.path.join(memdir, "MEMORY.md"))
    except OSError:
        return None
    return MEMORY_MD_WARN_TEMPLATE.format(bytes=size) if size > MEMORY_MD_WARN_BYTES else None

def format_output(results: list[dict], warning: str | None = None, cap_bytes: int = OUTPUT_CAP_BYTES) -> str:
    budget = max(cap_bytes - (len(warning.encode("utf-8")) + 1 if warning else 0), 0)
    hb = len(HEADER_LINE.encode("utf-8")) + 1
    lines = [HEADER_LINE] if results and hb <= budget else []
    total = hb if lines else 0
    for r in results:
        claim = redact(r["description"] or r["filename"])
        if len(claim) > CLAIM_MAX_CHARS:
            claim = claim[: CLAIM_MAX_CHARS - 1].rstrip() + "…"
        line = f"- {claim} → {r['filename']}"
        lb = len(line.encode("utf-8")) + 1
        if total + lb > budget:
            break
        lines.append(line)
        total += lb
    if warning:
        lines.append(warning)
    return "\n".join(lines)

def main() -> int:
    try:
        ap = argparse.ArgumentParser()
        for name, kw in [("--memdir", {}), ("--cache-path", {}), ("--no-cache", {"action": "store_true"}),
                         ("--query", {}), ("--cwd", {}), ("--topk", {"type": int, "default": DEFAULT_TOPK}),
                         ("--threshold", {"type": float, "default": DEFAULT_RELEVANCE_THRESHOLD})]:
            ap.add_argument(name, **kw)
        args = ap.parse_args()
        cwd = args.cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        memdir = args.memdir or resolve_memdir(cwd=cwd)
        if not memdir or not os.path.isdir(memdir):
            return 0  # not wired on this machine — silent, never the reason a session breaks
        cache_path = args.cache_path or os.path.join(memdir, CACHE_FILENAME)
        results, _stats = recall(memdir, cache_path, args.query or build_context_query(cwd),
                                  topk=args.topk, threshold=args.threshold, use_cache=not args.no_cache)
        out = format_output(results, warning=memory_md_warning(memdir))
        if out:
            print(out)
        return 0
    except Exception:
        return 0  # fail-open contract: a receptor must never break a session

if __name__ == "__main__":
    raise SystemExit(main())
