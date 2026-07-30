import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "The terms governing Bali Zero's visa, company setup, tax, and property services in Indonesia — engagement, fees, refunds, AI disclaimer, and governing law.",
};

export default function TermsOfServicePage() {
  return (
    <div
      className="min-h-screen"
      style={{
        background: "var(--bz-base, #0c0c0e)",
        color: "var(--bz-text-1, #f5f5f5)",
      }}
    >
      <div className="max-w-3xl mx-auto px-6 py-16 space-y-10">
        <header>
          <h1 className="text-3xl font-bold tracking-tight">
            Terms of Service
          </h1>
          <p
            className="mt-2 text-sm"
            style={{ color: "var(--bz-text-2, #a0a0a0)" }}
          >
            Last updated: April 2026
          </p>
        </header>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            1. Services
          </h2>
          <p>
            Bali Zero provides visa processing, company setup (PT PMA), tax
            compliance, and property due diligence services in Indonesia. All
            services are delivered by licensed Indonesian professionals. Our AI
            assistant (Zantara) provides information and drafts; licensed staff
            review and sign all filings.
          </p>
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            2. Engagement
          </h2>
          <p>
            A service engagement begins when you confirm a scope of work and
            make payment. Timelines are estimates; Indonesian government
            processing times are outside our control. We commit to keeping you
            informed at every step via your chosen channel (WhatsApp, email,
            Telegram).
          </p>
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            3. Fees and Payments
          </h2>
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
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            4. Your Responsibilities
          </h2>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Provide accurate, complete documents and information.</li>
            <li>Respond to our requests within reasonable timeframes.</li>
            <li>
              Comply with Indonesian law — we do not assist with applications
              that violate regulations.
            </li>
          </ul>
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            5. AI Disclaimer
          </h2>
          <p>
            Zantara AI provides information based on Indonesian regulations and
            our knowledge base. AI-generated content is reviewed by licensed
            staff before any filing. AI answers are informational, not legal
            advice. For binding legal opinions, we connect you with our licensed
            notary or tax consultant.
          </p>
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            6. Limitation of Liability
          </h2>
          <p>
            Our liability is limited to the fees paid for the specific service
            in question. We are not liable for delays caused by Indonesian
            government agencies, incomplete documents from clients, or changes
            in regulation after filing.
          </p>
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            7. Governing Law
          </h2>
          <p>
            These terms are governed by the laws of the Republic of Indonesia.
            Disputes shall be resolved through the Denpasar District Court
            (Pengadilan Negeri Denpasar).
          </p>
        </section>

        <section className="space-y-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: "var(--bz-accent-warm, #d4845a)" }}
          >
            8. Contact
          </h2>
          <p className="text-sm">
            <strong>Questions about these terms:</strong>{" "}
            <a
              href="mailto:legal@balizero.com"
              className="underline"
              style={{ color: "var(--bz-accent-warm, #d4845a)" }}
            >
              legal@balizero.com
            </a>
          </p>
          <p className="text-sm">
            <strong>Privacy and personal data:</strong> see our{" "}
            <a
              href="/privacy"
              className="underline"
              style={{ color: "var(--bz-accent-warm, #d4845a)" }}
            >
              Privacy Policy
            </a>
          </p>
          <p className="text-sm" style={{ color: "var(--bz-text-2, #a0a0a0)" }}>
            Bali Zero · Bali, Indonesia
          </p>
        </section>
      </div>
    </div>
  );
}
