# Claude Opus 4.7 max — Self-critique on TICKET A.1 narrow spec

**Date**: 2026-05-12 23:32 WITA
**Method**: adversarial reading, looking for hidden assumptions and test coverage gaps.

## Verdict (self-imposed)

**PROCEED WITH CONDITIONS** — spec is empirically anchored on fresh A.0 merge, but I find 5 substantive issues I would flag if reviewing peer's work.

## Findings

### F1 (severity: high) — `DeprecationWarning` raise semantics are arguably wrong

The spec has:

```python
class CrmHGTPublisher:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise DeprecationWarning("...")
```

**Problem**: `DeprecationWarning` is a subclass of `Warning`, NOT `Exception`. The Python convention is to `warnings.warn("...", DeprecationWarning)` for deprecation, not `raise`. Raising a `Warning` works (it inherits from Exception via Warning → Exception), but it's semantically muddled:

- Production code calling `CrmHGTPublisher()` gets a `DeprecationWarning` raised as if it were an error
- Code that filters warnings (e.g., `warnings.filterwarnings("ignore")`) will NOT silence this raise
- IDE/linter may flag the pattern as a code smell

Worse: `pytest.raises(DeprecationWarning)` accepts it (because it's an Exception subtree), but the intent is unclear to readers.

**Recommended action**: use `RuntimeError` with a clear message that mentions deprecation/removal. Or `NotImplementedError` (the class shape stays but the implementation is intentionally gone). Update test #8 in test_stubs.py migration accordingly:

```python
class CrmHGTPublisher:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "CrmHGTPublisher is removed in Phase 3 TICKET A.1. "
            "Use CrmHGTBridge.from_redis(redis_client).publish(...) instead. "
            "See docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md"
        )
```

```python
def test_legacy_crm_hgt_publisher_raises_on_construction():
    with pytest.raises(RuntimeError, match="CrmHGTBridge"):
        CrmHGTPublisher()
```

### F2 (severity: medium) — `procedure` string is sometimes garbage

The auto-formatted `procedure` reads:

```python
"procedure": (
    f"{pattern.pattern_kind}: " + ", ".join(
        f"{k}={v}" for k, v in sorted(pattern.payload.items())
        if k not in self._FORBIDDEN_PAYLOAD_KEYS
    )
),
```

For a pattern with payload `{"template_id": "T123", "bounce_pct": 0.82, "n": 1000}`, this produces:

```
"brevo_template_bounce_rate: bounce_pct=0.82, n=1000, template_id=T123"
```

That's readable. But for a payload `{"x": 1, "y": 2}` with pattern_kind `unknown_metric`:

```
"unknown_metric: x=1, y=2"
```

…which is useless as a "procedure" (a procedure should describe what the pattern says). The IntelScraperHGTBridge takes `procedure` as a user-supplied string explaining the pattern in plain English — that's the canonical contract.

**Problem**: my auto-formatted version reduces information to a key-value dump. Downstream consumers (HGTConsumer, future LLM that reads cell:skills) will struggle to extract semantic meaning.

**Recommended action**: 2 options:

- **Option α**: Require pattern.procedure as a string (extend `StructuralPattern` dataclass), matching IntelScraperHGTBridge canonical shape. Breaks legacy shape but zero callers.
- **Option β**: Keep auto-format but make it explicit (`"crm.pattern.<kind> with structural payload [k=v, ...]"`) and accept that human-readable descriptions are deferred to A.2 caller.

Recommend **Option α** since: (a) zero callers means zero breakage, (b) canonical schema across bridges helps Phase 4 consumers, (c) test fixtures can use a simple boilerplate string. Adds 1 field to dataclass.

### F3 (severity: medium) — `success_criterion` "7-day window" is hard-coded boilerplate

Same problem as F2 but for `success_criterion`:

```python
"success_criterion": (
    f"pattern {pattern.pattern_kind} replicates in next "
    "7-day observation window"
),
```

The pattern itself doesn't define how to verify it holds. Boilerplate is fine for v1 IF the consumer (HGTConsumer) doesn't act on success_criterion strings. If it does, this becomes a hidden coupling.

**Recommended action**: same as F2 — extend dataclass with `success_criterion: str` field. Default to boilerplate if not provided.

### F4 (severity: low) — Test 7 mock chain reaches the wrong catch

Spec test 7:

```python
async def test_publish_xadd_exception_swallowed_returns_false(bridge, mock_redis, caplog):
    mock_redis.xadd.side_effect = RuntimeError("redis down")
    ...
    result = await bridge.publish(pattern)
    assert result is False
    assert any("publish failed" in r.message for r in caplog.records)
```

**Problem**: the call chain is `bridge.publish() → self._publisher.publish() → self._redis.xadd()`. The xadd raises RuntimeError. Looking at HGTPublisher.publish() lines 54-77:

```python
try:
    await self._redis.xadd(...)
    ...
    return True
except Exception as e:
    logger.warning(f"[hgt] publish failed (Redis down?): {e}")
    return False
```

So HGTPublisher catches the RuntimeError and returns False. The bridge's own try/except wraps `published = await self._publisher.publish(skill)`, but since `_publisher.publish` returns cleanly (False), the bridge's except clause is NEVER hit.

The test passes (asserting result is False + log message contains "publish failed"), but the log message comes from HGTPublisher's `logger.warning(f"[hgt] publish failed ...")`, NOT from bridge's `logger.warning("hgt: publish failed (non-blocking): ...")`. Test 7 checks `caplog.records` for "publish failed" substring which matches BOTH messages, so the test isn't precise.

**Recommended action**: 2 options:

- **Option α** (precise test): use `caplog.set_level(logging.WARNING, logger="crm_cell.hgt_publisher")` to filter to bridge's logger only, and check for "non-blocking" in the message to disambiguate from HGTPublisher.
- **Option β** (refactor): the bridge's try/except is dead code since HGTPublisher already catches everything. Remove the bridge's try/except. The `logger.info("hgt: pattern X published=Y")` line should still run unconditionally.

Recommend **Option β** — kill dead defensive code, simplify the bridge.

### F5 (severity: low) — `from_redis(None)` no-op path test is insufficient

Test 6 (`test_publish_redis_none_returns_false`):

```python
bridge = CrmHGTBridge.from_redis(redis_client=None)
pattern = StructuralPattern(pattern_kind="test", confidence=0.9, payload={"k": "v"})
assert await bridge.publish(pattern) is False
```

Looking at HGTPublisher line 43: `if not self._redis: return False`. So `_redis = None` → publish returns False before xadd is called. Good.

But the test doesn't verify NO side effects (no xadd call, no log). A future change to HGTPublisher could remove that early-return and start calling `None.xadd(...)` → AttributeError → silent False via bridge's exception swallow. The test would still pass.

**Recommended action**: in test 6, also assert that `caplog.records` is empty (or contains a specific "redis not configured" message). Plus assert that no xadd attempt was made (but with None redis there's nothing to mock — so this is moot).

Lower priority. Skip if F4 refactor (Option β) removes the bridge's swallow.

## Open architectural question (no F, just thinking)

**Should CrmHGTBridge accept the canonical `StructuralPattern` shape directly?** I.e., kill the bridge translation layer entirely, make crm-cell publish the same shape as intel-scraper-cell.

Pros:

- Eliminates schema-translation cognitive load
- Single canonical StructuralPattern across all cells
- Bridge becomes a 2-line proxy

Cons:

- Breaks legacy `StructuralPattern(pattern_kind, confidence, payload)` shape
- Existing test_stubs.py fixtures would need rewrite (5 tests anyway being migrated)
- Couples crm-cell more tightly to intel-scraper-cell's design choices

The Phase 3 spec v2 decided Option γ (bridge with translation) explicitly. I'm consistent with that. But after writing the actual translation code (this spec) I'm less convinced — the translation feels like glue for the sake of "matching the pattern" rather than for any real abstraction benefit.

**Recommendation**: stay with Option γ this PR but flag for Phase 4 unified base class refactor (Option δ from spec v2).

## Top 5 convergent corrections for spec v2

1. **CORR-A1-1 (F1)**: replace `raise DeprecationWarning` with `raise RuntimeError`. Update test_stubs.py migration test accordingly.
2. **CORR-A1-2 (F2)**: extend `StructuralPattern` dataclass with `procedure: str` field; require caller to provide. Make boilerplate optional via default param.
3. **CORR-A1-3 (F3)**: extend `StructuralPattern` dataclass with `success_criterion: str` field (boilerplate default OK).
4. **CORR-A1-4 (F4)**: remove the bridge's try/except (dead code) OR refine test 7 to filter caplog by logger name + match "non-blocking" substring. Recommend the removal (Option β).
5. **CORR-A1-5 (F5)**: tighten test 6 to verify no side effects when `_redis=None`. Lower priority if F4 Option β.

## Meta-observation

The narrow spec is **already much tighter** than the original Phase 3 spec v2 because:

- A.0 is shipped (no cell_name protected access)
- "crm" is already registered (no domains.py edit)
- SEO cell is verified ZERO impact (no regression worry)

So A.1 is genuinely just 4 files / ~325 LOC. The remaining risk is **test fidelity** (F4) and **schema clarity** (F2/F3), both low-medium severity. No critical findings. PROCEED WITH CONDITIONS is honest.

If the 3 external reviewers converge on F1 (DeprecationWarning semantics) and F2/F3 (procedure/success_criterion as user-supplied), spec v2 corrections are ~30 min of work.
