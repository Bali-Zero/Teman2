@red-first @journey @payment @idempotency
Feature: Payment duplication is contained
  # RED-FIRST: use the real provider sandbox, signed webhook inbox, journal, outbox, and state store.

  Background:
    Given a reviewed synthetic application has a fresh single all-inclusive price
    And one unambiguous active signed retention policy authorizes the order row types

  Scenario: Reusing the same idempotency key cannot create a second checkout
    When the customer requests checkout with a new idempotency key
    Then one order enters "awaiting_payment"
    And one provider checkout session is created
    When the identical checkout command is retried with the same idempotency key
    Then the original order and provider checkout session are returned
    And no second provider request, order, journal event, email, or charge authorization exists
    When a different checkout payload is submitted with that same idempotency key
    Then the request fails with an idempotency conflict
    And no provider request, state write, journal business event, or email occurs

  Scenario: Two distinct successful charges create one practice and one remediation case
    Given one order is "awaiting_payment"
    When a valid signed successful-payment webhook for the first provider charge is reconciled
    Then the order becomes "paid" and exactly one practice becomes "Received"
    When a valid signed successful-payment webhook with a distinct event ID and charge ID is reconciled to the same order
    Then the order remains "paid"
    And "payment.duplicate_charge_detected" is appended once to the payment journal
    And exactly one remediation or refund case is opened and staff is paged
    And the customer receives one duplicate-charge acknowledgement
    But no second practice, "Received" email, order, or customer-visible price is created
    When the second webhook is retried
    Then no second remediation case, page, acknowledgement, journal event, or state change occurs

