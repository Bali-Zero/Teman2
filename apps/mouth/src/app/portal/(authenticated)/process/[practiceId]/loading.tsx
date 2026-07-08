import { Skeleton } from '@/components/ui/skeleton';

export default function PracticeDetailLoading() {
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

      {/* Timeline */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton variant="circular" width={28} height={28} />
            <Skeleton variant="text" width={220} />
          </div>
        ))}
      </div>
    </div>
  );
}
