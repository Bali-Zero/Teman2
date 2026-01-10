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
  '/cases',
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
    return NextResponse.next();
  }

  // Determine if we're on the public domain
  const isPublicDomain = hostname.includes(PUBLIC_DOMAIN) && !hostname.includes('zantara');
  const isAppDomain = hostname.includes(APP_DOMAIN) || hostname.includes('zantara');

  // Development and Fly.dev: allow all routes (public-facing)
  const isDevelopment = hostname.includes('localhost') || hostname.includes('127.0.0.1');
  const isFlyDev = hostname.includes('fly.dev');

  if (isDevelopment || isFlyDev) {
    return NextResponse.next();
  }

  // === PUBLIC DOMAIN (balizero.com) ===
  if (isPublicDomain) {
    // Check if trying to access internal routes
    const isInternalRoute = INTERNAL_ROUTES.some(route =>
      pathname === route || pathname.startsWith(`${route}/`)
    );

    if (isInternalRoute) {
      // Redirect to app domain
      const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
      appUrl.search = request.nextUrl.search;
      return NextResponse.redirect(appUrl);
    }

    // Check if it's the /chat route - redirect to app
    if (pathname === '/chat' || pathname.startsWith('/chat/')) {
      const appUrl = new URL(pathname, `https://${APP_DOMAIN}`);
      appUrl.search = request.nextUrl.search;
      return NextResponse.redirect(appUrl);
    }

    // Rewrite /insights/* to /* for backward compatibility
    if (pathname.startsWith('/insights')) {
      const newPath = pathname.replace('/insights', '') || '/';
      const url = request.nextUrl.clone();
      url.pathname = newPath;
      return NextResponse.redirect(url);
    }

    // Allow public routes
    return NextResponse.next();
  }

  // === APP DOMAIN (zantara.balizero.com) ===
  if (isAppDomain) {
    // Redirect root to login on app domain
    if (pathname === '/') {
      return NextResponse.redirect(new URL('/login', request.url));
    }

    // On app domain, redirect public content to main domain
    // Check if it's a category page (public content)
    const firstSegment = pathname.split('/')[1];

    if (PUBLIC_CATEGORIES.includes(firstSegment)) {
      // Redirect category pages to public domain
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return NextResponse.redirect(publicUrl);
    }

    // Redirect /services to public domain (except API routes)
    if (pathname.startsWith('/services') && !pathname.startsWith('/services/api')) {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return NextResponse.redirect(publicUrl);
    }

    // Redirect /contact to public domain
    if (pathname === '/contact') {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return NextResponse.redirect(publicUrl);
    }

    // Redirect /team to public domain (public team page, not /team-management)
    if (pathname === '/team') {
      const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
      publicUrl.search = request.nextUrl.search;
      return NextResponse.redirect(publicUrl);
    }

    // Allow all other routes on app domain
    return NextResponse.next();
  }

  return NextResponse.next();
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
