import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { I18nProvider } from "@/i18n";
import { ContentLangSync } from "@/i18n/ContentLangSync";
import { BreadcrumbJsonLd, FAQJsonLd } from "@/components/seo";
import { getLocalizedSecondHomeFaqs } from "@/lib/seo/faq-data";
import itMessages from "@/i18n/locales/it.json";
import idMessages from "@/i18n/locales/id.json";
import { SecondHomeLanding } from "../SecondHomeLanding";

/**
 * SEO-grade localized second-home routes (2026-08-20 spec).
 *
 * Mechanism-only: every visible string comes from the EXISTING vetted
 * dictionaries (`secondHome.*` in it.json/id.json, live behind the on-page
 * switcher since f2b325b79) — this route just gives it/id a crawlable,
 * SSG'd, `<html lang>`-correct URL instead of a client-side-only toggle.
 * EN canonical stays `/visa/second-home` (no global `/it/` namespace).
 *
 * `dynamicParams = false` + the exhaustive `generateStaticParams()` below
 * make ANY other segment (e.g. `/visa/second-home/xx`) a true build-time
 * 404 — the static `studio/` sibling is a separate directory entirely and
 * keeps its own priority untouched.
 */

const BASE_URL = "https://balizero.com";
const PAGE_PATH = "/visa/second-home";

type SecondHomeLocale = "it" | "id";

const SECOND_HOME_LOCALES: SecondHomeLocale[] = ["it", "id"];

const LOCALE_MESSAGES: Record<SecondHomeLocale, typeof itMessages> = {
  it: itMessages,
  id: idMessages,
};

// Faithful EN->locale translation of the EN canonical's metadata (no new
// numbers/claims beyond USD 130,000 / USD 1,000,000 / 5 years, already in the
// EN metadata) — no meta-suitable dictionary key covers this exact copy, so
// per spec this is hand-translated rather than reusing a shorter dictionary
// string that would change the claim shape.
const LOCALE_METADATA: Record<
  SecondHomeLocale,
  { title: string; description: string; ogTitle: string; ogDescription: string }
> = {
  it: {
    title: "Visto Second Home E33 Indonesia 2026 | Fit Memo Gratuito",
    description:
      "Visto Second Home indonesiano (E33): fino a 5 anni di soggiorno di lungo termine tramite un deposito di USD 130.000 intestato a te presso una banca statale indonesiana, oppure una proprietà strata-title completata da USD 1.000.000. Fit memo gratuito con Bali Zero.",
    ogTitle: "Visto Second Home E33 Indonesia — Bali Zero",
    ogDescription:
      "Fino a 5 anni di soggiorno in Indonesia, rinnovabile fino a 10. Qualificati con un deposito BUMN di USD 130.000 intestato a te oppure una proprietà strata-title completata da USD 1.000.000. Inizia con un fit memo gratuito.",
  },
  id: {
    title: "Visa Second Home E33 Indonesia 2026 | Fit Memo Gratis",
    description:
      "Visa Second Home Indonesia (E33): hingga 5 tahun izin tinggal jangka panjang melalui deposito USD 130.000 atas nama sendiri di bank BUMN Indonesia, atau properti strata-title senilai USD 1.000.000. Fit memo gratis dari Bali Zero.",
    ogTitle: "Visa Second Home E33 Indonesia — Bali Zero",
    ogDescription:
      "Hingga 5 tahun tinggal di Indonesia, dapat diperpanjang hingga 10 tahun. Memenuhi syarat dengan deposito bank BUMN USD 130.000 atas nama sendiri atau properti strata-title senilai USD 1.000.000. Mulai dengan fit memo gratis.",
  },
};

interface PageProps {
  params: Promise<{ locale: string }>;
}

function isSecondHomeLocale(value: string): value is SecondHomeLocale {
  return (SECOND_HOME_LOCALES as string[]).includes(value);
}

// Full SSG: only "it" and "id" are pre-rendered. `dynamicParams = false`
// turns any other segment into a true build-time 404 (verified in
// page.test.tsx — see spec §1/§7).
export const dynamicParams = false;

export async function generateStaticParams() {
  return SECOND_HOME_LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { locale } = await params;
  if (!isSecondHomeLocale(locale)) return { title: "Not Found" };

  const meta = LOCALE_METADATA[locale];

  return {
    title: meta.title,
    description: meta.description,
    openGraph: {
      title: meta.ogTitle,
      description: meta.ogDescription,
      type: "website",
    },
    alternates: {
      canonical: `${BASE_URL}${PAGE_PATH}/${locale}`,
      languages: {
        en: `${BASE_URL}${PAGE_PATH}`,
        it: `${BASE_URL}${PAGE_PATH}/it`,
        id: `${BASE_URL}${PAGE_PATH}/id`,
        "x-default": `${BASE_URL}${PAGE_PATH}`,
      },
    },
  };
}

export default async function SecondHomeLocalizedPage({ params }: PageProps) {
  const { locale } = await params;
  if (!isSecondHomeLocale(locale)) notFound();

  // Localized final crumb only — "Home"/"Visa" stay as on the EN canonical.
  // Reuses the existing hero eyebrow (short, already vetted) rather than
  // inventing a new breadcrumb-specific string.
  const finalCrumbName = LOCALE_MESSAGES[locale].secondHome.hero.eyebrow;
  const breadcrumbItems = [
    { name: "Home", url: BASE_URL },
    { name: "Visa", url: `${BASE_URL}/visa` },
    { name: finalCrumbName, url: `${BASE_URL}${PAGE_PATH}/${locale}` },
  ];

  return (
    <>
      {/* `<html lang>` ownership — same content-locale contract the article
          routes use (src/i18n/content-locale.ts): this page KNOWS its
          content language, so it claims ownership and the I18nProvider
          below yields. */}
      <ContentLangSync locale={locale} />
      {/* Server-side JSON-LD, built from the locale dictionary directly so
          it can never disagree with the visible FAQ section below. */}
      <BreadcrumbJsonLd items={breadcrumbItems} />
      <FAQJsonLd items={getLocalizedSecondHomeFaqs(locale)} />
      {/* `initialLocale` pins state to `locale` on the very first render —
          no effect required — so SSR/SSG output is already in the right
          language; the init effect inside I18nProvider skips the
          `?lang=`/localStorage restore entirely for this route. */}
      <I18nProvider initialLocale={locale}>
        <SecondHomeLanding />
      </I18nProvider>
    </>
  );
}
