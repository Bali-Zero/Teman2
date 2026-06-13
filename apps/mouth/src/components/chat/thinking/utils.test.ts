import { describe, it, expect } from "vitest";
import { getDynamicToolMessage } from "./utils";

describe("getDynamicToolMessage", () => {
  it("should format vector_search with query and collection", () => {
    const message = getDynamicToolMessage(
      "vector_search",
      { query: "bali visa", collection_name: "visa_oracle" },
      "Searching..."
    );
    expect(message).toBe('Searching for "bali visa" in visa documents...');
  });

  it("should format get_pricing with service name", () => {
    const message = getDynamicToolMessage(
      "get_pricing",
      { service_name: "E-Visa" },
      "Fetching price..."
    );
    expect(message).toBe('Retrieving price for "E-Visa"...');
  });

  it("should return default label for unknown tool", () => {
    const message = getDynamicToolMessage(
      "unknown_tool",
      {},
      "Processing..."
    );
    expect(message).toBe("Processing...");
  });
});
