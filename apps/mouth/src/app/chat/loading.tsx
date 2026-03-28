import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-4">
        <Skeleton variant="text" width={160} height={28} />
      </div>
      <div className="flex-1 space-y-4 p-4">
        <div className="flex gap-3">
          <Skeleton variant="circular" width={36} height={36} />
          <Skeleton variant="rounded" width={240} height={64} />
        </div>
        <div className="flex gap-3 flex-row-reverse">
          <Skeleton variant="circular" width={36} height={36} />
          <Skeleton variant="rounded" width={200} height={48} />
        </div>
        <div className="flex gap-3">
          <Skeleton variant="circular" width={36} height={36} />
          <Skeleton variant="rounded" width={280} height={80} />
        </div>
        <div className="flex gap-3 flex-row-reverse">
          <Skeleton variant="circular" width={36} height={36} />
          <Skeleton variant="rounded" width={160} height={48} />
        </div>
      </div>
      <div className="border-t p-4">
        <Skeleton variant="rounded" width="100%" height={48} />
      </div>
    </div>
  );
}
