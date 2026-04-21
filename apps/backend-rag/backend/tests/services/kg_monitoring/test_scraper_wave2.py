"""
Wave 2 tests for LegalScraper extensions:
- UA rotation (round-robin, deterministic)
- HTTP/2 enabled on the httpx client
- Playwright fallback trigger on block statuses (403/406/503)
- Rate-limit compliance after Playwright fallback

NOTE: Playwright is MOCKED here — we assert the orchestration (when is the
fallback invoked? what UA does it use? what does the caller see?) without
launching a real browser. An integration test that actually drives Chromium
belongs in a separate job because of timing and binary-install cost.

Run:
    PYTHONPATH=. pytest backend/tests/services/kg_monitoring/test_scraper_wave2.py -q
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.kg_monitoring.scraper import (
    REALISTIC_USER_AGENTS,
    LegalScraper,
    SourceConfig,
    SourceType,
    UserAgentRotator,
)


def _source(
    source_id: str = "test_src",
    **overrides,
) -> SourceConfig:
    defaults = dict(
        source_id=source_id,
        name="Test Source",
        base_url="https://example.go.id",
        source_type=SourceType.GOVERNMENT_SITE,
        search_paths=["/"],
        selectors={},
        rate_limit_delay=0.0,  # tests don't need real sleeps
        timeout=5,
        max_retries=2,
    )
    defaults.update(overrides)
    return SourceConfig(**defaults)


class TestUserAgentRotator:
    """Deterministic round-robin — load-bearing for tests AND real scrapes."""

    def test_rotation_cycles(self) -> None:
        rotator = UserAgentRotator(agents=["UA-A", "UA-B", "UA-C"])
        assert rotator.size == 3
        order = [rotator.next() for _ in range(7)]
        # Verify wrap-around: 7 picks from 3 agents → A B C A B C A.
        assert order == ["UA-A", "UA-B", "UA-C", "UA-A", "UA-B", "UA-C", "UA-A"]

    def test_default_agents_are_non_empty(self) -> None:
        rotator = UserAgentRotator()
        assert rotator.size >= 3
        # Every default UA must look like a real browser.
        for ua in REALISTIC_USER_AGENTS:
            assert "Mozilla/5.0" in ua

    def test_empty_agents_rejected(self) -> None:
        with pytest.raises(ValueError):
            UserAgentRotator(agents=[])


class TestHttp2Enabled:
    """We pass http2=True to httpx.AsyncClient; verify that's the actual call."""

    def test_client_created_with_http2_true(self) -> None:
        scraper = LegalScraper(custom_sources={"test": _source()})
        with patch(
            "backend.services.kg_monitoring.scraper.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client_cls.return_value = MagicMock(is_closed=False)
            client = scraper._get_client()
            # The first positional/kwarg call MUST include http2=True.
            kwargs = mock_client_cls.call_args.kwargs
            assert kwargs.get("http2") is True, (
                f"httpx.AsyncClient called without http2=True: {kwargs}"
            )
            assert client is mock_client_cls.return_value

    def test_client_falls_back_to_http1_if_h2_missing(self) -> None:
        """If the h2 package is absent at runtime, the code should still produce
        a working client (HTTP/1.1). Simulated via ImportError on first call."""
        scraper = LegalScraper(custom_sources={"test": _source()})
        call_count = {"n": 0}

        def fake_client(*args, **kwargs):
            call_count["n"] += 1
            if kwargs.get("http2"):
                raise ImportError("no h2 in this env")
            return MagicMock(is_closed=False)

        with patch(
            "backend.services.kg_monitoring.scraper.httpx.AsyncClient",
            side_effect=fake_client,
        ):
            client = scraper._get_client()
            # Two calls: one with http2=True (fails), one without (succeeds).
            assert call_count["n"] == 2
            assert client is not None


class TestUARotationDuringFetch:
    """Each retry attempt must use a different UA."""

    @pytest.mark.asyncio
    async def test_every_attempt_uses_rotated_ua(self) -> None:
        rotator = UserAgentRotator(agents=["UA-A", "UA-B", "UA-C"])
        scraper = LegalScraper(custom_sources={"s": _source()}, user_agent_rotator=rotator)
        source = scraper.sources["s"]
        source.max_retries = 3

        seen_uas: list[str] = []

        async def fake_get(url, headers, timeout):  # noqa: ARG001
            seen_uas.append(headers["User-Agent"])
            # Always 403 so we force all retries.
            resp = httpx.Response(
                status_code=403,
                request=httpx.Request("GET", url),
            )
            raise httpx.HTTPStatusError("blocked", request=resp.request, response=resp)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=fake_get)

        result = await scraper._fetch_with_retry(mock_client, "https://example.go.id", source)
        assert result is None  # all retries failed
        assert seen_uas == ["UA-A", "UA-B", "UA-C"], f"UA did not rotate: {seen_uas}"
        # Stat counter reflects 3 rotations.
        assert scraper.scrape_stats["user_agent_rotations"] == 3

    @pytest.mark.asyncio
    async def test_ua_not_rotated_when_disabled(self) -> None:
        scraper = LegalScraper(custom_sources={"s": _source(rotate_user_agent=False)})
        source = scraper.sources["s"]
        original_ua = source.headers["User-Agent"]

        seen_uas: list[str] = []

        async def fake_get(url, headers, timeout):  # noqa: ARG001
            seen_uas.append(headers["User-Agent"])
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=fake_get)

        await scraper._fetch_with_retry(mock_client, "https://example.go.id", source)
        # With rotation off the UA must be the one from source.headers verbatim.
        assert seen_uas == [original_ua]
        assert scraper.scrape_stats["user_agent_rotations"] == 0


class TestPlaywrightFallback:
    """Playwright is spun up only after httpx exhausts retries on a block
    status AND the source has opted in."""

    @pytest.mark.asyncio
    async def test_fallback_triggered_on_403_exhaustion(self) -> None:
        scraper = LegalScraper(
            custom_sources={"s": _source(use_playwright_fallback=True, max_retries=2)},
        )
        source = scraper.sources["s"]

        async def all_403(url, headers, timeout):  # noqa: ARG001
            resp = httpx.Response(
                status_code=403,
                request=httpx.Request("GET", url),
            )
            raise httpx.HTTPStatusError("blocked", request=resp.request, response=resp)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=all_403)

        # Mock the playwright fallback directly — we want to assert that it's
        # called, not test playwright itself.
        fake_response = httpx.Response(
            status_code=200,
            content=b"<html>rendered</html>",
            request=httpx.Request("GET", "https://example.go.id"),
        )
        with patch.object(
            scraper,
            "_fetch_with_playwright",
            AsyncMock(return_value=fake_response),
        ) as pw_mock:
            result = await scraper._fetch_with_retry(
                mock_client,
                "https://example.go.id",
                source,
            )
            pw_mock.assert_awaited_once()
            assert result is fake_response
            assert result.text == "<html>rendered</html>"

    @pytest.mark.asyncio
    async def test_fallback_not_triggered_on_timeout_without_block(self) -> None:
        """Timeouts are NOT block-status → don't burn Playwright for every
        flaky network hiccup."""
        scraper = LegalScraper(
            custom_sources={"s": _source(use_playwright_fallback=True, max_retries=2)},
        )
        source = scraper.sources["s"]

        async def always_timeout(url, headers, timeout):  # noqa: ARG001
            raise httpx.TimeoutException("slow")

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=always_timeout)

        with patch.object(
            scraper,
            "_fetch_with_playwright",
            AsyncMock(return_value=None),
        ) as pw_mock:
            result = await scraper._fetch_with_retry(
                mock_client,
                "https://example.go.id",
                source,
            )
            pw_mock.assert_not_awaited()
            assert result is None

    @pytest.mark.asyncio
    async def test_fallback_not_triggered_when_disabled(self) -> None:
        """Source without ``use_playwright_fallback`` never pays the browser tax."""
        scraper = LegalScraper(
            custom_sources={"s": _source(use_playwright_fallback=False, max_retries=2)},
        )
        source = scraper.sources["s"]

        async def all_403(url, headers, timeout):  # noqa: ARG001
            resp = httpx.Response(
                status_code=403,
                request=httpx.Request("GET", url),
            )
            raise httpx.HTTPStatusError("blocked", request=resp.request, response=resp)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=all_403)

        with patch.object(
            scraper,
            "_fetch_with_playwright",
            AsyncMock(return_value=None),
        ) as pw_mock:
            result = await scraper._fetch_with_retry(
                mock_client,
                "https://example.go.id",
                source,
            )
            pw_mock.assert_not_awaited()
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_with_playwright_uses_rotated_ua(self) -> None:
        """The browser gets the same UA rotation the httpx client would have."""
        rotator = UserAgentRotator(agents=["UA-A", "UA-B"])
        scraper = LegalScraper(
            custom_sources={"s": _source(use_playwright_fallback=True)},
            user_agent_rotator=rotator,
        )
        source = scraper.sources["s"]

        # Full playwright chain as AsyncMock so we can read back the UA.
        fake_page = MagicMock()
        fake_page.goto = AsyncMock()
        fake_page.wait_for_load_state = AsyncMock()
        fake_page.content = AsyncMock(return_value="<html>ok</html>")
        fake_context = MagicMock()
        fake_context.new_page = AsyncMock(return_value=fake_page)
        fake_context.close = AsyncMock()
        fake_browser = MagicMock()
        fake_browser.new_context = AsyncMock(return_value=fake_context)
        fake_browser.close = AsyncMock()
        fake_pw = MagicMock()
        fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)

        class _PWCtx:
            async def __aenter__(self):
                return fake_pw

            async def __aexit__(self, *_):
                return False

        def fake_async_playwright():
            return _PWCtx()

        with patch.dict(
            "sys.modules",
            {
                "playwright": MagicMock(),
                "playwright.async_api": MagicMock(async_playwright=fake_async_playwright),
            },
        ):
            response = await scraper._fetch_with_playwright("https://example.go.id", source)

        assert response is not None
        assert response.status_code == 200
        assert response.text == "<html>ok</html>"
        # new_context was called with one of our UAs.
        ua_used = fake_browser.new_context.call_args.kwargs["user_agent"]
        assert ua_used in {"UA-A", "UA-B"}
        # Counters bumped.
        assert scraper.scrape_stats["playwright_fallback_invocations"] == 1
        assert scraper.scrape_stats["playwright_fallback_successes"] == 1


class TestRateLimitCompliance:
    """We must sleep AT LEAST rate_limit_delay seconds between requests, even
    on the Playwright success path — otherwise we just shift the abuse to a
    different transport."""

    @pytest.mark.asyncio
    async def test_rate_limit_sleep_after_playwright_fallback(self) -> None:
        scraper = LegalScraper(
            custom_sources={
                "s": _source(
                    use_playwright_fallback=True,
                    rate_limit_delay=0.05,
                    max_retries=1,
                ),
            },
        )
        source = scraper.sources["s"]

        async def always_403(url, headers, timeout):  # noqa: ARG001
            resp = httpx.Response(
                status_code=403,
                request=httpx.Request("GET", url),
            )
            raise httpx.HTTPStatusError("blocked", request=resp.request, response=resp)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=always_403)

        fake_response = httpx.Response(
            status_code=200,
            content=b"ok",
            request=httpx.Request("GET", "https://example.go.id"),
        )

        sleeps: list[float] = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        with patch.object(
            scraper,
            "_fetch_with_playwright",
            AsyncMock(return_value=fake_response),
        ), patch("asyncio.sleep", fake_sleep):
            result = await scraper._fetch_with_retry(
                mock_client,
                "https://example.go.id",
                source,
            )

        assert result is fake_response
        # At least one sleep must equal the rate_limit_delay (final sleep).
        assert 0.05 in sleeps, f"rate_limit_delay never slept: {sleeps}"
