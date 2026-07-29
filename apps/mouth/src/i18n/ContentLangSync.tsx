"use client";

import * as React from "react";
import type { Locale } from "./types";
import { LANG_OWNER_ATTR, LANG_OWNER_CONTENT } from "./content-locale";

/**
 * Keeps `<html lang>` equal to the language the SERVER served for this page's
 * content, and holds ownership of the attribute for as long as such a page is
 * mounted (see content-locale.ts for why the I18nProvider must yield).
 *
 * It re-runs on every locale change, so a client-side navigation between two
 * articles in different languages re-declares correctly. On unmount it
 * releases ownership, so ordinary pages — whose language IS the UI locale —
 * go back to being described by the provider.
 *
 * This runs at hydration, not at parse: the server-rendered HTML still carries
 * the root layout's `lang="en"`. See content-locale.ts for why that residual
 * is not closed here.
 */
export function ContentLangSync({ locale }: { locale: Locale }) {
  React.useEffect(() => {
    const el = document.documentElement;
    el.lang = locale;
    el.setAttribute(LANG_OWNER_ATTR, LANG_OWNER_CONTENT);
    return () => {
      el.removeAttribute(LANG_OWNER_ATTR);
    };
  }, [locale]);

  return null;
}
