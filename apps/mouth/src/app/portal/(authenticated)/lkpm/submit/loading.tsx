import { Skeleton } from "@/components/ui/skeleton";

// Day skeleton surfaces (WS3 slice 8): token card + hairline border, not the
// old dark rgba(30,30,35,0.7) glass.
const SKELETON_SECTION_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
} as const;

export default function LkpmSubmitLoading() {
  return (
    <div className="space-y-6 p-2 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Skeleton variant="rounded" width={32} height={32} />
        <div className="space-y-1">
          <Skeleton variant="text" width={200} height={28} />
          <Skeleton variant="text" width={260} height={12} />
        </div>
      </div>

      {/* Period Selection */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={SKELETON_SECTION_STYLE}
      >
        <Skeleton variant="text" width={160} height={20} />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton variant="rounded" height={40} />
          <Skeleton variant="rounded" height={40} />
        </div>
      </div>

      {/* Capital Table */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={SKELETON_SECTION_STYLE}
      >
        <Skeleton variant="text" width={220} height={20} />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="grid grid-cols-3 gap-3">
              <Skeleton variant="text" width="90%" />
              <Skeleton variant="rounded" height={36} />
              <Skeleton variant="rounded" height={36} />
            </div>
          ))}
        </div>
      </div>

      {/* Employment */}
      <div
        className="rounded-xl border p-6 space-y-4"
        style={SKELETON_SECTION_STYLE}
      >
        <Skeleton variant="text" width={180} height={20} />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton variant="rounded" height={40} />
          <Skeleton variant="rounded" height={40} />
        </div>
      </div>

      {/* Submit */}
      <Skeleton variant="rounded" height={48} />
    </div>
  );
}
