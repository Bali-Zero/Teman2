"""Gates for seq-21 (``rulepack-prod-021.source.json``): the qualification fold.

Ground: ``fold_pack_seq21.py``'s docstring (what each edit is and why), the
coverage report of 2026-09-13 §A3/§B2/§C2, and the owner ruling of the same
day — «portare 38 prodotti su 38 raggiungibili dal percorso senza rimandare a
revisione umana ma spiegati deterministicamente».

seq-21 is NOT SIGNED and NOT ACTIVATED by anything in this module or in
``fold_pack_seq21.py`` — signing is the owner's offline ceremony
(``sign_pack.py``, an operator-supplied Ed25519 key). Every witness here that
needs a compiled pack therefore builds one with
``compile_pack.wrap_as_unsigned_pack`` (a placeholder envelope, never a trust
claim), exactly as ``test_seq20_pack.py`` does and for the same disk reason:
``gold_coverage_eval`` and ``gold_replay_driver`` are hardcoded to the real
production public key and would refuse an unsigned ``environment: PRODUCTION``
payload unconditionally.

Every behavioural witness is stated TWICE — guilt (the defect is gone) and
innocence (the legitimate outcome the same rule still produces). The guilt
witness that matters most here is :class:`TestSponsorTypeAloneIsNotEvidence`:
it strips the qualifying-fact conjunct back out of the nine SUPPORT rules and
proves the pack then hands out products on no evidence, which is exactly the
shape PR #6362 shipped and the signature dossier of 2026-09-13 §4 refused.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import (
    compile_rule_pack,
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.fold_pack_seq21 import (
    E33_GUARANTEE_REASON,
    E33_GUARANTEE_RULE_ID,
    EMPLOYMENT_SPONSOR_PRODUCT_CODES,
    EMPLOYMENT_SPONSOR_REASON,
    EMPLOYMENT_SPONSOR_RULE_ID,
    NEW_RULE_IDS,
    NEW_RULE_VALID_FROM,
    RETIRED_REVIEW_RULES,
    SEQ20_PAYLOAD_SHA256,
    SUPPORT_RULES,
    TARGET_PRODUCT_CODES,
    _assert_retired_review_rules_are_dormant,
    _assert_sponsor_premises_follow_the_catalogue,
    _rule_pack_id,
    fold,
    main,
)
from backend.scripts.visa_engine.gold_replay_driver import (
    _offline_identity_provider,
    build_persona_request,
)
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.models import DecisionState, RulePackPayload
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ20_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-020.source.json"
_SEQ20_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-020.signed.json"
_SEQ21_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-021.source.json"
_CORPUS_DIR = Path(__file__).resolve().parent / "gold_coverage" / "fixtures" / "walks"

pytestmark = pytest.mark.skipif(
    not _SEQ21_SOURCE_PATH.exists(),
    reason="rulepack-prod-021.source.json does not exist on disk — run "
    "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq21`",
)

PROD_TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)

#: After seq-20's ``signed_at`` (2026-09-06T14:59:27Z), before this fold's own
#: ``created_at`` — never real wall clock.
OBSERVED_AT = datetime(2026, 9, 13, 0, 30, 0, tzinfo=timezone.utc)

#: Pinned instant for every evaluator call, and the discipline the first
#: seq-21 census got WRONG: at/after the ``valid_period.from`` of every rule
#: this fold inserts (2026-09-13T00:00:00Z, the fold's ``created_at``, owner
#: order 2026-09-14 «da subito») and inside the pack's shortest freshness
#: window (the 32-day policy on sources verified 2026-08-30T13:18:00Z expires
#: 2026-10-01T13:18:00Z). 05:30 WITA on 2026-09-14, the day the owner signs:
#: the nine products must be SUPPORTED today, not tomorrow. Evaluating a
#: candidate at the INCUMBENT's ``signed_at`` reports "nothing moved" for
#: rules that are not yet in force.
AS_OF = datetime(2026, 9, 13, 21, 30, 0, tzinfo=timezone.utc)

#: The digest of the seq-21 payload this module gates. Measured BEFORE the
#: prettier pass and re-measured after it, unchanged — the pack's identity is
#: JCS over the PARSED document, never the file bytes. This is the digest the
#: owner signs.
SEQ21_PAYLOAD_SHA256 = "fda8c3121bdddb6a8e023cf246c241a34f754acaef44919bb8968b50ee8c98c7"

#: The ten wire facts registered with this fold — the qualification half of
#: the vocabulary. Declared here so the tests can assert against the SET
#: rather than against ten literals.
QUALIFICATION_FACTS: frozenset[str] = frozenset(
    {
        "sponsor.government_invitation",
        "sponsor.government_collaboration",
        "sponsor.world_figure_invitation",
        "sponsor.diplomatic_household",
        "sponsor.trade_office",
        "investment.establishes_indonesian_company",
        "investment.capital_market_only",
        "investment.foreign_branch_or_subsidiary",
        "investment.ikn_subsidiary",
        "investment.meets_published_threshold",
    }
)

#: The three ``§B2`` walks that answered with the generic catalogue sentence
#: on seq-20, and the named cause each one must answer with on seq-21. A
#: fourth row (E23V-DEFECT, mission seq-22) joined later: the same
#: already-existing ``hf.employment-without-indonesian-sponsor`` hard filter
#: this fold added also fires on the new
#: ``offshore/work/sponsor_government/trade_office_only/employer_no`` walk —
#: measured identically to ``offshore/other/paid/employer_no`` above (GENERIC
#: on seq-20, ``PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR`` on seq-21).
NAMED_CAUSE_WALKS: dict[str, str] = {
    "offshore/invest/bank_deposit/below_threshold": E33_GUARANTEE_REASON,
    "offshore/invest/property/below_threshold": E33_GUARANTEE_REASON,
    "offshore/other/paid/employer_no": EMPLOYMENT_SPONSOR_REASON,
    "offshore/work/sponsor_government/trade_office_only/employer_no": EMPLOYMENT_SPONSOR_REASON,
}

_GENERIC_CAUSE = "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"

#: W-VO-Q (mission SAETTA-VO3): what seq-21 ADDS to seq-20's candidates on each
#: walk once the interview asks the ten qualification facts, measured
#: 2026-09-14 over the 107-walk corpus at ``AS_OF``. 26 walks gain; none loses.
#: The defaults answer "yes", so the `work`/`invest`/paid-`other` default walks
#: gain several products at once; the one-product walks are W-VO-Q's own.
EXPECTED_SEQ21_GAINS: dict[str, tuple[str, ...]] = {
    # W-VO-Q item 7: the business explorer's default walk (INVESTMENT purpose,
    # conversion "yes", so the investor route questions are asked).
    "offshore/business/exploring": ("E28B", "E28D", "E28F"),
    "offshore/invest/capital_market": ("E28B", "E28D", "E28F"),
    "offshore/invest/capital_market/capital_market_only": ("E28C",),
    "offshore/invest/family": ("E28B", "E28D", "E28F"),
    "offshore/invest/merit": ("E28B", "E28D", "E28F"),
    "offshore/invest/merit/currency_usd": ("E28B", "E28D", "E28F"),
    "offshore/invest/pt_pma": ("E28B", "E28D", "E28F"),
    "offshore/invest/pt_pma/company_only": ("E28B",),
    "offshore/invest/pt_pma/foreign_branch_only": ("E28D",),
    "offshore/invest/pt_pma/full_capital": ("E28B", "E28D", "E28F"),
    "offshore/invest/pt_pma/ikn_subsidiary": ("E28B", "E28F"),
    "offshore/invest/pt_pma/offshore_application": ("E28B", "E28D", "E28F"),
    "offshore/invest/pt_pma/sponsor_government": ("E28B", "E28D", "E28F", "E33C"),
    "offshore/invest/pt_pma/sponsor_government/not_world_figure": ("E28B", "E28D", "E28F"),
    "offshore/invest/undecided": ("E28B", "E28D", "E28F"),
    "offshore/invest/undecided/currency_still_unsure": ("E28B", "E28D", "E28F"),
    "offshore/other": ("E33B",),
    "offshore/other/paid/sponsor_government": ("E23V", "E33A"),
    # The one state that moves: NEEDS_INPUT on `work.indonesian_work_sponsor_
    # confirmed` ("unsure") on seq-20, SUPPORTED [E33B] on seq-21 — the
    # default NONE sponsor answers the collaboration question "yes".
    "offshore/other/paid/sponsor_unsure": ("E33B",),
    "offshore/work": ("E33B",),
    "offshore/work/sponsor_government": ("E23V", "E33A"),
    "offshore/work/sponsor_government/invitation_only": ("E33A",),
    "offshore/work/sponsor_government/trade_office_only": ("E23V",),
    "offshore/work/sponsor_individual": ("E23U",),
    "onshore/invest": ("E28B", "E28D", "E28F"),
    "onshore/other": ("E33B",),
    "onshore/work": ("E33B",),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _nodes(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            out.extend(_nodes(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_nodes(value))
    return out


def _rules_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in payload["rules"]}


@pytest.fixture(scope="module")
def seq20_source() -> dict[str, Any]:
    return _read_json(_SEQ20_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq20_signed() -> dict[str, Any]:
    return _read_json(_SEQ20_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq21_source() -> dict[str, Any]:
    return _read_json(_SEQ21_SOURCE_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


def _compiled(payload_dict: dict[str, Any]) -> compiler.CompiledRulePack:
    payload = RulePackPayload.model_validate(payload_dict)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq20_compiled() -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_SEQ20_SOURCE_PATH)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq21_compiled() -> compiler.CompiledRulePack:
    """A CompiledRulePack built from 021 through a PLACEHOLDER envelope — never
    a trust claim (see ``wrap_as_unsigned_pack``'s own docstring). 021 is
    unsigned by design; this is the only way any witness here can exercise the
    real evaluator against it before the owner signs it."""
    payload = load_rule_pack_payload(_SEQ21_SOURCE_PATH)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def walks() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_CORPUS_DIR.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        out[str(spec["label"])] = spec
    assert len(out) >= 84, f"the walk corpus shrank to {len(out)} — a census over it proves nothing"
    return out


def _decide(
    pack: compiler.CompiledRulePack, overrides: dict[str, Any], label: str
) -> dict[str, Any]:
    """The applicant-facing outcome: the same verify-free compile → evaluate →
    ``apply_public_policy_adapters`` path ``gold_coverage_eval._evaluate``
    walks, with the pack handed in rather than selected from disk (the
    candidate is unsigned, so the selector cannot see it)."""
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        pack,
        effective_at=AS_OF,
        observed_at=AS_OF,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(
        decision,
        facts,
        pack,
        disclosed_review_flags=request.effective_review_flags(),
    )
    return _decision_actual(decision)


def _replay(
    pack: compiler.CompiledRulePack, walks: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    return {label: _decide(pack, spec["overrides"], label) for label, spec in sorted(walks.items())}


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


_UNKNOWN: dict[str, Any] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}

#: Every ``work.*`` answer withdrawn, so a gold fixture proves ITS product's
#: qualification and never rides on the base walk's employment facts.
_NO_WORK_FACTS: dict[str, Any] = {
    "work.employer_country_code": _UNKNOWN,
    "work.employer_is_indonesian_entity": _UNKNOWN,
    "work.indonesia_source_compensation": _UNKNOWN,
    "work.indonesian_work_sponsor_confirmed": _UNKNOWN,
    "work.serves_indonesian_clients": _UNKNOWN,
}


def _gold_overrides() -> dict[str, dict[str, Any]]:
    """One fixture per target product: the declared purpose, the sponsor or
    route premise, and the ONE qualifying fact this fold registered for it."""
    employment = {"intent.purposes": _known(["EMPLOYMENT"])}
    investment = {"intent.purposes": _known(["INVESTMENT"])}
    return {
        "E23U": {
            **employment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("INDIVIDUAL"),
            "sponsor.diplomatic_household": _known(True),
        },
        "E23V": {
            **employment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("GOVERNMENT"),
            "sponsor.trade_office": _known(True),
        },
        "E33A": {
            **employment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("GOVERNMENT"),
            "sponsor.government_invitation": _known(True),
        },
        "E33B": {
            **employment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("NONE"),
            "sponsor.government_collaboration": _known(True),
        },
        "E33C": {
            **investment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("GOVERNMENT"),
            "sponsor.world_figure_invitation": _known(True),
        },
        "E28B": {
            **investment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("INVESTMENT"),
            "investment.establishes_indonesian_company": _known(True),
            "investment.meets_published_threshold": _known(True),
        },
        "E28C": {
            **investment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("NONE"),
            "investment.capital_market_only": _known(True),
            "investment.meets_published_threshold": _known(True),
        },
        "E28D": {
            **investment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("INVESTMENT"),
            "investment.foreign_branch_or_subsidiary": _known(True),
            "investment.meets_published_threshold": _known(True),
        },
        "E28F": {
            **investment,
            **_NO_WORK_FACTS,
            "sponsor.type": _known("INVESTMENT"),
            "investment.ikn_subsidiary": _known(True),
            "investment.meets_published_threshold": _known(True),
        },
    }


def _as_before_the_questions(overrides: dict[str, Any]) -> dict[str, Any]:
    """A walk's wire facts with the ten qualification facts back at
    UNKNOWN(NOT_ASKED) — what the interview sent before W-VO-Q asked them.

    Since W-VO-Q the corpus ANSWERS the ten questions (their first option is
    "yes"), so the walks on the `work`, `invest` and paid-`other` branches
    carry the very facts these witnesses need to control. A test that proves
    what ONE qualifying fact does must start from a walk that carries none,
    or it measures the corpus's answer instead of its own fixture."""
    return {
        key: (_UNKNOWN if key in QUALIFICATION_FACTS else value) for key, value in overrides.items()
    }


@pytest.fixture(scope="module")
def unasked_walks(walks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every walk the interview before W-VO-Q could produce, with the ten
    facts back at UNKNOWN(NOT_ASKED). The business explorer (W-VO-Q item 7,
    ``business_activity = exploring``) is left out: that answer did not exist
    before the questions, so its "unasked" form is no interview anyone could
    have walked. Its answers on both packs are pinned per walk in
    ``test_interview_walk_census.py``."""
    return {
        label: {**spec, "overrides": _as_before_the_questions(spec["overrides"])}
        for label, spec in walks.items()
        if not label.startswith("offshore/business/exploring")
    }


@pytest.fixture(scope="module")
def gold_base(unasked_walks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A REAL corpus walk as the fixture base, never a hand-built fact bag: a
    persona assembled from scratch would drift from what the interview
    actually sends, and the point of these nine fixtures is that a real
    applicant can reach the product. Taken without the ten qualification
    answers, so each gold row supplies its product's fact alone."""
    return dict(unasked_walks["offshore/work/sponsor_government"]["overrides"])


# ---------------------------------------------------------------------------
# Fold integrity
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_is_deterministic_and_matches_disk(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        seq21_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        assert fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT) == seq21_source

    def test_the_cli_reproduces_the_bytes_the_owner_signs(
        self,
        tmp_path: Path,
        seq21_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        """Byte-level reproducibility, stated at the level that is signed.

        The committed file is NOT the writer's raw output: the repo's
        pre-commit hook runs prettier over every staged ``*.json`` (root
        ``package.json`` lint-staged), which reflows arrays — seq-19 and
        seq-20 carry the same reflow. What ``sign_pack.py`` signs is JCS over
        the parsed payload, so the byte contract a third party can re-execute
        is: run the CLI, canonicalize its file, and get EXACTLY the canonical
        bytes of the committed file, whose sha256 is the digest the owner
        signs. Comparing parsed dicts (the test above) would not catch a
        float/int or key-encoding drift that JCS would sign differently.

        The FILE bytes are reproducible too, one step further out: the CLI's
        output piped through ``prettier --stdin-filepath <this pack's path>``
        (prettier 3.9.6, repo root) is sha256-identical to the committed file
        — measured 2026-09-14, recorded in the evidence pack rather than
        asserted here, because this suite does not run node.
        """
        output = tmp_path / "rulepack-prod-021.source.json"
        assert (
            main(
                [
                    "--seq20-source",
                    str(_SEQ20_SOURCE_PATH),
                    "--seq20-signed",
                    str(_SEQ20_SIGNED_PATH),
                    "--output",
                    str(output),
                ],
                observed_at=OBSERVED_AT,
            )
            == 0
        )
        produced = canonicalize_json(json.loads(output.read_bytes()))
        committed = canonicalize_json(seq21_source)
        assert produced == committed
        assert hashlib.sha256(produced).hexdigest() == SEQ21_PAYLOAD_SHA256
        # sign_pack.py canonicalizes the TYPED payload
        # (``RulePackPayload.model_dump(mode="json", by_alias=True)``), not the
        # raw JSON: the digest above is only the signed one if both agree.
        typed = RulePackPayload.model_validate(seq21_source).model_dump(mode="json", by_alias=True)
        assert canonicalize_json(typed) == committed

    def test_fold_is_deterministic(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        first = fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)
        second = fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)
        assert first == second

    def test_fold_refuses_without_a_trust_store(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GUILT: the anchor must never be taken on the digest constant alone.
        Without the production PUBLIC key exported, the fold refuses instead
        of folding onto an unverified payload."""
        monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
        with pytest.raises(SystemExit) as excinfo:
            fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)
        assert "seq-20 anchor" in str(excinfo.value)

    def test_fold_refuses_a_base_pack_whose_review_rule_became_live(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """GUILT: the nine retirements are justified by the rules being
        dormant (gated on a fact the browser never sets). A base pack that had
        given one of them a browser-reachable condition must abort the fold,
        not have its gate silently deleted.

        The pre-flight census is exercised DIRECTLY rather than through
        :func:`fold`: mutating the base pack also moves its JCS digest, so the
        chain-anchor check would abort first and this witness would prove that
        check instead of the one it names.
        """
        mutated = copy.deepcopy(seq20_source)
        for rule in mutated["rules"]:
            if rule["rule_id"] == "review.e33b.expertise-qualification":
                rule["required_facts"] = ["intent.purposes"]
                rule["when"] = {
                    "op": "intersects",
                    "fact": "intent.purposes",
                    "values": ["EMPLOYMENT"],
                }
        with pytest.raises(SystemExit) as excinfo:
            _assert_retired_review_rules_are_dormant(mutated)
        assert "intent.requested_product_code" in str(excinfo.value)

    def test_the_dormancy_census_passes_on_the_real_base_pack(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """INNOCENCE for the guard above: it is not a check that always
        fails."""
        _assert_retired_review_rules_are_dormant(seq20_source)

    def test_fold_refuses_when_a_target_product_already_has_an_eligibility_rule(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        seq21_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        """GUILT: folding seq-21 onto ITSELF (a pack that already carries the
        nine SUPPORT rules) must abort rather than add a second, unreconciled
        route to the same products."""
        with pytest.raises(SystemExit):
            fold(seq21_source, seq20_signed, observed_at=OBSERVED_AT)

    def test_compile_rule_pack_reports_ok(self) -> None:
        payload = load_rule_pack_payload(_SEQ21_SOURCE_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, f"seq-21 does not compile clean: {report}"

    def test_source_validates_against_the_payload_model(self, seq21_source: dict[str, Any]) -> None:
        assert RulePackPayload.model_validate(seq21_source).sequence == 21


# ---------------------------------------------------------------------------
# Identity and chain
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_sequence_is_21(self, seq21_source: dict[str, Any]) -> None:
        assert seq21_source["sequence"] == 21

    def test_rule_pack_id_follows_the_uuid5_convention(self, seq21_source: dict[str, Any]) -> None:
        assert seq21_source["rule_pack_id"] == str(_rule_pack_id(21))

    def test_chain_anchor_is_the_measured_seq20_digest(
        self, seq20_source: dict[str, Any], seq21_source: dict[str, Any]
    ) -> None:
        """The anchor is re-derived from the seq-20 bytes on disk, never taken
        from the constant alone."""
        recomputed = hashlib.sha256(canonicalize_json(seq20_source)).hexdigest()
        assert recomputed == SEQ20_PAYLOAD_SHA256
        assert seq21_source["previous_payload_sha256"] == SEQ20_PAYLOAD_SHA256

    def test_chain_anchor_is_also_the_signed_artifacts_own_digest(
        self, seq20_signed: dict[str, Any]
    ) -> None:
        assert seq20_signed["payload_sha256"] == SEQ20_PAYLOAD_SHA256

    def test_payload_digest_survives_reformatting_of_the_file(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """The pack's identity is JCS over the PARSED document, never the file
        bytes, so the repo's prettier gate can reshape the file freely. The
        constant is the digest the owner signs; it was measured BEFORE the
        prettier pass and re-measured after it, unchanged."""
        digest = hashlib.sha256(canonicalize_json(seq21_source)).hexdigest()
        assert digest == SEQ21_PAYLOAD_SHA256

    def test_pack_legal_period_is_the_incumbents(
        self, seq21_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        """The pack's ``valid_period`` does not move, as in every fold since
        seq-13: it becomes the activation's ``legal_period``, and "not before
        the signature" is carried by the NEW rules' own validity instead."""
        assert seq21_source["valid_period"] == seq20_source["valid_period"]

    @staticmethod
    def _activation_would_be_refused(new: dict[str, Any], incumbent: dict[str, Any]) -> bool:
        """``visa_activate_rule_pack`` step 4 (migration 253), restated: an
        open prior activation whose legal period OVERLAPS the new one without
        being fully covered by it is an orphan, and the function refuses.
        Both periods here are ``[from, to)`` with ``to = None`` meaning open."""

        def bounds(period: dict[str, Any]) -> tuple[datetime, datetime]:
            low = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
            high = (
                datetime.max.replace(tzinfo=timezone.utc)
                if period["to"] is None
                else datetime.fromisoformat(period["to"].replace("Z", "+00:00"))
            )
            return low, high

        new_low, new_high = bounds(new["valid_period"])
        old_low, old_high = bounds(incumbent["valid_period"])
        overlaps = new_low < old_high and old_low < new_high
        covers = new_low <= old_low and old_high <= new_high
        return overlaps and not covers

    def test_the_activation_writer_would_accept_it_over_seq20(
        self, seq21_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        assert not self._activation_would_be_refused(seq21_source, seq20_source)

    def test_guilt_a_pack_opening_after_the_incumbent_would_be_refused(
        self, seq21_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        """GUILT: the first draft of this fold opened the PACK on
        2026-09-15. Over seq-20's open activation (legal period from
        2026-07-25) the DB would have inserted the immutable pack row and then
        refused the activation — sequence 21 burned at the ``--yes`` step."""
        mutated = copy.deepcopy(seq21_source)
        mutated["valid_period"] = {"to": None, "from": NEW_RULE_VALID_FROM}
        assert self._activation_would_be_refused(mutated, seq20_source)

    def test_every_new_rule_opens_no_earlier_than_the_fold(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """No inserted rule claims to have been law before the fold, and the
        census instant sits inside every new rule's window."""
        opens = datetime.fromisoformat(NEW_RULE_VALID_FROM.replace("Z", "+00:00"))
        assert opens >= datetime.fromisoformat(seq21_source["created_at"].replace("Z", "+00:00"))
        assert AS_OF >= opens
        new_rules = [r for r in seq21_source["rules"] if r["rule_id"] in NEW_RULE_IDS]
        assert len(new_rules) == len(NEW_RULE_IDS)
        for rule in new_rules:
            assert rule["valid_period"] == {"to": None, "from": NEW_RULE_VALID_FROM}

    def test_rollback_of_payload_sha256_is_null(self, seq21_source: dict[str, Any]) -> None:
        assert seq21_source["rollback_of_payload_sha256"] is None

    def test_products_and_sources_are_untouched(
        self, seq20_source: dict[str, Any], seq21_source: dict[str, Any]
    ) -> None:
        for key in (
            "environment",
            "jurisdiction",
            "decision_domain",
            "hit_policy",
            "products",
            "source_records",
            "engine_min_version",
            "engine_max_version",
            "engine_contract_version",
        ):
            assert _canon(seq21_source[key]) == _canon(seq20_source[key]), key


# ---------------------------------------------------------------------------
# Edit 1 — the nine retirements
# ---------------------------------------------------------------------------


class TestRetiredReviewRules:
    def test_every_retired_rule_was_dormant_in_seq20(self, seq20_source: dict[str, Any]) -> None:
        """INNOCENCE: nothing live was deleted. Each retired rule is a
        REQUIRE_REVIEW rule gated on ``intent.requested_product_code`` — the
        fact ``fact-mapper.ts`` hard-codes to UNKNOWN(NOT_ASKED), so no browser
        answer could ever make it fire."""
        rules = _rules_by_id(seq20_source)
        for rule_id in RETIRED_REVIEW_RULES:
            rule = rules[rule_id]
            assert rule["effect"]["type"] == "REQUIRE_REVIEW", rule_id
            assert "intent.requested_product_code" in rule["required_facts"], rule_id

    def test_retired_rules_are_absent_from_seq21(self, seq21_source: dict[str, Any]) -> None:
        present = sorted(set(RETIRED_REVIEW_RULES) & set(_rules_by_id(seq21_source)))
        assert present == []

    def test_no_review_rule_survives_on_requested_product_code_for_a_target_product(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """GUILT for A4: a REQUIRE_REVIEW rule that is UNKNOWN on
        ``intent.requested_product_code`` makes its product BLOCKED_UNKNOWN
        BEFORE ``purposes <= covered`` is ever tested
        (``evaluator.evaluate_product``), so one left behind would make the
        nine new SUPPORT rules structurally unable to produce a candidate."""
        products = {
            product["product_code"]: product["product_version_id"]
            for product in seq21_source["products"]
        }
        targets = {products[code] for code in TARGET_PRODUCT_CODES}
        offenders = [
            rule["rule_id"]
            for rule in seq21_source["rules"]
            if rule["stage"] == "HUMAN_REVIEW"
            and rule["on_unknown"] != "NO_EFFECT"
            and "intent.requested_product_code" in rule["required_facts"]
            and targets & set(rule["product_version_ids"])
        ]
        assert offenders == []

    def test_no_retired_rule_was_flipped_to_no_effect_instead(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """The dossier's §4 fail-open, stated as a test: a REQUIRE_REVIEW rule
        made ``NO_EFFECT`` still claims to police a qualification while being
        unable to block anything. None of the nine is in the pack at all."""
        for rule_id in RETIRED_REVIEW_RULES:
            assert rule_id not in _rules_by_id(seq21_source)

    def test_no_other_rule_moved(
        self, seq20_source: dict[str, Any], seq21_source: dict[str, Any]
    ) -> None:
        before = _rules_by_id(seq20_source)
        after = _rules_by_id(seq21_source)
        assert set(before) - set(after) == set(RETIRED_REVIEW_RULES)
        assert set(after) - set(before) == set(NEW_RULE_IDS)
        for rule_id, rule in after.items():
            if rule_id in set(NEW_RULE_IDS):
                continue
            assert _canon(rule) == _canon(before[rule_id]), rule_id


# ---------------------------------------------------------------------------
# Edit 2 — the nine SUPPORT rules
# ---------------------------------------------------------------------------


class TestSupportRuleShape:
    def test_every_target_product_has_exactly_one_eligibility_rule(
        self, seq21_source: dict[str, Any]
    ) -> None:
        products = {
            product["product_code"]: product["product_version_id"]
            for product in seq21_source["products"]
        }
        for row in SUPPORT_RULES:
            version_id = products[row["product_code"]]
            ids = sorted(
                rule["rule_id"]
                for rule in seq21_source["rules"]
                if rule["stage"] == "ELIGIBILITY" and version_id in rule["product_version_ids"]
            )
            assert ids == [row["rule_id"]], row["product_code"]

    def test_every_support_rule_reads_its_own_qualifying_fact(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """The cure, stated positively: no SUPPORT rule here is keyed on
        ``sponsor.type`` (or a route) alone."""
        rules = _rules_by_id(seq21_source)
        for row in SUPPORT_RULES:
            rule = rules[row["rule_id"]]
            assert row["qualifying_fact"] in QUALIFICATION_FACTS
            assert row["qualifying_fact"] in rule["required_facts"], row["rule_id"]
            eq_nodes = [
                node
                for node in _nodes(rule["when"])
                if node.get("fact") == row["qualifying_fact"]
                and node.get("op") == "eq"
                and node.get("value") is True
            ]
            assert len(eq_nodes) == 1, row["rule_id"]

    def test_sponsor_premises_admit_only_the_catalogues_sponsor_types(
        self, seq20_source: dict[str, Any], seq21_source: dict[str, Any]
    ) -> None:
        """INNOCENCE on the base pack, then measured on the output: every
        ``sponsor.type`` premise of a SUPPORT rule is a subset of its product's
        catalogue ``sponsor_types`` (E33B -> NONE, E33C -> GOVERNMENT, never
        the wider seq-20 hard filters' GOVERNMENT-or-NONE)."""
        _assert_sponsor_premises_follow_the_catalogue(seq20_source)
        products = {p["product_code"]: p for p in seq21_source["products"]}
        rules = {r["rule_id"]: r for r in seq21_source["rules"]}
        for row in SUPPORT_RULES:
            for node in rules[row["rule_id"]]["when"]["args"]:
                if node.get("fact") != "sponsor.type":
                    continue
                admitted = {node["value"]} if node["op"] == "eq" else set(node["values"])
                assert admitted <= set(products[row["product_code"]]["sponsor_types"])

    def test_guilt_a_premise_wider_than_the_catalogue_aborts_the_fold(
        self, seq20_source: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GUILT: re-widen E33C to the hard filter's GOVERNMENT-or-NONE, the
        shape of the first draft, and the fold-time check refuses."""
        import backend.scripts.visa_engine.fold_pack_seq21 as fold_module

        widened = tuple(
            {
                **row,
                "premises": [
                    {"op": "in", "fact": "sponsor.type", "values": ["GOVERNMENT", "NONE"]}
                ],
            }
            if row["product_code"] == "E33C"
            else row
            for row in SUPPORT_RULES
        )
        monkeypatch.setattr(fold_module, "SUPPORT_RULES", widened)
        with pytest.raises(SystemExit) as excinfo:
            fold_module._assert_sponsor_premises_follow_the_catalogue(seq20_source)
        assert "E33C" in str(excinfo.value)

    def test_no_two_support_rules_share_a_condition(self, seq21_source: dict[str, Any]) -> None:
        """GUILT, and the precise defect PR #6362 shipped: ``el.e33a``,
        ``el.e33b`` and ``el.e23v`` there had one byte-identical ``when``, so a
        single answer produced three products no fact distinguished."""
        rules = _rules_by_id(seq21_source)
        conditions = [_canon(rules[row["rule_id"]]["when"]) for row in SUPPORT_RULES]
        duplicates = [item for item, count in Counter(conditions).items() if count > 1]
        assert duplicates == []

    def test_every_support_rule_asks_rather_than_denies_on_an_unknown_qualification(
        self, seq21_source: dict[str, Any]
    ) -> None:
        rules = _rules_by_id(seq21_source)
        for row in SUPPORT_RULES:
            assert rules[row["rule_id"]]["on_unknown"] == "NEEDS_INPUT", row["rule_id"]

    def test_every_qualifying_fact_is_a_registered_fact_path(self) -> None:
        registered = {path.value for path in FactPath}
        assert QUALIFICATION_FACTS <= registered
        assert QUALIFICATION_FACTS <= {path.value for path in DEFAULT_FACT_REGISTRY.all_paths()}

    def test_support_purposes_are_covered_by_the_product_catalogue(
        self, seq21_source: dict[str, Any]
    ) -> None:
        products = {p["product_code"]: p for p in seq21_source["products"]}
        rules = _rules_by_id(seq21_source)
        for row in SUPPORT_RULES:
            covered = rules[row["rule_id"]]["effect"]["covered_purposes"]
            assert set(covered) <= set(products[row["product_code"]]["covered_purposes"])

    def test_no_e28_rule_invents_a_usd_figure(self, seq21_source: dict[str, Any]) -> None:
        """No source record in this pack states a Golden Visa USD minimum, so
        the four E28 rules must depend on the DECLARED
        ``investment.meets_published_threshold`` and never on a hard-coded
        comparison against ``investment.investment_amount_usd``."""
        rules = _rules_by_id(seq21_source)
        for row in SUPPORT_RULES:
            if not row["product_code"].startswith("E28"):
                continue
            rule = rules[row["rule_id"]]
            assert "investment.meets_published_threshold" in rule["required_facts"]
            assert "investment.investment_amount_usd" not in rule["required_facts"]
            assert rule["source_refs"], row["rule_id"]


# ---------------------------------------------------------------------------
# Edit 3 — the two named causes
# ---------------------------------------------------------------------------


class TestNamedCauseRules:
    def test_e33_guarantee_rule_mirrors_the_packs_own_bounds(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """The EXCLUDE's bounds are the SUPPORT rules' bounds, read from the
        pack — a second copy of the number would be free to drift, and the
        pack would then deny below X while granting at Y."""
        rules = _rules_by_id(seq21_source)
        rule = rules[E33_GUARANTEE_RULE_ID]
        deposit_support = [
            node
            for node in _nodes(rules["el.e33.deposit-basis"]["when"])
            if node.get("fact") == "secondhome.bank_deposit_usd" and node.get("op") == "gte"
        ]
        property_support = [
            node
            for node in _nodes(rules["el.e33.property-basis"]["when"])
            if node.get("fact") == "secondhome.qualifying_property_value_usd"
            and node.get("op") == "gte"
        ]
        exclude = {
            node["fact"]: node["value"] for node in _nodes(rule["when"]) if node.get("op") == "lt"
        }
        assert exclude["secondhome.bank_deposit_usd"] == deposit_support[0]["value"]
        assert exclude["secondhome.qualifying_property_value_usd"] == property_support[0]["value"]

    def test_both_named_cause_rules_never_fire_on_an_unknown(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """An EXCLUDE that fired on UNKNOWN would deny a product to somebody
        who never answered — the opposite of naming a cause."""
        rules = _rules_by_id(seq21_source)
        for rule_id in (E33_GUARANTEE_RULE_ID, EMPLOYMENT_SPONSOR_RULE_ID):
            assert rules[rule_id]["on_unknown"] == "NO_EFFECT", rule_id
            assert rules[rule_id]["effect"]["type"] == "EXCLUDE", rule_id
            assert rules[rule_id]["stage"] == "HARD_FILTER", rule_id

    def test_employment_rule_is_scoped_to_products_that_cover_employment(
        self, seq21_source: dict[str, Any]
    ) -> None:
        products = {p["product_version_id"]: p for p in seq21_source["products"]}
        rule = _rules_by_id(seq21_source)[EMPLOYMENT_SPONSOR_RULE_ID]
        codes = sorted(products[vid]["product_code"] for vid in rule["product_version_ids"])
        assert codes == sorted(EMPLOYMENT_SPONSOR_PRODUCT_CODES)
        for vid in rule["product_version_ids"]:
            assert "EMPLOYMENT" in products[vid]["covered_purposes"]

    def test_e23u_is_deliberately_outside_the_employment_exclusion(
        self, seq21_source: dict[str, Any]
    ) -> None:
        """INNOCENCE, and the reason it is written down: E23U's employer is a
        foreign diplomatic mission, which is legitimately NOT an Indonesian
        entity. Sweeping it into the exclusion would deny the product on the
        very fact that qualifies it."""
        products = {p["product_code"]: p["product_version_id"] for p in seq21_source["products"]}
        rule = _rules_by_id(seq21_source)[EMPLOYMENT_SPONSOR_RULE_ID]
        assert products["E23U"] not in rule["product_version_ids"]


# ---------------------------------------------------------------------------
# Behaviour — the nine gold fixtures
# ---------------------------------------------------------------------------


class TestTheNineProductsAreReachable:
    def test_each_target_product_is_supported_on_its_gold_fixture(
        self,
        seq21_compiled: compiler.CompiledRulePack,
        gold_base: dict[str, Any],
    ) -> None:
        """The objective, measured: all nine of the products with no SUPPORT
        rule on seq-20 are named by the engine on facts the interview can ask."""
        missing: list[str] = []
        for code, override in _gold_overrides().items():
            facts = {**gold_base, **override}
            actual = _decide(seq21_compiled, facts, f"gold/{code}")
            if actual["state"] != "SUPPORTED_CANDIDATES" or code not in actual["candidates"]:
                missing.append(f"{code}: {actual['state']} {actual['candidates']}")
        assert missing == []

    def test_seq20_reaches_none_of_them_on_the_same_fixtures(
        self,
        seq20_compiled: compiler.CompiledRulePack,
        gold_base: dict[str, Any],
    ) -> None:
        """INNOCENCE for the claim that this fold is what moved them: the SAME
        nine fact bags against the signed-today pack name none of the nine."""
        reached = []
        for code, override in _gold_overrides().items():
            facts = {**gold_base, **override}
            actual = _decide(seq20_compiled, facts, f"gold/{code}")
            if code in actual["candidates"]:
                reached.append(code)
        assert reached == []

    def test_an_unknown_qualification_asks_instead_of_supporting(
        self,
        seq21_compiled: compiler.CompiledRulePack,
        gold_base: dict[str, Any],
    ) -> None:
        """GUILT: withdraw the qualifying fact from each gold fixture and the
        product must disappear from the candidates, with the outcome becoming
        a QUESTION (``NEEDS_INPUT``) rather than a silent denial or, worse, a
        SUPPORT on the sponsor category alone."""
        offenders: list[str] = []
        for code, override in _gold_overrides().items():
            stripped = {
                key: (_UNKNOWN if key in QUALIFICATION_FACTS else value)
                for key, value in override.items()
            }
            actual = _decide(seq21_compiled, {**gold_base, **stripped}, f"gold-unknown/{code}")
            if code in actual["candidates"] or actual["state"] != "NEEDS_INPUT":
                offenders.append(f"{code}: {actual['state']} {actual['candidates']}")
        assert offenders == []


# ---------------------------------------------------------------------------
# Behaviour — the guilt witness for the cure itself
# ---------------------------------------------------------------------------


class TestSponsorTypeAloneIsNotEvidence:
    """Re-inject the defect and prove the corpus notices.

    ``_uncured`` removes ONLY the qualifying-fact conjunct from the nine
    SUPPORT rules, which is exactly the shape PR #6362 shipped for its five.
    If the census does not move, the qualifying facts are decorative and this
    whole fold is theatre.

    Replayed on the corpus WITHOUT the ten answers (``unasked_walks``): the
    witness is about what the rule does when nothing established the
    qualification, which is exactly the state W-VO-Q's answers would hide.
    """

    @staticmethod
    def _uncured(seq21_source: dict[str, Any]) -> dict[str, Any]:
        mutated = copy.deepcopy(seq21_source)
        quals = {row["rule_id"]: row["qualifying_fact"] for row in SUPPORT_RULES}
        for rule in mutated["rules"]:
            fact = quals.get(rule["rule_id"])
            if fact is None:
                continue
            rule["when"]["args"] = [arg for arg in rule["when"]["args"] if arg.get("fact") != fact]
            rule["required_facts"] = sorted(path for path in rule["required_facts"] if path != fact)
        return mutated

    def test_stripping_the_qualification_hands_products_out_on_no_evidence(
        self,
        seq21_source: dict[str, Any],
        seq21_compiled: compiler.CompiledRulePack,
        unasked_walks: dict[str, dict[str, Any]],
    ) -> None:
        cured = _replay(seq21_compiled, unasked_walks)
        uncured = _replay(_compiled(self._uncured(seq21_source)), unasked_walks)
        moved = [label for label in cured if cured[label] != uncured[label]]
        # Measured 2026-09-14: 9 walks. It was 16 while E33B/E33C admitted
        # GOVERNMENT-or-NONE; aligning both premises to the catalogue removed
        # seven of the would-be gains before this guilt witness even runs.
        assert len(moved) >= 9, (
            "removing the qualifying facts moved only "
            f"{len(moved)} walks — the conjuncts are not load-bearing"
        )

    def test_a_sponsor_type_of_none_would_gain_e33b(
        self,
        seq21_source: dict[str, Any],
        seq21_compiled: compiler.CompiledRulePack,
        unasked_walks: dict[str, dict[str, Any]],
    ) -> None:
        """The named guilt: ``offshore/work`` and ``offshore/other`` both
        declare ``sponsor.type = NONE``. Un-cured, the pack offers them E33B
        with nothing having established a collaboration."""
        label = "offshore/work"
        cured = _decide(seq21_compiled, unasked_walks[label]["overrides"], label)
        uncured = _decide(
            _compiled(self._uncured(seq21_source)), unasked_walks[label]["overrides"], label
        )
        assert "E33B" not in cured["candidates"]
        assert "E33B" in uncured["candidates"]

    def test_a_government_sponsor_would_gain_two_products_at_once(
        self,
        seq21_source: dict[str, Any],
        seq21_compiled: compiler.CompiledRulePack,
        unasked_walks: dict[str, dict[str, Any]],
    ) -> None:
        """The dossier's §4 finding, reproduced: un-cured, ONE answer produces
        E23V + E33A together because nothing tells them apart. (The dossier
        measured three with E33B; E33B's premise is now the catalogue's NONE,
        so a government sponsor no longer reaches it even un-cured.)"""
        label = "offshore/work/sponsor_government"
        cured = _decide(seq21_compiled, unasked_walks[label]["overrides"], label)
        uncured = _decide(
            _compiled(self._uncured(seq21_source)), unasked_walks[label]["overrides"], label
        )
        assert cured["candidates"] == ["E23"]
        assert {"E23V", "E33A"} <= set(uncured["candidates"])
        assert "E33B" not in uncured["candidates"]


# ---------------------------------------------------------------------------
# Behaviour — the walk-corpus census (84 walks when written, 94 since W-VO-E)
# ---------------------------------------------------------------------------


#: E23V-DEFECT (mission seq-22): the ONE walk whose "unasked" (pre-W-VO-Q)
#: replay legitimately DOES drift between seq-20 and seq-21, and exactly why.
#: With BOTH seq-21 qualification facts on the `sponsor.type == GOVERNMENT`
#: branch back at UNKNOWN, `el.e33a.government-invitation` and
#: `el.e23v.trade-office` are both undetermined — but on every OTHER walk on
#: that branch `work.employer_is_indonesian_entity` stays the corpus default
#: `true`, so E23 alone (unaffected by the two pending SUPPORT rules) already
#: covers EMPLOYMENT and the decision stays decisive. This walk is the ONE
#: exception: `work.employer_is_indonesian_entity = false` is NOT one of the
#: ten qualification facts `_as_before_the_questions` strips, so it survives
#: unasking and `hf.employment-without-indonesian-sponsor` (KNOWN, not
#: pending) excludes E23 too — the corpus's only safety net on this branch —
#: leaving E33A's own pending `sponsor.government_invitation` as the ONLY
#: still-open question. Measured: seq-20 NO_SUPPORTED_PATH (), seq-21
#: NEEDS_INPUT on `sponsor.government_invitation`.
_UNASKED_DRIFT_ALLOWLIST: dict[str, tuple[str, str]] = {
    "offshore/work/sponsor_government/trade_office_only/employer_no": (
        "NO_SUPPORTED_PATH",
        "NEEDS_INPUT",
    ),
}


class TestCensusReplay:
    def test_without_the_answers_no_walk_changes_state_or_candidates(
        self,
        seq20_compiled: compiler.CompiledRulePack,
        seq21_compiled: compiler.CompiledRulePack,
        unasked_walks: dict[str, dict[str, Any]],
    ) -> None:
        """The fold's own no-regression claim, kept: with the ten facts
        UNKNOWN (the interview before W-VO-Q), no walk gains a product and —
        what must never happen — no walk loses its answer, and no
        ``on_unknown: NEEDS_INPUT`` rule turns a decided dead end into a
        question, with exactly one named, checked exception —
        ``_UNASKED_DRIFT_ALLOWLIST`` — where a dead end becomes a QUESTION
        (never a lost answer) for a reason pinned above."""
        before = _replay(seq20_compiled, unasked_walks)
        after = _replay(seq21_compiled, unasked_walks)
        drift = [
            f"{label}: {before[label]['state']} {before[label]['candidates']} -> "
            f"{after[label]['state']} {after[label]['candidates']}"
            for label in sorted(before)
            if (before[label]["state"], before[label]["candidates"])
            != (after[label]["state"], after[label]["candidates"])
            and label not in _UNASKED_DRIFT_ALLOWLIST
        ]
        assert drift == []
        for label, (before_state, after_state) in _UNASKED_DRIFT_ALLOWLIST.items():
            assert before[label]["state"] == before_state, label
            assert after[label]["state"] == after_state, label
            assert before[label]["candidates"] == after[label]["candidates"] == [], label

    def test_without_the_answers_the_census_is_89_answers_15_no_paths_3_questions(
        self,
        seq21_compiled: compiler.CompiledRulePack,
        unasked_walks: dict[str, dict[str, Any]],
    ) -> None:
        """67 / 15 / 2 / 0 over the 84-walk corpus this fold was measured on;
        89 / 15 / 2 / 1 over W-VO-Q's 107 walks (W-VO-E's nine adult walks and
        W-VO-Q's thirteen are all answers on the signed pack, and the one hold is W-VO-E's
        minor walk, held by the privacy adapter, not by this pack). E23V-DEFECT
        (mission seq-22) adds one walk over a 107 -> 108 unasked corpus, and
        it is the one exception in ``_UNASKED_DRIFT_ALLOWLIST`` above:
        89 / 15 / 3 / 1."""
        replayed = _replay(seq21_compiled, unasked_walks)
        census = Counter(actual["state"] for actual in replayed.values())
        assert census["SUPPORTED_CANDIDATES"] == 89
        assert census["NO_SUPPORTED_PATH"] == 15
        assert census["NEEDS_INPUT"] == 3
        assert census["HUMAN_REVIEW_REQUIRED"] == 1
        held = [
            label
            for label, actual in replayed.items()
            if actual["state"] == "HUMAN_REVIEW_REQUIRED"
        ]
        assert held == ["offshore/family/PARENT/spNat=IT/minor"]

    def test_with_the_answers_walks_only_gain_the_nine_products(
        self,
        seq20_compiled: compiler.CompiledRulePack,
        seq21_compiled: compiler.CompiledRulePack,
        walks: dict[str, dict[str, Any]],
    ) -> None:
        """W-VO-Q's measured effect, pinned walk by walk: with the interview
        ASKING the ten facts, seq-21 adds exactly ``EXPECTED_SEQ21_GAINS`` to
        what seq-20 answers, every added code is one of the nine products this
        fold made supportable, no walk loses a candidate, and the only state
        that moves is one NEEDS_INPUT walk becoming an answer."""
        before = _replay(seq20_compiled, walks)
        after = _replay(seq21_compiled, walks)
        gains: dict[str, tuple[str, ...]] = {}
        for label in sorted(before):
            lost = [
                code
                for code in before[label]["candidates"]
                if code not in after[label]["candidates"]
            ]
            assert lost == [], f"{label}: seq-21 drops {lost}"
            gained = tuple(
                code
                for code in after[label]["candidates"]
                if code not in before[label]["candidates"]
            )
            if gained:
                gains[label] = gained
            if before[label]["state"] != after[label]["state"]:
                assert (before[label]["state"], after[label]["state"]) == (
                    "NEEDS_INPUT",
                    "SUPPORTED_CANDIDATES",
                ), label
        assert gains == EXPECTED_SEQ21_GAINS
        assert {code for codes in gains.values() for code in codes} == set(TARGET_PRODUCT_CODES)

    def test_no_walk_regresses_onto_requested_product_code(
        self,
        seq21_compiled: compiler.CompiledRulePack,
        walks: dict[str, dict[str, Any]],
    ) -> None:
        """A4. ``intent.requested_product_code`` is never asked by the browser,
        so a walk blocked on it is a question the funnel cannot honour."""
        offenders = [
            label
            for label, actual in _replay(seq21_compiled, walks).items()
            if "intent.requested_product_code" in actual["missing_facts"]
        ]
        assert offenders == []

    def test_the_four_generic_dead_ends_now_name_their_cause(
        self,
        seq20_compiled: compiler.CompiledRulePack,
        seq21_compiled: compiler.CompiledRulePack,
        walks: dict[str, dict[str, Any]],
    ) -> None:
        before = _replay(seq20_compiled, walks)
        after = _replay(seq21_compiled, walks)
        for label, expected_code in NAMED_CAUSE_WALKS.items():
            assert before[label]["no_path_reason_codes"] == [_GENERIC_CAUSE], label
            codes = after[label]["no_path_reason_codes"]
            assert _GENERIC_CAUSE not in codes, label
            assert expected_code in codes, label
            assert after[label]["state"] == "NO_SUPPORTED_PATH", label

    def test_no_other_walk_loses_or_gains_a_no_path_reason(
        self,
        seq20_compiled: compiler.CompiledRulePack,
        seq21_compiled: compiler.CompiledRulePack,
        walks: dict[str, dict[str, Any]],
    ) -> None:
        """INNOCENCE: the two new hard filters touch the three walks they were
        written for and nothing else."""
        before = _replay(seq20_compiled, walks)
        after = _replay(seq21_compiled, walks)
        moved = sorted(
            label
            for label in before
            if before[label]["no_path_reason_codes"] != after[label]["no_path_reason_codes"]
        )
        assert moved == sorted(NAMED_CAUSE_WALKS)

    def test_every_no_path_code_seq21_emits_on_the_corpus_has_visitor_copy(
        self,
        seq21_compiled: compiler.CompiledRulePack,
        walks: dict[str, dict[str, Any]],
    ) -> None:
        """Cross-app guard: a no-path code without an entry in the mouth's
        ``SUPPORT_REASON_COPY`` renders as ``Verified reason: <CODE>``. seq-21
        makes E33A purpose-feasible on a paid-work walk, which surfaces the
        seq-20 code ``E33A_SPONSOR_NOT_GOVERNMENT`` there for the first time;
        this measures every code the candidate emits on the corpus walks (94
        since W-VO-E) against the copy keys parsed out of
        ``engine-adapter.ts``."""
        adapter = (
            Path(__file__).resolve().parents[5]
            / "mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts"
        ).read_text(encoding="utf-8")
        start = adapter.index("export const SUPPORT_REASON_COPY")
        body = adapter[start : adapter.index("\n};", start)]
        copy_keys = set(re.findall(r"^  ([A-Z0-9_]+): text\(", body, re.MULTILINE))
        assert len(copy_keys) > 20, "the copy-map parse found almost nothing"
        emitted = {
            code
            for outcome in _replay(seq21_compiled, walks).values()
            for code in outcome["no_path_reason_codes"]
        }
        assert emitted, "no walk emitted a no-path code — the replay proves nothing"
        assert sorted(emitted - copy_keys) == []

    def test_the_generic_catalogue_sentence_is_gone_from_the_corpus(
        self,
        seq21_compiled: compiler.CompiledRulePack,
        walks: dict[str, dict[str, Any]],
    ) -> None:
        offenders = [
            label
            for label, actual in _replay(seq21_compiled, walks).items()
            if _GENERIC_CAUSE in actual["no_path_reason_codes"]
        ]
        assert offenders == []
