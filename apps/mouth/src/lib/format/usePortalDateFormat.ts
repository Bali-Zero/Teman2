"use client";

import { useMemo } from "react";
import { useLanguage } from "@/hooks/useLanguage";
import { formatDate, formatDateTime } from "./date";

/**
 * Binds `formatDate`/`formatDateTime` to the client's current portal
 * language (`useLanguage`, cookie `bz_lang`), so a portal component never
 * has to pass the language through by hand.
 */
export function usePortalDateFormat() {
  const { language } = useLanguage();

  return useMemo(
    () => ({
      formatDate: (
        value: string | Date | null | undefined,
        options?: Intl.DateTimeFormatOptions,
      ) => formatDate(value, language, options),
      formatDateTime: (
        value: string | Date | null | undefined,
        options?: Intl.DateTimeFormatOptions,
      ) => formatDateTime(value, language, options),
    }),
    [language],
  );
}
