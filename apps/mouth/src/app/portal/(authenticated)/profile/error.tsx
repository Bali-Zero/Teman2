'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { User, RefreshCw } from 'lucide-react';
import { logger } from '@/lib/logger';

export default function ProfileError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error('Portal profile page error', {}, error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 p-6 text-center">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-full"
        style={{ background: 'rgba(244,63,94,0.1)' }}
      >
        <User className="h-8 w-8" style={{ color: 'var(--neon-rose)' }} />
      </div>
      <div className="space-y-2 max-w-sm">
        <h2 className="text-xl font-semibold">Profile unavailable</h2>
        <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
          We couldn&apos;t load your profile. Please try again.
        </p>
      </div>
      <Button onClick={() => reset()}>
        <RefreshCw className="mr-2 h-4 w-4" />
        Try Again
      </Button>
    </div>
  );
}
