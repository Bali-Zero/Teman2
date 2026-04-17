import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { Footer } from "../_components/Footer";

export const metadata: Metadata = {
  title: "Privacy Policy",
  robots: { index: false, follow: false },
};

export default function PrivacyPage() {
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
          Privacy Policy
        </h1>

        <div className="legal-prose" style={{ color: "var(--text-secondary)" }}>
          <p
            className="text-[15px] leading-relaxed mb-6 font-medium"
            style={{ color: "var(--text-primary)" }}
          >
            Bali Zero (&ldquo;we&rdquo;, &ldquo;us&rdquo;, &ldquo;our&rdquo;)
            respects your privacy. This policy explains what data we collect,
            why, and how we handle it.
          </p>

          <Section title="1. Data we collect">
            <p>We collect only what we need to deliver our services:</p>
            <ul>
              <li>
                <strong>Contact information</strong> — name, email, phone,
                nationality — provided when you book a consultation or submit a
                form.
              </li>
              <li>
                <strong>Service data</strong> — visa type, company details, tax
                filings — provided during engagements.
              </li>
              <li>
                <strong>Usage data</strong> — pages visited, referrer, device
                type — collected via Google Analytics (anonymized IP).
              </li>
              <li>
                <strong>Chat data</strong> — messages sent to Zantara AI or
                WhatsApp — stored to improve response quality.
              </li>
            </ul>
          </Section>

          <Section title="2. How we use your data">
            <ul>
              <li>
                Deliver visa, company setup, tax, and property services you
                requested.
              </li>
              <li>
                Communicate about your case status via WhatsApp, email, or
                Telegram.
              </li>
              <li>
                Improve our AI assistant (Zantara) with anonymized conversation
                data.
              </li>
              <li>
                Comply with Indonesian regulatory requirements (immigration, tax
                filings).
              </li>
            </ul>
          </Section>

          <Section title="3. Data sharing">
            <p>We never sell your data. We share it only with:</p>
            <ul>
              <li>
                Indonesian government agencies (Imigrasi, DJP, OSS) — as
                required to process your visa, company, or tax filings.
              </li>
              <li>
                Licensed Indonesian notaries and tax consultants working on your
                case.
              </li>
              <li>
                Cloud infrastructure providers (Fly.io, Vercel, Google Cloud) —
                under strict data processing agreements.
              </li>
            </ul>
          </Section>

          <Section title="4. Data retention">
            <p>
              We retain service data for the duration of your engagement plus 5
              years (Indonesian regulatory minimum). Usage analytics are
              retained for 26 months. You can request deletion of non-regulatory
              data at any time.
            </p>
          </Section>

          <Section title="5. Your rights">
            <ul>
              <li>Access, correct, or delete your personal data.</li>
              <li>Withdraw consent for marketing communications.</li>
              <li>Request a copy of your data in a portable format.</li>
              <li>
                Lodge a complaint with the Indonesian data protection authority.
              </li>
            </ul>
            <p>
              Contact{" "}
              <a
                href="mailto:privacy@balizero.com"
                style={{ color: "var(--accent-funnel-text)" }}
              >
                privacy@balizero.com
              </a>{" "}
              for any request.
            </p>
          </Section>

          <Section title="6. Cookies">
            <p>
              We use essential cookies for authentication and preferences.
              Analytics cookies (Google Analytics) are opt-in. See our{" "}
              <a
                href="/v2/cookies"
                style={{ color: "var(--accent-funnel-text)" }}
              >
                Cookie Policy
              </a>{" "}
              for details.
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
            This policy is provided for transparency. For Indonesia-specific
            legal questions regarding data protection under PP 71/2019 and UU
            PDP, consult our legal team.
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
      <div className="text-[14px] leading-relaxed space-y-3 legal-list">
        {children}
      </div>
      <style>{`
        .legal-list ul { list-style: disc; padding-left: 1.5rem; }
        .legal-list li { margin-bottom: 0.5rem; }
      `}</style>
    </section>
  );
}
