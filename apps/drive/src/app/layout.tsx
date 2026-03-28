import type { Metadata } from 'next';
import { Providers } from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'Bali Zero Drive',
  description: 'Gestione documenti aziendali — Bali Zero',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="h-screen overflow-hidden bg-[#0c0c0e] text-[#f1f1f1]">
        <Providers>
          <AuthGate>
            <AppShell>{children}</AppShell>
          </AuthGate>
        </Providers>
      </body>
    </html>
  );
}

/**
 * Auth gate: checks for JWT cookie on .balizero.com domain.
 * If no valid session → redirects to kita.balizero.com/login?redirect=drive.balizero.com
 * Runs as a Server Component — redirect happens before any JS is sent to the browser.
 */
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import type { ReactNode } from 'react';

async function AuthGate({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const token =
    cookieStore.get('nz_access_token')?.value || cookieStore.get('nz_auth_token')?.value;

  if (!token) {
    const redirectUrl = encodeURIComponent(
      process.env.NEXT_PUBLIC_APP_URL || 'https://drive.balizero.com'
    );
    redirect(`https://kita.balizero.com/login?redirect=${redirectUrl}`);
  }

  return <>{children}</>;
}

const apps = [
  { name: 'Kita', href: 'https://kita.balizero.com', emoji: '🏠' },
  { name: 'Mail', href: 'https://mail.balizero.com', emoji: '✉️' },
  { name: 'Calendar', href: 'https://calendar.balizero.com', emoji: '📅' },
  {
    name: 'Drive',
    href: 'https://drive.balizero.com',
    emoji: '💾',
    active: true,
  },
  { name: 'Knowledge', href: 'https://knowledge.balizero.com', emoji: '📚' },
];

function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      {/* Top bar */}
      <header
        style={{
          height: '48px',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: '8px',
          borderBottom: '1px solid var(--bz-border, rgba(255,255,255,0.055))',
          background: 'var(--bz-elevated, #131315)',
          position: 'relative',
          zIndex: 40,
          flexShrink: 0,
        }}
      >
        {/* Left: BZ Logo + App name */}
        <a
          href="https://kita.balizero.com"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            textDecoration: 'none',
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/static/balizero-logo-clean.png"
            alt="Bali Zero"
            width={22}
            height={22}
            style={{ borderRadius: '50%', flexShrink: 0 }}
          />
          <span style={{ color: 'var(--bz-text-3, #575350)', fontSize: 14 }}>/</span>
          <span
            style={{
              fontSize: '13px',
              fontWeight: 500,
              color: 'var(--bz-text-1, #edeae4)',
            }}
          >
            Drive
          </span>
        </a>
        <div style={{ flex: 1 }} />

        {/* Right: App switcher */}
        <div className="drive-app-switcher" style={{ position: 'relative' }}>
          <button
            className="drive-switcher-btn"
            style={{
              padding: '8px',
              borderRadius: '8px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              color: 'rgba(241,241,241,0.5)',
            }}
            title="Switch app"
            aria-label="Cambia applicazione"
          >
            {/* 3x3 grid icon */}
            <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
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
            className="drive-switcher-dropdown"
            style={{
              position: 'absolute',
              right: 0,
              top: '100%',
              marginTop: '4px',
              width: '192px',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '12px',
              boxShadow: '0 25px 50px rgba(0,0,0,0.6)',
              padding: '8px',
              zIndex: 50,
              backgroundColor: '#1e1e20',
            }}
          >
            {apps.map((app) => (
              <a
                key={app.name}
                href={app.href}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  textDecoration: 'none',
                  color: app.active ? '#f1f1f1' : 'rgba(241,241,241,0.55)',
                  backgroundColor: app.active ? 'rgba(255,255,255,0.08)' : 'transparent',
                }}
              >
                <span>{app.emoji}</span>
                <span>{app.name}</span>
              </a>
            ))}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main style={{ height: 'calc(100vh - 48px)', overflow: 'auto' }}>{children}</main>

      <style>{`
        .drive-app-switcher .drive-switcher-dropdown {
          opacity: 0;
          visibility: hidden;
          transition: opacity 150ms, visibility 150ms;
        }
        .drive-app-switcher:hover .drive-switcher-dropdown,
        .drive-app-switcher:focus-within .drive-switcher-dropdown {
          opacity: 1;
          visibility: visible;
        }
      `}</style>
    </>
  );
}
