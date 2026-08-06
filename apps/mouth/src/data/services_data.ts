import * as React from "react";
import { Globe, Building2, Calculator, Home } from "lucide-react";
import { getExactPricingSnapshotEntries } from "@/lib/pricing-snapshot";

export interface ServicePackage {
  name: string;
  description: string;
  /** Non-monetary legacy label. Public rendering never trusts this value. */
  price: string;
  features: string[];
  popular: boolean;
  /** Optional deep-link to a dedicated landing page (rendered in the
   *  pricing modal below the WhatsApp CTA). */
  link?: { href: string; label: string };
  /** Optional exact PricingTool SSOT identity. Missing rows always abstain. */
  livePriceKey?: string;
  livePriceCategory?: string;
}

export interface ServiceData {
  name: string;
  slug: string;
  tagline: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  bgColor: string;
  iconColor: string;
  timeline: string;
  documentsRequired: string;
  validity: string;
  packages: ServicePackage[];
  included: string[];
  requirements: {
    documents: string[];
    eligibility: string[];
  };
  faqs: {
    question: string;
    answer: string;
  }[];
}

const VISA_PRICING_CATEGORIES = [
  "single_entry_visas",
  "multiple_entry_visas",
  "kitas_permits",
  "kitap_permits",
  "other_process",
  "urgent_processing",
] as const;

const POPULAR_VISA_PRICING_KEYS = new Set([
  "C1 Tourism",
  "Investor KITAS 2 Years (Offshore)",
  "E33G Remote Worker (Offshore)",
]);
const SEPARATE_MONETARY_DETAIL =
  /(?:\bIDR\s*\d|\b\d[\d.,]*\s*IDR\b|\bRp\.?\s*\d)/i;

function withoutSeparateMonetaryDetail(value: string | null): value is string {
  return Boolean(value?.trim()) && !SEPARATE_MONETARY_DETAIL.test(value as string);
}

const VISA_SERVICE_PACKAGES: ServicePackage[] = VISA_PRICING_CATEGORIES.flatMap(
  (category) =>
    getExactPricingSnapshotEntries(category).map((entry) => ({
      name: entry.name,
      description:
        [entry.description_en, entry.notes].find(withoutSeparateMonetaryDetail) ??
        `Bali Zero service: ${entry.name}`,
      price: "Contact",
      features: [entry.duration, entry.validity, entry.notes].filter(
        withoutSeparateMonetaryDetail,
      ),
      popular: POPULAR_VISA_PRICING_KEYS.has(entry.key),
      livePriceKey: entry.key,
      livePriceCategory: category,
      ...(entry.key === "E33 Second Home (5 Years)"
        ? {
            link: {
              href: "/visa/second-home",
              label: "Second Home Visa guide — free fit memo",
            },
          }
        : {}),
    })),
);

export const SERVICES_DATA: Record<string, ServiceData> = {
  visa: {
    name: "Visa & Immigration",
    slug: "visa",
    tagline: "Complete visa solutions for living and working in Indonesia",
    description:
      "Navigate Indonesia's immigration system with confidence. From short-term visit visas to permanent residency, we handle all visa types with full government compliance and ongoing support.",
    icon: Globe,
    bgColor: "bg-rose-500/10",
    iconColor: "text-rose-400",
    timeline: "Varies by visa type and sponsor readiness",
    documentsRequired: "Document set varies by pathway",
    validity: "Depends on permit class",
    packages: VISA_SERVICE_PACKAGES,
    included: [
      "Document review and preparation",
      "Government liaison and submission",
      "Status tracking and updates",
      "Translation services",
      "Immigration interview coaching",
      "SKTT/SKLD registration",
      "Re-entry permit arrangement",
      "Renewal reminders",
    ],
    requirements: {
      documents: [
        "Valid passport (min 18 months validity)",
        "Passport-size photos (4x6, red background)",
        "Sponsorship letter (for KITAS)",
        "CV/Resume and educational certificates",
        "Proof of income/financial capacity",
        "Medical check-up results",
        "Police clearance from home country",
      ],
      eligibility: [
        "No criminal record",
        "Valid sponsor (company or individual)",
        "Meet minimum investment (for investor visa)",
        "Relevant qualifications (for work visa)",
        "Age 55+ for retirement KITAS",
      ],
    },
    faqs: [
      {
        question: "How long does KITAS processing take?",
        answer:
          "Most visas and KITAS (C, D, E series) take 7-10 days from application to e-visa issuance. Only Working and Freelance KITAS (E23) take 4-6 weeks due to RPTKA and IMTA work permit approval process.",
      },
      {
        question: "What's the difference between offshore and onshore?",
        answer:
          "Offshore means applying from outside Indonesia before arrival; onshore means converting from within Indonesia while on another visa. They are distinct PricingTool services and may have different current all-inclusive prices.",
      },
      {
        question: "Do I need a work permit (IMTA) for all KITAS?",
        answer:
          "No. Only Working KITAS (E23) requires IMTA. Digital Nomad (E33G), Investor (E28), Retirement (E33E/F), and Family visas (E31) do NOT require IMTA - they use different legal frameworks.",
      },
      {
        question: "What is the Digital Nomad KITAS (E33G)?",
        answer:
          "E33G is for remote workers earning foreign income while living in Indonesia. No IMTA needed, 1-year validity, 7-10 days processing. You cannot work for Indonesian companies - only foreign employers/clients.",
      },
      {
        question: "What is the path to permanent residency (KITAP)?",
        answer:
          "After holding KITAS for 3-5 consecutive years (depending on category), you can apply for KITAP. Investor KITAP requires 3 consecutive Investor KITAS; Working KITAP requires 4 consecutive years.",
      },
      {
        question: "What is the Second Home Visa (E33)?",
        answer:
          "E33 is a long-term residence visa for high-net-worth individuals, with an initial validity of up to 5 years. It requires qualifying financial evidence, such as a USD 130,000 deposit in a state-owned Indonesian bank or eligible property ownership. No sponsor is required, and eligible family members can apply through dependent routes.",
      },
    ],
  },
  company: {
    name: "Company Setup & Licenses",
    slug: "company",
    tagline: "From licenses to structure — launch your business fast",
    description:
      "Start your Indonesian business the right way. We handle PT PMA/PMDN formation, business licensing through OSS, special permits like alcohol licenses, and ongoing compliance so you can focus on growth.",
    icon: Building2,
    bgColor: "bg-orange-500/10",
    iconColor: "text-orange-400",
    timeline: "2-12 weeks",
    documentsRequired: "10-15 docs",
    validity: "Perpetual",
    packages: [
      {
        name: "Company Revision",
        description: "Changes to existing company",
        price: "Check live pricing",
        features: [
          "Director/shareholder changes",
          "Business activity updates",
          "Address changes",
          "Capital adjustments",
          "Ministry of Law filing",
        ],
        popular: false,
      },
      {
        name: "SLHS (Hygiene Certificate)",
        description: "Mandatory for F&B businesses",
        price: "Check live pricing",
        features: [
          "Sertifikat Laik Higiene Sanitasi",
          "Required for all restaurants/cafés",
          "Dinas Kesehatan approval",
          "3-4 weeks processing",
          "Full documentation support",
        ],
        popular: false,
      },
      {
        name: "Alcohol License (NPBBKC)",
        description: "Golongan A+B+C for alcohol sales",
        price: "Check live pricing",
        features: [
          "Restaurant/bar alcohol permit",
          "Golongan A (≤5%), B (5-20%), C (>20%)",
          "Bea Cukai registration",
          "45-60 days processing",
          "Renewal guidance",
        ],
        popular: false,
      },
      {
        name: "PT PMA/PMDN Setup",
        description: "Full company establishment",
        price: "Check live pricing",
        features: [
          "Company registration",
          "Deed of establishment",
          "NIB & OSS licenses",
          "Tax registration (NPWP)",
          "Bank account assistance",
          "Company stamp",
        ],
        popular: true,
      },
    ],
    included: [
      "Company name reservation",
      "Deed of establishment",
      "Ministry of Law approval",
      "NIB (Business ID Number)",
      "OSS licenses & permits",
      "Tax registration (NPWP/PKP)",
      "Company stamp",
      "Digital document copies",
    ],
    requirements: {
      documents: [
        "Shareholder passports/KTP",
        "Director passport & KITAS (if foreign)",
        "Proof of address (all shareholders)",
        "Company name options (3)",
        "Business plan summary",
        "Paid-up capital proof",
      ],
      eligibility: [
        "Minimum 2 shareholders",
        "Minimum 1 director",
        "Paid-up capital (varies by sector)",
        "Business activity on positive list",
      ],
    },
    faqs: [
      {
        question: "What is the minimum capital for PT PMA?",
        answer:
          "Capital and investment requirements depend on the exact business activity and current regulation. We verify the live requirement before advising on structure or registration.",
      },
      {
        question: "Can foreigners own 100% of a PT PMA?",
        answer:
          "Yes, for most business sectors. Some sectors have foreign ownership restrictions. We'll advise on your specific case.",
      },
      {
        question: "How long does PT PMA setup take?",
        answer:
          "Setup timing depends on the business activity, licensing path, and document readiness. We treat timelines as operational estimates, not fixed promises.",
      },
      {
        question: "Do I need a physical office for my company?",
        answer:
          "Yes, Indonesian law requires a registered business address. We can help with virtual office solutions that meet legal requirements.",
      },
    ],
  },
  tax: {
    name: "Tax & BPJS Services",
    slug: "tax",
    tagline: "Navigate Indonesia's tax system with confidence",
    description:
      "Indonesian tax compliance made simple. From NPWP registration to annual SPT filing, BPJS enrollment to monthly reporting — we handle it all with expert precision.",
    icon: Calculator,
    bgColor: "bg-amber-500/10",
    iconColor: "text-amber-400",
    timeline: "Ongoing",
    documentsRequired: "Varies",
    validity: "Annual",
    packages: [
      {
        name: "NPWP Personal + Coretax",
        description: "Personal tax ID registration",
        price: "Check live pricing",
        features: [
          "Personal NPWP registration",
          "Coretax system integration",
          "Full documentation support",
          "Digital NPWP card",
        ],
        popular: false,
      },
      {
        name: "NPWPD Corporate",
        description: "Corporate/regional tax ID",
        price: "Check live pricing",
        features: [
          "Corporate tax ID registration",
          "Regional tax registration",
          "Company documentation",
          "Tax office liaison",
        ],
        popular: false,
      },
      {
        name: "SPT Annual Personal",
        description: "Individual tax return filing",
        price: "Check live pricing",
        features: [
          "Personal income tax return",
          "Income calculation",
          "Deduction optimization",
          "E-filing submission",
        ],
        popular: false,
      },
      {
        name: "SPT Annual Company (Zero)",
        description: "For dormant/zero-activity companies",
        price: "Check live pricing",
        features: [
          "Zero-activity tax return",
          "Company & personal filing",
          "Compliance documentation",
          "E-filing submission",
        ],
        popular: false,
      },
      {
        name: "SPT Annual Company (Operational)",
        description: "For active companies",
        price: "Check live pricing",
        features: [
          "Full company tax return",
          "Personal director filing included",
          "Financial statement review",
          "E-filing submission",
        ],
        popular: true,
      },
      {
        name: "Monthly Tax Report",
        description: "Ongoing tax compliance",
        price: "Check live pricing",
        features: [
          "Monthly PPh 21/23/26 filing",
          "PPN (VAT) reporting",
          "Payment slip preparation",
          "Deadline management",
        ],
        popular: false,
      },
      {
        name: "BPJS Health Insurance",
        description: "Mandatory health coverage",
        price: "Check live pricing",
        features: [
          "Company BPJS Kesehatan registration",
          "Minimum 2 employees",
          "Employee enrollment",
          "Monthly administration",
        ],
        popular: false,
      },
      {
        name: "BPJS Employment Insurance",
        description: "Mandatory employment coverage",
        price: "Check live pricing",
        features: [
          "BPJS Ketenagakerjaan registration",
          "JHT, JP, JKK, JKM coverage",
          "Minimum 2 employees",
          "Monthly administration",
        ],
        popular: false,
      },
      {
        name: "LKPM Report",
        description: "Investment Activity Report",
        price: "Check live pricing",
        features: [
          "Quarterly LKPM submission",
          "OSS compliance",
          "Investment progress report",
          "Government liaison",
        ],
        popular: false,
      },
    ],
    included: [
      "NPWP registration/update",
      "Tax calculation & filing",
      "Payment slip preparation (SSP)",
      "Archive of all filings",
      "Deadline reminders",
      "Tax office liaison",
      "Audit support",
      "Tax optimization advice",
    ],
    requirements: {
      documents: [
        "NPWP (Tax ID) or application docs",
        "Previous year tax returns (if any)",
        "Income statements/certificates",
        "Bank statements",
        "Business financial records",
        "Employee data (for corporate)",
      ],
      eligibility: [
        "Valid passport/KTP",
        "Indonesian resident status (for personal)",
        "Active company with NIB (for corporate)",
        "KITAS holders must file taxes",
      ],
    },
    faqs: [
      {
        question: "When is the tax filing deadline?",
        answer:
          "Personal tax (SPT) is due March 31. Corporate tax is due April 30. Monthly taxes are due by the 15th of the following month.",
      },
      {
        question: "Do expats need to file Indonesian taxes?",
        answer:
          "Yes, if you stay 183+ days in Indonesia, you're a tax resident and must file. KITAS holders are automatically tax residents. We can help determine your status.",
      },
      {
        question: "What are the tax rates in Indonesia?",
        answer:
          "Tax rates depend on taxpayer status, income type, incentive eligibility, and current rules. We verify the live rates before giving tax guidance.",
      },
      {
        question: "What is the difference between PPh 21, 23, and 26?",
        answer:
          "PPh 21 is employee income tax, PPh 23 is withholding on services/royalties, and PPh 26 is withholding for non-residents. Each has different rates and filing requirements.",
      },
    ],
  },
  property: {
    name: "Real Estate Services",
    slug: "property",
    tagline: "Secure property with legal clarity and guidance",
    description:
      "Navigate Indonesian property law with confidence. From due diligence to leasehold agreements, building permits to ownership structures — we protect your investment every step of the way.",
    icon: Home,
    bgColor: "bg-emerald-500/10",
    iconColor: "text-emerald-400",
    timeline: "Depends on transaction type and due diligence scope",
    documentsRequired: "Varies",
    validity: "Per transaction",
    packages: [
      {
        name: "Legal Due Diligence",
        description: "Complete property verification",
        price: "Contact",
        features: [
          "Certificate authenticity check",
          "Ownership history verification",
          "Zoning & land use compliance",
          "Encumbrance/lien search",
          "Detailed written report",
        ],
        popular: false,
      },
      {
        name: "Leasehold Agreement (Hak Sewa)",
        description: "Long-term rental contracts",
        price: "Contact",
        features: [
          "Contract drafting in English/Indonesian",
          "Terms negotiation support",
          "Notarization & legalization",
          "Registration at land office",
          "Up to 25+25+25 year terms",
        ],
        popular: true,
      },
      {
        name: "IMB & Building Permits",
        description: "Construction permits",
        price: "Contact",
        features: [
          "Building permit application (IMB/PBG)",
          "Site plan approval",
          "Environmental compliance (AMDAL/UKL-UPL)",
          "Occupancy certificate (SLF)",
          "Renovation permits",
        ],
        popular: false,
      },
      {
        name: "Ownership Structures (PT PMA)",
        description: "Foreign ownership solutions",
        price: "Contact",
        features: [
          "PT PMA for property holding",
          "Hak Guna Bangunan (HGB) rights",
          "Asset protection setup",
          "Tax-efficient structuring",
          "Succession planning",
        ],
        popular: false,
      },
    ],
    included: [
      "Property inspection coordination",
      "Legal document review",
      "Ownership & title verification",
      "Tax assessment review (PBB/BPHTB)",
      "Contract drafting/review",
      "Notary coordination",
      "Land office registration",
      "Post-transaction support",
    ],
    requirements: {
      documents: [
        "Property certificate copy (SHM/HGB/SHGB)",
        "Owner ID/company documents",
        "Tax payment receipts (PBB)",
        "Building permit (IMB/PBG)",
        "Site plan & location permit",
        "Buyer identification (passport/KTP)",
      ],
      eligibility: [
        "Foreigners can lease (up to 80 years total)",
        "PT PMA can hold HGB rights",
        "Hak Pakai available for KITAS holders",
        "Investment thresholds may apply",
      ],
    },
    faqs: [
      {
        question: "Can foreigners own property in Indonesia?",
        answer:
          "Foreigners cannot own freehold (Hak Milik) but can hold long-term leases (Hak Sewa up to 80 years), Hak Pakai (Right of Use), or own through a PT PMA company.",
      },
      {
        question: "What is Hak Guna Bangunan (HGB)?",
        answer:
          "HGB is a right to build and own structures on land. PT PMA companies can hold HGB for 30+20+20 years (70 years total), renewable.",
      },
      {
        question: "Is nominee ownership safe?",
        answer:
          "Nominee arrangements are legally risky and can result in total loss of your investment. We strongly recommend proper structures like PT PMA or notarized leases.",
      },
      {
        question: "What is the difference between IMB and PBG?",
        answer:
          "IMB (Izin Mendirikan Bangunan) is the old building permit system. PBG (Persetujuan Bangunan Gedung) is the new system under OSS. We handle both.",
      },
    ],
  },
};
