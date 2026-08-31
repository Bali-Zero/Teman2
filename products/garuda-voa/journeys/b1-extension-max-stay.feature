@red-first @journey @b1 @extension @safe-clock
Feature: B1 extension respects the inclusive maximum-stay edge
  # RED-FIRST: derive the boundary from engine symbols; no literal stay duration is permitted in this contract.

  Background:
    Given the B1 stay metadata is loaded from "apps/backend-rag/backend/services/visa_check/catalogue.py:VISA_META[VisaType.B1]"
    And the inclusive guard is "apps/backend-rag/backend/services/garuda_flow/constants.py:b1_max_total_stay_exceeded"
    And all other preliminary extension gates pass with the current printed VOA expiry

  Scenario: The last day before the inclusive maximum does not trigger the max-stay decline
    Given the current printed VOA expiry has a day difference of "max_total_stay_days - 1" from arrival
    When the extension eligibility request is evaluated
    Then "EXTENSION_EXCEEDS_MAX_STAY" is absent
    And arrival day is treated as stay day one
    And no customer response exposes an internal Safe Clock checkpoint

  Scenario: The exact day-difference maximum is one stay day too far
    Given the current printed VOA expiry has a day difference of "max_total_stay_days" from arrival
    When the extension eligibility request is evaluated
    Then the verdict is "DECLINE"
    And the stable reason is "EXTENSION_EXCEEDS_MAX_STAY"
    And no price or checkout action is present
    And the grounded alternative product and WhatsApp handoff are present
    And no literal stay duration or invented regulatory fact is supplied by the test fixture
