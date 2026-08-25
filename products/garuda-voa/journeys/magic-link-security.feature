@red-first @journey @magic-link @security
Feature: Magic links expire and are single use
  # RED-FIRST: real account and email surfaces only; token validators and sessions may not be mocked.
  # GROUNDED 2026-08-25 (was TODO): the lifetime and single-use authority are decided and
  # binding — `x-magic-link` in contracts/openapi.yaml, ttl_minutes 15, single_use true,
  # DECISIONS.md Q1. Session lifetime is a SEPARATE number and is not this one; conflating
  # them is how a 15-minute link becomes a 15-minute portal. The scenarios below deliberately
  # still say "the grounded lifetime policy" rather than "15 minutes" — they assert the
  # BEHAVIOUR, so revising the number stays a one-line contract diff and does not touch them.

  Background:
    Given an eligible persisted result owned by a synthetic customer
    And its opaque result identifier is not an authentication credential

  Scenario: An expired magic link cannot create a session
    Given one magic link was issued under the grounded lifetime policy
    And the authoritative clock is later than that link's expiry
    When the customer attempts to consume the link
    Then authentication fails with the same non-enumerating response used for an invalid link
    And no account session, replacement link, or result authorization is created
    And the token, email address, result identifier, and submitted answers are absent from logs and metrics labels
    And one coarse "magic_link_expired" security counter is recorded

  Scenario: A consumed magic link cannot authenticate twice
    Given one unused unexpired magic link was issued
    When the customer consumes that exact link
    Then one account session is created and the link is atomically marked used
    When the same link is replayed from the same or a different browser
    Then authentication fails with a non-enumerating response
    And no second account session or result authorization is created
    And the replay emits no personal data, token, or opaque identifier into logs
    And one coarse "magic_link_replay" security counter is recorded

