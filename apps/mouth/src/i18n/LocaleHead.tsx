"use client";

import { useTranslation } from "@/i18n";

const BASE_URL = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export function LocaleHead() {
  const { locale } = useTranslation();

  return (
    <>
      <link rel="alternate" hrefLang="en" href={BASE_URL} />
      <link rel="alternate" hrefLang="id" href={BASE_URL} />
      <link rel="alternate" hrefLang="x-default" href={BASE_URL} />
      <meta httpEquiv="content-language" content={locale} />
    </>
  );
}
