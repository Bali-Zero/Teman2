import { Skeleton } from '@/components/ui/skeleton';

export default function PartnerLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="text" width={280} className="mt-2" />
      </section>

      {/* Stat Cards */}
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-xl border p-4 h-24 animate-pulse"
            style={{
              background: 'rgba(30,30,35,0.7)',
              borderColor: 'rgba(255,255,255,0.05)',
            }}
          />
        ))}
      </div>

      {/* List rows */}
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border p-4 h-20 animate-pulse"
            style={{
              background: 'rgba(30,30,35,0.7)',
              borderColor: 'rgba(255,255,255,0.05)',
            }}
          />
        ))}
      </div>
    </div>
  );
}
