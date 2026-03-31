"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface TeamMember {
  id: string | null;
  email: string;
  full_name: string;
  role: string;
  avatar_url: string | null;
}

async function fetchTeamMembers(): Promise<TeamMember[]> {
  const res = await api.get<{ members: TeamMember[] }>("/api/team/members");
  return res.members;
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
  const options = members.map((m) => ({
    value: m.email,
    label: m.full_name,
    avatar: m.avatar_url ?? undefined,
  }));
  return { options, ...rest };
}
