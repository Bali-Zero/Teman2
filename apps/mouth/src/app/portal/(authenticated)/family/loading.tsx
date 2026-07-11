import { Skeleton } from '@/components/ui/skeleton';

export default function FamilyLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="text" width={280} className="mt-2" />
      </section>

      {/* Member rows */}
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border p-4 flex items-center gap-3"
            style={{
              background: 'rgba(30,30,35,0.7)',
              borderColor: 'rgba(255,255,255,0.05)',
            }}
          >
            <Skeleton variant="circular" width={36} height={36} />
            <div className="flex-1 space-y-1">
              <Skeleton variant="text" width={160} />
              <Skeleton variant="text" width={100} height={10} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
