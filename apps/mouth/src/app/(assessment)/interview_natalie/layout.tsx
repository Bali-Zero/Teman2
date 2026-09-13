import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Round 2 Written Assessment",
  description:
    "Bali Zero — Finance & Client Services Coordinator, round 2 written assessment.",
  robots: { index: false, follow: false, nocache: true },
};

export default function InterviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
