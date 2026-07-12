"""IG long-lived token watchdog — Task 30.

Meta long-lived tokens expire after ~60 days. The WR2 measurer
(`scheduler_cli.py` → `MetaGraphSampler`) silently starves when the token
dies, killing the learning-loop food supply. This module keeps a valid token
alive by refreshing it BEFORE it expires.

TWO token families exist (adversarial review 2026-07-13 caught the original
single-family draft as dead-on-arrival for the real token):

- ``instagram`` (DEFAULT — the verified live family, see
  scripts/wr2_ig_publish.py: the Fly secret INSTAGRAM_ACCESS_TOKEN is an
  *Instagram API with Instagram Login* token, valid on graph.instagram.com
  ONLY; graph.facebook.com answers "Cannot parse access token"):
  refresh via ``GET graph.instagram.com/refresh_access_token``
  (grant_type=ig_refresh_token — no app credentials needed). This host has
  no /debug_token, so expiry is tracked in an optional local STATE FILE
  (written by us after each refresh, holds dates only — never the token).
  No state → expiry unknown → refresh conservatively.

- ``facebook`` (Facebook Login tokens): inspect via ``GET /debug_token``,
  refresh via ``GET /oauth/access_token?grant_type=fb_exchange_token``
  (requires META_APP_ID + META_APP_SECRET).

Durability gate: the refresh only runs when the remaining lifetime is below
``DEFAULT_REFRESH_THRESHOLD_DAYS`` (or is unknown) — a known-fresh token is
never churned.

Secret discipline (scar #4): the token value NEVER appears in logs, reprs,
exceptions or stdout. Graph error messages are redacted before logging (a
proxy/WAF may echo the request URL, token included) and an httpx-logger
filter masks the query params httpx itself prints at INFO.

This module is invocable but deliberately NOT self-arming: installing it as
a cron/LaunchAgent is an operator[control-plane] action, and landing the
FIRST valid token is operator[secret]. See docs/runbooks/ig-token-watchdog.md.

Usage (one-shot):
    PYTHONPATH=. python -m backend.services.measurer.ig_token_watchdog

Env:
    IG_LONG_LIVED_TOKEN
    or INSTAGRAM_ACCESS_TOKEN       (required — same precedence as sampler)
    IG_TOKEN_FAMILY                 (optional — instagram|facebook, default instagram)
    META_APP_ID / META_APP_SECRET   (required for family=facebook only)
    IG_TOKEN_ENV_FILE               (persist refreshed token here; without it a
                                     refresh CANNOT be kept → treated as failure)
    IG_TOKEN_STATE_FILE             (optional — expiry sidecar for family=instagram)
    IG_TOKEN_REFRESH_THRESHOLD_DAYS (optional — default 7)

Exit codes:
    0  token fresh, or refreshed AND persisted
    1  configuration error (missing/invalid env)
    2  token invalid, refresh failed, network failure, or refreshed-but-not-
       persistable — operator attention needed
"""

from __future__ import annotations

import asyncio
import fcntl
import json
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

FACEBOOK_GRAPH_BASE = "https://graph.facebook.com/v21.0"
INSTAGRAM_GRAPH_BASE = "https://graph.instagram.com"
DEFAULT_REFRESH_THRESHOLD_DAYS = 7.0
DEFAULT_TIMEOUT = 20.0

TOKEN_ENV_KEYS = ("IG_LONG_LIVED_TOKEN", "INSTAGRAM_ACCESS_TOKEN")
VALID_FAMILIES = ("instagram", "facebook")


class IGTokenWatchdogError(RuntimeError):
    """Raised on Graph/IO errors. Never carries the token value."""


# httpx logs `HTTP Request: GET <full url>` at INFO — with Meta's flow the
# token (and app secret, facebook family) travel as query params, so without
# redaction every watchdog pass would leak them into any INFO-level log sink
# (scar #4).
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


def _redact(text: str, *secrets: str) -> str:
    """Strip known secret values AND token-shaped query params from text.

    Graph error payloads can echo the request URL (proxy/WAF in the path) —
    the message itself must be treated as secret-bearing until scrubbed.
    """
    out = _REDACT_RE.sub(r"\1=<redacted>", text)
    for s in secrets:
        if s:
            out = out.replace(s, "<redacted>")
    return out


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
    """Result of a token inspection. Carries NO secret material.

    expires_at semantics:
      datetime  -> known expiry
      None + never_expires=True  -> Meta's explicit expires_at=0 marker
      None + never_expires=False -> expiry UNKNOWN (absent field / no state
                                    file) — the watchdog refreshes conservatively
    """

    is_valid: bool
    expires_at: datetime | None
    days_remaining: float | None
    never_expires: bool = False
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


def _graph_error_message(body: object, *secrets: str) -> str:
    """Extract a REDACTED error message from a Graph error payload."""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            code = err.get("code", "?")
            message = _redact(str(err.get("message", "unknown Graph error")), *secrets)
            return f"code {code}: {message[:200]}"
    return "unknown Graph error"


async def _graph_get(
    url: str,
    params: dict[str, str],
    *,
    http_client: httpx.AsyncClient | None,
    secrets: tuple[str, ...],
) -> tuple[int, dict]:
    """GET + JSON-decode with network/decode errors mapped to the module error.

    Raising raw httpx errors would leak `exception.request.url` (token in
    query) into tracebacks AND break the CLI exit-code contract (exit 2 for
    operational failure, never an unhandled traceback).
    """
    _ensure_httpx_redaction()
    client = http_client or _get_module_client(DEFAULT_TIMEOUT)
    try:
        resp = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise IGTokenWatchdogError(
            f"network failure calling Graph: {type(exc).__name__}: "
            f"{_redact(str(exc), *secrets)[:200]}"
        ) from None
    try:
        body = resp.json()
    except ValueError:
        raise IGTokenWatchdogError(
            f"non-JSON Graph response (HTTP {resp.status_code}): "
            f"{_redact(resp.text[:120], *secrets)}"
        ) from None
    if not isinstance(body, dict):
        raise IGTokenWatchdogError(
            f"unexpected Graph response shape (HTTP {resp.status_code})"
        )
    return resp.status_code, body


# ── facebook family: /debug_token + fb_exchange_token ─────────


async def inspect_token(
    token: str,
    app_id: str,
    app_secret: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> TokenStatus:
    """Inspect a facebook-family token via ``GET /debug_token``.

    An invalid token is a reportable state, not an exception. Network
    failures DO raise (IGTokenWatchdogError) — they say nothing about the
    token itself.
    """
    now = now or datetime.now(timezone.utc)
    status_code, body = await _graph_get(
        f"{FACEBOOK_GRAPH_BASE}/debug_token",
        {"input_token": token, "access_token": f"{app_id}|{app_secret}"},
        http_client=http_client,
        secrets=(token, app_secret),
    )
    if status_code != 200 or "error" in body:
        return TokenStatus(
            is_valid=False,
            expires_at=None,
            days_remaining=None,
            error=_graph_error_message(body, token, app_secret),
        )
    data = body.get("data") or {}
    if not data.get("is_valid", False):
        return TokenStatus(
            is_valid=False,
            expires_at=None,
            days_remaining=None,
            error="token reported is_valid=false by /debug_token",
        )
    raw = data.get("expires_at")
    if raw is None:
        # Field ABSENT is not the same as explicit 0: treat as unknown so the
        # watchdog refreshes conservatively instead of assuming immortality.
        return TokenStatus(is_valid=True, expires_at=None, days_remaining=None)
    epoch = int(raw)
    if epoch == 0:
        # Meta's explicit marker for a never-expiring token.
        return TokenStatus(
            is_valid=True, expires_at=None, days_remaining=None, never_expires=True
        )
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
    """facebook family: exchange a long-lived token for a NEW long-lived one.

    Pure function of (token, app_id, app_secret) → (new token, expiry).
    Raises :class:`IGTokenWatchdogError` on Graph errors; the message is
    redacted and never contains the token or the app secret.
    """
    now = now or datetime.now(timezone.utc)
    status_code, body = await _graph_get(
        f"{FACEBOOK_GRAPH_BASE}/oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        },
        http_client=http_client,
        secrets=(token, app_secret),
    )
    if status_code != 200 or "error" in body:
        raise IGTokenWatchdogError(
            f"token exchange failed: {_graph_error_message(body, token, app_secret)}"
        )
    new_token = body.get("access_token")
    if not new_token:
        raise IGTokenWatchdogError("token exchange returned no access_token field")
    # Meta may omit expires_in; default to 60 days (conservative, re-gated
    # at the next tick anyway).
    expires_in = int(body.get("expires_in", 60 * 86400) or 60 * 86400)
    return RefreshedToken(
        token=new_token, expires_at=now + timedelta(seconds=expires_in)
    )


# ── instagram family: refresh_access_token + state sidecar ────


async def refresh_instagram_token(
    token: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> RefreshedToken:
    """instagram family: refresh a long-lived Instagram-Login token.

    ``GET graph.instagram.com/refresh_access_token`` — no app credentials.
    Constraint (Meta): the token must be at least 24h old and unexpired.
    """
    now = now or datetime.now(timezone.utc)
    status_code, body = await _graph_get(
        f"{INSTAGRAM_GRAPH_BASE}/refresh_access_token",
        {"grant_type": "ig_refresh_token", "access_token": token},
        http_client=http_client,
        secrets=(token,),
    )
    if status_code != 200 or "error" in body:
        raise IGTokenWatchdogError(
            f"ig refresh failed: {_graph_error_message(body, token)}"
        )
    new_token = body.get("access_token")
    if not new_token:
        raise IGTokenWatchdogError("ig refresh returned no access_token field")
    expires_in = int(body.get("expires_in", 60 * 86400) or 60 * 86400)
    return RefreshedToken(
        token=new_token, expires_at=now + timedelta(seconds=expires_in)
    )


def read_state_expiry(state_file: Path | str | None) -> datetime | None:
    """Read the expiry recorded by a previous refresh (dates only, no token)."""
    if not state_file:
        return None
    path = Path(state_file)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("expires_at")
        return datetime.fromisoformat(raw) if raw else None
    except (ValueError, OSError):
        return None


def write_state_expiry(
    state_file: Path | str, expires_at: datetime, *, refreshed_at: datetime
) -> None:
    """Persist expiry metadata after a refresh. NEVER writes the token."""
    path = Path(state_file)
    payload = {
        "expires_at": expires_at.isoformat(),
        "refreshed_at": refreshed_at.isoformat(),
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


# ── the watchdog pass ─────────────────────────────────────────


async def run_watchdog(
    token: str,
    app_id: str | None = None,
    app_secret: str | None = None,
    *,
    family: str = "instagram",
    threshold_days: float = DEFAULT_REFRESH_THRESHOLD_DAYS,
    state_file: Path | str | None = None,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> WatchdogOutcome:
    """One watchdog pass: establish remaining lifetime, refresh if needed.

    Gate: refresh when days_remaining < threshold OR expiry is unknown
    (absent /debug_token field, or no state sidecar for the instagram
    family). Explicit never-expiring tokens are left alone.

    Provenance is logged WITHOUT the token value (scar #4).
    """
    now = now or datetime.now(timezone.utc)
    if family not in VALID_FAMILIES:
        raise ValueError(f"unknown token family: {family!r}")

    # 1. Establish status.
    if family == "facebook":
        if not app_id or not app_secret:
            raise ValueError("facebook family requires app_id and app_secret")
        try:
            status = await inspect_token(
                token, app_id, app_secret, http_client=http_client, now=now
            )
        except IGTokenWatchdogError as exc:
            logger.error("[ig-token-watchdog] inspection failed: %s", exc)
            return WatchdogOutcome(
                action="error",
                status=TokenStatus(False, None, None, error=str(exc)),
                error=str(exc),
            )
        if not status.is_valid:
            logger.error("[ig-token-watchdog] token INVALID: %s", status.error)
            return WatchdogOutcome(action="invalid", status=status, error=status.error)
    else:
        expires_at = read_state_expiry(state_file)
        days = (
            (expires_at - now).total_seconds() / 86400.0 if expires_at else None
        )
        status = TokenStatus(
            is_valid=True, expires_at=expires_at, days_remaining=days
        )

    # 2. The durability gate.
    if status.never_expires:
        logger.info("[ig-token-watchdog] token never expires; nothing to do")
        return WatchdogOutcome(action="fresh", status=status)
    if status.days_remaining is not None and status.days_remaining >= threshold_days:
        logger.info(
            "[ig-token-watchdog] token fresh, expiry=%s (%.1f days left, threshold %.1f)",
            status.expires_at.date().isoformat() if status.expires_at else "?",
            status.days_remaining,
            threshold_days,
        )
        return WatchdogOutcome(action="fresh", status=status)
    if status.days_remaining is None:
        logger.info(
            "[ig-token-watchdog] expiry UNKNOWN (%s family, no %s) — refreshing conservatively",
            family,
            "/debug_token expiry" if family == "facebook" else "state file",
        )
    else:
        logger.info(
            "[ig-token-watchdog] token expiring in %.1f days (< %.1f) — refreshing",
            status.days_remaining,
            threshold_days,
        )

    # 3. Refresh.
    try:
        if family == "facebook":
            assert app_id is not None and app_secret is not None
            refreshed = await refresh_long_lived_token(
                token, app_id, app_secret, http_client=http_client, now=now
            )
        else:
            refreshed = await refresh_instagram_token(
                token, http_client=http_client, now=now
            )
    except IGTokenWatchdogError as exc:
        logger.error("[ig-token-watchdog] refresh FAILED: %s", exc)
        return WatchdogOutcome(action="error", status=status, error=str(exc))

    if family == "instagram" and state_file:
        try:
            write_state_expiry(state_file, refreshed.expires_at, refreshed_at=now)
        except OSError as exc:
            # State is an optimization for the gate, not the token itself —
            # log loudly but do not fail the refresh over it.
            logger.warning("[ig-token-watchdog] state write failed: %s", exc)

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


# ── persistence ───────────────────────────────────────────────


def persist_token_to_env_file(
    path: Path | str,
    new_token: str,
    *,
    key: str = "IG_LONG_LIVED_TOKEN",
) -> None:
    """Rewrite ``KEY=value`` in an env file with the refreshed token.

    - Refuses to create a new file: the FIRST token landing is an operator
      action; this function only rotates an existing installation.
    - Holds an exclusive flock on the target for the whole read→write span
      (a concurrent writer's update must not be clobbered by our stale
      snapshot), writes via temp file + atomic rename, and enforces mode
      0600 on both (scar #4: no world-readable secret).
    - Preserves every other line untouched.
    """
    path = Path(path)
    if not path.is_file():
        raise IGTokenWatchdogError(
            f"env file not found: {path} — first token landing is operator-owned"
        )
    try:
        lock_fd = os.open(path, os.O_RDONLY)
    except OSError as exc:
        raise IGTokenWatchdogError(f"cannot open env file for locking: {exc}") from None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
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

        fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=".ig-token-", text=True
        )
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
    except OSError as exc:
        raise IGTokenWatchdogError(f"env file persist failed: {exc}") from None
    finally:
        os.close(lock_fd)
    logger.info(
        "[ig-token-watchdog] persisted refreshed token to %s (key=%s, mode=0600)",
        path,
        key,
    )


# ── CLI ───────────────────────────────────────────────────────


def _resolve_token_from_env() -> tuple[str, str] | None:
    """Return (token, env_key_it_came_from) with sampler-identical precedence."""
    for env_key in TOKEN_ENV_KEYS:
        value = os.environ.get(env_key)
        if value:
            return value, env_key
    return None


async def run_from_env(*, http_client: httpx.AsyncClient | None = None) -> int:
    """CLI body: read config from env, run one pass, persist the result.

    A refresh that cannot be persisted is a FAILURE (exit 2), not a warning:
    the new token would be dropped and the cron would sit green while the
    live token marches toward expiry (family #2, esiste≠armato).
    """
    resolved = _resolve_token_from_env()
    if resolved is None:
        logger.error(
            "[ig-token-watchdog] no token in env (set %s)",
            " or ".join(TOKEN_ENV_KEYS),
        )
        return 1
    token, env_key = resolved

    family = os.environ.get("IG_TOKEN_FAMILY", "instagram").strip().lower()
    if family not in VALID_FAMILIES:
        logger.error(
            "[ig-token-watchdog] IG_TOKEN_FAMILY must be one of %s", VALID_FAMILIES
        )
        return 1

    app_id = os.environ.get("META_APP_ID")
    app_secret = os.environ.get("META_APP_SECRET")
    if family == "facebook" and (not app_id or not app_secret):
        logger.error(
            "[ig-token-watchdog] family=facebook requires META_APP_ID and "
            "META_APP_SECRET (the fb_exchange_token flow needs app credentials)"
        )
        return 1

    try:
        threshold = float(
            os.environ.get(
                "IG_TOKEN_REFRESH_THRESHOLD_DAYS",
                str(DEFAULT_REFRESH_THRESHOLD_DAYS),
            )
        )
    except ValueError:
        logger.error(
            "[ig-token-watchdog] IG_TOKEN_REFRESH_THRESHOLD_DAYS is not a number"
        )
        return 1

    state_file = os.environ.get("IG_TOKEN_STATE_FILE") or None

    try:
        outcome = await run_watchdog(
            token,
            app_id,
            app_secret,
            family=family,
            threshold_days=threshold,
            state_file=state_file,
            http_client=http_client,
        )
    finally:
        if http_client is None:
            await close_ig_token_watchdog_client()

    if outcome.action == "fresh":
        return 0
    if outcome.action in ("invalid", "error"):
        return 2

    # action == "refreshed": persisting is NOT optional.
    env_file = os.environ.get("IG_TOKEN_ENV_FILE")
    if not env_file:
        logger.error(
            "[ig-token-watchdog] refreshed but IG_TOKEN_ENV_FILE not set — the "
            "new token has nowhere to live and is DROPPED; set IG_TOKEN_ENV_FILE "
            "(the old token stays valid until its original expiry)"
        )
        return 2
    assert outcome.new_token is not None
    try:
        persist_token_to_env_file(env_file, outcome.new_token, key=env_key)
    except IGTokenWatchdogError as exc:
        logger.error("[ig-token-watchdog] persist FAILED: %s", exc)
        return 2
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    sys.exit(asyncio.run(run_from_env()))


if __name__ == "__main__":
    main()
