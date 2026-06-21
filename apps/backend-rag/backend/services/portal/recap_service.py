"""
Portal AI Recap — facts-locked, prose-polished (FASE 3, blueprint §3.5).

The "highly AI-smart with recaps" promise, built SAFELY for a legal/immigration
service. The hard constraint (DeepSeek red-team AP3 "hallucinated lawyer"): a
recap that invents a visa deadline → overstay → deportation → liability. So:

  1. FACTS are composed DETERMINISTICALLY from already-audited structured fields
     (open_actions, upcoming_deadlines, unread) — no LLM touches the numbers/dates.
  2. An OPTIONAL local-Ollama pass only POLISHES the tone (warmer, natural), with
     an explicit guardrail "do not change any number, date, name, or status".
  3. If Ollama is unavailable (e.g. on Fly — Ollama is local-only) OR the polished
     text drifts from the facts, we FALL BACK to the deterministic text.

No client PII ever leaves the machine: the polish runs on local Ollama only;
there is no cloud fallback for the recap (unlike RAG chat). On Fly the recap is
always the deterministic text. A permanent disclaimer is attached by the caller.
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

DISCLAIMER = (
    "AI summary of your Bali Zero records — not legal advice. "
    "Always confirm with your case officer."
)

# Numeric/date tokens we require the polished text to preserve verbatim.
_NUM_RE = re.compile(r"\d+")


def build_deterministic_recap(
    *,
    open_actions: list[dict[str, Any]],
    upcoming_deadlines: list[dict[str, Any]],
    unread_messages: int,
    client_name: str | None = None,
) -> str:
    """
    Compose the recap sentence(s) from audited structured fields ONLY.
    This is the source of truth — every number/date here is already verified
    upstream (portal_dashboard._fetch_*). Returns plain text.
    """
    greeting = f"Welcome back{', ' + client_name.split()[0] if client_name else ''}."
    parts: list[str] = []

    n_actions = len(open_actions)
    if n_actions == 0:
        parts.append("Nothing needs your attention right now — we're on it.")
    elif n_actions == 1:
        label = open_actions[0].get("title") or open_actions[0].get("label") or "one item"
        parts.append(f"There is 1 thing that needs you: {label}.")
    else:
        first = open_actions[0].get("title") or open_actions[0].get("label") or "an item"
        parts.append(
            f"There are {n_actions} things that need you — starting with {first}."
        )

    if upcoming_deadlines:
        d = upcoming_deadlines[0]
        label = d.get("label") or d.get("title") or "A deadline"
        days = d.get("days_until")
        if isinstance(days, int):
            when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            parts.append(f"Next deadline: {label} {when}.")
        else:
            due = d.get("due_date")
            parts.append(f"Next deadline: {label}{f' on {due}' if due else ''}.")

    if unread_messages > 0:
        parts.append(
            f"You have {unread_messages} unread message"
            f"{'s' if unread_messages != 1 else ''} from the team."
        )

    return f"{greeting} " + " ".join(parts)


def _facts_preserved(deterministic: str, polished: str) -> bool:
    """
    Guardrail: the polished text must preserve every number from the
    deterministic (factual) text. If a digit was added, dropped, or changed,
    we reject the polish and fall back. (Cheap, language-agnostic, catches the
    'hallucinated a different deadline' failure mode.)
    """
    det_nums = sorted(_NUM_RE.findall(deterministic))
    pol_nums = sorted(_NUM_RE.findall(polished))
    return det_nums == pol_nums


async def polish_recap(deterministic: str) -> str:
    """
    Optional local-Ollama style pass. Returns the polished text ONLY if it
    preserves all facts; otherwise returns the deterministic text unchanged.
    Any error (Ollama down, timeout, on Fly) → deterministic fallback.
    """
    try:
        from backend.llm.ollama_client import MODEL_FAST, ollama_generate
    except Exception:  # pragma: no cover - import guard
        return deterministic

    prompt = (
        "Rewrite the following client portal status update in a warm, calm, "
        "concise voice for a foreign client relocating to Bali. "
        "STRICT RULES: do NOT change, add, or remove any number, date, count, "
        "name, or status. Keep it to 2-3 short sentences. Output only the "
        "rewritten text, nothing else.\n\n"
        f"TEXT:\n{deterministic}"
    )
    try:
        polished = await ollama_generate(prompt=prompt, model=MODEL_FAST, timeout=12)
    except Exception as e:  # Ollama unavailable (e.g. Fly), timeout, etc.
        logger.info("recap polish unavailable, using deterministic: %s", e)
        return deterministic

    if not polished or not polished.strip():
        return deterministic

    polished = polished.strip()
    if not _facts_preserved(deterministic, polished):
        logger.warning("recap polish altered facts — falling back to deterministic")
        return deterministic

    return polished


async def build_recap(
    *,
    open_actions: list[dict[str, Any]],
    upcoming_deadlines: list[dict[str, Any]],
    unread_messages: int,
    client_name: str | None = None,
    polish: bool = True,
) -> dict[str, Any]:
    """
    Build the full recap object for the portal dashboard.

    Returns:
        {
          "text": <facts-locked, optionally prose-polished>,
          "polished": <bool — whether the LLM pass was applied>,
          "disclaimer": <permanent legal disclaimer>,
        }
    """
    deterministic = build_deterministic_recap(
        open_actions=open_actions,
        upcoming_deadlines=upcoming_deadlines,
        unread_messages=unread_messages,
        client_name=client_name,
    )
    text = deterministic
    polished_applied = False
    if polish:
        text = await polish_recap(deterministic)
        polished_applied = text != deterministic

    return {
        "text": text,
        "polished": polished_applied,
        "disclaimer": DISCLAIMER,
    }
