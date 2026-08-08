"""Snapshot diff + Telegram alert, routed through the ONE gateway.

Reuse, not reinvent (reuse-first discipline + scar family #4/#8): every
Telegram send in this repo goes through `scripts/tg_notify.py` — born
2026-07-06 specifically because ~240 files used to send Telegram directly,
each getting secret-handling/dedup/budget/argv-safety wrong in its own way
(W104 NOAUTH-on-stdout, W115 message-on-argv visible to `ps`, W55
single-attempt drop). This module shells out to it rather than re-deriving
any of that.

Dedup key design (matters — see the comment on CONTENT_HASH_LEN below):
tg_notify's DEFAULT identity-from-text strips numbers/hashes, which is
exactly wrong here — two DIFFERENT diffs on the same page are two distinct
newsworthy events, not one repeating condition to mute. So every diff alert
gets an EXPLICIT dedup key keyed on a content hash of the NEW snapshot: same
new content -> same key -> a duplicate send dedupes correctly; different new
content -> different key -> never falsely muted.
"""

from __future__ import annotations

import difflib
import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TG_NOTIFY = REPO_ROOT / "scripts" / "tg_notify.py"

CONTENT_HASH_LEN = 12
DEFAULT_MAX_DIFF_LINES = 25


def compute_diff(old_text: str, new_text: str, max_lines: int = DEFAULT_MAX_DIFF_LINES) -> tuple[str, int, int, bool]:
    """Returns (excerpt, added_lines, removed_lines, truncated)."""
    raw = list(
        difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="", n=1)
    )
    body = [ln for ln in raw if not (ln.startswith("---") or ln.startswith("+++"))]
    added = sum(1 for ln in body if ln.startswith("+"))
    removed = sum(1 for ln in body if ln.startswith("-"))
    truncated = len(body) > max_lines
    excerpt_lines = body[:max_lines]
    if truncated:
        excerpt_lines.append(f"… ({len(body)} righe totali di diff, mostrate {max_lines})")
    return "\n".join(excerpt_lines), added, removed, truncated


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _tg_notify(tier: str, source: str, dedup_key: str, text: str) -> str:
    """Ships `text` to tg_notify.py over STDIN (never argv — W115: an
    argument is readable by any `ps` on the box; the tg_notify gateway
    already reads stdin when no positional text is given)."""
    if not TG_NOTIFY.is_file():
        return "gateway_missing"
    cmd = [sys.executable, str(TG_NOTIFY), "--tier", tier, "--source", source, "--dedup-key", dedup_key]
    try:
        proc = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=20)
    except Exception as exc:  # never let an alert failure break the crawl
        return f"error:{exc}"
    combined = (proc.stderr or "") + "\n" + (proc.stdout or "")
    for line in combined.splitlines():
        line = line.strip()
        if line.startswith("tg_notify:"):
            return line.split("tg_notify:", 1)[1].strip()
    return f"exit_{proc.returncode}"


def send_diff_alert(page_label: str, url: str, diff_excerpt: str, new_content_hash: str) -> str:
    """`new_content_hash` must be content_hash(new_snapshot_text) — computed
    ONCE by the caller (run.py already needs it to persist in the diff
    record) and passed through, never re-derived here from something else."""
    msg = f"🇮🇩 imigrasi.go.id — {page_label} è cambiata\n{url}\n\n{diff_excerpt}"
    key = f"imigrasi-diff:{new_content_hash[:CONTENT_HASH_LEN]}"
    return _tg_notify("p0", "imigrasi-mirror", key, msg)


def send_status_note(text: str, dedup_key: str) -> str:
    """One-off informational message (e.g. the mandatory dry-run test alert),
    NOT a page-change event — separate dedup namespace from diff alerts."""
    return _tg_notify("p0", "imigrasi-mirror", dedup_key, text)
