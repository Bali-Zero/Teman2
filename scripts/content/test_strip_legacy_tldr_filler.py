"""Unit tests for strip_legacy_tldr_filler.py.

Guilt cases: exact converter shapes get removed.
Innocence cases: anything that deviates, even slightly, is left byte-exact.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from strip_legacy_tldr_filler import process_file, strip_checklist_filler, strip_info_card  # noqa: E402

FRONTMATTER = """---
title: "Example Article"
slug: "example-article"
excerpt: "Example Article"
coverImage: "/static/news/example-article.jpg"
coverImageAlt: "Example Article"
category: "immigration"
tags: ["immigration", "example"]
publishedAt: "2026-03-14"
author: "Test Author"
trending: false
featured: false
readingTime: 3
difficulty: "intermediate"
seoTitle: "Example Article..."
seoDescription: "Example Article"
---
"""


def make_article(tldr_block: str, next_steps_block: str = "") -> str:
    parts = [FRONTMATTER, "\n## TL;DR\n\n", tldr_block, "\n**This is the summary.**\n\n---\n\n## The Facts\n\nSome facts here.\n"]
    if next_steps_block:
        parts.append("\n---\n\n## Next Steps\n\n")
        parts.append(next_steps_block)
    parts.append(
        "\n---\n\n<AskZantara\n"
        '  question="Have questions about this topic?"\n'
        '  placeholder="Ask Zantara AI for personalized advice..."\n'
        "/>\n"
    )
    return "".join(parts)


EXACT_CARD = (
    "<InfoCard\n"
    '  title="Quick Summary"\n'
    "  items={[\n"
    '    { label: "Should I Worry?", value: "Yes" },\n'
    '    { label: "Risk Level", value: "High" },\n'
    '    { label: "Who\'s Affected", value: "Expats and investors in Indonesia" },\n'
    '    { label: "When", value: "Check article for specific dates" },\n'
    "  ]}\n"
    "/>\n"
)


# ---------------------------------------------------------------------------
# Guilt: InfoCard
# ---------------------------------------------------------------------------


def test_exact_converter_card_is_removed():
    text = make_article(EXACT_CARD)
    new_text, findings = strip_info_card(text)
    assert "<InfoCard" not in new_text
    assert len(findings) == 1
    assert findings[0].matched
    assert "## TL;DR\n\n**This is the summary.**" in new_text


def test_exact_converter_card_all_worry_risk_enum_values_removed():
    for worry in ("Yes", "Depends", "No"):
        for risk in ("High", "Medium", "Low"):
            card = (
                "<InfoCard\n"
                '  title="Quick Summary"\n'
                "  items={[\n"
                f'    {{ label: "Should I Worry?", value: "{worry}" }},\n'
                f'    {{ label: "Risk Level", value: "{risk}" }},\n'
                '    { label: "Who\'s Affected", value: "Expats and investors in Indonesia" },\n'
                '    { label: "When", value: "Check article for specific dates" },\n'
                "  ]}\n"
                "/>\n"
            )
            new_text, findings = strip_info_card(make_article(card))
            assert findings[0].matched, (worry, risk)
            assert "<InfoCard" not in new_text


# ---------------------------------------------------------------------------
# Innocence: InfoCard
# ---------------------------------------------------------------------------


def test_hand_edited_value_is_untouched():
    card = EXACT_CARD.replace('value: "Yes"', 'value: "Somewhat"')
    text = make_article(card)
    new_text, findings = strip_info_card(text)
    assert new_text == text  # byte-identical, nothing removed
    assert len(findings) == 1
    assert not findings[0].matched


def test_hand_edited_who_value_is_untouched():
    card = EXACT_CARD.replace(
        "Expats and investors in Indonesia", "Expats living in Bali on a KITAS"
    )
    text = make_article(card)
    new_text, findings = strip_info_card(text)
    assert new_text == text
    assert len(findings) == 1
    assert not findings[0].matched


def test_different_title_infocard_is_out_of_scope_and_untouched():
    card = (
        "<InfoCard\n"
        '  title="Working Visa (KITAS - 1-2 years):"\n'
        "  items={[\n"
        '    { label: "Cost", value: "USD 500" },\n'
        '    { label: "Duration", value: "12 months" },\n'
        "  ]}\n"
        "/>\n"
    )
    text = make_article(EXACT_CARD) + "\n" + card
    new_text, findings = strip_info_card(text)
    # The unrelated card must survive untouched; only the exact one is gone.
    assert card in new_text
    assert len(findings) == 1  # only the "Quick Summary" card is analyzed


def test_extra_label_in_items_is_untouched():
    card = EXACT_CARD.replace(
        "  ]}\n", '    { label: "Extra", value: "Field" },\n  ]}\n'
    )
    text = make_article(card)
    new_text, findings = strip_info_card(text)
    assert new_text == text
    assert not findings[0].matched


# ---------------------------------------------------------------------------
# Guilt: Checklist filler item
# ---------------------------------------------------------------------------

CHECKLIST_ONE_FILLER_ONE_REAL = (
    "<Checklist\n"
    '  title="Action Items"\n'
    "  items={[\n"
    "    {\n"
    '      text: "For Expats",\n'
    '      subItems: ["Review the article for specific actions"],\n'
    "    },\n"
    "    {\n"
    '      text: "For Investors",\n'
    '      subItems: ["Confirm your KBLI code before signing a lease."],\n'
    "    },\n"
    "  ]}\n"
    "/>\n"
)

CHECKLIST_BOTH_FILLER = (
    "<Checklist\n"
    '  title="Action Items"\n'
    "  items={[\n"
    "    {\n"
    '      text: "For Expats",\n'
    '      subItems: ["Review the article for specific actions"],\n'
    "    },\n"
    "    {\n"
    '      text: "For Investors",\n'
    '      subItems: ["Review the article for specific actions"],\n'
    "    },\n"
    "  ]}\n"
    "/>\n"
)

CHECKLIST_SINGLE_LINE_BOTH_FILLER = (
    "<Checklist\n"
    '  title="Action Items"\n'
    "  items={[\n"
    '    { text: "For Expats", subItems: ["Review the article for specific actions"] },\n'
    '    { text: "For Investors", subItems: ["Review the article for specific actions"] },\n'
    "  ]}\n"
    "/>\n"
)

CHECKLIST_REAL = (
    "<Checklist\n"
    '  title="Action Items"\n'
    "  items={[\n"
    "    {\n"
    '      text: "For Expats",\n'
    '      subItems: ["Confirm your KITAS is still valid.", "File your annual report."],\n'
    "    },\n"
    "    {\n"
    '      text: "For Investors",\n'
    '      subItems: ["Review the PT PMA minimum investment threshold."],\n'
    "    },\n"
    "  ]}\n"
    "/>\n"
)


def test_filler_item_removed_real_item_kept():
    text = make_article(EXACT_CARD, CHECKLIST_ONE_FILLER_ONE_REAL)
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.filler_items_removed == 1
    assert not outcome.checklist_removed
    assert "For Expats" not in new_text
    assert "For Investors" in new_text
    assert "Confirm your KBLI code before signing a lease." in new_text
    assert "## Next Steps" in new_text  # section survives, real item remains


def test_both_filler_removes_whole_checklist_and_empty_section():
    text = make_article(EXACT_CARD, CHECKLIST_BOTH_FILLER)
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.filler_items_removed == 2
    assert outcome.checklist_removed
    assert outcome.section_removed
    assert "<Checklist" not in new_text
    assert "## Next Steps" not in new_text
    # exactly one '---' separator remains between Facts and AskZantara, with
    # exactly one blank line on each side of it (no double blank line left
    # behind by the merge).
    tail = new_text.split("## The Facts", 1)[1]
    assert tail.count("---") == 1
    assert "<AskZantara" in new_text
    assert "\n\n---\n\n<AskZantara" in new_text
    assert "\n\n\n" not in new_text


def test_single_line_filler_items_both_removed():
    text = make_article(EXACT_CARD, CHECKLIST_SINGLE_LINE_BOTH_FILLER)
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.filler_items_removed == 2
    assert outcome.checklist_removed
    assert "<Checklist" not in new_text


# ---------------------------------------------------------------------------
# Innocence: Checklist
# ---------------------------------------------------------------------------


def test_checklist_with_real_steps_untouched():
    text = make_article(EXACT_CARD, CHECKLIST_REAL)
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.filler_items_removed == 0
    assert not outcome.checklist_removed
    assert new_text == text


def test_next_steps_immediately_followed_by_another_heading_no_separator():
    # Regression: some articles run "## Next Steps" straight into the next
    # "## " heading with no "---" between them. The empty-section cleanup
    # must stop at that heading, not swallow it looking for a "---".
    text = (
        FRONTMATTER
        + "\n## TL;DR\n\n"
        + EXACT_CARD
        + "\n**Summary.**\n\n---\n\n## The Facts\n\nFacts.\n\n---\n\n## Next Steps\n\n"
        + CHECKLIST_BOTH_FILLER
        + "\n## Primary Source\n\n[Source](https://example.com)\n\n---\n\n<AskZantara\n"
        '  question="Have questions about this topic?"\n'
        '  placeholder="Ask Zantara AI for personalized advice..."\n'
        "/>\n"
    )
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.checklist_removed
    assert outcome.section_removed
    assert "## Next Steps" not in new_text
    assert "<Checklist" not in new_text
    assert "## Primary Source" in new_text
    assert "[Source](https://example.com)" in new_text
    assert "---\n\n## Primary Source" in new_text


def test_emptied_section_after_an_unseparated_section_keeps_that_section():
    # Innocence (gate BLOCK on #7324): the separator merge cut from the LAST
    # '---' above the emptied heading, swallowing a whole section that sat
    # between that '---' and "## Next Steps" with no separator of its own.
    text = (
        FRONTMATTER
        + "\nIntro.\n\n---\n\n## What It Means\n\nReal analysis prose that must survive.\n\n"
        + "## Next Steps\n\n"
        + CHECKLIST_BOTH_FILLER
        + "\n---\n\n## Primary Source\n\n[Source](https://example.com)\n"
    )
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.section_removed
    assert "## Next Steps" not in new_text
    assert "## What It Means\n\nReal analysis prose that must survive.\n\n---\n\n## Primary Source" in new_text


def test_emptied_section_right_after_frontmatter_prose_keeps_the_prose():
    # Innocence (gate BLOCK on #7324): with no body separator above the
    # emptied section, the "last '---'" was the frontmatter's closing line,
    # so the merge deleted the article's opening paragraph.
    text = (
        FRONTMATTER
        + "\nIntro paragraph that must survive.\n\n## Next Steps\n\n"
        + CHECKLIST_BOTH_FILLER
        + "\n---\n\n## Primary Source\n\n[Source](https://example.com)\n"
    )
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.section_removed
    assert new_text.startswith(FRONTMATTER)
    assert "Intro paragraph that must survive.\n\n---\n\n## Primary Source" in new_text


def test_next_steps_with_other_content_besides_checklist_keeps_heading():
    extra = "Some hand-written note.\n\n" + CHECKLIST_BOTH_FILLER
    text = make_article(EXACT_CARD, extra)
    new_text, outcome = strip_checklist_filler(text)
    assert outcome.checklist_removed
    assert not outcome.section_removed
    assert "## Next Steps" in new_text
    assert "Some hand-written note." in new_text


# ---------------------------------------------------------------------------
# Frontmatter byte-identity + full-file integration
# ---------------------------------------------------------------------------


def test_frontmatter_byte_identical_after_full_processing(tmp_path):
    text = make_article(EXACT_CARD, CHECKLIST_BOTH_FILLER)
    p = tmp_path / "article.mdx"
    p.write_text(text, encoding="utf-8")
    result = process_file(p)
    assert result["changed"]
    new_frontmatter = result["new_text"].split("---\n", 2)[0] + "---\n"
    old_frontmatter = text.split("---\n", 2)[0] + "---\n"
    assert new_frontmatter == old_frontmatter
    assert result["cards_removed"] == 1
    assert result["filler_items_removed"] == 2
    assert result["checklists_removed"] == 1
    assert result["next_steps_sections_removed"] == 1


def test_untouched_file_reports_zero_changes(tmp_path):
    card = EXACT_CARD.replace('value: "Yes"', 'value: "Somewhat"')
    text = make_article(card, CHECKLIST_REAL)
    p = tmp_path / "article.mdx"
    p.write_text(text, encoding="utf-8")
    result = process_file(p)
    assert not result["changed"]
    assert result["new_text"] == text
    assert result["cards_removed"] == 0
    assert len(result["cards_deviating"]) == 1
    assert result["filler_items_removed"] == 0
