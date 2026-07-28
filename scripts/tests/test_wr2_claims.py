"""The WR2 claim contract — what may become a claim id, and what may not.

WR3's companion inherits these ids and does NOT re-verify them, so every id
minted here is an assertion that WR2 already checked. The corpus therefore
leans hard on the refusals: a false claim id costs Veo credits and puts an
unverified sentence in a published video.

The three brief shapes below are not invented for the test — they are the three
shapes actually found across the 23 briefs on disk on 2026-07-26:
plain strings (18 briefs), `{fact, source, source_status}` (1), and
`{id, fact}` with an author-assigned id that traces to nothing (2).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_REPO = _SCRIPTS.parent


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def wc() -> Any:
    return _load("wr2_claims")


def _brief(*facts: Any, **extra: Any) -> dict[str, Any]:
    return {"key_facts": list(facts), **extra}


_GOOD = {
    "fact": "PMK 37/2025 designates marketplaces as PPh Pasal 22 collectors.",
    "source": "DJP official FAQ PDF (pajak.go.id), Q1",
    "source_status": "verified_web",
}

# Verbatim from apps/war-room/output/carousel/2026-07-08-august-1-tokopedia-
# shopee-lazada-*/brief.json — the status that mixes a verified fact with an
# explicitly ILLUSTRATIVE rupiah figure.
_PROSE_STATUS = (
    "verified_web (FAQ example) / operator_brief (Rp10m illustrative figure, "
    "consistent with the confirmed 0.5% rate)"
)


# ── GUILT: what must never become a claim ────────────────────────────────


def test_a_prose_status_carrying_an_illustrative_figure_is_refused(wc) -> None:
    """The whole reason the vocabulary is closed.

    `status.startswith("verified")` accepts this string. It would promote an
    illustrative Rp10m figure to a verified claim, and WR3 would state it as
    fact in a video — matching the FORM of the status, not the entity.
    """
    ex = wc.extract_claims(_brief({**_GOOD, "source_status": _PROSE_STATUS}))
    assert ex.claims == []
    assert ex.rejected == {wc.RejectReason.STATUS_NOT_IN_VOCABULARY: 1}


def test_a_plain_string_fact_is_not_a_claim(wc) -> None:
    """18 of 23 briefs are shaped like this. Deriving ids from them would mint
    handles onto assertions whose grounding is a prose convention."""
    ex = wc.extract_claims(_brief("KITAP is valid 5 years — NB-2 [IMM-356]"))
    assert ex.claims == []
    assert ex.rejected == {wc.RejectReason.UNSTRUCTURED: 1}


def test_an_author_assigned_id_without_a_source_is_not_a_claim(wc) -> None:
    """The `{"id": "KF-1", "fact": ...}` shape, found in 2 briefs on disk."""
    ex = wc.extract_claims(_brief({"id": "KF-1", "fact": "SPDN has three triggers."}))
    assert ex.claims == []
    assert ex.rejected == {wc.RejectReason.NO_SOURCE: 1}


def test_a_declared_id_that_no_record_backs_is_ignored(wc) -> None:
    """A brief may narrow the set; it may never invent one.

    An authored id traces to nothing, and WR3 does not re-verify what it
    inherits — so honouring an unbacked declaration exports a phantom.
    """
    brief = _brief(_GOOD, primary_claim_ids=["KF-1", "KF-2"])
    ids, ex = wc.resolve_primary_claim_ids(brief)
    assert ids == [ex.claims[0].claim_id]
    assert "KF-1" not in ids


def test_corroboration_alone_does_not_verify(wc) -> None:
    ex = wc.extract_claims(
        _brief({**_GOOD, "source_status": "nb_corroborated"})
    )
    assert ex.claims == []
    assert ex.rejected == {wc.RejectReason.STATUS_ONLY_CORROBORATING: 1}


def test_an_unknown_status_token_inside_a_valid_composite_sinks_it(wc) -> None:
    """One bad token spoils the status — no partial credit."""
    ex = wc.extract_claims(
        _brief({**_GOOD, "source_status": "verified_web + operator_brief"})
    )
    assert ex.claims == []
    assert ex.rejected == {wc.RejectReason.STATUS_NOT_IN_VOCABULARY: 1}


# ── INNOCENCE: what must still work ──────────────────────────────────────


def test_a_well_formed_record_becomes_exactly_one_claim(wc) -> None:
    ex = wc.extract_claims(_brief(_GOOD))
    assert len(ex.claims) == 1
    c = ex.claims[0]
    assert c.kind == "fact"
    assert c.status_tokens == ("verified_web",)
    assert ex.rejected == {}


def test_a_composite_of_allowed_tokens_is_accepted(wc) -> None:
    ex = wc.extract_claims(
        _brief({**_GOOD, "source_status": "verified_web + nb_corroborated"})
    )
    assert len(ex.claims) == 1
    assert ex.claims[0].status_tokens == ("verified_web", "nb_corroborated")


def test_an_author_id_on_a_BACKED_record_is_honoured(wc) -> None:
    """`bkpm-5-2025-paid-up` reads better than `fact-e80b5a95faa4`.

    The id may be authored — but only once the record has proved it has a
    source and a verified status. Same string on a bare assertion is refused
    (see the KF-1 case above); the difference is the backing, not the name.
    """
    ex = wc.extract_claims(_brief({**_GOOD, "id": "bkpm-5-2025-paid-up"}))
    assert [c.claim_id for c in ex.claims] == ["bkpm-5-2025-paid-up"]


def test_an_id_with_whitespace_falls_back_to_the_derived_hash(wc) -> None:
    """An id is a handle other artifacts reference; prose is not a handle."""
    ex = wc.extract_claims(_brief({**_GOOD, "id": "the BKPM paid up rule"}))
    assert ex.claims[0].claim_id.startswith("fact-")


def test_the_id_is_stable_across_whitespace_reflow(wc) -> None:
    """Reflowing a brief must not orphan every downstream WR3 reference."""
    a = wc.make_claim_id("fact", "PMK 37/2025 applies.", "DJP FAQ")
    b = wc.make_claim_id("fact", "  PMK 37/2025\n   applies.  ", "DJP FAQ")
    assert a == b


def test_a_different_source_is_a_different_claim(wc) -> None:
    a = wc.make_claim_id("fact", "PMK 37/2025 applies.", "DJP FAQ")
    b = wc.make_claim_id("fact", "PMK 37/2025 applies.", "a blog post")
    assert a != b


def test_a_declared_subset_narrows_and_keeps_derivation_order(wc) -> None:
    second = {
        "number": "0.5% — the PPh 22 rate collected by marketplaces",
        "source": "DJP official FAQ PDF, Q7",
        "source_status": "nb_verified",
    }
    brief = _brief(_GOOD)
    brief["key_numbers"] = [second]
    all_ids, _ = wc.resolve_primary_claim_ids(brief)
    assert len(all_ids) == 2
    narrowed, _ = wc.resolve_primary_claim_ids({**brief, "primary_claim_ids": [all_ids[1]]})
    assert narrowed == [all_ids[1]]


def test_the_reject_summary_names_every_reason_it_counted(wc) -> None:
    """An honest zero has to say WHY, or the gap is invisible to the operator."""
    ex = wc.extract_claims(
        _brief("a bare string", {"fact": "no source here"}, {**_GOOD, "source_status": _PROSE_STATUS})
    )
    summary = ex.reject_summary()
    for reason in (
        wc.RejectReason.UNSTRUCTURED,
        wc.RejectReason.NO_SOURCE,
        wc.RejectReason.STATUS_NOT_IN_VOCABULARY,
    ):
        assert reason in summary


# ── The three real shapes, side by side ──────────────────────────────────


def test_a_mixed_brief_separates_the_three_real_shapes(wc) -> None:
    """One brief carrying all three shapes found on disk, verbatim.

    The carousel output tree is not tracked in git, so a test that walked it
    would skip in CI and be coverage in name only. These are the entries
    themselves, lifted from the real briefs.
    """
    brief = {
        "key_facts": [
            # shape 1 — 18 of 23 briefs
            "No Permenkumham 22/2024 exists — refers to the 22/2023 package — NB-2 [IMM-356]",
            # shape 2 — 1 of 23, the only one that qualifies
            {
                "fact": "PMK 37/2025 was signed 11 June 2025; DJP materials place "
                "its effective date at 14 July 2025.",
                "source": "JDIH Kemenkeu + DJP siaran pers, corroborated by NB-4",
                "source_status": "verified_web + nb_corroborated",
            },
            # shape 3 — 2 of 23, an id that traces to nothing
            {"id": "KF-1", "fact": "SPDN has THREE independent triggers under UU PPh 36/2008."},
        ]
    }
    ex = wc.extract_claims(brief)
    assert len(ex.claims) == 1
    assert ex.claims[0].status_tokens == ("verified_web", "nb_corroborated")
    assert ex.rejected == {
        wc.RejectReason.UNSTRUCTURED: 1,
        wc.RejectReason.NO_SOURCE: 1,
    }


def test_the_scan_cli_reports_a_corpus_without_inventing_one(wc, tmp_path, capsys) -> None:
    """`--scan` is how an operator sees the gap close; it must count honestly."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "brief.json").write_text(
        json.dumps({"key_facts": [_GOOD]}), encoding="utf-8"
    )
    (tmp_path / "b" / "brief.json").write_text(
        json.dumps({"key_facts": ["a bare string"]}), encoding="utf-8"
    )
    rc = wc.scan_corpus(tmp_path)
    out = capsys.readouterr().out
    assert rc == 0
    assert "1/2" in out  # one brief of two carries claims
    assert "unstructured" in out


def test_the_scan_ignores_hidden_backup_directories(wc, tmp_path, capsys) -> None:
    """A real one on disk: `.bali-pma-rental-crackdown.bak-pre-revise-20260714`.

    `Path.glob("*/brief.json")` matches dot-directories, the shell's `*` does
    not — which is how the same tree measured 24 and 23 within one minute. A
    dead snapshot must never move the denominator, nor supply a claim.
    """
    (tmp_path / "live").mkdir()
    (tmp_path / ".live.bak-pre-revise").mkdir()
    (tmp_path / "live" / "brief.json").write_text(
        json.dumps({"key_facts": [_GOOD]}), encoding="utf-8"
    )
    (tmp_path / ".live.bak-pre-revise" / "brief.json").write_text(
        json.dumps({"key_facts": [_GOOD]}), encoding="utf-8"
    )
    assert wc.scan_corpus(tmp_path) == 0
    assert "1/1" in capsys.readouterr().out
