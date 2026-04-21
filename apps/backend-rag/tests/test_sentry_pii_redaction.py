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

import re
from typing import Any

import pytest

from backend.app.setup.sentry_config import _before_send, PII_REDACTION_PLACEHOLDER

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
# Alert dedup: events tagged source=cron or source=deploy are dropped entirely
# so they don't duplicate the Telegram notifications emitted by those pipelines.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("source", ["cron", "deploy"])
def test_drops_events_tagged_as_cron_or_deploy(source: str):
    event = {
        "tags": {"source": source},
        "message": "boom",
    }
    assert _before_send(event, {}) is None


def test_keeps_events_with_other_tags():
    event = {"tags": {"source": "api"}, "message": "real error"}
    assert _before_send(event, {}) is not None
