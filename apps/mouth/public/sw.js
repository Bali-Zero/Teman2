/**
 * Bali Zero Service Worker
 *
 * Minimal PWA shell:
 *   - /api/* → Stale-While-Revalidate (cached JSON reused instantly, refreshed
 *     in background)
 *   - everything else → NOT intercepted (browser/CDN handle it)
 *
 * Previous iterations tried to cache static chunks/fonts/images. That caused
 * Chrome to hit ERR_INSUFFICIENT_RESOURCES under parallel load because the
 * SW-mediated cache.open + match + fetch pipeline exceeds the per-origin
 * socket budget when Next.js hydrates dozens of chunks in parallel. We keep
 * the SW scope tight to pure API data now.
 */

const VERSION = "v8";
const API_CACHE = `balizero-api-${VERSION}`;

function isAPIRequest(url) {
  return url.pathname.startsWith("/api/");
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse.ok) {
        cache.put(request, networkResponse.clone());
      }
      return networkResponse;
    })
    .catch(
      () =>
        cached ||
        new Response(
          JSON.stringify({ error: "offline", detail: "Network unavailable" }),
          {
            status: 503,
            headers: { "Content-Type": "application/json" },
          },
        ),
    );

  return cached || fetchPromise;
}

self.addEventListener("install", () => {
  // Nothing to pre-cache. skipWaiting so updated SWs take effect on reload.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Drop any cache from older SW versions so they don't leak memory.
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n.startsWith("balizero-") && n !== API_CACHE)
            .map((n) => caches.delete(n)),
        ),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== "GET") return;
  if (url.protocol === "chrome-extension:") return;
  if (url.origin !== self.location.origin) return;
  if (url.searchParams.has("_rsc")) return;
  if (!isAPIRequest(url)) return;

  event.respondWith(staleWhileRevalidate(request, API_CACHE));
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

console.log(`[SW] Service Worker loaded ${VERSION}`);
