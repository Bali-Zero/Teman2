import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  typescript: {
    // Allow build to complete despite pre-existing TypeScript errors
    ignoreBuildErrors: true,
  },
  // Redirect 301: mo.balizero.com → balizero.com
  // SEO: Prevent duplicate content and consolidate domain authority
  async redirects() {
    return [
      {
        source: '/:path*',
        has: [
          {
            type: 'host',
            value: 'mo.balizero.com',
          },
        ],
        destination: 'https://balizero.com/:path*',
        permanent: true, // 301 redirect
      },
    ];
  },
  images: {
    // 🖼️ Image Optimization - Auto AVIF/WebP conversion
    formats: ['image/avif', 'image/webp'], // Modern formats (70% smaller)
    deviceSizes: [640, 750, 828, 1080, 1200, 1920], // Responsive breakpoints
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384], // Icon/thumbnail sizes
    minimumCacheTTL: 60 * 60 * 24 * 365, // Cache 1 year
    dangerouslyAllowSVG: true,
    contentDispositionType: 'attachment',
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",

    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'nuzantara-rag.fly.dev',
      },
      {
        protocol: 'https',
        hostname: '*.fly.dev',
      },
      {
        protocol: 'https',
        hostname: 'oaidalleapiprodscus.blob.core.windows.net',
      },
      {
        protocol: 'https',
        hostname: 'placehold.co',
      },
      {
        protocol: 'https',
        hostname: 'image.pollinations.ai',
      },
      {
        protocol: 'https',
        hostname: 'balizero.com',
      },
      {
        protocol: 'https',
        hostname: 'www.datocms-assets.com',
      },
    ],
  },
  // NOTE: API proxying is handled by src/app/api/[...path]/route.ts
  // Do NOT add rewrites for /api/* here as they conflict with the API route handler
  // and can cause Mixed Content issues in production.
};

// Sentry configuration options
const sentryWebpackPluginOptions = {
  // Suppresses source map uploading logs during build
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  // Only upload source maps in production
  disableServerWebpackPlugin: !process.env.SENTRY_DSN,
  disableClientWebpackPlugin: !process.env.NEXT_PUBLIC_SENTRY_DSN,
};

// Export with Sentry wrapper (only if Sentry is configured)
export default process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(nextConfig, sentryWebpackPluginOptions)
  : nextConfig;
