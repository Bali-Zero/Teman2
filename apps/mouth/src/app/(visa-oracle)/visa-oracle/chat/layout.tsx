import type { Metadata } from "next";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Ask Visa Oracle — AI visa assistant",
  description:
    "Ask follow-up questions about Indonesian visas. AI-powered answers backed by 68,000+ legal documents.",
  alternates: {
    canonical: `${baseUrl}/visa-oracle/chat`,
  },
  robots: { index: false, follow: true },
};

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return children;
}
