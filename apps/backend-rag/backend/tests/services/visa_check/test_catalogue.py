"""Catalogue structure + seed drift guard.

Parses the authoritative seed at test time and asserts every VisaType
is (a) present in the seed and (b) has matching name/category.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from backend.services.visa_check.catalogue import (
    DEFAULT_DURATION_DAYS,
    EXTENSION_POLICY,
    VISA_META,
    VisaMeta,
    VisaType,
)
from backend.services.visa_check.match_tree import Purpose


def _find_repo_root(start: Path) -> Path:
    """Walk up from `start` until a directory containing `.git` is found.

    Works for both plain checkouts (`.git/` dir) and worktrees
    (`.git` file pointing to the real gitdir). Fails loudly if no
    repo root is found — never silently resolves to the filesystem root.
    """
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError(f"no .git found walking up from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
SEED_PATH = (
    REPO_ROOT / "apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py"
)
PACKS_DIR = (
    REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
)


def _load_seed() -> dict[str, dict]:
    src = SEED_PATH.read_text()
    m = re.search(r"VISA_TYPES\s*=\s*(\[.*?\n\])\s*\n\nasync def", src, re.DOTALL)
    assert m, "cannot parse seed VISA_TYPES"
    data = ast.literal_eval(m.group(1))
    return {v["code"]: v for v in data}


class TestEnumStability:
    def test_b211a_removed(self):
        assert not hasattr(VisaType, "B211A"), "B211A must not exist — it is not in the seed"

    def test_all_20_codes_present(self):
        expected = {
            "B1",
            "C1",
            "C2",
            "C6",
            "C7",
            "C7A",
            "C7B",
            "C18",
            "C22A",
            "D2",
            "D12",
            "E23",
            "E23-FREELANCE",
            "E28A",
            "E30A",
            "E31",
            "E33",
            "E33E",
            "E33F",
            "E33G",
        }
        got = {vt.value for vt in VisaType}
        assert got == expected, (
            f"VisaType values drift: extra={got - expected} missing={expected - got}"
        )

    def test_e23_freelance_has_hyphen_value(self):
        assert VisaType.E23_FREELANCE.value == "E23-FREELANCE"


class TestVisaMetaCompleteness:
    def test_every_visatype_has_meta(self):
        for vt in VisaType:
            assert vt in VISA_META, f"VISA_META missing entry for {vt.value}"

    def test_meta_is_visameta_instance(self):
        for vt, meta in VISA_META.items():
            assert isinstance(meta, VisaMeta), f"{vt.value} meta wrong type"

    def test_meta_required_fields_non_empty(self):
        for vt, meta in VISA_META.items():
            assert meta.name_en, f"{vt.value} missing name_en"
            assert meta.name_id, f"{vt.value} missing name_id"
            assert meta.category, f"{vt.value} missing category"
            assert meta.duration_days > 0, f"{vt.value} invalid duration_days"
            assert len(meta.extensions) == 2, f"{vt.value} extensions not (count, days)"
            assert meta.seed_source in {"seed", "seed+NB2"}, f"{vt.value} unknown seed_source"
            assert meta.duration_source, f"{vt.value} missing duration_source"


class TestSeedAgreement:
    def setup_method(self):
        self.seed = _load_seed()

    def test_every_visatype_code_in_seed(self):
        for vt in VisaType:
            assert vt.value in self.seed, f"VisaType.{vt.name}='{vt.value}' not in seed"

    def test_name_en_matches_seed(self):
        for vt, meta in VISA_META.items():
            seed_name = self.seed[vt.value]["name"]
            assert meta.name_en == seed_name, (
                f"{vt.value} name drift: meta={meta.name_en!r} seed={seed_name!r}"
            )

    def test_name_id_matches_seed(self):
        for vt, meta in VISA_META.items():
            seed_name_id = self.seed[vt.value]["metadata"]["name_id"]
            assert meta.name_id == seed_name_id, (
                f"{vt.value} name_id drift: meta={meta.name_id!r} seed={seed_name_id!r}"
            )

    def test_category_matches_seed(self):
        for vt, meta in VISA_META.items():
            seed_cat = self.seed[vt.value]["category"]
            assert meta.category == seed_cat, (
                f"{vt.value} category drift: meta={meta.category!r} seed={seed_cat!r}"
            )


class TestDerivedDicts:
    def test_default_duration_days_covers_all_types(self):
        for vt in VisaType:
            assert vt in DEFAULT_DURATION_DAYS
            assert DEFAULT_DURATION_DAYS[vt] == VISA_META[vt].duration_days

    def test_extension_policy_covers_all_types(self):
        for vt in VisaType:
            assert vt in EXTENSION_POLICY
            assert EXTENSION_POLICY[vt] == VISA_META[vt].extensions

    def test_c1_extensions_match_reference(self):
        # MEMORY.md reference_visa_c_duration_rules: C1 = 60 + 2×60
        assert DEFAULT_DURATION_DAYS[VisaType.C1] == 60
        assert EXTENSION_POLICY[VisaType.C1] == (2, 60)

    def test_c7a_non_extendable(self):
        assert EXTENSION_POLICY[VisaType.C7A] == (0, 0)


class TestPurposeCoverage:
    def test_every_non_other_purpose_has_at_least_one_match(self):
        # Purpose.OTHER is the catch-all referral branch — no visa is ever
        # surfaced for it (the match_tree returns referral_mode=True), so
        # it intentionally has no VISA_META entries.
        for p in Purpose:
            if p == Purpose.OTHER:
                continue
            candidates = [vt for vt, m in VISA_META.items() if p in m.purposes]
            assert candidates, f"no VisaType has purpose {p.value}"


def _find_dict(node: object, match) -> dict | None:
    """Structure-agnostic recursive search for the first dict satisfying `match`."""
    if isinstance(node, dict):
        if match(node):
            return node
        for value in node.values():
            found = _find_dict(value, match)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_dict(item, match)
            if found is not None:
                return found
    return None


def _highest_signed_prod_pack() -> Path:
    packs = list(PACKS_DIR.glob("rulepack-prod-*.signed.json"))
    assert packs, f"no rulepack-prod-*.signed.json found in {PACKS_DIR}"

    def _seq(path: Path) -> int:
        m = re.search(r"rulepack-prod-(\d+)\.signed\.json$", path.name)
        assert m, f"unexpected pack filename: {path.name}"
        return int(m.group(1))

    return max(packs, key=_seq)


class TestE33Notes:
    """E33 and E33G catalogue notes follow the signed rulepack and official pages."""

    def test_e33_notes_state_rangkap_kegiatan_and_not_non_working(self):
        notes = VISA_META[VisaType.E33].notes
        assert "non-working" not in notes.lower()
        assert "first stay permit of up to 5 years" in notes.lower()
        assert "rangkap kegiatan" in notes
        assert (
            "work or study only after rangkap kegiatan (dual-activity) reporting "
            "to the immigration office that issued the stay permit."
        ) in notes

    def test_e33g_notes_state_annual_income_from_signed_pack_and_not_savings(self):
        pack = json.loads(_highest_signed_prod_pack().read_text(encoding="utf-8"))
        rule = _find_dict(
            pack["payload"],
            lambda d: d.get("rule_id") == "el.e33g.remote-work"
            or d.get("id") == "el.e33g.remote-work",
        )
        assert rule is not None, "el.e33g.remote-work missing from signed pack payload"
        predicate = _find_dict(
            rule,
            lambda d: d.get("fact") == "work.annual_foreign_income_usd"
            and d.get("op") == "gte",
        )
        assert predicate is not None, (
            "work.annual_foreign_income_usd gte predicate missing in el.e33g.remote-work"
        )
        threshold = predicate["value"]
        assert isinstance(threshold, int) and threshold > 0

        notes = VISA_META[VisaType.E33G].notes
        assert "savings" not in notes.lower()
        assert "salary or income" in notes
        assert "employed by a company outside Indonesia" in notes
        assert f"USD {threshold:,}" in notes
        assert f"USD {threshold:,} a year" in notes

    def test_e33g_purposes_is_work_remote_only(self):
        assert VISA_META[VisaType.E33G].purposes == frozenset({Purpose.WORK_REMOTE})

    def test_e33_and_e33g_innocence_invariants_preserved(self):
        e33 = VISA_META[VisaType.E33]
        assert "USD 130,000" in e33.notes
        assert "no sponsor" in e33.notes
        assert e33.purposes == frozenset()

        e33g = VISA_META[VisaType.E33G]
        assert e33g.duration_days == 365
        assert e33g.extensions == (1, 365)
        assert e33g.min_budget_idr == 50_000_000
        assert Purpose.WORK_REMOTE in e33g.purposes
