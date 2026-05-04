#!/usr/bin/env python3
"""
subhi-memory-mirror.py — filter Antonello's ~/.claude memory dir to a
local staging dir for the Subhi Zantara onboarding tutor.

Per addendum B (option B):
  source_dir → filter (exclude/redact) → dest_dir (local staging)
  Distribution to Subhi happens via rsync over Tailscale (T3, separate).
  This script does NOT push to git.

Reads YAML config (default: scripts/subhi/subhi-memory-mirror.config.yaml).
Generates _AUDIT.txt summarising included/excluded/redacted counts.

Env overrides (used by tests):
  CONFIG_OVERRIDE_SOURCE_DIR — override source_dir from config
  CONFIG_OVERRIDE_DEST_DIR   — override dest_dir from config
  DRY_RUN                    — informational only; the script never pushes
                               to git anyway under option B, but it logs
                               "DRY_RUN=1 (no-op for git)" for clarity.

Exit codes:
  0  success
  1  config / source-dir error
  2  CLI usage error
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import logging
import os
import re
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover - import-time check
    print("ERROR: PyYAML not installed. Run: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)


REDACTION_MARKER = "[REDACTED-secret]"


# --------------------------------------------------------------------------- #
# Config loading                                                              #
# --------------------------------------------------------------------------- #


def load_config(config_path: Path) -> dict:
    """Load YAML config and apply env overrides for source_dir / dest_dir."""
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    src_override = os.environ.get("CONFIG_OVERRIDE_SOURCE_DIR")
    dst_override = os.environ.get("CONFIG_OVERRIDE_DEST_DIR")
    if src_override:
        cfg["source_dir"] = src_override
    if dst_override:
        cfg["dest_dir"] = dst_override

    cfg.setdefault("exclude_patterns", [])
    cfg.setdefault("include_patterns", ["*.md"])
    cfg.setdefault("content_redact_regex", [])
    cfg.setdefault("content_full_exclude_regex", [])
    cfg.setdefault("memory_index_strip_patterns", [])

    # Compile regex once.
    cfg["_redact_regex_compiled"] = [re.compile(p) for p in cfg["content_redact_regex"]]
    cfg["_full_exclude_regex_compiled"] = [
        re.compile(p) for p in cfg["content_full_exclude_regex"]
    ]
    return cfg


# --------------------------------------------------------------------------- #
# Filtering                                                                   #
# --------------------------------------------------------------------------- #


def is_excluded(rel_path: str, exclude_patterns: Iterable[str]) -> bool:
    """
    Return True if `rel_path` matches any exclude pattern.

    Supports two pattern flavours:
      - "Subhi/**"  — Python glob ** (any depth) under prefix Subhi/
      - "Subhi"     — exact prefix match (file or first dir component)
      - "*.md"      — fnmatch glob on the basename or full rel path

    Matching is generous: a hit on either fnmatch(rel_path, pattern) OR
    fnmatch(basename, pattern) OR a "**"-prefix-match counts as excluded.
    """
    basename = os.path.basename(rel_path)
    parts = rel_path.split("/")

    for pat in exclude_patterns:
        # Python's fnmatch doesn't grok ** as recursive glob; handle by hand.
        if pat.endswith("/**"):
            prefix = pat[: -len("/**")]
            # Match either the prefix as exact file/dir name, or anything below it.
            if rel_path == prefix or rel_path.startswith(prefix + "/"):
                return True
            # Allow leading-component match: pattern "archive/**" should also
            # match a file at "archive" (degenerate but harmless).
            if parts and parts[0] == prefix:
                return True
        elif "**" in pat:
            # Convert "a/**/b" → regex; rare, support generically.
            re_pat = "^" + re.escape(pat).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
            if re.match(re_pat, rel_path):
                return True
        else:
            # Exact-name or fnmatch test.
            if fnmatch.fnmatch(rel_path, pat):
                return True
            if fnmatch.fnmatch(basename, pat):
                return True
            # Top-level dir-name match (e.g. pattern "Subhi" excludes "Subhi"
            # and anything inside it, mirroring "Subhi/**" for safety).
            if parts and parts[0] == pat:
                return True

    return False


def included_by_pattern(rel_path: str, include_patterns: Iterable[str]) -> bool:
    """Return True if rel_path matches any include pattern."""
    basename = os.path.basename(rel_path)
    for pat in include_patterns:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(basename, pat):
            return True
    return False


def apply_redactions(content: str, redact_regex_compiled: list[re.Pattern]) -> tuple[str, int]:
    """Replace every regex hit with REDACTION_MARKER. Return (new_content, hits)."""
    hits = 0
    for rgx in redact_regex_compiled:
        new_content, n = rgx.subn(REDACTION_MARKER, content)
        if n > 0:
            hits += n
            content = new_content
    return content, hits


def has_full_exclude_match(content: str, full_exclude_regex_compiled: list[re.Pattern]) -> str | None:
    """Return the matching pattern source if the file should be skipped entirely, else None."""
    for rgx in full_exclude_regex_compiled:
        if rgx.search(content):
            return rgx.pattern
    return None


def strip_memory_index_lines(content: str, strip_patterns: Iterable[str]) -> str:
    """Remove every line in MEMORY.md that contains any of the substrings."""
    if not strip_patterns:
        return content
    kept = []
    for line in content.splitlines(keepends=True):
        if any(pat in line for pat in strip_patterns):
            continue
        kept.append(line)
    return "".join(kept)


# --------------------------------------------------------------------------- #
# Walk + emit                                                                 #
# --------------------------------------------------------------------------- #


def iter_source_files(source_dir: Path) -> Iterable[Path]:
    """Yield every regular file under source_dir."""
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            yield path


def mirror(cfg: dict, logger: logging.Logger) -> dict:
    source_dir = Path(cfg["source_dir"]).resolve()
    dest_dir = Path(cfg["dest_dir"]).resolve()

    if not source_dir.is_dir():
        raise FileNotFoundError(f"source_dir not found: {source_dir}")

    dest_dir.mkdir(parents=True, exist_ok=True)

    excluded: list[tuple[str, str]] = []  # (rel_path, reason)
    redacted: list[tuple[str, int]] = []  # (rel_path, hits)
    included: list[str] = []

    exclude_patterns = list(cfg["exclude_patterns"])
    include_patterns = list(cfg["include_patterns"])
    redact_regex = list(cfg["_redact_regex_compiled"])
    full_excl_regex = list(cfg["_full_exclude_regex_compiled"])
    mem_strip = list(cfg["memory_index_strip_patterns"])

    for src_path in iter_source_files(source_dir):
        rel = src_path.relative_to(source_dir).as_posix()

        # 1. Path-based exclusion.
        if is_excluded(rel, exclude_patterns):
            excluded.append((rel, "path-pattern"))
            continue

        # 2. Include filter (default: only *.md).
        if not included_by_pattern(rel, include_patterns):
            excluded.append((rel, "not-included"))
            continue

        # 3. Read content.
        try:
            content = src_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            excluded.append((rel, "binary-or-non-utf8"))
            continue
        except OSError as exc:
            logger.warning("read failed %s: %s", rel, exc)
            excluded.append((rel, f"read-error:{exc.__class__.__name__}"))
            continue

        # 4. Full-content exclude (drop entire file if it contains a banned token).
        full_match = has_full_exclude_match(content, full_excl_regex)
        if full_match is not None:
            preview = full_match[:30]
            excluded.append((rel, f"content-match:{preview}"))
            continue

        # 5. Apply redactions.
        new_content, hits = apply_redactions(content, redact_regex)
        if hits > 0:
            redacted.append((rel, hits))

        # 6. Special handling for MEMORY.md — strip index lines pointing at excluded files.
        if rel == "MEMORY.md":
            new_content = strip_memory_index_lines(new_content, mem_strip)

        # 7. Write.
        dest_path = dest_dir / rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(new_content, encoding="utf-8")
        included.append(rel)

    # ----- Audit trail -----
    audit_path = dest_dir / "_AUDIT.txt"
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with audit_path.open("w", encoding="utf-8") as fh:
        fh.write("=== Subhi Memory Mirror Audit ===\n")
        fh.write(f"Generated: {now}\n")
        fh.write(f"Source:    {source_dir}\n")
        fh.write(f"Dest:      {dest_dir}\n")
        fh.write("\n")
        fh.write(f"Included:  {len(included)} files\n")
        fh.write(f"Excluded:  {len(excluded)} files\n")
        total_redactions = sum(n for _, n in redacted)
        fh.write(f"Redacted:  {len(redacted)} files ({total_redactions} substitutions)\n")
        fh.write("\n")
        fh.write("=== Excluded files ===\n")
        for rel, reason in excluded:
            fh.write(f"  - {rel}  [{reason}]\n")
        fh.write("\n")
        fh.write("=== Redacted files ===\n")
        for rel, hits in redacted:
            fh.write(f"  - {rel} ({hits} substitutions)\n")
        fh.write("\n")
        fh.write("=== Notes ===\n")
        fh.write(
            "Per addendum B, this mirror is local-only. Distribution to Subhi\n"
            "happens via rsync over Tailscale (T3). No git push is performed.\n"
        )

    return {
        "included": len(included),
        "excluded": len(excluded),
        "redacted": len(redacted),
        "redactions_total": sum(n for _, n in redacted),
        "audit_path": str(audit_path),
    }


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Subhi memory mirror — filter Antonello's memory dir to a local staging dir."
    )
    default_config = Path(__file__).resolve().parent / "subhi-memory-mirror.config.yaml"
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help=f"Path to YAML config (default: {default_config})",
    )
    args = parser.parse_args(argv)

    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "subhi-memory-mirror.log"

    logger = logging.getLogger("subhi-memory-mirror")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        # File handler — best-effort; if log dir is read-only, fall back to stderr.
        try:
            fh = logging.FileHandler(log_path)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(fh)
        except OSError:  # pragma: no cover
            pass
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(sh)

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    try:
        stats = mirror(cfg, logger)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    logger.info(
        "Mirror complete: included=%d excluded=%d redacted=%d (%d substitutions)",
        stats["included"],
        stats["excluded"],
        stats["redacted"],
        stats["redactions_total"],
    )
    if os.environ.get("DRY_RUN") == "1":
        logger.info("DRY_RUN=1 (option B has no git push step; flag is a no-op for parity).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
