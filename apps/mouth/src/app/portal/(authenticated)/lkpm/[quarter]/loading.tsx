import { Skeleton } from '@/components/ui/skeleton';

export default function LkpmQuarterLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Back + Header */}
      <div className="flex items-center gap-3">
        <Skeleton variant="rounded" width={32} height={32} />
        <div className="space-y-1">
          <Skeleton variant="text" width={200} height={28} />
          <Skeleton variant="text" width={140} height={12} />
        </div>
      </div>

      {/* Status Card */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <div className="flex items-center justify-between">
          <Skeleton variant="text" width={160} height={24} />
          <Skeleton variant="rounded" width={90} height={28} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="p-4 rounded-lg"
              style={{ background: 'rgba(255,255,255,0.03)' }}
            >
              <Skeleton variant="text" width={80} height={10} className="mb-2" />
              <Skeleton variant="text" width={100} height={22} />
            </div>
          ))}
        </div>
      </div>

      {/* Capital Section */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <Skeleton variant="text" width={200} height={20} />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between py-2">
            <Skeleton variant="text" width={140} />
            <Skeleton variant="text" width={120} />
          </div>
        ))}
      </div>
    </div>
  );
}
