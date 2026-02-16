import { Skeleton } from "@/components/ui/skeleton";

export default function DocumentsLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton variant="text" width={200} height={32} />
          <Skeleton variant="text" width={280} />
        </div>
        <div className="flex gap-2">
          <Skeleton variant="rounded" width={120} height={40} />
          <Skeleton variant="rounded" width={140} height={40} />
        </div>
      </div>

      {/* Breadcrumbs + Filters */}
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={200} />
        <div className="flex items-center gap-2">
          <Skeleton variant="rounded" width={36} height={36} />
          <Skeleton variant="rounded" width={36} height={36} />
          <Skeleton variant="rounded" width={120} height={36} />
        </div>
      </div>

      {/* Documents Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border p-4 space-y-3 hover:border-accent/50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <Skeleton variant="rounded" width={48} height={48} />
              <Skeleton variant="circular" width={24} height={24} />
            </div>
            <Skeleton variant="text" width="100%" />
            <Skeleton variant="text" width={100} />
            <div className="flex items-center justify-between pt-2">
              <Skeleton variant="text" width={60} />
              <Skeleton variant="circular" width={28} height={28} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
