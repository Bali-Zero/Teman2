"""Guilt + innocence for scripts/_redact_pii.py pass4 (dynamic CRM names) word
boundaries. A `\\b` on a name whose first or last character is punctuation
("Zed Q. Invented.", "(Xyl Fakename)") never matches next to a space or the end
of the text, so the name went to the external reviewer in cleartext. Every name
and sentence below is invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _redact_pii import Redactor, load_config  # noqa: E402

PAD = (
    " This invented filler sentence only exists to clear the redactor's"
    " minimum-remaining-length gate, nothing in it is a real person."
)
CLIENTS = ["Zed Q. Invented.", "(Xyl Fakename)", "Vex Imaginary", "Wex Spacey ", "   ", ""]
COMPANIES = ["Fictiva Holdings Ltd.", "-Nullcorp Testing"]


@pytest.fixture
def redactor() -> Redactor:
    return Redactor(config=load_config(), runtime_names={
        "__DYNAMIC_CRM_CLIENT_NAMES__": CLIENTS,
        "__DYNAMIC_CRM_COMPANY_NAMES__": COMPANIES,
    })


@pytest.fixture
def redactor_no_names() -> Redactor:
    return Redactor(config=load_config(), runtime_names={
        "__DYNAMIC_CRM_CLIENT_NAMES__": [],
        "__DYNAMIC_CRM_COMPANY_NAMES__": [],
    })


@pytest.mark.parametrize("text, leaked", [
    ("Payment from Zed Q. Invented. was received with the usual reference.", "Invented."),
    ("The last signer on the draft deed was Zed Q. Invented.", "Invented."),
    ("Joined: Zed Q. Invented.Next step is the visa file.", "Zed Q"),
    ("Witness (Xyl Fakename) countersigned the invented draft deed.", "Xyl Fakename"),
    ("Invoice for Fictiva Holdings Ltd. is pending approval this week.", "Fictiva"),
    ("Vendor -Nullcorp Testing sent an invented quote last month.", "Nullcorp"),
    ("We met Wex Spacey. The file is ready for review.", "Wex Spacey"),
    ("A lowercase mention: vex imaginary asked about the invented KITAS.", "vex imaginary"),
])
def test_punctuation_edged_name_is_redacted(redactor, text, leaked):
    out = redactor.redact(text + PAD)
    assert leaked.lower() not in out.lower(), out


@pytest.mark.parametrize("text", [
    "Vexing Imaginaryness is a made-up word, not the client name in the list.",
    "aVex Imaginary glued to a word character is not the client name either.",
    "def redact_fragment(text): return Path('scripts/_redact_pii.py').read_text()",
    "Google, Anthropic and Microsoft are public companies the policy leaves alone.",
])
def test_neighbouring_text_is_unchanged(redactor, redactor_no_names, text):
    assert redactor.redact(text + PAD) == redactor_no_names.redact(text + PAD)
