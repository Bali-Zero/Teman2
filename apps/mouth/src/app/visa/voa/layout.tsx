import type { Metadata } from "next";
import { I18nProvider } from "@/i18n";

// Metadata lives in the LAYOUT, not in page.tsx: the wizard page is a client
// component ("use client"), which cannot export metadata. Sibling precedent
// (visa/second-home) splits a server page.tsx from a client landing component;
// this segment does not need that split just to carry a title.
//
// The canonical deliberately points at the funnel entry and is INHERITED by
// `voa/[hash]` result pages. That is the intent, not an oversight: a result
// page is one visitor's ephemeral answer, so the indexable representative of
// the whole segment is the entry page.
//
// No price in this copy — prices come from PricingTool server-side per request
// (golden rule 11); a number hardcoded here would go stale silently. No claim
// about timing or approval either: the charter's forbidden-claims list
// (guaranteed approval / guaranteed turnaround / fully-online extension) binds
// SEO copy exactly as it binds the page body.
export const metadata: Metadata = {
  title:
    "Visa on Arrival (B1) Indonesia — eligibility, dates, price | Bali Zero",
  description:
    "Check a Visa on Arrival or its extension in 7 questions: whether the case is straightforward, your stay window, the published filing deadline, and our all-inclusive fee. No documents to upload, no payment to check.",
  openGraph: {
    title: "Check your Visa on Arrival — Bali Zero",
    description:
      "Seven questions, then your stay window, the filing deadline that applies, and an all-inclusive price. Nothing to upload, nothing to pay to find out.",
    type: "website",
  },
  alternates: {
    canonical: "https://balizero.com/visa/voa",
  },
};

export default function GarudaVoaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Route-level provider — the /visa segment layout has no I18nProvider
  // ancestor. lint_i18n_providers contract: the provider must live in the
  // calling file itself or in an ancestor layout.tsx. Missing keys in fr/ru
  // fall back to EN (src/i18n/index.tsx).
  return <I18nProvider>{children}</I18nProvider>;
}
