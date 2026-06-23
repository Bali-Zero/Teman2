import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { VoiceConciergeClient } from "@/app/(workspace)/intelligence/voice-concierge/VoiceConciergeClient";
import {
  canAccessVoiceConciergeHeaders,
  isProduction,
} from "@/lib/server/voice-concierge-auth";

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

export default async function LabVoiceConciergePage(): Promise<React.JSX.Element> {
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
