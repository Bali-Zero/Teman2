#!/usr/bin/env python3
"""LAYER 3 — memory_index_build.py (production catalog generator).

Generates a full catalog (MEMORY_INDEX.md) of every memory file in MEMDIR,
grouped by type, one line per file, redacted — the "grep before you act on a
topic" fallback the Layer-2 recall hook (`mos_recall_sessionstart.py`) points
to for anything its top-6 cap dropped.

Scope: every ``*.md`` in MEMDIR except ``MEMORY*.md`` (the index itself and
thematic digests) and anything with ``.bak``/``backup`` in the filename.

MEMDIR is derived like the Layer-2 hook: ``$CLAUDE_PROJECT_DIR`` (fallback:
`git rev-parse --show-toplevel`) + ``Path.home()`` — no hardcoded M5 path, so
Pro/Mini resolve their own slug. Read-only on MEMDIR; ``--out`` never touches
the live MEMORY.md/MEMORY_*.md files, only the catalog itself.

Invoked by hand or by cron later (out of scope here — ships independently of
the Layer-2 PR). ``--check`` detects a stale catalog without a diff.
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

# Recognized filename-prefix taxonomy (the convention this corpus already
# uses in MEMORY.md's own links: discovery_/decision_/lesson_/fact_/
# project_/unresolved_/reference_/ops_/feedback_...).
KNOWN_PREFIXES = {
    "discovery", "decision", "lesson", "fact", "project",
    "unresolved", "reference", "ops", "feedback",
}

# PII redaction (transformation). Duplicated (not imported) from the sibling
# Layer-2 script mos_recall_sessionstart.py — separate PRs, keep in sync by hand.
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


def pii_scan(text: str) -> list[str]:
    """Detection only (category names) — used for the build report, kept
    separate from redact() since a report wants to KNOW what was found."""
    hits = []
    if REDACT_EMAIL_RE.search(text):
        hits.append("email")
    if REDACT_PHONE_RE.search(text):
        hits.append("phone_id_it")
    if REDACT_ID_RE.search(text):
        hits.append("passport_ktp")
    if REDACT_DIGITRUN_RE.search(text):
        hits.append("digit_run")
    return hits


def is_excluded(filename: str) -> bool:
    if not filename.endswith(".md"):
        return True
    if filename.startswith("MEMORY"):
        return True
    low = filename.lower()
    if ".bak" in low or "backup" in low:
        return True
    return False


def parse_frontmatter(text: str) -> dict:
    """Minimal frontmatter parser for THIS corpus's shape only:
    top-level 'key: value' lines plus one nested 'metadata:' block.
    Returns {} if there is no frontmatter block at all.
    """
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
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return v[1:-1]
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1]
    return v


def first_heading(text: str) -> str | None:
    body = FRONTMATTER_RE.sub("", text, count=1)
    m = HEADING_RE.search(body)
    if m:
        return m.group(1).strip()
    return None


def date_key(filename: str, mtime: float) -> str:
    m = DATE_IN_NAME_RE.search(filename.rsplit(".md", 1)[0] + ".md")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return time.strftime("%Y-%m-%d", time.localtime(mtime))


def classify_type(filename: str, fm_type: str | None) -> str:
    prefix = filename.split("_", 1)[0]
    if prefix in KNOWN_PREFIXES:
        return prefix
    if fm_type:
        return fm_type
    return "misc"


def resolve_memdir(cwd: str | None = None, home: str | None = None) -> str | None:
    """~/.claude/projects/<slug>/memory, <slug> = abs project dir, '/' -> '-'.
    `cwd` defaults to $CLAUDE_PROJECT_DIR (fallback: git toplevel of cwd);
    `home` overrides Path.home() (test-only)."""
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
    abs_dir = os.path.abspath(project_dir)
    slug = abs_dir.replace(os.sep, "-")
    home_path = Path(home) if home else Path.home()
    return str(home_path / ".claude" / "projects" / slug / "memory")


def build_index(memdir: str) -> tuple[str, dict]:
    t0 = time.time()
    files = sorted(
        fn for fn in os.listdir(memdir) if not is_excluded(fn)
    )

    entries = []  # (type, date_key, line, filename)
    pii_offenders = []
    n_no_frontmatter_named_by_heading = 0

    for fn in files:
        path = os.path.join(memdir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        fm = parse_frontmatter(text)
        name = fm.get("name")
        description = fm.get("description", "") or ""
        fm_type = (fm.get("metadata") or {}).get("type")

        title = name
        if not title:
            h = first_heading(text)
            title = h if h else fn[:-3]
            n_no_frontmatter_named_by_heading += 1

        raw_desc = description.strip()
        hits = pii_scan(raw_desc)
        if hits:
            pii_offenders.append((fn, hits))

        desc = redact(raw_desc)
        if len(desc) > DESC_MAX:
            desc = desc[: DESC_MAX - 1].rstrip() + "…"

        mtime = os.path.getmtime(path)
        dkey = date_key(fn, mtime)
        typ = classify_type(fn, fm_type)

        line = f"- {title}: {desc} ({fn})"
        entries.append((typ, dkey, line, fn))

    # Group by type, sort each group by date desc, then filename for stability.
    by_type: dict[str, list[tuple[str, str, str]]] = {}
    for typ, dkey, line, fn in entries:
        by_type.setdefault(typ, []).append((dkey, line, fn))
    for typ in by_type:
        by_type[typ].sort(key=lambda t: (t[0], t[2]), reverse=True)

    out_lines = ["# MEMORY_INDEX.md (generated — Layer 3 catalog, redacted)", ""]
    for typ in sorted(by_type.keys()):
        out_lines.append(f"## {typ}")
        for dkey, line, fn in by_type[typ]:
            out_lines.append(line)
        out_lines.append("")

    text_out = "\n".join(out_lines).rstrip("\n") + "\n"
    build_time = time.time() - t0

    meta = {
        "file_count": len(files),
        "bytes": len(text_out.encode("utf-8")),
        "line_count": text_out.count("\n"),
        "build_seconds": round(build_time, 4),
        "types": sorted(by_type.keys()),
        "frontmatter_less_count": n_no_frontmatter_named_by_heading,
        "pii_offender_count": len(pii_offenders),
        "pii_offender_files": [fn for fn, _hits in pii_offenders],
        "catalog_filenames": files,
    }
    return text_out, meta


def is_stale(memdir: str, out_path: str) -> bool:
    """True if `out_path` doesn't exist, or any included memory file in
    memdir has an mtime newer than the catalog's own mtime."""
    if not os.path.exists(out_path):
        return True
    catalog_mtime = os.path.getmtime(out_path)
    for path in glob.glob(os.path.join(memdir, "*.md")):
        fn = os.path.basename(path)
        if is_excluded(fn):
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
    ap.add_argument("--report-json", default=None)
    ap.add_argument("--check", action="store_true",
                     help="exit 1 if the catalog at --out is stale, without writing anything")
    args = ap.parse_args()

    memdir = args.memdir or resolve_memdir()
    if not memdir or not os.path.isdir(memdir):
        print("memory_index_build: no memdir resolved/found — nothing to do", file=sys.stderr)
        return 0 if not args.check else 1

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

    if args.report_json:
        import json
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    print(
        f"[memory_index_build] {meta['file_count']} files -> {meta['bytes']}B, "
        f"{meta['line_count']} lines, {meta['build_seconds']}s, "
        f"PII offenders redacted={meta['pii_offender_count']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
