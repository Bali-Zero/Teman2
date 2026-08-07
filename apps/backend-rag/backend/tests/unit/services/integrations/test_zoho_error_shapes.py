"""Zoho error bodies, and the row a user's token is read from.

Every payload below was captured from the live API on 2026-08-04, not invented:
the shapes are the point, and an invented shape would test the fixture rather
than Zoho.

Why this file exists. `_request` used to coerce any non-dict error body to `{}`
and read `data.errorCode` out of it, so the reply that says exactly what is
wrong — an authorization failure, which Zoho sends as a LIST — was reported as
`API error: unknown`. Four different faults (missing OAuth scope, dead token,
malformed account id, wrong API host) all printed the same word, which is how a
one-line diagnosis became a long one.
"""

import httpx

from backend.services.integrations import zoho_oauth_service
from backend.services.integrations.zoho_email_service import (
    _decode_body,
    zoho_error_code,
)

# GET /api/accounts/<numeric>/folders with a grant that lacks ZohoMail.folders.READ.
LIVE_SCOPE_REFUSAL = [
    2,
    {
        "msg": "Error while processing!",
        "errorCode": "INVALID_OAUTHSCOPE",
        "authFail": "true",
        "status": "401",
    },
]

# The same endpoint with an e-mail address where the numeric accountId belongs.
LIVE_BAD_ACCOUNT_ID = {
    "data": {"errorCode": "URL_RULE_NOT_CONFIGURED"},
    "status": {"code": 404, "description": "Invalid Input"},
}


class TestZohoErrorCode:
    def test_list_shaped_refusal_names_the_missing_scope(self):
        # The whole point: this used to be "unknown".
        assert zoho_error_code(LIVE_SCOPE_REFUSAL) == "INVALID_OAUTHSCOPE"

    def test_nested_data_error_code_still_works(self):
        assert zoho_error_code(LIVE_BAD_ACCOUNT_ID) == "URL_RULE_NOT_CONFIGURED"

    def test_top_level_error_code(self):
        assert zoho_error_code({"errorCode": "INVALID_TOKEN"}) == "INVALID_TOKEN"

    def test_falls_back_to_the_status_description(self):
        assert (
            zoho_error_code({"status": {"code": 500, "description": "Internal Error"}})
            == "Internal Error"
        )

    def test_a_body_with_nothing_useful_says_unknown(self):
        # Innocence: absent information must read as absent, never as a crash and
        # never as a fabricated code.
        assert zoho_error_code({}) == "unknown"
        assert zoho_error_code("API endpoint not found") == "unknown"
        assert zoho_error_code(None) == "unknown"
        assert zoho_error_code([]) == "unknown"

    def test_a_list_with_no_dict_in_it_says_unknown(self):
        assert zoho_error_code([1, 2, "nope"]) == "unknown"


class TestDecodeBody:
    def test_plain_text_error_does_not_raise(self):
        # Zoho answers the wrong host with plain text. `response.json()` raises on
        # it, turning a diagnosable HTTP error into a JSONDecodeError three frames
        # away from the request that caused it.
        response = httpx.Response(404, text="API endpoint not found")
        assert _decode_body(response) == "API endpoint not found"

    def test_json_error_is_decoded(self):
        response = httpx.Response(404, json=LIVE_BAD_ACCOUNT_ID)
        assert _decode_body(response) == LIVE_BAD_ACCOUNT_ID

    def test_empty_body(self):
        assert _decode_body(httpx.Response(401)) == {}


class TestTokenRowSelectionIsTotal:
    """No read of `zoho_email_tokens` by user_id may be left unordered.

    This is a structural check and says so: it pins that the ordering is applied
    everywhere, not what Postgres does with it. The ordering's actual verdict was
    proved separately against the live table — the two rows of user 7dfe56b2,
    where the unordered query returned the unusable one.

    A structural check is the right shape here precisely because the failure it
    guards against is a FIFTH read being added later without the clause: that is
    invisible to any test of the four that exist.
    """

    def _source(self) -> str:
        import inspect

        return inspect.getsource(zoho_oauth_service)

    def test_every_user_id_read_is_ordered(self):
        source = self._source()
        # Each read of the table by user_id must carry the shared ordering.
        reads = source.count("FROM zoho_email_tokens")
        deletes = source.count("DELETE FROM zoho_email_tokens")
        # `disconnect` reads every row on purpose (it revokes them all), so it is
        # the one read that must NOT be limited to one row.
        revoke_all = source.count("WHERE user_id = $1 AND refresh_token IS NOT NULL")
        ordered = source.count("{_TOKEN_ROW_ORDER}")
        assert ordered == reads - deletes - revoke_all, (
            f"{reads} reads, {deletes} deletes, {revoke_all} revoke-all, "
            f"but only {ordered} carry the ordering clause"
        )

    def test_the_ordering_is_total_and_null_safe(self):
        clause = zoho_oauth_service._TOKEN_ROW_ORDER
        # A numeric account_id wins: it is the only shape Zoho accepts in a URL.
        assert "~ '^[0-9]+$'" in clause
        # In Postgres, DESC defaults to NULLS FIRST — without these two guards a
        # NULL account_id or a NULL updated_at would sort to the top and
        # re-create the bug with a different unusable row.
        assert "COALESCE(account_id, '')" in clause
        assert "NULLS LAST" in clause
        # `id` makes the order total, so every read answers from the SAME row.
        assert "id DESC" in clause
        assert "LIMIT 1" in clause
