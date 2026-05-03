import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardRole } from "@/lib/dashboard-role";
import type {
  UseRoleMetricsResult,
  RoleWidgetData,
} from "@/types/dashboard-role.types";

export function useRoleMetrics(
  role: DashboardRole,
  userId: string,
): UseRoleMetricsResult {
  const { data, isLoading, isError } = useQuery<RoleWidgetData>({
    queryKey: ["role-metrics", role, userId],
    queryFn: () =>
      api.request<RoleWidgetData>(
        `/api/dashboard/role-metrics?role=${role}&user_id=${userId}`,
      ),
    staleTime: 30_000,
    refetchInterval: 60_000,
    enabled: !!userId,
  });

  return { data, isLoading, isError };
}
