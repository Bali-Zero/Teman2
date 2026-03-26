"use client";

import { useState, useCallback } from "react";
import Image from "next/image";
import { LazyMotion, domAnimation, m, AnimatePresence } from "framer-motion";
import { BookShell } from "@/components/book/BookShell";
import { ChapterSection } from "@/components/book/ChapterSection";
import { ChapterHero } from "@/components/book/ChapterHero";
import { StatsCounter } from "@/components/book/StatsCounter";
import { TeamGrid } from "@/components/book/TeamGrid";
import { TimelineComponent } from "@/components/book/TimelineComponent";
import { ZantaraCTA } from "@/components/book/ZantaraCTA";
import { ServicePricingCard } from "@/components/book/ServicePricingCard";
import {
  CHAPTERS,
  CONTACTS,
  SERVICES,
  TRANSLATIONS,
  LOCALE_LABELS,
  type Locale,
} from "@/components/book/book-data";

interface BookPageProps {
  initialChapter?: string;
}

// ─── Locale switcher ────────────────────────────────────────────────────────────
function LocaleSwitcher({
  locale,
  onChange,
}: {
  locale: Locale;
  onChange: (l: Locale) => void;
}) {
  const locales = Object.entries(LOCALE_LABELS) as [Locale, string][];
  return (
    <div className="fixed top-4 right-4 z-50 flex items-center gap-1 bg-black/40 backdrop-blur-sm border border-white/10 rounded-xl px-2 py-1.5">
      {locales.map(([l, label]) => (
        <button
          key={l}
          onClick={() => onChange(l)}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all font-[family-name:var(--font-montserrat)] ${
            locale === l
              ? "bg-[#d4845a] text-white"
              : "text-white/50 hover:text-white"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

// ─── Services section ────────────────────────────────────────────────────────────
function ServicesSection({ locale }: { locale: Locale }) {
  const t = TRANSLATIONS[locale];
  const categories = ["visa", "company", "tax", "property"] as const;
  const [activeCategory, setActiveCategory] =
    useState<(typeof categories)[number]>("visa");

  const filtered = SERVICES.filter((s) => s.category === activeCategory);

  // Build translated service items with translated features when locale is not english
  const translatedServices = filtered.map((s) => ({
    ...s,
    waMessage:
      locale === "en"
        ? s.waMessage
        : `Hi, I am interested in ${s.title}. Can you give me more info? (${LOCALE_LABELS[locale]})`,
    badge: s.badge
      ? s.badge === "Most popular"
        ? t.mostPopular
        : s.badge === "For companies"
          ? t.forCompanies
          : t.forBusinessOwners
      : undefined,
  }));

  return (
    <div className="px-6 md:px-16 py-12">
      {/* Category tabs */}
      <div className="flex flex-wrap gap-2 mb-8">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all font-[family-name:var(--font-montserrat)] border ${
              activeCategory === cat
                ? "bg-[#d4845a] border-[#d4845a] text-white"
                : "border-white/15 text-white/55 hover:border-white/30 hover:text-white/80"
            }`}
          >
            {t.servicesCategories[cat]}
          </button>
        ))}
      </div>

      {/* Cards */}
      <LazyMotion features={domAnimation}>
        <AnimatePresence mode="wait">
          <m.div
            key={activeCategory}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-5xl"
          >
            {translatedServices.map((svc) => (
              <ServicePricingCard
                key={svc.serviceKey}
                title={svc.title}
                tagline={svc.tagline}
                serviceKey={svc.serviceKey}
                features={svc.features}
                waMessage={svc.waMessage}
                badge={svc.badge}
                ctaLabel={t.askOnWhatsApp}
              />
            ))}
          </m.div>
        </AnimatePresence>
      </LazyMotion>
    </div>
  );
}

// ─── BookPage ───────────────────────────────────────────────────────────────────
export function BookPage({ initialChapter }: BookPageProps) {
  const [locale, setLocale] = useState<Locale>("en");
  const t = TRANSLATIONS[locale];

  const handleZantara = useCallback(() => {
    const trigger = document.querySelector<HTMLButtonElement>(
      "[data-zantara-trigger]",
    );
    if (trigger) trigger.click();
  }, []);

  return (
    <BookShell initialChapter={initialChapter} translations={t}>
      <LocaleSwitcher locale={locale} onChange={setLocale} />

      {/* ── Chapter 1: Cover ───────────────────────────────────────────────────── */}
      <ChapterSection id="cover" className="flex items-center justify-center">
        <div className="absolute inset-0">
          <Image
            src="/static/image_art/zantara_gold_black_gradient_transparent.png"
            alt="Bali Zero"
            fill
            priority
            className="object-cover opacity-40"
            sizes="100vw"
          />
          {/* Deeper nebula glow on cover */}
          <div
            aria-hidden="true"
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(212,132,90,0.12) 0%, transparent 70%)",
            }}
          />
        </div>
        <div className="relative z-10 flex flex-col items-center text-center px-8">
          {/* Logo instead of text */}
          <div className="mb-8 w-48 md:w-64 h-auto relative">
            <Image
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              width={320}
              height={120}
              className="object-contain drop-shadow-[0_0_32px_rgba(212,132,90,0.5)]"
              priority
            />
          </div>
          <p className="font-[family-name:var(--font-montserrat)] text-[#d4845a] tracking-[0.3em] text-xs uppercase mb-4">
            {t.coverTagline}
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/55 text-lg max-w-sm">
            {t.coverSubtitle}
          </p>
          <div className="mt-14 flex flex-col items-center gap-2">
            <div className="w-px h-10 bg-gradient-to-b from-transparent to-[#d4845a]/60 animate-pulse" />
            <span className="font-[family-name:var(--font-montserrat)] text-white/25 text-xs tracking-[0.25em] uppercase">
              {t.scrollDown}
            </span>
          </div>
        </div>
      </ChapterSection>

      {/* ── Chapter 2: Manifesto ───────────────────────────────────────────────── */}
      <ChapterSection id="manifesto">
        <ChapterHero
          image={CHAPTERS[1].heroImage}
          imageAlt={CHAPTERS[1].heroImageAlt}
          title={CHAPTERS[1].title}
          subtitle={CHAPTERS[1].subtitle}
        />
        <div className="px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-6">
            {t.manifestoP1}
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed">
            {t.manifestoP2}
          </p>
        </div>
        <StatsCounter locale={locale} />
      </ChapterSection>

      {/* ── Chapter 3: Origin ─────────────────────────────────────────────────── */}
      <ChapterSection id="origin">
        <ChapterHero
          image={CHAPTERS[2].heroImage}
          imageAlt={CHAPTERS[2].heroImageAlt}
          title={CHAPTERS[2].title}
          subtitle={CHAPTERS[2].subtitle}
        />
        <div className="px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-6">
            {t.originP1}
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed">
            {t.originP2}
          </p>
        </div>
        <TimelineComponent locale={locale} />
      </ChapterSection>

      {/* ── Chapter 4: Team ───────────────────────────────────────────────────── */}
      <ChapterSection id="team">
        <ChapterHero
          image={CHAPTERS[3].heroImage}
          imageAlt={CHAPTERS[3].heroImageAlt}
          title={CHAPTERS[3].title}
          subtitle={CHAPTERS[3].subtitle}
        />
        <TeamGrid locale={locale} />
      </ChapterSection>

      {/* ── Chapter 5: Services ───────────────────────────────────────────────── */}
      <ChapterSection id="services">
        <ChapterHero
          image={CHAPTERS[4].heroImage}
          imageAlt={CHAPTERS[4].heroImageAlt}
          title={CHAPTERS[4].title}
          subtitle={CHAPTERS[4].subtitle}
        />
        <ServicesSection locale={locale} />
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* ── Chapter 6: Impact ─────────────────────────────────────────────────── */}
      <ChapterSection id="impact">
        <ChapterHero
          image={CHAPTERS[5].heroImage}
          imageAlt={CHAPTERS[5].heroImageAlt}
          title={CHAPTERS[5].title}
          subtitle={CHAPTERS[5].subtitle}
        />
        <div className="px-8 md:px-16 py-12 max-w-4xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-10">
            {t.impactBody}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: "Emerhub", founded: 2011, trend: "-8.5%" },
              { name: "InCorp", founded: 2012, trend: "-19%" },
              { name: "LetsMoveIndonesia", founded: 2015, trend: "-23.5%" },
              { name: "Seven Stones", founded: 2016, trend: "+1.8%" },
            ].map((c) => (
              <div
                key={c.name}
                className="border border-white/8 rounded-2xl p-5 text-center bg-white/[0.015]"
              >
                <p className="font-[family-name:var(--font-spartan)] text-white/55 text-sm font-semibold mb-2">
                  {c.name}
                </p>
                <p
                  className={`font-[family-name:var(--font-spartan)] font-black text-2xl ${
                    c.trend.startsWith("+")
                      ? "text-emerald-400"
                      : "text-red-400"
                  }`}
                >
                  {c.trend}
                </p>
                <p className="text-white/30 text-xs mt-1">{t.headcountYoY}</p>
              </div>
            ))}
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* ── Chapter 7: Technology ─────────────────────────────────────────────── */}
      <ChapterSection id="technology">
        <ChapterHero
          image={CHAPTERS[6].heroImage}
          imageAlt={CHAPTERS[6].heroImageAlt}
          title={CHAPTERS[6].title}
          subtitle={CHAPTERS[6].subtitle}
        />
        <div className="px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-10">
            {t.techBody}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {t.techStats.map((s) => (
              <div
                key={s.l}
                className="border border-white/8 rounded-2xl p-5 bg-white/[0.015]"
              >
                <p className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-black text-3xl mb-1">
                  {s.n}
                </p>
                <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-xs leading-snug">
                  {s.l}
                </p>
              </div>
            ))}
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* ── Chapter 8: Contact ────────────────────────────────────────────────── */}
      <ChapterSection id="contact">
        <ChapterHero
          image={CHAPTERS[7].heroImage}
          imageAlt={CHAPTERS[7].heroImageAlt}
          title={CHAPTERS[7].title}
          subtitle={CHAPTERS[7].subtitle}
        />
        <div className="px-8 md:px-16 py-16 text-center max-w-2xl mx-auto">
          <p className="font-[family-name:var(--font-montserrat)] text-white/60 text-lg mb-10 leading-relaxed">
            {t.contactBody}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href={`${CONTACTS.whatsappUrl}?text=${encodeURIComponent(t.contactCta)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-[#25D366] text-white font-[family-name:var(--font-montserrat)] font-semibold text-lg hover:bg-[#1fb855] transition-colors shadow-[0_0_24px_rgba(37,211,102,0.25)]"
            >
              {CONTACTS.whatsapp}
            </a>
            <a
              href={`mailto:${CONTACTS.email}`}
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl border border-white/20 text-white font-[family-name:var(--font-montserrat)] font-semibold hover:bg-white/5 hover:border-white/30 transition-colors"
            >
              {CONTACTS.email}
            </a>
          </div>
          {/* Logo at the bottom */}
          <div className="mt-16 flex justify-center">
            <Image
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              width={120}
              height={48}
              className="object-contain opacity-30"
            />
          </div>
          <p className="font-[family-name:var(--font-montserrat)] text-white/20 text-xs mt-4">
            {t.copyright}
          </p>
        </div>
      </ChapterSection>
    </BookShell>
  );
}
