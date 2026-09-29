"use client";

import { useCallback, useState, type CSSProperties } from "react";

type TaxpayerType = "individual" | "company";
type CompanyType = "PT_PMA" | "PT_PMDN" | "CV" | "KP3A" | "KPPA" | "OTHER";
type InvestmentStage = "construction" | "commercial";

type Obligation = {
  id: string;
  name: string;
  authority: string;
  legal_source: string;
  frequency: string;
  reviewed_on: string;
  upcoming_due_dates: Array<{
    due_date: string;
    period_key: string;
    provisional?: boolean;
  }>;
};

type CalendarResponse = { obligations: Obligation[]; withheld_count: number };

type Profile = {
  taxpayerType?: TaxpayerType;
  companyType?: CompanyType;
  hasEmployees?: boolean;
  employeeCount?: number;
  hasForeignEmployees?: boolean;
  pkp?: boolean;
  sellsOnline?: boolean;
  pseRegistered?: boolean;
  pmseVatAppointed?: boolean;
  investmentStage?: InvestmentStage;
};

const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "https://nuzantara-rag.fly.dev";
const whatsappHref =
  "https://wa.me/628213454721?text=" +
  encodeURIComponent("Bali Zero tax calendar");

const cardStyle: CSSProperties = {
  background: "var(--r19-surface)",
  border: "1px solid var(--r19-line)",
  borderRadius: "8px",
  padding: "var(--space-6)",
};

const controlStyle: CSSProperties = {
  accentColor: "var(--r19-copper)",
  minHeight: "44px",
  minWidth: "44px",
};

function civilDateInMakassar(date: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}

function parseEmployeeCount(raw: string) {
  const parsed = Math.trunc(Number(raw));
  return raw.trim() === "" || Number.isNaN(parsed)
    ? undefined
    : Math.max(0, parsed);
}

function daysUntil(dueDate: string) {
  const today = civilDateInMakassar(new Date());
  const oneDay = 24 * 60 * 60 * 1000;
  return Math.round(
    (Date.parse(`${dueDate}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) /
      oneDay,
  );
}

function RadioOption({
  checked,
  children,
  name,
  onChange,
  value,
}: {
  checked: boolean;
  children: string;
  name: string;
  onChange: () => void;
  value: string;
}) {
  return (
    <label
      style={{
        alignItems: "center",
        border: "1px solid var(--r19-line)",
        borderRadius: "8px",
        color: "var(--r19-ink)",
        cursor: "pointer",
        display: "flex",
        fontFamily: "var(--font-sans)",
        gap: "var(--space-3)",
        minHeight: "44px",
        padding: "var(--space-3)",
      }}
    >
      <input
        checked={checked}
        name={name}
        onChange={onChange}
        style={controlStyle}
        type="radio"
        value={value}
      />
      {children}
    </label>
  );
}

export function MyTaxCalendar() {
  const [profile, setProfile] = useState<Profile>({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<CalendarResponse | null>(null);
  const [status, setStatus] = useState<
    "idle" | "loading" | "rate-limit" | "error"
  >("idle");

  const requestCalendar = useCallback(async (nextProfile: Profile) => {
    setStatus("loading");
    setResult(null);
    const body =
      nextProfile.taxpayerType === "individual"
        ? { taxpayer_type: "individual" }
        : {
            taxpayer_type: "company",
            company_type: nextProfile.companyType,
            has_employees: nextProfile.hasEmployees ?? false,
            employee_count: nextProfile.hasEmployees
              ? (nextProfile.employeeCount ?? 0)
              : 0,
            has_foreign_employees: nextProfile.hasEmployees
              ? (nextProfile.hasForeignEmployees ?? false)
              : false,
            pkp: nextProfile.pkp ?? false,
            serves_indonesian_users_online: nextProfile.sellsOnline ?? false,
            pse_registered: nextProfile.sellsOnline
              ? (nextProfile.pseRegistered ?? false)
              : false,
            pmse_vat_appointed: nextProfile.sellsOnline
              ? (nextProfile.pmseVatAppointed ?? false)
              : false,
            investment_stage: nextProfile.investmentStage ?? null,
            fiscal_year_end: "12-31",
            horizon_days: 365,
          };

    try {
      const response = await fetch(
        `${backendUrl}/api/public/tax-calendar/obligations`,
        {
          body: JSON.stringify(body),
          headers: { "Content-Type": "application/json" },
          method: "POST",
        },
      );
      if (response.status === 429) {
        setStatus("rate-limit");
        return;
      }
      if (!response.ok) {
        throw new Error("Unable to load tax calendar");
      }
      setResult((await response.json()) as CalendarResponse);
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }, []);

  const updateProfile = <K extends keyof Profile>(
    key: K,
    value: Profile[K],
  ) => {
    setProfile((current) => ({ ...current, [key]: value }));
  };
  const beginIndividual = () => {
    const nextProfile = { taxpayerType: "individual" } satisfies Profile;
    setProfile(nextProfile);
    setStep(6);
    void requestCalendar(nextProfile);
  };
  const beginCompany = () => {
    setProfile({ taxpayerType: "company" });
    setStep(1);
  };
  const startOver = () => {
    setProfile({});
    setResult(null);
    setStatus("idle");
    setStep(0);
  };

  if (step === 6) {
    return (
      <section aria-live="polite" style={{ fontFamily: "var(--font-sans)" }}>
        <div
          style={{
            display: "flex",
            gap: "var(--space-3)",
            marginBottom: "var(--space-4)",
            flexWrap: "wrap",
          }}
        >
          <button
            onClick={startOver}
            style={secondaryButtonStyle}
            type="button"
          >
            Start over
          </button>
          {status === "error" && (
            <button
              onClick={() => void requestCalendar(profile)}
              style={primaryButtonStyle}
              type="button"
            >
              Retry
            </button>
          )}
        </div>
        {status === "loading" && (
          <p style={mutedStyle}>Loading your calendar…</p>
        )}
        {status === "rate-limit" && (
          <p style={mutedStyle}>Too many requests — try again in a minute.</p>
        )}
        {status === "error" && (
          <p style={mutedStyle}>
            We could not load your calendar. Please try again.
          </p>
        )}
        {result && <CalendarResult profile={profile} result={result} />}
      </section>
    );
  }

  const totalSteps = 6;
  return (
    <section style={{ fontFamily: "var(--font-sans)" }}>
      <p style={{ ...mutedStyle, marginBottom: "var(--space-3)" }}>
        Step {step + 1} of {totalSteps}
      </p>
      <div style={cardStyle}>
        {step === 0 && (
          <fieldset style={fieldsetStyle}>
            <legend style={questionStyle}>
              Are you filing as an individual or a company?
            </legend>
            <RadioOption
              checked={false}
              name="taxpayer-type"
              onChange={beginIndividual}
              value="individual"
            >
              Individual
            </RadioOption>
            <RadioOption
              checked={false}
              name="taxpayer-type"
              onChange={beginCompany}
              value="company"
            >
              Company
            </RadioOption>
          </fieldset>
        )}
        {step === 1 && (
          <fieldset style={fieldsetStyle}>
            <legend style={questionStyle}>
              What is your company&apos;s legal form?
            </legend>
            {(
              ["PT_PMA", "PT_PMDN", "CV", "KP3A", "KPPA", "OTHER"] as const
            ).map((companyType) => (
              <RadioOption
                checked={profile.companyType === companyType}
                key={companyType}
                name="company-type"
                onChange={() => updateProfile("companyType", companyType)}
                value={companyType}
              >
                {companyType === "OTHER"
                  ? "Other"
                  : companyType.replace("_", " ")}
              </RadioOption>
            ))}
            <WizardButtons
              back={() => setStep(0)}
              disabled={!profile.companyType}
              next={() => setStep(2)}
            />
          </fieldset>
        )}
        {step === 2 && (
          <fieldset style={fieldsetStyle}>
            <legend style={questionStyle}>
              Does your company have employees?
            </legend>
            <RadioOption
              checked={profile.hasEmployees === true}
              name="employees"
              onChange={() => updateProfile("hasEmployees", true)}
              value="yes"
            >
              Yes
            </RadioOption>
            <RadioOption
              checked={profile.hasEmployees === false}
              name="employees"
              onChange={() => updateProfile("hasEmployees", false)}
              value="no"
            >
              No
            </RadioOption>
            {profile.hasEmployees && (
              <>
                <label htmlFor="employee-count" style={labelStyle}>
                  How many employees?
                </label>
                <input
                  id="employee-count"
                  min="0"
                  onChange={(event) =>
                    updateProfile(
                      "employeeCount",
                      parseEmployeeCount(event.target.value),
                    )
                  }
                  step="1"
                  style={inputStyle}
                  type="number"
                  value={profile.employeeCount ?? ""}
                />
                <p
                  style={{
                    ...questionStyle,
                    fontSize: "1rem",
                    marginTop: "var(--space-4)",
                  }}
                >
                  Any foreign employees?
                </p>
                <RadioOption
                  checked={profile.hasForeignEmployees === true}
                  name="foreign-employees"
                  onChange={() => updateProfile("hasForeignEmployees", true)}
                  value="yes"
                >
                  Yes
                </RadioOption>
                <RadioOption
                  checked={profile.hasForeignEmployees === false}
                  name="foreign-employees"
                  onChange={() => updateProfile("hasForeignEmployees", false)}
                  value="no"
                >
                  No
                </RadioOption>
              </>
            )}
            <WizardButtons
              back={() => setStep(1)}
              disabled={
                profile.hasEmployees === undefined ||
                (profile.hasEmployees &&
                  (profile.employeeCount === undefined ||
                    profile.hasForeignEmployees === undefined))
              }
              next={() => setStep(3)}
            />
          </fieldset>
        )}
        {step === 3 && (
          <BooleanStep
            back={() => setStep(2)}
            checked={profile.pkp}
            name="pkp"
            next={() => setStep(4)}
            onChange={(value) => updateProfile("pkp", value)}
            question="Is your company VAT-registered (PKP)?"
          />
        )}
        {step === 4 && (
          <OnlineStep
            back={() => setStep(3)}
            profile={profile}
            setProfile={updateProfile}
            next={() => setStep(5)}
          />
        )}
        {step === 5 && (
          <StageStep
            back={() => setStep(4)}
            profile={profile}
            setProfile={updateProfile}
            submit={() => {
              setStep(6);
              void requestCalendar(profile);
            }}
          />
        )}
      </div>
    </section>
  );
}

function CalendarResult({
  profile,
  result,
}: {
  profile: Profile;
  result: CalendarResponse;
}) {
  if (result.obligations.length === 0) {
    return (
      <div style={cardStyle}>
        {profile.taxpayerType === "individual" ? (
          <p style={questionStyle}>
            Personal tax deadlines are not in this calendar yet.
          </p>
        ) : (
          result.withheld_count === 0 && (
            <p style={questionStyle}>
              None of the obligations in our register apply to this profile.
            </p>
          )
        )}
        {profile.taxpayerType === "individual" && <WhatsAppLink />}
        {result.withheld_count > 0 && (
          <WithheldNote count={result.withheld_count} />
        )}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: "var(--space-4)" }}>
      {result.obligations.map((obligation) => {
        const next = obligation.upcoming_due_dates[0];
        return (
          <article key={obligation.id} style={cardStyle}>
            <div
              style={{
                alignItems: "start",
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-3)",
                justifyContent: "space-between",
              }}
            >
              <div>
                <h3 style={headingStyle}>{obligation.name}</h3>
                <p style={mutedStyle}>
                  {obligation.authority} · {obligation.frequency}
                </p>
              </div>
              {next && (
                <span style={badgeStyle}>
                  {next.due_date} · in {daysUntil(next.due_date)}d
                  {next.provisional && <ProvisionalLabel />}
                </span>
              )}
            </div>
            {!next && (
              <p style={mutedStyle}>
                No fixed date — due when the triggering event happens.
              </p>
            )}
            {obligation.upcoming_due_dates.length > 1 && (
              <ul style={listStyle}>
                {obligation.upcoming_due_dates.slice(1).map((date) => (
                  <li key={`${date.due_date}-${date.period_key}`}>
                    {date.due_date} — {date.period_key}
                    {date.provisional && <ProvisionalLabel />}
                  </li>
                ))}
              </ul>
            )}
            <p style={mutedStyle}>{obligation.legal_source}</p>
            <p style={mutedStyle}>
              Reviewed by our tax team on {obligation.reviewed_on}
            </p>
          </article>
        );
      })}
      {result.obligations.some((obligation) =>
        obligation.upcoming_due_dates.some((date) => date.provisional),
      ) && (
        <p style={mutedStyle}>
          Provisional dates may move to the next working day once that
          year&apos;s public holidays are loaded in our calendar.
        </p>
      )}
      {result.withheld_count > 0 && (
        <WithheldNote count={result.withheld_count} />
      )}
    </div>
  );
}

function ProvisionalLabel() {
  return (
    <em style={{ fontStyle: "normal", marginLeft: "0.5ch" }}>provisional</em>
  );
}

function WithheldNote({ count }: { count: number }) {
  return (
    <aside style={{ ...cardStyle, background: "var(--r19-wash)" }}>
      <p style={mutedStyle}>
        {count} more obligations may apply to you. Our tax team is reviewing
        them before we publish them here.
      </p>
      <WhatsAppLink />
    </aside>
  );
}
function WhatsAppLink() {
  return (
    <a
      href={whatsappHref}
      style={{
        color: "var(--r19-copper)",
        alignItems: "center",
        display: "inline-flex",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        minHeight: "44px",
      }}
    >
      Ask our tax team on WhatsApp
    </a>
  );
}
function WizardButtons({
  back,
  disabled,
  next,
}: {
  back: () => void;
  disabled: boolean;
  next: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: "var(--space-3)",
        marginTop: "var(--space-6)",
      }}
    >
      <button onClick={back} style={secondaryButtonStyle} type="button">
        Back
      </button>
      <button
        disabled={disabled}
        onClick={next}
        style={primaryButtonStyle}
        type="button"
      >
        Continue
      </button>
    </div>
  );
}
function BooleanStep({
  back,
  checked,
  name,
  next,
  onChange,
  question,
}: {
  back: () => void;
  checked?: boolean;
  name: string;
  next: () => void;
  onChange: (value: boolean) => void;
  question: string;
}) {
  return (
    <fieldset style={fieldsetStyle}>
      <legend style={questionStyle}>{question}</legend>
      <RadioOption
        checked={checked === true}
        name={name}
        onChange={() => onChange(true)}
        value="yes"
      >
        Yes
      </RadioOption>
      <RadioOption
        checked={checked === false}
        name={name}
        onChange={() => onChange(false)}
        value="no"
      >
        No
      </RadioOption>
      <WizardButtons back={back} disabled={checked === undefined} next={next} />
    </fieldset>
  );
}
function OnlineStep({
  back,
  next,
  profile,
  setProfile,
}: {
  back: () => void;
  next: () => void;
  profile: Profile;
  setProfile: <K extends keyof Profile>(key: K, value: Profile[K]) => void;
}) {
  const ready =
    profile.sellsOnline === false ||
    (profile.sellsOnline === true &&
      profile.pseRegistered !== undefined &&
      profile.pmseVatAppointed !== undefined);
  return (
    <fieldset style={fieldsetStyle}>
      <legend style={questionStyle}>
        Does your company sell online to users in Indonesia?
      </legend>
      <RadioOption
        checked={profile.sellsOnline === true}
        name="online"
        onChange={() => setProfile("sellsOnline", true)}
        value="yes"
      >
        Yes
      </RadioOption>
      <RadioOption
        checked={profile.sellsOnline === false}
        name="online"
        onChange={() => setProfile("sellsOnline", false)}
        value="no"
      >
        No
      </RadioOption>
      {profile.sellsOnline && (
        <>
          <p
            style={{
              ...questionStyle,
              fontSize: "1rem",
              marginTop: "var(--space-4)",
            }}
          >
            Are you PSE-registered?
          </p>
          <RadioOption
            checked={profile.pseRegistered === true}
            name="pse"
            onChange={() => setProfile("pseRegistered", true)}
            value="yes"
          >
            Yes
          </RadioOption>
          <RadioOption
            checked={profile.pseRegistered === false}
            name="pse"
            onChange={() => setProfile("pseRegistered", false)}
            value="no"
          >
            No
          </RadioOption>
          <p
            style={{
              ...questionStyle,
              fontSize: "1rem",
              marginTop: "var(--space-4)",
            }}
          >
            Are you appointed as a PMSE VAT collector?
          </p>
          <RadioOption
            checked={profile.pmseVatAppointed === true}
            name="pmse"
            onChange={() => setProfile("pmseVatAppointed", true)}
            value="yes"
          >
            Yes
          </RadioOption>
          <RadioOption
            checked={profile.pmseVatAppointed === false}
            name="pmse"
            onChange={() => setProfile("pmseVatAppointed", false)}
            value="no"
          >
            No
          </RadioOption>
        </>
      )}
      <WizardButtons back={back} disabled={!ready} next={next} />
    </fieldset>
  );
}
function StageStep({
  back,
  profile,
  setProfile,
  submit,
}: {
  back: () => void;
  profile: Profile;
  setProfile: <K extends keyof Profile>(key: K, value: Profile[K]) => void;
  submit: () => void;
}) {
  return (
    <fieldset style={fieldsetStyle}>
      <legend style={questionStyle}>
        What is your company&apos;s current investment stage?
      </legend>
      <RadioOption
        checked={profile.investmentStage === "construction"}
        name="stage"
        onChange={() => setProfile("investmentStage", "construction")}
        value="construction"
      >
        Construction or pre-operational
      </RadioOption>
      <RadioOption
        checked={profile.investmentStage === "commercial"}
        name="stage"
        onChange={() => setProfile("investmentStage", "commercial")}
        value="commercial"
      >
        Commercial operation
      </RadioOption>
      <WizardButtons
        back={back}
        disabled={!profile.investmentStage}
        next={submit}
      />
    </fieldset>
  );
}

const fieldsetStyle: CSSProperties = {
  border: 0,
  display: "grid",
  gap: "var(--space-3)",
  margin: 0,
  padding: 0,
};
const headingStyle: CSSProperties = {
  color: "var(--r19-ink)",
  fontFamily: "var(--font-serif)",
  fontSize: "1.35rem",
  fontWeight: 500,
  margin: 0,
};
const questionStyle: CSSProperties = {
  color: "var(--r19-ink)",
  fontFamily: "var(--font-serif)",
  fontSize: "1.2rem",
  fontWeight: 500,
  marginBottom: "var(--space-3)",
};
const mutedStyle: CSSProperties = {
  color: "var(--r19-muted)",
  fontFamily: "var(--font-sans)",
  margin: 0,
};
const labelStyle: CSSProperties = {
  color: "var(--r19-ink)",
  fontFamily: "var(--font-sans)",
  fontWeight: 600,
};
const inputStyle: CSSProperties = {
  border: "1px solid var(--r19-line)",
  borderRadius: "8px",
  color: "var(--r19-ink)",
  fontFamily: "var(--font-sans)",
  minHeight: "44px",
  padding: "var(--space-2) var(--space-3)",
};
const primaryButtonStyle: CSSProperties = {
  background: "var(--r19-copper)",
  border: "1px solid var(--r19-copper)",
  borderRadius: "8px",
  color: "var(--r19-cta-ink)",
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  fontWeight: 600,
  minHeight: "44px",
  padding: "var(--space-2) var(--space-4)",
};
const secondaryButtonStyle: CSSProperties = {
  background: "var(--r19-surface)",
  border: "1px solid var(--r19-line)",
  borderRadius: "8px",
  color: "var(--r19-ink)",
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  minHeight: "44px",
  padding: "var(--space-2) var(--space-4)",
};
const badgeStyle: CSSProperties = {
  background: "var(--r19-wash)",
  border: "1px solid var(--r19-line)",
  borderRadius: "999px",
  color: "var(--r19-copper)",
  fontFamily: "var(--font-sans)",
  fontWeight: 600,
  padding: "var(--space-2) var(--space-3)",
};
const listStyle: CSSProperties = {
  color: "var(--r19-muted)",
  margin: "var(--space-4) 0",
  paddingLeft: "var(--space-6)",
};
