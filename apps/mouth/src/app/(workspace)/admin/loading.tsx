import { Skeleton } from '@/components/ui/skeleton';

export default function AdminLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Skeleton variant="rounded" width={36} height={36} />
        <Skeleton variant="text" width={200} height={28} />
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-5 space-y-2">
            <Skeleton variant="text" width={100} />
            <Skeleton variant="text" width={50} height={28} />
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-lg border p-6 space-y-4">
        <Skeleton variant="text" width={150} />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton variant="circular" width={36} height={36} />
            <div className="flex-1 space-y-2">
              <Skeleton variant="text" width={180} />
              <Skeleton variant="text" width={100} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
