# Phase 3 — HGT FASE 4 Execution Spec (v2 — post 4-panel review)

**Date**: 2026-05-12 21:30 WITA · **Revised**: 21:45 WITA post-review
**Author**: Antonello (Zero) via Claude Opus 4.7 max
**Predecessor**: Phase 2 Core Plumbing complete (PR #620 merged; events_outbox drained 3 unconsumed, cell:skills seed 18, sentinel-1 consumer-group ready)
**Mode**: Spec doc only — execution scope deferred to operator-approval per ticket
**Estimated effort**: ~5 days code + 14-day soak + 0.5 day FASE 4 lift (revised from 7-day in v1)
**Review status**: APPROVED with 11 corrections — Claude self PROCEED WITH CONDITIONS + Gemini 3.1 Pro PROCEED WITH CONDITIONS + DeepSeek Reasoner PROCEED WITH CONDITIONS + NB-1 BLOCK (invalid, snapshot 2026-03-23 missed apps created Apr-May 2026 — see §"Hidden coupling notes")

## Goal

Lift the HGT HALT (commit `68efc17e3` 2026-05-08) by closing the 3 prerequisite tickets that gate FASE 4 activation. After Phase 3 completes, `cell:skills` Redis stream is fed by ≥2 production publishers AND consumed by the sentinel cell PulseLoop with `pending=0`, allowing the existing `packages/cell-core/cell_core/hgt_coordinator/` quarantine mechanism to graduate verified-good skills from propose-only to applied.

This spec is a **superset** of the Gap 3 empirical spec (`research/symbiosis/2026-05-12-gap3-hgt-3tickets-empirical-spec.md`, this morning 15:35 WITA), refined with empirical re-verification 2026-05-12 21:00 WITA and 6 cross-file discoveries from reading the actual sources, then revised post 4-panel review with 11 corrections.

## 4-panel review convergences applied (11 corrections)

| #   | Original spec v1                                                                                           | 4-panel verdict                                                  | Correction in v2                                                                                                                                                                                                                      |
| --- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Sync shim `CrmHGTPublisher.publish()` calls `asyncio.run()` (silent False inside running loop)             | UNANIMOUS critical (Claude/DeepSeek/Gemini) — major runtime risk | **REMOVE sync shim**. `CrmHGTPublisher` class raises `DeprecationWarning` in `__init__`. Migrate `test_stubs.py` to async fixture.                                                                                                    |
| 2   | TICKET B `_make_cell_runner()` default `redis://localhost:6379` not verified against Mini split-brain scar | Claude+DeepSeek HIGH                                             | **Preflight check**: connect to Redis, verify `XLEN cell:skills ≥18` (Phase 2.5 seed signature); abort if signature wrong. Document explicit invariant: cell:skills lives on **Pro localhost** (empirically verified Pro=18, Mini=0). |
| 3   | Acceptance: "XLEN ≥28 in 7 days" not empirically calibrated                                                | Claude+DeepSeek MEDIUM                                           | **Soak revised**: primary criterion "≥3 nights with positive delta in 14 days" + secondary "XLEN ≥23 total" (lowers bar to ~0.36/night, robust to empty nights).                                                                      |
| 4   | Refusals list 8 items, missing several                                                                     | Claude+DeepSeek MEDIUM                                           | **14 refusals** (added #9-#14: cell-core edits, intel.nightly plist, direct XADD, sequencing C-before-B, no Synchronous asyncio.run, seo_cell edits, monorepo path).                                                                  |
| 5   | Option A architecture decision (γ Bridge) lacks trade-off table                                            | Claude meta                                                      | **4-row decision table** A.α/β/γ/δ added (γ recommended with rationale).                                                                                                                                                              |
| 6   | TICKET C plist edit workflow missing chmod 0444 restore                                                    | Claude LOW                                                       | **4-step operator workflow** explicit (chmod u+w → plutil-replace → plutil-lint → chmod 0444 → bootout/bootstrap).                                                                                                                    |
| 7   | SEO cell impact not addressed                                                                              | NB-1 useful signal                                               | **Hidden coupling**: SEO cell regression-test required when "crm" added to `validate_domain`.                                                                                                                                         |
| 8   | TICKET B 3-night dry-run requirement is excessive IF fallback in place                                     | Gemini Q1.3 architectural                                        | **Mandate try/except fallback to legacy** in `_make_cell_runner()`. With fallback, drop 3-night dry-run. Deploy direct to production.                                                                                                 |
| 9   | `run_sentinel_cell.py` uses `asyncio.all_tasks()` blanket wait — anti-pattern                              | Gemini F3 MEDIUM                                                 | **Replace `all_tasks()` blanket wait** with explicit task tracking via `asyncio.TaskGroup` OR remove wait entirely if observatory library manages own shutdown.                                                                       |
| 10  | `cell_name` private attribute access in CrmHGTBridge                                                       | Gemini F4 LOW (was Claude DEFER)                                 | **UPGRADE to inline TICKET A.0**: add `HGTPublisher.cell_name` public property (5min mechanical). Both bridges use public attribute.                                                                                                  |
| 11  | TICKET B effort estimate based on 3-night dry-run                                                          | derived from #8                                                  | TICKET B effort: 1 day implementation + production direct deploy (no separate dry-run phase).                                                                                                                                         |

## Prerequisites (from Phase 2 closure, unchanged)

1. **Phase 2 complete** — ✅ `events_outbox` unconsumed=3, DLQ=5 understood, cell:skills XLEN=18, sentinel-1 consumer-group ready
2. **Plists EMIT-enabled** — ✅ 4 plists (seo-cell.daily, seo-cell.28d-check, sentinel.hourly, cell.organism)
3. **Operator-gate active** — operator-approval required for items in §"Refusals"

## Empirical state at spec v2 time (2026-05-12 21:30 WITA)

| Premise                                                                                              | Cited line                           | Re-verified 21:00-21:30                                                                   |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------- |
| `apps/crm-cell/crm_cell/hgt_publisher.py:79` stub `# Sprint 4: call into self._hgt_stream.xadd(...)` | line 79                              | ✅ still stub                                                                             |
| `apps/crm-cell/crm_cell/hgt_publisher.py` no production caller                                       | grep                                 | ✅ only `__init__.py` (re-export) + `tests/test_stubs.py`                                 |
| `apps/bali-intel-scraper/backend/cell/runner.py:175` `IntelScraperCellRunner` class                  | line 175                             | ✅ class defined, async context manager shape                                             |
| `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` import IntelScraperCellRunner                | grep                                 | ✅ zero matches                                                                           |
| `apps/mata-garuda/scripts/run_sentinel_py.py:120-135` legacy bypass                                  | line 120-135                         | ✅ confirmed (Normalizer → Scorer → NLM Feeder → Digest, no PulseLoop)                    |
| `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:46` `create_sentinel_cell()` PulseLoop factory  | line 46                              | ✅ **verified empirically** via `grep -n "def create_sentinel_cell"`, exact match line 46 |
| `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:25,91,95,167-170` HGTConsumer wiring            | lines 25/91/95/167-170               | ✅ confirmed                                                                              |
| `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist` invokes `run_sentinel_py.py`           | plist content                        | ✅ confirmed                                                                              |
| `~/Library/LaunchAgents/com.balizero.intel.nightly.plist` REDIS_URL env var                          | plutil -extract EnvironmentVariables | ✅ **NOT SET** (only HOME + PATH) — default localhost will apply                          |
| `redis-cli -h 127.0.0.1 XLEN cell:skills`                                                            | command                              | ✅ **18** (Pro localhost, Phase 2.5 seed canonical)                                       |
| `redis-cli -h 100.93.236.6 XLEN cell:skills`                                                         | command                              | ✅ **0** (Mini Redis empty — Mini is NOT the cell:skills owner)                           |
| `redis-cli XINFO GROUPS cell:skills` sentinel-1                                                      | command                              | ✅ exists, 0 consumers, lag=18, pending=0, last-delivered-id=0-0 (NEVER consumed)         |
| `packages/cell-core/cell_core/hgt_coordinator/` directory                                            | find                                 | ✅ **EXISTS** (corrected from v1 wrong path `apps/cell-core/hgt_coordinator/`)            |
| HGT kill-switch state                                                                                | commit `68efc17e3`                   | ✅ HALTED draft, no production changes shipped                                            |

All 3 HGT HALT premises **still valid 13 hours later**. Spec is empirically anchored. Critical addition: cell:skills lives on Pro localhost (NOT Mini), and `hgt_coordinator/` is in `packages/cell-core/`, not `apps/`.

## Cross-file discoveries

These 6 findings emerged from reading the actual source code and refine TICKET A's scope:

### Discovery 1 — CrmHGTPublisher.publish() is SYNC, IntelScraperHGTBridge.publish() is ASYNC

`apps/crm-cell/crm_cell/hgt_publisher.py:56` `def publish(self, pattern: StructuralPattern) -> bool:` (sync)
`apps/bali-intel-scraper/backend/cell/hgt_publisher.py:140` `async def publish(self, pattern: StructuralPattern) -> bool:` (async)

**Implication for TICKET A.1**: schema-divergence demands resolution. **TICKET A.1 makes `CrmHGTBridge.publish()` async** to match the canonical `cell_core.hgt.publisher.HGTPublisher` pattern. The legacy `CrmHGTPublisher` class is **removed** (DeprecationWarning on construction).

### Discovery 2 — CrmHGTPublisher StructuralPattern schema does NOT match cell_core.hgt schema

`apps/crm-cell/crm_cell/hgt_publisher.py:30-40` `StructuralPattern(pattern_kind, confidence, payload)`
vs.
`apps/bali-intel-scraper/backend/cell/hgt_publisher.py:33-72` `StructuralPattern(pattern_id, source, procedure, precondition, success_criterion, confidence, domain, metadata) + to_skill_dict()` returning the canonical 9-field shape that `cell_core.hgt.publisher.HGTPublisher.publish()` accepts.

**Implication for TICKET A.1**: 4 options considered.

#### Option A decision table (CORR-5)

| Option | Description                                                                                                                                                                      | Pros                                                                                                       | Cons                                                                                        | Verdict             |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------- |
| A.α    | Extend `CrmHGTPublisher.publish()` sync method to translate legacy → canonical 9-field inline before `xadd`                                                                      | Minimal code change. Keeps StructuralPattern shape.                                                        | Sync xadd is wrong (redis.asyncio is the canonical client). Schema-divergence persists.     | REJECTED            |
| A.β    | Refactor crm_cell `StructuralPattern` to mirror intel-scraper-cell shape verbatim (pattern_id, source, procedure, precondition, success_criterion, confidence, domain, metadata) | Highest fidelity. No translation layer.                                                                    | Breaks all existing test fixtures using old shape. Higher cognitive load (why same shape?). | REJECTED            |
| A.γ    | **Bridge `CrmHGTBridge` wrapping canonical `HGTPublisher`** — accepts legacy `StructuralPattern`, translates to 9-field skill dict internally                                    | Mirrors intel-scraper-cell exactly. Schema translation localized to one class. Backwards-compat for tests. | Translation logic must be maintained. Code smell (private attr access) until A.0 ships.     | **RECOMMENDED** ✅  |
| A.δ    | Unified `BaseHGTBridge` in `packages/cell-core/` consumed by both crm-cell and intel-scraper-cell                                                                                | Eliminates duplication of bridge logic.                                                                    | Requires refactor of intel-scraper-cell (out of TICKET A scope). Phase 4 candidate.         | DEFERRED to Phase 4 |

### Discovery 3 — `crm` domain not registered in cell_core.hgt.domains

`apps/bali-intel-scraper/backend/cell/hgt_publisher.py:27` `from cell_core.hgt.domains import validate_domain` (canonical)
`intel-scraper-cell` uses `domain="news"`.
`crm_cell` would need `domain="crm"`.

**Implication for TICKET A.1**: small additive PR to `packages/cell-core/cell_core/hgt/domains.py` to register `"crm"` as a valid domain. ~5 LOC. **Whitelist extension only — NOT replacement** (SEO cell regression risk, per NB-1 useful signal).

### Discovery 4 — sentinel_cell.py ALREADY wires HGTConsumer

`apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:25` imports `HGTConsumer`
Line 46: `def create_sentinel_cell() -> PulseLoop:` factory
Lines 91/95: `hgt_consumer = HGTConsumer(redis_client=..., stream_name="cell:skills", consumer_group="sentinel-1", consumer_name="sentinel-1-consumer-1")`
Lines 126/136/141: passed into the cell factory
Lines 167-170: in `.tick()` reflect phase, calls `await self.hgt_consumer.ensure_group() + await self.hgt_consumer.consume_once()`

**Implication for TICKET C**: the consumer side is **already wired in the cell layer**. The bypass is ONLY at the script-entry layer (`run_sentinel_py.py` doesn't drive `create_sentinel_cell().tick()`). Switching the plist target from `run_sentinel_py.py` to a new `run_sentinel_cell.py` (Option C.1) fixes both Layer A (plist) and Layer B (script) in one shim.

### Discovery 5 — IntelScraperHGTBridge accesses HGTPublisher private attribute (RESOLVED in spec v2 via TICKET A.0)

`apps/bali-intel-scraper/backend/cell/hgt_publisher.py:110` `self._cell_origin = publisher._cell_name  # type: ignore[attr-defined]`

**Implication v2**: spec v1 deferred this; spec v2 promotes it to **TICKET A.0 — inline 5min change**:

1. Add `@property def cell_name(self) -> str: return self._cell_name` to `packages/cell-core/cell_core/hgt/publisher.py`
2. Update `IntelScraperHGTBridge.__init__` line 110 from `publisher._cell_name` to `publisher.cell_name`
3. New `CrmHGTBridge` uses `publisher.cell_name` directly (no protected attr)

### Discovery 6 — TICKET A production caller is the actual hard problem

The empirical Gap 3 spec frames TICKET A as "implement xadd + caller". The implementation half is mechanical. The **caller** is the question: where in the CRM flow does a `StructuralPattern` naturally arise?

Candidates surveyed from `apps/backend-rag/backend/services/crm/`:

- **CRM bulk import script post `lkpm_ingest_completed`**: extract patterns like "Brevo template T123 bounces 80%+ for client segment X". Plausible, but requires a long observation window (≥30 days bounce data) before patterns are confident.
- **Practice transition events**: when a practice moves from stage N to N+1, count cycle times across all practices → pattern "stage X→Y average 4.2 days for visa-c1, 7.8 days for visa-e28a". Quick to implement, low-confidence early.
- **CRM activity aggregator on `client_changed` event**: derive patterns from communication frequency, response rates. Same long-window caveat.

**NB-1 architectural caveat (useful signal)**: NB-1 warned (despite stale snapshot) that putting an HGT publisher caller in FastAPI/RAG service code mixes API layer with cell layer. The signal is valid: **prefer caller co-located with crm-cell** (e.g., a background task in `apps/crm-cell/crm_cell/` or a separate poller) rather than embedded in `apps/backend-rag/backend/services/crm/`.

**Recommendation**: defer caller decision to TICKET A.2 sub-ticket, after the publisher infrastructure is in place. TICKET A.2 (caller integration) is a separate PR with operator-driven scope.

## The 3 tickets (refined v2)

### TICKET A.0 — Expose `cell_name` as public property on HGTPublisher (15 min, P0 — NEW)

**Files**:

- `packages/cell-core/cell_core/hgt/publisher.py` — add property
- `apps/bali-intel-scraper/backend/cell/hgt_publisher.py:110` — switch to public attr

```python
# packages/cell-core/cell_core/hgt/publisher.py — add after __init__
class HGTPublisher:
    # ... existing ...
    @property
    def cell_name(self) -> str:
        """Public read-only access to the cell name."""
        return self._cell_name
```

```python
# apps/bali-intel-scraper/backend/cell/hgt_publisher.py:110 — change
self._cell_origin = publisher.cell_name  # WAS: publisher._cell_name (type: ignore)
```

**Tests**: extend existing `packages/cell-core/tests/hgt/test_publisher.py` with 1 test asserting `cell_name` public property returns correct value.

**Acceptance**: CI tests green. No behavioral change. Existing intel-scraper-cell tests still pass.

**Effort**: 15 minutes. Ship as standalone PR or first commit in TICKET A.1 branch.

### TICKET A.1 — CrmHGTBridge async publisher infrastructure (1 day, P0)

**Files modified**:

- `apps/crm-cell/crm_cell/hgt_publisher.py` (full rewrite)
- `apps/crm-cell/crm_cell/__init__.py` (export `CrmHGTBridge.from_redis` factory)
- `apps/crm-cell/tests/test_hgt_publisher.py` (new — 9 tests)
- `apps/crm-cell/tests/test_stubs.py` (migrate to async — see below)
- `packages/cell-core/cell_core/hgt/domains.py` (add `"crm"` to whitelist ~5 LOC)
- `packages/cell-core/tests/hgt/test_domains.py` (extend with crm test ~5 LOC)

**Code change** (Option A.γ — Bridge wrapping canonical HGTPublisher, NO SYNC SHIM):

```python
# apps/crm-cell/crm_cell/hgt_publisher.py — v2 rewrite
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from cell_core.hgt.domains import validate_domain
from cell_core.hgt.publisher import HGTPublisher

logger = logging.getLogger("crm_cell.hgt_publisher")

CONFIDENCE_FLOOR: float = 0.7


@dataclass(frozen=True)
class StructuralPattern:
    """Backwards-compatible legacy shape for crm-cell.

    The bridge translates to the canonical cell_core schema internally.
    Kept identical to the Sprint 3 W2 shape so any test fixtures keep working.
    """
    pattern_kind: str
    confidence: float
    payload: dict


class CrmHGTBridge:
    """CRM-cell HGT bridge — mirrors IntelScraperHGTBridge.

    Filters (defense-in-depth, in addition to HGTPublisher's confidence ≥0.7
    + scope=Project gate):
    - Reject patterns whose payload keys mention PII (forbidden_keys set).
    - Reject confidence == 1.0 (fixture pollution guard).
    """

    _FORBIDDEN_PAYLOAD_KEYS = frozenset({
        "client_id", "email", "name", "surname", "phone",
        "npwp", "nib", "passport", "kitas_no", "ktp",
    })

    def __init__(self, publisher: HGTPublisher) -> None:
        self._publisher = publisher
        # Public attribute (TICKET A.0) — no protected access needed.
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

    @staticmethod
    def _is_pii_clean(payload: dict) -> bool:
        return not (set(payload.keys()) & CrmHGTBridge._FORBIDDEN_PAYLOAD_KEYS)

    async def publish(self, pattern: StructuralPattern) -> bool:
        """Publish one structural pattern. Returns True iff broadcast.

        Translates the legacy shape to the canonical 9-field skill dict.
        Confidence floor + PII check applied BEFORE translation.
        """
        if pattern.confidence < CONFIDENCE_FLOOR:
            logger.debug(
                "hgt: pattern %s below floor %s (got %s) — discarded",
                pattern.pattern_kind, CONFIDENCE_FLOOR, pattern.confidence,
            )
            return False
        if pattern.confidence == 1.0:
            logger.info(
                "hgt: pattern %s filtered (confidence=1.0 fixture guard)",
                pattern.pattern_kind,
            )
            return False
        if not self._is_pii_clean(pattern.payload):
            logger.warning(
                "hgt: pattern %s blocked — payload contains PII tokens",
                pattern.pattern_kind,
            )
            return False

        skill = {
            "id": f"crm.pattern.{pattern.pattern_kind}",
            "cell_origin": self._cell_origin,
            "procedure": (
                # NOT free-form description — structural summary keyed off payload.
                f"{pattern.pattern_kind}: " + ", ".join(
                    f"{k}={v}" for k, v in sorted(pattern.payload.items())
                    if k not in self._FORBIDDEN_PAYLOAD_KEYS
                )
            ),
            "precondition": "crm activity stream actively populated",
            "success_criterion": f"pattern {pattern.pattern_kind} replicates "
                                  "in next 7-day observation window",
            "confidence": float(pattern.confidence),
            "scope": "Project",
            "type": "skill",
            "domain": validate_domain("crm"),
            "_metadata": {"legacy_payload": pattern.payload},
        }
        try:
            published = await self._publisher.publish(skill)
            logger.info(
                "hgt: pattern %s published=%s confidence=%.2f",
                pattern.pattern_kind, published, pattern.confidence,
            )
            return published
        except Exception as exc:
            logger.warning(
                "hgt: publish failed (non-blocking): %s", exc,
            )
            return False


class CrmHGTPublisher:
    """REMOVED in spec v2. This class only exists to raise on construction.

    The Sprint 3 W2 sync stub was determined to be unsafe inside running
    event loops (unanimous 4-panel review verdict 2026-05-12).
    Production callers MUST use ``CrmHGTBridge.from_redis(...).publish(...)``
    (async).
    """

    def __init__(self, *args, **kwargs) -> None:
        raise DeprecationWarning(
            "CrmHGTPublisher is removed in Phase 3 (see "
            "docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md "
            "§ TICKET A.1). Use CrmHGTBridge.from_redis(redis_client).publish(...) "
            "directly. Async only."
        )


__all__ = [
    "StructuralPattern",
    "CrmHGTBridge",
    "CrmHGTPublisher",  # raises on construction — for migration discoverability
    "CONFIDENCE_FLOOR",
]
```

**Migration of `test_stubs.py`** (CORR-1 mandates this):

```python
# apps/crm-cell/tests/test_stubs.py — migrated to async
import pytest
from unittest.mock import AsyncMock, MagicMock
from crm_cell.hgt_publisher import (
    StructuralPattern, CrmHGTBridge, CrmHGTPublisher, CONFIDENCE_FLOOR,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    """In-memory mock for redis.asyncio.Redis."""
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value=b"1-0")
    return redis


@pytest.fixture
def bridge(mock_redis) -> CrmHGTBridge:
    return CrmHGTBridge.from_redis(redis_client=mock_redis)


def test_legacy_publisher_construction_raises():
    """CrmHGTPublisher class is gone; constructing it must raise."""
    with pytest.raises(DeprecationWarning, match="CrmHGTBridge"):
        CrmHGTPublisher()


@pytest.mark.asyncio
async def test_bridge_below_confidence_floor_returns_false(bridge):
    pattern = StructuralPattern(
        pattern_kind="test_low_conf", confidence=0.5, payload={"k": "v"},
    )
    assert await bridge.publish(pattern) is False


# ... rest of existing test_stubs.py migrated similarly
```

**Test scope** (`apps/crm-cell/tests/test_hgt_publisher.py` — new, 9 tests):

1. `test_publish_below_confidence_floor_returns_false` — confidence 0.5 → False
2. `test_publish_confidence_1_returns_false` — confidence 1.0 → False (fixture guard)
3. `test_publish_pii_payload_blocked` — payload with `client_id` → False
4. `test_publish_calls_xadd_with_canonical_schema` — assert `_publisher.publish(skill)` called with all 9 canonical fields
5. `test_publish_skill_id_namespace` — assert `id` starts with `crm.pattern.<kind>`
6. `test_publish_redis_none_returns_false` — `from_redis(None)` → publish returns False without exception
7. `test_publish_xadd_exception_swallowed_returns_false` — mock `_publisher.publish` raise → returns False, logs warning
8. `test_bridge_cell_origin_via_public_property` — assert TICKET A.0 public property accessed (NOT `_cell_name`)
9. `test_publish_validate_domain_accepts_crm` — assert `validate_domain("crm")` returns `"crm"` (proves domain registration)

**Acceptance criteria A.1**:

1. CI tests green: `pytest apps/crm-cell/tests/ -v` → all pass
2. `validate_domain("crm")` returns `"crm"` (domain registration verified)
3. `pytest packages/cell-core/tests/hgt/test_domains.py -v` → green (SEO cell + other domains unaffected — additive only)
4. **CI assertion** (new): `grep -rln 'CrmHGTBridge.from_redis' apps/ --include='*.py' | grep -v 'tests/' | wc -l` returns 0 (no production caller wired yet — TICKET A.2 scope)
5. `redis-cli -h 127.0.0.1 XLEN cell:skills` remains 18 after A.1 merge (no live caller)

**Effort A.1**: 1 day (mechanical refactor + 9 tests + domain registration + test_stubs migration).

### TICKET A.2 — Production caller wiring (0.5 day, deferred to operator)

**Files** (caller integration — operator decides which):

| Option   | Location                                                                           | Pros                                        | Cons                                            | NB-1 verdict                  |
| -------- | ---------------------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------- | ----------------------------- |
| α        | `apps/backend-rag/backend/services/crm/practice_aggregator.py` (new)               | RAG-side has direct DB access               | Mixes API layer with cell layer                 | NB-1 caveat says NO           |
| β        | `apps/backend-rag/backend/services/crm/brevo_aggregator.py` (new)                  | Webhook-driven, event-based                 | Same NB-1 caveat                                | NB-1 caveat says NO           |
| γ        | Hook into `apps/backend-rag/backend/services/crm/lkpm_ingest_completed_handler.py` | Reuses existing event flow                  | Coupling — ingest handler shouldn't publish HGT | NB-1 caveat says NO           |
| **δ** ⭐ | **New background task in `apps/crm-cell/crm_cell/` itself**                        | Co-located with bridge, clean cell boundary | Requires new poller infrastructure              | NB-1 useful signal: PREFERRED |

**Recommendation**: defer A.2 to operator decision. NB-1 useful signal nudges toward Option δ (caller inside crm-cell, not backend-rag).

**Effort A.2**: 0.5 day code + operator decision time (architectural choice).

### TICKET B — Wire IntelScraperCellRunner into run_intel_pipeline.py (1 day, P0 — revised v2)

**Files modified**:

- `apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (add runner instantiation + integration block WITH FALLBACK)
- `apps/bali-intel-scraper/tests/integration/test_intel_pipeline_with_runner.py` (new — 5 tests)

**Code change v2** (CORR-2 preflight + CORR-8 mandatory try/except fallback):

```python
# In run_intel_pipeline.py main flow, after argparse + IntelPipeline init

# Imports added near top:
import logging
import os
from datetime import datetime, timezone

from backend.cell.runner import IntelScraperCellRunner
from backend.cell.event_bridge import IntelScraperEventBridge
from backend.cell.hgt_publisher import IntelScraperHGTBridge
from backend.cell.scar_recorder import IntelScraperScarRecorder
import redis.asyncio as redis_async

logger = logging.getLogger(__name__)


async def _make_cell_runner_with_preflight() -> IntelScraperCellRunner | None:
    """Assemble runner with Redis preflight check.

    Returns None if preflight fails — caller falls back to legacy pipeline.
    Per spec v2 CORR-2 + CORR-8: cell:skills MUST be on Pro localhost,
    verified via seed signature XLEN ≥18 (Phase 2.5 seed canonical).
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    try:
        redis_client = redis_async.from_url(redis_url, decode_responses=False)
        # Preflight: verify cell:skills exists with seed signature
        cell_skills_len = await redis_client.xlen("cell:skills")
        if cell_skills_len < 18:
            logger.error(
                "intel_scraper.preflight_failed cell_skills_len=%d expected_min=18 "
                "redis_url=%s — likely WRONG Redis instance. Aborting cell integration.",
                cell_skills_len, redis_url,
            )
            await redis_client.aclose()
            return None
        logger.info(
            "intel_scraper.preflight_ok cell_skills_len=%d redis_url=%s",
            cell_skills_len, redis_url,
        )

        hgt_bridge = IntelScraperHGTBridge.from_redis(
            redis_client=redis_client,
            cell_name="intel-scraper-cell",
            maxlen=1000,
        )
        scar_recorder = IntelScraperScarRecorder.from_genome_path(
            os.environ.get("GENOME_DB_PATH", "~/.intel_scraper/genome.db"),
        )
        event_bridge = IntelScraperEventBridge.from_pg_dsn(
            os.environ.get("DATABASE_URL"),  # asyncpg-compatible DSN
            channel="intel_event",
        )
        return IntelScraperCellRunner(
            scar_recorder=scar_recorder,
            hgt_bridge=hgt_bridge,
            event_bridge=event_bridge,
        )
    except Exception as exc:
        logger.error(
            "intel_scraper.cell_runner_assembly_failed err=%r — falling back to legacy",
            exc,
        )
        return None


# In IntelPipeline.run() main flow:
async def run_with_cell_fallback(self) -> None:
    """Phase 3 TICKET B entrypoint — try cell-aware path, fall back to legacy.

    Spec v2 CORR-8: fallback is MANDATORY (Gemini Q1.3 architectural). With
    fallback, dry-run is not required — production direct deploy is safe.
    """
    runner = await _make_cell_runner_with_preflight()
    if runner is None:
        logger.warning(
            "intel_scraper.cell_disabled reason=preflight_or_assembly — using legacy pipeline"
        )
        await self.run_legacy()  # pre-existing implementation
        return

    trace_id = f"intel-nightly-{datetime.now(timezone.utc).isoformat()}"
    try:
        async with runner.run(trace_id=trace_id) as session:
            for source in self.sources:
                session.note_source_attempted(source.name)
                try:
                    articles = await source.fetch()
                    session.note_articles_found(len(articles))
                    for pattern in await source.extract_patterns(articles):
                        await session.publish_pattern(pattern)
                except RateLimit as exc:
                    session.record_failure(source.name, FailureKind.RATE_LIMIT, str(exc))
                except Exception as exc:
                    session.record_failure(source.name, FailureKind.HTTP_5XX, repr(exc))
    except Exception as exc:
        logger.error(
            "intel_scraper.cell_run_failed err=%r — falling back to legacy",
            exc,
        )
        await self.run_legacy()
```

**Tests** (`apps/bali-intel-scraper/tests/integration/test_intel_pipeline_with_runner.py` — new, 5 tests):

1. `test_preflight_succeeds_with_seed_signature` — mock redis xlen returns 18, assert runner instantiated
2. `test_preflight_fails_with_wrong_signature` — mock redis xlen returns 0, assert runner is None + logs error
3. `test_pipeline_falls_back_to_legacy_on_preflight_fail` — assert `run_legacy()` called when preflight returns None
4. `test_pipeline_records_sources_when_cell_path_active` — mock 3 sources, assert `summary.sources_attempted == 3`
5. `test_pipeline_falls_back_to_legacy_on_cell_run_exception` — mock cell run raises mid-flow, assert legacy called

**Acceptance criteria B (v2)**:

1. `grep "IntelScraperCellRunner" apps/bali-intel-scraper/scripts/run_intel_pipeline.py` returns ≥1 match (regression test)
2. CI tests green (5/5 integration)
3. **NO separate dry-run phase** (CORR-8 — fallback makes it unnecessary). Deploy direct to production.
4. After 1st nightly run post-merge: observatory.db shows `cell_id='intel-scraper-cell'` pulse events. If zero events: investigate logs for preflight failure (legacy fallback path) — non-blocking, no Telegram alert in v1.
5. `redis-cli XLEN cell:skills` increment ≥1 in 7 days after B ships (proves publisher → consumer chain works for `IntelScraperHGTBridge`).

**Effort B v2**: 1 day implementation + 5 tests. **No dry-run** (saved 3 nights vs v1).

**Risk note v2**: production cron `com.balizero.intel.nightly` at 03:00 WITA — blast radius is BOUNDED by the mandatory fallback (CORR-8). Worst case: cell integration silently disabled, legacy pipeline continues. Best case: cell-aware path emits patterns. No catastrophic failure mode.

### TICKET C — Switch sentinel cron entry to PulseLoop-aware path (2 days, P0 — revised v2)

**Files modified**:

- `apps/mata-garuda/scripts/run_sentinel_cell.py` (new — shim wrapping `create_sentinel_cell()`)
- `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist` (point ProgramArguments to new script — OPERATOR-GATED)
- `apps/mata-garuda/tests/test_run_sentinel_cell.py` (new — 4 tests)
- `apps/mata-garuda/CLAUDE.md` (document new canonical entry)

**Code change v2** (CORR-9: NO `asyncio.all_tasks()` blanket wait):

```python
# apps/mata-garuda/scripts/run_sentinel_cell.py — v2 (no all_tasks anti-pattern)
"""Cell-core-aware sentinel runner. Drives the full PulseLoop via
create_sentinel_cell() instead of bypassing to legacy workers.

The legacy script run_sentinel_py.py is preserved for backward
compatibility (manual invocation, debug). This new script is the
canonical HGT-enabled path going forward.

Layer A (plist target) and Layer B (script bypass) are both fixed
by switching the plist to invoke this file.

Per spec v2 CORR-9: NO asyncio.all_tasks() blanket wait — redis-py
and httpx leave background daemon tasks running, which would block
the script for the full 10s timeout. Rely on observatory library's
own graceful shutdown via cell_core.observatory.shutdown() context
manager (if exposed) or explicit task tracking on the emit path.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from mata_garuda.cells.sentinel_cell import create_sentinel_cell

logger = logging.getLogger("mata_garuda.scripts.run_sentinel_cell")


async def main() -> int:
    cell = create_sentinel_cell()
    logger.info("sentinel: cell created, starting tick()")
    result = await cell.tick()  # full sense→think→act→reflect→dream→mature
    logger.info(
        "sentinel: tick complete health=%s",
        result.health_status,
    )

    # Per spec v2 CORR-9: rely on cell_core.observatory's own shutdown.
    # The cell's __aexit__ (if implemented) handles fire-and-forget tasks
    # via the bridge's context manager. NO blanket asyncio.all_tasks() wait.
    #
    # If empirical testing shows observatory pulses not landing in
    # observatory.db, escalate to TICKET C.2 (explicit task tracking via
    # asyncio.TaskGroup in cell_core.observatory itself).
    return 0 if result.health_status != "red" else 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    sys.exit(asyncio.run(main()))
```

**Plist modification** (CORR-6 — explicit 4-step operator workflow):

```bash
# Operator-driven workflow per spec v2 CORR-6 (plist corruption scar antibody preserved):

# 1. Unlock plist for edit (chmod 0444 scar antibody)
chmod u+w ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 2. Modify ProgramArguments (point to run_sentinel_cell.py)
plutil -replace ProgramArguments -json '[
  "/bin/bash",
  "-lc",
  "source ~/.nuzantara-secrets.env 2>/dev/null; /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/run_sentinel_cell.py"
]' ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 3. Sanity check via plutil-lint BEFORE re-locking
plutil -lint ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist
# Expected output: "OK"

# 4. Re-lock plist (CRITICAL — restores corruption antibody)
chmod 0444 ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 5. Reload in launchd
launchctl bootout gui/$(id -u)/com.matagaruda.sentinel.hourly
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist

# 6. Verify
launchctl print gui/$(id -u)/com.matagaruda.sentinel.hourly | grep "ProgramArguments" -A4
# Should show run_sentinel_cell.py
```

**Tests** (`apps/mata-garuda/tests/test_run_sentinel_cell.py` — new, 4 tests):

1. `test_main_returns_0_on_green_health` — mock `create_sentinel_cell()` returns cell whose `.tick()` produces `health_status="green"`, assert `main()` returns 0
2. `test_main_returns_1_on_red_health` — mock `.tick()` returns `health_status="red"`, assert `main()` returns 1
3. `test_main_returns_0_on_yellow_health` — assert yellow ≠ red triggers exit 0
4. `test_main_does_not_call_asyncio_all_tasks` — assert spec v2 CORR-9 contract: no `asyncio.all_tasks()` blanket wait in the script

**Acceptance criteria C (v2)**:

1. CI tests green (4/4)
2. `apps/mata-garuda/scripts/run_sentinel_cell.py` passes mypy if mata-garuda has mypy config; passes ruff lint
3. **Manual smoke test BEFORE plist switch** (operator runs):
   ```bash
   cd ~/Desktop/nuzantara/apps/mata-garuda && \
     .venv/bin/python -u scripts/run_sentinel_cell.py
   ```
   Expected: exit 0, log lines `sentinel: cell created` + `sentinel: tick complete health=<green|yellow>`, observatory.db gains 1 row with `cell_id='sentinel'`.
4. **Plist switch (operator)**: 6-step workflow from CORR-6 above.
5. After first scheduled hourly tick post-switch: `~/.cell-observatory/observatory.db` shows ≥1 row with `cell_id='sentinel'` AND `cell:skills` consumer-group sentinel-1 shows `pending=0` AND (if TICKET B has shipped first) `entries-read` increments.

**Effort C v2**: 2 days (1 day shim + tests + docs, 1 day staged manual smoke + plist switch operator window).

**Risk note v2**: same as v1 — switching plist target is operator action with chmod 0444 scar constraint. v2 adds explicit 6-step workflow to mitigate forgetting chmod 0444 restore.

## Sequencing — A.0 → A.1 → B → C → 14-day soak → FASE 4 lift

**Hard sequencing requirements**:

1. A.0 ships FIRST (5 min, smallest blast radius) — gives both bridges public `cell_name` property to use cleanly
2. A.1 ships SECOND (1 day) — CrmHGTBridge available, "crm" domain registered, test_stubs.py migrated
3. B ships THIRD (1 day, no dry-run) — intel-scraper-cell publishes to cell:skills via fallback-protected path
4. C ships LAST (2 days, OPERATOR plist switch) — sentinel consumes cell:skills via PulseLoop

**Why this order**:

- A.0 → A.1: A.0 is the cleanup A.1 depends on for clean code (no protected attr)
- A.1 → B: cell_core "crm" domain must be registered before crm-cell can publish (A.2 caller). Even though A.2 is deferred, A.1's registration is a prerequisite invariant.
- B → C: TICKET B publishes; TICKET C consumes. Shipping C first means sentinel-1 consumer-group reads zero new entries for the entire B development window — wasted cron cycles + confusing metrics + risk of misleading consumer-group state.

**14-day soak window** (revised from 7-day per CORR-3):

- Intel-scraper nightly cron runs once/day → 14 nights = 14 publish opportunities
- Primary criterion: "≥3 nights with positive delta in 14 days" (robust to empty nights)
- Secondary: "XLEN cell:skills ≥23 total" (5 new patterns minimum)
- Cell-observatory has rolling 90-day retention so 14-day window is fully observable
- Allows for 2 weekends + 1 holiday + normal day-to-day variance

## Total effort (revised v2)

| Sub-ticket                                           |                                        Effort | Risk                   | Operator-gated?                               |
| ---------------------------------------------------- | --------------------------------------------: | ---------------------- | --------------------------------------------- |
| A.0 — HGTPublisher.cell_name public property         |                                           15m | very low               | no (autonomous)                               |
| A.1 — CrmHGTBridge async + domain + test migration   |                                         1 day | low                    | no (autonomous)                               |
| A.2 — production caller wire                         |                                       0.5 day | medium                 | YES (operator picks α/β/γ/δ)                  |
| B — IntelScraperCellRunner wire + 5 tests + fallback |                                         1 day | low (fallback bounded) | partial (production cron — but bounded blast) |
| C — sentinel cell-aware entry + 4 tests              |                                        2 days | medium                 | YES (plist edit + 6-step workflow)            |
| Soak period (passive observation)                    |                                       14 days | low                    | no                                            |
| FASE 4 kill-switch lift                              |                                       0.5 day | low                    | YES (HGT HALT revoke)                         |
| **Total Phase 3**                                    | **~5 days code + 14-day soak + 0.5 day lift** | medium                 | partially operator-gated                      |

Save vs v1: dropped 3-night dry-run thanks to CORR-8 fallback mandate. Soak extended from 7 → 14 days for empirical calibration robustness.

## Success criteria (revised v2)

Phase 3 complete when ALL conditions hold over the 14-day soak window:

1. ✅ **EITHER** "≥3 nights with positive delta in cell:skills XLEN" **OR** "XLEN cell:skills ≥23 total" (CORR-3 — robust to empty nights)
2. ✅ `redis-cli XINFO GROUPS cell:skills` → sentinel-1 group with `pending=0` AND `entries-read > 0`
3. ✅ `~/.cell-observatory/observatory.db` shows `cell_id='sentinel'` rows hourly with no >2h gap (raised from 1h to allow brief outage tolerance)
4. ✅ HGT HALT (commit `68efc17e3`) revoked (commit message documents lift criteria met)
5. ✅ `packages/cell-core/cell_core/hgt_coordinator/` graduation log shows ≥1 skill moved from propose-only to applied (path corrected from v1's incorrect `apps/cell-core/`)
6. ✅ **No regression** in `apps/evaluator/seo_cell/` (per NB-1 useful signal — SEO cell uses cell_core.hgt.domains and could be affected by additive "crm" registration; verify via SEO cell test suite green post-A.1)

## Refusals (14 items, v2 expanded)

This spec MUST NOT trigger autonomous execution of:

1. **No `launchctl bootstrap`** on the modified `com.matagaruda.sentinel.hourly.plist` — plist corruption scar 2026-04-29 mandates operator action
2. **No production caller wiring for A.2** without operator choosing α/β/γ/δ
3. **No plist EnvironmentVariables changes** beyond the ProgramArguments switch (CORR-1 secrets sourcing scar preserved)
4. **No kill-switch lift** on HGT HALT commit until 14-day soak metrics all green
5. **No bulk emit-flag flip** on additional plists (Phase 1+2 scope is closed)
6. **No autonomous `git push --force`** on any TICKET branch (atomic commits + auto-merge SQUASH only)
7. **No edits to `apps/backend-rag/backend/app/dependencies.py`** SPOF guard (CLAUDE.md hard rule)
8. **No edits to root `VADEMECUM.md`, `SYMBIOSIS.md`, `.claude/rules/cicatrix-scars*.md`, `~/.nuzantara-secrets.env`** (operator-controlled per CLAUDE.md)
9. **No edits to `packages/cell-core/cell_core/hgt/{publisher,consumer,coordinator}.py`** outside of TICKET A.0 (the 5min property add) — cross-cell blast radius (CORR-4)
10. **No edits to `~/Library/LaunchAgents/com.balizero.intel.nightly.plist`** (production cron — operator-gated, CORR-4)
11. **No direct `redis-cli XADD cell:skills`** debug commands during execution — would pollute the substrate (CORR-4)
12. **No TICKET C deployment before TICKET B is in production** (sequencing hard gate, CORR-4)
13. **No edits to `apps/evaluator/seo_cell/`** as part of Phase 3 (SEO cell independent; regression-test only, CORR-4 + CORR-7 NB-1 signal)
14. **No synchronous `asyncio.run()` execution inside HGT publisher application code** (CORR-4 + Gemini F1 — sync shim is removed in spec v2)

## Hidden coupling notes (revised v2)

### SEO cell regression risk (CORR-7, NB-1 useful signal)

`apps/evaluator/seo_cell/` uses `cell_core.hgt.domains.validate_domain` to filter its own HGT broadcasts (currently `action="none"` per CLAUDE.md mention but the import surface is shared). Adding "crm" to the whitelist in `packages/cell-core/cell_core/hgt/domains.py` (TICKET A.1) is ADDITIVE — does NOT replace existing domains. Regression test MUST verify SEO cell test suite passes post-A.1:

```bash
cd ~/Desktop/nuzantara/apps/evaluator && pytest tests/seo_cell/ -v
```

If any SEO cell test fails post-A.1, abort TICKET A.1 merge and investigate validate_domain implementation.

### NB-1 stale snapshot caveat

NotebookLM NB-1 (Nuzantara Codebase) verdict was BLOCK based on a snapshot from 2026-03-23 — predates the addition of `apps/crm-cell/`, `apps/cell/`, `apps/organism/`, `apps/openclaw-hgt-coordinator/` (all added Apr-May 2026). NB-1's claim that these paths "don't exist" is **factually wrong** vs. on-disk state at 2026-05-12 21:25 WITA. NB-1 useful signals (SEO cell, crm-cell caller preference, validate_domain canonical location) extracted into spec v2; BLOCK verdict rejected as STALE. Action: trigger NB-1 re-ingestion (nb-curator follow-up task — out of scope this PR).

### Phase 2.5 seed signature is the canonical Redis instance marker (CORR-2)

`XLEN cell:skills = 18` on Pro localhost Redis at 6379 is the canonical signature for "this Redis instance owns cell:skills". TICKET B `_make_cell_runner_with_preflight()` uses this signature as preflight check. If a future plist sets `REDIS_URL=redis://100.93.236.6:6379` (Mini Tailscale IP), preflight fails (Mini cell:skills = 0), runner returns None, legacy fallback engages — bounded blast.

### Sequencing dependency: A.1 "crm" domain registration is sticky

Once TICKET A.1 merges, `packages/cell-core/cell_core/hgt/domains.py` permanently includes "crm". Reverting requires a separate PR. This is intentional — TICKET A.2 caller integration cannot publish without the domain registered. If TICKET A.1 ships but A.2 never does, the only side effect is a registered-but-unused domain (harmless).

## What this spec produces (autonomous scope, v2)

**Doc only**. Spec landed in `docs/superpowers/specs/`. No autonomous code changes. After 4-panel review:

- TICKET A.0 (cell_name public property) is autonomous-capable (5min, blast radius bounded to public API addition) — operator may approve immediate execution
- TICKET A.1 (CrmHGTBridge async + domain + test migration) is autonomous-capable (1 day, zero production caller blast radius) — waits operator approval per "Phase 3 spec FIRST, execute AFTER" pattern
- TICKET A.2 (production caller wire) is operator-gated per refusal #2 (architectural choice α/β/γ/δ)
- TICKET B (intel-scraper-cell wire) is bounded blast radius (CORR-8 fallback) — autonomous-capable post-merge, operator monitoring during 1st nightly cycle
- TICKET C (sentinel plist switch) is operator-gated per refusal #1 + #12 (plist corruption scar + sequencing gate)

## Brainstorm artifacts archive plan

Pre-review (spec v1 + 4 reviews):

- `/tmp/symbiosis-phase3-spec-review-2026-05-12/00_briefing.md` (empirical state + reviewer questions)
- `/tmp/symbiosis-phase3-spec-review-2026-05-12/01_claude_self_critique.md` (6 findings)
- `/tmp/symbiosis-phase3-spec-review-2026-05-12/02_gemini_review.md` (4 findings + Q1.3 architectural shift)
- `/tmp/symbiosis-phase3-spec-review-2026-05-12/03_deepseek_review.md` (7 findings)
- `/tmp/symbiosis-phase3-spec-review-2026-05-12/04_nb1_review.md` + `04_nb1_review_meta.md` (BLOCK invalid + 3 useful signals)
- `/tmp/symbiosis-phase3-spec-review-2026-05-12/05_synthesis.md` (cross-reference + final CORR list)

Post-review (this v2):

- Spec v2 (this file) with §"4-panel review convergences applied" table
- All 6 brainstorm files archived to `docs/audits/2026-05-12-phase3-spec-brainstorm/` (in this PR)

## Sources

1. `apps/crm-cell/crm_cell/hgt_publisher.py:1-89` (full file read 21:00 WITA)
2. `apps/bali-intel-scraper/backend/cell/hgt_publisher.py:1-177` (full file read 21:00 WITA)
3. `apps/bali-intel-scraper/backend/cell/runner.py:1-269` (full file read 21:00 WITA)
4. `apps/mata-garuda/scripts/run_sentinel_py.py:120-135` (legacy bypass verbatim re-read)
5. `apps/mata-garuda/mata_garuda/cells/sentinel_cell.py:25,46,91,95,126,167-170` (HGTConsumer wiring grep — line 46 empirically verified for create_sentinel_cell)
6. `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist` (ProgramArguments grep)
7. `~/Library/LaunchAgents/com.balizero.intel.nightly.plist` (plutil -extract EnvironmentVariables — REDIS_URL NOT SET, only HOME+PATH)
8. Commit `68efc17e3` HGT HALT message (premises canonical)
9. `redis-cli -h 127.0.0.1 XLEN cell:skills` → 18 (Pro localhost canonical)
10. `redis-cli -h 100.93.236.6 XLEN cell:skills` → 0 (Mini Redis empty)
11. `redis-cli XINFO GROUPS cell:skills` → sentinel-1, 0 consumers, lag=18, pending=0
12. `find /Users/nuzantara/Desktop/nuzantara -type d -name "hgt_coordinator"` → `packages/cell-core/cell_core/hgt_coordinator` exists
13. Gap 3 empirical spec `research/symbiosis/2026-05-12-gap3-hgt-3tickets-empirical-spec.md` (15:35 WITA — superseded by this v2)
14. Phase 2 closure doc `research/symbiosis/2026-05-12-phase2-live-execution-complete.md` (Phase 2.5 seed validation)
15. 4-panel review artifacts `/tmp/symbiosis-phase3-spec-review-2026-05-12/{00..05}_*.md`
