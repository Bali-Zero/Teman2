import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ProcessTimeline } from "@/lib/api/portal/portal.types";

export function usePortalProcessTimeline(practiceId: number | null) {
  return useQuery<ProcessTimeline>({
    queryKey: ["portal", "process-timeline", practiceId],
    queryFn: () => api.portal.getProcessTimeline(practiceId!),
    enabled: !!practiceId,
    staleTime: 60_000,
  });
}
