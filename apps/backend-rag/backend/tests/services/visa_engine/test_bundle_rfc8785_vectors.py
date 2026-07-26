"""RFC 8785 (JSON Canonicalization Scheme) cross-language test vectors.

Mandatory per spec §3 ("Cross-language RFC 8785 test vectors are
mandatory."). The primary vector is transcribed verbatim from the RFC text
itself (section 3.2.2/3.2.3, fetched live from
https://www.rfc-editor.org/rfc/rfc8785.txt during authoring) — the exact
official "parse this JSON, canonicalize it" example the spec defines JCS
against, not an invented approximation. A handful of smaller, self-derived
vectors round out property-sorting/nesting/unicode edge cases the RFC
example doesn't individually isolate.

Pure ``canonicalize_json`` tests — no dependency on ``models.py`` at all, so
this file needed zero adaptation for the PR2b API-A port (see ``bundle.py``'s
module docstring).
"""

from __future__ import annotations

import json

from backend.services.visa_engine.bundle import canonicalize_json


class TestOfficialRfc8785Example:
    """RFC 8785 §3.2.2 (input) / §3.2.3 (canonical output) — the ONE example
    the spec text itself walks through end to end."""

    def test_numbers_string_literals_example(self) -> None:
        # Input JSON exactly as printed in the RFC (escapes written literally
        # so `json.loads` decodes them the same way any compliant JSON
        # parser would — including the deliberately non-canonical `1E30`,
        # `4.50` trailing zero, and the escaped-vs-raw string forms).
        input_text = (
            "{\n"
            '  "numbers": [333333333.33333329, 1E30, 4.50,\n'
            "              2e-3, 0.000000000000000000000000001],\n"
            '  "string": "\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/",\n'
            '  "literals": [null, true, false]\n'
            "}"
        )
        parsed = json.loads(input_text)

        actual = canonicalize_json(parsed)

        # RFC 8785 §3.2.3's canonical output, unwrapped to one line. The
        # euro sign is emitted RAW (UTF-8 bytes), not `€` escaped —
        # only the ASCII-control-range 0x0F and the predefined `\n`/`\"`/`\\`
        # escapes stay escaped (§3.2.2.2: non-control chars are serialized
        # "as is").
        expected = (
            '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,'
            '0.002,1e-27],"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
        ).encode()

        assert actual == expected
        # Sanity: both sides parse back to the identical logical value —
        # canonicalization must never change MEANING, only byte-shape.
        assert json.loads(actual.decode("utf-8")) == parsed


class TestPropertySortingAndNesting:
    """Self-derived vectors isolating §3.2.3's recursive lexicographic
    property-sorting rule (not itself the RFC's headline example, but
    explicitly required behavior: "JSON child Objects MUST have their
    properties sorted as well" / "array element order MUST NOT be
    changed")."""

    def test_top_level_keys_sorted_lexicographically(self) -> None:
        value = {"b": 1, "a": 2, "c": 3}
        assert canonicalize_json(value) == b'{"a":2,"b":1,"c":3}'

    def test_nested_object_keys_sorted_recursively(self) -> None:
        value = {"outer_z": {"z": 1, "a": 2}, "outer_a": True}
        assert canonicalize_json(value) == b'{"outer_a":true,"outer_z":{"a":2,"z":1}}'

    def test_array_element_order_preserved(self) -> None:
        # Array order is data, never re-sorted — only object KEYS are.
        value = {"items": [{"z": 1, "a": 2}, {"y": 3, "b": 4}]}
        assert canonicalize_json(value) == b'{"items":[{"a":2,"z":1},{"b":4,"y":3}]}'

    def test_no_whitespace_emitted(self) -> None:
        value = {"a": [1, 2, 3], "b": "x"}
        actual = canonicalize_json(value)
        assert b" " not in actual
        assert b"\n" not in actual
        assert actual == b'{"a":[1,2,3],"b":"x"}'
