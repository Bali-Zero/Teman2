import { afterEach, describe, expect, it, vi } from "vitest";

// COMMIT is read at module scope (baked into the build), so each case sets the env and then
// re-imports a fresh copy of the route.
async function healthCommit(): Promise<string | null> {
  vi.resetModules();
  const { GET } = await import("./route");
  const body = await (await GET()).json();
  expect(body.status).toBe("ok");
  return body.commit;
}

describe("GET /api/health commit", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("reports VERCEL_GIT_COMMIT_SHA for a git-sourced deployment", async () => {
    vi.stubEnv("VERCEL_GIT_COMMIT_SHA", "a".repeat(40));
    vi.stubEnv("BUILD_COMMIT_SHA", "b".repeat(40));
    expect(await healthCommit()).toBe("a".repeat(40));
  });

  it("falls back to BUILD_COMMIT_SHA for a CLI upload with no git metadata", async () => {
    vi.stubEnv("VERCEL_GIT_COMMIT_SHA", "");
    vi.stubEnv("BUILD_COMMIT_SHA", "b".repeat(40));
    expect(await healthCommit()).toBe("b".repeat(40));
  });

  it("is null when neither source exists", async () => {
    vi.stubEnv("VERCEL_GIT_COMMIT_SHA", "");
    vi.stubEnv("BUILD_COMMIT_SHA", "");
    expect(await healthCommit()).toBeNull();
  });
});
