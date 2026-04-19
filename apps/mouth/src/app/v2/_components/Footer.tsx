import { BZLogo } from "@balizero/core/components/BZLogo";
import {
  Mail,
  Phone,
  MapPin,
  MessageCircle,
  Send,
  type LucideIcon,
} from "lucide-react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";

const SERVICES = [
  { label: "Visa & Immigration", href: "/services/visa" },
  { label: "Company Setup", href: "/services/company" },
  { label: "Tax & Compliance", href: "/services/tax" },
  { label: "Property DD", href: "/services/property" },
  { label: "Golden Visa", href: "/services/visa" },
];

const NEWS = [
  { label: "Visas", href: "/v2/news" },
  { label: "Business", href: "/v2/news" },
  { label: "Taxes", href: "/v2/news" },
  { label: "Property", href: "/v2/news" },
  { label: "Living", href: "/v2/news" },
];

const COMPANY = [
  { label: "About", href: "/v2/company/about" },
  { label: "Team", href: "/v2/company/about" },
  { label: "Careers", href: "/v2/company/about" },
  { label: "Press", href: "/v2/company/about" },
];

export function Footer() {
  return (
    <footer
      className="pt-12 md:pt-20 pb-8 px-5 md:px-10"
      style={{
        background: "var(--footer-bg)",
        borderTop: "1px solid var(--footer-border)",
      }}
    >
      <div className="max-w-[1400px] mx-auto">
        {/* Top row — 5 columns on desktop, 2-col tablet, stacks on mobile */}
        <div className="footer-grid grid mb-14">
          {/* Brand */}
          <div>
            <BZLogo variant="round" size={68} />
            <h3
              className="brand-tagline mt-5 mb-4"
              style={{ fontSize: 16, justifyContent: "flex-start" }}
            >
              Your
              <img
                className="brand-logo-3-img"
                src="/assets/logo/balizero-3-red-fixed.png?v=1"
                alt="B"
                style={{ height: "1.6em", width: "auto" }}
              />
              ali, from Zer
              <span className="brand-om-circle" />
            </h3>
            <p
              className="text-[13px] leading-relaxed max-w-xs"
              style={{ color: "var(--text-tertiary)" }}
            >
              Your trusted partner for business, immigration, and investment in
              Indonesia since 2020. Trusted by 5,000+ clients.
            </p>
          </div>

          {/* Services */}
          <FooterCol title="Services" items={SERVICES} />

          {/* News */}
          <FooterCol title="News" items={NEWS} />

          {/* Company */}
          <FooterCol title="Company" items={COMPANY} />

          {/* Contact — the one that matters */}
          <div>
            <h4
              className="text-[11px] font-bold uppercase tracking-[0.15em] mb-5"
              style={{ color: "var(--text-tertiary)" }}
            >
              Get in touch
            </h4>
            <div className="flex flex-col gap-3">
              <ContactLink
                href={buildWhatsAppLink("home")}
                Icon={MessageCircle}
                label="WhatsApp"
                value="+62 821 3107 363"
                accent="#25D366"
                external
              />
              <ContactLink
                href="https://t.me/Balizerobot"
                Icon={Send}
                label="Telegram"
                value="@Balizerobot"
                accent="#26A5E4"
                external
              />
              <ContactLink
                href="mailto:zantara@balizero.com"
                Icon={Mail}
                label="Email"
                value="zantara@balizero.com"
                accent="#f59e0b"
              />
              <ContactLink
                href="tel:+628213107363"
                Icon={Phone}
                label="Phone"
                value="+62 821 3107 363"
                accent="#a78bfa"
              />
              <ContactLink
                href="https://maps.google.com/?q=Bali+Indonesia"
                Icon={MapPin}
                label="Location"
                value="Bali, Indonesia"
                accent="#22c55e"
                external
              />
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div
          className="pt-6 flex items-center justify-between flex-wrap gap-4"
          style={{ borderTop: "1px solid var(--footer-border)" }}
        >
          <span
            className="text-[11px]"
            style={{ color: "var(--text-tertiary)" }}
          >
            © 2026 Bali Zero. All rights reserved.
          </span>
          <div className="flex items-center gap-5">
            <a
              href="/v2/privacy"
              className="text-[11px]"
              style={{ color: "var(--text-tertiary)" }}
            >
              Privacy Policy
            </a>
            <a
              href="/v2/terms"
              className="text-[11px]"
              style={{ color: "var(--text-tertiary)" }}
            >
              Terms of Service
            </a>
            <a
              href="/v2/cookies"
              className="text-[11px]"
              style={{ color: "var(--text-tertiary)" }}
            >
              Cookie Policy
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({
  title,
  items,
}: {
  title: string;
  items: { label: string; href: string }[];
}) {
  return (
    <div>
      <h4
        className="text-[11px] font-bold uppercase tracking-[0.15em] mb-5"
        style={{ color: "var(--text-tertiary)" }}
      >
        {title}
      </h4>
      <ul className="flex flex-col gap-2.5 list-none p-0 m-0">
        {items.map((it) => (
          <li key={it.label}>
            <a
              href={it.href}
              className="text-[13px] transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              {it.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ContactLink({
  href,
  Icon,
  label,
  value,
  accent,
  external,
}: {
  href: string;
  Icon: LucideIcon;
  label: string;
  value: string;
  accent: string;
  external?: boolean;
}) {
  return (
    <a
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      className="flex items-center gap-3 group"
    >
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-all"
        style={{
          background: `color-mix(in srgb, ${accent} 15%, transparent)`,
          border: `1px solid color-mix(in srgb, ${accent} 30%, transparent)`,
          color: accent,
        }}
      >
        <Icon size={15} strokeWidth={2} />
      </div>
      <div className="flex flex-col min-w-0">
        <span
          className="text-[10px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--text-tertiary)" }}
        >
          {label}
        </span>
        <span
          className="text-[12px] font-semibold truncate"
          style={{ color: "var(--text-primary)" }}
        >
          {value}
        </span>
      </div>
    </a>
  );
}
