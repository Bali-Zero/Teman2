'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { ShieldAlert, Loader2, Lock } from 'lucide-react';

// Only the founder can access analytics
const FOUNDER_EMAIL = 'zero@balizero.com';

export default function AnalyticsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string>('');

  useEffect(() => {
    const checkAccess = async () => {
      try {
        const profile = await api.getProfile();
        setUserEmail(profile.email);

        if (profile.email.toLowerCase() === FOUNDER_EMAIL) {
          setIsAuthorized(true);
        } else {
          setIsAuthorized(false);
        }
      } catch {
        // Not authenticated - redirect to login
        router.push('/login');
        return;
      } finally {
        setIsLoading(false);
      }
    };

    checkAccess();
  }, [router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <Loader2 className="w-10 h-10 animate-spin text-[var(--accent)]" />
            <Lock className="w-4 h-4 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[var(--accent)]" />
          </div>
          <p className="text-[var(--foreground-muted)]">Verifying access...</p>
        </div>
      </div>
    );
  }

  if (!isAuthorized) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-6 p-8 rounded-2xl border border-[var(--error)]/20 bg-gradient-to-b from-[var(--error)]/5 to-transparent max-w-md text-center">
          <div className="p-4 rounded-full bg-[var(--error)]/10">
            <ShieldAlert className="w-12 h-12 text-[var(--error)]" />
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-[var(--foreground)]">Access Denied</h1>
            <p className="text-[var(--foreground-muted)]">
              The Analytics Dashboard is restricted to the Founder only.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-[var(--background-elevated)] border border-[var(--border)] w-full">
            <p className="text-xs text-[var(--foreground-muted)] mb-1">Logged in as:</p>
            <p className="font-medium text-[var(--foreground)]">{userEmail}</p>
          </div>

          <div className="flex gap-3 w-full">
            <button
              onClick={() => router.push('/dashboard')}
              className="flex-1 px-4 py-2.5 rounded-lg bg-[var(--accent)] text-white font-medium hover:opacity-90 transition-opacity"
            >
              Go to Dashboard
            </button>
            <button
              onClick={() => router.push('/chat')}
              className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border)] text-[var(--foreground)] font-medium hover:bg-[var(--background-elevated)] transition-colors"
            >
              Open Chat
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
