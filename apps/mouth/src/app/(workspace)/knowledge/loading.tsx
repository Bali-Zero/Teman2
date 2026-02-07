import { Skeleton } from '@/components/ui/skeleton';

export default function KnowledgeLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton variant="text" width={200} height={32} />
          <Skeleton variant="text" width={280} />
        </div>
        <Skeleton variant="rounded" width={140} height={40} />
      </div>

      {/* Search + Filters */}
      <div className="flex items-center gap-4">
        <Skeleton variant="rounded" width={320} height={40} />
        <Skeleton variant="rounded" width={120} height={40} />
        <Skeleton variant="rounded" width={100} height={40} />
      </div>

      {/* Categories */}
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" width={100} height={32} />
        ))}
      </div>

      {/* Knowledge Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border p-5 space-y-3 hover:border-accent/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Skeleton variant="rounded" width={48} height={48} />
              <Skeleton variant="rounded" width={60} height={24} />
            </div>
            <Skeleton variant="text" width="100%" />
            <Skeleton variant="text" width="90%" />
            <Skeleton variant="text" width={120} />
            <div className="flex items-center gap-2 pt-2">
              <Skeleton variant="circular" width={24} height={24} />
              <Skeleton variant="text" width={100} />
              <Skeleton variant="text" width={60} className="ml-auto" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
