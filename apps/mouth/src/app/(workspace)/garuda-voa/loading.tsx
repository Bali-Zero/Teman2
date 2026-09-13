import { Skeleton } from "@/components/ui/skeleton";

export default function GarudaVoaStaffLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={260} height={32} />
      </div>
      <div className="flex gap-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} variant="rounded" width={140} height={36} />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border p-4 flex items-center gap-4"
          >
            <Skeleton variant="text" width={140} />
            <Skeleton variant="rounded" width={80} height={24} />
            <Skeleton variant="text" width={120} />
          </div>
        ))}
      </div>
    </div>
  );
}
