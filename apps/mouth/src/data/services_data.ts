import * as React from "react";
import { Globe, Building2, Calculator, Home } from "lucide-react";

export interface ServicePackage {
  name: string;
  description: string;
  price: string;
  features: string[];
  popular: boolean;
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
    packages: [
      // ═══════════════════════════════════════════════════════════
      // VISIT VISAS (C Series) - Single Entry
      // ═══════════════════════════════════════════════════════════
      {
        name: "C1 - Tourism Visit",
        description: "Tourism, family visits, social activities",
        price: "Check live pricing",
        features: [
          "60 days (extendable 4x to 180 days)",
          "7-10 days processing",
          "Extension: 1.700.000 IDR each",
        ],
        popular: false,
      },
      {
        name: "C2 - Business Visit",
        description: "Business meetings, negotiations, conferences",
        price: "Check live pricing",
        features: [
          "60 days (extendable to 180 days)",
          "7-10 days processing",
          "No work permit required",
        ],
        popular: false,
      },
      {
        name: "C3 - Government Assignment",
        description: "Foreign government officials",
        price: "Contact",
        features: [
          "60 days validity",
          "Official assignment letter required",
          "Government liaison support",
        ],
        popular: false,
      },
      {
        name: "C4 - Journalism/Film",
        description: "Journalists, film crews, media production",
        price: "Contact",
        features: [
          "60 days validity",
          "Press credentials required",
          "Ministry approval needed",
        ],
        popular: false,
      },
      {
        name: "C5/C5A - Content Creator",
        description: "Influencers, YouTubers, content creators",
        price: "Contact",
        features: [
          "60-90 days validity",
          "Social media documentation",
          "No monetization in Indonesia",
        ],
        popular: false,
      },
      {
        name: "C6 - Medical Treatment",
        description: "Medical tourism and treatment",
        price: "Contact",
        features: [
          "60 days (extendable)",
          "Hospital appointment letter",
          "Medical documentation support",
        ],
        popular: false,
      },
      {
        name: "C7/C7AB - Professional Events",
        description: "Chefs, artists, musicians, performers",
        price: "Check live pricing",
        features: [
          "30 days validity",
          "Event-based permit",
          "Including urgent processing",
        ],
        popular: false,
      },
      {
        name: "C8 - Sports Events",
        description: "Athletes, coaches, sports competitions",
        price: "Contact",
        features: [
          "Event duration validity",
          "Federation invitation required",
          "Team support available",
        ],
        popular: false,
      },
      {
        name: "C18 - Work Trial",
        description: "Job trials and skill assessments",
        price: "Check live pricing",
        features: [
          "90 days validity",
          "Company sponsorship required",
          "Path to Working KITAS",
        ],
        popular: false,
      },
      {
        name: "C22A - Academic Internship",
        description: "University internship programs",
        price: "Check live pricing",
        features: [
          "60 days (or 5.8M for 180 days)",
          "Academic institution required",
          "Student documentation",
        ],
        popular: false,
      },
      {
        name: "C22B - Skills Development",
        description: "Company training programs",
        price: "Check live pricing",
        features: [
          "60 days (or 5.8M for 180 days)",
          "Company-sponsored training",
          "Professional development",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // MULTIPLE ENTRY VISAS (D Series)
      // ═══════════════════════════════════════════════════════════
      {
        name: "D1 - Multiple Entry Tourism",
        description: "Frequent visitors for tourism",
        price: "Contact",
        features: [
          "1 or 2 years validity",
          "Multiple entries allowed",
          "60 days per stay",
        ],
        popular: false,
      },
      {
        name: "D2 - Multiple Entry Business",
        description: "Frequent business travelers",
        price: "Contact",
        features: [
          "1 or 2 years validity",
          "Multiple entries allowed",
          "Business activities & meetings",
        ],
        popular: false,
      },
      {
        name: "D12 - Business Investigation",
        description: "Pre-investment research visits",
        price: "Check live pricing",
        features: [
          "1 year (or 10M for 2 years)",
          "7-10 days processing",
          "Path to Investor KITAS",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // KITAS - WORK PERMITS (E23 Series)
      // ═══════════════════════════════════════════════════════════
      {
        name: "E23 - Working KITAS (Offshore)",
        description: "Employment with Indonesian company",
        price: "Check live pricing",
        features: [
          "1 year validity (renewable)",
          "4-6 weeks (RPTKA + IMTA)",
          "Company sponsorship required",
        ],
        popular: false,
      },
      {
        name: "E23 - Working KITAS (Onshore)",
        description: "Convert from within Indonesia",
        price: "Check live pricing",
        features: [
          "1 year validity (renewable)",
          "4-6 weeks (RPTKA + IMTA)",
          "Full conversion assistance",
        ],
        popular: false,
      },
      {
        name: "E23 - Freelance KITAS (Offshore)",
        description: "Self-employed professionals",
        price: "Check live pricing",
        features: [
          "6 months validity",
          "4-6 weeks (RPTKA + IMTA)",
          "Work permit (IMTA) included",
        ],
        popular: false,
      },
      {
        name: "E23 - Freelance KITAS (Onshore)",
        description: "Convert from within Indonesia",
        price: "Check live pricing",
        features: [
          "6 months validity",
          "4-6 weeks (RPTKA + IMTA)",
          "Full conversion assistance",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // KITAS - INVESTOR (E28 Series)
      // ═══════════════════════════════════════════════════════════
      {
        name: "E28A - Investor KITAS (Offshore)",
        description: "PT PMA directors & shareholders",
        price: "Check live pricing",
        features: [
          "2 years validity",
          "7-10 days processing",
          "Company ownership required",
        ],
        popular: true,
      },
      {
        name: "E28A - Investor KITAS (Onshore)",
        description: "Convert from within Indonesia",
        price: "Check live pricing",
        features: [
          "2 years validity",
          "7-10 days processing",
          "Extension: 18.000.000 IDR",
        ],
        popular: false,
      },
      {
        name: "E28E - KEK Investor KITAS",
        description: "Special Economic Zone investors",
        price: "Contact",
        features: [
          "2 years validity",
          "KEK location required",
          "Special incentives available",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // KITAS - FAMILY (E31 Series)
      // ═══════════════════════════════════════════════════════════
      {
        name: "E31A - Spouse KITAS 1 Year (Offshore)",
        description: "Married to Indonesian citizen",
        price: "Check live pricing",
        features: [
          "1 year validity",
          "7-10 days processing",
          "Marriage certificate required",
        ],
        popular: false,
      },
      {
        name: "E31A - Spouse KITAS 2 Years (Offshore)",
        description: "Married to Indonesian citizen",
        price: "Check live pricing",
        features: [
          "2 years validity",
          "7-10 days processing",
          "Extension: 15.000.000 IDR",
        ],
        popular: false,
      },
      {
        name: "E31B/F - Dependent KITAS 1 Year",
        description: "Family of KITAS holders",
        price: "Check live pricing",
        features: [
          "1 year validity",
          "7-10 days processing",
          "Extension: 9.000.000 IDR",
        ],
        popular: false,
      },
      {
        name: "E31B/F - Dependent KITAS 2 Years",
        description: "Family of KITAS holders",
        price: "Check live pricing",
        features: [
          "2 years validity",
          "7-10 days processing",
          "Extension: 15.000.000 IDR",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // KITAS - LIFESTYLE (E33 Series)
      // ═══════════════════════════════════════════════════════════
      {
        name: "E33G - Digital Nomad KITAS (Offshore)",
        description: "Remote workers with foreign income",
        price: "Check live pricing",
        features: [
          "1 year validity",
          "7-10 days processing",
          "No work permit (IMTA) needed",
        ],
        popular: true,
      },
      {
        name: "E33G - Digital Nomad KITAS (Onshore)",
        description: "Convert from within Indonesia",
        price: "Check live pricing",
        features: [
          "1 year validity",
          "7-10 days processing",
          "Extension: 10.000.000 IDR",
        ],
        popular: false,
      },
      {
        name: "E33E/F - Retirement KITAS (Offshore)",
        description: "Retirees aged 55+",
        price: "Check live pricing",
        features: [
          "1-5 years validity",
          "7-10 days processing",
          "Pension proof required",
        ],
        popular: false,
      },
      {
        name: "E33E/F - Retirement KITAS (Onshore)",
        description: "Convert from within Indonesia",
        price: "Check live pricing",
        features: [
          "1-5 years validity",
          "7-10 days processing",
          "Extension: 10.000.000 IDR",
        ],
        popular: false,
      },
      {
        name: "E33A/B/C - Research/Education KITAS",
        description: "Researchers, students, educators",
        price: "Contact",
        features: [
          "1-2 years validity",
          "Institution sponsorship",
          "Academic documentation",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // SECOND HOME VISA (E35 Series)
      // ═══════════════════════════════════════════════════════════
      {
        name: "E35 - Second Home Visa",
        description: "Long-term residence (USD 130k+ deposit)",
        price: "Contact",
        features: [
          "5-10 years validity",
          "No sponsor required",
          "Bring family members",
        ],
        popular: false,
      },
      {
        name: "E35A - Working Holiday",
        description: "Australia bilateral agreement",
        price: "Contact",
        features: [
          "1 year validity",
          "Age 18-30 only",
          "Australian citizens only",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // KITAP - PERMANENT RESIDENCE
      // ═══════════════════════════════════════════════════════════
      {
        name: "Investor KITAP + MERP",
        description: "Permanent residence for investors",
        price: "Check live pricing",
        features: [
          "Permanent residence",
          "Multiple re-entry permit included",
          "Consecutive KITAS required",
        ],
        popular: false,
      },
      {
        name: "Dependent KITAP + MERP",
        description: "Family of Indonesian citizens",
        price: "Check live pricing",
        features: [
          "Permanent residence",
          "Multiple re-entry permit included",
          "Expedited processing available",
        ],
        popular: false,
      },
      {
        name: "Retirement KITAP + MERP",
        description: "Permanent residence for retirees",
        price: "Check live pricing",
        features: [
          "Permanent residence",
          "Multiple re-entry permit included",
          "Age 55+ requirement",
        ],
        popular: false,
      },
      {
        name: "Working KITAP",
        description: "Permanent residence for workers",
        price: "Contact",
        features: [
          "Permanent residence",
          "4 consecutive KITAS required",
          "Long-term employment history",
        ],
        popular: false,
      },
      {
        name: "MERP Only (1 Year)",
        description: "Multiple Exit Re-entry Permit",
        price: "Check live pricing",
        features: [
          "1 year validity",
          "Unlimited exits/entries",
          "For KITAP holders",
        ],
        popular: false,
      },
      {
        name: "MERP Only (2 Years)",
        description: "Multiple Exit Re-entry Permit",
        price: "Check live pricing",
        features: [
          "2 years validity",
          "Unlimited exits/entries",
          "For KITAP holders",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // IMMIGRATION SERVICES
      // ═══════════════════════════════════════════════════════════
      {
        name: "EPO (Exit Permit Only)",
        description: "One-way exit from Indonesia",
        price: "Check live pricing",
        features: [
          "Exit without re-entry",
          "1-3 days processing",
          "Urgent +300k IDR",
        ],
        popular: false,
      },
      {
        name: "ERP (Exit Re-entry Permit)",
        description: "Travel abroad and return",
        price: "Check live pricing",
        features: [
          "Preserves KITAS validity",
          "1-3 days processing",
          "Urgent +500k IDR",
        ],
        popular: false,
      },
      {
        name: "Mutation Passport",
        description: "Update KITAS with new passport",
        price: "Check live pricing",
        features: [
          "Required when passport renewed",
          "5-7 days processing",
          "Urgent +350k IDR",
        ],
        popular: false,
      },
      {
        name: "Mutation Address",
        description: "Update registered address",
        price: "Check live pricing",
        features: [
          "Immigration records update",
          "5-7 days processing",
          "New domicile letter needed",
        ],
        popular: false,
      },
      {
        name: "Cancel RPTKA + IMTA + Wajib Lapor",
        description: "Full work permit cancellation",
        price: "Check live pricing",
        features: [
          "Complete cancellation package",
          "Required when leaving employment",
          "7-14 days processing",
        ],
        popular: false,
      },
      {
        name: "Reset Molina",
        description: "Immigration online account reset",
        price: "Check live pricing",
        features: [
          "Fix login/account issues",
          "1-3 days processing",
          "Urgent +400k IDR",
        ],
        popular: false,
      },
      {
        name: "SKTT Registration",
        description: "Temporary residence certificate",
        price: "Check live pricing",
        features: [
          "Required for all KITAS holders",
          "7-10 days processing",
          "Local government registration",
        ],
        popular: false,
      },
      {
        name: "SKCK (Police Clearance)",
        description: "Indonesian police clearance",
        price: "Check live pricing",
        features: [
          "Clean record certificate",
          "5-7 days processing",
          "Valid 6 months",
        ],
        popular: false,
      },
      {
        name: "Domicile Letter",
        description: "Residence confirmation letter",
        price: "Check live pricing",
        features: [
          "Official domicile confirmation",
          "3-5 days processing",
          "Required for many permits",
        ],
        popular: false,
      },
      {
        name: "Domicile + SKTT Package",
        description: "Combined residence documents",
        price: "Check live pricing",
        features: [
          "Both documents together",
          "Save 700k IDR",
          "7-10 days processing",
        ],
        popular: false,
      },
      {
        name: "Born Report (Lapor Lahir)",
        description: "Birth registration for foreigner child",
        price: "Check live pricing",
        features: [
          "Required within 30 days of birth",
          "Full documentation support",
          "Immigration registration",
        ],
        popular: false,
      },
      // ═══════════════════════════════════════════════════════════
      // PASSPORT SERVICES
      // ═══════════════════════════════════════════════════════════
      {
        name: "Indonesian Passport 5 Years",
        description: "Standard passport renewal",
        price: "Check live pricing",
        features: [
          "5 years validity",
          "7-14 days processing",
          "Indonesian citizens only",
        ],
        popular: false,
      },
      {
        name: "Indonesian Passport 10 Years",
        description: "Long-term passport",
        price: "Check live pricing",
        features: [
          "10 years validity",
          "7-14 days processing",
          "Best value for frequent travelers",
        ],
        popular: false,
      },
      {
        name: "E-Passport 5 Years",
        description: "Biometric electronic passport",
        price: "Check live pricing",
        features: [
          "Biometric chip included",
          "5 years validity",
          "Faster immigration clearance",
        ],
        popular: false,
      },
      {
        name: "E-Passport 10 Years",
        description: "Premium biometric passport",
        price: "Check live pricing",
        features: [
          "Biometric chip included",
          "10 years validity",
          "Premium travel document",
        ],
        popular: false,
      },
    ],
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
          "Offshore means applying from outside Indonesia (before arrival), onshore means converting from within Indonesia while on another visa. Onshore is typically 2-4 million IDR more due to additional processing.",
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
        question: "What is the Second Home Visa (E35)?",
        answer:
          "E35 is a 5-10 year visa for high-net-worth individuals. Requires USD 130,000+ deposit in Indonesian bank, or proof of property ownership. No sponsor needed, can bring family members.",
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
