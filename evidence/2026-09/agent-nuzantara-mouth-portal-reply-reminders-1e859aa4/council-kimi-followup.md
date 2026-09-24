# Kimi council clarification

Actual existing subscription CLI review using kimi-code/k3. Static, no tools or tests; supplied source, frozen spec and aggregate preflight facts only. Initial dissent is preserved in council-kimi-initial.md.

• **Updated council judgement — portal reply reminders (continuation)**

No blocking findings retained. P1-2 and P2-4 are withdrawn on the supplied evidence; three P3 observations remain. I find no concrete counterexample to the stated bounded contract in the supplied code. Static review only; nothing executed.

**Withdrawn**

- **P1-2 (zero-state / failed-load behavior — previously speculative): WITHDRAWN.** The catch branch preserves already-rendered messages and sets `loadError`; a failed _first_ load renders the `role="alert"` error with Retry, never the "No portal messages yet" empty state. A poll failure over existing content shows the stale-data banner with inline Retry. This satisfies "preserve stale pending counts and visible retry on load failure" at thread level.
- **P2-4 (automatic-path provenance — previously speculative pending imports/writer): WITHDRAWN.** All three automatic paths (document, practice-status, profile) flow through the single `_insert_message`, which unconditionally sets `is_system_generated=TRUE` and `direction='team_to_client'`. The sibling contract's explicit-identification requirement is structurally enforced for all future automatic notices, and insert failure pages via `notify_email_failure_critical` instead of silently dropping. Combined with the frozen spec's exclusion of the historical `sent_by='portal'` sentinel and its explicit non-reconstruction stance, the historical ambiguity is a bounded, disclosed limitation — not a defect.

**Counterexample search (against the stated contract, not an invented one)**

I tested three candidates; none survives:

1. **Legacy fallback erasing pending** — `isPending` keys off `total_pending !== undefined`, so a legacy payload degrades to unread-only. The contract authorizes this only during rolling deployment and assigns fail-the-poll to the backend. Not a violation as bounded.
2. **Banner clearing on failed send** — invalidation occurs only after the awaited `sendPortalMessage` resolves; a throw skips it, retaining pending. Meets "clears only following a successfully saved manual reply."
3. **Reading erasing pending** — mark-read invalidates the unread key, but the banner derives from `total_pending`, defined independent of `read_at`. No erasure path exists in the supplied code.

**Retained observations (non-blocking)**

- **P3-a (reduced motion):** the reminder pulse is correctly gated (`motion-safe:animate-pulse motion-reduce:animate-none`), but the thread's `scrollIntoView({behavior:"smooth"})` ignores `prefers-reduced-motion`. Cosmetic; suggest a `matchMedia` guard.
- **P3-b (thread header badge):** the per-thread unread badge derives from local state and can stay stale up to one poll after auto-mark-read; self-correcting, harmless.
- **P3-c (observability, as invited):** the intentional stale-fence no-op and three-attempt exhaustion deserve a counter/structured log so a silently unclaimed finish is dashboard-distinguishable from success. Telemetry only — agreed this is not corrupt state or duplicate delivery, and the 429-as-retryable-rejection semantics within three bounded attempts are consistent.

**Residual items outside the supplied evidence (unchanged, gated)**

The unread hook, backend pending query, outbox atomicity, and consumer lease/14-minute stop are not in this pack; they remain covered by the stated release conditions (post-deploy schema/worker/consumer proof). The preflight booleans and the 8-client/27-message historical backlog are consistent with the bounded historical contract. The absence of an authorized real-inbox recipient is a disclosed evidence gap (provider acceptance ≠ receipt), already accepted by the final gate — not a defect I can convert into a finding without inventing a guarantee the spec never made.

**Judgement:** P1-2 and P2-4 withdrawn. No P1/P2 findings stand against the bounded contract. No objection to proceeding to the fresh BLUE final gate with the stated release conditions intact.
