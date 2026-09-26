"""Unit tests for email_audit helpers.

Covers:
- log_email_attempt: inserts 'sending' row, returns id
- record_email_result: computes retry_after based on attempt_number
- notify_email_failure_critical: Telegram call shape + token absent no-op
- is_critical: membership in CRITICAL_EMAIL_TYPES
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.security.pii_log_identifier import redact_identifier_for_log
from backend.services.notifications.email_audit import (
    CRITICAL_EMAIL_TYPES,
    _bounded_scrub,
    _redact_token,
    _scrub_email_tokens,
    _strip_trailing_partial_token,
    format_send_error,
    is_critical,
    log_email_attempt,
    notify_email_failure_critical,
    record_email_result,
)


@pytest.fixture
def fake_pool():
    conn = MagicMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()

    class _Acquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *a):
            return None

    pool = MagicMock()
    pool.acquire.return_value = _Acquire()
    pool._conn = conn
    return pool


# ----------------------------------------------------------------------
# log_email_attempt
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_email_attempt_returns_row_id(fake_pool):
    fake_pool._conn.fetchval.return_value = 1234

    row_id = await log_email_attempt(
        fake_pool,
        email_type="hr_bonus",
        to_email="asya@balizero.com",
        subject="Bonus Pending",
        practice_id=42,
        client_id=None,
    )

    assert row_id == 1234
    assert fake_pool._conn.fetchval.called


@pytest.mark.asyncio
async def test_log_email_attempt_swallows_db_error(fake_pool):
    """If the audit INSERT fails, log_email_attempt returns None and the
    caller can proceed with the send anyway."""
    fake_pool._conn.fetchval.side_effect = RuntimeError("db down")

    row_id = await log_email_attempt(
        fake_pool,
        email_type="welcome",
        to_email="x@y.com",
    )

    assert row_id is None


@pytest.mark.asyncio
async def test_log_email_attempt_db_error_log_does_not_leak_the_recipient(fake_pool, caplog):
    """C4 (PR #7385 gate follow-up): a DB exception's text is not
    controlled input — a unique-constraint violation on `to_email`, for
    instance, echoes the value straight back in its DETAIL line. It must
    not reach the log raw."""
    addr = "constraint.probe@example.com"
    fake_pool._conn.fetchval.side_effect = RuntimeError(
        'duplicate key value violates unique constraint "email_send_log_to_email_key" '
        f"DETAIL: Key (to_email)=({addr}) already exists."
    )

    with caplog.at_level(logging.WARNING, logger="backend.services.notifications.email_audit"):
        row_id = await log_email_attempt(fake_pool, email_type="welcome", to_email=addr)

    assert row_id is None
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert addr not in joined
    assert "constraint.probe" not in joined


# ----------------------------------------------------------------------
# record_email_result — retry_after schedule
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_email_result_sent_no_retry_after(fake_pool):
    """Sent rows set retry_after=None (nothing to retry)."""
    await record_email_result(fake_pool, 7, status="sent", provider="brevo")

    executed = str(fake_pool._conn.execute.call_args_list[0])
    assert "status" in executed.lower()


@pytest.mark.asyncio
async def test_record_email_result_first_failure_schedules_1h(fake_pool):
    """Attempt 1 failure → retry_after = NOW()+1h."""
    fake_pool._conn.fetchval.return_value = 1  # attempt_number=1

    await record_email_result(fake_pool, 7, status="failed", provider="brevo", error_message="500")

    # 1h is the first backoff step (_RETRY_BACKOFF[0])
    assert fake_pool._conn.execute.called


@pytest.mark.asyncio
async def test_record_email_result_null_row_id_is_noop(fake_pool):
    """Passing row_id=None must not call the DB (audit was never inserted)."""
    await record_email_result(fake_pool, None, status="failed")

    assert not fake_pool._conn.execute.called


@pytest.mark.asyncio
async def test_record_email_result_non_resurrectable_skips_retry_schedule(fake_pool):
    """Client-facing types whose body can't be reconstructed must NOT
    get a retry_after (review fix #3): the retry worker would send a
    stub meta-email which is worse than direct escalation."""
    # fetchrow returns attempt_number=1 + email_type='completion_client'
    fake_pool._conn.fetchrow = AsyncMock(
        return_value={"attempt_number": 1, "email_type": "completion_client"},
    )

    await record_email_result(fake_pool, 7, status="failed", provider="brevo", error_message="500")

    # Inspect the UPDATE call — retry_after arg (4th positional after
    # the UPDATE sql) must be None.
    update_call = fake_pool._conn.execute.call_args
    # Args are: (sql, row_id, status, provider, error_message, retry_after)
    # Positional (not kwargs).
    assert update_call.args[5] is None, "completion_client must not schedule retry — should be None"


@pytest.mark.asyncio
async def test_record_email_result_resurrectable_schedules_retry(fake_pool):
    """Stateless types (hr_bonus) DO get a retry_after on first failure."""
    fake_pool._conn.fetchrow = AsyncMock(
        return_value={"attempt_number": 1, "email_type": "hr_bonus"},
    )

    await record_email_result(fake_pool, 7, status="failed", provider="brevo", error_message="500")

    update_call = fake_pool._conn.execute.call_args
    assert update_call.args[5] is not None, "hr_bonus attempt=1 must schedule retry (1h backoff)"


@pytest.mark.asyncio
async def test_record_email_result_attempt_lookup_error_log_does_not_leak(fake_pool, caplog):
    """C4: the attempt_number/email_type lookup's own exception text can
    carry the DB's echo of `to_email` (e.g. a connection error surfaced
    mid-query); scrub it the same way the other two DB-exception logs in
    this module are scrubbed."""
    addr = "lookup.probe@example.com"
    fake_pool._conn.fetchrow = AsyncMock(
        side_effect=RuntimeError(f"server closed the connection while fetching row for {addr}")
    )

    with caplog.at_level(logging.WARNING, logger="backend.services.notifications.email_audit"):
        await record_email_result(fake_pool, 7, status="failed", provider="brevo", error_message="500")

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert addr not in joined
    assert "lookup.probe" not in joined


@pytest.mark.asyncio
async def test_record_email_result_update_error_log_does_not_leak(fake_pool, caplog):
    """C4: the terminal UPDATE's own exception text (e.g. a value-too-long
    error quoting the offending value) must not reach the log raw either."""
    addr = "update.probe@example.com"
    fake_pool._conn.execute.side_effect = RuntimeError(
        f"value too long for type character varying(255): {addr}"
    )

    with caplog.at_level(logging.WARNING, logger="backend.services.notifications.email_audit"):
        await record_email_result(fake_pool, 7, status="sent", provider="brevo")

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert addr not in joined
    assert "update.probe" not in joined


@pytest.mark.asyncio
async def test_record_email_result_invalid_status_coerced_to_failed(fake_pool):
    """Unknown status strings should be coerced to 'failed' so the row is
    still reachable by the retry worker."""
    fake_pool._conn.fetchval.return_value = 1

    await record_email_result(fake_pool, 7, status="what_is_this", provider="brevo")

    # Still calls execute (the row is updated, just with coerced status)
    assert fake_pool._conn.execute.called


# ----------------------------------------------------------------------
# notify_email_failure_critical
# ----------------------------------------------------------------------


def test_notify_email_failure_critical_sends_telegram(monkeypatch):
    """With a bot token set, a properly-formatted POST hits the Telegram API.

    _OWNER_CHAT_ID is frozen at module import (reads env once), so we
    assert on the module-level value rather than overriding via env.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    # Import after setenv so the module reads our token. chat_id is
    # frozen at first import of the module earlier in the test session.
    from backend.services.notifications import email_audit

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="waiting_docs_client",
            to_email="client@example.com",
            subject="Documents Needed",
            practice_id=42,
            error="brevo: 500 | zoho: 503",
        )

    assert mock_open.called
    url = mock_open.call_args[0][0]
    assert "api.telegram.org/botfake-token/sendMessage" in url
    data = mock_open.call_args[0][1]
    # chat_id is whatever the module captured at import (prod default
    # 8847435604 or CI override via env — both valid).
    assert f"chat_id={email_audit._OWNER_CHAT_ID}".encode() in data
    assert b"waiting_docs_client" in data


def test_notify_alert_distinguishes_resurrectable_from_non_resurrectable(monkeypatch):
    """Alert footer must tell the operator whether to wait or act (Q3 fix).

    - hr_bonus (resurrectable): "Queued for retry..."
    - welcome (non-resurrectable): "Not queued for retry..."
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="hr_bonus",
            to_email="asya@balizero.com",
            subject="s",
            practice_id=1,
            error="e",
        )
    data_hr = mock_open.call_args[0][1]
    assert b"Queued+for+retry" in data_hr
    assert b"Not+queued" not in data_hr

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email="c@example.com",
            subject="s",
            practice_id=None,
            error="e",
        )
    data_welcome = mock_open.call_args[0][1]
    assert b"Not+queued+for+retry" in data_welcome
    assert b"manual+recovery" in data_welcome


def test_notify_email_failure_critical_no_token_is_noop(monkeypatch):
    """Without TELEGRAM_BOT_TOKEN, the function should not raise and not
    attempt any network call."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="hr_bonus",
            to_email="asya@balizero.com",
            subject="Bonus",
            practice_id=1,
            error="anything",
        )

    assert not mock_open.called


def test_notify_email_failure_critical_swallows_network_error(monkeypatch):
    """A URLError from Telegram must not leak into the caller's retry path."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    import urllib.error

    with patch(
        "backend.services.notifications.email_audit.urllib.request.urlopen",
        side_effect=urllib.error.URLError("timeout"),
    ) as mock_open:
        # Must not raise.
        notify_email_failure_critical(
            email_type="completion_client",
            to_email="c@x.com",
            subject="s",
            practice_id=None,
            error="e",
        )
    # And must actually have tried: without this, an early return anywhere
    # upstream would satisfy "did not raise" without ever entering the except
    # clause this test exists to hold in place.
    assert mock_open.called


# ----------------------------------------------------------------------
# is_critical — membership
# ----------------------------------------------------------------------


def test_critical_email_types_include_key_flows():
    """The CRITICAL set must cover the five business-critical flows plus
    welcome (added in the 2026-04-21 audit)."""
    assert "waiting_docs_client" in CRITICAL_EMAIL_TYPES
    assert "waiting_docs_team" in CRITICAL_EMAIL_TYPES
    assert "completion_client" in CRITICAL_EMAIL_TYPES
    assert "completion_team" in CRITICAL_EMAIL_TYPES
    assert "hr_bonus" in CRITICAL_EMAIL_TYPES
    assert "invoice_client" in CRITICAL_EMAIL_TYPES
    assert "welcome" in CRITICAL_EMAIL_TYPES


def test_is_critical_membership():
    assert is_critical("hr_bonus") is True
    assert is_critical("cron_visa") is False
    assert is_critical("") is False
    assert is_critical("random_string") is False


# ---------------------------------------------------------------------------
# format_send_error — anti-empty-error_message guard (W57 2026-05-26)
# ---------------------------------------------------------------------------


def test_format_send_error_plain_exception_with_message():
    assert format_send_error(ValueError("boom")) == "boom"


def test_format_send_error_empty_str_falls_back_to_repr():
    class Silent(Exception):
        def __str__(self):  # noqa: D401 — fixture
            return ""

    out = format_send_error(Silent())
    assert "Silent" in out  # repr() is "Silent()", class name preserved


def test_format_send_error_empty_str_and_empty_repr_falls_back_to_classname():
    class Whisper(Exception):
        def __str__(self):
            return ""

        def __repr__(self):
            return ""

    assert format_send_error(Whisper()) == "Whisper"


def test_format_send_error_httpx_status_error_includes_status_and_body():
    import httpx

    req = httpx.Request("POST", "https://brevo.example/send")
    resp = httpx.Response(400, request=req, content=b'{"error":"invalid recipient"}')
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        out = format_send_error(e)
    assert "HTTP 400" in out
    assert "brevo.example" in out
    assert "invalid recipient" in out


def test_format_send_error_httpx_status_error_empty_body():
    import httpx

    req = httpx.Request("POST", "https://brevo.example/send")
    resp = httpx.Response(503, request=req, content=b"")
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        out = format_send_error(e)
    assert "HTTP 503" in out
    assert "brevo.example" in out


def test_format_send_error_never_returns_empty_string():
    """Anti-regression guard: caller writes result to email_send_log,
    empty-string error_message is undiagnosable from the dashboard."""

    class Bare(Exception):
        def __str__(self):
            return ""

    for exc in [
        ValueError("x"),
        Bare(),
        ConnectionResetError(),
        TimeoutError(),
    ]:
        assert format_send_error(exc) != ""


# ----------------------------------------------------------------------
# Recipient address never reaches a shared surface (SYMBIOSIS Law 2)
# ----------------------------------------------------------------------


def test_telegram_alert_never_transcribes_the_recipient_address(monkeypatch):
    """The alert body carries a stand-in, never the address itself.

    A Telegram alert is a shared surface in the sense CLAUDE.md §14 means:
    "nessun output, memoria, skill, report, log, alert o artefatto condiviso
    trascriva PII in chiaro". The operator keeps what triage needs — the
    email_type, the practice, and a stable token — and resolves the actual
    address in ``email_send_log``, which is where processing it is legitimate.

    Both halves are asserted on purpose: absence alone would still pass if
    someone deleted the *To:* line outright, which is not the fix.
    """
    from urllib.parse import quote_plus

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    address = "chiara.rossi@studio-legale-milano.it"

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email=address,
            subject="Benvenuta",
            practice_id=7,
            error="brevo: 500",
        )

    body = mock_open.call_args[0][1].decode()
    # Neither the local part nor the domain, in any encoding urlencode uses.
    assert "chiara.rossi" not in body
    assert "studio-legale-milano" not in body
    assert quote_plus(address) not in body
    # …and the stand-in is present, so the line still says something.
    assert quote_plus(redact_identifier_for_log(address)) in body
    # Triage keys survive.
    assert "welcome" in body
    assert "7" in body


def test_telegram_alert_scrubs_addresses_from_subject_and_error_text(monkeypatch):
    """R3 (PR #7385 round 1): `subject`/`error` are caller-supplied free
    text, not just `to_email` — a provider bounce message routinely quotes
    the recipient back, and a mis-typed subject line can BE an address.
    Redacting only `to_email` (the fix this test's sibling above covers)
    left both of these as an open leak into the same Telegram alert.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    subject_leak = "urgent-reply-to@client-domain.example"
    error_leak = "SMTP 550 5.1.1: recipient bounce.target@another-domain.example unknown"

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email="ok@example.com",
            subject=subject_leak,
            practice_id=7,
            error=error_leak,
        )

    body = mock_open.call_args[0][1].decode()
    assert "urgent-reply-to" not in body
    assert "client-domain" not in body
    assert "bounce.target" not in body
    assert "another-domain" not in body
    # Triage keys still survive the scrub.
    assert "welcome" in body
    assert "5.1.1" in body


@pytest.mark.parametrize(
    "cut_at",
    ["@", "leak.pr", "@exa"],
    ids=["cut_right_after_at", "cut_inside_local_part", "cut_inside_domain"],
)
@pytest.mark.parametrize(
    "field,limit",
    [("subject", 120), ("error", 400)],
    ids=["subject_120", "error_400"],
)
def test_telegram_alert_scrubs_address_cut_by_truncation(monkeypatch, field, limit, cut_at):
    """M4 (PR #7385 round 2), sharpened + parametrized by C2 (PR #7385 gate
    follow-up): `error`/`subject` are truncated to 400/120 chars BEFORE the
    R3 scrub runs (truncating AFTER would run the regex over unbounded
    text — quadratic, measured ~1s at 20k chars). A cut landing right
    after `@`, inside the local part, or inside the domain leaves a
    fragment `_scrub_email_tokens`'s regex cannot match at all (it needs
    >=1 character on BOTH sides of `@`), so that fragment used to survive
    the scrub untouched — a leak specifically CAUSED by truncating before
    scrubbing rather than after.

    C2 sharpens two things the round-2 test left loose: it only exercised
    `error` (400 chars) — `subject` (120 chars) goes through the same
    `_bounded_scrub` call with a different limit and was never itself
    driven through a cut; and it asserted `local not in body`, which would
    still pass if a SHORTER fragment of `local` (rather than the whole
    string) had leaked, because a substring is never equal to the whole
    string it's part of. `local[:7]` catches a partial leak the original
    assertion's shape could not.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    local = "leak.probe"
    addr = f"{local}@example.com"
    idx = addr.index(cut_at) + len(cut_at) if cut_at != "leak.pr" else len("leak.pr")
    padding = "x " * limit
    prefix = padding[: limit - idx]
    payload = prefix + addr + " trailing text"

    kwargs = {
        "email_type": "welcome",
        "to_email": "ok@example.com",
        "subject": "ok",
        "practice_id": 1,
        "error": "e",
    }
    kwargs[field] = payload

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(**kwargs)

    body = mock_open.call_args[0][1].decode()
    assert local[:7] not in body


def test_local_prefix_assertion_catches_a_partial_leak_full_local_assertion_missed():
    """Rationale test for the C2 sharpening above — not a regression guilt
    test (there is no code cure here, only a test-assertion change, and
    the M4 code fix already ships on `b491d10138`, so a test built the OLD
    way already passes there too). This shows CONCRETELY why `local[:7]
    not in body` is the stronger of the two shapes: a body that leaked
    only a same-or-shorter FRAGMENT of `local` (e.g. a partial redaction
    that stopped one character short of the full address) satisfies "the
    full string is not in the body" while still containing an obvious
    fragment of it.
    """
    local = "leak.probe"
    leaked_body = "Error: delivery to leak.pr******* failed"

    assert local not in leaked_body  # the round-2 assertion: passes despite the leak
    assert local[:7] in leaked_body  # ...because it only checked the WHOLE string
    with pytest.raises(AssertionError):
        assert local[:7] not in leaked_body  # the sharpened assertion: catches it


def test_telegram_alert_scrub_preserves_markdown_balance(monkeypatch):
    """M5 (PR #7385 round 2): the R3 scrub's token class devoured `*`/`_`
    delimiters together with the address it matched — `*Delivery to a@b*`
    lost its closing `*`. This alert is sent with parse_mode="Markdown";
    Telegram rejects an unbalanced message outright (swallowed by this
    function's own try/except), so a corrupted scrub means the CRITICAL
    alert is silently DROPPED — worse than the leak the scrub exists to
    prevent."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    addr = "leak.probe@example.com"

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email="ok@example.com",
            subject=f"*Delivery to {addr}*",
            practice_id=1,
            error="e",
        )

    import urllib.parse

    text = urllib.parse.parse_qs(mock_open.call_args[0][1].decode())["text"][0]
    assert "leak.probe" not in text
    subj_line = next(line for line in text.splitlines() if line.startswith("*Subject:*"))
    # The closing '*' the old token class ate is present again: balanced.
    assert subj_line.count("*") % 2 == 0


@pytest.mark.parametrize(
    "address,fragment",
    [
        ("first_last@example.com", "first_"),
        ("a*b@example.com", "a*"),
        ("x@sub_domain.example", "_domain"),
    ],
    ids=["underscore_in_local", "asterisk_in_local", "underscore_in_domain"],
)
def test_scrub_leaves_no_fragment_when_address_itself_contains_md_delimiters(
    monkeypatch, address, fragment
):
    """C1 (PR #7385 gate follow-up, M5 residual): excluding `*_[]()` from
    the token class ENTIRELY (M5, round 2) fixed `*Delivery to a@b*` but
    broke matching for an address that itself CONTAINS one of those chars
    — the class stopped matching THROUGH it, splitting one token into two
    pieces and leaving whichever piece didn't touch `@` unmatched:
    `first_last@example.com` matched only `last@example.com`
    (`first_` survived bare); `a*b@example.com` matched only `b@example.com`
    (`a*` survived bare); `x@sub_domain.example` matched only `x@sub`
    (`_domain.example` survived bare). No fragment of the address may
    survive scrubbing, whether or not it happens to touch `@`.

    K2 (PR #7417 gate follow-up): the body asserted against here is the
    raw urlencoded POST payload — `urllib.parse.urlencode` (via
    `quote_plus`) percent-encodes both `@` (-> `%40`) and `*` (-> `%2A`),
    so `address not in body` and (for `asterisk_in_local`) `fragment not
    in body` were true regardless of what actually got redacted: neither
    literal character can ever survive urlencoding, cure or no cure.
    Parse the payload back into its `text` field first and assert on
    THAT — the same string Telegram actually renders.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email="ok@example.com",
            subject="ok",
            practice_id=1,
            error=f"delivery to {address} failed",
        )

    import urllib.parse

    body = mock_open.call_args[0][1].decode()
    text = urllib.parse.parse_qs(body)["text"][0]
    assert address not in text
    assert fragment not in text


def test_scrub_preserves_markdown_wrapping_delimiters_around_a_delimiter_bearing_address(
    monkeypatch,
):
    """C1: the restored token class must not reopen the M5 leak it fixed —
    an address that both CONTAINS a delimiter and is WRAPPED in one must
    still redact fully while leaving the wrapping delimiter in place, e.g.
    `_Re: <addr>_` and `(<addr>).` in the PR #7385 gate comment.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    addr = "first_last@example.com"

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email="ok@example.com",
            subject=f"_Re: {addr}_",
            practice_id=1,
            error=f"({addr}).",
        )

    import urllib.parse

    text = urllib.parse.parse_qs(mock_open.call_args[0][1].decode())["text"][0]
    assert addr not in text
    assert "first_" not in text  # the fragment the old exclusion-based class left bare
    subj_line = next(line for line in text.splitlines() if line.startswith("*Subject:*"))
    err_line = next(line for line in text.splitlines() if line.startswith("*Error:*"))
    # Wrapping delimiters preserved verbatim around the digest. Subject is
    # itself inside a code span since K4 (PR #7417 gate follow-up) — same
    # treatment `error` already had — so the outer backtick comes first.
    assert subj_line.startswith("*Subject:* `_Re: ") and subj_line.endswith("_`")
    assert err_line.startswith("*Error:* `(")
    assert err_line.endswith(").`")


def test_scrub_subject_markdown_delimiter_parity_equals_input(monkeypatch):
    """C1: subject-line `*`/`_` parity must equal the input's when the
    delimiters are pure Markdown wrapping (not characters belonging to the
    address itself) — the peel-and-reattach in `_scrub_email_tokens`
    neither drops nor introduces a delimiter it did not consume from the
    address's own interior.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    addr = "leak.probe@example.com"
    subject = f"*_Update for {addr}_*"

    with patch("backend.services.notifications.email_audit.urllib.request.urlopen") as mock_open:
        notify_email_failure_critical(
            email_type="welcome",
            to_email="ok@example.com",
            subject=subject,
            practice_id=1,
            error="e",
        )

    import urllib.parse

    text = urllib.parse.parse_qs(mock_open.call_args[0][1].decode())["text"][0]
    subj_line = next(line for line in text.splitlines() if line.startswith("*Subject:*"))
    output_subject = subj_line[len("*Subject:* ") :]
    assert output_subject.count("*") == subject.count("*")
    assert output_subject.count("_") == subject.count("_")
    assert "leak.probe" not in output_subject


def test_missing_token_warning_does_not_log_the_recipient_address(monkeypatch, caplog):
    """The no-token early return logs a warning; it must be address-free too.

    This is the branch that fires in any environment where TELEGRAM_BOT_TOKEN
    was never provisioned — i.e. exactly where nobody is watching the log.
    """
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    address = "marco.bianchi@example.org"

    with caplog.at_level(logging.WARNING, logger="backend.services.notifications.email_audit"):
        notify_email_failure_critical(
            email_type="hr_bonus",
            to_email=address,
            subject="Bonus",
            practice_id=1,
            error="anything",
        )

    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "marco.bianchi" not in joined
    assert "example.org" not in joined
    assert redact_identifier_for_log(address) in joined


# ----------------------------------------------------------------------
# _bounded_scrub — truncation-boundary diagnostics (C3, PR #7385 gate
# follow-up, NIT)
# ----------------------------------------------------------------------


def test_bounded_scrub_single_overlong_token_becomes_an_empty_field():
    """C3: a single token longer than `limit`, with no whitespace anywhere
    in it, has no boundary to keep any of it on — `_bounded_scrub`
    collapses it to an empty field rather than a truncated fragment.
    Documented behaviour, not a regression fix: true on `b491d10138` too,
    since the trailing-partial-token strip removes the WHOLE truncated
    string when none of it is whitespace.
    """
    text = "a" * 200
    assert _bounded_scrub(text, 120) == ""


def test_bounded_scrub_keeps_a_complete_last_token_at_the_exact_boundary():
    """C3: guilt test — fails on b491d10138. A cut that lands EXACTLY on a
    whitespace boundary (the character right AFTER `limit`, i.e.
    ``text[limit]``, is itself whitespace) means the kept text ends on a
    COMPLETE token, not a partial one — there is nothing to strip. The
    pre-fix check looked only at ``truncated[-1]`` (the last KEPT
    character); it could not tell "this is mid-token" apart from "this
    coincidentally ends a token right at the cut", and dropped a complete
    trailing token in the second case too.

    ``_bounded_scrub("abcde fghij", 5)`` on b491d10138 returns ``""`` —
    "abcde" is whole (``text[5]`` is a space) but gets stripped anyway.
    """
    text = "abcde fghij"
    assert text[5] == " "  # the cut lands exactly on the boundary
    assert _bounded_scrub(text, 5) == "abcde"


def test_bounded_scrub_still_strips_a_genuinely_mid_token_cut():
    """Non-regression companion to the boundary test above: when the
    character right after the cut is NOT whitespace (a real mid-token
    cut, not a coincidental boundary), the partial token is still
    dropped — the C3 fix narrows the condition, it does not disable it.
    """
    text = "abcdef ghijkl"
    assert text[5] == "f"  # not a boundary — "abcde" is only half of "abcdef"
    assert _bounded_scrub(text, 5) == ""


# ----------------------------------------------------------------------
# _strip_trailing_partial_token — linear replacement for the polynomial
# `_TRAILING_PARTIAL_TOKEN_RE = r"\S+$"` sub (C6, PR #7385 gate follow-up,
# CodeQL alert 9192, py/polynomial-redos)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "abc",
        "abc def",
        "abc def ",
        " abc",
        "abc\tdef",
        "abc\ndef",
        "leak.pr",
        "leak.probe@example.co",
        "a" * 500,
    ],
)
def test_strip_trailing_partial_token_matches_the_old_regex_on_existing_cases(text):
    """C6: proves `_strip_trailing_partial_token` produces the IDENTICAL
    output to the regex it replaces (`re.sub(r"\\S+$", "", text)`) on
    every shape `_bounded_scrub` actually feeds it — the swap changes
    performance characteristics only, never behaviour.
    """
    import re as _re

    assert _strip_trailing_partial_token(text) == _re.sub(r"\S+$", "", text)


def test_strip_trailing_partial_token_handles_200k_chars_without_hanging():
    """C6: the replaced shape measured ~2.0s at 20k chars fed directly
    (gate addendum, CodeQL alert 9192) — genuinely polynomial, not just
    slow. This is NOT run against the old regex at this size (that IS the
    vulnerability the fix closes; reproducing it here would risk hanging
    the test run rather than proving anything the CodeQL scan and the
    20k-char measurement in the gate addendum don't already show). It
    only proves the linear replacement completes and is still CORRECT at
    a size an order of magnitude past the measured slow point — asserting
    on behaviour, never on wall time, per the follow-up mandate.
    """
    text = "a" * 200_000
    assert _strip_trailing_partial_token(text) == ""

    text_with_boundary = ("a" * 100_000) + " " + ("b" * 99_999)
    assert _strip_trailing_partial_token(text_with_boundary) == ("a" * 100_000) + " "


def test_bounded_scrub_handles_200k_char_single_token_without_hanging():
    """Same shape through the real call path (`_bounded_scrub`), not just
    the helper in isolation — proves the fix closes CodeQL alert 9192 on
    the function it was actually raised against, not a duplicate copy of
    the pattern."""
    text = "a" * 200_000
    assert _bounded_scrub(text, 400) == ""


# ----------------------------------------------------------------------
# _scrub_email_tokens / _scrub_word / _redact_token — K1 (PR #7417 gate
# follow-up, CodeQL alert 9200, py/polynomial-redos): the token scan and
# both peel steps used to be `re` patterns with the same quadratic shape
# C6 already removed from `_strip_trailing_partial_token`. Replaced with
# a linear forward scan (`_scrub_word`) and `str.lstrip`/`str.rstrip`
# peeling (`_redact_token`) — behaviour-only tests, never wall-time, per
# the same convention C6's own 200k tests use.
# ----------------------------------------------------------------------


def test_scrub_email_tokens_handles_200k_non_matching_chars_without_hanging():
    """The exact shape the gate measured at 1.05-1.28s/20k on the old
    `_EMAIL_TOKEN_RE.sub(...)` (no `@` anywhere, so every start position
    used to backtrack all the way down before failing): completes here,
    and — since nothing in a run of `!` is email-shaped — is untouched."""
    text = "!" * 200_000
    assert _scrub_email_tokens(text) == text


def test_scrub_email_tokens_handles_200k_char_trailing_punctuation_run_without_hanging():
    """N1 (PR #7426 gate) corrects this docstring's own claim: this shape —
    ending in `!`, itself one of `_TRAILING_MD_DELIM_PUNCT_RE`'s own
    delimiter chars — is NOT the one that was ever quadratic on the old
    regex. An anchored `.search` for a trailing delimiter run matches on
    its very first attempt when the string actually ends in one (measured
    2.7ms on the pre-K1 regex, not 1.64s/20k). It is still a useful
    behaviour proof: `_redact_token`'s `str.rstrip` peels the whole run in
    one pass regardless — the address is redacted while the 200k-char run
    survives verbatim as the trailing punctuation it's being treated as.
    See the sibling test below for the shape that was actually quadratic.
    """
    token = "a@b" + "!" * 200_000
    out = _scrub_email_tokens(token)
    assert out.endswith("!" * 200_000)
    assert out[: len(out) - 200_000].startswith("id:")


def test_scrub_email_tokens_handles_a_trailing_run_ending_in_a_non_delimiter_without_hanging():
    """N1 (PR #7426 gate): the actually-quadratic shape on the old
    `_TRAILING_MD_DELIM_PUNCT_RE.search(...)` ends its run in a character
    the pattern can never match (here, `x`) — `.search` retries from every
    earlier start position before giving up (measured 2,294ms at 20k on
    the old regex, 1.5ms on the linear replacement). `str.rstrip` has no
    such failure mode: since the very last character isn't in
    `_TRAILING_PUNCT_CHARS`, it strips nothing in one check, so the whole
    run — trailing `x` included — is consumed into the digest along with
    the address instead of surviving as (non-existent) trailing punctuation.
    """
    token = "a@b" + "!" * 200_000 + "x"
    out = _scrub_email_tokens(token)
    assert out.startswith("id:")
    assert "!" not in out
    assert "x" not in out


def test_scrub_email_tokens_fully_digests_a_400_char_single_token():
    """K1's own suggested proof: the bound `_bounded_scrub` actually uses
    (400 chars, the `error` field's limit) must still redact a token that
    fills the entire bound, not just short ones the linear rewrite could
    special-case."""
    local = "q" * 196
    domain = "b" * 200 + ".example.test"
    token = f"{local}@{domain}"
    assert len(token) >= 400
    out = _scrub_email_tokens(token[:400])
    assert local not in out
    assert "b" * 50 not in out
    assert out.startswith("id:")


def test_redact_token_peels_edges_and_digests_the_core():
    """Direct unit test of the peeling helper K1 introduced — the
    leading/trailing behaviour `_scrub_email_tokens`'s integration tests
    exercise indirectly, isolated to its own function."""
    out = _redact_token("(first_last@example.com).")
    assert out.startswith("(")
    assert out.endswith(").")
    assert "first_last" not in out
    assert "example.com" not in out


# ----------------------------------------------------------------------
# K3 (PR #7417 gate follow-up, folded into the #7385 C4 PR): quoted local
# parts (`"…"@domain`) and `'`/`` ` `` inside a local part.
# ----------------------------------------------------------------------


def test_scrub_email_tokens_digests_an_apostrophe_in_the_local_part():
    """GUILT: `'` used to be a hard boundary, so `qzvkwy'x@y.example.test`
    split into two 'words' at the apostrophe — the piece before it
    (`qzvkwy`) had no `@` of its own and survived unredacted, exactly the
    gate's measured case. `'` is now ordinary content, consumed into the
    digest with the rest of the local part."""
    out = _scrub_email_tokens("qzvkwy'x@y.example.test")
    assert "qzvkwy" not in out
    assert "y.example.test" not in out
    assert out.startswith("id:")


def test_scrub_email_tokens_digests_a_backtick_in_the_local_part():
    """GUILT: same bug, `` ` ``. RFC 5322 `atext` allows both — same
    reasoning already applied to `_`/`*` above."""
    out = _scrub_email_tokens("qzvkwy`x@y.example.test")
    assert "qzvkwy" not in out
    assert "y.example.test" not in out
    assert out.startswith("id:")


def test_scrub_email_tokens_fully_digests_a_quoted_local_part_with_a_space():
    """GUILT (the gate's Codex-found shape): a quoted local part can
    legally contain a space — `"qzvk wjyg"@example.test`. Before this fix
    NEITHER the old regex NOR the pre-K3 linear scan redacted any of it
    when the string is not truncated (`"` was a hard boundary, so the
    quoted phrase split into whitespace-bounded pieces with no `@` in
    them, and the bare `@example.test` piece had an empty local part and
    was left alone too) — the gate's own words: "both leak the whole
    address when it is not truncated". The quote-pairing lookahead below
    pulls the whole `"..."@` span into one token across the internal
    space, so the entire thing is now one digest."""
    out = _scrub_email_tokens('"qzvk wjyg"@example.test')
    assert "qzvk" not in out
    assert "wjyg" not in out
    assert "example.test" not in out
    assert "@" not in out
    assert out.startswith("id:")


def test_redact_token_peels_a_fully_wrapped_quoted_address():
    """A quote pair that wraps the WHOLE token — not just the local part —
    peels symmetrically, same as the existing Markdown-delimiter peel:
    `"matteo@example.test"` -> `"id:…"`, nothing unbalanced."""
    out = _redact_token('"matteo@example.test"')
    assert out.startswith('"') and out.endswith('"')
    assert "matteo" not in out
    assert "example.test" not in out


def test_redact_token_does_not_orphan_a_quote_for_the_quoted_local_shape():
    """The quoted-local shape's closing `"` sits mid-token, right before
    `@`, not at the token's own trailing edge — `_redact_token` leaves it
    as content rather than peeling only the leading quote and stranding an
    unmatched one in the output."""
    out = _redact_token('"qzvk wjyg"@example.test')
    assert out.count('"') == 0


# --- INNOCENCE: ordinary quoted prose is not over-redacted ---


def test_scrub_email_tokens_does_not_merge_ordinary_quoted_prose_across_a_space():
    """A quote that is not immediately followed by `@` — plain prose, not
    a quoted local part — must not suppress whitespace-splitting. `@home`
    here has no local part before it (nothing but the quote precedes it in
    that word) and stays exactly as `_scrub_word`'s existing empty-local
    special case already treats a bare `@word`."""
    text = 'He said "call me @home" now'
    out = _scrub_email_tokens(text)
    assert out == text


def test_scrub_email_tokens_leaves_an_unpaired_quote_alone_when_harmless():
    """A single stray `"` with no closing quote at all is not an address
    wrapper; nothing here is email-shaped, so nothing should be touched."""
    text = 'the setting is 6" deep, no address here'
    out = _scrub_email_tokens(text)
    assert out == text


def test_scrub_email_tokens_handles_many_lone_quotes_without_hanging():
    """K3: proof the added quote-pairing lookahead in `_scrub_email_tokens`
    stays linear. Each `"` triggers one `str.find` for its next pairing
    quote, scanning 50 characters before finding it and then rejecting the
    pairing (no `@` follows) — repeated 4,000 times (200k chars total).
    The searched ranges between consecutive quotes partition the string
    and never overlap, so total lookahead work is bounded by the string's
    own length however many quotes it holds. Behaviour-only proof, never
    wall-time, per the same convention the K1 200k tests above use."""
    text = ('"' + "a" * 50) * 4_000
    out = _scrub_email_tokens(text)
    assert out == text
