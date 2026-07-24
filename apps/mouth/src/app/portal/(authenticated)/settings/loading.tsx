import { Skeleton } from "@/components/ui/skeleton";

export default function PortalSettingsLoading() {
  return (
    <div className="space-y-6 p-2">
      {/* Header */}
      <section>
        <Skeleton variant="text" width={140} height={32} />
        <Skeleton variant="text" width={260} className="mt-2" />
      </section>

      {/* Settings Sections */}
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <Skeleton variant="text" width={160} height={20} />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, j) => (
              <div key={j} className="flex items-center justify-between">
                <div className="space-y-1">
                  <Skeleton variant="text" width={140} />
                  <Skeleton variant="text" width={200} height={10} />
                </div>
                <Skeleton variant="rounded" width={48} height={24} />
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Save Button */}
      <div className="flex justify-end">
        <Skeleton variant="rounded" width={120} height={40} />
      </div>
    </div>
  );
}
