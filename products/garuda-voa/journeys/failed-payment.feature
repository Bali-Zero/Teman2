@red-first @journey @payment @failure
Feature: Failed payment never releases a practice
  # RED-FIRST: the provider sandbox failure event and all persistence assertions are mandatory.
  # TODO(ground): approve the provider-neutral terminal-failure taxonomy and customer retry copy.

  Scenario: Reconciled terminal failure preserves a recoverable customer path
    Given one order is "awaiting_payment"
    When the sandbox sends a valid signed terminal-payment-failure webhook
    Then the webhook inbox, append-only journal, "failed" state, and failure-email outbox commit atomically
    And no practice, tracker event, paid email, or delivered artifact exists
    When the browser follows a provider failure or success redirect
    Then the browser observation cannot change the authoritative "failed" state
    And the customer sees a safe retry action without a price component split
    When the customer retries payment under the grounded retry policy
    Then any new checkout uses a new order identity and idempotency key
    And the original order remains "failed"
    And no forbidden "failed" to "awaiting_payment" transition occurs

