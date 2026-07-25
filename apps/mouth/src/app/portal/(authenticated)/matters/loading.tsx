import { Skeleton } from "@/components/ui/skeleton";

export default function MattersLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="text" width={280} className="mt-2" />
      </section>

      {/* Matter Cards */}
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border overflow-hidden"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
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
          </div>
        ))}
      </div>
    </div>
  );
}
