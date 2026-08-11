"""Guilt + innocence corpus for the casual-conversation gate (superscar #3).

`SystemPromptBuilder.check_casual_conversation` decides whether a WhatsApp
message is chit-chat. When it says yes, `get_casual_response` answers with a
canned line ("Got it! 😊 If you have questions about visas, business, or life
in Indonesia, I'm here to help!") and the message never reaches retrieval,
tools, or the human-escalation path.

Measured live on 2026-08-11 against 20 sentences a Bali Zero client actually
writes: **17 were classified as chit-chat**. The same brush-off is what the
2026-07-28 team beta recorded four times in a row for Krisna's LKPM question,
which read as stonewalling.

The costs are asymmetric and that is what the two-tier design encodes: a
message wrongly sent to retrieval costs a few seconds; a message wrongly
brushed off stonewalls a paying client. So a marker that has a twin in
ordinary business language may never decide on its own.
"""

from __future__ import annotations

import pytest

from backend.services.rag.agentic import prompt_builder
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> SystemPromptBuilder:
    # The predicate is pure w.r.t. instance state — no cache, no LLM, no I/O.
    #
    # `COMPANY_NAME` must be a real string: the business-keyword list contains
    # `settings.COMPANY_NAME.lower()`, and under this suite `settings` is a
    # MagicMock, so `keyword in query_lower` raises TypeError for every message
    # that does NOT match an earlier business keyword — i.e. for all the small
    # talk this file asserts. Prod is unaffected (settings is real there), but
    # without this line the guilt half of the corpus errors instead of running.
    monkeypatch.setattr(prompt_builder.settings, "COMPANY_NAME", "Bali Zero", raising=False)
    return SystemPromptBuilder.__new__(SystemPromptBuilder)


# --------------------------------------------------------------------------
# INNOCENCE — a real client message must never be answered with the brush-off.
# Every string below was DIVERTED by the pre-cure guard; the token that did it
# is named so a future reader can tell which defect a regression revived.
# --------------------------------------------------------------------------

CLIENT_MESSAGES_NOT_CHITCHAT = [
    # substring: `bar` inside kabar / sabar / gambar / lembar
    ("Halo, sudah dua minggu belum ada kabar soal dokumen saya", "bar⊂kabar"),
    ("Saya sudah sabar menunggu, tapi ini terlalu lama", "bar⊂sabar"),
    ("Saya kirim gambar paspor lewat sini ya", "bar⊂gambar"),
    ("Tolong kirim lembar tanda terima", "bar⊂lembar"),
    ("Mohon kabari saya kalau sudah selesai", "bar⊂kabari"),
    # substring: `oggi` inside soggiorno
    ("Quanto tempo ci vuole per il permesso di soggiorno?", "oggi⊂soggiorno + tempo"),
    # homograph: Italian `tempo` is time far more often than weather here
    ("Ho poco tempo, si puo accelerare la pratica?", "tempo"),
    # time words that mark urgency, not small talk
    ("Please send me the invoice today", "today"),
    ("Ho bisogno di una risposta oggi", "oggi"),
    ("Bisakah dikirim hari ini?", "hari ini"),
    ("Saya lagi tunggu dokumen dari kantor", "lagi"),
    # preference words: on a consultancy number these ARE the business talk
    ("I would like to proceed with the application", "like"),
    ("What is the best option for me?", "best"),
    ("Qual e l'opzione migliore per la mia situazione?", "migliore"),
    ("Could you recommend which route to take?", "recommend"),
    # mood used as a COMPLAINT — the one message that most needs a human
    ("Sono stanco di aspettare, quando arriva il documento?", "stanco + richiesta"),
    ("Saya kesel karena sudah lama tidak ada jawaban", "kesel + richiesta"),
]


@pytest.mark.parametrize(
    ("message", "token"),
    CLIENT_MESSAGES_NOT_CHITCHAT,
    ids=[t for _, t in CLIENT_MESSAGES_NOT_CHITCHAT],
)
def test_innocence_client_message_is_not_chitchat(
    gate: SystemPromptBuilder, message: str, token: str
) -> None:
    assert gate.check_casual_conversation(message) is False, (
        f"routed to the canned brush-off via `{token}` — this is a client "
        f"asking for service: {message!r}"
    )


def test_innocence_the_furious_complaint_reaches_the_real_pipeline(
    gate: SystemPromptBuilder,
) -> None:
    """The live case that opened this cure (measured 4/4 deterministic).

    An angry Indonesian message got `steps=0 tools_called=0 ctx=0 ev=1.0` and
    the canned reply, because `bar` matched inside `kabar`.
    """
    angry = (
        "Saya sudah bayar dua bulan lalu dan sampai sekarang belum ada kabar "
        "sama sekali. Ini bagaimana?"
    )
    assert gate.check_casual_conversation(angry) is False


# --------------------------------------------------------------------------
# GUILT — genuine small talk must still be recognised, or the cure has simply
# deleted the feature. `Suka musik apa?` used to be caught by the preference
# word `suka`; it now lands on `musik`, which this cure ADDED.
# --------------------------------------------------------------------------

REAL_SMALL_TALK = [
    "apa kabar?",
    "Come stai oggi?",
    "How are you doing?",
    "Ada rekomendasi restaurant enak di Canggu?",
    "Any good warung nearby?",
    "gabut nih, ada saran musik?",
    "hari ini cuaca gimana?",
    "What's the weather like in Bali?",
    "Do you like Indonesian food?",
    "Suka musik apa?",
    "thanks",
    "grazie",
]


@pytest.mark.parametrize("message", REAL_SMALL_TALK)
def test_guilt_small_talk_is_still_recognised(
    gate: SystemPromptBuilder, message: str
) -> None:
    assert gate.check_casual_conversation(message) is True, (
        f"small talk lost — it will now burn a retrieval and may end in an "
        f"abstain, which on WhatsApp is silence: {message!r}"
    )


def test_guilt_a_bare_mood_message_is_still_casual(gate: SystemPromptBuilder) -> None:
    """The mood tier must survive the cure, not be deleted by it.

    Without this the obvious over-correction — drop every word that has a
    business twin — passes every innocence case above while quietly making
    "capek banget" go to retrieval, abstain, and (on WhatsApp) silence.
    """
    assert gate.check_casual_conversation("capek banget") is True
    assert gate.check_casual_conversation("Sono stanco, che noia") is True


def test_guilt_mood_plus_service_request_is_business_not_mood(
    gate: SystemPromptBuilder,
) -> None:
    """Same mood word, opposite verdict — the tier is doing the deciding.

    Pins the W115 shape: the weak lane steps aside when the message also asks
    for something. If this passes while the pair above fails, the mood tier
    was removed rather than demoted.
    """
    assert gate.check_casual_conversation("capek banget") is True
    assert gate.check_casual_conversation("capek banget nunggu dokumen saya") is False


def test_business_keyword_shortcut_still_wins(gate: SystemPromptBuilder) -> None:
    """Innocence for the pre-existing guard this cure sits behind."""
    assert gate.check_casual_conversation("Berapa harga KITAS?") is False
    assert gate.check_casual_conversation("Requisiti E33G?") is False
