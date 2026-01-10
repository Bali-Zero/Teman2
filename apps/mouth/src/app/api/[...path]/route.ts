import type { NextRequest } from 'next/server';

function normalizeBackendBaseUrl(url: string): string {
  return url.replace(/\/+$/, '').replace(/\/api$/, '');
}

function getBackendBaseUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'https://nuzantara-rag.fly.dev';
  return normalizeBackendBaseUrl(raw);
}

async function proxy(req: NextRequest): Promise<Response> {
  const backendBase = getBackendBaseUrl();
  const url = new URL(req.url);
  const targetUrl = `${backendBase}${url.pathname}${url.search}`;

  // Extract correlation ID for logging
  const correlationId = req.headers.get('X-Correlation-ID') || 'unknown';
  const isStreamingEndpoint = url.pathname.includes('/agentic-rag/stream');

  // Log requests in development
  if (process.env.NODE_ENV !== 'production') {
    console.log(`[Proxy] ${req.method} ${url.pathname} -> ${targetUrl}`);
  }

  // Log streaming requests
  if (isStreamingEndpoint && process.env.NODE_ENV !== 'production') {
    console.log(
      `[Proxy] SSE request start: ${req.method} ${url.pathname} (correlation_id=${correlationId})`
    );
  }

  const headers = new Headers(req.headers);
  headers.delete('host');
  headers.delete('connection');
  headers.delete('content-length');

  // CRITICAL: Explicitly forward authentication cookies
  // In server-side Next.js, credentials: 'include' doesn't automatically forward cookies
  // We must extract cookies from the request and add them to headers
  const cookies = req.cookies;
  const authCookie = cookies.get('nz_access_token');
  const csrfCookie = cookies.get('nz_csrf_token');

  if (authCookie || csrfCookie) {
    const cookieParts: string[] = [];
    if (authCookie) {
      cookieParts.push(`nz_access_token=${authCookie.value}`);
    }
    if (csrfCookie) {
      cookieParts.push(`nz_csrf_token=${csrfCookie.value}`);
    }

    const existingCookie = headers.get('cookie') || '';
    const newCookieValue = cookieParts.join('; ');
    headers.set('cookie', existingCookie ? `${existingCookie}; ${newCookieValue}` : newCookieValue);
  }

  let body: BodyInit | undefined = undefined;
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const contentType = req.headers.get('content-type') || '';
    if (contentType.includes('multipart/form-data')) {
      // CRITICAL: When passing FormData to fetch, fetch generates its own boundary.
      // We must delete the original Content-Type header so fetch can set the correct one.
      headers.delete('content-type');
      body = (await req.formData()) as unknown as BodyInit;
    } else {
      const buf = await req.arrayBuffer();
      body = buf.byteLength ? buf : undefined;
      // CRITICAL: Preserve Content-Type header for JSON and other body types
      // FastAPI needs this to parse request body correctly
      if (contentType && !headers.has('content-type')) {
        headers.set('content-type', contentType);
      }
    }
  }

  const upstreamStartTime = Date.now();
  try {
    // Debug logging for DELETE with body
    if (req.method === 'DELETE' && body) {
      console.log('🔍 [PROXY] DELETE with body detected:', {
        method: req.method,
        path: url.pathname,
        hasBody: !!body,
        bodySize: body ? (typeof body === 'string' ? body.length : 'binary') : 'none',
        contentType: headers.get('content-type'),
        targetUrl,
      });
    }

    // Use redirect: 'manual' and handle redirects ourselves to preserve cookies
    // For DELETE with body, ensure body is properly forwarded
    const requestInit: RequestInit = {
      method: req.method,
      headers,
      redirect: 'manual',
      credentials: 'include',
    };

    // Only add body if it exists and method supports it
    if (body && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(req.method)) {
      requestInit.body = body;
      console.log('🔍 [PROXY] Body added to request:', {
        method: req.method,
        bodyIncluded: true,
        bodyLength: typeof body === 'string' ? body.length : 'binary',
      });
    }

    let upstream = await fetch(targetUrl, requestInit);

    // Handle redirects manually to preserve cookies (fetch doesn't forward cookies on redirects)
    let redirectCount = 0;
    const maxRedirects = 5;
    while (upstream.status >= 300 && upstream.status < 400 && redirectCount < maxRedirects) {
      const location = upstream.headers.get('location');
      if (!location) break;

      // Resolve relative URLs against the backend base
      const redirectUrl = location.startsWith('http')
        ? location.replace(/^http:/, 'https:') // Force HTTPS
        : `${backendBase}${location.startsWith('/') ? '' : '/'}${location}`;

      // HTTP 307 and 308 preserve the original method (including POST/DELETE body)
      // HTTP 301, 302, 303 convert POST to GET (standard browser behavior)
      // For DELETE with body, we need to preserve the method and body
      const preserveMethod = upstream.status === 307 || upstream.status === 308 || req.method === 'DELETE';
      const redirectMethod = preserveMethod ? req.method : (req.method === 'POST' ? 'GET' : req.method);

      upstream = await fetch(redirectUrl, {
        method: redirectMethod,
        headers,
        body: preserveMethod && body ? body : undefined, // Preserve body for 307/308
        redirect: 'manual',
        credentials: 'include',
      });
      redirectCount++;
    }

    const upstreamDuration = Date.now() - upstreamStartTime;

    // Log streaming response status
    if (isStreamingEndpoint && process.env.NODE_ENV !== 'production') {
      console.log(
        `[Proxy] SSE upstream response: ${upstream.status} (correlation_id=${correlationId}, ` +
          `duration_ms=${upstreamDuration})`
      );
    }

    // Log errors in development
    if (process.env.NODE_ENV !== 'production' && upstream.status >= 400) {
      console.error(`[Proxy] Error ${upstream.status} for ${req.method} ${url.pathname}`);
    }

    // Forward headers from upstream
    const respHeaders = new Headers(upstream.headers);
    respHeaders.delete('transfer-encoding');

    // CRITICAL: Prevent Fly.io edge from re-compressing our response
    respHeaders.set('Cache-Control', 'no-transform');

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
    respHeaders.delete('content-encoding');
    respHeaders.delete('content-length'); // Length may change after decompression

    const bodyBuffer = await upstream.arrayBuffer();

    return new Response(bodyBuffer, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (error) {
    console.error(`[Proxy] Fetch error for ${req.method} ${url.pathname}:`, error);
    return new Response(
      JSON.stringify({
        error: 'Proxy error',
        message: error instanceof Error ? error.message : 'Unknown error',
        targetUrl,
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
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
