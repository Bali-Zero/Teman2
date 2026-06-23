import { headers } from "next/headers";
import { notFound } from "next/navigation";
import {
  canAccessVoiceConciergeHeaders,
  isProduction,
} from "@/lib/server/voice-concierge-auth";
import { VoiceConciergeClient } from "./VoiceConciergeClient";

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

export default async function VoiceConciergePage(): Promise<React.JSX.Element> {
  if (!isPrototypeEnabled()) {
    notFound();
  }

  if (
    isProduction() &&
    !(await canAccessVoiceConciergeHeaders(await headers()))
  ) {
    notFound();
  }

  return <VoiceConciergeClient />;
}
