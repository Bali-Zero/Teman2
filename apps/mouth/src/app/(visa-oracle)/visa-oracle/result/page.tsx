"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { VisaCard } from "@/components/visa-oracle/VisaCard";
import { recommendVisas } from "@/lib/visa-oracle/api";
import { saveVisaResults, MAX_QUESTIONS } from "@/lib/visa-oracle/storage";
import {
  isCallingVisa,
  isGuarantorRequired,
} from "@/lib/visa-oracle/nationalities";
import type { QuizAnswers, VisaRecommendation } from "@/lib/visa-oracle/types";
import {
  trackVisaQuizCompleted,
  trackVisaResultViewed,
  trackVisaCallingBlock,
} from "@/lib/analytics";

export default function ResultPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [visas, setVisas] = useState<VisaRecommendation[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const nationality = searchParams.get("nationality") ?? "";
  const purpose = searchParams.get("purpose") as QuizAnswers["purpose"] | null;
  const duration = searchParams.get("duration") as
    | QuizAnswers["duration"]
    | null;
  const family = searchParams.get("family") as QuizAnswers["family"] | null;

  const answersValid = nationality && purpose && duration && family;

  useEffect(() => {
    if (!answersValid) {
      router.replace("/visa-oracle/quiz");
      return;
    }

    const answers: QuizAnswers = {
      nationality,
      purpose: purpose!,
      duration: duration!,
      family: family!,
    };

    trackVisaQuizCompleted(answers);

    recommendVisas(answers)
      .then((res) => {
        setVisas(res.visas);
        setSessionId(res.session_id);
        saveVisaResults(res.visas);
        if (res.visas.length > 0) {
          trackVisaResultViewed(res.visas[0].visa_name, res.visas.length);
        }
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.",
        );
      })
      .finally(() => {
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleAskQuestion() {
    const params = new URLSearchParams({
      nationality,
      purpose: purpose ?? "",
      duration: duration ?? "",
      family: family ?? "",
      session_id: sessionId,
    });
    router.push(`/visa-oracle/chat?${params.toString()}`);
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-20">
        <div
          className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: "var(--bz-accent)" }}
          role="status"
          aria-label="Loading"
        />
        <p className="text-sm" style={{ color: "var(--tx-secondary)" }}>
          Finding the best visas for your profile…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-6 py-20 text-center">
        <p className="text-sm" style={{ color: "var(--tx-secondary)" }}>
          {error}
        </p>
        <button
          onClick={() => router.replace("/visa-oracle/quiz")}
          className="px-6 py-2 rounded-lg text-sm font-semibold transition-opacity hover:opacity-80"
          style={{ backgroundColor: "var(--bz-accent)", color: "#fff" }}
        >
          Start over
        </button>
      </div>
    );
  }

  // Calling Visa — restricted nationalities
  if (!loading && !error && nationality && isCallingVisa(nationality)) {
    trackVisaCallingBlock(nationality);
    return (
      <div className="flex flex-col gap-6 max-w-2xl mx-auto py-8">
        <div
          className="p-6 rounded-xl border"
          style={{
            backgroundColor: "var(--bz-elevated)",
            borderColor: "rgba(212, 132, 90, 0.3)",
          }}
        >
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🛂</span>
            <h2
              className="text-xl font-bold"
              style={{ color: "var(--bz-accent)" }}
            >
              Calling Visa Required
            </h2>
          </div>
          <div
            className="flex flex-col gap-3"
            style={{ color: "var(--tx-secondary)" }}
          >
            <p className="leading-relaxed">
              As a national of{" "}
              <strong style={{ color: "var(--tx-primary)" }}>
                {nationality}
              </strong>
              , you are required to apply for a{" "}
              <strong style={{ color: "var(--tx-primary)" }}>
                Calling Visa
              </strong>{" "}
              to enter Indonesia.
            </p>
            <p className="leading-relaxed">
              This is a special visa category that requires:
            </p>
            <ul className="list-disc list-inside space-y-1.5 text-sm">
              <li>
                A corporate guarantor (sponsor company) based in Indonesia
              </li>
              <li>
                Mandatory interview at the Directorate General of Immigration in
                Jakarta
              </li>
              <li>
                Pre-approval from Indonesian Immigration before visa issuance
              </li>
              <li>Processing time is typically longer than standard visas</li>
            </ul>
            <p className="leading-relaxed text-sm mt-2">
              The Calling Visa process is complex and cannot be done
              independently. Our immigration team has experience handling these
              cases and can guide you through every step.
            </p>
          </div>
        </div>

        <a
          href={`https://wa.me/6281338051876?text=Hello%20Bali%20Zero!%20I%20am%20from%20${encodeURIComponent(nationality)}%20and%20I%20need%20a%20Calling%20Visa.%20Can%20you%20help%20me?`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
          style={{ backgroundColor: "#25d366", color: "#fff" }}
        >
          Talk to our team on WhatsApp
        </a>

        <button
          onClick={() => router.replace("/visa-oracle/quiz")}
          className="text-sm underline transition-opacity hover:opacity-70 self-center"
          style={{ color: "var(--tx-secondary)" }}
        >
          Start over
        </button>
      </div>
    );
  }

  // Guarantor required — restricted but possible
  if (!loading && !error && nationality && isGuarantorRequired(nationality)) {
    return (
      <div className="flex flex-col gap-6 max-w-2xl mx-auto">
        <div
          className="p-5 rounded-xl border mb-2"
          style={{
            backgroundColor: "var(--bz-elevated)",
            borderColor: "rgba(212, 132, 90, 0.25)",
          }}
        >
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xl">⚠️</span>
            <h3 className="font-semibold" style={{ color: "var(--bz-accent)" }}>
              Sponsor Required
            </h3>
          </div>
          <p
            className="text-sm leading-relaxed"
            style={{ color: "var(--tx-secondary)" }}
          >
            As a national of{" "}
            <strong style={{ color: "var(--tx-primary)" }}>
              {nationality}
            </strong>
            , your visa application requires a company sponsor (guarantor) in
            Indonesia. Processing may take longer and requires additional
            verification. Our team can act as your sponsor.
          </p>
        </div>

        {/* Still show normal results below the warning */}
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl sm:text-3xl font-bold">
            Your visa recommendations
          </h1>
          <p className="text-sm" style={{ color: "var(--tx-secondary)" }}>
            You have{" "}
            <span style={{ color: "var(--bz-accent)" }}>
              {MAX_QUESTIONS} free questions
            </span>{" "}
            to ask about these visa options.
          </p>
        </div>

        <div className="flex flex-col gap-4">
          {visas.map((visa, index) => (
            <VisaCard
              key={`${visa.visa_name}-${index}`}
              visa={visa}
              rank={index + 1}
              onAskQuestion={handleAskQuestion}
            />
          ))}
        </div>

        <div
          className="flex flex-col sm:flex-row items-center gap-4 p-6 rounded-xl"
          style={{ backgroundColor: "var(--bz-elevated)" }}
        >
          <div className="flex flex-col gap-1 flex-1">
            <p className="font-semibold text-sm">
              Need sponsorship assistance?
            </p>
            <p
              className="text-xs leading-relaxed"
              style={{ color: "var(--tx-secondary)" }}
            >
              Our team can act as your corporate guarantor and handle the entire
              visa process.
            </p>
          </div>
          <a
            href={`https://wa.me/6281338051876?text=${encodeURIComponent(
              `Hello Bali Zero! I need sponsorship help. Nationality: ${nationality}, Purpose: ${purpose ?? ""}. Can you act as my guarantor?`,
            )}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 px-5 py-2.5 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
            style={{ backgroundColor: "#25d366", color: "#fff" }}
          >
            WhatsApp us
          </a>
        </div>
      </div>
    );
  }

  if (visas.length === 0) {
    return (
      <div className="flex flex-col items-center gap-6 py-20 text-center max-w-lg mx-auto">
        <h2 className="text-xl font-bold">No matching visas found</h2>
        <p
          className="text-sm leading-relaxed"
          style={{ color: "var(--tx-secondary)" }}
        >
          We could not find a visa matching your profile. Speak directly with
          our team on WhatsApp — they will help you find the right solution.
        </p>
        <a
          href={`https://wa.me/6281338051876?text=${encodeURIComponent(
            `Hello Bali Zero! I used the Visa Oracle but no matching visa was found. Nationality: ${nationality}, Purpose: ${purpose ?? ""}, Duration: ${duration ?? ""}. Can you help me?`,
          )}`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-6 py-3 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
          style={{ backgroundColor: "#25d366", color: "#fff" }}
        >
          Contact us on WhatsApp
        </a>
        <button
          onClick={() => router.replace("/visa-oracle/quiz")}
          className="text-sm underline transition-opacity hover:opacity-70"
          style={{ color: "var(--tx-secondary)" }}
        >
          Start over
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl sm:text-3xl font-bold">
          Your visa recommendations
        </h1>
        <div className="flex items-center gap-3">
          <p className="text-sm" style={{ color: "var(--tx-secondary)" }}>
            You have{" "}
            <span style={{ color: "var(--bz-accent)" }}>
              {MAX_QUESTIONS} free questions
            </span>{" "}
            to ask about these visa options.
          </p>
          <button
            onClick={() => router.replace("/visa-oracle/quiz")}
            className="text-xs underline transition-opacity hover:opacity-70 whitespace-nowrap"
            style={{ color: "var(--tx-secondary)" }}
          >
            Change answers
          </button>
        </div>
      </div>

      {/* Visa cards */}
      <div className="flex flex-col gap-4">
        {visas.map((visa, index) => (
          <VisaCard
            key={`${visa.visa_name}-${index}`}
            visa={visa}
            rank={index + 1}
            onAskQuestion={handleAskQuestion}
          />
        ))}
      </div>

      {/* Bottom WhatsApp CTA — with pre-filled context */}
      <div
        className="flex flex-col sm:flex-row items-center gap-4 p-6 rounded-xl"
        style={{ backgroundColor: "var(--bz-elevated)" }}
      >
        <div className="flex flex-col gap-1 flex-1">
          <p className="font-semibold text-sm">Ready to apply?</p>
          <p
            className="text-xs leading-relaxed"
            style={{ color: "var(--tx-secondary)" }}
          >
            Our Bali Zero immigration specialists are ready to help you start
            your application today.
          </p>
        </div>
        <a
          href={`https://wa.me/6281338051876?text=${encodeURIComponent(
            `Hello Bali Zero! I used the Visa Oracle. Nationality: ${nationality}, Purpose: ${purpose ?? ""}, Duration: ${duration ?? ""}. My top recommendation is ${visas[0]?.visa_name ?? "a visa"}. Can you help me apply?`,
          )}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 px-5 py-2.5 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90"
          style={{ backgroundColor: "#25d366", color: "#fff" }}
        >
          WhatsApp us
        </a>
      </div>
    </div>
  );
}
