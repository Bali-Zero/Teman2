"""Tests for deterministic WhatsApp KBLI response guardrails."""

from __future__ import annotations

from backend.services.whatsapp_kbli_guard import (
    is_villa_kbli_query,
    sanitize_whatsapp_kbli_reply,
)


def test_detects_direct_55193_vs_55203_question() -> None:
    assert is_villa_kbli_query("ma 55193 o 55203?") is True
    assert is_villa_kbli_query("Differenza 55193 vs 55203") is True


def test_corrects_legacy_55193_answer_without_mapping() -> None:
    result = sanitize_whatsapp_kbli_reply(
        message_text="ma 55193 o 55203?",
        reply="55193 - Aktivitas Vila: se fai Airbnb usa questo codice.",
        detected_language="it",
    )

    assert result.corrected is True
    assert result.reason == "missing_55193_to_55203_mapping"
    assert "55193" in result.reply
    assert "55203" in result.reply
    assert "KBLI 2020/PP28" in result.reply
    assert "KBLI 2025" in result.reply


def test_corrects_off_topic_kbli_codes_for_villa_query() -> None:
    result = sanitize_whatsapp_kbli_reply(
        message_text="che codici kbli servono per fittare ville su Airbnb?",
        reply=(
            "1. KBLI 43224 - Installazione di Condizionamento e Ventilazione.\n"
            "2. KBLI 65201 - Riassicurazione Convenzionale."
        ),
        detected_language="it",
    )

    assert result.corrected is True
    assert result.reason == "off_topic_kbli_codes:43224,65201"
    assert "43224" not in result.reply
    assert "65201" not in result.reply
    assert "55203" in result.reply


def test_keeps_precise_55193_to_55203_mapping_reply() -> None:
    reply = (
        "55193 e' il codice KBLI 2020/PP28 sorgente per Vila; nel KBLI 2025 "
        "mappa a 55203 - Aktivitas Vila."
    )

    result = sanitize_whatsapp_kbli_reply(
        message_text="Differenza 55193 vs 55203",
        reply=reply,
        detected_language="it",
    )

    assert result.corrected is False
    assert result.reply == reply


def test_ignores_unrelated_non_kbli_message() -> None:
    reply = "Una nuova PT PMA con Bali Zero parte da 20.000.000 IDR."

    result = sanitize_whatsapp_kbli_reply(
        message_text="quanto costa una pma?",
        reply=reply,
        detected_language="it",
    )

    assert result.corrected is False
    assert result.reply == reply


def test_indonesian_villa_management_answer_mentions_management_and_platform_codes() -> None:
    result = sanitize_whatsapp_kbli_reply(
        message_text="Kode KBLI untuk manajemen vila Airbnb pihak ketiga apa?",
        reply="Untuk villa bisa cek kode real estate dulu.",
        detected_language="id",
    )

    assert result.corrected is True
    assert "55203" in result.reply
    assert "55901" in result.reply
    assert "55400" in result.reply
