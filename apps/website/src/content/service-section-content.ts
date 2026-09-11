import type { ServicePage } from "./service-pages";
import { visaCatalog } from "./service-visa-catalog";

export type ServiceCatalogGroup = {
  title: string;
  description: string;
  services: readonly string[];
};

type ServiceSectionsContent = {
  catalog: readonly ServiceCatalogGroup[];
  included: readonly string[];
  documents: readonly string[];
  review: readonly string[];
  faqs: readonly { question: string; answer: string }[];
  // Present only where a pillar has a small set of dated, sourced facts worth
  // surfacing as their own section (currently compliance only).
  whyNow?: readonly string[];
};

// Migrated from apps/mouth/src/data/services_data.ts. These are service scopes
// and preparation prompts, not eligibility determinations. Numeric requirements,
// legal conclusions, processing promises and prices are deliberately not copied.
export const serviceSectionContent: Record<
  ServicePage["slug"],
  ServiceSectionsContent
> = {
  immigration: {
    catalog: visaCatalog,
    included: [
      "Document review and preparation",
      "Application submission and liaison",
      "Status updates",
      "Translation support",
      "Renewal planning",
    ],
    documents: [
      "Passport and current immigration documents",
      "Travel and residence plans",
      "Sponsor documents, where relevant",
      "Work, education or financial records relevant to the route",
    ],
    review: [
      "The activities you intend to carry out",
      "Whether you are inside or outside Indonesia",
      "Your current permit and any upcoming expiry",
      "Any accompanying family members",
    ],
    faqs: [
      {
        question: "How do arrival, extension and residence services differ?",
        answer:
          "An arrival application concerns entry. An extension concerns the stay already granted, and a residence application concerns a particular basis for living in Indonesia. Start with your current location, permit and intended activities; a longer trip does not by itself turn a visit into a residence route.",
      },
      {
        question:
          "Does a two-year visa mean I can stay continuously for two years?",
        answer:
          "Not necessarily. A multiple-entry visa has a validity window for repeated entries, while each entry has its own stay limit. Residence permits use a different structure. Check the issued permission and its conditions; the catalogue period is not an individual stay entitlement.",
      },
      {
        question: "Can I change status inside Indonesia?",
        answer:
          "An onshore change (alih status) and an extension are different procedures. The current permit, sponsor and intended new purpose determine whether a change is available. A pending request does not automatically protect an expiring stay. Have the permit and exact expiry ready before planning the transition.",
      },
      {
        question:
          "Are government fees, translations and family members included?",
        answer:
          "The live price relates to the exact selected service. Ask for an itemised scope showing authority fees, sponsorship, translations, dependants and any additional administration. A partner or child is a separate applicant; a price check does not submit an application.",
      },
    ],
  },
  "company-setup": {
    catalog: [
      {
        title: "Company formation",
        description: "Put the structure behind your business plan in place.",
        services: ["PT PMA/PMDN Setup"],
      },
      {
        title: "Changes & specialist licenses",
        description:
          "Support for an existing company and its operating activities.",
        services: [
          "Company Revision",
          "SLHS (Hygiene Certificate)",
          "Alcohol License (NPBBKC)",
        ],
      },
    ],
    included: [
      "Company name and establishment documents",
      "Ministry of Law filing",
      "NIB and OSS registration support",
      "Tax registration support",
      "Digital document copies",
    ],
    documents: [
      "Shareholder and director identification",
      "Address information",
      "Proposed company names",
      "Business plan and intended activities",
      "Existing company documents, for revisions",
    ],
    review: [
      "Your business activities and KBLI classifications",
      "Shareholders, directors and intended roles",
      "Business location and operating plan",
      "Capital and licensing requirements for the activity",
    ],
    faqs: [
      {
        question: "How should I choose between PT PMA and PT PMDN?",
        answer:
          "Start with the shareholders and whether foreign investment is involved, then the actual activities and operating location. The chosen activities affect the ownership and licensing review. Do not choose a structure solely because it sounds simpler: the ownership, deed and business plan must describe the same operation.",
      },
      {
        question: "Does company formation include every operating licence?",
        answer:
          "Formation, NIB/OSS registration and specialist permissions are separate steps. A food operation may need hygiene work, an alcohol business an excise review, and the premises their own building approvals. The quote should identify the business activities and name each licence being handled.",
      },
      {
        question: "When is a revision better than a new incorporation?",
        answer:
          "Use a revision review when the existing entity will remain but its directors, shareholders, activities, address or capital will change. Bring the current deed and registrations alongside the proposed change. The review identifies which records and permissions must be updated together.",
      },
      {
        question: "What determines the setup timetable?",
        answer:
          "A name or deed stage can finish before sector licences or bank onboarding. Document readiness, activity restrictions, premises and third-party decisions affect the sequence. Plan against named milestones and dependencies in the scope rather than a single promised completion date.",
      },
    ],
  },
  tax: {
    catalog: [
      {
        title: "Tax registration",
        description:
          "Set up or review the registrations behind your reporting.",
        services: ["NPWP Personal + Coretax", "NPWPD Corporate"],
      },
      {
        title: "Returns & ongoing reporting",
        description:
          "Support for personal, company and investment activity reporting.",
        services: [
          "SPT Annual Personal",
          "SPT Annual Company (Zero)",
          "SPT Annual Company (Operational)",
          "Monthly Tax Report",
          "LKPM Report",
        ],
      },
      {
        title: "BPJS administration",
        description:
          "Registration and administration for health and employment coverage.",
        services: ["BPJS Health Insurance", "BPJS Employment Insurance"],
      },
    ],
    included: [
      "Registration and record review",
      "Tax calculation and filing support",
      "Payment document preparation",
      "Filing archives",
      "Tax office liaison and deadline planning",
    ],
    documents: [
      "Tax registration documents",
      "Previous returns, where available",
      "Income statements and supporting records",
      "Bank statements and business financial records",
      "Company and employment records relevant to the service",
    ],
    review: [
      "Whether the matter is personal or company-related",
      "The reporting periods involved",
      "Income, activities and relevant transactions",
      "Residency and registration context",
    ],
    faqs: [
      {
        question: "Is NPWPD the same as corporate NPWP?",
        answer:
          "No. NPWP is the national tax identity; NPWPD concerns regional tax registration. A business may need to review both depending on its activities and location. Coretax access is a national tax-account question, not proof that regional registration has been completed.",
      },
      {
        question:
          "Can a company with no revenue use the zero-activity return service?",
        answer:
          "No revenue is only the starting point for review. Bank fees, expenses, capital movements or other transactions may still need to be reflected. Reconcile the year’s records before classifying the return; this service does not declare the company exempt from reporting.",
      },
      {
        question:
          "Does the company’s annual return include my personal return?",
        answer:
          "They are separate taxpayers and separate filings. A director’s personal income, assets and other circumstances require their own review. List the individual and company returns explicitly in the quote, together with any monthly reporting or earlier-year corrections.",
      },
      {
        question: "Can monthly tax reporting replace BPJS or LKPM?",
        answer:
          "No. Tax reporting follows taxable transactions and registration status; BPJS concerns health or employment protection; LKPM reports investment activity through OSS. Use separate calendars and receipts for each obligation. The applicable period and frequency need checking for the actual business.",
      },
    ],
  },
  property: {
    catalog: [
      {
        title: "Before you commit",
        description:
          "Understand the documents and agreement behind the transaction.",
        services: ["Legal Due Diligence", "Leasehold Agreement (Hak Sewa)"],
      },
      {
        title: "Structures & building permits",
        description:
          "Review the proposed ownership structure and intended use.",
        services: ["Building Permits", "Ownership Structures (PT PMA)"],
      },
    ],
    included: [
      "Legal document review",
      "Ownership and title verification",
      "Property inspection coordination",
      "Contract drafting or review",
      "Notary coordination",
    ],
    documents: [
      "Property certificate and available title records",
      "Owner or company documents",
      "Property tax payment records",
      "Building permits and site plans",
      "Draft sale or lease agreement, if available",
    ],
    review: [
      "The intended use of the property",
      "The proposed buyer or tenant structure",
      "Available title and permit information",
      "The terms of the proposed agreement",
    ],
    faqs: [
      {
        question: "What should be checked before I pay a deposit?",
        answer:
          "Start with the title, the person entitled to sign, encumbrances, intended land use and the proposed contract. A written review should identify missing records and conditions that need resolution. A structural inspection is separate from legal due diligence and should be scoped if it matters to the decision.",
      },
      {
        question: "Does a lease renewal clause guarantee another full term?",
        answer:
          "Read the exact mechanism: an option, an agreement to negotiate and an automatic renewal are different arrangements. Review the lessor’s authority, conditions, price and enforceability. A marketing formula such as 25+25+25 years is not a substitute for the title and signed terms.",
      },
      {
        question:
          "What is the difference between PBG, SLF and an existing IMB?",
        answer:
          "PBG concerns building approval and SLF fitness for use. Existing IMB documentation needs review against the building, its history and proposed changes; it should not simply be discarded or relabelled. The building dossier links the official SIMBG guidance for that distinction.",
      },
      {
        question: "Does forming a PT PMA resolve the property question?",
        answer:
          "No. The company’s activities and ownership structure must be considered alongside the exact land right, intended use, building approvals and transaction. Formation is one component. The review should also cover governance, tax implications and the intended exit or succession arrangements.",
      },
    ],
  },
  compliance: {
    catalog: [
      {
        title: "Retainers",
        description: "Ongoing filing and payroll compliance for your entity.",
        services: [
          "Compliance Takeover",
          "Core Compliance Retainer (Monthly)",
          "Employer Compliance Retainer (Monthly)",
        ],
      },
      {
        title: "Registrations & assessments",
        description:
          "One-off reviews for platform and VAT-collector obligations.",
        services: ["PSE Registration", "PMSE VAT Assessment"],
      },
    ],
    included: [
      "An obligations register for your entity: every filing, its legal basis, deadline, owner and status",
      "Filings prepared by our team, approved by your director, submitted, receipt archived",
      "Payroll compliance checks for local and foreign staff, including BPJS enrolment for expats employed six months or more",
      "Quarterly LKPM prepared from your figures and submitted on OSS-RBA",
      "A compliance report: what was due, what was filed, evidence attached",
    ],
    documents: [
      "Company deed, NIB and current tax registrations",
      "Existing filing history, payroll and BPJS records",
      "List of systems, domains and apps reachable from Indonesia, if registering as a PSE",
    ],
    review: [
      "How many local and foreign staff the company employs",
      "Which systems, apps or platforms the company operates and who can reach them",
      "The entity's current filing cadence and any missed deadlines",
    ],
    faqs: [
      {
        question: "Do you sign filings for us?",
        answer:
          "No. Your director approves and signs with the company's own digital certificate; we prepare, check and submit under your authorisation.",
      },
      {
        question:
          "Do foreign operators without an Indonesian office need to register as a PSE?",
        answer:
          "Yes, if the website, app or platform is used by people in Indonesia. Permenkominfo 5/2020 reaches a foreign operator on that basis alone; having no local entity does not place it outside scope.",
      },
      {
        question: "Can you get us appointed as a PMSE VAT collector?",
        answer:
          "No one can. DJP appoints collectors under PMK 81/2024. We assess the threshold and prepare readiness; appointment itself is DJP's decision.",
      },
    ],
    whyNow: [
      "Komdigi blocked eBay and KLM on 28 June 2025 and sent notification letters to 25 operators on 26 June 2026 (Komdigi press releases 9446 and 10354).",
      "Coretax's first corporate filing season needed a rescue: DJP's KEP-71/PJ/2026 (issued 30 April 2026) waived late-filing penalties on 2025 corporate income tax returns (SPT Tahunan Badan) through 31 May 2026.",
      "Quarterly LKPM deadlines moved to the 15th under BKPM Regulation 5/2025.",
    ],
  },
};
