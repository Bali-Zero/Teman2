"""Unit tests for scripts/warroom_step2_briefer.py (War Room Step 2, B-fusione).

Covers the DETERMINISTIC logic only (no DB, no LLM) — the new, risky surface:
- content_hash determinism + content-mutation discrimination (D5 re-brief)
- rail injection into enrichment.the_facts (D6 — the field the drafter reads)
- NB staleness delta (D2)
- decide_status: substantive conflict -> needs_review_conflict (D3)
- build_brief_json: full schema + rails inside the final brief + minimal contract
- select_items: human-gate D7 (no --approved/--item-id => empty selection)

Design + panel verdict: research/marketing/2026-06-06-warroom-step2-design.md (§8 7 decisions).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
STEP2_PATH = SCRIPTS_DIR / "warroom_step2_briefer.py"


@pytest.fixture
def m():
    """Load warroom_step2_briefer as a module from scripts/."""
    sys.modules.pop("warroom_step2_briefer", None)
    spec = importlib.util.spec_from_file_location("warroom_step2_briefer", STEP2_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def nb_brief():
    """A realistic NB grounding brief (PP 20/2026 / PPh UMKM case)."""
    return {
        "key_facts": [
            "PP 55/2022 ha sostituito PP 23/2018 implementando UU HPP 7/2021",
            "Durata facility: 7 anni orang pribadi / 4 anni CV / 3 anni PT",
        ],
        "regulatory_citations_verbatim": ["PP 55/2022", "UU HPP 7/2021 Pasal 4(2)e", "PMK 81/2024 Pasal 448"],
        "key_numbers": ["0,5%", "Rp 4,8 mld", "7-4-3 anni", "Rp 10 mld PT PMA"],
        "bilingual_lexicon": [{"id_term": "omzet", "english_assist": "gross revenue", "always_untranslated": False}],
        "taboo_check": ["no 'save money on taxes' (la riforma chiude un loophole)", "no 'PT PMA can use UMKM'"],
        "archetype": "regulatory-explainer",
        "tone_register": "analitico/militante",
        "nb_sources": ["NB-4 848862af"],
        "nb_snapshot_date": "2025-11-01T00:00:00+00:00",
    }


@pytest.fixture
def item():
    """A realistic shortlist item (the fresh news that corrects the stale NB)."""
    return {
        "id": "44122b09-0000-0000-0000-000000000000",
        "item_id": "44122b09-0000-0000-0000-000000000000",
        "title": "Pemerintah Ubah Aturan PPh Final UMKM, PT dan CV Tak Lagi Dapat Fasilitas",
        "summary": "Pemerintah resmi menerbitkan PP 20/2026 tentang Perubahan atas PP 55/2022. Pasal 57.",
        "canonical_url": "https://liputan6.com/pph-umkm-pp20-2026",
        "source_domain": "liputan6.com",
        "published_at": "2026-06-05T00:00:00+00:00",
        "llm": {"relevance": 9, "service_line": "tax", "rationale": "core regulatory tax"},
    }


@pytest.fixture
def prose_clean():
    return {
        "the_facts": "Pemerintah menerbitkan PP 20/2026 yang mengubah PP 55/2022.",
        "bali_zero_take": "Per i clienti PT: niente nuova facility 0,5%.",
        "thirty_second_brief": {"what": "PPh UMKM cambia", "why_it_matters": "PT esclusi",
                                "who": "PT/CV", "risk_level": "medium"},
        "next_steps": "Verificare regime fiscale corrente.",
        "faq": [{"question": "PT PMA può usarlo?", "answer": "No, mai."}],
        "conflict": False,
        "conflict_note": "",
    }


# --- D5: content_hash --------------------------------------------------------
def test_content_hash_deterministic(m):
    assert m._content_hash("PP 20/2026", "testo a") == m._content_hash("PP 20/2026", "testo a")


def test_content_hash_discriminates_content(m):
    # same title, different body -> different hash (so re-brief triggers, D5)
    assert m._content_hash("PP 20/2026", "in attesa firma") != m._content_hash("PP 20/2026", "emanata")


# --- D6: rail injection into the_facts ---------------------------------------
def test_rails_injected_into_facts(m, nb_brief):
    facts = m._inject_rails_into_facts("I fatti base.", nb_brief)
    assert "I fatti base." in facts                       # base prose preserved
    assert "PP 55/2022" in facts                          # verbatim citation injected
    assert "0,5%" in facts                                # key number injected
    assert "loophole" in facts or "save money" in facts   # taboo injected
    assert "NON usare" in facts                            # taboo header present


def test_rails_injection_empty_nb_is_noop(m):
    # no NB grounding -> just the base prose, no crash
    assert m._inject_rails_into_facts("solo prosa", {}) == "solo prosa"


# --- D2: staleness -----------------------------------------------------------
def test_nb_staleness_days(m, nb_brief):
    pub = m._parse_dt("2026-06-05T00:00:00+00:00")
    assert m._nb_staleness_days(nb_brief, pub) == 216  # 2025-11-01 -> 2026-06-05


def test_nb_staleness_none_when_missing(m):
    assert m._nb_staleness_days({}, m._parse_dt("2026-06-05T00:00:00+00:00")) is None


# --- D3: decide_status -------------------------------------------------------
def test_decide_status_conflict_blocks(m):
    assert m.decide_status({"conflict": True}) == m.STATUS_CONFLICT == "needs_review_conflict"


def test_decide_status_clean_ready(m):
    assert m.decide_status({"conflict": False}) == m.STATUS_READY == "briefed"


# --- build_brief_json --------------------------------------------------------
def test_build_brief_json_full_schema(m, item, nb_brief, prose_clean):
    b = m.build_brief_json(item=item, nb_brief=nb_brief, prose=prose_clean, prev_revision=0)
    # enrichment is the channel the drafter reads
    assert isinstance(b["enrichment"], dict)
    assert b["enrichment"]["the_facts"].startswith("Pemerintah menerbitkan PP 20/2026")
    # D6: rails are INSIDE the_facts (drafter sees them)
    assert "PP 55/2022" in b["enrichment"]["the_facts"]
    assert "0,5%" in b["enrichment"]["the_facts"]
    # minimal contract (drafter)
    assert b["source_url"] == "https://liputan6.com/pph-umkm-pp20-2026"
    assert isinstance(b["live_news_reasons"], list)
    # idempotency provenance (D5)
    assert b["content_hash"] and b["revision"] == 1
    assert b["canonical_url"] == item["canonical_url"]
    # rich fields persisted (future)
    assert b["regulatory_citations_verbatim"] == nb_brief["regulatory_citations_verbatim"]
    assert b["key_numbers"] == nb_brief["key_numbers"]
    # fusion meta
    assert b["fusion_meta"]["nb_staleness_days"] == 216
    assert b["fusion_meta"]["conflict"] is False


def test_build_brief_json_revision_bump(m, item, nb_brief, prose_clean):
    b = m.build_brief_json(item=item, nb_brief=nb_brief, prose=prose_clean, prev_revision=2)
    assert b["revision"] == 3  # re-brief bumps revision (D5)


def test_build_brief_json_conflict_in_meta(m, item, nb_brief):
    prose = {"the_facts": "fonti discordi", "conflict": True, "conflict_note": "norma emanata sì/no"}
    b = m.build_brief_json(item=item, nb_brief=nb_brief, prose=prose, prev_revision=0)
    assert b["fusion_meta"]["conflict"] is True
    assert b["fusion_meta"]["conflict_note"] == "norma emanata sì/no"


# --- D7: human gate in select_items ------------------------------------------
def test_select_items_requires_explicit_gate(m, item):
    shortlist = [item]
    # no approved, no item_id -> EMPTY (never process whole shortlist blindly)
    assert m.select_items(shortlist, approved=None, item_id=None, top=3) == []


def test_select_items_by_item_id(m, item):
    picked = m.select_items([item], approved=None, item_id=item["item_id"], top=3)
    assert len(picked) == 1 and picked[0]["item_id"] == item["item_id"]


def test_select_items_by_approved_list(m, item):
    picked = m.select_items([item], approved=[item["item_id"]], item_id=None, top=3)
    assert len(picked) == 1


def test_select_items_top_caps_approved(m):
    items = [{"item_id": f"id-{i}"} for i in range(10)]
    approved = [f"id-{i}" for i in range(10)]
    assert len(m.select_items(items, approved=approved, item_id=None, top=2)) == 2


# --- fail-closed JSON extraction ---------------------------------------------
def test_extract_json_obj_empty_raises(m):
    with pytest.raises(ValueError, match="vuota"):
        m._extract_json_obj("")


def test_extract_json_obj_no_json_raises(m):
    with pytest.raises(ValueError, match="nessun oggetto JSON"):
        m._extract_json_obj("just prose no braces here")


def test_extract_json_obj_extracts(m):
    assert m._extract_json_obj('preamble {"ok": true} trailing')["ok"] is True
