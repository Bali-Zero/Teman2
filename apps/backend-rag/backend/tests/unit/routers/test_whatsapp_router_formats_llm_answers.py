"""The webhook router must format the model's answer for WhatsApp.

`format_rich_text(text, "whatsapp")` converts generic markdown into what WA
actually renders (`*bold*`, unicode bullets) and drops bare citation markers.
It was armed on 2026-07-25 (#3118) — inside `wa_inbox_bot.py` only.

Measured on `meta_inbox_messages`, the team beta of 2026-07-28: 18 of that
day's 66 bot replies reached a reader carrying raw `[1]`…`[8]`. Deploys run
about ten times a day, so the cure was live; it simply was not on this path.

**How much this actually fixes, measured against those 18 real bodies rather
than assumed:** 6 of 57 markers, and 1 of 18 messages fully cleaned. The other
51 are mid-sentence, and the formatter keeps them deliberately (see
`test_a_mid_sentence_bracket_survives`). Those 18 bodies also carry *zero*
`**bold**`, `##`, bullets, backticks or links — so on that day this cure is
worth 6 markers and some whitespace. It is the right change (this router owes
the same channel contract as every other producer) and it is a small one; the
larger question of whether a mid-sentence RAG source index should survive on
WhatsApp at all is NOT answered here and must not be answered by unanchoring
the regex.

Censused rather than assumed — `format_rich_text` call counts on origin/main:

    wa_inbox_bot.py        3      (formats, but does not insert outbound rows)
    whatsapp_chat.py       0      <- this file: answers the webhook
    wa_inbox.py            0
    wa_outbox_worker.py    0      (sends bodies wa_inbox_bot already formatted)

**Only the model's answer is formatted, never the canned messages this router
also sends** (`welcome_msg`, `escalation_msg`, `ack_text(...)`, `timeout_msg`,
`error_msg`). That is the whole design and the innocence tests below pin it: the
citation strip removes `[<digits>]`, and in a template those digits can be a
reference or invoice number rather than a citation. Formatting at the shared
`whatsapp_service.send_message` chokepoint would have covered all 19 callers and
silently gutted exactly those.

---

**What driving the second branch found — the reason this file is parametrised.**

The cure is two call sites: OpenClaw's answer and the fallback RAG answer. The
first version of this file tested only the first, and a mutation run showed the
second call site could be deleted with nothing turning red. Adding the `rag`
branch did not just close that gap — the branch would not run at all, for two
independent reasons, both live on `origin/main`, neither of which any test had
ever executed:

1. `whatsapp_persona.build_system_prompt` had its `time_of_day` parameter
   renamed to `_time_of_day` on 2026-03-17, against a call site written on
   2026-02-07 that still passes `time_of_day=`. Every fallback reply raised
   `TypeError` (~5 months).
2. `whatsapp_chat.py` called `get_orchestrator(request)` with no `await`,
   though it is `async def` — so the next line met a coroutine and raised
   `AttributeError: 'coroutine' object has no attribute 'process_query'`.

Both land in the same `except Exception`, so the client got
"Ops, errore tecnico 😬 Riprova tra un attimo!" — never the RAG answer. This
branch is the net under OpenClaw failing, and the net had a hole in it.

**Bounded honestly:** the handler persists that error reply to
`conversation_messages`, and it appears **0 times against 154 outbound
WhatsApp messages in July** — so as far as the record shows the branch has
never actually been taken, and no client has yet been hit by this. It was a
latent hole, not an active outage. Both are fixed here because this file
cannot test the second call site without them.

The lesson is not either bug: it is that a keyword mismatch and a missing
`await` are invisible to imports, to linters, and to every test that drives
only the other branch. `test_the_persona_builder_accepts_every_keyword_the_router_passes`
therefore binds the router's ACTUAL keywords against the signature, so the next
rename on either side fails here rather than in production.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROUTER = "backend.app.routers.whatsapp_chat"

_CONTEXT = {
    "_wa_user_id": "whatsapp_6281234567890",
    "_session_id": "wa_session_6281234567890",
    "_existing_row_id": None,
    "client_name": "Test Client",
    "client_profile": {"detected_language": "en"},
    "conversation_history": [],
    "detected_language": "en",
    "is_first_message": False,
    "time_of_day": "afternoon",
}


BRANCHES = ["openclaw", "rag"]


async def _drive(
    model_answer: str,
    *,
    message_text: str = "What is the paid-up capital?",
    via: str = "openclaw",
):
    """Run the webhook handler with the model returning `model_answer`.

    `via` selects WHICH of the two answering branches produces it — and both
    must be driven, because the cure is two call sites and a corpus that
    exercises one of them is half a corpus. Mutation-checked: deleting the
    format call in either branch turns a named test below red.

    - `openclaw`: `ask_openclaw_whatsapp` answers, handler returns at that
      branch's `return` (~line 435).
    - `rag`: OpenClaw returns nothing (its real fallback condition is a falsy
      response), so control falls through to the orchestrator branch.

    Returns the list of texts handed to `whatsapp_service.send_message`.
    """
    from backend.app.routers.whatsapp_chat import process_whatsapp_message
    from backend.services.integrations.whatsapp_triage_service import TriageDecision

    assert via in BRANCHES, via

    triage = MagicMock()
    triage.is_allowed.return_value = True
    triage.should_escalate = AsyncMock(
        return_value=(TriageDecision.BOT_CAN_HANDLE, "business_query")
    )

    wa = MagicMock()
    wa.mark_message_read = AsyncMock()
    wa.send_message = AsyncMock()
    # Identity chunker: this test is about WHAT is sent, not how it is split.
    wa.chunk_message.side_effect = lambda text, max_length: [text]

    onboarding = MagicMock()
    onboarding.detect_and_trigger = AsyncMock(return_value=None)

    orchestrator = MagicMock()
    orchestrator.process_query = AsyncMock(
        return_value=SimpleNamespace(answer=model_answer),
    )

    with (
        patch(f"{ROUTER}.whatsapp_service", wa),
        patch(f"{ROUTER}.whatsapp_triage_service", triage),
        patch(f"{ROUTER}.get_onboarding_detector", return_value=onboarding),
        patch(
            "backend.services.whatsapp_context_builder.build_context",
            new=AsyncMock(return_value=dict(_CONTEXT)),
        ),
        patch(
            f"{ROUTER}.ask_openclaw_whatsapp",
            new=AsyncMock(return_value=model_answer if via == "openclaw" else None),
        ),
        # Imported inside the handler body, so it resolves off the dependencies
        # module at call time — patch it there, not on the router.
        patch("backend.app.dependencies.get_orchestrator", return_value=orchestrator),
        patch(f"{ROUTER}.notify_zero_conversation_log", new=AsyncMock()),
        patch(f"{ROUTER}._save_conversation", new=AsyncMock()),
        patch(f"{ROUTER}._get_db_pool", return_value=None),
    ):
        await process_whatsapp_message(
            phone="6281234567890",
            message_text=message_text,
            sender_name="Test Client",
            message_id="msg_fmt",
            request=MagicMock(),
        )

    return [c.kwargs["text"] for c in wa.send_message.call_args_list]


@pytest.mark.parametrize("via", BRANCHES)
class TestGuiltTheAnswerIsFormatted:
    """Every case runs against BOTH answering branches.

    This router answers from OpenClaw when it responds and from the RAG
    orchestrator when it does not; the cure is one call site in each. Testing
    only the branch that happens to be convenient leaves the other free to
    regress silently — which is exactly what the first version of this file
    did, and a mutation run caught.
    """

    @pytest.mark.asyncio
    async def test_a_trailing_citation_marker_is_stripped(self, via: str) -> None:
        """TRAILING only — and that limit is the formatter's design, not a gap.

        `_BARE_CITATION_RE` is anchored to end-of-text/end-of-line because an
        earlier unanchored version corrupted Indonesian legal citations
        ("Pasal 6 [1] dan [3] berlaku." -> "Pasal 6 dan berlaku."). Measured
        against the 18 real beta-day bodies, routing them through this
        formatter clears 6 of 57 markers and fully cleans 1 of 18 messages:
        the rest are mid-sentence and kept ON PURPOSE. Anyone reading this
        cure as "the markers stop reaching clients" is reading it wrong.
        """
        sent = await _drive("It applies per KBLI and per location [2, 5].", via=via)

        assert sent, "the handler sent nothing — the harness is broken, not the cure"
        body = "\n".join(sent)
        assert "[2, 5]" not in body
        assert "per KBLI and per location" in body, "the citation strip ate the answer"

    @pytest.mark.asyncio
    async def test_a_mid_sentence_bracket_survives(self, via: str) -> None:
        """INNOCENCE, and the reason the anchor exists.

        This is a statute reference, not a RAG source index. A cure that
        "finally removes all those [N]" would delete it and change what the
        law says — the exact regression family #3 already records.
        """
        sent = await _drive("Pasal 6 [1] dan [3] berlaku untuk PT PMA.", via=via)
        body = "\n".join(sent)

        assert "Pasal 6 [1] dan [3] berlaku" in body

    @pytest.mark.asyncio
    async def test_double_asterisk_bold_becomes_whatsapp_bold(self, via: str) -> None:
        sent = await _drive("**Validity:** one year for an investor KITAS.", via=via)
        body = "\n".join(sent)

        assert "**" not in body
        assert "*Validity:*" in body

    @pytest.mark.asyncio
    async def test_markdown_headings_and_bullets_are_converted(self, via: str) -> None:
        sent = await _drive("## Requirements\n\n*   Passport\n*   NPWP", via=via)
        body = "\n".join(sent)

        assert "##" not in body
        assert "*Requirements*" in body
        assert "• Passport" in body
        assert "• NPWP" in body


@pytest.mark.parametrize("via", BRANCHES)
class TestInnocence:
    @pytest.mark.asyncio
    async def test_a_plain_answer_is_delivered_unchanged(self, via: str) -> None:
        plain = "Yes, a PT PMA can be fully foreign-owned in that sector."
        sent = await _drive(plain, via=via)

        assert sent == [plain]

    @pytest.mark.asyncio
    async def test_the_kbli_guard_still_sees_unformatted_text(self, via: str) -> None:
        """Formatting runs AFTER `sanitize_whatsapp_kbli_reply`, so the guard's
        input is byte-for-byte what it reads today. Pinned by driving the
        villa/KBLI correction that the guard exists for: if formatting moved
        ahead of it, the guard would be reading converted text and this
        correction is the first thing that would change."""
        sent = await _drive(
            "55193 - Aktivitas Vila: usa questo per Airbnb.",
            message_text="ma 55193 o 55203?",
            via=via,
        )
        body = "\n".join(sent)

        assert "55203" in body
        assert "usa questo per Airbnb" not in body


def test_the_persona_builder_accepts_every_keyword_the_router_passes() -> None:
    """The two sides must AGREE — checked by binding, not by reading.

    Found by driving the fallback branch for the first time: the router calls
    `build_system_prompt(..., time_of_day=...)` while the function had renamed
    that parameter to `_time_of_day` on 2026-03-17. Result, for ~5 months:
    every fallback-RAG reply died on `TypeError` and the client got
    "Ops, errore tecnico 😬". It survived because nothing executed the line —
    a keyword mismatch is invisible to imports, to type-free call sites, and
    to every test that drives only the other branch.

    This asserts the CLASS, not the instance: it reads whichever keywords the
    router actually passes today and binds them, so the next rename on either
    side fails here instead of in production.
    """
    import ast
    import inspect
    from pathlib import Path

    import backend.app.routers.whatsapp_chat as mod
    from backend.prompts.whatsapp_persona import build_system_prompt

    assert mod.__file__ is not None
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_system_prompt"
    ]
    assert calls, "the router no longer calls build_system_prompt — retarget this guard"

    for call in calls:
        keywords = [kw.arg for kw in call.keywords if kw.arg is not None]
        assert keywords, "call site passes nothing by keyword — unexpected shape"
        # Raises TypeError on any keyword the signature does not accept.
        inspect.signature(build_system_prompt).bind(**dict.fromkeys(keywords))


def test_only_the_answer_is_formatted_never_the_canned_messages() -> None:
    """Guard the guard, by reading the router's SOURCE.

    The cure is deliberately two call sites, not the shared send point. If a
    later edit formats a canned message, the citation strip starts deleting
    `[<digits>]` out of templates — where those digits are a reference number,
    not a citation. This fails the moment `format_rich_text` is applied to
    anything but the two model-answer variables.
    """
    import re
    from pathlib import Path

    import backend.app.routers.whatsapp_chat as mod

    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")

    formatted = re.findall(r"(\w+)\s*=\s*format_rich_text\(", source)
    assert formatted, "no format_rich_text call found — the cure is gone"
    assert set(formatted) <= {"openclaw_response", "response_text"}, (
        f"format_rich_text applied to something other than the model's answer: "
        f"{sorted(set(formatted))}"
    )
