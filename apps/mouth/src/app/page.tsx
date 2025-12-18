'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Check if user is authenticated
    if (api.isAuthenticated()) {
      router.push('/dashboard');
    } else {
      router.push('/login');
    }
  }, [router]);

  // Loading state while redirecting
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
      <div className="animate-pulse">
        <div className="w-16 h-16 rounded-full bg-[var(--background-secondary)]" />
      </div>
    </div>
  );
}
