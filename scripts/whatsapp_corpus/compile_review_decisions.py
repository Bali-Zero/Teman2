from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)

DEFAULT_REVIEW_MANIFEST = Path("research/personal/wa-corpus/review/review_manifest.local.tsv")
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/decisions")

ALLOW_DECISIONS = frozenset({"allow_team_local", "allow_business_local"})
DENY_DECISIONS = frozenset({"deny_personal", "deny_sensitive"})
HOLD_DECISION = "unknown_hold"
VALID_DECISIONS = ALLOW_DECISIONS | DENY_DECISIONS | frozenset({HOLD_DECISION})


@dataclass(frozen=True)
class ReviewRow:
    rank: int
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    classification_label: str
    privacy_tier: str
    processing_gate: str
    message_start_count: int
    normalized_message_start_count: int
    min_timestamp: str | None
    max_timestamp: str | None
    confidence: float
    resolution_status: str
    local_path: str
    evidence_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]
    owner_decision: str
    owner_notes: str


@dataclass(frozen=True)
class DecisionRow:
    review: ReviewRow
    effective_decision: str
    decision_origin: str
    decision_reason: str


def split_codes(value: str | None) -> tuple[str, ...]:
    """Split comma-delimited evidence/warning codes from the private manifest."""
    if not value:
        return ()
    return tuple(item for item in (token.strip() for token in value.split(",")) if item)


def read_review_manifest(path: Path) -> list[ReviewRow]:
    """Read the private review manifest containing local raw paths."""
    if not path.exists():
        raise FileNotFoundError(f"Review manifest does not exist: {path}")

    rows: list[ReviewRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for raw in reader:
            rows.append(
                ReviewRow(
                    rank=int(raw["rank"]),
                    file_id=raw["file_id"],
                    source=raw["source"],
                    source_tag=raw["source_tag"] or None,
                    path_hash=raw["path_hash"],
                    classification_label=raw["classification_label"],
                    privacy_tier=raw["privacy_tier"],
                    processing_gate=raw["processing_gate"],
                    message_start_count=int(raw["message_start_count"]),
                    normalized_message_start_count=int(raw["normalized_message_start_count"]),
                    min_timestamp=raw["min_timestamp"] or None,
                    max_timestamp=raw["max_timestamp"] or None,
                    confidence=float(raw["confidence"]),
                    resolution_status=raw["resolution_status"],
                    local_path=raw["local_path"],
                    evidence_codes=split_codes(raw["evidence_codes"]),
                    warning_codes=split_codes(raw["warning_codes"]),
                    owner_decision=(raw.get("owner_decision") or "").strip(),
                    owner_notes=(raw.get("owner_notes") or "").strip(),
                )
            )
    return rows


def default_decision(row: ReviewRow) -> tuple[str, str]:
    """Return the conservative local default decision for a blank owner decision."""
    if (
        row.processing_gate == "local_only_team_analysis_after_owner_approval"
        and row.classification_label == "team_operator_archive_candidate"
    ):
        return (
            "allow_team_local",
            "safe_default_team_gate_after_owner_go",
        )
    if row.processing_gate == "deny_content_mining_until_owner_allowlist":
        return (
            "deny_personal",
            "safe_default_private_gate_denied",
        )
    if row.processing_gate == "manual_review_before_any_use":
        return (
            HOLD_DECISION,
            "safe_default_any_use_gate_held",
        )
    return (
        HOLD_DECISION,
        "safe_default_manual_review_gate_held",
    )


def compile_decision(row: ReviewRow, *, apply_safe_defaults: bool) -> DecisionRow:
    """Resolve owner decision plus optional safe default into an effective decision."""
    if row.owner_decision:
        if row.owner_decision not in VALID_DECISIONS:
            return DecisionRow(
                review=row,
                effective_decision=HOLD_DECISION,
                decision_origin="invalid_owner_decision",
                decision_reason=f"invalid value: {row.owner_decision}",
            )
        return DecisionRow(
            review=row,
            effective_decision=row.owner_decision,
            decision_origin="owner_manifest",
            decision_reason="owner_decision column set",
        )

    if not apply_safe_defaults:
        return DecisionRow(
            review=row,
            effective_decision=HOLD_DECISION,
            decision_origin="blank_owner_decision",
            decision_reason="no owner decision and safe defaults disabled",
        )

    decision, reason = default_decision(row)
    return DecisionRow(
        review=row,
        effective_decision=decision,
        decision_origin="safe_default",
        decision_reason=reason,
    )


def compile_decisions(rows: Iterable[ReviewRow], *, apply_safe_defaults: bool) -> list[DecisionRow]:
    """Compile review rows into local-only decisions."""
    return [
        compile_decision(row, apply_safe_defaults=apply_safe_defaults)
        for row in rows
    ]


def decision_bucket(decision: str) -> str:
    """Return the processing bucket for a decision value."""
    if decision in ALLOW_DECISIONS:
        return "allow"
    if decision in DENY_DECISIONS:
        return "deny"
    return "hold"


def write_decisions_manifest(path: Path, rows: list[DecisionRow]) -> None:
    """Write the private decision manifest with raw paths."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "file_id",
                "source",
                "source_tag",
                "path_hash",
                "classification_label",
                "privacy_tier",
                "processing_gate",
                "message_start_count",
                "normalized_message_start_count",
                "effective_decision",
                "decision_bucket",
                "decision_origin",
                "decision_reason",
                "resolution_status",
                "local_path",
                "owner_notes",
            ]
        )
        for row in rows:
            review = row.review
            writer.writerow(
                [
                    review.rank,
                    review.file_id,
                    review.source,
                    review.source_tag or "",
                    review.path_hash,
                    review.classification_label,
                    review.privacy_tier,
                    review.processing_gate,
                    review.message_start_count,
                    review.normalized_message_start_count,
                    row.effective_decision,
                    decision_bucket(row.effective_decision),
                    row.decision_origin,
                    row.decision_reason,
                    review.resolution_status,
                    review.local_path,
                    review.owner_notes,
                ]
            )


def write_jsonl(path: Path, rows: Iterable[DecisionRow]) -> None:
    """Write private decision rows as JSONL with local paths."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            review = row.review
            handle.write(
                json.dumps(
                    {
                        "file_id": review.file_id,
                        "source": review.source,
                        "source_tag": review.source_tag,
                        "path_hash": review.path_hash,
                        "classification_label": review.classification_label,
                        "privacy_tier": review.privacy_tier,
                        "processing_gate": review.processing_gate,
                        "message_start_count": review.message_start_count,
                        "normalized_message_start_count": review.normalized_message_start_count,
                        "effective_decision": row.effective_decision,
                        "decision_bucket": decision_bucket(row.effective_decision),
                        "decision_origin": row.decision_origin,
                        "resolution_status": review.resolution_status,
                        "local_path": review.local_path,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def count_by_attr(rows: Iterable[DecisionRow], attr_name: str) -> Counter[str]:
    """Count compiled rows by a ReviewRow attribute."""
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update([str(getattr(row.review, attr_name))])
    return counts


def count_by_decision(rows: Iterable[DecisionRow]) -> Counter[str]:
    """Count compiled rows by effective decision."""
    counts: Counter[str] = Counter()
    counts.update(row.effective_decision for row in rows)
    return counts


def count_by_bucket(rows: Iterable[DecisionRow]) -> Counter[str]:
    """Count compiled rows by allow/deny/hold bucket."""
    counts: Counter[str] = Counter()
    counts.update(decision_bucket(row.effective_decision) for row in rows)
    return counts


def message_totals_by_bucket(rows: Iterable[DecisionRow]) -> dict[str, tuple[int, int]]:
    """Return baseline and normalized message totals by bucket."""
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        bucket = decision_bucket(row.effective_decision)
        totals[bucket][0] += row.review.message_start_count
        totals[bucket][1] += row.review.normalized_message_start_count
    return {bucket: (values[0], values[1]) for bucket, values in totals.items()}


def write_safe_summary(
    *,
    summary_path: Path,
    review_manifest_path: Path,
    decisions_manifest_path: Path,
    allowlist_path: Path,
    denylist_path: Path,
    holdlist_path: Path,
    rows: list[DecisionRow],
    apply_safe_defaults: bool,
) -> None:
    """Write tracked decision summary without raw paths or raw names."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    decision_counts = count_by_decision(rows)
    bucket_counts = count_by_bucket(rows)
    gate_counts = count_by_attr(rows, "processing_gate")
    label_counts = count_by_attr(rows, "classification_label")
    totals_by_bucket = message_totals_by_bucket(rows)
    origin_counts = Counter(row.decision_origin for row in rows)

    lines: list[str] = [
        "# WhatsApp Review Decisions Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input review manifest: `{review_manifest_path.as_posix()}`",
        f"Private decisions manifest: `{decisions_manifest_path.as_posix()}`",
        f"Private allowlist: `{allowlist_path.as_posix()}`",
        f"Private denylist: `{denylist_path.as_posix()}`",
        f"Private holdlist: `{holdlist_path.as_posix()}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers.",
        "- This tracked summary contains no raw source paths.",
        "- This tracked summary contains no raw contact names.",
        "- The private `.local.*` files contain raw local paths and are ignored by git.",
        "",
        "## Policy",
        "",
        f"- Safe defaults applied: `{str(apply_safe_defaults).lower()}`.",
        "- `allow_team_local` and `allow_business_local` are eligible for local-only content mining.",
        "- `deny_personal`, `deny_sensitive`, and `unknown_hold` remain excluded from content mining.",
        "- No cloud upload is permitted for any bucket.",
        "",
        "## Decision Counts",
        "",
        "| Decision | Rows |",
        "|---|---:|",
    ]
    for decision, count in decision_counts.most_common():
        lines.append(f"| {decision} | {count} |")

    lines.extend(
        [
            "",
            "## Bucket Counts",
            "",
            "| Bucket | Rows | Baseline starts | Normalized starts |",
            "|---|---:|---:|---:|",
        ]
    )
    for bucket, count in bucket_counts.most_common():
        baseline, normalized = totals_by_bucket[bucket]
        lines.append(f"| {bucket} | {count} | {baseline} | {normalized} |")

    lines.extend(
        [
            "",
            "## Decision Origins",
            "",
            "| Origin | Rows |",
            "|---|---:|",
        ]
    )
    for origin, count in origin_counts.most_common():
        lines.append(f"| {origin} | {count} |")

    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Rows |",
            "|---|---:|",
        ]
    )
    for gate, count in gate_counts.most_common():
        lines.append(f"| {gate} | {count} |")

    lines.extend(
        [
            "",
            "## Labels",
            "",
            "| Label | Rows |",
            "|---|---:|",
        ]
    )
    for label, count in label_counts.most_common():
        lines.append(f"| {label} | {count} |")

    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Use only `content_allowlist.local.jsonl` as input to the next local-only parser/indexer. Do not read files from the denylist or holdlist.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_review_decisions(
    *,
    review_manifest_path: Path,
    output_dir: Path,
    apply_safe_defaults: bool,
) -> list[DecisionRow]:
    """Compile the private review manifest into local-only allow/deny/hold files."""
    rows = compile_decisions(
        read_review_manifest(review_manifest_path),
        apply_safe_defaults=apply_safe_defaults,
    )
    decisions_manifest_path = output_dir / "review_decisions.local.tsv"
    allowlist_path = output_dir / "content_allowlist.local.jsonl"
    denylist_path = output_dir / "content_denylist.local.jsonl"
    holdlist_path = output_dir / "content_holdlist.local.jsonl"
    summary_path = output_dir / "review_decisions_summary.md"

    write_decisions_manifest(decisions_manifest_path, rows)
    write_jsonl(allowlist_path, [row for row in rows if decision_bucket(row.effective_decision) == "allow"])
    write_jsonl(denylist_path, [row for row in rows if decision_bucket(row.effective_decision) == "deny"])
    write_jsonl(holdlist_path, [row for row in rows if decision_bucket(row.effective_decision) == "hold"])
    write_safe_summary(
        summary_path=summary_path,
        review_manifest_path=review_manifest_path,
        decisions_manifest_path=decisions_manifest_path,
        allowlist_path=allowlist_path,
        denylist_path=denylist_path,
        holdlist_path=holdlist_path,
        rows=rows,
        apply_safe_defaults=apply_safe_defaults,
    )
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Compile private WhatsApp review decisions into local-only allow/deny/hold lists."
    )
    parser.add_argument(
        "--review-manifest",
        type=Path,
        default=DEFAULT_REVIEW_MANIFEST,
        help="Private review_manifest.local.tsv produced by build_review_manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for private decision files and safe summary.",
    )
    parser.add_argument(
        "--apply-safe-defaults",
        action="store_true",
        help="Use conservative defaults for blank owner_decision cells.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        rows = compile_review_decisions(
            review_manifest_path=args.review_manifest,
            output_dir=args.output_dir,
            apply_safe_defaults=args.apply_safe_defaults,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    bucket_counts = count_by_bucket(rows)
    LOGGER.info("Compiled %d review decisions.", len(rows))
    LOGGER.info(
        "Buckets: allow=%d deny=%d hold=%d",
        bucket_counts.get("allow", 0),
        bucket_counts.get("deny", 0),
        bucket_counts.get("hold", 0),
    )
    LOGGER.info("Wrote %s", args.output_dir / "review_decisions_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
