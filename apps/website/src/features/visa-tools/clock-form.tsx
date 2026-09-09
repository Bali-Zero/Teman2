"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppFrame, AppHeroForm } from "./ui";

const VISA_OPTIONS = [
  { code: "B1", label: "B1 Visa on Arrival (VOA)" },
  { code: "B211A", label: "B211A Tourism" },
  { code: "C1", label: "C1 Tourism" },
  { code: "C2", label: "C2 Business" },
  { code: "C7", label: "C7 Job training" },
  { code: "C7A", label: "C7A Music/Art" },
  { code: "C7B", label: "C7B Sport" },
  { code: "E33G", label: "E33G Digital Nomad KITAS" },
  { code: "E33", label: "E33 Second Home KITAS" },
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
  const [visaType, setVisaType] = useState("");
  const [entryDate, setEntryDate] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pending) return;
    if (!visaType || !entryDate) {
      setError("Pick a visa type and the entry date.");
      return;
    }
    setPending(true);
    setError(null);
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
      if (!res.ok) {
        throw new Error(`${res.status}`);
      }
      const { hash } = (await res.json()) as { hash: string };
      if (typeof hash !== "string" || !/^[A-Za-z0-9_-]{1,200}$/.test(hash))
        throw new Error("Invalid result reference");
      router.push(`/visa/clock/${hash}`);
    } catch {
      setError("Could not build your timeline. Please try again.");
      setPending(false);
    }
  };

  return (
    <AppFrame
      funnel="visa"
      title="Keep your next visa date in sight."
      subtitle="Build a planning timeline from your visa code and entry date. Check every date against the permit actually issued to you."
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
              }}
              style={fieldStyle}
              aria-label="Visa type"
            >
              <option value="">pick one…</option>
              {VISA_OPTIONS.map((v) => (
                <option key={v.code} value={v.code}>
                  {v.code}
                </option>
              ))}
            </select>
          ),
        }}
      />
    </AppFrame>
  );
}
