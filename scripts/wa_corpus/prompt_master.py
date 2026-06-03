"""The fixed 6-section grounded prompt-master + a recap structure validator.

Tested manually during the pilot (session report §PROMPT-MASTER). Every section
MUST include a verbatim citation or the literal 'not mentioned'. Output ENGLISH,
max ~2000 chars.
"""
from __future__ import annotations

REQUIRED_SECTIONS = (
    "DEADLINES",
    "PAYMENTS",
    "DOCUMENTS & CASES",
    "PENDING ACTIONS",
    "RISKS & URGENCIES",
    "RELATIONSHIP STATUS",
)

PROMPT_MASTER = """You are reviewing one WhatsApp conversation between a Bali Zero \
team member and a single client. Produce a concise status recap STRICTLY grounded \
in the source. Output in ENGLISH, max 2000 characters.

For EACH of the following six sections, give the current state. For every claim you \
MUST quote the exact verbatim text from the source that supports it (cited_text). \
If a section has nothing in the source, write exactly "not mentioned" — never guess, \
never infer beyond the text.

## DEADLINES
(visa/KITAS/permit/tax dates, appointments)
## PAYMENTS
(amounts owed, paid, pending invoices)
## DOCUMENTS & CASES
(documents requested/received, case/practice references)
## PENDING ACTIONS
(what the team or client still needs to do)
## RISKS & URGENCIES
(complaints, blockers, time-critical items)
## RELATIONSHIP STATUS
(tone, satisfaction, last contact)

Do not include information about any person other than this one client. If the \
conversation appears to involve many different clients, say so in RELATIONSHIP \
STATUS and stop."""


def recap_is_valid(recap: str) -> bool:
    """Structural check: all six section headers present in the recap text."""
    upper = recap.upper()
    return all(sec in upper for sec in REQUIRED_SECTIONS)
