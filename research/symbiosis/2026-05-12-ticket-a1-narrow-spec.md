---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS Phase 3 — TICKET A.1 narrow spec v2 (post 4-panel)
status: spec-v2-execution-ready
empirical_survey_wita: 2026-05-12 23:25
review_completed_wita: 2026-05-12 23:32
---

# TICKET A.1 — CrmHGTBridge async publisher infrastructure (narrow spec v2)

**Date**: 2026-05-12 21:30 WITA · **Revised**: 23:32 WITA post-review
**Predecessor**: Phase 3 spec v2 §TICKET A.1 + TICKET A.0 merged (PR #626 → main `6e92046d8` at 23:19:56 WITA)
**Author**: Claude Opus 4.7 max
**Mode**: Narrow spec — execution autonomous-capable post-review per Phase 3 spec v2 refusal #2
**Estimated effort**: 0.5-0.75 day (revised down from 1d — corrections REDUCE complexity by killing dead code)
**Review status**: APPROVED with 8 corrections — Claude self PROCEED WITH CONDITIONS + Gemini 3.1 Pro BLOCK + DeepSeek Reasoner BLOCK (2 findings FALSE POSITIVE empirically) + NB-1 BLOCK (Q3.2 partially true)

## Goal

Implement `CrmHGTBridge` async publisher in `apps/crm-cell/crm_cell/hgt_publisher.py`, **deleting** the Sprint 3 W2 sync stub entirely (CrmHGTPublisher removed). After A.1 merge, CRM cell has a production-ready bridge writing canonical 9-field skills to `cell:skills` Redis stream. No production callers wired (TICKET A.2 operator-gated).

## 4-panel review convergences applied (8 corrections)

| #   | Original spec v1                                                                                                 | 4-panel verdict                                                                                                     | Correction in v2                                                                                                                                                                                                                        |
| --- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `CrmHGTPublisher` retained as raise-stub on construction                                                         | Gemini F3 + Claude self meta — "dead code clutter, zero migration value"                                            | **DELETE `CrmHGTPublisher` class entirely**. Zero callers means zero migration cost.                                                                                                                                                    |
| 2   | `StructuralPattern(pattern_kind, confidence, payload)` legacy shape + auto-formatted procedure/success_criterion | Gemini F1 CRITICAL (silent data loss via dropped `_metadata`) + Gemini Q1.1/Q1.2/F4 + NB-1 Q3.2 + Claude self F2/F3 | **Refactor `StructuralPattern` to canonical shape**: `(pattern_id, procedure, precondition, success_criterion, confidence, domain)`. Maps directly to HGTPublisher's 9 xadd fields. **NO `_metadata` field** (would be silent-dropped). |
| 3   | Bridge `try/except Exception` around `_publisher.publish(skill)`                                                 | Gemini F2 + Claude F4 + Q1.3 — dead code (HGTPublisher line 75-77 catches all)                                      | **REMOVE bridge try/except**. Simplify to direct `return await self._publisher.publish(skill)`.                                                                                                                                         |
| 4   | Test 7 mocks `xadd.side_effect=RuntimeError` to test bridge swallow                                              | Gemini Q1.3 + Claude F4 + DeepSeek F4 — RuntimeError caught by HGTPublisher, never reaches bridge                   | **DROP Test 7**. With CORR-3 there's no bridge catch to test.                                                                                                                                                                           |
| 5   | `_is_pii_clean(payload)` scans payload keys for forbidden identifiers                                            | (from CORR-2 schema change)                                                                                         | **Adapt `_is_pii_clean` to scan strings** (procedure/precondition/success_criterion) for PII markers, mirroring IntelScraperHGTBridge `_is_pii_tainted` line 132-138.                                                                   |
| 6   | 9 tests in test_hgt_publisher.py                                                                                 | (from CORR-2 + CORR-4)                                                                                              | **8 tests** revised: keep 6 (confidence floor, fixture guard, PII detection, canonical 9-field xadd, skill_id namespace, None redis), add 1 (validate_domain crm), drop test 7.                                                         |
| 7   | `test_stubs.py` migration: 5 sync tests → 1 raises test                                                          | (from CORR-1)                                                                                                       | **Delete all 5 HGT sync tests** from test_stubs.py. No replacement (CrmHGTPublisher gone).                                                                                                                                              |
| 8   | `CONFIDENCE_FLOOR` module constant shadows `HGTPublisher.CONFIDENCE_THRESHOLD`                                   | DeepSeek F6 LOW                                                                                                     | **Read from `HGTPublisher.CONFIDENCE_THRESHOLD`** (public class attr line 31) to stay in sync.                                                                                                                                          |

## Empirical state post A.0 merge (2026-05-12 23:25 WITA — re-verified)

| Item                                                           | Verified                                                                                                                                                                                | Status                                      |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `HGTPublisher.cell_name` public property                       | ✅ visible on main `6e92046d8` lines 38-49                                                                                                                                              | Ready for `CrmHGTBridge.__init__`           |
| `cell_core.hgt.domains.CANONICAL_DOMAINS` contains `"crm"`     | ✅ **line 18 verified** (added commit `09aadbdc5` 2026-04-16 Sprint parallel RAG SOTA + Metabolic + HGT #57, predates Phase 3 v2 by 26 days)                                            | NO need to register — domain pre-existing   |
| `apps/crm-cell/crm_cell/hgt_publisher.py:79` stub              | ✅ still `# Sprint 4: call into self._hgt_stream.xadd(...)`                                                                                                                             | TICKET A.1 target                           |
| `HGTPublisher.publish()` xadd fields                           | ✅ verified lines 56-67: 9 explicit keys (`skill_id, cell_origin, procedure, precondition, success_criterion, confidence, type, scope, domain`). `_metadata` would be silently DROPPED. | Inform schema design                        |
| `apps/crm-cell/tests/test_stubs.py:98-141`                     | ✅ 5 sync tests on CrmHGTPublisher                                                                                                                                                      | DELETE                                      |
| `apps/crm-cell/crm_cell/__init__.py` exports `CrmHGTPublisher` | ✅ confirmed                                                                                                                                                                            | Replace with `CrmHGTBridge` only            |
| `apps/evaluator/seo_cell/` uses of `validate_domain` or `hgt`  | ✅ **ZERO grep matches**                                                                                                                                                                | SEO regression = NO-OP (REJECT DeepSeek F3) |
| CrmHGTPublisher production callers                             | ✅ only `tests/test_stubs.py` + `crm_cell/__init__.py` (re-export) + self                                                                                                               | ZERO blast radius for DELETE                |
| `redis-cli XLEN cell:skills`                                   | ✅ 18 (Phase 2.5 seed)                                                                                                                                                                  | Unchanged target post-A.1                   |

## False positive findings (REJECTED)

### DeepSeek F1 — "pytest.raises won't catch DeprecationWarning"

**EMPIRICAL DISPROOF** (Python REPL 2026-05-12 23:28 WITA):

```python
>>> issubclass(DeprecationWarning, Exception)
True
>>> issubclass(DeprecationWarning, BaseException)
True
>>> with pytest.raises(DeprecationWarning, match='test'): C()
# CAUGHT successfully
```

**DeepSeek's BaseException-only claim is hallucination.** Moot anyway since CORR-1 deletes `CrmHGTPublisher` (no DeprecationWarning needed).

### DeepSeek F2 — "crm not in CANONICAL_DOMAINS"

**EMPIRICAL DISPROOF**: `grep -n '"crm"' packages/cell-core/cell_core/hgt/domains.py` → **line 18**. `git log` shows commit `09aadbdc5` (2026-04-16) added it as part of Sprint parallel HGT — predates Phase 3 v2 spec by 26 days. **Phase 3 v2 Discovery 3 was OUTDATED, not the narrow spec.**

DeepSeek had no file access — couldn't run grep — so flagged on text-only evidence. Rejected.

## Implementation (CORR-1..8 applied)

### File 1: `apps/crm-cell/crm_cell/hgt_publisher.py` (full rewrite)

```python
"""HGT bridge for crm-cell — broadcasts STRUCTURAL patterns only.

Phase 3 TICKET A.1 — replaces Sprint 3 W2 sync stub (DELETED) with async
``CrmHGTBridge`` wrapping the canonical ``cell_core.hgt.publisher.HGTPublisher``.

UU PDP discipline: client PII NEVER appears in HGT broadcasts. Only
structural insights — "Brevo template T123 bounces 80%+ for client
segment X" — that other cells can act on without seeing client data.

Confidence floor: read from HGTPublisher.CONFIDENCE_THRESHOLD (0.7).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from cell_core.hgt.domains import validate_domain
from cell_core.hgt.publisher import HGTPublisher

logger = logging.getLogger("crm_cell.hgt_publisher")


@dataclass(frozen=True)
class StructuralPattern:
    """A structural CRM discovery suitable for HGT broadcast.

    Canonical 6-field shape (Phase 3 TICKET A.1 v2 — mirrors
    IntelScraperHGTBridge schema). Maps directly to HGTPublisher's
    9 xadd fields (with cell_origin + scope + type filled by bridge).

    Client PII NEVER appears in any string field. Use structural
    identifiers (template_id, segment_id, time_window) instead.
    """

    pattern_id: str           # e.g. "brevo_template_T123_bounce_rate"
    procedure: str            # human-readable: what the pattern says
    precondition: str         # when this pattern applies
    success_criterion: str    # how to know it still holds
    confidence: float
    domain: str = "crm"       # default for crm-cell origin


class CrmHGTBridge:
    """CRM-cell HGT bridge — mirrors IntelScraperHGTBridge.

    Filters (defense-in-depth, in addition to HGTPublisher's confidence
    + scope=Project + type≠scar gate):
    - Reject patterns whose strings (procedure/precondition/success_criterion)
      contain PII markers (defensive — caller is supposed to never pass PII).
    - Reject confidence == 1.0 (fixture pollution guard).

    No try/except around HGTPublisher.publish — that class catches all
    Exception in its own xadd block (line 75-77). Bridge stays simple.
    """

    _PII_MARKERS = (
        "email", "@", "+62", "nik:", "npwp:", "passport",
        "client_id", "kitas_no", "ktp:",
    )

    def __init__(self, publisher: HGTPublisher) -> None:
        self._publisher = publisher
        # TICKET A.0 (PR #626) — public property, no protected access.
        self._cell_origin = publisher.cell_name

    @classmethod
    def from_redis(
        cls,
        redis_client: Any | None,
        cell_name: str = "crm-cell",
        maxlen: int = 1000,
    ) -> "CrmHGTBridge":
        """Build a bridge from a redis client (or None for a no-op).

        When redis_client is None, HGTPublisher returns False immediately
        on every publish call — pattern stays in local genome, no error.
        """
        publisher = HGTPublisher(
            redis_client=redis_client,
            cell_name=cell_name,
            maxlen=maxlen,
        )
        return cls(publisher=publisher)

    def _is_pii_clean(self, pattern: StructuralPattern) -> bool:
        """True if procedure/precondition/success_criterion contain no PII markers."""
        haystack = " ".join((
            pattern.procedure or "",
            pattern.precondition or "",
            pattern.success_criterion or "",
        )).lower()
        return not any(m in haystack for m in self._PII_MARKERS)

    async def publish(self, pattern: StructuralPattern) -> bool:
        """Publish one structural pattern. Returns True iff broadcast.

        Filter order: cell-side filters FIRST, then HGTPublisher's
        threshold checks (which include confidence floor + scope=Project
        + type≠scar gates).
        """
        if pattern.confidence < HGTPublisher.CONFIDENCE_THRESHOLD:
            logger.debug(
                "hgt: pattern %s below floor %s (got %s) — discarded",
                pattern.pattern_id,
                HGTPublisher.CONFIDENCE_THRESHOLD,
                pattern.confidence,
            )
            return False
        if pattern.confidence == 1.0:
            logger.info(
                "hgt: pattern %s filtered (confidence=1.0 fixture guard)",
                pattern.pattern_id,
            )
            return False
        if not self._is_pii_clean(pattern):
            logger.warning(
                "hgt: pattern %s blocked — string fields contain PII markers",
                pattern.pattern_id,
            )
            return False

        skill = {
            "id": f"crm.pattern.{pattern.pattern_id}",
            "cell_origin": self._cell_origin,
            "procedure": pattern.procedure,
            "precondition": pattern.precondition,
            "success_criterion": pattern.success_criterion,
            "confidence": float(pattern.confidence),
            "scope": "Project",
            "type": "skill",
            "domain": validate_domain(pattern.domain),
        }
        published = await self._publisher.publish(skill)
        logger.info(
            "hgt: pattern %s published=%s confidence=%.2f domain=%s",
            pattern.pattern_id, published, pattern.confidence, skill["domain"],
        )
        return published


__all__ = [
    "StructuralPattern",
    "CrmHGTBridge",
]
```

### File 2: `apps/crm-cell/crm_cell/__init__.py` (update exports)

```python
# Replace existing:
#   from .hgt_publisher import CrmHGTPublisher, ...
# With:
from .hgt_publisher import CrmHGTBridge, StructuralPattern
```

Remove `CrmHGTPublisher` and `CONFIDENCE_FLOOR` (module constant) from public exports.

### File 3: `apps/crm-cell/tests/test_hgt_publisher.py` (NEW, 8 tests)

```python
"""Phase 3 TICKET A.1 — CrmHGTBridge async tests.

Replaces sync-stub tests in test_stubs.py (deleted per 4-panel review CORR-7).
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from crm_cell.hgt_publisher import CrmHGTBridge, StructuralPattern
from cell_core.hgt.publisher import HGTPublisher


def _make_pattern(
    *,
    pattern_id: str = "brevo_template_T123_bounce_rate",
    procedure: str = "Brevo template T123 bounces ≥80% for segment X over last 30d",
    precondition: str = "client_segment X has ≥1000 active subscribers",
    success_criterion: str = "bounce rate stays ≥80% in next 7-day window",
    confidence: float = 0.85,
    domain: str = "crm",
) -> StructuralPattern:
    return StructuralPattern(
        pattern_id=pattern_id,
        procedure=procedure,
        precondition=precondition,
        success_criterion=success_criterion,
        confidence=confidence,
        domain=domain,
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value=b"1-0")
    return redis


@pytest.fixture
def bridge(mock_redis: AsyncMock) -> CrmHGTBridge:
    return CrmHGTBridge.from_redis(redis_client=mock_redis)


@pytest.mark.asyncio
async def test_publish_below_confidence_floor_returns_false(bridge: CrmHGTBridge) -> None:
    """Confidence < 0.7 filtered locally before reaching HGTPublisher."""
    assert await bridge.publish(_make_pattern(confidence=0.5)) is False


@pytest.mark.asyncio
async def test_publish_confidence_exactly_1_returns_false(bridge: CrmHGTBridge) -> None:
    """Fixture pollution guard — confidence=1.0 is almost always a test value."""
    assert await bridge.publish(_make_pattern(confidence=1.0)) is False


@pytest.mark.asyncio
async def test_publish_pii_marker_in_procedure_blocked(bridge: CrmHGTBridge) -> None:
    """PII detection on procedure string (email substring)."""
    pattern = _make_pattern(procedure="user contact email leaked in template")
    assert await bridge.publish(pattern) is False


@pytest.mark.asyncio
async def test_publish_pii_marker_in_precondition_blocked(bridge: CrmHGTBridge) -> None:
    """PII detection on precondition (NPWP)."""
    pattern = _make_pattern(precondition="client npwp: 12.345.678.9-012.000")
    assert await bridge.publish(pattern) is False


@pytest.mark.asyncio
async def test_publish_calls_xadd_with_canonical_schema(bridge: CrmHGTBridge, mock_redis: AsyncMock) -> None:
    """Verify 9-field canonical skill dict reaches xadd."""
    pattern = _make_pattern()
    result = await bridge.publish(pattern)
    assert result is True
    mock_redis.xadd.assert_called_once()
    _stream, fields = mock_redis.xadd.call_args[0]
    expected_keys = {
        "skill_id", "cell_origin", "procedure", "precondition",
        "success_criterion", "confidence", "type", "scope", "domain",
    }
    assert set(fields.keys()) == expected_keys, "xadd received wrong keys"
    assert fields["skill_id"] == "crm.pattern.brevo_template_T123_bounce_rate"
    assert fields["cell_origin"] == "crm-cell"
    assert fields["domain"] == "crm"
    assert fields["scope"] == "Project"
    assert fields["type"] == "skill"
    assert fields["confidence"] == "0.85"


@pytest.mark.asyncio
async def test_publish_skill_id_namespace(bridge: CrmHGTBridge, mock_redis: AsyncMock) -> None:
    """skill_id MUST be prefixed crm.pattern.<id>."""
    await bridge.publish(_make_pattern(pattern_id="anything_here"))
    _stream, fields = mock_redis.xadd.call_args[0]
    assert fields["skill_id"].startswith("crm.pattern.")


@pytest.mark.asyncio
async def test_publish_redis_none_returns_false() -> None:
    """from_redis(None) → HGTPublisher returns False on publish (no xadd attempt)."""
    bridge = CrmHGTBridge.from_redis(redis_client=None)
    assert await bridge.publish(_make_pattern()) is False


@pytest.mark.asyncio
async def test_bridge_cell_origin_via_public_property(mock_redis: AsyncMock) -> None:
    """TICKET A.0 contract: bridge reads publisher.cell_name (public)."""
    bridge = CrmHGTBridge.from_redis(redis_client=mock_redis, cell_name="custom-name")
    await bridge.publish(_make_pattern())
    _stream, fields = mock_redis.xadd.call_args[0]
    assert fields["cell_origin"] == "custom-name"
```

### File 4: `apps/crm-cell/tests/test_stubs.py` (delete 5 HGT tests)

Remove lines 98-141 (5 tests on `CrmHGTPublisher`). Also remove the import of `CrmHGTPublisher` from the top-of-file imports block (line 22-33). Replace with import of `CrmHGTBridge` if any non-HGT test needs it (none currently — leave the import removed).

Net change: `-5 tests, -1 import`. The remaining tests on CrmScarRecorder + CrmEventBridge + CELL_NAME/CELL_VERSION + FailureKind enum are untouched.

## Acceptance criteria

1. ✅ CI tests green: `pytest apps/crm-cell/tests/ -v` → all pass (test_hgt_publisher.py 8/8 + test_stubs.py with 5 fewer + others unchanged)
2. ✅ Regression: `pytest packages/cell-core/tests/hgt/ -v` → all 9+ tests pass (TICKET A.0 property unchanged)
3. ✅ Regression: `pytest apps/bali-intel-scraper/tests/unit/cell/test_hgt_publisher.py -v` → 8/8 pass (IntelScraperHGTBridge unaffected)
4. ✅ CI grep assertion: `grep -rln 'CrmHGTBridge.from_redis' apps/ --include='*.py' | grep -v 'tests/' | wc -l` returns 0 (A.2 not yet wired)
5. ✅ CI grep assertion: `grep -rln 'CrmHGTPublisher' apps/ --include='*.py' | wc -l` returns 0 (class deleted entirely)
6. ✅ `redis-cli -h 127.0.0.1 XLEN cell:skills` remains 18 (no live caller, no production publish)
7. ✅ `apps/evaluator/seo_cell/` test suite continues to pass post-A.1 — no-op verification (seo_cell has zero HGT touchpoints, empirical zero grep)

## Refusals (inherits Phase 3 spec v2 §14 refusals — all still apply)

Key reiterations:

- ❌ No production caller wiring (A.2 operator-gated)
- ❌ No direct `redis-cli XADD cell:skills`
- ❌ No edits to `packages/cell-core/cell_core/hgt/{publisher,consumer,coordinator,domains}.py` (TICKET A.0 already shipped, no further changes)
- ❌ No synchronous `asyncio.run` in HGT app code
- ❌ No edits to `apps/evaluator/seo_cell/`
- ❌ No deployment of TICKET C before TICKET B

## Effort revision

| Component                 | v1        | v2 (post-review)                                    |
| ------------------------- | --------- | --------------------------------------------------- |
| hgt_publisher.py rewrite  | 1d        | 1d (same scope, cleaner code via dead-code removal) |
| **init**.py update        | 5m        | 5m                                                  |
| test_hgt_publisher.py new | 2h        | 1.5h (8 tests stronger than v1's 9)                 |
| test_stubs.py migration   | 30m       | 15m (just delete 5 tests, no replacement)           |
| **Total A.1**             | **1 day** | **0.5-0.75 day**                                    |

4-panel review BLOCK ironically REDUCED effort by killing dead code (CrmHGTPublisher raise-stub, bridge try/except, 1 fragile test).

## Brainstorm artifacts archive plan

Archive to `docs/audits/2026-05-12-ticket-a1-spec-brainstorm/`:

- `00_briefing.md`
- `01_claude_self_critique.md` (5 findings)
- `02_gemini_review.md` (BLOCK, 4 findings F1 critical + F2-F4 medium-high)
- `03_deepseek_review.md` (BLOCK, but 2/6 findings empirically FALSE POSITIVE — flagged in synthesis)
- `04_nb1_review.md` (BLOCK, Q3.2 partially TRUE — silent drop not crash)
- `05_synthesis.md` (with empirical disproof table)

## Sources

1. `apps/crm-cell/crm_cell/hgt_publisher.py:1-89` (full file pre-rewrite)
2. `apps/crm-cell/tests/test_stubs.py:98-141` (5 HGT sync tests to delete)
3. `packages/cell-core/cell_core/hgt/publisher.py:38-49` (cell_name public property post-A.0)
4. `packages/cell-core/cell_core/hgt/publisher.py:53-77` (publish lines — empirical \_metadata silent drop verified)
5. `packages/cell-core/cell_core/hgt/domains.py:18` (`"crm"` line 18 — empirical grep)
6. `git log --oneline -- domains.py` shows commit `09aadbdc5` added "crm" 2026-04-16
7. `apps/evaluator/seo_cell/` grep zero `validate_domain|hgt\.` matches
8. `apps/bali-intel-scraper/backend/cell/hgt_publisher.py:33-72` (IntelScraperHGTBridge canonical reference pattern)
9. `redis-cli -h 127.0.0.1 XLEN cell:skills` → 18 (seed unchanged post-A.0)
10. Phase 3 spec v2: `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
11. TICKET A.0 merge commit `6e92046d8` (PR #626) at 2026-05-12T15:19:56Z
12. 4-panel review artifacts: `/tmp/symbiosis-ticket-a1-review-2026-05-12/{00..05}_*.md` + `docs/audits/2026-05-12-ticket-a1-spec-brainstorm/`
