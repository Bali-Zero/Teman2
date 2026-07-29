import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Assessment",
  description: "Technical-Strategic Assessment for Bali Zero candidates",
  robots: { index: false, follow: false },
};

export default function AssessmentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
