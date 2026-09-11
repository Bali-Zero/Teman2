import type { DestinationId } from "./destinations";

export type ServicePage = {
  slug: "immigration" | "company-setup" | "tax" | "property" | "compliance";
  title: string;
  cardTitle: string;
  eyebrow: string;
  summary: string;
  metaDescription: string;
  image: { src: string; alt: string };
  whoItHelps: string;
  questions: readonly string[];
  contactTopic: string;
  // Absent when the pillar has no independent public tool of its own (e.g. compliance).
  toolDestinationId?: Extract<
    DestinationId,
    "visaOracle" | "kbliNavigator" | "taxIntelligence" | "propertyEligibility"
  >;
};

export const servicePages = [
  {
    slug: "immigration",
    title: "Immigration and residence",
    cardTitle: "Immigration",
    eyebrow: "Visas and residence",
    summary:
      "A first visit, a working life, a family move. Each starts with a different permission. Explore the route, the preparation and the decisions that come before an application.",
    metaDescription:
      "Discuss immigration and residence plans in Indonesia with the Bali Zero team.",
    image: {
      src: "/assets/tool-visa-traveler.png",
      alt: "Illustration of a traveller preparing for Indonesia",
    },
    whoItHelps:
      "People planning a visit, a move or a work-related stay who want to understand which questions to address before choosing a route.",
    questions: [
      "What is the purpose of the stay and which activities are planned?",
      "What timing, travel plans or current status should be considered?",
      "Who else is part of the plan?",
    ],
    contactTopic: "immigration and residence plans in Indonesia",
    toolDestinationId: "visaOracle",
  },
  {
    slug: "company-setup",
    title: "Company setup",
    cardTitle: "Company setup",
    eyebrow: "Business in Indonesia",
    summary:
      "Build the company around the business you intend to run. Formation establishes the entity; revisions and specialist licences keep its records aligned with the work on the ground.",
    metaDescription:
      "Discuss company setup questions and business plans in Indonesia with the Bali Zero team.",
    image: {
      src: "/assets/tool-kbli-illustration.png",
      alt: "Illustration representing Indonesian business activities",
    },
    whoItHelps:
      "Founders and operators who want to organise the practical questions behind establishing a company in Indonesia.",
    questions: [
      "Which business activities should the company cover?",
      "Who is involved and what roles are being considered?",
      "Where and how is the business expected to operate?",
    ],
    contactTopic: "setting up a company in Indonesia",
    toolDestinationId: "kbliNavigator",
  },
  {
    slug: "tax",
    title: "Tax and accounting",
    cardTitle: "Tax",
    eyebrow: "Personal and company tax",
    summary:
      "Registration, monthly records and the annual return serve different purposes. Find the support that matches the person, the company and the period you need to put in order.",
    metaDescription:
      "Discuss personal or company tax and accounting questions in Indonesia with the Bali Zero team.",
    image: {
      src: "/assets/tool-tax-illustration.png",
      alt: "Illustration representing tax records and reporting",
    },
    whoItHelps:
      "Individuals and companies that want to discuss their activities, records and reporting context with a local team.",
    questions: [
      "Is the question personal, company-related or connected to both?",
      "Which activities, entities or transactions form the context?",
      "Which records and reporting dates are already known?",
    ],
    contactTopic: "personal or company tax and accounting in Indonesia",
    toolDestinationId: "taxIntelligence",
  },
  {
    slug: "property",
    title: "Property and due diligence",
    cardTitle: "Property",
    eyebrow: "Property decisions",
    summary:
      "Understand what the land, the agreement and the building documents actually allow. Begin with the asset, then work through the contract, approvals and proposed holding structure.",
    metaDescription:
      "Discuss property and due diligence questions in Indonesia with the Bali Zero team.",
    image: {
      src: "/assets/tool-property-illustration.png",
      alt: "Illustration representing a property decision in Bali",
    },
    whoItHelps:
      "People considering a purchase, lease or investment who want to identify the questions and documents to discuss.",
    questions: [
      "How is the property intended to be used?",
      "Which ownership or contract structure is being considered?",
      "Which title, permit and agreement documents are available for review?",
    ],
    contactTopic: "property and due diligence questions in Indonesia",
    toolDestinationId: "propertyEligibility",
  },
  {
    slug: "compliance",
    title: "Compliance and obligations",
    cardTitle: "Compliance",
    eyebrow: "Ongoing regulatory obligations",
    summary:
      "Coretax filings, quarterly LKPM, payroll and BPJS, PSE registration. One accountable team, an obligations register for your entity, and a receipt for every submission.",
    metaDescription:
      "Discuss Indonesia compliance retainers, PSE registration and PMSE VAT obligations with the Bali Zero team.",
    image: {
      src: "/assets/tool-tax-illustration.png",
      alt: "Illustration representing recurring compliance filings and reporting",
    },
    whoItHelps:
      "Foreign-owned companies (PT PMA) with 5 to 50 staff and no in-house Indonesian finance lead, foreign platforms and apps reaching Indonesian users, and hotel or villa operators with booking systems and foreign staff.",
    questions: [
      "How many local and foreign staff does the company employ, and are expats past six months enrolled in BPJS?",
      "Which websites, apps or platforms does the company operate that people in Indonesia can access?",
      "What is the entity's current filing record: monthly tax, quarterly LKPM, annual return?",
    ],
    contactTopic:
      "Indonesia compliance retainers, PSE registration and PMSE VAT obligations",
    toolDestinationId: undefined,
  },
] as const satisfies readonly ServicePage[];

export function getServicePage(slug: string): ServicePage | undefined {
  return servicePages.find((service) => service.slug === slug);
}
