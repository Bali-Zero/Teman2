@red-first @journey @happy-path
Feature: Eligible customer completes a GARUDA VOA practice
  # RED-FIRST: bind every step to real HTTP, browser, email, webhook, database, and portal surfaces.
  # Undefined or pending steps, mocks, stubs, and 404/405/501 responses fail this contract.

  Background:
    Given one unambiguous active signed retention policy authorizes the public funnel row type
    And the signed rules and price truth sheets are inside their declared freshness windows
    And the provider-agnostic payment sandbox accepts signed webhook fixtures
    And a synthetic issuance request satisfies every grounded gate in "apps/backend-rag/backend/services/garuda_flow/intake.py:build_verdict"
    And the customer has seen and explicitly acknowledged the policy-derived storage, purpose, duration, and self-deletion notice

  Scenario: Eligibility to delivered visa follows authoritative state and evidence
    When the customer submits the public eligibility questions
    Then the preliminary verdict is "ACCEPT"
    And it does not represent or promise authority approval
    And the result location matches "/visa/voa/<opaque-id>"
    And the opaque identifier has at least 128 effective CSPRNG bits and contains no answer data
    And the eligibility response establishes a creator-bound result session separate from the opaque identifier
    And the identifier alone does not authorize result access
    And only the creator-bound result session can load the pre-account result
    And the result exposes one all-inclusive price from "apps/backend-rag/backend/services/garuda_flow/pricing.py:price_for_case"
    And the result exposes no price component, fee split, PNBP split, or additional government cost
    And the only public Safe Clock checkpoint is "apps/backend-rag/backend/services/garuda_flow/constants.py:PUBLISHED_FILING_DEADLINE_DAYS"
    And no internal checkpoint or escalation offset is present in HTML, JSON, email, or browser telemetry
    And the persisted result is bound to the active signed retention policy
    When the customer requests an account magic link
    Then one magic-link email is queued without personal data in its URL or logs
    When the customer consumes the unused unexpired magic link once
    Then one creator-bound authenticated account session is established
    When the customer uploads a readable synthetic passport photo from a phone browser
    Then local OCR returns customer-visible feedback and prefilled review fields
    And the uploaded bytes and extracted values are absent from URLs, logs, metrics labels, and analytics
    When the customer confirms the review and requests sandbox checkout with a new idempotency key
    Then one order is "created" and advances to "awaiting_payment"
    And exactly one provider checkout session exists for the order
    When the customer browser follows the provider success redirect
    Then the browser observation is "browser_return_observed"
    But the authoritative order remains "awaiting_payment"
    And no practice exists
    When the sandbox sends a valid signed successful-payment webhook
    Then the webhook inbox, append-only payment journal, "paid" state, and transactional outbox commit atomically
    And the order becomes "paid" exactly once
    And exactly one practice becomes "Received"
    And one "Received" email is queued
    When authorized staff advances the practice through "In review", "Submitted", and "Approved"
    Then each real tracker change has one state write, one journal event, and one customer email
    When authorized staff releases the verified visa artifact in the portal
    Then the tracker becomes "Delivered"
    And one "Delivered" email is queued
    And the authenticated customer can retrieve the visa artifact from the portal
    But possession of the opaque result identifier without creator-bound authorization cannot retrieve it
