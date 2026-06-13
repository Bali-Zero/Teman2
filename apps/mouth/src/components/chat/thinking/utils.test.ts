import { describe, it, expect } from "vitest";
import { getDynamicToolMessage } from "./utils";

describe("getDynamicToolMessage", () => {
  it("should format vector_search with query and collection in English", () => {
    const message = getDynamicToolMessage(
      "vector_search",
      { query: "bali visa", collection: "visa_oracle" }
    );
    expect(message).toBe('Searching for "bali visa" in visa documents...');
  });

  it("should format get_pricing with service name in English", () => {
    const message = getDynamicToolMessage(
      "get_pricing",
      { service_name: "E-Visa" }
    );
    expect(message).toBe('Retrieving price for "E-Visa"...');
  });

  it("should return English fallback for unknown tool", () => {
    const message = getDynamicToolMessage(
      "unknown_tool",
      {}
    );
    expect(message).toBe("Processing with unknown_tool...");
  });
});
