import { Skeleton } from '@/components/ui/skeleton';

export default function AnalyticsLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={160} height={32} />
        <Skeleton variant="rounded" width={100} height={36} />
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-5 space-y-2">
            <Skeleton variant="text" width={100} />
            <Skeleton variant="text" width={60} height={28} />
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-6 space-y-4">
            <Skeleton variant="text" width={140} />
            <Skeleton variant="rounded" height={200} />
          </div>
        ))}
      </div>
    </div>
  );
}
