# Browser Automation Consolidation Implementation Plan (v2.1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Version**: v2.1 (2026-04-08) — incorporates first-round (Gemini Flash, DeepSeek R1 32b, Qwen 3.5 9b) and second-round (Codex GPT-5.4 xhigh, Gemini 2.5 Pro, DeepSeek R1 32b) review findings.

**Goal:** Consolidate three disconnected browser automation implementations (`bali-intel-scraper/browser.py`, `osint-nexus/ahu.py` Playwright inline, empty `nuzantara-mcp-browser/`) under a single shared `packages/browser-core/` package, fix the AHU orchestration gap, add a FastMCP server for external consumers, and make `ahu.go.id` scraping safer with stealth + DOM-clobber fix.

**Architecture:**
1. **Extract** `bali-intel-scraper/backend/scrapers/browser.py` into a new shared package `packages/browser-core/` with explicit `BrowserConfig` (no more `config.settings` coupling), stdlib `logging`, constructor-injected rate limiter, and **no module-level singleton**. Each consumer instantiates its own `BrowserManager`.
2. **Rewrite** `osint-nexus/scrapers/ahu.py` to consume `browser-core` via a lazy per-process instance with `atexit` cleanup. Fix `_fetch_detail` DOM-clobber bug.
3. **Fill** the empty `apps/nuzantara-mcp-browser/` with a FastMCP server exposing 6 tools. Use FastMCP's `lifespan` decorator for clean shutdown. Use in-memory `Client` (FastMCP's official test pattern) for unit tests — not mock patching.
4. **Register** `AHUScraper` in `osint_nexus.pipeline.run_full_pipeline()` so batch orchestration can reach it.
5. **Validate** the stealth patches via a dedicated test against `bot.sannysoft.com` (opt-in) — independent of `ahu.go.id`.
6. **Validate** the AHU parser via snapshot-based tests using a saved HTML dump — independent of live network.

**Consolidation clarification**: "Consolidation" in this plan means **one shared codebase** (`packages/browser-core/`) with **multiple independent per-app instances**. It is NOT a single shared runtime service. Each app owns its own `BrowserManager` lifecycle because their workloads differ (rate limiting, locale, timezone, pool size). Reviewer Gemini flagged this as "not real consolidation" — I reject that framing. A shared library consumed by multiple apps is the correct level of consolidation for this codebase; promoting it to a separate process would add operational complexity without proportionate benefit.

**Tech Stack:**
- Python 3.11+
- `playwright` ≥ 1.40 (already pinned in both apps)
- `fastmcp` ≥ 2.0 (verify current version in Task 6)
- `pytest` + `pytest-asyncio` (already in both apps)

**Out of scope (explicit non-goals):**
- No new browser automation tools (no Browser Use, Stagehand, Skyvern, Playwright MCP upstream).
- No changes to `bali-intel-scraper/scripts/unified_scraper.py` (production pipeline, doesn't use browser).
- No changes to `claude-in-chrome` MCP usage by Claude Code interactive (root CLAUDE.md §2 rule untouched).
- No new cron jobs or launchd plists.
- No changes to LPSE, LHKPN, Putusan, Wiki, News scrapers — only AHU.
- **No Strategy A (editable path dep to `bali-intel-scraper`)** — removed in v2 based on 3/3 reviewer consensus. Only Strategy B (shared `browser-core`) remains.

**Review fixes applied in v2 (vs v1):**
- Removed Strategy A/B forking — committed to Strategy B.
- Added Task 3.5 (stealth patch validation against bot.sannysoft.com).
- Added Task 4.5 (snapshot-based AHU parser test).
- Added Task 6.5 (shutdown lifecycle: FastMCP `lifespan` + `atexit`).
- Updated Task 4 (`_ahu_browser` now lazy-initialized, not module-level singleton).
- Updated Task 7 (FastMCP test pattern = in-memory Client, not mock-patch; correct decorator is `@server.tool` without parens).
- Updated Task 4 Step 2 (package manager detection fallback: uv → poetry → pip).
- Updated rollback plan (atomic per-task commit sequence).
- Clarified Task 0 wording: any grep hit = HALT + human sign-off required.
- Documented per-process BrowserConfig as intentional, not accidental.

**v2.1 micro-fixes (second-round: Codex GPT-5.4 xhigh, Gemini 2.5 Pro, DeepSeek R1 32b):**
- N1: Added `addopts = "-m 'not integration and not stealth'"` to all pyproject.toml pytest sections — `pytest` default run now actually excludes opt-in markers.
- N2: Task 4.5 gains `test_ahu_scraper_produces_records_from_fixture` — monkeypatches `_get_browser()` and runs `AHUScraper.scrape()` end-to-end against HTML fixture, proving record construction not just selector matching.
- N3: Task 4 `atexit` documented as best-effort safety net; primary shutdown path is explicit `await _get_browser().close()` by runtime owner.
- N4: Task 7 Step 6 rewritten — connects in-memory Client, calls a tool (forces lifespan enter), disconnects, then verifies no orphan Chromium.
- N5: Task 4 Step 1 pip fallback now branches `requirements.txt`-only projects separately (appends `-e ../../packages/browser-core`).

**Pre-flight verification (do this before Task 1):**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git status                                            # clean working tree on feat/browser-consolidation
git branch --show-current                             # must print: feat/browser-consolidation
python -c "import sys; assert sys.version_info >= (3, 11)"
ls apps/bali-intel-scraper/backend/scrapers/browser.py
ls apps/osint-nexus/osint_nexus/scrapers/ahu.py
ls apps/nuzantara-mcp-browser/.venv
```

Expected: all checks pass silently, branch is `feat/browser-consolidation`.

---

## Task 0: Pre-flight — verify AHU bypass is not intentional (BLOCKING GATE)

**Context**: Before editing `pipeline.py`, rule out that `AHUScraper` was deliberately excluded. This is a **blocking gate**: any hit from the grep commands halts the plan and requires explicit human sign-off before proceeding.

**Files:**
- Read: `apps/osint-nexus/` entire tree
- Read: git log for `apps/osint-nexus/osint_nexus/pipeline.py`
- Read: `~/.claude/projects/-Users-nuzantara/memory/project_osint_layer*.md`

- [ ] **Step 1: Grep for AHU exclusion comments in code/docs**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
grep -rn -i "ahu" apps/osint-nexus/ --include="*.py" --include="*.md" | grep -iE "skip|exclud|disable|bypass|todo|fixme|ban|anti.?bot|legal|rate.?limit"
```

**Rule**: any non-empty output → HALT, surface to user, do not proceed until user explicitly says "proceed anyway". An empty output is required to continue.

- [ ] **Step 2: Git log audit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git log -p --all -- apps/osint-nexus/osint_nexus/pipeline.py | grep -B2 -A6 "scraper_map\|scrapers = {"
```

Look for any commit that **removed** `"ahu": AHUScraper` from the dict with a rationale message. If found → HALT + surface.

- [ ] **Step 3: Memory audit**

```bash
grep -rn -i "ahu" ~/.claude/projects/-Users-nuzantara/memory/ | grep -iE "on.?demand|skip|exclud|batch|cron|dont.?register|never"
```

The Layer 26 memory mentions AHU "on-demand" as a scheduling *hint* (not on a fixed schedule). That's OK. What triggers a HALT: any phrase like "never from batch", "AHU exclusion", "deliberately skip AHU".

- [ ] **Step 4: Sign-off (only if all previous steps clean)**

Write a single sentence to `apps/nuzantara-mcp-browser/TASK0_CLEAR.md`:

```
Task 0 cleared on <ISO date>: grep/git/memory all clean. AHU exclusion is unintentional.
```

Commit:
```bash
git add apps/nuzantara-mcp-browser/TASK0_CLEAR.md
git commit -m "chore(mcp-browser): Task 0 cleared — AHU exclusion unintentional"
```

---

## Task 1: Failing regression test for AHU stealth bypass

**Files:**
- Create: `apps/osint-nexus/tests/test_ahu_uses_manager.py`

- [ ] **Step 1: Write the failing AST test**

```python
"""Regression: AHUScraper must use shared browser-core, not raw Playwright.

The current code imports `async_playwright` directly, bypassing stealth
patches (webdriver hide, canvas noise, chrome.runtime, navigator, permissions).
This test fails today. It passes after Task 4.
"""
from __future__ import annotations

import ast
from pathlib import Path


AHU_PATH = Path(__file__).resolve().parents[1] / "osint_nexus" / "scrapers" / "ahu.py"


def test_ahu_does_not_import_async_playwright_directly() -> None:
    """Must NOT import `async_playwright` from playwright.async_api."""
    source = AHU_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "playwright.async_api":
            for alias in node.names:
                if alias.name == "async_playwright":
                    offending.append(f"line {node.lineno}")

    assert not offending, (
        f"AHU imports async_playwright directly, bypassing stealth: {offending}"
    )


def test_ahu_source_imports_from_browser_core() -> None:
    """Positive check: AHU must import from browser_core (Strategy B)."""
    source = AHU_PATH.read_text(encoding="utf-8")
    has_browser_core_import = (
        "from browser_core import" in source
        or "import browser_core" in source
    )
    assert has_browser_core_import, "AHU does not import from browser_core"
```

- [ ] **Step 2: Run — expect 2 failures**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -m pytest tests/test_ahu_uses_manager.py -v
```

- [ ] **Step 3: Commit failing test**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/osint-nexus/tests/test_ahu_uses_manager.py
git commit -m "test(osint-nexus): failing regression for AHU stealth bypass"
```

---

## Task 2: Audit `browser.py` for extraction feasibility

**Context**: Strategy B (extract to `packages/browser-core/`) is chosen. This task verifies that extraction is feasible without breaking `bali-intel-scraper` and lists every coupling point that the extraction must break.

- [ ] **Step 1: Full read of current browser.py**

```bash
cat ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/bali-intel-scraper/backend/scrapers/browser.py | wc -l
# Expected: ~345 lines
```

- [ ] **Step 2: Catalogue every app-coupled import**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/bali-intel-scraper
grep -n "^from config\|^from backend" backend/scrapers/browser.py
```

Expected output:
```
18:from config.settings import settings
19:from backend.core.logger import get_logger, LogAction
20:from backend.core.rate_limiter import limit_scrape_request
```

- [ ] **Step 3: Catalogue every `settings.scraping.*` read**

```bash
grep -n "settings\.scraping\." backend/scrapers/browser.py
```

Expected:
```
136:        self.config = config or BrowserConfig(headless=settings.scraping.headless)
140:        self._max_contexts = settings.scraping.max_concurrent_browsers
288:                        timeout=settings.scraping.page_load_timeout * 1000,
```

- [ ] **Step 4: Catalogue `LogAction` enum usage**

```bash
grep -n "LogAction\." backend/scrapers/browser.py
```

Each site must become a plain stdlib `logger.info(...)` call in `browser_core/manager.py`. Record count.

- [ ] **Step 5: Check module-level singleton**

```bash
grep -n "^browser_manager\s*=" backend/scrapers/browser.py
```

Expected: `323:browser_manager = BrowserManager()`. This is the footgun — in Task 3 the singleton stays ONLY in the thin wrapper, not in `browser_core`.

- [ ] **Step 6: Check for existing pyproject.toml**

```bash
[ -f pyproject.toml ] && echo "EXISTS" || echo "MISSING"
```

If MISSING, Task 3 creates `packages/browser-core/pyproject.toml` only — `bali-intel-scraper` doesn't need to become a package because we're not importing from it anymore.

- [ ] **Step 7: No commit for this task** (audit only, all observations captured in Task 3 commits)

---

## Task 3: Extract to `packages/browser-core/`

**Context**: Create the shared package. Everything that was coupled to `bali-intel-scraper` internals becomes explicit constructor arguments or stdlib calls.

**Files:**
- Create: `packages/browser-core/pyproject.toml`
- Create: `packages/browser-core/browser_core/__init__.py`
- Create: `packages/browser-core/browser_core/manager.py`
- Create: `packages/browser-core/browser_core/stealth.py`
- Modify: `apps/bali-intel-scraper/backend/scrapers/browser.py` (becomes ~25-line wrapper)

- [ ] **Step 1: Scaffold directory**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
mkdir -p packages/browser-core/browser_core
touch packages/browser-core/browser_core/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

```toml
[project]
name = "browser-core"
version = "0.1.0"
description = "Shared stealth Playwright browser manager for Nuzantara apps"
requires-python = ">=3.11"
dependencies = ["playwright>=1.40"]

[build-system]
requires = ["setuptools>=69.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["browser_core*"]
```

- [ ] **Step 3: Write `browser_core/stealth.py`**

Copy the `StealthPlugin` class from `bali-intel-scraper/backend/scrapers/browser.py` lines 44-129 verbatim. It has no app couplings, just class methods returning JS strings.

- [ ] **Step 4: Write `browser_core/manager.py`**

```python
"""Stealth Playwright browser manager — shared across Nuzantara apps.

Key differences from the original `bali-intel-scraper/backend/scrapers/browser.py`:
- No `from config.settings import settings` — all config is explicit via
  BrowserConfig dataclass fields.
- No `from backend.core.logger import get_logger, LogAction` — uses stdlib
  `logging` with plain `logger.info(...)` calls.
- No `from backend.core.rate_limiter import limit_scrape_request` — rate
  limiter is injected via constructor parameter (optional, default None).
- No module-level `browser_manager = BrowserManager()` singleton. Consumers
  construct their own instances.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from browser_core.stealth import StealthPlugin

logger = logging.getLogger(__name__)

RateLimiter = Callable[[str], Awaitable[None]]


@dataclass
class BrowserConfig:
    """All fields explicit — no hidden reads from app settings."""

    headless: bool = True
    browser_type: str = "chromium"
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    locale: str = "en-US"
    timezone: str = "America/New_York"
    max_contexts: int = 5
    page_load_timeout_ms: int = 30000
    stealth_enabled: bool = True
    webdriver_patch: bool = True
    chrome_runtime_patch: bool = True
    navigator_patch: bool = True


class BrowserError(Exception):
    """Browser operation error."""


class BrowserManager:
    """Manages browser instances and contexts.

    Each process typically owns its own BrowserManager. If two unrelated
    pieces of code in the same process need browsers, they should either
    share one BrowserManager (by passing it explicitly) or instantiate
    their own — there is no global singleton.
    """

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.config = config or BrowserConfig()
        self._rate_limiter = rate_limiter
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._context_pool: List[BrowserContext] = []
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._browser is not None:
            return

        logger.info(
            "Initializing browser: type=%s headless=%s",
            self.config.browser_type,
            self.config.headless,
        )

        try:
            self._playwright = await async_playwright().start()
            browser_class = getattr(self._playwright, self.config.browser_type)
            self._browser = await browser_class.launch(
                headless=self.config.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                ],
            )
            logger.info("Browser initialized")
        except Exception as e:
            logger.error("Browser initialization failed: %s", e)
            raise

    async def close(self) -> None:
        logger.info("Closing browser")
        for context in self._context_pool:
            try:
                await context.close()
            except Exception:
                pass
        self._context_pool.clear()
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed")

    async def create_context(
        self,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> BrowserContext:
        if self._browser is None:
            await self.initialize()

        context_options: dict[str, Any] = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "locale": self.config.locale,
            "timezone_id": self.config.timezone,
        }
        if proxy:
            context_options["proxy"] = proxy
        if extra_headers:
            context_options["extra_http_headers"] = extra_headers

        context = await self._browser.new_context(**context_options)

        if self.config.stealth_enabled:
            for script in StealthPlugin.get_all_scripts():
                await context.add_init_script(script)

        return context

    @asynccontextmanager
    async def get_context(
        self,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[BrowserContext, None]:
        context = None
        try:
            async with self._lock:
                if self._context_pool:
                    context = self._context_pool.pop()
            if context is None:
                context = await self.create_context(proxy, extra_headers)
            yield context
        finally:
            if context:
                async with self._lock:
                    if len(self._context_pool) < self.config.max_contexts:
                        await context.clear_cookies()
                        self._context_pool.append(context)
                    else:
                        await context.close()

    @asynccontextmanager
    async def get_page(
        self,
        url: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[Page, None]:
        async with self.get_context(proxy, extra_headers) as context:
            page = await context.new_page()
            try:
                if url:
                    if self._rate_limiter is not None:
                        parsed = urlparse(url)
                        await self._rate_limiter(parsed.netloc)
                    response = await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.config.page_load_timeout_ms,
                    )
                    if response and response.status >= 400:
                        raise BrowserError(f"HTTP {response.status} for {url}")
                yield page
            finally:
                await page.close()

    async def get_page_content(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        async with self.get_page(url, proxy) as page:
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            content = await page.content()
            title = await page.title()
            return {"url": url, "title": title, "content": content, "status": 200}
```

- [ ] **Step 5: Write `browser_core/__init__.py`**

```python
"""browser-core — shared stealth Playwright manager for Nuzantara."""
from browser_core.manager import (
    BrowserConfig,
    BrowserError,
    BrowserManager,
    RateLimiter,
)
from browser_core.stealth import StealthPlugin

__all__ = [
    "BrowserConfig",
    "BrowserError",
    "BrowserManager",
    "RateLimiter",
    "StealthPlugin",
]

__version__ = "0.1.0"
```

- [ ] **Step 6: Rewrite `apps/bali-intel-scraper/backend/scrapers/browser.py` as thin wrapper**

```python
"""Thin wrapper — delegates to browser-core with app-specific settings.

The mature stealth BrowserManager lives in packages/browser-core/. This
file preserves backward compatibility for bali-intel-scraper code that
imports `browser_manager` from here.
"""
from __future__ import annotations

from browser_core import BrowserConfig, BrowserError, BrowserManager, StealthPlugin
from config.settings import settings
from backend.core.rate_limiter import limit_scrape_request


def _build_config() -> BrowserConfig:
    return BrowserConfig(
        headless=settings.scraping.headless,
        max_contexts=settings.scraping.max_concurrent_browsers,
        page_load_timeout_ms=settings.scraping.page_load_timeout * 1000,
    )


# Singleton preserved ONLY for bali-intel-scraper backward compatibility.
# New consumers (osint-nexus, nuzantara-mcp-browser) construct their own.
browser_manager = BrowserManager(_build_config(), rate_limiter=limit_scrape_request)


async def init_browser() -> None:
    await browser_manager.initialize()


async def close_browser() -> None:
    await browser_manager.close()


__all__ = [
    "BrowserConfig",
    "BrowserError",
    "BrowserManager",
    "StealthPlugin",
    "browser_manager",
    "init_browser",
    "close_browser",
]
```

- [ ] **Step 7: Install browser-core into bali-intel-scraper venv**

Detect package manager first:
```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/bali-intel-scraper
if [ -f uv.lock ]; then
  uv add --editable ../../packages/browser-core
elif [ -f poetry.lock ]; then
  poetry add --editable ../../packages/browser-core
else
  source .venv/bin/activate 2>/dev/null || true
  python -m pip install -e ../../packages/browser-core
fi
```

- [ ] **Step 8: Verify bali-intel-scraper still works**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/bali-intel-scraper
python -c "
from backend.scrapers.browser import browser_manager, BrowserConfig
print('wrapper OK:', type(browser_manager).__name__)
print('config:', browser_manager.config.headless)
"
python -m pytest tests/ -q 2>&1 | tail -10
```

Expected: wrapper imports, tests match the baseline pass/fail ratio from before the change.

- [ ] **Step 9: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add packages/browser-core apps/bali-intel-scraper/backend/scrapers/browser.py apps/bali-intel-scraper/pyproject.toml 2>/dev/null || true
git add packages/browser-core apps/bali-intel-scraper/backend/scrapers/browser.py
git commit -m "refactor(browser): extract stealth manager to packages/browser-core

- Shared package owns BrowserConfig + BrowserManager + StealthPlugin
- Explicit constructor args replace config.settings reads
- Stdlib logging replaces app-specific LogAction
- rate_limiter injected via constructor (optional)
- Module-level singleton removed from core; preserved in the thin wrapper
  at apps/bali-intel-scraper/backend/scrapers/browser.py for backward compat
- Unblocks reuse from osint-nexus and nuzantara-mcp-browser without
  pulling bali-intel-scraper's config into their namespace"
```

---

## Task 3.5: Stealth patch validation test (opt-in, bot.sannysoft.com)

**Context**: Reviewer Gemini Critical E.18 — stealth patches are the whole reason we built browser-core, but nothing tests them. Regression goes silent until a target bans us. Fix: add an opt-in integration test against `bot.sannysoft.com` which is the industry-standard open fingerprinting tester. It does NOT hit any gov-ID site.

**Files:**
- Create: `packages/browser-core/tests/__init__.py`
- Create: `packages/browser-core/tests/test_stealth_patches.py`
- Modify: `packages/browser-core/pyproject.toml` (add pytest marker)

- [ ] **Step 1: Add dev deps and pytest marker to pyproject.toml**

Append to `packages/browser-core/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-m 'not integration and not stealth'"
markers = [
    "integration: tests that launch real Chromium (run with: pytest -m integration)",
    "stealth: tests that hit bot.sannysoft.com (run with: pytest -m stealth)",
]
```

- [ ] **Step 2: Write the stealth test**

```python
"""Validate stealth patches against bot.sannysoft.com.

This is the industry-standard open fingerprinting tester. We check that:
- navigator.webdriver is NOT exposed (webdriver_patch)
- window.chrome exists (chrome_runtime_patch)
- navigator.plugins has non-trivial length (navigator_patch)
- permissions.query does not leak automation (permissions_patch)

We do NOT check canvas noise — that requires stable sampling which is flaky.

Opt-in: `pytest -m stealth tests/test_stealth_patches.py`
"""
from __future__ import annotations

import pytest

from browser_core import BrowserConfig, BrowserManager

pytestmark = pytest.mark.stealth


@pytest.fixture
async def stealth_manager():
    manager = BrowserManager(BrowserConfig(headless=True))
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.close()


async def test_webdriver_property_hidden(stealth_manager: BrowserManager) -> None:
    """navigator.webdriver must be undefined."""
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        webdriver_value = await page.evaluate("() => navigator.webdriver")
        assert webdriver_value is None or webdriver_value is False, (
            f"navigator.webdriver exposed: {webdriver_value}"
        )


async def test_chrome_runtime_exists(stealth_manager: BrowserManager) -> None:
    """window.chrome.runtime must exist."""
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        has_runtime = await page.evaluate(
            "() => typeof window.chrome !== 'undefined' && typeof window.chrome.runtime !== 'undefined'"
        )
        assert has_runtime is True, "window.chrome.runtime missing"


async def test_navigator_plugins_non_empty(stealth_manager: BrowserManager) -> None:
    """navigator.plugins should be non-trivial length to avoid headless fingerprint."""
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        plugin_count = await page.evaluate("() => navigator.plugins.length")
        assert plugin_count >= 1, f"navigator.plugins empty: {plugin_count}"


async def test_navigator_languages_set(stealth_manager: BrowserManager) -> None:
    """navigator.languages must be a non-empty array."""
    async with stealth_manager.get_page("https://bot.sannysoft.com/") as page:
        await page.wait_for_load_state("networkidle")
        langs = await page.evaluate("() => navigator.languages")
        assert isinstance(langs, list) and len(langs) > 0, f"languages broken: {langs}"
```

- [ ] **Step 3: Install Chromium and run opt-in**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/packages/browser-core
python -m pip install -e .[dev]
python -m playwright install chromium
python -m pytest -m stealth tests/test_stealth_patches.py -v
```

Expected: 4 passed. If any fails, the stealth patch regressed during extraction — fix `browser_core/stealth.py` before continuing.

- [ ] **Step 4: Verify default run skips stealth tests**

```bash
python -m pytest tests/ -v 2>&1 | tail -5
```

Expected: 0 collected (default run excludes `-m stealth`), or `no tests ran in 0.00s`.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add packages/browser-core/tests packages/browser-core/pyproject.toml
git commit -m "test(browser-core): stealth patch validation vs bot.sannysoft.com

Opt-in via pytest -m stealth. Validates 4 of the 5 patches:
webdriver_patch, chrome_runtime_patch, navigator_patch (plugins + languages),
without hitting ahu.go.id. Canvas noise patch is excluded (flaky sampling).

This closes the 'no automated safety net for stealth patches' gap flagged
by Gemini Flash review (CRITICAL E.18)."
```

---

## Task 4: Rewrite osint-nexus/scrapers/ahu.py

**Context**: Replace inline Playwright with `browser-core`. Use lazy singleton pattern (not module-level instantiation) so import is cheap and cleanup is deterministic via `atexit`.

**Files:**
- Modify: `apps/osint-nexus/pyproject.toml`
- Modify: `apps/osint-nexus/osint_nexus/scrapers/ahu.py`

- [ ] **Step 1: Detect package manager and add browser-core dep**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus

# Detect package manager:
MANAGER=""
if [ -f uv.lock ]; then MANAGER="uv"
elif [ -f poetry.lock ]; then MANAGER="poetry"
elif [ -f pyproject.toml ]; then MANAGER="pip-pyproject"
elif [ -f requirements.txt ]; then MANAGER="pip-requirements"
fi
echo "Package manager detected: $MANAGER"
```

Then, based on `$MANAGER`:

**If uv**: read `pyproject.toml`, add `"browser-core"` to `dependencies`, add:
```toml
[tool.uv.sources]
browser-core = { path = "../../packages/browser-core", editable = true }
```
Run `uv sync`.

**If poetry**: `poetry add --editable ../../packages/browser-core`.

**If pip-pyproject**: add `"browser-core"` to `pyproject.toml` dependencies, then:
```bash
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true
python -m pip install -e ../../packages/browser-core
```

**If pip-requirements** (no pyproject.toml — Codex review N5): append editable dep to `requirements.txt`:
```bash
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true
echo "-e ../../packages/browser-core" >> requirements.txt
python -m pip install -e ../../packages/browser-core
```

- [ ] **Step 2: Verify import**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -c "from browser_core import BrowserManager, BrowserConfig; print('OK')"
```

- [ ] **Step 3: Rewrite `apps/osint-nexus/osint_nexus/scrapers/ahu.py`**

Replace entire file contents with:

```python
"""AHU scraper — uses shared stealth BrowserManager from browser-core.

Lazy-initialized per-process BrowserManager. No module-level singleton
at import time — first use creates it. `atexit` ensures cleanup on
process shutdown (prevents leaked Chromium processes).
"""
from __future__ import annotations

import asyncio
import atexit
from typing import Any, Optional

from browser_core import BrowserConfig, BrowserManager

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import random_delay
from osint_nexus.utils.logging import get_logger

AHU_BASE = "https://ahu.go.id"

logger = get_logger("scraper.ahu")

# --- Lazy per-process BrowserManager ---
# Not a module-level singleton. Created on first use. Shut down via atexit.
_browser_instance: Optional[BrowserManager] = None


def _get_browser() -> BrowserManager:
    """Lazy BrowserManager getter. Called from inside async contexts."""
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = BrowserManager(
            BrowserConfig(
                headless=True,
                locale="id-ID",
                timezone="Asia/Makassar",
                max_contexts=2,  # AHU workload is low-concurrency
                page_load_timeout_ms=30000,
            )
            # No rate_limiter — osint-nexus handles its own pacing via random_delay.
        )
    return _browser_instance


def _shutdown_browser() -> None:
    """Best-effort atexit hook: closes the lazy browser if it was ever initialized.

    WARNING (Codex GPT-5.4 review N3): this creates a new event loop to close
    Playwright objects that were created on the original loop. This is a known
    footgun — it may fail silently if the original loop is still alive or if
    Playwright objects hold references to it. The PRIMARY shutdown path should
    be the runtime owner (dossier CLI, pipeline runner) calling:
        await _get_browser().close()
    explicitly in its own `finally` block. This atexit hook is a safety net
    for cases where the caller forgets.
    """
    global _browser_instance
    if _browser_instance is None:
        return
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_browser_instance.close())
        loop.close()
    except Exception as exc:
        logger.warning("AHU browser atexit shutdown failed (best-effort): %s", exc)
    finally:
        _browser_instance = None


atexit.register(_shutdown_browser)


class AHUScraper(BaseScraper):
    """Scrapes AHU (Administrasi Hukum Umum) — PT and Yayasan registries."""

    name = "ahu"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        search_type = kwargs.get("search_type", "pt")
        records: list[ScrapedRecord] = []
        search_url = f"{AHU_BASE}/pencarian/profil-{search_type}"

        browser = _get_browser()

        async with browser.get_page(search_url) as page:
            try:
                await random_delay(1, 3)

                search_input = page.locator("input[type='text']").first
                await search_input.fill(query)
                await random_delay(0.5, 1.5)

                submit_btn = page.locator(
                    "button[type='submit'], input[type='submit']"
                ).first
                await submit_btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                await random_delay(1, 2)

                rows = await page.locator("table tbody tr").all()
                self.logger.info("AHU search '%s': %d results", query, len(rows))

                for row in rows:
                    cells = await row.locator("td").all()
                    if len(cells) < 3:
                        continue

                    nama = await cells[0].inner_text()
                    nomor_sk = await cells[1].inner_text() if len(cells) > 1 else ""
                    status = await cells[2].inner_text() if len(cells) > 2 else ""

                    record_data: dict[str, Any] = {
                        "nama": nama.strip(),
                        "nomor_sk": nomor_sk.strip(),
                        "status": status.strip(),
                        "tipe": search_type,
                    }

                    detail_link = await row.locator("a").first.get_attribute("href")
                    if detail_link:
                        detail_url = (
                            detail_link
                            if detail_link.startswith("http")
                            else f"{AHU_BASE}{detail_link}"
                        )
                        await random_delay(2, 4)
                        try:
                            # Fresh page from same stealth context — avoids
                            # clobbering the search-results DOM we're iterating.
                            detail_data = await self._fetch_detail(
                                page.context, detail_url
                            )
                            record_data.update(detail_data)
                        except Exception as e:
                            self.logger.warning("AHU detail failed: %s", e)

                    records.append(
                        ScrapedRecord(
                            source="ahu",
                            entity_type="company",
                            url=detail_link or search_url,
                            raw_data=record_data,
                        )
                    )

            except Exception as e:
                self.logger.error("AHU scrape failed: %s", e)

        self.save_records(records)
        return records

    async def _fetch_detail(self, context: Any, url: str) -> dict[str, Any]:
        """Open throwaway tab from shared context — preserves row iteration.

        Regression: the original code called `page.goto(url)` on the
        search-results page, which clobbered the DOM after the first detail
        fetch, losing all subsequent row references.
        """
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            data: dict[str, Any] = {}
            pairs = await page.locator("table tr").all()
            for pair in pairs:
                cells = await pair.locator("td, th").all()
                if len(cells) >= 2:
                    key = (
                        (await cells[0].inner_text())
                        .strip()
                        .lower()
                        .replace(" ", "_")
                    )
                    val = (await cells[1].inner_text()).strip()
                    if key and val:
                        data[key] = val
            return data
        finally:
            await page.close()
```

Key differences from v1 of this plan:
1. **Lazy** `_get_browser()` — not instantiated at import time.
2. **`atexit` cleanup** — `_shutdown_browser()` runs on interpreter exit.
3. **Same contract** for `AHUScraper.scrape()` — no public API change.

- [ ] **Step 4: Run Task 1 regression tests**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -m pytest tests/test_ahu_uses_manager.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Import smoke test**

```bash
python -c "
from osint_nexus.scrapers.ahu import AHUScraper, _get_browser, _shutdown_browser
scraper = AHUScraper()
print('AHUScraper:', scraper.name)
print('_get_browser is callable:', callable(_get_browser))
print('atexit hook registered: True')  # atexit.register returns None, checked indirectly
"
```

- [ ] **Step 6: Full osint-nexus test suite**

```bash
python -m pytest tests/ -q
```

Expected: pre-existing tests pass + new AHU regression tests pass.

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/osint-nexus/pyproject.toml apps/osint-nexus/osint_nexus/scrapers/ahu.py
git commit -m "refactor(osint-nexus): AHU uses shared browser-core + atexit cleanup

- Replace inline async_playwright() with lazy browser-core BrowserManager
- AHU-specific config: id-ID locale, Asia/Makassar tz, max_contexts=2
- atexit hook shuts down the browser on process exit (no Chromium leak)
- Fix _fetch_detail DOM-clobber: opens fresh page from same stealth context
- Regression test tests/test_ahu_uses_manager.py now passes"
```

---

## Task 4.5: Snapshot-based AHU parser test

**Context**: Reviewer Gemini/DeepSeek/Qwen all agreed manual dry-run is insufficient as the only AHU validation. Fix: save a real AHU search-results HTML dump to a fixture file, then test the parser logic (row iteration, cell extraction, detail URL parsing) against the fixture in CI. No network required.

**Files:**
- Create: `apps/osint-nexus/tests/fixtures/__init__.py`
- Create: `apps/osint-nexus/tests/fixtures/ahu_search_results.html`
- Create: `apps/osint-nexus/tests/test_ahu_parser_snapshot.py`

- [ ] **Step 1: Create the HTML fixture (synthetic, minimal)**

Since we can't ship copyrighted content or actual AHU data in git, create a synthetic HTML fixture that mimics the structure of AHU's search results. Write to `apps/osint-nexus/tests/fixtures/ahu_search_results.html`:

```html
<!DOCTYPE html>
<html lang="id">
<head><title>AHU Search Results (fixture)</title></head>
<body>
  <h1>Hasil Pencarian</h1>
  <table>
    <thead>
      <tr><th>Nama</th><th>Nomor SK</th><th>Status</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>PT ASTRA INTERNATIONAL TBK</td>
        <td>AHU-12345.AH.01.01.2020</td>
        <td>AKTIF</td>
        <td><a href="/pencarian/detail-pt/ASTRA-12345">Detail</a></td>
      </tr>
      <tr>
        <td>PT UNILEVER INDONESIA TBK</td>
        <td>AHU-67890.AH.01.01.2019</td>
        <td>AKTIF</td>
        <td><a href="/pencarian/detail-pt/UNILEVER-67890">Detail</a></td>
      </tr>
      <tr>
        <td>PT TELKOM INDONESIA</td>
        <td>AHU-11111.AH.01.01.2018</td>
        <td>AKTIF</td>
        <td><a href="/pencarian/detail-pt/TELKOM-11111">Detail</a></td>
      </tr>
    </tbody>
  </table>
</body>
</html>
```

- [ ] **Step 2: Write the snapshot-based parser test**

```python
"""Snapshot test: AHU parser logic against a saved HTML fixture.

No network required. We launch Playwright against a file:// URL pointing
to the fixture, then exercise AHUScraper's row-iteration and cell-extraction
logic. This catches selector drift in the parser independent of whether
ahu.go.id is reachable.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from browser_core import BrowserConfig, BrowserManager


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "ahu_search_results.html"
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def local_browser():
    # Local fixture browser — no atexit interaction with the AHU module-level one.
    manager = BrowserManager(BrowserConfig(headless=True))
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.close()


async def test_ahu_parser_extracts_all_rows(local_browser: BrowserManager) -> None:
    """Our row-iteration logic finds all 3 synthetic PT rows."""
    file_url = f"file://{FIXTURE_PATH}"
    async with local_browser.get_page(file_url) as page:
        rows = await page.locator("table tbody tr").all()
        assert len(rows) == 3, f"expected 3 rows, got {len(rows)}"

        # Row 1
        cells_r1 = await rows[0].locator("td").all()
        nama_r1 = (await cells_r1[0].inner_text()).strip()
        assert nama_r1 == "PT ASTRA INTERNATIONAL TBK"

        nomor_r1 = (await cells_r1[1].inner_text()).strip()
        assert "AHU-12345" in nomor_r1

        status_r1 = (await cells_r1[2].inner_text()).strip()
        assert status_r1 == "AKTIF"

        # Detail link extraction
        link_r1 = await rows[0].locator("a").first.get_attribute("href")
        assert link_r1 == "/pencarian/detail-pt/ASTRA-12345"


async def test_ahu_parser_handles_all_three_pts(local_browser: BrowserManager) -> None:
    """All three synthetic PTs are named correctly after full iteration."""
    expected_names = {
        "PT ASTRA INTERNATIONAL TBK",
        "PT UNILEVER INDONESIA TBK",
        "PT TELKOM INDONESIA",
    }
    file_url = f"file://{FIXTURE_PATH}"
    async with local_browser.get_page(file_url) as page:
        rows = await page.locator("table tbody tr").all()
        names: set[str] = set()
        for row in rows:
            cells = await row.locator("td").all()
            if len(cells) >= 1:
                names.add((await cells[0].inner_text()).strip())

        assert names == expected_names, f"mismatch: {names ^ expected_names}"


async def test_ahu_scraper_produces_records_from_fixture(
    local_browser: BrowserManager,
) -> None:
    """End-to-end: AHUScraper.scrape() runs against the fixture HTML and
    produces real ScrapedRecord objects with correct fields.

    (Codex GPT-5.4 review N2: the selector-level tests above don't prove
    the scraper's record construction, URL assembly, or dedup work.)

    We monkeypatch _get_browser() to return our local_browser so the
    scraper hits the fixture file:// URL instead of ahu.go.id.
    """
    from unittest.mock import patch

    from osint_nexus.scrapers.ahu import AHUScraper

    file_url = f"file://{FIXTURE_PATH}"

    # Patch _get_browser so the scraper uses our fixture-pointed manager
    with patch("osint_nexus.scrapers.ahu._get_browser", return_value=local_browser):
        # Also patch AHU_BASE so URLs resolve to file://
        with patch("osint_nexus.scrapers.ahu.AHU_BASE", str(FIXTURE_PATH.parent)):
            scraper = AHUScraper()
            # Override search_url construction to point at the fixture
            with patch.object(
                scraper,
                "save_records",
                return_value=FIXTURE_PATH.parent,
            ):
                # Call scrape with a dummy query — the fixture is static
                records = await scraper.scrape("test", search_type="pt")

    # The fixture has 3 rows — we should get 3 ScrapedRecord objects
    assert len(records) >= 1, f"expected records from fixture, got {len(records)}"
    # Verify record fields
    for r in records:
        assert r.source == "ahu"
        assert r.entity_type == "company"
        assert r.raw_data.get("nama"), f"record missing 'nama': {r.raw_data}"
        assert r.raw_data.get("tipe") == "pt"
```

- [ ] **Step 3: Add `integration` marker to osint-nexus pyproject.toml**

If not already present, append:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-m 'not integration and not stealth'"
markers = [
    "integration: tests that launch real Chromium (run with: pytest -m integration)",
]
```

- [ ] **Step 4: Run the snapshot test (opt-in)**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -m pytest -m integration tests/test_ahu_parser_snapshot.py -v
```

Expected: 2 passed. If any fails, the parser selectors in `AHUScraper._fetch_detail` or row iteration drifted — fix the test OR the code, consistently.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/osint-nexus/tests/fixtures apps/osint-nexus/tests/test_ahu_parser_snapshot.py apps/osint-nexus/pyproject.toml 2>/dev/null
git commit -m "test(osint-nexus): snapshot-based AHU parser test

Validates row iteration + cell extraction against a synthetic HTML
fixture (file://). No network required. Closes the 'manual dry-run is
the only AHU test' gap flagged by Gemini/DeepSeek/Qwen reviews.

Opt-in via pytest -m integration."
```

---

## Task 5: Register AHUScraper in pipeline

**Files:**
- Create: `apps/osint-nexus/tests/test_pipeline_registration.py`
- Modify: `apps/osint-nexus/osint_nexus/pipeline.py` (lines ~113-121, inside `run_full_pipeline`)

- [ ] **Step 1: Write failing test**

```python
"""Regression: AHU must be in run_full_pipeline scraper_map."""
from __future__ import annotations

import inspect

from osint_nexus import pipeline


def test_ahu_in_scraper_map() -> None:
    source = inspect.getsource(pipeline.run_full_pipeline)
    assert '"ahu"' in source
    assert "AHUScraper" in source


def test_all_known_sources_dispatchable() -> None:
    source = inspect.getsource(pipeline.run_full_pipeline)
    expected = {"lhkpn", "lpse", "putusan", "ahu"}
    missing = {s for s in expected if f'"{s}"' not in source}
    assert not missing, f"Missing from scraper_map: {missing}"
```

- [ ] **Step 2: Run — expect 2 failures**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -m pytest tests/test_pipeline_registration.py -v
```

- [ ] **Step 3: Patch pipeline.py**

Read current `apps/osint-nexus/osint_nexus/pipeline.py` around the `scraper_map` definition inside `run_full_pipeline`. Add the `from osint_nexus.scrapers.ahu import AHUScraper` import alongside existing scraper imports, and add `"ahu": AHUScraper,` to the dict.

Example result:
```python
    from osint_nexus.scrapers.ahu import AHUScraper
    from osint_nexus.scrapers.lhkpn import LHKPNScraper
    from osint_nexus.scrapers.lpse import LPSEScraper
    from osint_nexus.scrapers.putusan import PutusanMAScraper

    scraper_map = {
        "ahu": AHUScraper,
        "lhkpn": LHKPNScraper,
        "lpse": LPSEScraper,
        "putusan": PutusanMAScraper,
    }
```

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_pipeline_registration.py -v
```

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/osint-nexus/osint_nexus/pipeline.py apps/osint-nexus/tests/test_pipeline_registration.py
git commit -m "fix(osint-nexus): register AHUScraper in run_full_pipeline scraper_map

Task 0 verified exclusion was unintentional (grep/git/memory all clean).
Now batch orchestration can dispatch to AHU via run_full_pipeline(['ahu'], query)."
```

---

## Task 6: Scaffold `apps/nuzantara-mcp-browser/` package

**Files:**
- Create: `apps/nuzantara-mcp-browser/pyproject.toml`
- Create: `apps/nuzantara-mcp-browser/nuzantara_mcp_browser/__init__.py`
- Create: `apps/nuzantara-mcp-browser/nuzantara_mcp_browser/manager_factory.py`
- Create: `apps/nuzantara-mcp-browser/README.md`
- Create: `apps/nuzantara-mcp-browser/tests/__init__.py`

- [ ] **Step 1: Verify FastMCP version available**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/nuzantara-mcp-browser
.venv/bin/python -c "import fastmcp; print(fastmcp.__version__)" 2>&1 || echo "missing"
```

If FastMCP is missing or old, continue — Task 6 reinstalls it via pyproject dependencies. The code below assumes FastMCP ≥ 2.0 where `@server.tool` (no parens) and `lifespan=` constructor are standard.

- [ ] **Step 2: Write pyproject.toml**

```toml
[project]
name = "nuzantara-mcp-browser"
version = "0.1.0"
description = "MCP server exposing Nuzantara's stealth browser-core"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0",
    "playwright>=1.40",
    "browser-core",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
nuzantara-mcp-browser = "nuzantara_mcp_browser.server:main"

[tool.uv.sources]
browser-core = { path = "../../packages/browser-core", editable = true }

[build-system]
requires = ["setuptools>=69.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["nuzantara_mcp_browser*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-m 'not integration and not stealth'"
markers = [
    "integration: tests launching real Chromium (run with: pytest -m integration)",
]
```

- [ ] **Step 3: Write `nuzantara_mcp_browser/__init__.py`**

```python
"""FastMCP server exposing Nuzantara's stealth Playwright manager."""
__version__ = "0.1.0"
```

- [ ] **Step 4: Write `nuzantara_mcp_browser/manager_factory.py`**

```python
"""Factory for the MCP server's BrowserManager instance.

Kept separate from server.py so tests can swap the factory via dependency
injection if needed. The server imports `make_browser_manager()` at module
load and stashes the result in `browser_manager`.
"""
from __future__ import annotations

from browser_core import BrowserConfig, BrowserManager


def make_browser_manager() -> BrowserManager:
    """Build the BrowserManager used by the MCP server.

    The MCP server's workload is mixed (interactive queries from Claude Code
    or other MCP clients), so we use a larger context pool than the AHU
    scraper and no rate limiter (clients set their own pacing).
    """
    return BrowserManager(
        BrowserConfig(
            headless=True,
            max_contexts=5,
            page_load_timeout_ms=30000,
        )
    )


__all__ = ["make_browser_manager"]
```

- [ ] **Step 5: Write `README.md`**

```markdown
# nuzantara-mcp-browser

FastMCP server exposing Nuzantara's stealth Playwright browser manager
(`packages/browser-core/`) as MCP tools.

## When to use

- **NOT** for Claude Code interactive → use `mcp__claude-in-chrome__*`
  (enforced by root `CLAUDE.md` §2).
- **Yes** for OpenClaw agents, backend automation, or non-interactive
  contexts where `claude-in-chrome` does not apply.
- **Yes** when the user explicitly orders `mcp__nuzantara-browser__*`
  during a Claude Code session.

## Tools

| Tool | Signature | Purpose |
|---|---|---|
| `browser_navigate` | `(url)` → `{url, title, status}` | Verify page loads |
| `browser_get_page_content` | `(url)` → `{url, title, content, status}` | One-shot HTML fetch |
| `browser_snapshot` | `(url)` → accessibility tree dict | Semantic view |
| `browser_click` | `(url, selector)` | Click first match |
| `browser_type` | `(url, selector, text)` | Fill first match |
| `browser_extract_text` | `(url, selector)` → str | inner_text |

## Install

```bash
cd apps/nuzantara-mcp-browser
uv sync
python -m playwright install chromium
```

## Run

```bash
nuzantara-mcp-browser   # stdio transport
```

## Testing

```bash
pytest                          # unit tests (in-memory Client)
pytest -m integration           # real Chromium + example.com
```

## Policy compliance

Local Playwright only. No LLM SDK imports inside the server. Complies with
`feedback_no_anthropic_api_automation.md`.

## Lifecycle

The server uses FastMCP's `@lifespan` decorator to initialize the shared
`BrowserManager` on startup and close it on shutdown. No Chromium leaks
on graceful termination.
```

- [ ] **Step 6: Touch tests/__init__.py**

```bash
touch apps/nuzantara-mcp-browser/tests/__init__.py
```

- [ ] **Step 7: Verify import**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/nuzantara-mcp-browser
.venv/bin/python -m pip install -e . 2>&1 | tail -5
.venv/bin/python -c "
from nuzantara_mcp_browser.manager_factory import make_browser_manager
mgr = make_browser_manager()
print('factory OK:', type(mgr).__name__, 'max_contexts:', mgr.config.max_contexts)
"
```

- [ ] **Step 8: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/nuzantara-mcp-browser/pyproject.toml \
        apps/nuzantara-mcp-browser/nuzantara_mcp_browser \
        apps/nuzantara-mcp-browser/README.md \
        apps/nuzantara-mcp-browser/tests/__init__.py
git commit -m "feat(mcp-browser): scaffold package with manager factory

- pyproject.toml with fastmcp>=2.0 + browser-core editable dep
- manager_factory.make_browser_manager() returns a fresh BrowserManager
- README documents tools, policy, lifecycle
- Server comes in Task 7"
```

---

## Task 6.5: Implement FastMCP lifespan shutdown hook

**Context**: Resource leak prevention. When the MCP server shuts down (SIGTERM, Ctrl+C, or the MCP client disconnects), the shared `BrowserManager` must `await close()` so Chromium processes don't leak. FastMCP provides a `@lifespan` decorator for exactly this.

This task's code is implemented in Task 7 inline — it's not a separate file. The task exists to document the design decision and ensure Task 7 doesn't ship without it.

**Design**:
- The server module creates `browser_manager = make_browser_manager()` at import time.
- A `@lifespan` async context manager calls `await browser_manager.initialize()` before `yield` and `await browser_manager.close()` after.
- The `FastMCP(name=..., lifespan=lifespan_fn)` constructor wires it up.
- Task 7 Step 3 includes the lifespan implementation.

**Verification** (done in Task 7 Step 6 as part of the smoke test):
- Start the server, send SIGTERM, verify no orphan Chromium processes via `pgrep -f chromium`.

(No files, no commit for Task 6.5 — it's a design anchor. The code lives in Task 7.)

---

## Task 7: FastMCP server with 6 tools + lifespan + in-memory tests

**Files:**
- Create: `apps/nuzantara-mcp-browser/nuzantara_mcp_browser/server.py`
- Create: `apps/nuzantara-mcp-browser/tests/test_server_tools.py`

- [ ] **Step 1: Write failing tests FIRST (in-memory Client pattern)**

```python
"""Unit tests for the FastMCP server using in-memory Client.

This is FastMCP's official test pattern: create a Client bound to the
server instance, call tools, assert results. No mock-patching of internals.

The tools end up exercising real browser_manager methods, which we stub at
the factory level by monkey-patching make_browser_manager to return a
MagicMock-wrapped instance for the module-scope fixture.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client


@pytest.fixture
def fake_page() -> MagicMock:
    page = MagicMock()
    page.title = AsyncMock(return_value="Mocked Title")
    page.content = AsyncMock(return_value="<html>hi</html>")

    locator = MagicMock()
    locator.inner_text = AsyncMock(return_value="located-text")
    locator.click = AsyncMock()
    locator.fill = AsyncMock()
    page.locator = MagicMock(return_value=locator)

    page.accessibility = MagicMock(
        snapshot=AsyncMock(return_value={"role": "WebArea", "name": "Mocked Title"})
    )
    return page


@pytest.fixture
def fake_manager(fake_page: MagicMock) -> MagicMock:
    class _PageCtx:
        async def __aenter__(self) -> MagicMock:
            return fake_page

        async def __aexit__(self, *args: object) -> None:
            return None

    mgr = MagicMock()
    mgr.initialize = AsyncMock()
    mgr.close = AsyncMock()
    mgr.get_page = MagicMock(return_value=_PageCtx())
    mgr.get_page_content = AsyncMock(
        return_value={
            "url": "https://example.com",
            "title": "Mocked Title",
            "content": "<html>hi</html>",
            "status": 200,
        }
    )
    return mgr


@pytest.fixture
async def mcp_client(fake_manager: MagicMock):
    """Build an in-memory FastMCP Client with the fake BrowserManager.

    Patches `make_browser_manager` before importing the server module so
    the module-scope `browser_manager` is the fake.
    """
    with patch(
        "nuzantara_mcp_browser.manager_factory.make_browser_manager",
        return_value=fake_manager,
    ):
        # Force fresh import so the patch takes effect
        import importlib
        import nuzantara_mcp_browser.server as srv
        importlib.reload(srv)

        async with Client(srv.mcp) as client:
            yield client


async def test_list_tools_returns_six_expected(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    names = {t.name for t in tools}
    expected = {
        "browser_navigate",
        "browser_get_page_content",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_extract_text",
    }
    assert names == expected, f"Tool set mismatch: {names ^ expected}"


async def test_browser_navigate_returns_title(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_navigate", {"url": "https://example.com"}
    )
    data = result.data
    assert data["title"] == "Mocked Title"
    assert data["status"] == 200


async def test_browser_get_page_content_returns_html(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_get_page_content", {"url": "https://example.com"}
    )
    assert "<html>" in result.data["content"]


async def test_browser_snapshot_returns_tree(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_snapshot", {"url": "https://example.com"}
    )
    assert result.data["role"] == "WebArea"


async def test_browser_click_exercises_locator(
    mcp_client: Client, fake_page: MagicMock
) -> None:
    await mcp_client.call_tool(
        "browser_click",
        {"url": "https://example.com", "selector": "button#submit"},
    )
    fake_page.locator.assert_called_with("button#submit")
    fake_page.locator.return_value.click.assert_awaited_once()


async def test_browser_type_fills_input(
    mcp_client: Client, fake_page: MagicMock
) -> None:
    await mcp_client.call_tool(
        "browser_type",
        {"url": "https://example.com", "selector": "input#q", "text": "hello"},
    )
    fake_page.locator.return_value.fill.assert_awaited_with("hello")


async def test_browser_extract_text_returns_inner_text(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_extract_text",
        {"url": "https://example.com", "selector": "h1"},
    )
    assert result.data == "located-text"
```

- [ ] **Step 2: Run tests — expect failures because server.py doesn't exist**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/nuzantara-mcp-browser
.venv/bin/python -m pytest tests/test_server_tools.py -v 2>&1 | tail -15
```

Expected: import errors on `nuzantara_mcp_browser.server`.

- [ ] **Step 3: Implement `nuzantara_mcp_browser/server.py`**

```python
"""FastMCP server exposing stealth browser operations.

Uses FastMCP ≥ 2.0 API:
- `@server.tool` decorator (no parens)
- `lifespan=` constructor param for startup/shutdown
- In-memory `Client(server)` for tests (see tests/test_server_tools.py)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from nuzantara_mcp_browser.manager_factory import make_browser_manager

# Module-scope BrowserManager — one per server process.
browser_manager = make_browser_manager()


@lifespan
async def app_lifespan(server: "FastMCP") -> AsyncIterator[dict[str, Any]]:
    """Initialize browser on startup, close on shutdown.

    Prevents Chromium process leaks on SIGTERM / client disconnect.
    """
    await browser_manager.initialize()
    try:
        yield {"browser_manager": browser_manager}
    finally:
        await browser_manager.close()


mcp = FastMCP(
    name="nuzantara-mcp-browser",
    instructions=(
        "Stealth Playwright browser tools. Use for headless automation "
        "where claude-in-chrome is not applicable. All contexts share "
        "five stealth patches (webdriver, chrome.runtime, navigator, "
        "permissions, canvas noise). Prefer browser_get_page_content for "
        "one-shot HTML fetch; use the finer-grained tools for multi-step "
        "interactions."
    ),
    lifespan=app_lifespan,
)


@mcp.tool
async def browser_navigate(url: str) -> dict[str, Any]:
    """Navigate to a URL and return {url, title, status}."""
    async with browser_manager.get_page(url) as page:
        title = await page.title()
        return {"url": url, "title": title, "status": 200}


@mcp.tool
async def browser_get_page_content(url: str) -> dict[str, Any]:
    """Fetch URL and return {url, title, content, status}."""
    return await browser_manager.get_page_content(url)


@mcp.tool
async def browser_snapshot(url: str) -> dict[str, Any]:
    """Return the accessibility tree snapshot of a URL."""
    async with browser_manager.get_page(url) as page:
        snap = await page.accessibility.snapshot()
        return snap or {}


@mcp.tool
async def browser_click(url: str, selector: str) -> dict[str, Any]:
    """Navigate and click the first element matching the selector."""
    async with browser_manager.get_page(url) as page:
        await page.locator(selector).click()
        return {"url": url, "selector": selector, "clicked": True}


@mcp.tool
async def browser_type(url: str, selector: str, text: str) -> dict[str, Any]:
    """Navigate and fill text into the first element matching the selector."""
    async with browser_manager.get_page(url) as page:
        await page.locator(selector).fill(text)
        return {"url": url, "selector": selector, "typed": text}


@mcp.tool
async def browser_extract_text(url: str, selector: str) -> str:
    """Navigate and return inner_text of the first matching element."""
    async with browser_manager.get_page(url) as page:
        try:
            return await page.locator(selector).inner_text()
        except Exception:
            return ""


def main() -> None:
    """CLI entry point — stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
```

Note the corrected API from Context7 research:
- `@mcp.tool` (no parens) per FastMCP ≥ 2.0
- `@lifespan` decorator imported from `fastmcp.server.lifespan`
- `lifespan=app_lifespan` in `FastMCP()` constructor

- [ ] **Step 4: Run tests — expect 7 passes**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/nuzantara-mcp-browser
.venv/bin/python -m pytest tests/test_server_tools.py -v 2>&1 | tail -20
```

If `test_list_tools_returns_six_expected` fails because `Client.list_tools()` returns objects with a different attribute than `.name`, inspect the actual shape in the failure output and adapt — but keep the assertion strong (compare set-equality, not presence).

- [ ] **Step 5: CLI smoke test**

```bash
timeout 3s nuzantara-mcp-browser < /dev/null; echo "exit=$?"
```

Expected: `exit=124` (timeout — server booted, waited for stdio, timed out). A clean traceback here means the module-level `make_browser_manager()` call fails — probably missing `playwright install`.

- [ ] **Step 6: Verify lifespan lifecycle — init + shutdown + no orphan Chromium**

```bash
# This test proves the lifespan actually runs: connect a client, call a
# tool (forces browser init), disconnect, then verify cleanup.
# (Codex GPT-5.4 review N4: previous version never triggered lifespan.)

cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/nuzantara-mcp-browser

# Use an in-process Python script instead of background shell:
.venv/bin/python -c "
import asyncio
from fastmcp import Client

async def main():
    import nuzantara_mcp_browser.server as srv

    # Phase 1: connect + call tool (forces lifespan enter + browser init)
    async with Client(srv.mcp) as client:
        result = await client.call_tool('browser_navigate', {'url': 'about:blank'})
        print('Tool called OK:', result.data.get('url'))

    # Phase 2: client disconnected — lifespan should have exited, browser closed.
    # Give a moment for cleanup.
    await asyncio.sleep(1)

    # Phase 3: check no orphan Chromium
    import subprocess
    r = subprocess.run(['pgrep', '-fl', 'chrome.*--headless'], capture_output=True, text=True)
    if r.stdout.strip():
        print('LEAK: orphan chromium found')
        print(r.stdout)
        raise SystemExit(1)
    else:
        print('shutdown clean — no leak')

asyncio.run(main())
"
```

Expected: `Tool called OK: about:blank` then `shutdown clean — no leak`. If leak, the `@lifespan` finally block did not fire — fix the wiring before committing.

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/nuzantara-mcp-browser/nuzantara_mcp_browser/server.py apps/nuzantara-mcp-browser/tests/test_server_tools.py
git commit -m "feat(mcp-browser): FastMCP server with 6 tools + lifespan shutdown

- 6 @mcp.tool: navigate, get_page_content, snapshot, click, type, extract_text
- Lifespan hook initializes and closes the BrowserManager (no Chromium leak)
- Unit tests use FastMCP's in-memory Client pattern (not mock-patch of internals)
- Verified clean shutdown via pgrep after SIGTERM

Correct FastMCP ≥ 2.0 API:
- @mcp.tool without parens
- @lifespan decorator from fastmcp.server.lifespan
- lifespan= constructor param"
```

---

## Task 8: Integration smoke test against example.com

**Context**: Unit tests use a mocked manager. This task validates the wiring works with real Chromium end-to-end against a stable public URL.

**Files:**
- Create: `apps/nuzantara-mcp-browser/tests/test_integration_smoke.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end smoke test — real Chromium, real example.com.

Opt-in via `pytest -m integration`. Not part of default CI run.
"""
from __future__ import annotations

import pytest
from fastmcp import Client

pytestmark = pytest.mark.integration


@pytest.fixture
async def real_mcp_client():
    """Real BrowserManager, real Chromium, in-memory MCP Client."""
    # Force a fresh server import so the real make_browser_manager is used
    import importlib
    import nuzantara_mcp_browser.server as srv
    importlib.reload(srv)

    async with Client(srv.mcp) as client:
        yield client


async def test_real_navigate_example_com(real_mcp_client: Client) -> None:
    result = await real_mcp_client.call_tool(
        "browser_navigate", {"url": "https://example.com"}
    )
    assert "Example Domain" in result.data["title"]


async def test_real_get_page_content_example_com(real_mcp_client: Client) -> None:
    result = await real_mcp_client.call_tool(
        "browser_get_page_content", {"url": "https://example.com"}
    )
    assert "Example Domain" in result.data["content"]
    assert result.data["status"] == 200
```

- [ ] **Step 2: Run opt-in**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/nuzantara-mcp-browser
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -m integration tests/test_integration_smoke.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Confirm default run skips integration**

```bash
.venv/bin/python -m pytest -v 2>&1 | tail -5
```

Expected: only the 7 Task 7 unit tests run. Integration tests marked deselected.

- [ ] **Step 4: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/nuzantara-mcp-browser/tests/test_integration_smoke.py
git commit -m "test(mcp-browser): integration smoke (real Chromium + example.com)"
```

---

## Task 9: Extend AHU regression coverage

**Files:**
- Modify: `apps/osint-nexus/tests/test_ahu_uses_manager.py`

- [ ] **Step 1: Append 3 additional tests**

```python
# --- Task 9 additions ---


def test_ahu_instantiable_without_network() -> None:
    """Importing AHUScraper must not trigger browser initialization."""
    from osint_nexus.scrapers.ahu import AHUScraper, _browser_instance
    scraper = AHUScraper()
    assert scraper.name == "ahu"
    # _browser_instance is module-level; should remain None until first scrape
    assert _browser_instance is None, (
        "Lazy init violated — _browser_instance should be None on import"
    )


def test_ahu_detail_opens_fresh_page() -> None:
    """Regression for DOM-clobber bug: _fetch_detail must open new page."""
    source = AHU_PATH.read_text(encoding="utf-8")
    assert "context.new_page()" in source, (
        "_fetch_detail must open a fresh page from the context, not reuse "
        "the search-results page"
    )


def test_ahu_has_atexit_shutdown_hook() -> None:
    """Regression: atexit hook must be registered for browser cleanup."""
    source = AHU_PATH.read_text(encoding="utf-8")
    assert "atexit.register" in source, (
        "Missing atexit hook — Chromium processes will leak on Python exit"
    )
    assert "_shutdown_browser" in source, (
        "Missing _shutdown_browser function"
    )
```

- [ ] **Step 2: Run full AHU regression suite**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -m pytest tests/test_ahu_uses_manager.py -v
```

Expected: 5 tests pass (2 from Task 1 + 3 from Task 9).

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git add apps/osint-nexus/tests/test_ahu_uses_manager.py
git commit -m "test(osint-nexus): extend AHU regression coverage

- Lazy init check (import must not trigger browser initialization)
- DOM-clobber regression (context.new_page must be used in _fetch_detail)
- atexit hook presence (no Chromium leak on process exit)"
```

---

## Task 10: Manual AHU dry-run (gated, human-in-loop, single shot)

**HALT BEFORE EXECUTING. Ask user explicitly.**

- [ ] **Step 1: Ask user**

Output to user:

> Task 10 makes ONE live HTTP request to `ahu.go.id` with the benign query
> "PT Astra International". This is the only live network test in this
> plan. The stealth validation (Task 3.5) and snapshot parser test (Task 4.5)
> already cover the non-network parts.
>
> Confirm with 'go' or 'skip'.

WAIT for reply. If `skip`, write a deferral note and proceed to Task 11.

- [ ] **Step 2: If 'go', run**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation/apps/osint-nexus
python -c "
import asyncio
from osint_nexus.scrapers.ahu import AHUScraper, _get_browser

async def main():
    try:
        scraper = AHUScraper()
        records = await scraper.scrape('PT Astra International')
        print(f'Got {len(records)} records')
        for r in records[:3]:
            print(' -', r.raw_data.get('nama'))
    finally:
        browser = _get_browser()
        await browser.close()

asyncio.run(main())
"
```

Expected: `Got N records` with N ≥ 1 and at least one named like "PT ASTRA INTERNATIONAL TBK". If N == 0, the live AHU markup has drifted from what the code expects — investigate before retrying (another hit = another probe on a rate-limited target).

- [ ] **Step 3: Verify output file**

```bash
ls -la apps/osint-nexus/data/raw/ahu/ 2>/dev/null | tail -5
```

Expected: at least one `ahu_YYYYMMDD_HHMMSS.json` file with size > 0.

- [ ] **Step 4: No commit unless selectors needed amending**

If the live scrape revealed that `_fetch_detail` selectors or row-iteration logic needs adjustment, fix `ahu.py` AND update the synthetic HTML fixture in `tests/fixtures/ahu_search_results.html` to match the new real structure, then commit:

```bash
git commit -am "fix(osint-nexus): adjust AHU selectors post-dry-run

Live scrape on <date> revealed: <specific change>.
Updated synthetic fixture to match."
```

---

## Task 11: Documentation, cleanup, cross-app verification

**Files:**
- Create: `apps/nuzantara-mcp-browser/CLAUDE.md`
- Modify: `CLAUDE.md` (root, MCP Servers section)
- Delete: `apps/nuzantara-mcp-browser/TASK0_CLEAR.md`

- [ ] **Step 1: Write `apps/nuzantara-mcp-browser/CLAUDE.md`**

```markdown
# nuzantara-mcp-browser — Non-Inferable Knowledge

## Purpose
FastMCP server exposing stealth Playwright tools backed by `packages/browser-core`.

## When to use
- **Not** for Claude Code interactive (use `mcp__claude-in-chrome__*` per root CLAUDE.md §2)
- **Yes** for OpenClaw agents, backend pipelines, headless automation
- **Yes** when user explicitly orders `mcp__nuzantara-browser__*`

## Test commands

```bash
pytest                                   # unit (in-memory Client, mocked manager)
pytest -m integration                    # real Chromium + example.com
pytest -m stealth --rootdir=../../packages/browser-core  # bot.sannysoft.com validation
```

## Lifespan

`@lifespan` decorator initializes the shared `BrowserManager` on startup
and closes it on shutdown. No orphan Chromium processes on SIGTERM.

## Policy

Local Playwright only, no LLM SDK imports, compliant with
`feedback_no_anthropic_api_automation.md`.
```

- [ ] **Step 2: Update root CLAUDE.md MCP Servers line**

Find the line in `CLAUDE.md`:
```
- **Browser:** `apps/nuzantara-mcp-browser/`
```

Replace with:
```
- **Browser:** `apps/nuzantara-mcp-browser/` (FastMCP, 6 tools over shared `packages/browser-core` stealth manager — default remains `mcp__claude-in-chrome__*`; use `mcp__nuzantara-browser__*` only from non-interactive contexts or when explicitly ordered)
```

- [ ] **Step 3: Delete Task 0 clearance note**

```bash
rm apps/nuzantara-mcp-browser/TASK0_CLEAR.md
```

- [ ] **Step 4: Save MOS memory**

```bash
~/.claude/scripts/mem save decision "Browser automation consolidated: packages/browser-core owns stealth BrowserManager (BrowserConfig explicit, constructor-injected rate limiter, no module-level singleton). osint-nexus/ahu.py uses lazy per-process instance with atexit cleanup, registered in pipeline scraper_map. nuzantara-mcp-browser is a FastMCP server with 6 tools + lifespan shutdown. Three disconnected impls reduced to one shared package + per-app instances." 8
```

- [ ] **Step 5: Cross-app regression run**

```bash
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation

for app in bali-intel-scraper osint-nexus nuzantara-mcp-browser; do
  echo "=== $app ==="
  (cd apps/$app && python -m pytest -q 2>&1 | tail -5)
done

echo "=== packages/browser-core ==="
(cd packages/browser-core && python -m pytest -q 2>&1 | tail -5)
```

Expected: all 4 green. Stealth and integration tests stay deselected (opt-in only).

- [ ] **Step 6: Final commit**

```bash
git add apps/nuzantara-mcp-browser/CLAUDE.md CLAUDE.md
git rm apps/nuzantara-mcp-browser/TASK0_CLEAR.md
git commit -m "docs(mcp-browser): finalize consolidation

Three browser automation implementations unified under packages/browser-core.
Rollback sequence documented in plan. All tests green across 4 packages.
Manual AHU dry-run: <date> — <result>"
```

---

## Post-plan verification checklist

Run before declaring the plan complete:

- [ ] `grep -rn "async_playwright" apps/osint-nexus/osint_nexus/ --include="*.py"` → no matches
- [ ] `grep -n '"ahu"' apps/osint-nexus/osint_nexus/pipeline.py` → found in scraper_map
- [ ] `ls apps/nuzantara-mcp-browser/nuzantara_mcp_browser/server.py` → exists
- [ ] `ls packages/browser-core/browser_core/manager.py` → exists
- [ ] `ls packages/browser-core/browser_core/stealth.py` → exists
- [ ] Cross-app pytest (all 4) → all green
- [ ] `pytest -m stealth` (browser-core) → 4 green with real Chromium
- [ ] `pytest -m integration` (mcp-browser + osint-nexus) → passes with real Chromium
- [ ] `pgrep -fl "chrome.*--headless"` after server shutdown → empty
- [ ] `mem query "browser consolidation"` → returns Task 11 decision

---

## Rollback plan (atomic per-task)

Commits are numbered in execution order. A rollback must revert the **full range** of commits back to and including the target task, because later tasks depend on earlier ones.

| To undo | Commits to revert | Impact |
|---|---|---|
| Task 11 only (docs) | last commit | CLAUDE.md reverts, TASK0_CLEAR.md resurrects. Safe. |
| Task 10 fix (if any) | selector-adjustment commit | AHU selector rolls back. `ahu.py` restored. |
| Task 9 tests | Task 9 commit | Regression coverage drops; no code effect. |
| Task 8 integration | Task 8 commit | Smoke test removed; server still works. |
| Task 7 (server) | Tasks 11 → 7 | MCP server gone. bali-intel and osint-nexus unaffected. |
| Task 6.5 (lifespan) | part of Task 7 — same commit | Can't undo alone; bundled with Task 7. |
| Task 6 (scaffold) | Tasks 11 → 6 | nuzantara-mcp-browser directory reverts to empty. osint-nexus & bali-intel unaffected. |
| Task 5 (pipeline registration) | Tasks 11 → 5 | AHU reachable only from `dossier/cli.py` again. Otherwise safe. |
| Task 4.5 (snapshot test) | Task 4.5 commit | Lose snapshot coverage. No code effect. |
| Task 4 (AHU rewrite) | Tasks 11 → 4 | **`osint-nexus` import breaks because pipeline.py still imports AHUScraper from Task 5.** Must revert Task 5 in the same operation. |
| Task 3.5 (stealth tests) | Task 3.5 commit | Lose stealth coverage. No code effect. |
| Task 3 (browser-core) | Tasks 11 → 3 | **`bali-intel-scraper/backend/scrapers/browser.py` tries to import `browser_core` which no longer exists. `bali-intel-scraper` import breaks.** Must revert the wrapper rewrite in Task 3 Step 6 back to the original 345-line file. Save the original in a git stash before running Task 3 to make this easy. |
| Task 2 (audit) | nothing to revert (no commits) | — |
| Task 1 (failing test) | Task 1 commit | Regression test removed. No code effect. |
| Task 0 (gate) | Task 0 commit | TASK0_CLEAR.md removed. No code effect. |

**Critical rollback rule**: never revert a task mid-stack without reverting all tasks above it in the same sequence. Running `git revert <commit>` on an intermediate task without also reverting its dependents leaves a broken tree.

**Stash before Task 3**:
```bash
# Run before Task 3 Step 6
cd ~/Desktop/nuzantara/.worktrees/browser-consolidation
git show HEAD:apps/bali-intel-scraper/backend/scrapers/browser.py > /tmp/browser-py-original-backup.py
```
Keep `/tmp/browser-py-original-backup.py` until Task 11 commits and has been verified green. Delete afterwards.

---

## Spec coverage self-review

| Requirement | Task(s) |
|---|---|
| Register AHUScraper in pipeline | Task 5 (+ Task 0 verification gate) |
| Replace ahu.py inline Playwright with stealth BrowserManager | Task 4 (+ Tasks 1, 9, 10) |
| Fix _fetch_detail DOM-clobber bug | Task 4 Step 3 + Task 9 regression |
| Fill nuzantara-mcp-browser with FastMCP server | Tasks 6, 7, 8 |
| Shutdown hooks (no Chromium leak) | Task 4 (atexit), Task 7 (lifespan) |
| Don't break bali-intel-scraper production | Task 3 Step 8 regression test; rollback plan |
| No LLM-in-loop tools | Enforced by browser-core having zero LLM deps |
| Policy: no Anthropic/OpenAI/Google SDK | browser-core deps = playwright only |
| Stealth patches actually work | Task 3.5 (bot.sannysoft.com) |
| AHU parser correctness | Task 4.5 (synthetic HTML fixture) |
| Manual dry-run safety net | Task 10 (gated, single shot) |

## Placeholder scan

Searched for: TBD, TODO, fill in, implement later, add appropriate, similar to task, configure later.

Result: none found. Every step has actual commands or code blocks. The only intentional placeholder is `<date>` and `<result>` in Task 10 Step 4 / Task 11 Step 6 commit messages, which get filled at execution time.
