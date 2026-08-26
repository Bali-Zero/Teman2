@red-first @journey @upload @ocr
Feature: Corrupt or unreadable photo upload is recoverable
  # RED-FIRST: the upload and local OCR worker must be real; no fixture may bypass byte validation.

  Scenario: Declared image content with corrupt or unreadable bytes is rejected safely
    Given a creator-bound authenticated customer has an unpaid GARUDA intake draft
    And a synthetic upload declares an allowed image media type but contains corrupt or unreadable bytes
    When the customer uploads the synthetic file from a phone browser
    Then the upload receives the stable customer-safe outcome "UNREADABLE_DOCUMENT"
    And the customer is instructed to retake or replace the image
    And no extracted field is accepted or silently defaulted
    And review confirmation and checkout remain disabled
    And staff sees one quality-failure work item without fabricated OCR values
    And the raw bytes, extracted fragments, account identity, and opaque identifiers are absent from URLs, logs, metrics labels, and analytics
    When the same upload command is retried with the same idempotency identity
    Then the same outcome is returned without a second work item, document row, email, or OCR job

