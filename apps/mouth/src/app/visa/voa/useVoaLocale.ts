"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  resolveVoaLocale,
  SITE_LOCALE_PREFERENCE_KEY,
  VOA_LOCALE_QUERY_PARAM,
  VOA_LOCALE_RULING,
  VOA_LOCALE_COOKIE,
  VOA_LOCALE_COOKIE_MAX_AGE_S,
  VOA_LOCALE_SESSION_KEY,
  type VoaLocale,
} from "./voa-locale";

/** The journey cookie, read from `document.cookie` without a parser library. */
function readJourneyCookie(): string | null {
  const hit = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${VOA_LOCALE_COOKIE}=`));
  return hit
    ? decodeURIComponent(hit.slice(VOA_LOCALE_COOKIE.length + 1))
    : null;
}

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
  const [session, setSession] = useState<string | null>(null);
  const [journey, setJourney] = useState<string | null>(null);

  useEffect(() => {
    try {
      if (requested) {
        // Typed once, on whichever screen the visitor typed it; carried from
        // here so `router.push` to the verdict does not drop the language.
        window.sessionStorage.setItem(VOA_LOCALE_SESSION_KEY, requested);
        setSession(requested);
        // ...and into the cookie, which is the half that survives the magic
        // link's hop into a NEW tab. Written only on an explicit `?lang=`, so
        // a visitor who never asked never carries one.
        document.cookie = `${VOA_LOCALE_COOKIE}=${encodeURIComponent(requested)}; Max-Age=${VOA_LOCALE_COOKIE_MAX_AGE_S}; Path=/; SameSite=Lax`;
        setJourney(requested);
      } else {
        setSession(window.sessionStorage.getItem(VOA_LOCALE_SESSION_KEY));
        setJourney(readJourneyCookie());
      }
    } catch {
      // A tab with storage disabled keeps the language only while the query
      // string is in the URL. That is a smaller funnel, not a broken one.
    }
    if (VOA_LOCALE_RULING !== "follow-site-preference") return;
    try {
      setPreference(window.localStorage.getItem(SITE_LOCALE_PREFERENCE_KEY));
    } catch {
      // A browser with storage disabled is an English visitor, not an error.
    }
  }, [requested]);

  return resolveVoaLocale({ requested, session, journey, preference });
}
