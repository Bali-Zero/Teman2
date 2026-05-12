# WR2 Orchestrator PDF Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python orchestrator that closes the WR2 carousel loop end-to-end (`PG draft → ReportLab PDF → Tigris S3 upload → Canva MCP import-design-from-url → PG update`) without any LLM in the orchestration path. Replaces the legacy `wr2_canva_apply.py` which has a 50% MCP cold-fail rate.

**Architecture:** Python asyncio orchestrator using `mcp` SDK 1.12.4 (Anthropic official) over HTTP streamable transport with orchestrator-owned OAuth tokens at `~/.config/wr2/canva_tokens.json` (HMAC + flock + proactive refresh). Per-draft CAS lease in PG prevents overlapping launchd-tick processing. Tigris orphan PDFs cleaned via S3 lifecycle + explicit step on failure paths. Launchd plist uses `zsh -lc 'source ~/.nuzantara-secrets.env && exec flock -n <lock> python <orchestrator>'` for secret rotation + single-instance.

**Tech Stack:** Python 3.11+, asyncio, asyncpg, boto3, httpx, mcp SDK 1.12.4, ReportLab (renderer existing), flock 0.4.0 brew, launchd, PostgreSQL (Fly tunnel via flycast localhost:15432), Tigris S3 (fly.storage.tigris.dev), Canva remote MCP (mcp.canva.com/mcp HTTP+OAuth+RFC7591), Telegram bot API.

**Spec reference:** [`docs/superpowers/specs/2026-05-13-wr2-orchestrator-pdf-render-design.md`](../specs/2026-05-13-wr2-orchestrator-pdf-render-design.md) at commit `cee3e5c3b`.

---

## File structure

### Production code (10 modules + 4 scripts + 3 plist)

| Path | Purpose | Lines est. |
|---|---|---|
| `apps/backend-rag/backend/services/canva_renderer_v2/__init__.py` | package marker | 10 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_telegram.py` | best-effort Telegram notify | 40 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_pg.py` | asyncpg conn + kill switch + lease CAS + fetch + persist + cleanup | 180 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_schema_adapter.py` | detect legacy schema + adapt to v2 | 140 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_pdf_pipeline.py` | subprocess wrapper for `wr2_canva_pdf_render.py` | 70 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_tigris.py` | boto3 upload + delete + retry + URL build | 120 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_token_storage.py` | `OrchestratorTokenStorage(TokenStorage)` HMAC+flock+proactive | 200 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_canva_mcp.py` | `mcp.ClientSession` init + `call_tool` wrapper + transient classifier | 150 |
| `apps/backend-rag/backend/services/canva_renderer_v2/_telemetry.py` | append-only JSONL telemetry | 50 |
| `apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py` | top-level `run()` composing all above | 180 |
| `apps/backend-rag/backend/db/migrations_v2/NNN_wr2_draft_lease.sql` | new lease columns | 30 |
| `scripts/wr2_canva_pdf_apply.py` | thin launchd entrypoint | 30 |
| `scripts/wr2_bootstrap_canva_oauth.py` | one-shot interactive OAuth bootstrap | 180 |
| `scripts/wr2_canva_token_watchdog.py` | daily token expiry watchdog | 80 |
| `scripts/wr2_canva_lease_watchdog.py` | 10min stale-lease recovery | 80 |
| `scripts/wr2_e2e_create_fixture_draft.py` | E2E test draft creator | 70 |
| `infra/launchagents/com.balizero.wr2.canva-renderer.plist` | replaces existing plist | xml |
| `infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist` | new daily plist | xml |
| `infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist` | new 10min plist | xml |
| `infra/tigris/wr2-pdf-lifecycle.json` | S3 retention policy | json |

### Tests (8 unit + 1 e2e fixtures)

| Path | Purpose |
|---|---|
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/conftest.py` | pytest fixtures shared |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_telegram.py` | notify mock |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pg.py` | asyncpg mock + lease CAS |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py` | 3 fixture drafts |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pdf_pipeline.py` | subprocess mock |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_tigris.py` | moto S3 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_token_storage.py` | tmp dir + HMAC + flock concurrency |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_canva_mcp.py` | httpx_mock |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_orchestrator.py` | integration with all mocks |
| `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_legacy_parq.json` | data |
| `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_v2_kep71.json` | data |
| `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_v2_deep.json` | data |

---

## Task 1: DB migration for per-draft lease

**Files:**
- Create: `apps/backend-rag/backend/db/migrations_v2/146_wr2_draft_lease.sql`

> Numbering: most recent on prod is `145_*`. Verify on Pro before commit: `psql -c "SELECT max(migration_number) FROM schema_migrations"`. If higher than 145, bump.

- [ ] **Step 1: Write migration SQL**

Create file with content:

```sql
-- 146_wr2_draft_lease.sql
-- Adds per-draft CAS lease to war_room_drafts.
-- Two columns: lease_owner (PID@host string) + lease_acquired_at (timestamptz).
-- Used by canva_renderer_v2 orchestrator to prevent double-processing.

ALTER TABLE war_room_drafts
  ADD COLUMN IF NOT EXISTS lease_owner text,           -- squawk-ignore: prefer-text-field
  ADD COLUMN IF NOT EXISTS lease_acquired_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_war_room_drafts_lease_recovery
  ON war_room_drafts (lease_acquired_at)
  WHERE status = 'rendering' AND lease_acquired_at IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_war_room_drafts_lease_recovery;
ALTER TABLE war_room_drafts
  DROP COLUMN IF EXISTS lease_acquired_at,
  DROP COLUMN IF EXISTS lease_owner;
```

- [ ] **Step 2: Verify Squawk lint passes locally**

Run: `cd ~/Desktop/nuzantara && squawk apps/backend-rag/backend/db/migrations_v2/146_wr2_draft_lease.sql 2>&1 | tail -5`

Expected: no violations (partial index + IF NOT EXISTS pattern is Squawk-clean).

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/db/migrations_v2/146_wr2_draft_lease.sql
git commit -m "feat(db): migration 146 wr2_draft_lease columns for orchestrator v2

Adds lease_owner (text) + lease_acquired_at (timestamptz) to
war_room_drafts. Used by canva_renderer_v2 orchestrator for CAS lease
that prevents overlapping launchd-tick double-processing.

Partial index on (lease_acquired_at) WHERE status='rendering' supports
the 10min stale-lease watchdog query path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 2: Package skeleton + `_telegram.py`

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/__init__.py`
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_telegram.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/__init__.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/conftest.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_telegram.py`

- [ ] **Step 1: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_telegram.py`:

```python
"""Telegram notify is best-effort: never raises, swallows network errors."""
from unittest.mock import patch
from backend.services.canva_renderer_v2._telegram import send_telegram


def test_send_telegram_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    with patch("urllib.request.urlopen") as mock_open:
        send_telegram("hello world")
        assert mock_open.called
        url = mock_open.call_args[0][0]
        assert "api.telegram.org" in url


def test_send_telegram_swallows_network_error(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        send_telegram("hello")  # MUST NOT raise


def test_send_telegram_no_token_silent(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with patch("urllib.request.urlopen") as mock_open:
        send_telegram("hello")
        assert not mock_open.called
```

Create empty `__init__.py` in both test dir and the service dir.
Create `conftest.py`:

```python
"""Shared fixtures for canva_renderer_v2 tests."""
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "canva_renderer_v2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_telegram.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.canva_renderer_v2._telegram'`

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend-rag/backend/services/canva_renderer_v2/__init__.py`:

```python
"""WR2 orchestrator v2 — PDF render pipeline.

Replaces legacy backend.services.canva_renderer (which depended on
claude -p subprocess with 50% MCP cold-fail rate).

See docs/superpowers/specs/2026-05-13-wr2-orchestrator-pdf-render-design.md
"""
```

Create `apps/backend-rag/backend/services/canva_renderer_v2/_telegram.py`:

```python
"""Best-effort Telegram notify. Failures are swallowed (no raise).

Reads TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_CHAT_ID env vars.
If TELEGRAM_BOT_TOKEN absent, silently no-op.
"""
from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{token}/sendMessage",
            data,
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning("Telegram send failed (swallowed): %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_telegram.py -v`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/__init__.py \
        apps/backend-rag/backend/services/canva_renderer_v2/_telegram.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/__init__.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/conftest.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_telegram.py
git commit -m "feat(canva-renderer-v2): pkg init + _telegram.py best-effort notify

Telegram notify swallows network errors. No-op when TELEGRAM_BOT_TOKEN
unset. Pattern reused verbatim from legacy wr2_canva_apply.py.

3 unit tests cover success, network error swallowing, missing-token
silence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 3: `_schema_adapter.py` with 3 fixtures

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_schema_adapter.py`
- Create: `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_legacy_parq.json`
- Create: `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_v2_kep71.json`
- Create: `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_v2_deep.json`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py`

Source material: `/tmp/wr2_legacy_adapter.py` (130 LOC, working). Adapt for proper module structure + tests.

- [ ] **Step 1: Create fixture files**

`draft_legacy_parq.json` — legacy schema (slide_type field, no layout_family):

```json
{
  "slides": [
    {"slide_number": 1, "slide_type": "cover", "headline": "Parq Ambassador",
     "subhead": "Immigration designates Parq", "body": "...", "is_hero_image": true,
     "image_url": "https://example.com/parq-hero.jpg"},
    {"slide_number": 2, "slide_type": "take", "headline": "What happened",
     "subhead": "16 October 2026", "body": "Indonesia immigration appointed Parq..."},
    {"slide_number": 3, "slide_type": "law", "headline": "The provision",
     "subhead": "Permenkumham 22/2023", "body": "Article 14 ayat 2..."}
  ]
}
```

`draft_v2_kep71.json` — v2 schema (layout_family present):

```json
{
  "carousel_id": "kep71-pj-2026",
  "slide_count": 6,
  "primary_regulation_code": "KEP-71/PJ/2026",
  "slides": [
    {"index": 1, "layout_family": "cover-photo", "heading": "SPT Deadline",
     "subheading": "Extended", "body": "From 30/04 to 31/05/2026"},
    {"index": 2, "layout_family": "evidence-carved", "heading": "KEP-71",
     "evidence_code": "KEP-71/PJ/2026", "body": "Issued by Bimo Wijayanto"}
  ]
}
```

`draft_v2_deep.json` — v2 with multiple layout types:

```json
{
  "carousel_id": "deep-test",
  "slide_count": 4,
  "slides": [
    {"index": 1, "layout_family": "stat-card-hero", "stat": "31 MAY",
     "caption": "PPh Badan", "source": "KEP-71/PJ/2026"},
    {"index": 2, "layout_family": "thin-red-rule-divider",
     "body": "Late filing penalty: Rp 1jt", "source": "UU KUP"},
    {"index": 3, "layout_family": "swiss-grid-asymmetry",
     "yellow_accent": "MECHANISM",
     "steps": [
       {"num": "01", "head": "Check NPWP", "body": "Verify status"},
       {"num": "02", "head": "Submit SPT", "body": "Before deadline"}
     ]},
    {"index": 4, "layout_family": "statement-bomb",
     "statement": "Pay on time or pay double"}
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py`:

```python
"""Schema adapter: detect legacy + adapt to v2."""
import json
from pathlib import Path

import pytest

from backend.services.canva_renderer_v2._schema_adapter import (
    adapt_legacy_schema,
    is_legacy_schema,
)

FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "canva_renderer_v2"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_is_legacy_schema_detects_slide_type():
    data = _load("draft_legacy_parq.json")
    assert is_legacy_schema(data) is True


def test_is_legacy_schema_rejects_v2():
    assert is_legacy_schema(_load("draft_v2_kep71.json")) is False
    assert is_legacy_schema(_load("draft_v2_deep.json")) is False


def test_adapt_legacy_maps_cover_to_cover_photo():
    legacy = _load("draft_legacy_parq.json")
    adapted = adapt_legacy_schema(legacy, topic="Parq Ambassador")
    assert adapted["slide_count"] == 3
    assert adapted["slides"][0]["layout_family"] == "cover-photo"
    assert adapted["slides"][0]["heading"] == "Parq Ambassador"


def test_adapt_legacy_maps_law_to_thin_red_rule_divider():
    legacy = _load("draft_legacy_parq.json")
    adapted = adapt_legacy_schema(legacy, topic="Parq")
    slide_3 = adapted["slides"][2]
    assert slide_3["layout_family"] == "thin-red-rule-divider"
    assert slide_3["source"] == "Permenkumham 22/2023"


def test_adapt_legacy_no_hero_url_no_path():
    legacy = _load("draft_legacy_parq.json")
    # Strip the hero URL
    legacy["slides"][0]["image_url"] = ""
    adapted = adapt_legacy_schema(legacy, topic="Parq")
    assert "hero_image_path" not in adapted["slides"][0]


def test_v2_schema_passes_through_unchanged():
    """is_legacy=False drafts should not be touched."""
    v2 = _load("draft_v2_kep71.json")
    # adapt_legacy_schema is only called when is_legacy_schema is True,
    # but assert the detector says False.
    assert is_legacy_schema(v2) is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write minimal implementation**

Create `apps/backend-rag/backend/services/canva_renderer_v2/_schema_adapter.py`:

```python
"""Legacy slides_json schema → v2 (Article 14 layout_family) adapter.

Detection: presence of `slide_type` field on first slide AND absence of
`layout_family` → legacy. Otherwise v2 passes through unchanged.

Used for drafts created before 2026-05-13 by storyboarder versions that
emitted slide_type strings. Storyboarder patched 2026-05-13 emits v2
schema directly; orchestrator handles both via this adapter inline.

Source material: /tmp/wr2_legacy_adapter.py (working draft 2026-05-13).
"""
from __future__ import annotations

import logging
import re
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LEGACY_TO_LAYOUT = {
    "cover": "cover-photo",
    "take": "photo-headline-yellow-sub",
    "context": "photo-headline-yellow-sub",
    "shift": "evidence-carved",
    "mechanism": "swiss-grid-asymmetry",
    "stake": "photo-headline-yellow-sub",
    "law": "thin-red-rule-divider",
    "fiction-vs-substance": "dark-status-list",
    "numbers": "stat-card-hero",
    "signal": "photo-headline-yellow-sub",
    "cta": "elegant-close",
    "closing": "statement-bomb",
    "statement": "statement-bomb",
    "insight": "photo-headline-yellow-sub",
}

HERO_CACHE_DIR = Path("/tmp/wr2_hero_cache")


def is_legacy_schema(data: dict[str, Any]) -> bool:
    """Detect legacy schema by presence of `slide_type` on any slide."""
    slides = data.get("slides", [])
    if not slides:
        return False
    first = slides[0]
    return "slide_type" in first and "layout_family" not in first


def _download_hero(url: str, slide_n: int) -> str | None:
    if not url:
        return None
    HERO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = HERO_CACHE_DIR / f"hero_{slide_n:02d}.jpg"
    if dest.exists():
        return str(dest)
    try:
        urllib.request.urlretrieve(url, dest)  # noqa: S310
        return str(dest)
    except Exception as e:  # noqa: BLE001
        logger.warning("hero %d download failed: %s", slide_n, e)
        return None


def _map_swiss_grid_steps(body: str) -> list[dict]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    steps: list[dict] = []
    for k, sent in enumerate(sentences[:3]):
        words = sent.split()
        head = " ".join(words[:4]).rstrip(",.;:")
        rest = " ".join(words[4:]).strip()
        steps.append({"num": f"{k + 1:02d}", "head": head, "body": rest[:90]})
    return steps


def adapt_legacy_schema(legacy: dict[str, Any], *, topic: str) -> dict[str, Any]:
    """Convert legacy slides_json → v2 Article 14 layout schema."""
    slides_in = legacy.get("slides", [])
    n = len(slides_in)
    adapted: list[dict] = []

    for i, ls in enumerate(slides_in):
        slide_type = ls.get("slide_type", "")
        layout = LEGACY_TO_LAYOUT.get(slide_type, "photo-headline-yellow-sub")
        if i == n - 1 and slide_type == "cta":
            layout = "statement-bomb"

        hero_path = None
        if ls.get("is_hero_image") and ls.get("image_url"):
            hero_path = _download_hero(ls["image_url"], ls.get("slide_number", i + 1))

        new: dict[str, Any] = {
            "index": ls.get("slide_number", i + 1),
            "layout_family": layout,
            "heading": ls.get("headline") or "",
            "subheading": ls.get("subhead") or "",
            "body": ls.get("body") or "",
        }
        if hero_path:
            new["hero_image_path"] = hero_path

        if layout == "statement-bomb":
            new["statement"] = ls.get("headline") or (ls.get("body", "") or "")[:120]
        elif layout == "stat-card-hero":
            text = (ls.get("body") or "") + " " + (ls.get("headline") or "")
            m = re.search(r"\b(\d+(?:,\d{3})*(?:\.\d+)?[KMB%]?)\b", text)
            new["stat"] = m.group(1) if m else "—"
            new["caption"] = (ls.get("body") or "")[:120]
            new["source"] = ls.get("subhead") or ""
        elif layout == "thin-red-rule-divider":
            new["body"] = ls.get("body") or ls.get("headline") or ""
            new["source"] = ls.get("subhead") or ""
        elif layout == "swiss-grid-asymmetry":
            new["yellow_accent"] = ls.get("subhead") or "MECHANISM"
            new["steps"] = _map_swiss_grid_steps(ls.get("body") or "")
        elif layout == "dark-status-list":
            new["list_items"] = [
                {"label": "FICTION", "value": "MYTH", "status": "critical"},
                {"label": "SUBSTANCE", "value": "FACT", "status": "positive"},
            ]
        elif layout == "elegant-close":
            new["heading"] = "Want to act on this?"
            new["body"] = ls.get("body") or ""
            new["email"] = "zantara@balizero.com"
            new["whatsapp"] = "wa.me/6285954680980"
        elif layout == "evidence-carved":
            new["evidence_code"] = ls.get("subhead") or ""

        adapted.append(new)

    out = {
        "carousel_id": legacy.get("carousel_id", topic.lower().replace(" ", "-")[:80]),
        "slide_count": len(adapted),
        "slides": adapted,
    }
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py -v`

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_schema_adapter.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py \
        apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/
git commit -m "feat(canva-renderer-v2): _schema_adapter.py + 3 fixtures

Detects legacy slides_json (slide_type field) and adapts to v2 Article
14 layout_family schema. Pure function, no DB/network IO except hero
download via urllib (best-effort, returns None on failure).

3 fixtures: legacy Parq Ambassador, v2 KEP-71, v2 deep schema.
6 unit tests cover detection + layout mapping + missing hero URL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 4: `_pdf_pipeline.py` subprocess wrapper

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_pdf_pipeline.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pdf_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
"""PDF pipeline: invoke wr2_canva_pdf_render.py via subprocess, return path or None."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.services.canva_renderer_v2._pdf_pipeline import render_pdf, PdfRenderError


def test_render_pdf_success(tmp_path):
    slides = {"carousel_id": "test", "slide_count": 1, "slides": [
        {"index": 1, "layout_family": "cover-photo", "heading": "x", "body": "y"}
    ]}
    pdf_dest = tmp_path / "wr2_test.pdf"

    def fake_run(args, **kwargs):
        # Write a valid-looking PDF (first 4 bytes %PDF)
        pdf_dest.write_bytes(b"%PDF-1.4\n... fake pdf body\n%%EOF")
        return MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        result = render_pdf(slides, draft_id="test", out_path=pdf_dest)
        assert result == pdf_dest
        assert pdf_dest.exists() and pdf_dest.stat().st_size > 4


def test_render_pdf_subprocess_exit_nonzero(tmp_path):
    slides = {"slides": []}
    pdf_dest = tmp_path / "wr2_test.pdf"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="ReportLab error")
        with pytest.raises(PdfRenderError, match="exit≠0"):
            render_pdf(slides, draft_id="test", out_path=pdf_dest)


def test_render_pdf_zero_size_output(tmp_path):
    slides = {"slides": []}
    pdf_dest = tmp_path / "wr2_test.pdf"
    pdf_dest.write_bytes(b"")  # zero size

    def fake_run(args, **kwargs):
        return MagicMock(returncode=0, stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        with pytest.raises(PdfRenderError, match="zero.size"):
            render_pdf(slides, draft_id="test", out_path=pdf_dest)


def test_render_pdf_timeout(tmp_path):
    slides = {"slides": []}
    pdf_dest = tmp_path / "wr2_test.pdf"
    with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("python", 120)):
        with pytest.raises(PdfRenderError, match="timeout"):
            render_pdf(slides, draft_id="test", out_path=pdf_dest)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_pdf_pipeline.py -v`

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
"""Subprocess wrapper for scripts/wr2_canva_pdf_render.py.

Writes slides_json to a temp path, invokes the renderer Python script
via subprocess with 120s timeout, returns the output PDF path or raises
PdfRenderError. The renderer itself is a separate process so a hung
ReportLab call doesn't take down the orchestrator.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]  # backend-rag/backend/services/canva_renderer_v2/ → repo root
RENDER_SCRIPT = REPO_ROOT / "scripts" / "wr2_canva_pdf_render.py"

DEFAULT_TIMEOUT_S = 120


class PdfRenderError(RuntimeError):
    """Raised when the renderer subprocess fails."""


def render_pdf(
    slides_json: dict[str, Any],
    *,
    draft_id: str,
    out_path: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Path:
    """Render slides_json → PDF at out_path. Raise PdfRenderError on failure."""
    slides_tmp = Path(tempfile.mkstemp(prefix=f"slides_{draft_id}_", suffix=".json")[1])
    slides_tmp.write_text(json.dumps(slides_json))

    cmd = [
        sys.executable,
        str(RENDER_SCRIPT),
        "--slides-json", str(slides_tmp),
        "--out", str(out_path),
    ]
    logger.info("Render draft %s → %s", draft_id, out_path)

    try:
        result = subprocess.run(  # noqa: S603 — known python interpreter
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise PdfRenderError(f"timeout {timeout_s}s for draft {draft_id}") from e
    finally:
        slides_tmp.unlink(missing_ok=True)

    if result.returncode != 0:
        raise PdfRenderError(
            f"subprocess exit≠0 for draft {draft_id}: {result.stderr[:500]}"
        )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise PdfRenderError(
            f"renderer produced zero-size output for draft {draft_id}"
        )
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_pdf_pipeline.py -v`

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_pdf_pipeline.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pdf_pipeline.py
git commit -m "feat(canva-renderer-v2): _pdf_pipeline.py subprocess wrapper

Invokes scripts/wr2_canva_pdf_render.py via subprocess with 120s
timeout. Returns PDF path or raises PdfRenderError (exit≠0, zero-size,
or timeout). Subprocess isolation prevents hung ReportLab from
taking down the orchestrator.

4 unit tests cover success, exit≠0, zero-size output, timeout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 5: `_tigris.py` boto3 upload + delete + S3 lifecycle JSON

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_tigris.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_tigris.py`
- Create: `infra/tigris/wr2-pdf-lifecycle.json`

- [ ] **Step 1: Write S3 lifecycle policy**

`infra/tigris/wr2-pdf-lifecycle.json`:

```json
{
  "Rules": [
    {
      "ID": "wr2-pdf-prod-30d",
      "Status": "Enabled",
      "Filter": {"Prefix": "wr2-pdf/"},
      "Expiration": {"Days": 30}
    },
    {
      "ID": "wr2-pdf-tests-1d",
      "Status": "Enabled",
      "Filter": {"Prefix": "wr2-pdf-tests/"},
      "Expiration": {"Days": 1}
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
"""Tigris S3 client: put_object with retry + delete + URL build."""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.canva_renderer_v2._tigris import (
    build_public_url,
    delete_pdf,
    upload_pdf,
    TigrisError,
)


@pytest.fixture
def fake_s3():
    """boto3 client stub. Return success unless overridden by test."""
    client = MagicMock()
    client.put_object.return_value = {"ETag": '"abc123"'}
    client.delete_object.return_value = {}
    return client


def test_upload_pdf_success(tmp_path, fake_s3):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n...\n%%EOF")
    url = upload_pdf(fake_s3, pdf, draft_id="abc-123", prefix="wr2-pdf")
    assert url == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc-123.pdf"
    fake_s3.put_object.assert_called_once()
    call = fake_s3.put_object.call_args
    assert call.kwargs["Key"] == "wr2-pdf/abc-123.pdf"
    assert call.kwargs["ContentType"] == "application/pdf"
    assert call.kwargs["ACL"] == "public-read"


def test_upload_pdf_retries_on_transient_error(tmp_path):
    from botocore.exceptions import ClientError
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    s3 = MagicMock()
    # Fail twice (503), succeed third
    s3.put_object.side_effect = [
        ClientError({"Error": {"Code": "503"}}, "PutObject"),
        ClientError({"Error": {"Code": "503"}}, "PutObject"),
        {"ETag": '"abc"'},
    ]
    url = upload_pdf(s3, pdf, draft_id="abc", prefix="wr2-pdf")
    assert url.endswith("/wr2-pdf/abc.pdf")
    assert s3.put_object.call_count == 3


def test_upload_pdf_exhausts_retries(tmp_path):
    from botocore.exceptions import ClientError
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    s3 = MagicMock()
    s3.put_object.side_effect = ClientError({"Error": {"Code": "503"}}, "PutObject")
    with pytest.raises(TigrisError, match="exhausted retries"):
        upload_pdf(s3, pdf, draft_id="abc", prefix="wr2-pdf")
    assert s3.put_object.call_count == 3


def test_delete_pdf_best_effort(fake_s3):
    delete_pdf(fake_s3, draft_id="abc", prefix="wr2-pdf")
    fake_s3.delete_object.assert_called_once()
    # Must not raise even if delete fails
    fake_s3.delete_object.side_effect = Exception("boom")
    delete_pdf(fake_s3, draft_id="abc", prefix="wr2-pdf")  # no raise


def test_build_public_url():
    url = build_public_url("abc", prefix="wr2-pdf")
    assert url == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc.pdf"
    url2 = build_public_url("xyz", prefix="wr2-pdf-tests")
    assert url2 == "https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf-tests/xyz.pdf"
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_tigris.py -v`

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 4: Write implementation**

```python
"""Tigris S3 client wrapper. boto3 put_object with 3-retry + delete + URL build.

Bucket: nuzantara-warroom-images (public-read prefix wr2-pdf/).
Endpoint: https://fly.storage.tigris.dev
Credentials: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env (Tigris-compat).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

BUCKET = "nuzantara-warroom-images"
ENDPOINT = "https://fly.storage.tigris.dev"
PUBLIC_HOST = f"{BUCKET}.fly.storage.tigris.dev"

MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0  # 2s, 4s, 8s

TRANSIENT_ERROR_CODES = {"503", "502", "504", "RequestTimeout", "SlowDown", "Throttling"}


class TigrisError(RuntimeError):
    """Tigris S3 operation failed after retries."""


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="auto",
    )


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in TRANSIENT_ERROR_CODES
    return isinstance(exc, BotoCoreError)


def upload_pdf(s3, pdf_path: Path, *, draft_id: str, prefix: str = "wr2-pdf") -> str:
    """Upload PDF to s3://BUCKET/{prefix}/{draft_id}.pdf, return public URL."""
    key = f"{prefix}/{draft_id}.pdf"
    body = pdf_path.read_bytes()

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=body,
                ContentType="application/pdf",
                ACL="public-read",
            )
            logger.info("Tigris upload OK: %s (attempt %d)", key, attempt)
            return build_public_url(draft_id, prefix=prefix)
        except (ClientError, BotoCoreError) as e:
            last_exc = e
            if not _is_transient(e):
                raise TigrisError(f"Tigris non-transient error: {e}") from e
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE_S * (2 ** (attempt - 1))
                logger.warning(
                    "Tigris transient error attempt %d/%d: %s — sleep %.1fs",
                    attempt, MAX_RETRIES, e, delay,
                )
                time.sleep(delay)
    raise TigrisError(f"Tigris exhausted retries for {key}: {last_exc}") from last_exc


def delete_pdf(s3, *, draft_id: str, prefix: str = "wr2-pdf") -> None:
    """Best-effort delete. Never raises (S3 lifecycle is the safety net)."""
    key = f"{prefix}/{draft_id}.pdf"
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        logger.info("Tigris delete OK: %s", key)
    except Exception as e:  # noqa: BLE001
        logger.warning("Tigris delete failed (swallowed): %s — %s", key, e)


def build_public_url(draft_id: str, *, prefix: str = "wr2-pdf") -> str:
    return f"https://{PUBLIC_HOST}/{prefix}/{draft_id}.pdf"
```

- [ ] **Step 5: Run tests**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_tigris.py -v`

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_tigris.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_tigris.py \
        infra/tigris/wr2-pdf-lifecycle.json
git commit -m "feat(canva-renderer-v2): _tigris.py boto3 upload + S3 lifecycle

upload_pdf with 3-retry exp backoff (2s/4s/8s) classifies transient
codes (503/502/504/RequestTimeout/SlowDown/Throttling) vs permanent.
delete_pdf best-effort (S3 lifecycle is safety net).

infra/tigris/wr2-pdf-lifecycle.json: 30d retention on wr2-pdf/, 1d
on wr2-pdf-tests/ (E2E auto-cleanup).

5 unit tests cover success, transient retry, exhausted retries,
best-effort delete, URL builder.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 6: `_token_storage.py` HMAC + flock + proactive refresh

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_token_storage.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_token_storage.py`

- [ ] **Step 1: Write the failing test**

```python
"""OrchestratorTokenStorage: HMAC + flock + proactive refresh + atomic write."""
import hmac
import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from backend.services.canva_renderer_v2._token_storage import (
    OrchestratorTokenStorage,
    TokenStorageError,
    sign_payload,
)


HMAC_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _seed_valid(path: Path, expires_in_s: int = 3600) -> dict:
    payload = {
        "client_id": "cid",
        "client_secret": "",
        "access_token": "tok",
        "refresh_token": "ref",
        "scope": "user:read teams:read",
        "token_type": "bearer",
        "expires_at_epoch": time.time() + expires_in_s,
        "issued_at": "2026-05-13T18:30:00Z",
        "last_refreshed_iso": "2026-05-13T18:30:00Z",
    }
    signed = sign_payload(payload, key=bytes.fromhex(HMAC_KEY))
    path.write_text(json.dumps(signed))
    return signed


def test_token_load_valid(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    tokens = storage.load_sync()
    assert tokens["access_token"] == "tok"


def test_token_hmac_mismatch_raises(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    # Corrupt the file
    data = json.loads(p.read_text())
    data["access_token"] = "TAMPERED"
    p.write_text(json.dumps(data))

    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    with pytest.raises(TokenStorageError, match="HMAC"):
        storage.load_sync()


def test_token_missing_file_raises(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    with pytest.raises(TokenStorageError, match="not found"):
        storage.load_sync()


def test_proactive_refresh_signals_expiry(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p, expires_in_s=60)  # 1min < 300s margin
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    assert storage.needs_refresh() is True


def test_proactive_refresh_not_needed(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p, expires_in_s=3600)  # 1h > 300s margin
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()
    assert storage.needs_refresh() is False


def test_set_tokens_preserves_refresh_token_on_omission(tmp_path, monkeypatch):
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    storage = OrchestratorTokenStorage()

    # Canva omits refresh_token in refresh response (common pattern)
    new_tokens = {
        "access_token": "new_tok",
        "refresh_token": None,  # omitted
        "expires_in": 3600,
        "token_type": "bearer",
        "scope": "user:read teams:read",
    }
    storage.save_sync(new_tokens)
    saved = json.loads(p.read_text())
    assert saved["refresh_token"] == "ref"  # preserved from existing
    assert saved["access_token"] == "new_tok"


def _worker_lock_test(token_file: str, hmac_key: str, barrier_path: str):
    """Worker that loads + immediately saves under flock. Used in concurrency test."""
    os.environ["WR2_CANVA_TOKEN_FILE"] = token_file
    os.environ["WR2_CANVA_HMAC_KEY"] = hmac_key
    # Wait for sibling
    while not Path(barrier_path).exists():
        time.sleep(0.05)
    s = OrchestratorTokenStorage()
    tok = s.load_sync()
    s.save_sync({**tok, "access_token": f"by_pid_{os.getpid()}",
                 "expires_in": 3600, "refresh_token": tok["refresh_token"]})


def test_flock_serializes_concurrent_writes(tmp_path, monkeypatch):
    """Two processes saving concurrently → final file is consistent (HMAC valid)."""
    p = tmp_path / "canva_tokens.json"
    _seed_valid(p)
    barrier = tmp_path / "go"
    barrier.touch()

    procs = [
        multiprocessing.Process(target=_worker_lock_test, args=(str(p), HMAC_KEY, str(barrier)))
        for _ in range(2)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=10)
        assert proc.exitcode == 0

    # File must still be valid (HMAC intact)
    monkeypatch.setenv("WR2_CANVA_TOKEN_FILE", str(p))
    monkeypatch.setenv("WR2_CANVA_HMAC_KEY", HMAC_KEY)
    final = OrchestratorTokenStorage().load_sync()
    assert final["access_token"].startswith("by_pid_")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_token_storage.py -v`

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
"""Orchestrator-owned OAuth token storage.

Independent from mcp-remote npm cache (see spec §3 + memory
fact_canva_mcp_dynamic_client_registration). Path:
~/.config/wr2/canva_tokens.json (mode 0600).

Features:
- HMAC-SHA256 integrity check on every read (key from WR2_CANVA_HMAC_KEY hex).
- fcntl.flock advisory exclusive lock around read+write.
- Proactive refresh: needs_refresh() True when <300s + jitter to expiry.
- Atomic write via temp+rename.
- Preserves refresh_token if Canva omits it in refresh response.
- NO mtime-compare-before-replace (anti-pattern per panel).

Public API matches mcp.client.auth.TokenStorage (async). Sync helpers
exposed for bootstrap script + tests.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import hmac
import json
import logging
import os
import random
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REFRESH_MARGIN_S = 300
JITTER_MAX_S = 15


class TokenStorageError(RuntimeError):
    pass


def _canonical(payload: dict[str, Any]) -> str:
    without = {k: v for k, v in payload.items() if k != "_hmac"}
    return json.dumps(without, sort_keys=True, separators=(",", ":"))


def sign_payload(payload: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    sig = hmac.new(key, _canonical(payload).encode(), hashlib.sha256).hexdigest()
    return {**{k: v for k, v in payload.items() if k != "_hmac"}, "_hmac": sig}


def verify_payload(payload: dict[str, Any], *, key: bytes) -> dict[str, Any]:
    stored = payload.get("_hmac")
    if not stored:
        raise TokenStorageError("Token file missing HMAC field")
    computed = hmac.new(key, _canonical(payload).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(stored, computed):
        raise TokenStorageError("Token HMAC mismatch — corrupt or tampered")
    return {k: v for k, v in payload.items() if k != "_hmac"}


class OrchestratorTokenStorage:
    """Sync-first storage; async wrappers below for mcp SDK contract."""

    def __init__(self) -> None:
        path_env = os.environ.get("WR2_CANVA_TOKEN_FILE")
        if not path_env:
            raise TokenStorageError(
                "WR2_CANVA_TOKEN_FILE env var required (e.g. ~/.config/wr2/canva_tokens.json)"
            )
        self.path = Path(path_env).expanduser()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

        hex_key = os.environ.get("WR2_CANVA_HMAC_KEY")
        if not hex_key:
            raise TokenStorageError("WR2_CANVA_HMAC_KEY env var required (32-byte hex)")
        try:
            self.hmac_key = bytes.fromhex(hex_key)
        except ValueError as e:
            raise TokenStorageError(f"WR2_CANVA_HMAC_KEY not valid hex: {e}") from e

    @contextmanager
    def _lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "w") as fp:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)

    def load_sync(self) -> dict[str, Any]:
        if not self.path.exists():
            raise TokenStorageError(
                f"Token file not found: {self.path}. Run scripts/wr2_bootstrap_canva_oauth.py"
            )
        with self._lock():
            payload = json.loads(self.path.read_text())
            return verify_payload(payload, key=self.hmac_key)

    def needs_refresh(self) -> bool:
        try:
            tokens = self.load_sync()
        except TokenStorageError:
            return True  # treat unloadable as expired
        remaining = float(tokens.get("expires_at_epoch", 0)) - time.time()
        threshold = REFRESH_MARGIN_S + random.uniform(0, JITTER_MAX_S)
        return remaining < threshold

    def save_sync(self, new_tokens: dict[str, Any]) -> None:
        """Merge new_tokens into existing, sign, atomic write."""
        with self._lock():
            existing = {}
            if self.path.exists():
                try:
                    existing = verify_payload(
                        json.loads(self.path.read_text()), key=self.hmac_key
                    )
                except TokenStorageError:
                    logger.warning(
                        "Existing token file unverifiable; backup + replace"
                    )
                    backup = self.path.with_suffix(
                        f".broken-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
                    )
                    self.path.rename(backup)

            merged = {**existing, **new_tokens}
            # Preserve refresh_token if Canva omitted it on refresh
            if not new_tokens.get("refresh_token") and existing.get("refresh_token"):
                merged["refresh_token"] = existing["refresh_token"]
            merged["last_refreshed_iso"] = datetime.now(timezone.utc).isoformat()
            expires_in = new_tokens.get("expires_in", 3600)
            merged["expires_at_epoch"] = time.time() + float(expires_in)

            signed = sign_payload(merged, key=self.hmac_key)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(signed, indent=2))
            tmp.chmod(0o600)
            tmp.replace(self.path)

    # Async wrappers for mcp SDK TokenStorage contract
    async def get_tokens(self):
        return await asyncio.to_thread(self._load_for_sdk)

    async def set_tokens(self, tokens) -> None:
        await asyncio.to_thread(self._save_from_sdk, tokens)

    async def get_client_info(self):
        return await asyncio.to_thread(self._load_client_info)

    async def set_client_info(self, info) -> None:
        # client_info is owned by the orchestrator and written during bootstrap
        # only. Runtime no-op. (Subsequent OAuth flows in this orchestrator
        # always reuse the bootstrap-time client_id.)
        return

    def _load_for_sdk(self):
        from mcp.shared.auth import OAuthToken
        if self.needs_refresh():
            return None  # mcp SDK will trigger refresh
        data = self.load_sync()
        return OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            expires_in=int(max(0, data["expires_at_epoch"] - time.time())),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )

    def _save_from_sdk(self, tokens):
        self.save_sync({
            "access_token": tokens.access_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
            "refresh_token": tokens.refresh_token,
            "scope": tokens.scope,
        })

    def _load_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        data = self.load_sync()
        return OAuthClientInformationFull(
            client_id=data["client_id"],
            client_secret=data.get("client_secret") or None,
            redirect_uris=data.get("redirect_uris", []),
            grant_types=data.get("grant_types", ["authorization_code", "refresh_token"]),
            response_types=data.get("response_types", ["code"]),
            token_endpoint_auth_method=data.get("token_endpoint_auth_method", "none"),
            scope=data.get("scope"),
        )
```

- [ ] **Step 4: Install deps + run tests**

Run:
```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && pip install 'mcp>=1.12.4' --quiet
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_token_storage.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_token_storage.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_token_storage.py
git commit -m "feat(canva-renderer-v2): _token_storage.py HMAC+flock+proactive

OrchestratorTokenStorage owns OAuth tokens at WR2_CANVA_TOKEN_FILE
(default ~/.config/wr2/canva_tokens.json). Decoupled from mcp-remote
npm cache (see spec §3 + memory fact_canva_mcp_dynamic_client_registration).

Features: HMAC-SHA256 integrity, fcntl.flock advisory exclusive,
proactive refresh (5min margin + 0-15s jitter), atomic write,
refresh_token preservation on Canva omission, async-wrapper for mcp
SDK TokenStorage contract.

7 unit tests cover load/HMAC/missing-file/proactive/refresh-preserve/
concurrent-flock.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 7: `_canva_mcp.py` ClientSession wrapper + transient classifier

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_canva_mcp.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_canva_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
"""Canva MCP wrapper: call_tool + transient-vs-permanent classifier."""
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.canva_renderer_v2._canva_mcp import (
    CanvaMcpClient,
    is_transient_error,
    CanvaImportError,
)


def test_is_transient_429():
    err = Exception("429 Too Many Requests")
    err.status_code = 429
    assert is_transient_error(err) is True


def test_is_transient_503():
    err = Exception("503 Service Unavailable")
    err.status_code = 503
    assert is_transient_error(err) is True


def test_is_transient_400_permanent():
    err = Exception("400 Bad Request")
    err.status_code = 400
    assert is_transient_error(err) is False


def test_is_transient_network():
    import httpx
    assert is_transient_error(httpx.ConnectTimeout("boom")) is True
    assert is_transient_error(httpx.NetworkError("nope")) is True


def test_parse_design_id_from_mcp_result():
    from backend.services.canva_renderer_v2._canva_mcp import parse_design_id
    result_payload = {
        "content": [{"type": "text", "text": '{"design_id": "DAGabc1234"}'}]
    }
    assert parse_design_id(result_payload) == "DAGabc1234"


def test_parse_design_id_from_text_url():
    from backend.services.canva_renderer_v2._canva_mcp import parse_design_id
    result_payload = {
        "content": [{"type": "text",
                     "text": "Created: https://www.canva.com/design/DAGxyz9876/edit"}]
    }
    assert parse_design_id(result_payload) == "DAGxyz9876"


@pytest.mark.asyncio
async def test_import_design_calls_mcp_tool():
    client = CanvaMcpClient(server_url="https://mcp.canva.com/mcp")
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = type(
        "Result", (),
        {"content": [type("C", (), {"text": '{"design_id": "DAGabc"}'})()]},
    )()
    client._session = mock_session

    design_id, edit_url = await client.import_design_from_url(
        "https://example.com/foo.pdf", title="Test"
    )
    assert design_id == "DAGabc"
    assert edit_url == "https://www.canva.com/design/DAGabc/edit"
    mock_session.call_tool.assert_awaited_once_with(
        "import-design-from-url",
        arguments={"url": "https://example.com/foo.pdf", "title": "Test"},
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_canva_mcp.py -v`

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
"""Canva MCP client wrapper over mcp SDK 1.12.4 streamable HTTP transport.

Provides:
- CanvaMcpClient async context manager — manages ClientSession lifecycle.
- import_design_from_url() — wraps mcp call_tool + parses design_id.
- move_item_to_folder() — best-effort, non-fatal on failure.
- Transient-vs-permanent error classifier for orchestrator backoff logic.

OAuth handled by OrchestratorTokenStorage passed to OAuthClientProvider.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from backend.services.canva_renderer_v2._token_storage import OrchestratorTokenStorage

logger = logging.getLogger(__name__)

CANVA_MCP_URL = "https://mcp.canva.com/mcp"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


class CanvaImportError(RuntimeError):
    """Raised by import_design_from_url on permanent failure."""


def is_transient_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in TRANSIENT_HTTP_STATUS:
        return True
    if isinstance(exc, (httpx.NetworkError, httpx.TimeoutException)):
        return True
    return False


_DESIGN_ID_RE = re.compile(r"DA[A-Za-z0-9_-]{6,}")


def parse_design_id(result: Any) -> str:
    """Extract design_id from mcp call_tool response payload.

    Tolerates 2 shapes:
    1. {"content": [{"text": '{"design_id": "..."}'}]} — JSON-in-text
    2. {"content": [{"text": "https://www.canva.com/design/DA.../edit"}]} — URL embed
    """
    content = result.get("content") if isinstance(result, dict) else getattr(result, "content", None)
    if not content:
        raise CanvaImportError(f"MCP result missing content: {result!r}")

    first = content[0]
    text = first.get("text") if isinstance(first, dict) else getattr(first, "text", None)
    if not text:
        raise CanvaImportError(f"MCP result text empty: {first!r}")

    # Try JSON first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "design_id" in parsed:
            return parsed["design_id"]
    except json.JSONDecodeError:
        pass

    m = _DESIGN_ID_RE.search(text)
    if m:
        return m.group(0)
    raise CanvaImportError(f"design_id not found in MCP response: {text[:200]!r}")


class CanvaMcpClient:
    """Async context manager wrapping mcp.ClientSession against Canva HTTP MCP."""

    def __init__(self, server_url: str = CANVA_MCP_URL) -> None:
        self.server_url = server_url
        self._session: ClientSession | None = None
        self._cm = None  # context manager stack

    async def __aenter__(self) -> "CanvaMcpClient":
        storage = OrchestratorTokenStorage()
        info = await storage.get_client_info()
        oauth = OAuthClientProvider(
            server_url=self.server_url,
            client_metadata=OAuthClientMetadata(
                client_name="WR2 Pipeline Orchestrator",
                redirect_uris=[AnyUrl(u) for u in info.redirect_uris],
                grant_types=info.grant_types,
                response_types=info.response_types,
                token_endpoint_auth_method=info.token_endpoint_auth_method,
                scope=info.scope,
            ),
            storage=storage,
            redirect_handler=self._reject_interactive,
            callback_handler=self._reject_interactive,
        )
        self._http_client = httpx.AsyncClient(auth=oauth, follow_redirects=True, timeout=60.0)
        self._stream_cm = streamable_http_client(self.server_url, http_client=self._http_client)
        (read, write, _) = await self._stream_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session is not None:
            await self._session.__aexit__(exc_type, exc, tb)
        if self._stream_cm is not None:
            await self._stream_cm.__aexit__(exc_type, exc, tb)
        if self._http_client is not None:
            await self._http_client.aclose()

    @staticmethod
    async def _reject_interactive(*args, **kwargs):
        raise CanvaImportError(
            "OAuth interactive flow required — refresh token revoked. "
            "Run scripts/wr2_bootstrap_canva_oauth.py on Pro."
        )

    async def import_design_from_url(self, url: str, *, title: str) -> tuple[str, str]:
        if self._session is None:
            raise RuntimeError("CanvaMcpClient not entered")
        result = await self._session.call_tool(
            "import-design-from-url",
            arguments={"url": url, "title": title},
        )
        design_id = parse_design_id(result.__dict__ if not isinstance(result, dict) else result)
        edit_url = f"https://www.canva.com/design/{design_id}/edit"
        return design_id, edit_url

    async def move_item_to_folder(self, item_id: str, folder_id: str) -> None:
        if self._session is None:
            raise RuntimeError("CanvaMcpClient not entered")
        try:
            await self._session.call_tool(
                "move-item-to-folder",
                arguments={"item_id": item_id, "folder_id": folder_id},
            )
        except Exception as e:  # noqa: BLE001 — best-effort
            logger.warning("move-item-to-folder failed (non-fatal): %s", e)
```

- [ ] **Step 4: Install pytest-asyncio + run tests**

Run:
```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && pip install pytest-asyncio --quiet
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_canva_mcp.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_canva_mcp.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_canva_mcp.py
git commit -m "feat(canva-renderer-v2): _canva_mcp.py ClientSession wrapper

CanvaMcpClient async context manager wraps mcp SDK 1.12.4 streamable
HTTP client + OAuthClientProvider against https://mcp.canva.com/mcp.
OAuth tokens via OrchestratorTokenStorage. Interactive re-auth handler
raises (cron path can't open browser).

import_design_from_url + move_item_to_folder (best-effort).
parse_design_id tolerates 2 result shapes (JSON-in-text, URL-embed).
is_transient_error classifies 408/425/429/5xx + httpx Network/Timeout.

7 unit tests cover classifier + parser + tool call shape.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 8: `_pg.py` asyncpg + kill switch + lease CAS + fetch + persist

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_pg.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pg.py`

- [ ] **Step 1: Write the failing test**

```python
"""PG layer: kill switch + lease CAS fetch + persist + cleanup."""
from unittest.mock import AsyncMock

import pytest

from backend.services.canva_renderer_v2._pg import (
    acquire_lease_and_fetch,
    is_kill_switch_enabled,
    persist_canva_result,
    release_lease_permanent,
    release_lease_transient,
    reset_stale_leases,
)


@pytest.mark.asyncio
async def test_kill_switch_true():
    conn = AsyncMock()
    conn.fetchval.return_value = "true"
    assert await is_kill_switch_enabled(conn) is True


@pytest.mark.asyncio
async def test_kill_switch_false():
    conn = AsyncMock()
    conn.fetchval.return_value = "false"
    assert await is_kill_switch_enabled(conn) is False


@pytest.mark.asyncio
async def test_kill_switch_missing_row_treated_as_false():
    conn = AsyncMock()
    conn.fetchval.return_value = None
    assert await is_kill_switch_enabled(conn) is False


@pytest.mark.asyncio
async def test_acquire_lease_success_returns_row():
    conn = AsyncMock()
    fake_row = {"id": "abc", "topic": "T", "tone": "ped", "slides_json": "{}"}
    conn.fetchrow.return_value = fake_row
    row = await acquire_lease_and_fetch(conn, draft_id="abc", lease_owner="pid@host")
    assert row == fake_row
    args, kwargs = conn.fetchrow.call_args
    assert "UPDATE war_room_drafts" in args[0]
    assert args[1] == "pid@host"


@pytest.mark.asyncio
async def test_acquire_lease_loss_returns_none():
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    row = await acquire_lease_and_fetch(conn, draft_id="abc", lease_owner="pid@host")
    assert row is None


@pytest.mark.asyncio
async def test_persist_canva_result_clears_lease():
    conn = AsyncMock()
    await persist_canva_result(
        conn, draft_id="abc",
        canva_design_id="DAG1", canva_edit_url="https://canva.com/...",
        canva_view_url=None,
    )
    sql = conn.execute.call_args[0][0]
    assert "status = 'rendered'" in sql
    assert "lease_owner = NULL" in sql
    assert "lease_acquired_at = NULL" in sql


@pytest.mark.asyncio
async def test_release_lease_transient_reverts_status():
    conn = AsyncMock()
    await release_lease_transient(conn, draft_id="abc", reason="429 rate limited")
    sql = conn.execute.call_args[0][0]
    assert "status = 'drafts_imaged_checked'" in sql
    assert "lease_owner = NULL" in sql


@pytest.mark.asyncio
async def test_release_lease_permanent_sets_terminal():
    conn = AsyncMock()
    await release_lease_permanent(
        conn, draft_id="abc", status="canva_import_failed", reason="400 invalid",
    )
    sql = conn.execute.call_args[0][0]
    assert "status = $2" in sql
    assert "lease_owner = NULL" in sql


@pytest.mark.asyncio
async def test_reset_stale_leases_returns_count():
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": "abc"}, {"id": "xyz"}]
    ids = await reset_stale_leases(conn, stale_after_minutes=15)
    assert ids == ["abc", "xyz"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_pg.py -v`

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
"""PostgreSQL layer for canva_renderer_v2.

Functions:
- is_kill_switch_enabled(conn) — reads system_settings.wr2_canva_renderer_enabled
- fetch_pending_draft_ids(conn, limit) — pre-scan IDs to attempt lease
- acquire_lease_and_fetch(conn, draft_id, lease_owner) — CAS, returns row or None
- persist_canva_result(conn, ...) — UPDATE status='rendered' + canva_* + clear lease
- release_lease_transient(conn, ...) — revert status='drafts_imaged_checked'
- release_lease_permanent(conn, ..., status=...) — set terminal status
- reset_stale_leases(conn, stale_after_minutes) — watchdog recovery
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def is_kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_canva_renderer_enabled'"
    )
    return value == "true"


async def fetch_pending_draft_ids(
    conn: asyncpg.Connection, limit: int = 3
) -> list[UUID]:
    rows = await conn.fetch(
        """
        SELECT id FROM war_room_drafts
         WHERE status = 'drafts_imaged_checked'
           AND canva_edit_url IS NULL
           AND lease_owner IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )
    return [r["id"] for r in rows]


async def acquire_lease_and_fetch(
    conn: asyncpg.Connection, *, draft_id: UUID | str, lease_owner: str,
) -> dict[str, Any] | None:
    """CAS lease + return row payload, or None if another process won."""
    row = await conn.fetchrow(
        """
        UPDATE war_room_drafts
           SET status = 'rendering',
               lease_owner = $1,
               lease_acquired_at = NOW(),
               updated_at = NOW()
         WHERE id = $2
           AND status = 'drafts_imaged_checked'
           AND canva_edit_url IS NULL
           AND lease_owner IS NULL
        RETURNING id, topic, register AS tone, slides_json
        """,
        lease_owner, draft_id,
    )
    if row is None:
        logger.info("Draft %s lease lost to another process", draft_id)
    return dict(row) if row else None


async def persist_canva_result(
    conn: asyncpg.Connection, *,
    draft_id: UUID | str,
    canva_design_id: str,
    canva_edit_url: str,
    canva_view_url: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET canva_design_id = $2,
               canva_edit_url = $3,
               canva_view_url = $4,
               canva_applied_at = NOW(),
               status = 'rendered',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id, canva_design_id, canva_edit_url, canva_view_url,
    )


async def release_lease_transient(
    conn: asyncpg.Connection, *, draft_id: UUID | str, reason: str,
) -> None:
    """Revert to drafts_imaged_checked for natural retry on next tick."""
    logger.info("Draft %s released as transient: %s", draft_id, reason)
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id,
    )


async def release_lease_permanent(
    conn: asyncpg.Connection, *, draft_id: UUID | str, status: str, reason: str,
) -> None:
    """Mark terminal failure status. Not picked up by next tick."""
    logger.warning("Draft %s permanent failure (%s): %s", draft_id, status, reason)
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET status = $2,
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE id = $1
        """,
        draft_id, status,
    )


async def reset_stale_leases(
    conn: asyncpg.Connection, *, stale_after_minutes: int = 15,
) -> list[UUID]:
    """Watchdog: revert status='rendering' rows with old lease_acquired_at."""
    rows = await conn.fetch(
        """
        UPDATE war_room_drafts
           SET status = 'drafts_imaged_checked',
               lease_owner = NULL,
               lease_acquired_at = NULL,
               updated_at = NOW()
         WHERE status = 'rendering'
           AND lease_acquired_at < NOW() - ($1 || ' minutes')::interval
        RETURNING id
        """,
        str(stale_after_minutes),
    )
    return [r["id"] for r in rows]
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_pg.py -v`

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_pg.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pg.py
git commit -m "feat(canva-renderer-v2): _pg.py asyncpg + lease CAS

PG layer with:
- is_kill_switch_enabled (system_settings.wr2_canva_renderer_enabled)
- fetch_pending_draft_ids (pre-scan)
- acquire_lease_and_fetch (CAS, returns None if lost race)
- persist_canva_result (UPDATE status='rendered' + clear lease)
- release_lease_transient (revert to drafts_imaged_checked)
- release_lease_permanent (terminal status)
- reset_stale_leases (watchdog recovery >15min)

9 unit tests cover all paths with asyncpg mock.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 9: `_telemetry.py` JSONL append + log rotation

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/_telemetry.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_telemetry.py`

- [ ] **Step 1: Write test**

```python
"""Telemetry: JSONL append-only with size-based rotation."""
import json
from pathlib import Path

from backend.services.canva_renderer_v2._telemetry import log_telemetry


def test_telemetry_append(tmp_path, monkeypatch):
    log = tmp_path / "telemetry.jsonl"
    monkeypatch.setenv("WR2_TELEMETRY_PATH", str(log))
    log_telemetry(draft_id="abc", outcome="success", duration_s=12.3)
    log_telemetry(draft_id="xyz", outcome="canva_import_failed", duration_s=4.5, attempt=2)
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["draft_id"] == "abc"
    assert json.loads(lines[1])["attempt"] == 2


def test_telemetry_swallows_io_error(tmp_path, monkeypatch):
    # Point to unwritable path; must not raise
    monkeypatch.setenv("WR2_TELEMETRY_PATH", "/proc/cannot-write-here.jsonl")
    log_telemetry(draft_id="abc", outcome="success", duration_s=1.0)


def test_telemetry_rotation_at_size_cap(tmp_path, monkeypatch):
    log = tmp_path / "telemetry.jsonl"
    monkeypatch.setenv("WR2_TELEMETRY_PATH", str(log))
    monkeypatch.setenv("WR2_TELEMETRY_MAX_BYTES", "200")  # tiny cap for test
    for i in range(20):
        log_telemetry(draft_id=f"d{i}", outcome="success", duration_s=1.0)
    # Rotated file should exist alongside
    rotated = list(tmp_path.glob("telemetry.jsonl.*"))
    assert len(rotated) >= 1
```

- [ ] **Step 2: Run to verify fails**

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
"""Append-only JSONL telemetry with size-based rotation.

Path: $WR2_TELEMETRY_PATH or ~/logs/wr2_canva_pdf_apply_telemetry.jsonl.
Rotation: when file > $WR2_TELEMETRY_MAX_BYTES (default 50MB), rename
to .jsonl.<timestamp>. Old rotated files auto-deleted via OS cron
or manual cleanup (not this module's responsibility).

Never raises — telemetry must never break the orchestrator.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _path() -> Path:
    p = os.environ.get(
        "WR2_TELEMETRY_PATH",
        str(Path.home() / "logs" / "wr2_canva_pdf_apply_telemetry.jsonl"),
    )
    return Path(p)


def _max_bytes() -> int:
    return int(os.environ.get("WR2_TELEMETRY_MAX_BYTES", str(50 * 1024 * 1024)))


def _maybe_rotate(path: Path) -> None:
    if not path.exists():
        return
    if path.stat().st_size < _max_bytes():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rotated = path.with_suffix(path.suffix + f".{stamp}")
    try:
        path.rename(rotated)
    except OSError as e:
        logger.warning("Telemetry rotation failed: %s", e)


def log_telemetry(
    *, draft_id: str, outcome: str, duration_s: float,
    attempt: int = 1, exc_head: str = "",
) -> None:
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _maybe_rotate(path)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "draft_id": str(draft_id),
            "attempt": attempt,
            "outcome": outcome,
            "duration_s": round(duration_s, 1),
            "exc_head": exc_head[:240] if exc_head else "",
        }
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # noqa: BLE001 — telemetry must never break run
        logger.warning("Telemetry write failed (swallowed): %s", e)
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_telemetry.py -v`

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/_telemetry.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_telemetry.py
git commit -m "feat(canva-renderer-v2): _telemetry.py JSONL with rotation

Append-only JSONL at WR2_TELEMETRY_PATH (default
~/logs/wr2_canva_pdf_apply_telemetry.jsonl). Size-based rotation at
WR2_TELEMETRY_MAX_BYTES (default 50MB). Never raises.

3 unit tests cover append, IO swallowing, rotation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 10: `orchestrator.py` top-level integration + test

**Files:**
- Create: `apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py`
- Create: `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_orchestrator.py`

- [ ] **Step 1: Write the failing integration test**

```python
"""Orchestrator top-level: kill-switch + per-draft pipeline + happy path."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.canva_renderer_v2.orchestrator import (
    ExitCode,
    process_draft,
    run,
)


@pytest.mark.asyncio
async def test_run_exits_quiet_when_kill_switch_off():
    with patch("backend.services.canva_renderer_v2.orchestrator._connect", new=AsyncMock()) as mc:
        conn = AsyncMock()
        conn.fetchval.return_value = "false"  # kill switch off
        mc.return_value = conn
        result = await run()
        assert result == ExitCode.KILL_SWITCH_OFF


@pytest.mark.asyncio
async def test_process_draft_happy_path(tmp_path, monkeypatch):
    """Full happy path: schema adapt → render → upload → import → persist."""
    monkeypatch.setenv("TIGRIS_BUCKET", "test-bucket")

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "abc-uuid", "topic": "Test",
        "tone": "ped", "slides_json": json.dumps({"slides": []}),
    }

    mcp_client = AsyncMock()
    mcp_client.import_design_from_url.return_value = ("DAG123", "https://canva.com/design/DAG123/edit")
    mcp_client.move_item_to_folder = AsyncMock()

    s3 = MagicMock()

    with patch(
        "backend.services.canva_renderer_v2.orchestrator.render_pdf",
        return_value=tmp_path / "fake.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.upload_pdf",
        return_value="https://nuzantara-warroom-images.fly.storage.tigris.dev/wr2-pdf/abc-uuid.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.delete_pdf",
    ):
        (tmp_path / "fake.pdf").write_bytes(b"%PDF-1.4")
        ok = await process_draft(
            conn=conn, mcp_client=mcp_client, s3=s3,
            draft_id="abc-uuid", lease_owner="pid@host",
        )
        assert ok is True
        # persist_canva_result was called → status='rendered'
        sql_calls = [c.args[0] for c in conn.execute.call_args_list]
        assert any("status = 'rendered'" in s for s in sql_calls)


@pytest.mark.asyncio
async def test_process_draft_429_releases_transient_and_deletes_pdf(tmp_path):
    """429 from MCP → release_lease_transient + Tigris delete."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "abc-uuid", "topic": "T", "tone": "ped",
        "slides_json": json.dumps({"slides": []}),
    }

    mcp_client = AsyncMock()
    err = Exception("429")
    err.status_code = 429
    mcp_client.import_design_from_url.side_effect = err

    s3 = MagicMock()
    deleted: list[str] = []

    def fake_delete(s3_, **kwargs):
        deleted.append(kwargs.get("draft_id", ""))

    with patch(
        "backend.services.canva_renderer_v2.orchestrator.render_pdf",
        return_value=tmp_path / "fake.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.upload_pdf",
        return_value="https://test/wr2-pdf/abc-uuid.pdf",
    ), patch(
        "backend.services.canva_renderer_v2.orchestrator.delete_pdf",
        side_effect=fake_delete,
    ):
        (tmp_path / "fake.pdf").write_bytes(b"%PDF-1.4")
        ok = await process_draft(
            conn=conn, mcp_client=mcp_client, s3=s3,
            draft_id="abc-uuid", lease_owner="pid@host",
        )
        assert ok is False
        assert "abc-uuid" in deleted
        # release_lease_transient called → status='drafts_imaged_checked'
        sql_calls = [c.args[0] for c in conn.execute.call_args_list]
        assert any("status = 'drafts_imaged_checked'" in s for s in sql_calls)
```

- [ ] **Step 2: Run to verify fails**

Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
"""WR2 orchestrator top-level: composes all submodules.

Flow per run():
1. Connect to PG.
2. Check kill switch — exit 3 if off.
3. Reset stale leases (>15min watchdog).
4. Fetch up to MAX_DRAFTS_PER_RUN pending draft IDs.
5. For each ID: acquire CAS lease → process_draft().
6. Close PG. Return ExitCode.

Each draft has its own try/except so one failure doesn't block siblings.
"""
from __future__ import annotations

import asyncio
import enum
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.canva_renderer_v2 import _pg
from backend.services.canva_renderer_v2._canva_mcp import (
    CanvaImportError, CanvaMcpClient, is_transient_error,
)
from backend.services.canva_renderer_v2._pdf_pipeline import PdfRenderError, render_pdf
from backend.services.canva_renderer_v2._schema_adapter import (
    adapt_legacy_schema, is_legacy_schema,
)
from backend.services.canva_renderer_v2._telegram import send_telegram
from backend.services.canva_renderer_v2._telemetry import log_telemetry
from backend.services.canva_renderer_v2._tigris import (
    delete_pdf, get_s3_client, upload_pdf, TigrisError,
)
from backend.services.canva_renderer_v2._token_storage import TokenStorageError

logger = logging.getLogger(__name__)

MAX_DRAFTS_PER_RUN = 3
STALE_LEASE_MINUTES = 15
WR2_DRAFTS_FOLDER_ID = os.environ.get("WR2_DRAFTS_FOLDER_ID", "")
WR2_DRAFTS_FOLDER_ID_E2E = os.environ.get("WR2_DRAFTS_FOLDER_ID_E2E", "")


class ExitCode(enum.IntEnum):
    OK = 0
    TRANSIENT_ERROR = 1
    CONFIG_INVALID = 2
    KILL_SWITCH_OFF = 3
    TOKEN_FILE_MISSING = 4
    OAUTH_REFRESH_REVOKED = 5
    FLOCK_CONTENTION = 6
    TOKEN_CORRUPT = 7


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "wr2_canva_pdf_apply.log"),
            logging.StreamHandler(),
        ],
    )


async def _connect(dsn: str) -> asyncpg.Connection:
    return await asyncpg.connect(dsn, timeout=10)


def _lease_owner() -> str:
    return f"{os.getpid()}@{socket.gethostname()}"


async def process_draft(
    *, conn: asyncpg.Connection, mcp_client: CanvaMcpClient, s3: Any,
    draft_id: UUID | str, lease_owner: str,
) -> bool:
    """Acquire lease + run pipeline. Returns True on success, False on any failure."""
    row = await _pg.acquire_lease_and_fetch(conn, draft_id=draft_id, lease_owner=lease_owner)
    if row is None:
        return False  # lost race, silent

    topic = row["topic"]
    slides_raw = row["slides_json"]
    slides = json.loads(slides_raw) if isinstance(slides_raw, str) else slides_raw

    t0 = time.time()
    e2e_mode = os.environ.get("WR2_E2E_MODE") == "true"
    tigris_prefix = "wr2-pdf-tests" if e2e_mode else "wr2-pdf"
    folder_id = WR2_DRAFTS_FOLDER_ID_E2E if e2e_mode else WR2_DRAFTS_FOLDER_ID

    # Step A — schema adapt
    if is_legacy_schema(slides):
        slides = adapt_legacy_schema(slides, topic=topic)
        logger.info("Draft %s: adapted legacy schema", draft_id)

    # Step B — PDF render
    pdf_path = Path(f"/tmp/wr2_{draft_id}.pdf")
    try:
        render_pdf(slides, draft_id=str(draft_id), out_path=pdf_path)
    except PdfRenderError as e:
        await _pg.release_lease_permanent(
            conn, draft_id=draft_id, status="pdf_render_failed", reason=str(e),
        )
        send_telegram(f"🚨 WR2 PDF render FAILED\ndraft: `{draft_id}`\ntopic: {topic[:80]}\nerr: `{str(e)[:300]}`")
        log_telemetry(draft_id=str(draft_id), outcome="pdf_render_failed",
                      duration_s=time.time() - t0, exc_head=str(e))
        return False

    # Step C — Tigris upload
    try:
        pdf_url = upload_pdf(s3, pdf_path, draft_id=str(draft_id), prefix=tigris_prefix)
    except TigrisError as e:
        await _pg.release_lease_permanent(
            conn, draft_id=draft_id, status="pdf_render_failed", reason=str(e),
        )
        send_telegram(f"🚨 WR2 Tigris upload FAILED\ndraft: `{draft_id}`\nerr: `{str(e)[:300]}`")
        log_telemetry(draft_id=str(draft_id), outcome="tigris_failed",
                      duration_s=time.time() - t0, exc_head=str(e))
        return False

    # Step D — Canva import
    try:
        design_id, edit_url = await mcp_client.import_design_from_url(pdf_url, title=topic[:80])
    except Exception as e:
        delete_pdf(s3, draft_id=str(draft_id), prefix=tigris_prefix)
        if is_transient_error(e):
            await _pg.release_lease_transient(conn, draft_id=draft_id, reason=f"{type(e).__name__}: {e}")
            log_telemetry(draft_id=str(draft_id), outcome="canva_transient",
                          duration_s=time.time() - t0, exc_head=str(e))
        else:
            await _pg.release_lease_permanent(
                conn, draft_id=draft_id, status="canva_import_failed", reason=str(e),
            )
            send_telegram(f"🚨 WR2 Canva import FAILED\ndraft: `{draft_id}`\nerr: `{str(e)[:300]}`")
            log_telemetry(draft_id=str(draft_id), outcome="canva_import_failed",
                          duration_s=time.time() - t0, exc_head=str(e))
        return False

    # Step E — move-to-folder (best effort)
    if folder_id:
        await mcp_client.move_item_to_folder(design_id, folder_id)

    # Step F — persist
    try:
        await _pg.persist_canva_result(
            conn, draft_id=draft_id,
            canva_design_id=design_id, canva_edit_url=edit_url, canva_view_url=None,
        )
    except Exception as e:  # noqa: BLE001
        # Orphan: Canva design exists but DB didn't record. Alert + leave lease for watchdog.
        send_telegram(
            f"🚨 WR2 PG persist FAILED (Canva design EXISTS but DB unaware)\n"
            f"draft: `{draft_id}` design: `{design_id}` err: `{str(e)[:300]}`"
        )
        log_telemetry(draft_id=str(draft_id), outcome="persist_failed",
                      duration_s=time.time() - t0, exc_head=str(e))
        return False

    duration = time.time() - t0
    send_telegram(f"🎨 WR2 rendered: {topic[:80]}\n{edit_url}\nduration: {duration:.1f}s")
    log_telemetry(draft_id=str(draft_id), outcome="success", duration_s=duration)
    pdf_path.unlink(missing_ok=True)
    return True


async def run() -> ExitCode:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return ExitCode.CONFIG_INVALID

    try:
        conn = await _connect(dsn)
    except Exception as e:
        logger.error("PG connect failed: %s", e)
        return ExitCode.TRANSIENT_ERROR

    try:
        if not await _pg.is_kill_switch_enabled(conn):
            logger.info("wr2_canva_renderer_enabled != true — exiting quiet")
            return ExitCode.KILL_SWITCH_OFF

        # Stale lease watchdog (only emits Telegram, doesn't process)
        recovered = await _pg.reset_stale_leases(conn, stale_after_minutes=STALE_LEASE_MINUTES)
        if recovered:
            send_telegram(
                f"🪂 WR2 orchestrator recovered {len(recovered)} stale leases: "
                f"{[str(x)[:8] for x in recovered[:5]]}"
            )

        draft_ids = await _pg.fetch_pending_draft_ids(conn, limit=MAX_DRAFTS_PER_RUN)
        if not draft_ids:
            logger.info("no pending drafts")
            return ExitCode.OK

        lease_owner = _lease_owner()
        s3 = get_s3_client()

        try:
            async with CanvaMcpClient() as mcp_client:
                for draft_id in draft_ids:
                    try:
                        await process_draft(
                            conn=conn, mcp_client=mcp_client, s3=s3,
                            draft_id=draft_id, lease_owner=lease_owner,
                        )
                    except Exception as exc:  # noqa: BLE001 — siblings
                        logger.error("Draft %s unexpected exception: %s", draft_id, exc)
                        try:
                            await _pg.release_lease_transient(
                                conn, draft_id=draft_id, reason=f"unexpected: {exc}"
                            )
                        except Exception:  # noqa: BLE001
                            pass
        except TokenStorageError as e:
            msg = str(e).lower()
            if "not found" in msg:
                send_telegram(f"🚨 WR2 token file missing — run scripts/wr2_bootstrap_canva_oauth.py\n{e}")
                return ExitCode.TOKEN_FILE_MISSING
            if "hmac" in msg:
                send_telegram(f"🚨 WR2 token file CORRUPT — manual repair\n{e}")
                return ExitCode.TOKEN_CORRUPT
            send_telegram(f"🚨 WR2 token storage error\n{e}")
            return ExitCode.CONFIG_INVALID
        except CanvaImportError as e:
            if "refresh token revoked" in str(e).lower() or "interactive" in str(e).lower():
                send_telegram(f"🚨 WR2 OAuth refresh revoked — re-bootstrap needed\n{e}")
                return ExitCode.OAUTH_REFRESH_REVOKED
            send_telegram(f"🚨 WR2 Canva MCP error: {e}")
            return ExitCode.TRANSIENT_ERROR

        return ExitCode.OK
    finally:
        await conn.close()
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Desktop/nuzantara/apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/test_orchestrator.py -v`

Expected: 3 passed.

Then run full suite to verify nothing else broke:

```bash
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/ -v
```

Expected: 47 passed (all from tasks 2-10).

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py \
        apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_orchestrator.py
git commit -m "feat(canva-renderer-v2): orchestrator.py top-level integration

Composes all canva_renderer_v2 submodules into top-level run():
1. Connect PG → kill-switch check (exit 3)
2. Stale-lease watchdog (>15min)
3. Fetch up to MAX_DRAFTS_PER_RUN pending IDs
4. Per-draft: acquire CAS lease → process_draft pipeline
5. ExitCode enum maps exit codes 0/1/2/3/4/5/6/7

process_draft handles:
- schema adapt → render → Tigris upload → Canva import → folder move → persist
- transient (429/5xx/network) → release_lease_transient + Tigris cleanup
- permanent → release_lease_permanent + Telegram alert

3 integration unit tests cover kill-switch + happy path + 429 transient.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 11: `scripts/wr2_canva_pdf_apply.py` thin entrypoint

**Files:**
- Create: `scripts/wr2_canva_pdf_apply.py`

- [ ] **Step 1: Write entrypoint**

```python
#!/usr/bin/env python3
"""WR2 Canva PDF orchestrator entrypoint — invoked by launchd plist every 5min.

Thin wrapper around backend.services.canva_renderer_v2.orchestrator.run().
Returns ExitCode integer for launchd SuccessfulExit evaluation.
"""
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2.orchestrator import run  # noqa: E402


if __name__ == "__main__":
    exit_code = asyncio.run(run())
    sys.exit(int(exit_code))
```

- [ ] **Step 2: Smoke import test (no PG/network)**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
python -c "import sys; sys.path.insert(0, 'apps/backend-rag'); from backend.services.canva_renderer_v2.orchestrator import run, ExitCode; print('OK', ExitCode.OK)"
```

Expected: `OK ExitCode.OK`.

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/nuzantara
git add scripts/wr2_canva_pdf_apply.py
chmod +x scripts/wr2_canva_pdf_apply.py
git commit -m "feat(wr2): scripts/wr2_canva_pdf_apply.py thin entrypoint

30-LOC launchd entrypoint. Adds apps/backend-rag to sys.path, runs
orchestrator.run() via asyncio, exits with ExitCode integer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 12: Bootstrap + watchdogs + E2E fixture creator

**Files:**
- Create: `scripts/wr2_bootstrap_canva_oauth.py`
- Create: `scripts/wr2_canva_token_watchdog.py`
- Create: `scripts/wr2_canva_lease_watchdog.py`
- Create: `scripts/wr2_e2e_create_fixture_draft.py`

- [ ] **Step 1: Write bootstrap script**

```python
#!/usr/bin/env python3
"""WR2 Canva OAuth one-shot bootstrap.

Run interactively on Pro (browser available):
    export WR2_CANVA_TOKEN_FILE=~/.config/wr2/canva_tokens.json
    export WR2_CANVA_HMAC_KEY=$(openssl rand -hex 32)  # save to ~/.nuzantara-secrets.env
    python scripts/wr2_bootstrap_canva_oauth.py

Performs:
1. RFC 7591 dynamic client registration at mcp.canva.com/register
2. OAuth authorization code flow via local HTTP callback (ephemeral port)
3. Token exchange → token storage HMAC-signed
4. Smoke test: list-brand-kits via MCP, assert Bali Zero team in result

Idempotent: if token file already exists and is valid, prints status
and exits. To force re-bootstrap: delete WR2_CANVA_TOKEN_FILE first.
"""
import asyncio
import http.server
import json
import logging
import os
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2._token_storage import (  # noqa: E402
    OrchestratorTokenStorage, TokenStorageError, sign_payload,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bootstrap")

CANVA_REGISTER = "https://mcp.canva.com/register"
CANVA_AUTHORIZE = "https://mcp.canva.com/authorize"
CANVA_TOKEN = "https://mcp.canva.com/token"
SCOPE = "user:read offline_access account:read teams:read"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _register_client(redirect_uri: str) -> dict:
    body = json.dumps({
        "client_name": "WR2 Pipeline Orchestrator",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": SCOPE,
    }).encode()
    req = urllib.request.Request(
        CANVA_REGISTER, data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _exchange_code(client_id: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }).encode()
    req = urllib.request.Request(
        CANVA_TOKEN, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _smoke_test_list_brand_kits(access_token: str) -> bool:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "wr2-bootstrap", "version": "1.0"}},
    }).encode()
    req = urllib.request.Request(
        "https://mcp.canva.com/mcp", data=body,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read(200)
            logger.info("Smoke initialize: HTTP %s", r.status)
            return True
    except Exception as e:
        logger.error("Smoke failed: %s", e)
        return False


def main() -> int:
    storage = OrchestratorTokenStorage()
    if storage.path.exists():
        try:
            storage.load_sync()
            logger.info("Token file already exists and valid: %s", storage.path)
            logger.info("To force re-bootstrap: rm %s", storage.path)
            return 0
        except TokenStorageError as e:
            logger.warning("Existing token invalid, re-running bootstrap: %s", e)

    port = _free_port()
    redirect_uri = f"http://localhost:{port}/oauth/callback"
    logger.info("Registering client at %s ...", CANVA_REGISTER)
    client_info = _register_client(redirect_uri)
    client_id = client_info["client_id"]
    logger.info("client_id assigned: %s", client_id)

    import base64, hashlib, secrets
    code_verifier = secrets.token_urlsafe(96)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)

    auth_url = (
        f"{CANVA_AUTHORIZE}?response_type=code&client_id={client_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&scope={urllib.parse.quote(SCOPE)}"
        f"&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"
    )

    received: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            received["code"] = params.get("code", [""])[0]
            received["state"] = params.get("state", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>WR2 OAuth: code received. You can close this window.</h2></body></html>"
            )

        def log_message(self, format, *args):  # noqa: A002 — silence
            pass

    server = socketserver.TCPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Local callback server listening on %d. Opening browser ...", port)
    webbrowser.open(auth_url)

    # Wait for callback (max 5min)
    for _ in range(300):
        if received.get("code"):
            break
        time.sleep(1)
    server.shutdown()

    if not received.get("code"):
        logger.error("No callback within 5min")
        return 2
    if received["state"] != state:
        logger.error("State mismatch — possible CSRF")
        return 2

    logger.info("Exchanging code for tokens ...")
    tokens = _exchange_code(client_id, received["code"], code_verifier, redirect_uri)

    # Persist with HMAC. Use save_sync but enrich with client_info first.
    payload = {
        "client_id": client_id,
        "client_secret": "",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": tokens.get("scope", SCOPE),
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer"),
        "expires_in": tokens.get("expires_in", 3600),
    }
    storage.save_sync(payload)
    logger.info("Wrote token file: %s", storage.path)

    # Smoke test
    if _smoke_test_list_brand_kits(tokens["access_token"]):
        logger.info("✅ Bootstrap complete")
        return 0
    logger.error("❌ Smoke failed — token might still work but verify manually")
    return 3


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `wr2_canva_token_watchdog.py`**

```python
#!/usr/bin/env python3
"""Daily Canva OAuth refresh-token expiry watchdog.

Canva refresh tokens decay ~90 days unused. This watchdog reads
last_refreshed_iso from canva_tokens.json and alerts at 75d (warn)
and 85d (critical). Runs daily via launchd 09:00 WITA.
"""
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2._token_storage import (  # noqa: E402
    OrchestratorTokenStorage, TokenStorageError,
)
from backend.services.canva_renderer_v2._telegram import send_telegram  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token-watchdog")


def main() -> int:
    try:
        storage = OrchestratorTokenStorage()
        data = storage.load_sync()
    except TokenStorageError as e:
        send_telegram(f"🚨 WR2 Canva token UNREADABLE\n{e}")
        return 1

    last_iso = data.get("last_refreshed_iso")
    if not last_iso:
        logger.warning("No last_refreshed_iso — bootstrap predates this field")
        return 0

    last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days = (now - last).days

    if days > 85:
        send_telegram(
            f"🚨 *WR2 Canva refresh CRITICAL*\nDays since last refresh: {days}\n"
            f"Token decays at 90d — re-bootstrap NOW.\nRun: scripts/wr2_bootstrap_canva_oauth.py"
        )
    elif days > 75:
        send_telegram(
            f"⚠️ *WR2 Canva refresh WARN*\nDays since last refresh: {days}\n"
            f"Plan re-bootstrap within 15 days."
        )
    logger.info("Days since last refresh: %d", days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write `wr2_canva_lease_watchdog.py`**

```python
#!/usr/bin/env python3
"""10-min watchdog: reset stale war_room_drafts.status='rendering' leases."""
import asyncio
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.services.canva_renderer_v2._pg import reset_stale_leases  # noqa: E402
from backend.services.canva_renderer_v2._telegram import send_telegram  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lease-watchdog")


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        recovered = await reset_stale_leases(conn, stale_after_minutes=15)
        if recovered:
            ids_short = [str(x)[:8] for x in recovered[:5]]
            send_telegram(
                f"🪂 WR2 stale-lease watchdog recovered {len(recovered)}: {ids_short}"
            )
            logger.info("Recovered %d stale leases", len(recovered))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 4: Write `wr2_e2e_create_fixture_draft.py`**

```python
#!/usr/bin/env python3
"""Create a synthetic war_room_drafts row for E2E testing.

Inserts a draft with fixed UUID 00000000-0000-0000-e2e0-000000000001,
client_id 'e2e_test_client', topic prefixed [E2E TEST], status
'drafts_imaged_checked'.

Idempotent: ON CONFLICT (id) UPDATE re-resets fields for re-run.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e-fixture")

FIXTURE_UUID = "00000000-0000-0000-e2e0-000000000001"
FIXTURE_CLIENT = "e2e_test_client"

SLIDES_JSON = {
    "carousel_id": "e2e-smoke",
    "slide_count": 2,
    "slides": [
        {"index": 1, "layout_family": "cover-photo",
         "heading": "[E2E TEST] WR2 Pipeline Smoke",
         "subheading": "Synthetic test draft",
         "body": "If you see this in Canva, the pipeline works."},
        {"index": 2, "layout_family": "statement-bomb",
         "statement": "E2E success."},
    ],
}


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        await conn.execute(
            """
            INSERT INTO war_room_drafts
              (id, topic, register, slides_json, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4::jsonb, 'drafts_imaged_checked', NOW(), NOW())
            ON CONFLICT (id) DO UPDATE
              SET topic = EXCLUDED.topic,
                  slides_json = EXCLUDED.slides_json,
                  status = 'drafts_imaged_checked',
                  canva_edit_url = NULL,
                  canva_design_id = NULL,
                  lease_owner = NULL,
                  lease_acquired_at = NULL,
                  updated_at = NOW()
            """,
            FIXTURE_UUID, "[E2E TEST] WR2 Pipeline Smoke",
            "pedagogico", json.dumps(SLIDES_JSON),
        )
        logger.info("E2E fixture draft ready: id=%s", FIXTURE_UUID)
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 5: Smoke-import all 4 scripts**

```bash
cd ~/Desktop/nuzantara
for f in scripts/wr2_bootstrap_canva_oauth.py scripts/wr2_canva_token_watchdog.py \
         scripts/wr2_canva_lease_watchdog.py scripts/wr2_e2e_create_fixture_draft.py; do
  python -c "import ast; ast.parse(open('$f').read()); print('$f: syntax OK')"
done
```

Expected: 4 × "syntax OK".

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
chmod +x scripts/wr2_bootstrap_canva_oauth.py \
         scripts/wr2_canva_token_watchdog.py \
         scripts/wr2_canva_lease_watchdog.py \
         scripts/wr2_e2e_create_fixture_draft.py
git add scripts/wr2_bootstrap_canva_oauth.py \
        scripts/wr2_canva_token_watchdog.py \
        scripts/wr2_canva_lease_watchdog.py \
        scripts/wr2_e2e_create_fixture_draft.py
git commit -m "feat(wr2): bootstrap + token/lease watchdogs + E2E fixture creator

- wr2_bootstrap_canva_oauth.py: RFC 7591 dynamic registration + OAuth
  authorization code + PKCE + local HTTP callback + token persist with
  HMAC + smoke test.
- wr2_canva_token_watchdog.py: daily watchdog reads last_refreshed_iso,
  Telegram alert at 75d (warn) / 85d (critical) of 90d Canva decay.
- wr2_canva_lease_watchdog.py: 10min watchdog resets >15min stale
  war_room_drafts.status='rendering' leases.
- wr2_e2e_create_fixture_draft.py: synthetic draft with fixed UUID
  for E2E smoke testing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 13: launchd plist files

**Files:**
- Create: `infra/launchagents/com.balizero.wr2.canva-renderer.plist`
- Create: `infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist`
- Create: `infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist`

- [ ] **Step 1: Write renderer plist**

`infra/launchagents/com.balizero.wr2.canva-renderer.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.balizero.wr2.canva-renderer</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>source ~/.nuzantara-secrets.env 2>/dev/null; exec /opt/homebrew/bin/flock -n /tmp/wr2_canva_pdf_apply.lock /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/wr2_canva_pdf_apply.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/nuzantara/Desktop/nuzantara</string>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>SuccessfulExit</key>
  <array>
    <integer>0</integer>
    <integer>3</integer>
    <integer>4</integer>
    <integer>5</integer>
    <integer>7</integer>
  </array>
  <key>ThrottleInterval</key>
  <integer>300</integer>
  <key>StandardOutPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_pdf_apply.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_pdf_apply.error.log</string>
</dict>
</plist>
```

- [ ] **Step 2: Write daily token watchdog plist**

`infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.balizero.wr2.canva-token-watchdog</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>source ~/.nuzantara-secrets.env 2>/dev/null; exec /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/wr2_canva_token_watchdog.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/nuzantara/Desktop/nuzantara</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_token_watchdog.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_token_watchdog.error.log</string>
</dict>
</plist>
```

- [ ] **Step 3: Write 10-min lease watchdog plist**

`infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.balizero.wr2.canva-lease-watchdog</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>source ~/.nuzantara-secrets.env 2>/dev/null; exec /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/wr2_canva_lease_watchdog.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/nuzantara/Desktop/nuzantara</string>
  <key>StartInterval</key>
  <integer>600</integer>
  <key>RunAtLoad</key>
  <false/>
  <key>ThrottleInterval</key>
  <integer>600</integer>
  <key>StandardOutPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_lease_watchdog.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_lease_watchdog.error.log</string>
</dict>
</plist>
```

- [ ] **Step 4: Validate plist syntax**

```bash
cd ~/Desktop/nuzantara
for p in infra/launchagents/com.balizero.wr2.canva-renderer.plist \
         infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist \
         infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist; do
  plutil -lint "$p"
done
```

Expected: `OK` × 3.

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add infra/launchagents/com.balizero.wr2.canva-renderer.plist \
        infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist \
        infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist
git commit -m "feat(infra): launchd plist for v2 renderer + 2 watchdogs

- canva-renderer.plist: 5min interval, /bin/zsh -lc wrapper sourcing
  ~/.nuzantara-secrets.env, /opt/homebrew/bin/flock -n single-instance
  guard, SuccessfulExit array [0,3,4,5,7] to suppress restart loops.
- canva-token-watchdog.daily.plist: 09:00 WITA refresh-token expiry
  check.
- canva-lease-watchdog.10min.plist: 10min stale-lease recovery.

All 3 validated via plutil -lint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 14: Production runbook + cicatrix scar update

**Files:**
- Create: `docs/runbooks/wr2-orchestrator-pdf-render-runbook.md`
- Modify: `.claude/rules/cicatrix-scars.md` (status section of DAHJEkWpkzY scar)

- [ ] **Step 1: Write runbook**

Create `docs/runbooks/wr2-orchestrator-pdf-render-runbook.md`:

```markdown
# WR2 Orchestrator PDF Render — Production Runbook

## Initial deployment (one-time)

### 1. Generate HMAC key

```bash
echo "WR2_CANVA_HMAC_KEY=$(openssl rand -hex 32)" >> ~/.nuzantara-secrets.env
echo "WR2_CANVA_TOKEN_FILE=$HOME/.config/wr2/canva_tokens.json" >> ~/.nuzantara-secrets.env
echo "WR2_DRAFTS_FOLDER_ID=<your-canva-folder-id>" >> ~/.nuzantara-secrets.env
mkdir -p ~/.config/wr2 && chmod 700 ~/.config/wr2
```

### 2. Apply DB migration

```bash
ssh into Fly or run via flycast tunnel:
psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -f apps/backend-rag/backend/db/migrations_v2/146_wr2_draft_lease.sql
```

### 3. Apply Tigris S3 lifecycle

```bash
source ~/.nuzantara-secrets.env
aws s3api put-bucket-lifecycle-configuration \
  --bucket nuzantara-warroom-images \
  --lifecycle-configuration file://infra/tigris/wr2-pdf-lifecycle.json \
  --endpoint-url https://fly.storage.tigris.dev
```

### 4. Bootstrap Canva OAuth

```bash
source ~/.nuzantara-secrets.env
cd ~/Desktop/nuzantara
apps/backend-rag/.venv/bin/python scripts/wr2_bootstrap_canva_oauth.py
# Browser opens. Authorize Bali Zero team. Wait "✅ Bootstrap complete".
ls -la ~/.config/wr2/canva_tokens.json  # mode 0600
```

### 5. Install plists

```bash
cp infra/launchagents/com.balizero.wr2.canva-renderer.plist ~/Library/LaunchAgents/
cp infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist ~/Library/LaunchAgents/
cp infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist ~/Library/LaunchAgents/
```

### 6. Flip PG kill switch + bootstrap plists

```bash
psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -c "UPDATE system_settings SET value='true' WHERE key='wr2_canva_renderer_enabled'"

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-token-watchdog.daily.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-lease-watchdog.10min.plist
```

### 7. Monitor first 2-3 ticks

```bash
tail -F ~/logs/wr2_canva_pdf_apply.log

psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -c "SELECT id, status, canva_edit_url FROM war_room_drafts
      WHERE updated_at > NOW() - INTERVAL '15 minutes'
      ORDER BY updated_at DESC LIMIT 10"
```

## End-to-end smoke (after deployment)

```bash
# 1. Insert synthetic draft
python scripts/wr2_e2e_create_fixture_draft.py

# 2. Wait <=5 minutes for the next cron tick.

# 3. Verify
psql -c "SELECT status, canva_edit_url FROM war_room_drafts
         WHERE id = '00000000-0000-0000-e2e0-000000000001'"
# Expected: status='rendered', canva_edit_url populated.
```

## Rollback

```bash
launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer
psql -c "UPDATE system_settings SET value='false' WHERE key='wr2_canva_renderer_enabled'"
```

## Diagnostics

| Symptom | Check | Fix |
|---|---|---|
| "Exit 4" in log | `ls ~/.config/wr2/canva_tokens.json` | Bootstrap step 4 |
| "Exit 5" in log | Telegram says "refresh revoked" | Re-bootstrap step 4 |
| "Exit 7" in log | HMAC corruption | Backup at `.broken-*.json`, re-bootstrap |
| Drafts stuck `rendering` | Lease watchdog 10min interval | Should self-heal in ≤25min |
| Canva 429 spam | Tigris/MCP rate | Reduce MAX_DRAFTS_PER_RUN |

## Refresh-token expiry handling

Canva refresh tokens decay ~90 days. Telegram alerts at 75d (warn) and
85d (critical). Re-bootstrap:

```bash
rm ~/.config/wr2/canva_tokens.json
apps/backend-rag/.venv/bin/python scripts/wr2_bootstrap_canva_oauth.py
```
```

- [ ] **Step 2: Update cicatrix scar**

Modify `~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md`, find the section starting `### ⚠️ STRUCTURAL: WR2 master template requires verified richtext slot count (2026-05-10 → architecturally bypassed 2026-05-13)` and append in the **RESOLUTION** block at the bottom:

```markdown

**2026-05-13 v3 orchestrator end-to-end live** (commit `<final-tag>`):

The new `canva_renderer_v2` orchestrator + `wr2_canva_pdf_apply.py`
script is live on Pro via `com.balizero.wr2.canva-renderer.plist`.
End-to-end loop closed: PG draft → ReportLab → Tigris → Canva
`import-design-from-url` → PG update. No master template required.

First production draft processed: `<draft_id>` at `<timestamp>`,
duration `<X>s`. Tigris S3 lifecycle policy active (30d/1d retention).
Token + lease watchdogs running.

Legacy `wr2_canva_apply.py` remains in repo for ~2 weeks as
documented fallback, then removed in cleanup PR. Kill switch
`system_settings.wr2_canva_renderer_enabled='true'` flipped.

Scar now archival — orchestrator architecture moved past the master
template dependency entirely. Validation gap permanently closed.
```

- [ ] **Step 3: Commit**

```bash
cd ~/Desktop/nuzantara
git add docs/runbooks/wr2-orchestrator-pdf-render-runbook.md \
        .claude/rules/cicatrix-scars.md
git commit -m "docs(wr2): production runbook + cicatrix scar update v3 live

- runbook covers initial deployment (7 steps), E2E smoke, rollback,
  diagnostics, refresh-token expiry handling
- cicatrix scar DAHJEkWpkzY validation gap appends 2026-05-13 v3
  live resolution note

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin feat/wr2-canva-pdf-render-2026-05-13
```

---

## Task 15: Open PR + final acceptance

- [ ] **Step 1: Confirm all 14 prior tasks committed and pushed**

```bash
cd ~/Desktop/nuzantara
git log --oneline -20 | head -20
# Expected: 14+ commits since branch root (fbba52327)
```

- [ ] **Step 2: Run full unit-test suite locally**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/canva_renderer_v2/ -v
```

Expected: ~47-50 unit tests, all passing.

- [ ] **Step 3: Open PR**

```bash
cd ~/Desktop/nuzantara
gh pr create --base main --head feat/wr2-canva-pdf-render-2026-05-13 \
  --title "feat(wr2): orchestrator PDF render pipeline (replaces legacy canva-apply)" \
  --body "$(cat <<'EOF'
## Summary

- Replaces legacy `scripts/wr2_canva_apply.py` (50% MCP cold-fail rate) with deterministic Python orchestrator using `mcp` SDK 1.12.4 + httpx + boto3 + asyncpg.
- New `canva_renderer_v2` package (~1100 LOC across 10 modules), 4 scripts, 3 launchd plists, 1 SQL migration, S3 lifecycle JSON.
- OAuth tokens orchestrator-owned at `~/.config/wr2/canva_tokens.json` with HMAC + flock + proactive refresh, decoupled from `mcp-remote` cache.
- Per-draft CAS lease prevents overlapping launchd-tick double-processing.
- Tigris orphan PDFs cleaned via S3 lifecycle + explicit cleanup on failure.
- Transient-vs-permanent classifier (429/5xx/network → retry; 4xx structural → terminal).
- Spec at `docs/superpowers/specs/2026-05-13-wr2-orchestrator-pdf-render-design.md` (passed 3-LLM panel review: Gemini + GPT-5.5 + DeepSeek V4 Pro).

## Test plan

- [ ] All ~50 unit tests pass: `pytest backend/tests/unit/services/canva_renderer_v2/ -v`
- [ ] DB migration 146 applies cleanly + rollback restores
- [ ] Squawk lint passes on migration
- [ ] `plutil -lint` passes on 3 plist files
- [ ] Bootstrap script obtains Canva OAuth tokens (manual on Pro)
- [ ] Token watchdog detects 75d/85d threshold (manual time-travel test)
- [ ] Lease watchdog recovers stale lease (manual insert + verify)
- [ ] E2E fixture draft processes end-to-end (run after deployment)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Validate spec coverage**

Manually open `docs/superpowers/specs/2026-05-13-wr2-orchestrator-pdf-render-design.md` side-by-side with PR diff and tick each acceptance gate in §10. Address any gap found before requesting merge.

---

## Self-review checklist

After plan written, verify:

**1. Spec coverage:** Every section of the spec maps to ≥1 task:
- §1 Background → Task 1 (migration sets up DB) + Task 14 (runbook recap)
- §2 Architecture / Module decomp → Tasks 2-10 (one module per task)
- §3 Token storage → Task 6 (storage) + Task 12 (bootstrap)
- §4 Per-draft flow + Lease + Failure classification → Task 1 (DB) + Task 8 (PG layer) + Task 10 (orchestrator)
- §5 launchd plist + Kill switch + S3 lifecycle + Stale lease watchdog → Task 5 (lifecycle JSON) + Task 12 (lease watchdog script) + Task 13 (plists) + Task 14 (runbook)
- §6 Testing strategy + E2E isolation → unit tests embedded in tasks 2-10 + Task 12 (E2E fixture script)
- §7 Deliverables + commit plan → this 15-task structure mirrors §7.3

**2. Placeholder scan:** No `TBD`, `TODO`, `placeholder`, `...similar to`, or "add appropriate" found in code blocks.

**3. Type consistency:**
- `process_draft` signature in test_orchestrator.py matches definition in orchestrator.py (both take `conn`, `mcp_client`, `s3`, `draft_id`, `lease_owner` kwargs).
- `acquire_lease_and_fetch` return type `dict[str, Any] | None` matches usage in orchestrator.py.
- `ExitCode` enum used identically in test_orchestrator.py and orchestrator.py.
- `parse_design_id` defined in `_canva_mcp.py`, tested in `test_canva_mcp.py`, called in `_canva_mcp.py:CanvaMcpClient.import_design_from_url`.

All consistent.

---
