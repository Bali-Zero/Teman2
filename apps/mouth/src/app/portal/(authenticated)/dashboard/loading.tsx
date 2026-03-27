import { Skeleton } from '@/components/ui/skeleton';

export default function PortalDashboardLoading() {
  return (
    <div className="space-y-8 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={220} height={36} />
        <Skeleton variant="text" width={200} className="mt-2" />
      </section>

      {/* Status Cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border p-5 space-y-3"
            style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.06)' }}
          >
            <div className="flex justify-between items-start">
              <Skeleton variant="text" width={80} height={12} />
              <Skeleton variant="circular" width={20} height={20} />
            </div>
            <Skeleton variant="text" width={120} height={28} />
            <Skeleton variant="text" width={80} height={10} />
          </div>
        ))}
      </section>

      {/* Timeline */}
      <section className="space-y-4">
        <Skeleton variant="text" width={100} height={24} />
        <div className="space-y-4 ml-4 border-l-2" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="pl-6 relative">
              <div
                className="absolute -left-[9px] top-1 w-4 h-4 rounded-full"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              />
              <div
                className="rounded-lg border p-4 space-y-2"
                style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.06)' }}
              >
                <Skeleton variant="text" width={100} height={10} />
                <Skeleton variant="text" width={180} height={16} />
                <Skeleton variant="text" width={240} height={12} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
