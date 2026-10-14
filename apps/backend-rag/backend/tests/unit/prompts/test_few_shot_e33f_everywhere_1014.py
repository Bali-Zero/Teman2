"""Guilt + innocence tests for E33F everywhere in few-shot examples & worked examples (2026-10-14).

Verifies:
1. Every exported few-shot list (GENERAL_FEW_SHOT_EXAMPLES, WHATSAPP_FEW_SHOT_EXAMPLES,
   and whatsapp_persona.FEW_SHOT_EXAMPLES) is free of internal catalogue row names
   (loaded dynamically from bali_zero_official_prices_2026.json where "internal": true)
   and free of the bare product name 'Retirement KITAS'.
2. Every 'N juta' figure in a retirement/E33F few-shot message equals a canonical
   E33F Second Home Senior row price from the JSON catalogue.
3. Innocence: the E33F Second Home Senior KITAS reply is present with 14 and 16 juta
   and canonical requirements; the E33G remote-worker examples are untouched and
   len(whatsapp_persona.FEW_SHOT_EXAMPLES) == 18.
4. Guilt: the checker function flags the old 'Retirement KITAS ...' reply fixture as
   well as messages containing internal row names or non-canonical juta figures.
5. zantara_core_v4 and zantara_core_v5 worked examples do not contain
   'KITAS pensiun (Retirement)', 'bukti dana pensiun', 'sponsor lokal', or
   'asuransi kesehatan', and do contain 'E33F'.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.prompts import few_shot_examples, whatsapp_persona, zantara_core_v4, zantara_core_v5

CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "bali_zero_official_prices_2026.json"
)

OLD_FEW_SHOT_RETIREMENT_REPLY_FIXTURE = (
    "Retirement KITAS 14 juta (Offshore) atau 16 juta (Altus). "
    "Syaratnya umur minimal 55 tahun, asuransi kesehatan, dan bukti dana pensiun. "
    "Mau saya jelaskan dokumen lengkapnya?"
)

OLD_V4_WORKED_EXAMPLE_FIXTURE = (
    'Indonesian:\n'
    '  User: "Saya mau tanya soal KITAS pensiun, syaratnya apa saja?"\n'
    '  → CALL knowledge_graph_search("KITAS pensiun retirement requirements")\n'
    '  → Answer: "KITAS pensiun (Retirement) membutuhkan: usia minimal 55\n'
    '             tahun, asuransi kesehatan, bukti dana pensiun, dan\n'
    '             sponsor lokal. Mau saya jelaskan dokumen lengkapnya?"'
)

RETIREMENT_E33F_KEYWORDS = ("kitas pensiun", "e33f", "second home", "retirement")
FORBIDDEN_RETIREMENT_CLAIMS = ("asuransi kesehatan", "dana pensiun", "sponsor lokal")


def _iter_catalog_service_rows(catalog: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Walk all service entries in the 2026 catalogue (including 3-level sub-blocks)."""
    rows: list[tuple[str, dict[str, Any]]] = []
    services = catalog.get("services", {})

    def _is_entry(obj: Any) -> bool:
        return isinstance(obj, dict) and ("price" in obj or "tier_range" in obj)

    for _category, category_items in services.items():
        if not isinstance(category_items, dict):
            continue
        for item_name, item_data in category_items.items():
            if not isinstance(item_data, dict):
                continue
            if (
                not _is_entry(item_data)
                and item_data
                and all(_is_entry(v) for v in item_data.values())
            ):
                for sub_name, sub_entry in item_data.items():
                    if isinstance(sub_entry, dict):
                        rows.append((sub_name, sub_entry))
                continue
            rows.append((item_name, item_data))
    return rows


def load_internal_row_names(catalog_path: Path = CATALOG_PATH) -> set[str]:
    """Read row names marked 'internal': true from the canonical JSON at test time."""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    internal_names = {
        name
        for name, row in _iter_catalog_service_rows(catalog)
        if row.get("internal") is True
    }
    assert len(internal_names) >= 3, "Expected at least the 3 internal Retirement rows in JSON"
    return internal_names


def load_e33f_juta_prices(catalog_path: Path = CATALOG_PATH) -> set[int]:
    """Derive canonical 'N juta' integer figures from 'E33F Second Home Senior*' rows."""
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    juta_prices: set[int] = set()
    for name, row in _iter_catalog_service_rows(catalog):
        if name.startswith("E33F Second Home Senior"):
            raw_price = str(row.get("price", ""))
            match = re.match(r"^\s*(\d+)\.000\.000\s+IDR\s*$", raw_price)
            assert match is not None, f"Unexpected price format on {name!r}: {raw_price!r}"
            juta_prices.add(int(match.group(1)))
    assert juta_prices, "Expected canonical E33F Second Home Senior prices in JSON"
    return juta_prices


def find_few_shot_e33f_violations(
    messages: list[dict[str, Any]],
    internal_names: set[str],
    e33f_juta_prices: set[int],
) -> list[str]:
    """Return all E33F-everywhere violations found across a list of few-shot messages."""
    violations: list[str] = []

    for idx, msg in enumerate(messages):
        content = str(msg.get("content", ""))
        content_lower = content.lower()

        for internal_name in sorted(internal_names):
            if internal_name.lower() in content_lower:
                violations.append(
                    f"msg[{idx}] names internal catalogue row {internal_name!r}"
                )

        if "retirement kitas" in content_lower:
            violations.append(
                f"msg[{idx}] contains bare product name 'Retirement KITAS'"
            )

        is_retirement_or_e33f = any(kw in content_lower for kw in RETIREMENT_E33F_KEYWORDS)
        if is_retirement_or_e33f:
            for match in re.finditer(r"\b(\d+)\s*juta\b", content, flags=re.IGNORECASE):
                figure = int(match.group(1))
                if figure not in e33f_juta_prices:
                    violations.append(
                        f"msg[{idx}] has non-canonical E33F price '{figure} juta' "
                        f"(canonical: {sorted(e33f_juta_prices)})"
                    )

            for forbidden in FORBIDDEN_RETIREMENT_CLAIMS:
                if forbidden in content_lower:
                    violations.append(
                        f"msg[{idx}] contains non-canonical retirement claim {forbidden!r}"
                    )

    return violations


def find_worked_example_e33f_violations(prompt_source: str) -> list[str]:
    """Return violations in zantara_core_v4 / v5 worked-example source text."""
    violations: list[str] = []
    if "KITAS pensiun (Retirement)" in prompt_source:
        violations.append("contains stale 'KITAS pensiun (Retirement)'")
    for forbidden in FORBIDDEN_RETIREMENT_CLAIMS:
        if forbidden in prompt_source.lower():
            violations.append(f"contains non-canonical claim {forbidden!r}")
    if "E33F" not in prompt_source:
        violations.append("missing canonical 'E33F' reference")
    return violations


class TestFewShotE33FEverywhere:
    """Guilt and innocence tests for few-shot lists and whatsapp_persona re-export."""

    def test_exported_lists_have_zero_violations(self) -> None:
        internal_names = load_internal_row_names()
        e33f_prices = load_e33f_juta_prices()

        for list_name, messages in (
            ("GENERAL_FEW_SHOT_EXAMPLES", few_shot_examples.GENERAL_FEW_SHOT_EXAMPLES),
            ("WHATSAPP_FEW_SHOT_EXAMPLES", few_shot_examples.WHATSAPP_FEW_SHOT_EXAMPLES),
            ("whatsapp_persona.FEW_SHOT_EXAMPLES", whatsapp_persona.FEW_SHOT_EXAMPLES),
        ):
            violations = find_few_shot_e33f_violations(messages, internal_names, e33f_prices)
            assert violations == [], f"{list_name} failed E33F checks: {violations}"

    def test_innocence_e33f_reply_present_with_canonical_facts_and_prices(self) -> None:
        examples = few_shot_examples.GENERAL_FEW_SHOT_EXAMPLES
        pensiun_replies = [
            examples[i + 1]["content"]
            for i in range(len(examples) - 1)
            if examples[i].get("role") == "user"
            and "kitas pensiun" in str(examples[i].get("content", "")).lower()
        ]
        assert len(pensiun_replies) == 1
        reply = pensiun_replies[0]

        assert "E33F Second Home Senior" in reply
        assert "14 juta" in reply
        assert "16 juta" in reply
        assert "55 tahun" in reply
        assert "USD 3.000" in reply or "USD 3,000" in reply
        assert "penghasilan atau tunjangan" in reply
        assert "tanpa deposit" in reply
        assert "penjamin" in reply
        assert "Bali Zero" in reply
        assert "asuransi kesehatan" not in reply.lower()
        assert "dana pensiun" not in reply.lower()
        assert "Retirement KITAS" not in reply
        assert reply.endswith("?")

    def test_innocence_e33g_remote_worker_examples_untouched(self) -> None:
        assert len(whatsapp_persona.FEW_SHOT_EXAMPLES) == 18

        general_text = " ".join(
            str(m.get("content", "")) for m in few_shot_examples.GENERAL_FEW_SHOT_EXAMPLES
        )
        whatsapp_text = " ".join(
            str(m.get("content", "")) for m in whatsapp_persona.FEW_SHOT_EXAMPLES
        )

        assert "E33G" in general_text
        assert "13 juta" in general_text
        assert "E33G" in whatsapp_text
        assert "13 juta" in whatsapp_text
        assert "14 juta" in whatsapp_text

    def test_guilt_old_reply_fixture_is_flagged(self) -> None:
        internal_names = load_internal_row_names()
        e33f_prices = load_e33f_juta_prices()

        violations = find_few_shot_e33f_violations(
            [{"role": "assistant", "content": OLD_FEW_SHOT_RETIREMENT_REPLY_FIXTURE}],
            internal_names,
            e33f_prices,
        )
        assert violations, "Expected old Retirement KITAS reply fixture to be flagged"
        joined = " | ".join(violations)
        assert "Retirement KITAS" in joined
        assert "asuransi kesehatan" in joined
        assert "dana pensiun" in joined

    def test_guilt_internal_row_name_and_wrong_juta_price_are_flagged(self) -> None:
        internal_names = load_internal_row_names()
        e33f_prices = load_e33f_juta_prices()
        sample_internal_name = sorted(internal_names)[0]

        synthetic_bad_messages = [
            {
                "role": "assistant",
                "content": f"Untuk KITAS pensiun pilih {sample_internal_name} seharga 15 juta.",
            }
        ]
        violations = find_few_shot_e33f_violations(
            synthetic_bad_messages,
            internal_names,
            e33f_prices,
        )
        joined = " | ".join(violations)
        assert sample_internal_name in joined
        assert "15 juta" in joined


class TestZantaraCoreV4AndV5WorkedExampleE33F:
    """Guilt and innocence tests for zantara_core_v4 and zantara_core_v5 worked examples."""

    def test_innocence_v4_and_v5_contain_e33f_and_no_retirement_kitas_pensiun(self) -> None:
        for label, source in (
            ("v4.WORKED_EXAMPLES", zantara_core_v4.WORKED_EXAMPLES),
            ("v4.ZANTARA_MASTER_TEMPLATE", zantara_core_v4.ZANTARA_MASTER_TEMPLATE),
            ("v5.WORKED_EXAMPLES", zantara_core_v5.WORKED_EXAMPLES),
            ("v5.CORE_FACTUAL", zantara_core_v5.CORE_FACTUAL),
        ):
            violations = find_worked_example_e33f_violations(source)
            assert violations == [], f"{label} failed E33F worked-example check: {violations}"
            assert "KITAS pensiun (Retirement)" not in source
            assert "E33F" in source
            assert "E33F Second Home Senior" in source
            assert "penjamin" in source
            assert "USD 3.000" in source or "USD 3,000" in source

    def test_guilt_old_v4_worked_example_fixture_is_flagged(self) -> None:
        violations = find_worked_example_e33f_violations(OLD_V4_WORKED_EXAMPLE_FIXTURE)
        assert violations, "Expected old v4 worked example fixture to be flagged"
        joined = " | ".join(violations)
        assert "KITAS pensiun (Retirement)" in joined
        assert "asuransi kesehatan" in joined
        assert "dana pensiun" in joined
        assert "sponsor lokal" in joined
        assert "missing canonical 'E33F' reference" in joined
