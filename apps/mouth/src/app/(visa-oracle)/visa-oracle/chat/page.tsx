"use client";

import { useSearchParams } from "next/navigation";
import { VisaChat } from "@/components/visa-oracle/VisaChat";
import type { QuizAnswers } from "@/lib/visa-oracle/types";

export default function ChatPage() {
  const searchParams = useSearchParams();

  const nationality = searchParams.get("nationality");
  const purpose = searchParams.get("purpose") as QuizAnswers["purpose"] | null;
  const duration = searchParams.get("duration") as QuizAnswers["duration"] | null;
  const family = searchParams.get("family") as QuizAnswers["family"] | null;
  const sessionId = searchParams.get("session_id") ?? undefined;

  const quizAnswers: QuizAnswers | undefined =
    nationality && purpose && duration && family
      ? { nationality, purpose, duration, family }
      : undefined;

  return <VisaChat quizAnswers={quizAnswers} initialSessionId={sessionId} />;
}
