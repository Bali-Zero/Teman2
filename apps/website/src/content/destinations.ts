import {
  buildEmailIntent,
  buildWhatsAppIntent,
  toSafeExternalHref,
  toSafeDestinationHref,
  type SafeDestinationHref,
} from "../lib/destinations";

export type DestinationKind =
  | "contact"
  | "editorial"
  | "legal"
  | "location"
  | "portal"
  | "reputation"
  | "service"
  | "team";

export type DestinationAccess = "external-client" | "login-required" | "public";
export type DestinationReleaseStatus = "approved" | "blocked";

export interface DestinationContract {
  label: string;
  kind: DestinationKind;
  access: DestinationAccess;
  releaseStatus: DestinationReleaseStatus;
  href: SafeDestinationHref;
  intent: string;
  unavailableFallback: string;
}

export const destinations = {
  evoa: {
    label: "E-VOA",
    kind: "service",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/visa/voa"),
    intent: "Explain the Bali Zero E-VOA service and its current next step.",
    unavailableFallback:
      "Offer a contextual conversation with the Bali Zero team.",
  },
  secondHomeStudio: {
    label: "Second Home Studio",
    kind: "service",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/visa/second-home/studio"),
    intent: "Open the public Second Home planning experience.",
    unavailableFallback:
      "Offer a Second Home conversation without claiming eligibility.",
  },
  myBaliZero: {
    label: "My Bali Zero",
    kind: "portal",
    access: "login-required",
    releaseStatus: "approved",
    href: toSafeExternalHref("https://my.balizero.com/"),
    intent: "Open the existing client account sign-in surface.",
    unavailableFallback:
      "Describe this as account access and offer team contact for support.",
  },
  visaOracle: {
    label: "Visa Oracle",
    kind: "service",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/visa-oracle"),
    intent: "Open the public visa exploration tool.",
    unavailableFallback: "Offer immigration service guidance and team contact.",
  },
  kbliNavigator: {
    label: "KBLI Navigator",
    kind: "service",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/kbli"),
    intent: "Open the public Indonesian business activity navigator.",
    unavailableFallback:
      "Offer company setup guidance without suggesting a KBLI code.",
  },
  taxIntelligence: {
    label: "Tax Compliance Calendar",
    kind: "service",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/tax-calendar"),
    intent: "Open the public tax compliance calendar.",
    unavailableFallback:
      "Offer a tax consultation without stating an obligation or outcome.",
  },
  propertyEligibility: {
    label: "Property Check",
    kind: "service",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/property/eligibility"),
    intent: "Open the public property eligibility exploration destination.",
    unavailableFallback:
      "Offer property guidance without claiming eligibility.",
  },
  journal: {
    label: "The Bali Zero Journal",
    kind: "editorial",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/news"),
    intent: "Open the public Bali Zero editorial index.",
    unavailableFallback:
      "Keep the local Journal entry visible and omit unavailable filters.",
  },
  googleReviews: {
    label: "Bali Zero reviews on Google",
    kind: "reputation",
    access: "external-client",
    releaseStatus: "approved",
    href: toSafeExternalHref("https://maps.app.goo.gl/whiMUTNchcDR5naz8"),
    intent: "Open the current public Google review listing.",
    unavailableFallback:
      "Invite visitors to check the latest rating directly on Google.",
  },
  googleLocation: {
    label: "Bali Zero on Google Maps",
    kind: "location",
    access: "external-client",
    releaseStatus: "approved",
    href: toSafeExternalHref("https://maps.app.goo.gl/whiMUTNchcDR5naz8"),
    intent: "Open the verified public Google profile for the Kerobokan office.",
    unavailableFallback:
      "Show the verified address and offer an appointment with the team.",
  },
  companyAbout: {
    label: "Our story",
    kind: "team",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/about"),
    intent: "Open the public Bali Zero company story.",
    unavailableFallback:
      "Keep the local company introduction and omit the outbound action.",
  },
  team: {
    label: "Our team",
    kind: "team",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/team"),
    intent: "Open the public Bali Zero team directory.",
    unavailableFallback: "Keep the verified local team presentation only.",
  },
  privacy: {
    label: "Privacy",
    kind: "legal",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/v2/privacy"),
    intent: "Open the public privacy notice.",
    unavailableFallback:
      "Do not imply a policy is available; mark the link unavailable.",
  },
  terms: {
    label: "Terms",
    kind: "legal",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/v2/terms"),
    intent: "Open the public terms notice.",
    unavailableFallback:
      "Do not imply terms are available; mark the link unavailable.",
  },
  cookies: {
    label: "Cookies",
    kind: "legal",
    access: "public",
    releaseStatus: "approved",
    href: toSafeDestinationHref("/v2/cookies"),
    intent: "Open the public cookie notice.",
    unavailableFallback:
      "Do not imply a policy is available; mark the link unavailable.",
  },
  whatsapp: {
    label: "WhatsApp",
    kind: "contact",
    access: "external-client",
    releaseStatus: "approved",
    href: toSafeExternalHref("https://wa.me/628213454721"),
    intent: "Open a conversation with the Bali Zero team without sending it.",
    unavailableFallback: "Offer the verified email or telephone contact.",
  },
  email: {
    label: "Email",
    kind: "contact",
    access: "external-client",
    releaseStatus: "approved",
    href: toSafeExternalHref("mailto:zantara@balizero.com"),
    intent: "Prepare an email to the Bali Zero team without sending it.",
    unavailableFallback: "Show the verified email address as copyable text.",
  },
  telephone: {
    label: "Telephone",
    kind: "contact",
    access: "external-client",
    releaseStatus: "approved",
    href: toSafeExternalHref("tel:+628213454721"),
    intent:
      "Open the device dialer for the Bali Zero team without placing a call.",
    unavailableFallback: "Show the verified telephone number as copyable text.",
  },
  telegram: {
    label: "Zantara on Telegram",
    kind: "contact",
    access: "external-client",
    releaseStatus: "blocked",
    href: toSafeExternalHref("https://t.me/Balizerobot"),
    intent:
      "Open the public Zantara Telegram destination without sending a message.",
    unavailableFallback:
      "Offer the verified WhatsApp, email or telephone contact.",
  },
} as const satisfies Record<string, DestinationContract>;

export type DestinationId = keyof typeof destinations;

export function getDestination(id: DestinationId): DestinationContract {
  return destinations[id];
}

export function getReleasableDestination(
  id: DestinationId,
): DestinationContract | null {
  const destination = getDestination(id);
  return destination.releaseStatus === "approved" ? destination : null;
}

export const destinationIntents = {
  whatsapp: buildWhatsAppIntent,
  email: buildEmailIntent,
} as const;
