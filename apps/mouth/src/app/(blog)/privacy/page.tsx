import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  // Self-canonical, not the root layout's `canonical: appUrl`. Inherited,
  // this page told Google it WAS the homepage (#5887's class of defect;
  // /privacy carries 3 internal hrefs, so it is crawled).
  alternates: {
    canonical: "https://balizero.com/privacy",
  },
  title: "Privacy Policy",
  description:
    "How Bali Zero collects, processes, and protects your personal data under Indonesian law (UU PDP No. 27/2022).",
};

export default function PrivacyPolicyPage() {
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
          Privacy Policy
        </h1>
        <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
          Last updated: September 2026 · Effective: October 17, 2024
        </p>
      </header>

      <div style={{ color: "var(--text-secondary)", maxWidth: "72ch" }}>
        <Section title="1. Who We Are" first>
          <p>
            Bali Zero (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) provides
            immigration, business registration, tax, and property services for
            foreign nationals and companies in Indonesia. Our AI assistant
            Zantara processes your inquiries across WhatsApp, Telegram, Web,
            Instagram, and other channels.
          </p>
          <p>
            Under the Indonesian Personal Data Protection Law (UU PDP No.
            27/2022), we act as the <strong>Personal Data Controller</strong>{" "}
            for the data we collect and process.
          </p>
        </Section>

        <Section title="2. Data We Collect">
          <h3
            className="font-medium mt-4"
            style={{ color: "var(--text-primary)" }}
          >
            General Personal Data (Art. 4(2))
          </h3>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Full name, email address, phone number</li>
            <li>Nationality, date of birth, gender</li>
            <li>Address (residential and business)</li>
            <li>Passport number and expiry date</li>
            <li>Communication history (messages across all channels)</li>
            <li>
              Usage data (pages visited, device and browser type, traffic
              source) collected through Google Analytics with anonymized IP,
              only after you accept analytics cookies
            </li>
          </ul>

          <h3
            className="font-medium mt-4"
            style={{ color: "var(--text-primary)" }}
          >
            Specific Personal Data (Art. 4(1))
          </h3>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Passport photograph (biometric data when processed via OCR)</li>
            <li>KTP (Indonesian ID card) scans</li>
            <li>NPWP (tax identification number) documents</li>
            <li>
              Financial information (salary, investment amounts for visa
              applications)
            </li>
          </ul>
        </Section>

        <Section title="3. Legal Basis for Processing">
          <ul className="list-disc ml-6 space-y-2 text-sm">
            <li>
              <strong>Contract performance (Art. 20(b)):</strong> Processing
              necessary to fulfill our immigration and business services
            </li>
            <li>
              <strong>Explicit consent (Art. 21):</strong> For specific personal
              data (passport scans, KTP, biometric processing)
            </li>
            <li>
              <strong>Legal obligation (Art. 20(c)):</strong> Tax record
              retention as required by Indonesian tax law
            </li>
            <li>
              <strong>Legitimate interest (Art. 20(f)):</strong> Pre-contractual
              inquiries via WhatsApp/chat
            </li>
          </ul>
        </Section>

        <Section title="4. How We Use Your Data">
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>Processing visa applications and company registrations</li>
            <li>
              Document verification via OCR (optical character recognition)
            </li>
            <li>AI-powered assistance for your inquiries</li>
            <li>Tax filing and compliance monitoring</li>
            <li>Communication about your active services</li>
            <li>Improving our service quality</li>
          </ul>
        </Section>

        <Section title="5. Data Storage and Cross-Border Transfer">
          <p>
            Your data is stored on servers in <strong>Singapore</strong>{" "}
            (Fly.io, Qdrant Cloud) and processed by:
          </p>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>
              <strong>Fly.io</strong> (Singapore) — Application hosting and
              PostgreSQL database
            </li>
            <li>
              <strong>Qdrant Cloud</strong> (US) — Vector search database
            </li>
            <li>
              <strong>Google</strong> (global) — Google Drive for document
              storage, Gemini for AI processing
            </li>
            <li>
              <strong>Upstash</strong> (global) — Redis cache (temporary,
              5-minute TTL)
            </li>
            <li>
              <strong>Vercel</strong> (global) — Hosting and delivery of the
              balizero.com website
            </li>
            <li>
              <strong>Local processing</strong> (Bali) — Ollama AI for document
              OCR (no cross-border transfer)
            </li>
          </ul>
          <p className="text-sm mt-2">
            Cross-border transfers are protected by standard contractual clauses
            and data processing agreements with each provider, in compliance
            with Art. 56 of UU PDP.
          </p>
        </Section>

        <Section title="6. Data Retention">
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>
              <strong>Active service data:</strong> Duration of our engagement +
              5 years
            </li>
            <li>
              <strong>Tax records:</strong> 7 years (Indonesian tax law
              requirement)
            </li>
            <li>
              <strong>Communication history:</strong> 2 years after last
              interaction
            </li>
            <li>
              <strong>Document scans:</strong> 5 years after visa/permit expiry
            </li>
            <li>
              <strong>Cache data:</strong> 5 minutes (automatically deleted)
            </li>
            <li>
              <strong>Usage analytics:</strong> 26 months
            </li>
          </ul>
        </Section>

        <Section title="7. Your Rights (UU PDP Art. 5-12)">
          <p>You have the right to:</p>
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>
              <strong>Access:</strong> Request a copy of your personal data
            </li>
            <li>
              <strong>Rectification:</strong> Correct inaccurate data
            </li>
            <li>
              <strong>Erasure:</strong> Request deletion of your data (within 72
              hours)
            </li>
            <li>
              <strong>Portability:</strong> Receive your data in a structured
              format
            </li>
            <li>
              <strong>Withdraw consent:</strong> Revoke previously given consent
              at any time
            </li>
            <li>
              <strong>Object:</strong> Object to automated decision-making
            </li>
            <li>
              <strong>Complaint:</strong> Lodge a complaint with the Indonesian
              personal data protection authority
            </li>
          </ul>
          <p className="text-sm mt-2">
            To exercise your rights, contact our Data Protection Officer at{" "}
            <a
              href="mailto:privacy@balizero.com"
              className="underline"
              style={{ color: "var(--r19-copper)" }}
            >
              privacy@balizero.com
            </a>
          </p>
        </Section>

        <Section title="8. Data Security">
          <ul className="list-disc ml-6 space-y-1 text-sm">
            <li>
              Encryption at rest (database-level and column-level for sensitive
              fields)
            </li>
            <li>PII detection and redaction in AI-generated responses</li>
            <li>Immutable audit logging of all data access</li>
            <li>Role-based access control (RBAC)</li>
            <li>Regular security assessments</li>
          </ul>
        </Section>

        <Section title="9. Breach Notification">
          <p className="text-sm">
            In the event of a data breach affecting your personal data, we will
            notify you and the relevant Indonesian authorities (MOCD/Lembaga
            PDP) within <strong>72 hours</strong> (3 x 24 hours) of discovery,
            as required by Art. 46 of UU PDP.
          </p>
        </Section>

        <Section title="10. Cookies">
          <p className="text-sm">
            We use essential cookies for authentication and preferences.
            Analytics cookies (Google Analytics) are opt-in. See our{" "}
            <Link
              href="/cookies"
              className="underline"
              style={{ color: "var(--r19-copper)" }}
            >
              Cookie Policy
            </Link>{" "}
            for the full list.
          </p>
        </Section>

        <Section title="11. Contact">
          <p className="text-sm">
            <strong>Data Protection Officer:</strong>{" "}
            <a
              href="mailto:privacy@balizero.com"
              className="underline"
              style={{ color: "var(--r19-copper)" }}
            >
              privacy@balizero.com
            </a>
          </p>
          <p className="text-sm">
            <strong>General inquiries:</strong>{" "}
            <a
              href="mailto:hello@balizero.com"
              className="underline"
              style={{ color: "var(--r19-copper)" }}
            >
              hello@balizero.com
            </a>
          </p>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Bali Zero · Bali, Indonesia · PSE Registration: TD-PSE
            029817.01/DJAI.PSE/09/2026 (Komdigi, registered 14 September 2026)
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
