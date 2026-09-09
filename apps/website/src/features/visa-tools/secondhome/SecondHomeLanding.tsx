"use client";

import Link from "next/link";
import { Phone } from "lucide-react";
import { useTranslation } from "./translations";
import { OFFERED_LOCALES, type Locale } from "./translations";
import { WhatsAppLeadButton } from "./support";
import { ConsentBanner } from "./support";
import { usePricingData } from "./support";

import {
  E33_LIVE_PRICE_CATEGORY,
  E33_LIVE_PRICE_KEY,
} from "./engine/pricing-key";

const PAGE_PATH = "/visa/second-home";

const fontSans =
  "var(--font-sans, ui-sans-serif, system-ui, sans-serif)" as const;
const fontSerif = "var(--font-serif, Georgia, serif)" as const;

const tabularNums: React.CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontFeatureSettings: '"tnum"',
};

const eyebrowStyle: React.CSSProperties = {
  fontFamily: fontSans,
  fontSize: "0.7rem",
  fontWeight: 600,
  letterSpacing: "0.16em",
  textTransform: "uppercase",
  color: "var(--color-text-muted)",
  margin: 0,
  lineHeight: 1.4,
};

const cardStyle: React.CSSProperties = {
  background: "var(--surface-raised)",
  border: "1px solid var(--color-border-subtle)",
  borderRadius: 12,
  padding: "var(--space-4, 1rem)",
  display: "grid",
  gap: "var(--space-2, 0.5rem)",
  alignContent: "start",
};

const bodyStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: fontSans,
  fontSize: "var(--text-base, 1rem)",
  lineHeight: 1.7,
  color: "var(--text-primary)",
};

const mutedBodyStyle: React.CSSProperties = {
  ...bodyStyle,
  fontSize: "var(--text-sm, 0.875rem)",
  lineHeight: 1.65,
  color: "var(--color-text-muted)",
};

const sectionRuleStyle: React.CSSProperties = {
  borderTop: "1px solid var(--color-border-subtle)",
  paddingTop: "var(--space-8, 2rem)",
};

const heroSectionStyle: React.CSSProperties = {
  display: "grid",
  minWidth: 0,
  gap: "var(--space-4, 1rem)",
  paddingTop: "var(--space-2, 0.5rem)",
  paddingBottom: "var(--space-6, 1.5rem)",
};

const majorSectionStyle: React.CSSProperties = {
  ...sectionRuleStyle,
  display: "grid",
  gap: "var(--space-5, 1.25rem)",
};

const minorSectionStyle: React.CSSProperties = {
  ...sectionRuleStyle,
  display: "grid",
  gap: "var(--space-4, 1rem)",
  maxWidth: "48rem",
};

const ctaSectionStyle: React.CSSProperties = {
  ...cardStyle,
  gap: "var(--space-3, 0.75rem)",
  textAlign: "center",
  justifyItems: "center",
  padding: "clamp(var(--space-5, 1.5rem), 4vw, var(--space-8, 2rem))",
};

const fitCheckCtaStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "var(--space-3, 0.85rem) var(--space-5, 1.5rem)",
  borderRadius: 12,
  border: "1px solid var(--accent-funnel)",
  color: "var(--accent-funnel-text, var(--accent-funnel))",
  fontWeight: 600,
  textDecoration: "none",
  minHeight: 44,
};

const LOCALE_ROUTE: Partial<Record<Locale, string>> = {
  en: "/visa/second-home",
  it: "/visa/second-home/it",
  id: "/visa/second-home/id",
};

const switcherItemStyle = (isActive: boolean): React.CSSProperties => ({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "4px 10px",
  borderRadius: 4,
  border: `1px solid ${isActive ? "var(--accent-funnel)" : "var(--color-border-subtle)"}`,
  background: isActive ? "var(--surface-raised)" : "transparent",
  color: "var(--text-primary)",
  fontSize: "0.75rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  textDecoration: "none",
  cursor: "pointer",
  minHeight: 32,
});

function LanguageSwitcher() {
  const { locale, setLocale } = useTranslation();
  return (
    <div
      role="group"
      aria-label="Language"
      style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}
    >
      {OFFERED_LOCALES.map((l) => {
        const isActive = locale === l;
        const href = LOCALE_ROUTE[l];
        if (href) {
          return (
            <Link
              key={l}
              href={href}
              aria-current={isActive ? "page" : undefined}
              style={switcherItemStyle(isActive)}
            >
              {l}
            </Link>
          );
        }
        return (
          <button
            key={l}
            type="button"
            onClick={() => setLocale(l)}
            aria-pressed={isActive}
            style={switcherItemStyle(isActive)}
          >
            {l}
          </button>
        );
      })}
    </div>
  );
}

export function SecondHomeLanding() {
  const { t } = useTranslation();
  const { price } = usePricingData(E33_LIVE_PRICE_KEY, E33_LIVE_PRICE_CATEGORY);

  const faqItems = [1, 2, 3, 4, 5, 6]
    .filter((n) => n !== 6 || price !== null)
    .map((n) => ({
      q: t(`secondHome.faq.q${n}`),
      a: t(`secondHome.faq.a${n}`, price ? { price } : undefined),
    }));

  return (
    <div
      data-funnel="visa"
      className="visa-secondhome-guide"
      style={{
        display: "grid",
        gap: "var(--space-6, 1.5rem)",
        background: "var(--surface-base)",
        color: "var(--text-primary)",
      }}
    >
      <LanguageSwitcher />

      <section style={heroSectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.hero.eyebrow")}</p>
        <h1
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(2.25rem, 5vw, 2.875rem)",
            fontWeight: 500,
            lineHeight: 1.05,
            color: "var(--text-primary)",
            maxWidth: "16ch",
          }}
        >
          {t("secondHome.hero.title")}
        </h1>
        <p
          style={{
            margin: 0,
            fontFamily: fontSans,
            fontSize: "clamp(1.05rem, 2.2vw, 1.3rem)",
            lineHeight: 1.6,
            color: "var(--color-text-muted)",
            maxWidth: "46rem",
            paddingTop: "var(--space-1, 0.25rem)",
          }}
        >
          {t("secondHome.hero.subtitle")}
        </p>

        <Link
          href="/visa/second-home/studio"
          data-testid="hero-fit-check-cta"
          style={{ ...fitCheckCtaStyle, justifySelf: "start" }}
        >
          {t("secondHome.cta.fitCheck")}
        </Link>
        {price ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(min(150px, 100%), 1fr))",
              gap: "var(--space-3, 0.75rem)",
              marginTop: "var(--space-4, 1rem)",
              maxWidth: "42rem",
            }}
          >
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                style={{
                  ...cardStyle,
                  padding: "var(--space-4, 1rem)",
                  gap: "var(--space-1, 0.25rem)",
                  gridTemplateColumns: "minmax(0, 1fr)",
                }}
              >
                <div
                  style={{
                    fontFamily: fontSerif,
                    fontSize: "clamp(1.5rem, 3vw, 1.6rem)",
                    fontWeight: 500,
                    lineHeight: 1.1,
                    color: "var(--accent-funnel-text, var(--accent-funnel))",
                  }}
                >
                  {t(`secondHome.hero.stat${n}v`)}
                </div>
                <div
                  style={{
                    fontFamily: fontSans,
                    fontSize: "0.7rem",
                    fontWeight: 600,
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
        ) : null}
      </section>

      <section style={majorSectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.routes.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.75rem, 4vw, 2.6rem)",
            fontWeight: 500,
            lineHeight: 1.1,
            color: "var(--text-primary)",
            maxWidth: "18ch",
          }}
        >
          {t("secondHome.routes.title")}
        </h2>
        <div
          style={{
            display: "grid",
            gap: "var(--space-4, 1rem)",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(min(280px, 100%), 1fr))",
          }}
        >
          {(["a", "b"] as const).map((route) => (
            <div key={route} style={cardStyle}>
              <div
                style={{
                  fontFamily: fontSans,
                  fontSize: "0.7rem",
                  fontWeight: 600,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: "var(--color-text-muted)",
                }}
              >
                {t(`secondHome.routes.${route}.title`)}
              </div>
              <div
                style={{
                  ...tabularNums,
                  fontFamily: fontSerif,
                  fontSize: "clamp(1.75rem, 3.6vw, 2.4rem)",
                  fontWeight: 700,
                  lineHeight: 1.1,
                  color: "var(--accent-funnel-text, var(--accent-funnel))",
                }}
              >
                {t(`secondHome.routes.${route}.amount`)}
              </div>
              <p style={bodyStyle}>{t(`secondHome.routes.${route}.body`)}</p>
              <p style={mutedBodyStyle}>
                {t(`secondHome.routes.${route}.note`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section style={minorSectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.who.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.5rem, 3vw, 1.9rem)",
            fontWeight: 500,
            lineHeight: 1.15,
            color: "var(--text-primary)",
          }}
        >
          {t("secondHome.who.title")}
        </h2>
        <div
          style={{
            display: "grid",
            gap: "var(--space-3, 0.75rem)",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(min(240px, 100%), 1fr))",
          }}
        >
          {(["base", "e33e", "e33f"] as const).map((track) => (
            <div key={track} style={cardStyle}>
              <div
                style={{
                  fontFamily: fontSans,
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                {t(`secondHome.who.${track}.title`)}
              </div>
              <p style={mutedBodyStyle}>{t(`secondHome.who.${track}.body`)}</p>
            </div>
          ))}
        </div>
        <div style={cardStyle}>
          <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
            {t("secondHome.who.family.title")}
          </div>
          <p style={mutedBodyStyle}>{t("secondHome.who.family.body")}</p>
        </div>
        <div style={cardStyle}>
          <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
            {t("secondHome.who.nowork.title")}
          </div>
          <p style={mutedBodyStyle}>{t("secondHome.who.nowork.body")}</p>
        </div>
        <p
          style={{
            ...mutedBodyStyle,
            fontSize: "0.82rem",
            fontStyle: "italic",
          }}
        >
          {t("secondHome.who.ageNote")}
        </p>
      </section>

      <section style={majorSectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.how.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.75rem, 4vw, 2.6rem)",
            fontWeight: 500,
            lineHeight: 1.1,
            color: "var(--text-primary)",
            maxWidth: "18ch",
          }}
        >
          {t("secondHome.how.title")}
        </h2>
        <div
          style={{
            display: "grid",
            gap: "var(--space-4, 1rem)",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(min(240px, 100%), 1fr))",
          }}
        >
          {[1, 2, 3].map((step) => (
            <div key={step} style={cardStyle}>
              <div
                style={{
                  fontFamily: fontSans,
                  fontSize: "0.7rem",
                  fontWeight: 600,
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
              <p style={mutedBodyStyle}>
                {t(`secondHome.how.step${step}.body`)}
              </p>
            </div>
          ))}
        </div>

        <div
          style={{
            ...cardStyle,
            border: "1px solid var(--accent-funnel)",
            textAlign: "center",
            justifyItems: "center",
            gap: "var(--space-2, 0.5rem)",
            padding: "clamp(var(--space-5, 1.5rem), 4vw, var(--space-8, 2rem))",
          }}
        >
          <div
            style={{
              fontFamily: fontSans,
              fontSize: "0.75rem",
              fontWeight: 600,
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              color: "var(--color-text-muted)",
            }}
          >
            {t("secondHome.how.priceLabel")}
          </div>
          <div
            style={{
              ...tabularNums,
              fontFamily: fontSerif,
              fontSize: "clamp(2.4rem, 6vw, 3.6rem)",
              fontWeight: 700,
              lineHeight: 1,
              color: "var(--accent-funnel-text, var(--accent-funnel))",
            }}
          >
            {price}
          </div>
          <p
            style={{
              margin: 0,
              fontFamily: fontSans,
              fontSize: "var(--text-sm, 0.875rem)",
              lineHeight: 1.5,
              color: "var(--color-text-muted)",
              maxWidth: "30rem",
            }}
          >
            {t("secondHome.how.priceNote")}
          </p>
        </div>
      </section>

      <section style={minorSectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.duty.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.5rem, 3vw, 1.9rem)",
            fontWeight: 500,
            lineHeight: 1.15,
            color: "var(--text-primary)",
            maxWidth: "20ch",
          }}
        >
          {t("secondHome.duty.title")}
        </h2>
        <p
          style={{
            ...bodyStyle,
            maxWidth: "46rem",
          }}
        >
          {t("secondHome.duty.body")}
        </p>
      </section>

      <section style={minorSectionStyle}>
        <p style={eyebrowStyle}>{t("secondHome.faq.eyebrow")}</p>
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.5rem, 3vw, 1.9rem)",
            fontWeight: 500,
            lineHeight: 1.15,
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
                  lineHeight: 1.5,
                }}
              >
                {item.q}
              </summary>
              <p
                style={{
                  margin: "var(--space-2, 0.5rem) 0 0",
                  fontSize: "var(--text-sm, 0.875rem)",
                  lineHeight: 1.65,
                  color: "var(--color-text-muted)",
                }}
              >
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </section>

      <section
        style={{
          ...ctaSectionStyle,
          border: "1px solid var(--accent-funnel)",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.5rem, 3vw, 1.9rem)",
            fontWeight: 500,
            lineHeight: 1.15,
            color: "var(--text-primary)",
          }}
        >
          Check your fit in 3 minutes
        </h2>
        <p
          style={{
            margin: 0,
            fontFamily: fontSans,
            fontSize: "var(--text-base, 1rem)",
            lineHeight: 1.6,
            color: "var(--color-text-muted)",
            maxWidth: "38rem",
          }}
        >
          Free, anonymous, no email needed. Your answers stay on your device
          until you choose to share them.
        </p>
        <Link
          href="/visa/second-home/studio"
          data-testid="footer-fit-check-cta"
          style={fitCheckCtaStyle}
        >
          {t("secondHome.cta.fitCheck")}
        </Link>
      </section>

      <section style={ctaSectionStyle}>
        <h2
          style={{
            margin: 0,
            fontFamily: fontSerif,
            fontSize: "clamp(1.75rem, 4vw, 2.6rem)",
            fontWeight: 500,
            lineHeight: 1.1,
            color: "var(--text-primary)",
            maxWidth: "18ch",
          }}
        >
          {t("secondHome.cta.title")}
        </h2>
        <p
          style={{
            margin: 0,
            fontFamily: fontSans,
            fontSize: "var(--text-base, 1rem)",
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
            borderRadius: 12,
            background: "var(--surface-raised)",
            border: "1px solid var(--border-strong)",
            color: "var(--text-primary)",
            fontWeight: 600,
            textDecoration: "none",
            minHeight: 44,
          }}
        >
          <Phone
            size={18}
            aria-hidden
            color="var(--accent-whatsapp, #25d366)"
          />
          {t("secondHome.cta.button")}
        </WhatsAppLeadButton>
      </section>

      <ConsentBanner />
    </div>
  );
}
