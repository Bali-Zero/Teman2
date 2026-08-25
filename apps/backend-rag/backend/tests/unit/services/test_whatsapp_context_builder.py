"""
Comprehensive pytest suite for WhatsApp Context Builder.
Tests: detect_language, extract_visa_mentions, extract_interests,
       get_time_of_day, infer_client_type, build_context

Target: 80%+ coverage

Uses:
- pytest.mark.asyncio for async tests
- pytest.mark.parametrize for language detection variants
- AsyncMock for database pool mocking
- freezegun for time-based tests
"""

import json

# Set env vars before importing module under test
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.services.whatsapp_context_builder import (
    _VISA_PATTERNS,
    VISA_CODES,
    build_context,
    detect_language,
    extract_interests,
    extract_visa_mentions,
    get_time_of_day,
    infer_client_type,
)

# ============================================================================
# FIXTURES
# ============================================================================


def _create_async_cm(return_value):
    """Helper: create async context manager mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg.Pool with async context manager."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = _create_async_cm(mock_conn)
    return mock_pool, mock_conn


@pytest.fixture
def sample_conversation_row():
    """Sample database row for conversations table."""
    return {
        "id": 42,
        "messages": json.dumps(
            [
                {"role": "user", "content": "Ciao, vorrei informazioni sul KITAS"},
                {"role": "assistant", "content": "Buongiorno! Certamente..."},
                {"role": "user", "content": "Quanto costa la PT PMA?"},
            ],
        ),
        "metadata": json.dumps(
            {
                "channel": "whatsapp",
                "phone": "+628123456789",
                "sender_name": "Marco Rossi",
                "detected_language": "it",
                "message_count": 3,
                "visa_discussed": ["KITAS"],
                "interests": ["company_setup"],
                "client_type": "entrepreneur",
            },
        ),
    }


# ============================================================================
# detect_language TESTS
# ============================================================================


class TestDetectLanguage:
    """Tests for detect_language function."""

    @pytest.mark.parametrize(
        "text,expected_lang",
        [
            ("Ciao, vorrei informazioni sui visti", "it"),
            ("Buongiorno, quanto costa il servizio?", "it"),
            ("Grazie mille per l'aiuto", "it"),
            ("Hello, I need help with my visa", "en"),
            ("Hi, how much does it cost?", "en"),
            ("Thanks for the information", "en"),
            ("Halo, saya butuh bantuan", "id"),
            ("Berapa biaya untuk KITAS?", "id"),
            ("Hallo, ich brauche Hilfe", "de"),
            ("Bonjour, je veux des informations", "fr"),
            ("Hola, necesito ayuda", "es"),
        ],
        ids=[
            "it-ciao",
            "it-buongiorno",
            "it-grazie",
            "en-hello",
            "en-how-much",
            "en-thanks",
            "id-halo",
            "id-berapa",
            "de-hallo",
            "fr-bonjour",
            "es-hola",
        ],
    )
    def test_single_language_detection(self, text: str, expected_lang: str) -> None:
        """Detect language from a single message."""
        result = detect_language(text)
        assert result == expected_lang

    def test_default_to_english(self) -> None:
        """Unknown text defaults to English."""
        result = detect_language("xyz 12345 !@#$%")
        assert result == "en"

    def test_empty_string(self) -> None:
        """Empty string defaults to English."""
        result = detect_language("")
        assert result == "en"

    def test_with_conversation_history(self) -> None:
        """Language detection considers conversation history."""
        history = [
            {"role": "user", "content": "Ciao, come stai?"},
            {"role": "assistant", "content": "Bene, grazie!"},
            {"role": "user", "content": "Vorrei sapere qualcosa"},
        ]
        result = detect_language("informazioni", history)
        assert result == "it"

    def test_history_uses_only_user_messages(self) -> None:
        """Only user messages from history are used for detection."""
        history = [
            {"role": "assistant", "content": "Hello! How can I help?"},
            {"role": "user", "content": "Ciao, grazie mille"},
        ]
        # Current message is neutral, but history user message is Italian
        result = detect_language("ok", history)
        assert result == "it"

    def test_history_uses_last_3_messages(self) -> None:
        """History uses at most the last 3 user messages."""
        history = [
            {"role": "user", "content": "first message"},
            {"role": "user", "content": "second message"},
            {"role": "user", "content": "third message"},
            {"role": "user", "content": "Ciao ciao ciao"},
            {"role": "user", "content": "Buongiorno buongiorno"},
            {"role": "user", "content": "Grazie mille grazie"},
        ]
        result = detect_language("test", history)
        assert result == "it"

    def test_mixed_language_highest_score_wins(self) -> None:
        """When multiple languages detected, highest score wins."""
        # Italian has more keywords than English here
        result = detect_language("Ciao hello buongiorno grazie come stai?")
        assert result == "it"

    def test_russian_detection(self) -> None:
        """Russian text is detected correctly."""
        result = detect_language("привет, мне нужна помощь")
        assert result == "ru"


# ============================================================================
# extract_visa_mentions TESTS
# ============================================================================


class TestExtractVisaMentions:
    """Tests for extract_visa_mentions function."""

    def test_single_visa_code(self) -> None:
        """Extract a single visa code."""
        result = extract_visa_mentions("I need a KITAS visa")
        assert "KITAS" in result

    def test_multiple_visa_codes(self) -> None:
        """Extract multiple visa codes."""
        result = extract_visa_mentions("What about PMA company and working KITAS?")
        assert "PMA" in result
        assert "KITAS" in result

    def test_case_insensitive(self) -> None:
        """Detection is case-insensitive."""
        result = extract_visa_mentions("looking for KITAS or kitap")
        assert "KITAS" in result
        assert "KITAP" in result

    def test_no_visa_codes(self) -> None:
        """Empty list when no visa codes found."""
        result = extract_visa_mentions("I want to eat pizza")
        assert result == []

    def test_no_duplicates(self) -> None:
        """No duplicate codes in result."""
        result = extract_visa_mentions("kitas kitas kitas")
        assert result.count("KITAS") == 1

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        result = extract_visa_mentions("")
        assert result == []

    @pytest.mark.parametrize(
        "code",
        [
            "a1",
            "b1",
            "b211",
            "b211a",
            "b211b",
            "c1",
            "c2",
            "c6",
            "c7a",
            "c7b",
            "c7c",
            "c8a",
            "c8b",
            "c10",
            "c18",
            "c22a",
            "c22b",
            "d1",
            "d2",
            "d12",
            "e23",
            "e30a",
            "e30b",
            "e33",
            "e33e",
            "e33f",
            "e33g",
            "voa",
            "kitas",
            "kitap",
            "merp",
            "epo",
            "erp",
            "pma",
            "npwp",
            "npwpd",
            "spt",
            "sktt",
            "skck",
        ],
        ids=lambda c: f"code-{c}",
    )
    def test_all_visa_codes_detected(self, code: str) -> None:
        """Each defined visa code is detectable."""
        result = extract_visa_mentions(f"I need {code} visa")
        assert code.upper() in result


# ============================================================================
# Second Home + word-boundary matcher guilt / innocence tests
# ============================================================================


class TestSecondHomeAndBoundaryMatching:
    """Guilt and innocence tests for the word-boundary visa matcher.

    The matcher must recognise the base Second Home family (E33/E33E/E33F)
    and its natural-language triggers, while refusing to fire on substrings
    of longer codes ("e33" inside "e33g", "c1" inside "c18", etc.).
    """

    # --- GUILT ---
    def test_second_home_english_triggers_second_home_prospect(self) -> None:
        """"I want the Second Home Visa" tags SECOND HOME and types correctly."""
        visas = extract_visa_mentions("I want the Second Home Visa")
        assert "SECOND HOME" in visas
        client_type = infer_client_type({"visa_discussed": visas})
        assert client_type == "second_home_prospect"

    def test_e33_base_tags_second_home_prospect(self) -> None:
        """"interested in E33" tags E33 and types as second-home prospect."""
        visas = extract_visa_mentions("interested in E33")
        assert "E33" in visas
        assert "E33G" not in visas
        client_type = infer_client_type({"visa_discussed": visas})
        assert client_type == "second_home_prospect"

    def test_e33e_senior_tags_retiree(self) -> None:
        """"E33E senior route" tags E33E (not bare E33) and types as retiree."""
        visas = extract_visa_mentions("E33E senior route")
        assert "E33E" in visas
        assert "E33" not in visas
        client_type = infer_client_type({"visa_discussed": visas})
        assert client_type == "retiree"

    def test_rumah_kedua_triggers_second_home_prospect(self) -> None:
        """"visa rumah kedua" tags RUMAH KEDUA and types correctly."""
        visas = extract_visa_mentions("visa rumah kedua")
        assert "RUMAH KEDUA" in visas
        client_type = infer_client_type({"visa_discussed": visas})
        assert client_type == "second_home_prospect"

    # --- INNOCENCE: prefix collisions in the code list ---
    @pytest.mark.parametrize(
        "text,expected_code,unexpected_code",
        [
            ("E33G remote worker", "E33G", "E33"),
            ("E33E senior citizen visa", "E33E", "E33"),
            ("E33F family senior visa", "E33F", "E33"),
            ("C18 work trial visa", "C18", "C1"),
            ("C22A internship visa", "C22A", "C2"),
            ("C22B training visa", "C22B", "C2"),
        ],
        ids=[
            "e33g-not-e33",
            "e33e-not-e33",
            "e33f-not-e33",
            "c18-not-c1",
            "c22a-not-c2",
            "c22b-not-c2",
        ],
    )
    def test_prefix_collision_innocence(
        self,
        text: str,
        expected_code: str,
        unexpected_code: str,
    ) -> None:
        """A shorter code must not match inside a longer code with the same prefix."""
        visas = extract_visa_mentions(text)
        assert expected_code.upper() in visas
        assert unexpected_code.upper() not in visas

    def test_e33g_stays_digital_nomad(self) -> None:
        """E33G leads must still type as digital_nomad, not second_home_prospect."""
        visas = extract_visa_mentions("E33G remote worker")
        client_type = infer_client_type({"visa_discussed": visas})
        assert client_type == "digital_nomad"

    # --- REGRESSION: multi-word phrases boundaries ---
    @pytest.mark.parametrize(
        "text,expected_code",
        [
            ("I want a second home", "SECOND HOME"),
            ("saya mau rumah kedua", "RUMAH KEDUA"),
            ("I need working kitas", "WORKING KITAS"),
            ("book a virtual office", "VIRTUAL OFFICE"),
        ],
        ids=[
            "second-home-exact",
            "rumah-kedua-exact",
            "working-kitas-exact",
            "virtual-office-exact",
        ],
    )
    def test_multiword_phrase_matches_exactly(
        self,
        text: str,
        expected_code: str,
    ) -> None:
        """Multi-word visa codes fire on exact phrase matches."""
        visas = extract_visa_mentions(text)
        assert expected_code.upper() in visas

    @pytest.mark.parametrize(
        "text,unexpected_code",
        [
            ("I am a second homeowner", "SECOND HOME"),
            ("rumah keduaan di bali", "RUMAH KEDUA"),
            ("workings kitas only", "WORKING KITAS"),
            ("virtual officer service", "VIRTUAL OFFICE"),
            ("secondly my home", "SECOND HOME"),
        ],
        ids=[
            "second-homeowner",
            "rumah-keduaan",
            "workings-kitas",
            "virtual-officer",
            "secondly-home",
        ],
    )
    def test_multiword_phrase_rejects_substrings(
        self,
        text: str,
        unexpected_code: str,
    ) -> None:
        """Multi-word visa codes do not fire on substrings of longer words."""
        visas = extract_visa_mentions(text)
        assert unexpected_code.upper() not in visas

    def test_punctuation_adjacency_still_matches(self) -> None:
        """Standalone tokens adjacent to punctuation still match."""
        visas = extract_visa_mentions("E33. (E33G) e33/e33e and kitas?")
        assert "E33" in visas
        assert "E33G" in visas
        assert "E33E" in visas
        assert "KITAS" in visas


# ============================================================================
# Round-2 boundary regression + structural sibling coverage
# ============================================================================


# Canonical code tokens extracted from the live Bali Zero price catalogue
# (apps/backend-rag/backend/data/bali_zero_official_prices_2026.json).
# Used by the structural test to catch short codes whose longer siblings are
# missing from VISA_CODES.
_CATALOGUE_CODES = frozenset(
    {
        "a1",
        "b1",
        "b211",
        "b211a",
        "b211b",
        "c1",
        "c2",
        "c6",
        "c7a",
        "c7b",
        "c7c",
        "c8a",
        "c8b",
        "c10",
        "c18",
        "c22a",
        "c22b",
        "d1",
        "d2",
        "d12",
        "e23",
        "e30a",
        "e30b",
        "e33",
        "e33e",
        "e33f",
        "e33g",
        "voa",
        "kitas",
        "kitap",
        "merp",
        "epo",
        "erp",
        "pma",
        "virtual office",
        "npwp",
        "npwpd",
        "spt",
        "freelance",
        "investor",
        "retirement",
        "spouse",
        "dependent",
        "working kitas",
        "second home",
        "rumah kedua",
        "sktt",
        "skck",
        "domicilie",
    },
)


class TestVisaCodeBoundaryRegressions:
    """Regression tests for the word-boundary matcher coverage gap.

    The boundary fix removed accidental substring matches (e.g. "c1" inside
    "c18"). This class proves the *intentional* longer codes are still
    detected, and that the shorter prefix does NOT fire on them.
    """

    @pytest.mark.parametrize(
        "text,expected_codes,unexpected_codes",
        [
            ("I am on a B211A now", {"B211A"}, {"B211"}),
            ("extend my B211B", {"B211B"}, {"B211"}),
            ("B211 visa", {"B211"}, {"B211A", "B211B"}),
            ("C10 speaker visa", {"C10"}, {"C1"}),
            ("C18 work trial", {"C18"}, {"C1"}),
        ],
        ids=[
            "b211a-not-b211",
            "b211b-not-b211",
            "b211-only",
            "c10-not-c1",
            "c18-not-c1",
        ],
    )
    def test_explicit_regression_cases(
        self,
        text: str,
        expected_codes: set[str],
        unexpected_codes: set[str],
    ) -> None:
        """Known regression cases from the round-2 grader report."""
        visas = set(extract_visa_mentions(text))
        assert expected_codes.issubset(visas), f"Missing {expected_codes - visas} in {visas}"
        assert not unexpected_codes & visas, f"Unexpected {unexpected_codes & visas} in {visas}"

    @pytest.mark.parametrize(
        "text,expected_code,unexpected_code",
        [
            ("A1 visa-free tourism", "A1", "A12"),
            ("B1 visa on arrival", "B1", "B211"),
            ("B211A visit visa", "B211A", "B211"),
            ("B211B visit visa", "B211B", "B211"),
            ("C6 social activity", "C6", "C60"),
            ("C7C music visa", "C7C", "C7CAT"),
            ("C8A sports event", "C8A", "C8AB"),
            ("C8B referee visa", "C8B", "C8BC"),
            ("C10 speaker visa", "C10", "C1"),
            ("D1 tourism one year", "D1", "D12"),
            ("D2 business one year", "D2", "D22"),
            ("E23 freelance visa", "E23", "E230"),
            ("E30A education visa", "E30A", "E30AB"),
            ("E30B higher education", "E30B", "E30BC"),
            ("NPWPD registration", "NPWPD", "NPWP"),
        ],
        ids=[
            "a1",
            "b1",
            "b211a",
            "b211b",
            "c6",
            "c7c",
            "c8a",
            "c8b",
            "c10",
            "d1",
            "d2",
            "e23",
            "e30a",
            "e30b",
            "npwpd",
        ],
    )
    def test_new_code_guilt_and_innocence(
        self,
        text: str,
        expected_code: str,
        unexpected_code: str,
    ) -> None:
        """Every new code added in round 2 matches standalone and not as a prefix."""
        visas = set(extract_visa_mentions(text))
        assert expected_code.upper() in visas
        assert unexpected_code.upper() not in visas

    def test_no_code_has_an_unlisted_longer_sibling(self) -> None:
        """Structural guard: if a short code is listed, its catalogue siblings must be too.

        This prevents the boundary matcher from silently narrowing coverage the
        next time a short code is added without its longer real-world siblings.
        """
        missing: list[tuple[str, str]] = []
        for short in VISA_CODES:
            for long in _CATALOGUE_CODES:
                if long != short and long.startswith(short) and long not in VISA_CODES:
                    missing.append((short, long))

        assert not missing, (
            "VISA_CODES contains a short code but is missing its longer catalogue sibling(s).\n"
            "Add the missing sibling(s) to restore coverage:\n"
            + "\n".join(f"  {short!r} -> add {long!r}" for short, long in missing)
        )


# ============================================================================
# extract_interests TESTS
# ============================================================================


class TestExtractInterests:
    """Tests for extract_interests function."""

    def test_remote_work(self) -> None:
        result = extract_interests("I want to do remote work from Bali")
        assert "remote_work" in result

    def test_company_setup(self) -> None:
        result = extract_interests("How do I setup a PT PMA company?")
        assert "company_setup" in result

    def test_family_relocation(self) -> None:
        result = extract_interests("I'm moving with my wife and children")
        assert "family_relocation" in result

    def test_retirement(self) -> None:
        result = extract_interests("I want to retire in Bali")
        assert "retirement" in result

    def test_investment(self) -> None:
        result = extract_interests("I want to invest in property")
        assert "investment" in result

    def test_tax(self) -> None:
        result = extract_interests("What about NPWP and tax obligations?")
        assert "tax" in result

    def test_multiple_interests(self) -> None:
        result = extract_interests("I want to invest in property and setup a company")
        assert "investment" in result
        assert "company_setup" in result

    def test_no_interests(self) -> None:
        result = extract_interests("Nice weather today")
        assert result == []

    def test_italian_keywords(self) -> None:
        """Italian keywords are detected."""
        result = extract_interests("Vorrei aprire azienda a Bali")
        assert "company_setup" in result

    def test_indonesian_keywords(self) -> None:
        """Indonesian keywords are detected."""
        result = extract_interests("Saya mau buka perusahaan")
        assert "company_setup" in result


# ============================================================================
# get_time_of_day TESTS
# ============================================================================


class TestGetTimeOfDay:
    """Tests for get_time_of_day function."""

    @patch("backend.services.whatsapp_context_builder.datetime")
    def test_morning(self, mock_dt: MagicMock) -> None:
        """5:00 - 11:59 WITA is morning."""
        # WITA = UTC+8, so UTC 00:00 = WITA 08:00 (morning)
        mock_now = MagicMock()
        mock_now.hour = 0  # UTC 00:00 -> WITA 08:00
        mock_dt.now.return_value = mock_now
        assert get_time_of_day() == "morning"

    @patch("backend.services.whatsapp_context_builder.datetime")
    def test_afternoon(self, mock_dt: MagicMock) -> None:
        """12:00 - 16:59 WITA is afternoon."""
        mock_now = MagicMock()
        mock_now.hour = 6  # UTC 06:00 -> WITA 14:00
        mock_dt.now.return_value = mock_now
        assert get_time_of_day() == "afternoon"

    @patch("backend.services.whatsapp_context_builder.datetime")
    def test_evening(self, mock_dt: MagicMock) -> None:
        """17:00 - 04:59 WITA is evening."""
        mock_now = MagicMock()
        mock_now.hour = 12  # UTC 12:00 -> WITA 20:00
        mock_dt.now.return_value = mock_now
        assert get_time_of_day() == "evening"


# ============================================================================
# infer_client_type TESTS
# ============================================================================


class TestInferClientType:
    """Tests for infer_client_type function."""

    @pytest.mark.parametrize(
        "profile,expected_type",
        [
            ({"interests": ["retirement"]}, "retiree"),
            ({"visa_discussed": ["RETIREMENT"]}, "retiree"),
            ({"interests": ["company_setup"]}, "entrepreneur"),
            ({"visa_discussed": ["PMA"]}, "entrepreneur"),
            ({"interests": ["remote_work"]}, "digital_nomad"),
            ({"visa_discussed": ["E33G"]}, "digital_nomad"),
            ({"visa_discussed": ["E33"]}, "second_home_prospect"),
            ({"visa_discussed": ["SECOND HOME"]}, "second_home_prospect"),
            ({"visa_discussed": ["RUMAH KEDUA"]}, "second_home_prospect"),
            ({"visa_discussed": ["E33E"]}, "retiree"),
            ({"visa_discussed": ["E33F"]}, "retiree"),
            ({"interests": ["family_relocation"]}, "family_relocating"),
            ({"interests": ["investment"]}, "investor"),
            ({"visa_discussed": ["KITAS"]}, "potential_expat"),
            ({"visa_discussed": ["WORKING KITAS"]}, "potential_expat"),
            ({"visa_discussed": ["D12"]}, "visitor"),
            ({"visa_discussed": ["C1"]}, "visitor"),
            ({"visa_discussed": ["VOA"]}, "visitor"),
            ({}, "potential_client"),
            ({"interests": []}, "potential_client"),
        ],
        ids=[
            "retiree-interest",
            "retiree-visa",
            "entrepreneur-interest",
            "entrepreneur-visa",
            "nomad-interest",
            "nomad-visa",
            "second-home-e33",
            "second-home-english",
            "second-home-indonesian",
            "retiree-e33e",
            "retiree-e33f",
            "family",
            "investor",
            "expat-kitas",
            "expat-working",
            "visitor-d12",
            "visitor-c1",
            "visitor-voa",
            "empty-profile",
            "empty-interests",
        ],
    )
    def test_client_type_inference(self, profile: dict, expected_type: str) -> None:
        """Infer correct client type from profile data."""
        result = infer_client_type(profile)
        assert result == expected_type

    def test_priority_order(self) -> None:
        """Retirement takes priority over other interests."""
        profile = {
            "interests": ["retirement", "investment", "company_setup"],
            "visa_discussed": ["PMA", "KITAS"],
        }
        result = infer_client_type(profile)
        assert result == "retiree"


# ============================================================================
# build_context TESTS (Async + DB Mocking)
# ============================================================================


class TestBuildContext:
    """Tests for the async build_context function."""

    @pytest.mark.asyncio
    async def test_first_message_no_db(self) -> None:
        """First message without database returns defaults."""
        result = await build_context(
            phone="628123456789",
            sender_name="John Doe",
            message_text="Hello, I need help with KITAS",
            db_pool=None,
        )

        assert result["client_name"] == "John Doe"
        assert result["phone"] == "628123456789"
        assert result["is_first_message"] is True
        assert result["detected_language"] == "en"
        assert result["conversation_history"] == []
        assert result["client_profile"]["channel"] == "whatsapp"
        assert result["client_profile"]["phone"] == "+628123456789"
        assert result["client_profile"]["sender_name"] == "John Doe"
        assert "KITAS" in result["client_profile"]["visa_discussed"]
        assert result["time_of_day"] in ("morning", "afternoon", "evening")
        assert result["_wa_user_id"] == "whatsapp_628123456789"
        assert result["_session_id"] == "wa_session_628123456789"

    @pytest.mark.asyncio
    async def test_returning_user_with_db(self, mock_db_pool, sample_conversation_row) -> None:
        """Returning user loads conversation from database."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = sample_conversation_row

        result = await build_context(
            phone="628123456789",
            sender_name="Marco Rossi",
            message_text="Quanto costa?",
            db_pool=pool,
        )

        assert result["is_first_message"] is False
        assert len(result["conversation_history"]) == 3
        assert result["client_profile"]["sender_name"] == "Marco Rossi"
        assert result["client_profile"]["message_count"] == 4  # Was 3, +1
        assert result["_existing_row_id"] == 42

    @pytest.mark.asyncio
    async def test_db_read_failure_graceful(self, mock_db_pool) -> None:
        """Database read failure degrades gracefully."""
        pool, conn = mock_db_pool
        conn.fetchrow.side_effect = Exception("Connection refused")

        result = await build_context(
            phone="628123456789",
            sender_name="Test User",
            message_text="Hello",
            db_pool=pool,
        )

        # Should succeed with defaults despite DB error
        assert result["is_first_message"] is True
        assert result["client_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_db_write_failure_graceful(self, mock_db_pool, sample_conversation_row) -> None:
        """Database write failure for profile update is non-fatal."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = sample_conversation_row
        conn.execute.side_effect = Exception("Write failed")

        # Should not raise, just log warning
        result = await build_context(
            phone="628123456789",
            sender_name="Marco Rossi",
            message_text="Hello",
            db_pool=pool,
        )

        assert result["client_name"] == "Marco Rossi"

    @pytest.mark.asyncio
    async def test_profile_preserves_existing_data(self, mock_db_pool) -> None:
        """Existing profile data is preserved and merged."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = {
            "id": 10,
            "messages": json.dumps([{"role": "user", "content": "Ciao"}]),
            "metadata": json.dumps(
                {
                    "channel": "whatsapp",
                    "phone": "+628111",
                    "first_contact": "2026-01-01T00:00:00",
                    "visa_discussed": ["KITAS"],
                    "interests": ["company_setup"],
                    "message_count": 5,
                },
            ),
        }

        result = await build_context(
            phone="628111",
            sender_name="Test",
            message_text="What about PMA and retirement?",
            db_pool=pool,
        )

        profile = result["client_profile"]
        # Existing data preserved
        assert profile["first_contact"] == "2026-01-01T00:00:00"
        assert profile["message_count"] == 6  # Was 5, +1
        # New data merged
        assert "KITAS" in profile["visa_discussed"]
        assert "PMA" in profile["visa_discussed"]
        assert "company_setup" in profile["interests"]
        assert "retirement" in profile["interests"]

    @pytest.mark.asyncio
    async def test_metadata_as_string(self, mock_db_pool) -> None:
        """Handle metadata stored as JSON string (not pre-parsed)."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = {
            "id": 1,
            "messages": '[{"role": "user", "content": "Hi"}]',
            "metadata": '{"channel": "whatsapp", "message_count": 1}',
        }

        result = await build_context(
            phone="628222",
            sender_name="Test",
            message_text="Hello",
            db_pool=pool,
        )

        assert result["is_first_message"] is False
        assert result["client_profile"]["message_count"] == 2

    @pytest.mark.asyncio
    async def test_no_sender_name(self) -> None:
        """build_context works without sender_name."""
        result = await build_context(
            phone="628333",
            sender_name=None,
            message_text="Help me please",
            db_pool=None,
        )

        assert result["client_name"] is None
        assert "sender_name" not in result["client_profile"]

    @pytest.mark.asyncio
    async def test_empty_messages_in_db(self, mock_db_pool) -> None:
        """Handle empty messages array from database."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = {
            "id": 5,
            "messages": "[]",
            "metadata": "{}",
        }

        result = await build_context(
            phone="628444",
            sender_name="Empty",
            message_text="First message",
            db_pool=pool,
        )

        # Empty messages means "first message" behavior
        assert result["is_first_message"] is True

    @pytest.mark.asyncio
    async def test_profile_update_saved_to_db(self, mock_db_pool, sample_conversation_row) -> None:
        """Updated profile is written back to PostgreSQL."""
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = sample_conversation_row

        await build_context(
            phone="628123456789",
            sender_name="Marco Rossi",
            message_text="Tell me about retirement visa",
            db_pool=pool,
        )

        # Verify UPDATE was called with updated metadata
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "UPDATE conversations SET metadata" in call_args[0][0]
        # Metadata should be JSON string
        saved_metadata = json.loads(call_args[0][1])
        assert saved_metadata["message_count"] == 4

    @pytest.mark.asyncio
    async def test_client_type_inferred(self) -> None:
        """Client type is correctly inferred from detected data."""
        result = await build_context(
            phone="628555",
            sender_name="Nomad",
            message_text="I want E33G visa for remote work in Bali",
            db_pool=None,
        )

        assert result["client_profile"]["client_type"] == "digital_nomad"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestBuildContextIntegration:
    """Integration-style tests combining multiple functions."""

    @pytest.mark.asyncio
    async def test_full_italian_conversation_flow(self) -> None:
        """Simulate a full Italian user conversation."""
        # First message
        ctx1 = await build_context(
            phone="393331234567",
            sender_name="Giovanni",
            message_text="Ciao, vorrei aprire azienda a Bali. Quanto costa PMA?",
            db_pool=None,
        )

        assert ctx1["detected_language"] == "it"
        assert ctx1["is_first_message"] is True
        assert "PMA" in ctx1["client_profile"]["visa_discussed"]
        assert "company_setup" in ctx1["client_profile"]["interests"]
        assert ctx1["client_profile"]["client_type"] == "entrepreneur"

    @pytest.mark.asyncio
    async def test_interest_accumulation_across_messages(self) -> None:
        """Interests accumulate across messages when profile is loaded."""
        # Simulate loaded profile with existing interests
        mock_conn = AsyncMock()
        pool = MagicMock()
        pool.acquire.return_value = _create_async_cm(mock_conn)

        mock_conn.fetchrow.return_value = {
            "id": 1,
            "messages": json.dumps([{"role": "user", "content": "I want to invest"}]),
            "metadata": json.dumps(
                {
                    "interests": ["investment"],
                    "visa_discussed": [],
                    "message_count": 1,
                },
            ),
        }

        ctx = await build_context(
            phone="628666",
            sender_name="Multi",
            message_text="Also I need KITAS for my family",
            db_pool=pool,
        )

        profile = ctx["client_profile"]
        assert "investment" in profile["interests"]
        assert "family_relocation" in profile["interests"]
        assert "KITAS" in profile["visa_discussed"]



class TestVisaPatternLists:
    """Structural guard for the strict zip in extract_visa_mentions."""

    def test_visa_codes_and_patterns_same_length(self) -> None:
        """If these lists diverge, the strict zip in extract_visa_mentions raises."""
        assert len(VISA_CODES) == len(_VISA_PATTERNS)
