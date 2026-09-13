"""B2.1 lane B — the manifest_supplement_b2.json contract, plus the two B1 debts
(D-C4, D-B15) B1 handed to B2.1 (build spec sec. 7).

Nothing here touches `manifest_mandatory.json` (frozen at B1.3) or the scorer.
This module:

1. Proves `manifest_supplement_b2.json` (Set B — the 4 ruling-I26 mandatory
   distractor pairs — and Set C — the 12 D-SETC hard-case pairs) is
   well-formed under the harness's own `validate()`, that every pair carries
   exactly one `sufficient` + one `relevant_insufficient` member with
   IDENTICAL provenance, and that the two sets are never confused (each case
   carries its own `set` field).
2. D-C4 (#6274 C4): an INDEPENDENT reimplementation of the frozen mandatory
   manifest's own pinned `generic_word_definition` (using its own
   `generic_word_stopwords` / `generic_word_identifiers` lists, read from the
   manifest — never hand-copied), checked case by case against every
   recorded `generic_overlap` label. A disagreement is reported as a FAILURE
   naming the case_id; this test NEVER relabels the manifest to make itself
   pass.
3. D-B15 (B1.5 follow-up): binds the sha256 of the artifact FILE
   `query_vectors_b1_5.json` to the field in `b1-5-precall.json` that IS the
   file's hash — `completion.artifact_sha256` — never `list_sha256`, which
   (verified separately, see the test's own docstring below) hashes only the
   compact-JSON `query_list` field, not the file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from backend.tests.benchmarks.evidence_sufficiency import harness

_BENCH_DIR = Path(harness.__file__).resolve().parent
_MANDATORY_PATH = _BENCH_DIR / "manifest_mandatory.json"
_SUPPLEMENT_PATH = _BENCH_DIR / "manifest_supplement_b2.json"
_QUERY_VECTORS_PATH = _BENCH_DIR / "query_vectors_b1_5.json"


def _find_repo_root(start: Path) -> Path:
    """Walk up from `start` to the checkout root (the dir carrying both
    `.git` and `evidence/`) — robust to this test file's exact nesting depth,
    unlike a hardcoded `parents[N]`."""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() and (candidate / "evidence").is_dir():
            return candidate
    raise RuntimeError(f"repo root not found walking up from {start}")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_B15_PRECALL_PATH = (
    _REPO_ROOT
    / "evidence/2026-09/agent-nuzantara-backend-rag-b1-5-query-vectors-7057dd74"
    / "b1-5-precall.json"
)

_EXPECTED_ARTIFACT_SHA256 = (
    "0021c3275b7bd9f812f0ce52fc06da1330e89a9d1c40a4c105ca932720083012"
)

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]+")


def _generic_word_overlap(
    query: str,
    context: list[str],
    stopwords: set[str],
    identifiers: set[str],
) -> bool:
    """Literal reimplementation of the mandatory manifest's own
    `generic_word_definition` string: "a generic word is a case-insensitive
    literal token matched by [A-Za-zÀ-ÿ]+ with at least 3 letters that occurs
    in both the query and the context, is not in generic_word_stopwords and
    is not in generic_word_identifiers"."""

    def tokens(text: str) -> set[str]:
        return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= 3}

    query_words = tokens(query) - stopwords - identifiers
    context_words = tokens(" ".join(context)) - stopwords - identifiers
    return bool(query_words & context_words)


@pytest.fixture(scope="module")
def mandatory() -> dict[str, Any]:
    return harness.load(_MANDATORY_PATH)


@pytest.fixture(scope="module")
def supplement() -> dict[str, Any]:
    return harness.load(_SUPPLEMENT_PATH)


# ---------------------------------------------------------------------------
# Supplement well-formedness
# ---------------------------------------------------------------------------


def test_manifest_mandatory_is_untouched_by_this_lane() -> None:
    """This lane's whole point is the SUPPLEMENT; the frozen mandatory
    manifest must stay byte-identical. Reuses the sha256 already pinned by
    `test_evidence_sufficiency_benchmark.py` so a drift is caught here too."""
    import hashlib

    from backend.tests.unit.services.rag.test_evidence_sufficiency_benchmark import (
        MANDATORY_MANIFEST_SHA256,
    )

    digest = hashlib.sha256(_MANDATORY_PATH.read_bytes()).hexdigest()
    assert digest == MANDATORY_MANIFEST_SHA256


def test_supplement_validates_clean_under_the_harness(supplement: dict) -> None:
    errors = harness.validate(supplement)
    assert errors == [], errors


def test_supplement_has_the_expected_set_b_and_set_c_case_counts(supplement: dict) -> None:
    by_set: dict[str, int] = {}
    for case in supplement["cases"]:
        assert "set" in case, f"{case.get('case_id')}: missing 'set' field"
        by_set[case["set"]] = by_set.get(case["set"], 0) + 1

    # Set B: 4 ruling-I26 mandatory distractor pairs = 8 cases.
    assert by_set.get("B") == 8, by_set
    # Set C: 12 D-SETC hard-case pairs = 24 cases.
    assert by_set.get("C") == 24, by_set
    # Set D: the CROSS-LANGUAGE cell of 6 of those same hard pairs — English
    # query against the unchanged Indonesian context and label = 12 cases.
    # It exists because Set C is monolingual (12 EN>EN + 12 ID>ID), so it
    # never measured the one cell where a support-driven relevance RAISE
    # would fire, and that cell is where the refusal in pack.yml is decided.
    assert by_set.get("D") == 12, by_set
    assert sum(by_set.values()) == 44, by_set


def test_supplement_case_ids_are_never_confused_with_the_mandatory_manifest(
    mandatory: dict, supplement: dict
) -> None:
    mandatory_ids = {c["case_id"] for c in mandatory["cases"]}
    supplement_ids = {c["case_id"] for c in supplement["cases"]}
    assert mandatory_ids.isdisjoint(supplement_ids)
    assert len(supplement_ids) == len(supplement["cases"]), "duplicate case_id in supplement"


class TestEveryPairHasExactlyOneSufficientAndOneRelevantInsufficientMember:
    """Build-spec acceptance: 'every pair has exactly one sufficient and one
    relevant_insufficient member with identical provenance.'"""

    @staticmethod
    def _pairs(supplement: dict) -> dict[str, list[dict]]:
        pairs: dict[str, list[dict]] = {}
        for case in supplement["cases"]:
            pairs.setdefault(case["pair_id"], []).append(case)
        return pairs

    def test_pair_count_matches_set_b_plus_set_c_plus_set_d(self, supplement: dict) -> None:
        pairs = self._pairs(supplement)
        # 4 (Set B) + 12 (Set C) + 6 (Set D, the cross-language members of
        # six Set C pairs, carrying their own `-x` pair ids) = 22 pairs.
        assert len(pairs) == 22, sorted(pairs)

    def test_each_pair_has_exactly_two_members(self, supplement: dict) -> None:
        pairs = self._pairs(supplement)
        for pair_id, members in pairs.items():
            assert len(members) == 2, (pair_id, len(members))

    def test_each_pair_has_one_sufficient_and_one_relevant_insufficient(
        self, supplement: dict
    ) -> None:
        pairs = self._pairs(supplement)
        for pair_id, members in pairs.items():
            strata = sorted(m["stratum"] for m in members)
            assert strata == ["relevant_insufficient", "sufficient"], (pair_id, strata)

    def test_each_pair_has_identical_provenance_between_members(
        self, supplement: dict
    ) -> None:
        pairs = self._pairs(supplement)
        for pair_id, (a, b) in pairs.items():
            assert json.dumps(a["provenance_fixture"], sort_keys=True) == json.dumps(
                b["provenance_fixture"], sort_keys=True
            ), f"pair {pair_id}: provenance differs between members"

    def test_each_pair_never_mixes_two_sets(self, supplement: dict) -> None:
        pairs = self._pairs(supplement)
        for pair_id, members in pairs.items():
            sets = {m["set"] for m in members}
            assert len(sets) == 1, (pair_id, sets)


# ---------------------------------------------------------------------------
# D-C4 (#6274 C4) — generic_word_definition self-consistency, MANDATORY manifest only
# ---------------------------------------------------------------------------


def test_d_c4_generic_overlap_labels_agree_with_the_pinned_definition(
    mandatory: dict,
) -> None:
    """D-C4 (#6274 C4): the manifest's PINNED `generic_word_definition`,
    together with its own `generic_word_stopwords` and
    `generic_word_identifiers`, must agree with EVERY recorded
    `generic_overlap` label in the mandatory manifest.

    This test computes the rule independently (never imports the scorer) and
    compares it case by case. A disagreement here is a real finding to
    report to the Dux — this test must NEVER be made to pass by changing a
    manifest label.
    """
    stopwords = {w.lower() for w in mandatory["generic_word_stopwords"]}
    identifiers = {w.lower() for w in mandatory["generic_word_identifiers"]}

    disagreements: list[str] = []
    for case in mandatory["cases"]:
        computed = _generic_word_overlap(case["query"], case["context"], stopwords, identifiers)
        recorded = case["generic_overlap"]
        if computed != recorded:
            disagreements.append(
                f"{case['case_id']}: generic_word_definition computes "
                f"generic_overlap={computed} but the manifest records {recorded!r}"
            )

    assert disagreements == [], "\n".join(disagreements)


@pytest.mark.parametrize(
    "case",
    harness.load(_MANDATORY_PATH)["cases"],
    ids=[c["case_id"] for c in harness.load(_MANDATORY_PATH)["cases"]],
)
def test_d_c4_generic_overlap_per_case(case: dict, mandatory: dict) -> None:
    """Same rule as the aggregate test above, parametrized per case_id so a
    single disagreement fails on its own named test node rather than being
    buried inside one aggregate assertion."""
    stopwords = {w.lower() for w in mandatory["generic_word_stopwords"]}
    identifiers = {w.lower() for w in mandatory["generic_word_identifiers"]}
    computed = _generic_word_overlap(case["query"], case["context"], stopwords, identifiers)
    assert computed == case["generic_overlap"], (
        f"{case['case_id']}: generic_word_definition computes generic_overlap="
        f"{computed} but the manifest records {case['generic_overlap']!r}"
    )


# ---------------------------------------------------------------------------
# D-B15 — bind the artifact file's sha256 to the precall receipt
# ---------------------------------------------------------------------------


def test_d_b15_query_vectors_artifact_sha256_matches_the_precall_receipt() -> None:
    """D-B15 (B1.5 follow-up): binds the sha256 of the artifact FILE
    `query_vectors_b1_5.json` to the value recorded in `b1-5-precall.json`.

    The precall JSON carries TWO sha256-shaped fields:
      - `completion.artifact_sha256` — VERIFIED (this test IS that
        verification) to be `sha256(query_vectors_b1_5.json's raw bytes)`.
        This is the field this test binds to.
      - `list_sha256` — a DIFFERENT value. Measured separately (not by this
        test): it is `sha256(json.dumps(query_list, separators=(',', ':')))`
        — the compact JSON encoding of just the `query_list` field inside
        the artifact, not the artifact file itself. Binding to this field
        would be wrong; it is named here so a future reader does not repeat
        the confusion.

    Today this equality is checked only by hand (build spec sec. 7, D-B15);
    this test makes it a standing tripwire.
    """
    import hashlib

    assert _QUERY_VECTORS_PATH.exists(), f"artifact file missing: {_QUERY_VECTORS_PATH}"
    assert _B15_PRECALL_PATH.exists(), f"precall receipt missing: {_B15_PRECALL_PATH}"

    actual_sha256 = hashlib.sha256(_QUERY_VECTORS_PATH.read_bytes()).hexdigest()
    precall = json.loads(_B15_PRECALL_PATH.read_text(encoding="utf-8"))
    recorded_sha256 = precall["completion"]["artifact_sha256"]

    assert actual_sha256 == _EXPECTED_ARTIFACT_SHA256, (
        f"artifact file's sha256 changed on disk: {actual_sha256}"
    )
    assert recorded_sha256 == _EXPECTED_ARTIFACT_SHA256, (
        f"b1-5-precall.json's completion.artifact_sha256 changed: {recorded_sha256}"
    )
    assert actual_sha256 == recorded_sha256


def test_d_b15_list_sha256_is_a_different_field_and_is_not_the_file_hash() -> None:
    """Guards the D-B15 docstring's claim: `list_sha256` is NOT the file's
    sha256 (it hashes only the compact-JSON `query_list`), so a future editor
    is not tempted to bind to it instead of `completion.artifact_sha256`."""
    import hashlib

    precall = json.loads(_B15_PRECALL_PATH.read_text(encoding="utf-8"))
    artifact = json.loads(_QUERY_VECTORS_PATH.read_text(encoding="utf-8"))

    list_sha256_recorded = precall["list_sha256"]
    file_sha256 = hashlib.sha256(_QUERY_VECTORS_PATH.read_bytes()).hexdigest()
    assert list_sha256_recorded != file_sha256

    compact_query_list_sha256 = hashlib.sha256(
        json.dumps(artifact["query_list"], separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert list_sha256_recorded == compact_query_list_sha256


# ---------------------------------------------------------------------------
# Set D — the measured reason the support signal may ZERO relevance and never
# RAISE it.
#
# The refuter seat (kimi-code/k3, round 1) destroyed the FIRST version of that
# refusal: it read "letting SUPPORTED raise a band would turn the judge's 5
# Set C errors into 5 releases" and answered, correctly, that those 5 cases
# already release today — their lexical overlap is high, so nothing was
# blocking them and the raise has ZERO marginal effect there. The argument was
# arithmetic about the wrong cell.
#
# Set D is the cell the argument actually needed and Set C never had: the same
# hard pairs (entity present, referent WRONG, no meta-commentary) with an
# ENGLISH query against the unchanged Indonesian context, where the lexical
# ratio reads 0 and a raise WOULD be the only thing deciding the case.
# Measured there, the trade is one-for-one and against us — which is what
# these two tests freeze, so nobody re-opens the question from prose.
# ---------------------------------------------------------------------------

_SUPPORT_RECORD_PATH = _BENCH_DIR / "support_verdicts_b2.json"

#: Set D member whose label is `relevant_insufficient` and whose recorded
#: verdict is a WRONG `SUPPORTED` — the judge's own error, measured, not
#: hypothesised.
_SET_D_JUDGE_ERROR_CASE = "sup-d-dd0c1a97"


def _case(supplement: dict, case_id: str) -> dict:
    for case in supplement["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"{case_id} absent from the supplement")


def test_set_d_holds_a_wrongly_supported_insufficient_case(supplement: dict) -> None:
    """The premise. Without a recorded judge error in this cell there is
    nothing to protect against and the refusal would be a preference."""
    record = harness.load_support_record(_SUPPORT_RECORD_PATH)
    case = _case(supplement, _SET_D_JUDGE_ERROR_CASE)
    assert case["stratum"] == "relevant_insufficient"
    assert case["query_lang"] == "EN"
    assert case["context_lang"] == "ID"
    key = harness.support_record_key(case["query"], case["context"])
    assert record[key] == "SUPPORTED", "the recorded judge error is the premise of this test"


def test_only_the_zero_lexical_band_blocks_the_wrongly_supported_case(
    supplement: dict,
) -> None:
    """What actually holds the line today, and why support must never raise.

    The case abstains ONLY because its relevance band is zero: an English
    question against Indonesian text shares no token, and its fixture
    declares `score_kind: unknown`, so the provenance-primary path never
    applies. The support verdict is no help here — it is WRONG. Raise the
    band on a SUPPORTED verdict and this exact case releases unsupported
    fee/duration advice; that is the measured cost of curing the one
    residual false abstention (`bs-17806bb4`) the same way, and it is why
    `pack.yml` records the cure as REFUSED rather than as open work.
    """
    record = harness.load_support_record(_SUPPORT_RECORD_PATH)
    case = _case(supplement, _SET_D_JUDGE_ERROR_CASE)

    decision = harness.decide(case, record)
    assert decision["generation"] == "abstain", decision
    assert decision["label"] == "abstain", decision
    assert decision["score"] < 0.15, decision

    # And the counterfactual, computed rather than asserted: one band step is
    # all it takes to lose it. 0.2 is `_BAND_WEAK`'s value in
    # reasoning_utils.py; the scorer's own combination is not re-implemented
    # here — the point is only that the margin is a single step wide.
    assert decision["score"] <= 0.2, (
        "if this ever exceeds one band step the counterfactual in this test's "
        "docstring stops being the right argument and must be re-measured"
    )
