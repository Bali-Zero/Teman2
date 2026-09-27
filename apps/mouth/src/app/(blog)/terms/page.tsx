import type { Metadata } from "next";

export const metadata: Metadata = {
  // Self-canonical, not the root layout's `canonical: appUrl`. Inherited,
  // this page told Google it WAS the homepage (#5887's class of defect;
  // /terms carries 2 internal hrefs, so it is crawled).
  alternates: {
    canonical: "https://balizero.com/terms",
  },
  title: "Terms of Service",
  description:
    "The terms governing Bali Zero's visa, company setup, tax, and property services in Indonesia — engagement, fees, refunds, AI disclaimer, and governing law.",
};

export default function TermsOfServicePage() {
  return (
    <div
      className="max-w-3xl mx-auto px-6 md:px-10"
      style={{
        padding:
          "clamp(56px, 7vw, 96px) clamp(24px, 4vw, 40px) clamp(48px, 6vw, 80px)",
        fontVariantLigatures: "none",
      }}
    >
      <header className="mb-10">
        <div
          className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-4"
          style={{ color: "var(--r19-copper)" }}
        >
          Legal
        </div>
        <h1
          className="font-extrabold tracking-tight mb-3"
          style={{
            fontSize: "clamp(30px, 4.5vw, 52px)",
            lineHeight: 1.08,
            color: "var(--text-primary)",
          }}
        >
          Terms of Service
        </h1>
        <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
          Last updated: April 2026
        </p>
      </header>

      <div style={{ color: "var(--text-secondary)", maxWidth: "72ch" }}>
        <Section title="1. Services" first>
          <p>
            Bali Zero provides visa processing, company setup (PT PMA), tax
            compliance, and property due diligence services in Indonesia. All
            services are delivered by licensed Indonesian professionals. Our AI
            assistant (Zantara) provides information and drafts; licensed staff
            review and sign all filings.
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

        <Section title="3. Fees and Payments">
          <ul className="list-disc ml-6 space-y-2 text-sm">
            <li>
              All fees are listed on our service pages in USD. Government fees
              are passed through at cost.
            </li>
            <li>
              Payment is due before filing unless otherwise agreed in writing.
            </li>
            <li>
              <strong>Refund policy:</strong> if we cannot deliver the service
              due to our error, we refund the service fee in full. Government
              fees paid on your behalf are non-refundable.
            </li>
          </ul>
        </Section>

        <Section title="4. Your Responsibilities">
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Provide accurate, complete documents and information.</li>
            <li>Respond to our requests within reasonable timeframes.</li>
            <li>
              Comply with Indonesian law — we do not assist with applications
              that violate regulations.
            </li>
          </ul>
        </Section>

        <Section title="5. AI Disclaimer">
          <p>
            Zantara AI provides information based on Indonesian regulations and
            our knowledge base. AI-generated content is reviewed by licensed
            staff before any filing. AI answers are informational, not legal
            advice. For binding legal opinions, we connect you with our licensed
            notary or tax consultant.
          </p>
        </Section>

        <Section title="6. Limitation of Liability">
          <p>
            Our liability is limited to the fees paid for the specific service
            in question. We are not liable for delays caused by Indonesian
            government agencies, incomplete documents from clients, or changes
            in regulation after filing.
          </p>
        </Section>

        <Section title="7. Governing Law">
          <p>
            These terms are governed by the laws of the Republic of Indonesia.
            Disputes shall be resolved through the Denpasar District Court
            (Pengadilan Negeri Denpasar).
          </p>
        </Section>

        <Section title="8. Contact">
          <p className="text-sm">
            <strong>Questions about these terms:</strong>{" "}
            <a
              href="mailto:legal@balizero.com"
              className="underline"
              style={{ color: "var(--r19-copper)" }}
            >
              legal@balizero.com
            </a>
          </p>
          <p className="text-sm">
            <strong>Privacy and personal data:</strong> see our{" "}
            <a
              href="/privacy"
              className="underline"
              style={{ color: "var(--r19-copper)" }}
            >
              Privacy Policy
            </a>
          </p>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Bali Zero · Bali, Indonesia
          </p>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  first,
  children,
}: {
  title: string;
  first?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className="space-y-4 py-8"
      style={
        first
          ? { paddingTop: 0 }
          : { borderTop: "1px solid var(--border-subtle)" }
      }
    >
      <h2
        className="text-xl font-bold tracking-tight"
        style={{ color: "var(--text-primary)" }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}
