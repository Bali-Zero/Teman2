import { Skeleton } from "@/components/ui/skeleton";

// WS3 slice 4 (GARUDA Day Edition): skeleton cards read --bz-card /
// --bz-border / --glass-rim (was rgba(30,30,35,0.7) + white rgba hairlines
// — near-black panels flashing on the warm-paper page).
export default function ProcessLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="text" width={280} className="mt-2" />
      </section>

      {/* Process Cards */}
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border overflow-hidden"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
            {/* Card Header */}
            <div
              className="flex items-center justify-between px-5 py-4 border-b"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <div className="flex items-center gap-3">
                <Skeleton variant="circular" width={36} height={36} />
                <div className="space-y-1">
                  <Skeleton variant="text" width={160} />
                  <Skeleton variant="text" width={100} height={10} />
                </div>
              </div>
              <Skeleton variant="rounded" width={70} height={24} />
            </div>

            {/* Documents */}
            <div className="p-4 space-y-2">
              {Array.from({ length: 2 }).map((_, j) => (
                <div
                  key={j}
                  className="rounded-lg border p-3 flex items-center gap-3"
                  style={{
                    background: "var(--glass-rim)",
                    borderColor: "var(--bz-border)",
                  }}
                >
                  <Skeleton variant="rounded" width={32} height={32} />
                  <div className="flex-1 space-y-1">
                    <Skeleton variant="text" width={140} />
                    <Skeleton variant="text" width={80} height={10} />
                  </div>
                  <Skeleton variant="rounded" width={80} height={28} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
