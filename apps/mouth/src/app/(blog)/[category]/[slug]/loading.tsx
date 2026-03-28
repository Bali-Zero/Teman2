import { Skeleton } from '@/components/ui/skeleton';

export default function ArticleLoading() {
  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {/* Hero section skeleton */}
      <div className="max-w-4xl mx-auto px-4 pt-16 pb-8">
        <Skeleton variant="rounded" width={80} height={24} />
        <div className="mt-4">
          <Skeleton variant="text" width="80%" height={40} />
        </div>
        <div className="mt-2">
          <Skeleton variant="text" width="60%" height={40} />
        </div>
        <div className="flex items-center gap-4 mt-6">
          <Skeleton variant="circular" width={40} height={40} />
          <div className="space-y-1">
            <Skeleton variant="text" width={120} />
            <Skeleton variant="text" width={80} />
          </div>
        </div>
      </div>

      {/* Cover image skeleton */}
      <div className="max-w-6xl mx-auto px-4">
        <Skeleton variant="rounded" height={320} />
      </div>

      {/* Content skeleton */}
      <div className="max-w-4xl mx-auto px-4 py-12 space-y-4">
        <Skeleton variant="text" width="100%" />
        <Skeleton variant="text" width="95%" />
        <Skeleton variant="text" width="88%" />
        <Skeleton variant="text" width="92%" />
        <div className="py-4" />
        <Skeleton variant="text" width="100%" />
        <Skeleton variant="text" width="85%" />
        <Skeleton variant="text" width="90%" />
      </div>
    </div>
  );
}
