import type { Metadata } from "next";

// Deliberately noindex, not merely inherited from the parent layout: this
// page documents data handling for a tool that is itself SHADOW/unratified
// (see ../layout.tsx), so publicizing the policy independently of the tool
// it describes would be premature — nothing outside the tool links here,
// and a policy for an unratified prototype is not yet the stable public
// document a search index should point to. Set explicitly (not left to
// inherit) so this stays correct even if a future edit stops nesting under
// the parent layout, and so layout.test.tsx can pin it directly.
export const metadata: Metadata = {
  title: "Visa Oracle Privacy Policy",
  description:
    "How Visa Oracle processes, retains, and deletes evaluation data and optional handoff consent.",
  robots: { index: false, follow: false },
};

export default function VisaOraclePrivacyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
