import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-b"
        style={{ borderColor: "var(--bz-border)" }}
      >
        <Skeleton variant="circular" width={36} height={36} />
        <div className="space-y-1">
          <Skeleton variant="text" width={140} />
          <Skeleton variant="text" width={80} height={10} />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 p-4 space-y-4 overflow-hidden">
        {[80, 60, 90, 50, 70].map((w, i) => (
          <div
            key={i}
            className={`flex ${i % 2 === 0 ? "justify-start" : "justify-end"}`}
          >
            <div
              className="rounded-2xl px-4 py-3 max-w-[70%] space-y-2 border"
              style={{
                background: "var(--bz-card)",
                borderColor: "var(--bz-border)",
              }}
            >
              <Skeleton variant="text" width={`${w}%`} />
              {i % 3 === 0 && <Skeleton variant="text" width="60%" />}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 border-t"
        style={{ borderColor: "var(--bz-border)" }}
      >
        <div className="flex items-center gap-2">
          <Skeleton variant="rounded" className="flex-1" height={44} />
          <Skeleton variant="rounded" width={44} height={44} />
        </div>
      </div>
    </div>
  );
}
