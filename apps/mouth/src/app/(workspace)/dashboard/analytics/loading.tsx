import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardAnalyticsLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={220} height={32} />
        <div className="flex gap-2">
          <Skeleton variant="rounded" width={100} height={36} />
          <Skeleton variant="rounded" width={100} height={36} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border p-4 space-y-2">
            <Skeleton variant="text" width={80} />
            <Skeleton variant="text" width={120} height={28} />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border p-4">
          <Skeleton variant="text" width={160} className="mb-4" />
          <Skeleton variant="rounded" width="100%" height={220} />
        </div>
        <div className="rounded-xl border p-4">
          <Skeleton variant="text" width={140} className="mb-4" />
          <Skeleton variant="rounded" width="100%" height={220} />
        </div>
      </div>
    </div>
  );
}
