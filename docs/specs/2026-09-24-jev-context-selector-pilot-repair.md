# JEV repository context selector pilot — suspended-candidate repair

> **Status:** FROZEN repair contract.
> **Mandate:** `jev-context-selector-pilot-repair-20260925`.
> **Authorization:** explicit owner GO (`continua`) after the Phase 0 candidate was
> suspended on its third same-cause BLUE review failure.
> **Mission:** BLUE, Gear 2, external builder prepare-only. No push, PR open,
> merge, arm, deploy, publish or client-facing send is authorized.

## 1. Scope

This mandate repairs only the two unresolved defects already demonstrated by
independent review. It does not authorize Phase 1, workflow integration, new
selector policy, another TypeSafe dry run or any change to recorded metrics.

## 2. Protected-symbol excerpt contract

Definition matching must not let multiline whitespace move the reported match
start onto preceding blank lines. Definition patterns accept horizontal leading
whitespace only. The excerpt line is computed from the captured identifier,
`match.start(1)`, rather than from the beginning of the whole regex match.

The focused regression must place more than 12 generic definition hits before
the protected definition, insert blank lines immediately before it, and prove
that the exact definition line is present in both `excerpt_lines` and the packet.

## 3. TypeSafe abstention contract

An `answers` object keeps the envelope schema valid, but a requested Noul answer
is usable only when its entry contains a finite, non-boolean numeric `noul`
probability in the inclusive range 0 through 1. Empty or malformed requested
entries therefore produce `abstained=true` and `fallback=true` without changing
`schema_valid=true` or inventing a failure code.

Unknown future question types remain usable only when the requested identifier
maps to a non-empty object.

## 4. Acceptance and stop conditions

1. The two new focused regressions fail against the suspended candidate and pass
   after the repair.
2. The full Phase 0 acceptance command, Ruff, compileall, metrics assertion and
   staged-diff check pass on the final staged bytes.
3. A fresh independent BLUE Codex reviewer outside the repair contribution chain
   returns PASS on the frozen candidate.
4. The original Phase 0 metrics and frozen input hashes remain unchanged.

Any remaining protected-evidence omission, unusable-answer misclassification,
repository escape, PII/secret exposure or unknown-as-zero behavior stops the
repair. Phase 1 still requires a separate explicit owner GO after this repair.
