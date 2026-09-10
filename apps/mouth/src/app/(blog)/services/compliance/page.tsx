import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, Phone } from "lucide-react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { getExactPricingSnapshotEntries } from "@/lib/pricing-snapshot";
import { RUMAH_VARS, RUMAH_CLASS } from "@/lib/theme/rumahVars";

// Unlisted page (2026-09-11): not in the services grid, not in the sitemap
// (sitemap.ts enumerates a fixed servicePaths array that does not include
// this route). robots stays index:false/follow:false until the owner asks
// for it to go public — the five prices below are already confirmed
// (2026-09-10), this flag is only about listing, not about price accuracy.
export const metadata: Metadata = {
  title: "Indonesia Compliance Retainer | Bali Zero",
  description:
    "One accountable Indonesian team for your PT PMA: tax filings on Coretax, quarterly LKPM, payroll and BPJS, PSE registration. Published prices, submission receipts every month.",
  robots: { index: false, follow: false },
};

const WHATSAPP_GREETING =
  "Hi Bali Zero, I would like to book a compliance obligations review.";

const WHO_THIS_IS_FOR = [
  "Foreign-owned companies (PT PMA) with 5 to 50 staff and no in-house Indonesian finance lead.",
  "Foreign platforms and apps serving Indonesian users that received, or want to avoid, a Komdigi notice.",
  "Hotel and villa operators with booking engines, apps and foreign staff.",
];

const WHAT_YOU_GET = [
  "An obligations register for your entity: every filing, its legal basis, deadline, owner and status.",
  "Filings prepared by our team, approved by your director, submitted, receipt archived.",
  "Payroll compliance checks for local and foreign staff, including BPJS enrolment for expats employed six months or more and the PPh 21 versus PPh 26 residency review.",
  "Quarterly LKPM prepared from your figures and submitted on OSS-RBA.",
  "A headquarters-ready compliance report: what was due, what was filed, evidence attached.",
];

const HOW_IT_WORKS = [
  {
    n: "01",
    title: "Book the call",
    body: "Twenty-minute call, we send a redacted obligations list for your entity type.",
  },
  {
    n: "02",
    title: "Takeover",
    body: "We review your records and deliver the register and the gap list within ten working days.",
  },
  {
    n: "03",
    title: "Retainer",
    body: "Monthly document cutoff, preparation, your approval, submission, receipt.",
  },
];

const WHY_NOW = [
  "Komdigi blocked eBay and KLM in Indonesia in June 2025 for missing PSE registration, and in June 2026 warned 25 operators including airlines and hotel groups.",
  "Coretax made 2026 corporate filing harder, not easier: the deadline was extended after thousands of complaints.",
  "PP 28/2025 introduced fines tied to LKPM non-compliance.",
];

const FAQS = [
  {
    question: "Do you sign filings for us?",
    answer:
      "No. Your director approves and signs with the company's own digital certificate; we prepare, check and submit under your authorisation.",
  },
  {
    question: "Do we need PSE registration if we have no Indonesian office?",
    answer:
      "Yes, if your website, app or platform is used by people in Indonesia. Registration applies to private operators regardless of where the entity is incorporated.",
  },
  {
    question: "Can you get us appointed as a PMSE VAT collector?",
    answer:
      "No one can. DJP appoints. We assess your threshold exposure and prepare the readiness pack.",
  },
];

export default function ComplianceRetainerPage() {
  const packages = getExactPricingSnapshotEntries("compliance_retainers");

  return (
    <div
      className={`min-h-screen ${RUMAH_CLASS}`}
      style={{
        ...RUMAH_VARS,
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      {/* Hero */}
      <section
        style={{
          padding: "clamp(64px, 8vw, 120px) clamp(24px, 4vw, 40px) 40px",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.28em] mb-5"
            style={{
              color: "var(--rp-accent, var(--accent-funnel-text, #5c8aff))",
            }}
          >
            Compliance retainer
          </div>
          <h1
            className="font-extrabold tracking-tight mb-5"
            style={{
              fontSize: "clamp(30px, 4.5vw, 52px)",
              lineHeight: 1.08,
              color: "var(--text-primary)",
              maxWidth: "20ch",
            }}
          >
            Indonesia compliance, owned end to end.
          </h1>
          <p
            className="text-[16px] leading-[1.6] mb-8"
            style={{ color: "var(--text-secondary)", maxWidth: "68ch" }}
          >
            One accountable Indonesian team for your PT PMA: tax filings on
            Coretax, quarterly LKPM, payroll and BPJS for local and foreign
            staff, PSE registration. Published prices. Submission receipts every
            month.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={buildWhatsAppLink("home", WHATSAPP_GREETING)}
              target="_blank"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold"
              style={{
                background: "var(--accent-funnel, #3a6dff)",
                color: "var(--text-on-accent, #fff)",
                boxShadow: "0 10px 32px rgba(0,0,0,0.25)",
              }}
            >
              <Phone size={14} strokeWidth={2.2} />
              Book a 20-minute obligations review
            </Link>
            <Link
              href="#pricing"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold"
              style={{
                background: "transparent",
                color: "var(--text-secondary)",
                border: "1px solid var(--border-default)",
              }}
            >
              See the price list
              <ArrowRight size={13} strokeWidth={2.2} />
            </Link>
          </div>
        </div>
      </section>

      {/* Who this is for */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(40px, 5vw, 64px) clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <h2
            className="font-extrabold tracking-tight mb-6"
            style={{
              fontSize: "clamp(22px, 2.2vw, 30px)",
              color: "var(--text-primary)",
            }}
          >
            Who this is for
          </h2>
          <ul className="space-y-3" style={{ listStyle: "none", padding: 0 }}>
            {WHO_THIS_IS_FOR.map((item) => (
              <li
                key={item}
                className="flex items-start gap-3 text-[15px] leading-[1.6]"
                style={{ color: "var(--text-secondary)" }}
              >
                <Check
                  className="mt-1 shrink-0"
                  size={16}
                  style={{ color: "var(--rp-accent, #3a6dff)" }}
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* What you get every month */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(40px, 5vw, 64px) clamp(24px, 4vw, 40px)",
          background:
            "color-mix(in srgb, var(--accent-funnel, #3a6dff) 5%, transparent)",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <h2
            className="font-extrabold tracking-tight mb-6"
            style={{
              fontSize: "clamp(22px, 2.2vw, 30px)",
              color: "var(--text-primary)",
            }}
          >
            What you get every month
          </h2>
          <ul className="space-y-3" style={{ listStyle: "none", padding: 0 }}>
            {WHAT_YOU_GET.map((item) => (
              <li
                key={item}
                className="flex items-start gap-3 text-[15px] leading-[1.6]"
                style={{ color: "var(--text-secondary)" }}
              >
                <Check
                  className="mt-1 shrink-0"
                  size={16}
                  style={{ color: "var(--rp-accent, #3a6dff)" }}
                />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Price list — every figure below comes from the PricingTool SSOT
          (apps/backend-rag/backend/data/bali_zero_official_prices_2026.json,
          category compliance_retainers) via the generated, parity-tested
          snapshot. Never a literal here — a missing/malformed row abstains
          by not rendering, it never falls back to a hardcoded number. */}
      <section
        id="pricing"
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(40px, 5vw, 64px) clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <h2
            className="font-extrabold tracking-tight mb-2"
            style={{
              fontSize: "clamp(22px, 2.2vw, 30px)",
              color: "var(--text-primary)",
            }}
          >
            Price list
          </h2>
          <p
            className="text-[13px] mb-8"
            style={{ color: "var(--text-tertiary)" }}
          >
            Per legal entity, excluding government fees.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {packages.map((entry) => (
              <div
                key={entry.key}
                data-testid="compliance-price-card"
                className="rounded-xl p-6"
                style={{
                  background: "var(--rp-card-bg, #ffffff)",
                  border: "1px solid var(--rp-card-border, #e3e1da)",
                  boxShadow:
                    "var(--rp-card-shadow, 0 1px 2px rgba(22,33,58,0.05))",
                }}
              >
                <h3
                  className="text-[17px] font-bold tracking-tight mb-2"
                  style={{ color: "var(--text-primary)" }}
                >
                  {entry.name}
                </h3>
                <div
                  className="text-[26px] font-extrabold tracking-tight mb-3"
                  style={{ color: "var(--text-primary)" }}
                >
                  {entry.price}
                </div>
                {entry.description_en && (
                  <p
                    className="text-[14px] leading-[1.6] mb-3"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {entry.description_en}
                  </p>
                )}
                {entry.notes && (
                  <p
                    className="text-[12px] leading-[1.5]"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {entry.notes}
                  </p>
                )}
              </div>
            ))}
          </div>

          <ul
            className="space-y-2 mt-8"
            style={{ listStyle: "none", padding: 0 }}
          >
            {[
              "Prices are per legal entity with clean books. Complex structures are scoped before we quote.",
              "Government fees, notary fees and penalties are always passed through at cost.",
              "We are a licensed consulting company. Tax representation before DJP and legal opinions are delivered through our licensed tax consultant and advocate partners, named in the engagement letter.",
            ].map((note) => (
              <li
                key={note}
                className="text-[13px] leading-[1.6]"
                style={{ color: "var(--text-tertiary)" }}
              >
                {note}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* How it works */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(40px, 5vw, 64px) clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <h2
            className="font-extrabold tracking-tight mb-6"
            style={{
              fontSize: "clamp(22px, 2.2vw, 30px)",
              color: "var(--text-primary)",
            }}
          >
            How it works
          </h2>
          <ol
            className="grid gap-4"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              listStyle: "none",
              padding: 0,
              margin: 0,
            }}
          >
            {HOW_IT_WORKS.map(({ n, title, body }) => (
              <li
                key={n}
                className="rounded-2xl p-5"
                style={{
                  background:
                    "color-mix(in srgb, var(--accent-funnel, #3a6dff) 6%, transparent)",
                  border:
                    "1px solid color-mix(in srgb, var(--accent-funnel, #3a6dff) 22%, transparent)",
                }}
              >
                <div
                  className="text-[11px] font-bold tracking-[0.18em]"
                  style={{ color: "var(--rp-accent, #3a6dff)" }}
                >
                  {n}
                </div>
                <div
                  className="text-[16px] font-bold tracking-tight mt-1.5"
                  style={{ color: "var(--text-primary)" }}
                >
                  {title}
                </div>
                <div
                  className="text-[13px] leading-[1.55] mt-2"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {body}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Why now */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(40px, 5vw, 64px) clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <h2
            className="font-extrabold tracking-tight mb-6"
            style={{
              fontSize: "clamp(22px, 2.2vw, 30px)",
              color: "var(--text-primary)",
            }}
          >
            Why now
          </h2>
          <ul className="space-y-3" style={{ listStyle: "none", padding: 0 }}>
            {WHY_NOW.map((item) => (
              <li
                key={item}
                className="text-[15px] leading-[1.6]"
                style={{ color: "var(--text-secondary)" }}
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* FAQ */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(40px, 5vw, 64px) clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1000px] mx-auto">
          <h2
            className="font-extrabold tracking-tight mb-6"
            style={{
              fontSize: "clamp(22px, 2.2vw, 30px)",
              color: "var(--text-primary)",
            }}
          >
            Frequently asked questions
          </h2>
          <div className="space-y-3">
            {FAQS.map((faq) => (
              <details
                key={faq.question}
                className="group rounded-lg"
                style={{
                  background: "var(--rp-card-bg, #ffffff)",
                  border: "1px solid var(--rp-card-border, #e3e1da)",
                }}
              >
                <summary
                  className="flex items-center justify-between cursor-pointer p-5 font-medium"
                  style={{ color: "var(--text-primary)" }}
                >
                  {faq.question}
                </summary>
                <div
                  className="px-5 pb-5 text-[14px] leading-[1.6]"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {faq.answer}
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "clamp(48px, 6vw, 80px) clamp(24px, 4vw, 40px)",
        }}
      >
        <div className="max-w-[1000px] mx-auto flex flex-wrap items-center gap-3">
          <Link
            href={buildWhatsAppLink("home", WHATSAPP_GREETING)}
            target="_blank"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-[14px] font-semibold"
            style={{
              background: "var(--accent-funnel, #3a6dff)",
              color: "var(--text-on-accent, #fff)",
              boxShadow: "0 10px 32px rgba(0,0,0,0.25)",
            }}
          >
            <Phone size={14} strokeWidth={2.2} />
            Book a 20-minute obligations review
          </Link>
        </div>
      </section>
    </div>
  );
}
