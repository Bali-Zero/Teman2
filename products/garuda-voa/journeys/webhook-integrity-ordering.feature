@red-first @journey @payment @webhook @security
Feature: Payment webhooks are authenticated and order-independent
  # RED-FIRST: send bytes to the real sandbox webhook ingress and inspect the real inbox, journal, outbox, and state store.

  Scenario: A late paid event after a refund cannot resurrect the order
    Given one order is "awaiting_payment"
    When a valid signed refund webhook is reconciled before its related paid webhook
    Then the order becomes terminal "refunded"
    And no practice is released
    When the related valid signed paid webhook arrives later
    Then the order remains "refunded"
    And the forbidden transition "refunded" to "paid" is rejected
    And "payment.late_paid_after_refund" is appended once and reconciliation staff is paged
    But no practice, paid email, second refund, or customer-visible paid state is produced
    When either webhook is retried
    Then no state, journal, email, page, refund, or practice is duplicated

  Scenario: A spoofed successful-payment webhook cannot mutate business state
    Given one order is "awaiting_payment"
    When an otherwise valid successful-payment payload arrives with a missing or invalid signature
    Then webhook authentication fails before business reconciliation
    And the order remains "awaiting_payment"
    And no paid journal event, payment email, outbox item, or practice exists
    And only a coarse non-sensitive signature-failure security counter may change
    And the payload, signature, provider reference, order identifier, and customer data are absent from logs and metric labels
    When the browser follows a forged success redirect
    Then the order still remains "awaiting_payment"

