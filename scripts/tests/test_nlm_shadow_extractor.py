"""Tests for nlm_shadow_extractor.py — Sprint 2 Shadow Graphing.

Covers the parser/dispatch logic without touching NLM CLI, DeepSeek API,
OpenAI API, or Qdrant.
"""

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_extractor():
    """Load scripts/nlm_shadow_extractor.py as a module."""
    p = Path(__file__).resolve().parents[2] / "scripts" / "nlm_shadow_extractor.py"
    spec = importlib.util.spec_from_file_location("shadow_extractor", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["shadow_extractor"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── _parse_json_list ─────────────────────────────────────────────────────────

def test_parse_json_list_plain():
    ext = _load_extractor()
    answer = '[{"claim": "PT PMA needs IDR 10B", "source_id": "s1"}]'
    out = ext._parse_json_list(answer)
    assert len(out) == 1
    assert out[0]["claim"].startswith("PT PMA")


def test_parse_json_list_markdown_wrapped():
    ext = _load_extractor()
    answer = '```json\n[{"claim": "VOA tarif Rp500k", "source_id": "x"}]\n```'
    out = ext._parse_json_list(answer)
    assert len(out) == 1
    assert "VOA" in out[0]["claim"]


def test_parse_json_list_with_prose_around():
    ext = _load_extractor()
    answer = (
        "Sure, here are the claims:\n"
        '[{"claim": "KITAS valid 1y", "source_id": "a"},'
        ' {"claim": "renew at +30 days", "source_id": "b"}]\n'
        "Let me know if you need more."
    )
    out = ext._parse_json_list(answer)
    assert len(out) == 2


def test_parse_json_list_no_list_returns_empty():
    ext = _load_extractor()
    out = ext._parse_json_list("Sorry I cannot answer.")
    assert out == []


def test_parse_json_list_malformed_returns_empty():
    ext = _load_extractor()
    out = ext._parse_json_list('[{"claim": "broken json missing brace"')
    assert out == []


def test_parse_json_list_drops_items_without_claim_key():
    ext = _load_extractor()
    answer = '[{"claim": "good"}, {"source_id": "no_claim"}, {"claim": "also good"}]'
    out = ext._parse_json_list(answer)
    assert len(out) == 2
    assert all("claim" in o for o in out)


# ── extract_for_notebook unknown_domain path ─────────────────────────────────

def test_extract_for_notebook_unknown_domain():
    ext = _load_extractor()
    res = ext.extract_for_notebook("not-a-domain", dry_run=True)
    assert res["status"] == "unknown_domain"
    assert res["claims_emitted"] == 0


def test_extract_for_notebook_dry_run_known_domain():
    ext = _load_extractor()
    res = ext.extract_for_notebook("immigration", dry_run=True)
    assert res["status"] == "dry_run"
    assert res["domain"] == "immigration"
    assert res["notebook_id"] == "cff93ab0-813a-42f2-a8de-36987e724271"
    assert "run_id" in res


# ── domain registry coverage ─────────────────────────────────────────────────

def test_all_domains_have_required_fields():
    ext = _load_extractor()
    for domain, data in ext.DOMAIN_TO_NB.items():
        assert "id" in data and len(data["id"]) > 30
        assert "label" in data
        assert "extract_prompt_subject" in data
