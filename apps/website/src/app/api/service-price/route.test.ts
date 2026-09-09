import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";
import { servicePriceIdentities } from "../../../content/service-price-identities";

const identity = Object.values(servicePriceIdentities)[0];
const request = () => new Request(`http://localhost/api/service-price?key=${encodeURIComponent(identity.key)}`);
afterEach(() => vi.unstubAllGlobals());

describe("official service price boundary", () => {
  it("rejects an unknown key before reaching the upstream", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const response = await GET(new Request("http://localhost/api/service-price?key=unknown"));
    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns only a matching scalar price without caching or credentials", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ ...identity, price: "123.456 IDR", verified_on: "2026-09-08", notes: "not public response data" }));
    vi.stubGlobal("fetch", fetch);
    const response = await GET(request());
    expect(await response.json()).toEqual({ available: true, price: "123.456 IDR", verifiedOn: "2026-09-08" });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(fetch).toHaveBeenCalledWith(expect.objectContaining({ pathname: "/api/pricing/service" }), expect.objectContaining({ cache: "no-store", credentials: "omit" }));
  });

  it.each([
    { ...identity, key: "another service", price: "123.456 IDR" },
    { ...identity, category: "another category", price: "123.456 IDR" },
    { ...identity, price: "From 123.456 IDR + fees" },
    { ...identity, price: null },
  ])("abstains from mismatched or non-scalar prices", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body)));
    const response = await GET(request());
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ available: false });
  });

  it("keeps upstream errors out of the response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private upstream diagnostics")));
    const response = await GET(request());
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ available: false });
  });
});
