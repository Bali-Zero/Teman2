/**
 * Reviewed 2026-09-08 against public About/Team pages and the approved roster.
 * Publication confirms attribution, not licences, founding dates or volumes.
 * Working steps describe available visitor journeys, not an internal SLA.
 * Provenance and retired claims: output/design/astra-restoration-loops/results/04/company.md.
 */
export const company = {
  location: "Kerobokan, Bali",
  beginning:
    "Bali Zero was founded by Zainal Abidin and Pak Heru. Based in Kerobokan, Bali, the company works with people moving to Indonesia and founders setting up businesses here. Its services span immigration, company setup, tax compliance and property due diligence.",
  approach:
    "A move rarely involves just one decision. A residence plan can lead to questions about a business, its reporting obligations or a property. Our team brings together setup, tax, accounting and advisory roles. Exploring those areas together helps you identify the questions to raise before proceeding.",
} as const;

export const workingSteps = [
  {
    title: "Start with your situation",
    description:
      "Planning a move, already in Indonesia, opening a company or reviewing a property? Start with the relevant service or tool and the question you need to resolve.",
    label: "Find your starting point",
    href: "/#tools",
  },
  {
    title: "Understand the work involved",
    description:
      "Read the service scope, preparation notes and common questions. Use them to distinguish the work you need and prepare a focused conversation with the team.",
    label: "Explore service details",
    href: "/services",
  },
  {
    title: "Discuss the next step",
    description:
      "Tell us your goal and where you are in the process. Ask about scope, required documents and the next action for your case, or arrange an office appointment.",
    label: "Plan a conversation",
    href: "/contact?from=about",
  },
] as const;

export const companyExpertise = [
  {
    title: "Immigration",
    description:
      "Visits, residence plans and visa renewals. Start with the purpose of your stay and whether you are already in Indonesia.",
    href: "/services/immigration",
  },
  {
    title: "Company setup",
    description:
      "Incorporation, business activities and licensing. Bring your business idea so the company structure and setup questions can be considered together.",
    href: "/services/company-setup",
  },
  {
    title: "Tax & accounting",
    description:
      "Personal and company reporting, registration and bookkeeping questions. Identify the obligations and records that need attention.",
    href: "/services/tax",
  },
  {
    title: "Property",
    description:
      "Due diligence, ownership structures and questions about a property's permitted use. Understand what to investigate before making a commitment.",
    href: "/services/property",
  },
  {
    title: "Compliance",
    description:
      "Recurring obligations across tax, registration and reporting. Keep track of what is due and stay ahead of the deadlines.",
    href: "/services/compliance",
  },
] as const;
