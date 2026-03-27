import { Skeleton } from '@/components/ui/skeleton';

export default function CompaniesLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={160} height={32} />
        <Skeleton variant="text" width={240} className="mt-2" />
      </section>

      {/* Company Cards */}
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border p-5 space-y-4"
            style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <Skeleton variant="rounded" width={48} height={48} />
                <div className="space-y-1.5">
                  <Skeleton variant="text" width={180} height={20} />
                  <Skeleton variant="text" width={120} height={12} />
                </div>
              </div>
              <Skeleton variant="rounded" width={80} height={28} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} className="space-y-1">
                  <Skeleton variant="text" width={80} height={10} />
                  <Skeleton variant="text" width={120} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
