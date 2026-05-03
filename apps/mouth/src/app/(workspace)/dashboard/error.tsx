'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import Link from 'next/link';
import { logger } from '@/lib/logger';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error('Dashboard Error', {}, error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle className="h-10 w-10 text-destructive" />
      </div>

      <div className="mt-6 text-center space-y-2 max-w-md">
        <h2 className="text-2xl font-semibold tracking-tight">Dashboard Unavailable</h2>
        <p className="text-muted-foreground">
          We couldn&apos;t load your dashboard data. This might be due to a temporary connection
          issue.
        </p>
        {process.env.NODE_ENV === 'development' && (
          <div className="mt-4 p-3 bg-muted rounded-md text-left overflow-auto max-h-32 text-xs font-mono text-destructive">
            {error.message}
          </div>
        )}
      </div>

      <div className="mt-8 flex gap-3">
        <Button onClick={() => reset()} variant="default">
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
        <Link href="/">
          <Button variant="outline">
            <Home className="mr-2 h-4 w-4" />
            Go Home
          </Button>
        </Link>
      </div>
    </div>
  );
}
