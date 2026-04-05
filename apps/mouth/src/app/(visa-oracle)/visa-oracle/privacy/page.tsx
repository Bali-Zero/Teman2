import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy — Visa Oracle',
  description: 'How Visa Oracle handles your data and protects your privacy.',
};

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto py-8" style={{ color: 'var(--tx-primary)' }}>
      <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--bz-accent)' }}>
        Privacy Policy — Visa Oracle
      </h1>
      <p className="text-sm mb-10" style={{ color: 'var(--tx-secondary)' }}>
        Last updated: April 2026
      </p>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          1. What We Collect
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          We collect the following information when you use Visa Oracle:
        </p>
        <ul
          className="list-disc list-inside mt-2 space-y-1"
          style={{ color: 'var(--tx-secondary)' }}
        >
          <li>
            Nationality, purpose of stay, duration, and family situation — as provided through the
            quiz.
          </li>
          <li>Chat messages you send and AI responses you receive.</li>
          <li>Your IP address, stored as a SHA-256 hash, used solely for rate limiting.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          2. What We Don&apos;t Collect
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          We do not collect, and have no interest in collecting:
        </p>
        <ul
          className="list-disc list-inside mt-2 space-y-1"
          style={{ color: 'var(--tx-secondary)' }}
        >
          <li>Your name</li>
          <li>Email address</li>
          <li>Passport number</li>
          <li>Phone number</li>
          <li>Photographs</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          3. How We Store It
        </h2>
        <ul className="list-disc list-inside space-y-1" style={{ color: 'var(--tx-secondary)' }}>
          <li>Session data is stored server-side for 90 days, then automatically deleted.</li>
          <li>IP addresses are stored exclusively as SHA-256 hashes.</li>
          <li>
            We use <code>localStorage</code> on your device only to track your question counter.
            This data is never sent to our servers.
          </li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          4. Data Protection
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          We comply with Indonesian Law No. 27/2022 on Personal Data Protection (UU PDP). Since we
          collect no personally identifiable information, our data footprint is minimal.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          5. Third Parties
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          We use Google Gemini for AI responses. Your questions are processed by the AI but not
          stored by Google beyond the session. We send conversation summaries to our team via
          Telegram for follow-up purposes.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="text-xl font-semibold mb-3" style={{ color: 'var(--bz-accent)' }}>
          6. Your Rights
        </h2>
        <p style={{ color: 'var(--tx-secondary)' }}>
          You have the right to request information about your data, or to ask for its deletion.
          Contact us at{' '}
          <a
            href="mailto:info@balizero.com"
            className="underline hover:opacity-80 transition-opacity"
            style={{ color: 'var(--bz-accent)' }}
          >
            info@balizero.com
          </a>{' '}
          for any privacy questions.
        </p>
      </section>
    </div>
  );
}
