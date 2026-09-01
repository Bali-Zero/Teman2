@red-first @journey @eligibility @decline @whatsapp
Feature: Every preliminary decline has a grounded alternative and handoff
  # RED-FIRST: the complete engine code set and signed alternative map are read at test runtime.
  # TODO(ground): approve the complete eligibility.py:DeclineCode to alternative PricingTool product-key and localized WhatsApp-copy mapping.
  # TODO(ground): approve deterministic precedence when one verdict contains multiple decline codes.

  Background:
    Given the decline-code set is loaded from "apps/backend-rag/backend/services/garuda_flow/eligibility.py:DeclineCode"
    And a signed mapping binds every decline code to an alternative PricingTool product key and WhatsApp copy
    And the signed rules truth sheet is fresh

  Scenario Outline: The alternative registry is total for every engine decline code
    Given "<decline_code>" is loaded from the real decline-code set
    When the signed accompaniment mapping is resolved for "<decline_code>"
    Then exactly one alternative PricingTool product key is returned
    And exactly one localized customer-safe next action and WhatsApp handoff are returned
    And the mapping entry contains no literal or component price
    And no decline code resolves to a terminal wall or an ungrounded product

    Examples:
      | decline_code |
      | NATIONALITY_NOT_ELIGIBLE |
      | PURPOSE_NOT_ELIGIBLE |
      | GROUP_CASE |
      | PASSPORT_TYPE |
      | PASSPORT_VALIDITY |
      | NOT_SELF_PAY |
      | FEEDBACK_REQUIRED |
      | URGENT_CASE |
      | SPECIAL_PASSPORT |
      | PRIOR_ISSUE |
      | FASTLANE_REQUEST |
      | EXPIRY_UNKNOWN |
      | EXPIRES_TOO_SOON |
      | EXTENSION_ALREADY_USED |
      | ARRIVAL_TOO_SOON |
      | ARRIVAL_DATE_UNCONFIRMED |
      | ARRIVAL_TOO_FAR |
      | EXTENSION_EXCEEDS_MAX_STAY |

  Scenario: Every customer-reachable engine decline is accompanied end to end
    Given a grounded synthetic fixture corpus covers every decline code reachable through "apps/backend-rag/backend/services/garuda_flow/intake.py:build_verdict"
    When each fixture is submitted through the real public eligibility surface
    Then every "DECLINE" response retains its stable engine reasons for authorized staff
    And every "DECLINE" response shows the signed mapped alternative and a working WhatsApp handoff
    And every handoff URL contains no answers, personal data, contact value, document value, or opaque result identifier
    And no "DECLINE" response contains a checkout action or customer-visible price
    And no unreachable code is fabricated as an intake outcome

  Scenario: Multiple decline codes use the approved deterministic precedence
    Given a grounded synthetic request produces at least two distinct engine decline codes
    When the customer submits the public eligibility questions
    Then all stable reasons are retained for authorized staff
    And exactly one primary alternative is selected by the signed precedence rule
    And the customer sees the mapped primary alternative and WhatsApp handoff
    But no price, checkout action, private staff prose, or ungrounded alternative is present
