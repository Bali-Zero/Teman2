import type { Metadata } from "next";
import "./oracle.css";

// Prototype — public post-merge but never indexed (spec hard-constraint 5).
// No NavShell, no site chrome: an immersive, standalone full-viewport
// experience with its own footer disclaimer (rendered by OracleShell).
export const metadata: Metadata = {
  title: "Visa Oracle — Prototype | Bali Zero",
  description:
    "A demonstration decision tree for Indonesian visa eligibility. Sample data only — not a government service, not an approval.",
  robots: { index: false, follow: false },
};

export default function VisaOracleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
