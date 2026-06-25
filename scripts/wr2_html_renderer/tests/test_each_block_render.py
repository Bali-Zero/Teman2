"""Regression test for the {{#each}} list-block render bug (2026-06-25).

Slides 3/6/7 of `indonesia-visafree-myth-reality` shipped with RAW Handlebars
placeholders (`{{#each items}}`, `{{LABEL}}`, `{{VALUE}}`) because _fill_placeholders
never expanded {{#each}} blocks: the storyboarder emits `list_items` / `qa_pairs`,
the templates iterate `items` / want flat `voice_a/b_*`, and nothing bridged them.

This test pins both halves of the cure:
  - _expand_each_blocks: binds the loop (alias list_items→items), drops the block
    when the array is missing (NEVER ships raw {{#each}}), escapes row copy.
  - _qa_dialogue_fields: maps qa_pairs[0/1] → voice_a/voice_b flat fields.

Innocence: a slide with no {{#each}} block is returned byte-identical.
Guilt: a dark-status-list template with list_items → rows materialized, zero
raw mustache left.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from wr2_html_renderer import composer as C  # noqa: E402


def _check(name: str, got: bool, want: bool = True) -> bool:
    ok = got == want
    print(f"  {'✅' if ok else '❌'} {name}")
    return ok


def main() -> int:
    passed = True

    # --- GUILT: dark-status-list each block binds from list_items -------------
    tmpl = (
        '<div class="items">{{#each items}}'
        '<div class="item status-{{status}}">'
        '<div class="label">{{label}}</div>'
        '<div class="value">{{value}}</div>'
        "</div>{{/each}}</div>"
    )
    slide = {
        "layout_family": "dark-status-list",
        "list_items": [
            {"label": "FRAMEWORK", "value": "Perpres 95/2024", "status": "neutral"},
            {"label": "BVK LIST", "value": "16 nationalities", "status": "positive"},
        ],
    }
    out = C._expand_each_blocks(tmpl, slide)
    passed &= _check("guilt: no raw {{#each}} left", "{{#each" not in out)
    passed &= _check("guilt: no raw {{label}} left", "{{label}}" not in out)
    passed &= _check("guilt: no raw {{value}} left", "{{value}}" not in out)
    passed &= _check("guilt: FRAMEWORK row rendered", "FRAMEWORK" in out)
    passed &= _check("guilt: BVK row rendered", "BVK LIST" in out)
    passed &= _check("guilt: status class bound", 'status-positive' in out)
    # count only row divs (`class="item `), not the wrapper (`class="items"`)
    passed &= _check("guilt: both rows present (2 items)", out.count('class="item ') == 2)

    # --- GUILT: {{this}} scalar rows (evidence-carved facts) ------------------
    tmpl2 = "<ul>{{#each facts}}<li>{{this}}</li>{{/each}}</ul>"
    out2 = C._expand_each_blocks(tmpl2, {"facts": ["FACT ONE", "FACT TWO"]})
    passed &= _check("guilt: {{this}} scalar bound", "FACT ONE" in out2 and "FACT TWO" in out2)
    passed &= _check("guilt: no raw {{this}}", "{{this}}" not in out2)

    # --- INNOCENCE: no each block → unchanged --------------------------------
    plain = '<div class="heading">{{heading}}</div><div class="body">{{body}}</div>'
    out3 = C._expand_each_blocks(plain, {"heading": "X"})
    passed &= _check("innocence: no-each html unchanged", out3 == plain)

    # --- GUILT-by-absence: each block with missing array is DROPPED ----------
    out4 = C._expand_each_blocks(tmpl, {"layout_family": "dark-status-list"})  # no list_items
    passed &= _check("absent-array: block dropped, no raw {{#each}}", "{{#each" not in out4)
    passed &= _check("absent-array: no leftover {{label}}", "{{label}}" not in out4)

    # --- qa-dialogue: qa_pairs → flat voice fields ---------------------------
    qa = {
        "layout_family": "qa-dialogue",
        "qa_pairs": [
            {"voice": "INVESTOR", "line": "IS JAPAN VISA-FREE?"},
            {"voice": "BALI ZERO", "line": "NO. NOT ON THE LIST."},
        ],
    }
    fields = C._qa_dialogue_fields(qa)
    passed &= _check("qa: voice_a_label = INVESTOR", fields.get("voice_a_label") == "INVESTOR")
    passed &= _check("qa: voice_a_quote bound", fields.get("voice_a_quote") == "IS JAPAN VISA-FREE?")
    passed &= _check("qa: voice_b_label = BALI ZERO", fields.get("voice_b_label") == "BALI ZERO")
    passed &= _check("qa: voice_b_quote bound", fields.get("voice_b_quote") == "NO. NOT ON THE LIST.")
    passed &= _check("qa: empty pairs → {}", C._qa_dialogue_fields({"qa_pairs": []}) == {})

    # --- HTML escaping: row copy with < > & is escaped -----------------------
    out5 = C._expand_each_blocks(
        "{{#each items}}<li>{{value}}</li>{{/each}}",
        {"items": [{"value": "a < b & c"}]},
    )
    passed &= _check("escaping: < and & escaped in row", "&lt;" in out5 and "&amp;" in out5)

    print()
    print("RESULT:", "ALL PASS" if passed else "FAILURES")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
