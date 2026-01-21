import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Multi-domain Middleware
 *
 * Handles routing between:
 * - balizero.com (public website)
 * - zantara.balizero.com (internal app)
 */

// Internal app routes that should only be on zantara subdomain
const INTERNAL_ROUTES = [
  '/login',
  '/dashboard',
  '/clients',
  '/process',
  '/documents',
  '/email',
  '/knowledge',
  '/settings',
  '/team-management', // workspace team management (not /team which is public)
  '/whatsapp',
  '/admin',
  '/agents',
  '/portal',
  '/analytics',
  '/intelligence',
];

// Public routes for balizero.com
const PUBLIC_CATEGORIES = [
  'immigration',
  'business',
  'tax-legal',
  'property',
  'lifestyle',
  'digital-nomad',
  'tech',
];

// Domains
const PUBLIC_DOMAIN = 'balizero.com';
const APP_DOMAIN = 'zantara.balizero.com';
const MOBILE_DOMAIN = 'mo.balizero.com';

export function middleware(request: NextRequest) {
  const hostname = request.headers.get('host') || '';
  const pathname = request.nextUrl.pathname;

  // Skip static files and API routes
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/static') ||
    pathname.includes('.') // files with extensions
  ) {
    // Still add pathname header for consistency
    const response = NextResponse.next();
    response.headers.set('x-pathname', pathname);
    return response;
  }

  // Create response and add pathname header for Server Components
  const response = NextResponse.next();
  response.headers.set('x-pathname', pathname);

  // === REDIRECT 301: mo.balizero.com → balizero.com ===
  // SEO: Prevent duplicate content and consolidate domain authority
  if (hostname === MOBILE_DOMAIN || hostname === `www.${MOBILE_DOMAIN}`) {
    const redirectUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
    redirectUrl.search = request.nextUrl.search;
    const redirectResponse = NextResponse.redirect(redirectUrl, 301); // Permanent redirect
    redirectResponse.headers.set('x-pathname', pathname);
    return redirectResponse;
  }

  // Determine if we're on the public domain
  const isPublicDomain = hostname.includes(PUBLIC_DOMAIN) && !hostname.includes('zantara');
  const isAppDomain = hostname.includes(APP_DOMAIN) || hostname.includes('zantara');

  // Development and Fly.dev: allow all routes (public-facing)
  const isDevelopment = hostname.includes('localhost') || hostname.includes('127.0.0.1');
  const isFlyDev = hostname.includes('fly.dev');

  if (isDevelopment || isFlyDev) {
    return response;
  }

  // === PUBLIC DOMAIN (balizero.com) ===
  if (isPublicDomain) {
    // Check if trying to access internal routes
    const isInternalRoute = INTERNAL_ROUTES.some(
      (route) => pathname === route || pathname.startsWith(`${route}/`)
    );

    if (isInternalRoute) {
      // Redirect to app domain
      const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
      appUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(appUrl);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Check if it's the /chat route - redirect to app
    if (pathname === '/chat' || pathname.startsWith('/chat/')) {
      const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
      appUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(appUrl);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Rewrite /insights/* to /* for backward compatibility
    if (pathname.startsWith('/insights')) {
      const newPath = pathname.replace('/insights', '') || '/';
      const url = request.nextUrl.clone();
      url.pathname = newPath;
      const redirectResponse = NextResponse.redirect(url);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Allow public routes
    return response;
  }

  // === APP DOMAIN (zantara.balizero.com) ===
  if (isAppDomain) {
    // Redirect root to login on app domain
    if (pathname === '/') {
      const redirectResponse = NextResponse.redirect(new URL('/login', request.url));
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // On app domain, redirect public content to main domain
    // Check if it's a category page (public content)
    const firstSegment = pathname.split('/')[1];

    if (PUBLIC_CATEGORIES.includes(firstSegment)) {
      // Redirect category pages to public domain
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(publicUrl);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Redirect /services to public domain (except API routes)
    if (pathname.startsWith('/services') && !pathname.startsWith('/services/api')) {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(publicUrl);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Redirect /contact to public domain
    if (pathname === '/contact') {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(publicUrl);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Redirect /team to public domain (public team page, not /team-management)
    if (pathname === '/team') {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      const redirectResponse = NextResponse.redirect(publicUrl);
      redirectResponse.headers.set('x-pathname', pathname);
      return redirectResponse;
    }

    // Allow all other routes on app domain
    return response;
  }

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (images, etc)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\..*|api).*)',
  ],
};
