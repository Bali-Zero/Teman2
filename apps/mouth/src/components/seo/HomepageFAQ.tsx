'use client';

import { HOMEPAGE_FAQS, generateFAQSchema } from '@/lib/seo/faq-data';

/**
 * Homepage FAQ Schema Component
 * Injects FAQ structured data for SEO and AI
 */
export function HomepageFAQSchema() {
  const schema = generateFAQSchema(HOMEPAGE_FAQS);

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

/**
 * Service Schema for homepage
 */
export function HomepageServicesSchema() {
  const baseUrl = 'https://balizero.com';

  const services = [
    {
      '@type': 'Service',
      name: 'PT PMA Company Registration',
      description: 'Full foreign company setup in Indonesia including NIB, business licenses, and bank account. 4-8 weeks processing.',
      provider: { '@type': 'Organization', name: 'Bali Zero' },
      areaServed: { '@type': 'Country', name: 'Indonesia' },
      offers: {
        '@type': 'Offer',
        price: '45000000',
        priceCurrency: 'IDR',
        priceValidUntil: '2026-12-31',
      },
      url: `${baseUrl}/services/company`,
    },
    {
      '@type': 'Service',
      name: 'KITAS Visa Processing',
      description: 'Work permit and temporary stay permit for foreigners in Indonesia. Director, Investor, Employee, and Retirement visas available.',
      provider: { '@type': 'Organization', name: 'Bali Zero' },
      areaServed: { '@type': 'Country', name: 'Indonesia' },
      offers: {
        '@type': 'AggregateOffer',
        lowPrice: '14000000',
        highPrice: '50000000',
        priceCurrency: 'IDR',
        offerCount: '8',
      },
      url: `${baseUrl}/services/visa`,
    },
    {
      '@type': 'Service',
      name: 'Golden Visa Indonesia',
      description: 'Premium 5-10 year residence permit for investors and high-net-worth individuals. $350,000+ investment required.',
      provider: { '@type': 'Organization', name: 'Bali Zero' },
      areaServed: { '@type': 'Country', name: 'Indonesia' },
      offers: {
        '@type': 'Offer',
        price: '50000000',
        priceCurrency: 'IDR',
      },
      url: `${baseUrl}/immigration/golden-visa-indonesia`,
    },
    {
      '@type': 'Service',
      name: 'Tax Compliance & Filing',
      description: 'Personal and corporate tax registration, SPT filing, Coretax setup, and tax consultation for expats and businesses.',
      provider: { '@type': 'Organization', name: 'Bali Zero' },
      areaServed: { '@type': 'Country', name: 'Indonesia' },
      offers: {
        '@type': 'AggregateOffer',
        lowPrice: '3000000',
        highPrice: '10000000',
        priceCurrency: 'IDR',
      },
      url: `${baseUrl}/services/tax`,
    },
  ];

  const schema = {
    '@context': 'https://schema.org',
    '@graph': services,
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

/**
 * Combined schema export
 */
export function HomepageSEOSchemas() {
  return (
    <>
      <HomepageFAQSchema />
      <HomepageServicesSchema />
    </>
  );
}
