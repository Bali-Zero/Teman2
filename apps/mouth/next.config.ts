import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";
import bundleAnalyzer from "@next/bundle-analyzer";
import path from "node:path";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const nextConfig: NextConfig = {
  // Note: "standalone" output removed — Vercel handles bundling natively.
  // Using standalone on Vercel caused serverless functions to exceed 300MB
  // (507MB for KBLI routes) by including all node_modules in each function.
  turbopack: {
    root: path.join(__dirname, "../.."),
  },
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: false,
  },

  // ⚡ Bundle optimization
  compress: true,
  productionBrowserSourceMaps: false,
  poweredByHeader: false, // Remove X-Powered-By header for security

  // Exclude heavy directories from serverless function tracing
  // Without this, Vercel traces public/ (537MB) into each function, exceeding the 300MB limit
  outputFileTracingExcludes: {
    "/*": [
      "./public/blueprints/**",
      "./public/static/**",
      "./public/files/**",
      "./public/audio/**",
      "./public/videos/**",
      "./public/kbli-navigator/**",
      "./coverage/**",
      "./test-results/**",
      "./playwright-report/**",
    ],
  },
  outputFileTracingIncludes: {
    "/*": [
      "./data/KBLI_2025_FINAL_CLEAN.json",
      "./data/kbli-2025.json",
      "./data/kbli-gold-all.json",
      "./src/content/articles/**/*.mdx",
    ],
  },

  // 🚀 Experimental optimizations
  experimental: {
    // Optimize package imports for faster dev and smaller bundles
    optimizePackageImports: [
      "lucide-react",
      "@radix-ui/react-icons",
      "date-fns",
      "framer-motion",
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
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "storage.googleapis.com",
      },
    ],
  },
  // ⚡ Performance: Add cache headers for static assets
  async headers() {
    return [
      {
        // Force no-cache for kbli-navigator proxy routes
        source: "/kbli-navigator",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
      {
        source: "/kbli-navigator/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
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
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
          {
            key: "Content-Security-Policy-Report-Only",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com https://www.google-analytics.com; style-src 'self' 'unsafe-inline'; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https:; connect-src 'self' https://nuzantara-rag.fly.dev wss://nuzantara-rag.fly.dev https://127.0.0.1:8090 https://*.sentry.io https://www.google-analytics.com; frame-src 'none'; object-src 'none'; base-uri 'self'",
          },
        ],
      },
      // Preconnect to external domains for Core Web Vitals (LCP/FCP improvement)
      {
        source: "/:path*",
        headers: [
          {
            key: "Link",
            value:
              "<https://fonts.googleapis.com>; rel=preconnect, <https://fonts.gstatic.com>; rel=preconnect; crossorigin",
          },
        ],
      },
    ];
  },

  // Redirect legacy /kbli-navigator to new Next.js /kbli app
  async redirects() {
    return [
      // Category renames (2026-03-23) — keep for 12+ months
      { source: "/immigration", destination: "/visas", permanent: true },
      {
        source: "/immigration/:slug*",
        destination: "/visas/:slug*",
        permanent: true,
      },
      { source: "/tax-legal", destination: "/taxes", permanent: true },
      {
        source: "/tax-legal/:slug*",
        destination: "/taxes/:slug*",
        permanent: true,
      },
      { source: "/lifestyle", destination: "/living", permanent: true },
      {
        source: "/lifestyle/:slug*",
        destination: "/living/:slug*",
        permanent: true,
      },
      { source: "/tech", destination: "/trends", permanent: true },
      {
        source: "/tech/:slug*",
        destination: "/trends/:slug*",
        permanent: true,
      },
      { source: "/bali_news", destination: "/living", permanent: true },
      {
        source: "/bali_news/:slug*",
        destination: "/living/:slug*",
        permanent: true,
      },
      { source: "/digital-nomad", destination: "/living", permanent: true },
      {
        source: "/digital-nomad/:slug*",
        destination: "/living/:slug*",
        permanent: true,
      },
      {
        source: "/kbli-navigator",
        destination: "/kbli",
        permanent: true,
      },
      {
        source: "/kbli-navigator/:path*",
        destination: "/kbli/:path*",
        permanent: true,
      },
      // Note: /chat redirect to zantara.balizero.com is handled by middleware
      // (cannot be here — next.config redirects would conflict with middleware rewrites)
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
