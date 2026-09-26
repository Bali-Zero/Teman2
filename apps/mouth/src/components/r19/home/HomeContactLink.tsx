"use client";

import type { ReactNode } from "react";
import {
  WhatsAppLeadButton,
  FALLBACK_WA_URL,
} from "@/components/lead/WhatsAppLeadButton";

export const contactTopics = {
  general: "A general question",
  immigration: "Visas & residence",
  company: "Company setup & licensing",
  tax: "Tax & accounting",
  property: "Property due diligence",
  compliance: "Compliance & obligations",
  evoa: "E-VOA arrival planning",
  "second-home": "Second Home planning",
  portal: "Client portal access",
} as const;
export type ContactTopic = keyof typeof contactTopics;

export function HomeContactLink({
  topic,
  section,
  className,
  children,
}: {
  topic: ContactTopic;
  section: string;
  className?: string;
  children: ReactNode;
}) {
  const subject = contactTopics[topic];
  return (
    <WhatsAppLeadButton
      source="cta_handoff"
      context={{ topic, source_page: "/", section }}
      whatsappContext={[
        { label: "Topic", value: subject },
        { label: "Page", value: "Bali Zero homepage" },
      ]}
      utm={{ page: "/" }}
      fallbackHref={
        FALLBACK_WA_URL +
        "?text=" +
        encodeURIComponent(
          "Hello Bali Zero, I would like to discuss " + subject + ".",
        )
      }
      className={className}
    >
      {children}
    </WhatsAppLeadButton>
  );
}
