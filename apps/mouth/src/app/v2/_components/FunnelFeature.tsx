"use client";

import { useState } from "react";
import Image from "next/image";
import {
  Search,
  IdCard,
  Building2,
  TrendingUp,
  MapPinned,
  ArrowRight,
  Sparkles,
  MapPin,
  type LucideIcon,
} from "lucide-react";
import type { Funnel } from "@balizero/core/components/ThemeProvider";

type LayoutMode = "full" | "half";

const FUNNEL_HREF: Record<Exclude<Funnel, null>, string> = {
  visa: "https://visa.balizero.com/",
  kbli: "/kbli",
  tax: "https://tax.balizero.com/",
  property: "/property/eligibility",
};

// Separate destination for the "See transparent pricing" secondary CTA —
// must land on an actual pricing page, not on the funnel landing.
// Fix for CRO audit 2026-04-19 (bait-and-switch bug).
const FUNNEL_PRICING_HREF: Record<Exclude<Funnel, null>, string> = {
  visa: "https://visa.balizero.com/pricing",
  kbli: "https://kita.balizero.com/kbli/pricing",
  tax: "https://tax.balizero.com/pricing",
  property: "https://balizero.com/pricing",
};

interface FunnelFeatureProps {
  funnel: Exclude<Funnel, null>;
  layout: LayoutMode;
  status: "Live" | "Beta";
  badge: string;
  title: string;
  subtitle: string;
  description: string;
  features: string[];
  cta: string;
  searchPlaceholder: string;
  searchSuggestions: string[];
  Icon: LucideIcon;
  // Pricing — absorbed from former ServicesPricing block. Shown as a pill
  // next to the CTA so the offer is legible without a separate section.
  priceLabel: string; // e.g. "Visa Processing"
  price: string; // e.g. "$350"
  priceUnit: string; // e.g. "/ visa"
  location: string; // e.g. "Seminyak, Bali"
  // Editorial background image for the left half of the block.
  bgImage: string; // e.g. "/assets/art/hero-visa.jpg"
  // How the bg image fits: "cover" fills fully (may crop), "contain" shows
  // whole image without cropping (may leave side gutters filled by gradient).
  bgFit?: "cover" | "contain";
  // Object-position when using cover: shift the crop focus.
  bgPosition?: string; // e.g. "center top", "50% 30%"
}

const CONFIGS: Record<
  Exclude<Funnel, null>,
  Omit<FunnelFeatureProps, "layout">
> = {
  visa: {
    funnel: "visa",
    status: "Live",
    badge: "AI Immigration Assistant",
    title: "Visa Oracle",
    subtitle:
      "KITAS & Golden Visa 2025: residency guide for foreign investors.",
    description:
      "Chat with an AI that has read every Indonesian immigration regulation since 2011. KITAS, KITAP, Golden Visa, Digital Nomad — precise answers backed by source paragraphs, not guesswork.",
    features: [
      "AI drafts. Our licensed Indonesian team signs.",
      "24+ visa categories · Multilingual (EN · IT · ID)",
      "Every answer cited from primary sources",
      "5,000+ expat cases handled since 2019",
    ],
    cta: "Try Visa Oracle",
    searchPlaceholder: "e.g. Can I open a PT PMA on a B211A visa?",
    searchSuggestions: [
      "KITAS for retirees",
      "Golden Visa 5yr",
      "E33G investor",
      "Digital Nomad B1",
      "Dependent family visa",
    ],
    Icon: IdCard,
    priceLabel: "Visa Processing",
    price: "$350",
    priceUnit: "/ visa",
    location: "Seminyak, Bali",
    bgImage: "/assets/art/hero-visa.jpg",
    bgFit: "cover",
    bgPosition: "center center",
  },
  kbli: {
    funnel: "kbli",
    status: "Live",
    badge: "Featured Intelligence Tool",
    title: "KBLI 2025 Navigator",
    subtitle: "Find your eligible PT PMA business sectors in 60 seconds.",
    description:
      "Instant access to the complete Indonesian business classification with bilingual search, 4-level risk assessment, PMA status, minimum capital, required licenses.",
    features: [
      "AI narrows down. Our licensed notaries file.",
      "1,563 codes · bilingual search (EN/ID)",
      "4-level risk + PMA eligibility + minimum capital",
      "Hub-and-spoke linked to our PT PMA guides",
    ],
    cta: "Explore Navigator",
    searchPlaceholder:
      "Search KBLI codes — e.g. villa rental, restaurant, tech startup",
    searchSuggestions: [
      "Villa rental",
      "Restaurant",
      "Tech startup",
      "Property",
      "Education",
    ],
    Icon: Building2,
    priceLabel: "Company Setup",
    price: "$1,850",
    priceUnit: "/ company",
    location: "Kuta, Bali",
    bgImage: "/assets/art/hero-kbli.jpg",
    bgFit: "cover",
    bgPosition: "center center",
  },
  tax: {
    funnel: "tax",
    status: "Beta",
    badge: "Tax Intelligence",
    title: "Tax Intelligence",
    subtitle:
      "CoreTax 2025: corporate tax compliance for foreign PT PMA owners.",
    description:
      "Monthly PPh, PPN, annual SPT, BPJS, LKPM — handled by a dedicated team. CoreTax integrated. Not automated guesswork.",
    features: [
      "12+ filing types handled",
      "CoreTax native integration",
      "24/7 AI support",
    ],
    cta: "Book a Tax Review",
    searchPlaceholder: "e.g. How is PPh 21 calculated for expats?",
    searchSuggestions: [
      "PPh 21 for expats",
      "VAT refund",
      "SPT annual",
      "BPJS",
      "LKPM quarterly",
    ],
    Icon: TrendingUp,
    priceLabel: "Tax & Accounting",
    price: "$220",
    priceUnit: "/ month",
    location: "Denpasar, Bali",
    bgImage: "/assets/art/hero-tax.jpeg",
  },
  property: {
    funnel: "property",
    status: "Beta",
    badge: "Zoning & Due Diligence",
    title: "Property Map",
    subtitle:
      "Property due diligence 2025: zoning guide for foreign buyers in Bali.",
    description:
      "Zoning intelligence, due diligence, land certificate verification. Every plot, every zone, every rule across Bali.",
    features: [
      "Bali-wide zoning coverage",
      "7-day DD turnaround",
      "Land certificates verified",
    ],
    cta: "Check Zoning",
    searchPlaceholder: "Enter a plot address or sertifikat number",
    searchSuggestions: [
      "Canggu villa zone",
      "Ubud residential",
      "Seminyak commercial",
      "Hak Pakai",
      "Leasehold",
    ],
    Icon: MapPinned,
    priceLabel: "Property Due Diligence",
    price: "$850",
    priceUnit: "/ report",
    location: "Ubud, Bali",
    bgImage: "/assets/art/hero-zoning.jpeg",
  },
};

export function FunnelFeature({
  funnel,
  layout,
}: {
  funnel: Exclude<Funnel, null>;
  layout: LayoutMode;
}) {
  const cfg = CONFIGS[funnel];
  const [query, setQuery] = useState("");
  const isFull = layout === "full";

  return (
    <section
      id={funnel}
      data-funnel={funnel}
      className="px-5 md:px-10 relative scroll-mt-20"
      style={{
        paddingTop: isFull
          ? "clamp(48px, 6vw, 80px)"
          : "clamp(32px, 4vw, 48px)",
        paddingBottom: isFull
          ? "clamp(48px, 6vw, 80px)"
          : "clamp(32px, 4vw, 48px)",
        background: "var(--surface-base)",
      }}
    >
      <div
        className="funnel-grid rounded-[28px] grid relative"
        style={{
          minHeight: isFull ? 520 : 280,
        }}
      >
        {/* Left — editorial image bounded to its own column rectangle */}
        <div
          className="funnel-image relative rounded-[24px] overflow-hidden"
          style={{
            background: "color-mix(in srgb, var(--surface-base) 92%, #000)",
            border:
              "1px solid color-mix(in srgb, var(--accent-funnel) 18%, transparent)",
            boxShadow:
              "0 12px 40px color-mix(in srgb, var(--accent-funnel) 14%, transparent)",
          }}
        >
          <Image
            src={cfg.bgImage}
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, 50vw"
            quality={78}
            className="pointer-events-none"
            style={{
              objectFit: cfg.bgFit ?? "cover",
              objectPosition: cfg.bgPosition ?? "center",
            }}
            aria-hidden="true"
          />
          {/* Subtle funnel-tint wash over image for cohesion */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "linear-gradient(180deg, transparent 0%, transparent 60%, color-mix(in srgb, var(--accent-funnel) 18%, transparent) 100%)",
            }}
            aria-hidden="true"
          />
        </div>

        {/* Right — liquid-glass narrative card, saturated funnel tint */}
        <div
          className="flex flex-col justify-center relative rounded-[24px] overflow-hidden"
          style={{
            padding: isFull ? "48px 48px" : "32px 36px",
            background:
              "linear-gradient(135deg, color-mix(in srgb, var(--accent-funnel) 55%, transparent) 0%, color-mix(in srgb, var(--accent-funnel) 28%, transparent) 55%, color-mix(in srgb, var(--accent-funnel) 18%, transparent) 100%)",
            border:
              "1px solid color-mix(in srgb, var(--accent-funnel) 55%, transparent)",
            backdropFilter: "blur(28px) saturate(180%)",
            WebkitBackdropFilter: "blur(28px) saturate(180%)",
            boxShadow:
              "inset 0 1px 0 rgba(255,255,255,0.12), inset 0 0 80px color-mix(in srgb, var(--accent-funnel) 20%, transparent), 0 16px 56px color-mix(in srgb, var(--accent-funnel) 35%, transparent)",
          }}
        >
          {/* Inner glass highlight sheen */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "radial-gradient(ellipse 60% 40% at 30% 0%, rgba(255,255,255,0.10) 0%, transparent 70%)",
            }}
            aria-hidden="true"
          />
          <div className="relative z-10">
            <div
              className="inline-flex items-center gap-2 self-start rounded-full px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] mb-5"
              style={{
                color: "var(--accent-funnel-text)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel) 50%, transparent)",
                background:
                  "color-mix(in srgb, var(--accent-funnel) 14%, transparent)",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: "var(--accent-funnel)",
                  boxShadow: "0 0 8px var(--accent-funnel)",
                }}
              />
              {cfg.status === "Live" ? <Sparkles size={10} /> : null}
              {cfg.badge}
            </div>

            <h2
              className="font-black leading-[0.95] tracking-tight mb-3"
              style={{
                color: "var(--text-primary)",
                fontSize: isFull
                  ? "clamp(40px, 4vw, 60px)"
                  : "clamp(28px, 2.6vw, 38px)",
              }}
            >
              {cfg.title}
            </h2>

            <p
              className="font-bold mb-4"
              style={{
                color: "var(--accent-funnel-text)",
                fontSize: isFull ? 20 : 15,
              }}
            >
              {cfg.subtitle}
            </p>

            <p
              className="leading-relaxed mb-6"
              style={{
                color: "var(--text-secondary)",
                fontSize: isFull ? 15 : 13,
                maxWidth: 520,
              }}
            >
              {cfg.description}
            </p>

            {isFull && (
              <ul className="flex flex-col gap-2.5 mb-8 list-none p-0">
                {cfg.features.map((f) => (
                  <li
                    key={f}
                    className="flex items-center gap-3 text-[14px]"
                    style={{ color: "var(--text-primary)" }}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{
                        background: "var(--accent-funnel)",
                        boxShadow: "0 0 6px var(--accent-funnel)",
                      }}
                    />
                    {f}
                  </li>
                ))}
              </ul>
            )}

            <div className="flex items-center gap-4 flex-wrap">
              <a
                href={FUNNEL_HREF[funnel]}
                target={
                  FUNNEL_HREF[funnel].startsWith("http") ? "_blank" : undefined
                }
                rel={
                  FUNNEL_HREF[funnel].startsWith("http")
                    ? "noopener noreferrer"
                    : undefined
                }
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold transition-transform hover:-translate-y-0.5"
                style={{
                  background: "var(--accent-funnel)",
                  color: "var(--text-on-accent)",
                  fontSize: isFull ? 14 : 12,
                  boxShadow:
                    "0 8px 32px color-mix(in srgb, var(--accent-funnel) 40%, transparent)",
                  textDecoration: "none",
                }}
              >
                {cfg.cta}
                <ArrowRight size={14} strokeWidth={2} />
              </a>

              {/* Pricing pointer — avoids fixed-price commitment on home.
                Full pricing lives on the dedicated service detail page.
                Fix 2026-04-22: was FUNNEL_HREF (landing page) → bait-and-
                switch. Now FUNNEL_PRICING_HREF (real pricing page). */}
              <a
                href={FUNNEL_PRICING_HREF[funnel]}
                className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 transition-all hover:-translate-y-0.5"
                style={{
                  background:
                    "color-mix(in srgb, var(--accent-funnel) 8%, transparent)",
                  border:
                    "1px solid color-mix(in srgb, var(--accent-funnel) 25%, transparent)",
                  color: "var(--accent-funnel-text)",
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                <span
                  className="text-[10px] font-semibold uppercase tracking-[0.12em]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {cfg.priceLabel}
                </span>
                <span>·</span>
                See transparent pricing
                <ArrowRight size={12} strokeWidth={2} />
              </a>
            </div>

            {/* Search input + chips — merged into glass card (hidden in full homepage layout) */}
            {!isFull && (
              <div
                className="relative rounded-2xl overflow-hidden mt-8 mb-4"
                style={{
                  background: "color-mix(in srgb, #000 35%, transparent)",
                  border:
                    "1px solid color-mix(in srgb, var(--accent-funnel) 32%, transparent)",
                  backdropFilter: "blur(20px)",
                  WebkitBackdropFilter: "blur(20px)",
                  boxShadow:
                    "inset 0 1px 0 rgba(255,255,255,0.08), 0 0 30px color-mix(in srgb, var(--accent-funnel) 15%, transparent)",
                }}
              >
                <div className="flex items-center gap-3 px-4 py-3">
                  <Search
                    size={14}
                    strokeWidth={2}
                    style={{ color: "var(--accent-funnel-text)" }}
                  />
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={cfg.searchPlaceholder}
                    className="flex-1 bg-transparent outline-none"
                    style={{
                      color: "var(--text-primary)",
                      fontSize: 12,
                    }}
                  />
                  <kbd
                    className="hidden md:inline-flex items-center px-2 py-0.5 text-[10px] font-mono rounded"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      color: "var(--text-tertiary)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    ⌘K
                  </kbd>
                </div>
              </div>
            )}

            {!isFull && (
              <div className="flex flex-wrap gap-1.5">
                {cfg.searchSuggestions.slice(0, 4).map((sug) => (
                  <button
                    key={sug}
                    onClick={() => setQuery(sug)}
                    className="px-2.5 py-1 rounded-full text-[11px] font-medium transition-all"
                    style={{
                      background:
                        "color-mix(in srgb, var(--accent-funnel) 10%, transparent)",
                      border:
                        "1px solid color-mix(in srgb, var(--accent-funnel) 28%, transparent)",
                      color: "var(--accent-funnel-text)",
                    }}
                  >
                    {sug}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
