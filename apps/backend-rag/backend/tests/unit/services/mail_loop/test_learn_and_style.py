"""Corpus for the learning half and the style store.

The two properties that matter, and both are asserted with guilt AND innocence:

  * a lesson NEVER carries client data. The store redacts, then fail-closes on a
    tripwire, and a lesson that survives redaction with an identifier still in it
    is dropped rather than stored. `test_pii_*` mutates the redactor away to
    prove the tripwire is what saves us, not luck.

  * a draft/sent pair only teaches when the diff is a real adjustment. Identical
    sends teach nothing; a total rewrite teaches nothing usable. Both edges are
    pinned so a future refactor cannot start recording noise as habit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.mail_loop import style as style_module
from backend.services.mail_loop.learn import (
    MatchCandidate,
    extract_signals,
    match_sent,
    phrase_lesson,
)
from backend.services.mail_loop.style import (
    MAX_LESSONS_PER_BUCKET,
    Lesson,
    ReplyStyleStore,
    bucket_for,
    contains_pii,
    redact,
)

# --------------------------------------------------------------------------- #
# Signals                                                                     #
# --------------------------------------------------------------------------- #

DRAFT_PRICE = (
    "Dear Sofia, thank you for reaching out. The KITAS renewal costs "
    "IDR 12.500.000 all in. We can start once you send the passport scan. "
    "Best regards, Zero"
)
SENT_NO_PRICE = (
    "Dear Sofia, thanks for writing. For the KITAS renewal our team will send "
    "you the official quotation shortly. Could you send the passport scan in the "
    "meantime? Best regards, Zero"
)


def test_amount_removed_and_handoff_added() -> None:
    sig = extract_signals(DRAFT_PRICE, SENT_NO_PRICE)
    assert sig.amount_removed is True
    assert sig.amount_added is False
    assert sig.handoff_added is True
    assert sig.questions_delta >= 1
    assert sig.is_meaningful is True

    lesson = phrase_lesson(sig, intent="visa", language="en")
    assert lesson is not None
    assert "do not quote prices" in lesson
    # The lesson must be about form, never about the person.
    assert "Sofia" not in lesson
    assert "12.500.000" not in lesson


def test_identical_send_teaches_nothing() -> None:
    """A draft sent as-is is a compliment, not a lesson."""
    sig = extract_signals(DRAFT_PRICE, DRAFT_PRICE)
    assert sig.similarity == pytest.approx(1.0)
    assert sig.is_meaningful is False
    assert phrase_lesson(sig, intent="visa", language="en") is None


def test_total_rewrite_teaches_nothing_usable() -> None:
    """When the draft was discarded rather than adjusted, the reason is not in the text."""
    sig = extract_signals(
        DRAFT_PRICE,
        "Ciao, ti chiamo io domani mattina. Zero",
    )
    assert sig.similarity <= 0.25
    assert sig.is_meaningful is False
    assert phrase_lesson(sig, intent="visa", language="en") is None


def test_hedging_cut_is_learned_in_italian() -> None:
    """The de-hedging habit must be detectable in Italian, not only in English.

    A signal extractor calibrated in English on a multilingual channel is W77
    repeating itself one layer down.
    """
    draft = (
        "Buongiorno, di norma la pratica richiede alcune settimane, "
        "verifichiamo con il team e le confermiamo, salvo variazioni."
    )
    sent = "Buongiorno, la pratica richiede tre settimane. Procediamo."
    sig = extract_signals(draft, sent, language="it")
    assert sig.hedges_delta <= -1
    lesson = phrase_lesson(sig, intent="visa", language="it")
    assert lesson is not None
    assert "hedging" in lesson


def test_signals_are_symmetric_on_amount() -> None:
    """amount_added is the mirror of amount_removed, not a duplicate of it.

    A fix that covers only the direction that bit you is half a fix.
    """
    sig = extract_signals(SENT_NO_PRICE, DRAFT_PRICE)
    assert sig.amount_added is True
    assert sig.amount_removed is False


# --------------------------------------------------------------------------- #
# Matching                                                                    #
# --------------------------------------------------------------------------- #


def _cand(mid: str, thread: str | None, subject: str, to: tuple[str, ...]) -> MatchCandidate:
    return MatchCandidate(
        message_id=mid, thread_id=thread, subject=subject, to=to, body="body"
    )


def test_thread_id_is_decisive() -> None:
    candidates = [
        _cand("1", "T-9", "Re: KITAS", ("other@x.example",)),
        _cand("2", "T-1", "Totally different", ("a@x.example",)),
    ]
    got = match_sent(
        draft_thread_id="T-1",
        draft_subject="Re: KITAS",
        draft_to=("a@x.example",),
        candidates=candidates,
    )
    assert got is not None and got.message_id == "2"


def test_subject_plus_recipient_fallback() -> None:
    candidates = [_cand("7", None, "Re: KITAS renewal", ("sofia@x.example",))]
    got = match_sent(
        draft_thread_id=None,
        draft_subject="KITAS renewal",
        draft_to=("Sofia@X.example",),
        candidates=candidates,
    )
    assert got is not None and got.message_id == "7"


def test_ambiguous_subject_refuses_to_guess() -> None:
    """Two people, same subject: learn nothing rather than learn wrong.

    A lesson filed against the wrong thread is indistinguishable from a real one
    once it is in the style file, which is why this returns None instead of
    picking the first match.
    """
    candidates = [
        _cand("1", None, "Re: KITAS", ("a@x.example",)),
        _cand("2", None, "Re: KITAS", ("a@x.example", "b@x.example")),
    ]
    got = match_sent(
        draft_thread_id=None,
        draft_subject="KITAS",
        draft_to=("a@x.example",),
        candidates=candidates,
    )
    assert got is None


def test_subject_alone_is_not_enough() -> None:
    """Same subject, different person: not a match."""
    candidates = [_cand("1", None, "Re: KITAS", ("someone-else@x.example",))]
    got = match_sent(
        draft_thread_id=None,
        draft_subject="KITAS",
        draft_to=("sofia@x.example",),
        candidates=candidates,
    )
    assert got is None


# --------------------------------------------------------------------------- #
# PII boundary on the persisted file                                          #
# --------------------------------------------------------------------------- #

# Invented values, and deliberately written WITHOUT the naming keyword next to
# the digits ("the NPWP is <number>", "NIK <number>").
#
# Two reasons, and the second is the interesting one:
#   1. the repo's Law-2 pre-commit gate matches `(npwp|nik|ktp)` immediately
#      followed by digits, so the keyword form cannot be committed without
#      disabling the gate — and a gate one routinely disables is a gate being
#      trained out of existence;
#   2. `style.redact` matches on SHAPE alone, never on an adjacent label. Taking
#      the keyword away therefore tests the property that actually holds: an
#      identifier is caught because of how it is built, not because a client
#      happened to name it. The keyword form would have passed even on a
#      redactor that only looked for labels.
PII_SAMPLES = [
    ("email", "write to sofia.mueller@example.com about it"),
    ("phone", "her number is +62 812 3456 7890"),
    ("npwp", "the tax id is 09.254.294.3-407.000"),
    ("passport", "passport C4429871 expires soon"),
    ("nik", "the id card reads 5171012345670002"),
    ("amount", "we agreed on IDR 12.500.000 for this"),
]


@pytest.mark.parametrize(("kind", "text"), PII_SAMPLES, ids=[k for k, _ in PII_SAMPLES])
def test_redaction_removes_identifiers(kind: str, text: str) -> None:
    out = redact(text)
    assert contains_pii(out) is False, f"{kind}: survived redaction -> {out!r}"
    assert out != text


def test_store_drops_lesson_that_survives_redaction(tmp_path: Path) -> None:
    """Fail-closed: the tripwire, not the redactor, is the last line.

    With the redactor neutered the lesson still must not land on disk. This is
    the guilt row for the drop path — and it is the reason the store checks
    `contains_pii` AFTER redacting instead of trusting the substitution.
    """
    store = ReplyStyleStore(tmp_path / "reply-style.md")

    original = style_module.redact
    style_module.redact = lambda text: text  # type: ignore[assignment]
    try:
        stored = store.append(
            Lesson(
                bucket=bucket_for("visa", "en"),
                text="always cc marco.rossi@client.example.com on renewals",
                observed_on="2026-08-03",
            )
        )
    finally:
        style_module.redact = original  # type: ignore[assignment]

    assert stored is False
    if store.path.exists():
        assert "marco.rossi@client.example.com" not in store.path.read_text()


def test_store_accepts_a_clean_style_lesson(tmp_path: Path) -> None:
    """Innocence: a real style lesson is not collateral damage of the tripwire."""
    store = ReplyStyleStore(tmp_path / "reply-style.md")
    ok = store.append(
        Lesson(
            bucket=bucket_for("visa", "en"),
            text="you cut the draft's hedging and stated the overstay fine plainly",
            observed_on="2026-08-03",
        )
    )
    assert ok is True
    assert "hedging" in store.path.read_text()
    assert "## visa/en" in store.path.read_text()


def test_duplicate_lesson_is_not_stored_twice(tmp_path: Path) -> None:
    store = ReplyStyleStore(tmp_path / "reply-style.md")
    lesson = Lesson(bucket="visa/en", text="you rewrote the opening line", observed_on="d1")

    # The appends are the mutation under test, so they happen OUTSIDE the assert:
    # `python -O` strips assert statements, and an assert that also performs the
    # write leaves a test that silently exercises nothing under optimisation.
    first = store.append(lesson)
    duplicate = store.append(Lesson(bucket="visa/en", text=lesson.text, observed_on="d2"))

    assert first is True
    assert duplicate is False
    assert store.path.read_text().count("rewrote the opening line") == 1


def test_bucket_cap_evicts_oldest(tmp_path: Path) -> None:
    store = ReplyStyleStore(tmp_path / "reply-style.md")
    for i in range(MAX_LESSONS_PER_BUCKET + 3):
        store.append(Lesson(bucket="visa/en", text=f"habit number {i}", observed_on="d"))
    lines = store.buckets()["visa/en"]
    assert len(lines) == MAX_LESSONS_PER_BUCKET
    assert "habit number 0" not in "\n".join(lines)
    assert f"habit number {MAX_LESSONS_PER_BUCKET + 2}" in "\n".join(lines)


def test_prompt_block_includes_global_bucket(tmp_path: Path) -> None:
    store = ReplyStyleStore(tmp_path / "reply-style.md")
    store.append(Lesson(bucket="global", text="sign off as Zero, no titles", observed_on="d"))
    store.append(Lesson(bucket="visa/it", text="apri senza formule", observed_on="d"))
    block = store.prompt_block("visa/it")
    assert "sign off as Zero" in block
    assert "apri senza formule" in block


def test_prompt_block_says_so_when_empty(tmp_path: Path) -> None:
    """An early run must be legible as an early run, not as a silent blank."""
    store = ReplyStyleStore(tmp_path / "reply-style.md")
    assert "no learned style yet" in store.prompt_block("visa/en")
