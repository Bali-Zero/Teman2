@red-first @journey @practice @tracker
Feature: Blocked and rejected practices remain accompanied
  # RED-FIRST: use the real staff command, tracker, email outbox, and authenticated customer portal surfaces.
  # TODO(ground): approve customer-safe blocked/rejected reason codes, localized copy, and staff-only reason schema.

  Scenario: Staff blocks an in-review practice and the customer sees an actionable safe view
    Given a paid synthetic order has one practice in "In review"
    When authorized staff blocks the practice with a grounded safe reason, private staff note, and required customer action
    Then the authoritative practice state is "Blocked"
    And the customer tracker label is "Action required"
    And the customer sees the safe reason, required action, and grounded WhatsApp handoff
    But the customer cannot see the private staff note, document contents, or an internal Safe Clock checkpoint
    And staff sees the block identity, private note, required action, and resume target "In review"
    And one state write, journal event, and action-required email exist
    When the customer supplies the requested action and staff verifies it
    Then the practice resumes to "In review"
    And one resume journal event and one "In review" email exist
    When either staff command is retried
    Then no state write, journal event, email, or work item is duplicated

  Scenario: A post-filing block resumes only to Submitted
    Given a paid synthetic order has one practice in "Submitted"
    When authorized staff records an authority request for customer action
    Then the practice is "Blocked" with stored resume target "Submitted"
    And the customer sees "Action required", a safe next action, and the grounded WhatsApp handoff
    And no private authority note or internal checkpoint is customer-visible
    When staff verifies the completed customer action
    Then the practice resumes to "Submitted"
    But it does not become "In review", "Approved", or "Delivered"

  Scenario: A verified rejection is terminal and includes assistance
    Given a paid synthetic order has one practice in "Submitted"
    When authorized staff records verified authority rejection evidence
    Then the practice becomes terminal "Rejected"
    And the customer sees a customer-safe outcome, the grounded alternative product, and a WhatsApp handoff
    But the customer cannot see private authority notes or evidence
    And one rejection journal event and one accompanied-rejection email exist
    When any actor attempts to advance that practice to "Approved" or "Delivered"
    Then the forbidden transition is rejected without a state write, false tracker state, or customer email

