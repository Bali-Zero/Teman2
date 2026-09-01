@red-first @journey @upload @ocr @staff-view
Feature: Low-confidence OCR requires explicit resolution
  # RED-FIRST: exercise the real local OCR score, customer review, and staff queue surfaces.
  # Binding guardrail: G-OCR-LOCAL.
  # TODO(ground): approve the OCR confidence threshold, stable reason codes, and localized customer instruction.

  Scenario: Low-confidence fields are not presented as verified facts
    Given a creator-bound authenticated customer has an unpaid GARUDA intake draft
    And a synthetic readable photo yields at least one field below the grounded OCR confidence threshold
    When local OCR completes
    Then the customer sees a customer-safe low-confidence instruction
    And each uncertain field is marked for explicit confirmation, correction, or re-upload
    And no uncertain value is silently accepted as verified
    And checkout remains disabled until every required uncertain field is resolved
    And staff sees one "LOW_CONFIDENCE" work item with field paths and confidence values
    But staff-only diagnostics and extracted personal values are absent from the customer response, URLs, logs, metrics labels, and analytics
    When the same OCR completion event is retried
    Then no second work item, customer notification, or field mutation is produced

  Scenario: Optional cloud reinforcement receives redacted material only
    Given local-first OCR has produced a low-confidence result
    And the governed workflow elects to request cloud reinforcement
    When the egress boundary is observed for that request
    Then redaction completes before any cloud connection is opened
    And the outbound material contains no raw image, personal data, document number, contact value, or opaque result identifier
    And the cloud result may reinforce but cannot replace the local OCR evidence or customer confirmation
    When redaction cannot prove the outbound material safe
    Then cloud reinforcement is skipped and the customer remains on the manual confirmation or re-upload path
    And no raw material leaves the local boundary
