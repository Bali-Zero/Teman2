import { Skeleton } from '@/components/ui/skeleton';

export default function ProfileLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={160} height={32} />
        <Skeleton variant="text" width={260} className="mt-2" />
      </section>

      {/* 3-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border overflow-hidden"
            style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
          >
            {/* Card Header */}
            <div
              className="flex items-center gap-2 px-4 py-3 border-b"
              style={{ borderColor: 'rgba(255,255,255,0.05)' }}
            >
              <Skeleton variant="circular" width={20} height={20} />
              <Skeleton variant="text" width={120} />
            </div>

            {/* Card Content */}
            <div className="p-4 space-y-4">
              {i === 0 && (
                <>
                  {/* Team member */}
                  <div
                    className="flex items-center gap-3 p-3 rounded-lg"
                    style={{ background: 'rgba(255,255,255,0.03)' }}
                  >
                    <Skeleton variant="circular" width={40} height={40} />
                    <div className="space-y-1">
                      <Skeleton variant="text" width={110} />
                      <Skeleton variant="text" width={80} height={10} />
                    </div>
                  </div>
                  {/* Info rows */}
                  {Array.from({ length: 5 }).map((_, j) => (
                    <div key={j} className="flex items-start gap-2">
                      <Skeleton variant="circular" width={16} height={16} className="mt-0.5" />
                      <div className="space-y-1">
                        <Skeleton variant="text" width={60} height={10} />
                        <Skeleton variant="text" width={140} />
                      </div>
                    </div>
                  ))}
                </>
              )}
              {i === 1 && (
                <>
                  <Skeleton variant="rounded" className="aspect-[3/2]" />
                  {Array.from({ length: 3 }).map((_, j) => (
                    <div
                      key={j}
                      className="flex items-center justify-between p-2 rounded-lg"
                      style={{ background: 'rgba(255,255,255,0.03)' }}
                    >
                      <Skeleton variant="text" width={80} height={10} />
                      <Skeleton variant="text" width={100} />
                    </div>
                  ))}
                </>
              )}
              {i === 2 && (
                <>
                  <Skeleton variant="rounded" className="aspect-[3/2]" />
                  <div className="space-y-2">
                    <Skeleton variant="text" width={120} height={10} />
                    {Array.from({ length: 3 }).map((_, j) => (
                      <div key={j} className="flex items-center gap-2">
                        <Skeleton variant="circular" width={16} height={16} />
                        <Skeleton variant="text" width={160} />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
