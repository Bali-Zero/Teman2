import { describe, it, expect, beforeEach } from "vitest";
import { resolveDbUrl } from "../app/lib/db";

describe("resolveDbUrl", () => {
  it("prefers DATABASE_URL_LOCAL when both are set", () => {
    const { url, source } = resolveDbUrl({
      DATABASE_URL_LOCAL: "postgresql://local/nz",
      FLY_TUNNEL_URL: "postgresql://tunnel:15432/nz",
    } as unknown as NodeJS.ProcessEnv);
    expect(url).toBe("postgresql://local/nz");
    expect(source).toBe("local");
  });

  it("falls back to FLY_TUNNEL_URL when local missing", () => {
    const { url, source } = resolveDbUrl({
      FLY_TUNNEL_URL: "postgresql://tunnel:15432/nz",
    } as unknown as NodeJS.ProcessEnv);
    expect(url).toBe("postgresql://tunnel:15432/nz");
    expect(source).toBe("tunnel");
  });

  it("throws with actionable message when neither is set", () => {
    expect(() => resolveDbUrl({} as unknown as NodeJS.ProcessEnv)).toThrow(
      /DATABASE_URL_LOCAL.*FLY_TUNNEL_URL/s,
    );
  });
});
