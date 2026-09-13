"""The pre-ingest gate that stops the corpus teaching the price split.

Every string below is REAL corpus text, copied from the live `curated_qa`
collection on 2026-09-03. They are corpus, not client data — no PII.

The guilt set is the nine rows the FACT-scan found offending. The innocence
set is the model answers: rows that name a government fee and deliberately
refuse to quote a figure. Both halves are load-bearing — a gate that refuses
the whole 50-row government-fee population would take the good answers with
the bad, and the good ones are the behaviour the ruling wants.
"""

from __future__ import annotations

import pytest

from backend.services.misc.curated_qa_government_fee_detector import (
    REVIEW_FLAG_FIELD,
    REVIEW_NOTE_FIELD,
    row_is_refused,
    scan_government_fee,
)

# --- GUILT: the nine offenders, verbatim from the live collection ----------

OFFENDERS: dict[str, str] = {
    # 57deb254 — answers "how much does the Investor KITAS cost" with the
    # government fee ONLY. Cycle 359 Q11.
    "e28a_q5": (
        "The government fee (PNBP) totals Rp 7,000,000 for a 1-year Investor "
        "KITAS, or Rp 9,500,000 for 2 years — both cover the visa, the ITAS, "
        "the bundled re-entry permit, and the verification fee."
    ),
    # 59da08d9 — the split as written DOCTRINE. This is the one the earlier
    # phrase-based sweep missed (it looked for "we always show the two figures
    # separately"; the corpus says "keep these two costs distinct"). W82.
    "e28a_q6": (
        "No — the PNBP figures (Rp 7,000,000 for 1 year, Rp 9,500,000 for 2 "
        "years) are the Indonesian government's own visa and stay-permit fees; "
        "they are not Bali Zero's service fee. Our fee is separate and quoted "
        "individually by our team. We always keep these two costs distinct so "
        "you know exactly what's going to the government and what's going to us."
    ),
    # 8b520434
    "e33e_q13": (
        "The official government fee (PNBP) to issue an E33E totals "
        "Rp 13,000,000, broken down as: visa Rp 500,000 + verification "
        "Rp 2,000,000 + ITAS Rp 7,000,000 + re-entry permit Rp 3,500,000. "
        "This is the government fee only — it does not include Bali Zero's "
        "service fee, which we quote separately."
    ),
    # eacec21f — a bare PNBP figure volunteered inside an ELIGIBILITY answer.
    "final_q11": (
        "Government fee (PNBP): Rp 12,000,000 for 5 years, Rp 18,500,000 for "
        "10 years. The investment commitment is at least USD 30,000."
    ),
    # 8ebf681f
    "final_q13": (
        "All three KITAP routes share the same official government fee (PNBP) "
        "structure, tiered by validity period: roughly Rp 7,000,000 for the "
        "standard 5-year ITAP, a Rp 12,000,000 tier, and a Rp 15,000,000 tier."
    ),
    # The four this gate found that the corner had not yet named.
    "finalv2_q8": (
        "Official government PNBP fees for ITAP were revised under PP 45/2024 "
        "and are tiered by validity period: roughly Rp 7,000,000 for a 5-year."
    ),
    "c1_q19": (
        "The government issuance fee (PNBP) for the C1 is Rp 1,000,000, "
        "covering the initial 60-day stay — this is a fixed, official figure."
    ),
    "kitap_q7": (
        "Under the current official fee schedule (PP 45/2024), the government "
        "tariff (PNBP) for an ITAP is Rp 7,000,000 for the 5-year duration."
    ),
    "finalv2_q12": (
        "For the Golden Visa family, the official government PNBP structure is: "
        "IDR 13,000,000 total for the 5-year tier (residence permit "
        "IDR 7,000,000 + visa IDR 500,000 + verification IDR 2,000,000)."
    ),
}

# --- INNOCENCE: the model answers, also verbatim -------------------------

COMPLIANT_NO_FIGURE: dict[str, str] = {
    "defers_to_the_team": (
        "The government fee (PNBP) is set by immigration, varies by code and "
        "by how many years you choose, and can change over time — so rather "
        "than quote a figure that may age, ask our team for the current one."
    ),
    "d12_defers": (
        "The government fee (PNBP) for a D12 depends on whether you choose the "
        "1-year or 2-year validity, and it is set by immigration and can "
        "change over time."
    ),
    "non_refundable": (
        "Government fees (PNBP) paid to Indonesian Immigration are, in "
        "practice, treated as non-refundable once your application has been "
        "reviewed and a decision issued."
    ),
    "reentry_bundled": (
        "Yes — you can travel in and out of Indonesia during your Investor "
        "KITAS's validity. A re-entry permit is bundled directly into your "
        "permit, and its government fee is part of what you already paid."
    ),
}

NO_GOVERNMENT_FEE_AT_ALL: dict[str, str] = {
    "our_price": "Bali Zero quotes the Investor KITAS at Rp 20.000.000, all inclusive.",
    "no_money": "An Investor KITAS is granted for either 1 or 2 years, at your choice.",
    "empty": "",
}


class TestGuilt:
    @pytest.mark.parametrize("name", sorted(OFFENDERS))
    def test_every_known_offender_is_refused(self, name: str) -> None:
        """Recall measured at 9 of 9 against the live collection, 2026-09-03."""
        refusal = row_is_refused({"answer": OFFENDERS[name]})
        assert refusal is not None, f"{name} states a government-fee figure and must be refused"
        assert "all-inclusive" in refusal, "the refusal must name the ruling it enforces"

    def test_the_doctrine_row_is_caught_by_the_FACT_not_the_phrasing(self) -> None:
        """W82. The predecessor sweep searched "we always show the two figures
        separately" and missed "We always keep these two costs distinct" — the
        same teaching, different words. Rewording must not buy an escape."""
        for reworded in (
            "We always keep these two costs distinct: PNBP Rp 9,500,000 is the "
            "government's, our service fee is ours.",
            "Teniamo sempre separate le due voci: la tassa governativa è "
            "Rp 9.500.000, il nostro onorario è a parte.",
            "Kami selalu memisahkan dua biaya ini: biaya pemerintah "
            "Rp 9.500.000 dan jasa kami terpisah.",
        ):
            assert row_is_refused({"answer": reworded}) is not None, reworded


class TestInnocence:
    @pytest.mark.parametrize("name", sorted(COMPLIANT_NO_FIGURE))
    def test_naming_a_government_fee_without_a_figure_passes(self, name: str) -> None:
        """These are the answers the ruling WANTS: they explain that a
        government charge exists and refuse to quote it. 27 of the 50
        government-fee rows in the live collection are this shape."""
        text = COMPLIANT_NO_FIGURE[name]
        assert scan_government_fee(text) is not None, "the token IS present"
        assert row_is_refused({"answer": text}) is None, "but no figure — must pass"

    @pytest.mark.parametrize("name", sorted(NO_GOVERNMENT_FEE_AT_ALL))
    def test_a_row_that_names_no_government_fee_is_never_touched(self, name: str) -> None:
        """758 of 808. Our own all-inclusive price is not a government fee."""
        text = NO_GOVERNMENT_FEE_AT_ALL[name]
        assert scan_government_fee(text) is None
        assert row_is_refused({"answer": text}) is None


class TestTheReviewMarker:
    """The escape hatch for the 17 compliant rows that DO name a figure.

    No lexical rule separates "the government charges X, we charge Y" from
    "our X already includes the government charge" — a proximity rule was
    calibrated against the nine offenders and rejected on its numbers (at
    every window from 40 to 160 chars it caught at most 8 of 9 while blocking
    11 to 13 compliant rows). So the gate refuses by default and a human says
    otherwise, per row, in writing.
    """

    ALL_INCLUSIVE = (
        "Government immigration fees are included: our E33 Second Home price is "
        "one all-inclusive figure of Rp 20.000.000 that already contains the "
        "statutory PNBP, so you will never be asked to pay a government fee on top."
    )

    def test_a_compliant_figure_bearing_row_is_refused_without_the_marker(self) -> None:
        assert row_is_refused({"answer": self.ALL_INCLUSIVE}) is not None

    def test_the_marker_plus_a_note_releases_it(self) -> None:
        row = {
            "answer": self.ALL_INCLUSIVE,
            REVIEW_FLAG_FIELD: True,
            REVIEW_NOTE_FIELD: "all-inclusive explainer; the figure IS our price",
        }
        assert row_is_refused(row) is None

    def test_the_flag_alone_is_not_enough(self) -> None:
        """A bare boolean is a checkbox. A note is a claim someone can be held to."""
        for note in (None, "", "   "):
            row = {
                "answer": self.ALL_INCLUSIVE,
                REVIEW_FLAG_FIELD: True,
                REVIEW_NOTE_FIELD: note,
            }
            assert row_is_refused(row) is not None, f"note={note!r} must not release the row"

    def test_a_truthy_non_true_flag_is_not_enough(self) -> None:
        """`is True`, not truthiness: "no", "false" and 1 are all truthy strings
        or ints someone could put in a JSONL by accident."""
        for flag in ("false", "no", 1, "yes"):
            row = {
                "answer": self.ALL_INCLUSIVE,
                REVIEW_FLAG_FIELD: flag,
                REVIEW_NOTE_FIELD: "reviewed",
            }
            assert row_is_refused(row) is not None, f"flag={flag!r} must not release the row"
