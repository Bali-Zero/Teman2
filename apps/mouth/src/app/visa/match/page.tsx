"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AppFrame,
  AppTrustStrip,
  AppWizard,
  useFunnelApp,
  type WizardStep,
} from "@balizero/core";

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
  { iso: "OTHER", label: "Other — I'll tell you" },
];

const PURPOSES = [
  { id: "work_remote", label: "Work remotely for a foreign employer" },
  { id: "investor", label: "Open / invest in a PT PMA" },
  { id: "work_employee", label: "Be hired by an Indonesian company" },
  { id: "family", label: "Join family (spouse, child)" },
  { id: "long_tourism", label: "Long tourism / explore" },
  { id: "retirement", label: "Retirement (55+)" },
  { id: "student", label: "Study at an Indonesian university" },
  { id: "other", label: "Something else / not sure" },
];

const BUDGETS = [
  { id: "under_50m", label: "Under IDR 50M" },
  { id: "50m_500m", label: "IDR 50M – 500M" },
  { id: "over_500m", label: "Over IDR 500M" },
];

export default function VisaMatchPage() {
  const router = useRouter();
  const tracker = useFunnelApp("visa_match");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const steps: WizardStep[] = [
    {
      id: "nationality",
      title: "Nationality",
      render: ({ value, setValue }) => (
        <div>
          <p style={{ margin: 0 }}>What's your nationality?</p>
          <select
            value={(value as string) ?? ""}
            onChange={(e) => {
              setValue(e.target.value);
              tracker.formStarted("nationality");
            }}
            style={{
              marginTop: "var(--space-2)",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: 6,
              border: "1px solid var(--color-border-subtle)",
              fontSize: "var(--text-md)",
              width: "100%",
              maxWidth: 320,
            }}
          >
            <option value="">Select one…</option>
            {NATIONALITIES.map((n) => (
              <option key={n.iso} value={n.iso}>
                {n.label}
              </option>
            ))}
          </select>
        </div>
      ),
      validate: (v) => (v ? null : "Pick a nationality."),
    },
    {
      id: "purpose",
      title: "Purpose",
      render: ({ value, setValue }) => (
        <div>
          <p style={{ margin: 0 }}>Why are you coming to Indonesia?</p>
          <div
            style={{
              display: "grid",
              gap: "var(--space-2)",
              marginTop: "var(--space-3)",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            }}
          >
            {PURPOSES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setValue(p.id);
                  tracker.formStarted("purpose");
                }}
                style={{
                  padding: "var(--space-3)",
                  borderRadius: 8,
                  border:
                    value === p.id
                      ? "2px solid var(--bz-accent, #d4845a)"
                      : "1px solid var(--color-border-subtle)",
                  background:
                    value === p.id ? "var(--surface-raised)" : "transparent",
                  textAlign: "left",
                  cursor: "pointer",
                  color: "var(--color-text-primary)",
                }}
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
      id: "duration",
      title: "Duration",
      render: ({ value, setValue }) => {
        const num = typeof value === "number" ? value : 6;
        return (
          <div>
            <p style={{ margin: 0 }}>
              Roughly how many months? ({num} {num === 1 ? "month" : "months"})
            </p>
            <input
              type="range"
              min={1}
              max={60}
              value={num}
              onChange={(e) => {
                setValue(Number(e.target.value));
                tracker.formStarted("duration");
              }}
              style={{ width: "100%", marginTop: "var(--space-3)" }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: "var(--text-sm)",
                color: "var(--color-text-muted)",
              }}
            >
              <span>1 mo</span>
              <span>60 mo</span>
            </div>
          </div>
        );
      },
    },
    {
      id: "budget",
      title: "Budget",
      render: ({ value, setValue }) => (
        <div>
          <p style={{ margin: 0 }}>Budget band for Indonesia setup?</p>
          <div
            style={{
              display: "grid",
              gap: "var(--space-2)",
              marginTop: "var(--space-3)",
            }}
          >
            {BUDGETS.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => {
                  setValue(b.id);
                  tracker.formStarted("budget");
                }}
                style={{
                  padding: "var(--space-3)",
                  borderRadius: 8,
                  border:
                    value === b.id
                      ? "2px solid var(--bz-accent, #d4845a)"
                      : "1px solid var(--color-border-subtle)",
                  background:
                    value === b.id ? "var(--surface-raised)" : "transparent",
                  textAlign: "left",
                  cursor: "pointer",
                  color: "var(--color-text-primary)",
                }}
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>
      ),
      validate: (v) => (v ? null : "Pick a budget band."),
    },
  ];

  const onComplete = async (values: Record<string, unknown>) => {
    setSubmitError(null);
    tracker.formSubmitted(Object.keys(values));
    try {
      const res = await fetch("/api/visa/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nationality: String(values.nationality ?? ""),
          purpose: String(values.purpose ?? ""),
          duration_months: Number(values.duration ?? 6),
          budget_band: String(values.budget ?? ""),
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const { hash } = (await res.json()) as { hash: string };
      router.push(`/visa/match/${hash}`);
    } catch {
      setSubmitError(
        "We could not compute a recommendation. Please try again or message us on WhatsApp.",
      );
    }
  };

  return (
    <AppFrame
      title="Visa Match"
      subtitle="4 short questions. A visa recommendation with the cost and the pre-arrival checklist."
      trustStrip={
        <AppTrustStrip
          items={[
            { value: "24+", label: "visa categories supported" },
            { value: "4", label: "questions — takes under a minute" },
            { value: "0", label: "prices invented (all from PricingTool)" },
          ]}
        />
      }
    >
      <AppWizard
        steps={steps}
        persistKey="bz.visa_match.wizard"
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
