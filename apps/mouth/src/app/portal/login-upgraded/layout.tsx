import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Login — Bali Zero",
  robots: { index: false, follow: false },
};

export default function LoginUpgradedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
