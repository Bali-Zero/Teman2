@red-first @journey @freshness @fail-closed
Feature: Stale truth declines to sell without quoting
  # RED-FIRST: use the real signed truth-sheet registry and public response; frozen fixtures may not bypass freshness evaluation.
  # PARTLY GROUNDED 2026-08-25. Decided and binding: the freshness WINDOWS, in
  # `x-truth-freshness-max-age-days` (contracts/openapi.yaml, DECISIONS.md Q9) —
  # nationality_eligibility 90, rule_constants 180, price_catalogue 90 — and the wire outcome,
  # which differs by source and is load-bearing both ways: a stale nationality list or rule
  # constant DECLINES with ELIGIBILITY_UNCONFIRMED, a stale price catalogue is a 503
  # PRICE_UNRESOLVABLE. The customer is never quoted a price we cannot stand behind, and never
  # told "not eligible" when the truth is "we have not re-verified". Enforced fail-closed at
  # garuda_flow/pricing.py:92.
  # STILL TODO(ground): whether "signed" requires a cryptographic signature over the truth
  # sheet (open, and shared with retention-fail-closed.feature), and the stable customer-safe
  # failure copy.

  Background:
    Given one unambiguous active signed retention policy authorizes the public funnel row type
    And the synthetic eligibility answers would otherwise produce "ACCEPT"

  Scenario Outline: A stale authoritative truth sheet blocks sale before persistence or checkout
    Given the signed "<truth_sheet>" truth sheet is older than its declared freshness window
    And its last known values remain technically readable
    When the customer submits the public eligibility questions
    Then the funnel declines to sell because "<truth_sheet>" is stale
    And no result row, order, provider checkout session, or customer email is created
    And the response contains no price, cached price, price component, deadline, or checkout action
    And the stale value is absent from HTML, JSON, email, analytics, logs, and metrics labels
    And the customer sees the grounded WhatsApp handoff
    And only a coarse non-sensitive freshness-failure counter may survive

    Examples:
      | truth_sheet |
      | rules |
      | price |

  Scenario Outline: Unverifiable truth authority also blocks sale
    Given the "<authority_fault>" truth-sheet authority cannot prove one current signed rules and price set
    When the customer submits the public eligibility questions
    Then the funnel declines to sell
    And no result row, price, deadline, checkout action, order, or provider call exists
    And the customer sees the grounded WhatsApp handoff

    Examples:
      | authority_fault |
      | missing |
      | invalid-signature |
      | ambiguous-active-set |

