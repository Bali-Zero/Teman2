'use client';

import { useEffect, useState } from 'react';

function getToken(): string | null {
  if (typeof document === 'undefined') return null;
  // Check cookies
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (
      name === 'nz_access_token' ||
      name === 'auth_token' ||
      name === 'access_token' ||
      name === 'token'
    ) {
      return decodeURIComponent(value || '');
    }
  }
  // Check localStorage
  try {
    return localStorage.getItem('auth_token') || localStorage.getItem('token');
  } catch {
    return null;
  }
}

export default function AuthGateClient({ children }: { children: React.ReactNode }) {
  const [checked, setChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (token) {
      setAuthenticated(true);
    } else {
      const current = encodeURIComponent(window.location.href);
      window.location.href = `https://kita.balizero.com/login?redirect=${current}`;
    }
    setChecked(true);
  }, []);

  if (!checked || !authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent,#d4845a)] border-t-transparent" />
          <p className="text-[var(--foreground-muted)] text-sm">Verifying access...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Top bar */}
      <header className="border-b border-[var(--border)] bg-[var(--background-secondary)] px-6 py-3 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-4">
          <a
            href="https://kita.balizero.com"
            className="text-xs text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors flex items-center gap-1"
          >
            ← Back to Kita
          </a>
          <span className="text-[var(--border)]">|</span>
          <a href="/" className="text-sm font-semibold text-[var(--foreground)]">
            Bali Zero Knowledge
          </a>
        </div>
        <a
          href="https://kita.balizero.com"
          className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
          title="App switcher"
          aria-label="Cambia applicazione"
        >
          <svg
            className="w-5 h-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
        </a>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
    </div>
  );
}
