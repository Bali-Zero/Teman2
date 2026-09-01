@red-first @journey @privacy @deletion
Feature: A customer can erase a public-funnel result without email round trip
  # RED-FIRST: exercise the real result page, creator-bound authorization, erasure primitive, and aggregate store.

  Background:
    Given one pre-account synthetic result exists at "/visa/voa/<opaque-id>"
    And the opaque identifier has at least 128 effective CSPRNG bits
    And one creator-bound result session, separate from the opaque identifier, authorizes the result
    And no order, payment, practice, or statutory record has been created from this result

  Scenario: The result route is private, non-cacheable, and non-indexable
    Given the customer is viewing the result in its creator-bound session
    When the result representation is returned
    Then "Cache-Control" is "no-store, private"
    And "Referrer-Policy" is "no-referrer"
    And "X-Robots-Tag" is "noindex, nofollow, noarchive"
    And the result URL is excluded from every sitemap
    And no personal data appears in its path, query, headers, logs, analytics, or metric labels

  Scenario: Authorized self-service deletion erases the result and leaves only coarse aggregates
    Given the customer is viewing the result in its creator-bound session
    When the customer invokes self-service deletion from the result page
    Then deletion completes without an email round trip
    And the result row, answers, contact data, session binding, and derived per-result fields are atomically erased
    And subsequent authorized retrieval returns the non-enumerating absent-result response
    And the only surviving analytical record is a coarse count by month, decision, nationality, and decline code
    And the survivor contains no exact date, opaque identifier, linkable key, answer, contact value, IP address, user agent, document value, or free text
    And no deleted value appears in any URL
    And the permitted opaque path token appears in no log, analytics event, journal prose, or metric label

  Scenario: An opaque result identifier alone cannot authorize deletion
    Given a different browser has only the result URL and no creator-bound authorization
    When that browser attempts to read or delete the result
    Then it receives the same non-enumerating unauthorized-or-absent response
    And the result and aggregate count remain unchanged
    And no email, token, or identity clue is disclosed

  Scenario: Retrying deletion is idempotent
    Given the authorized customer has already deleted the result
    When the same authorized deletion command is retried
    Then the response remains non-enumerating and successful-or-absent according to the fixed contract
    And no row is recreated
    And no aggregate count, audit event, email, or deletion work item is duplicated
