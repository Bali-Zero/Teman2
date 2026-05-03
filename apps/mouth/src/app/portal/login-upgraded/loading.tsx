import { Skeleton } from "@/components/ui/skeleton";

export default function LoginUpgradedLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <Skeleton variant="circular" width={64} height={64} className="mx-auto" />
          <Skeleton variant="text" width={180} height={28} className="mx-auto" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} variant="rounded" width="100%" height={44} />
          ))}
        </div>
        <Skeleton variant="rounded" width="100%" height={44} />
      </div>
    </div>
  );
}
