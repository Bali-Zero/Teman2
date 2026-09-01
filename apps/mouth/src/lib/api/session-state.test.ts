import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClientBase } from "./client";

// Level is not under test here (see client.test.ts for that), but the
// module still logs — mock it so nothing hits real console output.
vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Map-based localStorage mock — mirrors client.test.ts so both files agree
// on how a token does/doesn't exist across a fresh ApiClientBase instance.
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("ApiClientBase.hasSession() — cookie-primary session probe", () => {
  let client: ApiClientBase;
  const baseUrl = "https://api.test.com";

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    client = new ApiClientBase(baseUrl);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fast path (local token present)", () => {
    it('returns "authenticated" without hitting the network', async () => {
      client.setToken("a-real-token");
      global.fetch = vi.fn();

      const result = await client.hasSession();

      expect(result).toBe("authenticated");
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe("cookie-only probe (no local token)", () => {
    it('maps a 200 OK to "authenticated"', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });

      await expect(client.hasSession()).resolves.toBe("authenticated");
    });

    it('maps a 401 to "anonymous"', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });

      await expect(client.hasSession()).resolves.toBe("anonymous");
    });

    it('maps a 500 to "unknown"', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });

      await expect(client.hasSession()).resolves.toBe("unknown");
    });

    it('maps a network throw to "unknown"', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error("network down"));

      await expect(client.hasSession()).resolves.toBe("unknown");
    });

    it("probes with credentials included, no-store cache, GET, never through request()", async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
      global.fetch = fetchMock;

      await client.hasSession();

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, options] = fetchMock.mock.calls[0];
      expect(url).toBe(`${baseUrl}/api/bali-zero/conversations/stats`);
      expect(options).toMatchObject({
        credentials: "include",
        cache: "no-store",
      });
      // request() always sends Content-Type + (when present) Authorization —
      // a naked probe must not, since it exists precisely to avoid the
      // request() 401-handler side effects (see the "side-effect zero" suite).
      expect(options?.headers).toBeUndefined();
    });
  });

  describe("dedup", () => {
    it("two concurrent callers collapse into a single fetch", async () => {
      let resolveFetch!: (value: unknown) => void;
      const fetchMock = vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
      );
      global.fetch = fetchMock;

      const p1 = client.hasSession();
      const p2 = client.hasSession();
      resolveFetch({ ok: true, status: 200 });

      const [r1, r2] = await Promise.all([p1, p2]);

      expect(r1).toBe("authenticated");
      expect(r2).toBe("authenticated");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe("caching", () => {
    it('does NOT cache "unknown" — the next call retries the probe', async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce({ ok: false, status: 500 })
        .mockResolvedValueOnce({ ok: true, status: 200 });
      global.fetch = fetchMock;

      const first = await client.hasSession();
      const second = await client.hasSession();

      expect(first).toBe("unknown");
      expect(second).toBe("authenticated");
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it('caches "authenticated" — a second call does not re-fetch', async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
      global.fetch = fetchMock;

      await client.hasSession();
      await client.hasSession();

      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('caches "anonymous" — a second call does not re-fetch', async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401 });
      global.fetch = fetchMock;

      await client.hasSession();
      await client.hasSession();

      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe("cache invalidation", () => {
    it("setToken() clears the cached probe", async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
      await client.hasSession();
      expect(
        (client as unknown as { sessionProbe: unknown }).sessionProbe,
      ).not.toBeNull();

      client.setToken("fresh-token");

      expect(
        (client as unknown as { sessionProbe: unknown }).sessionProbe,
      ).toBeNull();
    });

    it("clearToken() clears the cached probe", async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
      await client.hasSession();
      expect(
        (client as unknown as { sessionProbe: unknown }).sessionProbe,
      ).not.toBeNull();

      client.clearToken();

      expect(
        (client as unknown as { sessionProbe: unknown }).sessionProbe,
      ).toBeNull();
    });

    it("clearToken() invalidation means the next probe re-fetches instead of reusing a stale verdict", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce({ ok: false, status: 401 })
        .mockResolvedValueOnce({ ok: true, status: 200 });
      global.fetch = fetchMock;

      const first = await client.hasSession();
      expect(first).toBe("anonymous");

      client.clearToken();
      const second = await client.hasSession();

      expect(second).toBe("authenticated");
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  describe("side-effect zero", () => {
    let replace: ReturnType<typeof vi.fn>;
    let originalLocation: Location;

    beforeEach(() => {
      replace = vi.fn();
      originalLocation = window.location;
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: { pathname: "/dashboard", search: "", replace },
      });
    });

    afterEach(() => {
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: originalLocation,
      });
    });

    it("never calls clearToken() on a 401 (unlike request())", async () => {
      const clearTokenSpy = vi.spyOn(client, "clearToken");
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });

      const result = await client.hasSession();

      expect(result).toBe("anonymous");
      expect(clearTokenSpy).not.toHaveBeenCalled();
    });

    it("never triggers a redirect on a 401 (unlike request())", async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });

      await client.hasSession();

      expect(replace).not.toHaveBeenCalled();
    });
  });
});
