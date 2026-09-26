"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import {
  AppFrame,
  AppTrustStrip,
  AppWizard,
  useFunnelApp,
  type WizardStep,
} from "@balizero/core";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import type { CaseType, Purpose } from "@/components/garuda/declineEducation";
import { ContentLangSync } from "@/i18n/ContentLangSync";
import { voaCopy, type VoaCopyKey } from "./voa-copy";
import { useVoaLocale } from "./useVoaLocale";

/**
 * GARUDA VOA — public eligibility wizard (owner decision 5, "Concept A — The
 * Stamp"). Answers become the exact `EligibilityCheckRequest` body defined
 * in `products/garuda-voa/contracts/openapi.yaml` — every field name below
 * matches the frozen contract, nothing renamed on the way to the wire.
 *
 * Constraint 5a ("the public funnel is ENGLISH. All of it.") is still what
 * this surface SERVES: `VOA_LOCALE_RULING` ships as `english-by-default`, so
 * every visitor who does not type `?lang=id` — including one whose site
 * language preference is Bahasa — reads English. The copy moved to
 * `voa-copy.ts` in BOTH languages because the 2026-09-19 mandate's accent (6)
 * asks for EN/ID parity and the two owner statements collide; `voa-locale.ts`
 * holds the collision in one variable and explains the resolution. Nothing on
 * the wire changes with the language: the public API emits reason CODES.
 */

const CASE_TYPES: {
  id: CaseType;
  labelKey: VoaCopyKey;
  hintKey: VoaCopyKey;
}[] = [
  {
    id: "issuance",
    labelKey: "case.issuance.label",
    hintKey: "case.issuance.hint",
  },
  {
    id: "extension",
    labelKey: "case.extension.label",
    hintKey: "case.extension.hint",
  },
];

const PURPOSES: { id: Purpose; labelKey: VoaCopyKey }[] = [
  { id: "tourism", labelKey: "purpose.tourism" },
  { id: "family", labelKey: "purpose.family" },
  { id: "transit", labelKey: "purpose.transit" },
  { id: "business-meeting", labelKey: "purpose.business-meeting" },
];

const NATIONALITIES: { iso: string; labelKey: VoaCopyKey }[] = [
  { iso: "USA", labelKey: "nationality.USA" },
  { iso: "GBR", labelKey: "nationality.GBR" },
  { iso: "ITA", labelKey: "nationality.ITA" },
  { iso: "DEU", labelKey: "nationality.DEU" },
  { iso: "FRA", labelKey: "nationality.FRA" },
  { iso: "AUS", labelKey: "nationality.AUS" },
  { iso: "CAN", labelKey: "nationality.CAN" },
  { iso: "NLD", labelKey: "nationality.NLD" },
  { iso: "SGP", labelKey: "nationality.SGP" },
  { iso: "OTHER", labelKey: "nationality.OTHER" },
];

const labelStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: "var(--font-serif, Georgia, serif)",
  fontSize: "clamp(1.1rem, 2.6vw, 1.3rem)",
};

/**
 * MEASURED ON PRODUCTION, and the number is why this is `--tx-tertiary` and
 * not the subtle divider token it used to be. The boundary read
 * `--color-border-subtle` at 1.42:1 against the field's own fill, under SC
 * 1.4.11's 3:1 for the boundary of a user-interface component — and the fill
 * itself (`--surface-raised`) is only 1.09:1 against the page ground, so the
 * 1px rule was the ONLY thing making these look like fields at all. It now
 * measures 4.18:1. The same swap, for the same reason, cured the verdict
 * screen's entry field (PR 6912).
 */
const fieldStyle: React.CSSProperties = {
  padding: "0.6rem 0.7rem",
  borderRadius: 4,
  border: "1px solid var(--tx-tertiary)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
  fontSize: "1rem",
  fontFamily: "inherit",
  minHeight: 44,
};

const cardButtonStyle = (selected: boolean): React.CSSProperties => ({
  padding: "var(--space-3, 0.85rem)",
  borderRadius: 4,
  border: selected
    ? "2px solid var(--accent-funnel)"
    : "1px solid var(--color-border-subtle)",
  background: selected ? "var(--surface-raised)" : "transparent",
  textAlign: "left",
  cursor: "pointer",
  color: "var(--text-primary)",
  minHeight: 44,
  fontSize: "1rem",
  fontFamily: "inherit",
});

interface WizardAnswers {
  case_type?: CaseType;
  purpose?: Purpose;
  nationality?: string;
  travellers?: number;
  self_pay?: boolean;
  entry_date?: string;
  passport_expiry_date?: string;
  voa_expiry_date?: string;
  extension_already_used?: boolean;
  retention_notice_acknowledged?: boolean;
}

export default function VoaEligibilityPage() {
  const router = useRouter();
  const locale = useVoaLocale();
  const t = voaCopy(locale);
  const tracker = useFunnelApp("visa_voa");
  const [submitError, setSubmitError] = useState<React.ReactNode>(null);
  const [submitting, setSubmitting] = useState(false);
  // Synchronous twin of `submitting`: a second tap can land before React has
  // re-rendered the disabled button, and every attempt mints its own
  // Idempotency-Key, so a duplicate POST would create a second result row.
  const inFlight = useRef(false);
  // AppWizard's per-step render only sees that step's own value, never the
  // whole answer set — but the "dates" step needs to know case_type (extension
  // asks two extra contract-required fields the issuance case must NOT send).
  // Mirrored here as the wizard's own step 1 answer is set.
  const [caseType, setCaseType] = useState<CaseType | undefined>();

  const steps: WizardStep[] = [
    {
      id: "case_type",
      title: t("step.case.title"),
      summary: (v) => {
        const picked = CASE_TYPES.find((c) => c.id === v);
        return picked ? t(picked.labelKey) : "?";
      },
      render: ({ value, setValue }) => (
        <div>
          <p style={labelStyle}>{t("step.case.question")}</p>
          <div
            style={{
              display: "grid",
              gap: "var(--space-2, 0.5rem)",
              marginTop: "var(--space-3, 1rem)",
            }}
          >
            {CASE_TYPES.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  setValue(c.id);
                  setCaseType(c.id);
                }}
                style={cardButtonStyle(value === c.id)}
              >
                <div>{t(c.labelKey)}</div>
                <div
                  style={{
                    fontSize: "var(--text-sm, 0.85rem)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {t(c.hintKey)}
                </div>
              </button>
            ))}
          </div>
        </div>
      ),
      validate: (v) => (v ? null : t("validate.pickOne")),
    },
    {
      id: "purpose",
      title: t("step.purpose.title"),
      summary: (v) => {
        const picked = PURPOSES.find((p) => p.id === v);
        return picked ? t(picked.labelKey) : "?";
      },
      render: ({ value, setValue }) => (
        <div>
          <p style={labelStyle}>{t("step.purpose.question")}</p>
          <div
            style={{
              display: "grid",
              gap: "var(--space-2, 0.5rem)",
              marginTop: "var(--space-3, 1rem)",
            }}
          >
            {PURPOSES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setValue(p.id)}
                style={cardButtonStyle(value === p.id)}
              >
                {t(p.labelKey)}
              </button>
            ))}
          </div>
        </div>
      ),
      validate: (v) => (v ? null : t("validate.pickOne")),
    },
    {
      id: "trip",
      title: t("step.trip.title"),
      summary: (v) => {
        const trip = v as
          { nationality?: string; travellers?: number } | undefined;
        return trip?.nationality
          ? t("trip.summary", {
              nationality: trip.nationality,
              travellers: trip.travellers ?? 1,
            })
          : "?";
      },
      render: ({ value, setValue }) => {
        const v =
          (value as {
            nationality?: string;
            travellers?: number;
            self_pay?: boolean;
          }) ?? {};
        return (
          <div style={{ display: "grid", gap: "var(--space-4, 1.2rem)" }}>
            <div>
              <p style={labelStyle}>{t("trip.nationality.question")}</p>
              <select
                value={v.nationality ?? ""}
                onChange={(e) =>
                  setValue({ ...v, nationality: e.target.value })
                }
                style={{
                  ...fieldStyle,
                  marginTop: "var(--space-2, 0.5rem)",
                  width: "100%",
                  maxWidth: 320,
                }}
                aria-label={t("trip.nationality.aria")}
              >
                <option value="">{t("trip.nationality.placeholder")}</option>
                {NATIONALITIES.map((n) => (
                  <option key={n.iso} value={n.iso}>
                    {t(n.labelKey)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <p style={labelStyle}>{t("trip.travellers.question")}</p>
              <input
                type="number"
                min={1}
                inputMode="numeric"
                value={v.travellers ?? 1}
                onChange={(e) =>
                  setValue({
                    ...v,
                    travellers: Math.max(1, Number(e.target.value) || 1),
                  })
                }
                style={{
                  ...fieldStyle,
                  marginTop: "var(--space-2, 0.5rem)",
                  width: 100,
                }}
                aria-label={t("trip.travellers.aria")}
              />
            </div>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "1rem",
              }}
            >
              <input
                type="checkbox"
                checked={v.self_pay ?? true}
                onChange={(e) => setValue({ ...v, self_pay: e.target.checked })}
              />
              {t("trip.selfPay")}
            </label>
          </div>
        );
      },
      validate: (v) => {
        const trip = v as { nationality?: string } | undefined;
        return trip?.nationality ? null : t("validate.pickNationality");
      },
    },
    {
      id: "dates",
      title: t("step.dates.title"),
      summary: () => t("step.dates.summary"),
      render: ({ value, setValue }) => {
        const v =
          (value as {
            entry_date?: string;
            passport_expiry_date?: string;
            voa_expiry_date?: string;
            extension_already_used?: boolean;
            retention_notice_acknowledged?: boolean;
          }) ?? {};
        return (
          <div style={{ display: "grid", gap: "var(--space-4, 1.2rem)" }}>
            <div>
              <p style={labelStyle}>{t("dates.entry.question")}</p>
              <input
                type="date"
                value={v.entry_date ?? ""}
                onChange={(e) => setValue({ ...v, entry_date: e.target.value })}
                style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
                aria-label={t("dates.entry.aria")}
              />
            </div>
            <div>
              <p style={labelStyle}>{t("dates.passport.question")}</p>
              <input
                type="date"
                value={v.passport_expiry_date ?? ""}
                onChange={(e) =>
                  setValue({ ...v, passport_expiry_date: e.target.value })
                }
                style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
                aria-label={t("dates.passport.aria")}
              />
            </div>
            {caseType === "extension" ? (
              <>
                <div>
                  <p style={labelStyle}>{t("dates.voaExpiry.question")}</p>
                  <input
                    type="date"
                    value={v.voa_expiry_date ?? ""}
                    onChange={(e) =>
                      setValue({ ...v, voa_expiry_date: e.target.value })
                    }
                    style={{
                      ...fieldStyle,
                      marginTop: "var(--space-2, 0.5rem)",
                    }}
                    aria-label={t("dates.voaExpiry.aria")}
                  />
                </div>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    fontSize: "1rem",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={v.extension_already_used ?? false}
                    onChange={(e) =>
                      setValue({
                        ...v,
                        extension_already_used: e.target.checked,
                      })
                    }
                  />
                  {t("dates.extensionUsed")}
                </label>
              </>
            ) : null}
            <label
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "0.5rem",
                fontSize: "0.92rem",
                color: "var(--color-text-muted)",
              }}
            >
              <input
                type="checkbox"
                checked={v.retention_notice_acknowledged ?? false}
                onChange={(e) =>
                  setValue({
                    ...v,
                    retention_notice_acknowledged: e.target.checked,
                  })
                }
                aria-label={t("dates.retention.aria")}
              />
              {t("dates.retention")}
            </label>
          </div>
        );
      },
      validate: (v) => {
        const answered = v as
          | {
              entry_date?: string;
              passport_expiry_date?: string;
              voa_expiry_date?: string;
              retention_notice_acknowledged?: boolean;
            }
          | undefined;
        if (!answered?.entry_date || !answered?.passport_expiry_date)
          return t("validate.bothDates");
        if (caseType === "extension" && !answered.voa_expiry_date) {
          return t("validate.voaExpiry");
        }
        if (!answered.retention_notice_acknowledged)
          return t("validate.retention");
        return null;
      },
    },
  ];

  const onComplete = async (values: Record<string, unknown>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setSubmitError(null);
    setSubmitting(true);
    const trip =
      (values.trip as {
        nationality?: string;
        travellers?: number;
        self_pay?: boolean;
      }) ?? {};
    const dates =
      (values.dates as {
        entry_date?: string;
        passport_expiry_date?: string;
        voa_expiry_date?: string;
        extension_already_used?: boolean;
        retention_notice_acknowledged?: boolean;
      }) ?? {};
    const requestCaseType = values.case_type as CaseType;

    const body = {
      case_type: requestCaseType,
      nationality: trip.nationality,
      entry_date: dates.entry_date,
      passport_expiry_date: dates.passport_expiry_date,
      purpose: values.purpose as Purpose,
      travellers: trip.travellers ?? 1,
      self_pay: trip.self_pay ?? true,
      // Contract forbids voa_expiry_date/extension_already_used=true on issuance
      // (openapi.yaml EligibilityCheckRequest allOf) — only ever sent for extension.
      ...(requestCaseType === "extension"
        ? {
            voa_expiry_date: dates.voa_expiry_date,
            extension_already_used: dates.extension_already_used ?? false,
          }
        : { extension_already_used: false }),
      retention_notice_acknowledged:
        dates.retention_notice_acknowledged ?? false,
    };

    tracker.formSubmitted(Object.keys(body));
    // Captured OUTSIDE the catch, mirroring visa/match's W0b fix: the
    // failure event must carry the real HTTP status, never a swallowed
    // "network error" default — see funnel-app.ts's Law 2 payload note.
    let status: number | null = null;
    try {
      const res = await fetch("/api/visa/voa/eligibility-checks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key":
            globalThis.crypto?.randomUUID?.() ??
            `voa-${Date.now()}-${Math.random()}`,
        },
        body: JSON.stringify(body),
      });
      status = res.status;
      if (res.status === 201) {
        const location = res.headers.get("Location");
        const resultId = location?.split("/").pop();
        if (resultId) {
          router.push(`/visa/voa/${resultId}`);
          return;
        }
      }
      throw new Error(`unexpected status ${res.status}`);
    } catch {
      // Only a failure re-arms the button. On success the guard stays armed
      // until navigation unmounts the page: re-arming while `router.push` is
      // still resolving would re-open the very window this guard closes. A
      // retry keeps minting a fresh Idempotency-Key — a replayed key does not
      // re-issue the session cookie and would 404 the result page.
      inFlight.current = false;
      setSubmitting(false);
      tracker.formSubmitFailed("/api/visa/voa/eligibility-checks", status);
      setSubmitError(
        <>
          {t("error.eligibility.lead")}
          <a
            href={buildWhatsAppLink("visa", t("hero.wa.message"))}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--tx-pure)", textDecoration: "underline" }}
          >
            {t("error.eligibility.link")}
          </a>
          .
        </>,
      );
    }
  };

  return (
    <>
      {/*
       * The funnel KNOWS its content language, so it takes ownership of
       * `<html lang>` through the site's own protocol (i18n/content-locale.ts:
       * a page that knows wins, the provider yields) instead of inventing a
       * second writer for the same attribute. A screen reader announcing
       * Indonesian copy with an English voice is a WCAG 3.1.1/3.1.2 failure,
       * and under the ruling in force this simply re-states `en`.
       */}
      <ContentLangSync locale={locale} />
      <AppFrame
        funnel="visa"
        title={t("frame.title")}
        subtitle={t("frame.subtitle")}
        trustStrip={
          <AppTrustStrip
            items={[
              { value: "4", label: t("trust.questions.label") },
              { value: "1", label: t("trust.price.label") },
              { value: "0", label: t("trust.government.label") },
            ]}
          />
        }
      >
        {/*
         * Measured on production 2026-09-16 at 390px: the only WhatsApp
         * controls on this page were the nav link (height 0 — it lives inside
         * the collapsed hamburger) and a footer "Get Started". A visitor who
         * wants a human had nothing to tap in the first screen. This is that
         * control, and it is a WhatsAppLeadButton rather than a bare wa.me
         * anchor so the tap writes a lead_intents row first: a tourist who
         * leaves the funnel for a human is a lead saved, not a lead lost.
         */}
        <div className="voa-hero-wa">
          <p className="voa-hero-wa__line">{t("hero.wa.line")}</p>
          <WhatsAppLeadButton
            source="garuda_voa"
            className="voa-hero-wa__cta"
            fallbackHref={buildWhatsAppLink("visa", t("hero.wa.message"))}
            whatsappContext={[
              {
                label: t("lead.context.pageLabel"),
                value: t("lead.context.pageValue"),
              },
            ]}
            context={{ surface: "voa_hero" }}
          >
            {t("hero.wa.cta")}
          </WhatsAppLeadButton>
        </div>
        <AppWizard
          steps={steps}
          labels={{
            stepOf: (current, total) => t("wizard.stepOf", { current, total }),
            back: t("wizard.back"),
            next: t("wizard.next"),
            finish: t("wizard.finish"),
          }}
          persistKey="bz.garuda_voa.wizard"
          onStepChange={(step, total) => tracker.wizardStep(step + 1, total)}
          onAbandon={(step) => tracker.wizardAbandoned(step)}
          onComplete={onComplete}
          pending={submitting}
        />
        {submitting ? (
          <p style={{ color: "var(--color-text-muted)" }} role="status">
            {t("status.checking")}
          </p>
        ) : null}
        {submitError ? (
          <p
            role="alert"
            style={{
              color: "var(--tx-pure)",
              margin: 0,
              borderLeft: "3px solid var(--bz-border)",
              paddingLeft: "0.75rem",
            }}
          >
            {submitError}
          </p>
        ) : null}
      </AppFrame>
    </>
  );
}
