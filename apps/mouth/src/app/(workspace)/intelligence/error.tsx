'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Brain, RefreshCw } from 'lucide-react';
import { logger } from '@/lib/logger';

export default function IntelligenceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error('Intelligence Error', {}, error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-destructive/10">
        <Brain className="h-10 w-10 text-destructive" />
      </div>

      <div className="mt-6 text-center space-y-2 max-w-md">
        <h2 className="text-2xl font-semibold tracking-tight">Intelligence Center Offline</h2>
        <p className="text-muted-foreground">
          The intelligence feed is currently unavailable. Our team has been notified and is working
          on a fix.
        </p>
      </div>

      <div className="mt-8 flex gap-3">
        <Button onClick={() => reset()} variant="default">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh Feed
        </Button>
      </div>
    </div>
  );
}
