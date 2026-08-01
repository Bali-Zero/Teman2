import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("GET /portal/dashboard", () => {
  it("permanently redirects the legacy dashboard URL to the portal home", () => {
    const response = GET(
      new Request("https://my.balizero.com/portal/dashboard?source=legacy"),
    );

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(
      "https://my.balizero.com/portal?source=legacy",
    );
  });
});
