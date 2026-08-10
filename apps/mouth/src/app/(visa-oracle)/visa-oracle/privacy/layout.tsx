import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Visa Oracle Privacy Policy",
  description:
    "How Visa Oracle processes, retains, and deletes evaluation data and optional handoff consent.",
};

export default function VisaOraclePrivacyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
