"""Classify a WhatsApp counterpart: client / internal / multi-client / review.

Exclusion-first (F3): contact_type in EXCLUDED_CONTACT_TYPES is never a client.
For the rest, contact_type in {client, client_visa} is a positive signal; the
large 'contact'/'linked'/None bucket is split by volume + distinct-name count.
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
    CLIENT = "client"              # load into NB, recap valid
    INTERNAL = "internal"          # team/partner/group — exclude
    MULTI_CLIENT = "multi_client"  # operational channel — exclude in v1
    REVIEW = "review"              # ambiguous — human decides


@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    reason: str


class CounterpartClassifier:
    def classify(
        self,
        *,
        contact_type: str | None,
        n_msgs: int,
        n_distinct_names: int,
    ) -> Classification:
        ct = (contact_type or "").strip().lower()

        if ct in EXCLUDED_CONTACT_TYPES:
            return Classification(Verdict.INTERNAL, f"contact_type={ct} excluded")

        if ct in _CLIENT_TYPES:
            return Classification(Verdict.CLIENT, f"contact_type={ct} explicit client")

        # Unclassified bucket: contact / linked / None.
        high_vol = n_msgs >= MULTI_CLIENT_MIN_MSGS
        many_names = n_distinct_names >= MULTI_CLIENT_MIN_DISTINCT_NAMES

        if high_vol and many_names:
            return Classification(
                Verdict.MULTI_CLIENT,
                f"high volume ({n_msgs} msgs) + {n_distinct_names} distinct names",
            )
        if not high_vol and not many_names:
            return Classification(
                Verdict.CLIENT,
                f"low volume ({n_msgs} msgs), {n_distinct_names} name(s) -> 1-a-1",
            )
        # Exactly one signal fired -> ambiguous.
        return Classification(
            Verdict.REVIEW,
            f"ambiguous: {n_msgs} msgs, {n_distinct_names} distinct names",
        )
