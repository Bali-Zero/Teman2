"""Tests for Drive Changes Polling Service."""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.crm.drive_poll_service import (
    DriveCircuitBreaker,
    _infer_document_type,
    _send_telegram_alert,
    poll_drive_changes,
)


# ── DriveCircuitBreaker tests ────────────────────────────────────


class TestDriveCircuitBreaker:
    """Tests for DriveCircuitBreaker dataclass."""

    def test_initial_state_is_closed(self) -> None:
        cb = DriveCircuitBreaker()
        assert cb.state == "closed"
        assert cb._failures == 0

    def test_record_success_resets(self) -> None:
        cb = DriveCircuitBreaker()
        cb._failures = 2
        cb._state = "half-open"
        cb.record_success()
        assert cb._failures == 0
        assert cb._state == "closed"

    def test_record_failure_increments(self) -> None:
        cb = DriveCircuitBreaker()
        cb.record_failure()
        assert cb._failures == 1
        assert cb._state == "closed"

    def test_opens_after_threshold(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb._state == "closed"
        cb.record_failure()
        assert cb._state == "open"

    def test_state_transitions_to_half_open(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=2, recovery_timeout=0)
        cb.record_failure()
        cb.record_failure()
        assert cb._state == "open"
        # Recovery timeout is 0, so it should transition
        time.sleep(0.01)
        assert cb.state == "half-open"

    def test_state_remains_open_before_timeout(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=2, recovery_timeout=9999)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_call_closed_success(self) -> None:
        cb = DriveCircuitBreaker()
        result_value: dict[str, Any] = {"status": "ok", "processed": 5}
        fn = AsyncMock(return_value=result_value)
        result = await cb.call(fn)
        assert result == result_value
        fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_open_returns_none(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=1)
        cb.record_failure()  # Opens the circuit
        fn = AsyncMock()
        result = await cb.call(fn)
        assert result is None
        fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_call_failure_opens_circuit(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=1)
        fn = AsyncMock(side_effect=RuntimeError("fail"))
        on_open = MagicMock()

        with pytest.raises(RuntimeError, match="fail"):
            await cb.call(fn, on_open=on_open)

        assert cb._state == "open"
        on_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_half_open_success_closes(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb._state == "open"
        time.sleep(0.01)
        # Now half-open
        fn = AsyncMock(return_value={"ok": True})
        result = await cb.call(fn)
        assert result == {"ok": True}
        assert cb._state == "closed"

    @pytest.mark.asyncio
    async def test_call_failure_without_on_open(self) -> None:
        cb = DriveCircuitBreaker(failure_threshold=1)
        fn = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            await cb.call(fn, on_open=None)


# ── _send_telegram_alert tests ───────────────────────────────────


class TestSendTelegramAlert:
    """Tests for _send_telegram_alert function."""

    def test_no_bot_token(self) -> None:
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}, clear=False):
            _send_telegram_alert("test alert")  # Should not raise

    def test_successful_send(self) -> None:
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_OWNER_CHAT_ID": "123"}, clear=False):
            with patch("backend.services.crm.drive_poll_service.urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.return_value = MagicMock()
                _send_telegram_alert("Circuit breaker open!")
                mock_urlopen.assert_called_once()

    def test_send_failure_caught(self) -> None:
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token"}, clear=False):
            with patch("backend.services.crm.drive_poll_service.urllib.request.urlopen", side_effect=Exception("network error")):
                _send_telegram_alert("test")  # Should not raise


# ── _infer_document_type tests ───────────────────────────────────


class TestInferDocumentType:
    """Tests for _infer_document_type function."""

    def test_passport(self) -> None:
        assert _infer_document_type("John_Passport.pdf", "00_Profile") == "passport"

    def test_paspor(self) -> None:
        assert _infer_document_type("paspor_scan.jpg", "00_Profile") == "passport"

    def test_kitas(self) -> None:
        assert _infer_document_type("KITAS_2026.pdf", "01_Immigration") == "kitas"

    def test_kitap(self) -> None:
        assert _infer_document_type("KITAP_permanent.pdf", "01_Immigration") == "kitas"

    def test_visa(self) -> None:
        assert _infer_document_type("visa_approval.pdf", "01_Immigration") == "visa"

    def test_evisa(self) -> None:
        assert _infer_document_type("e-visa_confirmation.pdf", "01_Immigration") == "visa"

    def test_voa(self) -> None:
        assert _infer_document_type("VOA_receipt.pdf", "01_Immigration") == "visa"

    def test_imk(self) -> None:
        assert _infer_document_type("IMK_notification.pdf", "01_Immigration") == "imk"

    def test_reentry(self) -> None:
        assert _infer_document_type("reentry_permit.pdf", "01_Immigration") == "imk"

    def test_itk(self) -> None:
        assert _infer_document_type("ITK_work_permit.pdf", "01_Immigration") == "itk"

    def test_akta(self) -> None:
        assert _infer_document_type("AKTA_pendirian.pdf", "02_Company") == "akta"

    def test_nib(self) -> None:
        assert _infer_document_type("NIB_certificate.pdf", "02_Company") == "nib"

    def test_oss(self) -> None:
        assert _infer_document_type("OSS_license.pdf", "02_Company") == "nib"

    def test_npwp(self) -> None:
        assert _infer_document_type("NPWP_company.pdf", "02_Company") == "npwp"

    def test_spt(self) -> None:
        assert _infer_document_type("SPT_tahunan.pdf", "03_Tax") == "spt"

    def test_lkpm(self) -> None:
        assert _infer_document_type("LKPM_report.pdf", "03_Tax") == "lkpm"

    def test_profile_perseroan(self) -> None:
        assert _infer_document_type("Profile Perseroan PT ABC.pdf", "02_Company") == "profile_perseroan"

    def test_company_profile(self) -> None:
        assert _infer_document_type("Company Profile.pdf", "02_Company") == "profile_perseroan"

    def test_fallback_by_folder_profile(self) -> None:
        assert _infer_document_type("random_file.pdf", "00_Profile") == "profile_document"

    def test_fallback_by_folder_immigration(self) -> None:
        assert _infer_document_type("random.pdf", "01_Immigration") == "immigration_document"

    def test_fallback_by_folder_company(self) -> None:
        assert _infer_document_type("random.pdf", "02_Company") == "company_document"

    def test_fallback_by_folder_tax(self) -> None:
        assert _infer_document_type("random.pdf", "03_Tax") == "tax_document"

    def test_fallback_by_folder_family(self) -> None:
        assert _infer_document_type("random.pdf", "04_Family") == "family_document"

    def test_fallback_by_folder_misc(self) -> None:
        assert _infer_document_type("random.pdf", "99_Misc") == "misc_document"

    def test_fallback_nested_akta(self) -> None:
        assert _infer_document_type("random.pdf", "AKTA") == "akta"

    def test_fallback_nested_nib(self) -> None:
        assert _infer_document_type("random.pdf", "NIB") == "nib"

    def test_fallback_unknown(self) -> None:
        assert _infer_document_type("random.pdf", "unknown_folder") == "other"

    def test_b211_visa(self) -> None:
        assert _infer_document_type("b211_approval.pdf", "01_Immigration") == "visa"

    def test_berusaha(self) -> None:
        assert _infer_document_type("izin_berusaha.pdf", "02_Company") == "nib"

    def test_itas(self) -> None:
        assert _infer_document_type("ITAS_permit.pdf", "01_Immigration") == "kitas"


# ── poll_drive_changes tests ─────────────────────────────────────


class TestPollDriveChanges:
    """Tests for poll_drive_changes function."""

    @pytest.mark.asyncio
    async def test_circuit_open_returns_status(self) -> None:
        with patch(
            "backend.services.crm.drive_poll_service._drive_circuit_breaker"
        ) as mock_cb:
            mock_cb.call = AsyncMock(return_value=None)
            result = await poll_drive_changes()
            assert result["status"] == "circuit_open"
            assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_error(self) -> None:
        with patch(
            "backend.services.crm.drive_poll_service._drive_circuit_breaker"
        ) as mock_cb:
            mock_cb.call = AsyncMock(side_effect=RuntimeError("boom"))
            mock_cb.failure_threshold = 3
            mock_cb.recovery_timeout = 300
            result = await poll_drive_changes()
            assert result["status"] == "error"
            assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_success_returns_result(self) -> None:
        expected: dict[str, Any] = {"status": "ok", "processed": 3, "changes": 5, "skipped": 2}
        with patch(
            "backend.services.crm.drive_poll_service._drive_circuit_breaker"
        ) as mock_cb:
            mock_cb.call = AsyncMock(return_value=expected)
            result = await poll_drive_changes()
            assert result == expected


# ── Nested folder tests ──────────────────────────────────────────


class TestInferDocumentTypeFolderMap:
    """Test that folder-based fallback covers all mapped folders."""

    def test_spt_company_folder(self) -> None:
        assert _infer_document_type("file.pdf", "spt company") == "spt_company"

    def test_spt_personal_folder(self) -> None:
        assert _infer_document_type("file.pdf", "spt personal") == "spt_personal"

    def test_lkpm_reports_folder(self) -> None:
        assert _infer_document_type("file.pdf", "lkpm reports") == "lkpm"

    def test_npwp_personal_folder(self) -> None:
        assert _infer_document_type("file.pdf", "npwp personal") == "npwp_personal"

    def test_profile_perseroan_folder(self) -> None:
        assert _infer_document_type("file.pdf", "profile perseroan") == "profile_perseroan"
