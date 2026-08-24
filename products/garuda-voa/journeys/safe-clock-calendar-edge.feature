@red-first @journey @safe-clock @calendar
Feature: Filing arithmetic respects weekends and Indonesian collective leave
  # RED-FIRST: select fixtures from the real operating-calendar symbols and evaluate through the real eligibility surface.

  Background:
    Given the closure source is "apps/backend-rag/backend/services/garuda_flow/operating_calendar.py:OPERATING_CALENDAR"
    And the filing function is "apps/backend-rag/backend/services/garuda_flow/operating_calendar.py:last_open_day_before"
    And the synthetic request case type is "apps/backend-rag/backend/services/garuda_flow/intake.py:CaseType.ISSUANCE"
    And every non-calendar preliminary gate passes for the synthetic request

  Scenario: A weekend immediately before entry is skipped at the filing edge
    Given an entry date inside calendar coverage whose preceding closure run includes a weekend
    And the expected filing cutoff is computed by "last_open_day_before(entry_date)"
    When eligibility is evaluated on that exact open cutoff day
    Then the calendar edge does not add "ARRIVAL_TOO_SOON"
    When the same request is evaluated after that cutoff
    Then the verdict is "DECLINE" with "ARRIVAL_TOO_SOON"
    And the customer receives the grounded alternative and WhatsApp handoff
    And no customer surface contains an internal Safe Clock checkpoint or escalation offset
    And no public Safe Clock checkpoint other than "apps/backend-rag/backend/services/garuda_flow/constants.py:PUBLISHED_FILING_DEADLINE_DAYS" can be rendered

  Scenario: Cuti bersama is closed and the cutoff moves to the prior open day
    Given an entry date selected from a closure whose kind is "apps/backend-rag/backend/services/garuda_flow/operating_calendar.py:HolidayKind.CUTI_BERSAMA"
    And the expected filing cutoff is computed by "last_open_day_before(entry_date)"
    Then the cutoff is strictly earlier than the cuti-bersama date
    And the cutoff is an open day according to the same operating calendar
    When eligibility is evaluated on the exact cutoff day
    Then the cuti-bersama edge does not add "ARRIVAL_TOO_SOON"
    When eligibility is evaluated after the cutoff
    Then the verdict is "DECLINE" with "ARRIVAL_TOO_SOON"
    And the customer receives the grounded alternative and WhatsApp handoff without an invented date
