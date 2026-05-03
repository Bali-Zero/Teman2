"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { Search, Menu, ChevronDown, X, Globe } from "lucide-react";
import { useTranslation } from "@/i18n";
import type { Locale } from "@/i18n/types";

const LANGUAGES = [
  { code: "en", name: "English", flag: "\u{1F1EC}\u{1F1E7}" },
  { code: "id", name: "Bahasa Indonesia", flag: "\u{1F1EE}\u{1F1E9}" },
  { code: "it", name: "Italiano", flag: "\u{1F1EE}\u{1F1F9}" },
  {
    code: "ru",
    name: "\u0420\u0443\u0441\u0441\u043A\u0438\u0439",
    flag: "\u{1F1F7}\u{1F1FA}",
  },
  { code: "fr", name: "Fran\u00E7ais", flag: "\u{1F1EB}\u{1F1F7}" },
] as const;

export const INSIGHT_CATEGORIES = [
  { name: "Visas", slug: "visas" },
  { name: "Business", slug: "business" },
  { name: "Taxes", slug: "taxes" },
  { name: "Property", slug: "property" },
  { name: "Living", slug: "living" },
  { name: "Trends", slug: "trends" },
];

export const SERVICES = [
  { name: "Visa & Immigration", slug: "visa" },
  { name: "Company Setup", slug: "company" },
  { name: "Tax & Compliance", slug: "tax" },
  { name: "Property", slug: "property" },
];

interface PublicNavProps {
  variant?: "full" | "minimal";
  showSearch?: boolean;
  showLangSwitcher?: boolean;
  onSearchOpen?: () => void;
}

export function PublicNav({
  variant = "full",
  showSearch = false,
  showLangSwitcher = false,
  onSearchOpen,
}: PublicNavProps) {
  const { t, locale, setLocale } = useTranslation();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);
  const [activeDropdown, setActiveDropdown] = React.useState<string | null>(
    null,
  );
  const [langMenuOpen, setLangMenuOpen] = React.useState(false);
  const langMenuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        langMenuRef.current &&
        !langMenuRef.current.contains(e.target as Node)
      ) {
        setLangMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const currentLang = LANGUAGES.find((l) => l.code === locale) || LANGUAGES[0];

  if (variant === "minimal") {
    return (
      <header className="sticky top-0 z-50 bg-[rgba(12,31,58,0.7)] backdrop-blur-md border-b border-[rgba(255,255,255,0.05)] shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center">
              <Image
                src="/assets/logo/balizero-logo-clean.png"
                alt="Bali Zero"
                width={72}
                height={72}
                className="rounded-full"
              />
            </Link>
            <Link
              href="https://balizero.com"
              className="text-sm text-white/60 hover:text-white transition-colors"
            >
              balizero.com
            </Link>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-50 bg-[rgba(12,31,58,0.7)] backdrop-blur-md border-b border-[rgba(255,255,255,0.05)] shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <Link href="/" className="flex items-center">
            <Image
              src="/assets/logo/balizero-logo-clean.png"
              alt="Bali Zero"
              width={104}
              height={104}
              className="rounded-full"
            />
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-1">
            {/* News Dropdown */}
            <div
              className="relative"
              onMouseEnter={() => setActiveDropdown("news")}
              onMouseLeave={() => setActiveDropdown(null)}
            >
              <button className="flex items-center gap-1 px-4 py-2 text-sm text-white/80 hover:text-white transition-colors">
                {t("common.nav.news")}
                <ChevronDown className="w-4 h-4" />
              </button>
              {activeDropdown === "news" && (
                <div className="absolute top-full left-0 w-64 bg-[rgba(10,37,64,0.7)] backdrop-blur-lg border border-[rgba(255,255,255,0.1)] rounded-lg shadow-[0_8px_32px_rgba(0,0,0,0.3)] py-2 mt-1">
                  {INSIGHT_CATEGORIES.map((category) => (
                    <Link
                      key={category.slug}
                      href={`/${category.slug}`}
                      className="block px-4 py-2.5 text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      {category.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Services Dropdown */}
            <div
              className="relative"
              onMouseEnter={() => setActiveDropdown("services")}
              onMouseLeave={() => setActiveDropdown(null)}
            >
              <Link
                href="/services"
                className="flex items-center gap-1 px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
              >
                {t("common.nav.services")}
                <ChevronDown className="w-4 h-4" />
              </Link>
              {activeDropdown === "services" && (
                <div className="absolute top-full left-0 w-64 bg-[rgba(10,37,64,0.7)] backdrop-blur-lg border border-[rgba(255,255,255,0.1)] rounded-lg shadow-[0_8px_32px_rgba(0,0,0,0.3)] py-2 mt-1">
                  {SERVICES.map((service) => (
                    <Link
                      key={service.slug}
                      href={`/services/${service.slug}`}
                      className="block px-4 py-2.5 text-sm text-white/70 hover:text-white hover:bg-white/5 transition-colors"
                    >
                      {service.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Team */}
            <Link
              href="/team"
              className="px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
            >
              {t("common.nav.team")}
            </Link>

            {/* Contact */}
            <Link
              href="/contact"
              className="px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
            >
              {t("common.nav.contact")}
            </Link>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* Search button */}
            {showSearch && onSearchOpen && (
              <button
                onClick={onSearchOpen}
                className="flex items-center gap-2 p-2.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
              >
                <Search className="w-5 h-5" />
                <span className="hidden md:flex items-center gap-1 text-xs text-white/40">
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">
                    ⌘
                  </kbd>
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">
                    K
                  </kbd>
                </span>
              </button>
            )}

            {/* Language switcher */}
            {showLangSwitcher && (
              <div className="relative hidden md:block" ref={langMenuRef}>
                <button
                  onClick={() => setLangMenuOpen(!langMenuOpen)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <Globe className="w-4 h-4" />
                  <span>{currentLang.code.toUpperCase()}</span>
                  <ChevronDown
                    className={`w-3.5 h-3.5 transition-transform ${langMenuOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {langMenuOpen && (
                  <div className="absolute top-full right-0 mt-1 w-48 bg-[rgba(10,37,64,0.7)] backdrop-blur-lg border border-[rgba(255,255,255,0.1)] rounded-lg shadow-[0_8px_32px_rgba(0,0,0,0.3)] py-1 z-50">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => {
                          setLocale(lang.code as Locale);
                          setLangMenuOpen(false);
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                          locale === lang.code
                            ? "bg-white/10 text-white"
                            : "text-white/70 hover:text-white hover:bg-white/5"
                        }`}
                      >
                        <span className="text-lg">{lang.flag}</span>
                        <span>{lang.name}</span>
                        {locale === lang.code && (
                          <svg
                            className="w-4 h-4 ml-auto text-accent-blue-editorial"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
            >
              {mobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-[rgba(10,37,64,0.95)] backdrop-blur-xl border-t border-[rgba(255,255,255,0.05)]">
          <nav className="max-w-[1400px] mx-auto px-4 py-4 space-y-1">
            <div className="py-2">
              <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                {t("common.nav.news")}
              </p>
              {INSIGHT_CATEGORIES.map((category) => (
                <Link
                  key={category.slug}
                  href={`/${category.slug}`}
                  className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {category.name}
                </Link>
              ))}
            </div>

            <div className="py-2 border-t border-white/10">
              <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                {t("common.nav.services")}
              </p>
              {SERVICES.map((service) => (
                <Link
                  key={service.slug}
                  href={`/services/${service.slug}`}
                  className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {service.name}
                </Link>
              ))}
            </div>

            <div className="py-2 border-t border-white/10">
              <Link
                href="/team"
                className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                {t("common.nav.team")}
              </Link>
              <Link
                href="/contact"
                className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                {t("common.nav.contact")}
              </Link>
            </div>

            {/* Language switcher for mobile */}
            {showLangSwitcher && (
              <div className="py-2 border-t border-white/10">
                <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                  {t("common.nav.language")}
                </p>
                <div className="flex gap-2 px-4">
                  {LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      onClick={() => {
                        setLocale(lang.code as Locale);
                        setMobileMenuOpen(false);
                      }}
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors ${
                        locale === lang.code
                          ? "bg-accent-blue-editorial text-white"
                          : "bg-white/5 text-white/70 hover:bg-white/10"
                      }`}
                    >
                      <span>{lang.flag}</span>
                      <span>{lang.code.toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
