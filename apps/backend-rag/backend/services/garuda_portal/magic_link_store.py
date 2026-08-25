"""`PostgresMagicLinkStore` -- the concrete `MagicLinkStore` adapter
(products/garuda-voa/L4-CONTINUATION.md part 2 of 3).

Persists to `garuda_magic_link_tokens` / `garuda_magic_link_idempotency` /
`garuda_account_sessions` (migration 285). See that migration's header for
why this is a NEW table family rather than a reuse of `magic_link_tokens`
(237, the unrelated FASE 6 client-portal login table).

Every security property `magic_link.py`'s `MagicLinkStore` docstring
requires is enforced HERE, not left to a caller:

- The raw token/session-secret exist only transiently in this process's
  memory (and, for the token, in the outgoing email body) -- only their
  sha256 hex digest is ever written to a column, a log line, or an error
  message.
- Token consumption is ONE atomic
  `UPDATE ... WHERE used_at IS NULL AND expires_at > NOW() RETURNING ...`
  statement -- never a read-then-write -- so two concurrent `exchange`
  calls for the same token race at the database row-lock level and exactly
  one can ever observe a non-empty RETURNING set.
- Unknown, expired, and already-consumed tokens all fall through the same
  "0 rows returned" branch and produce the identical `ExchangeOutcome`
  (DECISIONS.md Q1) -- there is no code path that inspects *why* the UPDATE
  matched nothing. This is TIMING equivalence, not just response equivalence
  (team-lead review, 2026-08-25): `exchange` issues exactly ONE query shape
  for every deny outcome -- the single atomic UPDATE, whether it misses
  because the token_hash was never issued, is expired, or is already
  consumed -- followed by exactly one `idempotency.complete()` write. No
  branch does a cheaper "return immediately" for one deny reason and a more
  expensive lookup+compare for another; there is nothing FOR such a branch
  to inspect, because the adapter never determines *which* deny reason
  occurred in the first place (`security_counter` is hardcoded to the same
  constant for all three). The one asymmetry this does NOT attempt to
  erase is the underlying Postgres B-tree index's own hit-vs-miss cost (an
  index probe that finds no matching key vs. one that finds a row and then
  evaluates the `used_at`/`expires_at` predicates against it) -- closing
  that would require a fundamentally different storage structure
  (constant-cost lookup, e.g. a fixed-size in-memory table or an HMAC blind
  index) and is disproportionate for what it would defend against: the
  "secret" here is a full 256-bit `secrets.token_urlsafe(32)` bearer, not a
  partial value an attacker refines byte-by-byte against a comparison
  function the way a classic timing attack on MAC verification would.
  `test_magic_link_store_integration.py::test_deny_paths_execute_the_same_
  query_shape` pins the STRUCTURAL invariant (identical statement count for
  all three) that makes engine-level constancy at least possible; that same
  file's `test_deny_path_timing_does_not_separate_under_repetition` adds an
  empirical sample as a secondary, advisory signal and documents exactly
  why it is not the primary gate (CI-runner jitter, not application logic,
  dominates at this scale).
- `PersistencePolicyUnavailable` is raised BEFORE any row is attempted (a
  pre-check against `active_garuda_magic_link_policy_available`), mirroring
  `GarudaOrderRepository._active_order_policy_available` (L3) exactly --
  never caught out of the retention trigger's own `RAISE EXCEPTION`, which
  stays as pure defense-in-depth for a caller that skips the pre-check.
- `issue` fails closed with `RateLimited` once an email has received
  `_MAX_ISSUES_PER_EMAIL_PER_WINDOW` links within `_ISSUE_RATE_WINDOW_
  MINUTES` -- team-lead review, 2026-08-25: `RATE_LIMITED` (429) is
  declared in the frozen contract for both operations but was unreachable
  on any code path before this. Scoped by email (not IP, not session):
  `issue`'s Protocol signature carries no client IP, and email is exactly
  what an anti-mail-bomb throttle needs to count against -- migration 237's
  own `idx_magic_link_email_created` comment ("rate-limit / cleanup queries
  scan by email + recency") is the precedent this mirrors, and migration
  285's `idx_garuda_magic_link_tokens_email_created` was already built for
  the identical purpose on this table. `exchange`'s 429 is a SEPARATE,
  deliberately unimplemented decision -- see that method's docstring.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx

from backend.services.common.background import spawn
from backend.services.garuda_portal import idempotency
from backend.services.garuda_portal.magic_link import (
    MAGIC_LINK_TTL_MINUTES,
    ExchangeOutcome,
    IssueOutcome,
    PersistencePolicyUnavailable,
    RateLimited,
)

logger = logging.getLogger(__name__)

#: DECISIONS.md Q1: "proposed: 30 days, re-authenticated by a new link".
_ACCOUNT_SESSION_TTL_DAYS = 30

#: Anti-mail-bomb throttle on `issue` (team-lead review, 2026-08-25) -- same
#: window shape as `MagicLinkService.MAX_LIVE_TOKENS_PER_EMAIL` (the FASE-6
#: portal precedent) but counting BY RECENCY, not by still-live/unused
#: state: a fully-expired flood is exactly as much of a mailbox attack as a
#: live one, and counting only unused rows would let an attacker exhaust
#: nothing but this table's disk while every request still sends mail.
#: Proposed numbers, not asserted final -- Zero's call like every other
#: threshold in this repo.
_MAX_ISSUES_PER_EMAIL_PER_WINDOW = 5
_ISSUE_RATE_WINDOW_MINUTES = 15

_ISSUE_OPERATION = "requestMagicLink"
_EXCHANGE_OPERATION = "exchangeMagicLink"

#: Scoped-identity actor for magic-link commands. Neither operation is
#: gated behind an existing session (the whole point is to BUILD one), so
#: -- unlike L3's `_require_magic_session_actor`-derived actor -- there is
#: no pre-existing identity to scope by. A fixed, endpoint-specific string
#: is what `scoped_key_sha256` needs to keep this product's Idempotency-Key
#: namespace disjoint from every other actor+operation pair in the system;
#: it is not a secret and carries no per-caller information.
_ACTOR = "garuda_magic_link"


def _hash_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _default_send_magic_link_email(*, email: str, result_id: str, raw_token: str) -> None:
    """Dispatch the magic-link email via Brevo (from=zantara@balizero.com --
    CLAUDE.md fixed rule). Fire-and-forget by the caller (`spawn`); must
    never raise into the request path -- a send failure is logged, never
    surfaced to the enumeration-safe 202.

    `GARUDA_MAGIC_LINK_BASE_URL` default is a placeholder pending frontend
    confirmation (ARCHITECTURE.md does not yet name a canonical result-page
    URL) -- this is a call made explicit here, not asserted as final.
    """
    base = os.getenv("GARUDA_MAGIC_LINK_BASE_URL", "https://balizero.com/visa/voa").rstrip("/")
    link_url = f"{base}?result_id={result_id}&magic_token={raw_token}"
    api_url = os.getenv(
        "INTERNAL_EMAIL_API_URL",
        "https://nuzantara-rag.fly.dev/api/notifications/send-email",
    )
    api_key = os.getenv("NUZANTARA_API_KEY", "")
    html_body = (
        "Hello,<br><br>"
        "Use the secure link below to view your GARUDA VOA eligibility result. "
        f"This link works once and expires in {MAGIC_LINK_TTL_MINUTES} minutes.<br><br>"
        f'<a href="{link_url}">View my VOA result</a><br><br>'
        "If you didn't request this, you can safely ignore this email.<br><br>"
        "— Bali Zero"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                api_url,
                headers={"X-API-Key": api_key},
                json={"to": email, "subject": "Your Bali Zero VOA result link", "body": html_body},
            )
            resp.raise_for_status()
        logger.info("garuda_magic_link: email dispatched via Brevo")
    except Exception:
        logger.warning("garuda_magic_link: email send failed", exc_info=True)


class PostgresMagicLinkStore:
    """Concrete `MagicLinkStore` over migration 285's three tables.

    Not yet wired via `app.dependency_overrides[get_garuda_magic_link_store]`
    in `app_factory` -- see the PR body / migration 285 header. Until that
    wiring lands, the mounted router keeps answering fail-closed via
    `UnconfiguredMagicLinkStore`, exactly as it does today.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        environment: str,
        send_email: Callable[..., Awaitable[None]] = _default_send_magic_link_email,
    ) -> None:
        self._pool = pool
        self._environment = environment
        self._send_email = send_email

    async def _active_policy_available(self) -> bool:
        async with self._pool.acquire() as conn:
            return bool(
                await conn.fetchval(
                    "SELECT public.active_garuda_magic_link_policy_available($1, $2)",
                    self._environment,
                    datetime.now(UTC),
                )
            )

    async def issue(
        self,
        *,
        idempotency_key: str,
        result_id: str,
        email: str,
        result_session_secret: str,
    ) -> IssueOutcome:
        del result_session_secret  # not persisted -- see magic_link.py Protocol docstring

        if not await self._active_policy_available():
            raise PersistencePolicyUnavailable("no active GARUDA_MAGIC_LINK retention policy")

        key_hash = idempotency.scoped_key_sha256(
            actor=_ACTOR, operation=_ISSUE_OPERATION, raw_key=idempotency_key
        )
        payload_hash = idempotency.canonical_payload_sha256(
            {"result_id": result_id, "email": email}
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_hex(raw_token)
        expires_at = datetime.now(UTC) + timedelta(minutes=MAGIC_LINK_TTL_MINUTES)

        async with self._pool.acquire() as conn, conn.transaction():
            reservation = await idempotency.reserve(
                conn, key_sha256=key_hash, payload_sha256=payload_hash
            )
            if reservation.replayed:
                return IssueOutcome(idempotency_replayed=True)

            # Rate limit AFTER the replay check, BEFORE minting: an exact
            # replay of an already-issued request must never count a
            # second time against the window (that would let one client
            # retrying a slow response starve out its own legitimate
            # request), and a fresh request over the threshold must never
            # reach the INSERT/email-send below. Counts by RECENCY
            # (created_at within the window), not by still-unused rows --
            # see the class docstring for why an expired flood counts too.
            # `lower(email)` on BOTH sides (2026-08-25, Kimi K3 adversarial
            # review of this PR): the column itself is stored exactly as
            # submitted -- no case normalization anywhere in this store --
            # so an unqualified `email = $1` lets a caller multiply its own
            # window by varying case alone (`a@x.com` / `A@x.com` /
            # `a@X.COM` all land in different buckets while every one of
            # them is the SAME mailbox per RFC 5321's domain part and every
            # major provider's local part). This intentionally does not use
            # `idx_garuda_magic_link_tokens_email_created` (a plain B-tree on
            # raw `email` can't service a `lower()` predicate) -- accepted
            # for a low-cardinality-per-email anti-abuse check where
            # correctness of the THROTTLE matters more than this one query's
            # plan; a functional index is a fair follow-up if this table's
            # per-email row count ever makes it a real cost, not a
            # speculative one to add here.
            recent_count = await conn.fetchval(
                """
                SELECT count(*) FROM garuda_magic_link_tokens
                 WHERE lower(email) = lower($1)
                   AND created_at > statement_timestamp() - $2::interval
                """,
                email,
                timedelta(minutes=_ISSUE_RATE_WINDOW_MINUTES),
            )
            if recent_count >= _MAX_ISSUES_PER_EMAIL_PER_WINDOW:
                raise RateLimited(
                    f"more than {_MAX_ISSUES_PER_EMAIL_PER_WINDOW} magic-links issued "
                    f"for this email in the last {_ISSUE_RATE_WINDOW_MINUTES} minutes"
                )

            await conn.execute(
                """
                INSERT INTO garuda_magic_link_tokens (token_hash, result_id, email, environment, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                token_hash,
                result_id,
                email,
                self._environment,
                expires_at,
            )
            await idempotency.complete(
                conn, key_sha256=key_hash, response_status=202, response_body={}
            )

        # Outside the transaction and fire-and-forget: an email-send failure
        # must never roll back the token row or change the 202 the router
        # already returned by the time this task runs.
        spawn(
            self._send_email(email=email, result_id=result_id, raw_token=raw_token),
            name="garuda-magic-link-email",
        )
        return IssueOutcome(idempotency_replayed=False)

    async def exchange(
        self,
        *,
        idempotency_key: str,
        token: str,
    ) -> ExchangeOutcome:
        """Deliberately does NOT rate-limit here (team-lead review,
        2026-08-25): a brute-force throttle on token GUESSES is inherently
        an IP-scoped concern -- an attacker enumerating tokens uses
        arbitrary, mostly-nonexistent strings, so there is no row and no
        email to count against, and this Protocol's signature (frozen,
        `magic_link.py`) carries no client IP for the store to key on.
        That belongs at the router/middleware layer, the same place
        `visa_check`'s per-IP `RateLimitMiddleware` bucket already lives
        for this exact class of anonymous-POST-guessing surface
        (`public_endpoints.py`'s Visa Check entries). Left unimplemented
        here on purpose, not silently skipped -- flagged for the
        orchestrator to route as its own PR.
        """
        token_hash = _hash_hex(token)
        key_hash = idempotency.scoped_key_sha256(
            actor=_ACTOR, operation=_EXCHANGE_OPERATION, raw_key=idempotency_key
        )
        # The canonical payload binds on the token's HASH, never the raw
        # bearer -- token_hash is already the non-secret value this table
        # uses as its primary key, so this never leaks the raw token any
        # further than the tokens table already does.
        payload_hash = idempotency.canonical_payload_sha256({"token_hash": token_hash})

        async with self._pool.acquire() as conn, conn.transaction():
            reservation = await idempotency.reserve(
                conn, key_sha256=key_hash, payload_sha256=payload_hash
            )
            if reservation.replayed:
                body = reservation.response_body or {}
                return ExchangeOutcome(
                    authorized=bool(body.get("authorized", False)),
                    security_counter=str(body.get("security_counter", "magic_link_replay")),
                    result_id=body.get("result_id"),
                    account_session_secret=None,  # replay never re-emits the secret
                    idempotency_replayed=True,
                )

            row = await conn.fetchrow(
                """
                UPDATE garuda_magic_link_tokens
                   SET used_at = statement_timestamp()
                 WHERE token_hash = $1
                   AND used_at IS NULL
                   AND expires_at > statement_timestamp()
                RETURNING result_id, email
                """,
                token_hash,
            )

            if row is None:
                outcome_body = {"authorized": False, "security_counter": "magic_link_invalid"}
                await idempotency.complete(
                    conn, key_sha256=key_hash, response_status=401, response_body=outcome_body
                )
                return ExchangeOutcome(
                    authorized=False, security_counter="magic_link_invalid"
                )

            result_id = row["result_id"]
            email = row["email"]

            raw_secret = secrets.token_urlsafe(32)
            secret_hash = _hash_hex(raw_secret)
            session_expires_at = datetime.now(UTC) + timedelta(days=_ACCOUNT_SESSION_TTL_DAYS)
            await conn.execute(
                """
                INSERT INTO garuda_account_sessions (session_secret_hash, result_id, email, expires_at)
                VALUES ($1, $2, $3, $4)
                """,
                secret_hash,
                result_id,
                email,
                session_expires_at,
            )

            outcome_body = {
                "authorized": True,
                "security_counter": "magic_link_authorized",
                "result_id": result_id,
            }
            await idempotency.complete(
                conn, key_sha256=key_hash, response_status=204, response_body=outcome_body
            )

        return ExchangeOutcome(
            authorized=True,
            security_counter="magic_link_authorized",
            result_id=result_id,
            account_session_secret=raw_secret,
            idempotency_replayed=False,
        )


__all__ = ["PostgresMagicLinkStore"]
