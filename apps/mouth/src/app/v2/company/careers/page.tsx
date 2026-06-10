import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { Footer } from "../../_components/Footer";

export const metadata: Metadata = {
  title: "Careers — Bali Zero",
  description:
    "Join the team building the infrastructure for foreigners to thrive in Bali.",
  robots: { index: false, follow: false },
};

export default function CareersPage() {
  return (
    <div
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" size={36} />}
        items={[{ label: "Home", href: "/v2" }]}
        actions={null}
      />

      <main className="max-w-3xl mx-auto px-6 md:px-10 pt-28 pb-20">
        <div
          className="text-[10px] font-semibold uppercase tracking-[0.2em] mb-4"
          style={{ color: "var(--text-tertiary)" }}
        >
          Company · Careers
        </div>

        <h1
          className="font-black tracking-tight mb-6"
          style={{ fontSize: "clamp(28px, 4vw, 44px)", lineHeight: 1.1 }}
        >
          Work at Bali Zero
        </h1>

        <p
          className="text-[17px] leading-relaxed mb-10"
          style={{ color: "var(--text-secondary)" }}
        >
          We&apos;re building the infrastructure for foreigners to thrive in
          Bali — visas, companies, tax, property. The team doing this work is
          small, expert, and on fire. We&apos;ll post open roles here when the
          time is right.
        </p>

        <div
          className="rounded-lg px-6 py-5"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <p
            className="text-[13px] leading-relaxed"
            style={{ color: "var(--text-tertiary)" }}
          >
            In the meantime — if you think you belong here, reach out directly
            via WhatsApp. Tell us what you do and why Bali Zero.
          </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
