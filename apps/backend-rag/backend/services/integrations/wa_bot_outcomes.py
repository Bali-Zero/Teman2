"""Outcome types shared by the WhatsApp reply generator and the outbox worker.

The worker treats ``bot_generate_fn`` as an opaque injected callable and must
not import the generator (that coupling is what keeps the worker testable with
plain fakes). Both sides import THIS module instead.

Why it exists — measured, not theoretical. On 2026-07-27 every give-up ever
recorded in ``meta_inbox_messages.error`` was classified. Of 52 rows, **44** say
``wa-inbox bot auto-reply not enabled in v1`` and 5 say ``no customer message in
thread <n>``. The bot was simply switched off for two weeks in June, and the
ledger recorded every one of those messages under the same sentinel as a genuine
crash: ``bot_generate_failed_after_5_attempts``. Reading the ledger, two weeks of
"the bot is off" and a real RAG outage are indistinguishable.

That is a DIAGNOSTIC defect, and this class fixes exactly that: it marks the
failure as a standing condition of the system's configuration or state, so the
ledger can say which of the two happened.

What this class deliberately does NOT do (an adversarial review killed the first
version, which did all three):

* It does **not** skip the retry ladder. ``WA_INBOX_BOT_AUTOREPLY`` is read from
  the environment on every call, so a rollout that flips it ON mid-backoff can
  still rescue the row — a real recovery path, and ~7 minutes is well inside a
  reasonable WhatsApp reply window.
* It is **not** called "permanent". Neither condition is: the flag is mutable,
  and "no customer message" means "none in the last 13 records"
  (``_HISTORY_TURNS + 1``), which is a window artifact rather than a statement
  about the thread.
* It does **not** justify itself on cost. The flag check is the FIRST statement
  of ``generate_bot_reply``, before ``_load_thread_context`` and before any RAG
  call, so those 44 rows burned zero generations — five cheap no-ops, not five
  LLM round-trips. An earlier draft of this docstring claimed otherwise.

NOT for an ABSTAIN either. A refusal is a SUCCESSFUL send with truthful content
and belongs on the return path — see task #31.
"""

from __future__ import annotations

__all__ = ["BotStandingCondition"]


class BotStandingCondition(RuntimeError):
    """The generator declined because of system state, not a failed attempt.

    Raised when auto-reply is switched off, or when the thread window holds no
    customer message to answer. The worker retries and eventually parks the row
    exactly as before; the only thing that changes is the text written to the
    ledger, so "the bot was off" stops being spelled the same way as "the RAG
    crashed".

    Deliberately a ``RuntimeError`` subclass: every existing broad ``except
    Exception`` / ``except RuntimeError`` handler keeps catching it unchanged,
    so introducing it cannot silently alter any path that has not opted in.
    """
