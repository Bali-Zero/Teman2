import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

type ServiceWorkerListener = (event: {
  request?: { method: string; url: string };
  respondWith?: ReturnType<typeof vi.fn>;
  waitUntil?: ReturnType<typeof vi.fn>;
}) => void;

function loadServiceWorker() {
  const listeners = new Map<string, ServiceWorkerListener>();
  const cache = {
    match: vi.fn(),
    put: vi.fn(),
  };
  const caches = {
    open: vi.fn().mockResolvedValue(cache),
    keys: vi.fn().mockResolvedValue(["balizero-api-v8"]),
    delete: vi.fn().mockResolvedValue(true),
  };
  const self = {
    location: { origin: "https://my.balizero.com" },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
    addEventListener: vi.fn((type: string, listener: ServiceWorkerListener) => {
      listeners.set(type, listener);
    }),
  };

  const source = readFileSync(join(process.cwd(), "public", "sw.js"), "utf8");
  runInNewContext(source, {
    self,
    caches,
    fetch: vi.fn(),
    URL,
    Response,
    console: { log: vi.fn() },
  });

  return { listeners, caches };
}

describe("service worker cache policy", () => {
  it("never intercepts authenticated portal API reads", () => {
    const { listeners, caches } = loadServiceWorker();
    const respondWith = vi.fn();

    listeners.get("fetch")?.({
      request: {
        method: "GET",
        url: "https://my.balizero.com/api/portal/process/required-documents?as_client=12177",
      },
      respondWith,
    });

    expect(respondWith).not.toHaveBeenCalled();
    expect(caches.open).not.toHaveBeenCalled();
  });

  it("deletes legacy API caches during activation", async () => {
    const { listeners, caches } = loadServiceWorker();
    let activation: Promise<unknown> | undefined;

    listeners.get("activate")?.({
      waitUntil: vi.fn((promise: Promise<unknown>) => {
        activation = promise;
      }),
    });
    await activation;

    expect(caches.delete).toHaveBeenCalledWith("balizero-api-v8");
  });
});
