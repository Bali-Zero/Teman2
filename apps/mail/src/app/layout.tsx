import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mail — Bali Zero",
  description: "Bali Zero Mail Client",
  icons: { icon: "/favicon.ico" },
};

/**
 * Auth gate for mail.balizero.com
 *
 * Reads the JWT from cookies. The backend sets an httpOnly cookie on
 * `.balizero.com` so all subdomains (kita, mail, calendar, drive…)
 * share the same session without the user logging in again.
 *
 * Cookie names to check (in priority order):
 *  1. `bz_session`   — httpOnly JWT set by backend
 *  2. `access_token` — fallback (some older clients)
 *
 * If no cookie is found → redirect to kita.balizero.com/login
 */
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

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const authenticated = await isAuthenticated();

  if (!authenticated) {
    redirect(
      "https://kita.balizero.com/login?redirect=https://mail.balizero.com",
    );
  }

  return (
    <html lang="en">
      <body>
        {/* Top bar */}
        <header className="h-12 flex items-center justify-between px-4 border-b border-[var(--border)] bg-[var(--background-secondary)]">
          {/* Left: Back to Kita */}
          <a
            href="https://kita.balizero.com"
            className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            <span>Back to Kita</span>
          </a>

          {/* Center: App name */}
          <div className="flex items-center gap-2">
            <svg
              className="w-5 h-5 text-[var(--accent)]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
            <span className="text-sm font-semibold text-[var(--foreground)]">
              Mail
            </span>
          </div>

          {/* Right: App switcher */}
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
              {[
                {
                  name: "Kita",
                  href: "https://kita.balizero.com",
                  emoji: "🏠",
                },
                {
                  name: "Mail",
                  href: "https://mail.balizero.com",
                  emoji: "✉️",
                },
                {
                  name: "Calendar",
                  href: "https://calendar.balizero.com",
                  emoji: "📅",
                },
                {
                  name: "Drive",
                  href: "https://drive.balizero.com",
                  emoji: "💾",
                },
                {
                  name: "Knowledge",
                  href: "https://knowledge.balizero.com",
                  emoji: "📚",
                },
              ].map((app) => (
                <a
                  key={app.name}
                  href={app.href}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-secondary)] transition-colors"
                >
                  <span>{app.emoji}</span>
                  <span>{app.name}</span>
                </a>
              ))}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="h-[calc(100vh-3rem)]">{children}</main>
      </body>
    </html>
  );
}
