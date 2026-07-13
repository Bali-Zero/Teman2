"""Tests for nlm_dossier_synthesizer — PII stripping, schema, rendering, chunking.

Deterministic-no-network unit tests (LLM call is mocked).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from backend.services.crm.nlm_dossier_synthesizer import (
    ClientDossier,
    HardFacts,
    HumanLayer,
    SoftFacts,
    _format_conversation,
    strip_pii,
    synthesize_client_dossier,
)


class TestPIIStripping:
    def test_npwp_masked(self):
        text = "NPWP 12.345.678.9-012.345 is registered"
        out = strip_pii(text)
        assert "12.345.678" not in out
        assert "[NPWP-MASKED]" in out

    def test_passport_masked(self):
        text = "Passport A1234567 received"
        out = strip_pii(text)
        assert "A1234567" not in out
        assert "[PASSPORT-MASKED]" in out

    def test_nik_masked(self):
        text = "NIK 3201234567890123 confirmed"
        out = strip_pii(text)
        assert "3201234567890123" not in out
        assert "[NIK-MASKED]" in out

    def test_nib_masked(self):
        text = "NIB 8120012345678"
        out = strip_pii(text)
        assert "8120012345678" not in out
        assert "[NIB-MASKED]" in out

    def test_email_masked(self):
        text = "Send to client@gmail.com please"
        out = strip_pii(text)
        assert "client@gmail.com" not in out
        assert "[EMAIL-MASKED]" in out

    def test_full_phone_masked(self):
        text = "Call +62 822 3010 2328 for confirmation"
        out = strip_pii(text)
        assert "+62 822 3010 2328" not in out
        assert "[PHONE-MASKED]" in out

    def test_efin_masked(self):
        text = "EFIN: 1234567890 enabled"
        out = strip_pii(text)
        assert "1234567890" not in out
        assert "[EFIN-MASKED]" in out

    def test_money_amount_preserved(self):
        text = "Quote IDR 18,000,000 approved"
        out = strip_pii(text)
        assert "18,000,000" in out  # IDR amounts are not PII per UU PDP

    def test_empty_input_safe(self):
        assert strip_pii("") == ""
        assert strip_pii(None) == ""  # type: ignore[arg-type]

    def test_idempotent(self):
        """strip_pii applied twice should yield same result."""
        text = "NPWP 12.345.678.9-012.345 contact client@gmail.com"
        once = strip_pii(text)
        twice = strip_pii(once)
        assert once == twice


class TestFormatConversation:
    def test_renders_chronological_with_arrows(self):
        msgs = [
            {
                "message_date": datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc),
                "direction": "inbound",
                "team_member_email": None,
                "body": "Hi, when can we file SPT?",
                "message_text": None,
            },
            {
                "message_date": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
                "direction": "outbound",
                "team_member_email": "surya@balizero.com",
                "body": "We will file by 2026-05-15",
                "message_text": None,
            },
        ]
        out = _format_conversation(msgs)
        assert "←" in out
        assert "→" in out
        assert "surya@balizero.com" in out
        assert "SPT" in out

    def test_strips_pii_in_body(self):
        msgs = [
            {
                "message_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "direction": "inbound",
                "team_member_email": None,
                "body": "My passport is A1234567",
                "message_text": None,
            }
        ]
        out = _format_conversation(msgs)
        assert "A1234567" not in out
        assert "[PASSPORT-MASKED]" in out

    def test_falls_back_to_message_text_when_body_empty(self):
        msgs = [
            {
                "message_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "direction": "outbound",
                "team_member_email": "adit@balizero.com",
                "body": None,
                "message_text": "Quote sent",
            }
        ]
        out = _format_conversation(msgs)
        assert "Quote sent" in out

    def test_skips_empty_messages(self):
        msgs = [
            {
                "message_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "direction": "inbound",
                "team_member_email": None,
                "body": "",
                "message_text": None,
            }
        ]
        out = _format_conversation(msgs)
        assert out == ""


class TestClientDossierSchema:
    def test_minimum_valid(self):
        d = ClientDossier(
            client_id=11801,
            display_name="Test Client",
            msg_count=10,
            period_start="2026-01-01",
            period_end="2026-05-01",
        )
        assert d.hard_facts.decisions == []
        assert d.human_layer.sentiment_trend == "neutral"

    def test_full_payload_validates(self):
        d = ClientDossier(
            client_id=42,
            display_name="Anaya",
            msg_count=56,
            period_start="2025-11-15",
            period_end="2026-05-18",
            hard_facts=HardFacts.model_validate({
                "decisions": [
                    {"date": "2026-02-12", "what": "Approve SPT filing quote", "who": "client"}
                ],
                "documents_delivered": [
                    {"kind": "passport copy", "ref_date": "2026-03-04"}
                ],
                "declared_deadlines": [],
                "quotes_approved": [
                    {"date": "2026-02-12", "service": "SPT Tahunan", "amount_idr": 18000000}
                ],
            }),
            soft_facts=SoftFacts.model_validate({
                "client_business_goals": ["open PT PMA Q3 2026"],
                "warnings_given": [
                    {"date": "2026-02-28", "topic": "KITAS extension",
                     "note": "needs arrival 60d before expiry"}
                ],
                "promises_sla": [],
            }),
            human_layer=HumanLayer.model_validate({
                "sentiment_trend": "mixed",
                "frustration_episodes": [],
                "operator_handoffs": [
                    {"date": "2026-03-15", "from_operator": "sahira@balizero.com",
                     "to_operator": "surya@balizero.com", "reason": "tax escalation"}
                ],
            }),
        )
        assert d.hard_facts.quotes_approved[0].amount_idr == 18000000
        assert d.human_layer.operator_handoffs[0].reason == "tax escalation"

    def test_sentiment_constrained(self):
        with pytest.raises(ValidationError):
            HumanLayer(sentiment_trend="ecstatic")  # type: ignore[arg-type]


class TestMegaFileRendering:
    def test_render_dossier_markdown_structure(self):
        from scripts.nlm_pack_crm import render_dossier_markdown

        d = ClientDossier(
            client_id=42,
            display_name="Anaya",
            msg_count=10,
            period_start="2026-01-01",
            period_end="2026-05-01",
            hard_facts=HardFacts.model_validate({
                "decisions": [{"date": "2026-02-12", "what": "approve quote", "who": "client"}],
                "documents_delivered": [],
                "declared_deadlines": [],
                "quotes_approved": [
                    {"date": "2026-02-12", "service": "SPT", "amount_idr": 18000000}
                ],
            }),
        )
        out = render_dossier_markdown(d)
        assert "## Client: Anaya (id=42)" in out
        assert "### Hard Facts" in out
        assert "### Soft Facts" in out
        assert "### Human Layer" in out
        assert "approve quote" in out
        assert "IDR 18.000.000" in out  # locale-style formatting
        assert out.endswith("\n")

    def test_render_handles_missing_workspace_facts(self):
        from scripts.nlm_pack_crm import render_dossier_markdown

        d = ClientDossier(
            client_id=1, display_name="X", msg_count=1,
            period_start="2026-01-01", period_end="2026-01-02",
        )
        out = render_dossier_markdown(d)
        assert "Workspace AI facts" not in out
        assert "(none extracted)" in out

    def test_chunking_one_dossier_per_file_when_huge(self):
        from scripts.nlm_pack_crm import chunk_dossiers_by_word_count, render_dossier_markdown

        d_small = ClientDossier(
            client_id=1, display_name="A", msg_count=1,
            period_start="2026-01-01", period_end="2026-01-02",
        )
        rendered_words = len(render_dossier_markdown(d_small).split())
        max_words = rendered_words + 5

        dossiers = [
            ClientDossier(
                client_id=i, display_name=f"client_{i}", msg_count=1,
                period_start="2026-01-01", period_end="2026-01-02",
            )
            for i in range(1, 6)
        ]
        chunks = chunk_dossiers_by_word_count(dossiers, max_words)
        assert len(chunks) == 5  # each dossier in its own chunk
        for chunk in chunks:
            assert len(chunk) == 1

    def test_chunking_packs_multiple_when_fits(self):
        from scripts.nlm_pack_crm import chunk_dossiers_by_word_count

        dossiers = [
            ClientDossier(
                client_id=i, display_name=f"client_{i}", msg_count=1,
                period_start="2026-01-01", period_end="2026-01-02",
            )
            for i in range(1, 6)
        ]
        chunks = chunk_dossiers_by_word_count(dossiers, max_words=400_000)
        assert len(chunks) == 1
        assert len(chunks[0]) == 5


class TestWriteMegaFile:
    def test_writes_with_header(self, tmp_path: Path):
        from scripts.nlm_pack_crm import write_mega_file

        d = ClientDossier(
            client_id=1, display_name="Test", msg_count=5,
            period_start="2026-01-01", period_end="2026-05-01",
        )
        output = tmp_path / "batch-01.txt"
        write_mega_file([d], output_path=output, batch_num=1, total_batches=1, window_days=180)
        assert output.exists()
        text = output.read_text(encoding="utf-8")
        assert "Bali Zero CRM WhatsApp Dossier" in text
        assert "batch 01/01" in text
        assert "## Client: Test" in text
        assert "qwen3.5:9b" in text  # provenance


class TestSynthesizerDeterminism:
    @pytest.mark.asyncio
    async def test_same_messages_same_dossier_when_llm_deterministic(self):
        """If LLM returns identical JSON twice, dossier output is identical."""
        mock_response = {
            "hard_facts": {
                "decisions": [
                    {"date": "2026-02-12", "what": "approve quote", "who": "client"}
                ],
                "documents_delivered": [],
                "declared_deadlines": [],
                "quotes_approved": [],
            },
            "soft_facts": {
                "client_business_goals": ["open PT PMA"],
                "warnings_given": [],
                "promises_sla": [],
            },
            "human_layer": {
                "sentiment_trend": "neutral",
                "frustration_episodes": [],
                "operator_handoffs": [],
            },
        }

        messages = [
            {
                "message_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "direction": "inbound",
                "team_member_email": None,
                "body": "Hi, I want PT PMA",
                "message_text": None,
            },
            {
                "message_date": datetime(2026, 5, 2, tzinfo=timezone.utc),
                "direction": "outbound",
                "team_member_email": "sahira@balizero.com",
                "body": "Quote IDR 25.000.000",
                "message_text": None,
            },
        ]

        with patch(
            "backend.services.crm.nlm_dossier_synthesizer._call_ollama_json",
            new=AsyncMock(return_value=mock_response),
        ):
            d1 = await synthesize_client_dossier(
                client_id=1, display_name="X", messages=messages
            )
            d2 = await synthesize_client_dossier(
                client_id=1, display_name="X", messages=messages
            )

        assert d1 is not None and d2 is not None
        assert d1.model_dump() == d2.model_dump()

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self):
        with patch(
            "backend.services.crm.nlm_dossier_synthesizer._call_ollama_json",
            new=AsyncMock(return_value=None),
        ):
            result = await synthesize_client_dossier(
                client_id=1,
                display_name="X",
                messages=[{
                    "message_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
                    "direction": "inbound",
                    "team_member_email": None,
                    "body": "hi",
                    "message_text": None,
                }],
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_empty_message_list(self):
        result = await synthesize_client_dossier(
            client_id=1, display_name="X", messages=[]
        )
        assert result is None
