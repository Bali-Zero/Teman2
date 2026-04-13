/**
 * JSON-LD Structured Data Components
 * For rich snippets in Google, Bing, and AI search
 *
 * IMPORTANT: Uses native <script> tags instead of Next.js Script component
 * to ensure JSON-LD is present in the static HTML for Googlebot and validators.
 */

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

// Organization schema - for brand presence
export function OrganizationJsonLd() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Bali Zero",
    alternateName: "Bali Zero Team",
    url: baseUrl,
    logo: `${baseUrl}/static/balizero-logo-clean.png`,
    sameAs: [
      "https://www.linkedin.com/company/balizero",
      "https://www.instagram.com/balizero",
      "https://www.facebook.com/balizero",
      "https://wa.me/628213107363",
    ],
    contactPoint: {
      "@type": "ContactPoint",
      telephone: "+62-859-0436-9574",
      contactType: "customer service",
      availableLanguage: ["English", "Indonesian"],
    },
    address: {
      "@type": "PostalAddress",
      streetAddress: "Kerobokan",
      addressLocality: "Bali",
      addressRegion: "Bali",
      postalCode: "80361",
      addressCountry: "ID",
    },
    description:
      "Expert visa, immigration, company setup, and business consulting services in Bali, Indonesia.",
  };

  return (
    <script
      id="organization-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Local Business schema - for local SEO
export function LocalBusinessJsonLd() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "ProfessionalService",
    name: "Bali Zero",
    image: `${baseUrl}/static/balizero-logo-clean.png`,
    url: baseUrl,
    telephone: "+62-859-0436-9574",
    email: "info@balizero.com",
    address: {
      "@type": "PostalAddress",
      streetAddress: "Kerobokan",
      addressLocality: "Kerobokan",
      addressRegion: "Bali",
      postalCode: "80361",
      addressCountry: "ID",
    },
    geo: {
      "@type": "GeoCoordinates",
      latitude: -8.4095,
      longitude: 115.1889,
    },
    openingHoursSpecification: {
      "@type": "OpeningHoursSpecification",
      dayOfWeek: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      opens: "09:00",
      closes: "18:00",
    },
    priceRange: "$$",
    areaServed: {
      "@type": "Country",
      name: "Indonesia",
    },
    serviceArea: {
      "@type": "Place",
      name: "Bali, Indonesia",
    },
  };

  return (
    <script
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
}: Readonly<ArticleJsonLdProps>) {
  const articleUrl = `${baseUrl}/${category}/${slug}`;
  const imageUrl = image?.startsWith("http")
    ? image
    : `${baseUrl}${image || "/static/og-image.jpg"}`;

  const schema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: title,
    description: description,
    url: articleUrl,
    image: {
      "@type": "ImageObject",
      url: imageUrl,
      width: 1200,
      height: 630,
    },
    datePublished: publishedAt,
    dateModified: updatedAt || publishedAt,
    author: {
      "@type":
        author?.role === "AI Immigration Advisor" ? "Organization" : "Person",
      name: author?.name || "Bali Zero Editorial",
      url: baseUrl,
    },
    publisher: {
      "@type": "Organization",
      name: "Bali Zero",
      logo: {
        "@type": "ImageObject",
        url: `${baseUrl}/static/balizero-logo-clean.png`,
        width: 200,
        height: 200,
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": articleUrl,
    },
    keywords: tags?.join(", "),
    wordCount: readingTime ? readingTime * 200 : undefined, // Approximate
    articleSection: category,
    inLanguage: "en-US",
    copyrightHolder: { "@type": "Organization", name: "Bali Zero" },
    copyrightYear: new Date(publishedAt).getFullYear(),
    license: "https://balizero.com/terms",
  };

  return (
    <script
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

export function FAQJsonLd({ items }: Readonly<FAQJsonLdProps>) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  return (
    <script
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
  provider = "Bali Zero",
}: Readonly<ServiceJsonLdProps>) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: name,
    description: description,
    url: url.startsWith("http") ? url : `${baseUrl}${url}`,
    provider: {
      "@type": "Organization",
      name: provider,
      url: baseUrl,
    },
    areaServed: {
      "@type": "Country",
      name: "Indonesia",
    },
    offers: price
      ? {
          "@type": "Offer",
          price: price,
          priceCurrency: "IDR",
        }
      : undefined,
  };

  return (
    <script
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

export function BreadcrumbJsonLd({ items }: Readonly<BreadcrumbJsonLdProps>) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url.startsWith("http") ? item.url : `${baseUrl}${item.url}`,
    })),
  };

  return (
    <script
      id="breadcrumb-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// WebSite schema with SearchAction - for sitelinks search
export function WebsiteJsonLd() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Bali Zero",
    alternateName: "Bali Zero - Visa & Business Experts",
    url: baseUrl,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${baseUrl}/kbli-explorer?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };

  return (
    <script
      id="website-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Google Reviews AggregateRating — for rich snippets with stars
export function AggregateRatingJsonLd() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "ProfessionalService",
    name: "Bali Zero",
    url: baseUrl,
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: "5.0",
      bestRating: "5",
      worstRating: "1",
      ratingCount: "700",
      reviewCount: "700",
    },
    priceRange: "$$",
    address: {
      "@type": "PostalAddress",
      addressLocality: "Bali",
      addressCountry: "ID",
    },
  };

  return (
    <script
      id="aggregate-rating-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
