"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "@/i18n";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import {
  AppFrame,
  AppTrustStrip,
  AppWhatsAppCTA,
  AppWizard,
  useFunnelApp,
  type FunnelAppName,
  type WizardStep,
} from "@balizero/core";

type CaseType = "issuance" | "extension";

interface CaseDetailsValue {
  entry_date?: string;
  voa_expiry_date?: string;
  extension_already_used?: boolean;
}

const NATIONALITIES: { iso: string; key: string }[] = [
  { iso: "USA", key: "usa" },
  { iso: "GBR", key: "gbr" },
  { iso: "ITA", key: "ita" },
  { iso: "DEU", key: "deu" },
  { iso: "FRA", key: "fra" },
  { iso: "AUS", key: "aus" },
  { iso: "CAN", key: "can" },
  { iso: "NLD", key: "nld" },
  { iso: "SGP", key: "sgp" },
  { iso: "OTHER", key: "other" },
];

const PURPOSES: { id: string; key: string }[] = [
  { id: "tourism", key: "tourism" },
  { id: "family", key: "family" },
  { id: "transit", key: "transit" },
  { id: "business-meeting", key: "businessMeeting" },
];

const questionStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: "var(--font-serif, Georgia, serif)",
  fontSize: "clamp(1.1rem, 2.6vw, 1.3rem)",
};

const cardsGridStyle: React.CSSProperties = {
  display: "grid",
  gap: "var(--space-2, 0.5rem)",
  marginTop: "var(--space-3, 1rem)",
};

const noteStyle: React.CSSProperties = {
  margin: "var(--space-2, 0.5rem) 0 0",
  fontSize: "var(--text-sm, 0.85rem)",
  fontStyle: "italic",
  color: "var(--color-text-muted)",
};

const fieldStyle: React.CSSProperties = {
  padding: "0.45rem 0.7rem",
  borderRadius: 4,
  border: "1px solid var(--color-border-subtle)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
  fontSize: "inherit",
  fontFamily: "inherit",
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
  minHeight: "44px",
  fontSize: "inherit",
  fontFamily: "inherit",
});

const HYDRATE_TTL_MS = 60 * 60 * 1000; // must mirror AppWizard's own PERSIST_TTL_MS

/**
 * Restore `caseType` on remount from the SAME localStorage entry AppWizard
 * persists under `persistKey`. AppWizard owns {idx, values} internally and
 * exposes no "values changed" callback, so the parent has no other way to
 * learn which branch (issuance/extension) a resumed session picked before
 * the "caseDetails" step (which renders different fields per branch) comes
 * back into view. Mirrors AppWizard's exact {ts, idx, values} shape and 1h
 * TTL rather than adding a new prop to the shared wizard primitive.
 */
function hydrateCaseType(persistKey: string): CaseType | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(persistKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as {
      ts?: number;
      values?: Record<string, unknown>;
    };
    if (!parsed.ts || Date.now() - parsed.ts > HYDRATE_TTL_MS) return null;
    const v = parsed.values?.caseType;
    return v === "issuance" || v === "extension" ? v : null;
  } catch {
    return null;
  }
}

/**
 * Mirrors `hydrateCaseType` above for the same reason: on a resumed session
 * whose last answer was the "my country isn't listed" escape hatch, the
 * page needs to know that on the VERY FIRST render (before the nationality
 * step's own onChange has a chance to fire) so the step list is already
 * truncated — DEFECT 3 fix, see the escape-hatch handling at the bottom of
 * this component.
 */
function hydrateNationalityOther(persistKey: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = window.localStorage.getItem(persistKey);
    if (!raw) return false;
    const parsed = JSON.parse(raw) as {
      ts?: number;
      values?: Record<string, unknown>;
    };
    if (!parsed.ts || Date.now() - parsed.ts > HYDRATE_TTL_MS) return false;
    return parsed.values?.nationality === "OTHER";
  } catch {
    return false;
  }
}

const labelOf = (
  list: { iso?: string; id?: string; key: string }[],
  v: unknown,
) => list.find((x) => (x.iso ?? x.id) === v);

const PERSIST_KEY = "bz.garuda_voa.wizard";

export default function GarudaVoaPage() {
  const router = useRouter();
  const { t } = useTranslation();
  // FunnelAppName (packages/core/analytics/funnel-app.ts) is a closed union
  // owned by the analytics lane, not this frontend build's file list — "voa"
  // is not yet a member. Same band-aid convention documented in
  // apps/mouth/CLAUDE.md ("TypeScript Workarounds"): the cast only widens a
  // string literal, `tracker` itself stays fully typed from here on.
  const tracker = useFunnelApp("voa" as unknown as FunnelAppName);
  const [caseType, setCaseType] = useState<CaseType | null>(() =>
    hydrateCaseType(PERSIST_KEY),
  );
  const [submitError, setSubmitError] = useState<React.ReactNode>(null);
  // DEFECT 3 fix: "my country is not listed" must never reach the engine —
  // no machine verdict for that case. Tracked so the step list can end at
  // the nationality step and `onComplete` can route to a human handoff
  // instead of `POST /api/visa/voa`.
  const [nationalityOther, setNationalityOther] = useState<boolean>(() =>
    hydrateNationalityOther(PERSIST_KEY),
  );
  const [showOtherNationalityHandoff, setShowOtherNationalityHandoff] =
    useState(false);

  const allSteps: WizardStep[] = [
    {
      id: "caseType",
      title: t("garudaVoa.wizard.caseType.stepTitle"),
      summary: (v) =>
        v === "issuance"
          ? t("garudaVoa.wizard.caseType.issuance")
          : v === "extension"
            ? t("garudaVoa.wizard.caseType.extension")
            : "?",
      render: ({ value, setValue }) => (
        <div>
          <p style={questionStyle}>{t("garudaVoa.wizard.caseType.question")}</p>
          <div style={cardsGridStyle}>
            <button
              type="button"
              onClick={() => {
                setValue("issuance");
                setCaseType("issuance");
                tracker.formStarted("case_type");
              }}
              style={cardButtonStyle(value === "issuance")}
            >
              {t("garudaVoa.wizard.caseType.issuance")}
            </button>
            <button
              type="button"
              onClick={() => {
                setValue("extension");
                setCaseType("extension");
                tracker.formStarted("case_type");
              }}
              style={cardButtonStyle(value === "extension")}
            >
              {t("garudaVoa.wizard.caseType.extension")}
            </button>
          </div>
        </div>
      ),
      validate: (v) => (v ? null : t("garudaVoa.wizard.caseType.validate")),
    },
    {
      id: "caseDetails",
      title: t("garudaVoa.wizard.caseDetails.stepTitle"),
      summary: (v) => {
        const details = (v as CaseDetailsValue) ?? {};
        if (caseType === "extension") {
          return details.voa_expiry_date
            ? t("garudaVoa.wizard.caseDetails.summaryExtension", {
                date: details.voa_expiry_date,
              })
            : "?";
        }
        return details.entry_date
          ? t("garudaVoa.wizard.caseDetails.summaryIssuance", {
              date: details.entry_date,
            })
          : "?";
      },
      render: ({ value, setValue }) => {
        const details = (value as CaseDetailsValue) ?? {};
        if (caseType === "extension") {
          return (
            <div>
              <p style={questionStyle}>
                {t("garudaVoa.wizard.caseDetails.extensionQuestion")}
              </p>
              <input
                type="date"
                value={details.voa_expiry_date ?? ""}
                onChange={(e) => {
                  setValue({ ...details, voa_expiry_date: e.target.value });
                  tracker.formStarted("voa_expiry_date");
                }}
                style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
                aria-label={t("garudaVoa.wizard.caseDetails.voaExpiryLabel")}
              />
              {/* DEFECT 2 fix: entry_date is required by the backend for
                  EVERY case_type (it needs it to compute the stay window),
                  but this branch never asked for it. The visitor knows when
                  they entered — the question is answerable. */}
              <p
                style={{
                  ...questionStyle,
                  marginTop: "var(--space-4, 1.5rem)",
                }}
              >
                {t("garudaVoa.wizard.caseDetails.extensionEntryQuestion")}
              </p>
              <input
                type="date"
                value={details.entry_date ?? ""}
                onChange={(e) => {
                  setValue({ ...details, entry_date: e.target.value });
                  tracker.formStarted("entry_date");
                }}
                style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
                aria-label={t(
                  "garudaVoa.wizard.caseDetails.extensionEntryLabel",
                )}
              />
              <p
                style={{
                  ...questionStyle,
                  marginTop: "var(--space-4, 1.5rem)",
                }}
              >
                {t("garudaVoa.wizard.caseDetails.extensionUsedQuestion")}
              </p>
              <div style={cardsGridStyle}>
                <button
                  type="button"
                  onClick={() => {
                    setValue({ ...details, extension_already_used: false });
                    tracker.formStarted("extension_already_used");
                  }}
                  style={cardButtonStyle(
                    details.extension_already_used === false,
                  )}
                >
                  {t("garudaVoa.wizard.caseDetails.no")}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setValue({ ...details, extension_already_used: true });
                    tracker.formStarted("extension_already_used");
                  }}
                  style={cardButtonStyle(
                    details.extension_already_used === true,
                  )}
                >
                  {t("garudaVoa.wizard.caseDetails.yes")}
                </button>
              </div>
              <p style={noteStyle}>
                {t("garudaVoa.wizard.caseDetails.inPersonNote")}
              </p>
            </div>
          );
        }
        return (
          <div>
            <p style={questionStyle}>
              {t("garudaVoa.wizard.caseDetails.issuanceQuestion")}
            </p>
            <input
              type="date"
              value={details.entry_date ?? ""}
              onChange={(e) => {
                setValue({ ...details, entry_date: e.target.value });
                tracker.formStarted("entry_date");
              }}
              style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
              aria-label={t("garudaVoa.wizard.caseDetails.entryDateLabel")}
            />
          </div>
        );
      },
      validate: (v) => {
        const details = (v as CaseDetailsValue) ?? {};
        if (caseType === "extension") {
          if (!details.voa_expiry_date)
            return t("garudaVoa.wizard.caseDetails.validateVoaExpiry");
          if (!details.entry_date)
            return t("garudaVoa.wizard.caseDetails.validateExtensionEntry");
          if (details.extension_already_used === undefined)
            return t("garudaVoa.wizard.caseDetails.validateExtensionUsed");
          return null;
        }
        return details.entry_date
          ? null
          : t("garudaVoa.wizard.caseDetails.validateEntry");
      },
    },
    {
      id: "passportExpiry",
      title: t("garudaVoa.wizard.passportExpiry.stepTitle"),
      summary: (v) => (v ? String(v) : "?"),
      render: ({ value, setValue }) => (
        <div>
          <p style={questionStyle}>
            {t("garudaVoa.wizard.passportExpiry.question")}
          </p>
          <input
            type="date"
            value={(value as string) ?? ""}
            onChange={(e) => {
              setValue(e.target.value);
              tracker.formStarted("passport_expiry_date");
            }}
            style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
            aria-label={t("garudaVoa.wizard.passportExpiry.label")}
          />
        </div>
      ),
      validate: (v) =>
        v ? null : t("garudaVoa.wizard.passportExpiry.validate"),
    },
    {
      id: "nationality",
      title: t("garudaVoa.wizard.nationality.stepTitle"),
      summary: (v) => {
        const n = labelOf(NATIONALITIES, v);
        return n ? t(`garudaVoa.wizard.nationality.options.${n.key}`) : "?";
      },
      render: ({ value, setValue }) => (
        <div>
          <p style={questionStyle}>
            {t("garudaVoa.wizard.nationality.question")}
          </p>
          <select
            value={(value as string) ?? ""}
            onChange={(e) => {
              setValue(e.target.value);
              // DEFECT 3 fix: "my country is not listed" must never produce
              // a machine verdict. Tracked here (not just read at submit
              // time) so the step list itself ends at this step — the
              // visitor never sees purpose/travellers/payment questions
              // whose answers would be discarded anyway.
              setNationalityOther(e.target.value === "OTHER");
              tracker.formStarted("nationality");
            }}
            style={{
              marginTop: "var(--space-2, 0.5rem)",
              ...fieldStyle,
              width: "100%",
              maxWidth: 320,
            }}
            aria-label={t("garudaVoa.wizard.nationality.question")}
          >
            <option value="">
              {t("garudaVoa.wizard.nationality.placeholder")}
            </option>
            {NATIONALITIES.map((n) => (
              <option key={n.iso} value={n.iso}>
                {t(`garudaVoa.wizard.nationality.options.${n.key}`)}
              </option>
            ))}
          </select>
        </div>
      ),
      validate: (v) => (v ? null : t("garudaVoa.wizard.nationality.validate")),
    },
    {
      id: "purpose",
      title: t("garudaVoa.wizard.purpose.stepTitle"),
      summary: (v) => {
        const p = labelOf(PURPOSES, v);
        return p ? t(`garudaVoa.wizard.purpose.${p.key}`) : "?";
      },
      render: ({ value, setValue }) => (
        <div>
          <p style={questionStyle}>{t("garudaVoa.wizard.purpose.question")}</p>
          <div style={cardsGridStyle}>
            {PURPOSES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setValue(p.id);
                  tracker.formStarted("purpose");
                }}
                style={cardButtonStyle(value === p.id)}
              >
                {t(`garudaVoa.wizard.purpose.${p.key}`)}
              </button>
            ))}
          </div>
        </div>
      ),
      validate: (v) => (v ? null : t("garudaVoa.wizard.purpose.validate")),
    },
    {
      id: "travellers",
      title: t("garudaVoa.wizard.travellers.stepTitle"),
      summary: (v) => (typeof v === "number" ? String(v) : "1"),
      render: ({ value, setValue }) => {
        const num = typeof value === "number" ? value : 1;
        return (
          <div>
            <p style={questionStyle}>
              {t("garudaVoa.wizard.travellers.question", {
                count: String(num),
              })}
            </p>
            <input
              type="range"
              min={1}
              max={10}
              value={num}
              onChange={(e) => {
                setValue(Number(e.target.value));
                tracker.formStarted("travellers");
              }}
              style={{
                width: "100%",
                marginTop: "var(--space-3, 1rem)",
                accentColor: "var(--accent-funnel)",
              }}
              aria-label={t("garudaVoa.wizard.travellers.stepTitle")}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: "var(--text-sm, 0.85rem)",
                color: "var(--color-text-muted)",
              }}
            >
              <span>{t("garudaVoa.wizard.travellers.hintMin")}</span>
              <span>{t("garudaVoa.wizard.travellers.hintMax")}</span>
            </div>
          </div>
        );
      },
    },
    {
      id: "selfPay",
      title: t("garudaVoa.wizard.selfPay.stepTitle"),
      summary: (v) =>
        v === true
          ? t("garudaVoa.wizard.selfPay.yes")
          : v === false
            ? t("garudaVoa.wizard.selfPay.no")
            : "?",
      render: ({ value, setValue }) => (
        <div>
          <p style={questionStyle}>{t("garudaVoa.wizard.selfPay.question")}</p>
          <div style={cardsGridStyle}>
            <button
              type="button"
              onClick={() => {
                setValue(true);
                tracker.formStarted("self_pay");
              }}
              style={cardButtonStyle(value === true)}
            >
              {t("garudaVoa.wizard.selfPay.yes")}
            </button>
            <button
              type="button"
              onClick={() => {
                setValue(false);
                tracker.formStarted("self_pay");
              }}
              style={cardButtonStyle(value === false)}
            >
              {t("garudaVoa.wizard.selfPay.no")}
            </button>
          </div>
        </div>
      ),
      validate: (v) =>
        v === undefined ? t("garudaVoa.wizard.selfPay.validate") : null,
    },
  ];

  // DEFECT 3 fix: when the visitor picked "my country is not listed", end
  // the wizard right at the nationality step — purpose/travellers/payment
  // would never be sent anyway (see `onComplete` below), so don't ask them.
  const nationalityStepIdx = allSteps.findIndex((s) => s.id === "nationality");
  const steps: WizardStep[] = nationalityOther
    ? allSteps.slice(0, nationalityStepIdx + 1)
    : allSteps;

  const onComplete = async (values: Record<string, unknown>) => {
    setSubmitError(null);

    // DEFECT 3 fix: the escape-hatch option must never reach the engine —
    // no machine verdict for a nationality we can't evaluate. End here in a
    // human handoff instead of POSTing to the API.
    if (String(values.nationality ?? "") === "OTHER") {
      tracker.formSubmitted(Object.keys(values));
      setShowOtherNationalityHandoff(true);
      return;
    }

    tracker.formSubmitted(Object.keys(values));
    const details = (values.caseDetails as CaseDetailsValue) ?? {};
    const body: Record<string, unknown> = {
      case_type: caseType,
      nationality: String(values.nationality ?? ""),
      // DEFECT 2 fix: entry_date is required by the backend for EVERY
      // case_type — send it unconditionally, never only on issuance.
      entry_date: details.entry_date,
      passport_expiry_date: String(values.passportExpiry ?? ""),
      purpose: String(values.purpose ?? ""),
      travellers: Number(values.travellers ?? 1),
      self_pay: Boolean(values.selfPay),
    };
    if (caseType === "extension") {
      body.voa_expiry_date = details.voa_expiry_date;
      body.extension_already_used = Boolean(details.extension_already_used);
    }

    // HTTP status captured OUTSIDE the catch so the failure telemetry can
    // report it — Law 2: the failure event carries endpoint + status only,
    // never the form values (nationality, dates, etc).
    let status: number | null = null;
    try {
      const res = await fetch("/api/visa/voa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      // Status recorded for ANY completed response — a 2xx whose JSON
      // parse fails must not be misreported as a network failure (null).
      status = res.status;
      if (!res.ok) {
        throw new Error(`${res.status}`);
      }
      const { hash } = (await res.json()) as { hash: string };
      // `case_type` on the URL is copy-only branching (which reminder note
      // to show on the result page) — it is never sent back to any API and
      // carries no PII.
      router.push(`/visa/voa/${hash}?case_type=${caseType ?? "issuance"}`);
    } catch {
      tracker.formSubmitFailed("/api/visa/voa", status);
      setSubmitError(
        <>
          {t("garudaVoa.wizard.submitError.text")}{" "}
          <a
            href={buildWhatsAppLink("visa")}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--color-error)", textDecoration: "underline" }}
          >
            {t("garudaVoa.wizard.submitError.linkLabel")}
          </a>
          .
        </>,
      );
    }
  };

  // DEFECT 3 fix: "my country is not listed" ends in a human handoff, never
  // a machine verdict — same WhatsApp CTA the decline branch of the result
  // page uses, honest about why (no eligible-country dataset for it, not a
  // decline), and no fetch to `/api/visa/voa` ever happens for this path.
  if (showOtherNationalityHandoff) {
    return (
      <AppFrame
        funnel="visa"
        title={t("garudaVoa.wizard.otherNationality.title")}
        subtitle={t("garudaVoa.wizard.otherNationality.subtitle")}
      >
        <AppWhatsAppCTA
          source="garuda_voa"
          headline={t("garudaVoa.wizard.otherNationality.ctaHeadline")}
          description={t("garudaVoa.wizard.otherNationality.ctaDescription")}
          whatsappContext={[
            {
              label: t(
                "garudaVoa.wizard.otherNationality.whatsappContextLabel",
              ),
              value: t(
                "garudaVoa.wizard.otherNationality.whatsappContextValue",
              ),
            },
          ]}
          defaultLabel={t("garudaVoa.wizard.whatsappLabel")}
          onCaptured={({ leadIntentId }) =>
            tracker.whatsappHandoff(leadIntentId)
          }
        />
      </AppFrame>
    );
  }

  return (
    <AppFrame
      funnel="visa"
      title={t("garudaVoa.wizard.title")}
      subtitle={t("garudaVoa.wizard.subtitle")}
      trustStrip={
        <AppTrustStrip
          items={[
            { value: "7", label: t("garudaVoa.wizard.trust.stat1l") },
            { value: "0", label: t("garudaVoa.wizard.trust.stat2l") },
            { value: "0", label: t("garudaVoa.wizard.trust.stat3l") },
          ]}
        />
      }
    >
      <AppWizard
        steps={steps}
        persistKey={PERSIST_KEY}
        onStepChange={(step, total) => tracker.wizardStep(step + 1, total)}
        onAbandon={(step) => tracker.wizardAbandoned(step)}
        onComplete={onComplete}
      />
      {submitError ? (
        <p role="alert" style={{ color: "var(--color-error)", margin: 0 }}>
          {submitError}
        </p>
      ) : null}
    </AppFrame>
  );
}
