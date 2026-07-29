/**
 * Bali Zero Service Worker
 *
 * Minimal PWA shell:
 *   - authenticated API responses are NEVER cached or intercepted
 *   - page requests and static assets are left to the browser/CDN
 *
 * Previous iterations cached every /api/* GET with stale-while-revalidate.
 * Besides replaying stale CRM rows after mutations, that policy could retain
 * authenticated responses across sessions on a shared browser. The service
 * worker stays installed for PWA discoverability, but deliberately owns no
 * response cache.
 */

const VERSION = "v9";

self.addEventListener("install", () => {
  // Nothing to pre-cache. skipWaiting so updated SWs take effect on reload.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Purge all historical Bali Zero caches, including authenticated API data
  // written by v8 and earlier.
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith("balizero-"))
            .map((n) => caches.delete(n)),
        ),
      ),
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

console.log(`[SW] Service Worker loaded ${VERSION}`);
