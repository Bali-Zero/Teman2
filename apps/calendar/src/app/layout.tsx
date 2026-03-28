import type { Metadata } from 'next';
import { Geist } from 'next/font/google';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import './globals.css';

const geist = Geist({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Bali Zero Calendar',
  description: 'Bali Zero Team Calendar',
};

async function getSession(): Promise<boolean> {
  const cookieStore = await cookies();
  const token =
    cookieStore.get('nz_access_token')?.value ||
    cookieStore.get('balizero_session')?.value ||
    cookieStore.get('auth_token')?.value ||
    cookieStore.get('next-auth.session-token')?.value ||
    cookieStore.get('__Secure-next-auth.session-token')?.value;

  return !!token;
}

const apps = [
  { name: 'Kita', href: 'https://kita.balizero.com', emoji: '🏠' },
  { name: 'Mail', href: 'https://mail.balizero.com', emoji: '✉️' },
  {
    name: 'Calendar',
    href: 'https://calendar.balizero.com',
    emoji: '📅',
    active: true,
  },
  { name: 'Drive', href: 'https://drive.balizero.com', emoji: '💾' },
  { name: 'Knowledge', href: 'https://knowledge.balizero.com', emoji: '📚' },
];

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const isAuthenticated = await getSession();

  if (!isAuthenticated) {
    redirect('https://kita.balizero.com/login?redirect=https://calendar.balizero.com');
  }

  return (
    <html lang="it">
      <body className={geist.className}>
        {/* Top bar */}
        <header
          style={{
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 16px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
            backgroundColor: 'rgba(0,0,0,0.05)',
            position: 'sticky',
            top: 0,
            zIndex: 40,
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
            <span style={{ color: 'var(--bz-text-3)', fontSize: 14 }}>/</span>
            <span
              style={{
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--bz-text-1)',
              }}
            >
              Calendar
            </span>
          </a>

          {/* Center: spacer */}
          <div style={{ flex: 1 }} />

          {/* Right: App switcher */}
          <div className="relative group" style={{ position: 'relative' }}>
            <button
              style={{
                padding: '8px',
                borderRadius: '8px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                opacity: 0.6,
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
              className="app-switcher-dropdown"
              style={{
                position: 'absolute',
                right: 0,
                top: '100%',
                marginTop: '4px',
                width: '192px',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '12px',
                boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
                padding: '8px',
                zIndex: 50,
                backgroundColor: '#1a1a1a',
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
                    color: app.active ? '#fff' : 'rgba(255,255,255,0.6)',
                    backgroundColor: app.active ? 'rgba(255,255,255,0.1)' : 'transparent',
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
        <main style={{ height: 'calc(100vh - 48px)' }}>{children}</main>

        <style>{`
          .relative.group .app-switcher-dropdown {
            opacity: 0;
            visibility: hidden;
            transition: opacity 150ms, visibility 150ms;
          }
          .relative.group:hover .app-switcher-dropdown,
          .relative.group:focus-within .app-switcher-dropdown {
            opacity: 1;
            visibility: visible;
          }
        `}</style>
      </body>
    </html>
  );
}
