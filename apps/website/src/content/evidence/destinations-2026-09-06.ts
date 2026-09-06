import {
  toSafeExternalHref,
  type SafeExternalHref,
} from "../../lib/destinations";

export type DestinationAuditResult =
  | "BLOCKED"
  | "LOGIN_REQUIRED"
  | "NOT_TESTED"
  | "REACHABLE"
  | "REDIRECT"
  | "UNKNOWN";

export type DestinationIntentMatch =
  "MATCH" | "MISMATCH" | "NOT_TESTED" | "PARTIAL";

export type DestinationReleaseAction =
  "FALLBACK" | "LINK" | "LOGIN_COPY_ONLY" | "SUPPRESS";

export interface DestinationEvidence {
  id: string;
  requestedHref: SafeExternalHref;
  finalHref: SafeExternalHref | null;
  httpStatus: number | null;
  result: DestinationAuditResult;
  intentMatch: DestinationIntentMatch;
  releaseAction: DestinationReleaseAction;
  observation: string;
}

const href = toSafeExternalHref;

export const destinationEvidence20260906 = [
  {
    id: "evoa",
    requestedHref: href("https://balizero.com/visa/voa"),
    finalHref: href("https://balizero.com/visa/voa"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Visa on Arrival step 1 rendered; canonical points to /visa.",
  },
  {
    id: "secondHomeStudio",
    requestedHref: href("https://balizero.com/visa/second-home/studio"),
    finalHref: href("https://balizero.com/visa/second-home/studio"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Public six-step fit exploration rendered.",
  },
  {
    id: "myBaliZero",
    requestedHref: href("https://my.balizero.com/"),
    finalHref: href("https://my.balizero.com/portal/login-upgraded"),
    httpStatus: 200,
    result: "LOGIN_REQUIRED",
    intentMatch: "MATCH",
    releaseAction: "LOGIN_COPY_ONLY",
    observation:
      "Only account sign-in was verified; no portal features were tested.",
  },
  {
    id: "visaOracle",
    requestedHref: href("https://visa.balizero.com/"),
    finalHref: href("https://balizero.com/visa"),
    httpStatus: 200,
    result: "REDIRECT",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "One redirect reached the public Bali visa selector.",
  },
  {
    id: "kbliNavigator",
    requestedHref: href("https://balizero.com/kbli"),
    finalHref: href("https://balizero.com/kbli"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Public KBLI 2025 navigator rendered.",
  },
  {
    id: "taxIntelligence",
    requestedHref: href("https://tax.balizero.com/"),
    finalHref: href("https://tax.balizero.com/"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "PARTIAL",
    releaseAction: "LINK",
    observation: "Destination is specifically named Tax Compliance Calendar.",
  },
  {
    id: "propertyEligibility",
    requestedHref: href("https://balizero.com/property/eligibility"),
    finalHref: href("https://balizero.com/property/eligibility"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Public Property Eligibility Check rendered.",
  },
  {
    id: "journal",
    requestedHref: href("https://balizero.com/news"),
    finalHref: href("https://balizero.com/news"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Hydrated Journal index rendered with current stories.",
  },
  {
    id: "journalVillaBoom",
    requestedHref: href(
      "https://balizero.com/business/balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap",
    ),
    finalHref: href(
      "https://balizero.com/business/balis-sub-50k-villa-boom-accessible-luxury-or-due-diligence-trap",
    ),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Expected H1; BUSINESS; Sep 4, 2026; 3 min read.",
  },
  {
    id: "journalVillaWall",
    requestedHref: href(
      "https://balizero.com/business/the-villa-dream-has-a-new-wall",
    ),
    finalHref: href(
      "https://balizero.com/business/the-villa-dream-has-a-new-wall",
    ),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Expected H1; BUSINESS; Jun 23, 2026; 4 min read.",
  },
  {
    id: "journalKbliTransition",
    requestedHref: href(
      "https://balizero.com/business/indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know",
    ),
    finalHref: href(
      "https://balizero.com/business/indonesias-kbli-2025-shake-up-the-transition-rules-every-business-must-know",
    ),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Expected H1; BUSINESS; Sep 4, 2026; 3 min read.",
  },
  {
    id: "journalItEscapeRoute",
    requestedHref: href("https://balizero.com/business/the-it-escape-route"),
    finalHref: href("https://balizero.com/business/the-it-escape-route"),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Expected H1; BUSINESS; Jun 23, 2026; 3 min read.",
  },
  {
    id: "journalDiscoveryMall",
    requestedHref: href(
      "https://balizero.com/visas/bali-immigration-brings-permit-services-to-discovery-mall",
    ),
    finalHref: href(
      "https://balizero.com/visas/bali-immigration-brings-permit-services-to-discovery-mall",
    ),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Expected H1; VISAS; Jul 11, 2026; 3 min read.",
  },
  {
    id: "journalNib",
    requestedHref: href(
      "https://balizero.com/business/indonesias-nib-the-one-business-id-every-investor-must-have",
    ),
    finalHref: href(
      "https://balizero.com/business/indonesias-nib-the-one-business-id-every-investor-must-have",
    ),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Expected H1; BUSINESS; Jul 11, 2026; 3 min read.",
  },
  ...[
    ["journalFilterTrends", "https://balizero.com/news?category=trends"],
    ["journalFilterVisas", "https://balizero.com/news?category=visas"],
    ["journalSearchPtPma", "https://balizero.com/news?q=pt+pma"],
    ["journalFilterTaxes", "https://balizero.com/news?category=taxes"],
    ["journalSearchKitas", "https://balizero.com/news?q=kitas"],
    ["journalFilterProperty", "https://balizero.com/news?category=property"],
    ["journalSearchDigitalNomad", "https://balizero.com/news?q=digital+nomad"],
  ].map(([id, requestedHref]) => ({
    id,
    requestedHref: href(requestedHref),
    finalHref: href(requestedHref),
    httpStatus: 200,
    result: "REACHABLE" as const,
    intentMatch: "MISMATCH" as const,
    releaseAction: "FALLBACK" as const,
    observation:
      "Parameter remained in the URL but the unfiltered index rendered.",
  })),
  {
    id: "googleReviews",
    requestedHref: href("https://maps.app.goo.gl/whiMUTNchcDR5naz8"),
    finalHref: href(
      "https://www.google.com/maps/place/Bali+Zero/@-8.6481094,115.1588939,17z/data=!3m1!4b1!4m6!3m5!1s0x2dd247b7b741eb69:0xb3ec70896b8f8fbb!8m2!3d-8.6481094!4d115.1614688!16s%2Fg%2F11smvrwv0x?entry=tts&g_ep=EgoyMDI2MDQxMy4wIPu8ASoASAFQAw%3D%3D&skid=48c2e99a-ad97-4180-9e42-106c5a8ae231",
    ),
    httpStatus: 200,
    result: "REDIRECT",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Bali Zero profile showed 4.9 stars and 679 reviews, not 693.",
  },
  {
    id: "googleLocation",
    requestedHref: href("https://maps.google.com/?q=Bali+Zero+Kerobokan"),
    finalHref: href(
      "https://www.google.com/maps/place/Bali+Zero/@-8.6481094,115.1588939,17z/data=!3m1!4b1!4m6!3m5!1s0x2dd247b7b741eb69:0xb3ec70896b8f8fbb!8m2!3d-8.6481094!4d115.1614688!16s%2Fg%2F11smvrwv0x?entry=ttu&g_ep=EgoyMDI2MDkwMi4wIKXMDSoASAFQAw%3D%3D",
    ),
    httpStatus: 200,
    result: "REDIRECT",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "Bali Zero place profile in Kerobokan rendered.",
  },
  ...[
    [
      "companyAbout",
      "https://balizero.com/v2/company/about",
      "About Bali Zero",
    ],
    ["team", "https://balizero.com/team", "Team | Bali Zero"],
    [
      "privacy",
      "https://balizero.com/v2/privacy",
      "Privacy Policy | Bali Zero",
    ],
    ["terms", "https://balizero.com/v2/terms", "Terms of Service | Bali Zero"],
    ["cookies", "https://balizero.com/v2/cookies", "Cookie Policy | Bali Zero"],
  ].map(([id, requestedHref, title]) => ({
    id,
    requestedHref: href(requestedHref),
    finalHref: href(requestedHref),
    httpStatus: 200,
    result: "REACHABLE" as const,
    intentMatch: "MATCH" as const,
    releaseAction: "LINK" as const,
    observation: `Expected public page rendered as ${title}.`,
  })),
  {
    id: "whatsapp",
    requestedHref: href("https://wa.me/628213454721"),
    finalHref: href(
      "https://api.whatsapp.com/send/?phone=628213454721&text&type=phone_number&app_absent=0",
    ),
    httpStatus: 200,
    result: "REDIRECT",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation: "WhatsApp opened the Bali Zero contact; no message was sent.",
  },
  ...[
    [
      "secondHomeWhatsApp",
      "https://wa.me/628213454721?text=Hello%20Bali%20Zero%2C%20I%20would%20like%20to%20discuss%20Second%20Home%20Studio%20with%20Ari.",
      "https://api.whatsapp.com/send/?phone=628213454721&text=Hello+Bali+Zero%2C+I+would+like+to+discuss+Second+Home+Studio+with+Ari.&type=phone_number&app_absent=0",
    ],
    [
      "evoaWhatsApp",
      "https://wa.me/628213454721?text=Hello%20Bali%20Zero%2C%20I%20would%20like%20to%20discuss%20E-VOA%20with%20Surya.",
      "https://api.whatsapp.com/send/?phone=628213454721&text=Hello+Bali+Zero%2C+I+would+like+to+discuss+E-VOA+with+Surya.&type=phone_number&app_absent=0",
    ],
  ].map(([id, requestedHref, finalHref]) => ({
    id,
    requestedHref: href(requestedHref),
    finalHref: href(finalHref),
    httpStatus: 200,
    result: "REDIRECT" as const,
    intentMatch: "MATCH" as const,
    releaseAction: "LINK" as const,
    observation:
      "WhatsApp preserved the encoded contextual message; nothing sent.",
  })),
  {
    id: "email",
    requestedHref: href("mailto:zantara@balizero.com"),
    finalHref: null,
    httpStatus: null,
    result: "NOT_TESTED",
    intentMatch: "NOT_TESTED",
    releaseAction: "LINK",
    observation:
      "Syntax and recipient validated in tests; mail client was not opened.",
  },
  {
    id: "telephone",
    requestedHref: href("tel:+628213454721"),
    finalHref: null,
    httpStatus: null,
    result: "NOT_TESTED",
    intentMatch: "NOT_TESTED",
    releaseAction: "LINK",
    observation: "E.164 syntax validated in tests; dialer was not opened.",
  },
  {
    id: "telegram",
    requestedHref: href("https://t.me/Balizerobot"),
    finalHref: href("https://t.me/Balizerobot"),
    httpStatus: 200,
    result: "BLOCKED",
    intentMatch: "MISMATCH",
    releaseAction: "SUPPRESS",
    observation: "Public page exposed an unrelated adult/spam bot.",
  },
  {
    id: "pricingExactKey",
    requestedHref: href(
      "https://nuzantara-rag.fly.dev/api/pricing/service?key=E33+Second+Home+%285+Years%29",
    ),
    finalHref: href(
      "https://nuzantara-rag.fly.dev/api/pricing/service?key=E33+Second+Home+%285+Years%29",
    ),
    httpStatus: 200,
    result: "REACHABLE",
    intentMatch: "MATCH",
    releaseAction: "LINK",
    observation:
      "Public exact-key PricingService row returned from the live backend.",
  },
] as const satisfies readonly DestinationEvidence[];

export type DestinationEvidenceId =
  (typeof destinationEvidence20260906)[number]["id"];
