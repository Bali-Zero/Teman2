import { Skeleton } from '@/components/ui/skeleton';

export default function WhatsAppLoading() {
  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Conversation List */}
      <div className="w-80 border-r p-4 space-y-3">
        <Skeleton variant="rounded" width="100%" height={36} />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton variant="circular" width={44} height={44} />
            <div className="flex-1 space-y-2">
              <Skeleton variant="text" width={120} />
              <Skeleton variant="text" width={180} />
            </div>
          </div>
        ))}
      </div>
      {/* Chat Area */}
      <div className="flex-1 flex items-center justify-center">
        <Skeleton variant="text" width={200} />
      </div>
    </div>
  );
}
