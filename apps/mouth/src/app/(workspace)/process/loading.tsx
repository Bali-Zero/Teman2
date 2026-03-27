import { Skeleton } from '@/components/ui/skeleton';

export default function ProcessLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={180} height={32} />
        <div className="flex gap-2">
          <Skeleton variant="rounded" width={100} height={36} />
          <Skeleton variant="rounded" width={100} height={36} />
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" width={80} height={32} />
        ))}
      </div>

      {/* Process Cards */}
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 flex items-center gap-4">
            <Skeleton variant="circular" width={40} height={40} />
            <div className="flex-1 space-y-2">
              <Skeleton variant="text" width={200} />
              <Skeleton variant="text" width={120} />
            </div>
            <Skeleton variant="rounded" width={80} height={24} />
          </div>
        ))}
      </div>
    </div>
  );
}
