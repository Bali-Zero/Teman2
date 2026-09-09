// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  analyzeProperty,
  getPropertyZones,
  openPropertyProposal,
  propertyOrigin,
} from "./property.server";
import { getTaxDeadlines, getTaxIcal } from "./tax-calendar.server";

const origin = "http://localhost:3100";
const point = { lat: -8.5, lng: 115.25 };
function request(
  body: unknown = point,
  headers: Record<string, string> = {},
): Request {
  return new Request(`${origin}/api/property/analyze`, {
    method: "POST",
    headers: { Origin: origin, "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
}
function proposal(
  method = "POST",
  source = origin,
  site = "same-origin",
): Request {
  return new Request(`${origin}/api/prime/v2/proposal/synthetic-token`, {
    method,
    headers: { Origin: source, "Sec-Fetch-Site": site },
  });
}
const context = { params: Promise.resolve({ token: "synthetic-token" }) };

describe("property adapters with synthetic upstream only", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    vi.stubEnv("WEBSITE_PROPERTY_API_ORIGIN", "http://localhost:4801");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });
  it("requires explicit origin configuration; there is no production fallback", async () => {
    expect(propertyOrigin("https://property.example.test")).toBe(
      "https://property.example.test",
    );
    for (const value of [
      "",
      "http://external.test",
      "https://name:password@example.test",
      "https://example.test/api",
      "https://example.test?x=1",
    ])
      expect(propertyOrigin(value)).toBeNull();
    vi.stubEnv("WEBSITE_PROPERTY_API_ORIGIN", "");
    expect((await analyzeProperty(request())).status).toBe(503);
    expect((await getPropertyZones()).status).toBe(503);
    expect((await openPropertyProposal(proposal(), context)).status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("rejects cross-site, malformed, oversized and invalid analysis requests before upstream", async () => {
    expect(
      (
        await analyzeProperty(
          request(point, { Origin: "https://external.test" }),
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await analyzeProperty(
          request(point, { "Sec-Fetch-Site": "cross-site" }),
        )
      ).status,
    ).toBe(403);
    expect((await analyzeProperty(request({ ...point, lat: 91 }))).status).toBe(
      400,
    );
    expect(
      (await analyzeProperty(request(point, { "Content-Type": "text/plain" })))
        .status,
    ).toBe(415);
    expect(
      (await analyzeProperty(request({ ...point, ignored: "x".repeat(4100) })))
        .status,
    ).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("uses the fixed analysis path, omits credentials and strips unknown input and output", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        status: "analyzed",
        zone: { code: "TEST" },
        investor_name: "PRIVATE",
        intel_articles: ["PRIVATE"],
      }),
    );
    const response = await analyzeProperty(
      request(
        {
          ...point,
          investor_profile: { name: "PRIVATE" },
          geo_data: { score: 100 },
        },
        { Cookie: "PRIVATE", Authorization: "PRIVATE" },
      ),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:4801/api/prime/v2/analyze");
    expect(init.credentials).toBe("omit");
    expect(init.redirect).toBe("error");
    expect(JSON.parse(init.body)).toEqual(point);
    expect(JSON.stringify(init.headers)).not.toContain("PRIVATE");
    expect(await response.text()).not.toContain("PRIVATE");
  });
  it("does not turn upstream failure or oversized responses into a result", async () => {
    fetchMock.mockResolvedValueOnce(
      Response.json({ error: "PRIVATE" }, { status: 500 }),
    );
    expect(await (await analyzeProperty(request())).json()).toEqual({
      error: "analysis_unavailable",
    });
    fetchMock.mockResolvedValueOnce(
      Response.json({ status: "analyzed", ignored: "x".repeat(2_000_001) }),
    );
    expect((await analyzeProperty(request())).status).toBe(502);
  });
  it("loads only the fixed public geometry path", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ type: "FeatureCollection", features: [] }),
    );
    expect((await getPropertyZones()).status).toBe(200);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:4801/api/prime/zones-geojson",
    );
    expect(fetchMock.mock.calls[0][1].credentials).toBe("omit");
  });
  it("prevents GET, HEAD and cross-site proposal requests from recording a view", async () => {
    expect((await openPropertyProposal(proposal("GET"), context)).status).toBe(
      405,
    );
    expect((await openPropertyProposal(proposal("HEAD"), context)).status).toBe(
      405,
    );
    expect(
      (
        await openPropertyProposal(
          proposal("POST", "https://external.test"),
          context,
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await openPropertyProposal(
          proposal("POST", origin, "cross-site"),
          context,
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await openPropertyProposal(proposal(), {
          params: Promise.resolve({ token: "../../clients" }),
        })
      ).status,
    ).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("opens a proposal only on explicit POST and excludes client identity", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        ...point,
        zone_code: "TEST",
        investor_name: "PRIVATE",
        token: "PRIVATE",
        id: "PRIVATE",
        analysis: {
          status: "analyzed",
          zone: { code: "TEST" },
          investor_email: "PRIVATE",
        },
      }),
    );
    const response = await openPropertyProposal(proposal(), context);
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:4801/api/prime/v2/proposal/synthetic-token",
    );
    expect(fetchMock.mock.calls[0][1].method).toBeUndefined();
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(await response.text()).not.toContain("PRIVATE");
  });
  it.each([404, 410])(
    "preserves proposal status %s without exposing upstream messages",
    async (status) => {
      fetchMock.mockResolvedValue(
        Response.json({ private_error: "PRIVATE" }, { status }),
      );
      const response = await openPropertyProposal(proposal(), context);
      expect(response.status).toBe(status);
      expect(await response.text()).not.toContain("PRIVATE");
    },
  );
});

describe("archive route contracts", () => {
  it("declares its archival state and uses the same filter for JSON and ICS", async () => {
    const request = new Request(
      `${origin}/api/tax-calendar/deadlines?kind=PB1&regency=Badung`,
    );
    const json = await getTaxDeadlines(request).json();
    expect(json.status).toBe("historical_unverified");
    expect(json.verified_upcoming).toBe(false);
    expect(json.deadlines.map((d: { id: string }) => d.id)).toEqual([
      "pb1-badung",
    ]);
    const ics = getTaxIcal(request);
    expect(ics.headers.get("content-type")).toContain("text/calendar");
    expect(await ics.text()).not.toContain("Gianyar");
    expect(getTaxIcal(new Request(`${origin}/?kind=UNKNOWN`)).status).toBe(400);
  });
});
