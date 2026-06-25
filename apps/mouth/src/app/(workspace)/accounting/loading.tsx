import { Skeleton } from "@/components/ui/skeleton";

export default function AccountingLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="rounded" width={140} height={36} />
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={80} />
            <Skeleton variant="text" width={120} height={28} />
          </div>
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={240} />
            <Skeleton variant="text" width={160} />
          </div>
        ))}
      </div>
    </div>
  );
}
