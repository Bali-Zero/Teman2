import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { GoogleAnalytics } from "@next/third-parties/google";
import Script from "next/script";
import { Toaster } from "sonner";
import {
  OrganizationJsonLd,
  LocalBusinessJsonLd,
  WebsiteJsonLd,
  AggregateRatingJsonLd,
  DynamicJsonLd,
} from "@/components/seo";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { ErrorBoundary } from "@/components/optimization";
import { WebVitalsMonitor } from "@/components/providers/WebVitalsMonitor";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap", // Prevent FOIT (Flash of Invisible Text)
  preload: true,
  fallback: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap", // Prevent FOIT
  preload: true,
  fallback: ["SF Mono", "Monaco", "Inconsolata", "monospace"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

// Production URL - uses environment variable or falls back to production domain
const appUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  metadataBase: new URL(appUrl),
  title: {
    default:
      "Bali Zero | Visa, Business & Immigration Experts in Bali, Indonesia",
    template: "%s | Bali Zero",
  },
  description:
    "Bali's #1 AI-powered visa agency. KITAS, KITAP, PT PMA company setup, Golden Visa, KBLI 2025 compliance, tax consulting. Transparent pricing. Trusted by 5000+ clients since 2020.",
  keywords: [
    // Primary keywords
    "bali visa",
    "indonesia visa",
    "kitas bali",
    "pt pma indonesia",
    "company setup bali",
    "business license indonesia",
    "golden visa indonesia",
    // Long-tail keywords
    "how to get kitas in bali",
    "start business in indonesia foreigner",
    "retirement visa indonesia",
    "digital nomad visa bali",
    "pt pma registration process",
    "indonesian work permit",
    // Local SEO
    "bali visa agency",
    "visa agency bali",
    "visa agent bali",
    "immigration consultant bali",
    "notaris bali",
    "tax consultant bali",
    "company formation bali",
    // Brand
    "bali zero",
    "zantara ai",
    "bali zero team",
  ],
  authors: [{ name: "Bali Zero Team", url: "https://balizero.com" }],
  creator: "Bali Zero",
  publisher: "Bali Zero",
  category: "Business Services",
  // Icons are auto-detected by Next.js from app/icon.png and app/apple-icon.png
  // No explicit configuration needed - Next.js 13+ App Router handles this automatically
  openGraph: {
    type: "website",
    locale: "en_US",
    alternateLocale: ["id_ID"],
    url: appUrl,
    title: "Bali Zero | #1 Visa & Business Experts in Bali, Indonesia",
    description:
      "Bali's #1 AI-powered visa agency. KITAS, KITAP, PT PMA, Golden Visa, KBLI 2025, tax consulting. 5000+ clients since 2020.",
    siteName: "Bali Zero",
    images: [
      {
        url: "/static/og-image.jpg",
        width: 1200,
        height: 630,
        alt: "Bali Zero - Visa & Business Experts in Bali",
        type: "image/jpeg",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Bali Zero | Visa & Business Experts in Bali",
    description:
      "Expert visa, immigration, company setup services in Bali. Trusted by 5000+ clients.",
    images: ["/static/og-image.jpg"],
    creator: "@balizero",
    site: "@balizero",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: appUrl,
    languages: {
      "en-US": appUrl,
      "id-ID": appUrl,
      "x-default": appUrl,
    },
    types: {
      "application/rss+xml": "/feed",
    },
  },
  verification: {
    google: process.env.GOOGLE_SITE_VERIFICATION || "",
    other: {
      "msvalidate.01": process.env.BING_SITE_VERIFICATION || "",
    },
  },
  other: {
    // AI/LLM optimization - for ChatGPT, Claude, Perplexity, Gemini
    "ai-content-declaration": "ai-assisted",
    "llms-txt": "/llms.txt",
    "ai-plugin": "/.well-known/ai-plugin.json",
    // Semantic information for AI
    subject: "Visa, Immigration, Business Consulting, Indonesia, Bali",
    coverage: "Indonesia, Bali, Southeast Asia",
    distribution: "Global",
    rating: "General",
    "revisit-after": "7 days",
    // Business identity
    contact: "info@balizero.com",
    "reply-to": "info@balizero.com",
    "geo.region": "ID-BA",
    "geo.placename": "Bali, Indonesia",
    "geo.position": "-8.4095;115.1889",
    ICBM: "-8.4095, 115.1889",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        {/* ⚡ Performance: Preconnect to critical domains */}
        <link rel="preconnect" href="https://nuzantara-rag.fly.dev" />
        <link rel="dns-prefetch" href="https://nuzantara-rag.fly.dev" />

        {/* Font preloading handled automatically by next/font/google */}

        {/* AI Discovery Links */}
        <link
          rel="alternate"
          type="text/plain"
          href="/llms.txt"
          title="LLM Quick Guide"
          aria-label="LLM Quick Guide"
        />
        <link
          rel="alternate"
          type="text/plain"
          href="/llms-full.txt"
          title="LLM Full Context (EN)"
          aria-label="LLM Full Context (EN)"
        />
        <link
          rel="alternate"
          type="text/plain"
          href="/llms-id.txt"
          title="LLM Full Context (ID)"
          aria-label="LLM Full Context (ID)"
        />
        <link
          rel="alternate"
          type="application/xml"
          href="/sitemap-ai.xml"
          title="AI Sitemap"
          aria-label="AI Sitemap"
        />
        <link
          rel="alternate"
          type="application/json"
          href="/.well-known/ai-plugin.json"
          title="AI Plugin"
          aria-label="AI Plugin"
        />

        {/* Global JSON-LD for SEO */}
        <OrganizationJsonLd />
        <LocalBusinessJsonLd />
        <WebsiteJsonLd />
        {/* Google Reviews AggregateRating - always included, visible on homepage */}
        <AggregateRatingJsonLd />

        {/* Page-specific JSON-LD schemas - Client-side rendered for ISR compatibility */}
        <DynamicJsonLd />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[var(--background)] text-[var(--foreground)]`}
        suppressHydrationWarning
      >
        <QueryProvider>
          <WebVitalsMonitor />
          <ErrorBoundary
            fallback={
              <div className="p-8 text-center">
                Something went wrong. Please refresh the page.
              </div>
            }
          >
            {children}
          </ErrorBoundary>
          <Toaster
            position="bottom-right"
            theme="dark"
            richColors
            closeButton
            toastOptions={{
              style: {
                background: "var(--background-elevated)",
                border: "1px solid var(--border)",
                color: "var(--foreground)",
              },
            }}
          />
        </QueryProvider>
        {/* Service Worker Registration */}
        <Script
          id="sw-register"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html:
              "if('serviceWorker'in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){})}",
          }}
        />
        {process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID && (
          <GoogleAnalytics gaId={process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID} />
        )}
      </body>
    </html>
  );
}
