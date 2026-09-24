#!/usr/bin/env python3
"""Remove the two invented-content blocks the pre-#7209 News Room converter
wrote into every article, and ONLY those blocks, byte-exact elsewhere.

Block 1 — the "Quick Summary" InfoCard under `## TL;DR`. The converter always
emitted exactly:

    <InfoCard
      title="Quick Summary"
      items={[
        { label: "Should I Worry?", value: "Yes" | "Depends" | "No" },
        { label: "Risk Level", value: "High" | "Medium" | "Low" },
        { label: "Who's Affected", value: "Expats and investors in Indonesia" },
        { label: "When", value: "Check article for specific dates" },
      ]}
    />

Any InfoCard titled "Quick Summary" that deviates from this shape in any way
(different label set/order, a value outside the enum, extra/missing items)
is a hand-edited card and is left untouched — it is reported as "deviating"
so a human can look at it.

Block 2 — the filler Checklist item the converter wrote for "For Expats" /
"For Investors" whenever it had nothing specific to say:

    { text: "For Expats", subItems: ["Review the article for specific actions"] }

Only an item whose `subItems` array is EXACTLY that one string is removed.
If removing filler items empties a Checklist's `items` array, the whole
`<Checklist .../>` is removed. If that was the only content of its
`## Next Steps` section, the heading and the now-redundant `---` separator
are removed too (collapsing back to a single separator between the
sections that remain).

Frontmatter and every other line are left byte-identical. The script never
touches an InfoCard whose title isn't exactly "Quick Summary", and never
touches a Checklist item whose subItems don't match the filler string
exactly — those are reported, never guessed at.

Usage:
    python3 strip_legacy_tldr_filler.py --root <content-dir> [--write] [--json report.json]

Without --write, the script only reports what it WOULD do (dry run).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Generic JSX-ish balanced scanner
# ---------------------------------------------------------------------------

_OPENERS = "{[("
_CLOSERS = "}])"


def find_component_span(text: str, tag: str, start: int = 0) -> tuple[int, int] | None:
    """Find the next `<Tag ... />` self-closing component at/after `start`.

    Returns (open_idx, close_idx_exclusive) spanning from `<Tag` through the
    matching `/>`, tracking nested {[()]} and quoted strings so that a
    `/>`-looking substring inside a JS string value never terminates early.
    Returns None if no such component is found.
    """
    marker = "<" + tag
    idx = text.find(marker, start)
    while idx != -1:
        after = idx + len(marker)
        # Guard against matching a longer component name sharing the prefix.
        if after < len(text) and text[after] not in (" ", "\n", "\t", "/", ">"):
            idx = text.find(marker, idx + 1)
            continue
        end = _scan_to_self_close(text, after)
        if end is not None:
            return idx, end
        idx = text.find(marker, idx + 1)
    return None


def iter_component_spans(text: str, tag: str):
    pos = 0
    while True:
        span = find_component_span(text, tag, pos)
        if span is None:
            return
        yield span
        pos = span[1]


def _scan_to_self_close(text: str, start: int) -> int | None:
    """From `start` (just after the tag name), scan for `/>` at bracket
    depth 0, skipping over quoted strings. Returns the index just past the
    `/>`, or None if the text ends first."""
    depth = 0
    in_str = False
    quote = ""
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                in_str = False
            i += 1
            continue
        if c == '"' or c == "'":
            in_str = True
            quote = c
            i += 1
            continue
        if c in _OPENERS:
            depth += 1
            i += 1
            continue
        if c in _CLOSERS:
            depth -= 1
            i += 1
            continue
        if depth == 0 and text[i : i + 2] == "/>":
            return i + 2
        i += 1
    return None


def _scan_balanced(text: str, start: int) -> int:
    """text[start] must be an opening bracket. Return the index just past
    its matching close, tracking nested brackets and quoted strings."""
    assert text[start] in _OPENERS
    depth = 0
    in_str = False
    quote = ""
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                in_str = False
            i += 1
            continue
        if c == '"' or c == "'":
            in_str = True
            quote = c
            i += 1
            continue
        if c in _OPENERS:
            depth += 1
            i += 1
            continue
        if c in _CLOSERS:
            depth -= 1
            i += 1
            if depth == 0:
                return i
            continue
        i += 1
    raise ValueError("unbalanced brackets in component body")


def top_level_object_items(text: str, arr_start: int, arr_end_close: int) -> list[tuple[int, int]]:
    """Given the char range of an array's contents (text[arr_start] is the
    char right after '[', arr_end_close is the index of the matching ']'),
    return the (start, end) spans of each top-level `{...}` object item,
    end being exclusive (just past the item's own closing '}')."""
    items = []
    i = arr_start
    while i < arr_end_close:
        c = text[i]
        if c == "{":
            end = _scan_balanced(text, i)
            items.append((i, end))
            i = end
            continue
        i += 1
    return items


# ---------------------------------------------------------------------------
# InfoCard ("Quick Summary" TL;DR card)
# ---------------------------------------------------------------------------

_WORRY_VALUES = {"Yes", "Depends", "No"}
_RISK_VALUES = {"High", "Medium", "Low"}
_WHO_VALUE = "Expats and investors in Indonesia"
_WHEN_VALUE = "Check article for specific dates"

_ITEM_RE = re.compile(
    r'\{\s*label:\s*"((?:[^"\\]|\\.)*)"\s*,\s*value:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*\}',
    re.DOTALL,
)

_TITLE_RE = re.compile(r'title\s*=\s*"([^"]*)"')


@dataclass
class InfoCardFinding:
    file: str
    matched: bool
    reason: str
    items_preview: list[tuple[str, str]] = field(default_factory=list)


def analyze_info_card(text: str, span: tuple[int, int]) -> InfoCardFinding | None:
    """Return an InfoCardFinding for a "Quick Summary"-titled InfoCard, or
    None if this InfoCard isn't titled "Quick Summary" at all (out of
    scope — some articles embed unrelated InfoCards elsewhere)."""
    s, e = span
    block = text[s:e]
    title_m = _TITLE_RE.search(block)
    title = title_m.group(1) if title_m else None
    if title != "Quick Summary":
        return None

    items_kw = block.find("items={[")
    if items_kw == -1:
        return InfoCardFinding("", False, "quick-summary-titled but no items={[ array found")
    arr_open = items_kw + len("items={")  # index of '['
    arr_close = _scan_balanced(block, arr_open)  # index just past matching ']'
    inner = block[arr_open + 1 : arr_close - 1]

    matches = _ITEM_RE.findall(inner)
    # Structural exactness: the whole inner content, once whitespace/commas
    # around each matched item are discounted, must consist of exactly
    # those matched items and nothing else.
    reconstructed = "".join(m.group(0) for m in _ITEM_RE.finditer(inner))
    stripped_inner = re.sub(r"\s|,", "", inner)
    stripped_reconstructed = re.sub(r"\s|,", "", reconstructed)
    structurally_exact = stripped_inner == stripped_reconstructed

    if len(matches) != 4 or not structurally_exact:
        return InfoCardFinding(
            "", False, f"{len(matches)} label/value pairs (expected 4) or extra content in items array",
            items_preview=matches,
        )

    labels = [m[0] for m in matches]
    values = [m[1] for m in matches]
    expected_labels = ["Should I Worry?", "Risk Level", "Who's Affected", "When"]
    if labels != expected_labels:
        return InfoCardFinding("", False, f"label set/order differs: {labels}", items_preview=matches)
    if values[0] not in _WORRY_VALUES:
        return InfoCardFinding("", False, f'"Should I Worry?" value {values[0]!r} not in {_WORRY_VALUES}', items_preview=matches)
    if values[1] not in _RISK_VALUES:
        return InfoCardFinding("", False, f'"Risk Level" value {values[1]!r} not in {_RISK_VALUES}', items_preview=matches)
    if values[2] != _WHO_VALUE:
        return InfoCardFinding("", False, f'"Who\'s Affected" value differs: {values[2]!r}', items_preview=matches)
    if values[3] != _WHEN_VALUE:
        return InfoCardFinding("", False, f'"When" value differs: {values[3]!r}', items_preview=matches)

    return InfoCardFinding("", True, "exact converter shape", items_preview=matches)


def strip_info_card(text: str) -> tuple[str, list[InfoCardFinding]]:
    """Remove every exact-match "Quick Summary" InfoCard block (+ the blank
    line that follows it) from `text`. Returns (new_text, findings) where
    findings covers every "Quick Summary"-titled card seen (matched or
    deviating)."""
    findings: list[InfoCardFinding] = []
    out = []
    pos = 0
    for s, e in iter_component_spans(text, "InfoCard"):
        finding = analyze_info_card(text, (s, e))
        if finding is None:
            continue
        findings.append(finding)
        if not finding.matched:
            continue
        # Remove text[s:e] plus exactly one following blank line.
        out.append(text[pos:s])
        after = e
        # Skip the newline that ends the "/>" line.
        if after < len(text) and text[after] == "\n":
            after += 1
        # Skip exactly one blank line (a line containing only whitespace).
        line_end = text.find("\n", after)
        if line_end == -1:
            line_end = len(text)
        if text[after:line_end].strip() == "":
            after = line_end + 1 if line_end < len(text) else line_end
        pos = after
    out.append(text[pos:])
    return "".join(out), findings


# ---------------------------------------------------------------------------
# Checklist filler item ("For Expats" / "For Investors" -> "Review the
# article for specific actions")
# ---------------------------------------------------------------------------

_FILLER_ITEM_RE = re.compile(
    r'^\{\s*text:\s*"(?:[^"\\]|\\.)*"\s*,\s*subItems:\s*\[\s*'
    r'"Review the article for specific actions"\s*,?\s*\]\s*,?\s*\}$',
    re.DOTALL,
)


@dataclass
class ChecklistOutcome:
    filler_items_removed: int = 0
    checklist_removed: bool = False
    section_removed: bool = False


def _line_span_for_item(text: str, item_start: int, item_end: int) -> tuple[int, int] | None:
    """Expand an item's char span to the whole-line range that can be
    deleted cleanly: from the start of the item's own line through the end
    of the line containing its trailing comma (if any). Returns None if the
    item shares a line with other non-whitespace content that isn't part of
    the item itself (defensive: refuse to touch anything unexpected)."""
    line_start = text.rfind("\n", 0, item_start) + 1
    if text[line_start:item_start].strip() != "":
        return None
    end = item_end
    if end < len(text) and text[end] == ",":
        end += 1
    line_end = text.find("\n", end)
    line_end = line_end + 1 if line_end != -1 else len(text)
    if text[end:line_end].strip() != "":
        return None
    return line_start, line_end


def _process_checklist(text: str, span: tuple[int, int]) -> tuple[str, ChecklistOutcome] | None:
    """Process one <Checklist .../> block. Returns (replacement_text_for_
    the_whole_span, outcome) or None if this Checklist has no filler items
    (leave untouched)."""
    s, e = span
    block = text[s:e]
    items_kw = block.find("items={[")
    if items_kw == -1:
        return None
    arr_open = items_kw + len("items={")
    arr_close = _scan_balanced(block, arr_open)
    item_spans = top_level_object_items(block, arr_open + 1, arr_close - 1)
    if not item_spans:
        return None

    filler_spans = []
    for (a, b) in item_spans:
        raw = block[a:b]
        if _FILLER_ITEM_RE.match(raw):
            filler_spans.append((a, b))

    if not filler_spans:
        return None

    outcome = ChecklistOutcome(filler_items_removed=len(filler_spans))

    if len(filler_spans) == len(item_spans):
        # Every item is filler -> remove the whole Checklist component.
        outcome.checklist_removed = True
        return "", outcome

    # Remove only the filler items, each as a whole-line delete.
    line_ranges = []
    for (a, b) in filler_spans:
        lr = _line_span_for_item(block, a, b)
        if lr is None:
            # Unexpected layout for a filler item -> be conservative, don't
            # touch this Checklist at all.
            return None
        line_ranges.append(lr)
    line_ranges.sort()
    pieces = []
    cursor = 0
    for (ls, le) in line_ranges:
        pieces.append(block[cursor:ls])
        cursor = le
    pieces.append(block[cursor:])
    new_block = "".join(pieces)
    return new_block, outcome


def strip_checklist_filler(text: str) -> tuple[str, ChecklistOutcome]:
    total = ChecklistOutcome()
    out = []
    pos = 0
    running_len = 0
    # Offsets (in the text being assembled) right where a whole Checklist
    # was deleted -> candidates for an now-orphaned heading cleanup.
    deletion_points: list[int] = []
    for s, e in iter_component_spans(text, "Checklist"):
        result = _process_checklist(text, (s, e))
        if result is None:
            continue
        new_block, outcome = result
        total.filler_items_removed += outcome.filler_items_removed
        piece = text[pos:s]
        out.append(piece)
        running_len += len(piece)
        if outcome.checklist_removed:
            total.checklist_removed = True
            deletion_points.append(running_len)
        out.append(new_block)
        running_len += len(new_block)
        pos = e
    out.append(text[pos:])
    new_text = "".join(out)

    if deletion_points:
        new_text, removed_count = _cleanup_empty_sections(new_text, deletion_points)
        total.section_removed = removed_count > 0

    return new_text, total


_SEP_RE = re.compile(r"^---[ \t]*\n", re.MULTILINE)
_HEADING_RE = re.compile(r"^##[ \t]", re.MULTILINE)


def _cleanup_empty_sections(text: str, deletion_points: list[int]) -> tuple[str, int]:
    """For each offset where a whole Checklist was just deleted, find the
    heading immediately above it (whatever its text — "## Next Steps" in
    English articles, "## Prochaines étapes" / "## Prossimi passi" /
    "## Следующие шаги" in translated ones, etc: the heading text itself is
    NEVER what gates this, only whether its section is now empty) and, if
    that heading's whole section is now nothing but blank lines, remove the
    heading too. Processes deletion points right-to-left so earlier offsets
    stay valid as the text shrinks. Returns (new_text, sections_removed)."""
    removed_count = 0
    for point in sorted(deletion_points, reverse=True):
        text, removed = _cleanup_one_heading_if_empty(text, point)
        if removed:
            removed_count += 1
    return text, removed_count


def _cleanup_one_heading_if_empty(text: str, near_point: int) -> tuple[str, bool]:
    """Find the last `##` heading starting before `near_point` (the heading
    that used to sit directly above the just-deleted Checklist) and, if its
    section body is now nothing but blank lines, remove it.

    A section's body ends at the EARLIEST of: the next `---` separator
    line, the next `##` heading line, or EOF — some articles run two
    sections back-to-back with no `---` between them, so a `---`-only
    boundary search would swallow an unrelated following section (e.g.
    a heading directly followed by `## Primary Source`, no `---` in
    between). Only ever touches a section whose body is nothing but blank
    lines; otherwise leaves it untouched.

    - If the boundary is a `---` separator and only blank lines sit between
      the `---` preceding the heading and the heading itself, that trailing
      separator is redundant and is dropped too (collapsing back to a single
      separator). If anything else sits there — a section with no separator
      of its own, or body prose right under the frontmatter — only the
      heading and its blank body go, and the trailing `---` stays as the
      boundary.
    - If the boundary is another heading or EOF, there is nothing to
      collapse: the heading and its blank body are simply excised, and the
      untouched `---` (or content) that preceded it now sits directly
      before the next heading/EOF, exactly as it does elsewhere in these
      files.
    """
    heading_start = None
    for hm in _HEADING_RE.finditer(text, 0, near_point):
        heading_start = hm.start()
    if heading_start is None:
        return text, False

    line_end = text.find("\n", heading_start)
    body_start = line_end + 1 if line_end != -1 else len(text)

    next_sep = _SEP_RE.search(text, body_start)
    next_heading = _HEADING_RE.search(text, body_start)
    candidates = [c.start() for c in (next_sep, next_heading) if c is not None]
    boundary_start = min(candidates) if candidates else len(text)
    boundary_is_sep = next_sep is not None and next_sep.start() == boundary_start

    body = text[body_start:boundary_start]
    if body.strip() != "":
        return text, False  # section still has content -> leave alone

    if not boundary_is_sep:
        # Next boundary is another heading (or EOF) -> just excise the
        # empty heading + its blank body, nothing to merge.
        new_text = text[:heading_start] + text[boundary_start:]
        return new_text, True

    # Boundary is a redundant trailing '---' -> merge with the '---' that
    # preceded this heading.
    prev_sep_end = None
    for sm in _SEP_RE.finditer(text, 0, heading_start):
        prev_sep_end = sm.end()
    if prev_sep_end is None:
        return text, False  # no preceding separator -> unexpected shape, skip
    if text[prev_sep_end:heading_start].strip() != "":
        # Content sits between that '---' and this heading (a section with no
        # separator of its own, or body prose under the frontmatter's closing
        # line): merging from the '---' would delete it. Excise only the empty
        # heading and keep the trailing '---' as the boundary.
        return text[:heading_start] + text[boundary_start:], True

    # `tail` already starts with the blank line that followed the trailing
    # '---' (or is empty at EOF) — do not add another newline here, or the
    # merge leaves two blank lines where every other section boundary in
    # these files has exactly one.
    tail = text[next_sep.end() :]
    new_text = text[:prev_sep_end] + tail
    return new_text, True


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def process_file(path: Path) -> dict:
    original = path.read_text(encoding="utf-8")
    text = original

    text, info_findings = strip_info_card(text)
    text, checklist_outcome = strip_checklist_filler(text)

    matched_cards = [f for f in info_findings if f.matched]
    deviating_cards = [f for f in info_findings if not f.matched]

    changed = text != original
    return {
        "path": str(path),
        "changed": changed,
        "new_text": text,
        "cards_removed": len(matched_cards),
        "cards_deviating": [f.reason for f in deviating_cards],
        "filler_items_removed": checklist_outcome.filler_items_removed,
        "checklists_removed": 1 if checklist_outcome.checklist_removed else 0,
        "next_steps_sections_removed": 1 if checklist_outcome.section_removed else 0,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="Directory to walk for *.mdx files")
    ap.add_argument("--write", action="store_true", help="Actually rewrite changed files (default: dry run)")
    ap.add_argument("--json", help="Path to write a JSON report")
    args = ap.parse_args(argv)

    root = Path(args.root)
    files = sorted(root.rglob("*.mdx"))

    totals = {
        "files_scanned": 0,
        "files_changed": 0,
        "cards_removed": 0,
        "cards_deviating": 0,
        "filler_items_removed": 0,
        "checklists_removed": 0,
        "next_steps_sections_removed": 0,
    }
    deviating_examples = []
    changed_files = []

    for path in files:
        totals["files_scanned"] += 1
        result = process_file(path)
        totals["cards_removed"] += result["cards_removed"]
        totals["cards_deviating"] += len(result["cards_deviating"])
        totals["filler_items_removed"] += result["filler_items_removed"]
        totals["checklists_removed"] += result["checklists_removed"]
        totals["next_steps_sections_removed"] += result["next_steps_sections_removed"]
        if result["cards_deviating"]:
            deviating_examples.append({"path": result["path"], "reasons": result["cards_deviating"]})
        if result["changed"]:
            totals["files_changed"] += 1
            changed_files.append(result["path"])
            if args.write:
                path.write_text(result["new_text"], encoding="utf-8")

    report = {
        "totals": totals,
        "changed_files": changed_files,
        "deviating_examples": deviating_examples,
        "write_mode": args.write,
    }
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(totals, indent=2))
    if not args.write:
        print("(dry run — pass --write to apply)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
