"""Entrypoint for the daily mail loop.

    PYTHONPATH=. python -m backend.services.mail_loop.cli --dry-run

Exit codes are the contract with the wrapper, because the wrapper is what turns
a bad run into an alert and a shell only ever sees a number:

    0  clean run
    1  ran, but degraded (a folder is missing, drafting failed, nothing routed)
    2  could not run at all (no DB, no Zoho token, no such user)

There is no exit code that means "probably fine". A run that half-worked must be
distinguishable from one that worked, or the cron goes green forever while doing
nothing — the most repeated failure in this repo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("mail_loop")

DEFAULT_STATE_DIR = Path(
    os.environ.get("MAIL_LOOP_STATE_DIR", os.path.expanduser("~/.nuzantara/mail-loop"))
)
MAILBOX_EMAIL = os.environ.get("MAIL_LOOP_EMAIL", "zero@balizero.com")


def _configure_logging(verbose: bool) -> None:
    """Split streams: INFO to stdout, WARNING+ to stderr.

    launchd routes stderr to the .err log, and the default single-handler setup
    sends INFO there too — which is how a 12 MB error log fills with routine
    heartbeat and buries the one line that mattered.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    out = logging.StreamHandler(sys.stdout)
    out.setLevel(logging.DEBUG)
    out.addFilter(lambda record: record.levelno < logging.WARNING)
    out.setFormatter(fmt)

    err = logging.StreamHandler(sys.stderr)
    err.setLevel(logging.WARNING)
    err.setFormatter(fmt)

    root.handlers = [out, err]


async def _resolve_user_id(pool, email: str) -> str | None:
    """Look up the team_members row the Zoho token hangs off.

    Deliberately a query and not a constant: `zoho_email_tokens.user_id`
    references `team_members(id)`, and inventing an id here would be a guess
    dressed as configuration.
    """
    override = os.environ.get("MAIL_LOOP_USER_ID")
    if override:
        return override
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM team_members WHERE lower(email) = lower($1) LIMIT 1",
            email,
        )
    return str(row["id"]) if row else None


async def _amain(args: argparse.Namespace) -> int:
    # Imported here so that --help works without the backend's full dependency
    # tree, and so a missing dependency reports as exit 2 rather than a traceback
    # at import time.
    import asyncpg

    from backend.services.integrations.zoho_email_service import ZohoEmailService
    from backend.services.mail_loop.loop import MailLoop, PendingDrafts
    from backend.services.mail_loop.style import ReplyStyleStore

    # DATABASE_URL first, and the app settings only as a fallback — never the
    # other way round, and never at module import.
    #
    # `backend.app.core.config.Settings` validates the WHOLE application config:
    # importing it raises unless JWT_SECRET_KEY and API_KEYS are also present.
    # Those live in apps/backend-rag/.env, which pydantic finds only when the
    # process cwd happens to be that directory. So an import at the top of this
    # module makes a mail loop that needs one connection string fail on two
    # unrelated web-API secrets, with a pydantic traceback instead of an exit
    # code — and makes it unrunnable from anywhere but one directory.
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        try:
            from backend.app.core.config import settings

            dsn = getattr(settings, "database_url", None)
        except Exception as exc:  # broad on purpose: this becomes exit 2, never a stack trace
            logger.error(
                "no DATABASE_URL in the environment, and the app settings could "
                "not be loaded as a fallback (%s). Export DATABASE_URL.",
                exc,
            )
            return 2
    if not dsn:
        logger.error("no DATABASE_URL: cannot reach the Zoho token store")
        return 2

    state_dir = Path(args.state_dir)
    style = ReplyStyleStore(state_dir / "reply-style.md")
    pending = PendingDrafts(state_dir / "pending-drafts.json")

    pool = None
    service = None
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
        user_id = await _resolve_user_id(pool, args.email)
        if not user_id:
            logger.error(
                "no team_members row for %s — set MAIL_LOOP_USER_ID to override",
                args.email,
            )
            return 2

        service = ZohoEmailService(pool)

        # PREFLIGHT — refuse to touch Zoho without client credentials.
        #
        # This is not tidiness, it is damage control, and it was written after
        # doing the damage. `ZohoOAuthService._refresh_token` treats an
        # `invalid_client` reply as a dead USER token and writes
        #
        #     UPDATE zoho_email_tokens SET token_expires_at = NOW() - INTERVAL '1 year'
        #
        # But `invalid_client` means the CALLER is misconfigured — it says
        # nothing about the user's token. So a machine that merely lacks
        # ZOHO_CLIENT_ID marks a perfectly good production token as permanently
        # invalidated for every other consumer, including the live backend that
        # does have the right credentials. Measured, not reasoned: three probe
        # runs from this machine invalidated all three of zero@balizero.com's
        # rows (ids 2/25/28) before anyone knew the credentials were missing;
        # they were restored to their exact pre-probe values.
        #
        # Zoho also returns HTTP 200 with the error in the BODY, so nothing
        # upstream sees a failure status. Read the reply, never the code.
        #
        # The fix belongs in the shared service too, but this loop is not
        # allowed to be the thing that fires it. Absent credentials = exit 2,
        # before a single request goes out.
        oauth = getattr(service, "oauth_service", None)
        if oauth is not None and not (
            getattr(oauth, "client_id", "") and getattr(oauth, "client_secret", "")
        ):
            logger.error(
                "ZOHO_CLIENT_ID/ZOHO_CLIENT_SECRET are not configured on this "
                "machine. Refusing to run: a refresh attempted without them "
                "returns invalid_client, which the shared OAuth service records "
                "by INVALIDATING the stored token for every other consumer."
            )
            return 2

        loop = MailLoop(
            service,
            user_id=user_id,
            style=style,
            pending=pending,
            dry_run=args.dry_run,
        )
        summary = await loop.run()
    except Exception as exc:  # broad on purpose: the wrapper needs a code, not a stack
        logger.exception("mail loop could not run: %s", exc)
        return 2
    finally:
        if service is not None:
            close = getattr(service, "close", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    logger.warning("service.close() failed", exc_info=True)
        if pool is not None:
            await pool.close()

    # The print below is deliberate. This is a CLI, and the run summary on stdout is
    # its machine-readable output: the wrapper redirects stdout into the log, so
    # the JSON is what a human (or a future reconciler) reads to see what the run
    # actually did. Routing it through `logger` would wrap it in a timestamped
    # prefix and split it across the INFO/WARNING handlers configured above,
    # which is precisely what makes it stop being parseable.
    print(json.dumps(summary.as_dict(), indent=2, ensure_ascii=False))  # noqa: T201

    if summary.degraded:
        logger.warning(
            "run DEGRADED: routed=%d drafted=%d draft_failures=%d missing_folders=%s "
            "errors=%d",
            summary.routed,
            summary.drafted,
            summary.draft_failures,
            summary.missing_folders,
            len(summary.errors),
        )
        return 1

    logger.info(
        "run clean: seen=%d routed=%d drafted=%d left_in_inbox=%d lessons=%d%s",
        summary.seen,
        summary.routed,
        summary.drafted,
        summary.left_in_inbox,
        summary.lessons_learned,
        " (DRY-RUN)" if summary.dry_run else "",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mail_loop",
        description="Route the Zoho inbox, draft replies, learn from Sent. Never sends.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="classify and report, mutate nothing: no move, no draft, no state written",
    )
    parser.add_argument("--email", default=MAILBOX_EMAIL, help="mailbox to process")
    parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="where reply-style.md and the pending-comparison buffer live",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
