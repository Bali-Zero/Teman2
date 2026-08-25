"""render_member_card — the per-turn injection (owner directive #1 §3:
"member card compatta (~200 token) iniettata a ogni turno (stesso pattern
delle entity card CRM)").

**This is the only thing that reaches the model.** Everything else in this
package — the sqlite store, the three model types — stays local
(directive: "la memoria NON va mai al cloud come blob — al modello arriva
solo la card"). `render_member_card` is a pure function: no I/O, no clock
read, no network. Its ONLY inputs are the three typed models from
`models.py`, whose fields are, by construction, incapable of holding a
cleartext client name, phone number, passport/KTP/NPWP number, or chat
text (see `models.py`'s module docstring) — so this function cannot leak
PII by omission the way a free-text template could, because there is no
free-text field anywhere upstream of it to forget to scrub.

Token budget: this codebase has no Qwen-native tokenizer dependency
(`llama.cpp`/Ollama-served, not an OpenAI-compatible tokenizer library —
`tiktoken` would measure the wrong vocabulary; see this module's test file
for the empirical check against the heuristic below). `estimate_tokens`
is therefore a documented, conservative CHARACTER-count heuristic, not an
exact count. The PRIMARY control is structural: `MAX_CARD_EPISODIC_EVENTS`
and `MAX_CARD_PATTERNS` cap how much can ever be selected before rendering,
so the card cannot grow unbounded even if the heuristic is wrong; the
token estimate is the SECONDARY, verifying control, and `render_member_card`
actively trims (drops the oldest episodic event, then the weakest pattern,
in that order) if the structurally-capped render still estimates over
budget.

Author: Claude Sonnet 5 (lane B8 — per-member memory)
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import EpisodicEvent, LearnedPattern, MemberProfile

__all__ = [
    "DEFAULT_MAX_CARD_TOKENS",
    "MAX_CARD_EPISODIC_EVENTS",
    "MAX_CARD_PATTERNS",
    "estimate_tokens",
    "render_member_card",
]

DEFAULT_MAX_CARD_TOKENS = 200
MAX_CARD_EPISODIC_EVENTS = 5
MAX_CARD_PATTERNS = 3

# Conservative: real BPE tokenizers average closer to ~4 chars/token for
# English prose, but this card is ASCII-labels-and-IDs (denser, fewer
# tokens per char) and may render ID/IT/EN mixed content — 3 is a
# deliberately pessimistic (i.e. OVER-estimating) divisor, so a card that
# passes this estimate is very unlikely to exceed the real budget on the
# actual serving stack.
_CHARS_PER_TOKEN_ESTIMATE = 3


def estimate_tokens(text: str) -> int:
    """Ceiling-divide character count by the heuristic divisor. See module
    docstring for why this is an estimate, not a real tokenizer count."""
    if not text:
        return 0
    return -(-len(text) // _CHARS_PER_TOKEN_ESTIMATE)


def _profile_line(profile: MemberProfile | None) -> str:
    if profile is None:
        return "MEMBER: no profile on record"
    hours = (
        f"{profile.working_hours_start}-{profile.working_hours_end}"
        if profile.working_hours_start and profile.working_hours_end
        else "unset"
    )
    return (
        f"MEMBER role={profile.role.value} lang={profile.preferred_language.value} "
        f"fmt={profile.response_format.value} hours={hours}"
    )


def _recent_line(events: Sequence[EpisodicEvent]) -> str | None:
    if not events:
        return None
    items = " ".join(f"{e.target_id}({e.intent_category.value})" for e in events)
    return f"RECENT: {items}"


def _patterns_line(patterns: Sequence[LearnedPattern]) -> str | None:
    if not patterns:
        return None
    items = " ".join(f"{p.pattern_key}(x{p.observation_count})" for p in patterns)
    return f"PATTERNS: {items}"


def render_member_card(
    profile: MemberProfile | None,
    recent_episodic: Sequence[EpisodicEvent],
    patterns: Sequence[LearnedPattern],
    *,
    max_tokens: int = DEFAULT_MAX_CARD_TOKENS,
) -> str:
    """Renders the compact card. `recent_episodic` and `patterns` should
    already be pre-ordered most-relevant-first (that is `store.py`'s
    `list_recent_episodic`/`list_patterns` contract — DESC by recency /
    observation count) — this function trims from the END of each
    sequence when over budget, i.e. drops the LEAST relevant items first.
    """
    events = tuple(recent_episodic)[:MAX_CARD_EPISODIC_EVENTS]
    pats = tuple(patterns)[:MAX_CARD_PATTERNS]

    while True:
        lines = [_profile_line(profile)]
        recent_line = _recent_line(events)
        if recent_line:
            lines.append(recent_line)
        patterns_line = _patterns_line(pats)
        if patterns_line:
            lines.append(patterns_line)
        card = "\n".join(lines)

        if estimate_tokens(card) <= max_tokens or (not events and not pats):
            return card

        # Still over budget: drop the least-relevant item. Patterns are
        # trimmed before episodic events — "what was touched recently"
        # (anaphora resolution, the directive's own worked example) is the
        # layer with an explicit downstream consumer; "learned patterns"
        # is proactivity-only and degrades more gracefully to absent.
        if pats:
            pats = pats[:-1]
        elif events:
            events = events[:-1]
