## Station 1 — product front (`apps/mouth`)

Scope: `apps/mouth/src/app/visa/voa/orders/` — the customer-facing GARUDA VOA order tracker
(`OrderTracker.tsx`, `useOrderTracking.ts`, their tests, `messages.ts`, `types.ts`).

A staff member reports three things customers have complained about on the live tracker.
None of them has a failing test today. Find each in the code, fix it, and add a regression
test for each that fails before your fix and passes after.

1. **The tracker labels money as paid when the order is not paid.** The amount line says
   "Total paid" regardless of `order_state`. It must read "Total paid" only when
   `order_state === "paid"` and "Order total" otherwise.
2. **The tracker promises nothing was charged on failed or expired checkouts.** For a
   failed or expired checkout the copy currently asserts that no payment happened. The
   backend cannot prove charge absence at that moment. The failed heading must become
   "This checkout couldn't be completed." (status line: "Checkout couldn't be completed."),
   and the body must say "A consultant can verify your payment status before you try again."
   — no claim about what was or was not charged.
3. **Polling stops too early.** Once a practice reaches `Submitted` the tracker keeps
   refreshing, but `Approved` and `Blocked` are still non-terminal for the customer (they
   can transition again) and the tracker must keep polling for them too. Terminal states
   and unmount must still stop the timer — prove cleanup in a test.

Also: a refunded order's heading currently reads "This order was refunded in full."
Refunds may be partial. It must read "This order was refunded."

Acceptance: `NODE_ENV=test npx vitest run src/app/visa/voa/orders/` is green in your
worktree, and your new tests are red if your fix is reverted (say how you checked that in
EVIDENCE, or list it under UNRUN).
