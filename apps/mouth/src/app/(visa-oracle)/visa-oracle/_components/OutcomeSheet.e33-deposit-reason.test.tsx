import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  buildEngineOutcome,
  SUPPORT_REASON_COPY,
} from "../_lib/engine-adapter";
import { makeVisaOracleResponse } from "../_lib/visa-oracle-test-fixture";
import { OutcomeSheet } from "./OutcomeSheet";

afterEach(cleanup);

// e33-ownname-dead-end-reason: the sentence the adapter derives must reach the
// visitor's screen, not only the adapter's return value. The pack decides the
// reason CODE (AGE_BELOW_55 / OPERATIONAL, replayed by the observer); this
// renders the sheet the visitor sees for that code.
function outcomeFor(code: string, bank: string, name: string) {
  const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
  response.decision.no_path_reasons[0].code = code;
  const outcome = buildEngineOutcome(response, {
    facts: {
      category: "second_home",
      secondhome_basis: "bank_deposit",
      secondhome_deposit_usd: "130000",
      secondhome_state_bank: bank,
      secondhome_own_name: name,
    },
  });
  if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("unexpected");
  return outcome;
}

describe("OutcomeSheet renders the Second Home deposit reason", () => {
  it.each([
    ["AGE_BELOW_55", "no", "yes"],
    ["AGE_BELOW_55", "yes", "no"],
    ["OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES", "no", "no"],
  ])(
    "%s with bank=%s, own name=%s shows the holder sentence (EN)",
    (code, bank, name) => {
      const { container } = render(
        <OutcomeSheet
          language="en"
          outcome={outcomeFor(code, bank, name)}
          facts={{}}
        />,
      );
      const text = container.textContent ?? "";
      expect(text).toContain("USD 130,000");
      expect(text).toContain("at an Indonesian state-owned bank.");
      expect(text).not.toContain(SUPPORT_REASON_COPY.AGE_BELOW_55.en);
    },
  );

  it("shows the Indonesian sentence in ID", () => {
    const { container } = render(
      <OutcomeSheet
        language="id"
        outcome={outcomeFor("AGE_BELOW_55", "no", "yes")}
        facts={{}}
      />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("di bank milik negara Indonesia.");
    expect(text).toContain("USD 130.000");
    expect(text).not.toContain(SUPPORT_REASON_COPY.AGE_BELOW_55.id);
  });
});
