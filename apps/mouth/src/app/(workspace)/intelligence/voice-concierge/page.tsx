import { notFound } from "next/navigation";
import { VoiceConciergeClient } from "./VoiceConciergeClient";

function isPrototypeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" ||
    process.env.VOICE_CONCIERGE_LAB_ENABLED === "true"
  );
}

export default function VoiceConciergePage(): React.JSX.Element {
  if (!isPrototypeEnabled()) {
    notFound();
  }

  return <VoiceConciergeClient />;
}
