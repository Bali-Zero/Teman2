import { destinations, destinationIntents } from "./destinations";

export const services = [
  {
    id: "visa",
    route: "/services/immigration",
    title: "Immigration & residence",
    description: "Talk through your visa and residence plans with our team.",
    tool: "Visa Oracle",
    detail: "Explore visit, residence and work-related visa questions.",
    image: "tool-visa-traveler.png",
    href: destinations.visaOracle.href,
    action: "Open Visa Oracle",
  },
  {
    id: "business",
    route: "/services/company-setup",
    title: "Business & company setup",
    description:
      "Get guidance for setting up and running your company in Indonesia.",
    tool: "KBLI Navigator",
    detail:
      "Search Indonesian business activity classifications in the Navigator.",
    image: "tool-kbli-illustration.png",
    href: destinations.kbliNavigator.href,
    action: "Find a business code",
  },
  {
    id: "tax",
    route: "/services/tax",
    title: "Tax & accounting",
    description: "Discuss your personal or company tax and reporting needs.",
    tool: destinations.taxIntelligence.label,
    detail:
      "Explore the tax compliance calendar and discuss your reporting needs.",
    image: "tool-tax-illustration.png",
    href: destinations.taxIntelligence.href,
    action: "Open tax calendar",
  },
  {
    id: "property",
    route: "/services/property",
    title: "Property & due diligence",
    description:
      "Get help understanding the questions behind a property decision.",
    tool: "Property Check",
    detail: "Explore questions about property use and eligibility.",
    image: "tool-property-illustration.png",
    href: destinations.propertyEligibility.href,
    action: "Explore Property Check",
  },
] as const;
export function contactHref(topic: string) {
  return destinationIntents.whatsapp({ topic });
}
