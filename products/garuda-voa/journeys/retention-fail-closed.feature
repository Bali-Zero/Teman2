@red-first @journey @retention @fail-closed
Feature: Public persistence requires signed retention authority
  # RED-FIRST: query the real policy authority extended from migrations 264, 266, and 268 and inspect the real store.
  # TODO(ground): confirm whether "signed" requires a cryptographic signature in addition to approved append-only policy authority.

  Scenario Outline: Invalid retention authority prevents every public-surface write
    Given the retention authority for the GARUDA public result row is "<policy_state>"
    When a synthetic customer submits otherwise eligible answers
    Then the surface fails closed with "PERSISTENCE_POLICY_UNAVAILABLE"
    And no result row, opaque result identifier, magic link, order, payment session, practice, or customer email is created
    And no price or deadline is quoted
    And the customer receives a non-personalized WhatsApp handoff
    And submitted answers and personal data are absent from URLs, logs, analytics, and metric labels
    And only a coarse non-sensitive policy-failure counter may change

    Examples:
      | policy_state |
      | absent |
      | unsigned-or-unapproved |
      | ambiguous-multiple-active |
      | expired-or-inactive |

  Scenario: Missing explicit acknowledgement prevents persistence
    Given one unambiguous active signed retention policy authorizes the GARUDA public result row
    And the customer has not explicitly acknowledged the policy-derived storage, purpose, duration, and self-deletion notice
    When the customer submits otherwise eligible answers
    Then no result row, opaque result identifier, magic link, order, payment session, or practice is created
    And the customer is required to review and explicitly acknowledge the notice
    And acknowledgement is not inferred from page view, button press, or a preselected control
    And submitted answers and personal data are absent from URLs, logs, analytics, and metric labels

  Scenario: The database derives retention from the one active policy
    Given one unambiguous active signed policy defines the retention interval, anchor, effective period, approver, and approval reference
    When the public surface persists an acknowledged synthetic result
    Then the row binds the exact active policy identity
    And the database derives its retention deadline from that policy and recorded anchor
    And the derived deadline is later than the anchor
    When a caller supplies a different retention deadline or policy identity
    Then the write fails atomically and no result or opaque identifier is created

  Scenario: Bounded purge skips legal hold and leaves identifier-free evidence
    Given synthetic policy-bound rows exist beyond the active policy deadline
    And one expired row has active legal-hold history and one does not
    When the bounded retention purge runs under the authorized primitive
    Then only the eligible non-held row is erased
    And the held row and append-only legal-hold history remain
    And the purge batch cannot exceed its governed bound
    And surviving retention evidence is aggregate only with no applicant, result, decision, document, order, or payment identifier
    When the purge command is retried
    Then no row, evidence count, or purge event is duplicated

  Scenario: Retention authority cannot be bypassed through public execution
    Given the GARUDA extension follows the security-definer boundary established by migrations 264 and 268
    Then execution is revoked from "PUBLIC"
    And the policy-writer authority is separated from the application data writer
    And the security-definer search path and ownership are fixed to the approved roles
    When an unauthorized caller attempts a policy bind, deadline override, purge, or erasure
    Then the database denies it without a data mutation or identifier-bearing error
    And activation fails closed if any privilege or ownership assertion is false

  Scenario: Legacy GARUDA rows become governed rather than exempt
    Given a legacy "garuda_voa_checks" row predates the GARUDA retention extension
    And no duration is inferred before an active signed policy covers that row type
    When the extension and its active signed policy become authoritative
    Then the legacy row binds or becomes purge-eligible under the recorded policy anchor
    And it receives no permanent exemption or invented retention duration
    And any purge evidence that survives is aggregate only and identifier-free
