"""Async Chromium headless screenshot client via Playwright.

Budget: < 3s/slide (design §5.2). Uses data: URL so we don't hit disk.

Playwright is imported lazily — if the package is missing, screenshot calls
return an :class:`ScreenshotResult` with ``ok=False`` + actionable error,
rather than crashing the pipeline (Law 4 Graceful degradation).
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class ScreenshotError(RuntimeError):
    """Raised only on configuration errors (not per-call)."""


@dataclass
class ScreenshotResult:
    ok: bool
    png_bytes: bytes | None = None
    duration_ms: float = 0.0
    error: str | None = None
    width: int = 0
    height: int = 0


class PlaywrightClient:
    """Renders HTML → PNG via headless Chromium.

    A single :class:`PlaywrightClient` manages one persistent browser process;
    call :meth:`start` / :meth:`stop` for batch rendering, or use
    :meth:`screenshot_once` for single-shot.
    """

    def __init__(
        self,
        *,
        timeout_ms: int = 5000,
        wait_until: str = "networkidle",
    ) -> None:
        self.timeout_ms = timeout_ms
        self.wait_until = wait_until
        self._playwright: Any | None = None
        self._browser: Any | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch Chromium. Call before repeated screenshots."""
        try:
            from playwright.async_api import async_playwright  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ScreenshotError(
                "playwright is not installed — "
                "run `pip install playwright && playwright install chromium`"
            ) from exc
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self) -> PlaywrightClient:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    # ── Single shot / batch screenshot ─────────────────────────────────

    async def screenshot(
        self,
        html: str,
        *,
        width: int,
        height: int,
    ) -> ScreenshotResult:
        """Render HTML via data URL and capture a PNG at the given viewport."""
        if self._browser is None:
            return ScreenshotResult(
                ok=False,
                error="browser not started — call start() first",
                width=width,
                height=height,
            )

        start = time.perf_counter()
        context = None
        page = None
        try:
            context = await self._browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page = await context.new_page()
            data_url = _html_to_data_url(html)
            await page.goto(
                data_url,
                wait_until=self.wait_until,
                timeout=self.timeout_ms,
            )
            png = await page.screenshot(
                full_page=False,
                type="png",
                clip={"x": 0, "y": 0, "width": width, "height": height},
            )
            duration_ms = (time.perf_counter() - start) * 1000
            return ScreenshotResult(
                ok=True,
                png_bytes=png,
                duration_ms=duration_ms,
                width=width,
                height=height,
            )
        except Exception as exc:  # noqa: BLE001
            return ScreenshotResult(
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
                width=width,
                height=height,
            )
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:  # noqa: BLE001
                    pass
            if context is not None:
                try:
                    await context.close()
                except Exception:  # noqa: BLE001
                    pass

    async def screenshot_once(
        self,
        html: str,
        *,
        width: int,
        height: int,
    ) -> ScreenshotResult:
        """One-shot: start, screenshot, stop. Convenience for test fixtures."""
        try:
            await self.start()
        except ScreenshotError as exc:
            return ScreenshotResult(
                ok=False,
                error=str(exc),
                width=width,
                height=height,
            )
        try:
            return await self.screenshot(html, width=width, height=height)
        finally:
            await self.stop()


def _html_to_data_url(html: str) -> str:
    encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
    return f"data:text/html;base64,{encoded}"
