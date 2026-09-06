export const services = [
  {
    id: "visa",
    title: "Immigration & residence",
    description: "Talk through your visa and residence plans with our team.",
    tool: "Visa Oracle",
    detail: "Explore visit, residence and work-related visa questions.",
    image: "tool-visa-traveler.png",
    href: "https://visa.balizero.com/",
    action: "Open Visa Oracle",
  },
  {
    id: "business",
    title: "Business & company setup",
    description:
      "Get guidance for setting up and running your company in Indonesia.",
    tool: "KBLI Navigator",
    detail:
      "Search Indonesian business activity classifications in the Navigator.",
    image: "tool-kbli-illustration.png",
    href: "https://balizero.com/kbli",
    action: "Find a business code",
  },
  {
    id: "tax",
    title: "Tax & accounting",
    description: "Discuss your personal or company tax and reporting needs.",
    tool: "Tax Intelligence",
    detail: "Explore personal tax, company obligations and reporting topics.",
    image: "tool-tax-illustration.png",
    href: "https://tax.balizero.com/",
    action: "Explore tax guidance",
  },
  {
    id: "property",
    title: "Property & due diligence",
    description:
      "Get help understanding the questions behind a property decision.",
    tool: "Property Check",
    detail: "Explore questions about property use and eligibility.",
    image: "tool-property-illustration.png",
    href: "https://balizero.com/property/eligibility",
    action: "Explore Property Check",
  },
] as const;
export function contactHref(topic: string) {
  return (
    "https://wa.me/628213454721?text=" +
    encodeURIComponent(
      "Hello Bali Zero, I would like to discuss " + topic + ".",
    )
  );
}
