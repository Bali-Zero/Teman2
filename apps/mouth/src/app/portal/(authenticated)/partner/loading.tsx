import { Skeleton } from "@/components/ui/skeleton";

// WS3 final slice (GARUDA Day Edition): skeleton surfaces read --bz-card /
// --bz-border (were dark-only rgba(30,30,35,0.7) + white/5 hairlines).
const SKELETON_SURFACE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
} as const;

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
            style={SKELETON_SURFACE}
          />
        ))}
      </div>

      {/* List rows */}
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border p-4 h-20 animate-pulse"
            style={SKELETON_SURFACE}
          />
        ))}
      </div>
    </div>
  );
}
