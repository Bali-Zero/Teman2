import { describe, expect, it } from "vitest";
import { GET, HEAD } from "./route";

describe("legacy tax gap redirect", () => {
  it.each([GET, HEAD])(
    "permanently redirects to the canonical tax gap route",
    (handler) => {
      const response = handler(
        new Request("https://preview.example/tax/gap?source=legacy"),
      );

      expect(response.status).toBe(308);
      expect(response.headers.get("location")).toBe(
        "https://preview.example/taxes/gap?source=legacy",
      );
    },
  );
});
