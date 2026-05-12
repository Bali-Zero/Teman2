# TICKET A.1 narrow spec — 4-Panel Review Briefing

**Date**: 2026-05-12 23:30 WITA
**Spec under review**: `/Users/nuzantara/Desktop/nuzantara/research/symbiosis/2026-05-12-ticket-a1-narrow-spec.md`
**Predecessor**: Phase 3 spec v2 (PR #623 merged commit 957623090) + TICKET A.0 (PR #626 merged commit 6e92046d8)
**Empirical state**: 2026-05-12 23:25 WITA

## Context

This is **TICKET A.1 of Phase 3 SYMBIOSIS organism turn-on**, the narrow spec for the publisher infrastructure refactor (1 day code + tests).

A.1 follows A.0 (which just shipped 11 min ago) and is the largest autonomous-capable ticket in Phase 3. Subsequent tickets (A.2, B, C) are operator-gated.

## A.1 scope (narrow)

**4 files**:

1. `apps/crm-cell/crm_cell/hgt_publisher.py` — full rewrite (CrmHGTBridge async replaces CrmHGTPublisher sync; legacy class raises DeprecationWarning)
2. `apps/crm-cell/crm_cell/__init__.py` — add CrmHGTBridge export
3. `apps/crm-cell/tests/test_hgt_publisher.py` — NEW, 9 async tests
4. `apps/crm-cell/tests/test_stubs.py` — migrate 5 sync HGT tests to 1 DeprecationWarning test

**Total**: ~+325 / -80 LOC.

## Pre-condition relaxations from Phase 3 spec v2

Two spec v2 claims now empirically OBSOLETE:

1. "Register 'crm' domain in cell_core.hgt.domains" — **DROP**, `crm` already line 6 of CANONICAL_DOMAINS frozenset.
2. "SEO cell regression test required" — **DROP** (re-frame no-op), apps/evaluator/seo_cell/ has ZERO `validate_domain` or `hgt` references (empirical grep).

## Reviewer questions

### For Gemini 3.1 Pro (architectural)

- Q1.1: `procedure` string formatting (sort payload kv) — useful or should pattern carry richer fields like IntelScraperHGTBridge?
- Q1.2: `success_criterion` hardcoded "7-day window" boilerplate — parameterize or leave?
- Q1.3: test 7 mock chain (xadd RuntimeError) — does it actually hit CrmHGTBridge's catch or HGTPublisher's swallow?

### For DeepSeek Reasoner (logical)

- Q2.1: Verify cited file:line numbers (line 79 stub, CANONICAL_DOMAINS line 6, test_stubs.py 98-141)
- Q2.2: `DeprecationWarning` raised in **init** — semantically correct? Subclass of Warning, not Error. Should be RuntimeError/NotImplementedError instead?
- Q2.3: HGTPublisher line 43 checks `if not self._redis: return False`. AsyncMock is truthy → publish proceeds. Verify mock semantics.

### For NB-1 (with stale snapshot caveat)

- Q3.1: ⚠️ NB-1 March 23 snapshot predates crm-cell — skip crm-cell architecture, instead verify HGTPublisher 9-field schema contract.
- Q3.2: Does HGTConsumer accept `_metadata` field (with legacy_payload nested dict) in stream entry?
- Q3.3: Other consumers in tree affected by new `cell_origin="crm-cell"` appearing?

## Critical context

- ✅ A.0 shipped: HGTPublisher.cell_name public property is available
- ✅ "crm" in CANONICAL_DOMAINS already (verified)
- ✅ apps/evaluator/seo_cell/ has ZERO HGT/validate_domain refs (verified)
- ✅ CrmHGTPublisher zero production callers (only tests + **init** re-export)
- ✅ redis-cli XLEN cell:skills = 18 (seed unchanged)

## Verdict format

PROCEED / PROCEED WITH CONDITIONS / WEAK / BLOCK + numbered findings F1..Fn + top corrections.

## Sources

- Phase 3 spec v2: `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
- TICKET A.1 narrow spec: `research/symbiosis/2026-05-12-ticket-a1-narrow-spec.md`
- A.0 PR #626 merge: 2026-05-12T15:19:56Z commit `6e92046d8`
- 4-panel review for Phase 3 spec v2 archive: `docs/audits/2026-05-12-phase3-spec-brainstorm/`
