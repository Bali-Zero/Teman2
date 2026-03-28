import { Skeleton } from "@/components/ui/skeleton";

export default function LKPMSubmitLoading() {
  return (
    <div className="space-y-6 p-6 max-w-2xl">
      <Skeleton variant="text" width={200} height={32} />
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton variant="text" width={120} />
            <Skeleton variant="rounded" width="100%" height={40} />
          </div>
        ))}
      </div>
      <div className="flex gap-3 pt-2">
        <Skeleton variant="rounded" width={120} height={40} />
        <Skeleton variant="rounded" width={100} height={40} />
      </div>
    </div>
  );
}
