import { GOOGLE_MAPS_URL } from "@/lib/trust-figures";

// Existing public destinations; no duplicate routing or integration layer.
export const destinations = {
  visaOracle: {
    label: "Visa Oracle",
    href: "/visa-oracle",
  },
  kbliNavigator: {
    label: "KBLI Navigator",
    href: "/kbli",
  },
  taxIntelligence: {
    label: "Tax Compliance Calendar",
    href: "/tax-calendar",
  },
  propertyEligibility: {
    label: "Property Check",
    href: "/property/eligibility",
  },
  googleReviews: {
    label: "Bali Zero reviews on Google",
    href: GOOGLE_MAPS_URL,
  },
  googleLocation: {
    label: "Bali Zero on Google Maps",
    href: GOOGLE_MAPS_URL,
  },
  email: {
    label: "Email",
    href: "mailto:zantara@balizero.com",
  },
  myBaliZero: {
    label: "My Bali Zero",
    href: "https://my.balizero.com/",
  },
} as const;
