"""IG long-lived token watchdog — Task 30.

Meta long-lived user tokens expire after ~60 days. The WR2 measurer
(`scheduler_cli.py` → `MetaGraphSampler`) silently starves when the token
dies, killing the learning-loop food supply. This module keeps a valid token
alive by exchanging it for a fresh long-lived token BEFORE it expires
(Graph API ``GET /oauth/access_token?grant_type=fb_exchange_token``).

Durability gate: the exchange only runs when the remaining lifetime drops
below ``DEFAULT_REFRESH_THRESHOLD_DAYS`` — a fresh token is never churned.

Secret discipline (scar #4): the token value NEVER appears in logs, reprs,
exceptions or stdout. Provenance lines carry only the expiry date.

This module is invocable but deliberately NOT self-arming: installing it as
a cron/LaunchAgent is an operator[control-plane] action, and landing the
FIRST valid token is operator[secret]. See docs/runbooks/ig-token-watchdog.md.

Usage (one-shot):
    PYTHONPATH=. python -m backend.services.measurer.ig_token_watchdog

Env:
    IG_LONG_LIVED_TOKEN
    or INSTAGRAM_ACCESS_TOKEN       (required — same precedence as sampler)
    META_APP_ID                     (required)
    META_APP_SECRET                 (required)
    IG_TOKEN_ENV_FILE               (optional — persist refreshed token here)
    IG_TOKEN_REFRESH_THRESHOLD_DAYS (optional — default 7)

Exit codes:
    0  token fresh, or refreshed (and persisted when IG_TOKEN_ENV_FILE set)
    1  configuration error (missing env)
    2  token invalid or refresh failed — operator must land a new token
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# httpx logs `HTTP Request: GET <full url>` at INFO — with Meta's flow the
# token and app secret travel as query params, so without redaction every
# watchdog pass would leak them into any INFO-level log sink (scar #4).
_SENSITIVE_QUERY_PARAMS = (
    "access_token",
    "input_token",
    "fb_exchange_token",
    "client_secret",
)
_REDACT_RE = re.compile(
    r"(" + "|".join(_SENSITIVE_QUERY_PARAMS) + r")=[^&\s\"']+"
)


class _RedactTokenFilter(logging.Filter):
    """Masks sensitive query-param values in httpx's own log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = _REDACT_RE.sub(r"\1=<redacted>", msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def _ensure_httpx_redaction() -> None:
    httpx_logger = logging.getLogger("httpx")
    if not any(isinstance(f, _RedactTokenFilter) for f in httpx_logger.filters):
        httpx_logger.addFilter(_RedactTokenFilter())

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
DEFAULT_REFRESH_THRESHOLD_DAYS = 7
DEFAULT_TIMEOUT = 20.0

TOKEN_ENV_KEYS = ("IG_LONG_LIVED_TOKEN", "INSTAGRAM_ACCESS_TOKEN")


class IGTokenWatchdogError(RuntimeError):
    """Raised on Graph API errors. Never carries the token value."""


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_ig_token_watchdog_client() -> None:
    """Release the module-level AsyncClient (lifespan/CLI shutdown hook)."""
    global _module_client
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


@dataclass(frozen=True)
class TokenStatus:
    """Result of a /debug_token inspection. Carries NO secret material."""

    is_valid: bool
    expires_at: datetime | None  # None = never-expiring token
    days_remaining: float | None  # None when expires_at is None
    error: str | None = None


@dataclass(frozen=True, repr=False)
class RefreshedToken:
    """A freshly exchanged long-lived token.

    ``repr`` is redacted — the token value must never reach logs/tracebacks.
    """

    token: str
    expires_at: datetime

    def __repr__(self) -> str:
        return f"RefreshedToken(token=<redacted>, expires_at={self.expires_at.isoformat()})"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class WatchdogOutcome:
    """Outcome of one watchdog pass.

    action: 'fresh' | 'refreshed' | 'invalid' | 'error'
    new_token is set ONLY when action == 'refreshed'.
    """

    action: str
    status: TokenStatus
    new_token: str | None = None
    new_expires_at: datetime | None = None
    error: str | None = None

    def __repr__(self) -> str:
        return (
            f"WatchdogOutcome(action={self.action!r}, "
            f"new_token={'<redacted>' if self.new_token else None}, "
            f"new_expires_at={self.new_expires_at})"
        )

    __str__ = __repr__


def _graph_error_message(body: object) -> str:
    """Extract a safe error message from a Graph error payload."""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            code = err.get("code", "?")
            message = str(err.get("message", "unknown Graph error"))
            return f"code {code}: {message[:200]}"
    return "unknown Graph error"


async def inspect_token(
    token: str,
    app_id: str,
    app_secret: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> TokenStatus:
    """Inspect a token's validity + expiry via ``GET /debug_token``.

    Never raises on an invalid token — that is a reportable state, not an
    exception (the caller decides what to do with it).
    """
    now = now or datetime.now(timezone.utc)
    _ensure_httpx_redaction()
    client = http_client or _get_module_client(DEFAULT_TIMEOUT)
    resp = await client.get(
        f"{GRAPH_API_BASE}/debug_token",
        params={
            "input_token": token,
            "access_token": f"{app_id}|{app_secret}",
        },
    )
    body = resp.json()
    if resp.status_code != 200 or "error" in body:
        return TokenStatus(
            is_valid=False,
            expires_at=None,
            days_remaining=None,
            error=_graph_error_message(body),
        )
    data = body.get("data") or {}
    if not data.get("is_valid", False):
        return TokenStatus(
            is_valid=False,
            expires_at=None,
            days_remaining=None,
            error="token reported is_valid=false by /debug_token",
        )
    epoch = int(data.get("expires_at", 0) or 0)
    if epoch == 0:
        # Meta's marker for a never-expiring token.
        return TokenStatus(is_valid=True, expires_at=None, days_remaining=None)
    expires_at = datetime.fromtimestamp(epoch, tz=timezone.utc)
    days_remaining = (expires_at - now).total_seconds() / 86400.0
    return TokenStatus(
        is_valid=True, expires_at=expires_at, days_remaining=days_remaining
    )


async def refresh_long_lived_token(
    token: str,
    app_id: str,
    app_secret: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> RefreshedToken:
    """Exchange a long-lived token for a NEW long-lived token.

    Pure function of (token, app_id, app_secret) → (new token, expiry).
    Raises :class:`IGTokenWatchdogError` on Graph errors; the exception
    message never contains the token or the app secret.
    """
    now = now or datetime.now(timezone.utc)
    _ensure_httpx_redaction()
    client = http_client or _get_module_client(DEFAULT_TIMEOUT)
    resp = await client.get(
        f"{GRAPH_API_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        },
    )
    body = resp.json()
    if resp.status_code != 200 or "error" in body:
        raise IGTokenWatchdogError(
            f"token exchange failed: {_graph_error_message(body)}"
        )
    new_token = body.get("access_token")
    if not new_token:
        raise IGTokenWatchdogError("token exchange returned no access_token field")
    # Meta may omit expires_in for never-expiring tokens; default to 60 days
    # so the gate stays conservative rather than treating it as immortal.
    expires_in = int(body.get("expires_in", 60 * 86400) or 60 * 86400)
    return RefreshedToken(
        token=new_token, expires_at=now + timedelta(seconds=expires_in)
    )


async def run_watchdog(
    token: str,
    app_id: str,
    app_secret: str,
    *,
    threshold_days: float = DEFAULT_REFRESH_THRESHOLD_DAYS,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> WatchdogOutcome:
    """One watchdog pass: inspect, and refresh only if expiring soon.

    Provenance is logged WITHOUT the token value (scar #4).
    """
    now = now or datetime.now(timezone.utc)
    status = await inspect_token(
        token, app_id, app_secret, http_client=http_client, now=now
    )
    if not status.is_valid:
        logger.error("[ig-token-watchdog] token INVALID: %s", status.error)
        return WatchdogOutcome(action="invalid", status=status, error=status.error)

    if status.expires_at is None:
        logger.info("[ig-token-watchdog] token never expires; nothing to do")
        return WatchdogOutcome(action="fresh", status=status)

    assert status.days_remaining is not None
    if status.days_remaining >= threshold_days:
        logger.info(
            "[ig-token-watchdog] token fresh, expiry=%s (%.1f days left, threshold %.1f)",
            status.expires_at.date().isoformat(),
            status.days_remaining,
            threshold_days,
        )
        return WatchdogOutcome(action="fresh", status=status)

    logger.info(
        "[ig-token-watchdog] token expiring in %.1f days (< %.1f) — refreshing",
        status.days_remaining,
        threshold_days,
    )
    try:
        refreshed = await refresh_long_lived_token(
            token, app_id, app_secret, http_client=http_client, now=now
        )
    except IGTokenWatchdogError as exc:
        logger.error("[ig-token-watchdog] refresh FAILED: %s", exc)
        return WatchdogOutcome(action="error", status=status, error=str(exc))

    logger.info(
        "[ig-token-watchdog] refreshed, new expiry=%s",
        refreshed.expires_at.date().isoformat(),
    )
    return WatchdogOutcome(
        action="refreshed",
        status=status,
        new_token=refreshed.token,
        new_expires_at=refreshed.expires_at,
    )


def persist_token_to_env_file(
    path: Path | str,
    new_token: str,
    *,
    key: str = "IG_LONG_LIVED_TOKEN",
) -> None:
    """Rewrite ``KEY=value`` in an env file with the refreshed token.

    - Refuses to create a new file: the FIRST token landing is an operator
      action; this function only rotates an existing installation.
    - Writes atomically (temp file + rename) and enforces mode 0600 on both
      the temp file and the final file (scar #4: no world-readable secret).
    - Preserves every other line untouched.
    """
    path = Path(path)
    if not path.is_file():
        raise IGTokenWatchdogError(
            f"env file not found: {path} — first token landing is operator-owned"
        )
    lines = path.read_text().splitlines(keepends=True)
    prefix = f"{key}="
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.startswith(prefix) or line.startswith(f"export {prefix}"):
            export = "export " if line.startswith("export ") else ""
            out.append(f"{export}{prefix}{new_token}\n")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append(f"{prefix}{new_token}\n")

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".ig-token-", text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.writelines(out)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    os.chmod(path, 0o600)
    logger.info(
        "[ig-token-watchdog] persisted refreshed token to %s (key=%s, mode=0600)",
        path,
        key,
    )


def _resolve_token_from_env() -> tuple[str, str] | None:
    """Return (token, env_key_it_came_from) with sampler-identical precedence."""
    for env_key in TOKEN_ENV_KEYS:
        value = os.environ.get(env_key)
        if value:
            return value, env_key
    return None


async def run_from_env() -> int:
    """CLI body: read config from env, run one pass, optionally persist."""
    resolved = _resolve_token_from_env()
    if resolved is None:
        logger.error(
            "[ig-token-watchdog] no token in env (set %s)",
            " or ".join(TOKEN_ENV_KEYS),
        )
        return 1
    token, env_key = resolved
    app_id = os.environ.get("META_APP_ID")
    app_secret = os.environ.get("META_APP_SECRET")
    if not app_id or not app_secret:
        logger.error(
            "[ig-token-watchdog] META_APP_ID / META_APP_SECRET not set — "
            "the fb_exchange_token flow requires app credentials"
        )
        return 1
    threshold = float(
        os.environ.get(
            "IG_TOKEN_REFRESH_THRESHOLD_DAYS", str(DEFAULT_REFRESH_THRESHOLD_DAYS)
        )
    )

    try:
        outcome = await run_watchdog(
            token, app_id, app_secret, threshold_days=threshold
        )
    finally:
        await close_ig_token_watchdog_client()

    if outcome.action == "fresh":
        return 0
    if outcome.action in ("invalid", "error"):
        return 2

    # action == "refreshed": persist if a target env file is declared.
    env_file = os.environ.get("IG_TOKEN_ENV_FILE")
    if env_file:
        assert outcome.new_token is not None
        try:
            persist_token_to_env_file(env_file, outcome.new_token, key=env_key)
        except IGTokenWatchdogError as exc:
            logger.error("[ig-token-watchdog] persist FAILED: %s", exc)
            return 2
    else:
        logger.warning(
            "[ig-token-watchdog] refreshed but IG_TOKEN_ENV_FILE not set — "
            "the new token was NOT persisted anywhere and will be lost; "
            "the OLD token remains valid until its original expiry"
        )
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    sys.exit(asyncio.run(run_from_env()))


if __name__ == "__main__":
    main()
