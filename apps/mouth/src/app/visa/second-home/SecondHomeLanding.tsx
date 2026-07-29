"use client";

import { Phone } from "lucide-react";
import { useTranslation } from "@/i18n";
import { OFFERED_LOCALES } from "@/i18n/types";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import { ConsentBanner } from "@/components/visa/ConsentBanner";
import { usePricingData } from "@/hooks/usePricingData";

// PricingTool SSOT key (bali_zero_official_prices_2026.json). Matches the
// key registered in PRICING_FALLBACK (components/book/book-data.ts).
const E33_LIVE_PRICE_KEY = "E33 Second Home (5 Years)";
// Static fallback — never blank, never a stranding spinner. Kept identical
// to PRICING_FALLBACK's entry for this key so the figure never visibly
// shifts between "live" and "fallback" states.
const E33_FALLBACK_PRICE = "IDR 39,000,000";

/**
 * E33 Second Home Visa landing — Fit-Memo funnel (2026-07-24).
 *
 * Claims discipline (research/secondhome/e33-fact-registry.json + owner
 * decisions 2026-07-23):
 *  - Base E33: USD 130,000 own-name deposit at a state-owned (BUMN) bank
 *    OR USD 1,000,000 completed strata-title property. First grant up to
 *    5 years, renewable (10-year cumulative cap, Pasal 113).
 *  - Price: IDR 39,000,000 all-inclusive for the base E33 — NEVER
 *    decomposed into PNBP + service fee. Dependent add-on is DRAFT, so no
 *    dependent price appears anywhere on this page.
 *  - The fit memo is FREE; there is no "apply now" flow — the only CTA is
 *    the WhatsApp lead handoff.
 *  - FORBIDDEN until the official letters answer: BSI sharia equivalence,
 *    split deposits, ITAP/KITAP conversion, "any bank" placement. None of
 *    these appear in the copy — keep it that way.
 */

const PAGE_PATH = "/visa/second-home";

const sectionStyle: React.CSSProperties = {
  display: "grid",
  gap: "var(--space-3, 1rem)",
};

const eyebrowStyle: React.CSSProperties = {
  fontSize: "0.62rem",
  letterSpacing: "0.15em",
  textTransform: "uppercase",
  opacity: 0.5,
  color: "var(--color-text-muted)",
  margin: 0,
};

const cardStyle: React.CSSProperties = {
  background: "var(--surface-raised)",
  border: "1px solid var(--color-border-subtle)",
  borderRadius: 12,
  padding: "var(--space-4, 1.5rem)",
  display: "grid",
  gap: "var(--space-2, 0.5rem)",
  alignContent: "start",
};

function LanguageSwitcher() {
  const { locale, setLocale } = useTranslation();
  return (
    <div
      role="group"
      aria-label="Language"
      style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}
    >
      {OFFERED_LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => setLocale(l)}
          aria-pressed={locale === l}
          style={{
            padding: "4px 10px",
            borderRadius: 4,
            border: `1px solid ${locale === l ? "var(--accent-funnel)" : "var(--color-border-subtle)"}`,
            background: locale === l ? "var(--surface-raised)" : "transparent",
            color: "var(--text-primary)",
            fontSize: "0.75rem",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            cursor: "pointer",
            minHeight: 32,
          }}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export function SecondHomeLanding() {
  const { t } = useTranslation();
  const { price: livePrice } = usePricingData(E33_LIVE_PRICE_KEY);
  const price = livePrice ?? E33_FALLBACK_PRICE;

  const faqItems = [1, 2, 3, 4, 5, 6].map((n) => ({
    q: t(`secondHome.faq.q${n}`),
    a: t(`secondHome.faq.a${n}`),
  }));

  return (
    <div style={{ display: "grid", gap: "var(--space-6, 3rem)" }}>
      <LanguageSwitcher />

      {/* ── HERO ── */}
      <section
        style={{ ...sectionStyle, paddingTop: "var(--space-2, 0.5rem)" }}
      >
        <p style={eyebrowStyle}>{t("secondHome.hero.eyebrow")}</p>
        <h1
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.9rem, 5vw, 2.8rem)",
            lineHeight: 1.15,
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.hero.title")}
        </h1>
        <p
          style={{
            margin: 0,
            fontSize: "clamp(1rem, 2.4vw, 1.15rem)",
            lineHeight: 1.6,
            color: "var(--color-text-muted)",
            maxWidth: "46rem",
          }}
        >
          {t("secondHome.hero.subtitle")}
        </p>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-3, 1rem)",
            marginTop: "var(--space-2, 0.5rem)",
          }}
        >
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              style={{ ...cardStyle, padding: "var(--space-3, 1rem)" }}
            >
              <div
                style={{
                  fontFamily: "var(--font-serif, Georgia, serif)",
                  fontSize: "1.3rem",
                  color: "var(--accent-funnel-text, var(--accent-funnel))",
                }}
              >
                {t(`secondHome.hero.stat${n}v`)}
              </div>
              <div
                style={{
                  fontSize: "0.7rem",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--color-text-muted)",
                }}
              >
                {t(`secondHome.hero.stat${n}l`)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── TWO QUALIFYING ROUTES ── */}
      <section style={sectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.routes.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.4rem, 3.4vw, 1.9rem)",
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.routes.title")}
        </h2>
        <div
          style={{
            display: "grid",
            gap: "var(--space-3, 1rem)",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          }}
        >
          {(["a", "b"] as const).map((route) => (
            <div key={route} style={cardStyle}>
              <div
                style={{
                  fontSize: "0.7rem",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--color-text-muted)",
                }}
              >
                {t(`secondHome.routes.${route}.title`)}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-serif, Georgia, serif)",
                  fontSize: "1.5rem",
                  color: "var(--accent-funnel-text, var(--accent-funnel))",
                }}
              >
                {t(`secondHome.routes.${route}.amount`)}
              </div>
              <p
                style={{
                  margin: 0,
                  lineHeight: 1.6,
                  color: "var(--text-primary)",
                }}
              >
                {t(`secondHome.routes.${route}.body`)}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: "var(--text-sm, 0.88rem)",
                  lineHeight: 1.5,
                  color: "var(--color-text-muted)",
                }}
              >
                {t(`secondHome.routes.${route}.note`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── WHO IT'S FOR ── */}
      <section style={sectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.who.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.4rem, 3.4vw, 1.9rem)",
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.who.title")}
        </h2>
        <div
          style={{
            display: "grid",
            gap: "var(--space-3, 1rem)",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          }}
        >
          {(["base", "e33e", "e33f"] as const).map((track) => (
            <div key={track} style={cardStyle}>
              <div
                style={{
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                {t(`secondHome.who.${track}.title`)}
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: "var(--text-sm, 0.92rem)",
                  lineHeight: 1.6,
                  color: "var(--color-text-muted)",
                }}
              >
                {t(`secondHome.who.${track}.body`)}
              </p>
            </div>
          ))}
        </div>
        <div style={cardStyle}>
          <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
            {t("secondHome.who.family.title")}
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.92rem)",
              lineHeight: 1.6,
              color: "var(--color-text-muted)",
            }}
          >
            {t("secondHome.who.family.body")}
          </p>
        </div>
        <div style={cardStyle}>
          <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
            {t("secondHome.who.nowork.title")}
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.92rem)",
              lineHeight: 1.6,
              color: "var(--color-text-muted)",
            }}
          >
            {t("secondHome.who.nowork.body")}
          </p>
        </div>
        <p
          style={{
            margin: 0,
            fontSize: "var(--text-sm, 0.82rem)",
            lineHeight: 1.5,
            color: "var(--color-text-muted)",
            fontStyle: "italic",
          }}
        >
          {t("secondHome.who.ageNote")}
        </p>
      </section>

      {/* ── WHAT BALI ZERO DOES + PRICE ── */}
      <section style={sectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.how.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.4rem, 3.4vw, 1.9rem)",
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.how.title")}
        </h2>
        <div
          style={{
            display: "grid",
            gap: "var(--space-3, 1rem)",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          }}
        >
          {[1, 2, 3].map((step) => (
            <div key={step} style={cardStyle}>
              <div
                style={{
                  fontSize: "0.7rem",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--accent-funnel-text, var(--accent-funnel))",
                }}
              >
                {t(`secondHome.how.step${step}.label`)}
              </div>
              <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                {t(`secondHome.how.step${step}.title`)}
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: "var(--text-sm, 0.92rem)",
                  lineHeight: 1.6,
                  color: "var(--color-text-muted)",
                }}
              >
                {t(`secondHome.how.step${step}.body`)}
              </p>
            </div>
          ))}
        </div>

        {/* Price — single all-inclusive figure, never decomposed */}
        <div
          style={{
            ...cardStyle,
            border: "1px solid var(--accent-funnel)",
            textAlign: "center",
            justifyItems: "center",
            gap: "var(--space-1, 0.3rem)",
          }}
        >
          <div
            style={{
              fontSize: "0.7rem",
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
            }}
          >
            {t("secondHome.how.priceLabel")}
          </div>
          <div
            style={{
              fontFamily: "var(--font-serif, Georgia, serif)",
              fontSize: "clamp(2rem, 5vw, 2.6rem)",
              color: "var(--accent-funnel-text, var(--accent-funnel))",
            }}
          >
            {price}
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "var(--text-sm, 0.88rem)",
              color: "var(--color-text-muted)",
            }}
          >
            {t("secondHome.how.priceNote")}
          </p>
        </div>
      </section>

      {/* ── 90-DAY COMPLIANCE DUTY ── */}
      <section style={sectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.duty.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.4rem, 3.4vw, 1.9rem)",
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.duty.title")}
        </h2>
        <p
          style={{
            margin: 0,
            lineHeight: 1.7,
            color: "var(--text-primary)",
            maxWidth: "46rem",
          }}
        >
          {t("secondHome.duty.body")}
        </p>
      </section>

      {/* ── FAQ (visible; mirrors SECOND_HOME_FAQS used for JSON-LD) ── */}
      <section style={sectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.faq.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.4rem, 3.4vw, 1.9rem)",
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.faq.title")}
        </h2>
        <div style={{ display: "grid", gap: "var(--space-2, 0.5rem)" }}>
          {faqItems.map((item) => (
            <details key={item.q} style={{ ...cardStyle, gap: 0 }}>
              <summary
                style={{
                  cursor: "pointer",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                {item.q}
              </summary>
              <p
                style={{
                  margin: "var(--space-2, 0.5rem) 0 0",
                  fontSize: "var(--text-sm, 0.92rem)",
                  lineHeight: 1.6,
                  color: "var(--color-text-muted)",
                }}
              >
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </section>

      {/* ── CTA — the only action: free Fit Memo via WhatsApp handoff ── */}
      <section
        style={{
          ...cardStyle,
          gap: "var(--space-3, 1rem)",
          textAlign: "center",
          justifyItems: "center",
          padding: "var(--space-5, 2rem)",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-serif, Georgia, serif)",
            fontSize: "clamp(1.4rem, 3.4vw, 1.9rem)",
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.cta.title")}
        </h2>
        <p
          style={{
            margin: 0,
            lineHeight: 1.6,
            color: "var(--color-text-muted)",
            maxWidth: "38rem",
          }}
        >
          {t("secondHome.cta.body")}
        </p>
        <WhatsAppLeadButton
          source="cta_handoff"
          context={{
            page: PAGE_PATH,
            product: "e33_second_home",
            service_interest: "second_home",
          }}
          whatsappContext={[
            { label: "Product", value: "E33 Second Home Visa" },
            { label: "Fit memo", value: "Free assessment" },
            { label: "Page", value: PAGE_PATH },
          ]}
          utm={{ page: PAGE_PATH }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "var(--space-3, 0.85rem) var(--space-5, 1.5rem)",
            borderRadius: 8,
            background: "#25D366",
            color: "#fff",
            fontWeight: 600,
            textDecoration: "none",
            minHeight: 44,
          }}
        >
          <Phone size={18} aria-hidden />
          {t("secondHome.cta.button")}
        </WhatsAppLeadButton>
        <p
          style={{
            margin: 0,
            fontSize: "var(--text-sm, 0.82rem)",
            color: "var(--color-text-muted)",
          }}
        >
          {t("secondHome.cta.note")}
        </p>
      </section>

      <ConsentBanner />
    </div>
  );
}
