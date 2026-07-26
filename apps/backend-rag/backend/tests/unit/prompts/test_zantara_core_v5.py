"""
Falsifiable acceptance tests for zantara_core_v5 (audience-composed prompt).

Executes the design doc's §4 acceptance criteria verbatim as tests — these
ARE the deliverable's proof, not an afterthought:

1. TestClientAudiencePurity  — build("client") leaks no crm_query/timesheet/
   team_knowledge, and no third-person "the client"/"a client" referent.
2. TestTeamCapabilitySuperset — build("team") retains the CRM playbook and
   is a strict superset of client's (empty) capability set.
3. TestCoverage — the union of the three composed prompts covers every v4
   section; nothing was silently dropped in the CORE/VOICE/CAPABILITY split.
4. TestFactParity — every regulatory constant present in v4 is present,
   byte-identical, in the v5 composition.
5. TestFlagOff — this file's mere existence does not change
   backend.llm.prompt_manager's behaviour for ZANTARA_PROMPT_VERSION unset,
   "v4", or any other value (v5 is not wired into the door yet — see the
   module docstring's "Versioned door" section).

Also covers the mechanical-move discipline that makes 1-4 trustworthy:
TestRoundTrip proves the referent-neutralization + CRM-block split is
LOSSLESS (undoing it reconstructs v4's TOOL_USAGE_POLICY/INTERNAL_MONOLOGUE
byte-for-byte), so "no fact changed" isn't just asserted, it's verified
against the actual v4 source in this test run.
"""

import importlib
import re

import pytest

from backend.prompts import zantara_core_v4 as v4
from backend.prompts import zantara_core_v5 as v5

# ---------------------------------------------------------------------------
# 1. CLIENT AUDIENCE PURITY (C19 + C20 fix)
# ---------------------------------------------------------------------------


class TestClientAudiencePurity:
    def test_client_build_has_no_crm_query(self) -> None:
        built = v5.build_master_template("client")
        assert "crm_query" not in built

    def test_client_build_has_no_timesheet_tool(self) -> None:
        built = v5.build_master_template("client")
        assert "timesheet" not in built

    def test_client_build_has_no_team_knowledge_tool(self) -> None:
        built = v5.build_master_template("client")
        assert "team_knowledge" not in built

    def test_client_build_has_no_third_person_the_client(self) -> None:
        """The exact live-probe bug: model told 'you can pass this info
        directly to the client'. Guard against the referent pattern
        reappearing, not just the literal probe sentence."""
        built = v5.build_master_template("client")
        assert not re.search(r"(?i)\bthe client\b", built)

    def test_client_build_has_no_a_client_referent(self) -> None:
        built = v5.build_master_template("client")
        assert not re.search(r"(?i)\ba client\b", built)

    def test_client_build_has_no_possessive_client_referent(self) -> None:
        built = v5.build_master_template("client")
        assert not re.search(r"(?i)client['’]s", built)

    def test_client_capability_block_is_empty_by_construction(self) -> None:
        assert v5.CAPABILITY_BLOCK_CLIENT == ""

    def test_unknown_audience_defaults_to_client_fail_safe(self) -> None:
        """An unrecognised audience value must never fail open toward
        team/creator capabilities."""
        built_unknown = v5.build_master_template("nonsense-value")
        built_client = v5.build_master_template("client")
        assert built_unknown == built_client
        assert "crm_query" not in built_unknown


# ---------------------------------------------------------------------------
# 2. TEAM CAPABILITY SUPERSET
# ---------------------------------------------------------------------------


class TestTeamCapabilitySuperset:
    def test_team_build_contains_crm_playbook(self) -> None:
        built = v5.build_master_template("team")
        assert "crm_query" in built
        assert v5.CRM_CAPABILITY_BLOCK in built

    def test_creator_build_also_contains_crm_playbook(self) -> None:
        built = v5.build_master_template("creator")
        assert "crm_query" in built
        assert v5.CRM_CAPABILITY_BLOCK in built

    def test_team_capability_set_is_strict_superset_of_client(self) -> None:
        client_capabilities = set(v5.CAPABILITY_BLOCK_CLIENT.split())
        team_capabilities = set(v5.CAPABILITY_BLOCK_TEAM.split())
        assert client_capabilities.issubset(team_capabilities)
        assert client_capabilities != team_capabilities  # strictly more, not equal

    def test_team_and_client_share_identical_core_factual(self) -> None:
        """The audience split must not fork CORE_FACTUAL — team and client
        get the exact same shared body, only voice + capability differ."""
        client_built = v5.build_master_template("client")
        team_built = v5.build_master_template("team")
        assert v5.CORE_FACTUAL in client_built
        assert v5.CORE_FACTUAL in team_built

    def test_team_voice_is_the_existing_team_persona_unchanged(self) -> None:
        assert v5.AUDIENCE_VOICE_TEAM == v4.TEAM_PERSONA

    def test_creator_voice_is_the_existing_creator_persona_unchanged(self) -> None:
        assert v5.AUDIENCE_VOICE_CREATOR == v4.CREATOR_PERSONA


# ---------------------------------------------------------------------------
# 3. COVERAGE — union of the three builds covers every v4 section
# ---------------------------------------------------------------------------


class TestCoverage:
    """A dropped block must fail CI, not be discovered by a client."""

    # Sections moved into CORE_FACTUAL byte-identical (untouched by the
    # referent-neutralization split) — verbatim substring check.
    UNTOUCHED_CORE_SECTIONS = {
        "SECURITY_BOUNDARY": v4.SECURITY_BOUNDARY,
        "SYSTEM_INSTRUCTIONS": v4.SYSTEM_INSTRUCTIONS,
        "KNOWLEDGE_GOVERNANCE": v4.KNOWLEDGE_GOVERNANCE,
        "LANGUAGE_PROTOCOL": v4.LANGUAGE_PROTOCOL,
        "GREETING_RULES": v4.GREETING_RULES,
        "CITATION_RULES": v4.CITATION_RULES,
        "ESCALATION_PROTOCOL": v4.ESCALATION_PROTOCOL,
        "CRASH_PROTOCOL": v4.CRASH_PROTOCOL,
        "CLOSING_PHRASES": v4.CLOSING_PHRASES,
        "WORKED_EXAMPLES": v4.WORKED_EXAMPLES,
    }

    def test_every_untouched_core_section_lands_in_core_factual(self) -> None:
        missing = [
            name
            for name, text in self.UNTOUCHED_CORE_SECTIONS.items()
            if text not in v5.CORE_FACTUAL
        ]
        assert missing == [], f"Sections dropped from CORE_FACTUAL: {missing}"

    def test_tool_usage_policy_non_crm_content_covered_via_round_trip(self) -> None:
        """TOOL_USAGE_POLICY was split + partially reworded (referent fix) —
        can't substring-match verbatim, so coverage is proven by reversing
        the documented replacements and checking we land back on v4's
        original text exactly (see TestRoundTrip for the full proof)."""
        assert v5._TOOL_USAGE_POLICY_CORE in v5.CORE_FACTUAL

    def test_internal_monologue_covered_via_round_trip(self) -> None:
        assert v5.INTERNAL_MONOLOGUE in v5.CORE_FACTUAL

    def test_crm_capability_block_covered_in_team_and_creator_only(self) -> None:
        client_built = v5.build_master_template("client")
        team_built = v5.build_master_template("team")
        creator_built = v5.build_master_template("creator")
        assert v5.CRM_CAPABILITY_BLOCK not in client_built
        assert v5.CRM_CAPABILITY_BLOCK in team_built
        assert v5.CRM_CAPABILITY_BLOCK in creator_built

    def test_creator_persona_covered_in_creator_build(self) -> None:
        creator_built = v5.build_master_template("creator")
        assert v4.CREATOR_PERSONA in creator_built

    def test_team_persona_covered_in_team_build(self) -> None:
        team_built = v5.build_master_template("team")
        assert v4.TEAM_PERSONA in team_built

    def test_date_context_placeholder_present_in_every_audience(self) -> None:
        for audience in v5.VALID_AUDIENCES:
            built = v5.build_master_template(audience)
            assert "<date_context>" in built
            assert "{today_wita}" in built

    def test_runtime_placeholders_present_in_every_audience(self) -> None:
        for audience in v5.VALID_AUDIENCES:
            built = v5.build_master_template(audience)
            assert "{user_memory}" in built
            assert "{rag_results}" in built
            assert "{query}" in built


# ---------------------------------------------------------------------------
# ROUND-TRIP — proves the neutralization + CRM split is lossless (the
# structural guarantee behind "no fact changed", verified against the
# actual v4 source in THIS run, not just asserted in a docstring).
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_undoing_referent_neutralizations_reconstructs_v4_tool_usage_policy(
        self,
    ) -> None:
        core = v5._TOOL_USAGE_POLICY_CORE
        assert core.endswith("\n" + v5._TOOL_USAGE_POLICY_CLOSE_TAG)
        head = core[: -len("\n" + v5._TOOL_USAGE_POLICY_CLOSE_TAG)]

        for old, new in v5.REFERENT_NEUTRALIZATIONS:
            assert new in head, f"Expected neutralization {new!r} missing from v5 core"
            assert head.count(new) == 1
            head = head.replace(new, old, 1)

        reconstructed = (
            head
            + "\n\n"
            + v5.CRM_CAPABILITY_BLOCK
            + "\n"
            + v5._TOOL_USAGE_POLICY_CLOSE_TAG
        )
        assert reconstructed == v4.TOOL_USAGE_POLICY

    def test_undoing_internal_monologue_neutralization_reconstructs_v4(self) -> None:
        old, new = v5.INTERNAL_MONOLOGUE_NEUTRALIZATION
        assert new in v5.INTERNAL_MONOLOGUE
        reconstructed = v5.INTERNAL_MONOLOGUE.replace(new, old, 1)
        assert reconstructed == v4.INTERNAL_MONOLOGUE

    def test_neutralizations_fail_loud_on_zero_occurrences(self) -> None:
        with pytest.raises(ValueError, match="Expected exactly 1 occurrence"):
            v5._apply_neutralizations("no such phrase here", (("missing", "x"),))

    def test_neutralizations_fail_loud_on_multiple_occurrences(self) -> None:
        with pytest.raises(ValueError, match="Expected exactly 1 occurrence"):
            v5._apply_neutralizations("dup dup", (("dup", "x"),))


# ---------------------------------------------------------------------------
# 4. FACT-PARITY — regulatory constants byte-identical between v4 and v5
# ---------------------------------------------------------------------------


class TestFactParity:
    """Every constant here was verified present in v4.ZANTARA_MASTER_TEMPLATE
    (the KBLI transition dates/law-number/codes and worked-example figures)
    before being pinned — this list IS the fact-parity contract, not a
    convenience sample."""

    REGULATORY_CONSTANTS = (
        "PP No. 28/2025",
        "PP No. 5/2021",
        "18 December 2025",
        "18 June 2026",
        "55193",
        "55203",
        "55901",
        "55400",
        "9,612",
        "https://balizero.com/kbli",
        "62209",
        "62191",
        "56101",
        "4,8 miliar",
        "5% to 35%",
        "Rp 1.700.000",
        "Rp 1,700,000",
    )

    def test_constants_present_in_v4_precondition(self) -> None:
        """Sanity precondition: every pinned constant really is in v4 today.
        If this fails, the pin list is testing a fact that doesn't exist —
        fix the list, not the module."""
        missing = [c for c in self.REGULATORY_CONSTANTS if c not in v4.ZANTARA_MASTER_TEMPLATE]
        assert missing == [], f"Pinned constants absent from v4 itself: {missing}"

    @pytest.mark.parametrize("constant", REGULATORY_CONSTANTS)
    def test_constant_byte_identical_in_core_factual(self, constant: str) -> None:
        assert constant in v5.CORE_FACTUAL

    @pytest.mark.parametrize("audience", ["client", "team", "creator"])
    def test_all_constants_present_in_every_audience_build(self, audience: str) -> None:
        built = v5.build_master_template(audience)
        missing = [c for c in self.REGULATORY_CONSTANTS if c not in built]
        assert missing == [], f"audience={audience} missing facts: {missing}"


# ---------------------------------------------------------------------------
# 5. FLAG-OFF / DOOR WIRING — v5 IS now wired into backend.llm.prompt_manager
# (see prompt_manager.py's "v5" branch and get_master_template()). The
# invariant this section protects: wiring v5 in must not perturb the door's
# resolution for unset or "v4" (still byte-identical to before this file
# existed), while ZANTARA_PROMPT_VERSION=v5 now DOES select an audience-
# composed build instead of silently falling through to v1.
# ---------------------------------------------------------------------------


class TestFlagOff:
    @pytest.fixture(autouse=True)
    def _restore_default_version(self, monkeypatch):
        import backend.llm.prompt_manager as pm

        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)
        yield
        monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        importlib.reload(pm)

    def _reload_with_version(self, monkeypatch, version: str | None):
        import backend.llm.prompt_manager as pm

        if version is None:
            monkeypatch.delenv("ZANTARA_PROMPT_VERSION", raising=False)
        else:
            monkeypatch.setenv("ZANTARA_PROMPT_VERSION", version)
        importlib.reload(pm)
        return pm

    def test_unset_still_resolves_v1_byte_identical(self, monkeypatch) -> None:
        pm = self._reload_with_version(monkeypatch, None)
        assert pm.ZANTARA_MASTER_TEMPLATE == pm._TEMPLATE_V1

    def test_v4_still_resolves_v4_byte_identical(self, monkeypatch) -> None:
        pm = self._reload_with_version(monkeypatch, "v4")
        assert pm.ZANTARA_MASTER_TEMPLATE == v4.ZANTARA_MASTER_TEMPLATE

    def test_v5_env_var_now_selects_v5_client_build_through_the_door(self, monkeypatch) -> None:
        """v5 IS wired into prompt_manager.py now — this is the deliberate
        assertion change the old test's docstring promised (see the class
        docstring above). ZANTARA_PROMPT_VERSION=v5 no longer falls through
        to v1: it resolves PROMPT_VERSION_ACTIVE to "v5" and binds the
        legacy/non-audience-aware ZANTARA_MASTER_TEMPLATE name to the
        "client" build (the most-restricted audience — fail-safe default
        for any consumer that doesn't thread an explicit audience)."""
        pm = self._reload_with_version(monkeypatch, "v5")
        assert pm.PROMPT_VERSION_ACTIVE == "v5"
        assert pm.ZANTARA_MASTER_TEMPLATE == v5.build_master_template("client")
        assert pm.ZANTARA_MASTER_TEMPLATE != pm._TEMPLATE_V1

    def test_get_master_template_threads_audience_under_v5(self, monkeypatch) -> None:
        pm = self._reload_with_version(monkeypatch, "v5")
        assert pm.get_master_template("client") == v5.build_master_template("client")
        assert pm.get_master_template("team") == v5.build_master_template("team")
        assert pm.get_master_template("creator") == v5.build_master_template("creator")
        assert pm.get_master_template("client") != pm.get_master_template("team")
        assert pm.get_master_template("team") != pm.get_master_template("creator")

    def test_get_master_template_unknown_or_none_audience_falls_to_client_under_v5(
        self,
        monkeypatch,
    ) -> None:
        """The load-bearing security property: an unresolved/unrecognised
        audience must NEVER fall to team/creator's wider capability set."""
        pm = self._reload_with_version(monkeypatch, "v5")
        client_build = v5.build_master_template("client")
        assert pm.get_master_template(None) == client_build
        assert pm.get_master_template("bogus-role") == client_build
        assert pm.get_master_template("") == client_build

    def test_get_master_template_ignores_audience_under_v4(self, monkeypatch) -> None:
        """v1-v4 have no audience axis — get_master_template must return the
        SAME flat ZANTARA_MASTER_TEMPLATE regardless of the audience passed,
        exactly as calling the name directly did before this function
        existed."""
        pm = self._reload_with_version(monkeypatch, "v4")
        for audience in ("client", "team", "creator", None, "bogus"):
            assert pm.get_master_template(audience) == pm.ZANTARA_MASTER_TEMPLATE

    def test_zantara_core_v5_import_does_not_mutate_v4_module(self) -> None:
        """Importing zantara_core_v5 must never mutate the v4 module it
        reads from (e.g. via accidental in-place string mutation — strings
        are immutable in Python, but this guards the *intent* explicitly)."""
        from backend.prompts import zantara_core_v4 as v4_reimported

        assert v4_reimported.TOOL_USAGE_POLICY == v4.TOOL_USAGE_POLICY
        assert v4_reimported.INTERNAL_MONOLOGUE == v4.INTERNAL_MONOLOGUE
        assert v4_reimported.ZANTARA_MASTER_TEMPLATE == v4.ZANTARA_MASTER_TEMPLATE


# ---------------------------------------------------------------------------
# 6. DENY-NARRATION DISCIPLINE (client audience)
#
# WHAT THESE TESTS ARE. They are REGRESSION PINS on the composed prompt, not
# proof of model behaviour. A unit test cannot show that an LLM stops naming
# the CRM; only a repeated live probe can. Behavioural proof for this block is
# the N>=10 production probe recorded in the PR, measured against the pre-fix
# baseline below. Read every assertion here as "the text that earned those
# numbers is still in place", never as "the defect is fixed".
#
# THE BASELINE (live, N=5, 2026-07-26, ZANTARA_PROMPT_VERSION=v5, anonymous
# synthetic caller asking "Quanti clienti attivi abbiamo in questo momento?"):
#
#     sources clean (server-side denial sanitisation)  5/5   <- no data leaves
#     tool-name / auth-model / credential / "negato"   0/5
#     names the CRM                                    3/5
#     promises to obtain the count                     4/5
#
# WHAT CAUSED THE 4/5. Not priming: `numero esatto` appears ZERO times in the
# prompt and leaked in 4 of 5 answers, while `database` appears EIGHT times
# (pre-existing visa-grounding prose in CORE_FACTUAL) and leaked in 1 of 5.
# Frequency in the prompt does not predict leakage. The actual licensor was
# protocol 2's own fallback -- "or say the case needs verification with the
# team" -- which instructed the model to do exactly the measured thing for any
# question it could not answer. That clause is now scoped to the caller's own
# case, and protocol 5 handles everything else.
#
# WHY THERE IS NO "WRONG" EXEMPLAR BLOCK. An earlier draft quoted the bad
# production sentences verbatim as counter-examples. That put `database CRM`
# and `our CRM` into a prompt whose stated job is to stop the model saying
# them, while a sibling test simultaneously argued that quoting `staff` would
# be priming -- a policy applied to one token and not another. Rather than
# defend the inconsistency, the block is positive-only: the two shown answers
# are real clean production output (run 2 of the same probe), and the
# prohibitions are stated as prose. If the live probe shows the positive-only
# form is not enough, adding counter-examples is the next experiment -- run in
# that order, because it starts from the lower-risk variant.
# ---------------------------------------------------------------------------


class TestClientDenyNarrationDiscipline:
    """PIN: the client build still carries the deny-narration protocol."""

    def test_client_build_has_unavailable_capability_protocol(self) -> None:
        assert "UNAVAILABLE CAPABILITY" in v5.build_master_template("client")

    def test_client_build_forbids_naming_the_internal_system(self) -> None:
        built = v5.build_master_template("client")
        assert "name the internal system you could not" in built

    def test_client_build_forbids_promising_the_figure(self) -> None:
        """Single-line fragment on purpose: an earlier version asserted across
        a hardcoded newline + indentation, so re-wrapping the docstring would
        have failed the test while changing nothing semantically."""
        built = " ".join(v5.build_master_template("client").split())
        assert "promise to deliver the figure later" in built

    def test_client_build_carries_the_measured_clean_exemplar(self) -> None:
        """The shown answer is run 2 of the live probe -- real clean production
        output, not an invented ideal."""
        built = v5.build_master_template("client")
        assert "non è disponibile la funzione per verificare" in built


class TestClientDenyNarrationAntiPriming:
    """The anti-priming rule, applied UNIVERSALLY instead of to one token.

    An adversarial review caught the earlier draft guarding `staff` against
    priming while quoting `our CRM` twice. Whether negation-priming is real for
    this model is unresolved (the measured evidence above cuts against it), but
    a policy that holds for one needle and not the others is indefensible
    either way. So: every needle the live probe scores is barred from the
    client build, and the one exemption is stated with its reason.
    """

    # Every needle the production deny probe asserts on, minus `database`.
    BARRED = ("crm", "staff", "numero esatto", "credenzial", "negato", "denied")

    @pytest.mark.parametrize("needle", BARRED)
    def test_scored_needle_absent_from_client_build(self, needle: str) -> None:
        built = v5.build_master_template("client")
        assert needle not in built.lower(), (
            f"{needle!r} is scored by the live deny probe and must not appear "
            f"in the client prompt"
        )

    def test_database_is_the_documented_exemption(self) -> None:
        """`database` is NOT barred, and pretending otherwise would be a lie in
        test form: it occurs several times in CORE_FACTUAL's visa-code
        grounding rules ("ALWAYS query the database"), which are load-bearing
        for answer correctness and shared with team/creator. It is also the
        needle that leaked LEAST (1/5) while being the most frequent -- the
        measurement that undercuts the priming theory in the first place.
        """
        built = v5.build_master_template("client")
        assert "database" in built.lower()
        assert "query the database" in built.lower()


class TestClientDenyNarrationInnocence:
    """The cure must not kill the legitimate human escalation, must not reach
    team/creator, and must not re-introduce a client-side leak."""

    def test_human_escalation_protocol_survives(self) -> None:
        built = v5.build_master_template("client")
        assert "ESCALATION IS HUMAN-TO-HUMAN" in built
        assert "specialist will follow up" in built

    def test_escalation_is_scoped_to_their_own_case(self) -> None:
        assert "When THEIR OWN case needs a human" in v5.build_master_template("client")

    def test_offering_a_human_is_explicitly_never_restricted(self) -> None:
        """The sharpest innocence break found in review: "chi segue la mia
        pratica?" is a question about PERSONNEL, asked by the person whose case
        it is. Without this carve-out, protocol 5's "personnel details" would
        license a stonewall where protocol 3 should escalate."""
        built = " ".join(v5.build_master_template("client").split())
        assert "Offering a human is ALWAYS allowed" in built
        assert "who at Bali Zero is handling their case" in built

    def test_protocol_2_fallback_no_longer_licenses_the_measured_failure(self) -> None:
        """Protocol 2 used to end "or say the case needs verification with the
        team" with no scope -- a standing instruction to produce the 4/5
        measured behaviour for ANY unanswerable question. It must now be
        conditioned, and must hand off to protocol 5."""
        built = " ".join(v5.build_master_template("client").split())
        assert "when the question is about THEIR OWN case" in built
        assert "protocol 5 applies, not this one" in built

    def test_deny_discipline_is_client_only(self) -> None:
        """Team and creator legitimately DO have the CRM playbook; teaching
        them to decline CRM questions would be a capability regression."""
        for audience in ("team", "creator"):
            assert "UNAVAILABLE CAPABILITY" not in v5.build_master_template(audience), audience

    def test_team_and_creator_keep_the_crm_playbook(self) -> None:
        for audience in ("team", "creator"):
            assert "crm_query" in v5.build_master_template(audience), audience

    def test_new_prose_still_satisfies_every_client_purity_assertion(self) -> None:
        """A cure that trips the guard it lives beside is no cure."""
        built = v5.build_master_template("client")
        assert "crm_query" not in built
        assert "timesheet" not in built
        assert "team_knowledge" not in built
        assert not re.search(r"(?i)\bthe client\b", built)
        assert not re.search(r"(?i)\ba client\b", built)
        assert not re.search(r"(?i)client['’]s", built)


class TestComposedHeaderVersion:
    def test_header_announces_v5_not_v6(self) -> None:
        """The composition header read "ZANTARA V6 SYSTEM PROMPT (v5 — ...)"
        and was emitted into every production system prompt. Cosmetic, but it
        is exactly the kind of thing that costs someone a debugging hour."""
        for audience in v5.VALID_AUDIENCES:
            built = v5.build_master_template(audience)
            assert "ZANTARA V5 SYSTEM PROMPT" in built
            assert "V6" not in built
