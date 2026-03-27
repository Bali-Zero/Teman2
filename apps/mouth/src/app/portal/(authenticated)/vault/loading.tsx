import { Skeleton } from '@/components/ui/skeleton';

export default function VaultLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={160} height={32} />
        <Skeleton variant="text" width={240} className="mt-2" />
      </section>

      {/* Category Tabs */}
      <div className="flex gap-2 flex-wrap">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" width={90} height={32} />
        ))}
      </div>

      {/* Document Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border p-4 space-y-3"
            style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
          >
            <div className="flex items-center gap-3">
              <Skeleton variant="rounded" width={40} height={40} />
              <div className="flex-1 space-y-1">
                <Skeleton variant="text" width={120} />
                <Skeleton variant="text" width={80} height={10} />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Skeleton variant="rounded" width={60} height={20} />
              <Skeleton variant="rounded" width={32} height={32} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
