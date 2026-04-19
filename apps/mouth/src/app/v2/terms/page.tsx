import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { Footer } from "../_components/Footer";

export const metadata: Metadata = {
  title: "Terms of Service",
  robots: { index: false, follow: false },
};

export default function TermsPage() {
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
          Legal · Last updated April 2026
        </div>

        <h1
          className="font-black tracking-tight mb-8"
          style={{ fontSize: "clamp(28px, 4vw, 44px)", lineHeight: 1.1 }}
        >
          Terms of Service
        </h1>

        <div style={{ color: "var(--text-secondary)" }}>
          <Section title="1. Services">
            <p>
              Bali Zero provides visa processing, company setup (PT PMA), tax
              compliance, and property due diligence services in Indonesia. All
              services are delivered by licensed Indonesian professionals. Our
              AI assistant (Zantara) provides information and drafts; licensed
              staff review and sign all filings.
            </p>
          </Section>

          <Section title="2. Engagement">
            <p>
              A service engagement begins when you confirm a scope of work and
              make payment. Timelines are estimates; Indonesian government
              processing times are outside our control. We commit to keeping you
              informed at every step via your chosen channel (WhatsApp, email,
              Telegram).
            </p>
          </Section>

          <Section title="3. Fees and payments">
            <ul>
              <li>
                All fees are listed on our service pages in USD. Government fees
                are passed through at cost.
              </li>
              <li>
                Payment is due before filing unless otherwise agreed in writing.
              </li>
              <li>
                Refund policy: if we cannot deliver the service due to our
                error, we refund the service fee in full. Government fees paid
                on your behalf are non-refundable.
              </li>
            </ul>
          </Section>

          <Section title="4. Your responsibilities">
            <ul>
              <li>Provide accurate, complete documents and information.</li>
              <li>Respond to our requests within reasonable timeframes.</li>
              <li>
                Comply with Indonesian law — we do not assist with applications
                that violate regulations.
              </li>
            </ul>
          </Section>

          <Section title="5. AI disclaimer">
            <p>
              Zantara AI provides information based on Indonesian regulations
              and our knowledge base. AI-generated content is reviewed by
              licensed staff before any filing. AI answers are informational,
              not legal advice. For binding legal opinions, we connect you with
              our licensed notary or tax consultant.
            </p>
          </Section>

          <Section title="6. Limitation of liability">
            <p>
              Our liability is limited to the fees paid for the specific service
              in question. We are not liable for delays caused by Indonesian
              government agencies, incomplete documents from clients, or changes
              in regulation after filing.
            </p>
          </Section>

          <Section title="7. Governing law">
            <p>
              These terms are governed by the laws of the Republic of Indonesia.
              Disputes shall be resolved through the Denpasar District Court
              (Pengadilan Negeri Denpasar).
            </p>
          </Section>

          <div
            className="mt-12 p-5 rounded-xl text-[13px]"
            style={{
              background:
                "color-mix(in srgb, var(--text-tertiary) 8%, transparent)",
              border: "1px solid var(--border-default)",
              color: "var(--text-tertiary)",
            }}
          >
            Questions about these terms? Contact{" "}
            <a
              href="mailto:legal@balizero.com"
              style={{ color: "var(--accent-funnel-text)" }}
            >
              legal@balizero.com
            </a>
            .
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2
        className="text-[18px] font-bold tracking-tight mb-3"
        style={{ color: "var(--text-primary)" }}
      >
        {title}
      </h2>
      <div
        className="text-[14px] leading-relaxed space-y-3"
        style={{ listStyleType: "disc", paddingLeft: "1.5rem" }}
      >
        {children}
      </div>
    </section>
  );
}
