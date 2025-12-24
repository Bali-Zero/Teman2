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
    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
      redirect: 'manual',
      credentials: 'include', // CRITICAL: Pass httpOnly cookies to backend
    });
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

    // Forward all headers from upstream, including content-encoding
    // The browser will handle decompression automatically
    // Only delete transfer-encoding as it's hop-by-hop
    const respHeaders = new Headers(upstream.headers);
    respHeaders.delete('transfer-encoding');

    // CRITICAL: Rewrite Location header for redirects to prevent Mixed Content
    // FastAPI may return redirects with http:// URLs when behind a proxy
    const location = respHeaders.get('location');
    if (location && upstream.status >= 300 && upstream.status < 400) {
      // Rewrite backend URL to proxy URL
      const rewrittenLocation = location
        .replace(/^https?:\/\/nuzantara-rag\.fly\.dev/, '')
        .replace(/^https?:\/\/[^/]+\.fly\.dev/, '');
      respHeaders.set('location', rewrittenLocation);
    }

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
