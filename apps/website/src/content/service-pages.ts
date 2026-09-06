import type { DestinationId } from "./destinations";

export type ServicePage = {
  slug: "immigration" | "company-setup" | "tax" | "property";
  title: string;
  cardTitle: string;
  eyebrow: string;
  summary: string;
  metaDescription: string;
  image: { src: string; alt: string };
  whoItHelps: string;
  questions: readonly string[];
  contactTopic: string;
  toolDestinationId: Extract<
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
      "Start with the purpose of your stay, the activities you are planning and the context that may shape the conversation.",
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
      "Discuss the activity, people and operating plan behind a company before deciding how to proceed.",
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
      "Bring the facts of your situation into one conversation before making assumptions about obligations or reporting.",
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
      "Clarify the intended use, proposed structure and documents that deserve attention before a property decision.",
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
] as const satisfies readonly ServicePage[];

export function getServicePage(slug: string): ServicePage | undefined {
  return servicePages.find((service) => service.slug === slug);
}
