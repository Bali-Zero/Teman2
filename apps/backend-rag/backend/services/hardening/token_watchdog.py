"""TokenWatchdog — generic 60-day token expiry alerting.

Provider-agnostic: each probe returns a :class:`TokenExpiryReport` with an
optional ``expires_at``. If expiry is within ``warn_threshold_days``, the
watchdog emits a Telegram alert. A probe that can't determine expiry
(e.g. Meta Graph ``/debug_token`` unavailable) returns ``expires_at=None``
and the watchdog logs "unknown" without alerting — we don't cry wolf.

Wiring for IG + LinkedIn is injected by the caller: we keep the adapter
code separate from provider-specific HTTP so this module is pure.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.services.review.telegram_adapter import TelegramReviewAdapter

logger = logging.getLogger(__name__)


DEFAULT_WARN_DAYS = 7
DEFAULT_CRITICAL_DAYS = 2


@dataclass
class TokenExpiryReport:
    provider: str
    ok: bool
    expires_at: datetime | None = None
    days_remaining: float | None = None
    note: str = ""
    error: str | None = None


TokenProbe = Callable[[], Awaitable[TokenExpiryReport]]


@dataclass
class TokenWatchdogResult:
    ran_at: datetime
    reports: list[TokenExpiryReport] = field(default_factory=list)
    warnings_sent: int = 0
    errors: list[str] = field(default_factory=list)


class TokenWatchdog:
    """Run N probes, alert on any that will expire soon."""

    def __init__(
        self,
        probes: list[tuple[str, TokenProbe]],
        telegram: TelegramReviewAdapter,
        owner_chat_id: str | int,
        *,
        warn_threshold_days: int = DEFAULT_WARN_DAYS,
        critical_threshold_days: int = DEFAULT_CRITICAL_DAYS,
    ) -> None:
        self.probes = probes
        self.telegram = telegram
        self.owner_chat_id = str(owner_chat_id)
        self.warn_threshold = timedelta(days=warn_threshold_days)
        self.critical_threshold = timedelta(days=critical_threshold_days)

    async def sweep_once(
        self,
        *,
        now: datetime | None = None,
    ) -> TokenWatchdogResult:
        now = now or datetime.now(timezone.utc)
        result = TokenWatchdogResult(ran_at=now)

        for label, probe in self.probes:
            try:
                report = await probe()
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"probe {label}: {type(exc).__name__}: {exc}")
                continue
            # attach days_remaining from the provided expires_at
            if report.expires_at is not None:
                report.days_remaining = (
                    (report.expires_at - now).total_seconds() / 86400.0
                )
            result.reports.append(report)

            if self._should_alert(report, now=now):
                if await self._send_alert(report, now=now):
                    result.warnings_sent += 1

        return result

    # ── Internal ───────────────────────────────────────────────────

    def _should_alert(self, report: TokenExpiryReport, *, now: datetime) -> bool:
        if not report.ok:
            return False
        if report.expires_at is None:
            return False
        remaining = report.expires_at - now
        return remaining <= self.warn_threshold

    async def _send_alert(
        self, report: TokenExpiryReport, *, now: datetime,
    ) -> bool:
        assert report.expires_at is not None
        remaining = report.expires_at - now
        days = remaining.total_seconds() / 86400.0
        critical = remaining <= self.critical_threshold
        icon = "🚨" if critical else "⏰"
        text = (
            f"{icon} <b>Token {_escape_html(report.provider)} scade fra "
            f"{days:.1f} giorni</b>\n"
            f"<i>Expires at:</i> <code>"
            f"{report.expires_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}"
            f"</code>"
        )
        if report.note:
            text += f"\n<i>{_escape_html(report.note)}</i>"
        sr = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=text,
        )
        return sr.ok


def _escape_html(value: str) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ── Example probes (injectable) ───────────────────────────────────


async def probe_meta_graph_token(
    *,
    access_token: str,
    http_client,  # httpx.AsyncClient
    timeout: float = 10.0,
) -> TokenExpiryReport:
    """Probe Meta Graph ``/debug_token`` endpoint. Returns ``expires_at=None``
    on any failure so watchdog stays silent (better than crying wolf).
    """
    provider = "meta_graph_ig"
    try:
        resp = await http_client.get(
            "https://graph.facebook.com/v20.0/debug_token",
            params={
                "input_token": access_token,
                "access_token": access_token,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            return TokenExpiryReport(
                provider=provider,
                ok=True,
                expires_at=None,
                note=f"debug_token HTTP {resp.status_code}",
            )
        data = resp.json().get("data", {}) or {}
        expires_at = data.get("expires_at")
        if not expires_at:
            # 0 means "never expires" per Meta docs (rare for user tokens)
            return TokenExpiryReport(
                provider=provider,
                ok=True,
                expires_at=None,
                note="no_expiration_reported",
            )
        return TokenExpiryReport(
            provider=provider,
            ok=True,
            expires_at=datetime.fromtimestamp(int(expires_at), tz=timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001
        return TokenExpiryReport(
            provider=provider,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
