import { Skeleton } from "@/components/ui/skeleton";

/**
 * WS3 slice 9 (GARUDA Day Edition): skeleton cards read the theme surface
 * (--bz-card / --bz-border / --glass-rim) instead of the dark-only
 * rgba(30,30,35,0.7) glass + white hairlines, which rendered as muddy dark
 * islands on operative-light paper.
 */
export default function CompanyDetailLoading() {
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

      {/* Main Card */}
      <div
        className="rounded-xl border p-6 space-y-5"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-start gap-4">
          <Skeleton variant="rounded" width={64} height={64} />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" width={220} height={22} />
            <Skeleton variant="text" width={160} height={14} />
            <Skeleton variant="rounded" width={90} height={24} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <Skeleton variant="text" width={80} height={10} />
              <Skeleton variant="text" width={140} />
            </div>
          ))}
        </div>
      </div>

      {/* Documents Section */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <Skeleton variant="text" width={140} height={20} />
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border p-3 flex items-center gap-3"
              style={{
                background: "var(--glass-rim)",
                borderColor: "var(--bz-border)",
              }}
            >
              <Skeleton variant="rounded" width={32} height={32} />
              <div className="flex-1 space-y-1">
                <Skeleton variant="text" width={160} />
                <Skeleton variant="text" width={100} height={10} />
              </div>
              <Skeleton variant="rounded" width={32} height={32} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
