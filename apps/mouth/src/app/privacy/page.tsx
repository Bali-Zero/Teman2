import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy — Bali Zero',
  description: 'How Bali Zero collects, processes, and protects your personal data under Indonesian law (UU PDP No. 27/2022).',
};

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bz-base, #0c0c0e)', color: 'var(--bz-text-1, #f5f5f5)' }}>
      <div className="max-w-3xl mx-auto px-6 py-16 space-y-10">
        <header>
          <h1 className="text-3xl font-bold tracking-tight">Privacy Policy</h1>
          <p className="mt-2 text-sm" style={{ color: 'var(--bz-text-2, #a0a0a0)' }}>
            Last updated: March 2026 · Effective: October 17, 2024
          </p>
        </header>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>1. Who We Are</h2>
          <p>
            Bali Zero (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) provides immigration, business registration, tax, and property
            services for foreign nationals and companies in Indonesia. Our AI assistant Zantara processes your inquiries
            across WhatsApp, Telegram, Web, Instagram, and other channels.
          </p>
          <p>
            Under the Indonesian Personal Data Protection Law (UU PDP No. 27/2022), we act as the <strong>Personal Data Controller</strong> for
            the data we collect and process.
          </p>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>2. Data We Collect</h2>

          <h3 className="font-medium mt-4">General Personal Data (Art. 4(2))</h3>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Full name, email address, phone number</li>
            <li>Nationality, date of birth, gender</li>
            <li>Address (residential and business)</li>
            <li>Passport number and expiry date</li>
            <li>Communication history (messages across all channels)</li>
          </ul>

          <h3 className="font-medium mt-4">Specific Personal Data (Art. 4(1))</h3>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Passport photograph (biometric data when processed via OCR)</li>
            <li>KTP (Indonesian ID card) scans</li>
            <li>NPWP (tax identification number) documents</li>
            <li>Financial information (salary, investment amounts for visa applications)</li>
          </ul>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>3. Legal Basis for Processing</h2>
          <ul className="list-disc ml-6 space-y-2 text-sm">
            <li><strong>Contract performance (Art. 20(b)):</strong> Processing necessary to fulfill our immigration and business services</li>
            <li><strong>Explicit consent (Art. 21):</strong> For specific personal data (passport scans, KTP, biometric processing)</li>
            <li><strong>Legal obligation (Art. 20(c)):</strong> Tax record retention as required by Indonesian tax law</li>
            <li><strong>Legitimate interest (Art. 20(f)):</strong> Pre-contractual inquiries via WhatsApp/chat</li>
          </ul>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>4. How We Use Your Data</h2>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Processing visa applications and company registrations</li>
            <li>Document verification via OCR (optical character recognition)</li>
            <li>AI-powered assistance for your inquiries</li>
            <li>Tax filing and compliance monitoring</li>
            <li>Communication about your active services</li>
            <li>Improving our service quality</li>
          </ul>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>5. Data Storage and Cross-Border Transfer</h2>
          <p>Your data is stored on servers in <strong>Singapore</strong> (Fly.io, Qdrant Cloud) and processed by:</p>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li><strong>Fly.io</strong> (Singapore) — Application hosting and PostgreSQL database</li>
            <li><strong>Qdrant Cloud</strong> (US) — Vector search database</li>
            <li><strong>Google</strong> (global) — Google Drive for document storage, Gemini for AI processing</li>
            <li><strong>Upstash</strong> (global) — Redis cache (temporary, 5-minute TTL)</li>
            <li><strong>Local processing</strong> (Bali) — Ollama AI for document OCR (no cross-border transfer)</li>
          </ul>
          <p className="text-sm mt-2">
            Cross-border transfers are protected by standard contractual clauses and data processing agreements
            with each provider, in compliance with Art. 56 of UU PDP.
          </p>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>6. Data Retention</h2>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li><strong>Active service data:</strong> Duration of our engagement + 5 years</li>
            <li><strong>Tax records:</strong> 7 years (Indonesian tax law requirement)</li>
            <li><strong>Communication history:</strong> 2 years after last interaction</li>
            <li><strong>Document scans:</strong> 5 years after visa/permit expiry</li>
            <li><strong>Cache data:</strong> 5 minutes (automatically deleted)</li>
          </ul>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>7. Your Rights (UU PDP Art. 5-12)</h2>
          <p>You have the right to:</p>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li><strong>Access:</strong> Request a copy of your personal data</li>
            <li><strong>Rectification:</strong> Correct inaccurate data</li>
            <li><strong>Erasure:</strong> Request deletion of your data (within 72 hours)</li>
            <li><strong>Portability:</strong> Receive your data in a structured format</li>
            <li><strong>Withdraw consent:</strong> Revoke previously given consent at any time</li>
            <li><strong>Object:</strong> Object to automated decision-making</li>
          </ul>
          <p className="text-sm mt-2">
            To exercise your rights, contact our Data Protection Officer at{' '}
            <a href="mailto:privacy@balizero.com" className="underline" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>
              privacy@balizero.com
            </a>
          </p>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>8. Data Security</h2>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Encryption at rest (database-level and column-level for sensitive fields)</li>
            <li>PII detection and redaction in AI-generated responses</li>
            <li>Immutable audit logging of all data access</li>
            <li>Role-based access control (RBAC)</li>
            <li>Regular security assessments</li>
          </ul>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>9. Breach Notification</h2>
          <p className="text-sm">
            In the event of a data breach affecting your personal data, we will notify you and the relevant
            Indonesian authorities (MOCD/Lembaga PDP) within <strong>72 hours</strong> (3 x 24 hours) of discovery,
            as required by Art. 46 of UU PDP.
          </p>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>10. Contact</h2>
          <p className="text-sm">
            <strong>Data Protection Officer:</strong>{' '}
            <a href="mailto:privacy@balizero.com" className="underline" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>
              privacy@balizero.com
            </a>
          </p>
          <p className="text-sm">
            <strong>General inquiries:</strong>{' '}
            <a href="mailto:hello@balizero.com" className="underline" style={{ color: 'var(--bz-accent-warm, #d4845a)' }}>
              hello@balizero.com
            </a>
          </p>
          <p className="text-sm" style={{ color: 'var(--bz-text-2, #a0a0a0)' }}>
            Bali Zero · Bali, Indonesia · PSE Registration: [Pending]
          </p>
        </section>
      </div>
    </div>
  );
}
