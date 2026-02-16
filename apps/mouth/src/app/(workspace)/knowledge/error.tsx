"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { BookOpen, RefreshCw } from "lucide-react";

export default function KnowledgeError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Knowledge Error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-destructive/10">
        <BookOpen className="h-10 w-10 text-destructive" />
      </div>

      <div className="mt-6 text-center space-y-2 max-w-md">
        <h2 className="text-2xl font-semibold tracking-tight">
          Knowledge Base Error
        </h2>
        <p className="text-muted-foreground">
          We couldn&apos;t load the knowledge base. Please check your connection
          and try again.
        </p>
      </div>

      <div className="mt-8 flex gap-3">
        <Button onClick={() => reset()} variant="default">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    </div>
  );
}
