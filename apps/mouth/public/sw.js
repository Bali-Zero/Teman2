/**
 * Bali Zero Service Worker
 *
 * Strategia: Stale-While-Revalidate per API
 *            Cache-First per assets statici
 */

const CACHE_NAME = "balizero-v3";
const STATIC_CACHE = "balizero-static-v3";
const API_CACHE = "balizero-api-v3";

// Assets da cacheare immediatamente
const STATIC_ASSETS = ["/", "/offline"];

// Install: Cache static assets
self.addEventListener("install", (event) => {
  console.log("[SW] Install v2");

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
  console.log("[SW] Activate v2");

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

  // 3. Everything else: Network First with offline fallback
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

// Stale While Revalidate: Ritorna cache, aggiorna in background
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
    .catch(() => cached); // Fallback a cache se network fallisce

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

    // Pagina offline fallback
    if (request.mode === "navigate") {
      return new Response(
        `<!DOCTYPE html>
        <html>
          <head><title>Offline - Bali Zero</title></head>
          <body>
            <h1>You are offline</h1>
            <p>Please check your connection and try again.</p>
            <a href="/">Go Home</a>
          </body>
        </html>`,
        {
          status: 200,
          headers: { "Content-Type": "text/html" },
        },
      );
    }

    throw error;
  }
}

// Message handler per aggiornamenti
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

console.log("[SW] Service Worker loaded v3");
