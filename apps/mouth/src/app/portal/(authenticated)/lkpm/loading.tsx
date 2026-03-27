import { Skeleton } from '@/components/ui/skeleton';

export default function LkpmLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="text" width={280} className="mt-2" />
      </section>

      {/* Info Banner */}
      <Skeleton variant="rounded" height={60} />

      {/* Reports List */}
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border p-4"
            style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
          >
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <Skeleton variant="text" width={160} height={18} />
                <Skeleton variant="text" width={100} height={10} />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton variant="rounded" width={70} height={24} />
                <Skeleton variant="rounded" width={80} height={32} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
