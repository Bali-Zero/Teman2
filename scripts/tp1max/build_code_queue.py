#!/usr/bin/env python3
"""Build the L-CODE queue (TP1MAX-20261005) from a repo snapshot: one job per source file/chunk.

Every queued job is sent to an external provider (the Alibaba Token Plan), so the input screen is
fail-closed: a file is queued only when it was read, is UTF-8 text under MAX_BYTES, is not a
symlink, and carries no secret shape, phone number or non-allowlisted email address. Anything else
is SKIPPED and counted by reason, never sent. Test/fixture/data/content paths are never even read.

Usage: build_code_queue.py <repo> <out queue.jsonl>
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

EXT = (".py", ".sh", ".ts", ".tsx", ".js", ".mjs")
ROOTS = ("scripts/", "apps/backend-rag/backend/", "apps/nuzantara-mcp/", ".claude/hooks/", "infra/",
         "apps/mouth/src/", "apps/kbli-navigator/src/", "apps/")
SKIP_PATH = re.compile(r"(^|/)(\.env|tests?/|__tests__|fixtures?|testdata|test_|.*\.test\.|.*\.spec\.|data/|content/|"
                       r"node_modules|dist/|build/|migrations?/|vendor/|.*secret|.*credential|.*\.min\.)", re.I)
SECRET = re.compile(r"AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|xox[abp]-|-----BEGIN [A-Z ]*PRIVATE|"
                    r"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}")
# Indonesian mobile: 62/+62/0, then 8 and 7-11 more digits in ANY grouping (+62-8123-4567-8901,
# 62-812-34-56-7890); then any other +CC number written in groups.
PHONE = re.compile(r"(\+?62[\s.-]?|\b0)8(?:[\s.-]?\d){7,11}\b|\+\d{2}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3,4}")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"^(zantara|noreply|no-reply|example|test|user|foo|bar|you|name|info)@|@(example\.(com|org)|anthropic\.com|users\.noreply\.github\.com|localhost)$", re.I)
CHUNK = 700
MIN_CHARS = 300
MAX_BYTES = 512 * 1024

PROMPT = """Adversarial code audit of ONE file (or one chunk of it) from a public repository: ops tooling, a FastAPI/RAG backend and Next.js frontends of a small Indonesian consultancy.
Report ONLY concrete defects you can pin to a line: fail-open guards (an error path that lets a check pass or a monitor stay green), unhandled error paths, races/TOCTOU that can actually happen, dead code that a test or caller still relies on, wrong exit codes, shell pitfalls (missing pipefail, SIGPIPE under pipefail, unquoted expansions, `set -e` traps), wrong regex/off-by-one, timezone bugs, resource leaks, security holes (injection, path traversal, auth bypass). No style remarks, no "could be improved", no speculation about code you cannot see. If you find nothing concrete, return an empty list — that is a good answer.
Reply with ONLY a JSON object: {{"defects":[{{"line":<int>,"severity":"high|medium|low","class":"...","defect":"...","evidence":"<the exact code on that line>"}}]}}

FILE: {path}{part}
-----
{text}
-----"""


def files(repo: Path):
    out = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=True).stdout
    for f in out.splitlines():
        if f.endswith(EXT) and f.startswith(ROOTS) and not SKIP_PATH.search(f):
            yield f


def clean(text: str) -> bool:
    if SECRET.search(text) or PHONE.search(text):
        return False
    return all(EMAIL_OK.search(e) for e in EMAIL.findall(text))


def screen(path: Path, root: Optional[Path] = None) -> "tuple[Optional[str], str]":
    """(text, "ok") when the file may leave the machine, else (None, reason). Never raises."""
    try:
        rel = path.relative_to(root).parts if root else ()
        hops = [root.joinpath(*rel[:i]) for i in range(1, len(rel))] if root else []  # a linked DIRECTORY too
        if path.is_symlink() or any(hop.is_symlink() for hop in hops):
            return None, "symlink"  # it would send whatever the link points at, inside the repo or not
        if path.stat().st_size > MAX_BYTES:
            return None, "oversized"
        data = path.read_bytes()
    except (OSError, ValueError):  # ValueError: a path outside root
        return None, "unreadable"
    if len(data) > MAX_BYTES:
        return None, "oversized"
    if b"\0" in data:
        return None, "binary"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "binary"
    if len(text) < MIN_CHARS:
        return None, "short"
    if not clean(text):
        return None, "secret_pii"
    return text, "ok"


def build(repo: Path) -> "tuple[list[dict], collections.Counter]":
    jobs, skipped, seen = [], collections.Counter(), set()
    prio = lambda f: next(i for i, r in enumerate(ROOTS) if f.startswith(r))  # noqa: E731
    for f in sorted(files(repo), key=prio):
        if f in seen:
            continue
        seen.add(f)
        text, reason = screen(repo / f, repo)
        if text is None:
            skipped[reason] += 1
            continue
        lines = text.splitlines()
        parts = [(i, lines[i:i + CHUNK]) for i in range(0, len(lines), CHUNK)]
        for k, (start, chunk) in enumerate(parts):
            numbered = "\n".join(f"{start + j + 1:5d}| {line}" for j, line in enumerate(chunk))
            part = f" (lines {start + 1}-{start + len(chunk)} of {len(lines)})" if len(parts) > 1 else ""
            jid = f"code:{f}" + (f"#{k}" if len(parts) > 1 else "")
            jobs.append({"id": jid, "lane": "L-CODE", "prompt": PROMPT.format(path=f, part=part, text=numbered),
                         "sha": hashlib.sha256(text.encode()).hexdigest()[:12]})
    return jobs, skipped


def main(argv: "list[str]") -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    jobs, skipped = build(Path(argv[0]))
    out = Path(argv[1])
    tmp = out.with_suffix(".tmp")  # a live runner may be reading the queue: never leave it half-written
    tmp.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"jobs": len(jobs), "skipped": dict(sorted(skipped.items())),
                      "prompt_chars": sum(len(j["prompt"]) for j in jobs)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
