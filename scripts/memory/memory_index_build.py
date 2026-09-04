#!/usr/bin/env python3
"""LAYER 3 — memory_index_build.py: generates MEMORY_INDEX.md, a full
redacted catalog of every memory file in MEMDIR, grouped by type — the
"grep before you act" fallback the Layer-2 recall hook's top-6 cap drops.

MEMDIR derivation mirrors mos_recall_sessionstart.py: $CLAUDE_PROJECT_DIR
(fallback: git toplevel) + Path.home(), no hardcoded machine path.
Read-only on MEMDIR; --out never touches MEMORY.md/MEMORY_*.md.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DESC_MAX = 140

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
DATE_IN_NAME_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})(?:\.md)?$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
KNOWN_PREFIXES = {
    "discovery", "decision", "lesson", "fact", "project",
    "unresolved", "reference", "ops", "feedback",
}

# PII redaction (duplicated, not imported, from mos_recall_sessionstart.py —
# separate PRs, keep in sync by hand). Order matters: specific shapes
# consume their digits before the generic digit-run pattern would.
REDACT_PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    ("passport_ktp", re.compile(r"\b(?:passport|KTP|NIK|NPWP)\b\D{0,10}\d[\d\s-]*", re.IGNORECASE), "<id>"),
    ("phone_id_it", re.compile(r"\+(?:62|39)[\s.-]?\d[\d\s.-]{6,}\d"), "<num>"),
    ("digit_run", re.compile(r"(?<!\d)\d{10,15}(?!\d)"), "<num>"),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Replace PII shapes with placeholders; return (text, hit categories)."""
    hits = []
    if not text:
        return text, hits
    for name, pattern, placeholder in REDACT_PATTERNS:
        if pattern.search(text):
            hits.append(name)
        text = pattern.sub(placeholder, text)
    return text, hits


def is_excluded(filename: str) -> bool:
    if not filename.endswith(".md") or filename.startswith("MEMORY"):
        return True
    low = filename.lower()
    return ".bak" in low or "backup" in low


def parse_frontmatter(text: str) -> dict:
    """Minimal parser for this corpus's shape: top-level 'key: value' lines
    plus one nested 'metadata:' block. {} if there's no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict = {}
    metadata: dict = {}
    in_metadata = False
    for line in m.group(1).split("\n"):
        if not line.strip():
            continue
        if line.startswith("metadata:"):
            in_metadata = True
            continue
        if in_metadata and line.startswith((" ", "\t")):
            k, _, v = line.strip().partition(":")
            metadata[k.strip()] = v.strip().strip("'\"")
            continue
        in_metadata = False
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip("'\"")
    out["metadata"] = metadata
    return out


def first_heading(text: str) -> str | None:
    body = FRONTMATTER_RE.sub("", text, count=1)
    m = HEADING_RE.search(body)
    return m.group(1).strip() if m else None


def date_key(filename: str, mtime: float) -> str:
    m = DATE_IN_NAME_RE.search(filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return time.strftime("%Y-%m-%d", time.localtime(mtime))


def classify_type(filename: str, fm_type: str | None) -> str:
    prefix = filename.split("_", 1)[0]
    if prefix in KNOWN_PREFIXES:
        return prefix
    return fm_type or "misc"


def resolve_memdir(cwd: str | None = None, home: str | None = None) -> str | None:
    """~/.claude/projects/<slug>/memory, <slug> = abs project dir, '/' -> '-'.
    cwd defaults to $CLAUDE_PROJECT_DIR (fallback: git toplevel of cwd);
    home overrides Path.home() (test-only)."""
    project_dir = cwd or os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd(),
                capture_output=True, text=True, timeout=1.5,
            )
            project_dir = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            project_dir = None
    if not project_dir:
        return None
    slug = os.path.abspath(project_dir).replace(os.sep, "-")
    home_path = Path(home) if home else Path.home()
    return str(home_path / ".claude" / "projects" / slug / "memory")


def build_index(memdir: str) -> tuple[str, dict]:
    t0 = time.time()
    files = sorted(fn for fn in os.listdir(memdir) if not is_excluded(fn))

    by_type: dict[str, list[tuple[str, str]]] = {}
    frontmatter_less = 0
    pii_offenders = []

    for fn in files:
        path = os.path.join(memdir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        fm = parse_frontmatter(text)
        title = fm.get("name")
        if not title:
            title = first_heading(text) or fn[:-3]
            frontmatter_less += 1

        desc, hits = redact((fm.get("description") or "").strip())
        if hits:
            pii_offenders.append(fn)
        if len(desc) > DESC_MAX:
            desc = desc[: DESC_MAX - 1].rstrip() + "…"

        typ = classify_type(fn, (fm.get("metadata") or {}).get("type"))
        dkey = date_key(fn, os.path.getmtime(path))
        by_type.setdefault(typ, []).append((dkey, f"- {title}: {desc} ({fn})"))

    for typ in by_type:
        by_type[typ].sort(reverse=True)

    out_lines = ["# MEMORY_INDEX.md (generated — Layer 3 catalog, redacted)", ""]
    for typ in sorted(by_type):
        out_lines.append(f"## {typ}")
        out_lines.extend(line for _dkey, line in by_type[typ])
        out_lines.append("")

    text_out = "\n".join(out_lines).rstrip("\n") + "\n"
    meta = {
        "file_count": len(files),
        "bytes": len(text_out.encode("utf-8")),
        "line_count": text_out.count("\n"),
        "build_seconds": round(time.time() - t0, 4),
        "types": sorted(by_type),
        "frontmatter_less_count": frontmatter_less,
        "pii_offender_count": len(pii_offenders),
        "pii_offender_files": pii_offenders,
    }
    return text_out, meta


def is_stale(memdir: str, out_path: str) -> bool:
    """True if out_path is missing, or any included file's mtime is newer."""
    if not os.path.exists(out_path):
        return True
    catalog_mtime = os.path.getmtime(out_path)
    for path in glob.glob(os.path.join(memdir, "*.md")):
        if is_excluded(os.path.basename(path)):
            continue
        try:
            if os.path.getmtime(path) > catalog_mtime:
                return True
        except OSError:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--memdir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true",
                     help="exit 1 if the catalog at --out is stale, without writing anything")
    args = ap.parse_args()

    memdir = args.memdir or resolve_memdir()
    if not memdir or not os.path.isdir(memdir):
        print("memory_index_build: no memdir resolved/found — nothing to do", file=sys.stderr)
        return 1 if args.check else 0

    out_path = args.out or os.path.join(memdir, "MEMORY_INDEX.md")

    if args.check:
        stale = is_stale(memdir, out_path)
        print(f"[memory_index_build] --check: {'STALE' if stale else 'fresh'} ({out_path})", file=sys.stderr)
        return 1 if stale else 0

    text_out, meta = build_index(memdir)
    if out_path == "-":
        sys.stdout.write(text_out)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text_out)

    print(
        f"[memory_index_build] {meta['file_count']} files -> {meta['bytes']}B, "
        f"{meta['line_count']} lines, {meta['build_seconds']}s, "
        f"PII offenders redacted={meta['pii_offender_count']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
