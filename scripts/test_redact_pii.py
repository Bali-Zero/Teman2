"""Unit tests for scripts/_redact_pii.py.

Verifies:
    - 4-pass ordering (team emails tokenised BEFORE generic email)
    - Symbiosis Law 2 OSINT block redaction (closed + unclosed)
    - Each identifier class (NPWP, NIB, KTP, KITAS, IMTA, passport,
      SHM, AKTA, AJB/PPJB, AHU)
    - Generic email NOT capturing team emails after team pass ran
    - IBAN strict (no false-positive on uppercase English words)
    - SWIFT BIC requires context label
    - Bank account preserves label, redacts only digits
    - Idempotency (panel R2 L4): redact twice = same output
    - Gate.min_remaining_chars triggers fail-closed
    - Gate.fail_on_error propagates rule errors

Run:
    cd ~/Desktop/nuzantara-wt-evoskill-phase1 && python3 -m pytest scripts/test_redact_pii.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from scripts._redact_pii import (
    Redactor,
    RedactionError,
    load_config,
)


@pytest.fixture
def redactor_no_dynamic() -> Redactor:
    """Redactor with config loaded but no dynamic CRM names (offline)."""
    config = load_config()
    return Redactor(config=config, runtime_names={
        "__DYNAMIC_CRM_CLIENT_NAMES__": [],
        "__DYNAMIC_CRM_COMPANY_NAMES__": [],
    })


@pytest.fixture
def redactor_with_names() -> Redactor:
    """Redactor with simulated CRM names for pass4 test."""
    config = load_config()
    return Redactor(config=config, runtime_names={
        "__DYNAMIC_CRM_CLIENT_NAMES__": ["Sofia Mueller", "Andrey Pozdnyakov"],
        "__DYNAMIC_CRM_COMPANY_NAMES__": ["PT Milkup", "CV Acme"],
    })


# ─── Pass 1: identifier patterns ─────────────────────────────────────


def test_npwp_formatted_dotted(redactor_no_dynamic):
    text = "Client NPWP is 12.345.678.9-012.345 (active). " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "12.345.678.9-012.345" not in out
    assert "[NPWP-REDACTED]" in out


def test_npwp_bare_with_context_preserves_label(redactor_no_dynamic):
    text = "Field NPWP: 123456789012345 mentioned in form. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "123456789012345" not in out
    assert "[NPWP-BARE-REDACTED]" in out
    assert "NPWP:" in out, "context label must be preserved"


def test_nib_with_context_label(redactor_no_dynamic):
    """NIB context-required (panel R2 finding: unconditional 13-digit eats bank+WA prefixes)."""
    text = "NIB: 1234567890123 issued. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "1234567890123" not in out
    assert "[NIB-REDACTED]" in out
    assert "NIB:" in out, "context label preserved"


def test_nib_bare_13_digits_NOT_redacted_without_context(redactor_no_dynamic):
    """13-digit bare without label is NOT a NIB (could be bank, JID, etc.)."""
    text = "Random 1234567890123 reference. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "1234567890123" in out, "bare 13-digit without NIB label must NOT be redacted"


def test_ktp_with_context_label(redactor_no_dynamic):
    text = "KTP: 1234567890123456 verified. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "1234567890123456" not in out
    assert "[KTP-REDACTED]" in out


def test_kitas_format(redactor_no_dynamic):
    text = "KITAS 2C12345678901 visa. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "2C12345678901" not in out
    assert "[KITAS-REDACTED]" in out


def test_imta_format(redactor_no_dynamic):
    text = "Permit IMTA/12345/2024 granted. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "IMTA/12345/2024" not in out
    assert "[IMTA-REDACTED]" in out


def test_passport_with_label_preserves(redactor_no_dynamic):
    text = "Passport No. AB1234567 holder. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "AB1234567" not in out
    assert "[PASSPORT-REDACTED]" in out
    assert "Passport No." in out


def test_shm_property_certificate(redactor_no_dynamic):
    text = "Property SHM No. 12345/Kerobokan recorded. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "12345/Kerobokan" not in out
    assert "[SHM-REDACTED]" in out


def test_akta_notarial_deed(redactor_no_dynamic):
    text = "Akta Notaris No. 42/2024 dated. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "42/2024" not in out
    assert "[AKTA-REDACTED]" in out


def test_ajb_property_deed(redactor_no_dynamic):
    text = "AJB No. 100/2025 registered. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "100/2025" not in out
    assert "[AJB-PPJB-REDACTED]" in out


def test_ahu_company_deed(redactor_no_dynamic):
    text = "Reference AHU-12345.AH.01.02.2024 issued. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "AHU-12345.AH.01.02.2024" not in out
    assert "[AHU-REDACTED]" in out


# ─── OSINT block (Symbiosis Law 2 hard gate) ─────────────────────────


def test_osint_block_closed_redacts_para2_and_para3(redactor_no_dynamic):
    """Panel R1 CRITICAL: lazy regex leaked Para2+. Closing tag fixes it."""
    text = "Public intro paragraph.\n\n[osint-internal]\nPara1 secret.\n\nPara2 ALSO secret.\n\nPara3 third para.\n[/osint-internal]\n\nPublic outro paragraph.\n" + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "Para1 secret" not in out, "Para1 must be redacted"
    assert "Para2 ALSO secret" not in out, "Para2 must NOT leak (panel R1 fix)"
    assert "Para3 third para" not in out, "Para3 must NOT leak"
    assert "[OSINT-INTERNAL-BLOCK-DROPPED]" in out
    assert "Public intro paragraph" in out
    assert "Public outro paragraph" in out


def test_osint_block_unclosed_falls_back_to_eof(redactor_no_dynamic):
    """Unclosed [osint-internal] block matches to EOF (defensive over-redact).

    Note: padding goes BEFORE the trigger, because the EOF fallback by
    design eats everything after the opening tag. Gate.min_remaining_chars
    is still satisfied by the padding before the tag.
    """
    text = (
        "Padding before block to satisfy gate.min_remaining_chars. " + "y" * 200
        + "\n\n[osint-internal]\nPara1 secret.\n\nPara2 still in block."
    )
    out = redactor_no_dynamic.redact(text)
    assert "Para1 secret" not in out
    assert "Para2 still in block" not in out
    assert "[OSINT-INTERNAL-BLOCK-DROPPED]" in out


# ─── Pass 2: team emails BEFORE generic ──────────────────────────────


def test_team_email_tokenised_first(redactor_no_dynamic):
    text = "Contact zero@balizero.com or surya@balizero.com please. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "zero@balizero.com" not in out
    assert "surya@balizero.com" not in out
    assert "[TEAM-EMAIL-REDACTED]" in out
    # MUST NOT be replaced with CLIENT-EMAIL (would mean team-pass missed
    # and generic-pass caught it)
    assert "[CLIENT-EMAIL-REDACTED]" not in out


def test_owner_personal_gmail_distinct_token(redactor_no_dynamic):
    text = "Personal: antonellosiano@gmail.com (do not contact). " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "antonellosiano@gmail.com" not in out
    assert "[OWNER-PERSONAL-EMAIL-REDACTED]" in out


def test_phone_e164(redactor_no_dynamic):
    text = "Call +62 812 3456 7890 anytime. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "+62 812 3456 7890" not in out
    assert "[PHONE-REDACTED]" in out


def test_phone_id_local_08xx(redactor_no_dynamic):
    text = "Mobile 08123456789 on file. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "08123456789" not in out
    assert "[PHONE-ID-LOCAL-REDACTED]" in out


def test_whatsapp_jid(redactor_no_dynamic):
    text = "Group JID 6281234567890@s.whatsapp.net active. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "6281234567890@s.whatsapp.net" not in out
    assert "[WA-JID-REDACTED]" in out


# ─── Pass 3: generic email + IBAN strict + SWIFT context ─────────────


def test_generic_client_email_after_team(redactor_no_dynamic):
    text = (
        "Team: zero@balizero.com. "
        "Client: john.smith@example.com. " + "x" * 100
    )
    out = redactor_no_dynamic.redact(text)
    # Both should be redacted, but with DIFFERENT tokens
    assert "zero@balizero.com" not in out
    assert "john.smith@example.com" not in out
    assert "[TEAM-EMAIL-REDACTED]" in out
    assert "[CLIENT-EMAIL-REDACTED]" in out


def test_iban_strict_no_false_positive_on_english_words(redactor_no_dynamic):
    """Panel R2 Codex MEDIUM L19: 'CRITICAL', 'DATABASE', 'PASSPORT' must NOT match IBAN."""
    text = (
        "This is a CRITICAL DATABASE PASSPORT problem with text. "
        "Real IBAN GB82WEST12345698765432 here. " + "x" * 100
    )
    out = redactor_no_dynamic.redact(text)
    # English words preserved
    assert "CRITICAL" in out
    assert "DATABASE" in out
    # PASSPORT in "PASSPORT problem" context shouldn't have been redacted
    # by IBAN rule (passport rule needs lowercase "passport" + No. label)
    # Real IBAN redacted
    assert "GB82WEST12345698765432" not in out
    assert "[IBAN-REDACTED]" in out


def test_swift_bic_requires_context_label(redactor_no_dynamic):
    """SWIFT 8-char codes only redacted when prefixed by BIC/SWIFT label."""
    text = "BIC code DEUTDEFF for wire transfer. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "DEUTDEFF" not in out
    assert "[SWIFT-BIC-REDACTED]" in out


def test_bank_account_with_label_preserves(redactor_no_dynamic):
    text = "Rekening BCA: 1234567890123 active. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "1234567890123" not in out
    assert "[BANK-ACCOUNT-REDACTED]" in out
    assert "Rekening" in out, "label preserved"


# ─── Pass 4: dynamic CRM names ───────────────────────────────────────


def test_dynamic_client_name_redacted(redactor_with_names):
    text = "Client Sofia Mueller signed yesterday. " + "x" * 100
    out = redactor_with_names.redact(text)
    assert "Sofia Mueller" not in out
    assert "[CLIENT-NAME-REDACTED]" in out


def test_dynamic_company_name_redacted(redactor_with_names):
    text = "Company PT Milkup registered with BKPM. " + "x" * 100
    out = redactor_with_names.redact(text)
    assert "PT Milkup" not in out
    assert "[COMPANY-NAME-REDACTED]" in out


def test_no_dynamic_names_no_op(redactor_no_dynamic):
    """When PG returns empty, pass4 is no-op (logs warning, doesn't fail)."""
    text = "Random name Sofia Mueller without PG data. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    # Without dynamic names loaded, "Sofia Mueller" is NOT redacted
    assert "Sofia Mueller" in out


# ─── Symbiosis Law 2 + internal patterns ─────────────────────────────


def test_ssh_alias_redacted(redactor_no_dynamic):
    text = "Run ssh pro to start. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "ssh pro" not in out
    assert "[MACHINE-ALIAS-REDACTED]" in out


def test_internal_ip_redacted(redactor_no_dynamic):
    text = "Mini at 100.93.236.6 reachable. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "100.93.236.6" not in out
    assert "[INTERNAL-IP-REDACTED]" in out


def test_fly_token_name_redacted(redactor_no_dynamic):
    text = "Secret FLY_API_TOKEN rotated. " + "x" * 100
    out = redactor_no_dynamic.redact(text)
    assert "FLY_API_TOKEN" not in out
    assert "[FLY-INTERNAL-REDACTED]" in out


# ─── Idempotency (panel R2 L4) ───────────────────────────────────────


def test_idempotency_double_apply_same_output(redactor_no_dynamic):
    text = (
        "Contact zero@balizero.com or call +62 812 3456 7890. "
        "NPWP 12.345.678.9-012.345 on file. "
        "Random sentence to pad to gate min." + "x" * 100
    )
    out1 = redactor_no_dynamic.redact(text)
    out2 = redactor_no_dynamic.redact(out1)
    assert out1 == out2, (
        "redactor MUST be idempotent — applying twice produced different "
        "output, which means a substitution token matches a redaction "
        "pattern (creates a loop)"
    )


# ─── Gate: fail-closed ───────────────────────────────────────────────


def test_gate_min_chars_fail_closed_when_input_too_redacted(redactor_no_dynamic):
    """If redaction drops below gate.min_remaining_chars, fail-closed."""
    # Just a closed OSINT block — almost everything gets dropped
    text = "[osint-internal]\n" + "secret " * 200 + "\n[/osint-internal]"
    with pytest.raises(RedactionError, match="too short"):
        redactor_no_dynamic.redact(text)


def test_gate_min_chars_fail_closed_on_empty_input(redactor_no_dynamic):
    with pytest.raises(RedactionError, match="empty"):
        redactor_no_dynamic.redact("")


def test_gate_min_chars_fail_closed_on_whitespace_only(redactor_no_dynamic):
    with pytest.raises(RedactionError, match="empty"):
        redactor_no_dynamic.redact("   \n  \t  \n")


# ─── Config load errors ──────────────────────────────────────────────


def test_load_config_missing_file_raises(tmp_path):
    missing = tmp_path / "nonexistent.yaml"
    with pytest.raises(RedactionError, match="not found"):
        load_config(missing)


# ─── Symbiosis Law 2 hardness: Kura Kura / BTID case ─────────────────


def test_kura_kura_btid_dossier_redacted(redactor_no_dynamic):
    """Kura Kura / BTID rule redacts rest of line by design (greedy [^\\n]+).

    Padding placed on a separate line to survive the rest-of-line redact.
    """
    text = (
        "Padding line 1 unrelated content to keep gate happy. " + "y" * 200 + "\n"
        + "Padding line 2 also unrelated text.\n"
        + "The Kura Kura Bali land deal involves PT BTID Serangan.\n"
        + "Padding line 4 after the dossier mention to ensure tail survives.\n"
    )
    out = redactor_no_dynamic.redact(text)
    assert "Kura Kura Bali" not in out
    assert "BTID Serangan" not in out
    assert "[INTERNAL-DOSSIER-REDACTED]" in out
    assert "Padding line 1" in out, "unrelated content before must survive"
    assert "Padding line 4" in out, "unrelated content after must survive"
