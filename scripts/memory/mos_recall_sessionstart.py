#!/usr/bin/env python3
"""LAYER 2 — mos_recall_sessionstart.py (SessionStart recall hook).

score = recency x importance x BM25 relevance; prints top-k claims, silent
when nothing pertinent. MEMDIR = ~/.claude/projects/<slug>/memory (slug =
abs project dir, '/' -> '-'); missing in a worktree, so we retry against the
MAIN worktree via `git rev-parse --git-common-dir`. Only frontmatter
`description` is printed, through redact(). Fail-open: quiet exit 0.

Also indexes `docs/scars/cicatrix-scars.md` + `cicatrix-scars-archive.md`
(2026-09-04): each numbered scar heading becomes a `type="scar"` candidate
in the SAME recency x importance x BM25 pool as the memory files, so a
matching scar is recalled by pertinence instead of the whole
`cicatrix-superscar.md` roster being injected wholesale every turn (that
bridge is now a 2.5KB index of families only — see
`.claude/rules/cicatrix-superscar.md`). Resolved from `docs/scars/` under
the SAME project root as MEMDIR, which is repo-relative and therefore
identical on every machine (unlike MEMDIR's `~/.claude/projects/<slug>`
mapping, which can differ across hosts).

Sibling (2026-09-04): `mos_recall_userprompt.py` imports this module's
functions directly to run the SAME recall on every UserPromptSubmit turn
with a tighter budget (top-3/<=600B/0.45 vs this file's top-6/1500B/0.35).
`format_output()`'s `header`/`claim_max_chars` params and this CLI's
`--max-bytes`/`--header`/`--claim-max-chars`/`--no-memory-warning` flags
exist for that sibling; SessionStart's own call path never sets them.
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
IMPORTANCE_BY_TYPE = {"feedback": 1.0, "decision": 1.0, "lesson": 1.0, "lessons": 1.0, "scar": 1.0, "project": 0.9, "discovery": 0.8, "fact": 0.6, "reference": 0.6}
IMPORTANCE_DEFAULT = 0.5

# Scar-section indexing (Layer 2 also recalls docs/scars/*.md by pertinence).
SCAR_FILES = ("cicatrix-scars.md", "cicatrix-scars-archive.md")
SCAR_BODY_PREVIEW_CHARS = 160  # claim length, distinct from the 400-char memory-body preview above
SCAR_HEADING_RE = re.compile(r"^#{2,4} (.+)$", re.MULTILINE)
SCAR_WNUM_RE = re.compile(r"\bW\d+[a-z]?\b")
SCAR_DATE_RE = re.compile(r"2026-\d\d-\d\d")
SCAR_SLUG_RE = re.compile(r"[^a-z0-9]+")

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
    if entry.get("type") == "scar":
        # A cicatrix scar is a disease pattern, not a status note: one filed in April is
        # exactly as valid a warning today as one filed last week. The 30-day half-life
        # below is right for "what did I decide/discover recently" but wrong for scars —
        # applying it here buried every scar older than ~6 weeks under fresher, less
        # relevant memory notes (measured 2026-09-04: W67/W67b had the HIGHEST raw BM25
        # relevance of all 1,941 candidates for a KeepAlive-storm query, 13.3/12.6, yet
        # ranked #21/#23 after a ~90-day-old recency multiplier of ~0.13 crushed them).
        # Scars compete on relevance x importance alone.
        return 1.0
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

def resolve_scars_dir(cwd: str | None = None) -> str | None:
    project_dir = cwd or os.environ.get("CLAUDE_PROJECT_DIR") or _git(["rev-parse", "--show-toplevel"], os.getcwd())
    if not project_dir:
        return None
    d = os.path.join(project_dir, "docs", "scars")
    return d if os.path.isdir(d) else None

def _slugify(heading: str) -> str:
    return SCAR_SLUG_RE.sub("-", heading.lower()).strip("-")[:60]

def split_scar_sections(text: str) -> list[tuple[str, str]]:
    """(heading_text, body_text) for every `##`/`###`/`####` heading — a
    fallback-free single pass, since both scar files use that heading form
    consistently for every entry that carries a W-number."""
    matches = list(SCAR_HEADING_RE.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1).strip(), text[m.end():end].strip()))
    return sections

def build_scar_index(scars_dir: str) -> dict:
    """One `type="scar"` entry per W-numbered heading in either scar file.
    Headings with no W-number (older `RESOLVED`-only entries) are skipped —
    the output format cites a W-number, so there is nothing to cite for them."""
    index: dict = {}
    for fn in SCAR_FILES:
        path = os.path.join(scars_dir, fn)
        try:
            mtime = os.path.getmtime(path)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        for heading, body in split_scar_sections(text):
            wm = SCAR_WNUM_RE.search(heading)
            if not wm:
                continue
            wnum = wm.group(0)
            dm = SCAR_DATE_RE.search(heading) or SCAR_DATE_RE.search(body[:200])
            key = f"{fn}#{_slugify(heading)}"
            index[key] = {
                "mtime": mtime,
                "filename": f"{fn}#{_slugify(heading)}",
                "name": wnum,
                "description": body[:SCAR_BODY_PREVIEW_CHARS].strip(),
                "type": "scar",
                "date_key": dm.group(0) if dm else None,
                "indexed_text": f"{heading} {body[:BODY_PREVIEW_CHARS]}",
                "wnum": wnum,
            }
    return index

def build_context_query(cwd: str) -> str:
    parts = [os.path.basename(cwd.rstrip("/"))] if cwd else []
    parts += [o for o in (_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd), _git(["log", "-8", "--format=%s"], cwd)) if o]
    status = _git(["status", "--porcelain"], cwd)
    names = [os.path.basename(ln[3:].split(" -> ")[-1].strip()) for ln in status.splitlines() if len(ln) > 3] if status else []
    return " ".join(parts + ([" ".join(names)] if names else []))

def recall(memdir: str, cache_path: str, query: str, topk: int = DEFAULT_TOPK,
           threshold: float = DEFAULT_RELEVANCE_THRESHOLD, use_cache: bool = True,
           scars_dir: str | None = None) -> tuple[list[dict], dict]:
    index, idx_stats = build_or_refresh_index(memdir, cache_path, use_cache=use_cache)
    scar_count = 0
    if scars_dir:
        scar_index = build_scar_index(scars_dir)
        scar_count = len(scar_index)
        index = {**index, **scar_index}
    doc_tokens, df, avgdl = compute_doc_freq(index)
    n_docs, now_ts, q_tokens = len(index), time.time(), tokenize(query)
    scored = []
    for path, entry in index.items():
        rel = bm25_relevance(q_tokens, doc_tokens[path], df, n_docs, avgdl)
        scored.append((recency_score(entry, now_ts) * importance_score(entry) * rel, rel, entry))
    scored.sort(key=lambda t: t[0], reverse=True)
    best_rel = scored[0][1] if scored else 0.0
    stats = {**idx_stats, "scar_count": scar_count, "best_relevance": round(best_rel, 4),
              "threshold": threshold, "query": query}
    if best_rel < threshold:
        return [], stats
    results = []
    for _, _, e in scored[:topk]:
        r = {"filename": e["filename"], "description": e["description"]}
        if e.get("wnum"):
            r["wnum"] = e["wnum"]
        results.append(r)
    return results, stats

def memory_md_warning(memdir: str) -> str | None:
    try:
        size = os.path.getsize(os.path.join(memdir, "MEMORY.md"))
    except OSError:
        return None
    return MEMORY_MD_WARN_TEMPLATE.format(bytes=size) if size > MEMORY_MD_WARN_BYTES else None

def format_output(results: list[dict], warning: str | None = None, cap_bytes: int = OUTPUT_CAP_BYTES,
                   header: str = HEADER_LINE, claim_max_chars: int = CLAIM_MAX_CHARS) -> str:
    budget = max(cap_bytes - (len(warning.encode("utf-8")) + 1 if warning else 0), 0)
    hb = len(header.encode("utf-8")) + 1
    lines = [header] if results and hb <= budget else []
    total = hb if lines else 0
    for r in results:
        claim = redact(r["description"] or r["filename"])
        if len(claim) > claim_max_chars:
            claim = claim[: claim_max_chars - 1].rstrip() + "…"
        prefix = f"[{r['wnum']}] " if r.get("wnum") else ""
        line = f"- {prefix}{claim} → {r['filename']}"
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
                         ("--threshold", {"type": float, "default": DEFAULT_RELEVANCE_THRESHOLD}),
                         ("--scars-dir", {}),
                         # Below: surface added for mos_recall_userprompt.py (the per-prompt sibling hook,
                         # 2026-09-04) and for manual CLI debugging — never touched by SessionStart's own
                         # call path, so its defaults reproduce the pre-existing behaviour exactly.
                         ("--max-bytes", {"type": int, "default": OUTPUT_CAP_BYTES}),
                         ("--header", {"default": HEADER_LINE}),
                         ("--claim-max-chars", {"type": int, "default": CLAIM_MAX_CHARS}),
                         ("--no-memory-warning", {"action": "store_true"})]:
            ap.add_argument(name, **kw)
        args = ap.parse_args()
        cwd = args.cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        memdir = args.memdir or resolve_memdir(cwd=cwd)
        if not memdir or not os.path.isdir(memdir):
            return 0  # not wired on this machine — silent, never the reason a session breaks
        cache_path = args.cache_path or os.path.join(memdir, CACHE_FILENAME)
        scars_dir = args.scars_dir or resolve_scars_dir(cwd)
        results, _stats = recall(memdir, cache_path, args.query or build_context_query(cwd),
                                  topk=args.topk, threshold=args.threshold, use_cache=not args.no_cache,
                                  scars_dir=scars_dir)
        warning = None if args.no_memory_warning else memory_md_warning(memdir)
        out = format_output(results, warning=warning, cap_bytes=args.max_bytes, header=args.header,
                             claim_max_chars=args.claim_max_chars)
        if out:
            print(out)
        return 0
    except Exception:
        return 0  # fail-open contract: a receptor must never break a session

if __name__ == "__main__":
    raise SystemExit(main())
