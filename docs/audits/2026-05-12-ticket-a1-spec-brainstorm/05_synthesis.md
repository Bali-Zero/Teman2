# 4-Panel Synthesis — TICKET A.1 Narrow Spec v1

**Date**: 2026-05-12 23:32 WITA
**Inputs**: 4 reviews (Claude self + Gemini + DeepSeek + NB-1)

## Verdicts table

| Reviewer             | Verdict                 |                                               Findings |
| -------------------- | ----------------------- | -----------------------------------------------------: |
| Claude self-critique | PROCEED WITH CONDITIONS |                                                      5 |
| Gemini 3.1 Pro       | **BLOCK**               |                 4 (F1 CRITICAL, F2 HIGH, F3/F4 MEDIUM) |
| DeepSeek Reasoner    | **BLOCK**               | 6 (F1/F2 critical-HIGH but FALSE POSITIVE empirically) |
| NB-1 NotebookLM      | **BLOCK**               |        1 critical (Q3.2 \_metadata) — empirically TRUE |

**Aggregate**: 3/4 BLOCK. Convergence: **1 TRUE critical finding** (\_metadata silent drop) + 4 TRUE secondary findings. DeepSeek's 2 BLOCK findings are FALSE POSITIVE (empirically smentite).

## Empirical verification of disputed findings

| Finding               | Source                                       | Disputed claim                                                                                                                                                                                                                                                            | Empirical verdict           |
| --------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| DeepSeek F1           | pytest.raises won't catch DeprecationWarning | `DeprecationWarning issubclass of Exception: True`. pytest.raises(DeprecationWarning) catches correctly. Confirmed via Python REPL.                                                                                                                                       | ❌ FALSE — REJECT           |
| DeepSeek F2           | "crm" not in CANONICAL_DOMAINS               | `grep -n '"crm"' domains.py` → line 18. Added commit `09aadbdc5` (2026-04-16 Sprint parallel RAG SOTA + Metabolic + HGT #57), predates Phase 3 v2 by 26 days. Phase 3 v2 Discovery 3 was OUTDATED, not narrow spec's claim.                                               | ❌ FALSE — REJECT           |
| NB-1 Q3.2 / Gemini F1 | `_metadata` nested dict crashes Redis XADD   | EMPIRICAL: HGTPublisher line 56-67 selects 9 explicit keys (`skill_id`, `cell_origin`, `procedure`, `precondition`, `success_criterion`, `confidence`, `type`, `scope`, `domain`) — `_metadata` is **silently DROPPED**, not crashes. But the data IS lost (silent drop). | ✅ TRUE (modified) — ACCEPT |

NB-1 was partially wrong (no crash, just drop), but Gemini F1 captured the TRUE issue precisely. ACCEPT Gemini's framing.

## Convergent TRUE findings

| #      | Severity | Finding                                                                                                                                                                 | Source                                                                             | Resolution                                                                                                                                                                                                                               |
| ------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TRUE-1 | CRITICAL | `_metadata` field with `legacy_payload` is silently dropped by HGTPublisher. Either it's useless (remove) OR encode legacy_payload as JSON string in an existing field. | NB-1 Q3.2 + Gemini F1 + (Claude self implicit via F2 procedure formatting concern) | REMOVE `_metadata`. Encode meaningful data in `procedure`/`precondition`/`success_criterion` as plain strings (user-provided).                                                                                                           |
| TRUE-2 | HIGH     | `procedure` auto-joined from payload kv is impoverished                                                                                                                 | Claude self F2 + Gemini Q1.1+F4 + Gemini correction 1                              | Require `procedure: str` user-provided field on `StructuralPattern` dataclass. Mirrors IntelScraperHGTBridge.                                                                                                                            |
| TRUE-3 | HIGH     | `success_criterion` hardcoded boilerplate                                                                                                                               | Claude self F3 + Gemini Q1.2 + Gemini correction 1                                 | Require `success_criterion: str` user-provided field on `StructuralPattern`.                                                                                                                                                             |
| TRUE-4 | MEDIUM   | `precondition` similar issue (hardcoded "crm activity stream actively populated")                                                                                       | implicit from F2/F3                                                                | Require `precondition: str` user-provided field on `StructuralPattern`.                                                                                                                                                                  |
| TRUE-5 | MEDIUM   | Bridge `try/except Exception` is dead code (HGTPublisher line 75-77 catches all Exception)                                                                              | Claude self F4 + Gemini F2 + Gemini Q1.3                                           | Remove bridge try/except. Simplify to: `published = await self._publisher.publish(skill); return published`.                                                                                                                             |
| TRUE-6 | MEDIUM   | Test 7 mock chain reaches HGTPublisher's catch not bridge's                                                                                                             | Claude self F4 + Gemini Q1.3 + DeepSeek F4                                         | Either remove Test 7 (no bridge catch to test) OR refactor to mock `bridge._publisher.publish` with side_effect. Easier: remove Test 7.                                                                                                  |
| TRUE-7 | MEDIUM   | `CrmHGTPublisher` retained as raise-stub is "unnecessary clutter"                                                                                                       | Gemini F3 (Gemini's strongest stance)                                              | DELETE `CrmHGTPublisher` class entirely from `hgt_publisher.py` and `__init__.py`. Migrate `test_stubs.py` to remove the 5 HGT sync tests + the new "raises" test — replace with imports of `CrmHGTBridge` from `test_hgt_publisher.py`. |
| TRUE-8 | LOW      | StructuralPattern legacy shape `(pattern_kind, confidence, payload)` is wire-incompatible with canonical schema                                                         | Gemini correction 1 + Claude self meta-observation                                 | Refactor `StructuralPattern` to canonical shape: `(pattern_id, procedure, precondition, success_criterion, confidence, domain)`. Maps directly to xadd fields.                                                                           |

## Single-reviewer findings (decision)

| #           | From                                                             | Severity | Decision                                                                                                                                        |
| ----------- | ---------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| DeepSeek F3 | "Re-add SEO regression check"                                    | MEDIUM   | REJECT — empirical grep shows seo_cell has zero validate_domain/hgt refs. Keep no-op verification per narrow spec.                              |
| DeepSeek F5 | "Re-align with parent spec: keep idempotent domain registration" | LOW      | REJECT — empirical `crm` already line 18, idempotent re-add is harmless but unnecessary. Document the commit (already done in synthesis above). |
| DeepSeek F6 | "CONFIDENCE_FLOOR shadowing"                                     | LOW      | ADOPT in spec v2 — read from `HGTPublisher.CONFIDENCE_THRESHOLD` (public class attr line 31) instead of bridge module constant. Cleaner.        |
| Claude F5   | Test 6 doesn't verify no side effects                            | LOW      | REJECT — moot given HGTPublisher line 43 `if not self._redis: return False`, simple state.                                                      |

## Spec v2 corrections (final list — 8 corrections)

**CORR-1** (CRITICAL): **DELETE `CrmHGTPublisher` entirely**. No raise-stub, no DeprecationWarning, no re-export. Zero callers → zero migration cost. (TRUE-7, TRUE-8)

**CORR-2** (CRITICAL): Refactor `StructuralPattern` dataclass to canonical shape:

```python
@dataclass(frozen=True)
class StructuralPattern:
    pattern_id: str          # e.g. "brevo_template_T123_bounce_rate"
    procedure: str           # human-readable: what the pattern says
    precondition: str        # when this pattern applies
    success_criterion: str   # how to know it still holds
    confidence: float
    domain: str = "crm"      # default for crm-cell origin
```

(TRUE-1, TRUE-2, TRUE-3, TRUE-4, TRUE-8)

**CORR-3** (HIGH): **REMOVE bridge `try/except Exception`** — HGTPublisher's own line 75-77 catch already swallows. (TRUE-5)

**CORR-4** (HIGH): `CrmHGTBridge.publish()` becomes minimal:

```python
async def publish(self, pattern: StructuralPattern) -> bool:
    if pattern.confidence < CONFIDENCE_FLOOR:
        return False
    if pattern.confidence == 1.0:  # fixture guard
        return False
    if not self._is_pii_clean(pattern):
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
        "hgt: pattern %s published=%s confidence=%.2f",
        pattern.pattern_id, published, pattern.confidence,
    )
    return published
```

No `_metadata`. No try/except. No legacy payload preservation. (TRUE-1, TRUE-5)

**CORR-5** (HIGH): `_is_pii_clean` adapted to scan procedure/precondition/success_criterion strings for PII markers (mirrors IntelScraperHGTBridge `_is_pii_tainted` line 132-138):

```python
_PII_MARKERS = ("email", "@", "+62", "nik:", "npwp:", "passport", "client_id")

def _is_pii_clean(self, pattern: StructuralPattern) -> bool:
    haystack = " ".join((pattern.procedure, pattern.precondition, pattern.success_criterion)).lower()
    return not any(m in haystack for m in self._PII_MARKERS)
```

(Adapts old payload-keys check to new string-scan).

**CORR-6** (MEDIUM): `test_hgt_publisher.py` revised — **8 tests** (was 9):

- DROP test 7 (no bridge try/except to test) → 8 tests
- Test 4 asserts xadd called with canonical 9 fields (unchanged shape but now from typed StructuralPattern, not auto-joined payload)
- Test 9 (validate_domain) still proves domain="crm" not "generic"
- ADD test for PII detection on procedure string (e.g. "email" in procedure)

**CORR-7** (MEDIUM): `test_stubs.py` migration — remove all 5 HGT sync tests (lines 98-141). Do NOT add "raises" test (since CrmHGTPublisher is deleted entirely). Rest of test_stubs.py (CrmScarRecorder, CrmEventBridge, CELL_NAME, FailureKind) unchanged. Net: -5 tests in test_stubs.py.

**CORR-8** (LOW): `CONFIDENCE_FLOOR` read from `HGTPublisher.CONFIDENCE_THRESHOLD` instead of module constant. (DeepSeek F6)

## Effort revision

| Task                      | v1 estimate | v2 revised                                        |
| ------------------------- | ----------- | ------------------------------------------------- |
| Rewrite hgt_publisher.py  | 1d          | 1d (same scope, cleaner code)                     |
| **init**.py update        | 5min        | 5min (cleaner — no CrmHGTPublisher re-export)     |
| test_hgt_publisher.py new | 2h          | 2h (8 tests instead of 9, with stronger fidelity) |
| test_stubs.py migration   | 30min       | 15min (just delete 5 tests, no replacement)       |
| **Total A.1**             | 1 day       | **0.5-0.75 day** (corrections REDUCE complexity)  |

Counter-intuitive: 4-panel review's BLOCK actually REDUCES effort by killing dead code paths.

## Aggregate verdict

**PROCEED WITH 8 CORRECTIONS** (not BLOCK). 2/3 external BLOCK verdicts driven by partial truths (NB-1 right about silent drop but wrong about crash; Gemini F1 right) and false positives (DeepSeek F1+F2). After empirical verification + corrections applied, spec v2 is execution-ready with reduced complexity.

Same pattern as Phase 2/Phase 3 spec reviews: BLOCK verdicts capture genuine issues that converged after triangulation, but the spec writer should not auto-accept BLOCK without empirical verification.
