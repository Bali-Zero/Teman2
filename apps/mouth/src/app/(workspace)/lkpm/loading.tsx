import { Skeleton } from '@/components/ui/skeleton';

export default function LkpmLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={160} height={32} />
        <Skeleton variant="rounded" width={120} height={36} />
      </div>
      <div className="flex gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" width={90} height={32} />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={200} />
            <Skeleton variant="text" width={140} />
          </div>
        ))}
      </div>
    </div>
  );
}
