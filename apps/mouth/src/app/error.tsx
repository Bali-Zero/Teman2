'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-[var(--background)] text-[var(--foreground)] gap-6">
      <div className="flex items-center justify-center w-24 h-24 rounded-full bg-[var(--error)]/10">
        <AlertTriangle className="w-12 h-12 text-[var(--error)]" />
      </div>

      <div className="text-center space-y-2 max-w-md px-4">
        <h1 className="text-3xl font-bold tracking-tight">Something went wrong!</h1>
        <p className="text-[var(--foreground-secondary)]">
          We apologize for the inconvenience. An unexpected error has occurred.
        </p>
        {process.env.NODE_ENV === 'development' && (
          <div className="mt-4 p-4 bg-[var(--background-secondary)] rounded-lg text-left overflow-auto max-h-48 text-xs font-mono text-[var(--error)]">
            {error.message}
          </div>
        )}
      </div>

      <div className="flex gap-4">
        <Button onClick={() => reset()} variant="default">
          Try again
        </Button>
        <Button onClick={() => window.location.reload()} variant="outline">
          Reload Page
        </Button>
      </div>
    </div>
  );
}
