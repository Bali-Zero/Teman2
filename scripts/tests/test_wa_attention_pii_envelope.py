"""The masker was defeated by its own fallback, in three places.

`wa-mirror-attention-telegram.py` opens by declaring its own contract:

    OSINT-safe: Telegram message contains only:
    - contact display_name + phone (last 4 digits masked)

Measured against the code, that promise was false for the case the alerter
exists to surface. Both realtime compose paths did:

    display = it.get("crm_name") or f"+{phone}"
    ...
    f"{display} — {mask_phone(phone)}"

For a contact the CRM does not know — a NEW LEAD — `display` fell back to the
FULL number, and the masked form was printed right beside it:

    +6281312415572 — +6281****5572

The masking was never bypassed. It was made pointless by a fallback standing
next to it. The digest path had the same defect and worse: no `mask_phone()`
alongside at all, so the raw number was the ONLY rendering — in a mode whose
docstring says "Always sends", twice a day. And `mask_phone` itself returned
`f"+{phone}"` for anything shorter than 6 digits: the one function whose job is
not to emit a bare number emitted one, from inside its own guard clause.

Why the digest site survived the first pass, recorded because it is the
reusable part: the census grepped for the FORM of the line already found
(`display`, `phone`). The digest says `name` and `it['phone']`. A pattern
written from the instance you found catches the instance you found (W113). It
took an AST sweep — every f-string that renders anything named `phone` — to see
all four, and that sweep is now a test, so the next site cannot hide behind a
different variable name.

UU PDP Art. 67-68 / SYMBIOSIS Law 2. The severity here does not rest on a
reading of the law: the file's own docstring already promised masking, so this
is a breach of a declared contract, not a judgement call.

NOT changed, and deliberately so: the client's CRM `full_name` still appears.
That is the alerter's whole purpose — an alert that cannot say WHO needs
attention is not an alert — and narrowing it is a business call (Legge 5), not
a defect to fix unilaterally.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "wa-mirror-attention-telegram.py"


@pytest.fixture(scope="module")
def wa(tmp_path_factory):
    """Import the hyphenated script by path, in a throwaway world.

    HOME is redirected before the import because this module does real work at
    import time: it reads ~/.wa-mirror.env and mkdirs ~/.cache for its state
    file. A test must never touch production state (W96), and here that is not
    theoretical — the state file it would create is the live 4h dedup ledger.

    WA_MIRROR_DATABASE_URL is a throwaway string. Nothing in this corpus opens
    a connection; the variable exists only because the module exits at import
    without it. That exit, plus a config reader that consulted only the env
    FILE, is exactly why this file had no tests until now.
    """
    home = tmp_path_factory.mktemp("home")
    prev = {k: os.environ.get(k) for k in ("HOME", "WA_MIRROR_DATABASE_URL")}
    os.environ["HOME"] = str(home)
    os.environ["WA_MIRROR_DATABASE_URL"] = "postgresql://test/none"
    try:
        spec = importlib.util.spec_from_file_location("wa_attention", SRC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wa_attention"] = mod
        try:
            spec.loader.exec_module(mod)
        except ImportError as exc:  # asyncpg absent on a bare runner
            pytest.skip(f"dependency missing: {exc}")
        assert Path(mod.STATE_PATH).is_relative_to(home), (
            f"the import escaped the throwaway HOME: {mod.STATE_PATH}")
        yield mod
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --------------------------------------------------------------------- guilt
def test_a_contact_the_crm_does_not_know_is_never_rendered_in_the_clear(wa):
    """THE defect, verbatim: a new lead has no crm_name, and that is exactly
    the contact this alerter is for."""
    label = wa.contact_label({"phone": "6281312415572", "crm_name": None, "crm_id": None})
    assert "6281312415572" not in label, f"the full number reached the alert: {label}"
    assert "****" in label, f"nothing was masked: {label}"


def test_a_short_number_is_masked_more_not_less(wa):
    """`mask_phone` returned the whole string when it was too short to apply
    prefix(4)+suffix(4) — the masker leaking from inside its own guard."""
    out = wa.mask_phone("12345")
    assert "12345" not in out, f"a short number came back in the clear: {out}"
    assert wa.mask_phone("") == "+?"


def test_the_realtime_alert_never_carries_a_full_number(wa):
    """End-to-end through the real composer, single-contact AND roster: the
    two branches are separate code paths and the leak lived in both."""
    lead = {"phone": "6281312415572", "crm_name": None, "crm_id": None,
            "n_high": 2, "reasons": ["refund"]}
    known = {"phone": "6289988776655", "crm_name": "Test Client", "crm_id": 11580,
             "n_high": 1, "reasons": ["deadline"]}
    single = wa._compose_realtime_alert([("k1", lead, ["refund"])])
    roster = wa._compose_realtime_alert(
        [("k1", lead, ["refund"]), ("k2", known, ["deadline"])])
    for name, msg in (("single", single), ("roster", roster)):
        assert "6281312415572" not in msg, f"{name} branch leaked the full number:\n{msg}"
        assert "6289988776655" not in msg, f"{name} branch leaked the full number:\n{msg}"


def test_every_fstring_that_renders_a_phone_goes_through_a_masker(wa):
    """The sweep that found the digest site, kept as the guard.

    Grepping for the line shape that had already been found could only ever
    re-find it. This walks the AST instead and asks a question about the
    ENTITY: does anything named `phone` reach an f-string without passing a
    masker?

    TIGHTENED 2026-08-08: there used to be ONE declared exception — the local
    4h dedup state key `f"{phone}:{sorted(critical)[0]}"`, which never left the
    machine (Law 2 draws the line at output, not at local processing). The
    episode-tier change removed that f-string: episodes are keyed on the phone
    value directly, so the exception no longer exists and the invariant is now
    absolute. The count assertion below moved from `== 1` to `== 0` because the
    exception went away, NOT because it was waived — and it is kept, rather
    than deleted, so that reintroducing an undeclared local-state f-string
    still has to come past this test and be argued for.
    """
    allowed = ("mask", "contact_label", "distinct_phones", "phone[:4]", "phone[-4:]")
    offenders = []
    for node in ast.walk(ast.parse(SRC.read_text())):
        if not isinstance(node, ast.JoinedStr):
            continue
        for value in node.values:
            if not isinstance(value, ast.FormattedValue):
                continue
            rendered = ast.unparse(value.value)
            if "phone" in rendered and not any(a in rendered for a in allowed):
                offenders.append((node.lineno, rendered))
    local_state = [o for o in offenders if o[1] == "phone"]
    leaks = [o for o in offenders if o not in local_state]
    assert not leaks, f"an unmasked phone reaches a message: {leaks}"
    assert local_state == [], (
        "a bare-phone f-string is back; if it is genuinely local-only state, "
        f"declare it in the source and in this docstring first: {local_state}")


# ----------------------------------------------------------------- innocence
def test_a_known_client_is_still_named(wa):
    """INNOCENCE, and it is the point of the whole organ: an alert that cannot
    say WHO needs attention is not an alert. Masking the phone must not turn
    the roster into a list of anonymous stubs."""
    label = wa.contact_label({"phone": "6289988776655", "crm_name": "Test Client",
                              "crm_id": 11580})
    assert label.startswith("Test Client"), f"the client stopped being named: {label}"
    assert "6655" in label, "the last-4 tail is the operator's handle — keep it"


def test_the_masked_tail_still_identifies_the_contact(wa):
    """INNOCENCE: two different numbers must still LOOK different after
    masking, or the operator cannot tell two unnamed leads apart and the fix
    has traded a privacy defect for a usability one."""
    a = wa.contact_label({"phone": "6281312415572", "crm_name": None})
    b = wa.contact_label({"phone": "6281399990000", "crm_name": None})
    assert a != b, "two distinct leads collapsed into one indistinguishable label"


def test_the_header_promise_matches_the_code(wa):
    """The docstring is the contract this file is judged against, so it must
    not drift back into describing behaviour the code no longer has."""
    head = SRC.read_text().split('"""')[1]
    assert "masked" in head, "the file stopped promising masking"
