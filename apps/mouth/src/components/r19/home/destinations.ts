import { GOOGLE_MAPS_URL } from "@/lib/trust-figures";

// Existing public destinations; no duplicate routing or integration layer.
export const destinations = {
  // The four tool links keep the destinations of the pre-R19 home (byte-identical
  // to FunnelFeature's FUNNEL_HREF; D10 - whether the subdomains give way to the
  // in-app routes - is not resolved here).
  // visa.balizero.com is a legacy 302 to /visa (a 308 to /visa-oracle);
  // tax.balizero.com is a rewrite of /tax-calendar.
  visaOracle: {
    label: "Visa Oracle",
    href: "https://visa.balizero.com/",
  },
  kbliNavigator: {
    label: "KBLI Navigator",
    href: "/kbli",
  },
  taxIntelligence: {
    label: "Tax Compliance Calendar",
    href: "https://tax.balizero.com/",
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
  // The two contact destinations of the pre-R19 v2 Footer, verbatim.
  telegram: {
    label: "Telegram",
    href: "https://t.me/Balizerobot",
  },
  officeMap: {
    label: "Location",
    href: "https://maps.google.com/?q=Bali+Indonesia",
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
