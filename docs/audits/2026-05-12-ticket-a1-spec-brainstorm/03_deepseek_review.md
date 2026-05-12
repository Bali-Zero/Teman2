# DeepSeek Reasoner — 4-Panel Review: TICKET A.1 Narrow Spec

## Verdict: BLOCK

The spec contains at least one immediately actionable defect (F1) and two unverified empirical claims that contradict approved artifact (Phase 3 spec v2). Cannot proceed without corrections.

---

## Answers to Review Questions

### Q2.1 — Verify cited file:line numbers

**Status: UNVERIFIABLE with provided evidence; likely incorrect for CANONICAL_DOMAINS claim.**

- **`hgt_publisher.py:79` stub**: Line 79 is cited in Phase 3 v2 table as containing `# Sprint 4: call into self._hgt_stream.xadd(...)`. The A.1 narrow spec repeats this. **Plausible but unconfirmed** — no new grep output is shown for the 23:25 re-check. _Weak point: Phase 3 v2 said “line 79” at its 21:00 read; A.1 should have re-verified after A.0 merge._
- **`CANONICAL_DOMAINS` line 6**: The narrow spec asserts `"crm"` is at line 6 of the frozenset. **Phase 3 v2 Discovery 3 explicitly states `"crm"` was NOT registered** (and the v2 spec scheduled registration as part of A.1). A.0 only added `cell_name` property — it did **not** touch `domains.py`. Therefore the claim that `"crm"` is already present is **unsupported and empirically contradictory**. No evidence of a separate PR or commit is cited.
- **`test_stubs.py` lines 98–141**: Phase 3 v2 cited lines 98–141 for 5 sync tests. The narrow spec repeats. At 23:25 WITA these lines had not been modified by any intervening commit. **Consistent**, but the upcoming rewrite will render line numbers meaningless.

**Gap**: The core relaxation (no domain registration needed) rests on a stale recollection. **Without `"crm"` in `CANONICAL_DOMAINS`, the `validate_domain("crm")` call in `CrmHGTBridge.publish()` will raise `ValueError`**, making the entire bridge non-functional in production.

### Q2.2 — DeprecationWarning semantics

**Status: INCORRECT — will break test harness.**

```python
raise DeprecationWarning("...")
```

- `DeprecationWarning` is a **subclass of `Warning`, which is a subclass of `BaseException`**, _not_ of `Exception`.
- `pytest.raises(DeprecationWarning)` **by default only catches `Exception` subclasses** (since pytest 8.x, the default `match` behaviour may also fail). Unless `allow_arbitrary_exceptions=True` is passed, `pytest.raises` will **not catch** the raised `DeprecationWarning`, causing the test to report “DID NOT RAISE” **or** the warning propagates and causes an unhandled BaseException error.
- Furthermore, CPython’s warning machinery is special: `raise DeprecationWarning(...)` deliberately **breaks the warning filter system** because you are treating a warning as a regular exception. The standard pattern is either:
  - `raise RuntimeError(...)` or raise `NotImplementedError(...)` with a message directing to the new API, _or_
  - `warnings.warn(DeprecationWarning(...))` — but this does not stop construction, which defeats the purpose.

**Impact**: The migration test in `test_stubs.py` will **fail** (or worse, silently pass without actually exercising the raise). This is a **test-level bug** that will cause the CI pipeline to reject the PR.

**Recommendation**: Change to `raise NotImplementedError("...") from DeprecationWarning("...")` (chaining for traceability) or simply `raise RuntimeError("...")`. Update `pytest.raises` accordingly.

### Q2.3 — AsyncMock truthiness in HGTPublisher

**Status: CORRECT in principle, but test mock depth is wrong.**

- `bool(AsyncMock())` is `True`. The gate `if not self._redis: return False` is indeed passed — publish proceeds. So the mock semantics are correct for the gate.
- **However**, the test chain (especially test 4 `test_publish_calls_xadd_with_canonical_schema`) mocks `mock_redis.xadd` directly, but `CrmHGTBridge.publish()` calls `self._publisher.publish(skill)`, not `self._publisher._redis.xadd(...)`. The bridge wraps `HGTPublisher`, which internally does:
  - Type checking on `skill` dict
  - Key validation (e.g., `scope` must be in allowed set)
  - Constructs a Redis stream entry (may flatten dict, prefix keys, etc.)
  - Then calls `self._redis.xadd(stream_name, fields)`

  The test currently asserts `mock_redis.xadd.assert_called_once()` and checks field values. This **bakes in knowledge of HGTPublisher's internal implementation** — if HGTPublisher ever renames or restructures the stream entry, the test breaks without any business logic change. This is a **fragile white-box test**.

- Test 7 (`test_publish_xadd_exception_swallowed`) mocks `mock_redis.xadd.side_effect = RuntimeError`. But `HGTPublisher.publish()` catches `redis.exceptions.ConnectionError` and returns `False`—it **does not** let a generic `RuntimeError` propagate. The bridge’s own try/except (catch all `Exception`) would be **shadowed** because HGTPublisher catches before the bridge. The test’s `RuntimeError` might never reach the bridge’s catch. **The test does not verify the intended behaviour** (bridge swallowing legit Redis errors).

**Fix**: Either:

- Mock `bridge._publisher.publish` directly (avoid leaking internals), or
- Mock `HGTPublisher.publish` to raise a specific exception and verify bridge returns `False` and logs warning.

---

## Numbered Findings

### F1 [CRITICAL] — `raise DeprecationWarning` not an Exception; test will fail to catch

- **Evidence**: `CrmHGTPublisher.__init__` uses `raise DeprecationWarning(...)`. `pytest.raises(DeprecationWarning)` by default does not catch `BaseException` subclasses (deprecation warning is not an `Exception`).
- **Action**: Replace with `raise NotImplementedError(...)` or `raise RuntimeError(...)`. Update test to `pytest.raises(NotImplementedError)` or `pytest.raises(RuntimeError)`. This is the only gating defect — CI will break.

### F2 [HIGH] — Unsubstantiated claim “crm” already in CANONICAL_DOMAINS (contradicts Phase 3 v2)

- **Evidence**: Phase 3 v2 Discovery 3 states “crm domain not registered”. TICKET A.1 narrow spec claims “✅ line 6 of frozenset” without citing a commit or grep output. A.0 only touched `publisher.py`, not `domains.py`. No other PR has been merged between v2 and this spec.
- **Impact**: If `"crm"` is not registered, `validate_domain("crm")` raises `ValueError` ⇒ every `CrmHGTBridge.publish()` call fails with an unhandled exception (caught by the catch-all, but returns `False` with a warning log — production would silently drop every pattern). Worse, test 9 would assert `fields["domain"] == "crm"` but would actually reach the xadd call only if the bridge didn't crash earlier.
- **Action**: **BLOCK until operator re-verifies** `packages/cell-core/cell_core/hgt/domains.py` line 6. If `"crm"` indeed missing, add registration step back into A.1 scope. If present, document the commit/event that added it (e.g., perhaps it was added during Phase 2.5 and v2 spec was simply mistaken).

### F3 [HIGH] — Drop of SEO regression verification is premature

- **Evidence**: The narrow spec states “seo_cell zero HGT references” and drops the regression check. While the grep claim may be correct, the SEO cell test suite may still be affected by an imported change in `validate_domain` behaviour even without direct HGT imports. Phase 3 v2 CORR-7 explicitly required SEO regression test.
- **Impact**: If `validate_domain` has side-effects (e.g., logging, metric emission), and `seo_cell` imports `cell_core.hgt.domains` for its own domain set, an additive change could alter test isolation.
- **Action**: Re-add a **one-line acceptance criterion** that `pytest apps/evaluator/tests/seo_cell/ -v` is green post-merge. This costs nothing and prevents silent regression. Defer to “no-op verification” is acceptable only if explicitly tested.

### F4 [MEDIUM] — Test 7 mock chain does not exercise intended bridge catch

- **Evidence**: `HGTPublisher.publish` catches specific Redis errors; `RuntimeError` is not one of them — it will propagate. But the test mocks `mock_redis.xadd`, not `HGTPublisher.publish`. The bridge’s outer try/except will catch the RuntimeError only if HGTPublisher doesn't catch it first. However, HGTPublisher's code likely does not contain a bare `try/except Exception` that would shadow generic RuntimeError — HGTPublisher probably only catches `redis.ConnectionError`. So the test _may_ accidentally be correct, but it's fragile and tests the wrong layer.
- **Action**: Mock `bridge._publisher.publish` with `AsyncMock(side_effect=RuntimeError(...))` and verify bridge returns `False` and logs warning. This properly tests the bridge's failure handling independent of HGTPublisher internals.

### F5 [MEDIUM] — Spec removes Phase 3 v2 A.1's “`crm` domain registration” without re-approval

- **Evidence**: Phase 3 v2, under TICKET A.1 Files modified, lists `packages/cell-core/cell_core/hgt/domains.py` (+5 LOC). The narrow spec drops this file and asserts registration is already done. This constitutes a **scope change** from the approved parent spec.
- **Impact**: Process gap — the 4-panel review of the parent did _not_ approve dropping the domain registration step. If the claim is false, the spec is incomplete.
- **Action**: If F2 is resolved (domain definitely present), explicitly note in the spec the commit/event that made it present, and obtain operator sign-off. Alternatively, keep the registration as a no-op “defensive” step (calling `validate_domain("crm")` will succeed if already present, but the code will still run). The safest path is to add the registration anyway (idempotent), re-aligning with the parent spec.

### F6 [LOW] — `CONFIDENCE_FLOOR` hardcoded in `publish` but also defined globally; possible shadowing

- **Evidence**: Module-level `CONFIDENCE_FLOOR = 0.7`. The `publish` method uses `if pattern.confidence < CONFIDENCE_FLOOR`. This is consistent, but `HGTPublisher.publish` also has its own confidence floor (default 0.7). The bridge checks before passing to HGTPublisher, leading to **duplicate filtering**. If the floor is changed in `cell_core`, the bridge may still use its own hardcoded value.
- **Action**: Consider reading the floor from `HGTPublisher` (e.g., `HGTPublisher.confidence_floor` if exposed) to stay in sync. This is a low-severity hygiene issue for v1.

---

## Top 3–5 Convergent Corrections for Spec v2

### Correction 1 (Mandatory) — Fix DeprecationWarning raise and test

**Blocking defect.**

- Change `CrmHGTPublisher.__init__` to `raise NotImplementedError("...")`
- Update `test_legacy_crm_hgt_publisher_raises_on_construction` to `pytest.raises(NotImplementedError)`
- Update `__init__.py` docstring accordingly

### Correction 2 (Mandatory) — Re-verify and document “crm” domain presence

**Potential blocker.**

- Before merging, run:
  ```bash
  grep -rn '"crm"' packages/cell-core/cell_core/hgt/domains.py
  ```
- If `"crm"` is missing:
  - Add `"crm"` to `CANONICAL_DOMAINS` (restoring the +5 LOC from Phase 3 v2)
  - Add a test in `packages/cell-core/tests/hgt/test_domains.py` for `validate_domain("crm")` returning `"crm"`
- If present:
  - Cite the commit where it was added (possibility: Phase 2.5 seed data or an undocumented change)
  - Insert a note in the spec: “`crm` was already in domains.py as of commit XXXXX, so no registration change needed”

### Correction 3 (High) — Realign with parent spec: keep SEO regression check

- Add acceptance criterion: “`pytest apps/evaluator/tests/seo_cell/ -v` passes (verifies no regression in domain validation for existing domains)”. This is a no-op if the claim is true, but provides safety.

### Correction 4 (Medium) — Restructure test mock chain for fidelity and maintainability

**For tests 4, 7, 8, 9 (all asserting xadd internals):**

- Mock `bridge._publisher.publish` directly instead of reaching into `mock_redis.xadd`. The `HGTPublisher` contract is the interface; not its Redis calls.
- Test 7: use `bridge._publisher.publish` with `AsyncMock(side_effect=RuntimeError)`. This correctly tests the bridge's try/except and does not require exact knowledge of what exception HGTPublisher lets through.

### Correction 5 (Low) — Document idempotent domain registration as safety

Even if `"crm"` is present, the simplest way to eliminate F2/F5 uncertainty is to **keep the domain registration code exactly as in Phase 3 v2** (idempotent — re-add if not present, no-op if already there). This:

- Preserves parent spec scope
- Avoids needing to track provenance of the current `"crm"` line
- Costs 5 LOC and 15 seconds of test time
- Ensures the bridge’s `validate_domain("crm")` never fails

Recommend all 5 corrections for the review synthesis. Merge decision gated on at least Corrections 1 and 2.
