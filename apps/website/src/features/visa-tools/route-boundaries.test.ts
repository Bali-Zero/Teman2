import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { POST as clockPost } from "../../app/api/visa/clock/route";
import { GET as clockGet } from "../../app/api/visa/clock/[hash]/route";
import { POST as matchPost } from "../../app/api/visa/match/route";
import { GET as matchGet } from "../../app/api/visa/match/[hash]/route";
import { publicVisaRequest } from "./public-api";
const origin = "http://localhost:3102";
const clockAnswers = {
  visa_type: "B1",
  entry_date: "2026-08-01",
  in_country_now: true,
};
const post = (kind: string, body: unknown) =>
  new Request(`${origin}/api/visa/${kind}`, {
    method: "POST",
    headers: { origin, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
beforeEach(() => {
  vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", "");
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe("route-level public boundary", () => {
  it("all four route handlers fail closed when unconfigured", async () => {
    const context = { params: Promise.resolve({ hash: "synthetic_only" }) };
    const responses = await Promise.all([
      clockPost(post("clock", clockAnswers)),
      matchPost(post("match", {})),
      clockGet(new Request(`${origin}/api/visa/clock/synthetic_only`), context),
      matchGet(new Request(`${origin}/api/visa/match/synthetic_only`), context),
    ]);
    expect(responses.map((response) => response.status)).toEqual([
      503, 503, 503, 503,
    ]);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("does not install a VOA API or a dynamic page that would shadow authentication", () => {
    expect(existsSync(resolve("src/app/api/visa/voa"))).toBe(false);
    expect(existsSync(resolve("src/app/visa/voa/[hash]"))).toBe(false);
    expect(
      readFileSync(resolve("src/features/visa-tools/voa-form.tsx"), "utf8"),
    ).not.toMatch(/\bfetch\s*\(|\/api\/garuda|\/api\/visa\/voa/);
  });
  it("rejects a stalled request body within the bounded reading window", async () => {
    vi.useFakeTimers();
    vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", "http://127.0.0.1:9911");
    const stalled = new ReadableStream<Uint8Array>({ start() {} });
    const request = new Request(`${origin}/api/visa/clock`, {
      method: "POST",
      headers: { origin, "content-type": "application/json" },
      body: stalled,
      duplex: "half",
    } as RequestInit);
    const response = publicVisaRequest(request, "clock");
    await vi.advanceTimersByTimeAsync(8001);
    expect((await response).status).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("reports network and upstream body timeouts without fabricating a result", async () => {
    vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", "http://127.0.0.1:9911");
    vi.mocked(fetch).mockRejectedValueOnce(
      new DOMException("timed out", "TimeoutError"),
    );
    expect((await clockPost(post("clock", clockAnswers))).status).toBe(503);
    vi.useFakeTimers();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(new ReadableStream({ start() {} })),
    );
    const pending = clockGet(new Request(`${origin}/result`), {
      params: Promise.resolve({ hash: "synthetic" }),
    });
    await vi.advanceTimersByTimeAsync(8001);
    expect((await pending).status).toBe(503);
  });
  it("projects Match saved results without bearer or additional private fields", async () => {
    vi.stubEnv("WEBSITE_VISA_PUBLIC_BASE_URL", "http://127.0.0.1:9911");
    const result = {
      hash: "synthetic",
      recommended_visa: "E33G",
      reason: "Synthetic fixture only",
      estimated_cost_idr: null,
      cost_source: null,
      processing_days: 10,
      pre_arrival_steps: ["Review evidence"],
      alternatives: ["C1"],
      referral_mode: false,
      nationality: "ITA",
      purpose: "work_remote",
      duration_months: 12,
      budget_band: "under_50m",
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      Response.json({ ...result, session_jwt: "discard", account: "discard" }),
    );
    const response = await matchGet(new Request(`${origin}/result`), {
      params: Promise.resolve({ hash: "synthetic" }),
    });
    expect(await response.json()).toEqual(result);
  });
});
describe("preserved Second Home source contracts", () => {
  it("retains every pure engine module byte-for-byte from the current source", () => {
    const source = resolve("../mouth/src/lib/secondhome-studio");
    const modules = readdirSync(source).filter((file) => file.endsWith(".ts"));
    expect(modules.length).toBeGreaterThan(5);
    for (const module of modules)
      expect(
        readFileSync(
          resolve("src/features/visa-tools/secondhome/engine", module),
          "utf8",
        ),
        module,
      ).toBe(readFileSync(resolve(source, module), "utf8"));
  });
  it.each(["en", "it", "id"])(
    "retains the complete %s Second Home translation subtree",
    (locale) => {
      const source = JSON.parse(
        readFileSync(
          resolve(`../mouth/src/i18n/locales/${locale}.json`),
          "utf8",
        ),
      );
      const retained = JSON.parse(
        readFileSync(
          resolve(`src/features/visa-tools/secondhome/messages/${locale}.json`),
          "utf8",
        ),
      );
      expect(retained).toEqual({ secondHome: source.secondHome });
    },
  );
});
