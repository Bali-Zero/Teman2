import { Skeleton } from '@/components/ui/skeleton';

export default function TeamManagementLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <Skeleton variant="text" width={200} height={32} />

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-5 space-y-2">
            <Skeleton variant="text" width={80} />
            <Skeleton variant="text" width={40} height={28} />
          </div>
        ))}
      </div>

      {/* Team Members */}
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 flex items-center gap-4">
            <Skeleton variant="circular" width={48} height={48} />
            <div className="flex-1 space-y-2">
              <Skeleton variant="text" width={160} />
              <Skeleton variant="text" width={120} />
            </div>
            <Skeleton variant="rounded" width={60} height={24} />
          </div>
        ))}
      </div>
    </div>
  );
}
