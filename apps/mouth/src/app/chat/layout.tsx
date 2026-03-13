import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Zantara AI | Your Business Assistant in Bali",
  description:
    "AI-powered business assistant for Indonesia. Get instant answers about visas, company setup, KBLI codes, tax compliance, and more.",
  openGraph: {
    title: "Zantara AI | Your Business Assistant in Bali",
    description:
      "AI-powered business assistant for Indonesia. Visas, company setup, KBLI codes, and more.",
    url: "https://zantara.balizero.com",
  },
};

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
