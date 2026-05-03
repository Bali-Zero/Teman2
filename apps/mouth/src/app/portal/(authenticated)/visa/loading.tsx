import { Skeleton } from '@/components/ui/skeleton';

export default function VisaLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="text" width={260} className="mt-2" />
      </section>

      {/* Current Visa Card */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <div className="flex items-center justify-between">
          <Skeleton variant="text" width={140} height={24} />
          <Skeleton variant="rounded" width={90} height={28} />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between py-2">
              <Skeleton variant="text" width={100} />
              <Skeleton variant="text" width={140} />
            </div>
          ))}
        </div>
        <Skeleton variant="rounded" height={72} />
      </div>

      {/* Documents */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <Skeleton variant="text" width={160} height={24} />
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border p-3"
              style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.05)' }}
            >
              <div className="flex items-center gap-3">
                <Skeleton variant="rounded" width={36} height={36} />
                <div className="flex-1 space-y-1">
                  <Skeleton variant="text" width={160} />
                  <Skeleton variant="text" width={100} height={10} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
