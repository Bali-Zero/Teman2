import type { ArticleCategory } from "./types";

/**
 * SEO-optimized metadata for each category page.
 * Unique titles, descriptions, and canonicals per category.
 *
 * This is also the parent layout and article metadata routing allow-list. Typed
 * `Record<ArticleCategory, …>` rather than `Record<string, …>` on purpose: the
 * key set and `ArticleCategory` can no longer drift apart without a compile
 * error, which is what makes it safe to 404 on anything absent from it.
 */
export const CATEGORY_SEO: Record<
  ArticleCategory,
  { title: string; description: string }
> = {
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
  taxes: {
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
