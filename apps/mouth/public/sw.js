/**
 * Bali Zero Service Worker
 *
 * Strategia: Stale-While-Revalidate per API
 *            Cache-First per assets statici
 */

const CACHE_NAME = "balizero-v7";
const STATIC_CACHE = "balizero-static-v7";
const API_CACHE = "balizero-api-v7";

// Assets da cacheare al momento dell'install.
// "/offline" rimosso: su subdomini (my/kita) viene redirected cross-origin al
// dominio principale e bloccato da CORS, facendo fallire l'intero cache.addAll.
const STATIC_ASSETS = ["/"];

// Install: Cache static assets
self.addEventListener("install", (event) => {
  console.log("[SW] Install v5");

  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => {
        console.log("[SW] Caching static assets");
        return cache.addAll(STATIC_ASSETS);
      })
      .catch((err) => {
        console.warn("[SW] Failed to cache some assets:", err);
      }),
  );

  // Activate immediately
  self.skipWaiting();
});

// Activate: Clean old caches
self.addEventListener("activate", (event) => {
  console.log("[SW] Activate v5");

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            return (
              name.startsWith("balizero-") &&
              name !== STATIC_CACHE &&
              name !== API_CACHE &&
              name !== CACHE_NAME
            );
          })
          .map((name) => {
            console.log("[SW] Deleting old cache:", name);
            return caches.delete(name);
          }),
      );
    }),
  );

  // Claim clients immediately
  self.clients.claim();
});

// Fetch: Cache strategies
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") return;

  // Skip chrome-extension requests
  if (url.protocol === "chrome-extension:") return;

  // Skip cross-origin requests (prevents CORS redirect issues)
  if (url.origin !== self.location.origin) return;

  // Skip RSC navigation requests (these may redirect cross-origin)
  if (url.searchParams.has("_rsc")) return;

  // Skip navigation requests entirely. Next.js SSR + Vercel edge caching
  // already serve HTML correctly; intercepting them only risks serving a
  // stale "You are offline" fallback when a transient fetch() blip happens
  // (browsers can throw ERR_INSUFFICIENT_RESOURCES under load even while
  // online). The PWA offline page can come back later when we have a real
  // offline strategy per route.
  if (request.mode === "navigate") return;

  // 1. Static assets: Cache First
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // 2. API calls: Stale While Revalidate
  if (isAPIRequest(url)) {
    event.respondWith(staleWhileRevalidate(request, API_CACHE));
    return;
  }

  // 3. Everything else: Network First (no offline HTML fallback)
  event.respondWith(networkFirst(request));
});

// Helpers
function isStaticAsset(url) {
  // Next.js JS/CSS chunks are immutable (hash in filename) — skip SW cache,
  // let Vercel CDN handle them. Only cache images and fonts.
  if (url.pathname.startsWith("/_next/static/chunks/")) return false;
  return (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/_next/image/") ||
    url.pathname.match(/\.(png|jpg|jpeg|gif|webp|avif|svg|woff2?)$/)
  );
}

function isAPIRequest(url) {
  return url.pathname.startsWith("/api/");
}

// Cache First: Usa cache, se non c'e' fetcha
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached) {
    return cached;
  }

  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    return new Response("Offline", { status: 503 });
  }
}

// Stale While Revalidate: Ritorna cache, aggiorna in background.
// Se cache e network sono entrambi vuoti, restituiamo comunque una Response
// 503 sintetica — respondWith NON può rimanere senza una Response valida
// (il browser emette "Failed to convert value to 'Response'").
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

// Network First: Prova network, fallback a cache
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    return networkResponse;
  } catch (error) {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);

    if (cached) {
      return cached;
    }

    // Note: navigation requests are excluded from this handler entirely
    // (see fetch listener), so the offline HTML fallback no longer lives
    // here. API/asset fetches fall through to the 503 JSON below.

    // Never throw from fetch handler — Service Worker fetch listener must
    // always respondWith a valid Response, otherwise the browser reports
    // "Failed to convert value to 'Response'" and the navigation stalls.
    return new Response(
      JSON.stringify({ error: "offline", detail: "Network unavailable" }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}

// Message handler per aggiornamenti
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

console.log("[SW] Service Worker loaded v5");
