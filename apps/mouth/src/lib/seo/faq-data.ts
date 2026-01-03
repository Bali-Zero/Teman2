/**
 * FAQ Data for AI and SEO
 * Used for FAQ schema markup and AI context
 */

export interface FAQItem {
  question: string;
  answer: string;
  category?: 'immigration' | 'business' | 'tax' | 'property' | 'general';
}

// Homepage FAQs - Most common questions
export const HOMEPAGE_FAQS: FAQItem[] = [
  {
    question: 'What is PT PMA and how much does it cost to set up in Indonesia?',
    answer: 'PT PMA (Penanaman Modal Asing) is a foreign-owned limited liability company in Indonesia. The minimum investment requirement is IDR 10 billion (~$620,000 USD), with paid-up capital of IDR 2.5 billion per shareholder. Bali Zero charges IDR 45,000,000 (~$2,800 USD) for full PT PMA registration, which includes NIB, business licenses, and bank account setup. The process takes 4-8 weeks.',
    category: 'business',
  },
  {
    question: 'What is KITAS and what are the different types available in Indonesia?',
    answer: 'KITAS (Kartu Izin Tinggal Terbatas) is a Temporary Stay Permit for foreigners in Indonesia. Types include: C312 (Director KITAS) for PT PMA directors, C313 (Investor KITAS) for shareholders, C314 (Employee KITAS) for workers, E33F (1-year Retirement KITAS) and E33E (5-year Retirement KITAS) for retirees aged 55+. Each type has different requirements and costs.',
    category: 'immigration',
  },
  {
    question: 'Can foreigners own property in Indonesia?',
    answer: 'Foreigners cannot own freehold land (Hak Milik) in Indonesia. However, foreigners CAN own buildings on Hak Pakai (Right to Use) land for up to 80 years, hold long-term leases (Hak Sewa) typically 25-30 years, or own property through a PT PMA company which can hold Hak Guna Bangunan (Right to Build).',
    category: 'property',
  },
  {
    question: 'What is the Golden Visa Indonesia and who qualifies?',
    answer: 'Golden Visa is a premium 5-10 year residence permit launched in 2024 for high-net-worth individuals. Categories include: Investors ($350,000+ investment), Second Home Buyers ($350,000+ property), Directors of companies with $2.5M+ investment, and Specialists. Benefits include multiple entry, long-term stay, and family inclusion. Bali Zero charges IDR 50,000,000 for Golden Visa processing.',
    category: 'immigration',
  },
  {
    question: 'How long can I stay in Bali on a tourist visa?',
    answer: 'Visa on Arrival (VOA) allows 30 days, extendable once for 30 more days (60 total). C1 Tourism visa allows 60 days. For longer stays, you need KITAS (work permit), retirement visa (55+), Second Home Visa (proof of $130,000+), or Golden Visa. Digital nomads can use VOA with extensions or apply for E33G Digital Nomad KITAS.',
    category: 'immigration',
  },
  {
    question: 'What are the tax obligations for expats living in Indonesia?',
    answer: 'If you spend 183+ days in Indonesia within 12 months, you become a tax resident. You must: register for NPWP (tax ID), file annual SPT by March 31, and pay progressive income tax (5-35%). Indonesia has tax treaties with many countries. The new Coretax digital platform (2025-2026) modernizes tax registration and filing.',
    category: 'tax',
  },
  {
    question: 'Can I work on a retirement visa in Indonesia?',
    answer: 'NO. Retirement visas (E33F and E33E) strictly prohibit any employment or business activity in Indonesia. If you want to work legally, you need a work-related KITAS (C312 Director, C313 Investor, or C314 Employee). Violation can result in deportation and visa ban.',
    category: 'immigration',
  },
  {
    question: 'What is the Second Home Visa for Indonesia?',
    answer: 'Second Home Visa is a 5-10 year residence permit for wealthy individuals. Requirements: proof of $130,000+ in bank accounts (not investment required), health insurance, and clean criminal record. Unlike Golden Visa, you don\'t need to invest in Indonesia - just prove you have funds. Bali Zero charges IDR 25,000,000 for processing.',
    category: 'immigration',
  },
];

// Immigration category FAQs
export const IMMIGRATION_FAQS: FAQItem[] = [
  {
    question: 'What documents are needed for KITAS application?',
    answer: 'Common KITAS requirements include: valid passport (18+ months validity), passport photos, sponsoring company documents (NIB, NPWP, domicile letter), RPTKA approval for work permits, CV/resume, educational certificates (for employee KITAS), and health certificate. Specific requirements vary by KITAS type. Bali Zero handles all document preparation.',
    category: 'immigration',
  },
  {
    question: 'How long does KITAS processing take?',
    answer: 'KITAS processing typically takes 3-6 weeks depending on type: Employee KITAS (C314) is fastest at 3-4 weeks, Director/Investor KITAS (C312/C313) takes 4-6 weeks, and Retirement KITAS takes 3-4 weeks. Processing includes RPTKA approval (for work permits), ITAS application, and biometric registration.',
    category: 'immigration',
  },
  {
    question: 'What is KITAP and how do I qualify?',
    answer: 'KITAP (Kartu Izin Tinggal Tetap) is a Permanent Stay Permit. To qualify, you must hold KITAS continuously for 5 years, have Indonesian spouse (for marriage KITAP), or meet special criteria. KITAP is valid for 5 years and renewable indefinitely. It allows you to work without RPTKA renewal. Bali Zero charges IDR 25,000,000 for KITAP processing.',
    category: 'immigration',
  },
];

// Business category FAQs
export const BUSINESS_FAQS: FAQItem[] = [
  {
    question: 'What is NIB and why do I need it?',
    answer: 'NIB (Nomor Induk Berusaha) is a Business Identification Number required for all businesses in Indonesia. It\'s obtained through the OSS (Online Single Submission) system and serves as your primary business license. NIB is required for: bank accounts, tax registration, hiring employees, contracts, and obtaining operational permits.',
    category: 'business',
  },
  {
    question: 'What is the DNI (Negative Investment List)?',
    answer: 'DNI (Daftar Negatif Investasi), now called Investment Priority List, specifies which sectors are open, restricted, or closed to foreign investment. Some sectors require local partners, have maximum foreign ownership limits, or are completely closed to foreigners. Always check current regulations before starting a business. OSS-RBA system automatically validates against DNI.',
    category: 'business',
  },
  {
    question: 'Do I need a local partner for PT PMA?',
    answer: 'Most PT PMA businesses can be 100% foreign-owned. However, some sectors have restrictions: media (max 49% foreign), recruitment agencies (partner required), certain retail/distribution (size limits). The current regulation (PP 10/2021 and updates) allows most services and trading to be 100% foreign-owned.',
    category: 'business',
  },
];

// Generate JSON-LD schema from FAQ items
export function generateFAQSchema(items: FAQItem[]) {
  return {
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
}
