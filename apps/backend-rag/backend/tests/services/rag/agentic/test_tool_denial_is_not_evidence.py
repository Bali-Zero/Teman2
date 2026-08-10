"""A REFUSED tool call must not score as a successful one.

Measured in prod on 2026-08-10. A WhatsApp-shaped query ("Any deadlines I
should worry about for my clients this week?") made the model call
`crm_query`; the authorizer denied it (`principal_present=False`); and the
evidence layer logged:

    🔧 [Trusted Tools] crm_query used successfully (obs_len=54), bypassing
       keyword evidence check
    🛡️ [Evidence] Trusted tools used: score=0.85

`obs_len=54` is exactly `len(ANONYMOUS_DENIAL_OBSERVATION)`. The old gate
accepted it because it judged the observation's PROSE (no "error", no "not
found", no "no relevant") and its LENGTH (54 > 50). The denial string is bland
by design — P0-DENY made it name no tool and no control so a client-facing
model would have nothing to narrate — and blandness is precisely what a
failure-word scan cannot see.

Guilt, innocence, and an anti-drift pass that proves the mint and the
recogniser still agree (cicatrix #9 / W114: the two sides that never agreed).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.services.rag.agentic._reasoning_evidence import (
    _CONTEXT_MIN_LEN_FOR_TRUSTED_OBS,
    compute_evidence_score,
    detect_trusted_tool_usage,
)
from backend.services.rag.agentic._tool_denial import (
    ANONYMOUS_DENIAL_OBSERVATION,
    DENIAL_PREFIX,
    denial_observation,
    is_denial_observation,
)

TRUSTED = ("crm_query", "get_pricing", "team_knowledge", "vector_search")

# A real crm_query result: long enough, no failure words. The control that
# keeps this fix from being "return False always".
REAL_CRM_RESULT = (
    "3 records: KITAS extension due 2026-09-01; LKPM quarterly filing due "
    "2026-10-15; company NIB renewal due 2026-11-30."
)


@dataclass
class _Action:
    tool_name: str


@dataclass
class _Step:
    action: _Action
    observation: str


def _step(tool: str, observation: str) -> _Step:
    return _Step(action=_Action(tool_name=tool), observation=observation)


class TestTheOldHeuristicWouldHavePassedThisDenial:
    """Pins WHY the fix is needed, so a revert to prose-scanning fails here."""

    def test_the_anonymous_denial_clears_the_length_floor(self) -> None:
        # 54 > 50. Four characters is the whole margin.
        assert len(ANONYMOUS_DENIAL_OBSERVATION) > _CONTEXT_MIN_LEN_FOR_TRUSTED_OBS

    def test_the_anonymous_denial_contains_no_failure_word(self) -> None:
        lowered = ANONYMOUS_DENIAL_OBSERVATION.lower()
        for marker in ("error", "not found", "no relevant"):
            assert marker not in lowered, (
                f"{marker!r} appears in the denial string — if a future edit "
                "reintroduces a failure word this test's premise dies, and "
                "with it the reason the entity check exists"
            )


class TestGuiltADeniedToolIsNotEvidence:
    def test_anonymous_denial_does_not_grant_trusted_tool_usage(self) -> None:
        """The exact prod case: crm_query denied for a caller with no principal."""
        steps = [_step("crm_query", ANONYMOUS_DENIAL_OBSERVATION)]
        assert detect_trusted_tool_usage(steps, TRUSTED) is False

    def test_authenticated_denial_does_not_grant_trusted_tool_usage(self) -> None:
        """The other half of the mint — a resolved agent_role still got denied."""
        observation = denial_observation(
            "team_member", "crm_query requires scope crm:read"
        )
        steps = [_step("crm_query", observation)]
        assert detect_trusted_tool_usage(steps, TRUSTED) is False

    def test_a_denied_tool_no_longer_scores_085(self) -> None:
        """End to end: the score the client's answer is graded on."""
        steps = [_step("crm_query", ANONYMOUS_DENIAL_OBSERVATION)]
        trusted = detect_trusted_tool_usage(steps, TRUSTED)
        score = compute_evidence_score(
            trusted_tools_used=trusted,
            sources=[],
            context_gathered=[],
            query="Any deadlines I should worry about for my clients this week?",
        )
        assert score < 0.85, (
            "a refused CRM lookup was buying the same confidence as a "
            f"satisfied one (got {score})"
        )

    def test_a_denial_among_several_denials_still_yields_no_trust(self) -> None:
        steps = [
            _step("crm_query", ANONYMOUS_DENIAL_OBSERVATION),
            _step("get_pricing", denial_observation("team_member", "no scope")),
            _step("crm_query", ANONYMOUS_DENIAL_OBSERVATION),
        ]
        assert detect_trusted_tool_usage(steps, TRUSTED) is False


class TestInnocenceTheFixMustNotSwallowRealResults:
    """The load-bearing half — otherwise the cure is `return False`."""

    def test_a_real_crm_result_still_grants_trust(self) -> None:
        steps = [_step("crm_query", REAL_CRM_RESULT)]
        assert detect_trusted_tool_usage(steps, TRUSTED) is True

    def test_a_real_result_beside_a_denial_still_grants_trust(self) -> None:
        """One tool refused, another answered — OR-semantics must survive."""
        steps = [
            _step("crm_query", ANONYMOUS_DENIAL_OBSERVATION),
            _step("team_knowledge", REAL_CRM_RESULT),
        ]
        assert detect_trusted_tool_usage(steps, TRUSTED) is True

    def test_a_result_that_merely_discusses_denial_still_grants_trust(self) -> None:
        """Entity, not form — the cicatrix #3 innocence case.

        A KB chunk about visa refusals contains the word "denied" and even the
        phrase "execution denied" mid-sentence. It was NOT minted as a denial,
        so it is real content and must keep scoring.
        """
        observation = (
            "When an application is denied, the applicant receives a written "
            "notice. Tool execution denied is not a phrase used by Imigrasi; "
            "the formal term is penolakan and it may be appealed within 30 days."
        )
        assert is_denial_observation(observation) is False
        steps = [_step("team_knowledge", observation)]
        assert detect_trusted_tool_usage(steps, TRUSTED) is True

    def test_pricing_result_still_grants_trust(self) -> None:
        observation = (
            "E28A Investor KITAS: IDR 17,000,000 all-inclusive, 12 months, "
            "processing 30-45 working days."
        )
        steps = [_step("get_pricing", observation)]
        assert detect_trusted_tool_usage(steps, TRUSTED) is True


class TestTheMintAndTheRecogniserAgree:
    """W114 antidote: prove the two sides agree instead of assuming it.

    If someone rewords the denial copy and only touches the mint, this fails —
    which is the whole point. The defect being cured was born exactly that
    way: P0-DENY changed the string, and nothing told the evidence layer.
    """

    @pytest.mark.parametrize(
        "agent_role",
        [None, "team_member", "admin", object()],
    )
    @pytest.mark.parametrize(
        "detail",
        ["", "needs scope crm:read", "This action needs an authenticated principal."],
    )
    def test_every_minted_denial_is_recognised(
        self, agent_role: object, detail: str
    ) -> None:
        assert is_denial_observation(denial_observation(agent_role, detail)) is True

    def test_the_prefix_constant_is_what_the_mint_actually_writes(self) -> None:
        assert denial_observation("team_member", "X") == f"{DENIAL_PREFIX}X"

    def test_the_executor_reexports_the_same_string_it_always_did(self) -> None:
        """tool_executor's private name must keep pointing at the one owner."""
        from backend.services.rag.agentic.tool_executor import (
            _ANONYMOUS_DENIAL_OBSERVATION,
            _denial_observation,
        )

        assert _ANONYMOUS_DENIAL_OBSERVATION == ANONYMOUS_DENIAL_OBSERVATION
        assert _denial_observation(None, "ignored") == ANONYMOUS_DENIAL_OBSERVATION
        assert _denial_observation("team_member", "why") == f"{DENIAL_PREFIX}why"


class TestPredicateEdges:
    @pytest.mark.parametrize("value", [None, "", "   ", "some other text"])
    def test_a_non_denial_is_not_a_denial(self, value: str | None) -> None:
        # Whitespace is not a denial either: it is an empty observation, which
        # both callers already skip on their own `if not observation` guard.
        assert is_denial_observation(value) is False

    def test_a_denial_with_trailing_context_is_still_a_denial(self) -> None:
        """The mint appends detail after the prefix — prefix match is correct."""
        assert is_denial_observation(f"{DENIAL_PREFIX}anything at all here") is True
