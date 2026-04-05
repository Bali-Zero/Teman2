import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Service — Visa Oracle',
  description:
    'Terms and conditions for using Visa Oracle, an AI-powered Indonesian visa guidance tool.',
};

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto py-8" style={{ color: 'var(--tx-primary)' }}>
      <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--bz-accent)' }}>
        Terms of Service — Visa Oracle
      </h1>
      <p className="text-sm mb-10" style={{ color: 'var(--tx-secondary)' }}>
        Last updated: April 2026
      </p>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          1. Informational Only
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          Visa Oracle provides general informational guidance about Indonesian immigration. This is
          not legal advice. Immigration regulations change frequently and information presented here
          may not reflect the most recent changes.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          2. No Guarantee
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          While we base our information on 68,000+ legal documents and current regulations, we
          cannot guarantee accuracy or completeness. Always verify with official sources or a
          licensed immigration consultant before making any decisions.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          3. Not a Law Firm
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          Bali Zero is a registered business services provider in Indonesia, not a law firm or
          licensed immigration consultancy. Our AI provides information, not professional legal
          counsel.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          4. Limitation of Liability
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          Bali Zero and its employees are not liable for any decisions made based on Visa
          Oracle&apos;s recommendations. Use the information at your own discretion and risk.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          5. Service Pricing
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          Prices shown are Bali Zero&apos;s service fees and are subject to change without notice.
          Government fees are separate and are set by Indonesian authorities. We have no control
          over government fee changes.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          6. Changes
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          We may update these terms at any time. Continued use of Visa Oracle after changes
          constitutes your acceptance of the updated terms.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          7. Contact
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          For questions about these terms, reach us at{' '}
          <a
            href="mailto:info@balizero.com"
            className="underline hover:opacity-80 transition-opacity"
            style={{ color: 'var(--bz-accent)' }}
          >
            info@balizero.com
          </a>
          . We are located in Canggu, Bali, Indonesia.
        </p>
      </section>
    </div>
  );
}
