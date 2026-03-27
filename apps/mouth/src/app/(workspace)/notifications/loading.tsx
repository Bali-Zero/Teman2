import { Skeleton } from '@/components/ui/skeleton';

export default function NotificationsLoading() {
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

      {/* Stats Row */}
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={80} />
            <Skeleton variant="text" width={40} height={28} />
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-lg border overflow-hidden">
        <div className="p-4 space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton variant="circular" width={32} height={32} />
              <div className="flex-1 space-y-2">
                <Skeleton variant="text" width={200} />
                <Skeleton variant="text" width={140} />
              </div>
              <Skeleton variant="rounded" width={60} height={24} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
