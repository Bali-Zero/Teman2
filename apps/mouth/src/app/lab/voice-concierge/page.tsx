import { notFound } from "next/navigation";
import { VoiceConciergeClient } from "@/app/(workspace)/intelligence/voice-concierge/VoiceConciergeClient";

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

export default function LabVoiceConciergePage(): React.JSX.Element {
  if (!isPrototypeEnabled()) {
    notFound();
  }

  return <VoiceConciergeClient />;
}
