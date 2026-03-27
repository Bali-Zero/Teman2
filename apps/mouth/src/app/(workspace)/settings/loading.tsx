import { Skeleton } from '@/components/ui/skeleton';

export default function SettingsLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Skeleton variant="rounded" width={36} height={36} />
        <div className="space-y-2">
          <Skeleton variant="text" width={150} height={28} />
          <Skeleton variant="text" width={200} />
        </div>
      </div>

      {/* Settings Sections */}
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-lg border p-6 space-y-4">
          <Skeleton variant="text" width={140} height={24} />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, j) => (
              <div key={j} className="flex items-center justify-between">
                <Skeleton variant="text" width={160} />
                <Skeleton variant="rounded" width={200} height={36} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
