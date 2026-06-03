"""Classify a WhatsApp counterpart into one of the real categories.

Decision hierarchy (order matters — earlier wins):
  1. GROUP        — chat_type='group' (multi-party room). Excluded in v1.
  2. INTERNAL     — team member (roster contact_type='team' OR is a team line).
                    Team beats client: a teammate who is also in `clients` is
                    still INTERNAL (e.g. Lia is team=True AND crm=True).
  3. MULTI_CLIENT — operational channel: high volume + many distinct names.
  4. CLIENT       — already in the CRM (`clients` match) OR explicit client type.
  5. PROSPECT     — external person NOT yet in the CRM, normal 1-a-1 volume.
  6. REVIEW       — ambiguous; a human decides.

PROSPECT and CLIENT are both loaded into the NB (both are real people with a
chat worth recapping); the distinction tells the recap consumer whether the
person is already a paying client or a lead. Only INTERNAL/GROUP/MULTI_CLIENT
are excluded in v1.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

from scripts.wa_corpus.config import (
    EXCLUDED_CONTACT_TYPES,
    MULTI_CLIENT_MIN_DISTINCT_NAMES,
    MULTI_CLIENT_MIN_MSGS,
)

_CLIENT_TYPES = frozenset({"client", "client_visa"})


class Verdict(enum.Enum):
    CLIENT = "client"              # already in CRM — load, recap into client profile
    PROSPECT = "prospect"          # external, NOT in CRM — load, recap as lead
    INTERNAL = "internal"          # team/partner — exclude
    GROUP = "group"                # group chat — exclude in v1
    MULTI_CLIENT = "multi_client"  # operational channel — exclude in v1
    REVIEW = "review"              # ambiguous — human decides


@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    reason: str

    @property
    def loadable(self) -> bool:
        """Whether this counterpart should get a Doc + recap in v1."""
        return self.verdict in (Verdict.CLIENT, Verdict.PROSPECT)


class CounterpartClassifier:
    def classify(
        self,
        *,
        contact_type: str | None,
        n_msgs: int,
        n_distinct_names: int,
        chat_type: str = "direct",
        is_team_member: bool = False,
        in_crm: bool = False,
    ) -> Classification:
        ct = (contact_type or "").strip().lower()

        # 1. Group chat — multi-party, never a single-client profile.
        if (chat_type or "").strip().lower() == "group":
            return Classification(Verdict.GROUP, "chat_type=group (multi-party)")

        # 2. Team beats everything else. Roster signal OR known team line OR
        #    contact_type in the excluded set (team/partner).
        if is_team_member or ct in EXCLUDED_CONTACT_TYPES:
            why = "is_team_member" if is_team_member else f"contact_type={ct}"
            return Classification(Verdict.INTERNAL, f"internal: {why}")

        # 3. Operational channel: high volume + many distinct client names.
        high_vol = n_msgs >= MULTI_CLIENT_MIN_MSGS
        many_names = n_distinct_names >= MULTI_CLIENT_MIN_DISTINCT_NAMES
        if high_vol and many_names:
            return Classification(
                Verdict.MULTI_CLIENT,
                f"high volume ({n_msgs} msgs) + {n_distinct_names} distinct names",
            )

        # 4. Already a client (CRM match or explicit client contact_type).
        if in_crm or ct in _CLIENT_TYPES:
            why = "in CRM" if in_crm else f"contact_type={ct}"
            return Classification(Verdict.CLIENT, f"client: {why}")

        # 5/6. External, not in CRM. Normal 1-a-1 volume -> prospect; one stray
        #      high-signal -> review.
        if not high_vol and not many_names:
            return Classification(
                Verdict.PROSPECT,
                f"external not-in-CRM, {n_msgs} msgs, {n_distinct_names} name(s) -> lead",
            )
        return Classification(
            Verdict.REVIEW,
            f"ambiguous: {n_msgs} msgs, {n_distinct_names} distinct names",
        )
