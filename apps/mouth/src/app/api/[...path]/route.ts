import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";

function normalizeBackendBaseUrl(url: string): string {
  return url.replace(/\/+$/, "").replace(/\/api$/, "");
}

function getBackendBaseUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://nuzantara-rag.fly.dev";
  return normalizeBackendBaseUrl(raw);
}

async function proxy(req: NextRequest): Promise<Response> {
  const backendBase = getBackendBaseUrl();
  const url = new URL(req.url);
  const targetUrl = `${backendBase}${url.pathname}${url.search}`;

  // Extract correlation ID for logging
  const correlationId = req.headers.get("X-Correlation-ID") || "unknown";
  const isStreamingEndpoint = url.pathname.includes("/agentic-rag/stream");

  // Log requests in development
  if (process.env.NODE_ENV !== "production") {
    logger.debug(`[Proxy] ${req.method} ${url.pathname} -> ${targetUrl}`, {
      component: "AUTO",
      action: "log",
    });
  }

  // Log streaming requests
  if (isStreamingEndpoint && process.env.NODE_ENV !== "production") {
    logger.debug(`[Proxy] SSE request start: ${req.method} ${url.pathname}`, {
      component: "AUTO",
      action: "log",
      metadata: {
        correlationId,
      },
    });
  }

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  // CRITICAL: Explicitly forward authentication cookies
  // In server-side Next.js, credentials: 'include' doesn't automatically forward cookies
  // We must extract cookies from the request and add them to headers
  const cookies = req.cookies;
  const authCookie = cookies.get("nz_access_token");
  const csrfCookie = cookies.get("nz_csrf_token");

  if (authCookie || csrfCookie) {
    const cookieParts: string[] = [];
    if (authCookie) {
      cookieParts.push(`nz_access_token=${authCookie.value}`);
    }
    if (csrfCookie) {
      cookieParts.push(`nz_csrf_token=${csrfCookie.value}`);
    }

    const existingCookie = headers.get("cookie") || "";
    const newCookieValue = cookieParts.join("; ");
    headers.set(
      "cookie",
      existingCookie ? `${existingCookie}; ${newCookieValue}` : newCookieValue,
    );
  }

  let body: BodyInit | undefined = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const contentType = req.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      // CRITICAL: When passing FormData to fetch, fetch generates its own boundary.
      // We must delete the original Content-Type header so fetch can set the correct one.
      headers.delete("content-type");
      body = (await req.formData()) as unknown as BodyInit;
    } else {
      const buf = await req.arrayBuffer();
      body = buf.byteLength ? buf : undefined;
      // CRITICAL: Preserve Content-Type header for JSON and other body types
      // FastAPI needs this to parse request body correctly
      if (contentType && !headers.has("content-type")) {
        headers.set("content-type", contentType);
      }
    }
  }

  const upstreamStartTime = Date.now();
  try {
    // Debug logging for DELETE with body
    if (req.method === "DELETE" && body) {
      logger.debug("🔍 [PROXY] DELETE with body detected:", {
        component: "AUTO",
        action: "log",
        metadata: {
          method: req.method,
          path: url.pathname,
          hasBody: !!body,
          bodySize: body
            ? typeof body === "string"
              ? body.length
              : "binary"
            : "none",
          contentType: headers.get("content-type"),
          targetUrl,
        },
      });
    }

    // Use redirect: 'manual' and handle redirects ourselves to preserve cookies
    // For DELETE with body, ensure body is properly forwarded
    const requestInit: RequestInit = {
      method: req.method,
      headers,
      redirect: "manual",
      credentials: "include",
    };

    // Only add body if it exists and method supports it
    if (body && ["POST", "PUT", "DELETE", "PATCH"].includes(req.method)) {
      requestInit.body = body;
      logger.debug("🔍 [PROXY] Body added to request:", {
        component: "AUTO",
        action: "log",
        metadata: {
          method: req.method,
          bodyIncluded: true,
          bodyLength: typeof body === "string" ? body.length : "binary",
        },
      });
    }

    let upstream = await fetch(targetUrl, requestInit);

    // Handle redirects manually to preserve cookies (fetch doesn't forward cookies on redirects)
    let redirectCount = 0;
    const maxRedirects = 5;
    while (
      upstream.status >= 300 &&
      upstream.status < 400 &&
      redirectCount < maxRedirects
    ) {
      const location = upstream.headers.get("location");
      if (!location) break;

      // Resolve relative URLs against the backend base
      const redirectUrl = location.startsWith("http")
        ? location.replace(/^http:/, "https:") // Force HTTPS
        : `${backendBase}${location.startsWith("/") ? "" : "/"}${location}`;

      // HTTP 307 and 308 preserve the original method (including POST/DELETE body)
      // HTTP 301, 302, 303 convert POST to GET (standard browser behavior)
      // For DELETE with body, we need to preserve the method and body
      const preserveMethod =
        upstream.status === 307 ||
        upstream.status === 308 ||
        req.method === "DELETE";
      const redirectMethod = preserveMethod
        ? req.method
        : req.method === "POST"
          ? "GET"
          : req.method;

      upstream = await fetch(redirectUrl, {
        method: redirectMethod,
        headers,
        body: preserveMethod && body ? body : undefined, // Preserve body for 307/308
        redirect: "manual",
        credentials: "include",
      });
      redirectCount++;
    }

    const upstreamDuration = Date.now() - upstreamStartTime;

    // Log streaming response status
    if (isStreamingEndpoint && process.env.NODE_ENV !== "production") {
      logger.debug(`[Proxy] SSE upstream response: ${upstream.status}`, {
        component: "AUTO",
        action: "log",
        metadata: {
          correlationId,
          durationMs: upstreamDuration,
        },
      });
    }

    // Log errors in development and production (for auth errors)
    if (upstream.status >= 400) {
      const isAuthError = upstream.status === 401 || upstream.status === 403;

      // Always log auth errors (critical for debugging)
      if (isAuthError) {
        logger.error(
          `[Proxy] Auth error ${upstream.status} for ${req.method} ${url.pathname}`,
          {
            component: "AUTO",
            action: "error",
            metadata: {
              cookies: {
                authCookie: !!authCookie,
                csrfCookie: !!csrfCookie,
                authCookieValue: authCookie
                  ? `${authCookie.value.substring(0, 20)}...`
                  : "missing",
                csrfCookieValue: csrfCookie
                  ? `${csrfCookie.value.substring(0, 20)}...`
                  : "missing",
              },
              targetUrl,
              correlationId,
              userAgent: req.headers.get("user-agent")?.substring(0, 50),
            },
          },
          toError(
            `[Proxy] Auth error ${upstream.status} for ${req.method} ${url.pathname}`,
          ),
        );
      } else if (process.env.NODE_ENV !== "production") {
        // Log other errors only in development
        logger.error(
          `[Proxy] Error ${upstream.status} for ${req.method} ${url.pathname}`,
          {
            component: "AUTO",
            action: "error",
            metadata: {
              targetUrl,
              correlationId,
            },
          },
          toError(
            `[Proxy] Error ${upstream.status} for ${req.method} ${url.pathname}`,
          ),
        );
      }
    }

    // Forward headers from upstream
    const respHeaders = new Headers(upstream.headers);
    respHeaders.delete("transfer-encoding");
    respHeaders.delete("content-encoding");

    // CRITICAL: Prevent caching of authenticated API responses + Fly.io re-compression
    respHeaders.set("Cache-Control", "no-store, no-transform");

    // For SSE (streaming) endpoints, pass through the body stream as-is
    // SSE endpoints are typically not compressed and need to stay as streams
    if (isStreamingEndpoint) {
      return new Response(upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers: respHeaders,
      });
    }

    // For non-streaming endpoints, read the body as ArrayBuffer
    // This fixes an issue where Vercel edge doesn't properly pass through
    // compressed response bodies from upstream
    respHeaders.delete("content-length"); // Length may change after decompression

    const bodyBuffer = await upstream.arrayBuffer();

    // CRITICAL: For auth/login responses, manually set cookies via NextResponse
    // Vercel Edge Runtime silently drops Set-Cookie headers with domain=.balizero.com
    // when they come from a proxied response. We must use NextResponse.cookies.set()
    // to bypass this restriction.
    const isLoginEndpoint =
      url.pathname === "/api/auth/login" &&
      req.method === "POST" &&
      upstream.status === 200;

    if (isLoginEndpoint) {
      try {
        const bodyJson = JSON.parse(new TextDecoder().decode(bodyBuffer));
        const jwt = bodyJson?.data?.token;
        const csrf = bodyJson?.data?.csrfToken;
        if (jwt) {
          const isLocalhost =
            url.hostname === "localhost" || url.hostname === "127.0.0.1";
          const cookieDomain = isLocalhost
            ? null
            : (process.env.COOKIE_DOMAIN || ".balizero.com").replace(
                /\s+/g,
                "",
              );
          const maxAge = 86400; // 24h
          // CRITICAL: Strip upstream Set-Cookie headers — they carry SameSite=none
          // which Chrome 130+ rejects without Partitioned. We re-set cookies manually
          // using raw header strings to bypass Vercel Edge Runtime restrictions.
          respHeaders.delete("set-cookie");
          // Build raw Set-Cookie strings — Vercel Edge forwards these reliably
          // On localhost, omit Domain so the browser accepts the cookie
          const tokenParts = [
            `nz_access_token=${jwt}`,
            ...(cookieDomain ? [`Domain=${cookieDomain}`] : []),
            `HttpOnly`,
            `Max-Age=${maxAge}`,
            `Path=/`,
            `SameSite=Lax`,
            ...(isLocalhost ? [] : [`Secure`]),
          ];
          respHeaders.append("set-cookie", tokenParts.join("; "));
          if (csrf) {
            const csrfParts = [
              `nz_csrf_token=${csrf}`,
              ...(cookieDomain ? [`Domain=${cookieDomain}`] : []),
              `Max-Age=${maxAge}`,
              `Path=/`,
              `SameSite=Lax`,
              ...(isLocalhost ? [] : [`Secure`]),
            ];
            respHeaders.append("set-cookie", csrfParts.join("; "));
          }
          return new Response(bodyBuffer, {
            status: upstream.status,
            statusText: upstream.statusText,
            headers: respHeaders,
          });
        }
      } catch {
        // Fall through to normal response if JSON parse fails
      }
    }

    return new Response(bodyBuffer, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (error) {
    logger.error(
      `[Proxy] Fetch error for ${req.method} ${url.pathname}`,
      {
        component: "AUTO",
        action: "error",
        metadata: {
          method: req.method,
          pathname: url.pathname,
          targetUrl,
        },
      },
      toError(error),
    );
    return new Response(
      JSON.stringify({
        error: "Proxy error",
        message: error instanceof Error ? error.message : "Unknown error",
        targetUrl,
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}

export async function GET(req: NextRequest) {
  return proxy(req);
}

export async function POST(req: NextRequest) {
  return proxy(req);
}

export async function PUT(req: NextRequest) {
  return proxy(req);
}

export async function PATCH(req: NextRequest) {
  return proxy(req);
}

export async function DELETE(req: NextRequest) {
  return proxy(req);
}

export async function OPTIONS(req: NextRequest) {
  return proxy(req);
}
