import { Skeleton } from "@/components/ui/skeleton";

export default function SecuritySettingsLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="space-y-1">
        <Skeleton variant="text" width={180} height={28} />
        <Skeleton variant="text" width={300} />
      </div>
      <div className="rounded-xl border divide-y">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between p-4">
            <div className="space-y-1">
              <Skeleton variant="text" width={160} />
              <Skeleton variant="text" width={240} />
            </div>
            <Skeleton variant="rounded" width={60} height={28} />
          </div>
        ))}
      </div>
    </div>
  );
}
