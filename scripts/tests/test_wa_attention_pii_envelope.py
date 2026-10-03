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

    +6280000000001 — +6280****0001

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

NOT changed, and deliberately so, AT THE TIME: the client's CRM `full_name`
still appeared, on the reasoning that an alert which cannot say WHO needs
attention is not an alert, and narrowing it was called a business call
(Legge 5) rather than a defect.

SUPERSEDED 2026-09-29 (spec_attention_alert_pii, Builder Contract §4): that
reasoning does not survive contact with the boundary it was weighed against.
§4 is explicit — "no ... alert ... may carry client PII in cleartext — use a
client_id, a hash, a placeholder or a redaction" — and a full name next to a
masked phone in a message bound for Telegram (cloud) is exactly the shape it
forbids. "The alerter needs to say WHO" is still true, and it is answered by
`client #<crm_id>`, not by the name: an opaque id says who to the operator
holding the CRM open, without saying who to Telegram's cloud. `crm_name` is
no longer even fetched (the SELECT that produced it was dropped), so a third
call site cannot reintroduce it by copying the old field name back in.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "wa-mirror-attention-telegram.py"


class _FakeAcquire:
    """Shared by every test that drives `cmd_digest()` end-to-end."""

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquire()

    async def close(self):
        return None


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
    label = wa.contact_label({"phone": "6280000000001", "crm_name": None, "crm_id": None})
    assert "6280000000001" not in label, f"the full number reached the alert: {label}"
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
    lead = {"phone": "6280000000001", "crm_name": None, "crm_id": None,
            "n_high": 2, "reasons": ["refund"]}
    known = {"phone": "6289988776655", "crm_name": "Test Client", "crm_id": 11580,
             "n_high": 1, "reasons": ["deadline"]}
    single = wa._compose_realtime_alert([("k1", lead, ["refund"])])
    roster = wa._compose_realtime_alert(
        [("k1", lead, ["refund"]), ("k2", known, ["deadline"])])
    for name, msg in (("single", single), ("roster", roster)):
        assert "6280000000001" not in msg, f"{name} branch leaked the full number:\n{msg}"
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


def _named_item(**extra) -> dict:
    """A contact carrying the SAME fixture name under every key contact_label()
    (or a mutant of it) could plausibly read.

    2026-09-29 gate condition C1(a) (kills M1d), verbatim from the gate's own
    list (pull/7635#issuecomment-5885487709): "Carry the synthetic name under
    crm_name, full_name, name, display_name and push_name". A guilt test that
    only sets `crm_name` only catches a mutant that reads `crm_name` — the
    fixture below leaks under any of those five field names equally
    (`push_name` being the WhatsApp-side profile name a mutant could plausibly
    reach for, alongside the four CRM-side spellings), so the assertion
    catches the ENTITY (a name reaching the alert) rather than one spelling
    of it.
    """
    base = {"crm_name": "Fixture Person", "full_name": "Fixture Person",
            "name": "Fixture Person", "display_name": "Fixture Person",
            "push_name": "Fixture Person"}
    base.update(extra)
    return base


def test_a_client_name_never_reaches_the_label(wa):
    """GUILT (2026-09-29, Builder Contract §4): a synthetic, obviously-fake
    name carried on the item — under every key the code could plausibly read
    it from — must never surface in the rendered label."""
    label = wa.contact_label(_named_item(phone="6289988776655", crm_id=11580))
    assert "Fixture Person" not in label, f"a client name reached the alert: {label}"


def test_the_realtime_alert_never_carries_a_client_name(wa):
    """GUILT, end-to-end through the real composer: single-contact AND roster
    are separate code paths, so both must be checked independently, exactly
    like the full-number sibling test above."""
    lead = {"phone": "6280000000001", "crm_name": None, "crm_id": None,
            "n_high": 2, "reasons": ["refund"]}
    known = _named_item(phone="6289988776655", crm_id=11580, n_high=1, reasons=["deadline"])
    single = wa._compose_realtime_alert([("k1", known, ["deadline"])])
    roster = wa._compose_realtime_alert(
        [("k1", lead, ["refund"]), ("k2", known, ["deadline"])])
    for label, msg in (("single", single), ("roster", roster)):
        assert "Fixture Person" not in msg, f"{label} branch leaked the client name:\n{msg}"


def test_the_digest_never_carries_a_client_name(wa, monkeypatch):
    """GUILT: the digest path is a THIRD rendering site (its own cron mode,
    'always sends', twice a day) and was the worst of the three historically —
    it must be checked independently, not inferred from the realtime tests."""
    known = _named_item(phone="6289988776655", crm_id=11580, crm_status="active",
                         lead_source="wa", n_high=1, reasons=["deadline"],
                         first_high_id=1, last_high_id=1, first_high_at=None, last_high_at=None)
    metrics = {"inbound_24h": 1, "distinct_phones_24h": 1, "high_open": 1,
               "high_resolved": 0, "medium": 0, "new_leads_24h": 0}
    sent: list[str] = []

    async def fake_create_pool(*_a, **_k):
        return _FakePool()

    async def fake_metrics(_conn):
        return metrics

    async def fake_fetch(_conn):
        return [known]

    def fake_send(text, tier="digest", dedup_key=""):
        sent.append(text)
        return True

    monkeypatch.setattr(wa.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(wa, "fetch_digest_metrics", fake_metrics)
    monkeypatch.setattr(wa, "fetch_high_unresolved", fake_fetch)
    monkeypatch.setattr(wa, "send_telegram", fake_send)
    asyncio.run(wa.cmd_digest())
    assert len(sent) == 1
    assert "Fixture Person" not in sent[0], f"the digest leaked the client name:\n{sent[0]}"
    assert "client #11580" in sent[0], f"the digest stopped identifying the client:\n{sent[0]}"


class _SqlRecorder:
    """Captures the SQL each selector actually SENDS (helper output included)."""

    def __init__(self):
        self.sql: list[str] = []

    async def fetch(self, q, *a):
        self.sql.append(q)
        return []

    async def fetchrow(self, q, *a):
        self.sql.append(q)
        return {}

    async def fetchval(self, q, *a):
        self.sql.append(q)
        return 0


def _rendered_selectors(wa) -> dict[str, list[str]]:
    out = {}
    for fn in (wa.fetch_high_unresolved, wa.fetch_digest_metrics):
        rec = _SqlRecorder()
        asyncio.run(fn(rec))
        out[fn.__name__] = rec.sql
    return out


ALLOWED_CLIENT_COLUMNS = {"id", "status", "lead_source", "phone_normalized", "deleted_at",
                          "created_by", "created_at"}
ALLOWED_EVENT_KEYS = {"key", "senderPn", "remoteJid", "remoteJidAlt"}
ALLOWED_HIGHS_OUTPUT = {"phone", "first_high_id", "last_high_id", "first_high_at",
                        "last_high_at", "n_high", "reasons", "crm_id", "crm_status",
                        "lead_source", "sender_digits", "high_open", "high_resolved",
                        "medium", "distinct_phones_24h", "inbound_24h"}


def test_the_rendered_sql_of_every_selector_selects_no_name(wa):
    """M1b/X1-X3, on the entity not the spelling. The SQL the selectors SEND is
    what leaves Postgres, and part of it is built by `sender_digits_sql` — so
    `inspect.getsource` of one function cannot see it (a `/* full_name */`
    injected in the helper survived the old pin). Three independent layers, all
    on the RENDERED text: (1) no `name` substring anywhere (full_name,
    company_name, pushName, push_name ...); (2) every `c.<col>` is on a column
    allow-list; (3) the raw event is only ever read at allow-listed JSON keys and
    every output alias is allow-listed."""
    import re

    for fn, queries in _rendered_selectors(wa).items():
        assert queries, fn
        for q in queries:
            assert not re.search(r"name", q, re.I), f"{fn}: a name-ish token in the SQL:\n{q}"
            for col in re.findall(r"\bc2?\.(\w+)", q):
                assert col in ALLOWED_CLIENT_COLUMNS, f"{fn}: clients.{col} is not allow-listed"
            for key in re.findall(r"->>?\s*'(\w+)'", q):
                assert key in ALLOWED_EVENT_KEYS, f"{fn}: event key {key!r} is not allow-listed"
            for alias in re.findall(r"\bAS\s+(\w+)", q):
                assert alias in ALLOWED_HIGHS_OUTPUT | {"unnest", "reason", "window_msgs", "highs"}, \
                    f"{fn}: output alias {alias!r} is not allow-listed"


def test_the_label_is_exactly_client_id_and_masked_phone(wa):
    """X2: even if a name column were fetched, the label must not render it.
    The fixture carries every name-shaped field a mutant might read."""
    row = {"phone": "6280000000001", "crm_id": 42, "company_name": "Fixture Co",
           "full_name": "Fixture Person", "crm_name": "Fixture Person",
           "display_name": "Fixture Person", "push_name": "Fixture Person"}
    assert wa.contact_label(row) == f"client #42 \u2014 {wa.mask_phone('6280000000001')}"
    lead = dict(row, crm_id=None)
    assert wa.contact_label(lead) == wa.mask_phone("6280000000001")


def test_the_digest_never_leaks_a_5plus_digit_run_of_the_phone(wa, monkeypatch):
    """M6: a defect need not print the WHOLE phone to leak it — any run of 5+
    consecutive digits from the raw number is already enough to re-identify
    the contact against another channel (CRM export, another mirror row).
    Checks a NEW LEAD (no crm_id) specifically, because that is the branch
    that had no mask_phone() at all before this file's first fix."""
    phone = "6280000000099"
    lead = {"phone": phone, "crm_name": None, "crm_id": None,
            "crm_status": None, "lead_source": None, "n_high": 1,
            "reasons": ["deadline"], "first_high_id": 1, "last_high_id": 1,
            "first_high_at": None, "last_high_at": None}
    metrics = {"inbound_24h": 1, "distinct_phones_24h": 1, "high_open": 1,
               "high_resolved": 0, "medium": 0, "new_leads_24h": 1}
    sent: list[str] = []

    async def fake_create_pool(*_a, **_k):
        return _FakePool()

    async def fake_metrics(_conn):
        return metrics

    async def fake_fetch(_conn):
        return [lead]

    def fake_send(text, tier="digest", dedup_key=""):
        sent.append(text)
        return True

    monkeypatch.setattr(wa.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(wa, "fetch_digest_metrics", fake_metrics)
    monkeypatch.setattr(wa, "fetch_high_unresolved", fake_fetch)
    monkeypatch.setattr(wa, "send_telegram", fake_send)
    asyncio.run(wa.cmd_digest())
    assert len(sent) == 1
    text = sent[0]
    for i in range(len(phone) - 4):
        window = phone[i:i + 5]
        assert window not in text, f"a 5-digit run of the phone leaked ({window}):\n{text}"
    # Codex council finding (2026-09-29, delta review of PR #7635's C1 round): the
    # gate asked for "renders masked only" — this test previously only checked for
    # the ABSENCE of a leak, so a mutant that silently dropped the contact line
    # from the digest entirely (an availability defect, not a privacy one, but
    # still not what "masked only" means) would have passed unnoticed. Assert the
    # masked form is actually present, exactly once.
    masked = wa.mask_phone(phone)
    assert text.count(masked) == 1, (
        f"the new lead's masked phone should appear exactly once, got {text.count(masked)}:\n{text}")


# ----------------------------------------------------------------- innocence
def test_a_known_client_is_still_identified_by_crm_id(wa):
    """INNOCENCE, and it is the point of the whole organ: an alert that cannot
    say WHO needs attention is not an alert. Masking the phone — and now
    dropping the name too — must not turn the roster into a list of
    anonymous stubs; the opaque CRM id is the operator's handle instead."""
    label = wa.contact_label(_named_item(phone="6289988776655", crm_id=11580))
    assert label.startswith("client #11580"), f"the client stopped being identified: {label}"
    assert "6655" in label, "the last-4 tail is the operator's handle — keep it"


def test_a_new_lead_shows_masked_phone_only(wa):
    """INNOCENCE: no crm_id (a genuinely new lead, unknown to the CRM) must
    render as the masked phone alone — no `client #None`, no stray marker."""
    label = wa.contact_label({"phone": "6280000000001", "crm_name": None, "crm_id": None})
    assert "client #" not in label, f"a lead with no CRM id got a client tag: {label}"
    assert label == wa.mask_phone("6280000000001")


def test_the_masked_tail_still_identifies_the_contact(wa):
    """INNOCENCE: two different numbers must still LOOK different after
    masking, or the operator cannot tell two unnamed leads apart and the fix
    has traded a privacy defect for a usability one."""
    a = wa.contact_label({"phone": "6280000000001", "crm_name": None})
    b = wa.contact_label({"phone": "6281399990000", "crm_name": None})
    assert a != b, "two distinct leads collapsed into one indistinguishable label"


def test_the_header_promise_matches_the_code(wa):
    """The docstring is the contract this file is judged against, so it must
    not drift back into describing behaviour the code no longer has."""
    head = SRC.read_text().split('"""')[1]
    assert "masked" in head, "the file stopped promising masking"


def test_the_osint_safe_list_never_claims_a_name_is_allowed(wa):
    """M7: guards the ALLOWED-fields bullet list specifically, not the whole
    docstring — this exact list used to say 'contact display_name' was one
    of the fields a Telegram message may contain, and the SAME docstring
    correctly says elsewhere ("full_name NEVER sent") that a name is NOT
    allowed, so a blanket 'full_name not in head' would false-positive on
    the very sentence that fixes this. Scoped to the bullet block between
    the promise line and the next blank line."""
    head = SRC.read_text().split('"""')[1]
    marker = "OSINT-safe: Telegram message contains only:"
    assert marker in head, "the OSINT-safe contract line itself is gone"
    bullet_block = head.split(marker, 1)[1].split("\n\n", 1)[0]
    for banned in ("display_name", "full_name", "crm_name", "display name"):
        assert banned not in bullet_block, (
            f"the allowed-fields list claims {banned!r} is sendable:\n{bullet_block}")


def test_compose_realtime_alert_docstring_never_promises_a_name(wa):
    """Self-discovered while mutation-testing C1(d) at PR #7635's delta review:
    the module HEADER docstring (guarded above) is not the ONLY stale-docstring
    site the gate flagged — `_compose_realtime_alert`'s OWN docstring (line
    ~386 at gate time) also said "display name" and was fixed in the same
    commit, but nothing pinned THAT fix specifically. Reverting just this
    function's docstring wording left every other test green (confirmed by
    hand: 14/14 passed with the old "display name" wording restored), which
    means this exact regression was previously invisible to the corpus."""
    doc = inspect.getdoc(wa._compose_realtime_alert) or ""
    assert "display name" not in doc, f"the composer's own docstring promises a name again:\n{doc}"
    assert "client #<crm_id>" in doc, f"the composer's docstring stopped describing the opaque id:\n{doc}"
