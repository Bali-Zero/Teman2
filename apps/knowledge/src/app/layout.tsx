import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bali Zero Knowledge",
  description: "Knowledge Base — Visa, Company, Tax, TKA, KBLI Blueprints",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-[var(--background)] text-[var(--foreground)] min-h-screen">
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  );
}

// Auth gate: checks for auth token in cookie/localStorage.
// If missing, redirects to kita.balizero.com/login
function AuthGate({ children }: { children: React.ReactNode }) {
  return <AuthGateClient>{children}</AuthGateClient>;
}

// The actual client-side auth check lives in a separate component
// to avoid making the root layout a client component
import AuthGateClient from "@/components/AuthGateClient";
