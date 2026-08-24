"""WABA callback-override client (F9 step 5-6).

``POST /{GRAPH_VERSION}/{WABA-ID}/subscribed_apps`` with
``override_callback_uri`` + ``verify_token`` is the exact call
MANDATE.md F9 and the research capture §4.2 name — Meta's own docs for
per-WABA callback override:
<https://www.postman.com/meta/whatsapp-business-platform/request/l6a09ow/override-callback-url>.
F9 step 6 requires Pro to "fetch the WABA subscription and verify the
returned ``override_callback_uri``" before marking ingress active —
that verification is NOT optional here (``override_callback`` always
does both calls; there is no code path that trusts a 200 on the POST
alone).

**Disclosed honestly, not glossed over**: this repo has never called
this endpoint for real (owner switchboard item 1 — the second WABA
doesn't exist yet). The exact response SHAPE of the read-back GET is
therefore taken verbatim from what MANDATE.md's prose describes
(an ``override_callback_uri`` field to compare against), not from an
observed live payload. ``FakeGraphAPI`` in the test suite implements
that same shape so the CLIENT's control flow is proven; the live Graph
API contract itself is proven only once, for real, by the staging-WABA
drill F9 requires before ``TEAM_BOT_FAILOVER_AUTO_ENABLED`` may flip.

Golden Rule #10: the ``httpx.AsyncClient`` is ALWAYS injected — this
module never constructs one per call.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum

import httpx

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_VERSION = "v21.0"


class WABAOverrideErrorClass(StrEnum):
    """Closed wire-error vocabulary, same shape F3 mandates for the codex
    broker leg (AUTH_DEAD/QUOTA/... — "auth and quota MUST be distinct").
    Kept as a SEPARATE enum from F3's, not reused: these are Graph API
    failure modes, not codex CLI ones, and collapsing two unrelated wire
    vocabularies into one shared enum is exactly the kind of coupling
    that makes a future change to one silently ripple into the other.
    """

    AUTH_DEAD = "auth_dead"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"
    READBACK_MISMATCH = "readback_mismatch"


class WABAOverrideError(RuntimeError):
    def __init__(self, error_class: WABAOverrideErrorClass, message: str) -> None:
        super().__init__(message)
        self.error_class = error_class


@dataclass(frozen=True, slots=True)
class WABAOverrideResult:
    callback_uri: str
    callback_uri_sha256: str
    verified: bool
    """Always True on a successful return — override_callback raises
    rather than returning verified=False. The field exists so a caller
    can express the invariant in a type-checked way if it ever wants to
    (e.g. an assertion in a test), not because False is a real return
    value today.
    """


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _classify_status(status_code: int) -> WABAOverrideErrorClass | None:
    if status_code == 401 or status_code == 403:
        return WABAOverrideErrorClass.AUTH_DEAD
    if status_code == 429:
        return WABAOverrideErrorClass.RATE_LIMITED
    if status_code >= 500:
        return WABAOverrideErrorClass.SERVER_ERROR
    return None


class WABAOverrideClient:
    """Typed wrapper over the WABA subscribed_apps override + read-back.

    ``client`` is an already-constructed ``httpx.AsyncClient`` (base_url
    normally ``https://graph.facebook.com``) — this class never opens a
    connection itself, so ``network_guard.py``'s socket-level block still
    applies to it in tests exactly as it does to production code.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        access_token: str,
        graph_version: str = DEFAULT_GRAPH_VERSION,
    ) -> None:
        self._client = client
        self._access_token = access_token
        self._graph_version = graph_version

    async def override_callback(
        self, *, waba_id: str, callback_uri: str, verify_token: str
    ) -> WABAOverrideResult:
        """POST the override, then GET-and-verify. Raises
        :class:`WABAOverrideError` on ANY failure — including a
        successful-looking POST whose read-back does not confirm the new
        URI, which is exactly the case F9 step 6 exists to catch (Meta
        accepting the write but not actually applying it, or applying it
        to a different subscription than expected).
        """

        headers = {"Authorization": f"Bearer {self._access_token}"}
        post_url = f"/{self._graph_version}/{waba_id}/subscribed_apps"

        try:
            post_response = await self._client.post(
                post_url,
                headers=headers,
                data={
                    "override_callback_uri": callback_uri,
                    "verify_token": verify_token,
                },
            )
        except httpx.HTTPError as exc:
            raise WABAOverrideError(
                WABAOverrideErrorClass.NETWORK_ERROR, f"POST {post_url} failed: {exc}"
            ) from exc

        error_class = _classify_status(post_response.status_code)
        if error_class is not None:
            raise WABAOverrideError(
                error_class,
                f"POST {post_url} returned {post_response.status_code}",
            )
        if post_response.status_code >= 400:
            raise WABAOverrideError(
                WABAOverrideErrorClass.INVALID_RESPONSE,
                f"POST {post_url} returned unexpected {post_response.status_code}",
            )

        get_url = f"/{self._graph_version}/{waba_id}/subscribed_apps"
        try:
            get_response = await self._client.get(get_url, headers=headers)
        except httpx.HTTPError as exc:
            raise WABAOverrideError(
                WABAOverrideErrorClass.NETWORK_ERROR, f"GET {get_url} failed: {exc}"
            ) from exc

        error_class = _classify_status(get_response.status_code)
        if error_class is not None:
            raise WABAOverrideError(
                error_class, f"GET {get_url} returned {get_response.status_code}"
            )

        try:
            body = get_response.json()
            observed_uri = body["override_callback_uri"]
        except (ValueError, KeyError, TypeError) as exc:
            raise WABAOverrideError(
                WABAOverrideErrorClass.INVALID_RESPONSE,
                f"GET {get_url} response missing override_callback_uri: {exc}",
            ) from exc

        if observed_uri != callback_uri:
            logger.error(
                "waba_override: readback mismatch waba_id=%s expected_sha256=%s observed_sha256=%s",
                waba_id,
                _sha256(callback_uri),
                _sha256(observed_uri),
            )
            raise WABAOverrideError(
                WABAOverrideErrorClass.READBACK_MISMATCH,
                "GET readback did not confirm the callback URI just POSTed",
            )

        logger.info(
            "waba_override: callback override verified waba_id=%s callback_sha256=%s",
            waba_id,
            _sha256(callback_uri),
        )
        return WABAOverrideResult(
            callback_uri=callback_uri,
            callback_uri_sha256=_sha256(callback_uri),
            verified=True,
        )


__all__ = [
    "DEFAULT_GRAPH_VERSION",
    "WABAOverrideClient",
    "WABAOverrideError",
    "WABAOverrideErrorClass",
    "WABAOverrideResult",
]
