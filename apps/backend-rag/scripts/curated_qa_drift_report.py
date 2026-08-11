#!/usr/bin/env python3
"""Report curated-QA corpus files that have drifted from what production serves.

WHY THIS EXISTS
---------------
`curated_qa_harvest.py` already refuses to load a batch whose source file no
longer matches its manifest (`source_file_sha256`, Phase-0 FATAL 2). That gate
is correct and it is *not* the gap: it only fires **when somebody runs the
harvester**. Nothing tells you that edits are sitting on disk unharvested, so
the serving layer (Qdrant `curated_qa`, and the FAQ sink) can lag the vetted
answers indefinitely and read as healthy the whole time.

Measured on M5, 2026-08-11: **21 files, all in sync, zero pending promotions.**
The gap this closes is therefore structural, not a live incident — today the
corpus and the serving layer agree, and nothing existed that could tell you so.

That "all in sync" is itself the script's first useful result, because a
hand-measurement the same hour said the opposite: 7 mismatching manifests over
6 files. That was a probe defect, not drift — it dropped the *matching*
manifests before picking the newest one per file, so any file harvested twice
was judged on its stale manifest. Each of those 6 files does have a manifest
matching disk (verified per-file). Hence `_latest_manifest_per_file`, and hence
`test_the_older_of_two_manifests_does_not_invent_drift` — the exact false
positive, pinned so the tool cannot re-acquire it.

THE SAFETY-RELEVANT SUBSET
--------------------------
Drift is usually benign. One shape is not: a row whose `confidence_class`
becomes `JELAS` gains **verbatim eligibility**, and the exact-match FAQ sink
bypasses the abstain gate on every hit (see the corpus README). So a promotion
sitting unharvested is a pending change to what may be served with zero
reasoning. It is reported separately and it is the reason this script exists
rather than a one-line `sha256sum` loop.

Direction matters and is reported, never assumed. A reporter that cannot tell
"production is behind a STRICTER local copy" from "production is behind a
LOOSER one" ranks a harmless edit alongside a widening of what may be served
verbatim — and a report that ranks those the same is one people stop reading.

Pure reporter — it never writes, never harvests, never touches a sink.

The corpus is gitignored and ops-populated, so the default `--corpus-dir`
(derived from this file's location) is EMPTY inside any agent worktree — you
will get exit 4 there, not a drift crisis. Point it at the main checkout's
`apps/backend-rag/data/curated_qa`, which is where the ops-populated copy lives.

    python scripts/curated_qa_drift_report.py              # human summary
    python scripts/curated_qa_drift_report.py --json       # machine-readable
    python scripts/curated_qa_drift_report.py --strict     # exit 1 on any drift

Exit codes (bitwise, fail-visible):
    0  every harvested file matches disk
    1  at least one file drifted            (--strict only; else advisory)
    2  a promotion to JELAS is pending      (always non-zero, --strict or not)
    4  CANNOT VERIFY — no manifests, or no corpus dir. Never reported as clean:
       zero files traversed is not evidence of health (the blind-scan rule).
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_PENDING_PROMOTION = 2
EXIT_CANNOT_VERIFY = 4

VERBATIM_CLASS = "JELAS"


@dataclass
class FileVerdict:
    name: str
    domain: str | None
    state: str  # in_sync | drifted | source_missing | never_harvested
    rows_at_harvest: int | None = None
    rows_on_disk: int | None = None
    harvested_at: str | None = None
    faq_committed: bool | None = None
    classes_at_harvest: dict[str, int] = field(default_factory=dict)
    classes_on_disk: dict[str, int] = field(default_factory=dict)

    @property
    def promotion_pending(self) -> bool:
        """A row would GAIN verbatim eligibility if this file were harvested now.

        Compared on the histogram rather than per-row because the manifest
        records only the histogram — so this answers "does disk carry more
        JELAS than production does", which is exactly the question that
        matters for the abstain-bypassing sink.
        """
        if self.state != "drifted":
            return False
        return self.classes_on_disk.get(VERBATIM_CLASS, 0) > self.classes_at_harvest.get(
            VERBATIM_CLASS, 0
        )

    @property
    def demotion_pending(self) -> bool:
        """Disk is STRICTER than production — drift in the conservative
        direction. Still drift, but it does not widen what may be served
        verbatim, and saying so is the difference between a report someone
        acts on and one they learn to ignore."""
        if self.state != "drifted":
            return False
        return self.classes_on_disk.get(VERBATIM_CLASS, 0) < self.classes_at_harvest.get(
            VERBATIM_CLASS, 0
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_and_classify(path: Path) -> tuple[int, dict[str, int]]:
    """Row count + confidence-class histogram for a corpus file.

    Unparseable lines are counted under `__UNPARSEABLE__` rather than dropped:
    a corpus file that stopped being valid JSONL is a louder problem than
    drift, and silently skipping those lines would make it read as smaller.
    """
    rows = 0
    hist: collections.Counter[str] = collections.Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows += 1
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            hist["__UNPARSEABLE__"] += 1
            continue
        hist[str(rec.get("confidence_class", "__MISSING__"))] += 1
    return rows, dict(hist)


def _latest_manifest_per_file(manifest_dir: Path) -> dict[str, dict]:
    """Keep only the newest manifest per source file.

    A file harvested twice has two manifests; the older one always mismatches
    disk, so counting manifests instead of files inflates the drift count.
    (Measured: 28 manifests over 21 distinct files.)
    """
    latest: dict[str, dict] = {}
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        name = Path(str(data.get("source_file") or "")).name
        if not name:
            continue
        prev = latest.get(name)
        if prev is None or str(data.get("created_at", "")) > str(prev.get("created_at", "")):
            latest[name] = data
    return latest


def scan(corpus_dir: Path) -> tuple[list[FileVerdict], list[str]]:
    """Return (verdicts, problems). `problems` is non-empty when the scan
    itself could not be trusted — the caller turns that into exit bit 4."""
    problems: list[str] = []
    if not corpus_dir.is_dir():
        return [], [f"corpus dir not found: {corpus_dir}"]

    manifest_dir = corpus_dir / "_manifests"
    if not manifest_dir.is_dir():
        return [], [f"no _manifests/ under {corpus_dir} — nothing to compare against"]

    manifests = _latest_manifest_per_file(manifest_dir)
    on_disk = {p.name: p for p in sorted(corpus_dir.glob("*.jsonl"))}

    if not manifests and not on_disk:
        return [], [f"no manifests and no *.jsonl under {corpus_dir}"]
    if not manifests:
        problems.append(f"{len(on_disk)} corpus file(s) on disk but zero manifests")

    verdicts: list[FileVerdict] = []

    for name, data in sorted(manifests.items()):
        path = on_disk.get(name)
        if path is None:
            verdicts.append(
                FileVerdict(
                    name=name,
                    domain=data.get("domain"),
                    state="source_missing",
                    rows_at_harvest=data.get("row_count"),
                    harvested_at=data.get("created_at"),
                    faq_committed=data.get("faq_committed"),
                    classes_at_harvest=dict(data.get("class_histogram") or {}),
                )
            )
            continue

        rows, hist = _count_and_classify(path)
        drifted = _sha256(path) != str(data.get("source_file_sha256") or "")
        verdicts.append(
            FileVerdict(
                name=name,
                domain=data.get("domain"),
                state="drifted" if drifted else "in_sync",
                rows_at_harvest=data.get("row_count"),
                rows_on_disk=rows,
                harvested_at=data.get("created_at"),
                faq_committed=data.get("faq_committed"),
                classes_at_harvest=dict(data.get("class_histogram") or {}),
                classes_on_disk=hist,
            )
        )

    for name, path in on_disk.items():
        if name in manifests:
            continue
        rows, hist = _count_and_classify(path)
        verdicts.append(
            FileVerdict(
                name=name,
                domain=None,
                state="never_harvested",
                rows_on_disk=rows,
                classes_on_disk=hist,
            )
        )

    return verdicts, problems


def _render(verdicts: list[FileVerdict], problems: list[str]) -> str:
    by_state: collections.Counter[str] = collections.Counter(v.state for v in verdicts)
    lines: list[str] = []
    lines.append(
        "curated-QA corpus vs what production serves — "
        f"{len(verdicts)} file(s): " + ", ".join(f"{k}={v}" for k, v in sorted(by_state.items()))
    )

    promotions = [v for v in verdicts if v.promotion_pending]
    drifted = [v for v in verdicts if v.state == "drifted"]

    if promotions:
        lines.append("")
        lines.append("  PENDING VERBATIM PROMOTION — harvesting these widens what may be")
        lines.append("  served with the abstain gate bypassed. Review before re-harvest:")
        for v in promotions:
            was = v.classes_at_harvest.get(VERBATIM_CLASS, 0)
            now = v.classes_on_disk.get(VERBATIM_CLASS, 0)
            lines.append(f"    {v.name}: {VERBATIM_CLASS} {was} -> {now}  (domain={v.domain})")

    if drifted:
        lines.append("")
        lines.append("  DRIFTED (disk differs from the harvested copy):")
        for v in sorted(drifted, key=lambda x: x.name):
            direction = (
                "widens verbatim"
                if v.promotion_pending
                else "stricter than prod"
                if v.demotion_pending
                else "same class mix"
            )
            rows = (
                f"rows {v.rows_at_harvest}->{v.rows_on_disk}"
                if v.rows_at_harvest != v.rows_on_disk
                else f"rows {v.rows_on_disk} (content rewritten in place)"
            )
            lines.append(
                f"    {v.name}: {rows}; {direction}; "
                f"harvested {v.harvested_at}; faq_committed={v.faq_committed}"
            )

    for v in verdicts:
        if v.state == "source_missing":
            lines.append(f"  SOURCE MISSING: {v.name} was harvested but is no longer on disk")
        elif v.state == "never_harvested":
            lines.append(f"  NEVER HARVESTED: {v.name} ({v.rows_on_disk} rows) reaches no sink")

    for p in problems:
        lines.append(f"  CANNOT VERIFY: {p}")

    if not drifted and not problems and verdicts:
        lines.append("  every harvested file matches disk.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--corpus-dir",
        default=str(Path(__file__).resolve().parents[1] / "data" / "curated_qa"),
        help="directory holding the *.jsonl corpus and _manifests/",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any drift")
    args = ap.parse_args(argv)

    verdicts, problems = scan(Path(args.corpus_dir))

    if args.json:
        print(
            json.dumps(
                {
                    "files": [
                        {
                            "name": v.name,
                            "domain": v.domain,
                            "state": v.state,
                            "rows_at_harvest": v.rows_at_harvest,
                            "rows_on_disk": v.rows_on_disk,
                            "harvested_at": v.harvested_at,
                            "faq_committed": v.faq_committed,
                            "promotion_pending": v.promotion_pending,
                            "demotion_pending": v.demotion_pending,
                        }
                        for v in verdicts
                    ],
                    "problems": problems,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(_render(verdicts, problems))

    code = EXIT_OK
    if problems:
        code |= EXIT_CANNOT_VERIFY
    if any(v.promotion_pending for v in verdicts):
        code |= EXIT_PENDING_PROMOTION
    if args.strict and any(v.state in {"drifted", "source_missing"} for v in verdicts):
        code |= EXIT_DRIFT
    return code


if __name__ == "__main__":
    sys.exit(main())
