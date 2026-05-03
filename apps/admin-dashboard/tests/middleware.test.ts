import { SignJWT } from 'jose';
import { NextRequest } from 'next/server';
import { beforeAll, describe, expect, it } from 'vitest';

import { middleware } from '@/middleware';

const SECRET_STRING = 'test-secret-please-ignore-32bytes-minimum-length!!';
const secret = new TextEncoder().encode(SECRET_STRING);

async function sign(payload: Record<string, unknown>): Promise<string> {
  return await new SignJWT(payload)
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime(Math.floor(Date.now() / 1000) + 3600)
    .sign(secret);
}

function buildRequest(pathname: string, cookie: string | null): NextRequest {
  const url = new URL(`https://admin.balizero.com${pathname}`);
  const headers = new Headers();
  if (cookie) {
    headers.set('cookie', `nz_access_token=${cookie}`);
  }
  return new NextRequest(url, { headers });
}

beforeAll(() => {
  process.env.JWT_SECRET_KEY = SECRET_STRING;
  delete process.env.ADMIN_EMAILS;
});

describe('admin-dashboard middleware — API routes', () => {
  it('returns 401 JSON when cookie is missing on /api/qdrant/collections', async () => {
    const req = buildRequest('/api/qdrant/collections', null);
    const res = await middleware(req);
    expect(res).toBeDefined();
    expect(res!.status).toBe(401);
    expect(res!.headers.get('www-authenticate')).toContain('Bearer');
    const body = await res!.json();
    expect(body.error).toBe('unauthenticated');
  });

  it('returns 401 JSON when token is malformed', async () => {
    const req = buildRequest('/api/postgres/users', 'not-a-jwt');
    const res = await middleware(req);
    expect(res!.status).toBe(401);
  });

  it('returns 403 JSON when authenticated as role=client', async () => {
    const token = await sign({
      email: 'client@example.com',
      role: 'client',
      type: 'access',
    });
    const req = buildRequest('/api/qdrant/collections', token);
    const res = await middleware(req);
    expect(res!.status).toBe(403);
    const body = await res!.json();
    expect(body.error).toBe('forbidden');
  });

  it('passes through (no rewrite/redirect) when role=admin on an API route', async () => {
    const token = await sign({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'access',
    });
    const req = buildRequest('/api/qdrant/collections', token);
    const res = await middleware(req);
    expect(res).toBeDefined();
    // NextResponse.next() surfaces as a 200 with no body to the runtime; the
    // important invariant is that we don't return 401/403/redirect.
    expect(res!.status).toBe(200);
    expect(res!.headers.get('location')).toBeNull();
    expect(res!.headers.get('x-admin-email')).toBe('zero@balizero.com');
  });
});

describe('admin-dashboard middleware — HTML pages', () => {
  it('redirects to kita login when cookie missing on /qdrant', async () => {
    const req = buildRequest('/qdrant', null);
    const res = await middleware(req);
    expect(res!.status).toBeGreaterThanOrEqual(300);
    expect(res!.status).toBeLessThan(400);
    const location = res!.headers.get('location');
    expect(location).toContain('kita.balizero.com/login');
    expect(location).toContain(encodeURIComponent('/qdrant'));
  });

  it('redirects to kita login when token invalid on a page', async () => {
    const req = buildRequest('/postgres', 'invalid.jwt.here');
    const res = await middleware(req);
    const location = res!.headers.get('location');
    expect(location).toContain('kita.balizero.com/login');
  });

  it('returns plain-text 403 (no redirect loop) when logged-in non-admin hits a page', async () => {
    const token = await sign({
      email: 'client@example.com',
      role: 'client',
      type: 'access',
    });
    const req = buildRequest('/postgres', token);
    const res = await middleware(req);
    expect(res!.status).toBe(403);
    expect(res!.headers.get('location')).toBeNull();
  });

  it('passes through admin on a page', async () => {
    const token = await sign({
      email: 'zero@balizero.com',
      role: 'admin',
      type: 'access',
    });
    const req = buildRequest('/postgres', token);
    const res = await middleware(req);
    expect(res!.status).toBe(200);
    expect(res!.headers.get('location')).toBeNull();
  });
});

describe('admin-dashboard middleware — asset bypass', () => {
  it('lets /_next/static assets through even without cookie', async () => {
    const req = buildRequest('/_next/static/chunks/main.js', null);
    const res = await middleware(req);
    expect(res!.status).toBe(200);
    expect(res!.headers.get('location')).toBeNull();
  });

  it('lets /favicon.ico through', async () => {
    const req = buildRequest('/favicon.ico', null);
    const res = await middleware(req);
    expect(res!.status).toBe(200);
  });
});
