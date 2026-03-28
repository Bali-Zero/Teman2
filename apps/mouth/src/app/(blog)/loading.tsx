import { Skeleton } from '@/components/ui/skeleton';

export default function BlogLoading() {
  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Hero skeleton */}
      <div className="max-w-6xl mx-auto px-4 py-12">
        <Skeleton variant="text" width={300} height={40} />
        <div className="mt-2">
          <Skeleton variant="text" width={500} />
        </div>
      </div>

      {/* Featured article skeleton */}
      <div className="max-w-6xl mx-auto px-4">
        <Skeleton variant="rounded" height={320} />
      </div>

      {/* Article grid skeleton */}
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-white/5 overflow-hidden">
              <Skeleton variant="rounded" height={180} />
              <div className="p-5 space-y-3">
                <Skeleton variant="rounded" width={80} height={24} />
                <Skeleton variant="text" width="90%" height={24} />
                <Skeleton variant="text" width="70%" />
                <div className="flex gap-3 pt-2">
                  <Skeleton variant="text" width={60} />
                  <Skeleton variant="text" width={60} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
