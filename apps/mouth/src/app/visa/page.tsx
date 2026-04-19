"use client";

import {
  AppBranchSelector,
  AppFrame,
  AppTrustStrip,
  useFunnelApp,
} from "@balizero/core";

export default function VisaEntryPage() {
  const tracker = useFunnelApp("visa_clock"); // logical "entry"; branch event fires on click

  return (
    <AppFrame
      title="Visa Check"
      subtitle="Answer one question. We'll show you what comes next — or hand you off to the team."
      trustStrip={
        <AppTrustStrip
          items={[
            { value: "5,021", label: "visas filed since 2019" },
            { value: "24+", label: "visa categories supported" },
            { value: "4.8", label: "average first-reply hours on WhatsApp" },
          ]}
        />
      }
    >
      <AppBranchSelector
        question="Are you already in Indonesia?"
        options={[
          {
            id: "clock",
            title: "Yes, I'm here",
            description:
              "Tell us which visa and when you entered. We'll build your expiry timeline with 5 checkpoints.",
            href: "/visa/clock",
          },
          {
            id: "match",
            title: "No, I'm planning",
            description:
              "Answer 4 short questions. We'll recommend the right visa and show the cost.",
            href: "/visa/match",
          },
        ]}
        onSelect={(opt) => tracker.branchSelected(opt.id)}
      />
    </AppFrame>
  );
}
