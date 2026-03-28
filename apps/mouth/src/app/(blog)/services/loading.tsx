import { Skeleton } from "@/components/ui/skeleton";

export default function ServicesLoading() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton variant="text" width={240} height={36} />
      <Skeleton variant="text" width={400} />
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton variant="text" width={200} height={24} />
            <Skeleton variant="text" width={320} />
            <Skeleton variant="text" width={280} />
          </div>
        ))}
      </div>
    </div>
  );
}
