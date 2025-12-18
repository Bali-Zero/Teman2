'use client';

import { Clock } from 'lucide-react';

interface SchedulerStatusProps {
  status: {
    is_running?: boolean;
    tasks?: Array<{
      name: string;
      next_run: string;
      interval: string;
      enabled: boolean;
    }>;
  } | string | null;
}

export function SchedulerStatus({ status }: SchedulerStatusProps) {
  if (!status) return null;

  return (
    <div className="bg-[var(--background-elevated)] border border-[var(--border)] rounded-xl p-4">
      <div className="flex items-center gap-2 text-[var(--foreground)] font-medium">
        <Clock className="w-4 h-4 text-[var(--accent)]" />
        Scheduler
      </div>
      <div className="mt-2 text-sm text-[var(--foreground-muted)]">
        {typeof status === 'string' ? status : 'Scheduler status available'}
      </div>
    </div>
  );
}

