"""
PII redaction tests for the Sentry `before_send` hook.

We process NPWP, NIB, passport numbers, emails, phone numbers and client
identifiers on every request. If any of those fields leak into Sentry, we
violate UU PDP (Indonesian data protection law) and Bali Zero client trust.

These tests drive the shape of the `before_send` hook in
`backend.app.setup.sentry_config`. They construct synthetic Sentry event
payloads that mirror the structure of real events (request body/query,
exception locals, breadcrumbs, log messages) and assert that every known
PII field is redacted before the event would be shipped.

Rule: the hook MUST NEVER let any of the following leave the process:
- npwp, nib, tax_id, passport (Indonesian tax/ID numbers)
- email, phone (contact PII)
- client_id, name, surname (identity PII)
- any free-text containing an email-shaped substring
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from backend.app.setup.sentry_config import (
    PII_REDACTION_PLACEHOLDER,
    _before_send,
    _init_sentry_blocking,
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Sentinel values we scan events for. If any of these strings survive
# `_before_send`, the test fails.
PII_SAMPLES: dict[str, str] = {
    "npwp": "01.234.567.8-901.000",
    "nib": "1234567890123",
    "tax_id": "98.765.432.1-000.000",
    "passport": "A12345678",
    "email": "zero@balizero.com",
    "phone": "+62 812 3456 7890",
    "client_id": "CL-000142",
    "name": "Antonello",
    "surname": "Siano",
    # Added 2026-08-02 with the free-text tests below. Deliberately sequential,
    # like every other value here: these are sentinels, and a sentinel that
    # could be mistaken for a real identifier is a liability in a public repo.
    "nik": "1234567890123456",
    "phone_local": "081234567890",
    "phone_jid": "6281234567890",
    # Added 2026-08-25 (GARUDA VOA L4 magic-link auth, CodeQL
    # py/clear-text-storage-sensitive-data #8755 review): the router's raw
    # magic-link bearer and the session secret it establishes on success.
    "token": "t0k3n-aB3dEf9K2mN8pQ7rS5uV1wX6yZ",
    "account_session_secret": "sess-9xQ2mK7vL4pR8tY1wZ3nC6hJ0aB",
}


def _walk(obj: Any):
    """Yield every str leaf in a nested dict/list/tuple structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk(v)


def _assert_no_pii(event: dict[str, Any]) -> None:
    """Assert no PII sentinel value and no email-shaped string survives."""
    assert event is not None, "event was dropped entirely; tests expect redaction, not drop"
    leaked: list[str] = []
    for leaf in _walk(event):
        for label, sample in PII_SAMPLES.items():
            if sample in leaf:
                leaked.append(f"{label}={sample!r} leaked in {leaf!r}")
        if EMAIL_RE.search(leaf) and PII_REDACTION_PLACEHOLDER not in leaf:
            leaked.append(f"email-shaped string leaked: {leaf!r}")
    assert not leaked, "PII leaked through before_send:\n  " + "\n  ".join(leaked)


# --------------------------------------------------------------------------- #
# 0. Init configuration — frame locals bypass `_before_send` entirely
#
# `_before_send` walks the JSON-shaped event Sentry hands it, but the SDK
# attaches raw frame-LOCAL values to `stacktrace.frames[].vars` at capture
# time, before `before_send` ever runs, whenever `include_local_variables`
# is left at its default of `True`. A value that only ever exists as a bare
# local (e.g. `garuda_result_session` / `result_session_secret` in
# `garuda_portal_auth.py`, never as a dict key `_scrub` walks) leaks
# regardless of how complete `_PII_KEY_SUBSTRINGS` is — no amount of key-based
# redaction downstream can reach it. The only structural fix is telling the
# SDK not to collect locals at all.
# --------------------------------------------------------------------------- #
def test_init_sentry_disables_local_variable_capture(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_init(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("sentry_sdk.init", fake_init)
    _init_sentry_blocking("https://example.invalid/1")

    assert captured.get("include_local_variables") is False, (
        "sentry_sdk.init must be called with include_local_variables=False — "
        "otherwise frame locals bypass _before_send's key-based redaction entirely"
    )


# --------------------------------------------------------------------------- #
# 1. Request body — JSON with PII fields
# --------------------------------------------------------------------------- #
def test_redacts_request_body_json():
    event = {
        "request": {
            "method": "POST",
            "url": "https://api/example/clients",
            "data": {
                "name": PII_SAMPLES["name"],
                "surname": PII_SAMPLES["surname"],
                "email": PII_SAMPLES["email"],
                "phone": PII_SAMPLES["phone"],
                "npwp": PII_SAMPLES["npwp"],
                "nib": PII_SAMPLES["nib"],
                "passport": PII_SAMPLES["passport"],
            },
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 2. Request body — nested under "json"
# --------------------------------------------------------------------------- #
def test_redacts_nested_request_json():
    event = {
        "request": {
            "data": {
                "client": {
                    "id": PII_SAMPLES["client_id"],
                    "contact": {
                        "email": PII_SAMPLES["email"],
                        "tax_id": PII_SAMPLES["tax_id"],
                    },
                }
            }
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 3. Query string — PII in URL params
# --------------------------------------------------------------------------- #
def test_redacts_query_string_params():
    event = {
        "request": {
            "query_string": (
                f"client_id={PII_SAMPLES['client_id']}"
                f"&email={PII_SAMPLES['email']}"
                f"&nib={PII_SAMPLES['nib']}"
            ),
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 4. URL itself — PII in path segment (less common but possible)
# --------------------------------------------------------------------------- #
def test_redacts_email_in_url():
    event = {
        "request": {
            "url": f"https://api/example/clients/{PII_SAMPLES['email']}/profile",
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 5. Exception stacktrace — PII in frame locals
# --------------------------------------------------------------------------- #
def test_redacts_stacktrace_locals():
    event = {
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "bad input",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "backend/app/routers/clients.py",
                                "function": "create_client",
                                "vars": {
                                    "client_id": PII_SAMPLES["client_id"],
                                    "email": PII_SAMPLES["email"],
                                    "npwp": PII_SAMPLES["npwp"],
                                    "name": PII_SAMPLES["name"],
                                    "surname": PII_SAMPLES["surname"],
                                    "request_body": {
                                        "phone": PII_SAMPLES["phone"],
                                        "passport": PII_SAMPLES["passport"],
                                    },
                                },
                            }
                        ]
                    },
                }
            ]
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 6. Exception value — email embedded in error message string
# --------------------------------------------------------------------------- #
def test_redacts_email_in_exception_value():
    event = {
        "exception": {
            "values": [
                {
                    "type": "LookupError",
                    "value": f"no client found for {PII_SAMPLES['email']}",
                }
            ]
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 7. Breadcrumbs — PII in breadcrumb data
# --------------------------------------------------------------------------- #
def test_redacts_breadcrumb_data():
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "category": "http",
                    "message": f"POST /clients — {PII_SAMPLES['email']}",
                    "data": {
                        "client_id": PII_SAMPLES["client_id"],
                        "nib": PII_SAMPLES["nib"],
                    },
                }
            ]
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 8. Top-level message string containing email
# --------------------------------------------------------------------------- #
def test_redacts_email_in_log_message():
    event = {
        "message": f"Failed to notify {PII_SAMPLES['email']} about renewal",
        "level": "error",
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 9. User context — Sentry's built-in user dict. send_default_pii=False
# already covers IP/user.id but we still sanitize explicit email/username.
# --------------------------------------------------------------------------- #
def test_redacts_user_context():
    event = {
        "user": {
            "email": PII_SAMPLES["email"],
            "username": PII_SAMPLES["name"],
            "id": PII_SAMPLES["client_id"],
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 10. Extra / contexts — free-form dicts developers attach ad-hoc
# --------------------------------------------------------------------------- #
def test_redacts_extra_and_contexts():
    event = {
        "extra": {
            "payload": {
                "email": PII_SAMPLES["email"],
                "npwp": PII_SAMPLES["npwp"],
            }
        },
        "contexts": {
            "client": {
                "client_id": PII_SAMPLES["client_id"],
                "surname": PII_SAMPLES["surname"],
                "tax_id": PII_SAMPLES["tax_id"],
            }
        },
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# 11/12. GARUDA VOA L4 magic-link auth (2026-08-25, CodeQL #8755 review) —
# the raw magic-link bearer and the account-session secret it establishes.
# Mirrors the frame-locals shape from test #5 above: these are exactly the
# names that would appear as dict keys if a future `MagicLinkStore` adapter's
# kwargs, or `MagicLinkExchange.token`, ended up in a Sentry breadcrumb/frame.
# --------------------------------------------------------------------------- #
def test_redacts_magic_link_token_in_stacktrace_locals():
    event = {
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "store blew up",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "backend/app/routers/garuda_portal_auth.py",
                                "function": "exchange_magic_link",
                                "vars": {"token": PII_SAMPLES["token"]},
                            }
                        ]
                    },
                }
            ]
        }
    }
    _assert_no_pii(_before_send(event, {}))


def test_redacts_account_session_secret_in_extra():
    event = {
        "extra": {
            "outcome_kwargs": {
                "account_session_secret": PII_SAMPLES["account_session_secret"],
                "result_session_secret": PII_SAMPLES["account_session_secret"],
            }
        }
    }
    _assert_no_pii(_before_send(event, {}))


# --------------------------------------------------------------------------- #
# Positive control — "token" is EXACT-match only (see sentry_config.py
# comment), because this codebase logs `max_tokens`/`token_count`/`tokenizer`
# constantly for LLM call debugging. If "token" were ever widened to a
# substring match, this test goes red and that is the point: it is the
# tripwire for the exact regression the review warned against.
# --------------------------------------------------------------------------- #
def test_llm_token_usage_fields_survive_redaction():
    event = {
        "extra": {
            "max_tokens": 4096,
            "token_count": 812,
            "tokenizer": "cl100k_base",
            "input_tokens": 512,
            "output_tokens": 128,
        }
    }
    scrubbed = _before_send(event, {})
    assert scrubbed is not None
    extra = scrubbed["extra"]
    assert extra["max_tokens"] == 4096
    assert extra["token_count"] == 812
    assert extra["tokenizer"] == "cl100k_base"
    assert extra["input_tokens"] == 512
    assert extra["output_tokens"] == 128


# --------------------------------------------------------------------------- #
# Positive controls — debug fields whose name CONTAINS "name" as a substring
# must survive the scrubber, otherwise every Sentry stacktrace becomes
# unreadable. Regression guard for review #168/B1.
# --------------------------------------------------------------------------- #
def test_filename_key_survives_redaction():
    event = {
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "boom",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "backend/app/routers/clients.py",
                                "function": "create_client",
                                "lineno": 42,
                            }
                        ]
                    },
                }
            ]
        }
    }
    scrubbed = _before_send(event, {})
    assert scrubbed is not None
    frame = scrubbed["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["filename"] == "backend/app/routers/clients.py"
    assert frame["function"] == "create_client"
    assert frame["lineno"] == 42


def test_function_name_key_survives_redaction():
    # Fields developers attach ad-hoc to extra/contexts to aid debugging —
    # if any of these got redacted, Sentry would be less useful than logs.
    event = {
        "extra": {
            "function_name": "handle_webhook",
            "transaction_name": "POST /api/visa/submit",
            "endpoint_name": "visa.submit",
            "module_name": "backend.app.routers.visa",
            "hostname": "nuzantara-rag-app-01",
            "codename": "eagle",
            "nickname": "visa-worker-A",
        }
    }
    scrubbed = _before_send(event, {})
    assert scrubbed is not None
    extra = scrubbed["extra"]
    assert extra["function_name"] == "handle_webhook"
    assert extra["transaction_name"] == "POST /api/visa/submit"
    assert extra["endpoint_name"] == "visa.submit"
    assert extra["module_name"] == "backend.app.routers.visa"
    assert extra["hostname"] == "nuzantara-rag-app-01"
    assert extra["codename"] == "eagle"
    assert extra["nickname"] == "visa-worker-A"


# --------------------------------------------------------------------------- #
# Resilience: if _scrub raises, _before_send MUST NOT let the exception
# propagate (Sentry drops events silently when before_send raises).
# Regression guard for review #168/B3.
# --------------------------------------------------------------------------- #
def test_before_send_handles_scrub_exception(monkeypatch, capsys):
    # Force the inner implementation to blow up on any input.
    import backend.app.setup.sentry_config as mod

    def boom(*_a, **_kw):
        raise RuntimeError("scrubber exploded")

    monkeypatch.setattr(mod, "_before_send_impl", boom)

    event = {
        "level": "error",
        "exception": {"values": [{"type": "ValueError", "value": "original error"}]},
        "extra": {"should_be_stripped": PII_SAMPLES["email"]},
    }
    result = _before_send(event, {})

    # Hook must NOT raise.
    assert result is not None
    # Minimal event preserves diagnosis-relevant fields.
    assert result["level"] == "error"
    assert result["exception"] == event["exception"]
    # ...and marks itself so the Sentry UI flags these.
    # The exception is still KEPT — but it now passes through the scrubber on its
    # own (see test_the_exception_fallback_still_redacts_what_it_keeps). This
    # assertion used to be an exact-dict comparison, which is why the second tag
    # broke it; the tag says whether the exception survived that second pass.
    assert result["tags"]["sentry_hook_error"] == "true"
    assert result["tags"]["sentry_exception_dropped"] == "false"
    # Any other content (incl. unscrubbed PII) is stripped defensively.
    assert "extra" not in result
    # Failure surfaced to stderr so fly logs catch it.
    captured = capsys.readouterr()
    assert "scrubber exploded" in captured.err
    assert "_before_send raised" in captured.err


# --------------------------------------------------------------------------- #
# 14. FREE TEXT — the surface the key-based rules cannot see
#
# Every test above puts PII inside a dict whose KEY names it, so `_is_pii_key`
# does the work. A log message has no keys. `LoggingIntegration` is a DEFAULT
# Sentry integration (level=INFO -> breadcrumb, event_level=ERROR -> event), so
# every `logger.*` call in the process is a candidate — and until 2026-08-02
# free text was covered by email + `CL-\d{3,}` only. Measured before the fix,
# through this very hook: passport, phone, NPWP, NIB and client name all
# survived `_before_send` and would have left the process.
# --------------------------------------------------------------------------- #
# Composed from PII_SAMPLES, never from fresh literals: one place holds the
# synthetic sentinels, and the file's documented convention is to extend that
# dict when a new PII-bearing field appears.
# label -> (log line, the exact value that must NOT survive it).
# Carrying the secret alongside the message is the point: asserting only that
# "[REDACTED]" appears would pass a PARTIAL redaction that still ships half a
# phone number. Codex flagged exactly that on the first draft of this file.
#
# The separator variants are not decoration. The first draft matched contiguous
# digits only, so `0812 3456 7890` — how a human actually types it into the CRM
# field these messages quote — walked straight through.
FREE_TEXT_GUILTY: dict[str, tuple[str, str]] = {
    "passport labelled": (
        f"OCR done, passport {PII_SAMPLES['passport']} extracted",
        PII_SAMPLES["passport"],
    ),
    "npwp formatted": (
        f"Registered with NPWP {PII_SAMPLES['npwp']} today",
        PII_SAMPLES["npwp"],
    ),
    "nib labelled": (f"NIB {PII_SAMPLES['nib']} registered", PII_SAMPLES["nib"]),
    "nik labelled": (f"NIK: {PII_SAMPLES['nik']} verified", PII_SAMPLES["nik"]),
    "phone intl spaced": (
        f"Timeout sending WhatsApp message to {PII_SAMPLES['phone']}",
        PII_SAMPLES["phone"],
    ),
    "phone intl solid": (
        f"from=+{PII_SAMPLES['phone_jid']} body empty",
        PII_SAMPLES["phone_jid"],
    ),
    "phone intl parenthesised": ("callback to +62 (812) 3456-7890 failed", "3456-7890"),
    "phone local 08": (
        f"Empty text body from {PII_SAMPLES['phone_local']}",
        PII_SAMPLES["phone_local"],
    ),
    "phone local spaced": ("Welcome message sent to 0812 3456 7890", "0812 3456 7890"),
    "phone local dashed": ("Triage decision for 0812-3456-7890: escalate", "0812-3456-7890"),
    "phone whatsapp jid": (
        f"conversation {PII_SAMPLES['phone_jid']} archived",
        PII_SAMPLES["phone_jid"],
    ),
    "email": (f"Clock-in: {PII_SAMPLES['email']} at 09:00", PII_SAMPLES["email"]),
}

# A redactor that eats timestamps is worse than no redactor: the breadcrumb
# exists to diagnose, and every one of these shapes is ordinary log traffic.
# The two `+`-prefixed integers were added after GLM pointed out that the first
# draft redacted `+12345678`, which in a repo that logs rupiah deltas and byte
# offsets is far likelier to be money than a phone number.
FREE_TEXT_INNOCENT: tuple[str, ...] = (
    "elapsed_ms=1754044800000 for job run",
    "created_at=1754044800 ok",
    "latency drift +12.345678901 sec",
    "revenue delta +12345678 IDR this month",
    "offset +1234567890 bytes written",
    "trace 6d449787-04e3-430e-acbe-d6fc38d379a9 ok",
    "wrote /data/1234567890123.json",
    "starting zantara v0.8.12 (build 20260801)",
    "rows=1234567890 tokens_used=98765 status=200",
    "GET /api/clients 200 in 1234.5678ms",
    "commit 9a6a30a38 deployed",
    "indexed 93283 vectors in 6281 batches",
)


@pytest.mark.parametrize("label", sorted(FREE_TEXT_GUILTY))
def test_free_text_identifier_is_redacted_in_a_breadcrumb(label):
    """A log line carrying an identifier must not leave the process intact."""
    message, secret = FREE_TEXT_GUILTY[label]
    event = {"breadcrumbs": {"values": [{"category": "log", "message": message}]}}
    out = _before_send(event, {})
    got = out["breadcrumbs"]["values"][0]["message"]
    assert PII_REDACTION_PLACEHOLDER in got, f"{label}: nothing was redacted in {got!r}"
    assert secret not in got, f"{label}: the value itself survived in {got!r}"


def test_accepted_collateral_a_62_prefixed_count_is_redacted():
    """Declared over-redaction, pinned so nobody "fixes" it into a leak.

    An 11-14 digit integer starting with 62 is byte-identical to a WhatsApp JID,
    and the dominant real leak shape in this codebase is `logger.info("... %s",
    phone)` — bare, unlabelled, no @s.whatsapp.net suffix. There is no rule that
    keeps the JID and spares the counter, so the counter loses: over-redaction
    costs a diagnostic, under-redaction is a UU PDP breach.
    """
    message = "indexed 6281234567890 tokens in 1 pass"
    event = {"breadcrumbs": {"values": [{"category": "log", "message": message}]}}
    out = _before_send(event, {})
    got = out["breadcrumbs"]["values"][0]["message"]
    assert PII_REDACTION_PLACEHOLDER in got, (
        "this is the ACCEPTED collateral of the JID rule; if it no longer fires, "
        "check that the JID rule itself still does"
    )


@pytest.mark.parametrize("message", FREE_TEXT_INNOCENT)
def test_ordinary_log_traffic_survives_free_text_redaction(message):
    """Innocence: a timestamp, a UUID or a byte count is not an identifier."""
    event = {"breadcrumbs": {"values": [{"category": "log", "message": message}]}}
    out = _before_send(event, {})
    got = out["breadcrumbs"]["values"][0]["message"]
    assert got == message, (
        f"redaction damaged ordinary log output:\n  before: {message!r}\n  after:  {got!r}"
    )


def test_known_gap_a_bare_personal_name_in_free_text_is_not_redactable():
    """DECLARED LIMIT, pinned so nobody reads the cure as wider than it is.

    `logger.info(f"Created client {id}: {client.full_name}")` produces a name in
    a sentence, and a name has no regex-recognisable shape — catching it needs
    NER (`backend/middleware/pii_scanner.py`, Presidio), which cannot live on
    the error path of a hook that must never itself raise. The only real fix is
    the call site: do not log the value. Flip this test the day the hook grows
    a name detector.
    """
    message = "Created client 7: Jane Synthetic Doe"
    event = {"breadcrumbs": {"values": [{"category": "log", "message": message}]}}
    out = _before_send(event, {})
    assert out["breadcrumbs"]["values"][0]["message"] == message


def test_known_gap_an_unlabelled_passport_number_has_no_anchor():
    """DECLARED LIMIT: `": X1234567"` names no field, so nothing anchors it.

    Making it unconditional would redact build numbers, SKUs and internal ids.
    The call site that produced this exact shape (`crm_enhanced.py`, auto-OCR)
    was fixed in the same change to stop emitting the value at all.
    """
    message = "Auto OCR completed for client 7: X1234567"
    event = {"breadcrumbs": {"values": [{"category": "log", "message": message}]}}
    out = _before_send(event, {})
    assert "X1234567" in out["breadcrumbs"]["values"][0]["message"]


def test_the_exception_fallback_still_redacts_what_it_keeps(monkeypatch, capsys):
    """The escape hatch must not become the leak.

    `_before_send` wraps the walk in try/except so a scrubber bug cannot silently
    drop events, and keeps `exception` so the diagnosis survives. But `exception`
    is precisely where a formatted message lives — and it used to be handed back
    RAW, which made the wrapper's own docstring ("we strip everything else, incl.
    potentially-unscrubbed data") false for the only field it does not strip.
    Two independent reviewers, different model families, found this on the same
    diff; that agreement is why it is pinned rather than noted.
    """
    import backend.app.setup.sentry_config as mod

    def boom(*_a, **_kw):
        raise RuntimeError("scrubber exploded")

    monkeypatch.setattr(mod, "_before_send_impl", boom)

    leaked = f"no client for {PII_SAMPLES['email']}, phone {PII_SAMPLES['phone_jid']}"
    event = {
        "level": "error",
        "exception": {"values": [{"type": "ValueError", "value": leaked}]},
    }
    out = _before_send(event, {})
    capsys.readouterr()  # drain the stderr notice the hook prints

    assert out["tags"]["sentry_hook_error"] == "true", "this test must exercise the FALLBACK"
    kept = json.dumps(out.get("exception"))
    assert PII_SAMPLES["email"] not in kept, f"fallback leaked the email: {kept}"
    assert PII_SAMPLES["phone_jid"] not in kept, f"fallback leaked the phone: {kept}"
    assert PII_REDACTION_PLACEHOLDER in kept, "the exception should be scrubbed, not blanked"
