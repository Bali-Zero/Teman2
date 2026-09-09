"use client";

import { useState } from "react";
import { AppFrame, AppWizard, type WizardStep } from "./ui";
import type { CaseType, Purpose } from "./declineEducation";

/**
 * GARUDA VOA — public eligibility wizard (owner decision 5, "Concept A — The
 * Stamp"). Answers become the exact `EligibilityCheckRequest` body defined
 * in `products/garuda-voa/contracts/openapi.yaml` — every field name below
 * matches the frozen contract, nothing renamed on the way to the wire.
 *
 * Constraint 5a: this whole surface is English, no exceptions, no locale
 * switcher — the public API only ever emits reason codes, never prose, so
 * there is nothing here to translate against.
 */

const CASE_TYPES: { id: CaseType; label: string; hint: string }[] = [
  {
    id: "issuance",
    label: "Get a new Visa on Arrival",
    hint: "First time, or a fresh entry",
  },
  {
    id: "extension",
    label: "Extend a Visa on Arrival I already have",
    hint: "You're already in Indonesia",
  },
];

const PURPOSES: { id: Purpose; label: string }[] = [
  { id: "tourism", label: "Tourism" },
  { id: "family", label: "Visiting family" },
  { id: "transit", label: "Transit" },
  { id: "business-meeting", label: "A business meeting" },
];

const NATIONALITIES = [
  { iso: "USA", label: "United States" },
  { iso: "GBR", label: "United Kingdom" },
  { iso: "ITA", label: "Italy" },
  { iso: "DEU", label: "Germany" },
  { iso: "FRA", label: "France" },
  { iso: "AUS", label: "Australia" },
  { iso: "CAN", label: "Canada" },
  { iso: "NLD", label: "Netherlands" },
  { iso: "SGP", label: "Singapore" },
  { iso: "OTHER", label: "Other" },
];

const labelStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: "var(--font-serif, Georgia, serif)",
  fontSize: "clamp(1.1rem, 2.6vw, 1.3rem)",
};

const fieldStyle: React.CSSProperties = {
  padding: "0.6rem 0.7rem",
  borderRadius: 4,
  border: "1px solid var(--color-border-subtle)",
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
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  // AppWizard's per-step render only sees that step's own value, never the
  // whole answer set — but the "dates" step needs to know case_type (extension
  // asks two extra contract-required fields the issuance case must NOT send).
  // Mirrored here as the wizard's own step 1 answer is set.
  const [caseType, setCaseType] = useState<CaseType | undefined>();

  const steps: WizardStep[] = [
    {
      id: "case_type",
      title: "Your case",
      summary: (v) => CASE_TYPES.find((c) => c.id === v)?.label ?? "?",
      render: ({ value, setValue }) => (
        <div>
          <p style={labelStyle}>What are you here for?</p>
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
                <div>{c.label}</div>
                <div
                  style={{
                    fontSize: "var(--text-sm, 0.85rem)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {c.hint}
                </div>
              </button>
            ))}
          </div>
        </div>
      ),
      validate: (v) => (v ? null : "Pick one."),
    },
    {
      id: "purpose",
      title: "Purpose",
      summary: (v) => PURPOSES.find((p) => p.id === v)?.label ?? "?",
      render: ({ value, setValue }) => (
        <div>
          <p style={labelStyle}>Why are you travelling?</p>
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
                {p.label}
              </button>
            ))}
          </div>
        </div>
      ),
      validate: (v) => (v ? null : "Pick one."),
    },
    {
      id: "trip",
      title: "About you",
      summary: (v) => {
        const t = v as
          { nationality?: string; travellers?: number } | undefined;
        return t?.nationality
          ? `${t.nationality} · ${t.travellers ?? 1} traveller(s)`
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
              <p style={labelStyle}>What&apos;s your nationality?</p>
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
                aria-label="Nationality"
              >
                <option value="">Select one…</option>
                {NATIONALITIES.map((n) => (
                  <option key={n.iso} value={n.iso}>
                    {n.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <p style={labelStyle}>How many travellers on this application?</p>
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
                aria-label="Number of travellers"
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
              I am paying for this application myself
            </label>
          </div>
        );
      },
      validate: (v) => {
        const t = v as { nationality?: string } | undefined;
        return t?.nationality ? null : "Pick a nationality.";
      },
    },
    {
      id: "dates",
      title: "Dates",
      summary: () => "Confirmed",
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
              <p style={labelStyle}>When do you arrive (or did you arrive)?</p>
              <input
                type="date"
                value={v.entry_date ?? ""}
                onChange={(e) => setValue({ ...v, entry_date: e.target.value })}
                style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
                aria-label="Entry date"
              />
            </div>
            <div>
              <p style={labelStyle}>Passport expiry date</p>
              <input
                type="date"
                value={v.passport_expiry_date ?? ""}
                onChange={(e) =>
                  setValue({ ...v, passport_expiry_date: e.target.value })
                }
                style={{ ...fieldStyle, marginTop: "var(--space-2, 0.5rem)" }}
                aria-label="Passport expiry date"
              />
            </div>
            {caseType === "extension" ? (
              <>
                <div>
                  <p style={labelStyle}>
                    When does your current Visa on Arrival expire?
                  </p>
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
                    aria-label="Current Visa on Arrival expiry date"
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
                  I have already extended this Visa on Arrival once
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
                aria-label="Storage and deletion notice acknowledgement"
              />
              These saved answers can be resumed for up to one hour. I can clear
              them with “Start again”. The secure service asks for its own
              storage acknowledgement.
            </label>
          </div>
        );
      },
      validate: (v) => {
        const t = v as
          | {
              entry_date?: string;
              passport_expiry_date?: string;
              voa_expiry_date?: string;
              retention_notice_acknowledged?: boolean;
            }
          | undefined;
        if (!t?.entry_date || !t?.passport_expiry_date)
          return "Both dates are needed.";
        if (caseType === "extension" && !t.voa_expiry_date) {
          return "Your current Visa on Arrival's expiry date is needed.";
        }
        if (!t.retention_notice_acknowledged)
          return "Please confirm you've read the storage notice.";
        return null;
      },
    },
  ];

  const onComplete = (values: Record<string, unknown>) => {
    setReview(values);
  };

  return (
    <AppFrame
      funnel="visa"
      title="Prepare your Visa on Arrival check"
      subtitle="Review the information needed for a new Visa on Arrival or an extension. The secure service runs the eligibility check after you continue."
    >
      {review ? (
        <VoaPreparationReview answers={review} onEdit={() => setReview(null)} />
      ) : (
        <AppWizard
          steps={steps}
          persistKey="bz.garuda_voa.wizard"
          onComplete={onComplete}
          completeLabel="Review my answers"
          onRestore={(values) =>
            setCaseType(
              values.case_type === "extension" ? "extension" : "issuance",
            )
          }
        />
      )}
    </AppFrame>
  );
}

function VoaPreparationReview({
  answers,
  onEdit,
}: {
  answers: Record<string, unknown>;
  onEdit: () => void;
}) {
  const trip = answers.trip as {
    nationality: string;
    travellers?: number;
    self_pay?: boolean;
  };
  const dates = answers.dates as {
    entry_date: string;
    passport_expiry_date: string;
    voa_expiry_date?: string;
    extension_already_used?: boolean;
  };
  const extension = answers.case_type === "extension";
  return (
    <section className="visa-tool-card">
      <p className="visa-tool-eyebrow">
        Preparation only · No eligibility check submitted
      </p>
      <h2>Your answers, ready to review.</h2>
      <dl className="visa-tool-facts">
        <div>
          <dt>Request</dt>
          <dd>{extension ? "Extension" : "New Visa on Arrival"}</dd>
        </div>
        <div>
          <dt>Passport nationality</dt>
          <dd>{trip.nationality}</dd>
        </div>
        <div>
          <dt>Purpose</dt>
          <dd>{String(answers.purpose)}</dd>
        </div>
        <div>
          <dt>Travellers / payment</dt>
          <dd>
            {trip.travellers ?? 1} /{" "}
            {trip.self_pay === false ? "Paid by someone else" : "Self pay"}
          </dd>
        </div>
        <div>
          <dt>Entry date</dt>
          <dd>{dates.entry_date}</dd>
        </div>
        <div>
          <dt>Passport expires</dt>
          <dd>{dates.passport_expiry_date}</dd>
        </div>
        {extension && (
          <>
            <div>
              <dt>Current VOA expires</dt>
              <dd>{dates.voa_expiry_date}</dd>
            </div>
            <div>
              <dt>Extension already used</dt>
              <dd>{dates.extension_already_used ? "Yes" : "No"}</dd>
            </div>
          </>
        )}
      </dl>
      <h3>What happens next</h3>
      <ol>
        <li>
          Continue to the secure service and confirm these answers there. No
          answers are transferred by this link.
        </li>
        <li>
          The eligibility engine checks your case and returns its decision, any
          supported price and the applicable next step.
        </li>
        <li>
          For a supported case, verify your email, upload the requested
          documents, review the order and complete payment in that same service.
        </li>
        <li>
          Use your secure order link to follow the application. This preparation
          page does not create an order or reserve a filing date.
        </li>
      </ol>
      <div className="visa-tool-actions">
        <a className="visa-tool-primary" href="/legacy/visa/voa">
          Continue to the secure eligibility check
        </a>
        <button type="button" onClick={onEdit}>
          Edit my answers
        </button>
        <button type="button" onClick={() => window.print()}>
          Print preparation
        </button>
      </div>
    </section>
  );
}
