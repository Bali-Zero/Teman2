"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { QuizAnswers } from "@/lib/visa-oracle/types";
import {
  PURPOSE_OPTIONS,
  DURATION_OPTIONS,
  FAMILY_OPTIONS,
  getStepTitle,
  type QuizStep,
} from "@/lib/visa-oracle/quiz-logic";
import { ALL_NATIONALITIES } from "@/lib/visa-oracle/nationalities";

export function QuizWizard() {
  const router = useRouter();
  const [step, setStep] = useState<QuizStep>(1);
  const [answers, setAnswers] = useState<Partial<QuizAnswers>>({});
  const [search, setSearch] = useState("");

  const filteredNationalities = ALL_NATIONALITIES.filter((n) =>
    n.name.toLowerCase().includes(search.toLowerCase()),
  );

  function handleNationality(nationality: string) {
    setAnswers((prev) => ({ ...prev, nationality }));
    setStep(2);
  }

  function handlePurpose(purpose: QuizAnswers["purpose"]) {
    setAnswers((prev) => ({ ...prev, purpose }));
    setStep(3);
  }

  function handleDuration(duration: QuizAnswers["duration"]) {
    setAnswers((prev) => ({ ...prev, duration }));
    setStep(4);
  }

  function handleFamily(family: QuizAnswers["family"]) {
    const finalAnswers = { ...answers, family } as QuizAnswers;
    const params = new URLSearchParams({
      nationality: finalAnswers.nationality,
      purpose: finalAnswers.purpose,
      duration: finalAnswers.duration,
      family: finalAnswers.family,
    });
    router.push(`/visa-oracle/result?${params.toString()}`);
  }

  function handleBack() {
    if (step > 1) setStep((prev) => (prev - 1) as QuizStep);
  }

  return (
    <div className="flex flex-col gap-8 max-w-2xl mx-auto">
      {/* Progress bar */}
      <div className="flex gap-1.5">
        {([1, 2, 3, 4] as QuizStep[]).map((s) => (
          <div
            key={s}
            className="flex-1 h-1 rounded-full transition-all duration-300"
            style={{
              backgroundColor:
                s <= step ? "var(--bz-accent)" : "rgba(255,255,255,0.12)",
            }}
          />
        ))}
      </div>

      {/* Header */}
      <div className="flex items-center gap-4">
        {step > 1 && (
          <button
            onClick={handleBack}
            className="flex-shrink-0 p-2 rounded-lg transition-opacity hover:opacity-70"
            style={{ color: "var(--tx-secondary)" }}
            aria-label="Go back"
          >
            ←
          </button>
        )}
        <h2 className="text-xl sm:text-2xl font-bold">{getStepTitle(step)}</h2>
      </div>

      {/* Step 1: Nationality */}
      {step === 1 && (
        <div className="flex flex-col gap-4">
          <input
            type="text"
            placeholder="Search your country..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-4 py-3 rounded-lg text-base outline-none focus:ring-2 transition-all"
            style={{
              backgroundColor: "var(--bz-elevated)",
              color: "var(--tx-primary)",
              border: "1px solid rgba(255,255,255,0.12)",
            }}
            autoFocus
          />
          <div
            className="flex flex-col gap-1 max-h-80 overflow-y-auto rounded-lg"
            style={{ backgroundColor: "var(--bz-elevated)" }}
          >
            {filteredNationalities.length === 0 ? (
              <p
                className="text-sm text-center py-6"
                style={{ color: "var(--tx-secondary)" }}
              >
                No countries found.
              </p>
            ) : (
              filteredNationalities.map((nat) => (
                <button
                  key={nat.code}
                  onClick={() => handleNationality(nat.name)}
                  className="flex items-center gap-3 px-4 py-3 text-left transition-colors hover:opacity-80 w-full"
                  style={{
                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <span className="text-xl" aria-hidden>
                    {nat.flag}
                  </span>
                  <span className="text-sm font-medium">{nat.name}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {/* Step 2: Purpose */}
      {step === 2 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {PURPOSE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handlePurpose(opt.value)}
              className="flex flex-col items-center gap-2 p-5 rounded-xl transition-all hover:opacity-90 active:scale-95"
              style={{ backgroundColor: "var(--bz-elevated)" }}
            >
              <span className="text-3xl" aria-hidden>
                {opt.icon}
              </span>
              <span className="text-sm font-medium text-center">
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Step 3: Duration */}
      {step === 3 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {DURATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleDuration(opt.value)}
              className="flex flex-col gap-1 p-5 rounded-xl text-left transition-all hover:opacity-90 active:scale-95"
              style={{ backgroundColor: "var(--bz-elevated)" }}
            >
              <span className="font-semibold">{opt.label}</span>
              <span
                className="text-sm"
                style={{ color: "var(--tx-secondary)" }}
              >
                {opt.description}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Step 4: Family */}
      {step === 4 && (
        <div className="grid grid-cols-2 gap-3">
          {FAMILY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleFamily(opt.value)}
              className="flex flex-col items-center gap-2 p-5 rounded-xl transition-all hover:opacity-90 active:scale-95"
              style={{ backgroundColor: "var(--bz-elevated)" }}
            >
              <span className="text-3xl" aria-hidden>
                {opt.icon}
              </span>
              <span className="text-sm font-medium text-center">
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
