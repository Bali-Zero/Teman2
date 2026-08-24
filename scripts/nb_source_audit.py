#!/usr/bin/env python3
"""nb_source_audit.py — read-only auditor over an existing NotebookLM notebook.

Reports three classes of problems:

  1. SHELL sources — sources whose live ``char_count`` is below the per-type
     emptiness floor. For PDFs the floor is ``pages * floor_chars_per_page``;
     the page count is inferred from NotebookLM's image-URL output for scanned
     PDFs, and falls back to 1 page for text-extracted PDFs. For all other
     types the floor is the absolute ``--floor-chars`` value.
  2. UNREADABLE sources — sources for which ``nlm source content`` fails or
     returns NOT_FOUND.
  3. DUPLICATE titles — two or more sources sharing the same normalized title.

The notebook is never modified. Exit code is 1 when one or more shell sources
are found (so the tool can be wired to a cron/organ), 0 otherwise. Duplicate
titles are reported but do not change the exit code.

FLOOR DERIVATION
----------------
Measured 2026-08-24 on Kepmen M.IP-19.GR.01.01/2025 (3 pages) in NB-2:

  - raw NotebookLM extraction of the scanned PDF: 721 characters total
    -> ~240 characters / page.
  - local tesseract OCR at 300 dpi on the same PDF: 6 963 characters total
    -> ~2 321 characters / page.

The default PDF floor of 500 characters / page sits between the measured shell
and real-text densities and is configurable via ``--floor-chars-per-page``.
The default non-PDF floor is 50 characters.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nb-source-audit")

NLM_CLI = str(Path.home() / ".local" / "bin" / "nlm")

DEFAULT_PDF_FLOOR_CHARS_PER_PAGE = 500
DEFAULT_OTHER_FLOOR_CHARS = 50
DEFAULT_SLEEP = 0.5
NLM_TIMEOUT = 90.0

RunNlm = Callable[[list[str], float], subprocess.CompletedProcess[str]]


def default_run_nlm(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Default subprocess runner for the nlm CLI."""
    return subprocess.run(
        [NLM_CLI, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _nlm_with_profile(base_args: list[str], profile: str) -> list[str]:
    if profile and profile != "default":
        return [*base_args, "--profile", profile]
    return base_args


def list_sources(
    notebook_id: str,
    *,
    profile: str = "default",
    run_nlm: RunNlm = default_run_nlm,
) -> list[dict]:
    """Return the source list for ``notebook_id`` via ``nlm source list --json``."""
    args = _nlm_with_profile(["source", "list", notebook_id, "--json"], profile)
    result = run_nlm(args, timeout=NLM_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(
            f"nlm source list failed for {notebook_id} (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    data = json.loads(result.stdout or "[]")
    if isinstance(data, dict):
        return data.get("sources") or data.get("data") or []
    return list(data)


def get_source_content(
    source_id: str,
    *,
    profile: str = "default",
    run_nlm: RunNlm = default_run_nlm,
) -> Optional[dict]:
    """Fetch live content for ``source_id``.

    Returns ``None`` if the source is unreadable/NOT_FOUND, logging the reason.
    """
    args = _nlm_with_profile(["source", "content", source_id, "--json"], profile)
    result = run_nlm(args, timeout=NLM_TIMEOUT)
    if result.returncode != 0:
        err = result.stderr.strip()
        if "NOT_FOUND" in err or "not found" in err.lower():
            logger.warning("Source %s is phantom (NOT_FOUND)", source_id)
        else:
            logger.warning("Source %s content failed: %s", source_id, err)
        return None
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        logger.warning("Source %s returned invalid JSON: %s", source_id, exc)
        return None


def infer_pdf_pages(content: str) -> Optional[int]:
    """Infer page count for a scanned PDF from NotebookLM image URLs.

    When NotebookLM stores a scanned PDF without OCR, the raw content contains
    one Google-Storage image URL per page. Counting those URLs gives the page
    count for floor calculation. If no such URL is present, return ``None`` and
    the auditor falls back to a 1-page floor.
    """
    prefix = "https://lh3.googleusercontent.com/notebooklm"
    if prefix in content:
        return content.count(prefix)
    return None


def emptiness_floor(
    source_type: str,
    page_count: Optional[int],
    *,
    pdf_floor_per_page: int,
    other_floor: int,
) -> int:
    """Compute the character-count floor for a source."""
    if source_type == "pdf":
        pages = page_count if page_count is not None else 1
        return max(1, pages) * pdf_floor_per_page
    return other_floor


def normalize_title(title: str) -> str:
    """Normalize a title for duplicate detection."""
    return re.sub(r"\s+", " ", title).strip().lower()


def audit_notebook(
    notebook_id: str,
    *,
    profile: str = "default",
    pdf_floor_per_page: int = DEFAULT_PDF_FLOOR_CHARS_PER_PAGE,
    other_floor: int = DEFAULT_OTHER_FLOOR_CHARS,
    sleep_seconds: float = DEFAULT_SLEEP,
    run_nlm: RunNlm = default_run_nlm,
) -> dict:
    """Audit a notebook and return a structured report dict.

    The report contains:
      - notebook_id, profile, floors
      - source_count
      - shells: list of sources below the emptiness floor
      - unreadable: list of sources whose content could not be fetched
      - duplicates: list of title groups with >1 source
      - healthy_count, shell_count, unreadable_count, duplicate_group_count
    """
    sources = list_sources(notebook_id, profile=profile, run_nlm=run_nlm)
    logger.info("Auditing notebook %s: %d sources", notebook_id, len(sources))

    shells: list[dict] = []
    unreadable: list[dict] = []
    title_buckets: dict[str, list[dict]] = defaultdict(list)
    healthy_count = 0

    for src in sources:
        sid = src.get("id") or src.get("source_id")
        title = src.get("title", "")
        source_type = src.get("type", "")
        title_buckets[normalize_title(title)].append({"id": sid, "title": title, "type": source_type})

        content = get_source_content(sid, profile=profile, run_nlm=run_nlm)
        if content is None:
            unreadable.append({"id": sid, "title": title, "type": source_type})
            continue

        char_count = content.get("char_count", 0) or 0
        page_count: Optional[int] = None
        if source_type == "pdf":
            page_count = infer_pdf_pages(content.get("content", "") or "")

        floor = emptiness_floor(
            source_type,
            page_count,
            pdf_floor_per_page=pdf_floor_per_page,
            other_floor=other_floor,
        )

        if char_count < floor:
            shells.append(
                {
                    "id": sid,
                    "title": title,
                    "type": source_type,
                    "char_count": char_count,
                    "floor": floor,
                    "page_count": page_count,
                }
            )
        else:
            healthy_count += 1

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    duplicates = [
        {"title": items[0]["title"], "normalized": norm, "count": len(items), "ids": [i["id"] for i in items]}
        for norm, items in title_buckets.items()
        if len(items) > 1
    ]

    return {
        "notebook_id": notebook_id,
        "profile": profile,
        "pdf_floor_chars_per_page": pdf_floor_per_page,
        "other_floor_chars": other_floor,
        "source_count": len(sources),
        "healthy_count": healthy_count,
        "shell_count": len(shells),
        "unreadable_count": len(unreadable),
        "duplicate_group_count": len(duplicates),
        "shells": shells,
        "unreadable": unreadable,
        "duplicates": duplicates,
    }


def print_report(report: dict, *, as_json: bool) -> None:
    """Print the audit report to stdout (JSON or human-readable)."""
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print(f"Notebook: {report['notebook_id']} (profile: {report['profile']})")
    print(f"Sources: {report['source_count']}  "
          f"healthy={report['healthy_count']}  "
          f"shells={report['shell_count']}  "
          f"unreadable={report['unreadable_count']}  "
          f"duplicate_groups={report['duplicate_group_count']}")
    print(f"Floors: PDF={report['pdf_floor_chars_per_page']} chars/page, "
          f"other={report['other_floor_chars']} chars")

    if report["shells"]:
        print("\nSHELL sources (below emptiness floor):")
        for s in report["shells"]:
            page_info = f", pages_inferred={s['page_count']}" if s["page_count"] is not None else ""
            print(f"  [{s['type']}] {s['title'][:80]}")
            print(f"    id={s['id']} char_count={s['char_count']} floor={s['floor']}{page_info}")

    if report["unreadable"]:
        print("\nUNREADABLE sources:")
        for u in report["unreadable"]:
            print(f"  [{u['type']}] {u['title'][:80]}")
            print(f"    id={u['id']}")

    if report["duplicates"]:
        print("\nDUPLICATE titles:")
        for d in report["duplicates"]:
            print(f"  count={d['count']} title={d['title'][:80]}")
            print(f"    ids={', '.join(d['ids'])}")

    if not report["shells"] and not report["unreadable"] and not report["duplicates"]:
        print("\nNo issues found.")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only auditor over a NotebookLM notebook.")
    p.add_argument("--notebook", "-n", required=True, help="Notebook UUID")
    p.add_argument("--profile", "-p", default="default", help="nlm profile (default: default)")
    p.add_argument("--json", "-j", action="store_true", help="Emit JSON output")
    p.add_argument(
        "--floor-chars-per-page",
        type=int,
        default=DEFAULT_PDF_FLOOR_CHARS_PER_PAGE,
        help=f"PDF emptiness floor per page (default: {DEFAULT_PDF_FLOOR_CHARS_PER_PAGE})",
    )
    p.add_argument(
        "--floor-chars",
        type=int,
        default=DEFAULT_OTHER_FLOOR_CHARS,
        help=f"Absolute emptiness floor for non-PDF sources (default: {DEFAULT_OTHER_FLOOR_CHARS})",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP,
        help=f"Seconds to sleep between source content fetches (default: {DEFAULT_SLEEP})",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = audit_notebook(
        args.notebook,
        profile=args.profile,
        pdf_floor_per_page=args.floor_chars_per_page,
        other_floor=args.floor_chars,
        sleep_seconds=args.sleep,
        run_nlm=default_run_nlm,
    )
    print_report(report, as_json=args.json)
    return 1 if report["shell_count"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
