import type { Metadata } from "next";
import Link from "next/link";
import { Mail, MessageCircle, MapPin, Clock, ArrowRight } from "lucide-react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";

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
    href: buildWhatsAppLink("home"),
    note: "Fastest response — usually under 15 minutes.",
    accent: "#22c55e",
    fill: "solid" as const,
  },
  {
    icon: Mail,
    title: "Email",
    value: "zantara@balizero.com",
    href: "mailto:zantara@balizero.com",
    note: "For documents, scans, and longer threads.",
    accent: "#ffffff",
    fill: "light" as const,
  },
  {
    icon: MapPin,
    title: "Office",
    value: "Jalan Raya Anyar n.2, Kerobokan, Bali",
    href: "https://maps.app.goo.gl/whiMUTNchcDR5naz8",
    note: "By appointment — tap to open on Google Maps.",
    accent: "#c8102e",
    fill: "solid" as const,
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
            staffed Mon-Fri 9:00-17:00 WITA, closed Sat-Sun. Email for
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
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              maxWidth: "1100px",
              margin: "0 auto",
            }}
          >
            {CHANNELS.map((c) => {
              const solid = c.fill === "solid";
              const fg = solid ? "#ffffff" : "#0a0a0a";
              const subFg = solid
                ? "rgba(255,255,255,0.82)"
                : "rgba(0,0,0,0.65)";
              const cta = solid ? "rgba(255,255,255,0.9)" : c.accent;
              return (
                <Link
                  key={c.title}
                  href={c.href}
                  target={c.href.startsWith("http") ? "_blank" : undefined}
                  className="group relative rounded-2xl p-6 transition-all hover:-translate-y-1 overflow-hidden"
                  style={{
                    background: solid ? c.accent : "#ffffff",
                    border: solid
                      ? `1px solid ${c.accent}`
                      : "1px solid rgba(0,0,0,0.08)",
                    boxShadow: solid
                      ? `0 18px 42px color-mix(in srgb, ${c.accent} 35%, transparent)`
                      : "0 18px 42px rgba(0,0,0,0.18)",
                  }}
                >
                  <div
                    className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
                    style={{
                      background: solid
                        ? "rgba(255,255,255,0.2)"
                        : "rgba(0,0,0,0.06)",
                      border: solid
                        ? "1px solid rgba(255,255,255,0.3)"
                        : "1px solid rgba(0,0,0,0.1)",
                      color: solid ? "#ffffff" : "#0a0a0a",
                    }}
                  >
                    <c.icon size={20} strokeWidth={2} />
                  </div>
                  <div
                    className="text-[11px] font-semibold uppercase tracking-[0.18em] mb-1.5"
                    style={{ color: fg, opacity: 0.9 }}
                  >
                    {c.title}
                  </div>
                  <div
                    className="text-[18px] font-bold tracking-tight mb-2 break-words"
                    style={{ color: fg }}
                  >
                    {c.value}
                  </div>
                  <div
                    className="text-[12.5px] leading-[1.5]"
                    style={{ color: subFg }}
                  >
                    {c.note}
                  </div>
                  <div
                    className="inline-flex items-center gap-1.5 text-[12px] font-semibold mt-4 opacity-80 group-hover:opacity-100 transition"
                    style={{ color: cta }}
                  >
                    Open
                    <ArrowRight size={12} strokeWidth={2.2} />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

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
                  ["Saturday, Sunday, Public holidays", "Closed"],
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
                    href: "/visa",
                    label: "Visa Check — KITAS, Golden Visa, Digital Nomad",
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
