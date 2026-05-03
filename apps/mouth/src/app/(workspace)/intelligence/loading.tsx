import { Skeleton } from "@/components/ui/skeleton";

export default function IntelligenceLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton variant="text" width={220} height={32} />
          <Skeleton variant="text" width={300} />
        </div>
        <Skeleton variant="rounded" width={140} height={40} />
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton
            key={i}
            variant="text"
            width={100}
            height={40}
            className="rounded-t-lg"
          />
        ))}
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={80} />
            <Skeleton variant="text" width={50} height={28} />
            <Skeleton variant="text" width={60} />
          </div>
        ))}
      </div>

      {/* Main Content Area */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Feed */}
        <div className="lg:col-span-2 space-y-4">
          <Skeleton variant="text" width={120} />
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-lg border p-4 space-y-3">
              <div className="flex items-center gap-3">
                <Skeleton variant="circular" width={40} height={40} />
                <div className="flex-1 space-y-1">
                  <Skeleton variant="text" width={150} />
                  <Skeleton variant="text" width={100} />
                </div>
              </div>
              <Skeleton variant="text" width="90%" />
              <Skeleton variant="text" width="70%" />
              <div className="flex items-center gap-2 pt-2">
                <Skeleton variant="rounded" width={80} height={24} />
                <Skeleton variant="rounded" width={80} height={24} />
              </div>
            </div>
          ))}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Skeleton variant="text" width={100} />
          <div className="rounded-lg border p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-2">
                <Skeleton variant="circular" width={8} height={8} />
                <Skeleton variant="text" width={140} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
