import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bali Zero Knowledge",
  description: "Knowledge Base — Visa, Company, Tax, TKA, KBLI Blueprints",
};

async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();

  const nzToken = cookieStore.get("nz_access_token");
  if (nzToken?.value) return true;

  // Legacy fallbacks
  const bzSession = cookieStore.get("bz_session");
  if (bzSession?.value) return true;

  const accessToken = cookieStore.get("access_token");
  if (accessToken?.value) return true;

  return false;
}

const apps = [
  { name: "Kita", href: "https://kita.balizero.com", emoji: "🏠" },
  { name: "Mail", href: "https://mail.balizero.com", emoji: "✉️" },
  { name: "Calendar", href: "https://calendar.balizero.com", emoji: "📅" },
  { name: "Drive", href: "https://drive.balizero.com", emoji: "💾" },
  {
    name: "Knowledge",
    href: "https://knowledge.balizero.com",
    emoji: "📚",
    active: true,
  },
];

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const authenticated = await isAuthenticated();

  if (!authenticated) {
    redirect(
      "https://kita.balizero.com/login?redirect=https://knowledge.balizero.com",
    );
  }

  return (
    <html lang="en">
      <body className="bg-[var(--background)] text-[var(--foreground)] min-h-screen">
        {/* Top bar */}
        <header
          style={{
            height: "48px",
            display: "flex",
            alignItems: "center",
            padding: "0 16px",
            gap: "8px",
            borderBottom: "1px solid var(--bz-border)",
            background: "var(--bz-elevated)",
            position: "sticky",
            top: 0,
            zIndex: 40,
          }}
        >
          <a
            href="https://kita.balizero.com"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              textDecoration: "none",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              width={22}
              height={22}
              style={{ borderRadius: "50%", flexShrink: 0 }}
            />
            <span style={{ color: "var(--bz-text-3)", fontSize: 14 }}>/</span>
            <span
              style={{
                fontSize: "13px",
                fontWeight: 500,
                color: "var(--bz-text-1)",
              }}
            >
              Knowledge
            </span>
          </a>
          <div style={{ flex: 1 }} />

          {/* App switcher */}
          <div className="relative group">
            <button
              className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
              title="Switch app"
            >
              {/* 3x3 grid icon */}
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <rect x="3" y="3" width="4" height="4" rx="0.5" />
                <rect x="10" y="3" width="4" height="4" rx="0.5" />
                <rect x="17" y="3" width="4" height="4" rx="0.5" />
                <rect x="3" y="10" width="4" height="4" rx="0.5" />
                <rect x="10" y="10" width="4" height="4" rx="0.5" />
                <rect x="17" y="10" width="4" height="4" rx="0.5" />
                <rect x="3" y="17" width="4" height="4" rx="0.5" />
                <rect x="10" y="17" width="4" height="4" rx="0.5" />
                <rect x="17" y="17" width="4" height="4" rx="0.5" />
              </svg>
            </button>

            {/* Dropdown */}
            <div
              className="absolute right-0 top-full mt-1 w-48 bg-[var(--background-elevated)] border border-[var(--border)] rounded-xl shadow-2xl
              opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-50 p-2"
            >
              {apps.map((app) => (
                <a
                  key={app.name}
                  href={app.href}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    app.active
                      ? "text-[var(--foreground)] bg-[var(--background-secondary)] font-medium"
                      : "text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-secondary)]"
                  }`}
                >
                  <span>{app.emoji}</span>
                  <span>{app.name}</span>
                </a>
              ))}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
