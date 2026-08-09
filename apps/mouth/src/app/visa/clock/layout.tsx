import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Visa Stay Calculator & Overstay Clock | Bali Zero",
  description:
    "Track your Bali stay duration, visa expiration dates, and extension deadlines automatically.",
  alternates: {
    canonical: "https://balizero.com/visa/clock",
  },
};

export default function VisaClockLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
