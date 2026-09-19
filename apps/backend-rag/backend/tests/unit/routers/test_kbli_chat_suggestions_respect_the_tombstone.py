"""The follow-ups must not invite a question the answer just refused.

PR #6823 taught the chat channel to bury a KBLI-2020 number. Its PROVE-LIVE run
caught what the burial did not reach: `suggested_queries` is built from the match at
the end of the route and knows nothing about the verdict, so the deployed answer said
74100 cannot be registered and then offered "What licenses do I need for KBLI 74100?"
and "Can a foreigner own a KBLI 74100 [KBLI 2020 — tidak ada dalam KBLI 2025]
business?".

Neither line is FALSE, which is why #6823 was not widened to swallow this: the first
is a question, the second is accurate but unreadable — the tombstone suffix is a
TITLE and the builder interpolates it as a noun phrase. What they are is an invitation
back into a dead code, printed under an answer that just closed it.

Detection is on the ENTITY, never on the title text: a buried result is one whose
`risk_category` is `PHANTOM_LICENSING_STATUS`, the field `_tombstone_result` sets.
Matching on the suffix string would be a substring guard over prose — superscar #3 —
and would break the moment the suffix is reworded.

The innocence half is the one that matters most here, because a cure that simply
emptied the list would pass any guilt test written carelessly: a LIVE code must keep
all three of its suggestions, and the two shapes the builder can take (a single result
versus several) must both survive.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import backend.app.routers.kbli_notebook_chat as chat_module
from backend.app.routers.kbli_notebook import _tombstone_result
from backend.services.kbli_catalogue_membership import PHANTOM_LICENSING_STATUS

PHANTOM_CODE = "74100"


def _result(code: str, title: str, *, pma_status: str = "TERBUKA", risk: str = "Menengah Tinggi"):
    r = MagicMock()
    r.code = code
    r.title = title
    r.description = f"{title}."
    r.score = 0.9
    r.pma_status = pma_status
    r.risk_category = risk
    return r


def _buried(code: str = PHANTOM_CODE):
    """A result carried through the REAL tombstone, not a hand-built lookalike."""
    return _tombstone_result(_result(code, "Aktivitas Perancangan Khusus"))


# --------------------------------------------------------------------------
# GUILT — a buried code earns no invitation back into itself
# --------------------------------------------------------------------------


def test_a_buried_code_is_not_offered_a_licensing_question():
    suggestions = chat_module._suggested_queries([_buried()])

    assert not any("licenses do I need" in s for s in suggestions), suggestions


def test_no_suggestion_interpolates_the_tombstone_suffix_into_a_sentence():
    buried = _buried()
    suggestions = chat_module._suggested_queries([buried])

    assert not any("tidak ada dalam KBLI 2025" in s for s in suggestions), suggestions
    assert not any(buried.title in s for s in suggestions), suggestions


def test_a_buried_code_still_gets_help_rather_than_silence():
    """Suppression is not the cure: the reader still needs the way forward.

    Asserted as the EXACT list rather than as `any("KBLI 2025" in s)`. The first
    draft used that looser form and survived the mutation run — because the
    tombstone suffix itself contains the words "KBLI 2025", so the assertion passed
    on the leaked title it was supposed to be ruling out. A test that can be
    satisfied by the defect is not a test.
    """
    suggestions = chat_module._suggested_queries([_buried()])

    assert suggestions == [
        f"Which KBLI 2025 code replaces {PHANTOM_CODE}?",
        "How do I find the right KBLI 2025 code for my activity?",
    ]


def test_burial_is_detected_on_the_entity_not_on_the_title_text():
    """A result whose title merely LOOKS like a tombstone is not one."""
    impostor = _result(
        "56101",
        "Restoran [KBLI 2020 — tidak ada dalam KBLI 2025]",
        risk="Menengah Tinggi",
    )
    suggestions = chat_module._suggested_queries([impostor])

    assert any("licenses do I need for KBLI 56101" in s for s in suggestions), suggestions


def test_the_buried_top_governs_even_when_a_live_code_follows_it():
    suggestions = chat_module._suggested_queries(
        [_buried(), _result("74115", "Desain Elektronika")]
    )

    assert not any("licenses do I need" in s for s in suggestions), suggestions


# --------------------------------------------------------------------------
# INNOCENCE — a live code keeps every suggestion it had
# --------------------------------------------------------------------------


def test_a_live_code_alone_keeps_its_three_suggestions():
    top = _result("56101", "Restoran")
    suggestions = chat_module._suggested_queries([top])

    assert suggestions == [
        "What licenses do I need for KBLI 56101?",
        "Is Restoran open to foreign investors?",
        "What are the risk requirements for KBLI 56101?",
    ]


def test_a_live_code_with_a_sibling_keeps_the_comparison_suggestion():
    suggestions = chat_module._suggested_queries(
        [_result("56101", "Restoran"), _result("56102", "Rumah Makan")],
    )

    assert suggestions == [
        "What licenses do I need for KBLI 56101?",
        "Is Restoran open to foreign investors?",
        "What's the difference between KBLI 56101 and 56102?",
    ]


@pytest.mark.parametrize("pma_status", ["NOT_VERIFIED", "", None])
def test_an_unverified_pma_status_still_takes_the_ownership_phrasing(pma_status):
    """The pre-existing fork on `pma_status` is untouched by this cure."""
    suggestions = chat_module._suggested_queries(
        [_result("56101", "Restoran", pma_status=pma_status)]
    )

    assert "Can a foreigner own a Restoran business?" in suggestions


def test_no_results_produces_no_suggestions():
    assert chat_module._suggested_queries([]) == []


def test_the_phantom_status_constant_is_the_one_the_tombstone_writes():
    """Innocence for every guilt test: they must key on the REAL marker."""
    assert _buried().risk_category == PHANTOM_LICENSING_STATUS
