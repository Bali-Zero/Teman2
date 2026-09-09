import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { publicVisaRequest, validDate } from "./public-api";
const clock = {
  hash: "synthetic_123",
  visa_type: "B1",
  entry_date: "2026-08-01",
  expiry_date: "2026-08-30",
  extensions_possible: 1,
  extension_days: 30,
  checkpoints: [
    {
      label: "D-7",
      at: "2026-08-23",
      title: "Prepare",
      body: "Review your permit.",
    },
  ],
};
const request = (body: unknown, origin = "http://localhost:3100") =>
  new Request("http://localhost:3100/api/visa/clock", {
    method: "POST",
    headers: {
      origin,
      "content-type": "application/json",
      cookie: "private=discard",
      authorization: "Bearer discard",
    },
    body: JSON.stringify(body),
  });
const answers = {
  visa_type: "B1",
  entry_date: "2026-08-01",
  in_country_now: true,
};
beforeEach(() => {
  vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", "http://127.0.0.1:9911");
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
describe("public visa boundaries", () => {
  it("fails closed with no upstream configured and sends nothing", async () => {
    vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", "");
    const res = await publicVisaRequest(request(answers), "clock");
    expect(res.status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([
    "http://example.com",
    "https://user:secret@example.com",
    "https://example.com/path",
    "https://example.com/?key=secret",
  ])("rejects unsafe configured base %s", async (base) => {
    vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", base);
    expect((await publicVisaRequest(request(answers), "clock")).status).toBe(
      503,
    );
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects cross-origin submissions", async () => {
    expect(
      (
        await publicVisaRequest(
          request(answers, "https://unrelated.test"),
          "clock",
        )
      ).status,
    ).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([
    { ...answers, name: "not-permitted" },
    { ...answers, entry_date: "2026-02-30" },
    { ...answers, in_country_now: false },
  ])("rejects invalid or additional answers", async (body) => {
    expect((await publicVisaRequest(request(body), "clock")).status).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("caps request size", async () => {
    expect(
      (
        await publicVisaRequest(
          request({ ...answers, visa_type: "X".repeat(5000) }),
          "clock",
        )
      ).status,
    ).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("forwards only public fields and returns only the result reference", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      Response.json({
        ...clock,
        session_jwt: "never-return",
        result_url: "https://unrelated.test",
      }),
    );
    const res = await publicVisaRequest(request(answers), "clock");
    expect(await res.json()).toEqual({ hash: clock.hash });
    const [url, options] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toBe("http://127.0.0.1:9911/api/visa/clock");
    expect(options).toMatchObject({
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      body: JSON.stringify(answers),
    });
    expect(options?.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
    });
    expect(options?.signal).toBeInstanceOf(AbortSignal);
  });
  it("projects the public saved result and discards upstream session tokens and cookies", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      Response.json(
        { ...clock, session_jwt: "secret", other: "private" },
        { headers: { "set-cookie": "auth=secret" } },
      ),
    );
    const res = await publicVisaRequest(
      new Request(`http://localhost:3100/api/visa/clock/${clock.hash}`),
      "clock",
      clock.hash,
    );
    expect(await res.json()).toEqual(clock);
    expect(res.headers.get("set-cookie")).toBeNull();
    expect(res.headers.get("cache-control")).toBe("no-store");
  });
  it("fails closed for malformed, mismatched and oversized upstream responses", async () => {
    for (const value of [
      { ...clock, hash: "other" },
      { ...clock, expiry_date: "tomorrow" },
      { ...clock, checkpoints: [{ body: "x".repeat(70000) }] },
    ]) {
      vi.mocked(fetch).mockResolvedValueOnce(Response.json(value));
      expect(
        (
          await publicVisaRequest(
            new Request("http://localhost:3100/result"),
            "clock",
            clock.hash,
          )
        ).status,
      ).toBe(503);
    }
  });
  it("preserves not-found and rate-limit states, suppressing upstream error details", async () => {
    for (const status of [404, 429, 500]) {
      vi.mocked(fetch).mockResolvedValueOnce(
        Response.json({ secret: "not-for-browser" }, { status }),
      );
      const res = await publicVisaRequest(
        new Request("http://localhost:3100/result"),
        "clock",
        clock.hash,
      );
      expect(res.status).toBe(status === 500 ? 503 : status);
      expect(await res.text()).not.toContain("not-for-browser");
    }
  });
  it("rejects unsupported methods and invalid references before forwarding", async () => {
    expect(
      (
        await publicVisaRequest(
          new Request("http://localhost:3100/result", { method: "DELETE" }),
          "clock",
          clock.hash,
        )
      ).status,
    ).toBe(404);
    expect(
      (
        await publicVisaRequest(
          new Request("http://localhost:3100/result"),
          "clock",
          "../auth",
        )
      ).status,
    ).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("accepts a canonical Match request without adding fields", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      Response.json({ hash: "synthetic_match" }),
    );
    const body = {
      nationality: "ITA",
      purpose: "work_remote",
      duration_months: 12,
      budget_band: "under_50m",
    };
    const res = await publicVisaRequest(request(body), "match");
    expect(res.status).toBe(200);
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))).toEqual(
      body,
    );
  });
  it("does not promote invalid calendar dates", () => {
    expect(validDate("2024-02-29")).toBe(true);
    expect(validDate("2026-02-29")).toBe(false);
  });
});
