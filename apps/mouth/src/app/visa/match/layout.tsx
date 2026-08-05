import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Visa Match Assessment | Bali Zero",
  description:
    "Get matched with the exact Indonesian visa for your travel, remote work, or residency plans.",
  alternates: {
    canonical: "https://balizero.com/visa/match",
  },
};

export default function VisaMatchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
