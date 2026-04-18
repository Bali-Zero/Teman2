"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Language } from "@/lib/schemas/settings";
import { logger } from "@/lib/logger";

const COOKIE_NAME = "bz_lang";
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/**
 * Production cookie domain. All subdomains under `.balizero.com` share
 * the same `bz_lang` cookie so a language choice on kita.balizero.com
 * carries across to my./prime./etc.
 *
 * In non-prod environments (localhost, Vercel preview) we intentionally
 * omit the Domain attribute so the cookie is host-scoped.
 */
function cookieDomainAttr(): string {
  if (typeof window === "undefined") return "";
  const host = window.location.hostname;
  if (host === "balizero.com" || host.endsWith(".balizero.com")) {
    return "; Domain=.balizero.com";
  }
  return "";
}

/**
 * Read `bz_lang` from document.cookie. Returns `null` if missing or when
 * running SSR.
 */
export function readLanguageCookie(): Language | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|; )bz_lang=([^;]+)/);
  if (!match) return null;
  const parsed = Language.safeParse(decodeURIComponent(match[1]));
  return parsed.success ? parsed.data : null;
}

/**
 * Write `bz_lang` to document.cookie on the appropriate domain. Fails
 * silently when running SSR (no document).
 *
 * Cookie attributes:
 *   - Domain=.balizero.com (prod only — cross-subdomain SSO)
 *   - Path=/
 *   - Max-Age=1 year
 *   - SameSite=Lax (portal flows are same-site)
 *   - Secure (prod only — https everywhere)
 */
export function writeLanguageCookie(lang: Language): void {
  if (typeof document === "undefined") return;
  const isSecure =
    typeof window !== "undefined" && window.location.protocol === "https:";
  const parts = [
    `${COOKIE_NAME}=${encodeURIComponent(lang)}`,
    "Path=/",
    `Max-Age=${ONE_YEAR_SECONDS}`,
    "SameSite=Lax",
  ];
  if (isSecure) parts.push("Secure");
  parts.push(cookieDomainAttr().replace(/^; /, ""));
  // Filter out accidental empty segments from cookieDomainAttr() on non-prod.
  document.cookie = parts.filter(Boolean).join("; ");
}

/**
 * Best-effort PATCH to `/api/portal/settings` to sync the chosen
 * language into `client_preferences`. Never throws — the cookie is the
 * source of truth for the UI, BE sync is opportunistic so that a
 * logged-in user's preference survives across devices.
 *
 * Returns `true` when the BE accepted the update, `false` otherwise
 * (including when the caller isn't a portal client).
 */
async function syncLanguageToBackend(lang: Language): Promise<boolean> {
  try {
    await api.patch("/api/portal/settings", { language: lang });
    return true;
  } catch (err) {
    logger.debug("useLanguage: BE sync failed (cookie still authoritative)", {
      component: "useLanguage",
      action: "be_sync_failure",
      metadata: { error: String(err) },
    });
    return false;
  }
}

export interface UseLanguageResult {
  /** Current language (cookie-first, falls back to `en`). */
  language: Language;
  /** Set language: writes cookie synchronously, fires BE sync in background. */
  setLanguage: (lang: Language) => void;
  /** True while a BE sync is in flight (UI can show a spinner). */
  isSyncing: boolean;
}

/**
 * Cookie-first language preference hook.
 *
 * Semantics:
 *   - Cookie write is the source of truth and is synchronous.
 *   - BE PATCH is best-effort; failures do NOT revert the cookie.
 *   - Initial value reads the cookie; falls back to `"en"`.
 */
export function useLanguage(): UseLanguageResult {
  const [language, setLanguageState] = useState<Language>("en");
  const [isSyncing, setIsSyncing] = useState(false);

  // Hydrate from the cookie on mount (client-only).
  useEffect(() => {
    const fromCookie = readLanguageCookie();
    if (fromCookie) setLanguageState(fromCookie);
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    // 1. Validate — guard against stray inputs from consumers.
    const parsed = Language.safeParse(lang);
    if (!parsed.success) return;

    // 2. Cookie-first: synchronous write, never fails loudly.
    writeLanguageCookie(parsed.data);
    setLanguageState(parsed.data);

    // 3. Best-effort BE sync (fire-and-forget).
    setIsSyncing(true);
    void syncLanguageToBackend(parsed.data).finally(() => {
      setIsSyncing(false);
    });
  }, []);

  return { language, setLanguage, isSyncing };
}
