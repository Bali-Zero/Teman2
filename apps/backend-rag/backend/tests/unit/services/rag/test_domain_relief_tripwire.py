"""B2.2 — tripwire for the domain-relief thresholds (RULING I40).

`DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT` (reasoning_utils.py) widens the LABEL
gate for two domains — tax 0.10, visa 0.12 — below the flat 0.15 every
other domain uses, because Indonesian-language tax/visa docs have lower
keyword overlap with IT/EN queries (see that module's own docstring). This
test does not touch those values; it measures whether the relief they grant
ever becomes the REASON a negative-stratum benchmark case (insufficient /
irrelevant context, per `manifest_mandatory.json` +
`manifest_supplement_b2.json`) clears the label gate.

Mechanism: `harness.decide()` — the same function the frozen benchmark
report calls — drives the REAL scorer (`calculate_evidence_score`) and the
REAL `AbstainPolicy` for every negative case, once with the live relief
thresholds and once with every domain flattened to 0.15. A case whose label
decision differs between the two runs is passing (or abstaining)
BECAUSE the relief exists — exactly what RULING I40 forbids.

NOT asserted here: that every negative case abstains under the relief, full
stop. Six Set-C/D "hard-case" pairs (contradiction-distractor cases in
`manifest_supplement_b2.json` — sup-c-725a39c8, sup-c-244d993f,
sup-d-1d738fd7 in the visa domain; sup-c-75d9a21c, sup-c-5fb1b72f in
pricing; sup-c-d4fff2f6 in default) already PASS the label gate today, at
scores 0.8 / 0.8 / 0.3 / 0.8 / 0.8 / 0.3, IDENTICALLY under the relief and
under a flat 0.15 — three of the six aren't even in a relieved domain, so a
flat threshold cannot be what lets them through. Their own
`provenance_fixture.note` says their target signal is "the FUTURE support
judge... not today's provenance-band scorer", and `harness.report()`
already tracks this class of miss as a `false_acceptance` count rather than
gating it to zero — measured and accepted, not hidden. That gap is real but
it is NOT relief-driven and closing it is out of scope for a relief
tripwire;
`TestDomainReliefNeverFlipsANegativeCaseToPass.test_the_six_known_hard_case_false_acceptances_are_relief_independent`
names them explicitly so a future reader is not left to rediscover this.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from backend.services.rag.agentic import reasoning_utils
from backend.tests.benchmarks.evidence_sufficiency import harness

_BENCH_DIR = Path(harness.__file__).resolve().parent
_MANDATORY_PATH = _BENCH_DIR / "manifest_mandatory.json"
_SUPPLEMENT_PATH = _BENCH_DIR / "manifest_supplement_b2.json"
_SUPPORT_RECORD_PATH = _BENCH_DIR / "support_verdicts_b2.json"

_NEGATIVE_STRATA = (
    "relevant_insufficient",
    "irrelevant",
    "generic_overlap",
    "company_prefix_chunk",
)

#: The relief thresholds under scrutiny (RULING I40): tax 0.10, visa 0.12,
#: pricing/kbli/default unchanged. This module never edits these — only
#: measures against them.
RELIEF_THRESHOLDS: dict[str, float] = dict(reasoning_utils.DOMAIN_ABSTAIN_THRESHOLDS_DEFAULT)
#: The counterfactual the relief is measured against: every domain flattened
#: to the 0.15 the relief widens away from. Any negative case whose label
#: decision differs between RELIEF_THRESHOLDS and this dict is passing (or
#: abstaining) BECAUSE the relief exists.
#: CORRECTED after the council round (codex-gpt-5.6-sol, P2): flattening EVERY
#: domain to 0.15 also LOWERS kbli from 0.20, so a negative kbli case scoring
#: between 0.15 and 0.20 would flip under the counterfactual and be reported as
#: relief-caused — a false positive about a domain that has no relief. The
#: counterfactual must move ONLY the domains whose threshold is BELOW the
#: default 0.15, i.e. the reliefs themselves.
# Refuted in council round 1 (kimi-code/k3, R6): a literal 0.15 here would
# silently stop meaning "no relief" the day the engine's own `default` moves.
# Read it from the engine dict, like the reliefs themselves.
_DEFAULT_THRESHOLD = RELIEF_THRESHOLDS["default"]
UNIFORM_THRESHOLDS: dict[str, float] = {
    domain: (_DEFAULT_THRESHOLD if value < _DEFAULT_THRESHOLD else value)
    for domain, value in RELIEF_THRESHOLDS.items()
}

_KNOWN_RELIEF_INDEPENDENT_HARD_CASES = frozenset(
    {
        "sup-c-725a39c8",  # visa
        "sup-c-244d993f",  # visa
        "sup-d-1d738fd7",  # visa
        "sup-c-75d9a21c",  # pricing — relief does not even touch this domain
        "sup-c-5fb1b72f",  # pricing — relief does not even touch this domain
        "sup-c-d4fff2f6",  # default — relief does not even touch this domain
    },
)


@contextlib.contextmanager
def _domain_thresholds(overrides: dict[str, float]):
    """Swap the module-global dict `reasoning_utils.get_abstain_threshold()`
    reads, for the duration of the block, then restore it.

    Deliberately a bare context manager rather than the pytest `monkeypatch`
    fixture: the same helper is used both by the tests below AND by the
    standalone falsification probe run once (by hand, outside pytest) to
    prove this mechanism is sensitive — see the PR report.
    """
    original = reasoning_utils._DOMAIN_THRESHOLDS
    reasoning_utils._DOMAIN_THRESHOLDS = dict(overrides)
    try:
        yield
    finally:
        reasoning_utils._DOMAIN_THRESHOLDS = original


def _negative_cases() -> list[dict]:
    mandatory = harness.load(_MANDATORY_PATH)
    supplement = harness.load(_SUPPLEMENT_PATH)
    return [
        c for c in mandatory["cases"] + supplement["cases"] if c["stratum"] in _NEGATIVE_STRATA
    ]


@pytest.fixture(scope="module")
def negative_cases() -> list[dict]:
    cases = _negative_cases()
    assert cases, "no negative-stratum cases in either manifest — tripwire would be vacuous"
    for case in cases:
        # sanity: validate() already enforces this manifest-wide, but a
        # tripwire that silently included a mislabeled case would be worse
        # than one that fails loudly here instead.
        assert case["expected_label_gate"] == "abstain", case["case_id"]
    return cases


@pytest.fixture(scope="module")
def support_record() -> dict[str, str]:
    return harness.load_support_record(_SUPPORT_RECORD_PATH)


def _label_under(
    cases: list[dict],
    support_record: dict[str, str],
    thresholds: dict[str, float],
) -> dict[str, str]:
    with _domain_thresholds(thresholds):
        return {c["case_id"]: harness.decide(c, support_record)["label"] for c in cases}


def _relief_caused_flips(
    cases: list[dict],
    support_record: dict[str, str],
    relief: dict[str, float],
) -> dict[str, tuple[str, str]]:
    """`{case_id: (relief_label, uniform_label)}` for every case whose label
    decision under `relief` differs from its decision under
    `UNIFORM_THRESHOLDS`. Non-empty means at least one case's outcome
    depends on `relief` existing at all."""
    relief_labels = _label_under(cases, support_record, relief)
    uniform_labels = _label_under(cases, support_record, UNIFORM_THRESHOLDS)
    return {
        cid: (relief_labels[cid], uniform_labels[cid])
        for cid in relief_labels
        if relief_labels[cid] != uniform_labels[cid]
    }


class TestDomainReliefNeverFlipsANegativeCaseToPass:
    def test_is_non_vacuous_some_negative_case_is_in_a_relieved_domain(
        self,
        negative_cases: list[dict],
    ) -> None:
        domains = {reasoning_utils.classify_query_domain(c["query"]) for c in negative_cases}
        assert domains & {"tax", "visa"}, (
            "no negative case classifies into tax or visa — the only domains "
            "the relief loosens below 0.15 — so this tripwire would never fire: "
            f"observed domains {domains}"
        )

    def test_no_negative_case_label_decision_depends_on_the_relief(
        self,
        negative_cases: list[dict],
        support_record: dict[str, str],
    ) -> None:
        flips = _relief_caused_flips(negative_cases, support_record, RELIEF_THRESHOLDS)
        assert flips == {}, flips

    def test_the_six_known_hard_case_false_acceptances_are_relief_independent(
        self,
        negative_cases: list[dict],
        support_record: dict[str, str],
    ) -> None:
        """Names the module docstring's exception explicitly: these cases DO
        pass the label gate, but identically so with or without the relief
        — and every OTHER negative case abstains under the relief."""
        relief_labels = _label_under(negative_cases, support_record, RELIEF_THRESHOLDS)
        uniform_labels = _label_under(negative_cases, support_record, UNIFORM_THRESHOLDS)

        present = _KNOWN_RELIEF_INDEPENDENT_HARD_CASES & set(relief_labels)
        assert present == _KNOWN_RELIEF_INDEPENDENT_HARD_CASES, (
            "expected hard-case ids missing from the corpora — manifest changed? "
            f"missing={_KNOWN_RELIEF_INDEPENDENT_HARD_CASES - present}"
        )
        for cid in _KNOWN_RELIEF_INDEPENDENT_HARD_CASES:
            assert relief_labels[cid] == "pass", (cid, relief_labels[cid])
            assert uniform_labels[cid] == "pass", (cid, uniform_labels[cid])

        other_ids = set(relief_labels) - _KNOWN_RELIEF_INDEPENDENT_HARD_CASES
        offenders = {cid: relief_labels[cid] for cid in other_ids if relief_labels[cid] == "pass"}
        assert offenders == {}, offenders


class TestTheTripwireIsFalsifiable:
    """Proves `_relief_caused_flips` is not vacuously green: an extreme
    relief (every domain at 0.0, so nothing can ever score below threshold)
    DOES produce a non-empty flip set against the same `UNIFORM_THRESHOLDS`
    counterfactual the real tests above use — i.e. the detection mechanism
    the tests above rely on is provably sensitive to a relief that is too
    generous, not just to the specific values in force today."""

    def test_an_extreme_relief_is_caught_as_a_flip(
        self,
        negative_cases: list[dict],
        support_record: dict[str, str],
    ) -> None:
        extreme = dict.fromkeys(RELIEF_THRESHOLDS, 0.0)
        flips = _relief_caused_flips(negative_cases, support_record, extreme)
        assert flips, (
            "an extreme relief (0.0 for every domain) produced NO flips — "
            "the flip-detection mechanism above is not actually sensitive"
        )
