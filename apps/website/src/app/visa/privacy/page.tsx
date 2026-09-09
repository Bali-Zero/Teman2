import type { Metadata } from "next";

export const metadata: Metadata = {
  title: { absolute: "Privacy Policy — Bali Zero — Visa" },
  description:
    "How Bali Zero — Visa handles your data and protects your privacy.",
  robots: { index: false, follow: false },
};

function ExistingPrivacyPolicy() {
  return (
    <div style={{ color: "var(--text-primary)" }}>
      <h2 style={{ color: "var(--text-primary)" }}>
        Privacy Policy — Bali Zero — Visa
      </h2>
      <p style={{ color: "var(--text-secondary)" }}>Last updated: April 2026</p>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>1. What We Collect</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          We collect the following information when you use Bali Zero — Visa:
        </p>
        <ul style={{ color: "var(--text-secondary)" }}>
          <li>
            Nationality, purpose of stay, duration, and family situation — as
            provided through the quiz.
          </li>
          <li>Chat messages you send and AI responses you receive.</li>
          <li>
            Your IP address, stored as a SHA-256 hash, used solely for rate
            limiting.
          </li>
        </ul>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>
          2. What We Don&apos;t Collect
        </h2>
        <p style={{ color: "var(--text-secondary)" }}>
          We do not collect, and have no interest in collecting:
        </p>
        <ul style={{ color: "var(--text-secondary)" }}>
          <li>Your name</li>
          <li>Email address</li>
          <li>Passport number</li>
          <li>Phone number</li>
          <li>Photographs</li>
        </ul>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>3. How We Store It</h2>
        <ul style={{ color: "var(--text-secondary)" }}>
          <li>
            Session data is stored server-side for 90 days, then automatically
            deleted.
          </li>
          <li>IP addresses are stored exclusively as SHA-256 hashes.</li>
          <li>
            We use <code>localStorage</code> on your device only to track your
            question counter. This data is never sent to our servers.
          </li>
        </ul>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>4. Data Protection</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          We comply with Indonesian Law No. 27/2022 on Personal Data Protection
          (UU PDP). Since we collect no personally identifiable information, our
          data footprint is minimal.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>5. Third Parties</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          We use Google Gemini for AI responses. Your questions are processed by
          the AI but not stored by Google beyond the session. We send
          conversation summaries to our team via Telegram for follow-up
          purposes.
        </p>
      </section>

      <section>
        <h2 style={{ color: "var(--text-primary)" }}>6. Your Rights</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          You have the right to request information about your data, or to ask
          for its deletion. Contact us at{" "}
          <a
            href="mailto:zantara@balizero.com"

            style={{ color: "var(--text-primary)" }}
          >
            zantara@balizero.com
          </a>{" "}
          for any privacy questions.
        </p>
      </section>
    </div>
  );
}

export default function PrivacyPage() {
  return (
    <article className="visa-tool-legal">
      <p className="visa-tool-eyebrow">Bali Zero · Visa tools</p>
      <h1>Privacy for Visa tools</h1>
      <p>
        This unpublished website includes public preparation tools and links to
        the existing Visa service. The processing notes below describe these
        tools. The existing service policy is preserved separately below; its
        terms are not being rewritten by this design preview.
      </p>
      <section>
        <h2>Preparation in this browser</h2>
        <p>
          Visa on Arrival preparation stores your selected case type, purpose,
          nationality, traveller count, payment choice and relevant dates in
          this browser. The wizard ignores saved answers older than one hour.
          “Start again” clears the current answers. Preparing a review does not
          submit an eligibility check, upload a document or create an order.
        </p>
        <p>
          Second Home Studio stores its answers and checklist locally until you
          clear the plan or your browser storage. Copying a plan link places
          those answers in the link fragment. Anyone you share the link with can
          read them. Keep names, passport numbers and other identity details out
          of shared plans.
        </p>
      </section>
      <section>
        <h2>Public result requests</h2>
        <p>
          When connected, Visa Clock sends the selected visa code and entry date
          to the existing visa service. Visa Match sends nationality, purpose,
          intended duration and budget band. A result reference allows its
          holder to retrieve the saved result. Copying a result link shares that
          access.
        </p>
        <p>
          If the preview is not connected to its public service, these requests
          fail without an evaluation being sent. The website adapter does not
          forward browser authentication cookies or expose the service session
          token.
        </p>
      </section>
      <section>
        <h2>Continuing with the existing service</h2>
        <p>
          The secure Visa on Arrival check, identity verification, document
          upload, payment and order tracking remain in the existing service. Its
          own storage acknowledgement, access controls and notices apply there.
          This preparation page does not change its records or deletion process.
        </p>
        <p>
          Second Home contact links open a draft in WhatsApp with the displayed
          plan context. You choose whether to send it. The Studio does not
          automatically submit a CRM lead.
        </p>
      </section>
      <section>
        <h2>Your rights and contact</h2>
        <p>
          You can request information about your data or ask for its deletion by
          contacting{" "}
          <a href="mailto:zantara@balizero.com">zantara@balizero.com</a>.
          Clearing browser storage removes local preparation; it does not delete
          records previously submitted to the existing service.
        </p>
      </section>
      <details>
        <summary>Existing Visa service privacy policy — April 2026</summary>
        <p className="visa-tool-note">
          The following is the retained source policy for the original service.
          Its description of local storage as only a question counter does not
          describe the new preparation tools; the processing notes above cover
          those tools.
        </p>
        <ExistingPrivacyPolicy />
      </details>
    </article>
  );
}
