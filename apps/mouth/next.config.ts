import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";
import bundleAnalyzer from "@next/bundle-analyzer";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Force ignore errors for immediate deployment
  typescript: {
    ignoreBuildErrors: true,
  },

  // ⚡ Bundle optimization
  compress: true,
  productionBrowserSourceMaps: false,
  poweredByHeader: false, // Remove X-Powered-By header for security

  // 🚀 Experimental optimizations
  experimental: {
    // Optimize package imports for faster dev and smaller bundles
    optimizePackageImports: [
      "lucide-react",
      "@radix-ui/react-icons",
      "date-fns",
      "@nivo/core",
      "@nivo/bar",
      "@nivo/line",
      "@nivo/pie",
    ],
    // Server Actions optimization
    serverMinification: true,
    // Optimize CSS (removes unused CSS in production)
    optimizeCss: true,
    // Partial Prerendering - Next.js 16 handles this automatically
    // PPR features are now part of the core rendering engine
    // Turbopack for faster builds (when stable)
    // turbo: {},
  },
  // NOTE: Domain redirects handled by Vercel Dashboard to avoid conflicts
  images: {
    // 🖼️ Image Optimization - Auto AVIF/WebP conversion
    formats: ["image/avif", "image/webp"], // Modern formats (70% smaller)
    deviceSizes: [640, 750, 828, 1080, 1200, 1920], // Responsive breakpoints
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384], // Icon/thumbnail sizes
    minimumCacheTTL: 60 * 60 * 24 * 365, // Cache 1 year
    dangerouslyAllowSVG: true,
    contentDispositionType: "attachment",
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",

    remotePatterns: [
      {
        protocol: "https",
        hostname: "nuzantara-rag.fly.dev",
      },
      {
        protocol: "https",
        hostname: "*.fly.dev",
      },
      {
        protocol: "https",
        hostname: "oaidalleapiprodscus.blob.core.windows.net",
      },
      {
        protocol: "https",
        hostname: "placehold.co",
      },
      {
        protocol: "https",
        hostname: "image.pollinations.ai",
      },
      {
        protocol: "https",
        hostname: "balizero.com",
      },
      {
        protocol: "https",
        hostname: "www.datocms-assets.com",
      },
    ],
  },
  // ⚡ Performance: Add cache headers for static assets
  async headers() {
    return [
      {
        // Cache static assets for 1 year (immutable)
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        // Cache images for 1 year
        source: "/_next/image/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        // Cache public assets (fonts, etc) for 1 year
        source: "/:path*.woff2",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        // Add security headers
        source: "/:path*",
        headers: [
          {
            key: "X-DNS-Prefetch-Control",
            value: "on",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
      {
        // 103 Early Hints for critical resources
        source: "/",
        headers: [
          {
            key: "Link",
            value:
              "</_next/static/media/GeistVariableVF.woff2>; rel=preload; as=font; crossorigin, </_next/static/css/app/layout.css>; rel=preload; as=style, </assets/static/indonesian-flag-drape.jpg>; rel=preload; as=image",
          },
        ],
      },
    ];
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

// Export with Sentry and Bundle Analyzer wrappers
const configWithAnalyzer = withBundleAnalyzer(nextConfig);

export default process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(configWithAnalyzer, sentryWebpackPluginOptions)
  : configWithAnalyzer;
