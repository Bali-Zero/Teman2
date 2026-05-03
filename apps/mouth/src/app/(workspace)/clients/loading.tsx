import { Skeleton } from "@/components/ui/skeleton";

export default function ClientsLoading() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton variant="text" width={180} height={32} />
          <Skeleton variant="text" width={250} />
        </div>
        <Skeleton variant="rounded" width={140} height={40} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <Skeleton variant="rounded" width={280} height={40} />
        <Skeleton variant="rounded" width={120} height={40} />
        <Skeleton variant="rounded" width={100} height={40} />
      </div>

      {/* Table Header */}
      <div className="rounded-t-lg border-x border-t p-4 bg-muted/50">
        <div className="grid grid-cols-12 gap-4">
          <Skeleton variant="text" width={40} className="col-span-1" />
          <Skeleton variant="text" width={120} className="col-span-3" />
          <Skeleton variant="text" width={100} className="col-span-2" />
          <Skeleton variant="text" width={120} className="col-span-2" />
          <Skeleton variant="text" width={80} className="col-span-2" />
          <Skeleton variant="text" width={60} className="col-span-2" />
        </div>
      </div>

      {/* Table Rows */}
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="border-x border-b p-4 last:rounded-b-lg hover:bg-muted/50"
        >
          <div className="grid grid-cols-12 gap-4 items-center">
            <Skeleton
              variant="circular"
              width={32}
              height={32}
              className="col-span-1"
            />
            <div className="col-span-3 space-y-1">
              <Skeleton variant="text" width={140} />
              <Skeleton variant="text" width={100} />
            </div>
            <Skeleton variant="text" width={100} className="col-span-2" />
            <Skeleton variant="text" width={120} className="col-span-2" />
            <Skeleton
              variant="rounded"
              width={60}
              height={24}
              className="col-span-2"
            />
            <Skeleton
              variant="rounded"
              width={80}
              height={32}
              className="col-span-2"
            />
          </div>
        </div>
      ))}

      {/* Pagination */}
      <div className="flex items-center justify-between pt-4">
        <Skeleton variant="text" width={120} />
        <div className="flex items-center gap-2">
          <Skeleton variant="rounded" width={36} height={36} />
          <Skeleton variant="rounded" width={36} height={36} />
          <Skeleton variant="rounded" width={36} height={36} />
        </div>
      </div>
    </div>
  );
}
