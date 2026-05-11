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
  { code: "B211A", label: "B211A Tourism" },
  { code: "C1", label: "C1 Tourism" },
  { code: "C2", label: "C2 Business" },
  { code: "C7", label: "C7 Job training" },
  { code: "C7A", label: "C7A Music/Art" },
  { code: "C7B", label: "C7B Sport" },
  { code: "E33G", label: "E33G Digital Nomad KITAS" },
  { code: "E28A", label: "E28A Investor KITAS" },
  { code: "E23", label: "E23 Work KITAS" },
  { code: "E33F", label: "E33F Retirement KITAS" },
  { code: "E31", label: "E31 Family KITAS" },
  { code: "E30A", label: "E30A Student KITAS" },
];

const fieldStyle: React.CSSProperties = {
  padding: "0.45rem 0.7rem",
  borderRadius: 4,
  border: "1px solid var(--color-border-subtle)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
  fontSize: "inherit",
  fontFamily: "inherit",
};

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
      funnel="visa"
      title="Your timeline in five checkpoints."
      subtitle="Fill in the two blanks."
      trustStrip={
        <AppTrustStrip
          items={[
            { value: "5,021", label: "visas filed since 2019" },
            { value: "5", label: "checkpoints (D-60 → D-1)" },
            { value: "4.8h", label: "avg first-reply on WhatsApp" },
          ]}
        />
      }
    >
      <AppHeroForm
        headline="Two fields. Your expiry timeline."
        submitLabel="Show my timeline"
        onSubmit={submit}
        pending={pending}
        error={error}
        sentenceTemplate="I entered on {entry} with a {visa} visa."
        sentenceFields={{
          entry: (
            <input
              type="date"
              required
              value={entryDate}
              onChange={(e) => {
                setEntryDate(e.target.value);
                tracker.formStarted("entry_date");
              }}
              style={fieldStyle}
              aria-label="Entry date"
            />
          ),
          visa: (
            <select
              required
              value={visaType}
              onChange={(e) => {
                setVisaType(e.target.value);
                tracker.formStarted("visa_type");
              }}
              style={fieldStyle}
              aria-label="Visa type"
            >
              <option value="">pick one…</option>
              {VISA_OPTIONS.map((v) => (
                <option key={v.code} value={v.code}>
                  {v.label}
                </option>
              ))}
            </select>
          ),
        }}
      />
    </AppFrame>
  );
}
