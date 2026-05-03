import { NextRequest, NextResponse } from 'next/server';

import { verifyAdminToken } from '@/lib/auth/verify-admin';

/**
 * Organo: admin-dashboard (apps/admin-dashboard)
 *   → consuma JWT emesso da apps/backend-rag/backend/app/routers/auth.py
 *   → produce 401/403/redirect (nessuna persistenza, pure gate)
 *
 * Audit 2026-04-18 CRIT-1: questa app esponeva `/api/postgres/*`, `/api/qdrant/*`,
 * `/api/kg/*`, `/api/legal/*`, `/api/calendar/*`, `/api/rag/*` senza alcun
 * controllo auth. Il middleware ripristina l'invariante "solo admin può accedere".
 *
 * Differenze dal pattern satelliti standard (drive/mail/calendar/knowledge):
 *  1. NON saltiamo `/api` — le API espongono dump DB e vanno protette anche
 *     se il cookie manca.
 *  2. Decodifichiamo il JWT (jose/HS256 con JWT_SECRET_KEY) e richiediamo
 *     `role ∈ {admin, super_admin, owner}`. La sola presenza del cookie
 *     basta solo per subdomain "workspace" (drive, mail...), non per un
 *     pannello che accede al DB.
 *  3. Se `ADMIN_EMAILS` env var è settata, è un secondo gate (difesa in profondità).
 *
 * Le API rispondono JSON 401/403. Le pagine HTML redirectano a kita login.
 */

const LOGIN_URL = 'https://kita.balizero.com/login';
const SELF_ORIGIN_DEFAULT = 'https://admin.balizero.com';

function isApiPath(pathname: string): boolean {
  return pathname.startsWith('/api/');
}

function isStaticAsset(pathname: string): boolean {
  return (
    pathname.startsWith('/_next/') ||
    pathname === '/favicon.ico' ||
    pathname === '/robots.txt' ||
    /\.[a-zA-Z0-9]+$/.test(pathname)
  );
}

function jsonError(
  status: number,
  code: 'unauthenticated' | 'forbidden',
  detail: string
): NextResponse {
  const body = JSON.stringify({ error: code, detail });
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    'cache-control': 'no-store',
  };
  if (status === 401) {
    headers['www-authenticate'] = 'Bearer realm="admin-dashboard"';
  }
  return new NextResponse(body, { status, headers });
}

function redirectToLogin(request: NextRequest): NextResponse {
  const selfOrigin =
    process.env.NEXT_PUBLIC_ADMIN_ORIGIN || request.nextUrl.origin || SELF_ORIGIN_DEFAULT;
  const returnTo = encodeURIComponent(
    `${selfOrigin}${request.nextUrl.pathname}${request.nextUrl.search}`
  );
  return NextResponse.redirect(`${LOGIN_URL}?redirect=${returnTo}`);
}

export async function middleware(request: NextRequest): Promise<NextResponse | undefined> {
  const { pathname } = request.nextUrl;

  if (isStaticAsset(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get('nz_access_token')?.value;
  const outcome = await verifyAdminToken(token);

  if (outcome.ok) {
    const res = NextResponse.next();
    res.headers.set('x-admin-email', outcome.email);
    return res;
  }

  const isApi = isApiPath(pathname);

  if (outcome.reason === 'missing_cookie') {
    if (isApi) {
      return jsonError(401, 'unauthenticated', 'Authentication required');
    }
    return redirectToLogin(request);
  }

  if (outcome.reason === 'bad_token') {
    if (isApi) {
      return jsonError(401, 'unauthenticated', 'Invalid or expired token');
    }
    // For HTML pages we redirect so the user can re-authenticate.
    return redirectToLogin(request);
  }

  // forbidden_role: authenticated but not admin. Never bounce to login — that
  // would create a redirect loop for a logged-in non-admin user.
  if (isApi) {
    return jsonError(403, 'forbidden', 'Admin role required');
  }
  return new NextResponse('Forbidden: admin role required', {
    status: 403,
    headers: { 'content-type': 'text/plain', 'cache-control': 'no-store' },
  });
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|robots.txt).*)'],
};
