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
      body = (await req.formData()) as unknown as BodyInit;
    } else {
      const buf = await req.arrayBuffer();
      body = buf.byteLength ? buf : undefined;
    }
  }

  const upstreamStartTime = Date.now();
  try {
    // Use redirect: 'manual' and handle redirects ourselves to preserve cookies
    let upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
      redirect: 'manual',
      credentials: 'include',
    });

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

      upstream = await fetch(redirectUrl, {
        method: req.method === 'POST' ? 'GET' : req.method, // POST->GET on redirect
        headers,
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
    // IMPORTANT: Remove content-encoding because Node.js fetch already decompresses the body
    // If we forward content-encoding: gzip with an already-decompressed body,
    // the browser will try to decompress again causing ERR_CONTENT_DECODING_FAILED
    const respHeaders = new Headers(upstream.headers);
    respHeaders.delete('transfer-encoding');
    respHeaders.delete('content-encoding');

    return new Response(upstream.body, {
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
