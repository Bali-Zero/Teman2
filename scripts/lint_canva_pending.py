#!/usr/bin/env python3
"""Validator for `apps/war-room/output/canva/canva_pending_*.json`.

P1.5 (2026-05-26) — guard against the structural bugs caught by the 4-LLM panel.

Checks enforced (HARD = exit 1, SOFT = warn):

HARD:
- schema_version >= "wr2-canva-pending-v2.2"
- slides_count == declared, no >10 slides without `slides_dropped_reason` containing
  one of (drop|merge|split into part)
- operations_count == len(operations)
- ig_publish_max_items == 10 (Bali Zero constant)
- All operations have valid `type` (replace_text | upload-asset-from-url |
  insert-overlay-from-url | update_fill)
- _drop_page is BANNED (use copy_design page_numbers instead)
- hero_sha256_uniqueness_check.pairwise_distinct == true (Article 5.10.3)
- hero_sha256_uniqueness_check.anchor_distinct == true (Article 5.10.1)
- All slide indices referenced by operations are in [1..slides_count]

SOFT:
- hero_slide_indices declared matches sum of upload-asset-from-url operations
- apply_workflow present
- Every page in [1..slides_count] has at least 1 operation

Usage:
    python scripts/lint_canva_pending.py apps/war-room/output/canva/canva_pending_*.json

Exit codes:
    0 — all PASS
    1 — at least one HARD violation
    2 — usage / file-not-found error
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BANNED_OP_TYPES = {"_drop_page", "_drop_pages", "delete_page", "_dropped_op_was_drop_page"}
ALLOWED_OP_TYPES = {
    "replace_text",
    "upload-asset-from-url",
    "insert-overlay-from-url",
    "update_fill",
    "insert_fill",
    "delete_element",
    "find_and_replace_text",
    "format_text",
    "position_element",
    "resize_element",
    "update_title",
    "update_autofill_field",
}
IG_PUBLISH_MAX_ITEMS = 10
MIN_SCHEMA_VERSION = (2, 2)
SLIDES_DROPPED_REGEX = re.compile(
    r"\b(drop|dropped|merge|merged|split|splitting)\b", re.IGNORECASE
)


def _parse_schema_version(s: str | None) -> tuple[int, int] | None:
    if not s:
        return None
    m = re.search(r"v(\d+)\.(\d+)", s)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def lint(path: Path) -> tuple[list[str], list[str]]:
    """Return (hard_errors, soft_warnings)."""
    hard: list[str] = []
    soft: list[str] = []

    try:
        d = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        hard.append(f"INVALID JSON: {e}")
        return hard, soft

    # 1. Schema version
    sv = d.get("schema_version")
    parsed = _parse_schema_version(sv)
    if not parsed:
        hard.append(f"schema_version missing or unparseable: {sv!r}")
    elif parsed < MIN_SCHEMA_VERSION:
        hard.append(
            f"schema_version {sv!r} < required v{MIN_SCHEMA_VERSION[0]}.{MIN_SCHEMA_VERSION[1]}"
        )

    # 2. Slides count
    slides_count = d.get("slides_count")
    if not isinstance(slides_count, int) or slides_count < 1:
        hard.append(f"slides_count must be positive int, got {slides_count!r}")
    elif slides_count > IG_PUBLISH_MAX_ITEMS:
        reason = d.get("slides_dropped_reason", "") or ""
        if not SLIDES_DROPPED_REGEX.search(reason):
            hard.append(
                f"slides_count={slides_count} > IG max {IG_PUBLISH_MAX_ITEMS} "
                f"and slides_dropped_reason does not document a drop/merge/split strategy. "
                f"Got reason: {reason[:120]!r}"
            )

    # 3. Operations count
    ops = d.get("operations", [])
    ops_declared = d.get("operations_count")
    if not isinstance(ops, list):
        hard.append("operations must be a list")
    elif ops_declared != len(ops):
        hard.append(
            f"operations_count {ops_declared} != actual {len(ops)} in operations array"
        )

    # 4. IG publish max items constant
    cap = d.get("ig_publish_max_items")
    if cap != IG_PUBLISH_MAX_ITEMS:
        hard.append(
            f"ig_publish_max_items must be {IG_PUBLISH_MAX_ITEMS}, got {cap!r}. "
            f"This is a Bali Zero constant tied to apps/backend-rag/backend/services/publisher/ig_publisher.py:106."
        )

    # 5. Operation types valid + no banned types
    if isinstance(ops, list):
        for i, op in enumerate(ops):
            t = op.get("type")
            if t in BANNED_OP_TYPES:
                hard.append(
                    f"operations[{i}]: type {t!r} is BANNED. "
                    f"Use copy_design(page_numbers=[...]) in apply_workflow step 1 instead of in-transaction page drops."
                )
            elif t not in ALLOWED_OP_TYPES:
                hard.append(
                    f"operations[{i}]: unknown type {t!r}. "
                    f"Allowed: {sorted(ALLOWED_OP_TYPES)}"
                )

    # 6. Hero sha256 uniqueness
    h = d.get("hero_sha256_uniqueness_check", {})
    if not h.get("pairwise_distinct"):
        hard.append(
            "hero_sha256_uniqueness_check.pairwise_distinct must be true "
            "(Article 5.10.3 — hero photos must have distinct sha256)"
        )
    if not h.get("anchor_distinct"):
        hard.append(
            "hero_sha256_uniqueness_check.anchor_distinct must be true "
            "(Article 5.10.1 — hero sha256 must differ from anchor sha256)"
        )

    # 7. Page indices in range
    if isinstance(ops, list) and isinstance(slides_count, int):
        for i, op in enumerate(ops):
            p = op.get("page_index")
            if not isinstance(p, int):
                hard.append(f"operations[{i}]: page_index must be int, got {p!r}")
            elif p < 1 or p > slides_count:
                hard.append(
                    f"operations[{i}]: page_index={p} out of range [1..{slides_count}]"
                )

    # 8. SOFT: hero count consistency
    uploads = [op for op in ops if op.get("type") == "upload-asset-from-url"]
    hero_indices_declared = d.get("hero_slide_indices", [])
    if isinstance(hero_indices_declared, list) and len(uploads) != len(
        hero_indices_declared
    ):
        # Some hero slides may use anchor reuse (Article 5.10.2) without upload op
        # That's OK — just warn so operator sees the gap intentionally
        diff = len(hero_indices_declared) - len(uploads)
        if diff > 0:
            soft.append(
                f"hero_slide_indices declares {len(hero_indices_declared)} hero slides "
                f"but only {len(uploads)} upload-asset-from-url ops. "
                f"{diff} slide(s) may use anchor reuse (Article 5.10.2 exception) — verify intentional."
            )
        else:
            soft.append(
                f"hero_slide_indices declares {len(hero_indices_declared)} hero slides "
                f"but {len(uploads)} upload ops — MORE uploads than declared heroes. Possible drift."
            )

    # 9. SOFT: apply_workflow present
    if not d.get("apply_workflow"):
        soft.append(
            "apply_workflow missing — recommended in v2.2+ for explicit MCP execution steps "
            "(copy_design → upload → start_editing_transaction → perform_editing_operations → commit)"
        )

    # 10. SOFT: every page has at least 1 op
    if isinstance(ops, list) and isinstance(slides_count, int):
        pages_with_ops = {op.get("page_index") for op in ops if isinstance(op.get("page_index"), int)}
        for p in range(1, slides_count + 1):
            if p not in pages_with_ops:
                soft.append(f"page {p} has no operations — slide will inherit template content unchanged")

    return hard, soft


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    files = [Path(p) for p in argv[1:]]
    missing = [p for p in files if not p.exists()]
    if missing:
        for p in missing:
            print(f"NOT FOUND: {p}", file=sys.stderr)
        return 2

    overall_hard = 0
    overall_soft = 0
    for p in files:
        print(f"\n=== lint: {p} ===")
        hard, soft = lint(p)
        for h in hard:
            print(f"  [HARD] {h}")
        for w in soft:
            print(f"  [WARN] {w}")
        if not hard and not soft:
            print("  PASS — no issues")
        elif not hard:
            print(f"  PASS_WITH_WARNINGS — {len(soft)} soft warnings, 0 hard errors")
        else:
            print(f"  FAIL — {len(hard)} hard errors, {len(soft)} soft warnings")
        overall_hard += len(hard)
        overall_soft += len(soft)

    print(f"\n=== summary ===")
    print(f"hard errors total: {overall_hard}")
    print(f"soft warnings total: {overall_soft}")
    print(f"files: {len(files)}")
    return 1 if overall_hard > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
