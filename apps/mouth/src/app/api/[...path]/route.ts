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

  const headers = new Headers(req.headers);
  headers.delete('host');
  headers.delete('connection');
  headers.delete('content-length');

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

  const upstream = await fetch(targetUrl, {
    method: req.method,
    headers,
    body,
    redirect: 'manual',
  });

  const respHeaders = new Headers(upstream.headers);
  respHeaders.delete('content-encoding');
  respHeaders.delete('transfer-encoding');

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
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

