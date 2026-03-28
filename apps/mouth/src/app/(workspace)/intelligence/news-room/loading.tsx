import { Skeleton } from "@/components/ui/skeleton";

export default function NewsRoomLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={200} height={32} />
        <Skeleton variant="rounded" width={140} height={40} />
      </div>
      <div className="flex items-center gap-3">
        <Skeleton variant="rounded" width={280} height={40} />
        <Skeleton variant="rounded" width={120} height={40} />
      </div>
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 rounded-lg border p-4">
            <Skeleton variant="circular" width={40} height={40} />
            <div className="flex-1 space-y-1">
              <Skeleton variant="text" width={200} />
              <Skeleton variant="text" width={140} />
            </div>
            <Skeleton variant="rounded" width={80} height={28} />
          </div>
        ))}
      </div>
    </div>
  );
}
