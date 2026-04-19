/**
 * Schema.org JSON-LD generator for the 4 Bali Zero funnel pages.
 *
 * Output is consumed by Next.js metadata API + injected as
 * <script type="application/ld+json"> in <head>. Optimized for:
 * - Google AI Overviews (cited sources get +35% CTR)
 * - Perplexity AI citations (2.76x more cites per query vs ChatGPT)
 * - ChatGPT Browse (authority-first model)
 *
 * Pattern: Service schema with FAQ mainEntity for each funnel.
 *
 * Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
 * Plan: docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md Task 7
 * Companion: apps/bali-intel-scraper/scripts/gemini_seo_optimizer.py
 *            (does same for blog articles)
 */

export type Funnel = "visa" | "kbli" | "tax" | "property";

interface FAQEntry {
  question: string;
  answer: string;
}

const PROVIDER_BLOCK = {
  "@type": "LegalService",
  name: "Bali Zero",
  url: "https://balizero.com",
  telephone: "+62-821-3107-363",
  address: {
    "@type": "PostalAddress",
    addressLocality: "Kerobokan",
    addressRegion: "Bali",
    addressCountry: "ID",
  },
  description:
    "Indonesian business advisory firm: visa, PT PMA, tax, property. Licensed konsultan pajak, registered PPJK. 5,000+ expat cases since 2019.",
  aggregateRating: {
    "@type": "AggregateRating",
    ratingValue: "4.9",
    reviewCount: "1200",
  },
};

const FUNNEL_CONFIG: Record<
  Funnel,
  {
    serviceType: string;
    description: string;
    faq: FAQEntry[];
  }
> = {
  visa: {
    serviceType: "Visa & Immigration Services",
    description:
      "KITAS, KITAP, Golden Visa, E33G Remote Worker, E28A Investor, Tourist Visa applications and extensions for foreigners in Indonesia.",
    faq: [
      {
        question: "How much does an E33G Remote Worker KITAS cost in 2026?",
        answer:
          "Bali Zero processes E33G Remote Worker KITAS for $1,850 USD all-inclusive. Government fees are separate. Typical processing time: 6-8 weeks. Eligible: foreigners working remotely for non-Indonesian clients with proven income $2,000+/month.",
      },
      {
        question: "What is the difference between KITAS and KITAP?",
        answer:
          "KITAS is a temporary stay permit (1-2 years renewable). KITAP is permanent (5 years renewable indefinitely after holding KITAS for 3-4 years). KITAP holders gain near-citizen rights minus voting and government employment.",
      },
      {
        question: "Can I work in Indonesia on a B211A visa?",
        answer:
          "No. B211A is a visit visa, not a work permit. Working on B211A risks deportation and 5-year ban. For employment in Indonesian entities you need E23 KITAS with RPTKA work permit. For your own PT PMA: E28A Investor KITAS.",
      },
    ],
  },
  kbli: {
    serviceType: "PT PMA Company Setup & KBLI Classification",
    description:
      "Foreign-owned company (PT PMA) registration in Indonesia. KBLI 2025 business classification with 1,563 codes. Notaris filing, OSS submission, NIB issuance.",
    faq: [
      {
        question:
          "What is the minimum capital for a PT PMA in Indonesia in 2026?",
        answer:
          "Stated investment: IDR 10 billion (~$625K USD). Paid-up capital per shareholder: IDR 2.5 billion (~$156K USD). Cash needed at registration day-1: only IDR 7-10 million (~$450-650 USD). The IDR 10 billion is investment commitment over time, not cash at the bank.",
      },
      {
        question: "How long does PT PMA registration take with Bali Zero?",
        answer:
          "Standard: 4-6 weeks from notaris akta to NIB issuance. Bali Zero pricing: $1,850 USD setup fee. KBLI code selection consultation included. We file via OSS, handle PT PMA tax registration, BPJS enrollment, and bank account opening guidance.",
      },
      {
        question: "Can a foreigner own 100% of a PT PMA in Indonesia?",
        answer:
          "Yes for most KBLI codes — 100% foreign ownership is allowed in over 800 sectors under DNI 2021/100. Restricted sectors: media, defense, certain agriculture. Check the specific KBLI code on balizero.com/kbli for your business activity.",
      },
    ],
  },
  tax: {
    serviceType: "Indonesian Tax Compliance Services",
    description:
      "Monthly PPh 21, PPN, annual SPT, BPJS, LKPM, CoreTax integration for foreign-owned PT PMA and individual tax residents. Licensed konsultan pajak.",
    faq: [
      {
        question:
          "Do I need to pay Indonesian tax on my foreign income as a KITAS holder?",
        answer:
          "If you stay in Indonesia 183+ days in any 12-month period, you become a tax resident and worldwide income is taxable in Indonesia (subject to DTAA relief with your origin country). PPh 21 brackets: 5/15/25/30/35%. Annual SPT deadline: March 31.",
      },
      {
        question: "How much does Bali Zero charge for monthly tax compliance?",
        answer:
          "PT PMA monthly compliance package: $220 USD/month covering PPh 21 employees, PPh 25 corporate prepayment, PPN, BPJS Kesehatan + Ketenagakerjaan submission. Annual SPT corporate: $450 additional. CoreTax integration native.",
      },
      {
        question: "What happens if I miss an Indonesian tax filing deadline?",
        answer:
          "Late filing penalty: IDR 100,000-500,000 per filing. Late payment penalty: 2% per month of unpaid amount. Persistent non-compliance can trigger tax audit and KITAS issues. Bali Zero monitors deadlines and sends alerts 7 days before due date.",
      },
    ],
  },
  property: {
    serviceType: "Bali Property Due Diligence & Land Title Services",
    description:
      "Land due diligence, zoning verification (PostGIS-backed), Hak Pakai / Hak Sewa / HGB title structuring for foreign buyers in Bali. PP 18/2021 compliant.",
    faq: [
      {
        question: "Can a foreigner own land freehold in Bali?",
        answer:
          "No. Foreigners cannot hold Hak Milik (freehold) in Indonesia. Three legal options: Hak Pakai (right to use, max 80 years renewable), Hak Sewa (leasehold, max 30 years), or HGB (Right to Build) via your own PT PMA company. Nominee agreements are illegal and unenforceable under Indonesian law.",
      },
      {
        question: "How much does property due diligence cost with Bali Zero?",
        answer:
          "Standard due diligence: $850 USD per plot. Includes: zoning verification via PostGIS layer, title certificate verification at BPN, encumbrance check, Perda compliance (e.g., Bali Perda 4/2026 on land conversion), seller identity verification.",
      },
      {
        question:
          "What is the difference between Hak Pakai and HGB for foreign buyers?",
        answer:
          "Hak Pakai: right to use a plot you do not own. Foreigners can hold directly on individual basis. Maximum 80 years total. HGB: Right to Build, must be held via PT PMA. Renewable 30+20+30 years. HGB is preferred for commercial development; Hak Pakai for personal residence.",
      },
    ],
  },
};

export function buildFunnelSchema(funnel: Funnel): Record<string, unknown> {
  const config = FUNNEL_CONFIG[funnel];
  const baseUrl = "https://balizero.com";
  const funnelUrl = `${baseUrl}/${funnel === "kbli" ? "kbli" : funnel}`;

  return {
    "@context": "https://schema.org",
    "@type": "Service",
    "@id": `${funnelUrl}#service`,
    serviceType: config.serviceType,
    description: config.description,
    provider: PROVIDER_BLOCK,
    areaServed: "Indonesia",
    url: funnelUrl,
    mainEntity: config.faq.map((entry) => ({
      "@type": "Question",
      name: entry.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: entry.answer,
      },
    })),
  };
}

export function buildCombinedHomepageSchema(): Record<string, unknown> {
  const allFunnelSchemas = (["visa", "kbli", "tax", "property"] as const).map(
    buildFunnelSchema,
  );
  return {
    "@context": "https://schema.org",
    "@graph": allFunnelSchemas,
  };
}
