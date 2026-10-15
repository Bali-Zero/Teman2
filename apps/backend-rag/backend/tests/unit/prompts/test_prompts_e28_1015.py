"""E28 family F31 + F32: prompts say IDR 2.5 billion paid-up / more than IDR 10 billion total
investment (zantara_core_v4 RULE 6) and describe the Investor KITAS as the E28A page does."""

from __future__ import annotations

import re
from typing import Any

from backend.prompts import few_shot_examples, whatsapp_persona, zantara_core_v3, zantara_core_v4

RULE_V4 = "Rp2.500.000.000 per limited company"
CITATION = "Permen Investasi/BKPM 5/2025, Article 26"
MIN_CAPITAL_Q = "What is the minimum capital for a PT PMA?"
# 10 billion described as the minimum / subscribed / paid-up capital (either word order).
TEN_BN = r"(?:(?:IDR|Rp\.?)\s?10(?:\.000\.000\.000|\s?billion|\s?miliar)|10\s?billion\s?(?:IDR)?)"
BAD_CAPITAL_RE = re.compile(
    rf"(?:capital|modal)[^.\n]{{0,60}}?{TEN_BN}"
    rf"|^{TEN_BN}[^.\n]{{0,20}}?about"
    rf"|{TEN_BN}[^.\n]{{0,30}}?(?:subscribed|paid-up|capital|you commit)",
    re.I,
)
INNOCENT_RE = re.compile(r"shareholding|not paid-up capital|total investment value", re.I)
# The Investor KITAS worked example, one per module.
WORKED = {"v3": zantara_core_v3.WORKED_EXAMPLES, "v4": zantara_core_v4.WORKED_EXAMPLES}


def _qa_answer(shots: list[dict[str, Any]]) -> str:
    for i, m in enumerate(shots):
        if m["role"] == "user" and m["content"] == MIN_CAPITAL_Q:
            return shots[i + 1]["content"]
    raise AssertionError("minimum-capital few-shot missing")


def _between(text: str, start: str, stop: str) -> str:
    i = text.index(start)
    return " ".join(text[i : text.index(stop, i)].split())


def _investor_block(text: str) -> str:
    return _between(text, "What are the requirements for the Investor KITAS Offshore?", "Indonesian:")


def _italian_block(text: str) -> str:
    return _between(text, "Quali sono i requisiti per il KITAS Investor Offshore?", "English:")


import pytest


@pytest.mark.parametrize(
    "text",
    [
        "PT PMA capital is IDR 10 billion",
        "PT PMA must have Rp10.000.000.000 paid-up capital",
        "the OSS-registered minimum capital is 10 billion IDR",
        "10 billion IDR, about $650k.",
        "modal minimum Rp10.000.000.000",
    ],
)
def test_prompt_capital_detector_catches_mutants(text: str) -> None:
    assert BAD_CAPITAL_RE.search(text) and not INNOCENT_RE.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "your own shareholding of at least IDR 10 billion in that company",
        "minimum placed/paid-up capital is Rp2.500.000.000 per limited company. The separate minimum total "
        "investment value is more than Rp10.000.000.000 under its per-KBLI/location rules.",
    ],
)
def test_prompt_capital_detector_acquits_correct_sentences(text: str) -> None:
    assert not BAD_CAPITAL_RE.search(text) or INNOCENT_RE.search(text)


def test_bad_capital_regex_convicts_the_old_answers() -> None:
    old = (
        "10 billion IDR, about $650k. But you don't have to put it all in on day one, "
        "it's the subscribed capital you commit to invest over time."
    )
    assert BAD_CAPITAL_RE.search(old)
    assert BAD_CAPITAL_RE.search("the OSS-registered minimum capital is 10 billion")
    assert INNOCENT_RE.search("total investment value of more than 10 billion IDR, which is not paid-up capital")


def test_few_shot_minimum_capital_answers_follow_the_v4_rule() -> None:
    for shots in (
        few_shot_examples.GENERAL_FEW_SHOT_EXAMPLES + few_shot_examples.WHATSAPP_FEW_SHOT_EXAMPLES,
        whatsapp_persona.FEW_SHOT_EXAMPLES,
    ):
        try:
            answer = _qa_answer(shots)
        except AssertionError:
            continue
        assert not BAD_CAPITAL_RE.search(answer) or INNOCENT_RE.search(answer), answer
        assert "2.5 billion IDR" in answer and "paid-up" in answer
        assert "more than 10 billion IDR" in answer and "not paid-up capital" in answer
        assert CITATION in answer
        assert not answer.startswith("10 billion")
    assert RULE_V4 in zantara_core_v4.ZANTARA_MASTER_TEMPLATE
    assert CITATION in zantara_core_v4.ZANTARA_MASTER_TEMPLATE


def test_both_few_shot_modules_carry_the_minimum_capital_example() -> None:
    assert _qa_answer(few_shot_examples.WHATSAPP_FEW_SHOT_EXAMPLES + few_shot_examples.GENERAL_FEW_SHOT_EXAMPLES)
    assert _qa_answer(whatsapp_persona.FEW_SHOT_EXAMPLES)


def test_investor_kitas_example_matches_the_e28a_page() -> None:
    for name, text in WORKED.items():
        for block in (_investor_block(text), _italian_block(text)):
            assert "OSS-registered minimum capital" not in block, name
            assert "capitale minimo richiesto in OSS" not in block, name
            assert "BKPM clearance" not in block and "clearance" not in block, name
        en, it = _investor_block(text), _italian_block(text)
        assert "your own shareholding of at least IDR 10 billion in that company" in en, name
        assert "director or commissioner" in en and "Working KITAS" in en, name
        assert "PT PMA as sponsor" in en, name
        assert "una PT PMA come sponsor" in it, name
        assert "almeno IDR 10 miliardi" in it and "direttore o commissario" in it, name
        assert "KITAS di lavoro" in it or "Working KITAS" in it, name


def test_v3_and_v4_investor_examples_are_identical() -> None:
    assert _investor_block(WORKED["v3"]) == _investor_block(WORKED["v4"])
    assert _italian_block(WORKED["v3"]) == _italian_block(WORKED["v4"])
