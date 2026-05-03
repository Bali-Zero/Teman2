import type { Metadata } from "next";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

/**
 * SEO-optimized metadata for each category page.
 * Unique titles, descriptions, and canonicals per category.
 */
const CATEGORY_SEO: Record<string, { title: string; description: string }> = {
  visas: {
    title: "Immigration & Visa Guides Bali 2026",
    description:
      "Expert guides on Indonesia visas: KITAS, KITAP, Golden Visa, work permits, retirement visa, digital nomad visa. Updated 2026 requirements from Bali Zero.",
  },
  business: {
    title: "Business Setup & Company Formation Indonesia 2026",
    description:
      "Complete guides to PT PMA company setup, KBLI codes, business licenses, OSS registration. Expert advice for foreign entrepreneurs in Bali.",
  },
  "taxes": {
    title: "Indonesia Tax & Legal Compliance Guides 2026",
    description:
      "Tax compliance guides for expats and businesses in Indonesia. Personal tax, corporate tax, Coretax system, deadlines, and legal requirements.",
  },
  property: {
    title: "Bali Property Investment & Real Estate Guides 2026",
    description:
      "Property guides for foreigners: Hak Pakai, leasehold, villa investment, Airbnb regulations. Expert real estate advice for buying property in Bali.",
  },
  living: {
    title: "Living in Bali - Expat Lifestyle & Relocation Guides",
    description:
      "Guides for living in Bali: cost of living, healthcare, banking, culture, digital nomad life, expat community. Everything you need to know.",
  },
  trends: {
    title: "Tech & Digital Nomad Life in Indonesia 2026",
    description:
      "Digital nomad guides for Bali: visa options, coworking spaces, internet, remote work tips. Stay connected and productive in paradise.",
  },
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  const seo = CATEGORY_SEO[category];

  if (!seo) {
    return {
      title: `${category.charAt(0).toUpperCase() + category.slice(1)} Insights`,
      description: `Expert guides and insights about ${category} in Indonesia and Bali.`,
    };
  }

  const categoryUrl = `${baseUrl}/${category}`;

  return {
    title: seo.title,
    description: seo.description,
    openGraph: {
      type: "website",
      locale: "en_US",
      url: categoryUrl,
      title: `${seo.title} | Bali Zero`,
      description: seo.description,
      siteName: "Bali Zero",
      images: [
        {
          url: `${baseUrl}/static/og-image.jpg`,
          width: 1200,
          height: 630,
          alt: seo.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${seo.title} | Bali Zero`,
      description: seo.description,
      creator: "@balizero",
    },
    alternates: {
      canonical: categoryUrl,
    },
  };
}

export default function CategoryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
