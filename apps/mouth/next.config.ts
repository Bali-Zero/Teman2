import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  images: {
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
    ],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination:
          process.env.NODE_ENV === 'development'
            ? 'http://127.0.0.1:8080/api/:path*'
            : (process.env.NEXT_PUBLIC_API_URL || 'https://nuzantara-rag.fly.dev') + '/api/:path*',
      },
    ];
  },
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
