/**
 * FAQ Data for AI and SEO
 * Used for FAQ schema markup and AI context
 */

export interface FAQItem {
  question: string;
  answer: string;
  category?: "visas" | "business" | "tax" | "property" | "general";
}

// Homepage FAQs - Most common questions
export const HOMEPAGE_FAQS: FAQItem[] = [
  {
    question:
      "What is PT PMA and how much does it cost to set up in Indonesia?",
    answer:
      "PT PMA (Penanaman Modal Asing) is a foreign-owned limited liability company in Indonesia. Capital requirements, ownership rules, timelines, and service pricing depend on the business activity and current regulations. For live pricing or current setup requirements, use the official pricing and advisory flow rather than static website copy.",
    category: "business",
  },
  {
    question:
      "What is KITAS and what are the different types available in Indonesia?",
    answer:
      "KITAS (Kartu Izin Tinggal Terbatas) is a Temporary Stay Permit for foreigners in Indonesia. Types include: C312 (Director KITAS) for PT PMA directors, C313 (Investor KITAS) for shareholders, C314 (Employee KITAS) for workers, E33F (1-year Retirement KITAS) and E33E (5-year Retirement KITAS) for retirees aged 55+. Each type has different requirements and costs.",
    category: "visas",
  },
  {
    question: "Can foreigners own property in Indonesia?",
    answer:
      "Foreigners cannot own freehold land (Hak Milik) in Indonesia. However, foreigners CAN own buildings on Hak Pakai (Right to Use) land for up to 80 years, hold long-term leases (Hak Sewa) typically 25-30 years, or own property through a PT PMA company which can hold Hak Guna Bangunan (Right to Build).",
    category: "property",
  },
  {
    question: "What is the Golden Visa Indonesia and who qualifies?",
    answer:
      "Golden Visa is a long-stay residence pathway for qualifying investors and high-net-worth individuals. Eligibility, investment thresholds, and processing rules can change, so qualification should always be checked against the current immigration framework and the latest Bali Zero service guidance.",
    category: "visas",
  },
  {
    question: "How long can I stay in Bali on a tourist visa?",
    answer:
      "Short-stay options depend on your nationality and the visa class you use. Entry periods, extension rules, and long-stay alternatives should always be checked against the current immigration rules before travel.",
    category: "visas",
  },
  {
    question: "What are the tax obligations for expats living in Indonesia?",
    answer:
      "Tax obligations depend on residency status, income source, treaty position, and the current tax platform rules. Residency thresholds and filing duties should be verified against the latest tax guidance before acting.",
    category: "tax",
  },
  {
    question: "Can I work on a retirement visa in Indonesia?",
    answer:
      "NO. Retirement visas (E33F and E33E) strictly prohibit any employment or business activity in Indonesia. If you want to work legally, you need a work-related KITAS (C312 Director, C313 Investor, or C314 Employee). Violation can result in deportation and visa ban.",
    category: "visas",
  },
  {
    question: "What is the Second Home Visa for Indonesia?",
    answer:
      "Second Home Visa is a long-stay residence option aimed at financially established applicants. Financial proof, eligibility rules, and processing standards should be checked against the latest immigration policy before applying.",
    category: "visas",
  },
];

// Visas category FAQs
export const IMMIGRATION_FAQS: FAQItem[] = [
  {
    question: "What documents are needed for KITAS application?",
    answer:
      "Common KITAS requirements include: valid passport (18+ months validity), passport photos, sponsoring company documents (NIB, NPWP, domicile letter), RPTKA approval for work permits, CV/resume, educational certificates (for employee KITAS), and health certificate. Specific requirements vary by KITAS type. Bali Zero handles all document preparation.",
    category: "visas",
  },
  {
    question: "How long does KITAS processing take?",
    answer:
      "KITAS processing time depends on the visa type, sponsor readiness, document quality, and current immigration workload. Exact timelines should be treated as operational estimates, not fixed promises.",
    category: "visas",
  },
  {
    question: "What is KITAP and how do I qualify?",
    answer:
      "KITAP (Kartu Izin Tinggal Tetap) is a permanent stay permit for applicants who meet the relevant long-stay or family-based eligibility rules. Qualification pathways and operational requirements should be checked against the current immigration framework.",
    category: "visas",
  },
];

// Business category FAQs
export const BUSINESS_FAQS: FAQItem[] = [
  {
    question: "What is NIB and why do I need it?",
    answer:
      "NIB (Nomor Induk Berusaha) is a Business Identification Number required for all businesses in Indonesia. It's obtained through the OSS (Online Single Submission) system and serves as your primary business license. NIB is required for: bank accounts, tax registration, hiring employees, contracts, and obtaining operational permits.",
    category: "business",
  },
  {
    question: "What is the DNI (Negative Investment List)?",
    answer:
      "DNI (Daftar Negatif Investasi), now called Investment Priority List, specifies which sectors are open, restricted, or closed to foreign investment. Some sectors require local partners, have maximum foreign ownership limits, or are completely closed to foreigners. Always check current regulations before starting a business. OSS-RBA system automatically validates against DNI.",
    category: "business",
  },
  {
    question: "Do I need a local partner for PT PMA?",
    answer:
      "Some PT PMA businesses can be fully foreign-owned, while others have ownership caps, licensing gates, or sector-specific restrictions. The answer depends on the exact KBLI code and current investment rules, so it should be checked case by case.",
    category: "business",
  },
];

// Generate JSON-LD schema from FAQ items
export function generateFAQSchema(items: FAQItem[]) {
  return {
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
}
