/**
 * JSON-LD Structured Data Components
 * For rich snippets in Google, Bing, and AI search
 */

import Script from 'next/script';

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';

// Organization schema - for brand presence
export function OrganizationJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Bali Zero',
    alternateName: 'Bali Zero Team',
    url: baseUrl,
    logo: `${baseUrl}/images/balizero-logo-clean.png`,
    sameAs: [
      'https://instagram.com/balizero',
      'https://linkedin.com/company/balizero',
      'https://wa.me/6281234567890',
    ],
    contactPoint: {
      '@type': 'ContactPoint',
      telephone: '+62-812-3456-7890',
      contactType: 'customer service',
      availableLanguage: ['English', 'Indonesian'],
    },
    address: {
      '@type': 'PostalAddress',
      addressLocality: 'Bali',
      addressCountry: 'ID',
    },
    description: 'Expert visa, immigration, company setup, and business consulting services in Bali, Indonesia.',
  };

  return (
    <Script
      id="organization-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Local Business schema - for local SEO
export function LocalBusinessJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'ProfessionalService',
    name: 'Bali Zero',
    image: `${baseUrl}/images/balizero-logo-clean.png`,
    url: baseUrl,
    telephone: '+62-812-3456-7890',
    email: 'hello@balizero.com',
    address: {
      '@type': 'PostalAddress',
      streetAddress: 'Bali',
      addressLocality: 'Denpasar',
      addressRegion: 'Bali',
      postalCode: '80361',
      addressCountry: 'ID',
    },
    geo: {
      '@type': 'GeoCoordinates',
      latitude: -8.4095,
      longitude: 115.1889,
    },
    openingHoursSpecification: {
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
      opens: '09:00',
      closes: '18:00',
    },
    priceRange: '$$',
    areaServed: {
      '@type': 'Country',
      name: 'Indonesia',
    },
    serviceArea: {
      '@type': 'Place',
      name: 'Bali, Indonesia',
    },
  };

  return (
    <Script
      id="localbusiness-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Article schema - for blog posts
interface ArticleJsonLdProps {
  title: string;
  description: string;
  slug: string;
  category: string;
  publishedAt: string;
  updatedAt?: string;
  author?: {
    name: string;
    role?: string;
  };
  image?: string;
  tags?: string[];
  readingTime?: number;
}

export function ArticleJsonLd({
  title,
  description,
  slug,
  category,
  publishedAt,
  updatedAt,
  author,
  image,
  tags,
  readingTime,
}: ArticleJsonLdProps) {
  const articleUrl = `${baseUrl}/${category}/${slug}`;
  const imageUrl = image?.startsWith('http') ? image : `${baseUrl}${image || '/images/og-image.jpg'}`;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: title,
    description: description,
    url: articleUrl,
    image: {
      '@type': 'ImageObject',
      url: imageUrl,
      width: 1200,
      height: 630,
    },
    datePublished: publishedAt,
    dateModified: updatedAt || publishedAt,
    author: {
      '@type': author?.role === 'AI Immigration Advisor' ? 'Organization' : 'Person',
      name: author?.name || 'Bali Zero Editorial',
      url: baseUrl,
    },
    publisher: {
      '@type': 'Organization',
      name: 'Bali Zero',
      logo: {
        '@type': 'ImageObject',
        url: `${baseUrl}/images/balizero-logo-clean.png`,
        width: 200,
        height: 200,
      },
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': articleUrl,
    },
    keywords: tags?.join(', '),
    wordCount: readingTime ? readingTime * 200 : undefined, // Approximate
    articleSection: category,
    inLanguage: 'en-US',
  };

  return (
    <Script
      id="article-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// FAQ schema - for articles with FAQ sections
interface FAQItem {
  question: string;
  answer: string;
}

interface FAQJsonLdProps {
  items: FAQItem[];
}

export function FAQJsonLd({ items }: FAQJsonLdProps) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.answer,
      },
    })),
  };

  return (
    <Script
      id="faq-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Service schema - for service pages
interface ServiceJsonLdProps {
  name: string;
  description: string;
  url: string;
  price?: string;
  provider?: string;
}

export function ServiceJsonLd({
  name,
  description,
  url,
  price,
  provider = 'Bali Zero',
}: ServiceJsonLdProps) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Service',
    name: name,
    description: description,
    url: url.startsWith('http') ? url : `${baseUrl}${url}`,
    provider: {
      '@type': 'Organization',
      name: provider,
      url: baseUrl,
    },
    areaServed: {
      '@type': 'Country',
      name: 'Indonesia',
    },
    offers: price
      ? {
          '@type': 'Offer',
          price: price,
          priceCurrency: 'IDR',
        }
      : undefined,
  };

  return (
    <Script
      id="service-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Breadcrumb schema - for navigation
interface BreadcrumbItem {
  name: string;
  url: string;
}

interface BreadcrumbJsonLdProps {
  items: BreadcrumbItem[];
}

export function BreadcrumbJsonLd({ items }: BreadcrumbJsonLdProps) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url.startsWith('http') ? item.url : `${baseUrl}${item.url}`,
    })),
  };

  return (
    <Script
      id="breadcrumb-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// WebSite schema with SearchAction - for sitelinks search
export function WebsiteJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Bali Zero',
    alternateName: 'Bali Zero - Visa & Business Experts',
    url: baseUrl,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${baseUrl}/?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };

  return (
    <Script
      id="website-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
