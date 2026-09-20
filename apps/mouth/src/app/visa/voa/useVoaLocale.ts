"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  resolveVoaLocale,
  SITE_LOCALE_PREFERENCE_KEY,
  VOA_LOCALE_QUERY_PARAM,
  VOA_LOCALE_RULING,
  type VoaLocale,
} from "./voa-locale";

/**
 * The funnel's language on the client. Split from `voa-locale.ts` so the
 * ruling and its resolver stay importable from a node test without React.
 *
 * The stored preference is read in an EFFECT, never during render: the page
 * is server-rendered (the layout is `force-dynamic`), and reading
 * localStorage while rendering would make the server's HTML and the client's
 * first paint disagree. Under the ruling in force — `english-by-default` —
 * the preference is not read at all, so there is nothing to flash.
 */
export function useVoaLocale(): VoaLocale {
  const searchParams = useSearchParams();
  const requested = searchParams?.get(VOA_LOCALE_QUERY_PARAM) ?? null;
  const [preference, setPreference] = useState<string | null>(null);

  useEffect(() => {
    if (VOA_LOCALE_RULING !== "follow-site-preference") return;
    try {
      setPreference(window.localStorage.getItem(SITE_LOCALE_PREFERENCE_KEY));
    } catch {
      // A browser with storage disabled is an English visitor, not an error.
    }
  }, []);

  return resolveVoaLocale({ requested, preference });
}
