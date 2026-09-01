@red-first @journey @orders @resume
Feature: A customer who comes back to a live order is told the truth about it
  # RED-FIRST: real repository and real provider adapter; the order state and the provider
  # session may not be mocked away, because every defect this journey exists to prevent lives
  # in the seam between what the database holds and what the customer is shown.
  #
  # GROUNDED 2026-08-25 by the orchestrator, and this file is the reason it exists. Three
  # separate corrections landed on "what happens when a customer returns to a live order"
  # without anyone ever specifying it: a crash on a fresh Idempotency-Key, then a lookup that
  # cured the crash and introduced a state lie, then a placeholder checkout URL nobody could
  # navigate. Each was a reasonable local guess. The surface was under-specified, so the
  # guesses kept contradicting each other — this journey is the spec they were missing, and
  # per the repo's rule 8 it is written INSTEAD of a fourth patch, not alongside one.
  #
  # The unifying rule, from which every scenario below follows: THE RESPONSE DESCRIBES THE
  # ORDER THAT EXISTS. Never a hardcoded state, never a checkout action for money already
  # taken, never a URL the customer cannot open.

  Background:
    Given one eligibility check owned by a synthetic customer
    And exactly one live order exists for that check
    And the customer's browser has lost whatever it knew about the previous attempt

  Scenario: A reload with a fresh Idempotency-Key does not create a second order
    Given the customer's first attempt already committed a live order
    When the customer submits again under a NEW Idempotency-Key for the same check
    Then no second order row is created for that check
    And the response carries the order identifier of the existing live order
    And the response is not an error and is not a 500
    # The unique index on (result_id_ref) over live states is the backstop, not the mechanism.
    # Reaching it means the read-then-insert raced: the lookup and the insert must be atomic,
    # or the insert must handle the conflict. A narrower crash window is not a fixed crash.

  Scenario: Two simultaneous fresh keys still produce exactly one order
    Given no order yet exists for the check
    When two requests carrying two different Idempotency-Keys arrive concurrently
    Then exactly one order row exists for that check afterwards
    And neither response is a 500
    And both responses describe the same order identifier

  Scenario Outline: The reported state is the state the order is actually in
    Given the live order is in state "<state>"
    When the customer returns to it
    Then the response reports order state "<state>"
    And the response offers a payment action only when "<offers_checkout>" is "yes"
    And any checkout URL in the response is one the customer's browser can open

    Examples:
      | state            | offers_checkout |
      | created          | yes             |
      | awaiting_payment | yes             |
      | paid             | no              |
    # `paid` is the one that matters and the one that was wrong: the response body hardcoded
    # "awaiting_payment", so a customer who had already paid was shown a payment action. It
    # was survivable only because the URL was a non-navigable placeholder — and the planned
    # cure for the placeholder (re-fetch the real URL from the provider) is exactly what would
    # have turned a state lie into a second charge. Fix the state, not just the URL.

  Scenario: Resuming an unpaid order reuses its provider session rather than opening another
    Given the live order is in state "awaiting_payment" with a provider session that has not expired
    When the customer returns to it
    Then the existing provider session is re-fetched by its identifier
    And no second provider checkout session is created for that order
    And the customer receives the real checkout URL for that existing session

  Scenario: An expired provider session is replaced, because the money was never taken
    Given the live order is in state "awaiting_payment" and its provider session has expired
    When the customer returns to it
    Then one replacement checkout session is created for the same order
    And the order identifier and the price are unchanged
    # Safe precisely because nothing was charged. This is the ONE case where a second session
    # is correct, and it is why the paid case must be excluded by state rather than by URL.

  Scenario: A customer correcting their own data before paying is not silently ignored
    Given the live order is in state "created" or "awaiting_payment"
    And the customer resubmits with a corrected passport number
    When the customer returns to the order
    Then the stored applicant details are updated to the corrected values
    And the correction is journalled as a customer-visible amendment
    # The resume lookup ignored the incoming applicant entirely, so the single most common
    # reason a person reloads a visa form — they mistyped the passport number — silently
    # bound them to an order carrying the wrong one. On this product the passport number IS
    # the deliverable; a dropped correction is a rejected application weeks later.

  Scenario: A change of case type is a different order, not an amendment
    Given the live order is in state "created" or "awaiting_payment"
    When the customer resubmits with a different case type
    Then the request is refused with a stable, customer-safe reason
    And the existing live order is left untouched
    # Issuance and extension are different products at different prices. Mutating case_type
    # under a live order would re-price an order the customer may already be paying for.

  Scenario: After payment, a data correction is staff-mediated and never silent
    Given the live order is in state "paid"
    When the customer resubmits with different applicant details
    Then the stored applicant details are NOT overwritten by the request
    And a staff-visible amendment case is opened against that order
    And the customer is told the correction is being handled, not that it was applied
    # The order is in fulfilment; a silent overwrite would desynchronise what the customer
    # believes was submitted from what was actually filed.

  Scenario: The customer is never handed a URL that does nothing
    When any resume path produces a checkout action
    Then the URL is a real provider URL
    And no response body contains a placeholder scheme such as "pending-resume:"
    # A placeholder that reaches a customer is worse than an honest error: it looks like
    # progress, so the customer waits instead of contacting anyone.
