import type { Metadata } from "next";

export const metadata: Metadata = {
  title: { absolute: "Terms of Service — Bali Zero — Visa" },
  description:
    "Terms and conditions for using Bali Zero — Visa, an AI-powered Indonesian visa guidance tool.",
  robots: { index: false, follow: false },
};

function ExistingTerms() {
  return (
    <div style={{ color: "var(--text-primary)" }}>
      <h2 style={{ color: "var(--text-primary)" }}>
        Terms of Service — Bali Zero — Visa
      </h2>
      <p style={{ color: "var(--text-secondary)" }}>Last updated: April 2026</p>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>1. Informational Only</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          Bali Zero — Visa provides general informational guidance about
          Indonesian immigration. This is not legal advice. Immigration
          regulations change frequently and information presented here may not
          reflect the most recent changes.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>2. No Guarantee</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          While we base our information on 68,000+ legal documents and current
          regulations, we cannot guarantee accuracy or completeness. Always
          verify with official sources or a licensed immigration consultant
          before making any decisions.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>
          3. Licensed Immigration Consultancy
        </h2>
        <p style={{ color: "var(--text-secondary)" }}>
          Bali Zero is a licensed immigration consultancy registered in
          Indonesia, not a law firm. While our team provides professional
          immigration services, the AI-powered Bali Zero — Visa tool offers
          general guidance only and does not constitute formal legal counsel.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>
          4. Limitation of Liability
        </h2>
        <p style={{ color: "var(--text-secondary)" }}>
          Bali Zero and its employees are not liable for any decisions made
          based on Visa Oracle&apos;s recommendations. Use the information at
          your own discretion and risk.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>5. Service Pricing</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          Prices shown are Bali Zero&apos;s service fees and are subject to
          change without notice. Government fees are separate and are set by
          Indonesian authorities. We have no control over government fee
          changes.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>6. Changes</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          We may update these terms at any time. Continued use of Bali Zero —
          Visa after changes constitutes your acceptance of the updated terms.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>7. Contact</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          For questions about these terms, reach us at{" "}
          <a
            href="mailto:zantara@balizero.com"

            style={{ color: "var(--text-primary)" }}
          >
            zantara@balizero.com
          </a>
          . We are located in Canggu, Bali, Indonesia.
        </p>
      </section>
    </div>
  );
}

export default function TermsPage() {
  return (
    <article className="visa-tool-legal">
      <p className="visa-tool-eyebrow">Bali Zero · Visa tools</p>
      <h1>Terms for Visa guidance</h1>
      <section className="visa-tool-card">
        <h2>Using this website preview</h2>
        <p>
          Preparation, route suggestions and saved timelines provide general
          information. They do not approve a visa, confirm an immigration
          status, reserve a filing date or place an order. The permit issued by
          Immigration controls the authorised stay.
        </p>
        <p>
          Visa on Arrival preparation ends with a review of your own answers.
          The secure service must run the eligibility check separately. Second
          Home Studio applies the existing fit rules and explains its reasons; a
          fit result is not an immigration decision.
        </p>
        <p>
          Prices appear only when supplied by the pricing service. Confirm the
          current amount and inclusions for the specific product before
          proceeding. The existing general pricing terms below must be read
          alongside the product quote: where a Second Home quote explicitly says
          all-inclusive, do not add a separate government fee to that quote.
        </p>
      </section>
      <ExistingTerms />
    </article>
  );
}
