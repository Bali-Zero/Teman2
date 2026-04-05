"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { VisaCard } from "@/components/visa-oracle/VisaCard";
import { recommendVisas } from "@/lib/visa-oracle/api";
import { saveVisaResults, MAX_QUESTIONS } from "@/lib/visa-oracle/storage";
import type { QuizAnswers, VisaRecommendation } from "@/lib/visa-oracle/types";

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

    recommendVisas(answers)
      .then((res) => {
        setVisas(res.visas);
        setSessionId(res.session_id);
        saveVisaResults(res.visas);
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
          href="https://wa.me/6281338051876"
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
        <p className="text-sm" style={{ color: "var(--tx-secondary)" }}>
          You have{" "}
          <span style={{ color: "var(--bz-accent)" }}>{MAX_QUESTIONS} free questions</span> to
          ask about these visa options.
        </p>
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

      {/* Bottom WhatsApp CTA */}
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
          href="https://wa.me/6281338051876"
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
