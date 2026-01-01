'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Search, Menu, ChevronDown, X, Globe } from 'lucide-react';
import { SearchModal } from '@/components/blog/SearchBar';

// Language options
const LANGUAGES = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'id', name: 'Bahasa Indonesia', flag: '🇮🇩' },
] as const;

type LanguageCode = typeof LANGUAGES[number]['code'];

/**
 * Blog Layout - "The Chronicle"
 * McKinsey-inspired layout with professional navigation
 */
export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);
  const [activeDropdown, setActiveDropdown] = React.useState<string | null>(null);
  const [isSearchOpen, setIsSearchOpen] = React.useState(false);
  const [language, setLanguage] = React.useState<LanguageCode>('en');
  const [langMenuOpen, setLangMenuOpen] = React.useState(false);
  const langMenuRef = React.useRef<HTMLDivElement>(null);

  // Load saved language preference
  React.useEffect(() => {
    const saved = localStorage.getItem('blog-language') as LanguageCode | null;
    if (saved && LANGUAGES.some(l => l.code === saved)) {
      setLanguage(saved);
    }
  }, []);

  // Close language menu when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (langMenuRef.current && !langMenuRef.current.contains(e.target as Node)) {
        setLangMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLanguageChange = (code: LanguageCode) => {
    setLanguage(code);
    localStorage.setItem('blog-language', code);
    setLangMenuOpen(false);
    // In future: trigger content translation or reload
  };

  const currentLang = LANGUAGES.find(l => l.code === language) || LANGUAGES[0];

  // Global keyboard shortcut for search (Cmd/Ctrl + K)
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="min-h-screen bg-[#051C2C] text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#051C2C] border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            {/* Logo */}
            <Link href="/" className="flex items-center">
              <Image
                src="/images/balizero-logo.png"
                alt="Bali Zero"
                width={52}
                height={52}
                className="rounded-full"
              />
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center gap-1">
              {/* Insights Dropdown */}
              <div
                className="relative"
                onMouseEnter={() => setActiveDropdown('insights')}
                onMouseLeave={() => setActiveDropdown(null)}
              >
                <Link
                  href="/insights"
                  className="flex items-center gap-1 px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
                >
                  Insights
                  <ChevronDown className="w-4 h-4" />
                </Link>

                {activeDropdown === 'insights' && (
                  <div className="absolute top-full left-0 w-64 bg-[#0a2540] border border-white/10 rounded-lg shadow-xl py-2 mt-1">
                    {INSIGHT_CATEGORIES.map((category) => (
                      <Link
                        key={category.slug}
                        href={`/insights/${category.slug}`}
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
                onMouseEnter={() => setActiveDropdown('services')}
                onMouseLeave={() => setActiveDropdown(null)}
              >
                <Link
                  href="/services"
                  className="flex items-center gap-1 px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
                >
                  Services
                  <ChevronDown className="w-4 h-4" />
                </Link>

                {activeDropdown === 'services' && (
                  <div className="absolute top-full left-0 w-64 bg-[#0a2540] border border-white/10 rounded-lg shadow-xl py-2 mt-1">
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

              <Link
                href="/about"
                className="px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
              >
                About
              </Link>

              <Link
                href="/contact"
                className="px-4 py-2 text-sm text-white/80 hover:text-white transition-colors"
              >
                Contact
              </Link>
            </nav>

            {/* Actions */}
            <div className="flex items-center gap-3">
              {/* Search button */}
              <button
                onClick={() => setIsSearchOpen(true)}
                className="flex items-center gap-2 p-2.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors"
              >
                <Search className="w-5 h-5" />
                <span className="hidden md:flex items-center gap-1 text-xs text-white/40">
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">⌘</kbd>
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">K</kbd>
                </span>
              </button>

              {/* Language switcher */}
              <div className="relative hidden md:block" ref={langMenuRef}>
                <button
                  onClick={() => setLangMenuOpen(!langMenuOpen)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <Globe className="w-4 h-4" />
                  <span>{currentLang.code.toUpperCase()}</span>
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${langMenuOpen ? 'rotate-180' : ''}`} />
                </button>

                {langMenuOpen && (
                  <div className="absolute top-full right-0 mt-1 w-48 bg-[#0a2540] border border-white/10 rounded-lg shadow-xl py-1 z-50">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => handleLanguageChange(lang.code)}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                          language === lang.code
                            ? 'bg-white/10 text-white'
                            : 'text-white/70 hover:text-white hover:bg-white/5'
                        }`}
                      >
                        <span className="text-lg">{lang.flag}</span>
                        <span>{lang.name}</span>
                        {language === lang.code && (
                          <svg className="w-4 h-4 ml-auto text-[#2251ff]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* CTA Button */}
              <Link
                href="/contact"
                className="hidden md:inline-flex px-5 py-2.5 rounded-lg bg-[#2251ff] text-white text-sm font-medium hover:bg-[#1a41cc] transition-colors"
              >
                Get Started
              </Link>

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
          <div className="lg:hidden bg-[#0a2540] border-t border-white/10">
            <nav className="max-w-[1400px] mx-auto px-4 py-4 space-y-1">
              <div className="py-2">
                <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                  Insights
                </p>
                {INSIGHT_CATEGORIES.map((category) => (
                  <Link
                    key={category.slug}
                    href={`/insights/${category.slug}`}
                    className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {category.name}
                  </Link>
                ))}
              </div>

              <div className="py-2 border-t border-white/10">
                <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                  Services
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
                  href="/about"
                  className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  About
                </Link>
                <Link
                  href="/contact"
                  className="block px-4 py-2.5 text-sm text-white/70 hover:text-white transition-colors"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Contact
                </Link>
              </div>

              {/* Language switcher for mobile */}
              <div className="py-2 border-t border-white/10">
                <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/40">
                  Language
                </p>
                <div className="flex gap-2 px-4">
                  {LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      onClick={() => {
                        handleLanguageChange(lang.code);
                        setMobileMenuOpen(false);
                      }}
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors ${
                        language === lang.code
                          ? 'bg-[#2251ff] text-white'
                          : 'bg-white/5 text-white/70 hover:bg-white/10'
                      }`}
                    >
                      <span>{lang.flag}</span>
                      <span>{lang.code.toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-4">
                <Link
                  href="/contact"
                  className="block w-full px-4 py-3 rounded-lg bg-[#2251ff] text-white text-sm font-medium text-center hover:bg-[#1a41cc] transition-colors"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Get Started
                </Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      {/* Main content */}
      <main>{children}</main>

      {/* Search Modal */}
      <SearchModal isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />

      {/* Footer */}
      <footer className="bg-[#031219] border-t border-white/10">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10">
            {/* Brand */}
            <div className="lg:col-span-2">
              <Link href="/" className="flex items-center mb-6">
                <Image
                  src="/images/balizero-logo.png"
                  alt="Bali Zero"
                  width={52}
                  height={52}
                  className="rounded-full"
                />
              </Link>
              <p className="text-white/50 max-w-sm mb-6 leading-relaxed">
                Your trusted partner for business, immigration, and life in
                Indonesia. Expert guidance for every step of your journey.
              </p>

              {/* Social Links */}
              <div className="flex items-center gap-4">
                <a
                  href="https://instagram.com/balizero"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                </a>
                <a
                  href="https://wa.me/6281234567890"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                  </svg>
                </a>
                <a
                  href="https://linkedin.com/company/balizero"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-10 h-10 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                </a>
              </div>
            </div>

            {/* Services */}
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-wider text-white mb-5">
                Services
              </h4>
              <ul className="space-y-3">
                {SERVICES.map((service) => (
                  <li key={service.slug}>
                    <Link
                      href={`/services/${service.slug}`}
                      className="text-sm text-white/50 hover:text-white transition-colors"
                    >
                      {service.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Insights */}
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-wider text-white mb-5">
                Insights
              </h4>
              <ul className="space-y-3">
                {INSIGHT_CATEGORIES.map((category) => (
                  <li key={category.slug}>
                    <Link
                      href={`/insights/${category.slug}`}
                      className="text-sm text-white/50 hover:text-white transition-colors"
                    >
                      {category.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Contact */}
            <div>
              <h4 className="text-sm font-semibold uppercase tracking-wider text-white mb-5">
                Contact
              </h4>
              <ul className="space-y-3">
                <li>
                  <a
                    href="mailto:hello@balizero.com"
                    className="text-sm text-white/50 hover:text-white transition-colors"
                  >
                    hello@balizero.com
                  </a>
                </li>
                <li>
                  <a
                    href="https://wa.me/6281234567890"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-white/50 hover:text-white transition-colors"
                  >
                    +62 812 3456 7890
                  </a>
                </li>
                <li>
                  <span className="text-sm text-white/50">
                    Bali, Indonesia
                  </span>
                </li>
              </ul>

              <div className="mt-6">
                <Link
                  href="/contact"
                  className="inline-flex px-4 py-2 rounded-lg bg-[#2251ff] text-white text-sm font-medium hover:bg-[#1a41cc] transition-colors"
                >
                  Get in touch
                </Link>
              </div>
            </div>
          </div>

          {/* Copyright */}
          <div className="mt-16 pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-xs text-white/40">
              &copy; {new Date().getFullYear()} Bali Zero. All rights reserved.
            </p>
            <div className="flex items-center gap-6 text-xs text-white/40">
              <Link href="/privacy" className="hover:text-white transition-colors">
                Privacy Policy
              </Link>
              <Link href="/terms" className="hover:text-white transition-colors">
                Terms of Service
              </Link>
              <Link href="/sitemap" className="hover:text-white transition-colors">
                Sitemap
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Navigation data
const INSIGHT_CATEGORIES = [
  { name: 'Immigration', slug: 'immigration' },
  { name: 'Business', slug: 'business' },
  { name: 'Tax & Legal', slug: 'tax-legal' },
  { name: 'Property', slug: 'property' },
  { name: 'Lifestyle', slug: 'lifestyle' },
];

const SERVICES = [
  { name: 'Visa & Immigration', slug: 'visa' },
  { name: 'Company Setup', slug: 'company' },
  { name: 'Tax & Compliance', slug: 'tax' },
  { name: 'Property', slug: 'property' },
];
