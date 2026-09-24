"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { BZLogo, useFunnelApp, type WizardStep } from "@balizero/core";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import type { CaseType, Purpose } from "@/components/garuda/declineEducation";
import { ContentLangSync } from "@/i18n/ContentLangSync";
import { voaCopy, type VoaCopyKey } from "./voa-copy";
import { useVoaLocale } from "./useVoaLocale";
import { VoaWizard } from "./VoaWizard";
import {
  stampSubmittedAnswersHash,
  writeSubmittedAnswers,
} from "./submittedAnswers";

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

/**
 * The field boundary is `--tx-tertiary`, measured on production at 4.18:1
 * against the field's own fill (SC 1.4.11 asks 3:1 of a control's edge; the
 * subtle divider token it used to wear read 1.42:1 and was the only thing
 * making these look like fields at all — PR 6912 cured the verdict screen's
 * entry field the same way). That rule now lives in `voa-r19.css`
 * (`.voa-field`), next to every other control on this surface, instead of in
 * inline style objects the skin could not reach.
 */

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
          <p className="voa-q">{t("step.case.question")}</p>
          <div className="voa-options">
            {CASE_TYPES.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  setValue(c.id);
                  setCaseType(c.id);
                }}
                className="voa-option"
                aria-pressed={value === c.id}
              >
                <span className="voa-option__label">{t(c.labelKey)}</span>
                <span className="voa-option__hint">{t(c.hintKey)}</span>
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
          <p className="voa-q">{t("step.purpose.question")}</p>
          <div className="voa-options">
            {PURPOSES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setValue(p.id)}
                className="voa-option"
                aria-pressed={value === p.id}
              >
                <span className="voa-option__label">{t(p.labelKey)}</span>
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
          <div className="voa-fields">
            <div>
              <p className="voa-q">{t("trip.nationality.question")}</p>
              <select
                value={v.nationality ?? ""}
                onChange={(e) =>
                  setValue({ ...v, nationality: e.target.value })
                }
                className="voa-field voa-field--select"
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
              <p className="voa-q">{t("trip.travellers.question")}</p>
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
                className="voa-field voa-field--count"
                aria-label={t("trip.travellers.aria")}
              />
            </div>
            <label className="voa-check">
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
          <div className="voa-fields">
            <div>
              <p className="voa-q">{t("dates.entry.question")}</p>
              <input
                type="date"
                value={v.entry_date ?? ""}
                onChange={(e) => setValue({ ...v, entry_date: e.target.value })}
                className="voa-field"
                aria-label={t("dates.entry.aria")}
              />
            </div>
            <div>
              <p className="voa-q">{t("dates.passport.question")}</p>
              <input
                type="date"
                value={v.passport_expiry_date ?? ""}
                onChange={(e) =>
                  setValue({ ...v, passport_expiry_date: e.target.value })
                }
                className="voa-field"
                aria-label={t("dates.passport.aria")}
              />
            </div>
            {caseType === "extension" ? (
              <>
                <div>
                  <p className="voa-q">{t("dates.voaExpiry.question")}</p>
                  <input
                    type="date"
                    value={v.voa_expiry_date ?? ""}
                    onChange={(e) =>
                      setValue({ ...v, voa_expiry_date: e.target.value })
                    }
                    className="voa-field"
                    aria-label={t("dates.voaExpiry.aria")}
                  />
                </div>
                <label className="voa-check">
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
            <label className="voa-check voa-check--notice">
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
    // The verdict screen's decline "mirror" ("You told us you hold a passport
    // from …") reads the answers back from this browser. It used to read the
    // wizard's resume key — which the wizard deletes the moment it completes,
    // so every real decline mirrored an empty nationality. The hand-off gets
    // its own tab-scoped entry, written here just before the check is sent
    // and stamped with the result hash below once the backend returns one —
    // see submittedAnswers.ts for why it is unreadable until then.
    writeSubmittedAnswers(values);

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
          stampSubmittedAnswersHash(resultId);
          router.push(`/visa/voa/${resultId}`);
          return;
        }
      }
      throw new Error(`unexpected status ${res.status}`);
    } catch {
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
    } finally {
      setSubmitting(false);
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
      {/*
       * The sheet the funnel is filed on. It used to be core's AppFrame,
       * whose inline `minHeight: 100vh` ran the paper to the bottom of every
       * viewport under a lone Next button, and whose trust strip set three
       * dashboard numerals between the promise and the first question —
       * measured at 390px, that pushed step 1's options and its action below
       * the fold. `data-funnel` stays: voa-r19.css's 0-3-0 accent override
       * keys on it.
       */}
      <section
        role="region"
        aria-label={t("frame.title")}
        data-funnel="visa"
        className="voa-sheet"
      >
        <header className="voa-head">
          <p className="voa-lockup">
            <BZLogo variant="round" size={28} priority />
            <span className="voa-lockup__name">{t("lockup.brand")}</span>
          </p>
          <h1 className="voa-head__title">{t("frame.title")}</h1>
          <p className="voa-head__lede">{t("frame.subtitle")}</p>
          {/* The three terms, read as a filed line rather than a scoreboard. */}
          <ul className="voa-terms">
            <li>
              <span className="voa-terms__n">4</span>
              {t("trust.questions.label")}
            </li>
            <li>
              <span className="voa-terms__n">1</span>
              {t("trust.price.label")}
            </li>
            <li>
              <span className="voa-terms__n">0</span>
              {t("trust.government.label")}
            </li>
          </ul>
          {/*
           * Measured on production 2026-09-16 at 390px: the only WhatsApp
           * controls on this page were the nav link (height 0 — it lives
           * inside the collapsed hamburger) and a footer "Get Started". A
           * visitor who wants a human had nothing to tap in the first screen.
           * This is that control, and it is a WhatsAppLeadButton rather than
           * a bare wa.me anchor so the tap writes a lead_intents row first: a
           * tourist who leaves the funnel for a human is a lead saved, not a
           * lead lost. The face is the named agent the owner ruled for this
           * funnel (Cap Dinas v2, ruling 5) — a person, not a presence dot.
           */}
          <div className="voa-hero-wa">
            <p className="voa-hero-wa__line">
              {t("hero.wa.line")}{" "}
              <span className="voa-hero-wa__who">{t("hero.wa.who")}</span>
            </p>
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
              {/* eslint-disable-next-line @next/next/no-img-element -- a 32px staff face; the optimiser adds nothing here */}
              <img
                className="voa-hero-wa__face"
                src="/static/team/surya.jpg"
                alt=""
                width={32}
                height={32}
              />
              {t("hero.wa.cta")}
            </WhatsAppLeadButton>
          </div>
        </header>
        <main className="voa-main">
          <VoaWizard
            steps={steps}
            labels={{
              stepOf: (current, total) =>
                t("wizard.stepOf", { current, total }),
              progress: t("wizard.progress"),
              back: t("wizard.back"),
              next: t("wizard.next"),
              finish: t("wizard.finish"),
              change: t("wizard.change"),
              assure: t("wizard.assure"),
            }}
            persistKey="bz.garuda_voa.wizard"
            onStepChange={(step, total) => tracker.wizardStep(step + 1, total)}
            onAbandon={(step) => tracker.wizardAbandoned(step)}
            onComplete={onComplete}
          />
          {submitting ? (
            <p className="voa-status" role="status">
              {t("status.checking")}
            </p>
          ) : null}
          {submitError ? (
            <p
              role="alert"
              className="voa-submit-error"
              style={{ color: "var(--tx-pure)" }}
            >
              {submitError}
            </p>
          ) : null}
        </main>
      </section>
    </>
  );
}
