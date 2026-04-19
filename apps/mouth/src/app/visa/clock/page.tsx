"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  AppFrame,
  AppHeroForm,
  AppTrustStrip,
  useFunnelApp,
} from "@balizero/core";

const VISA_OPTIONS = [
  { code: "B211A", label: "B211A Tourism (60–180 days)" },
  { code: "C1", label: "C1 Tourism (60 days, extendable)" },
  { code: "C2", label: "C2 Business visit" },
  { code: "C7", label: "C7 Job training" },
  { code: "C7A", label: "C7A Music / art" },
  { code: "C7B", label: "C7B Sport" },
  { code: "E33G", label: "E33G Digital Nomad / Remote Worker KITAS" },
  { code: "E28A", label: "E28A Investor KITAS (2 years)" },
  { code: "E23", label: "E23 Work KITAS (employer-sponsored)" },
  { code: "E33F", label: "E33F Retirement KITAS (55+)" },
  { code: "E31", label: "E31 Family / Dependent KITAS" },
  { code: "E30A", label: "E30A Student KITAS" },
];

export default function VisaClockPage() {
  const router = useRouter();
  const tracker = useFunnelApp("visa_clock");
  const [visaType, setVisaType] = useState("");
  const [entryDate, setEntryDate] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!visaType || !entryDate) {
      setError("Pick a visa type and the entry date.");
      return;
    }
    setPending(true);
    setError(null);
    tracker.formSubmitted(["visa_type", "entry_date"]);
    try {
      const res = await fetch("/api/visa/clock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visa_type: visaType,
          entry_date: entryDate,
          in_country_now: true,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const { hash } = (await res.json()) as { hash: string };
      router.push(`/visa/clock/${hash}`);
    } catch {
      setError("Could not build your timeline. Please try again.");
      setPending(false);
    }
  };

  return (
    <AppFrame
      title="Visa Clock"
      subtitle="Two fields. Your expiry timeline with 5 checkpoints."
      trustStrip={
        <AppTrustStrip
          items={[
            { value: "5,021", label: "visas filed since 2019" },
            { value: "5", label: "timeline checkpoints (D-60 → D-1)" },
            { value: "4.8h", label: "average first-reply on WhatsApp" },
          ]}
        />
      }
    >
      <AppHeroForm
        headline="Which visa + when did you enter Indonesia?"
        submitLabel="Show my timeline"
        onSubmit={submit}
        pending={pending}
        error={error}
      >
        <label
          style={{
            display: "grid",
            gap: "var(--space-1)",
            fontSize: "var(--text-sm)",
          }}
        >
          Visa type
          <select
            required
            value={visaType}
            onChange={(e) => {
              setVisaType(e.target.value);
              tracker.formStarted("visa_type");
            }}
            style={{
              padding: "var(--space-2) var(--space-3)",
              borderRadius: 6,
              border: "1px solid var(--color-border-subtle)",
              fontSize: "var(--text-md)",
            }}
          >
            <option value="">Select one…</option>
            {VISA_OPTIONS.map((v) => (
              <option key={v.code} value={v.code}>
                {v.label}
              </option>
            ))}
          </select>
        </label>
        <label
          style={{
            display: "grid",
            gap: "var(--space-1)",
            fontSize: "var(--text-sm)",
          }}
        >
          Entry date
          <input
            type="date"
            required
            value={entryDate}
            onChange={(e) => {
              setEntryDate(e.target.value);
              tracker.formStarted("entry_date");
            }}
            style={{
              padding: "var(--space-2) var(--space-3)",
              borderRadius: 6,
              border: "1px solid var(--color-border-subtle)",
              fontSize: "var(--text-md)",
            }}
          />
        </label>
      </AppHeroForm>
    </AppFrame>
  );
}
