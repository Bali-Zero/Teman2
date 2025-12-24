'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { ShieldAlert, Loader2 } from 'lucide-react';

const FOUNDER_EMAIL = 'zero@balizero.com';

export default function AnalyticsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAccess = async () => {
      try {
        const profile = await api.getProfile();
        if (profile.email.toLowerCase() === FOUNDER_EMAIL) {
          setIsAuthorized(true);
        } else {
          setIsAuthorized(false);
        }
      } catch {
        setIsAuthorized(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAccess();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)]" />
          <p className="text-[var(--foreground-muted)]">Verifying access...</p>
        </div>
      </div>
    );
  }

  if (!isAuthorized) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4 p-8 rounded-xl border border-[var(--error)]/20 bg-[var(--error)]/5 max-w-md text-center">
          <ShieldAlert className="w-12 h-12 text-[var(--error)]" />
          <h1 className="text-xl font-bold text-[var(--foreground)]">Access Denied</h1>
          <p className="text-[var(--foreground-muted)]">
            The Analytics Dashboard is restricted to the Founder only.
          </p>
          <button
            onClick={() => router.push('/dashboard')}
            className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
