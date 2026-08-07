"""The one thing this loop persists: a growing file of learned reply habits.

Nothing else survives a run. Mail stays in Zoho, attachments are already handled
by `services.intake.zoho_adapter`, and no message body is written to our disk.
What accumulates here is a small, human-readable set of observations about how
Zero actually answers — the residue of diff(our draft, what he sent).

PII boundary (UU PDP Art. 67-68, SYMBIOSIS Law 2), enforced not assumed:

    A lesson is a statement about STYLE, never about a client. Every lesson is
    run through `redact` and then through `contains_pii`; a lesson that still
    trips a detector after redaction is DROPPED, not stored redacted-ish. Losing
    a lesson costs a day of learning. Storing a passport number costs more than
    that. Fail-closed is the cheap side of this trade.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.services.mail_loop.state_io import write_private

logger = logging.getLogger(__name__)

# Cap per (intent, language) bucket. A style file that grows without bound stops
# fitting in the drafting prompt, and the oldest habits are the least current.
MAX_LESSONS_PER_BUCKET = 12

_HEADER = """# reply-style.md

Learned reply habits for the daily Zoho mail loop. AUTO-GENERATED — the loop
appends here after comparing its own draft against the mail Zero actually sent.

Read-only for humans in practice: edits survive (the loop only appends), but a
hand-written line will be counted against the per-bucket cap like any other.

NEVER put client data in this file. Lessons are statements about style. The
writer redacts and then drops anything that still looks like PII.
"""

# Redaction patterns. Order matters: structured identifiers first, then the
# generic catch-alls, so a passport number is not merely eaten by the digit rule
# and thereby mislabelled.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b"), "[NPWP]"),
    (re.compile(r"(?<![\w])\d{13,16}(?![\w])"), "[NIK-OR-NIB]"),
    (re.compile(r"(?<![\w])[A-Z]{1,2}\d{6,9}(?![\w])"), "[DOC-NO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"(?<![\w])\+?\d[\d\s().-]{7,}\d(?![\w])"), "[PHONE]"),
    (re.compile(r"(?<![\w])(?:Rp|IDR|USD|EUR|\$|€)\s?[\d.,]{4,}", re.I), "[AMOUNT]"),
)

# After redaction, a lesson matching any of these is discarded outright.
_PII_TRIPWIRES: tuple[re.Pattern[str], ...] = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"(?<![\w])\d{7,}(?![\w])"),
    re.compile(r"(?<![\w])[A-Z]{1,2}\d{6,9}(?![\w])"),
)


def redact(text: str) -> str:
    """Replace identifiers and contact details with tokens."""
    out = text
    for pattern, token in _REDACTIONS:
        out = pattern.sub(token, out)
    return out


def contains_pii(text: str) -> bool:
    """Fail-closed tripwire, run AFTER redaction."""
    return any(p.search(text) for p in _PII_TRIPWIRES)


@dataclass(frozen=True)
class Lesson:
    """One observation. `bucket` is intent + language, e.g. "visa/it"."""

    bucket: str
    text: str
    observed_on: str

    def render(self) -> str:
        return f"- ({self.observed_on}) {self.text}"


class ReplyStyleStore:
    """Append-only, bucketed markdown store.

    Concurrency: a process-level lock plus an atomic replace. Two runs of the
    daily loop should never overlap, but the wrapper is not the only possible
    caller and a torn style file is a silent corruption of the only state we
    keep.
    """

    _lock = threading.Lock()

    def __init__(self, path: Path) -> None:
        self.path = path

    # -- read ------------------------------------------------------------- #

    def _raw(self) -> str:
        if not self.path.exists():
            return _HEADER
        return self.path.read_text(encoding="utf-8")

    def buckets(self) -> dict[str, list[str]]:
        """Parse the file into {bucket: [lesson lines]}."""
        out: dict[str, list[str]] = {}
        current: str | None = None
        for line in self._raw().splitlines():
            if line.startswith("## "):
                current = line[3:].strip()
                out.setdefault(current, [])
            elif current and line.startswith("- "):
                out[current].append(line)
        return out

    def prompt_block(self, bucket: str, *, fallback_global: bool = True) -> str:
        """The slice of learned style handed to the drafting step.

        Returns the bucket's lessons plus the `global` bucket, which holds
        habits that are not lane-specific (sign-off, hedging posture).
        """
        parsed = self.buckets()
        lines = list(parsed.get(bucket, []))
        if fallback_global:
            lines.extend(parsed.get("global", []))
        if not lines:
            return "(no learned style yet — this is an early run)"
        return "\n".join(lines)

    # -- write ------------------------------------------------------------ #

    def append(self, lesson: Lesson) -> bool:
        """Store one lesson. Returns False when it was rejected or duplicate.

        Rejection reasons, all logged at WARNING so a silently-not-learning loop
        is visible rather than merely quiet (superscar #2):
          * empty after redaction
          * still tripping a PII detector after redaction
          * already present verbatim in the bucket
        """
        safe = redact(lesson.text).strip()
        if not safe:
            logger.warning("style: lesson empty after redaction, dropped")
            return False
        if contains_pii(safe):
            logger.warning(
                "style: lesson still matched a PII tripwire after redaction, "
                "DROPPED (bucket=%s)",
                lesson.bucket,
            )
            return False

        stored = Lesson(bucket=lesson.bucket, text=safe, observed_on=lesson.observed_on)

        with self._lock:
            parsed = self.buckets()
            existing = parsed.get(lesson.bucket, [])
            # Compare on the text only: the same habit re-observed on a later
            # day is not new information.
            if any(safe in line for line in existing):
                logger.debug("style: duplicate lesson, skipped")
                return False

            existing.append(stored.render())
            if len(existing) > MAX_LESSONS_PER_BUCKET:
                dropped = len(existing) - MAX_LESSONS_PER_BUCKET
                existing = existing[dropped:]
                logger.info(
                    "style: bucket=%s at cap, evicted %d oldest",
                    lesson.bucket,
                    dropped,
                )
            parsed[lesson.bucket] = existing
            self._write(parsed)
        return True

    def _write(self, parsed: dict[str, list[str]]) -> None:
        chunks = [_HEADER.rstrip(), ""]
        for bucket in sorted(parsed):
            chunks.append(f"## {bucket}")
            chunks.extend(parsed[bucket])
            chunks.append("")
        body = "\n".join(chunks).rstrip() + "\n"

        write_private(self.path, body)


def bucket_for(intent: str, language: str) -> str:
    """Bucket key. Kept as a function so the shape has one definition."""
    return f"{intent}/{language}"


def today() -> str:
    return date.today().isoformat()
