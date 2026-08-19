import { Skeleton } from "@/components/ui/skeleton";

export default function SecondHomeLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton variant="text" width={180} height={28} />
          <Skeleton variant="text" width={320} />
        </div>
        <Skeleton variant="rounded" width={120} height={36} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-xl border p-4 space-y-3">
            <Skeleton variant="text" width={100} />
            <Skeleton variant="rounded" height={64} />
            <Skeleton variant="rounded" height={64} />
          </div>
        ))}
      </div>
    </div>
  );
}
