import type { Metadata } from "next";
import Link from "next/link";
import {
  Phone,
  Mail,
  MessageCircle,
  MapPin,
  Clock,
  ArrowRight,
} from "lucide-react";
import { GoogleReviewsBlock } from "../_components/GoogleReviewsBlock";

export const metadata: Metadata = {
  title: "Contact · Bali Zero",
  description:
    "Talk to the Bali Zero team in Kerobokan. WhatsApp, email, office — every channel staffed by licensed Indonesian consultants.",
};

const CHANNELS = [
  {
    icon: MessageCircle,
    title: "WhatsApp",
    value: "+62 821 3107 363",
    href: "https://wa.me/628213107363",
    note: "Fastest response — usually under 15 minutes.",
    accent: "#22c55e",
  },
  {
    icon: Mail,
    title: "Email",
    value: "info@balizero.com",
    href: "mailto:info@balizero.com",
    note: "For documents, scans, and longer threads.",
    accent: "#3a6dff",
  },
  {
    icon: MapPin,
    title: "Office",
    value: "Kerobokan, Bali",
    href: "https://maps.app.goo.gl/whiMUTNchcDR5naz8",
    note: "By appointment — exact address shared on confirmation.",
    accent: "#f59e0b",
  },
  {
    icon: Phone,
    title: "Phone",
    value: "+62 821 3107 363",
    href: "tel:+628213107363",
    note: "English · Italian · Bahasa Indonesia.",
    accent: "#a78bfa",
  },
];

export default function ContactPage() {
  return (
    <div
      className="min-h-screen"
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      {/* Hero */}
      <section
        style={{
          padding: "clamp(64px, 8vw, 120px) clamp(24px, 4vw, 40px) 40px",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-5"
            style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
          >
            Contact · Kerobokan, Bali · WITA (UTC+8)
          </div>
          <h1
            className="font-extrabold tracking-tight mb-5"
            style={{
              fontSize: "clamp(34px, 5vw, 60px)",
              lineHeight: 1.05,
              color: "var(--text-primary)",
              maxWidth: "20ch",
            }}
          >
            Talk to a real person.
            <br />
            <span style={{ color: "var(--text-secondary)" }}>
              Usually within 15 minutes.
            </span>
          </h1>
          <p
            className="text-[16px] leading-[1.6] mb-4"
            style={{ color: "var(--text-secondary)", maxWidth: "60ch" }}
          >
            No bots in the first reply. WhatsApp is the fastest channel —
            staffed Mon-Fri 9:00-17:00 WITA, Sat 10:00-14:00. Email for
            documents. Office visits by appointment.
          </p>
        </div>
      </section>

      {/* Channels */}
      <section
        style={{
          borderBottom: "1px solid var(--border-subtle)",
          padding: "0 clamp(24px, 4vw, 40px) clamp(48px, 6vw, 80px)",
        }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            }}
          >
            {CHANNELS.map((c) => (
              <Link
                key={c.title}
                href={c.href}
                target={c.href.startsWith("http") ? "_blank" : undefined}
                className="group relative rounded-2xl p-6 transition-all hover:-translate-y-1 overflow-hidden"
                style={{
                  background: `color-mix(in srgb, ${c.accent} 8%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${c.accent} 30%, transparent)`,
                  boxShadow: `0 10px 30px color-mix(in srgb, ${c.accent} 15%, transparent)`,
                  backdropFilter: "blur(20px) saturate(160%)",
                  WebkitBackdropFilter: "blur(20px) saturate(160%)",
                }}
              >
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
                  style={{
                    background: `color-mix(in srgb, ${c.accent} 18%, transparent)`,
                    border: `1px solid color-mix(in srgb, ${c.accent} 45%, transparent)`,
                    color: c.accent,
                  }}
                >
                  <c.icon size={20} strokeWidth={2} />
                </div>
                <div
                  className="text-[11px] font-semibold uppercase tracking-[0.18em] mb-1.5"
                  style={{ color: c.accent }}
                >
                  {c.title}
                </div>
                <div
                  className="text-[18px] font-bold tracking-tight mb-2 break-words"
                  style={{ color: "var(--text-primary)" }}
                >
                  {c.value}
                </div>
                <div
                  className="text-[12.5px] leading-[1.5]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  {c.note}
                </div>
                <div
                  className="inline-flex items-center gap-1.5 text-[12px] font-semibold mt-4 opacity-80 group-hover:opacity-100 transition"
                  style={{ color: c.accent }}
                >
                  Open
                  <ArrowRight size={12} strokeWidth={2.2} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <GoogleReviewsBlock limit={6} />

      {/* Hours + useful links */}
      <section
        style={{ padding: "clamp(48px, 6vw, 80px) clamp(24px, 4vw, 40px)" }}
      >
        <div className="max-w-[1400px] mx-auto">
          <div className="grid gap-8 md:grid-cols-2">
            {/* Hours */}
            <div
              className="rounded-2xl p-6"
              style={{
                background:
                  "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 18%, transparent)",
              }}
            >
              <div
                className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] mb-4"
                style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
              >
                <Clock size={13} strokeWidth={2.2} /> Office hours · WITA
              </div>
              <ul
                className="space-y-2.5 text-[14px]"
                style={{ listStyle: "none", padding: 0, margin: 0 }}
              >
                {[
                  ["Monday — Friday", "09:00 — 17:00"],
                  ["Saturday", "10:00 — 14:00"],
                  ["Sunday", "Closed"],
                  ["Public holidays", "Closed (Nyepi, Galungan, Idul Fitri)"],
                ].map(([day, time]) => (
                  <li
                    key={day}
                    className="flex justify-between gap-4"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    <span>{day}</span>
                    <span
                      className="font-semibold"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {time}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Before you write */}
            <div
              className="rounded-2xl p-6"
              style={{
                background:
                  "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
                border:
                  "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 18%, transparent)",
              }}
            >
              <div
                className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] mb-4"
                style={{ color: "var(--accent-funnel-text, #5c8aff)" }}
              >
                Before you write
              </div>
              <p
                className="text-[14px] leading-[1.6] mb-4"
                style={{ color: "var(--text-secondary)" }}
              >
                Most questions already have an answer in our AI tools. Try one
                of these first — if the AI can't resolve it, the team steps in.
              </p>
              <ul
                className="space-y-2 text-[13.5px]"
                style={{ listStyle: "none", padding: 0, margin: 0 }}
              >
                {[
                  {
                    href: "/visa-oracle",
                    label: "Visa Oracle — KITAS, Golden Visa, Digital Nomad",
                  },
                  {
                    href: "/kbli",
                    label: "KBLI 2025 — find eligible PT PMA codes",
                  },
                  {
                    href: "/tax-calendar",
                    label: "Tax Calendar — 2026 deadlines per regency",
                  },
                  {
                    href: "/property/eligibility",
                    label: "Property Eligibility — zoning + risk for any plot",
                  },
                ].map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="inline-flex items-center gap-2 hover:underline"
                      style={{ color: "var(--text-primary)" }}
                    >
                      <ArrowRight size={12} strokeWidth={2.2} />
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
