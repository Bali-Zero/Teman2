import { Skeleton } from "@/components/ui/skeleton";

/**
 * WS3 slice 9 (GARUDA Day Edition): skeleton cards read the theme surface
 * (--bz-card / --bz-border / --glass-rim) instead of the dark-only
 * rgba(30,30,35,0.7) glass + white hairlines, which rendered as muddy dark
 * islands on operative-light paper.
 */
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
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
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
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <Skeleton variant="text" width={160} height={24} />
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border p-3"
              style={{
                background: "var(--glass-rim)",
                borderColor: "var(--bz-border)",
              }}
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
