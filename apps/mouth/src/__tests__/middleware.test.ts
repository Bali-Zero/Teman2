import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest, NextResponse } from 'next/server';
import { middleware } from '../middleware';

describe('Middleware - Multi-domain Routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Static Files and API Routes', () => {
    it('should skip middleware for _next static files', () => {
      const request = new NextRequest('https://balizero.com/_next/static/chunk.js');
      const response = middleware(request);

      expect(response.headers.get('x-pathname')).toBe('/_next/static/chunk.js');
    });

    it('should skip middleware for API routes', () => {
      const request = new NextRequest('https://balizero.com/api/auth/login');
      const response = middleware(request);

      expect(response.headers.get('x-pathname')).toBe('/api/auth/login');
    });

    it('should skip middleware for files with extensions', () => {
      const request = new NextRequest('https://balizero.com/favicon.ico');
      const response = middleware(request);

      expect(response.headers.get('x-pathname')).toBe('/favicon.ico');
    });
  });

  describe('Mobile Domain Redirect (mo.balizero.com)', () => {
    it('should redirect mo.balizero.com to balizero.com with 301', () => {
      const request = new NextRequest('https://mo.balizero.com/immigration/kitas');
      const response = middleware(request);

      expect(response.status).toBe(301);
      expect(response.headers.get('location')).toBe('https://balizero.com/immigration/kitas');
    });

    it('should redirect www.mo.balizero.com to balizero.com', () => {
      const request = new NextRequest('https://www.mo.balizero.com/business');
      const response = middleware(request);

      expect(response.status).toBe(301);
      expect(response.headers.get('location')).toBe('https://balizero.com/business');
    });

    it('should preserve query parameters in mobile redirect', () => {
      const request = new NextRequest('https://mo.balizero.com/services?category=visa');
      const response = middleware(request);

      expect(response.status).toBe(301);
      expect(response.headers.get('location')).toBe('https://balizero.com/services?category=visa');
    });
  });

  describe('Development and Fly.dev Environments', () => {
    it('should allow all routes on localhost', () => {
      const request = new NextRequest('http://localhost:3000/dashboard');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/dashboard');
    });

    it('should allow all routes on 127.0.0.1', () => {
      const request = new NextRequest('http://127.0.0.1:3000/login');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get('x-pathname')).toBe('/login');
    });

    it('should allow all routes on fly.dev', () => {
      const request = new NextRequest('https://app.fly.dev/clients');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get('x-pathname')).toBe('/clients');
    });
  });

  describe('Portal Domain (my.balizero.com)', () => {
    it('should allow /portal routes on portal domain', () => {
      const request = new NextRequest('https://my.balizero.com/portal/dashboard');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/portal/dashboard');
    });

    it('should redirect root to /portal/login on portal domain', () => {
      const request = new NextRequest('https://my.balizero.com/');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toContain('/portal/login');
    });

    it('should redirect non-portal routes to public domain', () => {
      const request = new NextRequest('https://my.balizero.com/immigration/kitas');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/immigration/kitas');
    });

    it('should preserve query params when redirecting from portal domain', () => {
      const request = new NextRequest('https://my.balizero.com/services?type=visa');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/services?type=visa');
    });
  });

  describe('Public Domain (balizero.com)', () => {
    it('should redirect /portal routes to portal domain with 301', () => {
      const request = new NextRequest('https://balizero.com/portal/dashboard');
      const response = middleware(request);

      expect(response.status).toBe(301);
      expect(response.headers.get('location')).toBe('https://my.balizero.com/portal/dashboard');
    });

    it('should redirect /login to app domain', () => {
      const request = new NextRequest('https://balizero.com/login');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://zantara.balizero.com/login');
    });

    it('should redirect /dashboard to app domain', () => {
      const request = new NextRequest('https://balizero.com/dashboard');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://zantara.balizero.com/dashboard');
    });

    it('should redirect /clients to app domain', () => {
      const request = new NextRequest('https://balizero.com/clients');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://zantara.balizero.com/clients');
    });

    it('should redirect /chat to app domain', () => {
      const request = new NextRequest('https://balizero.com/chat');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://zantara.balizero.com/chat');
    });

    it('should redirect /admin to app domain', () => {
      const request = new NextRequest('https://balizero.com/admin');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://zantara.balizero.com/admin');
    });

    it('should redirect /insights/* to root path for backward compatibility', () => {
      const request = new NextRequest('https://balizero.com/insights/immigration');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toContain('/immigration');
    });

    it('should allow public category routes', () => {
      const request = new NextRequest('https://balizero.com/immigration/kitas');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/immigration/kitas');
    });

    it('should allow /services routes', () => {
      const request = new NextRequest('https://balizero.com/services/visa-assistance');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get('x-pathname')).toBe('/services/visa-assistance');
    });

    it('should allow /contact route', () => {
      const request = new NextRequest('https://balizero.com/contact');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.headers.get('x-pathname')).toBe('/contact');
    });

    it('should preserve query params when redirecting internal routes', () => {
      const request = new NextRequest('https://balizero.com/dashboard?tab=analytics');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe(
        'https://zantara.balizero.com/dashboard?tab=analytics'
      );
    });
  });

  describe('App Domain (zantara.balizero.com)', () => {
    it('should redirect /portal routes to portal domain with 301', () => {
      const request = new NextRequest('https://zantara.balizero.com/portal/documents');
      const response = middleware(request);

      expect(response.status).toBe(301);
      expect(response.headers.get('location')).toBe('https://my.balizero.com/portal/documents');
    });

    it('should redirect root to /login on app domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toContain('/login');
    });

    it('should redirect public category pages to public domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/immigration/kitas');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/immigration/kitas');
    });

    it('should redirect /services to public domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/services');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/services');
    });

    it('should allow /services/api routes on app domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/services/api/endpoint');
      const response = middleware(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/services/api/endpoint');
    });

    it('should redirect /contact to public domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/contact');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/contact');
    });

    it('should redirect /team to public domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/team');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/team');
    });

    it('should allow /team-management on app domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/team-management');
      const response = middleware(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/team-management');
    });

    it('should allow internal app routes', () => {
      const request = new NextRequest('https://zantara.balizero.com/dashboard');
      const response = middleware(request);

      expect(response.status).not.toBe(301);
      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/dashboard');
    });

    it('should allow /clients route', () => {
      const request = new NextRequest('https://zantara.balizero.com/clients');
      const response = middleware(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/clients');
    });

    it('should allow /whatsapp route', () => {
      const request = new NextRequest('https://zantara.balizero.com/whatsapp');
      const response = middleware(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/whatsapp');
    });

    it('should preserve query params when redirecting to public domain', () => {
      const request = new NextRequest('https://zantara.balizero.com/immigration?lang=en');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe('https://balizero.com/immigration?lang=en');
    });
  });

  describe('Pathname Header', () => {
    it('should always set x-pathname header', () => {
      const request = new NextRequest('https://balizero.com/immigration/kitas');
      const response = middleware(request);

      expect(response.headers.get('x-pathname')).toBe('/immigration/kitas');
    });

    it('should set x-pathname header even for redirects on public domain', () => {
      const request = new NextRequest('https://balizero.com/login');
      const response = middleware(request);

      expect(response.headers.get('x-pathname')).toBe('/login');
      expect(response.status).toBe(307);
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing host header gracefully', () => {
      const request = new NextRequest('https://balizero.com/test');
      // Simulate missing host header
      Object.defineProperty(request.headers, 'get', {
        value: (key: string) => (key === 'host' ? null : request.headers.get(key)),
      });

      expect(() => middleware(request)).not.toThrow();
    });

    it('should handle nested internal routes on public domain', () => {
      const request = new NextRequest('https://balizero.com/dashboard/analytics/reports');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe(
        'https://zantara.balizero.com/dashboard/analytics/reports'
      );
    });

    it('should handle chat subroutes on public domain', () => {
      const request = new NextRequest('https://balizero.com/chat/conversation/123');
      const response = middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toBe(
        'https://zantara.balizero.com/chat/conversation/123'
      );
    });

    it('should allow chat subroutes on localhost', () => {
      const request = new NextRequest('http://localhost:3000/chat/conversation/123');
      const response = middleware(request);

      expect(response.status).not.toBe(307);
      expect(response.headers.get('x-pathname')).toBe('/chat/conversation/123');
    });
  });
});
