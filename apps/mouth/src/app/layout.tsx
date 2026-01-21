import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import { Toaster } from 'sonner';
import { headers } from 'next/headers';
import { OrganizationJsonLd, LocalBusinessJsonLd, WebsiteJsonLd } from '@/components/seo';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { WebVitalsMonitor } from '@/components/providers/WebVitalsMonitor';
import { SERVICES_DATA } from '@/data/services_data';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

// Production URL - uses environment variable or falls back to production domain
const appUrl =
  process.env.NEXT_PUBLIC_PUBLIC_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'https://balizero.com');

export const metadata: Metadata = {
  metadataBase: new URL(appUrl),
  title: {
    default: 'Bali Zero | Visa, Business & Immigration Experts in Bali, Indonesia',
    template: '%s | Bali Zero',
  },
  description:
    'Expert visa, immigration, company setup, and business consulting services in Bali, Indonesia. PT PMA registration, KITAS, Golden Visa, tax compliance. Trusted by 1000+ expats.',
  keywords: [
    // Primary keywords
    'bali visa',
    'indonesia visa',
    'kitas bali',
    'pt pma indonesia',
    'company setup bali',
    'business license indonesia',
    'golden visa indonesia',
    // Long-tail keywords
    'how to get kitas in bali',
    'start business in indonesia foreigner',
    'retirement visa indonesia',
    'digital nomad visa bali',
    'pt pma registration process',
    'indonesian work permit',
    // Local SEO
    'visa agent bali',
    'immigration consultant bali',
    'notaris bali',
    'tax consultant bali',
    'company formation bali',
    // Brand
    'bali zero',
    'zantara ai',
    'bali zero team',
  ],
  authors: [{ name: 'Bali Zero Team', url: 'https://balizero.com' }],
  creator: 'Bali Zero',
  publisher: 'Bali Zero',
  category: 'Business Services',
  icons: {
    icon: '/static/balizero-logo-clean.png',
    apple: '/static/balizero-logo-clean.png',
    shortcut: '/static/balizero-logo-clean.png',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    alternateLocale: ['id_ID'],
    url: appUrl,
    title: 'Bali Zero | #1 Visa & Business Experts in Bali, Indonesia',
    description:
      'Expert visa, immigration, company setup, and business consulting services in Bali. PT PMA, KITAS, Golden Visa, tax compliance. Trusted by 1000+ expats.',
    siteName: 'Bali Zero',
    images: [
      {
        url: '/static/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'Bali Zero - Visa & Business Experts in Bali',
        type: 'image/jpeg',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Bali Zero | Visa & Business Experts in Bali',
    description:
      'Expert visa, immigration, company setup services in Bali. Trusted by 1000+ expats.',
    images: ['/static/og-image.jpg'],
    creator: '@balizero',
    site: '@balizero',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  alternates: {
    canonical: appUrl,
    languages: {
      'en-US': appUrl,
      'id-ID': `${appUrl}/id`,
    },
  },
  verification: {
    google: process.env.GOOGLE_SITE_VERIFICATION || '',
    // Add when ready: yandex, bing
  },
  other: {
    // AI/LLM optimization - for ChatGPT, Claude, Perplexity, Gemini
    'ai-content-declaration': 'human-created',
    'llms-txt': '/llms.txt',
    'ai-plugin': '/.well-known/ai-plugin.json',
    // Semantic information for AI
    subject: 'Visa, Immigration, Business Consulting, Indonesia, Bali',
    coverage: 'Indonesia, Bali, Southeast Asia',
    distribution: 'Global',
    rating: 'General',
    'revisit-after': '7 days',
    // Business identity
    contact: 'info@balizero.com',
    'reply-to': 'info@balizero.com',
    'geo.region': 'ID-BA',
    'geo.placename': 'Bali, Indonesia',
    'geo.position': '-8.4095;115.1889',
    ICBM: '-8.4095, 115.1889',
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Get current pathname to inject service-specific JSON-LD schemas
  const headersList = await headers();
  const pathname = headersList.get('x-pathname') || headersList.get('x-invoke-path') || '';
  
  // Check if we're on a service detail page
  const serviceMatch = pathname.match(/^\/services\/([^\/]+)$/);
  const serviceSlug = serviceMatch ? serviceMatch[1] : null;
  const service = serviceSlug ? SERVICES_DATA[serviceSlug] : null;

  // Generate service-specific JSON-LD schemas if on a service page
  let serviceSchemas: any[] = [];
  if (service) {
    const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';
    const serviceType = serviceSlug === 'visa' ? 'GovernmentService' : 'ProfessionalService';

    const serviceSchema = {
      '@context': 'https://schema.org',
      '@type': serviceType,
      name: service.name,
      description: service.description,
      provider: {
        '@type': 'Organization',
        name: 'Bali Zero',
        url: baseUrl,
        logo: `${baseUrl}/assets/logo/balizero-logo.png`,
        contactPoint: {
          '@type': 'ContactPoint',
          telephone: '+62-859-0436-9574',
          contactType: 'customer service',
          availableLanguage: ['English', 'Indonesian'],
        },
      },
      areaServed: {
        '@type': 'Country',
        name: 'Indonesia',
      },
      offers: service.packages
        .filter((pkg) => pkg.price !== 'Contact')
        .map((pkg) => ({
          '@type': 'Offer',
          name: pkg.name,
          description: pkg.description,
          price: pkg.price.replace(/\./g, ''),
          priceCurrency: 'IDR',
          availability: 'https://schema.org/InStock',
          validFrom: '2026-01-01',
        })),
      serviceType: service.name,
      hoursAvailable: service.timeline,
    };

    const faqSchema = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: service.faqs.map((faq) => ({
        '@type': 'Question',
        name: faq.question,
        acceptedAnswer: {
          '@type': 'Answer',
          text: faq.answer,
        },
      })),
    };

    serviceSchemas = [serviceSchema, faqSchema];
  }

  return (
    <html lang="en" className="dark">
      <head>
        {/* AI Discovery Links */}
        <link rel="alternate" type="text/plain" href="/llms.txt" title="LLM Context" />
        <link
          rel="alternate"
          type="application/json"
          href="/.well-known/ai-plugin.json"
          title="AI Plugin"
        />
        <link rel="alternate" type="text/yaml" href="/openapi.yaml" title="OpenAPI Spec" />

        {/* Global JSON-LD for SEO */}
        <OrganizationJsonLd />
        <LocalBusinessJsonLd />
        <WebsiteJsonLd />

        {/* Service-specific JSON-LD schemas - Injected in <head> for Schema.org Validator */}
        {serviceSchemas.map((schema, index) => {
          const schemaType = schema['@type'] || 'schema';
          const uniqueId = `json-ld-${schemaType.toLowerCase()}-${index}`;
          return (
            <script
              key={uniqueId}
              id={uniqueId}
              type="application/ld+json"
              dangerouslySetInnerHTML={{
                __html: JSON.stringify(schema).replace(/</g, '\\u003c'),
              }}
            />
          );
        })}
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[var(--background)] text-[var(--foreground)]`}
      >
        <QueryProvider>
          <WebVitalsMonitor />
          {children}
          <Toaster
            position="bottom-right"
            theme="dark"
            richColors
            closeButton
            toastOptions={{
              style: {
                background: 'var(--background-elevated)',
                border: '1px solid var(--border)',
                color: 'var(--foreground)',
              },
            }}
          />
        </QueryProvider>
      </body>
    </html>
  );
}
