import type { Metadata } from "next";
import { I18nProvider } from "@/i18n";
import { BreadcrumbJsonLd, FAQJsonLd } from "@/components/seo";
import { SECOND_HOME_FAQS } from "@/lib/seo/faq-data";
import { SecondHomeLanding } from "./SecondHomeLanding";

export const metadata: Metadata = {
  title: "E33 Second Home Visa Indonesia 2026 | Free Fit Memo | Bali Zero",
  description:
    "Indonesia's Second Home Visa (E33): up to 5 years of long-term residence via a USD 130,000 own-name deposit at a state-owned Indonesian bank or USD 1,000,000 completed strata-title property. Free fit memo from Bali Zero.",
  openGraph: {
    title: "E33 Second Home Visa Indonesia — Bali Zero",
    description:
      "Up to 5 years of residence in Indonesia, renewable to 10. Qualify with a USD 130,000 own-name BUMN bank deposit or USD 1,000,000 completed strata-title property. Start with a free fit memo.",
    type: "website",
  },
  alternates: {
    canonical: "https://balizero.com/visa/second-home",
  },
};

const breadcrumbItems = [
  { name: "Home", url: "https://balizero.com" },
  { name: "Visa", url: "https://balizero.com/visa" },
  {
    name: "Second Home Visa (E33)",
    url: "https://balizero.com/visa/second-home",
  },
];

export default function SecondHomeVisaPage() {
  return (
    <>
      {/* Server-side JSON-LD — included in static HTML for Googlebot.
          FAQ copy mirrors the page's localized FAQ section (EN canonical). */}
      <BreadcrumbJsonLd items={breadcrumbItems} />
      <FAQJsonLd items={SECOND_HOME_FAQS} />
      {/* Page-level provider — same pattern as portal/forgot-password: the
          /visa segment layout has no I18nProvider ancestor. Missing keys in
          fr/ru fall back to EN (src/i18n/index.tsx). */}
      <I18nProvider>
        <SecondHomeLanding />
      </I18nProvider>
    </>
  );
}
