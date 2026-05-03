import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="rounded" width={120} height={40} />
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-6 space-y-2">
            <Skeleton variant="text" width={100} />
            <Skeleton variant="text" width={60} height={32} />
            <Skeleton variant="text" width={80} />
          </div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-6 space-y-4">
          <Skeleton variant="text" width={150} />
          <Skeleton variant="rounded" height={200} />
        </div>
        <div className="rounded-lg border p-6 space-y-4">
          <Skeleton variant="text" width={150} />
          <Skeleton variant="rounded" height={200} />
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-lg border p-6 space-y-4">
        <Skeleton variant="text" width={150} />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton variant="circular" width={40} height={40} />
            <div className="flex-1 space-y-2">
              <Skeleton variant="text" width={200} />
              <Skeleton variant="text" width={120} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
