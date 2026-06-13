import { describe, it, expect } from "vitest";
import { getDynamicToolMessage } from "./utils";

describe("getDynamicToolMessage", () => {
  it("verifies localized tool messages", () => {
    expect(getDynamicToolMessage("vector_search", { query: "visa", collection: "visa_oracle" }))
      .toBe('Searching for "visa" in visa documents...');
    expect(getDynamicToolMessage("get_pricing", { service_name: "E-Visa" }))
      .toBe('Retrieving price for "E-Visa"...');
  });
});
