import { Skeleton } from "@/components/ui/skeleton";

export default function ProcessDetailLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-4">
        <Skeleton variant="circular" width={64} height={64} />
        <div className="space-y-2">
          <Skeleton variant="text" width={240} height={28} />
          <Skeleton variant="text" width={160} />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={100} />
            <Skeleton variant="text" width={180} height={24} />
          </div>
        ))}
      </div>
    </div>
  );
}
