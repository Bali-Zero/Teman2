import type { Metadata } from "next";
import Link from "next/link";
import { ConsentBanner } from "@/components/visa-oracle/ConsentBanner";

export const metadata: Metadata = {
  title: "Visa Oracle — What visa do you need for Indonesia?",
  description:
    "AI-powered visa guidance for Indonesia. Get instant, accurate answers about Indonesian visas built on 68,000+ legal documents.",
};

export default function VisaOracleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        backgroundColor: "var(--bz-base)",
        color: "var(--tx-primary)",
      }}
    >
      {/* Header */}
      <header
        style={{
          backgroundColor: "var(--bz-elevated)",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
          >
            <span
              className="text-xl font-semibold tracking-tight"
              style={{ color: "var(--bz-accent)" }}
            >
              Visa Oracle
            </span>
            <span className="text-sm" style={{ color: "var(--tx-secondary)" }}>
              by Bali Zero
            </span>
          </Link>
          <Link
            href="https://balizero.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm hover:opacity-80 transition-opacity"
            style={{ color: "var(--tx-secondary)" }}
          >
            balizero.com
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer
        style={{
          backgroundColor: "var(--bz-elevated)",
          borderTop: "1px solid rgba(255,255,255,0.08)",
          color: "var(--tx-secondary)",
        }}
      >
        <div className="max-w-5xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-center sm:text-left">
            Visa Oracle provides general informational guidance about Indonesian
            immigration. This is not legal advice.
          </p>
          <div className="flex items-center gap-4 text-xs">
            <Link
              href="/privacy"
              className="hover:opacity-80 transition-opacity"
              style={{ color: "var(--tx-secondary)" }}
            >
              Privacy
            </Link>
            <Link
              href="/terms"
              className="hover:opacity-80 transition-opacity"
              style={{ color: "var(--tx-secondary)" }}
            >
              Terms
            </Link>
          </div>
        </div>
      </footer>

      <ConsentBanner />
    </div>
  );
}
