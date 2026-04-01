"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface TeamMember {
  id: string | null;
  email: string;
  full_name: string;
  name: string;
  role: string;
  avatar_url: string | null;
  avatar: string | null;
}

async function fetchTeamMembers(): Promise<TeamMember[]> {
  const res = await api.get<TeamMember[] | { members: TeamMember[] }>(
    "/api/team/members",
  );
  // Backend returns array directly; handle both formats for safety
  return Array.isArray(res) ? res : res.members;
}

export function useTeamMembers() {
  return useQuery({
    queryKey: ["team-members"],
    queryFn: fetchTeamMembers,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

export function useTeamMemberOptions() {
  const { data: members = [], ...rest } = useTeamMembers();
  // Filter out portal "client" role — only show actual team members
  const options = members
    .filter((m) => m.role?.toLowerCase() !== "client")
    .map((m) => ({
      value: m.email,
      label: m.full_name || m.name,
      avatar: m.avatar_url ?? m.avatar ?? undefined,
    }));
  return { options, ...rest };
}
