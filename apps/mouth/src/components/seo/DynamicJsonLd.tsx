'use client';

import { usePathname } from 'next/navigation';
import { SERVICES_DATA } from '@/data/services_data';
import { useEffect, useState } from 'react';

interface PageSchema {
  '@context': string;
  '@type': string | string[];
  [key: string]: unknown;
}

export function DynamicJsonLd() {
  const pathname = usePathname();
  const [pageSchemas, setPageSchemas] = useState<PageSchema[]>([]);
  const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';

  useEffect(() => {
    const schemas: PageSchema[] = [];

    // 1. SERVICE DETAIL PAGES: /services/[slug]
    const serviceMatch = pathname?.match(/^\/services\/([^\/]+)$/);
    const serviceSlug = serviceMatch ? serviceMatch[1] : null;
    const service = serviceSlug ? SERVICES_DATA[serviceSlug] : null;

    if (service) {
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

      schemas.push(serviceSchema, faqSchema);
    }

    // Note: Article JSON-LD (Article + Breadcrumb) is handled server-side
    // by ArticleWithFAQJsonLd / EnhancedArticleJsonLd in app/(blog)/[category]/[slug]/page.tsx
    // Do NOT duplicate it here — server-side rendering ensures Googlebot sees it in static HTML.

    // 2. SERVICES LIST PAGE: /services
    if (pathname === '/services') {
      const servicesListSchema = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        name: 'Bali Zero Services',
        description:
          'Complete visa, immigration, company setup, and business consulting services in Bali, Indonesia',
        itemListElement: Object.values(SERVICES_DATA).map((svc, index) => ({
          '@type': 'ListItem',
          position: index + 1,
          item: {
            '@type': 'Service',
            name: svc.name,
            description: svc.description,
            url: `${baseUrl}/services/${svc.slug}`,
          },
        })),
      };
      schemas.push(servicesListSchema);
    }

    // 4. CONTACT PAGE: /contact
    if (pathname === '/contact') {
      const contactPageSchema = {
        '@context': 'https://schema.org',
        '@type': 'ContactPage',
        name: 'Contact Bali Zero',
        description:
          'Get in touch with Bali Zero for visa, immigration, and business consulting services in Bali, Indonesia',
        url: `${baseUrl}/contact`,
        mainEntity: {
          '@type': 'Organization',
          name: 'Bali Zero',
          url: baseUrl,
          contactPoint: [
            {
              '@type': 'ContactPoint',
              telephone: '+62-859-0436-9574',
              contactType: 'customer service',
              availableLanguage: ['English', 'Indonesian'],
              areaServed: 'ID',
            },
            {
              '@type': 'ContactPoint',
              email: 'info@balizero.com',
              contactType: 'customer service',
              availableLanguage: ['English', 'Indonesian'],
            },
          ],
        },
      };
      schemas.push(contactPageSchema);
    }

    // 5. TEAM PAGE: /team
    if (pathname === '/team') {
      const aboutPageSchema = {
        '@context': 'https://schema.org',
        '@type': 'AboutPage',
        name: 'Bali Zero Team',
        description:
          'Meet the expert team at Bali Zero - visa, immigration, and business consulting professionals in Bali, Indonesia',
        url: `${baseUrl}/team`,
        mainEntity: {
          '@type': 'Organization',
          name: 'Bali Zero',
          alternateName: 'Bali Zero Team',
          url: baseUrl,
          description:
            'Expert visa, immigration, company setup, and business consulting services in Bali, Indonesia. Trusted by 1000+ expats.',
          foundingDate: '2023',
          numberOfEmployees: {
            '@type': 'QuantitativeValue',
            value: '10-50',
          },
          address: {
            '@type': 'PostalAddress',
            addressLocality: 'Bali',
            addressRegion: 'Bali',
            addressCountry: 'ID',
          },
        },
      };
      schemas.push(aboutPageSchema);
    }

    setPageSchemas(schemas);
  }, [pathname, baseUrl]);

  if (pageSchemas.length === 0) return null;

  return (
    <>
      {pageSchemas.map((schema, index) => {
        const schemaType = schema['@type'] || 'schema';
        const schemaTypeStr = Array.isArray(schemaType) ? schemaType[0] : schemaType;
        const uniqueId = `json-ld-${schemaTypeStr.toLowerCase()}-${index}`;
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
    </>
  );
}
